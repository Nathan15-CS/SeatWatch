# SeatWatch — Architecture (end-to-end)

How the whole system fits together, so a new engineer (or reviewer) can follow a
request and an alert from start to finish.

---

## The 10,000-foot view

```
                    ┌─────────────┐
  Student's phone → │  Cloudflare │  (DNS, HTTPS edge, DDoS, hides origin IP)
                    └──────┬──────┘
                           │  HTTPS
                    ┌──────▼──────┐
                    │    Caddy    │  (origin reverse proxy, :443 → :8080)
                    └──────┬──────┘
                           │  HTTP (localhost)
                    ┌──────▼───────────────────────────────┐
                    │  app.py  (ThreadingHTTPServer :8080)  │
                    │  ┌──────────────┐   ┌──────────────┐  │
                    │  │ HTTP Handler │   │   Poller     │  │
                    │  │ (requests)   │   │ (background  │  │
                    │  └──────┬───────┘   │  thread)     │  │
                    │         │           └──────┬───────┘  │
                    │      ┌──▼───────────────────▼──┐      │
                    │      │      SQLite (watches.db) │      │
                    │      └──────────────────────────┘      │
                    └───────────────┬───────────────────────┘
                                    │
              ┌─────────────────────┼──────────────────────┐
              ▼                     ▼                      ▼
      Google OAuth        schools.py adapters       Web Push / ntfy
      (sign-in)           (live seat data from       (deliver alerts
                           each university)            to phones)
```

Two independent loops share one SQLite database:
1. **The request loop** (HTTP Handler) — humans signing in and creating watches.
2. **The poll loop** (background Poller) — checking schools and firing alerts.

---

## Flow A — a student creates a watch

1. **Land & sign in.** `GET /` renders the marketing page. Not signed in → a
   "Continue with Google" card. `GET /login` sets a random `state` cookie and
   redirects to Google. Google returns to `GET /auth/callback`, which verifies
   `state` (CSRF), exchanges the code for an id_token, verifies
   aud/iss/exp/email_verified, upserts the user, and sets the signed
   `sw_session` cookie.

2. **Submit the form.** `POST /watch` with school, course, section(s), and the
   CSRF token. The handler, in order:
   - rate-limits by real client IP (Cloudflare `CF-Connecting-IP`);
   - re-derives the user from the signed cookie (fail closed if missing/invalid);
   - verifies the CSRF token;
   - validates the course format via `school.valid_course()` and section format
     via `SECTION_RE`;
   - **confirms the course actually exists right now** by calling
     `school.fetch({course})` (this also blocks watches on fake courses);
   - enforces the per-account entitlement **under a lock** (`_WLOCK`) so two
     simultaneous submits can't both slip past the free-tier limit;
   - inserts the watch row(s) tied to `user_id`, alerting through the account's
     stable ntfy `topic`.

3. **Turn on phone alerts.** On the success/home page the student taps "Turn on
   phone alerts." The browser registers `/sw.js`, requests notification
   permission, and creates a push subscription. `POST /push/subscribe` (auth +
   CSRF) stores `{endpoint, p256dh, auth}` in `push_subs` and immediately sends a
   **test push** so the student sees it working. (iPhone must "Add to Home
   Screen" first — Apple's rule — which the UI explains.)

---

## Flow B — the poller detects an opening and alerts

Runs forever in a background thread (`poller()`), every `POLL_SECONDS` (~20s):

1. **Load all watches**, grouped by school.
2. **Fetch every school concurrently** (ThreadPoolExecutor). Each
   `school.fetch(courses)` returns
   `{course: {section: {"open": bool, "seats": int|None}}}` — or `{}` on any
   error. `_school_fetch` wraps this so a crash becomes `{}` (never raises).
3. **Health guard.** If a course returns no data, increment a failure counter;
   after N consecutive failures pause it and ping the operator. **A course with
   no data is skipped, never alerted** — this is the "never fake" guarantee.
4. **Diff + alert.** For each watched section: if it's now open and its `alerted`
   latch is 0 → send the alert and set `alerted=1`. If it's full again and
   `alerted=1` → reset to 0 (so a future reopening re-alerts once).
5. **Deliver.** `_alert()` sends the notification via **both** Web Push
   (`send_web_push()` → every device the account registered) **and** ntfy (the
   account's topic). Dead push subscriptions (HTTP 404/410) are pruned.
6. **Self-maintenance, on the same loop:** daily "all healthy" operator digest;
   once/day, Banner schools auto-detect the new semester's term (verify-before-
   adopt, else keep last-known-good); weekly **fire drill** that plants a
   synthetic watch on a genuinely-open real section and confirms the full
   detect→deliver path, paging the operator on PASS or (loudly) on FAILURE.

---

## The data layer — `schools.py`

Every school is an object with `valid_course()`, `reg_url()`, and
`fetch(courses)`. The registry `SCHOOLS = {id: instance}` is read dynamically by
`app.py`, so adding a school is purely additive.

**The sacred contract:** `fetch()` returns only data it truly read. On *any*
failure (network, parse, unexpected shape) it returns `{}`. The poller treats
`{}` as "skip," so a broken school goes **silent**, never sends a false "open."
Seat counts are clamped to ≥0; `open` must be consistent with `seats` when a
count exists.

Two families of adapter:

- **`Banner` base class** — Ellucian Banner 9 exposes an identical JSON class-
  search API at every school; only host + term differ. So 100+ schools are tiny
  subclasses. Reads `seatsAvailable` (the true count), never the misleading
  `openSection` flag. Includes retry/backoff, multi-entity (`mepCode`) and
  shared-pool (`campus` filter) support, and daily term auto-refresh.

- **Custom adapters** for schools with their own systems:
  - **UMD / Rutgers / Cornell / Penn** — bespoke public APIs.
  - **Virginia Tech** — public Banner-8 timetable with an authoritative
    "open only" filter (section id = CRN).
  - **`Fose` base → CU Boulder / Brown / Yale** — the shared "fose" search API;
    `stat` field `A`=open / `F`=full.
  - **Wisconsin** — public enroll API; gives status **and exact seat counts**.
  - **Iowa** — MAUI API; authoritative `sectionStatus`, grouped per-department
    for efficiency.

Each proven "shape" (Banner 9, Banner-8 timetable, fose, enroll-API, MAUI)
becomes a reusable pattern for the next school that uses the same system.

---

## Security model (where the guarantees live)

- **Auth fails closed.** `read_session_value()` rejects any cookie that isn't a
  valid, unexpired HMAC. CSRF tokens gate every state change.
- **No trust in client input.** Course/section regex-validated; existence checked
  against live data before storing; SQL always parameterized; HTML output escaped.
- **Abuse control.** Rate limit keyed on the unspoofable Cloudflare client-IP
  header; request body size capped; forged `Content-Length` handled safely.
- **Defense in depth.** Strict CSP/HSTS/X-Frame-Options; systemd sandbox;
  fail2ban; firewall; origin IP hidden behind Cloudflare; secrets only in env.
- **Reputation = "fail closed."** The single most important invariant: when in
  doubt, say nothing. Silence is acceptable; a false "seat open" is not.

---

## Scalability notes (honest)

Current scale (one small VM, one SQLite file, a handful of concurrent watches)
is comfortably handled. Things to revisit if usage grows large:

- SQLite is fine for thousands of watches but is single-writer; heavy write
  concurrency would eventually want WAL mode tuning or Postgres.
- The poller fetches every watched course every cycle; at very high watch counts
  you'd batch/stagger per school and add caching per (school, course).
- One VM is a single point of failure; a second instance + managed DB would add
  redundancy. Not needed at current scale, and adds cost — deliberately deferred.
