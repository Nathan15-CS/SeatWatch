#!/usr/bin/env python3
"""
SeatWatch — multi-user web app (zero external dependencies).

- Any student opens the page, picks their classes, and gets a private alert
  channel (ntfy). The background poller checks ONLY the classes people asked
  for (never all of UMD — that would get us blocked), and pushes each user the
  instant one of their sections opens.

Run:   python3 app.py     (serves on http://localhost:8080)
Stdlib only -> deploys on any machine with python3, nothing to install.
"""
import base64
import hashlib
import hmac
import html
import json
import os
import re
import secrets
import shutil
import signal
import sqlite3
import threading
import smtplib
import ssl
import time
import urllib.error
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from email.message import EmailMessage
from email.utils import formataddr
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlencode, urlparse

import ca_chain         # CA intermediates colleges' own servers fail to send
import seatwatch as sw  # reuse: notify, log
import schools          # multi-school registry (UMD, Rutgers, ...)
import guardian         # reliability guardian: off | shadow (default) | enforce

try:                    # real Web Push (VAPID) — installed on the server; optional locally
    from pywebpush import webpush, WebPushException
except ImportError:     # missing lib -> push features quietly disabled, everything else runs
    webpush, WebPushException = None, Exception

try:                    # Sign in with Apple client-secret signing (ES256). The lib is
    # already on the server as pywebpush's own dependency; optional locally.
    from cryptography.hazmat.primitives import hashes as _ec_hashes, serialization as _ec_ser
    from cryptography.hazmat.primitives.asymmetric import ec as _ec_ec
    from cryptography.hazmat.primitives.asymmetric.utils import decode_dss_signature as _ec_dds
except ImportError:     # missing lib -> Apple sign-in quietly disabled
    _ec_ser = None

HERE = os.path.dirname(os.path.abspath(__file__))
# SECRETS & CONFIG come from ENVIRONMENT VARIABLES on the server — never hardcoded,
# never committed to git. The fallbacks below are safe non-secrets for local dev only.
# (When we add Stripe etc., its key lives in the server's environment, never in code.)
DB = os.environ.get("SEATWATCH_DB", os.path.join(HERE, "watches.db"))
PORT = int(os.environ.get("PORT", "8080"))
POLL_SECONDS = int(os.environ.get("POLL_SECONDS", "20"))

# --- accounts / auth (Google sign-in; secrets come from the server env) ---
SECRET = os.environ.get("SEATWATCH_SECRET") or secrets.token_hex(32)  # random fallback = dev only
GOOGLE_CLIENT_ID = os.environ.get("GOOGLE_CLIENT_ID", "")
GOOGLE_CLIENT_SECRET = os.environ.get("GOOGLE_CLIENT_SECRET", "")
BASE_URL = os.environ.get("SEATWATCH_BASE_URL", "https://seatwatchapp.com")

# --- Meta Pixel -----------------------------------------------------------------------
# DEFAULT OFF. Production sets META_PIXEL_ID explicitly in /etc/seatwatch.env; every other
# environment — a laptop, a test run, a restored backup, a future host somebody forgets to
# configure — sends Meta nothing at all. A hardcoded production id would follow the code
# everywhere it is ever copied.
META_PIXEL_ID = os.getenv("META_PIXEL_ID", "")

# autoConfig=false is the load-bearing line, not a nicety. Left on, Meta's script runs
# Automatic Advanced Matching: it scrapes the page's own form fields and sends back
# whatever looks like an email address or a phone number. SeatWatch renders BOTH — the
# signed-in address and the SMS opt-in phone box — so the default behaviour would ship
# exactly the identifiers the privacy policy promises never to share. Set BEFORE init,
# because by the time init runs the first PageView has already gone out.
# --- Content-Security-Policy ---------------------------------------------------------
# default-src 'none' with an explicit allowlist. This policy is why the Meta Pixel sent
# nothing for its first hour: connect.facebook.net was refused by script-src, fbevents.js
# never initialised, and every call — including PageView — sat queued in the browser with
# no error the server could see.
#
# The three Meta hosts are added ONLY when a pixel is configured, so an environment with
# META_PIXEL_ID unset keeps the original, tighter policy. Exact hosts, no wildcards, and
# nothing else is relaxed:
#
#   script-src  https://connect.facebook.net  loads fbevents.js
#   img-src     https://www.facebook.com      the /tr beacon, and the <noscript> pixel
#   connect-src https://www.facebook.com      the same /tr endpoint via fetch/sendBeacon,
#                                             which modern fbevents prefers over an Image
#
# connect.facebook.net is deliberately NOT in connect-src: it serves the script, and the
# script talks to www.facebook.com. Add it only if a real console violation names it.
_META_HOSTS = bool(META_PIXEL_ID)
CSP = ("default-src 'none'; "
       "style-src 'unsafe-inline' https://fonts.googleapis.com; "
       "font-src https://fonts.gstatic.com; "
       "script-src 'self' 'unsafe-inline'"
       + (" https://connect.facebook.net" if _META_HOSTS else "") + "; "
       "worker-src 'self'; "
       "connect-src 'self'"
       + (" https://www.facebook.com" if _META_HOSTS else "") + "; "
       "manifest-src 'self'; "
       "img-src 'self' data:"
       + (" https://www.facebook.com" if _META_HOSTS else "") + "; "
       "form-action 'self'; base-uri 'none'; frame-ancestors 'none'")

META_PIXEL_BASE = ("""<script>
!function(f,b,e,v,n,t,s){if(f.fbq)return;n=f.fbq=function(){n.callMethod?
n.callMethod.apply(n,arguments):n.queue.push(arguments)};if(!f._fbq)f._fbq=n;
n.push=n;n.loaded=!0;n.version='2.0';n.queue=[];t=b.createElement(e);t.async=!0;
t.src=v;s=b.getElementsByTagName(e)[0];s.parentNode.insertBefore(t,s)}(window,
document,'script','https://connect.facebook.net/en_US/fbevents.js');
fbq('set','autoConfig',false,'__PIXELID__');
fbq('init','__PIXELID__');fbq('track','PageView');</script>
<noscript><img height="1" width="1" style="display:none" alt=""
src="https://www.facebook.com/tr?id=__PIXELID__&ev=PageView&noscript=1"></noscript>"""
                   .replace("__PIXELID__", META_PIXEL_ID) if META_PIXEL_ID else "")

# --- Sign in with Apple (2nd provider; REQUIRED for the iOS app by App Store rule 4.8:
# an app offering Google login must offer Apple's too). Invisible until ALL pieces are
# in the server env: Apple issues them when the developer account exists. The private
# key is the .p8 file Apple generates (an EC P-256 PEM).
APPLE_TEAM_ID = os.environ.get("APPLE_TEAM_ID", "")
APPLE_CLIENT_ID = os.environ.get("APPLE_CLIENT_ID", "")        # the "Services ID"
APPLE_KEY_ID = os.environ.get("APPLE_KEY_ID", "")
APPLE_PRIVATE_PEM = os.environ.get("APPLE_PRIVATE_PEM", os.path.join(HERE, "apple_signin.p8"))
APPLE_ENABLED = bool(APPLE_TEAM_ID and APPLE_CLIENT_ID and APPLE_KEY_ID
                     and _ec_ser and os.path.exists(APPLE_PRIVATE_PEM))

# Operator stats endpoint (/admin/stats): AGGREGATES ONLY, never raw rows/PII. Off
# until this key is set in the server env; wrong or missing key answers a plain 404,
# indistinguishable from the route not existing.
STATS_KEY = os.environ.get("SEATWATCH_STATS_KEY", "")

# --- Android app (Trusted Web Activity). assetlinks.json is how Android verifies the
# Play-Store app is allowed to own seatwatchapp.com links. The SHA-256 fingerprint(s)
# come from the Play console AFTER the listing exists (Google re-signs the app), so
# they live in the env: empty -> the route 404s and nothing about the site changes.
TWA_PACKAGE = os.environ.get("TWA_PACKAGE", "com.seatwatchapp.app")
TWA_FINGERPRINTS = [f.strip() for f in
                    os.environ.get("TWA_SHA256_FINGERPRINTS", "").split(",") if f.strip()]
DEV_LOGIN = os.environ.get("SEATWATCH_DEV") == "1"   # local testing only, never set in prod
# Web Push (VAPID). Keys live on the server; page gets ONLY the public key.
VAPID_PUBLIC_KEY = os.environ.get("VAPID_PUBLIC_KEY", "")
VAPID_PRIVATE_PEM = os.environ.get("VAPID_PRIVATE_PEM", os.path.join(HERE, "vapid_private.pem"))
VAPID_SUBJECT = os.environ.get("VAPID_SUBJECT", "mailto:support@seatwatchapp.com")
PUSH_ENABLED = bool(VAPID_PUBLIC_KEY and webpush)

# Colleges whose servers omit their certificate's intermediate link — see ca_chain.py.
# Installed before any adapter runs, and shared with ops/sweep-schools.py so the sweep
# judges a school under the same TLS conditions the poller will actually fetch it under.
ca_chain.install(sw.log)
# --- Email alerts (the zero-setup default channel). SMTP creds come from the server env
# and work with any provider — Gmail app-password, Resend, SES, etc. If unset, email is
# quietly disabled and nothing breaks (push/ntfy still run). ---
SMTP_HOST = os.environ.get("SMTP_HOST", "")
SMTP_PORT = int(os.environ.get("SMTP_PORT", "587"))
SMTP_USER = os.environ.get("SMTP_USER", "")
SMTP_PASS = os.environ.get("SMTP_PASS", "")
SMTP_FROM = os.environ.get("SMTP_FROM", SMTP_USER)   # the visible "from" address
SUPPORT_EMAIL = os.environ.get("SUPPORT_EMAIL", "support@seatwatchapp.com")
EMAIL_ENABLED = bool(SMTP_HOST and SMTP_USER and SMTP_PASS)
SESSION_DAYS = 90
FREE_COURSES = 1                # free account: 1 class...
FREE_SECTIONS_PER_COURSE = 2    # ...and up to 2 of its sections (the REAL free tier,
                                # matching the site copy). Paid tiers watch ALL sections.
PAID_MAX_SECTIONS = 400         # bot-sanity ceiling on a paid all-sections course (a
                                # real course never has this many; never a pricing limit)

# --- Paid tiers (Nathan-locked ladder). Ships DORMANT behind PAID_ENABLED: until that
# env flag is "1", effective_tier() is always 0 (free) and the /pricing + Stripe routes
# 404, so the free campaign is untouched. Entitlement = ONE-TIME per registration cycle
# (not a subscription): paid access lasts PAID_TERM_DAYS from purchase, then reverts to
# free. Upgrades charge only the DELTA. ---
PAID_ENABLED = os.environ.get("PAID_ENABLED") == "1"
PAID_TERM_DAYS = int(os.environ.get("PAID_TERM_DAYS", "150"))   # ~one reg+add/drop cycle
TIER_COURSES = {0: 1, 1: 1, 2: 2, 3: 5}                        # courses allowed per tier
TIER_PRICE_CENTS = {1: 1995, 2: 2495, 3: 2995}                 # one-time, USD cents
TIER_NAME = {0: "Free", 1: "1 course, unlimited sections",
             2: "2 courses, unlimited sections",
             3: "5 courses, unlimited sections"}
# Stripe (Checkout hosted — card data NEVER touches this server). All keys from env;
# test keys first, live at launch. Nathan provides them; never hardcode.
STRIPE_SECRET_KEY = os.environ.get("STRIPE_SECRET_KEY", "")
STRIPE_PUBLISHABLE_KEY = os.environ.get("STRIPE_PUBLISHABLE_KEY", "")
STRIPE_WEBHOOK_SECRET = os.environ.get("STRIPE_WEBHOOK_SECRET", "")
PAID_LIVE = bool(PAID_ENABLED and STRIPE_SECRET_KEY and STRIPE_WEBHOOK_SECRET)

# --- SMS alerts (Twilio) — ships DORMANT behind SMS_ENABLED (default off): until that
# flag is "1" no SMS is ever sent, the opt-in UI renders nothing and the /sms routes 404.
# Go-live is a SEPARATE gate from the code existing: A2P 10DLC registration + Twilio
# prepaid balance with auto-recharge OFF (the only ceiling no code bug can bypass) +
# Nathan's explicit go. SMS is CONSENT-gated, NOT tier-gated (enforced inside send_sms,
# not at call sites) — free students are texted too, because a free tier that texts you
# is the reason anyone signs up. That removes the "every recipient already paid ~$20"
# argument that used to make volume self-funding by construction, so cost is now bounded
# by MECHANISM instead: one text per watch ever, a per-user daily cap, a daily dollar
# ceiling, and a velocity breaker. Those are the real ceiling — do not treat the tier as
# one. Every cap below is DERIVED from the alert_log ledger at check
# time, never held in memory: the poller restarts on every deploy, and an in-memory
# counter would let a crashing runaway loop reset its own circuit breaker. ---
SMS_ENABLED = os.environ.get("SMS_ENABLED") == "1"
TWILIO_SID = os.environ.get("TWILIO_ACCOUNT_SID", "")
TWILIO_TOKEN = os.environ.get("TWILIO_AUTH_TOKEN", "")
TWILIO_FROM = os.environ.get("TWILIO_FROM", "")          # E.164 number or Messaging Service SID
SMS_LIVE = bool(SMS_ENABLED and TWILIO_SID and TWILIO_TOKEN and TWILIO_FROM)
# DRY-RUN: exercise the full detection -> gate -> message pipeline on REAL seat openings and
# LOG the exact text that WOULD send (recipient, body, segment count) without calling Twilio.
# Proves the pipeline pre-approval so go-live is confirmation, not discovery. Never sends.
SMS_DRYRUN = os.environ.get("SMS_DRYRUN") == "1"
SMS_COST_CENTS = int(os.environ.get("SMS_COST_CENTS", "1"))          # cost PER SEGMENT (¢)
# Cost-safety knobs — env vars, not constants: they are stage-appropriate catastrophe
# floors Nathan raises in seconds as real volume grows, never permanent growth ceilings.
SMS_DAILY_CAP_CENTS = int(os.environ.get("SMS_DAILY_CAP_CENTS", "2000"))   # $20/day site-wide
# Runaway DETECTOR, not a product limit: every genuine opening must text, so any number
# small enough to be a "cap" would silence a real seat. Real sections opened 4 times in
# two weeks at the busiest UMD course, so 40 in 180 days is unreachable without a bug.
SMS_PER_WATCH_MAX = int(os.environ.get("SMS_PER_WATCH_MAX", "40"))
SMS_PER_USER_DAILY = int(os.environ.get("SMS_PER_USER_DAILY", "15"))
# ONE repeat rule for BOTH channels, defined once here so the two can never drift into
# separate regimes. Email had no cap at all (eight messages in an hour) while SMS had a
# permanent one-per-watch latch (four texts, ever) — the same bug pointing opposite ways.
REPEAT_ALERT_COOLDOWN_S = int(os.environ.get("REPEAT_ALERT_COOLDOWN_S", "1800"))
SMS_DEDUP_SECS = int(os.environ.get("SMS_DEDUP_SECS", str(REPEAT_ALERT_COOLDOWN_S)))
SMS_VELOCITY_PER_MIN = int(os.environ.get("SMS_VELOCITY_PER_MIN", "30"))
SMS_VELOCITY_FLOOR = int(os.environ.get("SMS_VELOCITY_FLOOR", "50"))  # breaker can't trip under
                                                                      # this many sends today
# EXACT opt-in disclosure — registered verbatim with the 10DLC campaign, so this string
# must match the checkbox, the /text-alerts page, and the SMS Terms word-for-word. Any
# drift between the public site and the registered campaign is the #1 carrier-rejection
# cause. Stored plain in each consent record as proof of exactly what the user agreed to;
# _sms_consent_html() renders it with Terms/Privacy hyperlinked for display.
SMS_CONSENT_WORDING = ("I agree to receive automated SeatWatch course seat-availability "
                       "alerts at the number provided. Message frequency varies based on the "
                       "courses I monitor. Message and data rates may apply. Reply STOP to opt "
                       "out or HELP for help. Consent is not a condition of purchase. See our "
                       "Terms and Privacy Policy.")

PLAN_MSG = ("Your free plan covers 1 class, up to 2 of its sections. Stop watching "
            "your current class below to switch classes.")

# --- operator guard (so the system watches itself and pings YOU, not the users) ---
OPERATOR_TOPIC = os.environ.get("SEATWATCH_ADMIN_TOPIC", "seatwatch-admin-q7x2k9m4")
HEALTHCHECK_URL = os.environ.get("HEALTHCHECK_URL", "")
FAIL_THRESHOLD = int(os.environ.get("FAIL_THRESHOLD", "5"))
# How long a school must stay unreadable before the OPERATOR is emailed. The pause itself
# still happens at FAIL_THRESHOLD (~100s) — that is correctness, and no false alert can
# escape meanwhile. This governs only the mail. Every operator page Nathan received in the
# week of 2026-08-14 was a school that healed itself: MUSC204 down and "recovered ✅" 24
# SECONDS later, Towson ENGL102 twice in one day. Two mails apiece for an outage nobody
# could act on and that was over before either was read. A page a human cannot act on
# isn't a page, it is training to ignore the next one.
OUTAGE_CONFIRM_S = int(os.environ.get("OUTAGE_CONFIRM_S", "900"))   # 15 min; 0 = mail at once
SUMMARY_EVERY_HOURS = 24
DRILL_EVERY_HOURS = 168        # automated end-to-end fire drill, weekly
# Reliable, always-on schools to drill against (rotated through until one delivers).
DRILL_SCHOOLS = ["umd", "gatech", "utsa", "usf", "vcu", "txst", "memphis"]

# --- input hardening / abuse protection ---
COURSE_RE = re.compile(r"^[A-Z]{2,4}\d{3,4}[A-Z]?$")   # e.g. ENG101, MATH140, BIOL2020
SECTION_RE = re.compile(r"^[A-Z0-9]{1,20}$")            # 0101, FC01, 83510, LEC002LAB324
_RATE = {}                                             # ip -> [timestamps]
# 15/hour was sized for an anonymous stranger and was far too tight for a real student:
# sign in, add a class, add a second section, set preferences, add a phone, fix a typo —
# a legitimate registration session reaches double figures easily. Signed-in students get
# a per-ACCOUNT budget generous enough for that; anonymous callers keep a tighter one.
RATE_MAX, RATE_WINDOW = 40, 3600        # anonymous: 40 submissions / IP / hour
RATE_MAX_USER = 120                     # signed in: 120 / account / hour


def rate_ok(ip, limit=None):
    """True if this caller may proceed. `ip` is really a KEY, not necessarily an address.

    Rate-limiting a university by IP alone does not work, and the failure is silent and
    total: a campus puts hundreds of students behind ONE NAT address, so a dorm would
    burn the shared budget in minutes during add/drop and then lock each other out — every
    one of them seeing "too many requests" for something they did not do. Callers pass a
    per-USER key whenever the request is authenticated (see _rate_key), which is both
    fairer and stricter: it follows the actual person instead of the building.
    """
    now = time.time()
    if len(_RATE) > 5000:  # prune stale IPs so memory can't grow forever
        for k in [k for k, v in _RATE.items() if not v or now - v[-1] > RATE_WINDOW]:
            _RATE.pop(k, None)
    keep = [t for t in _RATE.get(ip, []) if now - t < RATE_WINDOW]
    keep.append(now)
    _RATE[ip] = keep
    return len(keep) <= (limit if limit is not None else RATE_MAX)


# --------------------------------------------------------------------------- db
def db():
    c = sqlite3.connect(DB, timeout=30)
    c.row_factory = sqlite3.Row
    return c


def init_db():
    with db() as c:
        c.execute("""CREATE TABLE IF NOT EXISTS watches(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            school  TEXT NOT NULL DEFAULT 'umd',
            topic   TEXT NOT NULL,
            course  TEXT NOT NULL,
            section TEXT NOT NULL,          -- "" means ALL sections
            term    TEXT NOT NULL,
            alerted INTEGER NOT NULL DEFAULT 0,
            created REAL NOT NULL)""")
        c.execute("""CREATE TABLE IF NOT EXISTS users(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            google_sub TEXT NOT NULL UNIQUE,   -- Google's permanent account id
            email   TEXT NOT NULL,
            topic   TEXT NOT NULL UNIQUE,      -- one stable ntfy channel per account
            created REAL NOT NULL)""")
        cols = [r[1] for r in c.execute("PRAGMA table_info(watches)")]
        if "user_id" not in cols:              # migrate pre-accounts DBs in place
            c.execute("ALTER TABLE watches ADD COLUMN user_id INTEGER")
        # stranded_notified_at: stamped when we TELL the student their watch died at a
        # semester rollover. A watch is bound to the term it was created in; once the
        # school moves on, the watch is skipped forever so it cannot false-alert about the
        # wrong semester. That skip was silent to the student — the operator got paged and
        # the student got nothing, which is the same silent failure as an alert delivered
        # to a dead channel. Stamped so the warning goes out ONCE per watch, not every
        # 20-second cycle.
        if "stranded_notified_at" not in cols:
            c.execute("ALTER TABLE watches ADD COLUMN stranded_notified_at REAL")
        # --- free-tier abuse signals (all SOFT except free_eligible; detect-and-trim,
        # never block-at-door — campus NAT means shared IPs are normal) ---
        ucols = [r[1] for r in c.execute("PRAGMA table_info(users)")]
        if "normalized_email" not in ucols:
            c.execute("ALTER TABLE users ADD COLUMN normalized_email TEXT")
            for r in c.execute("SELECT id, email FROM users").fetchall():
                c.execute("UPDATE users SET normalized_email=? WHERE id=?",
                          (normalize_email(r["email"]), r["id"]))
        if "risk_score" not in ucols:
            c.execute("ALTER TABLE users ADD COLUMN risk_score INTEGER NOT NULL DEFAULT 0")
        if "free_eligible" not in ucols:       # 0 = this normalized email already used its
            c.execute("ALTER TABLE users ADD COLUMN free_eligible INTEGER NOT NULL DEFAULT 1")
        if "signup_ip" not in ucols:
            c.execute("ALTER TABLE users ADD COLUMN signup_ip TEXT")
        if "signup_source" not in ucols:
            # Where this student came from, captured at signup. Six accounts arrived in
            # August 2026 and the acquisition channel for every one was unknown: the site
            # sends Referrer-Policy: no-referrer by design, and nothing stored the UTM. So
            # a post that works and a post that does nothing looked identical afterwards.
            c.execute("ALTER TABLE users ADD COLUMN signup_source TEXT")
        if "pixel_activated_at" not in ucols:
            # Stamped the first time a student successfully creates a watch, and
            # never again. The ad conversion is meant to count an ACTIVATED NEW
            # USER; without it, one student adding four classes reports as four
            # acquisitions and every cost-per-signup figure is wrong by 4x.
            c.execute("ALTER TABLE users ADD COLUMN pixel_activated_at REAL")
        # BACKFILL — runs on every start, not just the one that adds the column.
        # The column arrives NULL for accounts that have been watching classes for
        # weeks, so without this the next watch an EXISTING student creates would flip
        # that NULL and report them to Meta as a newly acquired user. Their real
        # activation moment is their first watch, so that is the value written.
        # Idempotent by construction: the IS NULL predicate matches nothing on a second
        # run, and a student with no watches is deliberately left NULL so their genuine
        # first watch still converts.
        c.execute("UPDATE users SET pixel_activated_at="
                  "(SELECT MIN(w.created) FROM watches w WHERE w.user_id=users.id) "
                  "WHERE pixel_activated_at IS NULL "
                  "AND EXISTS(SELECT 1 FROM watches w WHERE w.user_id=users.id)")
        c.execute("""CREATE TABLE IF NOT EXISTS device_markers(
            device_id  TEXT NOT NULL,
            user_id    INTEGER NOT NULL,
            first_seen REAL NOT NULL,
            UNIQUE(device_id, user_id))""")
        # Operator mail damping, on DISK rather than in memory. The in-memory version
        # forgot everything on restart, so a redeploy during a long outage re-mailed
        # instantly, and a poller that restarts often mails as if nothing were damped.
        c.execute("""CREATE TABLE IF NOT EXISTS operator_mail(
            key       TEXT PRIMARY KEY,
            last_sent REAL NOT NULL,
            last_seen REAL NOT NULL,
            streak    INTEGER NOT NULL DEFAULT 0)""")
        # --- paid tiers (dormant until PAID_ENABLED) ---
        if "plan_tier" not in ucols:
            c.execute("ALTER TABLE users ADD COLUMN plan_tier INTEGER NOT NULL DEFAULT 0")
        if "plan_purchased_at" not in ucols:
            c.execute("ALTER TABLE users ADD COLUMN plan_purchased_at REAL")
        if "plan_term" not in ucols:            # season label at purchase, for reporting
            c.execute("ALTER TABLE users ADD COLUMN plan_term TEXT")
        if "stripe_customer_id" not in ucols:
            c.execute("ALTER TABLE users ADD COLUMN stripe_customer_id TEXT")
        if "plan_payment_intent" not in ucols:   # the charge that granted the CURRENT plan —
            c.execute("ALTER TABLE users ADD COLUMN plan_payment_intent TEXT")  # lets a refund
                                                 # downgrade ONLY that charge, never a newer one
        # --- per-user channel preferences -------------------------------------------
        # DEFAULT 1 on both: every existing row keeps exactly today's behaviour, so this
        # migration cannot change what any current user receives. A student who is paying
        # should be able to stop getting the same alert three ways without unsubscribing
        # from the product. The floor (at least one channel on) is enforced server-side in
        # the handler, never in the UI — a watch with no reachable channel is a watch that
        # can never fire, which is the silent-failure class the surfacing work just closed.
        if "notify_email" not in ucols:
            c.execute("ALTER TABLE users ADD COLUMN notify_email INTEGER NOT NULL DEFAULT 1")
        if "notify_push" not in ucols:
            c.execute("ALTER TABLE users ADD COLUMN notify_push INTEGER NOT NULL DEFAULT 1")
        if "notify_sms" not in ucols:
            c.execute("ALTER TABLE users ADD COLUMN notify_sms INTEGER NOT NULL DEFAULT 1")
        # --- retiring push: rescue anyone it was the only channel for ---------------
        # Push is gone as a student channel. An account that had push on and both email
        # and text off was, under the old rules, a fully-configured account — it passed
        # the floor. Under the new rules it has NOTHING, and its watches would fire into
        # a void forever without a single error anywhere. So switch email back on for
        # exactly those accounts before the new floor can apply to them.
        #
        # This is the migration that actually matters. It runs before any request is
        # served and is idempotent: once notify_email is 1 the WHERE clause stops
        # matching. Scoped to accounts that HAVE an email address, since turning on a
        # channel with no destination would just be a different kind of unreachable.
        rescued = c.execute(
            "UPDATE users SET notify_email=1 WHERE COALESCE(notify_email,0)=0 "
            "AND COALESCE(notify_sms,0)=0 AND email IS NOT NULL AND email != ''").rowcount
        if rescued:
            sw.log(f"[migrate] push retired: re-enabled email for {rescued} account(s) that "
                   f"had no other way to be reached")
        c.execute("UPDATE users SET notify_push=0 WHERE COALESCE(notify_push,0)=1")
        # --- one-time sample text + promo -------------------------------------------
        # sample_sms_at: stamped the FIRST time a student is shown what an alert looks
        # like. Once per account, ever — not per watch — so adding five classes does not
        # send five sample texts.
        # promo_sent_at: stamped when the 7-day discount email goes out, so a restart or a
        # double sweep can never mail the same student twice.
        # promo_code / promo_redeemed_at: the 7-day offer is a PER-STUDENT numeric code,
        # not one shared string. A shared code leaks instantly (one screenshot on Reddit
        # and everyone pays $24.95 forever), and it cannot be revoked without breaking it
        # for the people who earned it. Per-student codes are individually redeemable,
        # single-use, and traceable back to the sweep that issued them.
        if "promo_code" not in ucols:
            c.execute("ALTER TABLE users ADD COLUMN promo_code TEXT")
        if "promo_redeemed_at" not in ucols:
            c.execute("ALTER TABLE users ADD COLUMN promo_redeemed_at REAL")
        if "sample_sms_at" not in ucols:
            c.execute("ALTER TABLE users ADD COLUMN sample_sms_at REAL")
        # sample_email_at: the same idea for email, and it was missing. SMS proved itself
        # on day one with a sample text; email's first ever use was a REAL seat alert. If
        # the address is wrong, or Gmail files it under Promotions, the student discovers
        # that by missing the seat — which is the exact failure the sample text prevents.
        if "sample_email_at" not in ucols:
            c.execute("ALTER TABLE users ADD COLUMN sample_email_at REAL")
        if "promo_sent_at" not in ucols:
            c.execute("ALTER TABLE users ADD COLUMN promo_sent_at REAL")
        # webhook idempotency — a Stripe event unlocks a tier AT MOST once, even on retries
        c.execute("""CREATE TABLE IF NOT EXISTS stripe_events(
            event_id  TEXT PRIMARY KEY,
            kind      TEXT,
            user_id   INTEGER,
            processed REAL NOT NULL)""")
        # conversion-intent signals (wall_hit / simultaneous_course_need) — the data
        # Nathan watches to decide WHEN to flip paid on
        c.execute("""CREATE TABLE IF NOT EXISTS conv_signals(
            kind    TEXT NOT NULL,
            user_id INTEGER,
            created REAL NOT NULL)""")
        c.execute("""CREATE TABLE IF NOT EXISTS push_subs(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id  INTEGER NOT NULL,
            endpoint TEXT NOT NULL UNIQUE,     -- one row per device/browser
            p256dh   TEXT NOT NULL,
            auth     TEXT NOT NULL,
            created  REAL NOT NULL)""")
        # --- alert delivery ledger: append-only, one row per channel that reported
        # success. The SINGLE source of truth three features query: SMS cost caps
        # (per-watch / per-user / dedup / velocity / daily spend are all derived from it
        # at check time — nothing in memory, so a poller restart can't reset a breaker),
        # refund eligibility ("was this account ever alerted since purchase" — the
        # watches.alerted latch resets when a section refills, so it can't answer that),
        # and the TCPA audit trail of what was sent to whom when. Rows with channel
        # 'sms_breaker' are circuit-breaker trip markers, not deliveries — cost 0, and
        # written so the daily pause survives restarts. ---
        c.execute("""CREATE TABLE IF NOT EXISTS alert_log(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id    INTEGER,
            watch_id   INTEGER,
            school     TEXT,
            course     TEXT,
            section    TEXT,
            channel    TEXT NOT NULL,          -- ntfy | webpush | email | sms | sms_breaker
            cost_cents INTEGER NOT NULL DEFAULT 0,
            sent_at    REAL NOT NULL)""")
        c.execute("CREATE INDEX IF NOT EXISTS ix_alog_chan_time ON alert_log(channel, sent_at)")
        c.execute("CREATE INDEX IF NOT EXISTS ix_alog_user ON alert_log(user_id, channel, sent_at)")
        c.execute("CREATE INDEX IF NOT EXISTS ix_alog_watch ON alert_log(watch_id, channel)")
        # --- SMS consent (TCPA): durable record of exactly who agreed to what, when,
        # from which IP, in which words. Double opt-in: a row is REQUESTED at form
        # submit and only CONFIRMED when the user texts back YES; revoked_at set by
        # STOP. send_sms refuses anything but (confirmed, not revoked). ---
        c.execute("""CREATE TABLE IF NOT EXISTS sms_consent(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id      INTEGER NOT NULL,
            phone        TEXT NOT NULL,        -- E.164
            wording      TEXT NOT NULL,        -- exact consent text shown at opt-in
            ip           TEXT,
            requested_at REAL NOT NULL,
            confirmed_at REAL,
            revoked_at   REAL)""")
        c.execute("CREATE INDEX IF NOT EXISTS ix_smsc_user ON sms_consent(user_id, requested_at)")
        c.execute("CREATE INDEX IF NOT EXISTS ix_smsc_phone ON sms_consent(phone)")
        # --- beta instrumentation ---------------------------------------------------
        # alert_log records only SUCCESSES, which makes delivery look like a perfect 100%:
        # a student whose seat opened while they had NO reachable channel leaves no trace.
        # alert_attempt logs EVERY intended notification, so the denominator exists and the
        # silent failures are countable ('no_channel' is the one we hunt). It also carries
        # the click token, so ONE table answers all three open questions:
        #   reachability     = sent / attempts
        #   action rate      = clicked / sent, per channel   (delivery != value)
        #   time-to-action   = clicked_at - attempted_at     (the real SMS-vs-push test)
        c.execute("""CREATE TABLE IF NOT EXISTS alert_attempt(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            token        TEXT UNIQUE,          -- /r/<token> click attribution, per channel
            user_id      INTEGER,
            watch_id     INTEGER,
            school       TEXT,
            course       TEXT,
            section      TEXT,
            channel      TEXT,                 -- NULL when nothing was reachable
            outcome      TEXT NOT NULL,        -- sent | no_channel | provider_error
            attempted_at REAL NOT NULL,
            clicked_at   REAL)""")
        c.execute("CREATE INDEX IF NOT EXISTS ix_att_outcome ON alert_attempt(outcome, attempted_at)")
        c.execute("CREATE INDEX IF NOT EXISTS ix_att_chan ON alert_attempt(channel, attempted_at)")
        c.execute("CREATE INDEX IF NOT EXISTS ix_att_user ON alert_attempt(user_id, attempted_at)")
        # Revealed willingness-to-pay for the end-of-beta price probe. Comping the beta
        # measures USAGE, not whether anyone will PAY — and shipping on a usage signal alone
        # is how you build something people love and nobody buys. Dormant until the paid
        # path is switched on AND Nathan explicitly says go.
        # --- user feedback ---------------------------------------------------------
        # Stored FIRST, emailed second. Email is best-effort (and is off entirely until
        # SMTP is configured), so persisting is what guarantees a student's feedback is
        # never lost — emailed_at stays NULL until it actually goes out, so unsent notes
        # are trivially findable and re-sendable.
        c.execute("""CREATE TABLE IF NOT EXISTS feedback(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id   INTEGER,
            email     TEXT,
            message   TEXT NOT NULL,
            created   REAL NOT NULL,
            emailed_at REAL)""")
        c.execute("CREATE INDEX IF NOT EXISTS ix_fb_created ON feedback(created)")
        c.execute("""CREATE TABLE IF NOT EXISTS price_probe(
            user_id            INTEGER PRIMARY KEY,
            shown_at           REAL NOT NULL,
            clicked_checkout_at REAL,
            purchased_at       REAL,
            decline_reason     TEXT)""")
        guardian.init_schema(c)   # additive guardian_* evidence tables


# ------------------------------------------------------------------- auth
_WLOCK = threading.Lock()   # serializes entitlement check + insert (no race-around)


def _sign(msg):
    return hmac.new(SECRET.encode(), msg.encode(), hashlib.sha256).hexdigest()


def session_cookie(user_id):
    exp = int(time.time()) + SESSION_DAYS * 86400
    val = f"{user_id}.{exp}.{_sign(f'sess:{user_id}.{exp}')}"
    return (f"sw_session={val}; Path=/; Max-Age={SESSION_DAYS * 86400}; "
            "HttpOnly; Secure; SameSite=Lax")


def read_session_value(val):
    """Returns user_id or None. Forged/expired/tampered cookies all fail closed."""
    bits = (val or "").split(".")
    if len(bits) != 3:
        return None
    uid, exp, sig = bits
    if not (uid.isdigit() and exp.isdigit()):
        return None
    if not hmac.compare_digest(sig, _sign(f"sess:{uid}.{exp}")):
        return None
    if int(exp) < time.time():
        return None
    return int(uid)


def csrf_token(user_id):
    return _sign(f"csrf:{user_id}")


def _abuse_clusters(c):
    """THE paid-perk protection, flag-only: correlated account groups collectively
    covering more of one (school, course) than a single free account allows (>2
    sections marketed). Correlation = shared device marker, same signup IP, same
    normalized email, or signups within 24h. Surfaced to the operator via
    /admin/stats; never auto-bans."""
    rows = c.execute("SELECT school, course, user_id, COUNT(*) n FROM watches "
                     "WHERE user_id IS NOT NULL GROUP BY school, course, user_id").fetchall()
    by_course = {}
    for r in rows:
        by_course.setdefault((r["school"], r["course"]), []).append((r["user_id"], r["n"]))
    clusters = []
    for (school, course), members in by_course.items():
        if len(members) < 2:
            continue
        total = sum(n for _, n in members)
        if total <= 2:                      # fits one account's marketed allotment
            continue
        uids = sorted({u for u, _ in members})
        ph = ",".join("?" * len(uids))
        us = {r["id"]: r for r in c.execute(
            f"SELECT id, normalized_email, signup_ip, created FROM users WHERE id IN ({ph})",
            uids)}
        signals = set()
        for i in range(len(uids)):
            for j in range(i + 1, len(uids)):
                a, b = us.get(uids[i]), us.get(uids[j])
                if not a or not b:
                    continue
                if a["normalized_email"] and a["normalized_email"] == b["normalized_email"]:
                    signals.add("same_email")
                if a["signup_ip"] and a["signup_ip"] == b["signup_ip"]:
                    signals.add("same_ip")
                if abs((a["created"] or 0) - (b["created"] or 0)) < 86400:
                    signals.add("signup_window_24h")
        if c.execute(f"SELECT 1 FROM device_markers WHERE user_id IN ({ph}) "
                     "GROUP BY device_id HAVING COUNT(DISTINCT user_id)>1 LIMIT 1",
                     uids).fetchone():
            signals.add("shared_device")
        if signals:
            clusters.append({"school": school, "course": course, "user_ids": uids,
                             "sections_covered": total, "signals": sorted(signals)})
    return clusters


def current_season():
    """Coarse registration season for reporting/labels (e.g. '2026-fall'). Registration
    runs ahead of the term, so this maps the CALENDAR month to the season students are
    signing up for; it's a label only — entitlement expiry is the fixed PAID_TERM_DAYS
    window, not this."""
    t = time.localtime()   # app.py imports `time`, not `datetime` — use what's here
    season = "spring" if t.tm_mon <= 5 else "summer" if t.tm_mon <= 7 else "fall"
    return f"{t.tm_year}-{season}"


def stamp_term(school):
    """Term recorded on a NEW watch. Must be the same value run_cycle will later
    compare against (cur_term(), falling back to the static pin): stamping the
    pin while the school's active term has rolled makes the watch dead on
    arrival — skipped as stale from its first cycle, silently."""
    try:
        if callable(getattr(school, "cur_term", None)):
            return school.cur_term() or getattr(school, "term", "")
    except Exception:
        pass
    return getattr(school, "term", "")


def effective_tier(user):
    """The tier a user is ACTUALLY entitled to right now. 0 (free) unless paid is live,
    they hold a paid tier, AND it's still inside the PAID_TERM_DAYS window. Fail-closed:
    any missing/odd data -> free. This one function gates every paid capability, so a
    lapsed or dormant entitlement can never leak the paid perk."""
    if not PAID_ENABLED:
        return 0
    try:
        tier = int(user["plan_tier"] or 0)
    except (KeyError, TypeError, ValueError, IndexError):
        return 0
    if tier <= 0:
        return 0
    bought = user["plan_purchased_at"] if "plan_purchased_at" in user.keys() else None
    if not bought or (time.time() - float(bought)) > PAID_TERM_DAYS * 86400:
        return 0                                  # expired -> back to free
    return min(tier, 3)


def tier_courses(tier):
    return TIER_COURSES.get(tier, 1)


def _conv_signal(kind, user_id):
    try:
        with db() as c:
            c.execute("INSERT INTO conv_signals(kind,user_id,created) VALUES(?,?,?)",
                      (kind, user_id, time.time()))
    except Exception:
        pass


# ------------------------------------------------------------------- Stripe (stdlib)
# PIN THE STRIPE API VERSION. Without this, every request uses whatever version Stripe
# has made the account default — which they move forward over time, changing request
# shapes underneath a running app. It already bit us: the account had rolled onto a
# version where /v1/promotion_codes rejects `coupon` ("Received unknown parameter:
# coupon"), so EVERY promo code silently failed to mint. The 7-day offer would have
# quietly stopped existing, and the only visible symptom would have been students never
# receiving an email nobody was watching for.
#
# Pinned to a version verified working against this account for coupons, promotion codes
# and Checkout Sessions. Moving it is a deliberate, tested change — never a default.
STRIPE_API_VERSION = "2024-06-20"


def _stripe_get(path):
    """GET a Stripe object. Returns parsed JSON, or None if absent/unreachable."""
    req = urllib.request.Request("https://api.stripe.com/v1" + path)
    req.add_header("Authorization", "Bearer " + STRIPE_SECRET_KEY)
    req.add_header("Stripe-Version", STRIPE_API_VERSION)
    try:
        return json.loads(urllib.request.urlopen(req, timeout=20).read().decode())
    except Exception:
        return None


def _stripe_post(path, fields, idem=None):
    """Minimal Stripe API call — form-encoded POST with the secret key as Bearer. No SDK
    (keeps the stdlib-only posture). Returns parsed JSON or None on failure."""
    data = urllib.parse.urlencode(fields, doseq=True).encode()
    req = urllib.request.Request("https://api.stripe.com/v1" + path, data=data)
    req.add_header("Authorization", "Bearer " + STRIPE_SECRET_KEY)
    req.add_header("Content-Type", "application/x-www-form-urlencoded")
    req.add_header("Stripe-Version", STRIPE_API_VERSION)
    if idem:
        req.add_header("Idempotency-Key", idem)   # safe to retry without double-charge
    try:
        return json.loads(urllib.request.urlopen(req, timeout=20).read().decode())
    except urllib.error.HTTPError as e:
        # Stripe puts the actual reason in the body. Logging only the status code cost
        # real time here: four identical "HTTP Error 400" lines that said nothing, when
        # the body said "Received unknown parameter: coupon" and named the bug outright.
        detail = ""
        try:
            detail = (json.loads(e.read().decode()).get("error", {}) or {}).get("message", "")
        except Exception:
            pass
        sw.log(f"  [stripe] POST {path} failed: {e.code} {detail}"[:300])
        return None
    except Exception as e:
        sw.log(f"  [stripe] POST {path} failed: {e}")
        return None


# --- the 7-day promo -----------------------------------------------------------------
# Nathan's spec, and every clause is a constraint the code enforces rather than displays:
#   * only students on FREE for a week are offered it; anyone who already paid is skipped
#   * the code is NUMERIC and issued PER STUDENT
#   * the coupon field appears at the PAYMENT step, beside card and Apple Pay, on every plan
#   * it discounts ONLY the top plan: $29.95 -> $24.95. The $19.95 and $24.95 plans get nothing
#   * a student who pays $24.95 is charged EXACTLY $24.95
#
# The field lives on Stripe's hosted Checkout page (allow_promotion_codes), because that is
# where "next to credit card and Apple Pay" physically is — we do not render that page and
# cannot inject into it. So the discount is a real Stripe Promotion Code, and Stripe both
# displays the field and enforces the rules.
#
# The tier restriction rides on restrictions[minimum_amount] rather than a product
# allow-list. Our line items are ad-hoc price_data, not saved Prices, so there is no
# product id to restrict against — but a minimum order of $29.95 is exactly equivalent
# here and needs no catalogue: the $19.95 and $24.95 plans cannot reach it, and neither
# can an upgrade delta. Stripe rejects the code itself, on its own page, with its own
# message, so the rule cannot drift away from what we tell students.
PROMO_TIER = 3                     # the ONLY tier the coupon can reach
PROMO_PRICE_CENTS = 2495           # what tier 3 costs with a valid code (from 2995)
PROMO_OFF_CENTS = 500
STRIPE_COUPON_ID = "seatwatch_5off"


def _new_promo_code():
    """8 digits. Numeric because Nathan asked for numeric, and 8 because 6 is guessable:
    a plan is worth $5 to an attacker, and at 6 digits a script finds a live code in a few
    hundred thousand tries. secrets, never random — this decides who pays less."""
    return "".join(str(secrets.randbelow(10)) for _ in range(8))


def _stripe_ensure_coupon():
    """The single $5 coupon every student's personal code points at. Created once and
    reused: a fixed id makes this idempotent, so a restart or a second sweep cannot
    litter the Stripe account with duplicates."""
    if not STRIPE_SECRET_KEY:
        return None
    got = _stripe_get("/coupons/" + STRIPE_COUPON_ID)
    if got and got.get("id"):
        return got["id"]
    made = _stripe_post("/coupons", {
        "id": STRIPE_COUPON_ID,
        "amount_off": str(PROMO_OFF_CENTS),
        "currency": "usd",
        "duration": "once",
        "name": "SeatWatch $5 off",
    }, idem="coupon-" + STRIPE_COUPON_ID)
    return (made or {}).get("id")


def issue_promo_code(user_id):
    """Mint this student's personal promotion code IN STRIPE and return it.

    Returns None if Stripe refuses — and the caller must then NOT send the email. A code
    in a student's inbox that Stripe will reject is worse than no promo at all: they type
    it at the moment they have decided to pay, and it tells them the company is broken.
    """
    if not _stripe_ensure_coupon():
        return None
    for _ in range(5):                       # collisions ~1 in 10^8; still, don't assume
        code = _new_promo_code()
        res = _stripe_post("/promotion_codes", {
            "coupon": STRIPE_COUPON_ID,
            "code": code,
            "max_redemptions": "1",          # single use, enforced by Stripe
            # THE TIER LOCK. $19.95 and $24.95 orders never reach this floor, and neither
            # does an upgrade delta, so the code is inert everywhere except a full-price
            # $29.95 purchase — which is exactly who the 7-day offer is for.
            "restrictions[minimum_amount]": str(TIER_PRICE_CENTS[PROMO_TIER]),
            "restrictions[minimum_amount_currency]": "usd",
            "metadata[user_id]": str(user_id),
        }, idem=f"promo-{user_id}-{code}")
        if res and res.get("id"):
            with db() as c:
                c.execute("UPDATE users SET promo_code=? WHERE id=?", (code, user_id))
            return code
    return None


def stripe_checkout_url(user, target_tier):
    """Create a one-time hosted Checkout Session for an upgrade to target_tier and return
    its URL. Charges only the DELTA above the user's current effective tier (never a
    re-charge). None if paid isn't live or the tier is invalid/not an upgrade."""
    if not PAID_LIVE or target_tier not in TIER_PRICE_CENTS:
        return None
    # UPWARD ONLY. A student on the $19.95 plan can move to $24.95 or $29.95; a student
    # on $24.95 can never "buy" $19.95. Two separate reasons, and both matter:
    #
    #   Selling DOWN is not a purchase, it is a refund request wearing a checkout button.
    #   Taking $19.95 to reduce someone's plan would be charging them to lose something,
    #   and it is the kind of thing a student screenshots.
    #
    #   Re-buying the SAME tier is equally refused. It reads as a renewal and is not one —
    #   they already hold it for this term, so it would be money for nothing.
    #
    # They pay only the DIFFERENCE, never the full price again. Someone who paid $19.95 and
    # then wants five courses owes $10, not $29.95; charging twice for the overlap is how
    # an upgrade path turns into a reason to ask for a refund instead.
    cur = effective_tier(user)
    if target_tier <= cur:
        return None
    amount = TIER_PRICE_CENTS[target_tier] - TIER_PRICE_CENTS.get(cur, 0)
    if amount <= 0:
        return None
    season = current_season()
    fields = {
        "mode": "payment",
        "success_url": BASE_URL + "/checkout/success",
        "cancel_url": BASE_URL + "/pricing",
        "client_reference_id": str(user["id"]),
        "line_items[0][quantity]": "1",
        "line_items[0][price_data][currency]": "usd",
        "line_items[0][price_data][unit_amount]": str(amount),
        "line_items[0][price_data][product_data][name]":
            f"SeatWatch: {TIER_NAME[target_tier]}"
            + (f" (upgrade from {TIER_NAME[cur]})" if cur else ""),
        # metadata is the ONLY thing the webhook trusts to unlock
        "metadata[user_id]": str(user["id"]),
        "metadata[target_tier]": str(target_tier),
        "metadata[season]": season,
        # EXACTLY the shown price leaves the student's card and nothing else. Stripe
        # Checkout charges unit_amount, but automatic tax and adjustable quantity are
        # account/session settings that would silently change the total, so both are
        # pinned off HERE rather than assumed from the dashboard. Nathan's requirement:
        # if it says $24.95, the statement says $24.95.
        "automatic_tax[enabled]": "false",
        "line_items[0][adjustable_quantity][enabled]": "false",
    }
    if target_tier == PROMO_TIER:
        # THE COUPON FIELD, and ONLY here. Stripe renders "Add promotion code" on the
        # payment page beside card and Apple Pay. Showing it on the $19.95 and $24.95
        # plans would invite a student to type a code that is guaranteed to be refused —
        # a box that exists only to say no. The $29.95 minimum on the code itself is the
        # second lock, so even a hand-crafted request cannot discount the cheaper plans.
        fields["allow_promotion_codes"] = "true"
    if user["stripe_customer_id"] if "stripe_customer_id" in user.keys() else None:
        fields["customer"] = user["stripe_customer_id"]
    sess = _stripe_post("/checkout/sessions", fields,
                        idem=f"co-{user['id']}-{target_tier}-{int(time.time()//3600)}")
    return sess.get("url") if sess else None


def stripe_verify_webhook(payload_bytes, sig_header):
    """Verify a Stripe webhook signature (t=<ts>,v1=<hmac>). Returns the parsed event on
    success, else None. Signature + 5-min freshness are the gate — the redirect back from
    Checkout is NEVER trusted to unlock; only a verified webhook is."""
    if not STRIPE_WEBHOOK_SECRET or not sig_header:
        return None
    parts = dict(p.split("=", 1) for p in sig_header.split(",") if "=" in p)
    ts, v1 = parts.get("t"), parts.get("v1")
    if not ts or not v1:
        return None
    try:
        if abs(time.time() - int(ts)) > 300:      # replay guard
            return None
    except ValueError:
        return None
    signed = ts.encode() + b"." + payload_bytes
    expected = hmac.new(STRIPE_WEBHOOK_SECRET.encode(), signed, hashlib.sha256).hexdigest()
    if not hmac.compare_digest(expected, v1):
        return None
    try:
        return json.loads(payload_bytes.decode())
    except Exception:
        return None


def stripe_apply_event(event):
    """Process a VERIFIED Stripe event, idempotently. Purchase -> unlock; a FULL refund or a
    dispute/chargeback of the CURRENT entitlement's charge -> downgrade to free."""
    if not event:
        return
    etype = event.get("type")
    if etype == "checkout.session.completed":
        _stripe_unlock(event)
    elif etype in ("charge.refunded", "charge.dispute.created"):
        _stripe_downgrade(event)


def _stripe_unlock(event):
    """Unlock a tier from a checkout.session.completed event. Records the session's
    payment_intent so a later refund of THIS charge can be matched precisely."""
    eid = event.get("id") or ""
    sess = (event.get("data") or {}).get("object") or {}
    meta = sess.get("metadata") or {}
    try:
        uid = int(meta.get("user_id"))
        tier = int(meta.get("target_tier"))
    except (TypeError, ValueError):
        return
    if tier not in TIER_PRICE_CENTS:
        return
    with db() as c:
        if eid and c.execute("SELECT 1 FROM stripe_events WHERE event_id=?", (eid,)).fetchone():
            return                                 # already processed this event
        # only ever RAISE a tier (a stale/duplicate lower event can't downgrade)
        row = c.execute("SELECT plan_tier FROM users WHERE id=?", (uid,)).fetchone()
        if not row:
            return
        new_tier = max(int(row["plan_tier"] or 0), tier)
        c.execute("UPDATE users SET plan_tier=?, plan_purchased_at=?, plan_term=?, "
                  "stripe_customer_id=COALESCE(?,stripe_customer_id), plan_payment_intent=? "
                  "WHERE id=?",
                  (new_tier, time.time(), meta.get("season") or current_season(),
                   sess.get("customer"), sess.get("payment_intent"), uid))
        # Burn the coupon HERE, on a real completed payment, and only if it is still the
        # code we issued to THIS student. Not at checkout-creation (an abandoned tab would
        # eat it) and not on trust of metadata alone (metadata is only as good as the
        # signature that carried it, so re-verify ownership against the row).
        # Stripe owns redemption (max_redemptions=1); we mirror it so our own records
        # can answer "did this student use their code?" without an API round trip.
        if (sess.get("total_details") or {}).get("amount_discount"):
            c.execute("UPDATE users SET promo_redeemed_at=? WHERE id=? "
                      "AND promo_redeemed_at IS NULL", (time.time(), uid))
        if eid:
            c.execute("INSERT OR IGNORE INTO stripe_events(event_id,kind,user_id,processed) "
                      "VALUES(?,?,?,?)", (eid, "checkout.session.completed", uid, time.time()))
    sw.log(f"  [stripe] user {uid} unlocked tier {new_tier}")


def _stripe_downgrade(event):
    """A FULL refund or a dispute/chargeback -> revert the account to free.

    ORDERED by payment_intent: we downgrade only the user whose CURRENT entitlement was
    granted by the exact refunded/disputed charge — so refunding a SUPERSEDED charge (an
    old plan the user already re-purchased past) can never strip their newer valid plan.
    Idempotent by event id. Partial refunds are ignored — the user still holds the plan
    they mostly paid for. Conservative by construction: no PI match -> no change."""
    eid = event.get("id") or ""
    etype = event.get("type")
    obj = (event.get("data") or {}).get("object") or {}
    pi = obj.get("payment_intent")
    if etype == "charge.dispute.created":
        full = True                              # a chargeback reverses the whole payment
    else:                                        # charge.refunded — only a FULL refund downgrades
        amt, refunded = int(obj.get("amount") or 0), int(obj.get("amount_refunded") or 0)
        full = bool(obj.get("refunded")) or (amt > 0 and refunded >= amt)
    if not pi or not full:
        return
    with db() as c:
        if eid and c.execute("SELECT 1 FROM stripe_events WHERE event_id=?", (eid,)).fetchone():
            return
        row = c.execute("SELECT id, plan_tier FROM users WHERE plan_payment_intent=?",
                        (pi,)).fetchone()
        if row and int(row["plan_tier"] or 0) > 0:
            c.execute("UPDATE users SET plan_tier=0, plan_purchased_at=NULL, plan_term=NULL, "
                      "plan_payment_intent=NULL WHERE id=?", (row["id"],))
            sw.log(f"  [stripe] user {row['id']} {etype} (full) -> downgraded to free")
        if eid:
            c.execute("INSERT OR IGNORE INTO stripe_events(event_id,kind,user_id,processed) "
                      "VALUES(?,?,?,?)", (eid, etype, row["id"] if row else None, time.time()))


def google_auth_url(state):
    return "https://accounts.google.com/o/oauth2/v2/auth?" + urlencode({
        "client_id": GOOGLE_CLIENT_ID,
        "redirect_uri": BASE_URL + "/auth/callback",
        "response_type": "code",
        "scope": "openid email",
        "state": state,
        "prompt": "select_account",
    })


def google_exchange(code):
    """Swap the one-time code for the user's identity. Returns {sub,email} or None.
    The id_token comes to us DIRECTLY from Google over HTTPS (server-to-server with
    our client secret), so its contents are trustworthy per Google's own guidance —
    we still verify audience/issuer/expiry/email_verified and fail closed."""
    try:
        data = urlencode({
            "code": code,
            "client_id": GOOGLE_CLIENT_ID,
            "client_secret": GOOGLE_CLIENT_SECRET,
            "redirect_uri": BASE_URL + "/auth/callback",
            "grant_type": "authorization_code"}).encode()
        req = urllib.request.Request("https://oauth2.googleapis.com/token", data=data)
        with urllib.request.urlopen(req, timeout=15) as r:
            tok = json.loads(r.read().decode())
        parts = tok.get("id_token", "").split(".")
        if len(parts) != 3:
            return None
        pad = parts[1] + "=" * (-len(parts[1]) % 4)
        claims = json.loads(base64.urlsafe_b64decode(pad))
        if claims.get("aud") != GOOGLE_CLIENT_ID:
            return None
        if claims.get("iss") not in ("https://accounts.google.com", "accounts.google.com"):
            return None
        if int(claims.get("exp", 0)) < time.time():
            return None
        if not claims.get("email_verified") or not claims.get("sub"):
            return None
        return {"sub": str(claims["sub"]), "email": claims.get("email", "")}
    except Exception as e:
        sw.log(f"  [warn] google_exchange failed: {e}")
        return None


def apple_auth_url(state):
    # response_mode MUST be form_post when a scope is requested (Apple's rule); Apple
    # then returns the user to us via a CROSS-SITE POST — which is why this flow's
    # state cookie is set with SameSite=None (a Lax cookie doesn't ride that POST).
    return "https://appleid.apple.com/auth/authorize?" + urlencode({
        "client_id": APPLE_CLIENT_ID,
        "redirect_uri": BASE_URL + "/auth/apple",
        "response_type": "code",
        "scope": "email",
        "response_mode": "form_post",
        "state": state,
    })


def _apple_client_secret():
    """Apple's 'client secret' is not a static string — it's a fresh ES256 JWT
    signed with the .p8 key, asserting our Team ID + Services ID."""
    with open(APPLE_PRIVATE_PEM, "rb") as f:
        key = _ec_ser.load_pem_private_key(f.read(), password=None)

    def b64(d):
        return base64.urlsafe_b64encode(d).rstrip(b"=")
    now = int(time.time())
    head = b64(json.dumps({"alg": "ES256", "kid": APPLE_KEY_ID},
                          separators=(",", ":")).encode())
    body = b64(json.dumps({"iss": APPLE_TEAM_ID, "iat": now, "exp": now + 3600,
                           "aud": "https://appleid.apple.com", "sub": APPLE_CLIENT_ID},
                          separators=(",", ":")).encode())
    signing = head + b"." + body
    r, s = _ec_dds(key.sign(signing, _ec_ec.ECDSA(_ec_hashes.SHA256())))
    return (signing + b"." + b64(r.to_bytes(32, "big") + s.to_bytes(32, "big"))).decode()


def apple_exchange(code):
    """Swap Apple's one-time code for the user's identity. Returns {sub,email} or None.
    Same trust model as google_exchange: the id_token arrives DIRECTLY from Apple over
    HTTPS (server-to-server, authenticated by our signed client secret), so we verify
    audience/issuer/expiry and fail closed. The email may be Apple's private-relay
    address — real and forwarding, but only once the sending domain is registered in
    the Apple developer console (deploy note for the owner)."""
    try:
        data = urlencode({
            "code": code,
            "client_id": APPLE_CLIENT_ID,
            "client_secret": _apple_client_secret(),
            "redirect_uri": BASE_URL + "/auth/apple",
            "grant_type": "authorization_code"}).encode()
        req = urllib.request.Request("https://appleid.apple.com/auth/token", data=data)
        with urllib.request.urlopen(req, timeout=15) as r:
            tok = json.loads(r.read().decode())
        parts = tok.get("id_token", "").split(".")
        if len(parts) != 3:
            return None
        pad = parts[1] + "=" * (-len(parts[1]) % 4)
        claims = json.loads(base64.urlsafe_b64decode(pad))
        if claims.get("aud") != APPLE_CLIENT_ID:
            return None
        if claims.get("iss") != "https://appleid.apple.com":
            return None
        if int(claims.get("exp", 0)) < time.time():
            return None
        if not claims.get("sub"):
            return None
        # 'apple:' prefix keeps Apple subs from ever colliding with Google subs in the
        # shared users.google_sub column (same pattern as dev-login's 'dev:' prefix).
        return {"sub": "apple:" + str(claims["sub"]), "email": claims.get("email", "") or ""}
    except Exception as e:
        sw.log(f"  [warn] apple_exchange failed: {e}")
        return None


def normalize_email(email):
    """Collapse the aliases ONE person controls into one identity. Google-correct:
    lowercase; drop +tag everywhere; dots are insignificant ONLY on gmail/googlemail
    (Workspace domains treat dots as real); googlemail.com == gmail.com."""
    e = (email or "").strip().lower()
    if "@" not in e:
        return e
    local, domain = e.rsplit("@", 1)
    local = local.split("+", 1)[0]
    if domain == "googlemail.com":
        domain = "gmail.com"
    if domain == "gmail.com":
        local = local.replace(".", "")
    return f"{local}@{domain}"


def get_or_create_user(sub, email, ip=None, device_id=None, source=None):
    """Returns the user row; on FIRST creation also records the soft abuse signals
    (device marker, IP signup velocity, duplicate normalized email). Signals only
    ever flag/score — the single hard rule is free_eligible=0 when this normalized
    email already claimed its free allotment on another account (they can still sign
    in; they just don't mint a fresh free class)."""
    with db() as c:
        row = c.execute("SELECT * FROM users WHERE google_sub=?", (sub,)).fetchone()
        if row:
            if email and row["email"] != email:
                c.execute("UPDATE users SET email=?, normalized_email=? WHERE id=?",
                          (email, normalize_email(email), row["id"]))
            return row
        norm = normalize_email(email)
        dup = c.execute("SELECT id FROM users WHERE normalized_email=? AND free_eligible=1",
                        (norm,)).fetchone() if norm else None
        risk = 0
        if dup:
            risk += 2
        if ip:
            recent = c.execute("SELECT COUNT(*) FROM users WHERE signup_ip=? AND created>?",
                               (ip, time.time() - 86400)).fetchone()[0]
            if recent >= 6:                   # generous: dorm/campus NAT is normal
                risk += 1
        if device_id:
            other = c.execute("SELECT COUNT(*) FROM device_markers WHERE device_id=?",
                              (device_id,)).fetchone()[0]
            if other:
                risk += 2                     # same device already created an account
        c.execute("INSERT INTO users(google_sub,email,topic,created,normalized_email,"
                  "risk_score,free_eligible,signup_ip,signup_source) "
                  "VALUES(?,?,?,?,?,?,?,?,?)",
                  (sub, email, "seatwatch-" + secrets.token_hex(6), time.time(),
                   norm, risk, 0 if dup else 1, ip or "", (source or "")[:64]))
        row = c.execute("SELECT * FROM users WHERE google_sub=?", (sub,)).fetchone()
        if device_id:
            c.execute("INSERT OR IGNORE INTO device_markers(device_id,user_id,first_seen) "
                      "VALUES(?,?,?)", (device_id, row["id"], time.time()))
        return row


# ------------------------------------------------------------------------- html
PAGE = """<!doctype html><html lang="en"><head><meta charset="utf-8">
__METAPIXEL__
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>SeatWatch: Get a text the second a full class opens | __COUNT__ universities</title>
<meta name="description" content="SeatWatch alerts you the instant a seat opens in a full college class, across __COUNT__ universities. Watch the exact section you want and get the professor you want. Free to start.">
<link rel="canonical" href="https://seatwatchapp.com/">
<meta name="robots" content="index, follow, max-image-preview:large">
<meta name="keywords" content="seatwatch, seat watch, course seat alert, class seat notification, college registration alert, open seat finder, coursicle alternative">
<meta name="author" content="SeatWatch LLC">
<meta name="application-name" content="SeatWatch">
<meta property="og:type" content="website">
<meta property="og:site_name" content="SeatWatch">
<meta property="og:title" content="SeatWatch: Get into the class you actually need">
<meta property="og:description" content="Get an instant alert the second a seat opens in a full college class, across __COUNT__ universities. Watch the exact section, get the professor you want.">
<meta property="og:url" content="https://seatwatchapp.com/">
<meta property="og:image" content="https://seatwatchapp.com/og-image.png">
<meta property="og:image:width" content="1200">
<meta property="og:image:height" content="630">
<meta name="twitter:card" content="summary_large_image">
<meta name="twitter:title" content="SeatWatch: Get into the class you actually need">
<meta name="twitter:description" content="Get an instant alert the second a seat opens in a full college class. __COUNT__ universities. Free to start.">
<meta name="twitter:image" content="https://seatwatchapp.com/og-image.png">
<script type="application/ld+json">{"@context":"https://schema.org","@graph":[{"@type":"Organization","@id":"https://seatwatchapp.com/#org","name":"SeatWatch","legalName":"SeatWatch LLC","url":"https://seatwatchapp.com/","logo":"https://seatwatchapp.com/icon-512.png","email":"support@seatwatchapp.com","address":{"@type":"PostalAddress","streetAddress":"2219 York Rd, Ste 400 #1032","addressLocality":"Timonium","addressRegion":"MD","postalCode":"21093","addressCountry":"US"},"description":"Instant alerts when a seat opens in a full college class, across __COUNT__ universities."},{"@type":"WebSite","@id":"https://seatwatchapp.com/#site","url":"https://seatwatchapp.com/","name":"SeatWatch","publisher":{"@id":"https://seatwatchapp.com/#org"}},{"@type":"WebApplication","name":"SeatWatch","url":"https://seatwatchapp.com/","applicationCategory":"EducationalApplication","operatingSystem":"Web","offers":{"@type":"Offer","price":"0","priceCurrency":"USD","description":"First class free"},"description":"Get an instant phone alert the second a seat opens in a full college class."}]}</script>
<link rel="icon" href="data:image/svg+xml,<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 120 120'><defs><linearGradient id='b' x1='0' y1='0' x2='1' y2='1'><stop offset='0' stop-color='%233b82f6'/><stop offset='1' stop-color='%232563eb'/></linearGradient></defs><path d='M40 14 H80 Q104 14 104 38 V72 Q104 96 80 96 H64 L54 110 L49 96 H36 Q12 96 12 72 V38 Q12 14 36 14 Z' fill='white' stroke='%232563eb' stroke-width='9' stroke-linejoin='round'/><rect x='42' y='32' width='28' height='24' rx='7' fill='url(%23b)'/><rect x='38' y='56' width='40' height='11' rx='5.5' fill='url(%23b)'/><rect x='42' y='67' width='8' height='15' rx='3' fill='url(%23b)'/><rect x='66' y='67' width='8' height='15' rx='3' fill='url(%23b)'/><circle cx='100' cy='20' r='11' fill='%2310b981' stroke='white' stroke-width='5'/><path d='M100 4 V1 M111 9 L114 6 M116 20 H119' stroke='%2310b981' stroke-width='4.5' stroke-linecap='round'/></svg>">
<meta name="theme-color" content="#F8FAFC">
<link rel="manifest" href="/manifest.json">
<link rel="apple-touch-icon" href="/icon-192.png">
<link rel="preconnect" href="https://fonts.googleapis.com"><link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Plus+Jakarta+Sans:wght@400;500;600;700;800&family=JetBrains+Mono:wght@500;600&display=swap" rel="stylesheet">
<style>
 *{box-sizing:border-box}
 :root{--bg:#F8FAFC;--txt:#0F172A;--mut:#475569;--dim:#94A3B8;--line:#E2E8F0;--line2:#EEF2F7;--blue:#2563EB;--blue2:#1D4ED8;--blue3:#3B82F6;--tint:#EFF5FF;--navy:#0F172A;--green:#10B981;--green2:#059669;--mono:'JetBrains Mono',ui-monospace,monospace;--spring:cubic-bezier(.34,1.56,.64,1);--ease:cubic-bezier(.4,0,.2,1)}
 ::selection{background:var(--blue);color:#fff}
 html{scroll-behavior:smooth}
 body{margin:0;overflow-x:hidden;font-family:'Plus Jakarta Sans',-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif;color:var(--txt);background:var(--bg);-webkit-font-smoothing:antialiased}
 body::before{content:"";position:fixed;inset:0;z-index:-2;background-image:linear-gradient(var(--line) 1px,transparent 1px),linear-gradient(90deg,var(--line) 1px,transparent 1px);background-size:48px 48px;opacity:.5;-webkit-mask-image:radial-gradient(743px 520px at 50% -40px,#000,transparent 72%);mask-image:radial-gradient(743px 520px at 50% -40px,#000,transparent 72%)}
 body::after{content:"";position:fixed;inset:0;z-index:-1;background:radial-gradient(743px 440px at 50% -130px,rgba(37,99,235,.12),transparent 68%),radial-gradient(600px 400px at 88% 8%,rgba(16,185,129,.05),transparent 60%)}
 a:focus-visible,button:focus-visible,input:focus-visible{outline:3px solid rgba(37,99,235,.5);outline-offset:2px}
 @media(prefers-reduced-motion:reduce){*,*::before,*::after{animation:none!important;transition:none!important}}
 a{color:var(--blue);text-decoration:none} a:hover{text-decoration:underline}
 svg{display:block}
 @keyframes rise{from{opacity:0;transform:translateY(16px)}to{opacity:1;transform:none}}
 @keyframes blurin{from{opacity:0;filter:blur(9px);transform:translateY(14px)}to{opacity:1;filter:blur(0);transform:none}}
 @keyframes pulse{0%,100%{opacity:1}50%{opacity:.35}}
 @keyframes float{0%,100%{transform:translateY(0) rotate(-.5deg)}50%{transform:translateY(-9px) rotate(.4deg)}}
 @keyframes shimmer{to{background-position:-200% 0}}
 .reveal{animation:blurin .7s var(--ease) both}
 .d1{animation-delay:.06s}.d2{animation-delay:.13s}.d3{animation-delay:.2s}.d4{animation-delay:.28s}
 header{position:sticky;top:0;z-index:50;background:rgba(248,250,252,.72);backdrop-filter:saturate(180%) blur(18px);-webkit-backdrop-filter:saturate(180%) blur(18px);border-bottom:1px solid rgba(15,23,42,.06)}
 .nav{max-width:1040px;margin:0 auto;padding:13px 24px;display:flex;align-items:center;gap:11px}
 .nav .mark{width:38px;height:38px;display:block;filter:drop-shadow(0 3px 8px rgba(37,99,235,.24))}
 .nav .word{font-weight:800;font-size:21px;letter-spacing:-.6px;color:var(--navy)}
 .nav .word i{font-style:normal;color:var(--blue)}
 .nav .spacer{flex:1}
 .nav .signin{display:inline-flex;align-items:center;gap:6px;font-size:14px;font-weight:600;color:var(--mut);border:1px solid var(--line);background:#fff;padding:8px 14px;border-radius:10px;transition:all .18s var(--ease)}
 .nav .signin:hover{color:var(--blue);border-color:#C7D2FE;box-shadow:0 4px 12px rgba(37,99,235,.1);text-decoration:none;transform:translateY(-1px)}
 main{max-width:640px;margin:0 auto;padding:0 22px 96px}
 .hero{text-align:center;padding:70px 0 16px}
 .badge{position:relative;overflow:hidden;display:inline-flex;align-items:center;gap:8px;font-family:var(--mono);font-size:10.5px;font-weight:600;letter-spacing:.11em;color:var(--mut);border:1px solid var(--line);background:#fff;padding:8px 15px;border-radius:999px;margin-bottom:28px;box-shadow:0 1px 3px rgba(15,23,42,.06)}
 .badge::after{content:"";position:absolute;inset:0;background:linear-gradient(110deg,transparent 32%,rgba(37,99,235,.13) 50%,transparent 68%);background-size:200% 100%;animation:shimmer 4s linear infinite}
 .dotlive{width:7px;height:7px;border-radius:50%;background:var(--green);box-shadow:0 0 0 3px rgba(16,185,129,.2);animation:pulse 2.2s infinite}
 .hero h1{font-size:57px;line-height:1.03;margin:0 0 20px;letter-spacing:-2.8px;font-weight:800;color:var(--navy)}
 .grad{background:linear-gradient(100deg,#2563EB,#3B82F6);-webkit-background-clip:text;background-clip:text;color:transparent}
 .hero p.lede{font-size:19px;line-height:1.6;color:var(--mut);margin:0 auto 34px;max-width:548px;font-weight:400}
 .notif{display:flex;gap:12px;align-items:flex-start;background:rgba(255,255,255,.92);backdrop-filter:blur(14px);border:1px solid rgba(15,23,42,.08);border-radius:18px;padding:14px 17px;max-width:404px;margin:0 auto 40px;box-shadow:0 24px 60px rgba(15,23,42,.16);text-align:left;animation:float 5.5s ease-in-out infinite}
 .notif .nicon{width:40px;height:40px;flex:none}
 .nbody{flex:1;min-width:0}
 .nrow{display:flex;justify-content:space-between;align-items:baseline;gap:8px}
 .nrow b{font-size:13.5px;color:var(--txt)}
 .nrow .live{display:inline-flex;align-items:center;gap:4px;font-size:11px;color:var(--green2);font-weight:600}
 .notif p{margin:3px 0 0;font-size:13.5px;line-height:1.5;color:#334155}
 .stats{display:grid;grid-template-columns:repeat(3,1fr);gap:12px;margin:0 auto 40px;max-width:470px}
 .stat{background:#fff;border:1px solid var(--line);border-radius:16px;padding:18px 10px 15px;text-align:center;box-shadow:0 1px 3px rgba(15,23,42,.05);transition:transform .22s var(--spring),box-shadow .22s var(--ease)}
 .stat:hover{transform:translateY(-3px);box-shadow:0 14px 30px rgba(15,23,42,.1)}
 .chip{width:36px;height:36px;border-radius:11px;background:var(--tint);color:var(--blue);display:flex;align-items:center;justify-content:center;margin:0 auto 11px}
 .stat b{display:block;font-family:var(--mono);font-size:20px;font-weight:600;color:var(--navy);letter-spacing:-.03em;margin-bottom:3px}
 .stat span{font-size:9.5px;font-weight:700;letter-spacing:.11em;text-transform:uppercase;color:var(--dim)}
 .card{background:#fff;border:1px solid var(--line);border-radius:24px;padding:32px;box-shadow:0 1px 3px rgba(15,23,42,.05),0 30px 68px -20px rgba(15,23,42,.18)}
 .card h2.ct{margin:0 0 5px;font-size:20px;font-weight:800;letter-spacing:-.5px;color:var(--navy)}
 .card p.cs{margin:0 0 20px;font-size:14.5px;color:var(--mut);line-height:1.55}
 label{display:block;font-weight:600;font-size:12.5px;margin:18px 0 8px;color:#334155;letter-spacing:.01em}
 form label:first-of-type{margin-top:0}
 input{width:100%;padding:13px 14px;border:1px solid #CBD5E1;border-radius:12px;font-size:15px;font-family:inherit;color:var(--txt);background:#F8FAFC;transition:border .16s var(--ease),box-shadow .16s var(--ease),background .16s var(--ease)}
 input::placeholder{color:#94A3B8}
 input:focus{outline:none;border-color:var(--blue);background:#fff;box-shadow:0 0 0 4px rgba(37,99,235,.13)}
 small{color:var(--dim);font-weight:500}
 button{display:inline-flex;align-items:center;justify-content:center;gap:8px;width:100%;margin-top:24px;padding:15px;background:var(--blue);color:#fff;border:none;border-radius:13px;font-size:15.5px;font-weight:700;font-family:inherit;letter-spacing:.005em;cursor:pointer;box-shadow:0 8px 22px -4px rgba(37,99,235,.45);transition:background .18s var(--ease),transform .18s var(--spring),box-shadow .18s var(--ease)}
 button:hover{background:var(--blue2);transform:translateY(-2px);box-shadow:0 14px 30px -6px rgba(37,99,235,.55)}
 button:active{transform:translateY(0) scale(.99)}
 button svg{transition:transform .2s var(--spring)}
 button:hover svg{transform:translateX(3px)}
 .combo{position:relative}
 .dropdown{display:none;position:absolute;left:0;right:0;top:calc(100% + 6px);z-index:30;background:#fff;border:1px solid var(--line);border-radius:13px;max-height:254px;overflow-y:auto;box-shadow:0 22px 54px rgba(15,23,42,.16);padding:5px}
 .dropdown .opt{padding:11px 13px;font-size:14.5px;cursor:pointer;color:#334155;border-radius:9px}
 .dropdown .opt:hover{background:var(--tint);color:var(--blue2)}
 .note{font-size:12.5px;color:var(--dim);text-align:center;margin:14px 0 0;line-height:1.5}
 .gbtn{display:flex;align-items:center;justify-content:center;gap:10px;width:100%;padding:14px;background:#fff;border:1px solid #CBD5E1;border-radius:13px;font-size:15px;font-weight:700;color:var(--txt);box-shadow:0 1px 3px rgba(15,23,42,.07);transition:all .16s var(--ease)}
 .gbtn:hover{transform:translateY(-1px);border-color:#94A3B8;box-shadow:0 10px 22px rgba(15,23,42,.1);text-decoration:none}
 .userbar{display:flex;justify-content:space-between;align-items:center;font-size:12.5px;color:var(--dim);margin-bottom:18px;padding-bottom:14px;border-bottom:1px solid var(--line2)}
 .userbar b{color:var(--mut);font-weight:600}
 .userbar a{color:var(--dim);font-weight:600;display:inline-flex;align-items:center;gap:4px}
 .userbar a:hover{color:var(--blue)}
 .mywatches{margin-top:22px;border-top:1px solid var(--line2);padding-top:16px}
 .mywatches b{font-size:11px;letter-spacing:.1em;text-transform:uppercase;color:var(--dim);display:flex;align-items:center;gap:6px}
 .mywatches ul{list-style:none;padding:0;margin:10px 0 0}
 .mywatches li{display:flex;justify-content:space-between;align-items:center;gap:10px;font-size:14px;padding:10px 12px;color:#334155;background:#F8FAFC;border:1px solid var(--line2);border-radius:11px;margin-bottom:8px}
 .mywatches li span{font-family:var(--mono);font-size:13px;font-weight:500}
 button.stop{width:auto;margin:0;padding:6px 12px;background:#fff;color:#DC2626;border:1px solid #FECACA;border-radius:9px;font-size:12px;font-weight:600;box-shadow:none;gap:5px}
 button.stop:hover{background:#FEF2F2;transform:none;box-shadow:none}
 .ok{display:flex;gap:10px;align-items:flex-start;background:#ECFDF5;border:1px solid #A7F3D0;border-radius:13px;padding:15px 16px;margin-bottom:14px;font-size:14.5px;line-height:1.5;color:#065F46}
 .ok svg{flex:none;margin-top:1px}
 .err{display:flex;gap:10px;align-items:flex-start;background:#FEF2F2;border:1px solid #FECACA;border-radius:13px;padding:15px 16px;margin-bottom:14px;font-size:14.5px;line-height:1.5;color:#991B1B}
 .err svg{flex:none;margin-top:1px}
 code{background:var(--tint);color:var(--blue2);font-family:var(--mono);padding:3px 9px;border-radius:7px;font-size:13px;font-weight:500;word-break:break-all}
 ol{padding-left:20px;font-size:14.5px;line-height:1.8;color:#334155}
 .sub{color:var(--dim);font-size:13px}
 section.blk{margin-top:88px}
 section.blk h2{font-size:32px;margin:0 0 8px;font-weight:800;letter-spacing:-1.3px;color:var(--navy);text-align:center}
 section.blk .lede2{text-align:center;color:var(--mut);font-size:15.5px;margin:0 auto 28px;max-width:400px}
 .steps{display:grid;gap:12px}
 .step{display:flex;gap:15px;align-items:flex-start;background:#fff;border:1px solid var(--line);border-radius:16px;padding:19px 20px;box-shadow:0 1px 3px rgba(15,23,42,.05);transition:transform .22s var(--spring),box-shadow .22s var(--ease),border-color .2s}
 .step:hover{transform:translateY(-3px);box-shadow:0 16px 34px rgba(15,23,42,.1);border-color:#C7D2FE}
 .step .chip{margin:0;flex:none}
 .step b{display:block;font-size:15px;margin-bottom:3px;color:var(--navy);font-weight:700}
 .step span{font-size:13.5px;color:var(--mut);line-height:1.55}
 .prices{display:grid;gap:14px;grid-template-columns:repeat(4,1fr);max-width:1040px;margin:0 auto}
 .price{position:relative;background:#fff;border:1px solid var(--line);border-radius:20px;padding:24px;box-shadow:0 1px 3px rgba(15,23,42,.05);transition:transform .22s var(--spring),box-shadow .22s var(--ease)}
 .price:hover{transform:translateY(-4px);box-shadow:0 22px 46px rgba(15,23,42,.12)}
 .price.free{border:1.5px solid var(--green);box-shadow:0 10px 34px rgba(16,185,129,.16)}
 .price.free:hover{box-shadow:0 24px 50px rgba(16,185,129,.24)}
 .price .tag{display:inline-block;font-family:var(--mono);font-size:10px;font-weight:700;letter-spacing:.12em;text-transform:uppercase;color:var(--green2);margin-bottom:9px}
 .price .tag.soon{color:var(--dim)}
 .price .amt{font-size:32px;font-weight:800;margin:0 0 14px;letter-spacing:-1.3px;color:var(--navy)}
 .price .amt small{font-size:13px;color:var(--dim);font-weight:500;letter-spacing:0}
 .feat{list-style:none;padding:0;margin:0}
 .feat li{display:flex;gap:9px;align-items:flex-start;font-size:13.5px;color:var(--mut);line-height:1.45;margin-bottom:9px}
 .feat li svg{flex:none;margin-top:1px;color:var(--green)}
 .price:not(.free) .feat li svg{color:var(--blue3)}
 .tagline{font-size:13px;font-weight:700;color:var(--navy);letter-spacing:-.1px}
 .tagline em{font-style:normal;color:var(--green2)}
 footer{text-align:center;font-size:12px;color:var(--dim);padding:48px 20px 54px;line-height:2;letter-spacing:.02em}
 footer a{color:#64748B}
 /* --- scroll-reveal: sections ease up + un-blur as they enter view --- */
 .sr{opacity:0;transform:translateY(26px);filter:blur(6px);transition:opacity .7s var(--ease),transform .8s var(--spring),filter .7s var(--ease);transition-delay:calc(var(--i,0)*90ms)}
 .sr.in{opacity:1;transform:none;filter:blur(0)}
 /* --- social proof / testimonials --- */
 .quotes{display:grid;gap:14px;grid-template-columns:repeat(3,1fr)}
 .quote{background:#fff;border:1px solid var(--line);border-radius:18px;padding:20px 19px;box-shadow:0 1px 3px rgba(15,23,42,.05);text-align:left;display:flex;flex-direction:column;gap:13px;transition:transform .22s var(--spring),box-shadow .22s var(--ease),border-color .2s}
 .quote:hover{transform:translateY(-4px);box-shadow:0 18px 38px rgba(15,23,42,.1);border-color:#C7D2FE}
 .quote .stars{display:flex;gap:2px;color:#F5A623}
 .quote p{margin:0;font-size:14px;line-height:1.6;color:#334155;flex:1}
 .who{display:flex;align-items:center;gap:11px}
 .who .av{width:38px;height:38px;border-radius:50%;flex:none;display:flex;align-items:center;justify-content:center;font-weight:700;font-size:14px;color:#fff;letter-spacing:-.02em}
 .who .nm{font-size:13px;font-weight:700;color:var(--navy);line-height:1.25}
 .who .mt{font-size:11.5px;color:var(--dim);font-weight:500}
 /* --- FAQ --- */
 .faq{display:grid;gap:11px;max-width:560px;margin:0 auto}
 .faq details{background:#fff;border:1px solid var(--line);border-radius:15px;padding:2px 20px;box-shadow:0 1px 3px rgba(15,23,42,.05);transition:border-color .2s,box-shadow .2s}
 .faq details[open]{border-color:#C7D2FE;box-shadow:0 12px 28px rgba(15,23,42,.08)}
 .faq summary{list-style:none;cursor:pointer;padding:17px 0;font-size:15px;font-weight:700;color:var(--navy);display:flex;justify-content:space-between;align-items:center;gap:12px}
 .faq summary::-webkit-details-marker{display:none}
 .faq summary .pm{flex:none;width:22px;height:22px;border-radius:7px;background:var(--tint);color:var(--blue);display:flex;align-items:center;justify-content:center;font-size:17px;font-weight:600;transition:transform .28s var(--spring),background .2s}
 .faq details[open] summary .pm{transform:rotate(135deg);background:var(--blue);color:#fff}
 .faq details p{margin:0 0 18px;font-size:14px;line-height:1.65;color:var(--mut)}
 /* --- final call to action --- */
 .cta{position:relative;overflow:hidden;text-align:center;background:linear-gradient(135deg,#1D4ED8,#2563EB 45%,#3B82F6);border-radius:26px;padding:44px 30px;box-shadow:0 24px 60px -18px rgba(37,99,235,.55)}
 .cta::before{content:"";position:absolute;inset:0;background:radial-gradient(420px 200px at 20% 0,rgba(255,255,255,.22),transparent 60%),radial-gradient(360px 220px at 90% 120%,rgba(16,185,129,.28),transparent 62%)}
 .blk .cta h2{position:relative;color:#fff;font-size:29px;letter-spacing:-1.2px;margin:0 0 9px}
 .cta p{position:relative;color:rgba(255,255,255,.9);font-size:15.5px;margin:0 auto 22px;max-width:400px;line-height:1.55}
 .cta .cbtn{position:relative;display:inline-flex;align-items:center;gap:9px;background:#fff;color:var(--blue2);font-weight:700;font-size:15.5px;padding:14px 26px;border-radius:13px;box-shadow:0 10px 26px rgba(0,0,0,.18);transition:transform .18s var(--spring),box-shadow .18s var(--ease)}
 .cta .cbtn:hover{transform:translateY(-2px);box-shadow:0 16px 34px rgba(0,0,0,.24);text-decoration:none}
 .cta .cbtn svg{transition:transform .2s var(--spring)}
 .cta .cbtn:hover svg{transform:translateX(3px)}
 @media(max-width:560px){.hero{padding-top:46px}.hero h1{font-size:33px;letter-spacing:-1.5px}.hero p.lede{font-size:16px}.badge{font-size:9.5px;letter-spacing:.08em}.prices{grid-template-columns:1fr}.quotes{grid-template-columns:1fr}.nav .word{font-size:19px}.nav .signin{padding:7px 11px;font-size:13px}section.blk h2{font-size:26px}.blk .cta h2{font-size:24px}}
</style></head><body>
<header><div class="nav"><svg class="mark" viewBox="0 0 120 120" xmlns="http://www.w3.org/2000/svg"><defs><linearGradient id="b" x1="0" y1="0" x2="1" y2="1"><stop offset="0" stop-color="#3b82f6"/><stop offset="1" stop-color="#2563eb"/></linearGradient></defs><path d="M40 14 H80 Q104 14 104 38 V72 Q104 96 80 96 H64 L54 110 L49 96 H36 Q12 96 12 72 V38 Q12 14 36 14 Z" fill="#fff" stroke="#2563eb" stroke-width="9" stroke-linejoin="round"/><rect x="42" y="32" width="28" height="24" rx="7" fill="url(#b)"/><rect x="38" y="56" width="40" height="11" rx="5.5" fill="url(#b)"/><rect x="42" y="67" width="8" height="15" rx="3" fill="url(#b)"/><rect x="66" y="67" width="8" height="15" rx="3" fill="url(#b)"/><circle cx="100" cy="20" r="11" fill="#10b981" stroke="#fff" stroke-width="5"/><path d="M100 4 V1 M111 9 L114 6 M116 20 H119" stroke="#10b981" stroke-width="4.5" stroke-linecap="round"/></svg><span class="word"><i>Seat</i>Watch</span><span class="spacer"></span><a class="signin" href="/login"><svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M15 3h4a2 2 0 0 1 2 2v14a2 2 0 0 1-2 2h-4"/><polyline points="10 17 15 12 10 7"/><line x1="15" y1="12" x2="3" y2="12"/></svg>Sign in</a></div></header>
<main>__BODY__</main>
<footer><span class="tagline">We watch seats. <em>You get the class.</em></span>__FEEDBACK__<br>© 2026 SeatWatch &nbsp;·&nbsp; <a href="/terms">Terms</a> &nbsp;·&nbsp; <a href="/privacy">Privacy</a> &nbsp;·&nbsp; <a href="/privacy#adchoices">Privacy &amp; Ad Choices</a> &nbsp;·&nbsp; <a href="/text-alerts">Text Alerts</a> &nbsp;·&nbsp; <a href="/sms-terms">SMS Terms</a><br>Not affiliated with any university.</footer>
<script>
(function(){/* durable device marker: cookie + localStorage mirror (soft signal only) */
try{
 var m=document.cookie.match(/(?:^|; )sw_dev=([A-Za-z0-9-]{8,64})/),c=m&&m[1],l=null;
 try{l=localStorage.getItem('sw_dev');}catch(e){}
 var v=c||l;
 if(!v){var a=new Uint8Array(16);(window.crypto||{}).getRandomValues?crypto.getRandomValues(a):a.forEach(function(_,i){a[i]=Math.floor(Math.random()*256);});
  v=Array.prototype.map.call(a,function(b){return b.toString(16).padStart(2,'0');}).join('');}
 if(!c)document.cookie='sw_dev='+v+'; Path=/; Max-Age=34560000; SameSite=Lax; Secure';
 try{if(l!==v)localStorage.setItem('sw_dev',v);}catch(e){}
}catch(e){}
})();
</script>
</body></html>"""

FORM = """<section class="hero">
 <div class="badge reveal"><span class="dotlive"></span>LIVE · WATCHING __COUNT__ UNIVERSITIES</div>
 <h1 class="reveal d1">Get into the class you <span class="grad">actually need</span>.</h1>
 <p class="lede reveal d2">That full class you're stuck on? We watch it around the clock and buzz your phone the instant a seat opens. Free to start, and we never show fake openings.</p>
 <div class="notif reveal d3" aria-hidden="true"><svg class="nicon" viewBox="0 0 120 120" xmlns="http://www.w3.org/2000/svg"><path d="M40 14 H80 Q104 14 104 38 V72 Q104 96 80 96 H64 L54 110 L49 96 H36 Q12 96 12 72 V38 Q12 14 36 14 Z" fill="#fff" stroke="#2563eb" stroke-width="9" stroke-linejoin="round"/><rect x="42" y="32" width="28" height="24" rx="7" fill="url(#b)"/><rect x="38" y="56" width="40" height="11" rx="5.5" fill="url(#b)"/><rect x="42" y="67" width="8" height="15" rx="3" fill="url(#b)"/><rect x="66" y="67" width="8" height="15" rx="3" fill="url(#b)"/><circle cx="100" cy="20" r="11" fill="#10b981" stroke="#fff" stroke-width="5"/></svg><div class="nbody"><div class="nrow"><b>SeatWatch</b><span class="live"><svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="3" stroke-linecap="round" stroke-linejoin="round"><polyline points="20 6 9 17 4 12"/></svg>now</span></div><p>Seat open: <b>ENG101-0101</b>: 2 seats just opened.</p></div></div>
 <div class="stats reveal d4">
  <div class="stat"><div class="chip"><svg width="19" height="19" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M21.42 10.922a1 1 0 0 0-.019-1.838L12.83 5.18a2 2 0 0 0-1.66 0L2.6 9.08a1 1 0 0 0 0 1.832l8.57 3.908a2 2 0 0 0 1.66 0z"/><path d="M22 10v6"/><path d="M6 12.5V16a6 3 0 0 0 12 0v-3.5"/></svg></div><b data-count="__COUNT__">__COUNT__</b><span>universities</span></div>
  <div class="stat"><div class="chip"><svg width="19" height="19" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="10"/><polyline points="12 6 12 12 16 14"/></svg></div><b>20s</b><span>check interval</span></div>
  <div class="stat"><div class="chip"><svg width="19" height="19" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M19.07 4.93A10 10 0 0 0 6.99 3.34"/><path d="M4 6h.01"/><path d="M2.29 9.62A10 10 0 1 0 21.31 8.35"/><path d="M16.24 7.76A6 6 0 1 0 8.23 16.67"/><path d="M12 18h.01"/><path d="M17.99 11.66A6 6 0 0 1 15.77 16.67"/><circle cx="12" cy="12" r="2"/><path d="m13.41 10.59 5.66-5.66"/></svg></div><b>24/7</b><span>monitoring</span></div>
 </div>
</section>
__CARD__
<section class="blk sr">
 <h2>Get the professor you want.</h2>
 <p class="lede2">Stuck out of the class, or the exact section, you were hoping for? SeatWatch watches the <b>specific section you pick</b>, so you land the <b>professor, time, and class</b> you actually want the moment a seat opens up. Not just any seat. <em>Your</em> seat.</p>
</section>
<section class="blk sr">
 <h2>How it works</h2>
 <p class="lede2">Three steps between you and the class you need.</p>
 <div class="steps">
  <div class="step"><div class="chip"><svg width="19" height="19" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="11" cy="11" r="8"/><path d="m21 21-4.3-4.3"/></svg></div><div><b>Tell us your class</b><span>Pick your school, the course, and the section(s) you want to watch.</span></div></div>
  <div class="step"><div class="chip"><svg width="19" height="19" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M2 12a10 10 0 0 1 10-10"/><path d="M2 12a10 10 0 0 0 10 10"/><path d="M12 2a10 10 0 0 1 10 10"/><circle cx="12" cy="12" r="3"/></svg></div><div><b>We watch it around the clock</b><span>Our engine checks the live registration site every 20 seconds. Fast and accurate.</span></div></div>
  <div class="step"><div class="chip"><svg width="19" height="19" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M10.268 21a2 2 0 0 0 3.464 0"/><path d="M3.262 15.326A1 1 0 0 0 4 17h16a1 1 0 0 0 .74-1.673C19.41 13.956 18 12.499 18 8A6 6 0 0 0 6 8c0 4.499-1.411 5.956-2.738 7.326"/></svg></div><div><b>Your phone buzzes instantly</b><span>The second a real seat opens, you get a push alert. Tap it and go register.</span></div></div>
 </div>
</section>
<section class="blk sr">
 <h2>Students get their class back.</h2>
 <p class="lede2">The seat you need can open at 2am. We're the ones watching so you don't have to.</p>
 <div class="quotes">
  <div data-reveal style="background:#fff;border:1px solid rgba(11,21,38,.07);border-radius:20px;padding:28px;box-shadow:0 10px 30px -14px rgba(11,21,38,.1);display:flex;flex-direction:column;gap:12px;"><div style="font-size:26px;">🎯</div><div style="font-size:16px;font-weight:800;color:#0b1526;">Never a fake alert</div><p style="margin:0;font-size:14.5px;line-height:1.6;color:#4b5a72;">We notify you only when a seat is genuinely open. Real registration data, checked live, every time.</p></div>
    <div data-reveal style="background:#fff;border:1px solid rgba(11,21,38,.07);border-radius:20px;padding:28px;box-shadow:0 10px 30px -14px rgba(11,21,38,.1);display:flex;flex-direction:column;gap:12px;transition-delay:.08s;"><div style="font-size:26px;">⏱️</div><div style="font-size:16px;font-weight:800;color:#0b1526;">Always watching</div><p style="margin:0;font-size:14.5px;line-height:1.6;color:#4b5a72;">We check around the clock, roughly every 20 seconds, so you never have to refresh a registration page again.</p></div>
    <div data-reveal style="background:#fff;border:1px solid rgba(11,21,38,.07);border-radius:20px;padding:28px;box-shadow:0 10px 30px -14px rgba(11,21,38,.1);display:flex;flex-direction:column;gap:12px;transition-delay:.16s;"><div style="font-size:26px;">🎓</div><div style="font-size:16px;font-weight:800;color:#0b1526;">The exact section you want</div><p style="margin:0;font-size:14.5px;line-height:1.6;color:#4b5a72;">Watch a specific section to land the professor, time, or campus that actually fits your schedule.</p></div>
 </div>
</section>
__PRICING__
<section class="blk sr">
 <h2>Questions, answered.</h2>
 <p class="lede2">The stuff students actually ask us.</p>
 <div class="faq">
  <details><summary>Is it really free?<span class="pm">+</span></summary><p>Yes. Your first class, up to two sections, is completely free. No credit card, no trial clock. We only ask you to sign in so your watch stays tied to you.</p></details>
  <details><summary>How fast will I hear about an open seat?<span class="pm">+</span></summary><p>We check your class's live registration system every 20 seconds, around the clock. The instant a real seat appears, your phone gets a push alert, usually within seconds of it opening.</p></details>
  <details><summary>Will you ever send a fake alert?<span class="pm">+</span></summary><p>Never. We read the true seat count straight from your school's registration system and only alert on a genuinely open seat. If our engine can't confirm a seat is really open, it stays silent. No false alarms.</p></details>
  <details><summary>Can I watch a specific section or professor?<span class="pm">+</span></summary><p>That's the whole point. You pick the exact section(s) you want, so you land the professor, time, and class you're actually after, not just any open seat.</p></details>
  <details><summary>Is my school supported?<span class="pm">+</span></summary><p>We watch classes at <b data-count2="__COUNT__">__COUNT__</b> universities and colleges, and we're adding more every week. Start typing your school in the box above. If it's there, you're good to go.</p></details>
  <details><summary>Is this against my school's rules?<span class="pm">+</span></summary><p>No. SeatWatch only reads the same public class-availability info you'd see yourself. It never logs into your account or registers for you. When a seat opens, <i>you</i> tap the alert and register, just like normal.</p></details>
 </div>
</section>
<section class="blk sr">
 <div class="cta">
  <h2>Your seat is out there.</h2>
  <p>Let us watch for it. Set up your first class free in under a minute, and get on with your day.</p>
  <a class="cbtn" href="/login">Start watching free<svg width="17" height="17" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.4" stroke-linecap="round" stroke-linejoin="round"><path d="M5 12h14"/><path d="m12 5 7 7-7 7"/></svg></a>
  <p style="margin-top:12px;font-size:12px;color:rgba(255,255,255,.65);">By continuing, you agree to our <a href="/terms" style="color:rgba(255,255,255,.85);">Terms of Service</a> and <a href="/privacy" style="color:rgba(255,255,255,.85);">Privacy Policy</a>.</p>
 </div>
</section>
<script>
(function(){
var mq=window.matchMedia&&matchMedia('(prefers-reduced-motion: reduce)').matches;
/* scroll-reveal: reveal sections as they enter the viewport */
var srs=[].slice.call(document.querySelectorAll('.sr'));
if(mq){srs.forEach(function(e){e.classList.add('in');});}
else if('IntersectionObserver' in window){
 var io=new IntersectionObserver(function(en){en.forEach(function(x){
   if(x.isIntersecting){x.target.classList.add('in');io.unobserve(x.target);}});},
   {threshold:.14,rootMargin:'0px 0px -8% 0px'});
 srs.forEach(function(e){io.observe(e);});
}else{srs.forEach(function(e){e.classList.add('in');});}
if(mq)return;
var el=document.querySelector('[data-count]');if(!el)return;
var target=+el.getAttribute('data-count'),t0=null;
function step(ts){if(!t0)t0=ts;var p=Math.min((ts-t0)/900,1);
 el.textContent=Math.round(target*(1-Math.pow(1-p,3)));if(p<1)requestAnimationFrame(step);}
requestAnimationFrame(step);
})();
</script>"""

CARD_LOGIN = """<div class="card reveal d2">
__NOTICE__
<h2 class="ct">Start watching your class</h2>
<p class="cs">Sign in so your watches stay yours. One click, no password, no spam ever.</p>
<a class="gbtn" href="/login/google"><svg width="18" height="18" viewBox="0 0 48 48"><path fill="#EA4335" d="M24 9.5c3.54 0 6.71 1.22 9.21 3.6l6.85-6.85C35.9 2.38 30.47 0 24 0 14.62 0 6.51 5.38 2.56 13.22l7.98 6.19C12.43 13.72 17.74 9.5 24 9.5z"/><path fill="#4285F4" d="M46.98 24.55c0-1.57-.15-3.09-.38-4.55H24v9.02h12.94c-.58 2.96-2.26 5.48-4.78 7.18l7.73 6c4.51-4.18 7.09-10.36 7.09-17.65z"/><path fill="#FBBC05" d="M10.53 28.59c-.48-1.45-.76-2.99-.76-4.59s.27-3.14.76-4.59l-7.98-6.19C.92 16.46 0 20.12 0 24c0 3.88.92 7.54 2.56 10.78l7.97-6.19z"/><path fill="#34A853" d="M24 48c6.48 0 11.93-2.13 15.89-5.81l-7.73-6c-2.15 1.45-4.92 2.3-8.16 2.3-6.26 0-11.57-4.22-13.47-9.91l-7.98 6.19C6.51 42.62 14.62 48 24 48z"/></svg>Continue with Google</a>
__APPLEBTN__
<p class="note" style="margin-top:10px;font-size:12px">By continuing, you agree to our <a href="/terms">Terms of Service</a> and <a href="/privacy">Privacy Policy</a>.</p>
<p class="note">Free: watch <b>1 class (up to 2 sections)</b>. No card required.</p>
</div>"""

# Apple mandates the black button style; shown only when Sign in with Apple is live.
APPLE_BTN = """<a class="gbtn" href="/login/apple" style="background:#000;color:#fff;border-color:#000;margin-top:10px"><svg width="17" height="17" viewBox="0 0 24 24" fill="currentColor"><path d="M17.05 20.28c-.98.95-2.05.8-3.08.35-1.09-.46-2.09-.48-3.24 0-1.44.62-2.2.44-3.06-.35C2.79 15.25 3.51 7.59 9.05 7.31c1.35.07 2.29.74 3.08.8 1.18-.24 2.31-.93 3.57-.84 1.51.12 2.65.72 3.4 1.8-3.12 1.87-2.38 5.98.48 7.13-.57 1.5-1.31 2.99-2.53 4.09zM12.03 7.25c-.15-2.23 1.66-4.07 3.74-4.25.29 2.58-2.34 4.5-3.74 4.25z"/></svg>Continue with Apple</a>"""

CARD_FORM = """<div class="card reveal d2">
<div class="userbar"><span>Signed in as <b>__EMAIL__</b></span><a href="/logout"><svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M9 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h4"/><polyline points="16 17 21 12 16 7"/><line x1="21" y1="12" x2="9" y2="12"/></svg>Sign out</a></div>
__NOTICE__
<form method="post" action="/watch" autocomplete="off">
 <input type="hidden" name="csrf" value="__CSRF__">
 <label>Your school</label>
 <div class="combo">
  <input type="text" id="schoolSearch" placeholder="Type your school (e.g. Maryland)…" autocomplete="off">
  <input type="hidden" name="school" id="schoolId" required>
  <div id="schoolList" class="dropdown"></div>
 </div>
 <label>Course code <small id="ex"></small></label>
 <input name="course" id="course" placeholder="e.g. ENG101" required>
__SECFIELD__ __PHONEFIELD__
 <button type="submit">Watch this class<svg width="17" height="17" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round"><path d="M5 12h14"/><path d="m12 5 7 7-7 7"/></svg></button>
</form>
__PLANNOTE__
__PUSHBLOCK__
__WATCHES__
<script>
var SCHOOLS=__SCHOOLS__;
var srch=document.getElementById('schoolSearch'),hid=document.getElementById('schoolId'),
    list=document.getElementById('schoolList'),exEl=document.getElementById('ex'),
    course=document.getElementById('course');
function pick(s){srch.value=s.name;hid.value=s.id;list.style.display='none';
  exEl.textContent='';course.placeholder='e.g. '+s.ex;
  try{localStorage.setItem('sw_school',s.id);}catch(e){}}
function render(q){q=(q||'').trim().toLowerCase();
  var m=SCHOOLS.filter(function(s){var n=s.name.toLowerCase();
    if(!q)return true;if(n.indexOf(q)===0)return true;
    return n.split(/[^a-z0-9]+/).some(function(w){return w.indexOf(q)===0;});});
  list.innerHTML='';m.forEach(function(s){var d=document.createElement('div');
    d.textContent=s.name;d.className='opt';d.onmousedown=function(){pick(s);};
    list.appendChild(d);});list.style.display=m.length?'block':'none';}
srch.addEventListener('input',function(){hid.value='';render(srch.value);});
srch.addEventListener('focus',function(){render(srch.value);});
srch.addEventListener('blur',function(){setTimeout(function(){list.style.display='none';},150);});
document.querySelector('form').addEventListener('submit',function(e){
  if(!hid.value){var q=srch.value.trim().toLowerCase();
    var s=SCHOOLS.find(function(x){return x.name.toLowerCase()===q;});
    if(s){hid.value=s.id;}else{e.preventDefault();srch.focus();render(srch.value);}}});
try{var saved=localStorage.getItem('sw_school');
  if(saved){var s0=SCHOOLS.find(function(x){return x.id===saved;});if(s0)pick(s0);}}catch(e){}
</script>
</div>"""

SW_JS = """self.addEventListener('push', function(e){
  var d = {};
  try { d = e.data.json(); } catch(err) {}
  e.waitUntil(self.registration.showNotification(d.title || 'SeatWatch', {
    body: d.body || 'A seat opened!', icon: '/icon-192.png', badge: '/icon-192.png',
    data: {url: d.url || 'https://seatwatchapp.com/'},
    tag: d.tag || 'seatwatch', renotify: true, requireInteraction: true,
    vibrate: [200, 100, 200]
  }));
});
self.addEventListener('notificationclick', function(e){
  e.notification.close();
  e.waitUntil(clients.openWindow((e.notification.data && e.notification.data.url) || '/'));
});
self.addEventListener('install', function(){ self.skipWaiting(); });
self.addEventListener('activate', function(e){ e.waitUntil(clients.claim()); });
"""

MANIFEST = json.dumps({
    "name": "SeatWatch", "short_name": "SeatWatch",
    "description": "Get an instant alert the second a seat opens in a full class.",
    "id": "/", "scope": "/",
    "start_url": "/", "display": "standalone",
    "background_color": "#F8FAFC", "theme_color": "#2563EB",
    "icons": [{"src": "/icon-192.png", "sizes": "192x192", "type": "image/png"},
              {"src": "/icon-512.png", "sizes": "512x512", "type": "image/png",
               "purpose": "any maskable"}]})


def _media_ver(name):
    """A short version tag derived from the file's size and mtime.

    Appended to the media URLs so a replaced file is a NEW url to Cloudflare. Without it
    the 24h Cache-Control means an updated ad is invisible to visitors for a day — which
    is exactly what happened on the first re-render: the origin had the new file and the
    edge kept serving the old one, cf-cache-status HIT. Long caching plus versioned urls
    gets both properties; a short cache would just be slow for everyone forever.

    Computed per render rather than at import, because ops/push-media.sh replaces the file
    WITHOUT restarting the app — a start-up value would be stale the moment it mattered.
    One stat() on a page render is free.
    """
    try:
        st = os.stat(os.path.join(HERE, name))
        return hashlib.sha256(f"{st.st_size}.{int(st.st_mtime)}".encode()).hexdigest()[:10]
    except OSError:
        return "0"


def _send_media(handler, name, ctype):
    """Stream a large static file from DISK with Range support.

    Deliberately NOT _read_static: the icons are a few KB and live in memory happily, but
    the ad is 26 MB and this VM has 1 GB total. Holding it resident would cost a fortieth
    of the machine's memory permanently, to serve a file most visitors never request.

    Range matters as much as size. Without a 206 the browser cannot seek, so dragging the
    scrubber restarts the download from zero — on campus wifi that reads as a broken
    player. Safari will not even begin playback of a long file without it.
    """
    path = os.path.join(HERE, name)
    try:
        total = os.path.getsize(path)
    except OSError:
        return handler._send(page("<p>Not found.</p>"), 404)
    start, end = 0, total - 1
    rng = (handler.headers.get("Range") or "").strip()
    partial = False
    m = re.match(r"bytes=(\d*)-(\d*)$", rng)
    if m:
        a, b = m.group(1), m.group(2)
        if a:
            start = int(a)
            end = min(int(b), total - 1) if b else total - 1
        elif b:                                   # suffix range: last N bytes
            start = max(0, total - int(b))
        # RFC 7233: a range that starts past the end is UNSATISFIABLE and must be 416.
        # Clamping it to the last byte instead looks harmless and is worse — the player
        # receives 206 with content it did not ask for, and a seek past the end silently
        # returns the wrong bytes rather than an error it can handle.
        if start >= total or start > end:
            handler.send_response(416)
            handler.send_header("Content-Range", f"bytes */{total}")
            handler.end_headers()
            return
        partial = True
    length = end - start + 1
    handler.send_response(206 if partial else 200)
    handler.send_header("Content-Type", ctype)
    handler.send_header("Content-Length", str(length))
    handler.send_header("Accept-Ranges", "bytes")
    if partial:
        handler.send_header("Content-Range", f"bytes {start}-{end}/{total}")
    handler.send_header("Cache-Control", "public, max-age=86400")
    handler.end_headers()
    try:
        with open(path, "rb") as f:
            f.seek(start)
            left = length
            while left > 0:
                chunk = f.read(min(262144, left))
                if not chunk:
                    break
                handler.wfile.write(chunk)
                left -= len(chunk)
    except (BrokenPipeError, ConnectionResetError):
        pass          # the visitor closed the tab mid-stream; entirely normal


def _read_static(name):
    try:
        with open(os.path.join(HERE, name), "rb") as f:
            return f.read()
    except Exception:
        return b""


ICON192 = _read_static("icon-192.png")
ICON512 = _read_static("icon-512.png")
OG_IMAGE = _read_static("og-image.png")

ROBOTS = """User-agent: *
Allow: /
Disallow: /auth/
Disallow: /watch
Disallow: /unwatch
Disallow: /push/
Disallow: /dev-login

Sitemap: https://seatwatchapp.com/sitemap.xml
"""

SITEMAP = """<?xml version="1.0" encoding="UTF-8"?>
<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
 <url><loc>https://seatwatchapp.com/</loc><changefreq>daily</changefreq><priority>1.0</priority></url>
 <url><loc>https://seatwatchapp.com/terms</loc><changefreq>monthly</changefreq><priority>0.3</priority></url>
 <url><loc>https://seatwatchapp.com/privacy</loc><changefreq>monthly</changefreq><priority>0.3</priority></url>
</urlset>
"""


DONE = """<div class="hero" style="padding-top:34px;padding-bottom:0"><h1 class="reveal" style="font-size:34px;letter-spacing:-1.4px">You're all set 🎉</h1></div>
<div class="card reveal d2">
<div class="ok"><svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="10"/><path d="m9 12 2 2 4-4"/></svg><span>Now watching <b>__WHAT__</b>.</span></div>
__ALERTINTRO__
__PUSHBLOCK__
<a href="/" style="display:block;text-align:center;margin-top:18px;font-weight:700">← Back to your watches</a>
</div>"""

_PSTYLE = "font-size:14px;line-height:1.65;color:#374151"

TERMS = """<h2 style="font-size:20px;margin:6px 0 2px">Terms of Service</h2>
<p class="sub" style="margin-bottom:14px">Last updated: July 13, 2026</p>
<div style="STYLE">
<p><b>1. Acceptance and eligibility.</b> By using SeatWatch or signing in, you agree to these Terms of Service and our Privacy Policy. If you do not agree, do not use SeatWatch. You must be at least 18 years old, or at least 13 with the permission of a parent or guardian who agrees to these Terms on your behalf. SeatWatch is intended for college students.</p>
<p><b>2. What SeatWatch is.</b> SeatWatch checks publicly-available course-registration pages and notifies you when a seat appears to open in a class you ask us to watch. That is all it does.</p>
<p><b>3. Not affiliated with any school.</b> SeatWatch is an independent tool. We are not affiliated with, endorsed by, or connected to any university, college, or registration system. School and course names are used only to identify what you want to watch.</p>
<p><b>4. You register yourself.</b> SeatWatch only sends alerts. It does not enroll you in anything. Actually registering for a class is your responsibility, and we are not responsible for whether you get a seat, a professor, a time, or a class.</p>
<p><b>5. Your account and acceptable use.</b> Keep your sign-in secure; you are responsible for activity under your account. Use SeatWatch only for your own personal course-watching. Do not abuse, overload, scrape, copy, resell, or attempt to disrupt or reverse-engineer the service; do not create multiple accounts to get around free-plan limits; and do not use SeatWatch for any unlawful purpose. We may remove watches, or suspend or terminate accounts, that do.</p>
<p><b>6. Payments.</b> Your first class is free. Paid plans are one-time payments for a single academic term. They are not subscriptions and do not auto-renew, and are charged at the prices shown when you buy. Payments are processed by our payment provider (Stripe); we never see or store your full card details. Except where the law requires otherwise, all payments are final and non-refundable. You are responsible for any applicable taxes. Prices and plans may change for future terms.</p>
<p><b>7. No guarantee.</b> We try hard, but we cannot promise SeatWatch will catch every opening, alert you in time, or be accurate or error-free. Seat information can be delayed, wrong, or missed; seats fill in seconds; notifications can be delayed or fail; and school websites change without notice. <b>You use SeatWatch entirely at your own risk, and you should always confirm seat availability yourself before relying on it.</b></p>
<p><b>8. Disclaimer of warranties.</b> The service is provided &ldquo;as is&rdquo; and &ldquo;as available,&rdquo; without warranties of any kind, express or implied, including any implied warranties of merchantability, fitness for a particular purpose, accuracy, or non-infringement, and any warranty that the service will be uninterrupted, timely, secure, or error-free.</p>
<p><b>9. Limitation of liability.</b> To the fullest extent permitted by law, SeatWatch LLC and its owners, creators, and operators will not be liable for any indirect, incidental, special, consequential, exemplary, or punitive damages, or for any missed or lost class, lost opportunity, lost data, or other loss, arising from or relating to your use of (or inability to use) the service, even if advised such damages were possible. Our total liability for any claim will not exceed the greater of (a) the amount you paid us in the 12 months before the claim, or (b) US $100.</p>
<p><b>10. Indemnification.</b> You agree to defend, indemnify, and hold harmless SeatWatch LLC and its owners, creators, and operators from any claims, liabilities, damages, losses, and costs (including reasonable attorneys&rsquo; fees) arising from or relating to your use of the service, your violation of these Terms, or your violation of any law or the rights of any third party.</p>
<p><b>11. Suspension and termination.</b> We may suspend or end your access, or discontinue the service, at any time, with or without notice, including for any violation of these Terms or suspected abuse. You may stop using SeatWatch at any time. Provisions that by their nature should survive (including Payments, Disclaimers, Limitation of Liability, Indemnification, and Dispute Resolution) will survive.</p>
<p><b>12. Dispute resolution; binding arbitration; class-action waiver.</b> <i>Please read this carefully. It affects your legal rights.</i> (a) <b>Informal first:</b> if you have a dispute, email support@seatwatchapp.com and we will try to resolve it within 30 days before either of us starts a formal proceeding. (b) <b>Binding arbitration:</b> if we cannot resolve it, you and SeatWatch agree that any dispute arising out of or relating to SeatWatch or these Terms will be resolved by final and binding <i>individual</i> arbitration administered by the American Arbitration Association under its Consumer Arbitration Rules, rather than in court, except that either of us may bring an individual claim in small-claims court. (c) <b>Class-action and jury waiver:</b> you and SeatWatch agree to bring claims only individually, and not as a plaintiff or member of any class, collective, or representative action, and each waives any right to a jury trial. (d) <b>30-day opt-out:</b> you may opt out of this arbitration agreement by emailing support@seatwatchapp.com within 30 days of first accepting these Terms, stating your name and that you opt out of arbitration; if you opt out, the rest of these Terms still apply. (e) If the class-action waiver is found unenforceable, the remainder of this section still applies; if the entire arbitration agreement is found unenforceable, disputes will proceed in the courts named below.</p>
<p><b>13. Changes.</b> We may change, pause, or discontinue the service, or update these Terms, at any time. If we make material changes, we will update the &ldquo;last updated&rdquo; date; continued use means you accept the current Terms.</p>
<p><b>14. Governing law and venue.</b> These Terms are governed by the laws of the State of Maryland, USA, without regard to its conflict-of-laws rules. Subject to the arbitration section above, any dispute that proceeds in court will be brought exclusively in the state or federal courts located in Maryland, and you consent to their jurisdiction.</p>
<p><b>15. General.</b> These Terms, with the Privacy Policy, are the entire agreement between you and SeatWatch about the service and replace any prior understandings. If any part is found unenforceable, the rest stays in effect. Our failure to enforce a provision is not a waiver. You may not assign these Terms; we may assign them to a successor (for example, in a sale of the business). You agree we may give notices and communicate with you electronically. We are not liable for delays or failures caused by events beyond our reasonable control.</p>
<p><b>16. Contact.</b> Questions? Reach the SeatWatch LLC team at <a href="mailto:support@seatwatchapp.com">support@seatwatchapp.com</a>. You can also reach us by mail at SeatWatch LLC, 2219 York Rd, Ste 400 #1032, Timonium, MD 21093, USA.</p>
</div>
<p style="font-size:13px;margin-top:16px"><a href="/">&larr; Back to SeatWatch</a> &nbsp;&middot;&nbsp; <a href="/privacy">Privacy Policy</a></p>""".replace("STYLE", _PSTYLE)

PRIVACY = """<h2 style="font-size:20px;margin:6px 0 2px">Privacy Policy</h2>
<p class="sub" style="margin-bottom:14px">Last updated: July 23, 2026</p>
<div style="STYLE">
<p><b>The short version:</b> we collect the bare minimum needed to run your alerts: your email (from sign-in) and the classes you watch, plus a little more only to stop people from abusing the free plan. We never sell your data or use it for ads.</p>
<p><b>1. What we collect.</b> (a) your email address and account ID, via &ldquo;Sign in with Google&rdquo; or &ldquo;Sign in with Apple&rdquo; (we never see or store your password); (b) the classes and sections you ask us to watch; (c) if you choose to receive text alerts, the mobile number you give us, together with a record of your consent (the wording you agreed to, and the date, time, and IP address it was given); (d) your IP address, used to keep the service secure, including rate-limiting and helping us spot abuse such as one person creating many accounts to get around free-plan limits; (e) a device identifier, a random ID we generate and store in your browser (a cookie and local storage) used <b>solely</b> to detect fraud and free-plan abuse (for example, many accounts from one device). It is not an advertising ID and is never used to track you across other websites.</p>
<p><b>2. Payment information.</b> If you buy a paid plan, our payment provider (Stripe) processes your payment. We never see or store your full card number; we keep only a record of the transaction (such as amount, date, plan, and a payment reference) to run the service, prevent fraud, and meet legal and tax obligations.</p>
<p><b>3. What we do NOT collect.</b> No password (sign-in is handled by Google/Apple) and we never see or store your card details (payment, if any, is handled by Stripe); no location, no browsing history, and no browser &ldquo;fingerprinting&rdquo;. We do run one third-party advertising tag, the Meta Pixel, which is cross-site tracking &mdash; see 7b below for exactly what it sees and how to stop it.</p>
<p><b>4. How alerts are delivered.</b> Alerts are sent by email, and by text message if you have given consent for texts. Email is delivered through our email provider, and texts through our SMS provider (Twilio); each receives only what is needed to deliver your alert. You can change which of these you receive at any time from your account page, and you can stop texts at any time by replying STOP.</p>
<p><b>5. How we use your data.</b> To run the watch-and-alert service, and to keep it secure and fair (see below). Nothing else.</p>
<p><b>6. Preventing abuse of the free plan.</b> So we can keep offering a free plan, we look for signs that one person is using multiple accounts to bypass the free limit, for example accounts that share a device, network/IP address, or email, or that together watch more of a class than one free account is meant to. To do this we use only the data described above (the device identifier, IP address, sign-in email, any mobile number you gave us, and your watch activity), the minimum needed, and no invasive fingerprinting. This protects our legitimate interest in preventing fraud. If we find likely abuse, we may remove the extra watches or accounts, as permitted by our <a href="/terms">Terms of Service</a>. These checks are reviewed by a person before any action. <b>If you believe you were flagged by mistake, email <a href="mailto:support@seatwatchapp.com">support@seatwatchapp.com</a> and a human will help sort it out.</b></p>
<p><b>7. Sharing.</b> We do not sell or rent your data. The one exception is the Meta Pixel described in 7b, which reports page views and first-time signups to Meta so we can measure and target our advertising. We share nothing else for advertising &mdash; not your email address, not your phone number, not the classes you watch.</p>
<p id="adchoices"><b>7b. Advertising &amp; Ad Choices (Meta Pixel).</b> Our pages load the Meta Pixel, code provided by Meta Platforms. <b>Why we use it:</b> to measure whether our advertising works &mdash; it tells Meta that a browser visited SeatWatch and, when someone creates their first class alert, that a signup was completed &mdash; and to let us target and optimise ads on Facebook and Instagram. <b>What Meta receives:</b> your IP address, browser and device information, and the address of the page. Meta may combine this with information it already holds about you. <b>What Meta never receives from us:</b> your name, your email address, your mobile number, your school, or any course, section or professor you watch. We have switched off Meta&rsquo;s automatic matching feature, which would otherwise read those details out of the page. <b>How to opt out.</b> Two controls actually stop this, and both sit with you rather than with us: block the pixel in your browser &mdash; Firefox and Safari do it by default, and any ad blocker or a browser extension will do it in Chrome &mdash; or use the &ldquo;Off-Facebook activity&rdquo; and ad-preference controls in your Meta account to limit what Meta does with what it receives. <b>We cannot switch Meta off for you from our end</b>, so we are not going to promise it: the pixel runs in your browser, not on our server. What we can do, if you email <a href="mailto:support@seatwatchapp.com">support@seatwatchapp.com</a>, is delete your account and everything attached to it. Blocking the pixel never changes your alerts or your plan &mdash; SeatWatch works exactly the same with it blocked.</p>
<p><b>7a. Text-message (SMS) alerts.</b> If you opt in to text alerts, we collect your mobile number and a record of your consent: the exact wording you agreed to, the date and time, and the originating IP address, used <b>solely</b> to send the course seat-availability alerts you requested and to honor your STOP and HELP replies. <b>SeatWatch does not share or sell mobile phone numbers, SMS opt-in, or consent information with third parties or affiliates for marketing or promotional purposes.</b> We disclose your mobile number only to our SMS delivery provider (Twilio), strictly to transmit the alerts you asked for. Message frequency varies based on the courses you monitor; message and data rates may apply. Reply STOP to any alert to unsubscribe, or HELP for help. Opting in is never a condition of purchase. SeatWatch works fully without a phone number on every plan, using web push and email. See our <a href="/sms-terms">SMS Terms &amp; Conditions</a>.</p>
<p><b>California residents.</b> Where these rights apply to you, you may ask what personal information we hold about you and how it is used, and request a copy, a correction, or deletion, without being treated differently for asking. <b>We do not sell your personal information.</b> We do disclose limited identifiers (IP address and browser information) to Meta for advertising measurement, described in 7b, and you can opt out of that at any time by the means listed there or by emailing us. To exercise any right, email <a href="mailto:support@seatwatchapp.com">support@seatwatchapp.com</a>. Nothing here is a statement about which privacy laws apply to SeatWatch; we offer these choices to everyone who asks, whether or not a statute requires it.</p>
<p><b>8. Retention.</b> A watch is kept only while it is active. Stop it (or ask us) and it is removed. Abuse-prevention signals are kept only as long as needed to protect the service.</p>
<p><b>9. Security.</b> We use reasonable safeguards to protect the service, but no system is 100% secure.</p>
<p><b>Data breaches.</b> If a breach affects your personal information, we will notify you and any authorities as required by applicable law.</p>
<p><b>10. Children.</b> SeatWatch is intended for college students and is not directed at children under 13.</p>
<p><b>11. Changes.</b> We may update this policy; the &ldquo;last updated&rdquo; date above will change.</p>
<p><b>12. Contact / data removal.</b> Want your data removed, or have a question? Contact the SeatWatch LLC team at <a href="mailto:support@seatwatchapp.com">support@seatwatchapp.com</a>. You can also reach us by mail at SeatWatch LLC, 2219 York Rd, Ste 400 #1032, Timonium, MD 21093, USA.</p>
</div>
<p style="font-size:13px;margin-top:16px"><a href="/">&larr; Back to SeatWatch</a> &nbsp;&middot;&nbsp; <a href="/terms">Terms of Service</a></p>""".replace("STYLE", _PSTYLE)


SMS_TERMS = """<h2 style="font-size:20px;margin:6px 0 2px">SMS Terms &amp; Conditions</h2>
<p class="sub" style="margin-bottom:14px">Last updated: July 23, 2026</p>
<div style="STYLE">
<p><b>1. Program description.</b> The SeatWatch text-alert program sends automated text messages notifying you when a seat opens in a full college course or section you have chosen to monitor. Text alerts are an optional feature of SeatWatch, available on every plan including the free one.</p>
<p><b>2. How to opt in.</b> Add your U.S. mobile number and check the consent box that reads: &ldquo;<i>I agree to receive automated SeatWatch course seat-availability alerts at the number provided. Message frequency varies based on the courses I monitor. Message and data rates may apply. Reply STOP to opt out or HELP for help. Consent is not a condition of purchase. See our Terms and Privacy Policy.</i>&rdquo; The box is unchecked by default; checking it and submitting is your affirmative opt-in.</p>
<p><b>3. Consent is not a condition of purchase.</b> You are never required to provide a mobile number or agree to texts to buy or use SeatWatch. SeatWatch works fully without text alerts on every plan &mdash; web push and email are always available.</p>
<p><b>4. Message frequency.</b> Message frequency varies based on how many courses and sections you monitor and how often seats open in them. You may receive multiple messages when seats open, or none when they do not.</p>
<p><b>5. Cost.</b> <b>Message and data rates may apply.</b> SeatWatch does not charge for the text messages themselves; your mobile carrier&rsquo;s standard messaging and data rates apply, and you are responsible for them.</p>
<p><b>6. To unsubscribe (STOP).</b> Reply <b>STOP</b> to any SeatWatch text at any time to cancel. After you send STOP, we will stop sending course alerts to that number. You may also receive one final message confirming your opt-out.</p>
<p><b>7. For help (HELP).</b> Reply <b>HELP</b> to any SeatWatch text for help, or email <a href="mailto:support@seatwatchapp.com">support@seatwatchapp.com</a>.</p>
<p><b>8. Supported carriers.</b> Text alerts are available on major U.S. mobile carriers. Carriers are not liable for delayed or undelivered messages.</p>
<p><b>9. No guarantee of delivery.</b> Text messages depend on your carrier and device and may be delayed or fail to arrive for reasons outside our control. SeatWatch also delivers the same alerts by web push and email, and you should not rely on text messages as your only means of notification. Text alerts do not guarantee you a seat, because open seats can fill in seconds.</p>
<p><b>10. Privacy.</b> Your mobile number and consent record are used only to deliver the alerts you requested and are never sold or shared for marketing. See our <a href="/privacy">Privacy Policy</a> for full details.</p>
<p><b>11. Changes.</b> We may update these SMS Terms; the &ldquo;last updated&rdquo; date above will change.</p>
<p><b>12. Contact.</b> SeatWatch LLC, 2219 York Rd, Ste 400 #1032, Timonium, MD 21093, USA &nbsp;&middot;&nbsp; <a href="mailto:support@seatwatchapp.com">support@seatwatchapp.com</a>.</p>
</div>
<p style="font-size:13px;margin-top:16px"><a href="/">&larr; Back to SeatWatch</a> &nbsp;&middot;&nbsp; <a href="/privacy">Privacy Policy</a> &nbsp;&middot;&nbsp; <a href="/terms">Terms of Service</a></p>""".replace("STYLE", _PSTYLE)


LANDING = """<!doctype html><html lang="en"><head><meta charset="utf-8">
__METAPIXEL__
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>SeatWatch: Get into the class you actually need | __COUNT__ universities</title>
<meta name="description" content="SeatWatch alerts you the instant a seat opens in a full college class, across __COUNT__ universities. Watch the exact section you want and get the professor you want. Free to start.">
<link rel="canonical" href="https://seatwatchapp.com/">
<meta name="robots" content="index, follow, max-image-preview:large">
<meta name="keywords" content="seatwatch, seat watch, course seat alert, class seat notification, college registration alert, open seat finder, coursicle alternative">
<meta name="author" content="SeatWatch LLC">
<meta name="application-name" content="SeatWatch">
<meta property="og:type" content="website">
<meta property="og:site_name" content="SeatWatch">
<meta property="og:title" content="SeatWatch: Get into the class you actually need">
<meta property="og:description" content="Get an instant alert the second a seat opens in a full college class, across __COUNT__ universities. Watch the exact section, get the professor you want.">
<meta property="og:url" content="https://seatwatchapp.com/">
<meta property="og:image" content="https://seatwatchapp.com/og-image.png">
<meta property="og:image:width" content="1200"><meta property="og:image:height" content="630">
<meta name="twitter:card" content="summary_large_image">
<meta name="twitter:title" content="SeatWatch: Get into the class you actually need">
<meta name="twitter:description" content="Get an instant alert the second a seat opens in a full college class. __COUNT__ universities. Free to start.">
<meta name="twitter:image" content="https://seatwatchapp.com/og-image.png">
<script type="application/ld+json">{"@context":"https://schema.org","@graph":[{"@type":"Organization","@id":"https://seatwatchapp.com/#org","name":"SeatWatch","legalName":"SeatWatch LLC","url":"https://seatwatchapp.com/","logo":"https://seatwatchapp.com/icon-512.png","email":"support@seatwatchapp.com","address":{"@type":"PostalAddress","streetAddress":"2219 York Rd, Ste 400 #1032","addressLocality":"Timonium","addressRegion":"MD","postalCode":"21093","addressCountry":"US"},"description":"Instant alerts when a seat opens in a full college class, across __COUNT__ universities."},{"@type":"WebSite","@id":"https://seatwatchapp.com/#site","url":"https://seatwatchapp.com/","name":"SeatWatch","publisher":{"@id":"https://seatwatchapp.com/#org"}},{"@type":"WebApplication","name":"SeatWatch","url":"https://seatwatchapp.com/","applicationCategory":"EducationalApplication","operatingSystem":"Web","offers":{"@type":"Offer","price":"0","priceCurrency":"USD","description":"First class free"},"description":"Get an instant phone alert the second a seat opens in a full college class."}]}</script>
<link rel="icon" href="data:image/svg+xml,<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 120 120'><defs><linearGradient id='b' x1='0' y1='0' x2='1' y2='1'><stop offset='0' stop-color='%233b82f6'/><stop offset='1' stop-color='%232563eb'/></linearGradient></defs><path d='M40 14 H80 Q104 14 104 38 V72 Q104 96 80 96 H64 L54 110 L49 96 H36 Q12 96 12 72 V38 Q12 14 36 14 Z' fill='white' stroke='%232563eb' stroke-width='9' stroke-linejoin='round'/><rect x='42' y='32' width='28' height='24' rx='7' fill='url(%23b)'/><rect x='38' y='56' width='40' height='11' rx='5.5' fill='url(%23b)'/><rect x='42' y='67' width='8' height='15' rx='3' fill='url(%23b)'/><rect x='66' y='67' width='8' height='15' rx='3' fill='url(%23b)'/><circle cx='100' cy='20' r='11' fill='%2310b981' stroke='white' stroke-width='5'/></svg>">
<meta name="theme-color" content="#f7f9fc">
<link rel="manifest" href="/manifest.json">
<link rel="apple-touch-icon" href="/icon-192.png">
<link rel="preconnect" href="https://fonts.googleapis.com"><link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Plus+Jakarta+Sans:ital,wght@0,400;0,500;0,600;0,700;0,800;1,400&family=IBM+Plex+Mono:wght@400;500;600&display=swap" rel="stylesheet">
<style>
 *{box-sizing:border-box}
 body{margin:0;background:#f7f9fc;font-family:"Plus Jakarta Sans",system-ui,sans-serif;color:#0b1526}
 a{color:#2563eb;text-decoration:none}
 ::selection{background:rgba(37,99,235,.18)}
 @keyframes swPing{0%{transform:scale(.85);opacity:.8}70%{transform:scale(2.6);opacity:0}100%{opacity:0}}
 @keyframes swSlideIn{0%{opacity:0;transform:translateY(-14px) scale(.97)}100%{opacity:1;transform:translateY(0) scale(1)}}
 @keyframes swFloat{0%,100%{transform:translateY(0)}50%{transform:translateY(-8px)}}
 [data-reveal]{opacity:0;transform:translateY(26px);transition:opacity .7s cubic-bezier(.16,1,.3,1),transform .7s cubic-bezier(.16,1,.3,1)}
 [data-reveal].sw-in{opacity:1;transform:translateY(0)}
 .sw-cta{transition:transform .2s,box-shadow .2s}.sw-cta:hover{transform:translateY(-2px)}
 .sw-dark{transition:background .2s}.sw-dark:hover{background:#1e293b}
 .sw-navlink{transition:color .2s}.sw-navlink:hover{color:#2563eb}
 @media(max-width:900px){
   .sw-hero{grid-template-columns:1fr!important;gap:44px!important;padding:56px 22px 68px!important}
   .sw-h1{font-size:44px!important}
   .sw-grid2{grid-template-columns:1fr!important;gap:40px!important;padding:72px 22px!important}
   .sw-grid3{grid-template-columns:1fr!important}
   .sw-navlinks{display:none!important}
   .sw-connector{display:none!important}
   .sw-h2{font-size:32px!important}
   .sw-price{grid-template-columns:1fr!important}
   .sw-final h2{font-size:34px!important}
 }
</style></head>
<body>

<nav id="sw-nav" style="position:sticky;top:0;z-index:50;background:rgba(247,249,252,.75);backdrop-filter:blur(16px);-webkit-backdrop-filter:blur(16px);border-bottom:1px solid rgba(11,21,38,.06);transition:box-shadow .3s;">
  <div style="max-width:1140px;margin:0 auto;padding:0 28px;height:68px;display:flex;align-items:center;justify-content:space-between;">
    <a href="/" style="display:flex;align-items:center;gap:10px;">
      <div style="position:relative;width:34px;height:34px;border-radius:10px;background:linear-gradient(140deg,#2563eb,#3b82f6);display:flex;align-items:center;justify-content:center;box-shadow:0 4px 12px -2px rgba(37,99,235,.4);">
        <div style="width:12px;height:12px;border-radius:4px;border:2.5px solid #fff;border-bottom-width:5px;"></div>
        <div style="position:absolute;top:-2px;right:-2px;width:9px;height:9px;border-radius:50%;background:#17b26a;border:2px solid #f7f9fc;"></div>
      </div>
      <span style="font-size:20px;font-weight:800;letter-spacing:-.02em;color:#0b1526;"><span style="color:#2563eb;">Seat</span>Watch</span>
    </a>
    <div style="display:flex;align-items:center;gap:30px;">
      <div class="sw-navlinks" style="display:flex;gap:28px;font-size:14.5px;font-weight:600;">
        <a href="#sw-how" class="sw-navlink" style="color:#4b5a72;">How it works</a>
        <a href="#sw-pricing" class="sw-navlink" style="color:#4b5a72;">Pricing</a>
        <a href="#sw-faq" class="sw-navlink" style="color:#4b5a72;">FAQ</a>
      </div>
      <div style="display:flex;align-items:center;gap:12px;">
        <a href="/login" class="sw-navlink" style="font-size:14.5px;font-weight:600;color:#4b5a72;padding:9px 14px;white-space:nowrap;">Sign in</a>
        <a href="/login" class="sw-dark" style="font-size:14.5px;font-weight:700;color:#fff;background:#0b1526;padding:10px 20px;border-radius:100px;white-space:nowrap;">Start free</a>
      </div>
    </div>
  </div>
</nav>

<header style="position:relative;overflow:hidden;">
  <div style="position:absolute;inset:0;background-image:linear-gradient(rgba(11,21,38,.035) 1px,transparent 1px),linear-gradient(90deg,rgba(11,21,38,.035) 1px,transparent 1px);background-size:56px 56px;mask-image:radial-gradient(75% 90% at 50% 0%,#000 30%,transparent 100%);-webkit-mask-image:radial-gradient(75% 90% at 50% 0%,#000 30%,transparent 100%);"></div>
  <div style="position:absolute;top:-220px;right:-140px;width:640px;height:640px;border-radius:50%;background:radial-gradient(circle,rgba(59,130,246,.13),transparent 65%);"></div>
  <div style="position:absolute;bottom:-100px;left:-180px;width:520px;height:520px;border-radius:50%;background:radial-gradient(circle,rgba(23,178,106,.09),transparent 65%);"></div>
  <div class="sw-hero" style="position:relative;max-width:1140px;margin:0 auto;padding:84px 28px 96px;display:grid;grid-template-columns:1.05fr .95fr;gap:64px;align-items:center;">
    <div>
      <div style="display:inline-flex;align-items:center;gap:9px;padding:7px 15px;background:#fff;border:1px solid rgba(11,21,38,.08);border-radius:100px;box-shadow:0 2px 8px rgba(11,21,38,.05);font-family:'IBM Plex Mono',monospace;font-size:12px;font-weight:500;letter-spacing:.09em;color:#3d4c63;">
        <span style="position:relative;display:inline-flex;width:8px;height:8px;">
          <span style="position:absolute;inset:0;border-radius:50%;background:#17b26a;"></span>
          <span style="position:absolute;inset:0;border-radius:50%;background:#17b26a;animation:swPing 2s ease-out infinite;"></span>
        </span>
        LIVE · WATCHING __COUNT__ UNIVERSITIES
      </div>
      <h1 class="sw-h1" style="margin:26px 0 0;font-size:64px;line-height:1.04;font-weight:800;letter-spacing:-.035em;">
        Get into the class you <span style="color:#2563eb;">actually need</span><span style="color:#17b26a;">.</span>
      </h1>
      <p style="margin:22px 0 0;font-size:19px;line-height:1.6;color:#4b5a72;max-width:490px;">
        That full class you're stuck on? We watch it around the clock and buzz your phone the instant a seat opens, and we never show fake openings.
      </p>
      <div style="display:flex;align-items:center;gap:18px;margin-top:36px;flex-wrap:wrap;">
        <a href="/login" class="sw-cta" style="display:inline-flex;align-items:center;gap:10px;padding:17px 30px;background:linear-gradient(140deg,#2563eb,#3b82f6);color:#fff;border-radius:100px;font-size:16.5px;font-weight:700;box-shadow:0 14px 30px -8px rgba(37,99,235,.5),inset 0 1px 0 rgba(255,255,255,.25);">
          Start watching free <span style="font-size:18px;">→</span>
        </a>
        <div style="display:flex;flex-direction:column;gap:2px;">
          <span style="font-size:14px;font-weight:700;color:#0b1526;">Free for your first class</span>
          <span style="font-size:13px;color:#6b7a92;">No card · no spam · 1-click sign in</span>
          <span style="font-size:12px;color:#8b98ac;">By continuing, you agree to our <a href="/terms" style="color:#6b7a92;text-decoration:underline;">Terms</a> and <a href="/privacy" style="color:#6b7a92;text-decoration:underline;">Privacy Policy</a>.</span>
        </div>
      </div>
      <div style="display:flex;gap:0;margin-top:48px;border-top:1px solid rgba(11,21,38,.08);padding-top:24px;max-width:470px;">
        <div style="flex:1;"><div style="font-size:26px;font-weight:800;letter-spacing:-.02em;">__COUNT__</div><div style="font-family:'IBM Plex Mono',monospace;font-size:11px;letter-spacing:.1em;color:#6b7a92;margin-top:3px;">UNIVERSITIES</div></div>
        <div style="width:1px;background:rgba(11,21,38,.08);margin:0 26px;"></div>
        <div style="flex:1;"><div style="font-size:26px;font-weight:800;letter-spacing:-.02em;">20s</div><div style="font-family:'IBM Plex Mono',monospace;font-size:11px;letter-spacing:.1em;color:#6b7a92;margin-top:3px;">CHECK INTERVAL</div></div>
        <div style="width:1px;background:rgba(11,21,38,.08);margin:0 26px;"></div>
        <div style="flex:1;"><div style="font-size:26px;font-weight:800;letter-spacing:-.02em;">24/7</div><div style="font-family:'IBM Plex Mono',monospace;font-size:11px;letter-spacing:.1em;color:#6b7a92;margin-top:3px;">MONITORING</div></div>
      </div>
    </div>
    <div style="position:relative;">
      <div style="position:absolute;inset:-40px -30px;background:radial-gradient(60% 60% at 50% 40%,rgba(37,99,235,.08),transparent 70%);"></div>
      <div style="position:relative;background:rgba(255,255,255,.72);backdrop-filter:blur(20px);-webkit-backdrop-filter:blur(20px);border:1px solid rgba(11,21,38,.07);border-radius:24px;box-shadow:0 30px 70px -24px rgba(11,21,38,.22),0 2px 10px rgba(11,21,38,.04);padding:22px;">
        <div style="display:flex;align-items:center;justify-content:space-between;padding:0 4px 16px;border-bottom:1px solid rgba(11,21,38,.06);">
          <span style="font-family:'IBM Plex Mono',monospace;font-size:11.5px;font-weight:600;letter-spacing:.1em;color:#3d4c63;">SAMPLE ACTIVITY</span>
          
        </div>
        <div id="sw-feed" style="display:flex;flex-direction:column;gap:12px;padding-top:16px;min-height:328px;">
          <div style="display:flex;gap:13px;padding:15px;background:#fff;border:1px solid rgba(23,178,106,.25);border-radius:16px;box-shadow:0 6px 18px -6px rgba(11,21,38,.1);"><div style="flex:none;width:40px;height:40px;border-radius:12px;background:rgba(23,178,106,.12);display:flex;align-items:center;justify-content:center;font-size:17px;">🔔</div><div style="min-width:0;"><div style="font-size:14.5px;font-weight:700;">Seat open: ENG101-0101</div><div style="font-size:13px;color:#6b7a92;margin-top:2px;">2 seats open</div></div></div>
          <div style="display:flex;gap:13px;padding:15px;background:#fff;border:1px solid rgba(11,21,38,.07);border-radius:16px;"><div style="flex:none;width:40px;height:40px;border-radius:12px;background:rgba(37,99,235,.1);display:flex;align-items:center;justify-content:center;font-size:17px;">👀</div><div style="min-width:0;"><div style="font-size:14.5px;font-weight:700;">Watching CHEM 231 · Sec 03</div><div style="font-size:13px;color:#6b7a92;margin-top:2px;">Currently full</div></div></div>
          <div style="display:flex;gap:13px;padding:15px;background:#fff;border:1px solid rgba(11,21,38,.07);border-radius:16px;"><div style="flex:none;width:40px;height:40px;border-radius:12px;background:rgba(37,99,235,.1);display:flex;align-items:center;justify-content:center;font-size:17px;">👀</div><div style="min-width:0;"><div style="font-size:14.5px;font-weight:700;">Watching MATH 140 · Sec 01</div><div style="font-size:13px;color:#6b7a92;margin-top:2px;">Currently full</div></div></div>
          <div style="display:flex;gap:13px;padding:15px;background:#fff;border:1px solid rgba(11,21,38,.07);border-radius:16px;"><div style="flex:none;width:40px;height:40px;border-radius:12px;background:rgba(23,178,106,.12);display:flex;align-items:center;justify-content:center;font-size:17px;">👀</div><div style="min-width:0;"><div style="font-size:14.5px;font-weight:700;">Watching BIO 1A · Sec 02</div><div style="font-size:13px;color:#6b7a92;margin-top:2px;">Currently full</div></div></div>
        </div>
      </div>
      <div style="text-align:center;margin-top:12px;font-family:'IBM Plex Mono',monospace;font-size:10.5px;letter-spacing:.06em;color:#8b98ac;">Illustration: sample activity, not live data.</div>
      <div style="position:absolute;right:-14px;bottom:-18px;animation:swFloat 5s ease-in-out infinite;background:#0b1526;color:#fff;border-radius:14px;padding:12px 18px;box-shadow:0 18px 40px -12px rgba(11,21,38,.5);display:flex;align-items:center;gap:9px;"><span style="font-size:15px;">⚡</span><span style="font-size:13.5px;font-weight:600;">Alerts in <span style="color:#7db8ff;">seconds</span></span></div>
    </div>
  </div>
</header>

<!-- The 36-second tour. Directly after the hero: first thing below the fold on desktop,
     right under the call to action on mobile.

     A PLAIN LINK, and deliberately so. Every richer version of this failed in a way that
     was invisible to the visitor: an embedded player that an extension replaced with a
     silent grey box, a video element that reported no error while never requesting the
     file. A link cannot do that. There is no JavaScript here at all, nothing to block,
     and nothing that can half-work.

     The poster carries the whole pitch at 81 KB — FULL, 120/120 seats taken, and it's the
     class you need to graduate — so a visitor who never clicks still gets the message.
     New tab, so nobody loses the page they were about to sign up on. -->
<section id="sw-tour" style="background:linear-gradient(180deg,#fff 0%,#F7F9FC 100%);border-top:1px solid rgba(11,21,38,.06);">
  <div style="max-width:1000px;margin:0 auto;padding:78px 28px 84px;text-align:center;">
    <div style="display:inline-flex;align-items:center;gap:8px;padding:6px 14px;background:#fff;border:1px solid rgba(11,21,38,.08);border-radius:100px;font-family:'IBM Plex Mono',monospace;font-size:11.5px;font-weight:500;letter-spacing:.09em;color:#3d4c63;">36 SECONDS</div>
    <h2 style="margin:20px 0 10px;font-size:40px;line-height:1.1;font-weight:800;letter-spacing:-.03em;">See it happen.</h2>
    <p style="margin:0 auto 34px;max-width:520px;font-size:17px;line-height:1.6;color:#4b5a72;">A full class, a seat opening at 2am, and the text that gets you in.</p>
    <a href="https://www.youtube.com/shorts/Orpi5y0Us8U" target="_blank" rel="noopener"
       aria-label="Watch the 36-second SeatWatch tour"
       style="position:relative;display:block;width:100%;max-width:380px;margin:0 auto;aspect-ratio:9/16;border-radius:22px;overflow:hidden;background:#0b1526;box-shadow:0 34px 80px -28px rgba(11,21,38,.4);border:1px solid rgba(11,21,38,.08);">
      <img src="/tour-poster.jpg?v=__ADPOSTERV__" alt="A full class, a seat opening, and the text that gets you in" style="display:block;width:100%;height:100%;object-fit:cover;">
      <span style="position:absolute;inset:0;display:flex;align-items:center;justify-content:center;background:rgba(11,21,38,.2);">
        <span style="display:flex;align-items:center;justify-content:center;width:78px;height:78px;border-radius:50%;background:rgba(255,255,255,.96);box-shadow:0 12px 34px -8px rgba(11,21,38,.55);">
          <svg width="29" height="29" viewBox="0 0 24 24" fill="#2563eb" style="margin-left:5px;"><path d="M8 5v14l11-7z"/></svg>
        </span>
      </span>
    </a>
    <p style="margin:22px 0 0;font-size:14px;color:#6b7a92;">Sound on. It is 36 seconds.</p>
  </div>
</section>

<div data-reveal style="border-top:1px solid rgba(11,21,38,.06);border-bottom:1px solid rgba(11,21,38,.06);background:#fff;">
  <div style="max-width:1140px;margin:0 auto;padding:18px 28px;display:flex;align-items:center;justify-content:center;gap:34px;flex-wrap:wrap;font-size:13.5px;font-weight:600;color:#4b5a72;">
    <span style="display:flex;align-items:center;gap:8px;"><span style="color:#17b26a;">✓</span>Never fake: real seats only</span>
    <span style="width:4px;height:4px;border-radius:50%;background:rgba(11,21,38,.15);"></span>
    <span style="display:flex;align-items:center;gap:8px;"><span style="color:#17b26a;">✓</span>Reads live registration data</span>
    <span style="width:4px;height:4px;border-radius:50%;background:rgba(11,21,38,.15);"></span>
    <span style="display:flex;align-items:center;gap:8px;"><span style="color:#17b26a;">✓</span>Never logs into your account</span>
    <span style="width:4px;height:4px;border-radius:50%;background:rgba(11,21,38,.15);"></span>
    <span style="display:flex;align-items:center;gap:8px;"><span style="color:#17b26a;">✓</span>Watch the exact section you want</span>
  </div>
</div>

<section class="sw-grid2" style="max-width:1140px;margin:0 auto;padding:110px 28px;display:grid;grid-template-columns:1fr 1fr;gap:70px;align-items:center;">
  <div data-reveal>
    <div style="font-family:'IBM Plex Mono',monospace;font-size:12px;font-weight:600;letter-spacing:.12em;color:#2563eb;">SECTION-LEVEL PRECISION</div>
    <h2 class="sw-h2" style="margin:16px 0 0;font-size:42px;font-weight:800;letter-spacing:-.03em;line-height:1.1;">Get the professor you want.</h2>
    <p style="margin:20px 0 0;font-size:17px;line-height:1.65;color:#4b5a72;">Stuck out of the class, or the exact section, you were hoping for? SeatWatch watches the <strong style="color:#0b1526;">specific section you pick</strong>, so you land the professor, time, and class you actually want the moment a seat opens up.</p>
    <p style="margin:14px 0 0;font-size:17px;line-height:1.65;color:#4b5a72;">Not just any seat. <em style="color:#2563eb;font-weight:600;">Your</em> seat.</p>
  </div>
  <div data-reveal style="background:#fff;border:1px solid rgba(11,21,38,.07);border-radius:22px;box-shadow:0 24px 60px -24px rgba(11,21,38,.16);padding:24px;">
    <div style="display:flex;align-items:center;justify-content:space-between;padding-bottom:16px;border-bottom:1px solid rgba(11,21,38,.06);">
      <div><div style="font-size:16px;font-weight:800;">CHEM 231: Organic Chemistry</div><div style="font-size:13px;color:#6b7a92;margin-top:2px;">Fall 2026 · pick your sections</div></div>
      <span style="font-family:'IBM Plex Mono',monospace;font-size:11px;color:#6b7a92;">4 SECTIONS</span>
    </div>
    <div style="display:flex;flex-direction:column;gap:10px;padding-top:16px;">
      <div style="display:flex;align-items:center;gap:14px;padding:14px 16px;border:1.5px solid #2563eb;background:rgba(37,99,235,.04);border-radius:14px;"><div style="flex:1;"><div style="font-size:14.5px;font-weight:700;">Sec 01 · Dr. Alvarez</div><div style="font-size:12.5px;color:#6b7a92;margin-top:1px;">MWF 10:00 – 10:50 · <span style="color:#e11d48;font-weight:600;">Full 120/120</span></div></div><span style="padding:7px 14px;background:#2563eb;color:#fff;border-radius:100px;font-size:12.5px;font-weight:700;">Watching ✓</span></div>
      <div style="display:flex;align-items:center;gap:14px;padding:14px 16px;border:1.5px solid #2563eb;background:rgba(37,99,235,.04);border-radius:14px;"><div style="flex:1;"><div style="font-size:14.5px;font-weight:700;">Sec 03 · Dr. Alvarez</div><div style="font-size:12.5px;color:#6b7a92;margin-top:1px;">TuTh 2:00 – 3:15 · <span style="color:#e11d48;font-weight:600;">Full 120/120</span></div></div><span style="padding:7px 14px;background:#2563eb;color:#fff;border-radius:100px;font-size:12.5px;font-weight:700;">Watching ✓</span></div>
      <div style="display:flex;align-items:center;gap:14px;padding:14px 16px;border:1px solid rgba(11,21,38,.08);border-radius:14px;opacity:.65;"><div style="flex:1;"><div style="font-size:14.5px;font-weight:700;">Sec 02 · Staff</div><div style="font-size:12.5px;color:#6b7a92;margin-top:1px;">MWF 8:00 – 8:50 · Full 120/120</div></div><span style="padding:7px 14px;border:1px solid rgba(11,21,38,.12);color:#4b5a72;border-radius:100px;font-size:12.5px;font-weight:700;">Watch</span></div>
      <div style="display:flex;align-items:center;gap:14px;padding:14px 16px;border:1px solid rgba(11,21,38,.08);border-radius:14px;opacity:.65;"><div style="flex:1;"><div style="font-size:14.5px;font-weight:700;">Sec 04 · Dr. Okafor</div><div style="font-size:12.5px;color:#6b7a92;margin-top:1px;">TuTh 9:30 – 10:45 · Full 120/120</div></div><span style="padding:7px 14px;border:1px solid rgba(11,21,38,.12);color:#4b5a72;border-radius:100px;font-size:12.5px;font-weight:700;">Watch</span></div>
    </div>
  </div>
</section>

<section id="sw-how" style="background:#fff;border-top:1px solid rgba(11,21,38,.06);border-bottom:1px solid rgba(11,21,38,.06);">
  <div style="max-width:1140px;margin:0 auto;padding:110px 28px;">
    <div data-reveal style="text-align:center;max-width:560px;margin:0 auto;">
      <div style="font-family:'IBM Plex Mono',monospace;font-size:12px;font-weight:600;letter-spacing:.12em;color:#2563eb;">HOW IT WORKS</div>
      <h2 class="sw-h2" style="margin:16px 0 0;font-size:42px;font-weight:800;letter-spacing:-.03em;line-height:1.1;">Three steps between you and the class you need.</h2>
    </div>
    <div class="sw-grid3" style="display:grid;grid-template-columns:repeat(3,1fr);gap:26px;margin-top:64px;position:relative;">
      <div class="sw-connector" style="position:absolute;top:31px;left:16%;right:16%;height:2px;background:repeating-linear-gradient(90deg,rgba(37,99,235,.3) 0 8px,transparent 8px 16px);"></div>
      <div data-reveal style="position:relative;text-align:center;padding:0 18px;"><div style="width:62px;height:62px;margin:0 auto;border-radius:18px;background:#f7f9fc;border:1px solid rgba(11,21,38,.08);display:flex;align-items:center;justify-content:center;font-size:24px;box-shadow:0 4px 14px rgba(11,21,38,.06);position:relative;z-index:1;">🔍</div><div style="font-family:'IBM Plex Mono',monospace;font-size:11px;letter-spacing:.12em;color:#2563eb;margin-top:22px;">STEP 01</div><h3 style="margin:8px 0 0;font-size:19px;font-weight:800;letter-spacing:-.01em;">Tell us your class</h3><p style="margin:10px 0 0;font-size:15px;line-height:1.6;color:#4b5a72;">Pick your school, the course, and the section(s) you want to watch.</p></div>
      <div data-reveal style="position:relative;text-align:center;padding:0 18px;transition-delay:.1s;"><div style="width:62px;height:62px;margin:0 auto;border-radius:18px;background:#f7f9fc;border:1px solid rgba(11,21,38,.08);display:flex;align-items:center;justify-content:center;font-size:24px;box-shadow:0 4px 14px rgba(11,21,38,.06);position:relative;z-index:1;">📡</div><div style="font-family:'IBM Plex Mono',monospace;font-size:11px;letter-spacing:.12em;color:#2563eb;margin-top:22px;">STEP 02</div><h3 style="margin:8px 0 0;font-size:19px;font-weight:800;letter-spacing:-.01em;">We watch it around the clock</h3><p style="margin:10px 0 0;font-size:15px;line-height:1.6;color:#4b5a72;">Our engine checks the live registration site every 20 seconds. Fast and accurate.</p></div>
      <div data-reveal style="position:relative;text-align:center;padding:0 18px;transition-delay:.2s;"><div style="width:62px;height:62px;margin:0 auto;border-radius:18px;background:#f7f9fc;border:1px solid rgba(11,21,38,.08);display:flex;align-items:center;justify-content:center;font-size:24px;box-shadow:0 4px 14px rgba(11,21,38,.06);position:relative;z-index:1;">📱</div><div style="font-family:'IBM Plex Mono',monospace;font-size:11px;letter-spacing:.12em;color:#2563eb;margin-top:22px;">STEP 03</div><h3 style="margin:8px 0 0;font-size:19px;font-weight:800;letter-spacing:-.01em;">Your phone buzzes instantly</h3><p style="margin:10px 0 0;font-size:15px;line-height:1.6;color:#4b5a72;">The second a real seat opens, you get a push alert. Tap it and go register.</p></div>
    </div>
  </div>
</section>

<section style="max-width:1140px;margin:0 auto;padding:110px 28px;">
  <div data-reveal style="text-align:center;max-width:560px;margin:0 auto;">
    <div style="font-family:'IBM Plex Mono',monospace;font-size:12px;font-weight:600;letter-spacing:.12em;color:#2563eb;">STUDENTS GET THEIR CLASS BACK</div>
    <h2 class="sw-h2" style="margin:16px 0 0;font-size:42px;font-weight:800;letter-spacing:-.03em;line-height:1.1;">The seat you need can open at 2am.</h2>
    <p style="margin:16px 0 0;font-size:17px;color:#4b5a72;">We're the ones watching so you don't have to.</p>
  </div>
  <div class="sw-grid3" style="display:grid;grid-template-columns:repeat(3,1fr);gap:24px;margin-top:56px;">
    <div data-reveal style="background:#fff;border:1px solid rgba(11,21,38,.07);border-radius:20px;padding:28px;box-shadow:0 10px 30px -14px rgba(11,21,38,.1);display:flex;flex-direction:column;gap:12px;"><div style="font-size:26px;">🎯</div><div style="font-size:16px;font-weight:800;color:#0b1526;">Never a fake alert</div><p style="margin:0;font-size:14.5px;line-height:1.6;color:#4b5a72;">We notify you only when a seat is genuinely open. Real registration data, checked live, every time.</p></div>
    <div data-reveal style="background:#fff;border:1px solid rgba(11,21,38,.07);border-radius:20px;padding:28px;box-shadow:0 10px 30px -14px rgba(11,21,38,.1);display:flex;flex-direction:column;gap:12px;transition-delay:.08s;"><div style="font-size:26px;">⏱️</div><div style="font-size:16px;font-weight:800;color:#0b1526;">Always watching</div><p style="margin:0;font-size:14.5px;line-height:1.6;color:#4b5a72;">We check around the clock, roughly every 20 seconds, so you never have to refresh a registration page again.</p></div>
    <div data-reveal style="background:#fff;border:1px solid rgba(11,21,38,.07);border-radius:20px;padding:28px;box-shadow:0 10px 30px -14px rgba(11,21,38,.1);display:flex;flex-direction:column;gap:12px;transition-delay:.16s;"><div style="font-size:26px;">🎓</div><div style="font-size:16px;font-weight:800;color:#0b1526;">The exact section you want</div><p style="margin:0;font-size:14.5px;line-height:1.6;color:#4b5a72;">Watch a specific section to land the professor, time, or campus that actually fits your schedule.</p></div>
  </div>
  </div>
</section>

__PRICING__

<section id="sw-faq" style="max-width:760px;margin:0 auto;padding:110px 28px;">
  <div data-reveal style="text-align:center;">
    <div style="font-family:'IBM Plex Mono',monospace;font-size:12px;font-weight:600;letter-spacing:.12em;color:#2563eb;">FAQ</div>
    <h2 class="sw-h2" style="margin:16px 0 0;font-size:42px;font-weight:800;letter-spacing:-.03em;">Questions, answered.</h2>
    <p style="margin:16px 0 0;font-size:17px;color:#4b5a72;">The stuff students actually ask us.</p>
  </div>
  <div data-reveal style="display:flex;flex-direction:column;gap:12px;margin-top:48px;">
    <div data-faq style="background:#fff;border:1px solid rgba(11,21,38,.07);border-radius:16px;overflow:hidden;cursor:pointer;transition:border-color .25s;"><div style="display:flex;align-items:center;justify-content:space-between;padding:20px 24px;gap:16px;"><span style="font-size:16.5px;font-weight:700;">Is it really free?</span><span data-faq-icon style="flex:none;width:28px;height:28px;border-radius:50%;background:rgba(37,99,235,.08);color:#2563eb;display:flex;align-items:center;justify-content:center;font-size:16px;font-weight:600;transition:transform .3s;">+</span></div><div data-faq-body style="max-height:0;overflow:hidden;transition:max-height .35s cubic-bezier(.16,1,.3,1);"><p style="margin:0;padding:0 24px 22px;font-size:15px;line-height:1.65;color:#4b5a72;">Yes. Your first class, up to two sections, is completely free. No credit card, no trial clock. We only ask you to sign in so your watch stays tied to you.</p></div></div>
    <div data-faq style="background:#fff;border:1px solid rgba(11,21,38,.07);border-radius:16px;overflow:hidden;cursor:pointer;transition:border-color .25s;"><div style="display:flex;align-items:center;justify-content:space-between;padding:20px 24px;gap:16px;"><span style="font-size:16.5px;font-weight:700;">How fast will I hear about an open seat?</span><span data-faq-icon style="flex:none;width:28px;height:28px;border-radius:50%;background:rgba(37,99,235,.08);color:#2563eb;display:flex;align-items:center;justify-content:center;font-size:16px;font-weight:600;transition:transform .3s;">+</span></div><div data-faq-body style="max-height:0;overflow:hidden;transition:max-height .35s cubic-bezier(.16,1,.3,1);"><p style="margin:0;padding:0 24px 22px;font-size:15px;line-height:1.65;color:#4b5a72;">We check your class's live registration system every 20 seconds, around the clock. The instant a real seat appears, your phone gets a push alert, usually within seconds of it opening.</p></div></div>
    <div data-faq style="background:#fff;border:1px solid rgba(11,21,38,.07);border-radius:16px;overflow:hidden;cursor:pointer;transition:border-color .25s;"><div style="display:flex;align-items:center;justify-content:space-between;padding:20px 24px;gap:16px;"><span style="font-size:16.5px;font-weight:700;">Will you ever send a fake alert?</span><span data-faq-icon style="flex:none;width:28px;height:28px;border-radius:50%;background:rgba(37,99,235,.08);color:#2563eb;display:flex;align-items:center;justify-content:center;font-size:16px;font-weight:600;transition:transform .3s;">+</span></div><div data-faq-body style="max-height:0;overflow:hidden;transition:max-height .35s cubic-bezier(.16,1,.3,1);"><p style="margin:0;padding:0 24px 22px;font-size:15px;line-height:1.65;color:#4b5a72;">Never. We read the true seat count straight from your school's registration system and only alert on a genuinely open seat. If our engine can't confirm a seat is really open, it stays silent. No false alarms.</p></div></div>
    <div data-faq style="background:#fff;border:1px solid rgba(11,21,38,.07);border-radius:16px;overflow:hidden;cursor:pointer;transition:border-color .25s;"><div style="display:flex;align-items:center;justify-content:space-between;padding:20px 24px;gap:16px;"><span style="font-size:16.5px;font-weight:700;">Can I watch a specific section or professor?</span><span data-faq-icon style="flex:none;width:28px;height:28px;border-radius:50%;background:rgba(37,99,235,.08);color:#2563eb;display:flex;align-items:center;justify-content:center;font-size:16px;font-weight:600;transition:transform .3s;">+</span></div><div data-faq-body style="max-height:0;overflow:hidden;transition:max-height .35s cubic-bezier(.16,1,.3,1);"><p style="margin:0;padding:0 24px 22px;font-size:15px;line-height:1.65;color:#4b5a72;">That's the whole point. You pick the exact section(s) you want, so you land the professor, time, and class you're actually after, not just any open seat.</p></div></div>
    <div data-faq style="background:#fff;border:1px solid rgba(11,21,38,.07);border-radius:16px;overflow:hidden;cursor:pointer;transition:border-color .25s;"><div style="display:flex;align-items:center;justify-content:space-between;padding:20px 24px;gap:16px;"><span style="font-size:16.5px;font-weight:700;">Is my school supported?</span><span data-faq-icon style="flex:none;width:28px;height:28px;border-radius:50%;background:rgba(37,99,235,.08);color:#2563eb;display:flex;align-items:center;justify-content:center;font-size:16px;font-weight:600;transition:transform .3s;">+</span></div><div data-faq-body style="max-height:0;overflow:hidden;transition:max-height .35s cubic-bezier(.16,1,.3,1);"><p style="margin:0;padding:0 24px 22px;font-size:15px;line-height:1.65;color:#4b5a72;">We watch classes at __COUNT__ universities and colleges, and we're adding more every week. Sign in and start typing your school. If it's there, you're good to go.</p></div></div>
    <div data-faq style="background:#fff;border:1px solid rgba(11,21,38,.07);border-radius:16px;overflow:hidden;cursor:pointer;transition:border-color .25s;"><div style="display:flex;align-items:center;justify-content:space-between;padding:20px 24px;gap:16px;"><span style="font-size:16.5px;font-weight:700;">Is this against my school's rules?</span><span data-faq-icon style="flex:none;width:28px;height:28px;border-radius:50%;background:rgba(37,99,235,.08);color:#2563eb;display:flex;align-items:center;justify-content:center;font-size:16px;font-weight:600;transition:transform .3s;">+</span></div><div data-faq-body style="max-height:0;overflow:hidden;transition:max-height .35s cubic-bezier(.16,1,.3,1);"><p style="margin:0;padding:0 24px 22px;font-size:15px;line-height:1.65;color:#4b5a72;">No. SeatWatch only reads the same public class-availability info you'd see yourself. It never logs into your account or registers for you. When a seat opens, you tap the alert and register, just like normal.</p></div></div>
  </div>
</section>

<section style="max-width:1140px;margin:0 auto;padding:0 28px 110px;">
  <div class="sw-final" data-reveal style="position:relative;overflow:hidden;background:linear-gradient(140deg,#1d4ed8 0%,#2563eb 55%,#3b82f6 100%);border-radius:28px;padding:88px 40px;text-align:center;box-shadow:0 40px 90px -30px rgba(37,99,235,.55);">
    <div style="position:absolute;inset:0;background-image:linear-gradient(rgba(255,255,255,.06) 1px,transparent 1px),linear-gradient(90deg,rgba(255,255,255,.06) 1px,transparent 1px);background-size:48px 48px;mask-image:radial-gradient(70% 100% at 50% 0%,#000,transparent);-webkit-mask-image:radial-gradient(70% 100% at 50% 0%,#000,transparent);"></div>
    <div style="position:relative;">
      <h2 style="margin:0;font-size:48px;font-weight:800;letter-spacing:-.03em;color:#fff;">Your seat is out there.</h2>
      <p style="margin:18px auto 0;font-size:18px;line-height:1.6;color:rgba(255,255,255,.85);max-width:480px;">Let us watch for it. Set up your first class free in under a minute, and get on with your day.</p>
      <a href="/login" class="sw-cta" style="display:inline-flex;align-items:center;gap:10px;margin-top:36px;padding:17px 32px;background:#fff;color:#1d4ed8;border-radius:100px;font-size:16.5px;font-weight:800;box-shadow:0 16px 40px -10px rgba(11,21,38,.4);">Start watching free <span style="font-size:18px;">→</span></a>
      <div style="margin-top:18px;font-size:13.5px;color:rgba(255,255,255,.7);">Free first class · No card required · Alerts in seconds</div>
      <div style="margin-top:10px;font-size:12px;color:rgba(255,255,255,.55);">By continuing, you agree to our <a href="/terms" style="color:rgba(255,255,255,.75);text-decoration:underline;">Terms</a> and <a href="/privacy" style="color:rgba(255,255,255,.75);text-decoration:underline;">Privacy Policy</a>.</div>
    </div>
  </div>
</section>

<footer style="border-top:1px solid rgba(11,21,38,.06);background:#fff;">
  <div style="max-width:1140px;margin:0 auto;padding:34px 28px;display:flex;align-items:center;justify-content:space-between;flex-wrap:wrap;gap:16px;">
    <div style="display:flex;align-items:center;gap:10px;">
      <div style="width:26px;height:26px;border-radius:8px;background:linear-gradient(140deg,#2563eb,#3b82f6);display:flex;align-items:center;justify-content:center;"><div style="width:9px;height:9px;border-radius:3px;border:2px solid #fff;border-bottom-width:4px;"></div></div>
      <span style="font-size:14px;color:#4b5a72;">We watch seats. <em style="color:#0b1526;font-weight:600;">You get the class.</em></span>
    </div>
    <div style="display:flex;gap:22px;font-size:13.5px;color:#6b7a92;align-items:center;flex-wrap:wrap;">
      <span>© 2026 SeatWatch LLC</span>
      <a href="/terms" style="color:#6b7a92;">Terms</a>
      <a href="/privacy" style="color:#6b7a92;">Privacy</a> &nbsp;·&nbsp; <a href="/privacy#adchoices" style="color:#6b7a92;">Privacy &amp; Ad Choices</a>
      <span style="color:#9aa7ba;">Not affiliated with any university.</span>
    </div>
  </div>
</footer>

<script>
(function(){
 // The custom play overlay makes the poster read as a video rather than a picture.
 // Native controls stay ON underneath for keyboard access and scrubbing; the overlay
 // hides itself the moment playback begins and returns when the ad ends.
})();
(function(){
 var io=new IntersectionObserver(function(es){es.forEach(function(e){if(e.isIntersecting){e.target.classList.add('sw-in');io.unobserve(e.target);}});},{threshold:.12});
 document.querySelectorAll('[data-reveal]').forEach(function(el){io.observe(el);});
 document.querySelectorAll('[data-faq]').forEach(function(item){
   var body=item.querySelector('[data-faq-body]'),icon=item.querySelector('[data-faq-icon]');
   item.addEventListener('click',function(){
     var open=body.style.maxHeight&&body.style.maxHeight!=='0px';
     document.querySelectorAll('[data-faq]').forEach(function(o){
       o.querySelector('[data-faq-body]').style.maxHeight='0px';
       o.querySelector('[data-faq-icon]').style.transform='rotate(0deg)';
       o.style.borderColor='rgba(11,21,38,.07)';
     });
     if(!open){body.style.maxHeight=body.scrollHeight+'px';icon.style.transform='rotate(45deg)';item.style.borderColor='rgba(37,99,235,.4)';}
   });
 });
 var nav=document.getElementById('sw-nav');
 if(nav)window.addEventListener('scroll',function(){nav.style.boxShadow=window.scrollY>8?'0 8px 24px -12px rgba(11,21,38,.12)':'none';},{passive:true});
})();
</script>
</body></html>
"""


def pricing_section():
    """ONE conversion pricing block, injected into BOTH the logged-out landing and the
    logged-in form page so the two surfaces are byte-identical. Self-contained scoped
    (.pw-*) CSS incl. responsive (4-across / 2x2 / 1-col) so it renders the same in either
    template. Whole-semester tier is the hero on every breakpoint. While paid is dormant
    (PAID_LIVE off) the paid CTAs are 'Notify me' (a warm early-access list + intent
    signal) with a 'Coming soon' tag; when PAID_ENABLED flips on they become buy actions
    to /checkout. Badge is 'Best value' (factually the best per-class price) — never
    fabricated popularity, per the never-fake brand."""
    soon = not PAID_LIVE
    def cta(tier, label, solid):
        href = "/login" if soon else f"/checkout?tier={tier}"
        text = "Notify me" if soon else label
        if solid:
            style = "background:#2563eb;color:#fff;border:1px solid #2563eb"
        else:
            style = "background:#fff;color:#4b5a72;border:1px solid rgba(11,21,38,.14)"
        return (f'<a href="{href}" class="pw-cta" style="{style}">{text}</a>')
    tag_soon = ('<span class="pw-tag pw-soon">Coming soon</span>' if soon else "")
    ck = ('<span class="pw-ck">'
          '<svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" '
          'stroke-width="2.6" stroke-linecap="round" stroke-linejoin="round">'
          '<path d="M20 6 9 17l-5-5"/></svg></span>')
    def feat(t):
        return f'<div class="pw-feat">{ck}<span>{t}</span></div>'
    return f"""<section id="sw-pricing" class="pw-wrap">
<style>
.pw-wrap{{background:#fff;border-top:1px solid rgba(11,21,38,.06);border-bottom:1px solid rgba(11,21,38,.06)}}
.pw-inner{{max-width:1140px;margin:0 auto;padding:96px 24px}}
.pw-head{{text-align:center;max-width:620px;margin:0 auto}}
.pw-eyebrow{{font-family:'IBM Plex Mono',monospace;font-size:12px;font-weight:600;letter-spacing:.12em;color:#2563eb}}
.pw-h2{{margin:15px 0 0;font-size:40px;font-weight:800;letter-spacing:-.03em;line-height:1.12;color:#0b1526}}
.pw-sub{{margin:15px auto 0;font-size:16.5px;line-height:1.6;color:#4b5a72;max-width:560px}}
.pw-grid{{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:18px;margin-top:52px;align-items:stretch}}
.pw-card{{position:relative;background:#fff;border:1px solid rgba(11,21,38,.1);border-radius:20px;padding:26px 24px;display:flex;flex-direction:column}}
.pw-card.free{{border:1.5px solid #17b26a;background:#f7fcf9}}
.pw-card.hero{{border:2px solid #2563eb;box-shadow:0 24px 54px -20px rgba(37,99,235,.45)}}
.pw-tag{{position:absolute;top:-12px;left:22px;font-family:'IBM Plex Mono',monospace;font-size:10.5px;font-weight:600;letter-spacing:.1em;padding:5px 12px;border-radius:100px}}
.pw-free-tag{{background:#17b26a;color:#fff}}
.pw-soon{{background:#eef2f8;color:#7c8aa0;border:1px solid rgba(11,21,38,.07)}}
.pw-best{{background:#2563eb;color:#fff}}
.pw-amt{{font-size:38px;font-weight:800;letter-spacing:-.03em;color:#0b1526;margin-top:6px}}
.pw-amt small{{font-size:13px;font-weight:500;color:#6b7a92;letter-spacing:0}}
.pw-name{{margin-top:3px;font-size:14.5px;font-weight:700;color:#0b1526}}
.pw-each{{margin-top:5px;font-size:13px;font-weight:600;color:#2563eb}}
.pw-list{{display:flex;flex-direction:column;gap:10px;margin-top:18px;flex:1}}
.pw-feat{{display:flex;gap:9px;align-items:flex-start;font-size:13.5px;line-height:1.45;color:#243247}}
.pw-ck{{flex:none;color:#2563eb;margin-top:1px;display:flex}}
.pw-card.free .pw-ck{{color:#17b26a}}
.pw-anchor{{margin-top:14px;font-size:12.5px;font-weight:600;color:#2563eb}}
.pw-cta{{margin-top:18px;padding:13px;text-align:center;border-radius:100px;font-size:14.5px;font-weight:700;text-decoration:none;transition:transform .15s ease}}
.pw-cta:hover{{transform:translateY(-1px)}}
.pw-cta.dark{{background:#0b1526;color:#fff;border:1px solid #0b1526}}
.pw-trust{{text-align:center;margin-top:34px;font-size:14px;color:#4b5a72}}
.pw-stars{{color:#f59e0b;letter-spacing:2px;font-size:15px}}
@media(max-width:900px){{.pw-grid{{grid-template-columns:repeat(2,1fr)}}}}
@media(max-width:560px){{.pw-grid{{grid-template-columns:1fr}}.pw-inner{{padding:64px 20px}}.pw-h2{{font-size:31px}}}}
</style>
<div class="pw-inner">
 <div class="pw-head">
  <div class="pw-eyebrow">PRICING</div>
  <h2 class="pw-h2">Get into every class you need.</h2>
  <p class="pw-sub">Start free. Pay once per term if you need more. Never a subscription. Less than a textbook to not lose a semester.</p>
 </div>
 <div class="pw-grid">
  <div class="pw-card free">
   <span class="pw-tag pw-free-tag">Start free</span>
   <div class="pw-amt">$0</div>
   <div class="pw-name">1 class · 2 sections</div>
   <div class="pw-list">{feat("Instant phone alerts")}{feat("Real seats only, never fake")}{feat("No card to start")}</div>
   <a href="/login" class="pw-cta dark">Start free</a>
  </div>
  <div class="pw-card">
   {tag_soon}
   <div class="pw-amt">$19.95</div>
   <div class="pw-name">One class</div>
   <div class="pw-list">{feat("<b>Unlimited sections</b>, not just 2")}</div>
   {cta(1, "Choose", False)}
  </div>
  <div class="pw-card">
   {tag_soon}
   <div class="pw-amt">$24.95</div>
   <div class="pw-name">Two classes</div>
   <div class="pw-list">{feat("Two classes, unlimited sections")}</div>
   {cta(2, "Choose", False)}
  </div>
  <div class="pw-card hero">
   <span class="pw-tag pw-best">Best value{"" if not soon else " · soon"}</span>
   <div class="pw-amt">$29.95</div>
   <div class="pw-name">5 courses</div>
   <div class="pw-each">up to 5 classes · about $6 each</div>
   <div class="pw-list">{feat("Unlimited sections, every class")}</div>
   <div class="pw-anchor">Just $5 more than two classes.</div>
   {cta(3, "Cover my whole schedule", True)}
  </div>
 </div>
 <div class="pw-trust">You only pay if your free class isn't enough.</div>
</div>
</section>"""


def landing_page():
    """The redesigned marketing landing page (logged-out home). Fills the live
    school count; all CTAs route to /login (Google sign-in)."""
    return (LANDING.replace("__METAPIXEL__", META_PIXEL_BASE)
            .replace("__COUNT__", str(proven_count()))
            .replace("__PRICING__", pricing_section())
            .replace("__ADVIDEOV__", _media_ver("tour.mp4"))
            .replace("__ADPOSTERV__", _media_ver("tour-poster.jpg")))

def page(body, feedback=""):
    # Substitute __COUNT__ on the ASSEMBLED page so the shell (PAGE) and every body
    # (FORM, DONE, TERMS…) share one source of truth. These used to hardcode the number,
    # so the signed-in view silently drifted stale on every school add while only the
    # logged-out LANDING updated — 743 showing after the registry hit 746.
    # `feedback` renders in the footer under the tagline; it defaults to "" so every other
    # page (terms, privacy, notices) strips the placeholder rather than leaking it.
    return (PAGE.replace("__BODY__", body)
            .replace("__FEEDBACK__", feedback)
            .replace("__METAPIXEL__", META_PIXEL_BASE)
            .replace("__COUNT__", str(proven_count())))


# --- Coverage: what we can actually PROVE, not what is in the registry file ----------
#
# The homepage used to say len(SCHOOLS) — the number of rows in schools.py, whether or not
# a row worked. 926 rows meant "926 universities" on the marketing page while 31 of them
# returned nothing to a student who signed up. That is not a rounding error, it is a claim
# we could not support, and it is the same silent-failure shape as an alert sent to a
# channel nobody reads.
#
# Both the number and the picker now derive from ops/coverage.json, written by
# ops/sweep-schools.py when it probes every school against its real registration system:
#
#   COUNTED   OK          returned real sections AND correctly separated open from full.
#                         The only verdict we are willing to publish a number for.
#   LISTED    ALL_OPEN    returns usable data, but every section reads open, so we have
#                         not yet watched it call anything full. Watchable, not provable —
#                         so a student may pick it, and it is left OUT of the count.
#   HIDDEN    everything  EMPTY/ERROR/MALFORMED/NEGATIVE/FAKE_OPEN/PHANTOM/NO_EXAMPLE.
#             else        Removed from the picker so nobody can start a watch we cannot
#                         deliver. FAKE_OPEN especially: a school that claims open with no
#                         seats would send false alerts, which costs more than silence.
#
# Existing watches are never touched by this — hiding governs what can be STARTED. A
# school that breaks and is fixed returns to the list on the next sweep, with no code
# change and nobody having to remember to update a number.
COVERAGE_PATH = os.environ.get("COVERAGE_PATH", os.path.join(HERE, "ops", "coverage.json"))
BLOCKED_PATH = os.environ.get("BLOCKED_PATH", os.path.join(HERE, "ops", "blocked.json"))
COUNTED_VERDICTS = ("OK",)
LISTED_VERDICTS = ("OK", "ALL_OPEN")
_cov = {"mtime": -1.0, "data": {}}
_blocked = {"mtime": -1.0, "data": {}}


def coverage():
    """{school_id: verdict} from the last sweep, reloaded when the file changes.

    Missing or unreadable file FAILS OPEN — every school stays listed and counted — and
    pages the operator. Taking the school list down because a data file went missing would
    turn a reporting problem into an outage; an overstated count for the minutes it takes
    someone to notice is the smaller harm. ops/deploy.sh ships this file so "missing"
    means a broken deploy, not a normal state.
    """
    try:
        m = os.path.getmtime(COVERAGE_PATH)
        if m != _cov["mtime"]:
            with open(COVERAGE_PATH) as f:
                raw = json.load(f)
            _cov["data"] = {k: (v.get("verdict") if isinstance(v, dict) else v)
                            for k, v in raw.items()}
            _cov["mtime"] = m
            sw.log(f"  [coverage] loaded {len(_cov['data'])} school verdict(s); "
                   f"{sum(1 for x in _cov['data'].values() if x in COUNTED_VERDICTS)} proven")
    except Exception as e:
        if _cov["mtime"] != -2.0:
            _cov["mtime"] = -2.0        # page once, not every request
            sw.log(f"  [coverage] UNREADABLE ({type(e).__name__}) — failing OPEN, every "
                   f"school listed and counted until it is restored")
            try:
                operator_alert("⚠️ coverage.json unreadable — the homepage count is back to "
                               "the raw registry size and broken schools are selectable "
                               "again. Re-run ops/sweep-schools.py --out ops/coverage.json.")
            except Exception:
                pass
        return {}
    return _cov["data"]


def blocked_schools():
    """ops/blocked.json — schools held off the site by a human decision, outranking the
    sweep. The sweep probes one course and asks whether the answer looks sane; it cannot
    catch an adapter returning confident, wrong data, and it would put such a school back
    on the site at the next run. Jackson College passed the sweep while collapsing three
    terms of sections into one namespace. Keys starting with _ are documentation."""
    try:
        m = os.path.getmtime(BLOCKED_PATH)
        if m != _blocked["mtime"]:
            with open(BLOCKED_PATH) as f:
                _blocked["data"] = {k: v for k, v in json.load(f).items()
                                    if not k.startswith("_")}
            _blocked["mtime"] = m
            if _blocked["data"]:
                sw.log(f"  [coverage] {len(_blocked['data'])} school(s) held off the site "
                       f"by ops/blocked.json: {', '.join(sorted(_blocked['data']))}")
    except Exception:
        return _blocked["data"]        # keep the last good list; never un-block on error
    return _blocked["data"]


def school_listed(school_id):
    """May a student START a watch here? Unknown to the sweep = listed (fail open), but a
    blocklist entry always wins — that one IS a decision, not an absence of data."""
    if school_id in blocked_schools():
        return False
    v = coverage().get(school_id)
    return v is None or v in LISTED_VERDICTS


def listed_schools():
    return [s for s in schools.SCHOOLS.values() if school_listed(s.id)]


def proven_count():
    """The number we are willing to print. Schools whose last probe returned real sections
    AND showed us open and full sections side by side — the evidence that the adapter can
    tell them apart. Falls back to the registry size only when coverage is unavailable."""
    cov = coverage()
    if not cov:
        return len(schools.SCHOOLS)
    blocked = blocked_schools()
    n = sum(1 for s in schools.SCHOOLS
            if cov.get(s) in COUNTED_VERDICTS and s not in blocked)
    return n or len(schools.SCHOOLS)


_schools_js = {"key": None, "val": ""}


def schools_js():
    """Picker payload, rebuilt when coverage changes so a fixed school reappears without
    a restart. Cached against the same mtime the verdicts are — read AFTER coverage() has
    had its chance to reload, or the first call would cache under a stale key."""
    coverage()
    key = _cov["mtime"]
    if _schools_js["key"] != key:
        _schools_js["val"] = json.dumps([
            {"id": s.id, "name": s.name, "ex": s.example}
            for s in sorted(listed_schools(), key=lambda s: s.name.lower())])
        _schools_js["key"] = key
    return _schools_js["val"]


def watches_html(user_id, csrf):
    with db() as c:
        rows = c.execute("SELECT id,school,course,section FROM watches "
                         "WHERE user_id=? ORDER BY id", (user_id,)).fetchall()
    if not rows:
        return ""
    items = ""
    for r in rows:
        sch = schools.SCHOOLS.get(r["school"])
        name = sch.name if sch else r["school"]
        # An all-sections watch stores section="" and used to render as "CMSC250 §," —
        # a section symbol pointing at nothing. It looked like a bug in the row rather
        # than the feature the student had just paid for, and it did not answer the only
        # question they actually have: is this covering everything or not? Say it.
        sect = (f"§{html.escape(r['section'])}" if r["section"]
                else "<span style='color:#0F9D74;font-weight:600'>all sections</span>")
        items += (f"<li><span>{html.escape(r['course'])} {sect}"
                  f" &middot; {html.escape(name)}</span>"
                  f"<form method='post' action='/unwatch'>"
                  f"<input type='hidden' name='id' value='{r['id']}'>"
                  f"<input type='hidden' name='csrf' value='{csrf}'>"
                  f"<button class='stop'><svg width='12' height='12' viewBox='0 0 24 24' "
                  f"fill='none' stroke='currentColor' stroke-width='2.5' stroke-linecap='round'>"
                  f"<path d='M18 6 6 18'/><path d='m6 6 12 12'/></svg>Stop</button></form></li>")
    hdr = ("<svg width='13' height='13' viewBox='0 0 24 24' fill='none' stroke='currentColor' "
           "stroke-width='2' stroke-linecap='round' stroke-linejoin='round'><path d='M10.268 21a2 "
           "2 0 0 0 3.464 0'/><path d='M3.262 15.326A1 1 0 0 0 4 17h16a1 1 0 0 0 .74-1.673C19.41 "
           "13.956 18 12.499 18 8A6 6 0 0 0 6 8c0 4.499-1.411 5.956-2.738 7.326'/></svg>")
    return f"<div class='mywatches'><b>{hdr}Your watches</b><ul>" + items + "</ul></div>"


def _sms_consent_html():
    """The registered opt-in disclosure, verbatim, with Terms/Privacy hyperlinked. Stays
    word-for-word identical to SMS_CONSENT_WORDING everywhere it renders (checkbox,
    /text-alerts, SMS Terms) — that's what the 10DLC campaign registers."""
    return html.escape(SMS_CONSENT_WORDING).replace(
        "Terms and Privacy Policy",
        '<a href="/sms-terms">Terms</a> and <a href="/privacy">Privacy Policy</a>')


def _sms_optin_form(tok):
    """The single web opt-in form: mobile number + an UNCHECKED-by-default consent
    checkbox carrying the exact disclosure. Both fields are required, so a submission
    cannot happen without an explicit, affirmative opt-in. Reused by the in-app card and
    the public /text-alerts page so the two can never drift. Posts to /sms/optin, which
    requires sign-in (ties consent to an account) — a logged-out visitor still SEES the
    checkbox and language."""
    return (f'<form method="post" action="/sms/optin" style="margin:0">'
            f'<input type="hidden" name="csrf" value="{html.escape(tok or "")}">'
            f'<label>Mobile number <small>(U.S. mobile)</small></label>'
            f'<input name="phone" type="tel" inputmode="tel" placeholder="e.g. 301 555 0123" '
            f'autocomplete="tel" required>'
            f'<label style="display:flex;gap:9px;align-items:flex-start;font-weight:400;'
            f'font-size:12.5px;line-height:1.55;margin-top:9px;text-transform:none;'
            f'letter-spacing:0"><input type="checkbox" name="sms_consent" value="1" required '
            f'style="margin-top:2px;flex:none;width:auto">'
            f'<span>{_sms_consent_html()}</span></label>'
            f'<button type="submit" style="margin-top:11px">Turn on text alerts</button></form>')


def sms_block(user, tok):
    """In-app text-alert opt-in card for EVERY signed-in user, free included — SMS is
    consent-gated, not tier-gated. Empty only while SMS is dormant (the /text-alerts page
    is the public opt-in home until launch). Single opt-in: once the box is submitted the
    alerts are ON — there is no confirm-reply step."""
    if not SMS_ENABLED or not user:
        return ""          # every signed-in user, free included — SMS is consent-gated now
    with db() as c:
        row = c.execute("SELECT phone, confirmed_at, revoked_at FROM sms_consent WHERE "
                        "user_id=? ORDER BY id DESC LIMIT 1", (user["id"],)).fetchone()
    box = ('<div style="margin-top:14px;border-top:1px solid #F3F4F6;padding-top:13px">')
    if row and row["confirmed_at"] and not row["revoked_at"]:
        return (box + '<p class="note" style="margin:0">📱 Text alerts are ON for '
                f'<b>••• ••• {html.escape(row["phone"][-4:])}</b>. Reply STOP to any alert '
                'to turn them off.</p></div>')
    return box + _sms_optin_form(tok) + "</div>"


def inline_phone_field(user):
    """The phone + consent prompt, INSIDE the watch form, directly after the sections.

    It used to live in its own card below the form and people never reached it: they
    arrive wanting to watch a class, fill the first fields they see, and submit. The
    option has to sit in the path they already walk, not beside it. It briefly sat
    BEFORE the sections; Nathan moved it after, so the student finishes describing the
    class they came for before being asked for anything about themselves.

    Marked RECOMMENDED, never required — a phone number is not a condition of using
    SeatWatch, and saying so is both true and a TCPA nicety. Empty for anyone who has
    already opted in (nothing to ask) and while SMS is dormant.

    The checkbox is unchecked by default and carries the exact registered disclosure, the
    same wording as the standalone form, because that string is what the carrier approved
    and what we would show if consent were ever disputed.
    """
    if not SMS_ENABLED or not user:
        return ""
    with db() as c:
        row = c.execute("SELECT 1 FROM sms_consent WHERE user_id=? AND confirmed_at "
                        "IS NOT NULL AND revoked_at IS NULL LIMIT 1",
                        (user["id"],)).fetchone()
    if row:
        return ""                      # already opted in; do not ask twice
    return (
        ' <label>Mobile number '
        '<small style="color:#0F9D74;font-weight:700">RECOMMENDED &mdash; a seat can open '
        'at 2am and a text is what wakes you</small></label>\n'
        ' <input name="phone" type="tel" inputmode="tel" autocomplete="tel" '
        'placeholder="e.g. 301 555 0123 (optional)">\n'
        ' <label style="display:flex;gap:9px;align-items:flex-start;font-weight:400;'
        'font-size:12.5px;line-height:1.55;margin:7px 0 2px;text-transform:none;'
        'letter-spacing:0"><input type="checkbox" name="sms_consent" value="1" '
        'style="margin-top:2px;flex:none;width:auto">'
        f'<span>{_sms_consent_html()}</span></label>\n')


def notify_prefs_block(user, tok):
    """Email and text — the two ways a student can be alerted.

    Deliberately shown to everyone (not just paid): a free user with both email and text
    firing on the same seat is the person most likely to call us spam. There is no
    checkbox for "all off" — the floor is enforced in the handler, not here, because a
    UI-only guard is bypassed by anyone who can craft a POST.

    Email is always listed. Text only appears for someone who has actually given consent,
    so a student who never gave us a number sees one box, which they cannot switch off —
    the honest UI for "this is the only way we can reach you."
    """
    if not user:
        return ""
    _, want_email, want_sms = notify_prefs(user["id"])
    with db() as c:
        has_sms = c.execute("SELECT 1 FROM sms_consent WHERE user_id=? AND confirmed_at "
                            "IS NOT NULL AND revoked_at IS NULL LIMIT 1",
                            (user["id"],)).fetchone() is not None
    ck = ' checked'
    # sms_offered marks that this form ASKED about texts. Without it the handler cannot
    # tell an unchecked box from a box that was never rendered, and would read the second
    # as "switch texts off" — silently disabling a channel the student never touched.
    sms_row = ('' if not has_sms else
               '<input type="hidden" name="sms_offered" value="1">'
               '<label style="display:flex;gap:9px;align-items:center;font-weight:400;'
               'font-size:13px;text-transform:none;letter-spacing:0;margin:6px 0 0">'
               f'<input type="checkbox" name="notify_sms" value="1"{ck if want_sms else ""} '
               'style="flex:none;width:auto"><span>Text message</span></label>')
    floor = ('Email is how we reach you, so it stays on. Add a phone number when you add a '
             'class if you want texts too.' if not has_sms else
             'Keep at least one on, or we have no way to tell you a seat opened.')
    return (
        '<div style="margin-top:14px;border-top:1px solid #F3F4F6;padding-top:13px">'
        '<form method="post" action="/notify-prefs" style="margin:0">'
        f'<input type="hidden" name="csrf" value="{html.escape(tok or "")}">'
        '<label style="margin-bottom:7px">How should we alert you?</label>'
        '<label style="display:flex;gap:9px;align-items:center;font-weight:400;font-size:13px;'
        'text-transform:none;letter-spacing:0;margin:0">'
        # Just "Email". The address was printed here beside the checkbox, which told the
        # signed-in student nothing they did not already know — they are looking at their
        # own account — and put a live address on screen during screen-shares and demos.
        f'<input type="checkbox" name="notify_email" value="1"{ck if want_email else ""} '
        f'style="flex:none;width:auto"><span>Email</span></label>'
        + sms_row +
        f'<p class="note" style="margin:8px 0 0;font-size:12px">{floor}</p>'
        '<button type="submit" style="margin-top:9px">Save</button></form></div>')


def feedback_block(tok):
    """Click-to-open feedback box, rendered at the BOTTOM of the page under the tagline.

    Sized to actually get noticed (the previous version was a small line buried inside the
    watch card). Still plain <details> + a form, no JS, so it works everywhere and can't
    break the page. The textarea is left EMPTY on purpose: a long placeholder reads as
    instructions and narrows what people think they're allowed to say.

    Footer text is 12px/centered with wide letter-spacing, so this block resets those
    explicitly rather than inheriting them."""
    if not tok:
        return ""
    return (
        '<div style="max-width:560px;margin:22px auto 0;text-align:left;letter-spacing:normal;'
        'line-height:1.5">'
        '<details style="border:1.5px solid #DBEAFE;border-radius:14px;background:#F8FAFC;'
        'overflow:hidden">'
        '<summary style="cursor:pointer;list-style:none;padding:15px 18px;font-size:15px;'
        'font-weight:700;color:#2563eb;display:flex;align-items:center;gap:9px">'
        '<svg width="17" height="17" viewBox="0 0 24 24" fill="none" stroke="currentColor" '
        'stroke-width="2" stroke-linecap="round" stroke-linejoin="round" style="flex:none">'
        '<path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z"/></svg>'
        'Got feedback? Tell us how we can improve</summary>'
        '<form method="post" action="/feedback" style="margin:0;padding:0 18px 18px">'
        f'<input type="hidden" name="csrf" value="{html.escape(tok)}">'
        '<textarea name="message" rows="5" required maxlength="4000" '
        'style="width:100%;box-sizing:border-box;padding:12px 14px;border:1.5px solid #E5E7EB;'
        'border-radius:11px;font-family:inherit;font-size:15px;line-height:1.55;color:#0b1526;'
        'background:#fff;resize:vertical"></textarea>'
        '<button type="submit" style="margin-top:10px;width:100%;padding:12px;border:0;'
        'border-radius:11px;background:#2563eb;color:#fff;font-weight:700;font-size:15px;'
        'font-family:inherit;cursor:pointer">Send feedback</button>'
        '</form></details></div>')


def text_alerts_body(user):
    """PUBLIC /text-alerts page — the carrier-inspectable opt-in. Shows the program, the
    UNCHECKED consent checkbox with the exact registered disclosure, and links to the SMS
    Terms + Privacy Policy. Reachable without an account (a logged-out visitor sees the
    checkbox and language; submitting prompts sign-in). Everything here is truthful to what
    the code does today: single web opt-in, no confirmation-reply step, texts sent only
    once the SMS service is live."""
    tok = csrf_token(user["id"]) if user else ""
    gate = ("" if user else
            '<p class="note" style="margin:0 0 12px"><a href="/login">Sign in</a> to turn on '
            'text alerts. They are free on every plan.</p>')
    return (
        '<h2 style="font-size:20px;margin:6px 0 2px">SeatWatch Text Alerts</h2>'
        '<p class="sub" style="margin-bottom:14px">Get a text the moment a seat opens.</p>'
        f'<div style="{_PSTYLE}">'
        '<p>SeatWatch watches the full college courses you choose and sends an automated text '
        'message the instant a seat opens, so you can register before it fills again. Text '
        'alerts are an optional feature of SeatWatch, available on every plan including the '
        'free one.</p>'
        '<p><b>How it works.</b> Enter your U.S. mobile number below and check '
        'the consent box. That is your opt-in. The box is unchecked by default, and a '
        'phone number is <b>never required</b> to use SeatWatch: every plan works '
        'fully with web push and email.</p>'
        '<div style="background:#F8FAFC;border:1px solid rgba(11,21,38,.08);border-radius:14px;'
        'padding:16px 16px 18px;margin:15px 0">'
        f'{gate}{_sms_optin_form(tok)}</div>'
        '<p style="font-size:12.5px;color:#6b7a92;line-height:1.6"><b>Message frequency varies</b> '
        'based on the courses you monitor. <b>Message and data rates may apply.</b> Reply '
        '<b>STOP</b> to any alert to unsubscribe, or <b>HELP</b> for help. Consent is not a '
        'condition of purchase.</p>'
        '</div>'
        '<p style="font-size:13px;margin-top:16px"><a href="/">&larr; Back to SeatWatch</a> '
        '&nbsp;&middot;&nbsp; <a href="/sms-terms">SMS Terms &amp; Conditions</a> '
        '&nbsp;&middot;&nbsp; <a href="/privacy">Privacy Policy</a></p>')


def form_page(notice="", user=None):
    if user is None:
        card = (CARD_LOGIN.replace("__NOTICE__", notice)
                .replace("__APPLEBTN__", APPLE_BTN if APPLE_ENABLED else ""))
    else:
        tok = csrf_token(user["id"])
        # Section field + plan note are tier-aware. Paid (tier>=1) watches EVERY section, so
        # listing them is pointless — the field goes optional and the copy says so. Free copy
        # is preserved verbatim (and is what shows whenever paid is parked, since tier is 0).
        if effective_tier(user) >= 1:
            secfield = ('<label>Section number(s) <small>(name the ones you want, or leave '
                        'blank for <b>all</b>)</small></label>\n'
                        ' <input name="sections" placeholder="e.g. 0101, 0102 &mdash; or blank for every section">')
            plannote = ('<p class="note">Name the sections you can actually take and we will '
                        'only alert you about those. Leave it blank and your plan watches '
                        '<b>every section</b> of the class.</p>')
        else:
            secfield = ('<label>Section number(s) <small>(up to 2, comma-separated)</small></label>\n'
                        ' <input name="sections" placeholder="e.g. 0101, 0102" required>')
            plannote = ('<p class="note">Free plan: <b>1 class, up to 2 sections</b>. Heads up: a '
                        'seat that opens in a section you\'re <i>not</i> watching won\'t alert you; '
                        'paid plans watch unlimited sections.</p>')
        card = (CARD_FORM.replace("__NOTICE__", notice)
                .replace("__PHONEFIELD__", inline_phone_field(user))
                .replace("__SECFIELD__", secfield)
                .replace("__PLANNOTE__", plannote)
                .replace("__EMAIL__", html.escape(user["email"]))
                .replace("__PUSHBLOCK__", notify_prefs_block(user, tok))
                .replace("__CSRF__", tok)
                .replace("__WATCHES__", watches_html(user["id"], tok))
                .replace("__SCHOOLS__", schools_js()))
    # Feedback lives in the footer, and only for signed-in users (the POST requires auth,
    # so showing it logged-out would just bounce them to a login screen).
    fb = feedback_block(csrf_token(user["id"])) if user else ""
    return page(FORM.replace("__CARD__", card).replace("__PRICING__", pricing_section()), fb)


def alert_intro(user):
    """Confirmation that the student is already covered — there is no setup step left.

    This used to hand off to a 'now turn on phone alerts' widget. With push retired there
    is nothing further to do, so the line says so and stops. Naming the address matters:
    it is the student's one chance to notice we have the wrong one before a seat opens."""
    if EMAIL_ENABLED:
        return ("<div class='ok'><svg width='18' height='18' viewBox='0 0 24 24' fill='none' "
                "stroke='currentColor' stroke-width='2' stroke-linecap='round' "
                "stroke-linejoin='round'><rect x='2' y='4' width='20' height='16' rx='2'/>"
                "<path d='m22 7-8.97 5.7a1.94 1.94 0 0 1-2.06 0L2 7'/></svg><span>We'll email "
                f"you at <b>{html.escape(user['email'])}</b> the second a seat opens, nothing "
                "else to do.</span></div>")
    return ("<p class='note' style='text-align:left'>Alerts are being set up on this "
            "account, check back shortly.</p>")


def done_page(what, user):
    tok = csrf_token(user["id"])
    body = (DONE.replace("__WHAT__", html.escape(what))
                .replace("__ALERTINTRO__", alert_intro(user))
                .replace("__PUSHBLOCK__", notify_prefs_block(user, tok)))
    # The ONLY place CompleteRegistration fires, and it fires at most ONCE PER STUDENT,
    # ever — on their first successful watch. Meta is being asked "did this person become
    # a user?", so a student who adds four classes must not read as four acquisitions.
    #
    # The atomic UPDATE is the whole mechanism. Exactly one statement can flip a NULL
    # pixel_activated_at, so rowcount==1 happens once and only once per account however
    # the page is reached: refresh, Back, a replayed flash cookie, or two tabs racing.
    # That is stronger than the client-side eventID this used to carry, and it needs no
    # identifier derived from the student or from what they are watching.
    # Stamped whether or not a pixel is configured. "When did this student first create
    # a watch" is a fact about the product, not about advertising — and recording it only
    # while tracking happens to be enabled would leave a hole: anyone who activated during
    # a pixel-off period keeps a NULL, and their SECOND watch would later be reported as
    # a first. The pixel only ever READS this flag.
    fire = False
    try:
        with db() as c:
            fire = c.execute("UPDATE users SET pixel_activated_at=? WHERE id=? AND "
                             "pixel_activated_at IS NULL",
                             (time.time(), user["id"])).rowcount == 1
    except Exception:
        fire = False              # tracking must never be able to break the success page
    if fire and META_PIXEL_ID:
        # No parameters. Meta gets the fact of a conversion and nothing else: no email,
        # no phone, no school, course, section or professor, and no id derived from them.
        body += "<script>window.fbq&&fbq('track','CompleteRegistration');</script>"
    return page(body)


# ----------------------------------------------------------------------- server
class Handler(BaseHTTPRequestHandler):
    server_version = "SeatWatch"   # don't disclose Python / BaseHTTP version
    sys_version = ""

    # A SOCKET TIMEOUT, and it is load-bearing rather than tidy.
    #
    # The body read is capped at 4096 bytes, but a client that DECLARES a large
    # Content-Length and then sends nothing makes rfile.read() sit waiting for bytes that
    # never arrive. With no timeout that thread is parked forever; a handful of such
    # requests exhausts the pool and the site stops answering anyone — the classic
    # slowloris, costing an attacker almost nothing.
    #
    # This was invisible until the rate limit was loosened: at 15/hour the flood tests
    # were being refused BEFORE they reached the read, so the suite passed for a reason
    # that had nothing to do with the bug being absent. A tight limit was standing in
    # front of a real defect and hiding it.
    timeout = 20

    def _send(self, body, code=200, extra_cookies=()):
        data = body.encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(data)))
        # Signed-in HTML must never rest in a shared or browser cache: on a shared campus
        # machine the next person can press Back and read the previous student's watches.
        # Keyed on cookie PRESENCE (no DB hit, no session lookup) rather than blanket, so
        # the anonymous landing page stays edge-cacheable — if a post drives a spike we do
        # not want every hit landing on the one origin box that also runs the poller.
        # Errs toward no-store (a stale/expired cookie still suppresses caching), never
        # toward caching private content.
        if self._cookie("sw_session"):
            self.send_header("Cache-Control", "private, no-store, max-age=0")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("X-Frame-Options", "DENY")
        self.send_header("Referrer-Policy", "no-referrer")
        self.send_header("Strict-Transport-Security", "max-age=15552000")
        for ck in extra_cookies:            # e.g. clearing a consumed flash message
            self.send_header("Set-Cookie", ck)
        self.send_header("Content-Security-Policy", CSP)
        self.end_headers()
        self.wfile.write(data)

    def _send_bytes(self, data, ctype, code=200, cache="public, max-age=86400"):
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Cache-Control", cache)
        self.send_header("X-Content-Type-Options", "nosniff")
        self.end_headers()
        self.wfile.write(data)

    def _send_json(self, obj, code=200):
        self._send_bytes(json.dumps(obj).encode(), "application/json", code, cache="no-store")

    # POST / REDIRECT / GET.
    #
    # Every form used to answer its own POST with HTML, which leaves a POST in the
    # browser's history. Pressing Back then offers "Confirm Form Resubmission", and a
    # student who presses reload re-runs whatever the POST did — adding a watch twice,
    # or worse on a payment path. It also makes the ordinary back button look broken,
    # which is its own quiet cost.
    #
    # So a POST now answers with a 303 to a GET, carrying its message in a short-lived
    # SIGNED cookie. Signed because the message is rendered back into the page: an
    # unsigned one would let any site set arbitrary text on seatwatchapp.com, and
    # 30 seconds because it exists only to survive one redirect.
    _FLASH_MAX_AGE = 30

    def _flash_set(self, kind, code, msg):
        payload = f"{kind}|{code}|{base64.urlsafe_b64encode(msg.encode()).decode()}"
        val = payload + "|" + _sign("flash:" + payload)
        return (f"sw_flash={val}; Path=/; Max-Age={self._FLASH_MAX_AGE}; "
                "HttpOnly; Secure; SameSite=Lax")

    def _flash_take(self):
        """(kind, code, msg) or (None, 0, ''). Fails closed on anything tampered with."""
        raw = self._cookie("sw_flash")
        if not raw:
            return None, 0, ""
        bits = raw.split("|")
        if len(bits) != 4:
            return None, 0, ""
        kind, code, b64, sig = bits
        if not hmac.compare_digest(sig, _sign("flash:" + "|".join(bits[:3]))):
            return None, 0, ""
        try:
            msg = base64.urlsafe_b64decode(b64.encode()).decode()
        except Exception:
            return None, 0, ""
        return kind, (int(code) if code.isdigit() else 200), msg

    _FLASH_CLEAR = "sw_flash=; Path=/; Max-Age=0; HttpOnly; Secure; SameSite=Lax"

    def _redirect(self, location, cookies=()):
        self.send_response(302)
        self.send_header("Location", location)
        for ck in cookies:
            self.send_header("Set-Cookie", ck)
        self.send_header("Content-Length", "0")
        self.end_headers()

    _SRC_RE = re.compile(r"^[A-Za-z0-9._-]{1,64}$")

    def _source_cookie(self):
        """A utm_source on the landing URL, turned into a cookie so it survives the Google
        round-trip. The parameter is on the page they land on; the user row is created
        after OAuth returns, by which point the query string is gone — a cookie is the only
        thing that spans both.

        Whitelisted to [A-Za-z0-9._-] and truncated: this is attacker-supplied text that
        ends up in a database and on an admin page, so it is treated as hostile. Returns a
        Set-Cookie value, or None when there is nothing to record.
        """
        q = urllib.parse.parse_qs(urllib.parse.urlparse(self.path).query)
        src = (q.get("utm_source") or q.get("src") or q.get("ref") or [""])[0][:64]
        if not src or not self._SRC_RE.match(src):
            return None
        # SameSite follows the sign-in that is actually enabled. Apple returns with
        # response_mode=form_post, a CROSS-SITE POST, and a Lax cookie is not sent on one
        # — sw_astate right below is already SameSite=None for exactly this reason. With
        # Lax and Apple on, every Apple signup would record a blank source and look
        # organic: a silent miss, not an error. Lax stays the default while Google is the
        # only live path, because this needs to travel no further than the round-trip.
        same = "None" if APPLE_ENABLED else "Lax"
        return (f"sw_src={src}; Path=/; Max-Age=2592000; "
                f"HttpOnly; Secure; SameSite={same}")

    def _cookie(self, name):
        for part in (self.headers.get("Cookie") or "").split(";"):
            k, _, v = part.strip().partition("=")
            if k == name:
                return v
        return ""

    def _user(self):
        uid = read_session_value(self._cookie("sw_session"))
        if uid is None:
            return None
        with db() as c:
            return c.execute("SELECT * FROM users WHERE id=?", (uid,)).fetchone()

    def do_GET(self):
        url = urlparse(self.path)
        path, qs = url.path, parse_qs(url.query)
        if path == "/terms":
            return self._send(page(TERMS))
        if path == "/privacy":
            return self._send(page(PRIVACY))
        if path.startswith("/r/"):
            # Alert click -> record ACTION (once), then bounce to the registrar.
            # A student mid-registration must never be stranded: any failure here still
            # redirects, falling back to the homepage only if the token is unknown.
            token = path[3:][:64]
            dest = BASE_URL or "https://seatwatchapp.com/"
            try:
                with db() as c:
                    row = c.execute("SELECT id, school, course, clicked_at FROM alert_attempt "
                                    "WHERE token=?", (token,)).fetchone()
                    if row:
                        if row["clicked_at"] is None:      # first click only = true action
                            c.execute("UPDATE alert_attempt SET clicked_at=? WHERE id=?",
                                      (time.time(), row["id"]))
                        s = schools.SCHOOLS.get(row["school"])
                        if s:
                            dest = s.reg_url(row["course"])
            except Exception as e:
                sw.log(f"  [click] {type(e).__name__} — redirecting anyway")
            return self._redirect(dest)
        if path == "/sms-terms":
            return self._send(page(SMS_TERMS))
        if path == "/text-alerts":            # public opt-in page (carrier-inspectable)
            return self._send(page(text_alerts_body(self._user())))
        if path == "/sw.js":   # service worker: no-cache so updates roll out fast
            return self._send_bytes(SW_JS.encode(), "application/javascript; charset=utf-8",
                                    cache="no-cache")
        if path == "/manifest.json":
            return self._send_bytes(MANIFEST.encode(), "application/manifest+json",
                                    cache="public, max-age=3600")
        if path == "/.well-known/assetlinks.json" and TWA_FINGERPRINTS:
            body = json.dumps([{"relation": ["delegate_permission/common.handle_all_urls"],
                                "target": {"namespace": "android_app",
                                           "package_name": TWA_PACKAGE,
                                           "sha256_cert_fingerprints": TWA_FINGERPRINTS}}])
            return self._send_bytes(body.encode(), "application/json",
                                    cache="public, max-age=3600")
        if path == "/tour.mp4":
            return _send_media(self, "tour.mp4", "video/mp4")
        if path == "/tour-poster.jpg":
            return _send_media(self, "tour-poster.jpg", "image/jpeg")
        if path == "/icon-192.png":
            return (self._send_bytes(ICON192, "image/png") if ICON192
                    else self._send(page("<p>Not found.</p>"), 404))
        if path == "/icon-512.png":
            return (self._send_bytes(ICON512, "image/png") if ICON512
                    else self._send(page("<p>Not found.</p>"), 404))
        if path == "/og-image.png":
            return (self._send_bytes(OG_IMAGE, "image/png") if OG_IMAGE
                    else self._send_bytes(ICON512, "image/png"))
        if path == "/robots.txt":
            return self._send_bytes(ROBOTS.encode(), "text/plain; charset=utf-8",
                                    cache="public, max-age=86400")
        if path == "/sitemap.xml":
            return self._send_bytes(SITEMAP.encode(), "application/xml; charset=utf-8",
                                    cache="public, max-age=86400")
        if path in ("/login", "/login/google"):
            if not GOOGLE_CLIENT_ID:
                return self._send(form_page(
                    "<div class='ok'>Sign-in is being switched on, check back shortly!</div>"))
            if path == "/login" and APPLE_ENABLED:
                # two providers exist -> /login becomes the chooser card; the direct
                # /login/google and /login/apple links on it skip straight through.
                return self._send(form_page())
            state = secrets.token_urlsafe(24)
            return self._redirect(google_auth_url(state), cookies=[
                f"sw_state={state}; Path=/; Max-Age=600; HttpOnly; Secure; SameSite=Lax"])
        if path == "/login/apple":
            if not APPLE_ENABLED:
                return self._redirect("/login")
            state = secrets.token_urlsafe(24)
            return self._redirect(apple_auth_url(state), cookies=[
                f"sw_astate={state}; Path=/; Max-Age=600; HttpOnly; Secure; SameSite=None"])
        if path == "/auth/callback":
            state, code = qs.get("state", [""])[0], qs.get("code", [""])[0]
            want = self._cookie("sw_state")
            clear = "sw_state=; Path=/; Max-Age=0; HttpOnly; Secure; SameSite=Lax"
            if not (state and want and code) or not hmac.compare_digest(state, want):
                return self._send(form_page(
                    "<div class='ok'>Sign-in didn't complete, please try again.</div>"))
            info = google_exchange(code)
            if not info:
                return self._send(form_page(
                    "<div class='ok'>Google sign-in failed, please try again.</div>"))
            user = get_or_create_user(info["sub"], info["email"],
                                      ip=self._client_ip(), device_id=self._device_id(),
                                      source=self._cookie("sw_src"))
            return self._redirect("/", cookies=[session_cookie(user["id"]), clear])
        if path == "/logout":
            return self._redirect("/", cookies=[
                "sw_session=; Path=/; Max-Age=0; HttpOnly; Secure; SameSite=Lax"])
        if path == "/pricing":
            if not PAID_LIVE:
                return self._send(page("<p>Paid plans are coming soon. "
                                       "<a href='/'>Back</a></p>"))
            return self._send(page(self._pricing_html(self._user())))
        if path == "/checkout":
            u = self._user()
            if not u:
                return self._redirect("/login")
            try:
                target = int(qs.get("tier", ["0"])[0])
            except ValueError:
                target = 0
            url = stripe_checkout_url(u, target)   # None if not a valid paid upgrade
            return self._redirect(url or "/pricing")
        if path == "/checkout/success":
            # unlock happens via the webhook, NOT here — this is just a friendly page.
            return self._send(page(
                "<div class='card reveal d2' style='text-align:center'>"
                "<h2 class='ct'>You're upgraded 🎉</h2>"
                "<p class='cs'>Your plan is active. It may take a moment to reflect, "
                "add your classes below.</p>"
                "<a href='/' style='display:block;margin-top:14px;font-weight:700'>"
                "← Go watch your classes</a></div>"))
        if path == "/admin/stats":
            # operator-only usage aggregates (no PII). Rate-limit BEFORE the key compare
            # blunts brute force; every failure path is the ordinary 404 page.
            if (not rate_ok(self._client_ip()) or not STATS_KEY
                    or not hmac.compare_digest(qs.get("key", [""])[0], STATS_KEY)):
                return self._send(page("<p>Not found. <a href='/'>Home</a></p>"), 404)
            with db() as c:
                stats = {
                    "users": c.execute("SELECT COUNT(*) FROM users").fetchone()[0],
                    "watches": c.execute("SELECT COUNT(*) FROM watches").fetchone()[0],
                    "push_devices": c.execute("SELECT COUNT(*) FROM push_subs").fetchone()[0],
                    "guardian": guardian.report_block(),
                    "signups_by_day": {r[0]: r[1] for r in c.execute(
                        "SELECT date(created,'unixepoch') d, COUNT(*) FROM users "
                        "GROUP BY d ORDER BY d")},
                    "watches_by_school": {r[0]: r[1] for r in c.execute(
                        "SELECT school, COUNT(*) n FROM watches "
                        "GROUP BY school ORDER BY n DESC LIMIT 40")},
                    "watched_courses_top": {f"{r[0]} {r[1]}": r[2] for r in c.execute(
                        "SELECT school, course, COUNT(*) n FROM watches "
                        "GROUP BY school, course ORDER BY n DESC LIMIT 40")},
                    # abuse review (ids only, never emails): soft risk signals + the
                    # class-split detector
                    "flagged_users": [
                        {"id": r["id"], "risk": r["risk_score"],
                         "free_eligible": r["free_eligible"],
                         "watches": r["n"]}
                        for r in c.execute(
                            "SELECT u.id, u.risk_score, u.free_eligible, "
                            "(SELECT COUNT(*) FROM watches w WHERE w.user_id=u.id) n "
                            "FROM users u WHERE u.risk_score>0 OR u.free_eligible=0 "
                            "ORDER BY u.risk_score DESC LIMIT 25")],
                    "suspected_abuse_clusters": _abuse_clusters(c),
                    # paid-conversion instrumentation
                    "paid_enabled": PAID_ENABLED,
                    "users_by_tier": {str(r[0]): r[1] for r in c.execute(
                        "SELECT plan_tier, COUNT(*) FROM users GROUP BY plan_tier")},
                    "revenue_cents_by_tier": {str(t): TIER_PRICE_CENTS[t] * c.execute(
                        "SELECT COUNT(*) FROM users WHERE plan_tier=? AND plan_purchased_at>?",
                        (t, time.time() - PAID_TERM_DAYS * 86400)).fetchone()[0]
                        for t in TIER_PRICE_CENTS},
                    "conv_signals_total": {r[0]: r[1] for r in c.execute(
                        "SELECT kind, COUNT(*) FROM conv_signals GROUP BY kind")},
                    "conv_signals_7d": {r[0]: r[1] for r in c.execute(
                        "SELECT kind, COUNT(*) FROM conv_signals WHERE created>? GROUP BY kind",
                        (time.time() - 7 * 86400,))},
                }
            return self._send_json(stats)
        if path == "/dev-login" and DEV_LOGIN:   # local testing only (env-gated)
            email = qs.get("email", ["dev@example.com"])[0][:80]
            user = get_or_create_user("dev:" + email, email,
                                      ip=self._client_ip(), device_id=self._device_id())
            return self._redirect("/", cookies=[session_cookie(user["id"])])
        if path != "/":
            return self._send(page("<p>Not found. <a href='/'>Home</a></p>"), 404)
        u = self._user()
        if u is None:
            src = self._source_cookie()
            return self._send(landing_page(), extra_cookies=(src,) if src else ())
        kind, code, msg = self._flash_take()
        if kind == "done":
            return self._send(done_page(msg, u), extra_cookies=(self._FLASH_CLEAR,))
        if kind == "notice":
            err = code >= 400
            icon = self._ERR_ICON if err else self._OK_ICON
            note = (f"<div class='{'err' if err else 'ok'}'>{icon}"
                    f"<span>{html.escape(msg)}</span></div>")
            return self._send(form_page(note, user=u), extra_cookies=(self._FLASH_CLEAR,))
        self._send(form_page(user=u))

    def _device_id(self):
        """Soft device marker from the sw_dev cookie (JS keeps a localStorage mirror so
        clearing cookies alone doesn't shed it). Advisory signal only — absent or forged
        just means no signal, never a block."""
        v = self._cookie("sw_dev") or ""
        return v[:64] if re.fullmatch(r"[A-Za-z0-9-]{8,64}", v) else None

    def _rate_key(self):
        """Who to charge this request to. A signed session identifies a person, so use it:
        NAT then cannot make one student's activity throttle another's. Falls back to the
        address only when we genuinely do not know who is calling."""
        uid = read_session_value(self._cookie("sw_session"))
        return (f"u:{uid}", RATE_MAX_USER) if uid else (self._client_ip(), RATE_MAX)

    def _client_ip(self):
        # Cloudflare sets CF-Connecting-IP itself and overwrites any value the
        # visitor sends, so it can't be spoofed. X-Forwarded-For's FIRST hop
        # CAN be forged by the client (rate-limit bypass) — never trust it.
        cf = self.headers.get("CF-Connecting-IP", "").strip()
        return cf or self.client_address[0]

    _OK_ICON = ("<svg width='18' height='18' viewBox='0 0 24 24' fill='none' stroke='currentColor' "
                "stroke-width='2' stroke-linecap='round' stroke-linejoin='round'><circle cx='12' "
                "cy='12' r='10'/><path d='m9 12 2 2 4-4'/></svg>")

    _ERR_ICON = ("<svg width='18' height='18' viewBox='0 0 24 24' fill='none' stroke='currentColor' "
                 "stroke-width='2' stroke-linecap='round' stroke-linejoin='round'><circle cx='12' "
                 "cy='12' r='10'/><path d='M12 8v5'/><path d='M12 16.5h.01'/></svg>")

    def _notice(self, msg, code=200, user=None):
        """Style follows the STATUS CODE, not the call site.

        Every notice used to render green with a tick, including "Too many requests" at
        429 — a failure wearing the costume of a success. A student reads the tick, not
        the sentence, and walks away believing their class is being watched when nothing
        was saved. Any 4xx/5xx is now visibly a problem.
        """
        # PRG on SUCCESS ONLY, and the exception is not cosmetic.
        #
        # Redirecting everything looked tidier and broke the meaning of the response: a
        # rate-limited POST came back 303, so the 429 disappeared. The action was still
        # refused, but the status code said otherwise — and a status code is the only
        # thing a non-browser client, a monitor, or a test can read. Losing 429 in
        # particular hides exactly the signal you need when someone is hammering you.
        #
        # So: 2xx redirects (that is the common path, and the one that put a POST in the
        # back-button history), while 4xx/5xx render in place with their real status. The
        # cost is that Back after a VALIDATION error can still offer to resubmit — much
        # rarer, and resubmitting a rejected form repeats nothing.
        if self.command == "POST" and code < 400:
            self.send_response(303)
            self.send_header("Location", "/")
            self.send_header("Set-Cookie", self._flash_set("notice", code, msg))
            self.send_header("Content-Length", "0")
            self.end_headers()
            return
        err = code >= 400
        icon = self._ERR_ICON if err else self._OK_ICON
        cls = "err" if err else "ok"
        self._send(form_page(f"<div class='{cls}'>{icon}<span>{html.escape(msg)}</span></div>",
                             user=user), code)

    @staticmethod
    def _plan_upsell(tier):
        """Message when a user hits their course-count ceiling. Names the next tier and
        its price when paid is live; stays a plain limit message while paid is dormant."""
        nxt = tier + 1
        if PAID_LIVE and nxt in TIER_PRICE_CENTS:
            delta = (TIER_PRICE_CENTS[nxt] - TIER_PRICE_CENTS.get(tier, 0)) / 100
            return (f"Your plan covers {tier_courses(tier)} "
                    f"class{'es' if tier_courses(tier) > 1 else ''}. Add another for "
                    f"${delta:.2f} — visit Plans to upgrade.")
        if tier == 0:
            return PLAN_MSG + (" Paid plans (more classes, unlimited sections) are coming soon."
                               if not PAID_LIVE else "")
        return f"Your plan covers {tier_courses(tier)} classes — stop one below to switch."

    def _pricing_html(self, user):
        """The plan ladder (only rendered when PAID_LIVE).

        UPWARD ONLY. A student already on a plan sees the ones ABOVE theirs priced at the
        difference, their own marked as current, and the ones below marked as included —
        never as something to buy. Selling a smaller plan to someone who already holds a
        bigger one is charging them to lose something.

        What this page renders is presentation only; stripe_checkout_url re-derives the
        tier and the price server-side, so a hand-edited link cannot buy a downgrade or
        dodge the delta.
        """
        cur = effective_tier(user) if user else 0
        cards = []
        for t in (1, 2, 3):
            price = f"${TIER_PRICE_CENTS[t] / 100:.2f}"
            if not user:
                btn = "<a class='cbtn' href='/login'>Sign in to choose</a>"
                sub = "one-time, this term"
            elif t == cur:
                btn = ("<span class='note' style='display:block;font-weight:700;"
                       "color:#0F9D74'>Your current plan ✓</span>")
                sub = "one-time, this term"
            elif t < cur:
                # Already covered by what they hold. Not a product, not a button.
                btn = "<span class='note' style='display:block'>Included in your plan</span>"
                sub = "one-time, this term"
            else:
                delta = (TIER_PRICE_CENTS[t] - TIER_PRICE_CENTS.get(cur, 0)) / 100
                btn = (f"<a class='cbtn' href='/checkout?tier={t}'>"
                       + (f"Upgrade — ${delta:.2f}" if cur else f"Choose — {price}")
                       + "</a>")
                sub = (f"${delta:.2f} more than your plan" if cur else "one-time, this term")
            # The promo code only ever reaches the top plan at full price, so mentioning it
            # on an upgrade would be a promise the payment page cannot keep.
            note = ("<p class='note' style='margin:6px 0 0'>Have a promotional code? "
                    "Enter it on the payment page.</p>"
                    if (t == PROMO_TIER and not cur) else "")
            cards.append(f"<div class='price'><p class='amt'>{price} "
                         f"<small>{sub}</small></p>"
                         f"<p style='font-weight:700;margin:6px 0'>{html.escape(TIER_NAME[t])}</p>"
                         f"{btn}{note}</div>")
        head = ("Add more classes" if cur else "Watch more classes")
        lede = ("You're on the " + html.escape(TIER_NAME[cur]) + " plan. Moving up costs "
                "only the difference." if cur else
                "One-time for the term, no subscription. Pick the one that fits — your "
                "first class is always free.")
        return (f"<div class='card reveal d2'><h2 class='ct'>{head}</h2>"
                f"<p class='cs'>{lede}</p><div class='prices'>"
                + "".join(cards) + "</div>"
                "<a href='/' style='display:block;margin-top:16px;font-weight:700'>← Back</a></div>")

    def do_POST(self):
        path = urlparse(self.path).path
        if path == "/stripe/webhook":
            # verified-signature webhook is the ONLY thing that unlocks a paid tier.
            # No CSRF/session (Stripe calls it server-to-server); cap the body, verify HMAC.
            length = max(0, min(int(self.headers.get("Content-Length", 0) or 0), 65536))
            raw = self.rfile.read(length)
            event = stripe_verify_webhook(raw, self.headers.get("Stripe-Signature", ""))
            if event is None:
                return self._send_json({"ok": False}, 400)   # bad/forged signature
            try:
                stripe_apply_event(event)
            except Exception as e:
                sw.log(f"  [stripe] apply failed: {e}")
                return self._send_json({"ok": False}, 500)   # let Stripe retry
            return self._send_json({"ok": True})
        if path == "/sms/inbound":
            # Twilio calls this server-to-server for replies (STOP/HELP/YES). Authenticity
            # is the X-Twilio-Signature HMAC over url+params, checked with the auth token.
            # Gate on the TOKEN, not SMS_ENABLED: inbound texts work WITHOUT campaign
            # approval, so once Nathan sets TWILIO_AUTH_TOKEN we can validate a REAL
            # Twilio-signed request and close the signature gap before go-live. The outbound
            # TwiML reply stays gated behind SMS_LIVE, so this prep path records but sends
            # nothing.
            if not TWILIO_TOKEN:
                return self._send(page("<p>Not found.</p>"), 404)
            length = max(0, min(int(self.headers.get("Content-Length", 0) or 0), 8192))
            # keep_blank_values=True is REQUIRED here and is not a style choice. Twilio
            # signs over every parameter it sends, and for toll-free numbers it routinely
            # sends the geo fields (FromCity/FromState/FromZip/ToCity/ToState/ToZip) as
            # empty strings. parse_qs drops blanks by default, so our signed string omitted
            # those keys entirely while Twilio's included them -> different HMAC -> every
            # genuine inbound text failed with 403. That silently breaks STOP, which is how
            # a student revokes consent, so the opt-out would never be recorded and texts
            # would keep going. Do NOT copy this flag to the other parse_qs call sites:
            # /sms/optin checks `not oform.get("sms_consent")`, and keeping blanks there
            # would turn an empty sms_consent= into accepted consent.
            form = {k: v[0] for k, v in parse_qs(
                self.rfile.read(length).decode("utf-8", "replace"),
                keep_blank_values=True).items()}
            # self.path, not the parsed path: if the console URL carries a query string
            # Twilio signs over that too, and dropping it reproduces the same 403.
            cands = _twilio_candidate_urls(self.headers, self.path, BASE_URL)
            valid, matched = _twilio_verify_any(
                cands, form, self.headers.get("X-Twilio-Signature", ""))
            frm = form.get("From", "")
            sw.log(f"  [sms] inbound from {('*' * 6 + frm[-4:]) if frm else '?'} "
                   f"body={form.get('Body', '')!r} signature={'VALID' if valid else 'INVALID'}"
                   + (f" url={matched}" if valid else f" tried={cands}"))
            if not valid:
                # Log the candidates so a mismatch is diagnosable from the journal alone.
                # Never log the signature or the token.
                operator_alert(
                    "⚠️ Twilio inbound REJECTED (bad signature). A STOP reply may have "
                    "been dropped, which means someone who opted out can still be texted. "
                    f"Tried: {cands}. Check the webhook URL in the Twilio console matches "
                    "one of these exactly.")
                return self._send_json({"ok": False}, 403)
            reply = sms_apply_inbound(frm, form.get("Body", ""))
            # Emit an outbound reply only once SMS is fully live; during the pre-approval
            # signature test we validate + record (e.g. STOP revocation) and send nothing.
            msg = f"<Message>{html.escape(reply)}</Message>" if (reply and SMS_LIVE) else ""
            twiml = f"<?xml version='1.0' encoding='UTF-8'?><Response>{msg}</Response>"
            return self._send_bytes(twiml.encode(), "text/xml; charset=utf-8",
                                    cache="no-store")
        if path not in ("/watch", "/unwatch", "/push/subscribe", "/auth/apple",
                        "/sms/optin", "/feedback", "/notify-prefs"):
            return self._send(page("<p>Not found.</p>"), 404)

        # (1) rate limit FIRST — blocks form-flooding before any work is done
        rkey, rmax = self._rate_key()
        if not rate_ok(rkey, rmax):
            return self._notice("Too many requests, wait a minute and try again.", 429)

        try:
            length = int(self.headers.get("Content-Length", 0) or 0)
        except ValueError:
            length = 0
        length = max(0, min(length, 4096))  # cap body size; never read(-1) on a forged header
        raw_body = self.rfile.read(length).decode("utf-8", "replace")

        if path == "/auth/apple":           # Apple returns the signed-in user as a POST
            if not APPLE_ENABLED:
                return self._send(page("<p>Not found.</p>"), 404)
            aform = parse_qs(raw_body)
            state, code = aform.get("state", [""])[0], aform.get("code", [""])[0]
            want = self._cookie("sw_astate")
            clear = "sw_astate=; Path=/; Max-Age=0; HttpOnly; Secure; SameSite=None"
            if not (state and want and code) or not hmac.compare_digest(state, want):
                return self._send(form_page(
                    "<div class='ok'>Sign-in didn't complete, please try again.</div>"))
            info = apple_exchange(code)
            if not info:
                return self._send(form_page(
                    "<div class='ok'>Apple sign-in failed, please try again.</div>"))
            user = get_or_create_user(info["sub"], info["email"],
                                      ip=self._client_ip(), device_id=self._device_id(),
                                      source=self._cookie("sw_src"))
            return self._redirect("/", cookies=[session_cookie(user["id"]), clear])

        # (2) WHO IS THIS? Signed session cookie or nothing. Entitlements are
        # per-account — an anonymous POST can no longer create watches at all.
        user = self._user()

        if path == "/notify-prefs":
            if not user:
                return self._redirect("/login")
            nform = parse_qs(raw_body)
            if not hmac.compare_digest(nform.get("csrf", [""])[0], csrf_token(user["id"])):
                return self._notice("That form expired, please try again.", 403, user=user)
            want_email = bool(nform.get("notify_email"))
            # Someone with a consented number and every box cleared would be unreachable,
            # so text counts toward the floor for them. For anyone without a number it
            # cannot count, or they could switch off their only real channel and be stranded.
            with db() as c:
                has_sms = c.execute("SELECT 1 FROM sms_consent WHERE user_id=? AND "
                                    "confirmed_at IS NOT NULL AND revoked_at IS NULL LIMIT 1",
                                    (user["id"],)).fetchone() is not None
                cur_sms = bool(c.execute("SELECT notify_sms FROM users WHERE id=?",
                                         (user["id"],)).fetchone()["notify_sms"])
            # An UNCHECKED checkbox and a checkbox that was never on the page look identical
            # in a form post — both are simply absent. The SMS row is only rendered once
            # consent is confirmed, so reading "absent" as "turn texts off" lets a save from
            # a page that never offered the choice silently disable a channel the student
            # never touched. Today that self-heals, because confirming consent sets
            # notify_sms=1, which is the only reason it has never bitten. Depending on one
            # fix to cover another is not a guarantee. The form now states explicitly
            # whether it asked, and a form that did not ask cannot answer.
            # Three cases, not two. Collapsing the last two is the bug; collapsing the
            # FIRST two throws away an explicit request to switch texts ON.
            #   notify_sms present            -> the student asked for texts. Always honour.
            #   absent, but the form asked    -> they cleared the box. Off.
            #   absent, and the form never asked -> no decision was made. Leave it alone.
            if nform.get("notify_sms"):
                want_sms = True
            elif bool(nform.get("sms_offered")):
                want_sms = False
            else:
                want_sms = cur_sms
            # THE FLOOR, enforced here and not in the browser. An account with every
            # channel off is an account whose watches can never fire: the alert would be
            # generated, delivered nowhere, and nobody — including us — would be told the
            # student missed their seat. Unchecking both is refused outright rather than
            # accepted-and-ignored, so the saved state always matches what we will do.
            # Push used to satisfy this floor, which is precisely how an account ended up
            # "covered" by a channel that could not reach anyone. Only email and a
            # consented number count now.
            if not (want_email or (want_sms and has_sms)):
                return self._notice(
                    "Keep at least one alert method on. With both off we would have no way "
                    "to tell you a seat opened. To stop alerts entirely, remove the class "
                    "you are watching.", user=user)
            with db() as c:
                c.execute("UPDATE users SET notify_push=0, notify_email=?, notify_sms=? "
                          "WHERE id=?", (int(want_email), int(want_sms), user["id"]))
            on = " and ".join([x for x in ("email" if want_email else "",
                                           "text" if (want_sms and has_sms) else "") if x])
            return self._notice(f"Saved. We will alert you by {on}.", user=user)

        if path == "/feedback":
            if not user:
                return self._redirect("/login")
            fform = parse_qs(raw_body)
            if not hmac.compare_digest(fform.get("csrf", [""])[0], csrf_token(user["id"])):
                return self._notice("That form expired, please try again.", 403, user=user)
            msg = (fform.get("message", [""])[0] or "").strip()[:4000]
            if not msg:
                return self._notice("Please write a message first.", user=user)
            # PERSIST FIRST. Email is best-effort (and off entirely until SMTP is set up),
            # so the database is what guarantees a student's feedback is never lost.
            with db() as c:
                cur = c.execute("INSERT INTO feedback(user_id,email,message,created) "
                                "VALUES(?,?,?,?)",
                                (user["id"], user["email"], msg, time.time()))
                fid = cur.lastrowid
            sent = False
            if EMAIL_ENABLED:
                try:
                    sent = send_email(
                        SUPPORT_EMAIL, f"SeatWatch feedback #{fid} from {user['email']}",
                        f"From: {user['email']} (user {user['id']})\n\n{msg}",
                        BASE_URL or "https://seatwatchapp.com/")
                except Exception as e:
                    sw.log(f"  [feedback] email failed: {type(e).__name__}")
            if sent:
                with db() as c:
                    c.execute("UPDATE feedback SET emailed_at=? WHERE id=?", (time.time(), fid))
            else:
                # Not lost — just not delivered yet. Page the operator so it's not silent.
                sw.log(f"  [feedback] #{fid} stored but NOT emailed (EMAIL_ENABLED="
                       f"{EMAIL_ENABLED}) — read it from the feedback table")
            return self._notice("Thank you, that went straight to us. We read every message.",
                                user=user)

        if path == "/sms/optin":            # SINGLE web opt-in — the checked box IS consent
            if not user:
                return self._redirect("/login")
            oform = parse_qs(raw_body)
            if not hmac.compare_digest(oform.get("csrf", [""])[0], csrf_token(user["id"])):
                return self._notice("Session expired, please try again.", 403, user=user)
            # No tier check: text alerts are for everyone who consents. A phone number is
            # still never REQUIRED — push and email work without one — but a student who
            # gives us one gets the channel that actually wakes them at 2am.
            phone = _norm_phone(oform.get("phone", [""])[0])
            if not phone:
                return self._notice("That phone number doesn't look right, use a US "
                                    "10-digit mobile number.", 400, user=user)
            # Test the VALUE, not the key. `oform.get("sms_consent")` returns a list, so a
            # crafted `sms_consent=` would be ['']  -- truthy -- and read as consent the
            # moment anyone adds keep_blank_values here (as the Twilio parse now needs).
            # Today the blank is dropped so this is safe; this makes it safe by construction
            # rather than by a side effect of parsing. A consent record with no consent
            # behind it is the one TCPA record we can never defend.
            if not oform.get("sms_consent", [""])[0].strip():
                return self._notice("Please check the consent box to turn on text alerts.", 400,
                                    user=user)
            # Single web opt-in: checking the (unchecked-by-default) box and submitting IS
            # the consent, recorded CONFIRMED immediately — no reply required (a
            # confirmation TEXT can't honestly exist until the 10DLC campaign is approved).
            # We store exactly what they agreed to, when, from which IP, and the phone, as
            # durable proof a carrier can inspect on demand.
            now = time.time()
            with db() as c:
                c.execute("UPDATE sms_consent SET revoked_at=? WHERE user_id=? AND "
                          "revoked_at IS NULL AND phone!=?", (now, user["id"], phone))
                c.execute("INSERT INTO sms_consent(user_id,phone,wording,ip,requested_at,"
                          "confirmed_at) VALUES(?,?,?,?,?,?)",
                          (user["id"], phone, SMS_CONSENT_WORDING, self._client_ip(), now, now))
                # Handing over a number and ticking the box IS the preference. Without
                # this, a student who had once switched texts off would consent, receive a
                # sample promising alerts, and then never get one — the preference and the
                # consent silently disagreeing. Their most recent explicit act wins.
                c.execute("UPDATE users SET notify_sms=1 WHERE id=?", (user["id"],))
            # Also sample HERE, not only on watch creation. The two natural orders are
            # "give a number, then add a class" and "add a class, then notice the phone
            # option" — and the second is more common, because people arrive wanting to
            # watch something. Firing only on watch creation meant anyone who consented
            # second never saw what an alert looks like. Safe to call from both places:
            # sample_sms_at makes it once per ACCOUNT, so this can never double-send.
            send_sample_sms(user["id"])
            send_sample_email(user["id"])
            return self._notice(
                "You're opted in to text alerts. Check your phone — we just sent you an "
                "example of what an alert looks like. Reply STOP anytime to turn them off."
                if SMS_LIVE else
                "You're opted in — text alerts will begin as soon as our SMS service goes "
                "live. You can turn them off anytime by replying STOP once they start.",
                user=user)

        if path == "/push/subscribe":       # JSON body, JSON reply
            if not user:
                return self._send_json({"ok": False, "err": "auth"}, 401)
            try:
                body = json.loads(raw_body)
            except ValueError:
                return self._send_json({"ok": False, "err": "bad json"}, 400)
            if not hmac.compare_digest(str(body.get("csrf", "")), csrf_token(user["id"])):
                return self._send_json({"ok": False, "err": "csrf"}, 403)
            sub = body.get("sub") or {}
            endpoint = str(sub.get("endpoint", ""))
            keys = sub.get("keys") or {}
            p256dh, auth = str(keys.get("p256dh", "")), str(keys.get("auth", ""))
            if (not endpoint.startswith("https://") or len(endpoint) > 1000
                    or not (0 < len(p256dh) < 300) or not (0 < len(auth) < 300)):
                return self._send_json({"ok": False, "err": "bad sub"}, 400)
            with db() as c:   # endpoint UNIQUE -> re-subscribes just refresh the row
                prev = c.execute("SELECT user_id FROM push_subs WHERE endpoint=?",
                                 (endpoint,)).fetchone()
                if prev and prev["user_id"] != user["id"]:
                    # same physical device subscribed under a different account before —
                    # soft multi-account signal (shared/library machines exist; flag only)
                    c.execute("UPDATE users SET risk_score=risk_score+2 WHERE id=?",
                              (user["id"],))
                c.execute("INSERT INTO push_subs(user_id,endpoint,p256dh,auth,created) "
                          "VALUES(?,?,?,?,?) ON CONFLICT(endpoint) DO UPDATE SET "
                          "user_id=excluded.user_id, p256dh=excluded.p256dh, auth=excluded.auth",
                          (user["id"], endpoint, p256dh, auth, time.time()))
            sent = send_web_push(user["id"],
                                 "SeatWatch alerts are ON 🎉",
                                 "This is exactly how we'll buzz you the second a seat opens.",
                                 BASE_URL)
            if sent:
                # ledger the test push: durable proof this account has a WORKING
                # human-reaching channel (the confidence engine's W6 evidence)
                _log_alert({"id": None, "user_id": user["id"], "school": "",
                            "course": "", "section": ""}, "webpush_test")
            sw.log(f"  [push] user {user['id']} subscribed via {urlparse(endpoint).netloc} "
                   f"(test push confirmed to {sent} device)")
            return self._send_json({"ok": True, "test_sent": sent})

        form = parse_qs(raw_body)
        if not user:
            return self._notice("Please sign in first, it takes one click, no password.")
        if not hmac.compare_digest(form.get("csrf", [""])[0], csrf_token(user["id"])):
            return self._notice("That form expired, please try again.", 403, user=user)

        if path == "/unwatch":
            wid = form.get("id", ["0"])[0]
            if wid.isdigit():
                with db() as c:   # user_id in WHERE = can only delete YOUR OWN watch
                    c.execute("DELETE FROM watches WHERE id=? AND user_id=?",
                              (int(wid), user["id"]))
            return self._notice("Stopped. You can watch a different class now.", user=user)

        # the ONE hard abuse rule: a normalized email that already claimed its free
        # class on another account doesn't mint a fresh allotment (sign-in still works)
        if not user["free_eligible"]:
            return self._notice("Your free class is already in use on your other account, "
                                "sign in there to manage it.", user=user)

        school = schools.SCHOOLS.get(form.get("school", [""])[0].strip())
        if not school:
            return self._notice("Please choose a valid school.", 400, user=user)
        # Enforced HERE, not just by leaving it out of the picker: the picker is a JSON
        # blob in the page, and anyone who can craft a POST can name a school that is not
        # in it. A watch on a school whose last probe failed is a watch that can only ever
        # produce silence — the student would wait all term for an alert that cannot come.
        # Say so plainly instead, and never create the row.
        if not school_listed(school.id):
            return self._notice(
                f"We can't read {school.name}'s seat data right now, so we can't watch a "
                "class there yet — and we'd rather tell you than take the request and go "
                "quiet. We're working on it. Email support@seatwatchapp.com and we'll let "
                "you know the moment it works.", 400, user=user)
        course = form.get("course", [""])[0].strip().upper()

        # Optional phone + consent, collected INSIDE this form so it sits in the path a
        # student already walks instead of in a card below it. Recorded BEFORE the watch is
        # created, so the sample text can fire on this same request with a valid number.
        #
        # A number WITHOUT a ticked box is refused outright, never quietly stored: it is
        # the one case where guessing costs $500-$1500 a message. Refusing is also the
        # honest reading — somebody who typed a number and left the box alone has not
        # agreed to anything, and silently dropping the number would leave them expecting
        # texts that never come.
        inline_phone = _norm_phone(form.get("phone", [""])[0])
        inline_consent = bool(form.get("sms_consent", [""])[0].strip())
        if form.get("phone", [""])[0].strip() and not inline_phone:
            return self._notice("That phone number doesn't look right — use a US 10-digit "
                                "mobile number, or leave it blank.", 400, user=user)
        if inline_phone and not inline_consent:
            return self._notice("Please tick the consent box if you'd like text alerts, or "
                                "clear the phone number. We can't text you without it.",
                                400, user=user)
        if inline_phone and inline_consent:
            now_ts = time.time()
            with db() as c:
                already = c.execute("SELECT 1 FROM sms_consent WHERE user_id=? AND "
                                    "confirmed_at IS NOT NULL AND revoked_at IS NULL LIMIT 1",
                                    (user["id"],)).fetchone()
                if not already:
                    c.execute("UPDATE sms_consent SET revoked_at=? WHERE user_id=? AND "
                              "revoked_at IS NULL AND phone!=?",
                              (now_ts, user["id"], inline_phone))
                    c.execute("INSERT INTO sms_consent(user_id,phone,wording,ip,requested_at,"
                              "confirmed_at) VALUES(?,?,?,?,?,?)",
                              (user["id"], inline_phone, SMS_CONSENT_WORDING,
                               self._client_ip(), now_ts, now_ts))
                    c.execute("UPDATE users SET notify_sms=1 WHERE id=?", (user["id"],))
            # Sample HERE, right after consent lands, not only after the watch succeeds.
            # The watch can still be rejected below — a mistyped course code, a plan limit —
            # and a student who just handed over their number and ticked a box should not be
            # punished for that with silence. Once per account, so this cannot double-send.
            send_sample_sms(user["id"])
            send_sample_email(user["id"])

        tier = effective_tier(user)             # 0 = free (also the state when paid is off)
        # all_sections is decided BELOW, once we know whether the student named any —
        # a paid plan lets you watch every section, it does not oblige you to.
        max_courses = tier_courses(tier)

        raw = form.get("sections", [""])[0]
        # dict.fromkeys dedupes ("0101, 0101" would otherwise double-alert)
        sections = list(dict.fromkeys(s.strip().upper() for s in raw.split(",") if s.strip()))
        # THE STUDENT'S CHOICE WINS. This used to be `tier >= 1`, so a paid account had its
        # typed sections thrown away and every section of the course watched instead. Nathan
        # entered 0101 and was alerted about the whole course — which is worse than noise:
        # a text saying a seat opened in a section he cannot take teaches him to ignore the
        # next one, and the next one is the real seat. "Unlimited sections" is a capability,
        # not an obligation. Name sections and we watch exactly those; leave it blank and
        # a paid plan watches them all.
        all_sections = tier >= 1 and not sections
        if not all_sections:
            if not sections:
                return self._notice("Please add the section number(s) you want to watch, e.g. 0101.",
                                    user=user)
            if tier == 0 and len(sections) > FREE_SECTIONS_PER_COURSE:
                _conv_signal("wall_hit", user["id"])   # tried >2 sections on free
                return self._notice(
                    f"Your free plan watches up to {FREE_SECTIONS_PER_COURSE} sections of "
                    f"1 class. A seat in the others won't alert you — the paid plans watch "
                    f"unlimited sections." + (" (Coming soon.)" if not PAID_LIVE else ""),
                    user=user)

        # (3) per-school FORMAT validation — no junk reaches a fetch
        if not school.valid_course(course):
            return self._notice(f"That doesn't look like a {school.name} course code "
                                f"(e.g. {school.example}).", user=user)
        for s in sections:
            if s and not SECTION_RE.match(s):
                return self._notice(f"Invalid section: {s}", 400, user=user)

        # (3.5) cheap COURSE-COUNT pre-check BEFORE the network fetch, so a limit-hit user
        # can't make us hammer school sites (authoritative re-check happens under the lock)
        with db() as c:
            pre = {(r["school"], r["course"]) for r in c.execute(
                "SELECT school,course FROM watches WHERE user_id=?", (user["id"],))}
        if (school.id, course) not in pre and len(pre) >= max_courses:
            if tier == 0:
                _conv_signal("simultaneous_course_need", user["id"])   # wants >1 class
            return self._notice(self._plan_upsell(tier), user=user)

        # (4) validate it ACTUALLY EXISTS — blocks fake-course flooding. Drop the "none"
        # sentinel some catalog adapters (ListcrseBanner8) return for a nonexistent course:
        # to run_cycle's health guard it correctly means "fetch succeeded, no sections" (so
        # it must stay in fetch()), but HERE it means "no such course" — without dropping it,
        # an all-sections watch on a typo'd code would slip past this check as a phantom.
        secs = {k: v for k, v in school.fetch({course}).get(course, {}).items() if k != "none"}
        if not secs:
            return self._notice(f"Couldn't find {course} at {school.name} this term, check the code?",
                                user=user)
        bad = [s for s in sections if s and s not in secs]
        if bad:
            return self._notice(
                f"{course} has no section(s): {', '.join(bad)}. "
                f"Real ones include: {', '.join(sorted(secs)[:8])}…", user=user)

        # (5) ENTITLEMENT — enforced per ACCOUNT, under a lock so two parallel
        # submissions can't both slip past the count check.
        with _WLOCK:
            with db() as c:
                mine = c.execute("SELECT school,course,section FROM watches WHERE user_id=?",
                                 (user["id"],)).fetchall()
            my_courses = {(r["school"], r["course"]) for r in mine}
            key = (school.id, course)
            if key not in my_courses and len(my_courses) >= max_courses:
                return self._notice(self._plan_upsell(tier), user=user)
            have = {r["section"] for r in mine if (r["school"], r["course"]) == key}

            if all_sections:
                # paid: ONE row with section="" watches EVERY section (the engine alerts
                # on any open section, reading the fully-paginated fetch). Idempotent.
                if "" in have:
                    return self._notice("You're already watching unlimited sections of this class.",
                                        user=user)
                with db() as c:
                    c.execute("DELETE FROM watches WHERE user_id=? AND school=? AND course=?",
                              (user["id"], school.id, course))   # collapse any old picks
                    c.execute("INSERT INTO watches(school,topic,course,section,term,created,user_id) "
                              "VALUES(?,?,?,?,?,?,?)",
                              (school.id, user["topic"], course, "",
                               stamp_term(school), time.time(), user["id"]))
                what = course + " (unlimited sections)"
            else:
                if "" in have:
                    # They previously watched EVERY section and have now named specific
                    # ones: that is a deliberate narrowing, so the catch-all row has to go
                    # or it would keep alerting on the sections they just excluded.
                    with db() as c:
                        c.execute("DELETE FROM watches WHERE user_id=? AND school=? AND "
                                  "course=? AND section=''", (user["id"], school.id, course))
                    have.discard("")
                new = [s for s in sections if s not in have]
                if not new:
                    return self._notice("You're already watching those sections.", user=user)
                # TIER-AWARE, and it was not. The check above already lets a paid student
                # name as many sections as they like; this one — on the insert path —
                # still applied the FREE cap of 2, so a customer on the 5-course plan was
                # told about "your free plan" while the note under the same form correctly
                # described their paid one. Being refused something you have just paid for,
                # by a message calling you a free user, is the worst version of a bug.
                cap = FREE_SECTIONS_PER_COURSE if tier == 0 else PAID_MAX_SECTIONS
                if len(have) + len(new) > cap:
                    if tier == 0:
                        _conv_signal("wall_hit", user["id"])
                        return self._notice(
                            f"Your free plan watches {FREE_SECTIONS_PER_COURSE} sections of "
                            f"one class" + (f", and you're already watching {len(have)} of "
                            f"this one" if have else "") + ". Stop one below, or a paid plan "
                            f"watches every section." + (" (Coming soon.)" if not PAID_LIVE else ""),
                            user=user)
                    return self._notice(
                        f"That's more than {cap} sections of one class — leave the section "
                        f"box blank and your plan watches every section instead.", user=user)
                with db() as c:
                    for sec in new:
                        c.execute("INSERT INTO watches(school,topic,course,section,term,created,user_id) "
                                  "VALUES(?,?,?,?,?,?,?)",
                                  (school.id, user["topic"], course, sec,
                                   stamp_term(school), time.time(), user["id"]))
                what = course + " " + ", ".join(new)
        # They have just told us the class they are stuck on. If they gave us a consented
        # number, show them RIGHT NOW what the alert will look like — the single best
        # moment to demonstrate the product is the moment they start needing it. Once per
        # account, never per watch, and it can never break watch creation.
        send_sample_sms(user["id"])
        send_sample_email(user["id"])
        # Same treatment for the success page: a student who presses Back after adding a
        # class must not be asked to resubmit the thing that added it.
        self.send_response(303)
        self.send_header("Location", "/")
        self.send_header("Set-Cookie", self._flash_set("done", 200, f"{what} @ {school.name}"))
        self.send_header("Content-Length", "0")
        self.end_headers()
        return

    def log_message(self, *a):  # quiet
        pass


# ----------------------------------------------------------------- health guard
health = {}            # course -> {fails, alerted, last_count}  (in-memory)
_stale_logged = set()  # (school, watch_term, cur_term) already reported — log once, not per cycle

# --- fake-all-open watchdog (accuracy backstop for the never-false-alert promise) ---
# The one way a school could false-alert is a STATUS-ONLY guest view that reports every
# section "open" even when it's full (the classic-PeopleSoft trap). Numeric-seat schools
# are immune — the count is real — so we only watch status-only schools (every section
# reports seats=None). A real status-only school shows closed sections routinely
# (watched courses skew full); a faking one never does. If such a school accumulates a
# large sample and has NEVER shown a single closed section, page the operator to re-run
# the completed-term test. Page-ONLY: this never pauses a school or changes any alert,
# so a heuristic false-positive can't silence a real school — it just prompts a human check.
_ALLOPEN = {}          # school_id -> {"n": int, "closed": int, "flagged": bool}
_ALLOPEN_MIN = 400     # sections observed before an all-open school is suspicious

# --- opening confirmation (a CORRECT alert nobody can act on is still a bad alert) ---
# Measured on the live UMD watches, 2026-08: 18 real openings, median life 35 SECONDS.
# 14 of the 18 were gone inside two minutes; the other 4 stayed open about an HOUR.
# NOTHING at all landed between 94 seconds and 58 minutes — the distribution is bimodal,
# blip or genuine. A student needs 2-5 minutes to read the mail, open the portal, log in
# and register, so a sub-minute seat is a promise we cannot keep, and eight of them in an
# hour (watch 27, CMSC216 0102) is how somebody learns to ignore SeatWatch before the
# opening that would have worked.
#
# The first build of this gated on churn HISTORY — alert instantly, then require proof
# only from sections that had already flickered. Replaying the true production timeline
# killed it: every parameterisation removed exactly ONE of eight emails, because the
# blips that reach a student are each the FIRST on their section inside a cooldown
# window, and history cannot catch a first occurrence.
#
# The same replay found the thing that actually matters: blips were not merely noise,
# they were CROWDING OUT real seats. A 23-second blip fired, spent the 30-minute repeat
# cooldown, and when the 58-minute opening arrived there was no budget left — so only
# 2 of the 4 genuine openings ever reached anybody. Confirming EVERY opening takes that
# timeline from 8 emails to 4 while raising real seats delivered from 2 to 4: strictly
# fewer alerts and strictly more seats, which is why this overrides the "never delay the
# first alert" instinct the earlier design was built around.
#
# The cost is bounded and paid only by seats with runway to spare — 2 minutes out of a
# 58-102 minute window — and a seat too short to confirm is one the student could never
# have reached. Caveat kept in the open: 18 openings, ONE school, one add/drop period.
# CONFIRM_SECONDS=0 disables this entirely and restores the previous behavior exactly.
CONFIRM_SECONDS = int(os.environ.get("CONFIRM_SECONDS", "120"))   # 0 = off
_OPEN_SINCE = {}       # "school:course:section" -> ts of the rising edge; absent = shut
_OPEN_SINCE_MAX = 20000
_now = time.time       # indirection so tests can drive the clock


def _confirm_hold(key, is_open, now=None):
    """Track one section's open/shut edges; return (hold, open_for).

    hold=True means the seat is real but has not yet proven it will still be there when
    a human actually arrives. Only currently-open sections are retained, so the table
    stays the size of "sections open right now", not "sections ever seen".

    Safe to call once per WATCH though it is keyed per SECTION: two students on the same
    section make two identical calls per cycle, and only edges mutate state.
    """
    now = _now() if now is None else now
    if not is_open:
        _OPEN_SINCE.pop(key, None)         # falling edge — re-arm
        return False, 0.0
    if len(_OPEN_SINCE) > _OPEN_SINCE_MAX:
        # Fail OPEN, never closed. Clearing the table here instead would reset every
        # in-flight timer on every call, so nothing could ever reach CONFIRM_SECONDS and
        # the product would go permanently silent — the one failure worse than noise.
        return False, 0.0
    open_for = now - _OPEN_SINCE.setdefault(key, now)
    return (CONFIRM_SECONDS > 0 and open_for < CONFIRM_SECONDS), open_for

# The daily-summary and weekly-drill timers are PERSISTED to a small state file so
# they survive restarts. Without this, every restart reset them to 0 and re-fired both
# operator alerts immediately — so a day of frequent redeploys spammed the operator with
# duplicate "drill PASSED" / "daily check" texts. Persisting means they truly fire on
# their real schedule (daily / weekly) regardless of how often the service restarts.
STATE_PATH = os.environ.get("SEATWATCH_STATE", DB + ".state.json")


def _load_state():
    try:
        with open(STATE_PATH) as f:
            return json.load(f)
    except Exception:
        return {}


def _save_state(**kv):
    """Atomically merge keys into the state file. Best-effort — never raises."""
    try:
        cur = _load_state()
        cur.update(kv)
        tmp = STATE_PATH + ".tmp"
        with open(tmp, "w") as f:
            json.dump(cur, f)
        os.replace(tmp, STATE_PATH)
    except Exception:
        pass


_st = _load_state()
_last_summary = [float(_st.get("last_summary", 0.0))]  # persisted daily-summary timestamp
_last_drill = [float(_st.get("last_drill", 0.0))]      # persisted fire-drill timestamp


ADMIN_USER_ID = int(os.environ.get("SEATWATCH_ADMIN_USER", "0") or 0)
# One operator email per distinct problem per half hour. Long enough that an
# escalating outage is one message, short enough that a NEW problem is not muted
# behind an old one — the keys are per-message, so they damp independently.
OPERATOR_MAIL_COOLDOWN_S = int(os.environ.get("OPERATOR_MAIL_COOLDOWN_S", "1800"))
# A problem does not become more informative by being repeated. The FIRST report of an
# outage is urgent; the ninety-sixth report of the same unchanged outage is noise that
# trains you to ignore the channel — which is how a real one gets missed. So the gap
# doubles each time a condition keeps firing, up to a daily floor: loud when new, quiet
# when chronic, never actually silent. Towson was mailing every 30 minutes for 19 days.
OPERATOR_MAIL_MAX_COOLDOWN_S = int(os.environ.get("OPERATOR_MAIL_MAX_COOLDOWN_S", "86400"))
# If a condition stops recurring for this long it is treated as over, and the next
# occurrence is loud again. Without this a school that broke in August would still be
# on a 24-hour backoff in December, and its next outage would be reported a day late.
OPERATOR_MAIL_RESET_S = int(os.environ.get("OPERATOR_MAIL_RESET_S", "3600"))




def operator_alert(message):
    """Ping YOU (the operator) when something needs a human. Never goes to users.

    EMAIL is the channel that actually arrives. Web push and ntfy are kept as extras,
    but neither is trusted on its own — that is not a guess, it is the documented cause
    of a real miss: on 2026-08-02 USF went dark for 1h48m across 272 consecutive failed
    fetches with two live watches on it. The guard worked perfectly, the page fired five
    seconds after the fifth failure, and the operator alert went to web push and ntfy —
    where nobody was looking. It surfaced two days later only because a scheduled
    checkpoint happened to read the incidents table.

    That is the same failure students had until today: a channel that reports success
    while reaching no one. It was worth fixing for them; it is worth fixing here, because
    an operator who is not told cannot fix anything, and every guard in this system
    ultimately terminates in a human being informed.

    Mail is damped on the message with its NUMBERS STRIPPED, so an escalating outage
    ("5 consecutive", "6 consecutive", "7 consecutive"...) is one email rather than one
    every twenty seconds. Guardian dampens its own pages, but run_cycle calls this
    directly too, and a bad hour there would otherwise mail hundreds of times.

    Never raises: an operator alert that breaks the poller would take down alerting for
    every student to report a problem with one school.
    """
    if ADMIN_USER_ID:
        try:
            send_web_push(ADMIN_USER_ID, "SeatWatch health", message, BASE_URL)
        except Exception:
            pass
    sw.notify("SeatWatch health", message, topic=OPERATOR_TOPIC)
    sw.log("  [OPERATOR ALERT] " + message)
    try:
        if not (EMAIL_ENABLED and ADMIN_USER_ID):
            return
        key = re.sub(r"\d+", "#", message)[:120]
        now = _now()
        with db() as c:
            prev = c.execute("SELECT last_sent,last_seen,streak FROM operator_mail "
                             "WHERE key=?", (key,)).fetchone()
            if prev and now - prev["last_seen"] > OPERATOR_MAIL_RESET_S:
                prev = None                      # went quiet; treat the next one as new
            streak = prev["streak"] if prev else 0
            wait = min(OPERATOR_MAIL_COOLDOWN_S * (2 ** max(0, streak - 1)),
                       OPERATOR_MAIL_MAX_COOLDOWN_S) if streak else 0
            # last_seen is stamped on every occurrence, mailed or not — it is what tells
            # a chronic condition apart from one that stopped and came back.
            c.execute("INSERT INTO operator_mail(key,last_sent,last_seen,streak) "
                      "VALUES(?,0,?,0) ON CONFLICT(key) DO UPDATE SET last_seen=?",
                      (key, now, now))
            if prev and now - prev["last_sent"] < wait:
                return
        with db() as c:
            row = c.execute("SELECT email FROM users WHERE id=?", (ADMIN_USER_ID,)).fetchone()
        if not (row and row["email"]):
            return
        # Stamp only on SUCCESS. Stamping the attempt would let one SMTP hiccup silence
        # this problem for the whole cooldown — the same mistake the student notifier
        # makes if you are not careful, and the cost here is an operator never learning
        # a school went dark.
        if send_email(row["email"], "SeatWatch: something needs you",
                      message + "\n\nThis is an operator alert — students were not "
                                "contacted.\n\n— SeatWatch health", BASE_URL):
            # Stamped only on SUCCESS, and the streak advances only when mail actually
            # went out, so a failing SMTP cannot silently escalate you into a 24-hour gap.
            with db() as c:
                c.execute("UPDATE operator_mail SET last_sent=?, streak=streak+1 "
                          "WHERE key=?", (now, key))
    except Exception as e:
        sw.log(f"  [OPERATOR ALERT] could not email: {type(e).__name__}")


def ping_healthcheck():
    """Optional dead-man's switch: if these pings stop, healthchecks.io emails you."""
    if not HEALTHCHECK_URL:
        return
    try:
        urllib.request.urlopen(HEALTHCHECK_URL, timeout=10)
    except Exception:
        pass


def maybe_daily_summary():
    now = time.time()
    if now - _last_summary[0] < SUMMARY_EVERY_HOURS * 3600:
        return
    _last_summary[0] = now
    _save_state(last_summary=now)
    with db() as c:
        n_watches = c.execute("SELECT COUNT(*) FROM watches").fetchone()[0]
        n_users = c.execute("SELECT COUNT(DISTINCT topic) FROM watches").fetchone()[0]
    broken = [crs for crs, h in health.items() if h.get("alerted")]
    gline = guardian.summary_line()
    try:
        quiet = not broken and not guardian.summary_needs_attention()
    except Exception:
        quiet = False          # cannot tell whether anything is wrong -> say something
    if quiet:
        # SILENT WHEN CLEAN. A daily "all healthy ✅" is a mail that, by definition, never
        # needs opening — and its real cost is that it trains the reader to archive
        # SeatWatch mail unread, including the one that matters. The healthy state is still
        # recorded in the log and is available on demand from ops/triage.py, which answers
        # the same question without arriving uninvited.
        sw.log(f"  [daily] watching {n_watches} class(es) for {n_users} user(s). "
               f"all healthy — not mailed" + (f" — {gline}" if gline else ""))
        return
    status = "NEEDS ATTENTION ⚠️: " + (", ".join(broken) if broken else "see Guardian")
    operator_alert(f"Daily check — watching {n_watches} class(es) for {n_users} user(s). "
                   f"{status}" + (f" — {gline}" if gline else ""))


def run_fire_drill():
    """Weekly automated end-to-end proof of the whole money path: for a real school,
    fetch LIVE data → find a genuinely open section → deliver a real alert → confirm it
    was accepted. Pages the operator on PASS (reassurance) and, loudly, on total FAILURE.
    Self-contained: uses a dedicated drill topic, never touches user watches."""
    now = time.time()
    if now - _last_drill[0] < DRILL_EVERY_HOURS * 3600:
        return
    _last_drill[0] = now
    _save_state(last_drill=now)
    tested = []
    # Rotate the starting school each week so the drill proves a DIFFERENT school over time
    # (it still returns on the first that passes — this just varies which one that is, so the
    # operator sees variety instead of the same school every week).
    wk = int(now // (7 * 86400))
    rot = DRILL_SCHOOLS[wk % len(DRILL_SCHOOLS):] + DRILL_SCHOOLS[:wk % len(DRILL_SCHOOLS)]
    for sid in rot:
        s = schools.SCHOOLS.get(sid)
        if not s:
            continue
        try:
            data = s.fetch({s.example}).get(s.example, {})
        except Exception as e:
            tested.append(f"{sid}:crash({type(e).__name__})")
            continue
        if not data:
            tested.append(f"{sid}:no-data")
            continue
        # data-sanity: seat counts must be clean ints and open must match seats>0
        if any(not isinstance(i.get("seats"), int) or i["seats"] < 0
               or i["open"] != (i["seats"] > 0) for i in data.values()):
            tested.append(f"{sid}:INSANE-DATA")
            continue
        openish = [(n, i) for n, i in data.items() if i["open"] and i["seats"] > 0]
        if not openish:
            tested.append(f"{sid}:{len(data)}secs-none-open")
            continue
        n, info = openish[0]
        ok = sw.notify("SeatWatch self-test",
                       f"[DRILL] {s.example}-{n}: {info['seats']} live seats — full "
                       "detect+deliver path verified.",
                       topic="seatwatch-drill-selftest")
        if ok:
            operator_alert(f"Weekly fire drill PASSED ✅ — {s.name} {s.example}-{n} "
                           f"({info['seats']} seats) fetched live AND alert delivered. "
                           "The full pipeline works.")
            return
        tested.append(f"{sid}:notify-FAILED")
    operator_alert("🚨 Weekly fire drill FAILED — NO school completed detect+deliver. "
                   "The alert pipeline may be broken; investigate now. Tried: "
                   + "; ".join(tested))


# ------------------------------------------------------------------------ poller
def _school_fetch(school_id, items):
    """Network I/O for one school. Never raises — returns {} so the guard handles it."""
    school = schools.SCHOOLS.get(school_id)
    if not school:
        return school_id, {}, 0
    t0 = time.time()
    try:
        return (school_id, school.fetch({r["course"] for r in items}),
                int((time.time() - t0) * 1000))
    except Exception as e:
        sw.log(f"  [warn] {school_id} fetch crashed (treated as no-data): {e}")
        return school_id, {}, int((time.time() - t0) * 1000)


def run_cycle():
    with db() as c:
        rows = c.execute("SELECT * FROM watches").fetchall()
    cyc = guardian.begin_cycle(rows)   # expected-identity snapshot; every watch below
    by_school = {}                     # must end the cycle with a terminal outcome
    for r in rows:
        by_school.setdefault(r["school"], []).append(r)
    if not by_school:
        guardian.finalize(cyc)
        return cyc

    # Fetch every school CONCURRENTLY so cycle time stays flat as schools scale
    # (sequential would grow linearly). Alert logic below stays sequential + safe.
    data_by_school, fetch_ms = {}, {}
    with ThreadPoolExecutor(max_workers=min(12, len(by_school))) as ex:
        for school_id, data, ms in ex.map(lambda kv: _school_fetch(*kv), by_school.items()):
            data_by_school[school_id] = data
            fetch_ms[school_id] = ms

    cur_terms, fetched_at = {}, {}     # per-school context the alert gate re-checks
    for school_id, items in by_school.items():
        school = schools.SCHOOLS.get(school_id)
        if not school:
            for r in items:            # registry no longer knows this school: the watch
                guardian.record(cyc, r["id"], "school_missing")   # must not vanish silently
            continue
        data = data_by_school.get(school_id, {})  # {course: {section: {open(bool), seats}}}
        guardian.note_fetch(cyc, school_id, bool(data), fetch_ms.get(school_id, 0), data)
        fetched_at[school_id] = guardian.now()
        cur_term = (school.cur_term() if callable(getattr(school, "cur_term", None))
                    else getattr(school, "term", None))
        cur_terms[school_id] = cur_term

        for r in items:
            course = r["course"]
            # A watch is bound to the term it was created in, but the fetch above always
            # returns the school's CURRENT term. Once a school rolls semesters, a leftover
            # watch would be matched against a same-numbered section in the NEW term and
            # fire "a seat opened in CMSC216-0101" for a semester the student never signed
            # up for — a FALSE ALERT, the one thing we must never do. Skip it.
            # Only on a DEFINITE mismatch: if either term is unknown we cannot prove
            # staleness, and skipping would silently kill a working watch.
            if r["term"] and cur_term and r["term"] != cur_term:
                guardian.record(cyc, r["id"], "blocked_wrong_term",
                                adapter_term=cur_term, watch_term=r["term"])
                # Tell the STUDENT, not just the operator. Skipping this watch is right,
                # but doing it silently means someone who set a watch in August simply
                # never hears from us again and concludes their class never opened.
                notify_stranded(r, school, cur_term)
                k = (school_id, r["term"], cur_term)
                if k not in _stale_logged:
                    _stale_logged.add(k)
                    sw.log(f"  [term] {school_id}: watches created for term {r['term']} are "
                           f"stale (school now on {cur_term}) — they will NOT alert. "
                           f"Students must re-create them for the new term.")
                    guardian.page(f"term_stale:{school_id}",
                                  f"⚠️ {school.name}: watches from term {r['term']} are "
                                  f"STRANDED (school rolled to {cur_term}). They will not "
                                  "alert until the student re-creates them.")
                continue
            hkey = f"{school_id}:{course}"
            h = health.setdefault(hkey, {"fails": 0, "alerted": False, "last_count": 0})
            secs = data.get(course)

            # GUARD — course returned no data (fetch failed / format changed / blocked)
            if not secs:
                h["fails"] += 1
                if h["fails"] >= FAIL_THRESHOLD and not h.get("down_since"):
                    h["down_since"] = time.time()      # pause starts NOW; mail waits
                # The PAUSE is immediate at FAIL_THRESHOLD — that is correctness and has
                # not changed; no false alert can escape while a school is unreadable.
                # The EMAIL waits for OUTAGE_CONFIRM_S, because a page a human cannot act
                # on is not a page. Every operator mail Nathan received this week was a
                # school that came back on its own: MUSC204 down and "recovered ✅" 24
                # SECONDS later, Towson ENGL102 twice the same day. Two mails each, for an
                # outage that resolved before either could be read. Same lesson as the seat
                # alerts one screen up — make it prove it is real before you shout.
                if (h.get("down_since") and not h["alerted"]
                        and time.time() - h["down_since"] >= OUTAGE_CONFIRM_S):
                    mins = int((time.time() - h["down_since"]) / 60)
                    operator_alert(f"{school.name} {course}: no data for {mins} min "
                                   f"({h['fails']}x in a row) — possible block or format "
                                   "change. Paused (NO false alerts go out). I'll report "
                                   "when it recovers.")
                    h["alerted"] = True
                guardian.record(cyc, r["id"], "adapter_failed",
                                fails=h["fails"], adapter_term=cur_term)
                continue

            # "Recovered" is only worth an email if we actually mailed about the outage.
            # Sending it after a blip we deliberately stayed quiet about would reintroduce
            # exactly the noise this removes — and would be the more confusing half, since
            # it reports the end of something the reader never heard had begun.
            if h["alerted"]:
                operator_alert(f"{school.name} {course}: recovered ✅")
            h.update(fails=0, alerted=False, down_since=0, last_count=len(secs))

            # fake-all-open watchdog — count real sections at STATUS-ONLY schools only
            # (exclude the "none" not-offered sentinel; numeric-seat schools are immune).
            real_secs = [i for n, i in secs.items() if n != "none"]
            if real_secs and all(i.get("seats") is None for i in real_secs):
                w = _ALLOPEN.setdefault(school_id, {"n": 0, "closed": 0, "flagged": False})
                w["n"] += len(real_secs)
                w["closed"] += sum(1 for i in real_secs if not i["open"])
                if not w["flagged"] and w["n"] >= _ALLOPEN_MIN and w["closed"] == 0:
                    operator_alert(f"⚠️ {school.name}: {w['n']} sections observed, NONE ever "
                                   "closed — possible FAKE all-open status. Re-run the "
                                   "completed-term test; pause this school if its guest view "
                                   "fakes 'open' (false-alert risk).")
                    w["flagged"] = True

            url = school.reg_url(course)
            want = r["section"]
            if want == "":                  # watching ALL sections of the course
                open_secs = [n for n, i in secs.items() if i["open"]]
                hold, open_for = _confirm_hold(f"{school_id}:{course}:*", bool(open_secs))
                if open_secs and not r["alerted"] and hold:
                    # real, but not yet proven to still be there when a human arrives
                    guardian.record(cyc, r["id"], "checked_unconfirmed",
                                    adapter_term=cur_term, sections=len(open_secs),
                                    open_for=round(open_for))
                elif open_secs and not r["alerted"]:
                    guardian.queue_alert(cyc, r, f"Open in {course}: "
                                         f"{', '.join(sorted(open_secs))}", url,
                                         sections=open_secs)
                elif not open_secs and r["alerted"]:
                    _set_alerted(r["id"], 0)
                    guardian.record(cyc, r["id"], "checked_closed_reset",
                                    adapter_term=cur_term)
                elif open_secs:
                    guardian.record(cyc, r["id"], "checked_open_already",
                                    adapter_term=cur_term)
                else:
                    guardian.record(cyc, r["id"], "checked_no_change",
                                    adapter_term=cur_term)
            else:
                info = secs.get(want)
                if not info:
                    # the COURSE answered but this SECTION vanished from it — a silent
                    # miss in progress (renumbered/collapsed/filtered); count it.
                    guardian.record(cyc, r["id"], "section_missing",
                                    adapter_term=cur_term, sections_seen=len(secs))
                    continue
                hold, open_for = _confirm_hold(f"{school_id}:{course}:{want}", info["open"])
                if info["open"] and not r["alerted"] and hold:
                    # A real seat that has not yet proven it will outlive the walk from
                    # inbox to registration page. Hold rather than send someone to a
                    # section that will be full again before the portal finishes loading.
                    guardian.record(cyc, r["id"], "checked_unconfirmed",
                                    adapter_term=cur_term, seats=info.get("seats"),
                                    open_for=round(open_for))
                elif info["open"] and not r["alerted"]:
                    seats = info.get("seats")
                    msg = (f"{seats} seat(s) open in {course}-{want}!" if seats
                           else f"A seat opened in {course} section {want}!")
                    guardian.queue_alert(cyc, r, msg, url)
                elif not info["open"] and r["alerted"]:
                    _set_alerted(r["id"], 0)
                    guardian.record(cyc, r["id"], "checked_closed_reset",
                                    adapter_term=cur_term, seats=info.get("seats"))
                elif info["open"]:
                    guardian.record(cyc, r["id"], "checked_open_already",
                                    adapter_term=cur_term, seats=info.get("seats"))
                else:
                    guardian.record(cyc, r["id"], "checked_no_change",
                                    adapter_term=cur_term, seats=info.get("seats"))

    # Deliver queued alerts through the safety gate + mass-transition tripwire,
    # then reconcile: every expected watch must now hold a terminal outcome.
    # off/shadow: sends are exactly what the legacy inline path produced.
    guardian.flush_alerts(cyc, _alert, _set_alerted, cur_terms, fetched_at)
    guardian.finalize(cyc)
    return cyc


def send_web_push(user_id, title, body, url):
    """Web Push to every device this account enabled. Returns # delivered.
    Dead subscriptions (404/410 = user revoked/uninstalled) are pruned so we
    never keep 'delivering' into the void."""
    if not PUSH_ENABLED or not user_id:
        return 0
    with db() as c:
        subs = c.execute("SELECT * FROM push_subs WHERE user_id=?", (user_id,)).fetchall()
    sent = 0
    for s0 in subs:
        info = {"endpoint": s0["endpoint"],
                "keys": {"p256dh": s0["p256dh"], "auth": s0["auth"]}}
        host = urlparse(s0["endpoint"]).netloc          # which push service (FCM/Apple/Mozilla)
        try:
            webpush(subscription_info=info,
                    data=json.dumps({"title": title, "body": body, "url": url}),
                    vapid_private_key=VAPID_PRIVATE_PEM,
                    vapid_claims={"sub": VAPID_SUBJECT},   # fresh dict: pywebpush mutates it
                    ttl=600,                               # keep up to 10 min if device offline
                    headers={"Urgency": "high"},
                    timeout=15)
            sent += 1
        except WebPushException as e:
            resp = getattr(e, "response", None)
            code = getattr(resp, "status_code", None)
            bodytext = ""
            try:
                bodytext = (resp.text or "")[:120] if resp is not None else ""
            except Exception:
                pass
            if code in (404, 410):
                with db() as c:
                    c.execute("DELETE FROM push_subs WHERE id=?", (s0["id"],))
                sw.log(f"  [push] pruned dead sub {s0['id']} via {host} (HTTP {code}) {bodytext}")
            else:
                sw.log(f"  [push] send failed via {host} (HTTP {code}): {str(e)[:80]} {bodytext}")
        except Exception as e:
            sw.log(f"  [push] send crashed via {host}: {type(e).__name__}: {str(e)[:80]}")
    return sent


def send_email(to, subject, body_text, url):
    """The zero-setup default alert channel. Sends a plain, unmissable email via SMTP.
    Returns True if handed off to the mail server. If SMTP isn't configured (EMAIL_ENABLED
    False) or no address, it's a silent no-op — the other channels still fire, nothing breaks."""
    if not EMAIL_ENABLED or not to:
        return False
    try:
        msg = EmailMessage()
        msg["Subject"] = subject
        msg["From"] = formataddr(("SeatWatch", SMTP_FROM))
        msg["To"] = to
        # One-click unsubscribe. Since Gmail's 2024 sender rules this is the single
        # highest-weighted signal separating wanted mail from bulk, and its absence is one
        # of the few content signals a correctly-authenticated transactional alert can
        # still trip. Routed to support@, which is monitored.
        msg["List-Unsubscribe"] = f"<mailto:{SUPPORT_EMAIL}?subject=unsubscribe>"
        msg["List-Unsubscribe-Post"] = "List-Unsubscribe=One-Click"
        # No "STOP" wording here: that is bulk-SMS marketing boilerplate, it was going out
        # on every alert, and it reads to a filter exactly like the mail we are not.
        msg.set_content(f"{body_text}\n\nRegister now: {url}\n\n"
                        f"— SeatWatch\nYou're getting this because you asked us to watch this class. "
                        f"You can turn off alerts for this class any time at seatwatchapp.com.")
        with smtplib.SMTP(SMTP_HOST, SMTP_PORT, timeout=15) as s:
            s.starttls(context=ssl.create_default_context())
            s.login(SMTP_USER, SMTP_PASS)
            s.send_message(msg)
        return True
    except Exception as e:
        sw.log(f"  [email] send failed to {to}: {type(e).__name__}: {str(e)[:80]}")
        return False


# ------------------------------------------------------------------- SMS (dormant)
def _day_start(now=None):
    """Epoch of local midnight — the boundary for 'today' in every daily cap."""
    t = time.localtime(now if now is not None else time.time())
    return (now if now is not None else time.time()) - (t.tm_hour * 3600 + t.tm_min * 60 + t.tm_sec)


def _log_alert(r, channel, cost=0):
    """Append one delivery to the ledger. Never raises — a logging failure must not
    block the alert itself (the send already happened)."""
    try:
        with db() as c:
            c.execute("INSERT INTO alert_log(user_id,watch_id,school,course,section,"
                      "channel,cost_cents,sent_at) VALUES(?,?,?,?,?,?,?,?)",
                      (r["user_id"] if "user_id" in r.keys() else None, r["id"],
                       r["school"], r["course"], r["section"], channel, cost, time.time()))
    except Exception as e:
        sw.log(f"  [ledger] write failed ({channel}): {type(e).__name__}")


def _log_attempt(r, channel, outcome, token=None):
    """Record ONE intended notification (success or not). Never raises — instrumentation
    must never break a real alert."""
    try:
        with db() as c:
            c.execute("INSERT INTO alert_attempt(token,user_id,watch_id,school,course,"
                      "section,channel,outcome,attempted_at) VALUES(?,?,?,?,?,?,?,?,?)",
                      (token, r["user_id"] if "user_id" in r.keys() else None, r["id"],
                       r["school"], r["course"], r["section"], channel, outcome, time.time()))
    except Exception as e:
        sw.log(f"  [attempt] log failed ({channel}/{outcome}): {type(e).__name__}")


def _click_url(token, fallback):
    """The link a student taps. Routes through /r/<token> so we can measure whether an
    alert produced ACTION (and how fast, per channel) — delivery is not value.

    Falls back to the registrar URL directly if BASE_URL isn't configured, so a
    misconfiguration can never leave a student without a working link."""
    return f"{BASE_URL}/r/{token}" if BASE_URL else fallback


def _sms_phone(user_id):
    """The user's consented phone: newest consent row that is CONFIRMED (they texted
    back YES) and not revoked (no STOP). Anything else -> None, no SMS."""
    with db() as c:
        row = c.execute("SELECT phone FROM sms_consent WHERE user_id=? AND "
                        "confirmed_at IS NOT NULL AND revoked_at IS NULL "
                        "ORDER BY id DESC LIMIT 1", (user_id,)).fetchone()
    return row["phone"] if row else None


def _sms_segments(text):
    """Billable Twilio segments for `text`. GSM-7 fits 160 chars (153 when concatenated);
    any non-GSM character forces UCS-2 at 70 (67 concatenated). We bill PER SEGMENT, so a
    two-part alert must count as two — otherwise the ledger under-counts real spend and the
    daily $ cap is wrong (the alert body with a course URL routinely runs to 2 segments)."""
    gsm = set("@£$¥èéùìòÇ\nØø\rÅåΔ_ΦΓΛΩΠΨΣΘΞÆæßÉ !\"#¤%&'()*+,-./0123456789:;<=>?¡"
              "ABCDEFGHIJKLMNOPQRSTUVWXYZÄÖÑÜ§¿abcdefghijklmnopqrstuvwxyzäöñüà"
              "€^{}\\[~]|")
    n = len(text)
    single, multi = (160, 153) if all(ch in gsm for ch in text) else (70, 67)
    return 1 if n <= single else -(-n // multi)          # ceil division


# Terminal Twilio error codes worth acting on rather than blind-retrying.
_TWILIO_STOP_CODES = {21610}          # recipient has unsubscribed (carrier-level STOP)


def _twilio_post(to, body):
    """Send one SMS via Twilio's REST API (stdlib only). Returns (ok, err_code):
    (True, None) on 2xx; (False, <int code>) on a Twilio API error (e.g. 21610 recipient
    unsubscribed, 30034 A2P number unregistered, 21211 invalid 'To'); (False, None) on a
    transport error. Never raises — the caller decides what to do with the code."""
    url = f"https://api.twilio.com/2010-04-01/Accounts/{TWILIO_SID}/Messages.json"
    field = "MessagingServiceSid" if TWILIO_FROM.startswith("MG") else "From"
    data = urllib.parse.urlencode({"To": to, field: TWILIO_FROM, "Body": body}).encode()
    auth = base64.b64encode(f"{TWILIO_SID}:{TWILIO_TOKEN}".encode()).decode()
    req = urllib.request.Request(url, data=data,
                                 headers={"Authorization": f"Basic {auth}", "User-Agent": sw.UA})
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            return (200 <= resp.status < 300, None)
    except urllib.error.HTTPError as e:
        code = None
        try:
            code = int(json.loads(e.read().decode("utf-8", "replace")).get("code"))
        except Exception:
            pass
        if code in (30032, 30034):        # the premature-enable foot-gun, made obvious
            kind = "verified (toll-free)" if code == 30032 else "registered (10DLC)"
            sw.log(f"  [sms] ⚠️ Twilio {code}: sender number NOT {kind} — SMS_ENABLED was flipped "
                   "on before the number's verification/registration cleared. NO texts will "
                   "send until it's approved; alerts are falling back to push/email.")
        else:
            sw.log(f"  [sms] Twilio API error HTTP {e.code} code={code}")
        return (False, code)
    except Exception as e:
        sw.log(f"  [sms] Twilio transport error: {type(e).__name__}: {str(e)[:80]}")
        return (False, None)


_sms_paged = set()   # which cap trips were already operator-paged today (page once, not
                     # per cycle; cosmetic only — the CAPS themselves are ledger-derived)
_dryrun_logged = set()   # watch_ids already dry-run-logged this process (log once, not per cycle)


def send_sample_email(user_id):
    """Show a student what a seat alert looks like, by email, once.

    SMS has done this since day one. Email never did — so the first time a student's
    inbox was used was a REAL opening, and a wrong address, a full mailbox or Gmail's
    Promotions tab all failed silently at the worst possible moment. This makes email
    prove itself on the calm day instead of the urgent one.

    Deliberately NOT a "welcome" or "confirm your account" mail. It is a WORKED EXAMPLE
    of the thing they signed up for, so the value is visible even to someone who never
    reads it twice — and it doubles as a deliverability test they do not have to run.

    Once per ACCOUNT (sample_email_at), never per watch. Honours the email preference:
    a student who switched email off must not receive a demonstration of email. Never
    raises — a nicety must not be able to break watch creation.
    """
    if not EMAIL_ENABLED or not user_id:
        return False
    try:
        with db() as c:
            u = c.execute("SELECT email, sample_email_at FROM users WHERE id=?",
                          (user_id,)).fetchone()
        if not u or u["sample_email_at"] or not (u["email"] or "").strip():
            return False
        if not notify_prefs(user_id)[1]:
            return False                      # they turned email off; respect it
        base = BASE_URL or "https://seatwatchapp.com"
        body = (
            "You're all set — we're watching your class.\n\n"
            "This is what an alert will look like when a seat opens:\n\n"
            "    Seat open: CHEM231-0101\n"
            "    2 seats just opened. Register now.\n"
            f"    {base}/\n\n"
            "That is the whole product. We check every 20 seconds, around the clock, and\n"
            "we never send an alert for a seat that is not really there.\n\n"
            "Nothing else to do — keep this so you know what to look for, and make sure\n"
            "it did not land in Promotions or Spam. If it did, drag it to your inbox so\n"
            "the real one reaches you.\n\n"
            f"Your classes: {base}/\n\n— SeatWatch")
        ok = send_email(u["email"], "This is what a SeatWatch alert looks like",
                        body, base + "/")
        # Stamp on ATTEMPT, like the sample text. Retrying a courtesy email until it
        # succeeds is how someone ends up receiving it four times.
        with db() as c:
            c.execute("UPDATE users SET sample_email_at=? WHERE id=?", (time.time(), user_id))
        if ok:
            sw.log(f"  [email] sample alert sent to user {user_id}")
        return bool(ok)
    except Exception as e:
        sw.log(f"  [email] sample failed: {type(e).__name__}")
        return False


def send_sample_sms(user_id):
    """Show a student exactly what a seat alert will look like, once, when they first
    start watching a class.

    This is the whole pitch delivered in ten seconds: they have just told us which class
    they are stuck on, and their phone immediately shows the message that will arrive when
    a seat frees up. Nothing else we can say converts as well as the thing itself.

    Strictly ONCE per account (sample_sms_at), never per watch — adding five classes must
    not send five texts. Consent-gated like every other send: _sms_phone() returns a number
    only when it is confirmed and not revoked. Costs about a penny, and never raises: a
    marketing nicety must not be able to break watch creation.
    """
    if not (SMS_LIVE or SMS_DRYRUN) or not user_id:
        return False
    try:
        with db() as c:
            u = c.execute("SELECT sample_sms_at FROM users WHERE id=?", (user_id,)).fetchone()
        if not u or u["sample_sms_at"]:
            return False                      # already shown, or no such user
        phone = _sms_phone(user_id)
        if not phone:
            return False                      # no consented number: nothing to show
        if not notify_prefs(user_id)[2]:
            # The sample says "we'll text you the moment a real seat frees up". If this
            # account has texts switched off, send_sms would refuse that alert, so the
            # sample would be a promise the product does not keep. Consent paths set
            # notify_sms=1, so reaching here means the student turned it off deliberately
            # after consenting — and that choice outranks the demo.
            return False
        body = ("SeatWatch: you're all set. This is what an alert looks like — "
                "\"CHEM231-0101: 2 seats just opened. Register now.\" "
                "We'll text you the moment a real seat frees up. Reply STOP to opt out.")
        segs = _sms_segments(body)
        if SMS_DRYRUN and not SMS_LIVE:
            sw.log(f"  [sms DRY-RUN] sample to ••••{phone[-4:]} segs={segs} body={body!r}")
            ok = True
        else:
            ok, code = _twilio_post(phone, body)
            if not ok and code in _TWILIO_STOP_CODES:
                with db() as c:
                    c.execute("UPDATE sms_consent SET revoked_at=? WHERE user_id=? AND "
                              "phone=? AND revoked_at IS NULL", (time.time(), user_id, phone))
        # Stamp on ATTEMPT, not only on success. A carrier failure is not worth retrying
        # forever, and a student who signs up during an outage should not be sampled
        # repeatedly later — the real alerts are what matter.
        with db() as c:
            c.execute("UPDATE users SET sample_sms_at=? WHERE id=?", (time.time(), user_id))
        sw.log(f"  [sms] sample alert {'sent' if ok else 'attempted'} to ••••{phone[-4:]} "
               f"({segs} seg)")
        return bool(ok)
    except Exception as e:
        sw.log(f"  [sms] sample failed: {type(e).__name__}")
        return False


def send_sms(user_id, r, message, url):
    """Deliver one seat alert by SMS, spending real money — so this function is where
    EVERY cost gate lives, structurally, not at call sites. Returns True only when
    Twilio accepted the message. Any refusal returns False silently toward the caller:
    _alert fires web-push/email/ntfy regardless, so capping SMS switches channels and
    never suppresses the student's alert (the existing DELIVERED-TO-NOBODY page still
    covers the nobody-reachable case).

    THE RULE (Nathan, 2026-08-14): every time a section genuinely opens, the student is
    texted; the same opening is never texted twice. So the limit is per OPENING, not a
    count per term — a cap of N texts per semester silences opening N+1, which is exactly
    the seat somebody was waiting for.

    "No repeats" is not enforced here. It is the watch's `alerted` latch: set when an
    alert fires, cleared only when the section is observed CLOSED, and persisted in the
    DB so a restart cannot re-fire it. One alert per closed->open transition, by
    construction. This function's job is cost catastrophe, not product behaviour.

    What was removed and why: a permanent ONE-TEXT-PER-WATCH-EVER latch, justified on
    texts being the paid tier's headline feature. SMS moved to the free tier and the
    justification went with it, but the latch stayed — so the differentiator fired once
    per watch per SEMESTER, and four texts is SeatWatch's entire sending history. The
    other half of that justification, that a flickering section would bill repeatedly,
    is now handled upstream: CONFIRM_SECONDS means a seat that dies inside two minutes
    never alerts on ANY channel, which is where 14 of 18 measured openings went.

    Order of gates (cheapest first, all ledger-derived):
      dormant -> channel preference (the student's own notify_sms switch) -> consent
      (confirmed double opt-in, no STOP) -> repeat cooldown (SHARED with email, so the
      two channels obey one rule instead of two regimes) -> runaway detector -> per-user
      daily -> daily $ ceiling -> velocity breaker (a loop is a vertical spike; growth is
      a slope — the floor keeps tiny legitimate volume from ever tripping it)."""
    if not (SMS_LIVE or SMS_DRYRUN):       # dormant, or dry-run for pipeline proving
        return False
    if not user_id:
        return False
    with db() as c:
        u = c.execute("SELECT * FROM users WHERE id=?", (user_id,)).fetchone()
    if not u:
        return False
    # SMS is CONSENT-gated, not tier-gated. It used to be paid-only, on the reasoning that
    # texts cost money forever and were the paid tier's headline feature. The tiers actually
    # sell QUANTITY (free = 1 class / 2 sections; paid = more classes, unlimited sections),
    # so the ladder survives, and a free tier that texts you is the reason anyone signs up
    # at all. Spend stays bounded by the per-watch latch, the per-user daily cap, the daily
    # dollar ceiling and the velocity breaker below — none of which changed.
    # Consent is still absolute: _sms_phone() returns a number ONLY when it is confirmed
    # and not revoked, so nobody is texted who did not ask to be.
    if not notify_prefs(user_id)[2]:
        return False                       # student switched texts off in their preferences
    phone = _sms_phone(user_id)
    if not phone:
        return False
    body = f"SeatWatch: {message} Register now: {url} (Reply STOP to opt out)"
    cost = SMS_COST_CENTS * _sms_segments(body)   # PER-SEGMENT — a 2-part alert costs 2
    now = time.time()
    day0 = _day_start(now)
    wid = r["id"]
    with db() as c:
        # Repeat cooldown, SHARED with email (SMS_DEDUP_SECS defaults to
        # REPEAT_ALERT_COOLDOWN_S). Two distinct openings more than the window apart are
        # two notifications, which is the rule; the same opening re-observed inside it is
        # one. Keyed on (user, course, section) rather than watch_id so deleting and
        # re-creating a watch cannot be used to re-send the same alert.
        if c.execute("SELECT 1 FROM alert_log WHERE user_id=? AND course=? AND section=? "
                     "AND channel='sms' AND sent_at>? LIMIT 1",
                     (user_id, r["course"], r["section"], now - SMS_DEDUP_SECS)).fetchone():
            return False
        # Runaway detector, NOT a product limit. The old value (3 per 180 days) became the
        # binding cap the moment the permanent latch was removed, and would have silenced
        # the fourth genuine opening of the semester. SMS_PER_WATCH_MAX is now set where
        # only a bug can reach it, and it pages instead of failing quietly.
        n = c.execute("SELECT COUNT(*) FROM alert_log WHERE user_id=? AND course=? AND "
                      "section=? AND channel='sms' AND sent_at>?",
                      (user_id, r["course"], r["section"], now - 180 * 86400)).fetchone()[0]
        if n >= SMS_PER_WATCH_MAX:
            if (user_id, r["course"], "watchcap") not in _sms_paged:
                _sms_paged.add((user_id, r["course"], "watchcap"))
                operator_alert(f"SMS runaway: user {user_id} {r['course']}-"
                               f"{r['section'] or 'ALL'} hit {SMS_PER_WATCH_MAX} texts in "
                               "180 days. One section does not open that often — this is "
                               "a bug, not demand. Investigate before raising the cap.")
            return False
        # per-user daily
        n = c.execute("SELECT COUNT(*) FROM alert_log WHERE user_id=? AND channel='sms' "
                      "AND sent_at>?", (user_id, day0)).fetchone()[0]
        if n >= SMS_PER_USER_DAILY:
            return False                   # falls back to free channels; log-only
        # site-wide daily $ ceiling (env-tunable catastrophe floor, not a growth cap)
        spent = c.execute("SELECT COALESCE(SUM(cost_cents),0) FROM alert_log WHERE "
                          "channel='sms' AND sent_at>?", (day0,)).fetchone()[0]
        if spent + cost > SMS_DAILY_CAP_CENTS:        # accurate: cost is per-segment
            if "dailycap" not in _sms_paged:
                _sms_paged.add("dailycap")
                operator_alert(f"💸 SMS daily cap ${SMS_DAILY_CAP_CENTS/100:.2f} reached — "
                               "SMS paused until midnight, alerts falling back to "
                               "push/email. Raise SMS_DAILY_CAP_CENTS if this is growth.")
            return False
        # circuit breaker: already tripped today? (durable — it's a ledger row, so a
        # crashing runaway loop cannot reset it by restarting the process)
        if c.execute("SELECT 1 FROM alert_log WHERE channel='sms_breaker' AND sent_at>? "
                     "LIMIT 1", (day0,)).fetchone():
            return False
        # velocity: vertical spike = loop signature; the floor keeps small real volume
        # from ever tripping it
        today_n = c.execute("SELECT COUNT(*) FROM alert_log WHERE channel='sms' AND "
                            "sent_at>?", (day0,)).fetchone()[0]
        minute_n = c.execute("SELECT COUNT(*) FROM alert_log WHERE channel='sms' AND "
                             "sent_at>?", (now - 60,)).fetchone()[0]
        if today_n >= SMS_VELOCITY_FLOOR and minute_n >= SMS_VELOCITY_PER_MIN:
            c.execute("INSERT INTO alert_log(user_id,watch_id,school,course,section,"
                      "channel,cost_cents,sent_at) VALUES(NULL,NULL,'','','',"
                      "'sms_breaker',0,?)", (now,))
            operator_alert(f"🚨 SMS VELOCITY BREAKER: {minute_n} texts/min with {today_n} "
                           "today — looks like a loop, not growth. SMS paused until "
                           "midnight; alerts falling back to push/email.")
            return False
    if not SMS_LIVE:
        # DRY-RUN (SMS_DRYRUN, not live): prove detection -> gate -> message on real data
        # without sending. Log the exact would-send ONCE per watch; record a distinct
        # 'sms_dryrun' ledger row (never counted by the caps or the real send-latch, so it
        # can't interfere with them or pollute real spend). Returns False so _alert still
        # fires the free channels.
        if wid not in _dryrun_logged:
            _dryrun_logged.add(wid)
            sw.log(f"  [sms DRY-RUN] would text ••••{phone[-4:]}  "
                   f"segs={_sms_segments(body)} cost={cost}¢  body={body!r}")
            _log_alert(r, "sms_dryrun", 0)
        return False
    ok, code = _twilio_post(phone, body)
    if not ok and code in _TWILIO_STOP_CODES:
        # a carrier-level STOP that never reached our webhook — record the revocation so
        # we stop attempting this number (keeps our consent records authoritative)
        with db() as c:
            c.execute("UPDATE sms_consent SET revoked_at=? WHERE user_id=? AND phone=? "
                      "AND revoked_at IS NULL", (time.time(), user_id, phone))
        sw.log(f"  [sms] user {user_id} unsubscribed at carrier (Twilio {code}) — consent revoked")
    if ok:
        _log_alert(r, "sms", cost)
    return ok


def _norm_phone(raw):
    """US-defaulted E.164 or None. A wrong format returns None (no SMS), never a guess."""
    d = re.sub(r"\D", "", raw or "")
    if len(d) == 10:
        return "+1" + d
    if len(d) == 11 and d.startswith("1"):
        return "+" + d
    return None


def _twilio_candidate_urls(headers, path, base):
    """Every URL Twilio might have signed, most-likely first.

    The signature is an HMAC over the EXACT URL Twilio requested. We used to sign one
    hardcoded guess (BASE_URL + path), which breaks on www-vs-apex, http-vs-https behind
    a proxy, or a trailing slash in the console — and it breaks SILENTLY, as a 403. That
    is how STOP stops working: the student texts STOP, we reject the webhook, consent is
    never revoked, and we keep texting someone who opted out. It cost us a live failure
    on the first real inbound message ever received.

    Reconstructing from the request is what Twilio's own helper libraries do. Trying
    several candidates weakens nothing: every one still requires the auth token, so an
    attacker who can set a Host header still cannot forge a signature.
    """
    host = (headers.get("X-Forwarded-Host") or headers.get("Host") or "").split(",")[0].strip()
    proto = (headers.get("X-Forwarded-Proto") or "https").split(",")[0].strip() or "https"
    hosts = []
    if host:
        hosts.append(host)
        hosts.append(host[4:] if host.startswith("www.") else "www." + host)
    if base:
        b = base.split("://")[-1].strip("/")
        if b and b not in hosts:
            hosts.append(b)
    # A reverse proxy normalises the path BEFORE the app sees it, so a trailing slash in
    # the Twilio console arrives here stripped — while Twilio signed the slash. Same for
    # the scheme: Caddy terminates TLS and may forward as http, or forward no
    # X-Forwarded-Proto at all. Both produce a different HMAC and a silent 403, which is
    # how a STOP disappears. HMAC is microseconds, so cover the space instead of guessing.
    p0 = path.split("?")[0]
    paths = [path, p0, p0.rstrip("/"), p0.rstrip("/") + "/"]
    cands = [f"{p}://{h}{pa}"
             for h in dict.fromkeys(hosts)
             for p in dict.fromkeys((proto, "https", "http"))
             for pa in dict.fromkeys(paths)]
    seen, out = set(), []
    for u in cands:
        if u and u not in seen:
            seen.add(u)
            out.append(u)
    return out


def _twilio_verify_any(urls, params, signature):
    """(valid, matched_url). Returns the URL that validated so the log can record which
    form Twilio actually uses — the next person should not have to rediscover this."""
    for u in urls:
        if _twilio_verify(u, params, signature):
            return True, u
    return False, None


def _twilio_verify(url, params, signature):
    """Twilio webhook auth: base64(HMAC-SHA1(auth_token, url + params sorted by key,
    concatenated key+value)). Constant-time compare; False on anything malformed."""
    if not TWILIO_TOKEN or not signature:
        return False
    try:
        s = url + "".join(k + v for k, v in sorted(params.items()))
        want = base64.b64encode(hmac.new(TWILIO_TOKEN.encode(), s.encode(),
                                         hashlib.sha1).digest()).decode()
        return hmac.compare_digest(want, signature)
    except Exception:
        return False


def sms_apply_inbound(from_phone, body):
    """Handle a student's reply text. STOP revokes consent (durable, effective
    immediately); YES/START confirms the double opt-in (or re-subscribes after a STOP);
    HELP gets a help reply. Returns the reply text to send back, or None for silence.
    Twilio's own Advanced Opt-Out also enforces STOP at the carrier level — this keeps
    OUR consent records authoritative rather than relying on theirs."""
    word = (body or "").strip().upper().split()[:1]
    word = word[0] if word else ""
    now = time.time()
    if word in ("STOP", "STOPALL", "UNSUBSCRIBE", "CANCEL", "END", "QUIT"):
        with db() as c:
            c.execute("UPDATE sms_consent SET revoked_at=? WHERE phone=? AND revoked_at IS NULL",
                      (now, from_phone))
        sw.log(f"  [sms] STOP from {from_phone[-4:].rjust(4, '*')}")
        return None                        # Twilio sends the compliance STOP reply itself
    if word in ("YES", "START", "UNSTOP", "SUBSCRIBE"):
        with db() as c:
            row = c.execute("SELECT id, confirmed_at, revoked_at FROM sms_consent WHERE "
                            "phone=? ORDER BY id DESC LIMIT 1", (from_phone,)).fetchone()
            if not row:
                return None                # a YES from a number that never opted in: ignore
            if row["revoked_at"] is not None:
                # re-subscribe after STOP: fresh confirmation on the newest record
                c.execute("UPDATE sms_consent SET revoked_at=NULL, confirmed_at=? WHERE id=?",
                          (now, row["id"]))
            elif row["confirmed_at"] is None:
                c.execute("UPDATE sms_consent SET confirmed_at=? WHERE id=?", (now, row["id"]))
        return ("SeatWatch: you're confirmed for seat alerts. Msg frequency varies. "
                "Msg&data rates may apply. Reply STOP to cancel, HELP for help.")
    if word == "HELP":
        return ("SeatWatch seat alerts. Support: support@seatwatchapp.com. "
                "Msg&data rates may apply. Reply STOP to cancel.")
    return None


def notify_prefs(user_id):
    """(want_push, want_email, want_sms) for this account. Fail OPEN: any missing row, missing
    column or DB error reads as ENABLED, because the failure mode of guessing wrong
    is a student who silently stops being alerted. An extra notification is a nuisance; a
    missing one is the whole product failing.

    want_push is now ALWAYS False — push is retired. The slot stays so the Guardian's
    notify_prefs(uid)[:2] read keeps working and so the stored column survives for anyone
    who wants the history; nothing consults it to decide whether to send.

    Guardian reads this too (via app.notify_prefs) so the sender and the latch can never
    disagree about which channels an account actually uses.
    """
    if not user_id:
        return False, True, True
    try:
        with db() as c:
            u = c.execute("SELECT notify_email, notify_sms FROM users "
                          "WHERE id=?", (user_id,)).fetchone()
        if not u:
            return False, True, True
        return False, bool(u["notify_email"]), bool(u["notify_sms"])
    except Exception:
        return False, True, True


_undelivered = set()   # watch_ids whose last alert reached NOBODY (retrying each cycle)


# REPEAT_ALERT_COOLDOWN_S is defined up with the SMS constants, because SMS shares it —
# one repeat rule for both channels rather than two regimes that drift apart. Rationale
# for 1800: bursts on one contested section arrive ~45-70s apart, and the two bursts
# observed on 2026-08-13 were about an hour apart. Thirty minutes collapses a burst to a
# single alert while still letting a genuinely new opening an hour later through. Longer
# would start hiding real second chances; shorter would not have stopped the storm.


def _repeat_suppressed(watch_id):
    """Has THIS watch already had an alert DELIVERED inside the cooldown?

    Per watch, deliberately and strictly: a storm on one student's CMSC216 must never
    delay a different course, a different section, or a different student. The watch id
    is the narrowest key that exists, so nothing wider can be suppressed by accident.

    SMS is excluded from the lookup because it enforces one text per watch EVER, which is
    stricter than this; counting it would let a months-old text mute a fresh email.
    """
    try:
        with db() as c:
            return c.execute(
                "SELECT 1 FROM alert_log WHERE watch_id=? AND channel!='sms' AND sent_at>? "
                "LIMIT 1", (watch_id, time.time() - REPEAT_ALERT_COOLDOWN_S)).fetchone() is not None
    except Exception:
        return False          # never let a bookkeeping error swallow a real alert


def _alert(r, message, url):
    """Deliver a seat-open alert on every channel. Returns True iff AT LEAST ONE channel
    actually delivered. On total failure the caller must NOT latch the watch, so it
    retries next cycle instead of silently losing the seat — and the operator is paged
    once (a real alert reached nobody)."""
    # One token per CHANNEL so a click attributes to the channel that produced it — that's
    # what makes "is SMS actually faster than email?" answerable with data instead of priors.
    tok = {ch: secrets.token_urlsafe(9) for ch in ("email", "sms")}
    # Push and ntfy are RETIRED as student channels. Both could report success while
    # reaching nobody — a browser subscription the student never granted, or an ntfy topic
    # with no listener (publishing to an empty topic still returns 200). That is how a paid
    # account sat "alerted" for a seat it was never told about. Email and SMS are the only
    # two channels whose delivery we can actually stand behind, so they are the only two we
    # offer. ntfy remains in operator_alert, which pages the operator, not students.
    ok, pushed = False, 0
    uid = r["user_id"] if "user_id" in r.keys() else None
    # Per-user channel preferences. Read ONCE here and reused for the latch decision, so
    # the Guardian and the sender can never disagree about which channels this account
    # actually uses. Missing/legacy rows read as enabled, matching the DEFAULT 1 migration.
    _, want_email, want_sms = notify_prefs(uid)
    # REPEAT-ALERT COOLDOWN. Every alert below is CORRECT — each follows a real
    # closed->open transition the poller observed. But on 2026-08-13 watch 27 (CMSC216
    # 0102) produced EIGHT emails in an hour while SMS sent exactly one, because SMS has a
    # one-text-per-watch rule and email had nothing. Add/drop churn on a contested course
    # opens and refills a seat within seconds, so a student got eight mails about a class
    # they could not get into. That is how a beta user unsubscribes on day one and then
    # never hears about the seat they WOULD have got: a correct alert that drives someone
    # away is worse than no alert.
    #
    # Derived from the alert_log ledger rather than held in memory, for the same reason
    # every SMS cap is: the poller restarts on each deploy, and an in-memory counter would
    # let a runaway loop reset its own brake.
    #
    # It gates on a previous DELIVERY, not on elapsed time, and that distinction is the
    # whole safety of it. alert_log records successes only, so "a row inside the window"
    # means this student genuinely heard from us recently. A watch whose alert reached
    # NOBODY has no row, so the every-cycle delivery retry still runs untouched — losing
    # that would resurrect the silent-failure class closed last week.
    suppressed = _repeat_suppressed(r["id"]) if uid else False
    emailed = False
    if want_email and EMAIL_ENABLED and uid and not suppressed:
        with db() as c:
            row = c.execute("SELECT email FROM users WHERE id=?", (uid,)).fetchone()
        if row and row["email"]:
            emailed = send_email(row["email"], f"Seat open: {r['course']} — go register",
                                 message + " Register now before it fills again.",
                                 _click_url(tok["email"], url))
    # SMS keeps the DIRECT registrar link: texts are billed per 160-char segment and a
    # student must be able to reach the registrar even if our box is down mid-registration.
    # SMS respects the preference too. Consent (via the box, revoked by STOP) is the
    # LEGAL gate; this is the student's day-to-day "stop texting me, email is fine" switch.
    # Both must allow it, and either one alone can stop it.
    texted = send_sms(uid, r, message, url) if want_sms else False
    # Ledger: one row per channel that reported success. Every row here now represents a
    # channel that addresses a real inbox or handset, so a count of these is a count of
    # students actually reached — which was never true while ntfy was in the total.
    if emailed:
        _log_alert(r, "email")
    # Attempt ledger: the DENOMINATOR. Every channel that delivered gets a click token;
    # if NOTHING reached the student we record one 'no_channel' row, so silent failures are
    # counted instead of being invisible (alert_log holds successes only).
    for ch, sent_ok in (("email", emailed), ("sms", texted)):
        if sent_ok:
            _log_attempt(r, ch, "sent", tok[ch] if ch != "sms" else None)
    # A repeat we deliberately HELD is not an attempt that failed — it is an attempt we
    # chose not to make, because the student was told minutes ago. Logging it as
    # 'no_channel' manufactured SeatWatch's first-ever "silent delivery failure" (id=44,
    # watch 63) THIRTEEN SECONDS AFTER that student had already clicked through to the
    # registrar from the email we did send. Two costs, and the second is the real one:
    # reachability (sent/attempts) gets a phantom miss in its denominator, and a genuinely
    # unreachable student would be buried among routine suppressions in the one signal we
    # hunt for exactly that. The suppression is still recorded — guardian's cycle outcome
    # and the "repeat within cooldown — not re-sent" log line both carry it.
    if not (emailed or texted) and not suppressed:
        _log_attempt(r, None, "no_channel")
    # Latch only on a channel that reached a person. With ntfy_ok/pushed pinned False the
    # honest and legacy rules collapse to the same answer — "email or text delivered" —
    # so this now means the same thing in every Guardian mode. Signature kept so the
    # Guardian lane's file needs no edit from here.
    # A suppressed repeat COUNTS AS DELIVERED, and getting this wrong would have been
    # worse than the storm. Without it the latch sees no channel succeed, so the watch
    # never latches, retries every 20 seconds forever, and pages the operator
    # "DELIVERED-TO-NOBODY" for a student who was in fact emailed minutes ago. The student
    # WAS reached; we are declining to repeat ourselves, which is the opposite of a
    # delivery failure.
    delivered = guardian.latch_decision(r, ok, pushed, emailed, texted) or suppressed
    sw.log(f"  ALERT {r['course']}-{r['section'] or 'ALL'} -> user {uid} "
           + ("(repeat within cooldown — not re-sent; already alerted <"
              f"{REPEAT_ALERT_COOLDOWN_S // 60}min ago)" if suppressed else
              f"(email {'sent' if emailed else 'off'}; sms {'sent' if texted else 'off'}"
              f"{'; ⚠️DELIVERED-TO-NOBODY' if not delivered else ''})"))
    wid = r["id"]
    if not delivered:
        if wid not in _undelivered:            # page once, not every retry cycle
            operator_alert(f"🚨 UNDELIVERED: {r['course']} seat opened but email + text BOTH "
                           "failed — student was NOT notified. Retrying every cycle until a "
                           "channel works; check SMTP and Twilio config.")
            _undelivered.add(wid)
    else:
        _undelivered.discard(wid)              # recovered (or first success)
    return delivered


def notify_stranded(watch, school, new_term):
    """Tell a student, ONCE, that their watch died because the school changed semesters.

    A watch is bound to the term it was created in. When the school rolls, run_cycle skips
    it forever — correctly, because matching a Fall watch against a same-numbered Spring
    section would alert about a semester the student never asked for. But the skip was
    SILENT: the operator got paged and the student got nothing, so someone who set a watch
    in August would simply never hear from us again and would assume their class never
    opened. That is indistinguishable, from their side, from us being broken.

    This matters far more in the next few weeks than it did all year. Roughly 277 schools
    re-pick their term on every fetch and will move to Spring 2027 on their own around
    October; every Fall watch at those schools goes quiet the moment they do.

    Stamped so it goes out exactly once per watch. Failure to send is not stamped, so a
    transient SMTP problem retries next cycle rather than silently swallowing the only
    warning the student gets. Never raises: telling someone their watch expired must not
    be able to interfere with alerting everybody else.
    """
    wid = watch["id"]
    uid = watch["user_id"] if "user_id" in watch.keys() else None
    if not uid:
        return False
    try:
        with db() as c:
            row = c.execute("SELECT stranded_notified_at, email FROM watches w "
                            "JOIN users u ON u.id=w.user_id WHERE w.id=?", (wid,)).fetchone()
        if not row or row["stranded_notified_at"]:
            return False                      # already told them; never nag
        _, want_email, want_sms = notify_prefs(uid)
        what = f"{watch['course']}" + (f" section {watch['section']}" if watch["section"] else "")
        base = BASE_URL or "https://seatwatchapp.com"
        sent = False
        if want_email and EMAIL_ENABLED and row["email"]:
            sent = send_email(
                row["email"],
                f"Your {what} watch has ended — {school.name} moved to a new semester",
                f"{school.name} has moved its class schedule to a new semester, so your "
                f"watch on {what} has ended.\n\n"
                f"We stopped it on purpose. Section numbers get reused between semesters, "
                f"and letting it run would have texted you about a seat in a term you never "
                f"signed up for.\n\n"
                f"If you still want this class, add it again and we will watch the new "
                f"semester:\n\n    {base}/\n\n"
                f"Nothing else you watch is affected.\n\n— SeatWatch",
                base + "/")
        if not sent and want_sms:
            sent = bool(send_sms(uid, watch,
                                 f"Your {what} watch ended: {school.name} moved to a new "
                                 f"semester. Add the class again to watch it.", base + "/"))
        if sent:
            with db() as c:
                c.execute("UPDATE watches SET stranded_notified_at=? WHERE id=?",
                          (time.time(), wid))
            sw.log(f"  [term] told watch {wid} its term ({watch['term']}) is over at "
                   f"{school.id} (now {new_term})")
        return sent
    except Exception as e:
        sw.log(f"  [term] could not notify stranded watch {wid}: {type(e).__name__}")
        return False


def _set_alerted(watch_id, val):
    with db() as c:
        c.execute("UPDATE watches SET alerted=? WHERE id=?", (val, watch_id))


POLL_LEASE_TTL = int(os.environ.get("POLL_LEASE_TTL", "180"))   # ~9 poll cycles
_LEASE_ID = f"{os.getpid()}-{secrets.token_hex(4)}"             # unique per process
_stood_down = [False]        # log the stand-down once, not every cycle


def acquire_poll_lease():
    """Single-poller guarantee: only the lease holder may run a cycle.

    The poller alerts INLINE, so two live processes (a double-start, a failover, or a
    deploy overlap) would each fetch and each alert — a duplicate text/push for the same
    seat, which reads as spam and costs trust (and money on SMS). One row in the DB is the
    token; SQLite's write lock makes the claim atomic.

    Crash-safe by construction: the lease carries an EXPIRY, so a process that dies holding
    it is automatically reclaimed after POLL_LEASE_TTL — a crash can never permanently stop
    polling (the failure mode worse than a duplicate). Returns True if we hold it.
    """
    now = time.time()
    with db() as c:
        c.execute("""CREATE TABLE IF NOT EXISTS poll_lease(
            id INTEGER PRIMARY KEY CHECK (id = 1),
            holder TEXT NOT NULL,
            expires_at REAL NOT NULL)""")
        row = c.execute("SELECT holder, expires_at FROM poll_lease WHERE id=1").fetchone()
        if row is None:
            c.execute("INSERT INTO poll_lease(id,holder,expires_at) VALUES(1,?,?)",
                      (_LEASE_ID, now + POLL_LEASE_TTL))
            return True
        # Renew ours, or reclaim an EXPIRED one. Both are guarded in the WHERE clause so the
        # claim is atomic under SQLite's write lock — a simultaneous second process either
        # sees a live lease (and stands down) or loses this UPDATE race and re-reads.
        c.execute("UPDATE poll_lease SET holder=?, expires_at=? "
                  "WHERE id=1 AND (holder=? OR expires_at<=?)",
                  (_LEASE_ID, now + POLL_LEASE_TTL, _LEASE_ID, now))
        got = c.execute("SELECT holder FROM poll_lease WHERE id=1").fetchone()["holder"]
        return got == _LEASE_ID         # False => another LIVE process holds it; stand down


def release_poll_lease():
    """Hand the poll lease back on a clean shutdown.

    Without this the lease is only freed by EXPIRY, so every deploy leaves the dying
    process's claim sitting in the table and the incoming process stands down until it
    times out — a measured ~181 seconds of no polling on each deploy, during which no
    seat alert can fire for anyone. Restarts are the one moment we control completely,
    so paying 181s of blindness for them is pure waste.

    Guarded on holder: if another process already took the lease (ours expired first),
    this must delete nothing rather than evicting the live poller.
    """
    try:
        with db() as c:
            c.execute("DELETE FROM poll_lease WHERE id=1 AND holder=?", (_LEASE_ID,))
        sw.log("[lease] released on shutdown — successor can poll immediately")
    except Exception as e:
        sw.log(f"[lease] release on shutdown failed: {type(e).__name__}")


FEEDBACK_RETRY_SECS = 600          # sweep the unsent-feedback backlog at most every 10 min
_feedback_retry_at = [0.0]


def retry_unsent_feedback():
    """Deliver feedback that was stored but never emailed.

    Feedback is PERSISTED before it is emailed, so a student's message is never lost — but
    nothing retried a failed send, so a message could sit unread indefinitely. That is not
    hypothetical: feedback #1-#3 sat in the table for a day because SMTP had not been
    configured yet, and only a manual sweep surfaced them. Two of the three were people
    asking how to pay. This drains the backlog on its own the moment mail starts working.

    Throttled, capped, and it stops at the first failure rather than hammering a mail
    server that is still down. Never raises: a mail problem must not slow or stop polling.
    """
    if not EMAIL_ENABLED:
        return
    now = time.time()
    if now < _feedback_retry_at[0]:
        return
    _feedback_retry_at[0] = now + FEEDBACK_RETRY_SECS
    try:
        with db() as c:
            rows = c.execute("SELECT id, user_id, email, message FROM feedback "
                             "WHERE emailed_at IS NULL ORDER BY id LIMIT 20").fetchall()
        for r in rows:
            ok = send_email(SUPPORT_EMAIL,
                            f"SeatWatch feedback #{r['id']} from {r['email']}",
                            f"From: {r['email']} (user {r['user_id']})\n\n{r['message']}",
                            BASE_URL or "https://seatwatchapp.com/")
            if not ok:
                break              # still down: leave the rest queued for the next sweep
            with db() as c:
                c.execute("UPDATE feedback SET emailed_at=? WHERE id=?",
                          (time.time(), r["id"]))
            sw.log(f"  [feedback] #{r['id']} delivered on retry")
    except Exception as e:
        sw.log(f"  [feedback] retry sweep failed: {type(e).__name__}")


# KILL SWITCH — default OFF. Nathan discontinued the 7-day $5 offer on 2026-08-19: with
# five non-family accounts and one activated user, a discount on extra capacity reaches
# nobody who has hit the free limit yet, and it spends the single marketing email you get
# per student at the wrong moment. Everything else stays built and tested: the Stripe
# coupon, the per-student code minting, the tier lock, the preference check. Set
# PROMO_ENABLED=1 in /etc/seatwatch.env and restart to resume.
#
# Re-enabling sends to EVERY eligible student at once (promo_sent_at is still NULL for
# them, capped at 50 per sweep) — which is what you want for a timed campaign, but know
# it is a batch, not a trickle.
PROMO_ENABLED = os.environ.get("PROMO_ENABLED") == "1"
PROMO_CODE = os.environ.get("PROMO_CODE", "SEATWATCH5")
PROMO_AFTER_DAYS = int(os.environ.get("PROMO_AFTER_DAYS", "7"))
PROMO_SWEEP_SECS = 3600            # look for eligible students at most once an hour
_promo_sweep_at = [0.0]


def send_promo_emails():
    """Offer $5 off to students who have been here a week and have not bought anything.

    Gated on PAID_ENABLED for a reason that is not technical: a promotional code that leads
    to a page saying "Coming soon" is worse than sending nothing at all. It burns the one
    moment a student is thinking about paying, and it reads as a company that does not
    have its act together. So this stays silent until there is something to buy.

    promo_sent_at makes it strictly once per student — a restart, a double sweep or two
    pollers racing can never mail the same person twice. Never raises: a marketing job
    must not be able to interfere with seat alerts.
    """
    if not (PROMO_ENABLED and PAID_ENABLED and EMAIL_ENABLED):
        return 0
    now = time.time()
    if now < _promo_sweep_at[0]:
        return 0
    _promo_sweep_at[0] = now + PROMO_SWEEP_SECS
    sent = 0
    try:
        cutoff = now - PROMO_AFTER_DAYS * 86400
        with db() as c:
            rows = c.execute(
                "SELECT id, email FROM users WHERE promo_sent_at IS NULL AND created < ? "
                "AND email IS NOT NULL AND email != '' AND COALESCE(plan_tier,0) < 1 "
                "ORDER BY created LIMIT 50", (cutoff,)).fetchall()
        for u in rows:
            # "If they choose not to get email, are you sure they never get email?" — they
            # did not, until this line. The promo queried users directly and never consulted
            # the preference, so someone who unchecked Email would still have received it.
            # A preference that holds for alerts but not for marketing is not a preference.
            if not notify_prefs(u["id"])[1]:
                with db() as c:            # stamp so the sweep does not reconsider them daily
                    c.execute("UPDATE users SET promo_sent_at=? WHERE id=?",
                              (time.time(), u["id"]))
                continue
            # Mint the code IN STRIPE first. If Stripe refuses, send NOTHING: a code that
            # Stripe will reject reaches the student at the exact moment they have decided
            # to pay, and tells them the company is broken. Reuse an existing code on a
            # retry rather than minting a second one for the same person.
            with db() as c:
                row = c.execute("SELECT promo_code FROM users WHERE id=?", (u["id"],)).fetchone()
            code = row["promo_code"] if row and row["promo_code"] else issue_promo_code(u["id"])
            if not code:
                continue                    # leave promo_sent_at NULL: retry next sweep
            base = BASE_URL or "https://seatwatchapp.com"
            price = f"${PROMO_PRICE_CENTS / 100:.2f}"
            body = (
                f"You have been watching classes with SeatWatch for a week.\n\n"
                f"Here is your code for $5 off the {TIER_NAME[PROMO_TIER]} plan:\n\n"
                f"    {code}\n\n"
                f"It brings that plan to {price} instead of "
                f"${TIER_PRICE_CENTS[PROMO_TIER] / 100:.2f}.\n\n"
                f"Go straight to the payment page:\n\n"
                f"    {base}/checkout?tier={PROMO_TIER}\n\n"
                f"On that page, click 'Add promotion code', type the 8 digits above, and "
                f"the total becomes {price}.\n\n"
                f"The code is yours alone and works once. It applies to the "
                f"{TIER_NAME[PROMO_TIER]} plan only.\n\n"
                f"If the free plan is doing the job, ignore this. It keeps working either "
                f"way, and we will keep watching your class.\n\n— SeatWatch")
            ok = send_email(u["email"], "Your code for $5 off, if you need more classes",
                            body, f"{base}/checkout?tier={PROMO_TIER}")
            # Stamp on ATTEMPT. Retrying a marketing email until it succeeds is how people
            # end up receiving it four times; one honest attempt each is the right trade.
            with db() as c:
                c.execute("UPDATE users SET promo_sent_at=? WHERE id=?", (time.time(), u["id"]))
            sent += bool(ok)
        if sent:
            sw.log(f"  [promo] personal codes issued to {sent} student(s)")
    except Exception as e:
        sw.log(f"  [promo] sweep failed: {type(e).__name__}")
    return sent


def poller():
    sw.log("Poller started (with health guard).")
    if os.environ.get("AUTO_ROLL_TERMS") != "1":
        sw.log("[term] daily auto-roll DISARMED (AUTO_ROLL_TERMS != 1): terms hold at "
               "last-known-good; semester boundaries need a manual pin bump. Fail-closed "
               "default — a roll against a stale watch stamp silently kills watches.")
    last_term_refresh = 0.0
    while True:
        try:
            # Self-maintenance: auto-roll schools to the new semester once/day, in the
            # background so it never blocks polling (verify-before-adopt inside). The
            # WHOLE job is env-gated OFF by default: with stamped watches live, a term
            # roll must be a deliberate operator act, never a scheduled surprise.
            if (os.environ.get("AUTO_ROLL_TERMS") == "1"
                    and time.time() - last_term_refresh > 86400):
                last_term_refresh = time.time()
                threading.Thread(target=schools.refresh_all_terms,
                                 kwargs={"log": sw.log}, daemon=True).start()
            if not acquire_poll_lease():
                # Another live process is polling. Standing down prevents DUPLICATE alerts
                # (we alert inline). Logged once per stand-down so it's diagnosable, and we
                # keep looping: if that holder dies, its lease expires and we take over.
                if not _stood_down[0]:
                    _stood_down[0] = True
                    sw.log("[lease] another poller holds the lease — standing down to avoid "
                           "duplicate alerts (will take over if it stops)")
                time.sleep(POLL_SECONDS)
                continue
            if _stood_down[0]:
                # Taking over was silent, so a stood-down log line with nothing after it
                # read as "the poller is dead" during an incident. Say when we take over.
                sw.log("[lease] took over the lease — this process is now polling")
            _stood_down[0] = False
            cyc = run_cycle()
            if guardian.ping_ok(cyc):   # enforce: only a reconciled, non-RED cycle may
                ping_healthcheck()      # claim success; off/shadow: semantics unchanged
            maybe_daily_summary()
            retry_unsent_feedback()     # drain any feedback that failed to email
            send_promo_emails()         # 7-day $5-off nudge (dormant until paid)
            run_fire_drill()
        except Exception as e:
            sw.log(f"[poller error, recovering] {e}")
            guardian.poller_recover(e)  # evidence + damped page, not a 20s page storm
        time.sleep(POLL_SECONDS)


def main():
    init_db()
    guardian.TUNING["POLL_S"] = POLL_SECONDS
    guardian.configure(db, lambda k, d=None: _load_state().get(k, d), _save_state,
                       sw.log, operator_alert,
                       mode=os.environ.get("GUARDIAN_MODE", "shadow"),
                       deploy_sha=os.environ.get("SEATWATCH_DEPLOY_SHA", ""))
    # systemd sends SIGTERM on restart/stop. Release the lease so the successor polls
    # straight away instead of standing down for the full TTL.
    def _shutdown(signum, _frame):
        sw.log(f"[shutdown] signal {signum} — releasing poll lease")
        release_poll_lease()
        raise SystemExit(0)
    for _sig in (signal.SIGTERM, signal.SIGINT):
        try:
            signal.signal(_sig, _shutdown)
        except (ValueError, OSError):
            pass                     # not the main thread / unsupported: expiry still frees it
    threading.Thread(target=poller, daemon=True).start()
    server = ThreadingHTTPServer(("0.0.0.0", PORT), Handler)
    sw.log(f"SeatWatch web app on http://localhost:{PORT}  (term {sw.TERM})")
    server.serve_forever()


if __name__ == "__main__":
    main()
