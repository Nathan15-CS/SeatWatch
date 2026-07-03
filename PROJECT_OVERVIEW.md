# SeatWatch — Project Overview

_Accurate as of July 2026. This document describes the project as it actually is,
not an idealized version._

---

## 1. What SeatWatch does

Students often can't register for a full class — or a full *section* (a specific
professor/time). SeatWatch lets a signed-in student say "watch **this** course
section at **my** school." A background poller checks that school's live
registration system every ~20 seconds and, the instant a real seat opens, pushes
a notification to the student's phone so they can register immediately.

Core promise: **we never show a fake opening.** If a data source fails or a page
can't be parsed, we go silent for that course — we never guess "open." This
"fail closed" behavior is the product's whole reputation and is enforced
everywhere (see ARCHITECTURE.md).

---

## 2. Tech stack

- **Language:** Python 3, **standard library only** — `http.server`
  (`ThreadingHTTPServer`), `sqlite3`, `urllib`, `json`, `re`, `hmac`,
  `http.cookiejar`, `concurrent.futures`. No Flask/Django/requests.
- **One optional third-party lib:** `pywebpush` (+ its deps `py_vapid`,
  `cryptography`) for Web Push. If it's absent, push is disabled gracefully and
  everything else still runs.
- **Database:** SQLite (single file, `watches.db`).
- **Frontend:** server-rendered HTML with inline CSS + a little vanilla JS
  (school combobox, push subscription). No build step, no framework.
- **Reverse proxy:** Caddy (terminates origin HTTPS, proxies to the app).
- **Edge:** Cloudflare (DNS, CDN, DDoS, HTTPS, hides origin IP).
- **Host:** Oracle Cloud Always-Free VM (Ubuntu), runs as a `systemd` service.

## 3. Folder structure

See README.md. Summary: `app.py` (everything web), `schools.py` (data adapters),
`seatwatch.py` (shared helpers + ntfy notify). Flat by design.

## 4. Database architecture

SQLite, created/migrated in `init_db()` in `app.py`. Three tables:

- **`users`** — one row per Google account.
  `id, google_sub (unique), email, topic (unique ntfy channel), created`
- **`watches`** — one row per watched section.
  `id, school, topic, course, section, term, alerted, created, user_id`
  (`user_id` was added by an in-place `ALTER TABLE` migration; pre-account rows
  have `NULL` and are grandfathered.)
- **`push_subs`** — one row per browser/device that enabled web push.
  `id, user_id, endpoint (unique), p256dh, auth, created`

`alerted` on a watch is a latch: set to 1 when we alert, reset to 0 when the
section goes full again, so a reopening re-alerts once (no spam, no misses).

## 5. Authentication flow

Google OAuth 2.0 (authorization-code flow), implemented by hand with `urllib`:

1. `/login` → generates a random `state`, sets it in a short-lived cookie,
   redirects to Google.
2. Google redirects back to `/auth/callback?code=…&state=…`. We verify `state`
   matches the cookie (CSRF protection), then exchange the code server-to-server
   (with our client secret) for an `id_token`.
3. We decode the id_token and verify `aud` (our client id), `iss` (Google),
   `exp` (not expired), and `email_verified`. Fail any check → reject.
4. `get_or_create_user()` upserts the account; we set a **signed session cookie**
   `sw_session = userid.expiry.HMAC_SHA256(secret, "sess:userid.expiry")`,
   HttpOnly + Secure + SameSite=Lax, 90-day expiry.
5. Every request re-derives the user from that cookie via
   `read_session_value()`, which fails closed on any tamper/expiry.

Per-user **CSRF tokens** (`HMAC(secret, "csrf:userid")`) guard all POST actions
(watch / unwatch / push subscribe).

## 6. API routes (all in `app.py`)

GET:
- `/` — landing page + (if signed in) the watch form and the user's watches
- `/login`, `/auth/callback`, `/logout` — auth
- `/terms`, `/privacy` — legal pages
- `/sw.js` — service worker (web push)
- `/manifest.json`, `/icon-192.png`, `/icon-512.png` — PWA assets
- `/dev-login` — local testing only, gated behind `SEATWATCH_DEV=1` (404 in prod)

POST:
- `/watch` — create watches (auth + CSRF + rate-limit + per-account entitlement)
- `/unwatch` — stop a watch (only your own rows)
- `/push/subscribe` — save a device's web-push subscription (auth + CSRF), sends a
  test push immediately

## 7. Main components

- **`Handler` (BaseHTTPRequestHandler)** — routing, security headers, request
  parsing, all the endpoints above.
- **Poller (`poller()` / `run_cycle()`)** — background thread; every ~20s fetches
  every watched course (schools fetched concurrently via ThreadPoolExecutor),
  diffs against last state, sends alerts, and manages the health guard.
- **Health guard + operator alerts** — if a course returns no data N times in a
  row, it's paused and the operator (you) is pinged; daily "all healthy" digest;
  weekly automated **fire drill** that plants a synthetic watch on a real open
  section and verifies the whole detect→deliver path still works.
- **`schools.py` registry** — `SCHOOLS = {id: instance}`. Two families:
  1. **`Banner`** base class — one uniform Ellucian Banner 9 adapter; 100+
     schools are ~4-line subclasses (host + term + example course).
  2. **Per-school custom adapters** — UMD, Rutgers, Cornell, Penn (unique APIs)
     and big non-Banner schools: Virginia Tech (public Banner-8 timetable),
     CU Boulder / Brown / Yale (shared `Fose` base — the "fose" search API),
     Wisconsin (public enroll API, real seat counts), Iowa (MAUI API).
  Every adapter returns `{course: {section: {"open": bool, "seats": int|None}}}`
  and returns `{}` on any error — **never fabricates data.**

## 8. Third-party services

- **Google Identity** — sign-in.
- **Cloudflare** — DNS, CDN, edge HTTPS/DDoS, (planned) email routing.
- **Web Push services** (Google FCM / Apple / Mozilla autopush) — reached via
  VAPID; no account needed.
- **ntfy.sh** — legacy/backup push channel + the operator health channel.
- **Oracle Cloud** — the VM.
- Each **school's public registration system** — the live seat data source.

## 9. Environment variables (names only — never commit values)

Set in `/etc/seatwatch.env` on the server (root-only, read by systemd):

- `SEATWATCH_SECRET` — HMAC key for session + CSRF signing
- `GOOGLE_CLIENT_ID`, `GOOGLE_CLIENT_SECRET` — OAuth
- `VAPID_PUBLIC_KEY`, `VAPID_PRIVATE_PEM` (path), `VAPID_SUBJECT` — web push
- `SEATWATCH_BASE_URL` — e.g. https://seatwatchapp.com
- `SEATWATCH_ADMIN_TOPIC`, `SEATWATCH_ADMIN_USER` — operator alert routing
- `PORT`, `SEATWATCH_DB`, `POLL_SECONDS` — runtime config
- `SEATWATCH_DEV` — **local only**; enables the dev-login backdoor. NEVER set in prod.

## 10. Current features

- 120+ universities, live/accurate, self-maintaining across semesters (Banner
  schools auto-detect the new term).
- Google sign-in; per-account entitlement (currently: 1 free class, up to 2
  sections — payments not yet wired).
- First-party Web Push (installable PWA) + ntfy fallback.
- Full security hardening (see §12) and an automated weekly fire drill.

## 11. Current limitations / known issues

- **Payments not built.** Pricing is displayed ($0 first class, $19.95/additional
  course incl. all sections) but not enforced/charged. The site is effectively
  free right now (intentional, for early adoption).
- **Custom-adapter terms are hardcoded** (UMD, Cornell, Penn, VT, CU, Brown,
  Yale, Wisconsin, Iowa). The auto-term refresher only covers Banner schools, so
  these need a manual term bump each semester (or a per-school refresher).
- **Some big schools can't be added** without breaking accuracy — most large
  PeopleSoft/Workday schools have no public seat feed and are deliberately skipped.
- **iPhone web push** requires the user to "Add to Home Screen" first (Apple's
  rule); handled with an on-screen hint.
- **`support@seatwatchapp.com` isn't a live mailbox yet** — needs Cloudflare
  Email Routing set up to forward it privately.
- Single VM, single SQLite file — fine for current scale; would need work to
  scale to very high traffic (see §13 scalability notes in ARCHITECTURE.md).

## 12. Security posture (already in place)

- Parameterized SQL everywhere; regex input validation; output HTML-escaped.
- Signed session cookies + per-user CSRF tokens; fail-closed auth.
- Rate limiting (per real client IP via Cloudflare header, not spoofable XFF).
- Strict security headers incl. Content-Security-Policy, HSTS, X-Frame-Options.
- Body-size caps; safe handling of forged Content-Length.
- systemd sandboxing, fail2ban, unattended-upgrades, SSH hardening, firewall
  locked to needed ports; origin IP hidden behind Cloudflare.
- No secrets in code — all from env. Dev-login backdoor is env-gated (404 in prod).

## 13. Planned next steps

- Wire up payments (Merchant of Record + Stripe) to enforce the pricing tiers.
- Set up Cloudflare Email Routing for `support@seatwatchapp.com`.
- Continue adding high-population schools (custom adapters for big non-Banner ones).
- Per-school term auto-refresh for the custom adapters.
- Launch to first real users (UMD).

## 14. Files that are critical or risky to modify

- **`schools.py` `Banner` base class + `fetch()`** — 100+ schools depend on it.
  The `{}`-on-error / never-fabricate contract is sacred; a bug here risks fake
  alerts (reputation). Change with extreme care + full regression.
- **`app.py` auth block** (`read_session_value`, `session_cookie`, CSRF, OAuth) —
  a mistake here is a security hole. Don't loosen the fail-closed checks.
- **`app.py` `do_POST` entitlement logic** — the per-account limit under a lock.
- **`init_db()` migrations** — must stay backward-compatible (in-place ALTERs).
- **Do NOT move files into subfolders** — deploy scripts and the systemd unit
  reference these exact flat paths.
