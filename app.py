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
import sqlite3
import threading
import smtplib
import ssl
import time
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from email.message import EmailMessage
from email.utils import formataddr
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlencode, urlparse

import seatwatch as sw  # reuse: notify, log
import schools          # multi-school registry (UMD, Rutgers, ...)

try:                    # real Web Push (VAPID) — installed on the server; optional locally
    from pywebpush import webpush, WebPushException
except ImportError:     # missing lib -> push features quietly disabled, everything else runs
    webpush, WebPushException = None, Exception

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
DEV_LOGIN = os.environ.get("SEATWATCH_DEV") == "1"   # local testing only, never set in prod
# Web Push (VAPID). Keys live on the server; page gets ONLY the public key.
VAPID_PUBLIC_KEY = os.environ.get("VAPID_PUBLIC_KEY", "")
VAPID_PRIVATE_PEM = os.environ.get("VAPID_PRIVATE_PEM", os.path.join(HERE, "vapid_private.pem"))
VAPID_SUBJECT = os.environ.get("VAPID_SUBJECT", "mailto:support@seatwatchapp.com")
PUSH_ENABLED = bool(VAPID_PUBLIC_KEY and webpush)
# --- Email alerts (the zero-setup default channel). SMTP creds come from the server env
# and work with any provider — Gmail app-password, Resend, SES, etc. If unset, email is
# quietly disabled and nothing breaks (push/ntfy still run). ---
SMTP_HOST = os.environ.get("SMTP_HOST", "")
SMTP_PORT = int(os.environ.get("SMTP_PORT", "587"))
SMTP_USER = os.environ.get("SMTP_USER", "")
SMTP_PASS = os.environ.get("SMTP_PASS", "")
SMTP_FROM = os.environ.get("SMTP_FROM", SMTP_USER)   # the visible "from" address
EMAIL_ENABLED = bool(SMTP_HOST and SMTP_USER and SMTP_PASS)
SESSION_DAYS = 90
FREE_COURSES = 1                # per account: 1 free class (ALL of its sections)
FREE_SECTIONS_PER_COURSE = 25   # generous anti-abuse guard, NOT a pricing limit —
                                # the free class includes every section you want
PLAN_MSG = ("Your free plan covers 1 class — all of its sections. Stop watching "
            "your current class below to switch, or grab more classes when paid "
            "plans launch ($19.95 per additional course, all sections included).")

# --- operator guard (so the system watches itself and pings YOU, not the users) ---
OPERATOR_TOPIC = os.environ.get("SEATWATCH_ADMIN_TOPIC", "seatwatch-admin-q7x2k9m4")
HEALTHCHECK_URL = os.environ.get("HEALTHCHECK_URL", "")
FAIL_THRESHOLD = int(os.environ.get("FAIL_THRESHOLD", "5"))
SUMMARY_EVERY_HOURS = 24
DRILL_EVERY_HOURS = 168        # automated end-to-end fire drill, weekly
# Reliable, always-on schools to drill against (rotated through until one delivers).
DRILL_SCHOOLS = ["umd", "gatech", "utsa", "usf", "vcu", "txst", "memphis"]

# --- input hardening / abuse protection ---
COURSE_RE = re.compile(r"^[A-Z]{2,4}\d{3,4}[A-Z]?$")   # e.g. ENG101, MATH140, BIOL2020
SECTION_RE = re.compile(r"^[A-Z0-9]{1,20}$")            # 0101, FC01, 83510, LEC002LAB324
_RATE = {}                                             # ip -> [timestamps]
RATE_MAX, RATE_WINDOW = 15, 3600                       # max 15 submissions / IP / hour


def rate_ok(ip):
    now = time.time()
    if len(_RATE) > 5000:  # prune stale IPs so memory can't grow forever
        for k in [k for k, v in _RATE.items() if not v or now - v[-1] > RATE_WINDOW]:
            _RATE.pop(k, None)
    keep = [t for t in _RATE.get(ip, []) if now - t < RATE_WINDOW]
    keep.append(now)
    _RATE[ip] = keep
    return len(keep) <= RATE_MAX


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
        c.execute("""CREATE TABLE IF NOT EXISTS push_subs(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id  INTEGER NOT NULL,
            endpoint TEXT NOT NULL UNIQUE,     -- one row per device/browser
            p256dh   TEXT NOT NULL,
            auth     TEXT NOT NULL,
            created  REAL NOT NULL)""")


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


def get_or_create_user(sub, email):
    with db() as c:
        row = c.execute("SELECT * FROM users WHERE google_sub=?", (sub,)).fetchone()
        if row:
            if email and row["email"] != email:
                c.execute("UPDATE users SET email=? WHERE id=?", (email, row["id"]))
            return row
        c.execute("INSERT INTO users(google_sub,email,topic,created) VALUES(?,?,?,?)",
                  (sub, email, "seatwatch-" + secrets.token_hex(6), time.time()))
        return c.execute("SELECT * FROM users WHERE google_sub=?", (sub,)).fetchone()


# ------------------------------------------------------------------------- html
PAGE = """<!doctype html><html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>SeatWatch — Get a text the second a full class opens | 375 universities</title>
<meta name="description" content="SeatWatch alerts you the instant a seat opens in a full college class, across 375 universities. Watch the exact section you want and get the professor you want. Free to start.">
<link rel="canonical" href="https://seatwatchapp.com/">
<meta name="robots" content="index, follow, max-image-preview:large">
<meta name="keywords" content="seatwatch, seat watch, course seat alert, class seat notification, college registration alert, open seat finder, coursicle alternative">
<meta name="author" content="SeatWatch LLC">
<meta name="application-name" content="SeatWatch">
<meta property="og:type" content="website">
<meta property="og:site_name" content="SeatWatch">
<meta property="og:title" content="SeatWatch — Get into the class you actually need">
<meta property="og:description" content="Get an instant alert the second a seat opens in a full college class — across 375 universities. Watch the exact section, get the professor you want.">
<meta property="og:url" content="https://seatwatchapp.com/">
<meta property="og:image" content="https://seatwatchapp.com/og-image.png">
<meta property="og:image:width" content="1200">
<meta property="og:image:height" content="630">
<meta name="twitter:card" content="summary_large_image">
<meta name="twitter:title" content="SeatWatch — Get into the class you actually need">
<meta name="twitter:description" content="Get an instant alert the second a seat opens in a full college class. 375 universities. Free to start.">
<meta name="twitter:image" content="https://seatwatchapp.com/og-image.png">
<script type="application/ld+json">{"@context":"https://schema.org","@graph":[{"@type":"Organization","@id":"https://seatwatchapp.com/#org","name":"SeatWatch","legalName":"SeatWatch LLC","url":"https://seatwatchapp.com/","logo":"https://seatwatchapp.com/icon-512.png","email":"support@seatwatchapp.com","description":"Instant alerts when a seat opens in a full college class, across 375 universities."},{"@type":"WebSite","@id":"https://seatwatchapp.com/#site","url":"https://seatwatchapp.com/","name":"SeatWatch","publisher":{"@id":"https://seatwatchapp.com/#org"}},{"@type":"WebApplication","name":"SeatWatch","url":"https://seatwatchapp.com/","applicationCategory":"EducationalApplication","operatingSystem":"Web","offers":{"@type":"Offer","price":"0","priceCurrency":"USD","description":"First class free"},"description":"Get an instant phone alert the second a seat opens in a full college class."}]}</script>
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
 body::before{content:"";position:fixed;inset:0;z-index:-2;background-image:linear-gradient(var(--line) 1px,transparent 1px),linear-gradient(90deg,var(--line) 1px,transparent 1px);background-size:48px 48px;opacity:.5;-webkit-mask-image:radial-gradient(680px 520px at 50% -40px,#000,transparent 72%);mask-image:radial-gradient(680px 520px at 50% -40px,#000,transparent 72%)}
 body::after{content:"";position:fixed;inset:0;z-index:-1;background:radial-gradient(720px 440px at 50% -130px,rgba(37,99,235,.12),transparent 68%),radial-gradient(600px 400px at 88% 8%,rgba(16,185,129,.05),transparent 60%)}
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
 .pushbtn{background:linear-gradient(135deg,#2563EB,#3B82F6)}
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
 .prices{display:grid;gap:14px;grid-template-columns:1fr 1fr}
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
 .iosHint{display:none;background:var(--tint);border:1px solid #C7D2FE;border-radius:13px;padding:15px;font-size:13.5px;line-height:1.65;color:#1E3A5F;margin-top:10px}
 .tnum{flex:none;width:22px;height:22px;border-radius:50%;background:var(--blue);color:#fff;font-size:12px;font-weight:700;display:flex;align-items:center;justify-content:center}
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
<footer><span class="tagline">We watch seats. <em>You get the class.</em></span><br>© 2026 SeatWatch &nbsp;·&nbsp; <a href="/terms">Terms</a> &nbsp;·&nbsp; <a href="/privacy">Privacy</a><br>Not affiliated with any university.</footer>
</body></html>"""

FORM = """<section class="hero">
 <div class="badge reveal"><span class="dotlive"></span>LIVE — WATCHING 375 UNIVERSITIES</div>
 <h1 class="reveal d1">Get into the class you <span class="grad">actually need</span>.</h1>
 <p class="lede reveal d2">That full class you're stuck on? We watch it around the clock and buzz your phone the instant a seat opens — free to start, and we never show fake openings.</p>
 <div class="notif reveal d3" aria-hidden="true"><svg class="nicon" viewBox="0 0 120 120" xmlns="http://www.w3.org/2000/svg"><path d="M40 14 H80 Q104 14 104 38 V72 Q104 96 80 96 H64 L54 110 L49 96 H36 Q12 96 12 72 V38 Q12 14 36 14 Z" fill="#fff" stroke="#2563eb" stroke-width="9" stroke-linejoin="round"/><rect x="42" y="32" width="28" height="24" rx="7" fill="url(#b)"/><rect x="38" y="56" width="40" height="11" rx="5.5" fill="url(#b)"/><rect x="42" y="67" width="8" height="15" rx="3" fill="url(#b)"/><rect x="66" y="67" width="8" height="15" rx="3" fill="url(#b)"/><circle cx="100" cy="20" r="11" fill="#10b981" stroke="#fff" stroke-width="5"/></svg><div class="nbody"><div class="nrow"><b>SeatWatch</b><span class="live"><svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="3" stroke-linecap="round" stroke-linejoin="round"><polyline points="20 6 9 17 4 12"/></svg>now</span></div><p>Seat open: <b>ENG101-0101</b> — 2 seats just opened. Tap to register!</p></div></div>
 <div class="stats reveal d4">
  <div class="stat"><div class="chip"><svg width="19" height="19" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M21.42 10.922a1 1 0 0 0-.019-1.838L12.83 5.18a2 2 0 0 0-1.66 0L2.6 9.08a1 1 0 0 0 0 1.832l8.57 3.908a2 2 0 0 0 1.66 0z"/><path d="M22 10v6"/><path d="M6 12.5V16a6 3 0 0 0 12 0v-3.5"/></svg></div><b data-count="375">375</b><span>universities</span></div>
  <div class="stat"><div class="chip"><svg width="19" height="19" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="10"/><polyline points="12 6 12 12 16 14"/></svg></div><b>20s</b><span>check interval</span></div>
  <div class="stat"><div class="chip"><svg width="19" height="19" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M19.07 4.93A10 10 0 0 0 6.99 3.34"/><path d="M4 6h.01"/><path d="M2.29 9.62A10 10 0 1 0 21.31 8.35"/><path d="M16.24 7.76A6 6 0 1 0 8.23 16.67"/><path d="M12 18h.01"/><path d="M17.99 11.66A6 6 0 0 1 15.77 16.67"/><circle cx="12" cy="12" r="2"/><path d="m13.41 10.59 5.66-5.66"/></svg></div><b>24/7</b><span>monitoring</span></div>
 </div>
</section>
__CARD__
<section class="blk sr">
 <h2>Get the professor you want.</h2>
 <p class="lede2">Stuck out of the class — or the exact section — you were hoping for? SeatWatch watches the <b>specific section you pick</b>, so you land the <b>professor, time, and class</b> you actually want the moment a seat opens up. Not just any seat — <em>your</em> seat.</p>
</section>
<section class="blk sr">
 <h2>How it works</h2>
 <p class="lede2">Three steps between you and the class you need.</p>
 <div class="steps">
  <div class="step"><div class="chip"><svg width="19" height="19" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="11" cy="11" r="8"/><path d="m21 21-4.3-4.3"/></svg></div><div><b>Tell us your class</b><span>Pick your school, the course, and the section(s) you want to watch.</span></div></div>
  <div class="step"><div class="chip"><svg width="19" height="19" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M2 12a10 10 0 0 1 10-10"/><path d="M2 12a10 10 0 0 0 10 10"/><path d="M12 2a10 10 0 0 1 10 10"/><circle cx="12" cy="12" r="3"/></svg></div><div><b>We watch it around the clock</b><span>Our engine checks the live registration site every 20 seconds — fast and accurate.</span></div></div>
  <div class="step"><div class="chip"><svg width="19" height="19" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M10.268 21a2 2 0 0 0 3.464 0"/><path d="M3.262 15.326A1 1 0 0 0 4 17h16a1 1 0 0 0 .74-1.673C19.41 13.956 18 12.499 18 8A6 6 0 0 0 6 8c0 4.499-1.411 5.956-2.738 7.326"/></svg></div><div><b>Your phone buzzes instantly</b><span>The second a real seat opens, you get a push alert. Tap it and go register.</span></div></div>
 </div>
</section>
<section class="blk sr">
 <h2>Students get their class back.</h2>
 <p class="lede2">The seat you need can open at 2am. We're the ones watching so you don't have to.</p>
 <div class="quotes">
  <div class="quote"><div class="stars"><svg width="14" height="14" viewBox="0 0 24 24" fill="currentColor"><path d="M12 2l2.9 6.3 6.9.7-5.1 4.6 1.4 6.8L12 17.8 5.9 20.4l1.4-6.8L2.2 9l6.9-.7z"/></svg><svg width="14" height="14" viewBox="0 0 24 24" fill="currentColor"><path d="M12 2l2.9 6.3 6.9.7-5.1 4.6 1.4 6.8L12 17.8 5.9 20.4l1.4-6.8L2.2 9l6.9-.7z"/></svg><svg width="14" height="14" viewBox="0 0 24 24" fill="currentColor"><path d="M12 2l2.9 6.3 6.9.7-5.1 4.6 1.4 6.8L12 17.8 5.9 20.4l1.4-6.8L2.2 9l6.9-.7z"/></svg><svg width="14" height="14" viewBox="0 0 24 24" fill="currentColor"><path d="M12 2l2.9 6.3 6.9.7-5.1 4.6 1.4 6.8L12 17.8 5.9 20.4l1.4-6.8L2.2 9l6.9-.7z"/></svg><svg width="14" height="14" viewBox="0 0 24 24" fill="currentColor"><path d="M12 2l2.9 6.3 6.9.7-5.1 4.6 1.4 6.8L12 17.8 5.9 20.4l1.4-6.8L2.2 9l6.9-.7z"/></svg></div><p>"I'd refreshed the registration page for a week. SeatWatch texted me at 7am, I tapped it, and I was in. Genuinely saved my semester."</p><div class="who"><span class="av" style="background:linear-gradient(135deg,#2563EB,#3B82F6)">MR</span><div><div class="nm">Maya R.</div><div class="mt">Junior · Computer Science</div></div></div></div>
  <div class="quote"><div class="stars"><svg width="14" height="14" viewBox="0 0 24 24" fill="currentColor"><path d="M12 2l2.9 6.3 6.9.7-5.1 4.6 1.4 6.8L12 17.8 5.9 20.4l1.4-6.8L2.2 9l6.9-.7z"/></svg><svg width="14" height="14" viewBox="0 0 24 24" fill="currentColor"><path d="M12 2l2.9 6.3 6.9.7-5.1 4.6 1.4 6.8L12 17.8 5.9 20.4l1.4-6.8L2.2 9l6.9-.7z"/></svg><svg width="14" height="14" viewBox="0 0 24 24" fill="currentColor"><path d="M12 2l2.9 6.3 6.9.7-5.1 4.6 1.4 6.8L12 17.8 5.9 20.4l1.4-6.8L2.2 9l6.9-.7z"/></svg><svg width="14" height="14" viewBox="0 0 24 24" fill="currentColor"><path d="M12 2l2.9 6.3 6.9.7-5.1 4.6 1.4 6.8L12 17.8 5.9 20.4l1.4-6.8L2.2 9l6.9-.7z"/></svg><svg width="14" height="14" viewBox="0 0 24 24" fill="currentColor"><path d="M12 2l2.9 6.3 6.9.7-5.1 4.6 1.4 6.8L12 17.8 5.9 20.4l1.4-6.8L2.2 9l6.9-.7z"/></svg></div><p>"Needed one specific section to keep my work schedule. It watched that exact one and pinged me the second it opened. No more all-nighters refreshing."</p><div class="who"><span class="av" style="background:linear-gradient(135deg,#059669,#10B981)">JT</span><div><div class="nm">Jordan T.</div><div class="mt">Sophomore · Nursing</div></div></div></div>
  <div class="quote"><div class="stars"><svg width="14" height="14" viewBox="0 0 24 24" fill="currentColor"><path d="M12 2l2.9 6.3 6.9.7-5.1 4.6 1.4 6.8L12 17.8 5.9 20.4l1.4-6.8L2.2 9l6.9-.7z"/></svg><svg width="14" height="14" viewBox="0 0 24 24" fill="currentColor"><path d="M12 2l2.9 6.3 6.9.7-5.1 4.6 1.4 6.8L12 17.8 5.9 20.4l1.4-6.8L2.2 9l6.9-.7z"/></svg><svg width="14" height="14" viewBox="0 0 24 24" fill="currentColor"><path d="M12 2l2.9 6.3 6.9.7-5.1 4.6 1.4 6.8L12 17.8 5.9 20.4l1.4-6.8L2.2 9l6.9-.7z"/></svg><svg width="14" height="14" viewBox="0 0 24 24" fill="currentColor"><path d="M12 2l2.9 6.3 6.9.7-5.1 4.6 1.4 6.8L12 17.8 5.9 20.4l1.4-6.8L2.2 9l6.9-.7z"/></svg><svg width="14" height="14" viewBox="0 0 24 24" fill="currentColor"><path d="M12 2l2.9 6.3 6.9.7-5.1 4.6 1.4 6.8L12 17.8 5.9 20.4l1.4-6.8L2.2 9l6.9-.7z"/></svg></div><p>"The class I needed to graduate on time was full all summer. Got the alert in August, registered from my phone in the dining hall. Unreal."</p><div class="who"><span class="av" style="background:linear-gradient(135deg,#7C3AED,#A855F7)">DK</span><div><div class="nm">Devin K.</div><div class="mt">Senior · Business</div></div></div></div>
 </div>
</section>
<section class="blk sr">
 <h2>Simple, fair pricing</h2>
 <p class="lede2">Start free. Upgrade only if you need more.</p>
 <div class="prices">
  <div class="price free"><span class="tag">Start free</span><p class="amt">$0 <small>first class</small></p>
   <ul class="feat">
    <li><svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"><path d="M20 6 9 17l-5-5"/></svg>Your first class — completely free</li>
    <li><svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"><path d="M20 6 9 17l-5-5"/></svg>Instant phone alerts</li>
    <li><svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"><path d="M20 6 9 17l-5-5"/></svg>Never fake — real seats only</li>
    <li><svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"><path d="M20 6 9 17l-5-5"/></svg>No card required</li>
   </ul>
  </div>
  <div class="price"><span class="tag soon">Coming soon</span><p class="amt">$19.95 <small>per additional course</small></p>
   <ul class="feat">
    <li><svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"><path d="M20 6 9 17l-5-5"/></svg><b>Includes all sections</b> of the course</li>
   </ul>
  </div>
 </div>
</section>
<section class="blk sr">
 <h2>Questions, answered.</h2>
 <p class="lede2">The stuff students actually ask us.</p>
 <div class="faq">
  <details><summary>Is it really free?<span class="pm">+</span></summary><p>Yes. Your first class — up to two sections — is completely free, forever. No credit card, no trial clock. We only ask you to sign in so your watch stays tied to you.</p></details>
  <details><summary>How fast will I hear about an open seat?<span class="pm">+</span></summary><p>We check your class's live registration system every 20 seconds, around the clock. The instant a real seat appears, your phone gets a push alert — usually within seconds of it opening.</p></details>
  <details><summary>Will you ever send a fake alert?<span class="pm">+</span></summary><p>Never. We read the true seat count straight from your school's registration system and only alert on a genuinely open seat. If our engine can't confirm a seat is really open, it stays silent — no false alarms.</p></details>
  <details><summary>Can I watch a specific section or professor?<span class="pm">+</span></summary><p>That's the whole point. You pick the exact section(s) you want, so you land the professor, time, and class you're actually after — not just any open seat.</p></details>
  <details><summary>Is my school supported?<span class="pm">+</span></summary><p>We watch classes at <b data-count2="375">375</b> universities and colleges, and we're adding more every week. Start typing your school in the box above — if it's there, you're good to go.</p></details>
  <details><summary>Is this against my school's rules?<span class="pm">+</span></summary><p>No. SeatWatch only reads the same public class-availability info you'd see yourself — it never logs into your account or registers for you. When a seat opens, <i>you</i> tap the alert and register, just like normal.</p></details>
 </div>
</section>
<section class="blk sr">
 <div class="cta">
  <h2>Your seat is out there.</h2>
  <p>Let us watch for it. Set up your first class free in under a minute — and get on with your day.</p>
  <a class="cbtn" href="/login">Start watching free<svg width="17" height="17" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.4" stroke-linecap="round" stroke-linejoin="round"><path d="M5 12h14"/><path d="m12 5 7 7-7 7"/></svg></a>
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
<p class="cs">Sign in so your watches stay yours — one click, no password, no spam ever.</p>
<a class="gbtn" href="/login"><svg width="18" height="18" viewBox="0 0 48 48"><path fill="#EA4335" d="M24 9.5c3.54 0 6.71 1.22 9.21 3.6l6.85-6.85C35.9 2.38 30.47 0 24 0 14.62 0 6.51 5.38 2.56 13.22l7.98 6.19C12.43 13.72 17.74 9.5 24 9.5z"/><path fill="#4285F4" d="M46.98 24.55c0-1.57-.15-3.09-.38-4.55H24v9.02h12.94c-.58 2.96-2.26 5.48-4.78 7.18l7.73 6c4.51-4.18 7.09-10.36 7.09-17.65z"/><path fill="#FBBC05" d="M10.53 28.59c-.48-1.45-.76-2.99-.76-4.59s.27-3.14.76-4.59l-7.98-6.19C.92 16.46 0 20.12 0 24c0 3.88.92 7.54 2.56 10.78l7.97-6.19z"/><path fill="#34A853" d="M24 48c6.48 0 11.93-2.13 15.89-5.81l-7.73-6c-2.15 1.45-4.92 2.3-8.16 2.3-6.26 0-11.57-4.22-13.47-9.91l-7.98 6.19C6.51 42.62 14.62 48 24 48z"/></svg>Continue with Google</a>
<p class="note">Free: watch <b>1 class (up to 2 sections)</b>. No card required.</p>
</div>"""

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
 <label>Section number(s) <small>— up to 2, comma-separated</small></label>
 <input name="sections" placeholder="e.g. 0101, 0102" required>
 <button type="submit">Watch this class<svg width="17" height="17" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round"><path d="M5 12h14"/><path d="m12 5 7 7-7 7"/></svg></button>
</form>
<p class="note">Free plan: <b>1 class, up to 2 sections</b>. We only watch what you ask for.</p>
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
    "start_url": "/", "display": "standalone",
    "background_color": "#F8FAFC", "theme_color": "#2563EB",
    "icons": [{"src": "/icon-192.png", "sizes": "192x192", "type": "image/png"},
              {"src": "/icon-512.png", "sizes": "512x512", "type": "image/png",
               "purpose": "any maskable"}]})


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

# The one-tap alert setup. Shown on the success page and the signed-in card.
PUSH_BLOCK = """<div style="margin-top:18px;border-top:1px solid #F3F4F6;padding-top:16px">
 <button type="button" id="pushBtn" class="pushbtn" style="margin-top:0"><svg width="17" height="17" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M10.268 21a2 2 0 0 0 3.464 0"/><path d="M3.262 15.326A1 1 0 0 0 4 17h16a1 1 0 0 0 .74-1.673C19.41 13.956 18 12.499 18 8A6 6 0 0 0 6 8c0 4.499-1.411 5.956-2.738 7.326"/></svg>Turn on phone alerts</button>
 <p class="note" id="pushStatus">One tap — alerts come straight to this device. No app to install.</p>
 <div id="iosHint" class="iosHint">
  <b style="display:block;font-size:14px;margin-bottom:12px;color:#1E3A5F">📲 On iPhone? Turn on alerts in 3 quick steps <span style="font-weight:500;color:#4B6B9A">(about 15 seconds)</span>:</b>
  <div style="display:flex;gap:11px;align-items:flex-start;margin-bottom:12px">
   <span class="tnum">1</span>
   <div style="font-size:13.5px;line-height:1.5;color:#1E3A5F">Tap the <b>Share</b> icon <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" style="display:inline;vertical-align:-2px"><path d="M4 12v8a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2v-8"/><polyline points="16 6 12 2 8 6"/><line x1="12" y1="2" x2="12" y2="15"/></svg> at the bottom of Safari (the box with an up-arrow).</div>
  </div>
  <div style="display:flex;gap:11px;align-items:flex-start;margin-bottom:12px">
   <span class="tnum">2</span>
   <div style="font-size:13.5px;line-height:1.5;color:#1E3A5F">Scroll down and tap <b>Add to Home Screen</b>, then tap <b>Add</b> in the top corner.</div>
  </div>
  <div style="display:flex;gap:11px;align-items:flex-start">
   <span class="tnum">3</span>
   <div style="font-size:13.5px;line-height:1.5;color:#1E3A5F">Open <b>SeatWatch</b> from your Home Screen and tap <b>Turn on phone alerts</b>. That's it — you're covered. ✅</div>
  </div>
 </div>
</div>
<script>
(function(){
var PUSH_CSRF="__CSRF__",VAPID_PK="__VAPIDPK__";
var btn=document.getElementById('pushBtn'),st=document.getElementById('pushStatus'),ios=document.getElementById('iosHint');
if(!btn||!VAPID_PK)return;
function s(m){st.textContent=m;}
var isIOS=/iphone|ipad|ipod/i.test(navigator.userAgent);
var standalone=(window.matchMedia&&matchMedia('(display-mode: standalone)').matches)||window.navigator.standalone;
function b64(u){var p='='.repeat((4-u.length%4)%4);var b=atob((u+p).replace(/-/g,'+').replace(/_/g,'/'));var a=new Uint8Array(b.length);for(var i=0;i<b.length;i++)a[i]=b.charCodeAt(i);return a;}
// iPhone-in-Safari: push physically can't turn on until the site is added to the Home Screen
// (an Apple rule we can't change). So show the steps upfront and hide the button that would
// only dead-end here — no guessing, nothing to discover, nobody gets stuck.
if(isIOS&&!standalone){
  ios.style.display='block';
  btn.style.display='none';
  s('Follow the 3 steps below to get alerts on your iPhone:');
  return;
}
if(!('serviceWorker' in navigator)||!('PushManager' in window)){
  s('This browser does not support push — try Chrome or Safari 16.4+.');btn.disabled=true;return;
}
btn.onclick=async function(){
  try{
    var reg=await navigator.serviceWorker.register('/sw.js');
    var perm=await Notification.requestPermission();
    if(perm!=='granted'){s('Notifications are blocked — allow them for seatwatchapp.com in settings, then retry.');return;}
    var sub=await reg.pushManager.subscribe({userVisibleOnly:true,applicationServerKey:b64(VAPID_PK)});
    var r=await fetch('/push/subscribe',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({csrf:PUSH_CSRF,sub:sub.toJSON()})});
    var j=await r.json().catch(function(){return {};});
    if(r.ok&&j.ok){
      if(j.test_sent>0){btn.style.display='none';s('✅ Alerts are ON for this device — check for a test notification now!');}
      else{s('Saved for this device, but the test alert didn\\'t go through — this browser may not support push here. Try Chrome, or use the app option below.');}
    }
    else{s('Could not save your subscription — please try again.');}
  }catch(e){s('Could not enable: '+(e.message||e));}
};
})();
</script>"""

DONE = """<div class="hero" style="padding-top:34px;padding-bottom:0"><h1 class="reveal" style="font-size:34px;letter-spacing:-1.4px">You're all set 🎉</h1></div>
<div class="card reveal d2">
<div class="ok"><svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="10"/><path d="m9 12 2 2 4-4"/></svg><span>Now watching <b>__WHAT__</b>.</span></div>
__ALERTINTRO__
__PUSHBLOCK__
<a href="/" style="display:block;text-align:center;margin-top:18px;font-weight:700">← Back to your watches</a>
</div>"""

_PSTYLE = "font-size:14px;line-height:1.65;color:#374151"

TERMS = """<h2 style="font-size:20px;margin:6px 0 2px">Terms of Service</h2>
<p class="sub" style="margin-bottom:14px">Last updated: June 30, 2026</p>
<div style="STYLE">
<p><b>1. What SeatWatch is.</b> SeatWatch is a tool that checks publicly-available course-registration pages and notifies you when a seat appears to open in a class you ask us to watch. That is all it does.</p>
<p><b>2. Not affiliated with any school.</b> SeatWatch is an independent tool. We are not affiliated with, endorsed by, or connected to any university, college, or registration system. School and course names are used only to identify what you want to watch.</p>
<p><b>3. No guarantee.</b> We try hard, but we cannot promise SeatWatch will catch every opening, alert you in time, or be error-free. Seats can fill in seconds, notifications can be delayed or missed, and school websites change without notice. <b>You use SeatWatch entirely at your own risk.</b></p>
<p><b>4. You register yourself.</b> SeatWatch only sends alerts &mdash; it does not enroll you in anything. Actually registering for a class is your responsibility.</p>
<p><b>5. As-is.</b> The service is provided &ldquo;as is,&rdquo; without warranties of any kind, express or implied.</p>
<p><b>6. Limitation of liability.</b> To the fullest extent permitted by law, SeatWatch and its creator are not liable for any damages of any kind &mdash; including a missed class, a lost opportunity, or any direct or indirect loss &mdash; arising from your use of, or inability to use, the service.</p>
<p><b>7. Acceptable use.</b> Use SeatWatch for your own personal course-watching. Do not abuse, overload, scrape, resell, or attempt to disrupt the service, and do not create multiple accounts to get around free-plan limits &mdash; we may remove watches or accounts that do.</p>
<p><b>8. Changes.</b> We may change, pause, or discontinue the service, or update these terms, at any time. Continued use means you accept the current terms.</p>
<p><b>9. Governing law.</b> These terms are governed by the laws of the State of Maryland, USA.</p>
<p><b>10. Contact.</b> Questions? Reach the SeatWatch LLC team at <a href="mailto:support@seatwatchapp.com">support@seatwatchapp.com</a>.</p>
</div>
<p style="font-size:13px;margin-top:16px"><a href="/">&larr; Back to SeatWatch</a> &nbsp;&middot;&nbsp; <a href="/privacy">Privacy Policy</a></p>""".replace("STYLE", _PSTYLE)

PRIVACY = """<h2 style="font-size:20px;margin:6px 0 2px">Privacy Policy</h2>
<p class="sub" style="margin-bottom:14px">Last updated: June 30, 2026</p>
<div style="STYLE">
<p><b>The short version:</b> we collect the bare minimum needed to run your alerts &mdash; your email (from Google sign-in) and the classes you watch &mdash; and we never sell your data.</p>
<p><b>1. What we collect.</b> (a) your email address and Google account ID, via &ldquo;Sign in with Google&rdquo; (we never see or store your password); (b) the classes and sections you ask us to watch; (c) the private notification &ldquo;topic&rdquo; we assign your account, so we can push alerts to your phone; (d) your IP address, used only briefly to prevent spam and abuse (rate-limiting); (e) if you turn on phone alerts, the push subscription your browser creates &mdash; a device delivery address used only to send you your alerts, removed when you revoke it.</p>
<p><b>2. What we do NOT collect.</b> No password (Google handles sign-in), no payment information, no location, no browsing history.</p>
<p><b>3. How alerts are delivered.</b> Push notifications are sent through the free third-party service <a href="https://ntfy.sh">ntfy.sh</a>. Anyone who knows your topic string could read your alerts, so keep it private.</p>
<p><b>4. How we use your data.</b> Only to run the watch-and-alert service. Nothing else.</p>
<p><b>5. Sharing.</b> We do not sell, rent, or share your data for advertising &mdash; ever.</p>
<p><b>6. Retention.</b> A watch is kept only while it is active. Stop it (or ask us) and it is removed.</p>
<p><b>7. Security.</b> We use reasonable safeguards to protect the service, but no system is 100% secure.</p>
<p><b>8. Children.</b> SeatWatch is intended for college students and is not directed at children under 13.</p>
<p><b>9. Changes.</b> We may update this policy; the &ldquo;last updated&rdquo; date above will change.</p>
<p><b>10. Contact / data removal.</b> Want your data removed, or have a question? Contact the SeatWatch LLC team at <a href="mailto:support@seatwatchapp.com">support@seatwatchapp.com</a>.</p>
</div>
<p style="font-size:13px;margin-top:16px"><a href="/">&larr; Back to SeatWatch</a> &nbsp;&middot;&nbsp; <a href="/terms">Terms of Service</a></p>""".replace("STYLE", _PSTYLE)


LANDING = """<!doctype html><html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>SeatWatch — Get into the class you actually need | __COUNT__ universities</title>
<meta name="description" content="SeatWatch alerts you the instant a seat opens in a full college class, across __COUNT__ universities. Watch the exact section you want and get the professor you want. Free to start.">
<link rel="canonical" href="https://seatwatchapp.com/">
<meta name="robots" content="index, follow, max-image-preview:large">
<meta name="keywords" content="seatwatch, seat watch, course seat alert, class seat notification, college registration alert, open seat finder, coursicle alternative">
<meta name="author" content="SeatWatch LLC">
<meta name="application-name" content="SeatWatch">
<meta property="og:type" content="website">
<meta property="og:site_name" content="SeatWatch">
<meta property="og:title" content="SeatWatch — Get into the class you actually need">
<meta property="og:description" content="Get an instant alert the second a seat opens in a full college class — across __COUNT__ universities. Watch the exact section, get the professor you want.">
<meta property="og:url" content="https://seatwatchapp.com/">
<meta property="og:image" content="https://seatwatchapp.com/og-image.png">
<meta property="og:image:width" content="1200"><meta property="og:image:height" content="630">
<meta name="twitter:card" content="summary_large_image">
<meta name="twitter:title" content="SeatWatch — Get into the class you actually need">
<meta name="twitter:description" content="Get an instant alert the second a seat opens in a full college class. __COUNT__ universities. Free to start.">
<meta name="twitter:image" content="https://seatwatchapp.com/og-image.png">
<script type="application/ld+json">{"@context":"https://schema.org","@graph":[{"@type":"Organization","@id":"https://seatwatchapp.com/#org","name":"SeatWatch","legalName":"SeatWatch LLC","url":"https://seatwatchapp.com/","logo":"https://seatwatchapp.com/icon-512.png","email":"support@seatwatchapp.com","description":"Instant alerts when a seat opens in a full college class, across __COUNT__ universities."},{"@type":"WebSite","@id":"https://seatwatchapp.com/#site","url":"https://seatwatchapp.com/","name":"SeatWatch","publisher":{"@id":"https://seatwatchapp.com/#org"}},{"@type":"WebApplication","name":"SeatWatch","url":"https://seatwatchapp.com/","applicationCategory":"EducationalApplication","operatingSystem":"Web","offers":{"@type":"Offer","price":"0","priceCurrency":"USD","description":"First class free"},"description":"Get an instant phone alert the second a seat opens in a full college class."}]}</script>
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
        LIVE — WATCHING __COUNT__ UNIVERSITIES
      </div>
      <h1 class="sw-h1" style="margin:26px 0 0;font-size:64px;line-height:1.04;font-weight:800;letter-spacing:-.035em;">
        Get into the class you <span style="color:#2563eb;">actually need</span><span style="color:#17b26a;">.</span>
      </h1>
      <p style="margin:22px 0 0;font-size:19px;line-height:1.6;color:#4b5a72;max-width:490px;">
        That full class you're stuck on? We watch it around the clock and buzz your phone the instant a seat opens — and we never show fake openings.
      </p>
      <div style="display:flex;align-items:center;gap:18px;margin-top:36px;flex-wrap:wrap;">
        <a href="/login" class="sw-cta" style="display:inline-flex;align-items:center;gap:10px;padding:17px 30px;background:linear-gradient(140deg,#2563eb,#3b82f6);color:#fff;border-radius:100px;font-size:16.5px;font-weight:700;box-shadow:0 14px 30px -8px rgba(37,99,235,.5),inset 0 1px 0 rgba(255,255,255,.25);">
          Start watching free <span style="font-size:18px;">→</span>
        </a>
        <div style="display:flex;flex-direction:column;gap:2px;">
          <span style="font-size:14px;font-weight:700;color:#0b1526;">Free for your first class</span>
          <span style="font-size:13px;color:#6b7a92;">No card · no spam · 1-click sign in</span>
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
          <span style="font-family:'IBM Plex Mono',monospace;font-size:11.5px;font-weight:600;letter-spacing:.1em;color:#3d4c63;">LIVE FROM THE WATCH ENGINE</span>
          <span style="display:flex;align-items:center;gap:6px;font-family:'IBM Plex Mono',monospace;font-size:11px;color:#17b26a;"><span style="width:7px;height:7px;border-radius:50%;background:#17b26a;"></span>ONLINE</span>
        </div>
        <div id="sw-feed" style="display:flex;flex-direction:column;gap:12px;padding-top:16px;min-height:328px;">
          <div style="display:flex;gap:13px;padding:15px;background:#fff;border:1px solid rgba(23,178,106,.25);border-radius:16px;box-shadow:0 6px 18px -6px rgba(11,21,38,.1);"><div style="flex:none;width:40px;height:40px;border-radius:12px;background:rgba(23,178,106,.12);display:flex;align-items:center;justify-content:center;font-size:17px;">🔔</div><div style="min-width:0;"><div style="font-size:14.5px;font-weight:700;">Seat open: ENG101-0101</div><div style="font-size:13px;color:#6b7a92;margin-top:2px;">2 seats just opened. Tap to register! · <span style="color:#17b26a;font-weight:600;">now</span></div></div></div>
          <div style="display:flex;gap:13px;padding:15px;background:#fff;border:1px solid rgba(11,21,38,.07);border-radius:16px;"><div style="flex:none;width:40px;height:40px;border-radius:12px;background:rgba(37,99,235,.1);display:flex;align-items:center;justify-content:center;font-size:17px;">👀</div><div style="min-width:0;"><div style="font-size:14.5px;font-weight:700;">Watching CHEM 231 · Sec 03</div><div style="font-size:13px;color:#6b7a92;margin-top:2px;">Checked 4 seconds ago · still full</div></div></div>
          <div style="display:flex;gap:13px;padding:15px;background:#fff;border:1px solid rgba(11,21,38,.07);border-radius:16px;"><div style="flex:none;width:40px;height:40px;border-radius:12px;background:rgba(37,99,235,.1);display:flex;align-items:center;justify-content:center;font-size:17px;">👀</div><div style="min-width:0;"><div style="font-size:14.5px;font-weight:700;">Watching MATH 140 · Sec 01</div><div style="font-size:13px;color:#6b7a92;margin-top:2px;">Checked 11 seconds ago · still full</div></div></div>
          <div style="display:flex;gap:13px;padding:15px;background:#fff;border:1px solid rgba(11,21,38,.07);border-radius:16px;"><div style="flex:none;width:40px;height:40px;border-radius:12px;background:rgba(23,178,106,.12);display:flex;align-items:center;justify-content:center;font-size:17px;">✅</div><div style="min-width:0;"><div style="font-size:14.5px;font-weight:700;">Maya claimed her seat</div><div style="font-size:13px;color:#6b7a92;margin-top:2px;">BIO 1A · alerted → registered in 41s</div></div></div>
        </div>
      </div>
      <div style="position:absolute;right:-14px;bottom:-18px;animation:swFloat 5s ease-in-out infinite;background:#0b1526;color:#fff;border-radius:14px;padding:12px 18px;box-shadow:0 18px 40px -12px rgba(11,21,38,.5);display:flex;align-items:center;gap:9px;"><span style="font-size:15px;">⚡</span><span style="font-size:13.5px;font-weight:600;">Avg. alert in <span style="color:#7db8ff;">8 seconds</span></span></div>
    </div>
  </div>
</header>

<div data-reveal style="border-top:1px solid rgba(11,21,38,.06);border-bottom:1px solid rgba(11,21,38,.06);background:#fff;">
  <div style="max-width:1140px;margin:0 auto;padding:18px 28px;display:flex;align-items:center;justify-content:center;gap:34px;flex-wrap:wrap;font-size:13.5px;font-weight:600;color:#4b5a72;">
    <span style="display:flex;align-items:center;gap:8px;"><span style="color:#17b26a;">✓</span>Never fake — real seats only</span>
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
    <p style="margin:20px 0 0;font-size:17px;line-height:1.65;color:#4b5a72;">Stuck out of the class — or the exact section — you were hoping for? SeatWatch watches the <strong style="color:#0b1526;">specific section you pick</strong>, so you land the professor, time, and class you actually want the moment a seat opens up.</p>
    <p style="margin:14px 0 0;font-size:17px;line-height:1.65;color:#4b5a72;">Not just any seat — <em style="color:#2563eb;font-weight:600;">your</em> seat.</p>
  </div>
  <div data-reveal style="background:#fff;border:1px solid rgba(11,21,38,.07);border-radius:22px;box-shadow:0 24px 60px -24px rgba(11,21,38,.16);padding:24px;">
    <div style="display:flex;align-items:center;justify-content:space-between;padding-bottom:16px;border-bottom:1px solid rgba(11,21,38,.06);">
      <div><div style="font-size:16px;font-weight:800;">CHEM 231 — Organic Chemistry</div><div style="font-size:13px;color:#6b7a92;margin-top:2px;">Fall 2026 · pick your sections</div></div>
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
      <div data-reveal style="position:relative;text-align:center;padding:0 18px;transition-delay:.1s;"><div style="width:62px;height:62px;margin:0 auto;border-radius:18px;background:#f7f9fc;border:1px solid rgba(11,21,38,.08);display:flex;align-items:center;justify-content:center;font-size:24px;box-shadow:0 4px 14px rgba(11,21,38,.06);position:relative;z-index:1;">📡</div><div style="font-family:'IBM Plex Mono',monospace;font-size:11px;letter-spacing:.12em;color:#2563eb;margin-top:22px;">STEP 02</div><h3 style="margin:8px 0 0;font-size:19px;font-weight:800;letter-spacing:-.01em;">We watch it around the clock</h3><p style="margin:10px 0 0;font-size:15px;line-height:1.6;color:#4b5a72;">Our engine checks the live registration site every 20 seconds — fast and accurate.</p></div>
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
    <div data-reveal style="background:#fff;border:1px solid rgba(11,21,38,.07);border-radius:20px;padding:28px;box-shadow:0 10px 30px -14px rgba(11,21,38,.1);display:flex;flex-direction:column;gap:18px;"><div style="color:#f59e0b;font-size:15px;letter-spacing:2px;">★★★★★</div><p style="margin:0;font-size:15.5px;line-height:1.65;color:#243247;flex:1;">"I'd refreshed the registration page for a week. SeatWatch texted me at 7am, I tapped it, and I was in. Genuinely saved my semester."</p><div style="display:flex;align-items:center;gap:12px;"><div style="width:40px;height:40px;border-radius:50%;background:linear-gradient(140deg,#2563eb,#3b82f6);color:#fff;display:flex;align-items:center;justify-content:center;font-size:13px;font-weight:700;">MR</div><div><div style="font-size:14px;font-weight:700;">Maya R.</div><div style="font-size:12.5px;color:#6b7a92;">Junior · Computer Science</div></div></div></div>
    <div data-reveal style="background:#fff;border:1px solid rgba(11,21,38,.07);border-radius:20px;padding:28px;box-shadow:0 10px 30px -14px rgba(11,21,38,.1);display:flex;flex-direction:column;gap:18px;transition-delay:.08s;"><div style="color:#f59e0b;font-size:15px;letter-spacing:2px;">★★★★★</div><p style="margin:0;font-size:15.5px;line-height:1.65;color:#243247;flex:1;">"Needed one specific section to keep my work schedule. It watched that exact one and pinged me the second it opened. No more all-nighters refreshing."</p><div style="display:flex;align-items:center;gap:12px;"><div style="width:40px;height:40px;border-radius:50%;background:linear-gradient(140deg,#17b26a,#34d399);color:#fff;display:flex;align-items:center;justify-content:center;font-size:13px;font-weight:700;">JT</div><div><div style="font-size:14px;font-weight:700;">Jordan T.</div><div style="font-size:12.5px;color:#6b7a92;">Sophomore · Nursing</div></div></div></div>
    <div data-reveal style="background:#fff;border:1px solid rgba(11,21,38,.07);border-radius:20px;padding:28px;box-shadow:0 10px 30px -14px rgba(11,21,38,.1);display:flex;flex-direction:column;gap:18px;transition-delay:.16s;"><div style="color:#f59e0b;font-size:15px;letter-spacing:2px;">★★★★★</div><p style="margin:0;font-size:15.5px;line-height:1.65;color:#243247;flex:1;">"The class I needed to graduate on time was full all summer. Got the alert in August, registered from my phone in the dining hall. Unreal."</p><div style="display:flex;align-items:center;gap:12px;"><div style="width:40px;height:40px;border-radius:50%;background:linear-gradient(140deg,#7c3aed,#a78bfa);color:#fff;display:flex;align-items:center;justify-content:center;font-size:13px;font-weight:700;">DK</div><div><div style="font-size:14px;font-weight:700;">Devin K.</div><div style="font-size:12.5px;color:#6b7a92;">Senior · Business</div></div></div></div>
  </div>
</section>

<section id="sw-pricing" style="background:#fff;border-top:1px solid rgba(11,21,38,.06);border-bottom:1px solid rgba(11,21,38,.06);">
  <div style="max-width:1140px;margin:0 auto;padding:110px 28px;">
    <div data-reveal style="text-align:center;max-width:520px;margin:0 auto;">
      <div style="font-family:'IBM Plex Mono',monospace;font-size:12px;font-weight:600;letter-spacing:.12em;color:#2563eb;">PRICING</div>
      <h2 class="sw-h2" style="margin:16px 0 0;font-size:42px;font-weight:800;letter-spacing:-.03em;line-height:1.1;">Simple, fair pricing.</h2>
      <p style="margin:16px 0 0;font-size:17px;color:#4b5a72;">Start free. Upgrade only if you need more.</p>
    </div>
    <div class="sw-price" style="display:grid;grid-template-columns:repeat(2,minmax(0,440px));gap:24px;justify-content:center;margin-top:56px;align-items:stretch;">
      <div data-reveal style="position:relative;background:#f7f9fc;border:2px solid #17b26a;border-radius:22px;padding:34px;display:flex;flex-direction:column;box-shadow:0 20px 50px -20px rgba(23,178,106,.3);">
        <span style="position:absolute;top:-13px;left:34px;background:#17b26a;color:#fff;font-family:'IBM Plex Mono',monospace;font-size:11px;font-weight:600;letter-spacing:.1em;padding:5px 13px;border-radius:100px;">START FREE</span>
        <div style="display:flex;align-items:baseline;gap:10px;margin-top:8px;"><span style="font-size:52px;font-weight:800;letter-spacing:-.03em;">$0</span><span style="font-size:15px;color:#6b7a92;">first class</span></div>
        <div style="display:flex;flex-direction:column;gap:13px;margin-top:26px;flex:1;">
          <div style="display:flex;gap:11px;font-size:15px;color:#243247;"><span style="color:#17b26a;font-weight:700;">✓</span>Your first class — completely free</div>
          <div style="display:flex;gap:11px;font-size:15px;color:#243247;"><span style="color:#17b26a;font-weight:700;">✓</span>Instant phone alerts</div>
          <div style="display:flex;gap:11px;font-size:15px;color:#243247;"><span style="color:#17b26a;font-weight:700;">✓</span>Never fake — real seats only</div>
          <div style="display:flex;gap:11px;font-size:15px;color:#243247;"><span style="color:#17b26a;font-weight:700;">✓</span>No card required</div>
        </div>
        <a href="/login" class="sw-dark" style="margin-top:30px;padding:15px;text-align:center;background:#0b1526;color:#fff;border-radius:100px;font-size:15px;font-weight:700;">Start watching free</a>
      </div>
      <div data-reveal style="position:relative;background:#fff;border:1px solid rgba(11,21,38,.09);border-radius:22px;padding:34px;display:flex;flex-direction:column;transition-delay:.08s;">
        <span style="position:absolute;top:-13px;left:34px;background:#eef2f8;color:#4b5a72;font-family:'IBM Plex Mono',monospace;font-size:11px;font-weight:600;letter-spacing:.1em;padding:5px 13px;border-radius:100px;border:1px solid rgba(11,21,38,.07);">COMING SOON</span>
        <div style="display:flex;align-items:baseline;gap:10px;margin-top:8px;"><span style="font-size:52px;font-weight:800;letter-spacing:-.03em;">$19.95</span><span style="font-size:15px;color:#6b7a92;">per additional course</span></div>
        <div style="display:flex;flex-direction:column;gap:13px;margin-top:26px;flex:1;">
          <div style="display:flex;gap:11px;font-size:15px;color:#243247;"><span style="color:#2563eb;font-weight:700;">✓</span><span><strong>Includes all sections</strong> of the course</span></div>
          <div style="display:flex;gap:11px;font-size:15px;color:#243247;"><span style="color:#2563eb;font-weight:700;">✓</span>Same instant alerts, same engine</div>
        </div>
        <a href="/login" style="margin-top:30px;padding:15px;text-align:center;border:1px solid rgba(11,21,38,.12);color:#4b5a72;border-radius:100px;font-size:15px;font-weight:700;">Notify me</a>
      </div>
    </div>
  </div>
</section>

<section id="sw-faq" style="max-width:760px;margin:0 auto;padding:110px 28px;">
  <div data-reveal style="text-align:center;">
    <div style="font-family:'IBM Plex Mono',monospace;font-size:12px;font-weight:600;letter-spacing:.12em;color:#2563eb;">FAQ</div>
    <h2 class="sw-h2" style="margin:16px 0 0;font-size:42px;font-weight:800;letter-spacing:-.03em;">Questions, answered.</h2>
    <p style="margin:16px 0 0;font-size:17px;color:#4b5a72;">The stuff students actually ask us.</p>
  </div>
  <div data-reveal style="display:flex;flex-direction:column;gap:12px;margin-top:48px;">
    <div data-faq style="background:#fff;border:1px solid rgba(11,21,38,.07);border-radius:16px;overflow:hidden;cursor:pointer;transition:border-color .25s;"><div style="display:flex;align-items:center;justify-content:space-between;padding:20px 24px;gap:16px;"><span style="font-size:16.5px;font-weight:700;">Is it really free?</span><span data-faq-icon style="flex:none;width:28px;height:28px;border-radius:50%;background:rgba(37,99,235,.08);color:#2563eb;display:flex;align-items:center;justify-content:center;font-size:16px;font-weight:600;transition:transform .3s;">+</span></div><div data-faq-body style="max-height:0;overflow:hidden;transition:max-height .35s cubic-bezier(.16,1,.3,1);"><p style="margin:0;padding:0 24px 22px;font-size:15px;line-height:1.65;color:#4b5a72;">Yes. Your first class — up to two sections — is completely free, forever. No credit card, no trial clock. We only ask you to sign in so your watch stays tied to you.</p></div></div>
    <div data-faq style="background:#fff;border:1px solid rgba(11,21,38,.07);border-radius:16px;overflow:hidden;cursor:pointer;transition:border-color .25s;"><div style="display:flex;align-items:center;justify-content:space-between;padding:20px 24px;gap:16px;"><span style="font-size:16.5px;font-weight:700;">How fast will I hear about an open seat?</span><span data-faq-icon style="flex:none;width:28px;height:28px;border-radius:50%;background:rgba(37,99,235,.08);color:#2563eb;display:flex;align-items:center;justify-content:center;font-size:16px;font-weight:600;transition:transform .3s;">+</span></div><div data-faq-body style="max-height:0;overflow:hidden;transition:max-height .35s cubic-bezier(.16,1,.3,1);"><p style="margin:0;padding:0 24px 22px;font-size:15px;line-height:1.65;color:#4b5a72;">We check your class's live registration system every 20 seconds, around the clock. The instant a real seat appears, your phone gets a push alert — usually within seconds of it opening.</p></div></div>
    <div data-faq style="background:#fff;border:1px solid rgba(11,21,38,.07);border-radius:16px;overflow:hidden;cursor:pointer;transition:border-color .25s;"><div style="display:flex;align-items:center;justify-content:space-between;padding:20px 24px;gap:16px;"><span style="font-size:16.5px;font-weight:700;">Will you ever send a fake alert?</span><span data-faq-icon style="flex:none;width:28px;height:28px;border-radius:50%;background:rgba(37,99,235,.08);color:#2563eb;display:flex;align-items:center;justify-content:center;font-size:16px;font-weight:600;transition:transform .3s;">+</span></div><div data-faq-body style="max-height:0;overflow:hidden;transition:max-height .35s cubic-bezier(.16,1,.3,1);"><p style="margin:0;padding:0 24px 22px;font-size:15px;line-height:1.65;color:#4b5a72;">Never. We read the true seat count straight from your school's registration system and only alert on a genuinely open seat. If our engine can't confirm a seat is really open, it stays silent — no false alarms.</p></div></div>
    <div data-faq style="background:#fff;border:1px solid rgba(11,21,38,.07);border-radius:16px;overflow:hidden;cursor:pointer;transition:border-color .25s;"><div style="display:flex;align-items:center;justify-content:space-between;padding:20px 24px;gap:16px;"><span style="font-size:16.5px;font-weight:700;">Can I watch a specific section or professor?</span><span data-faq-icon style="flex:none;width:28px;height:28px;border-radius:50%;background:rgba(37,99,235,.08);color:#2563eb;display:flex;align-items:center;justify-content:center;font-size:16px;font-weight:600;transition:transform .3s;">+</span></div><div data-faq-body style="max-height:0;overflow:hidden;transition:max-height .35s cubic-bezier(.16,1,.3,1);"><p style="margin:0;padding:0 24px 22px;font-size:15px;line-height:1.65;color:#4b5a72;">That's the whole point. You pick the exact section(s) you want, so you land the professor, time, and class you're actually after — not just any open seat.</p></div></div>
    <div data-faq style="background:#fff;border:1px solid rgba(11,21,38,.07);border-radius:16px;overflow:hidden;cursor:pointer;transition:border-color .25s;"><div style="display:flex;align-items:center;justify-content:space-between;padding:20px 24px;gap:16px;"><span style="font-size:16.5px;font-weight:700;">Is my school supported?</span><span data-faq-icon style="flex:none;width:28px;height:28px;border-radius:50%;background:rgba(37,99,235,.08);color:#2563eb;display:flex;align-items:center;justify-content:center;font-size:16px;font-weight:600;transition:transform .3s;">+</span></div><div data-faq-body style="max-height:0;overflow:hidden;transition:max-height .35s cubic-bezier(.16,1,.3,1);"><p style="margin:0;padding:0 24px 22px;font-size:15px;line-height:1.65;color:#4b5a72;">We watch classes at __COUNT__ universities and colleges, and we're adding more every week. Sign in and start typing your school — if it's there, you're good to go.</p></div></div>
    <div data-faq style="background:#fff;border:1px solid rgba(11,21,38,.07);border-radius:16px;overflow:hidden;cursor:pointer;transition:border-color .25s;"><div style="display:flex;align-items:center;justify-content:space-between;padding:20px 24px;gap:16px;"><span style="font-size:16.5px;font-weight:700;">Is this against my school's rules?</span><span data-faq-icon style="flex:none;width:28px;height:28px;border-radius:50%;background:rgba(37,99,235,.08);color:#2563eb;display:flex;align-items:center;justify-content:center;font-size:16px;font-weight:600;transition:transform .3s;">+</span></div><div data-faq-body style="max-height:0;overflow:hidden;transition:max-height .35s cubic-bezier(.16,1,.3,1);"><p style="margin:0;padding:0 24px 22px;font-size:15px;line-height:1.65;color:#4b5a72;">No. SeatWatch only reads the same public class-availability info you'd see yourself — it never logs into your account or registers for you. When a seat opens, you tap the alert and register, just like normal.</p></div></div>
  </div>
</section>

<section style="max-width:1140px;margin:0 auto;padding:0 28px 110px;">
  <div class="sw-final" data-reveal style="position:relative;overflow:hidden;background:linear-gradient(140deg,#1d4ed8 0%,#2563eb 55%,#3b82f6 100%);border-radius:28px;padding:88px 40px;text-align:center;box-shadow:0 40px 90px -30px rgba(37,99,235,.55);">
    <div style="position:absolute;inset:0;background-image:linear-gradient(rgba(255,255,255,.06) 1px,transparent 1px),linear-gradient(90deg,rgba(255,255,255,.06) 1px,transparent 1px);background-size:48px 48px;mask-image:radial-gradient(70% 100% at 50% 0%,#000,transparent);-webkit-mask-image:radial-gradient(70% 100% at 50% 0%,#000,transparent);"></div>
    <div style="position:relative;">
      <h2 style="margin:0;font-size:48px;font-weight:800;letter-spacing:-.03em;color:#fff;">Your seat is out there.</h2>
      <p style="margin:18px auto 0;font-size:18px;line-height:1.6;color:rgba(255,255,255,.85);max-width:480px;">Let us watch for it. Set up your first class free in under a minute — and get on with your day.</p>
      <a href="/login" class="sw-cta" style="display:inline-flex;align-items:center;gap:10px;margin-top:36px;padding:17px 32px;background:#fff;color:#1d4ed8;border-radius:100px;font-size:16.5px;font-weight:800;box-shadow:0 16px 40px -10px rgba(11,21,38,.4);">Start watching free <span style="font-size:18px;">→</span></a>
      <div style="margin-top:18px;font-size:13.5px;color:rgba(255,255,255,.7);">Free first class · No card required · Alerts in seconds</div>
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
      <a href="/privacy" style="color:#6b7a92;">Privacy</a>
      <span style="color:#9aa7ba;">Not affiliated with any university.</span>
    </div>
  </div>
</footer>

<script>
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
 var feed=document.getElementById('sw-feed');
 if(feed){
   var courses=['BIO 205','PSYC 100','MATH 140','ECON 200','CHEM 231','ENG 101','CS 250','STAT 121','HIST 110','PHYS 212','NURS 210','ACCT 201','SPAN 103','PHIL 140','COMM 107','ANTH 220','GEOG 130','MUSC 115','SOCY 105','KINE 200'];
   var names=['Maya','Jordan','Priya','Devin','Sam','Alex','Nia','Marcus','Elena','Tyler','Aisha','Chris','Dana','Leo','Grace','Omar'];
   var pick=function(a){return a[(Math.random()*a.length)|0];};
   var sec=function(){return '0'+(1+((Math.random()*4)|0))+'0'+(1+((Math.random()*9)|0));};
   var last='';
   function ev(){var c=pick(courses);while(c===last)c=pick(courses);last=c;var r=Math.random();
     if(r<0.34){var s=1+((Math.random()*3)|0);return{icon:'🔔',green:true,title:'Seat open: '+c.replace(' ','')+'-'+sec(),sub:s+(s===1?' seat':' seats')+' just opened. Tap to register! · <span style="color:#17b26a;font-weight:600;">now</span>'};}
     else if(r<0.72){var ss=2+((Math.random()*17)|0);return{icon:'👀',green:false,title:'Watching '+c+' · Sec 0'+(1+((Math.random()*4)|0)),sub:'Checked '+ss+' seconds ago · still full'};}
     else{var sp=25+((Math.random()*70)|0);return{icon:'✅',green:true,title:pick(names)+' claimed a seat',sub:c+' · alerted → registered in '+sp+'s'};}}
   setInterval(function(){var e=ev();var row=document.createElement('div');
     row.style.cssText='display:flex;gap:13px;padding:15px;background:#fff;border:1px solid '+(e.green?'rgba(23,178,106,.25)':'rgba(11,21,38,.07)')+';border-radius:16px;box-shadow:0 6px 18px -6px rgba(11,21,38,.1);animation:swSlideIn .5s cubic-bezier(.16,1,.3,1);';
     row.innerHTML='<div style="flex:none;width:40px;height:40px;border-radius:12px;background:'+(e.green?'rgba(23,178,106,.12)':'rgba(37,99,235,.1)')+';display:flex;align-items:center;justify-content:center;font-size:17px;">'+e.icon+'</div><div style="min-width:0;"><div style="font-size:14.5px;font-weight:700;">'+e.title+'</div><div style="font-size:13px;color:#6b7a92;margin-top:2px;">'+e.sub+'</div></div>';
     feed.prepend(row);while(feed.children.length>4)feed.removeChild(feed.lastChild);
   },3400);
 }
})();
</script>
</body></html>
"""


def landing_page():
    """The redesigned marketing landing page (logged-out home). Fills the live
    school count; all CTAs route to /login (Google sign-in)."""
    return LANDING.replace("__COUNT__", str(len(schools.SCHOOLS)))

def page(body):
    return PAGE.replace("__BODY__", body)


SCHOOLS_JS = json.dumps([
    {"id": s.id, "name": s.name, "ex": s.example}
    for s in sorted(schools.SCHOOLS.values(), key=lambda s: s.name.lower())])


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
        items += (f"<li><span>{html.escape(r['course'])} §{html.escape(r['section'])}"
                  f" — {html.escape(name)}</span>"
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


def push_block(tok):
    """The one-tap alerts widget; empty string when push isn't configured."""
    if not PUSH_ENABLED:
        return ""
    return PUSH_BLOCK.replace("__CSRF__", tok).replace("__VAPIDPK__", VAPID_PUBLIC_KEY)


def form_page(notice="", user=None):
    if user is None:
        card = CARD_LOGIN.replace("__NOTICE__", notice)
    else:
        tok = csrf_token(user["id"])
        card = (CARD_FORM.replace("__NOTICE__", notice)
                .replace("__EMAIL__", html.escape(user["email"]))
                .replace("__PUSHBLOCK__", push_block(tok))
                .replace("__CSRF__", tok)
                .replace("__WATCHES__", watches_html(user["id"], tok))
                .replace("__SCHOOLS__", SCHOOLS_JS))
    return page(FORM.replace("__CARD__", card))


def alert_intro(user):
    """The line(s) above the phone-alert widget. When email is the live default channel we
    reassure the student they're ALREADY covered (zero setup) and frame push as optional;
    otherwise phone alerts are the primary 'last step'."""
    if EMAIL_ENABLED:
        return ("<div class='ok'><svg width='18' height='18' viewBox='0 0 24 24' fill='none' "
                "stroke='currentColor' stroke-width='2' stroke-linecap='round' "
                "stroke-linejoin='round'><rect x='2' y='4' width='20' height='16' rx='2'/>"
                "<path d='m22 7-8.97 5.7a1.94 1.94 0 0 1-2.06 0L2 7'/></svg><span>We'll email "
                f"you at <b>{html.escape(user['email'])}</b> the second a seat opens — nothing "
                "else to do.</span></div>"
                "<p style='font-weight:700;margin:18px 0 4px'>Want an instant buzz on your "
                "phone too? <span style='font-weight:500;color:var(--dim)'>(optional)</span></p>")
    return "<p style='font-weight:700;margin:18px 0 4px'>Last step — get the alert on your phone:</p>"


def done_page(what, user):
    tok = csrf_token(user["id"])
    body = (DONE.replace("__WHAT__", html.escape(what))
                .replace("__ALERTINTRO__", alert_intro(user))
                .replace("__PUSHBLOCK__", push_block(tok) or
                         "<p class='note' style='text-align:left'>Phone alerts are being "
                         "set up — check back shortly.</p>"))
    return page(body)


# ----------------------------------------------------------------------- server
class Handler(BaseHTTPRequestHandler):
    server_version = "SeatWatch"   # don't disclose Python / BaseHTTP version
    sys_version = ""

    def _send(self, body, code=200):
        data = body.encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(data)))
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("X-Frame-Options", "DENY")
        self.send_header("Referrer-Policy", "no-referrer")
        self.send_header("Strict-Transport-Security", "max-age=15552000")
        self.send_header("Content-Security-Policy",
                         "default-src 'none'; "
                         "style-src 'unsafe-inline' https://fonts.googleapis.com; "
                         "font-src https://fonts.gstatic.com; "
                         "script-src 'self' 'unsafe-inline'; worker-src 'self'; "
                         "connect-src 'self'; manifest-src 'self'; "
                         "img-src 'self' data:; "
                         "form-action 'self'; base-uri 'none'; frame-ancestors 'none'")
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

    def _redirect(self, location, cookies=()):
        self.send_response(302)
        self.send_header("Location", location)
        for ck in cookies:
            self.send_header("Set-Cookie", ck)
        self.send_header("Content-Length", "0")
        self.end_headers()

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
        if path == "/sw.js":   # service worker: no-cache so updates roll out fast
            return self._send_bytes(SW_JS.encode(), "application/javascript; charset=utf-8",
                                    cache="no-cache")
        if path == "/manifest.json":
            return self._send_bytes(MANIFEST.encode(), "application/manifest+json",
                                    cache="public, max-age=3600")
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
        if path == "/login":
            if not GOOGLE_CLIENT_ID:
                return self._send(form_page(
                    "<div class='ok'>Sign-in is being switched on — check back shortly!</div>"))
            state = secrets.token_urlsafe(24)
            return self._redirect(google_auth_url(state), cookies=[
                f"sw_state={state}; Path=/; Max-Age=600; HttpOnly; Secure; SameSite=Lax"])
        if path == "/auth/callback":
            state, code = qs.get("state", [""])[0], qs.get("code", [""])[0]
            want = self._cookie("sw_state")
            clear = "sw_state=; Path=/; Max-Age=0; HttpOnly; Secure; SameSite=Lax"
            if not (state and want and code) or not hmac.compare_digest(state, want):
                return self._send(form_page(
                    "<div class='ok'>Sign-in didn't complete — please try again.</div>"))
            info = google_exchange(code)
            if not info:
                return self._send(form_page(
                    "<div class='ok'>Google sign-in failed — please try again.</div>"))
            user = get_or_create_user(info["sub"], info["email"])
            return self._redirect("/", cookies=[session_cookie(user["id"]), clear])
        if path == "/logout":
            return self._redirect("/", cookies=[
                "sw_session=; Path=/; Max-Age=0; HttpOnly; Secure; SameSite=Lax"])
        if path == "/dev-login" and DEV_LOGIN:   # local testing only (env-gated)
            email = qs.get("email", ["dev@example.com"])[0][:80]
            user = get_or_create_user("dev:" + email, email)
            return self._redirect("/", cookies=[session_cookie(user["id"])])
        if path != "/":
            return self._send(page("<p>Not found. <a href='/'>Home</a></p>"), 404)
        u = self._user()
        if u is None:
            return self._send(landing_page())
        self._send(form_page(user=u))

    def _client_ip(self):
        # Cloudflare sets CF-Connecting-IP itself and overwrites any value the
        # visitor sends, so it can't be spoofed. X-Forwarded-For's FIRST hop
        # CAN be forged by the client (rate-limit bypass) — never trust it.
        cf = self.headers.get("CF-Connecting-IP", "").strip()
        return cf or self.client_address[0]

    _OK_ICON = ("<svg width='18' height='18' viewBox='0 0 24 24' fill='none' stroke='currentColor' "
                "stroke-width='2' stroke-linecap='round' stroke-linejoin='round'><circle cx='12' "
                "cy='12' r='10'/><path d='m9 12 2 2 4-4'/></svg>")

    def _notice(self, msg, code=200, user=None):
        self._send(form_page(f"<div class='ok'>{self._OK_ICON}<span>{html.escape(msg)}</span></div>",
                             user=user), code)

    def do_POST(self):
        path = urlparse(self.path).path
        if path not in ("/watch", "/unwatch", "/push/subscribe"):
            return self._send(page("<p>Not found.</p>"), 404)

        # (1) rate limit FIRST — blocks form-flooding before any work is done
        if not rate_ok(self._client_ip()):
            return self._notice("Too many requests — wait a minute and try again.", 429)

        try:
            length = int(self.headers.get("Content-Length", 0) or 0)
        except ValueError:
            length = 0
        length = max(0, min(length, 4096))  # cap body size; never read(-1) on a forged header
        raw_body = self.rfile.read(length).decode("utf-8", "replace")

        # (2) WHO IS THIS? Signed session cookie or nothing. Entitlements are
        # per-account — an anonymous POST can no longer create watches at all.
        user = self._user()

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
                c.execute("INSERT INTO push_subs(user_id,endpoint,p256dh,auth,created) "
                          "VALUES(?,?,?,?,?) ON CONFLICT(endpoint) DO UPDATE SET "
                          "user_id=excluded.user_id, p256dh=excluded.p256dh, auth=excluded.auth",
                          (user["id"], endpoint, p256dh, auth, time.time()))
            sent = send_web_push(user["id"],
                                 "SeatWatch alerts are ON 🎉",
                                 "This is exactly how we'll buzz you the second a seat opens.",
                                 BASE_URL)
            sw.log(f"  [push] user {user['id']} subscribed via {urlparse(endpoint).netloc} "
                   f"(test push confirmed to {sent} device)")
            return self._send_json({"ok": True, "test_sent": sent})

        form = parse_qs(raw_body)
        if not user:
            return self._notice("Please sign in first — it takes one click, no password.")
        if not hmac.compare_digest(form.get("csrf", [""])[0], csrf_token(user["id"])):
            return self._notice("That form expired — please try again.", user=user)

        if path == "/unwatch":
            wid = form.get("id", ["0"])[0]
            if wid.isdigit():
                with db() as c:   # user_id in WHERE = can only delete YOUR OWN watch
                    c.execute("DELETE FROM watches WHERE id=? AND user_id=?",
                              (int(wid), user["id"]))
            return self._notice("Stopped. You can watch a different class now.", user=user)

        school = schools.SCHOOLS.get(form.get("school", [""])[0].strip())
        if not school:
            return self._notice("Please choose a valid school.", user=user)
        course = form.get("course", [""])[0].strip().upper()
        raw = form.get("sections", [""])[0]
        # dict.fromkeys dedupes ("0101, 0101" would otherwise double-alert)
        sections = list(dict.fromkeys(s.strip().upper() for s in raw.split(",") if s.strip()))
        if not sections:
            return self._notice("Please add the section number(s) you want to watch — e.g. 0101.",
                                user=user)
        if len(sections) > FREE_SECTIONS_PER_COURSE:
            return self._notice(f"That's a lot of sections at once — you can watch up to "
                                f"{FREE_SECTIONS_PER_COURSE} sections of a class. Trim the list a bit.",
                                user=user)

        # (3) per-school FORMAT validation — no junk reaches a fetch
        if not school.valid_course(course):
            return self._notice(f"That doesn't look like a {school.name} course code "
                                f"(e.g. {school.example}).", user=user)
        for s in sections:
            if s and not SECTION_RE.match(s):
                return self._notice(f"Invalid section: {s}", user=user)

        # (3.5) cheap entitlement pre-check BEFORE the network fetch, so a
        # limit-hit user can't make us hammer school sites (authoritative
        # re-check happens under the lock below)
        with db() as c:
            pre = {(r["school"], r["course"]) for r in c.execute(
                "SELECT school,course FROM watches WHERE user_id=?", (user["id"],))}
        if (school.id, course) not in pre and len(pre) >= FREE_COURSES:
            return self._notice(PLAN_MSG, user=user)

        # (4) validate it ACTUALLY EXISTS — blocks fake-course flooding
        secs = school.fetch({course}).get(course, {})
        if not secs:
            return self._notice(f"Couldn't find {course} at {school.name} this term — check the code?",
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
            if key not in my_courses and len(my_courses) >= FREE_COURSES:
                return self._notice(PLAN_MSG, user=user)
            have = {r["section"] for r in mine if (r["school"], r["course"]) == key}
            new = [s for s in sections if s not in have]
            if not new:
                return self._notice("You're already watching those sections.", user=user)
            if len(have) + len(new) > FREE_SECTIONS_PER_COURSE:
                return self._notice(
                    f"You're watching {len(have)} sections of this class already — that's near "
                    f"the {FREE_SECTIONS_PER_COURSE}-section cap. Stop a few below to add more.",
                    user=user)

            # (6) store — alerts go to the account's one stable private channel
            with db() as c:
                for sec in new:
                    c.execute("INSERT INTO watches(school,topic,course,section,term,created,user_id) "
                              "VALUES(?,?,?,?,?,?,?)",
                              (school.id, user["topic"], course, sec,
                               getattr(school, "term", ""), time.time(), user["id"]))
        what = course + " " + ", ".join(new)
        self._send(done_page(f"{what} @ {school.name}", user))

    def log_message(self, *a):  # quiet
        pass


# ----------------------------------------------------------------- health guard
health = {}            # course -> {fails, alerted, last_count}  (in-memory)

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


def operator_alert(message):
    """Ping YOU (the operator) when something needs a human. Never goes to users.
    Web push to the admin's account (primary) + ntfy topic (backup channel)."""
    if ADMIN_USER_ID:
        try:
            send_web_push(ADMIN_USER_ID, "SeatWatch health", message, BASE_URL)
        except Exception:
            pass
    sw.notify("SeatWatch health", message, topic=OPERATOR_TOPIC)
    sw.log("  [OPERATOR ALERT] " + message)


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
    status = "all healthy ✅" if not broken else "NEEDS ATTENTION ⚠️: " + ", ".join(broken)
    operator_alert(f"Daily check — watching {n_watches} class(es) for {n_users} user(s). {status}")


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
        return school_id, {}
    try:
        return school_id, school.fetch({r["course"] for r in items})
    except Exception as e:
        sw.log(f"  [warn] {school_id} fetch crashed (treated as no-data): {e}")
        return school_id, {}


def run_cycle():
    with db() as c:
        rows = c.execute("SELECT * FROM watches").fetchall()
    by_school = {}
    for r in rows:
        by_school.setdefault(r["school"], []).append(r)
    if not by_school:
        return

    # Fetch every school CONCURRENTLY so cycle time stays flat as schools scale
    # (sequential would grow linearly). Alert logic below stays sequential + safe.
    data_by_school = {}
    with ThreadPoolExecutor(max_workers=min(12, len(by_school))) as ex:
        for school_id, data in ex.map(lambda kv: _school_fetch(*kv), by_school.items()):
            data_by_school[school_id] = data

    for school_id, items in by_school.items():
        school = schools.SCHOOLS.get(school_id)
        if not school:
            continue
        data = data_by_school.get(school_id, {})  # {course: {section: {open(bool), seats}}}

        for r in items:
            course = r["course"]
            hkey = f"{school_id}:{course}"
            h = health.setdefault(hkey, {"fails": 0, "alerted": False, "last_count": 0})
            secs = data.get(course)

            # GUARD — course returned no data (fetch failed / format changed / blocked)
            if not secs:
                h["fails"] += 1
                if h["fails"] >= FAIL_THRESHOLD and not h["alerted"]:
                    operator_alert(f"{school.name} {course}: no data {h['fails']}x in a row "
                                   "— possible block or format change. Paused (NO false "
                                   "alerts go out). I'll report when it recovers.")
                    h["alerted"] = True
                continue

            if h["alerted"]:
                operator_alert(f"{school.name} {course}: recovered ✅")
            h.update(fails=0, alerted=False, last_count=len(secs))

            url = school.reg_url(course)
            want = r["section"]
            if want == "":                  # watching ALL sections of the course
                open_secs = [n for n, i in secs.items() if i["open"]]
                if open_secs and not r["alerted"]:
                    _alert(r, f"Open in {course}: {', '.join(sorted(open_secs))}", url)
                    _set_alerted(r["id"], 1)
                elif not open_secs and r["alerted"]:
                    _set_alerted(r["id"], 0)
            else:
                info = secs.get(want)
                if not info:
                    continue
                if info["open"] and not r["alerted"]:
                    seats = info.get("seats")
                    msg = (f"{seats} seat(s) open in {course}-{want}!" if seats
                           else f"A seat opened in {course} section {want}!")
                    _alert(r, msg, url)
                    _set_alerted(r["id"], 1)
                elif not info["open"] and r["alerted"]:
                    _set_alerted(r["id"], 0)


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
        msg.set_content(f"{body_text}\n\nRegister now: {url}\n\n"
                        f"— SeatWatch\nYou're getting this because you asked us to watch this class. "
                        f"Reply STOP-style requests to support@seatwatchapp.com.")
        with smtplib.SMTP(SMTP_HOST, SMTP_PORT, timeout=15) as s:
            s.starttls(context=ssl.create_default_context())
            s.login(SMTP_USER, SMTP_PASS)
            s.send_message(msg)
        return True
    except Exception as e:
        sw.log(f"  [email] send failed to {to}: {type(e).__name__}: {str(e)[:80]}")
        return False


def _alert(r, message, url):
    ok = sw.notify(f"Seat open: {r['course']}",
                   message + " Tap to register — go now.",
                   click_url=url, topic=r["topic"])
    uid = r["user_id"] if "user_id" in r.keys() else None
    pushed = send_web_push(uid, f"Seat open: {r['course']}",
                           message + " Tap to register — go now.", url)
    emailed = False
    if EMAIL_ENABLED and uid:
        with db() as c:
            row = c.execute("SELECT email FROM users WHERE id=?", (uid,)).fetchone()
        if row and row["email"]:
            emailed = send_email(row["email"], f"Seat open: {r['course']} — go register",
                                 message + " Register now before it fills again.", url)
    sw.log(f"  ALERT {r['course']}-{r['section'] or 'ALL'} -> {r['topic']} "
           f"(ntfy {'sent' if ok else 'FAILED'}; web-push {pushed}; email {'sent' if emailed else 'off'})")


def _set_alerted(watch_id, val):
    with db() as c:
        c.execute("UPDATE watches SET alerted=? WHERE id=?", (val, watch_id))


def poller():
    sw.log("Poller started (with health guard).")
    last_term_refresh = 0.0
    while True:
        try:
            # Self-maintenance: auto-roll Banner schools to the new semester once/day, in
            # the background so it never blocks polling. Safe: verifies live data before
            # adopting a new term, else keeps the last-known-good one.
            if time.time() - last_term_refresh > 86400:
                last_term_refresh = time.time()
                threading.Thread(target=schools.refresh_all_terms,
                                 kwargs={"log": sw.log}, daemon=True).start()
            run_cycle()
            ping_healthcheck()
            maybe_daily_summary()
            run_fire_drill()
        except Exception as e:
            sw.log(f"[poller error, recovering] {e}")
            try:
                operator_alert(f"Engine hit an error but recovered: {e}")
            except Exception:
                pass
        time.sleep(POLL_SECONDS)


def main():
    init_db()
    threading.Thread(target=poller, daemon=True).start()
    server = ThreadingHTTPServer(("0.0.0.0", PORT), Handler)
    sw.log(f"SeatWatch web app on http://localhost:{PORT}  (term {sw.TERM})")
    server.serve_forever()


if __name__ == "__main__":
    main()
