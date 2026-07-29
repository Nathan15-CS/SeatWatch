# SeatWatch — Security / Privacy Control Tracker (authoritative working copy)

Phase-1 audit. **Read-only — no code, infra, prod or legal copy was changed.**
Rule: **NO ASSUMED PASS.** A control is PASS only with concrete evidence (file:line, config,
passing test, or live prod check). Anything unverifiable stays UNKNOWN.
No secrets, tokens, phone numbers or DB contents appear in this file.

Audited: 2026-07-28 · Gate 0 + Gate 1 rows first (beta-blockers).

---

## PASS (evidence recorded)

| # | Control | ASVS | Evidence |
|---|---|---|---|
| 1 | **Account isolation / IDOR** | 4.1, 4.2 | Static: every destructive query owner-scoped — `DELETE FROM watches WHERE id=? AND user_id=?` app.py:2481; `DELETE ... WHERE user_id=? AND school=? AND course=?` :2566; `SELECT ... WHERE user_id=?` :1773/:2526/:2551/:2903/:3007. Bare `DELETE FROM push_subs WHERE id=?` :2928 is safe — id comes from the user-scoped SELECT at :2903, no request path supplies it. Dynamic: 2-account sweep, 8/8 — A cannot delete B's watch by id, cannot see B's watches/phone/devices/feedback; CSRF tokens per-user; session cookie signed, not a bare id. |
| 2 | **CSRF on state-changing POSTs** | 4.2.2 | Shared guard app.py:2474 runs **before** path dispatch → covers `/watch`, `/unwatch`. Per-route: `/feedback` :2364, `/sms/optin` :2399, `/push/subscribe` :2437. All 5 covered. |
| 3 | **SQL injection** | 5.3.4 | All queries parameterised. Single f-string exec (app.py:434) interpolates only `?` placeholders for an `IN` clause; values passed as bound params. |
| 4 | **Session cookie security** | 3.4.1–3.4.3 | `HttpOnly; Secure; SameSite=Lax; Path=/; Max-Age` app.py:376-377. HMAC-signed with expiry, verified `hmac.compare_digest` :388 — forged/expired/tampered all fail closed. SameSite=Lax (not Strict) is required for the OAuth return. |
| 5 | **Secrets not in repo** | 14.3 | No secrets in git history — an initial 22 "matches" were **commit-hash false positives** (`AC[0-9a-f]{32}` matching SHAs); precise re-scan returns none. No `.env`/`.pem` ever tracked; `vapid_private.pem` untracked. `ORG/records/stage-0b-credential-custody.md` records custody only, contains no values. |
| 6 | **Payments dormant** | — | Live prod: `PAID_ENABLED=False`, `PAID_LIVE=False`; a tier-3 user resolves to `effective_tier=0`. `/checkout` 302s. No charge is possible. |
| 7 | **SMS dormant** | — | Live prod: `SMS_ENABLED=False`, `SMS_LIVE=False`. Outbound structurally impossible. |
| 8 | **Security headers (HTML)** | 14.4 | app.py `_send()`: CSP `default-src 'none'` + allowlist, HSTS 180d, `X-Frame-Options: DENY`, `X-Content-Type-Options: nosniff`, `Referrer-Policy: no-referrer`. |
| 9 | **Admin endpoint auth** | 4.1 | `/admin/stats` requires `STATS_KEY` via `compare_digest` (app.py:2160) **and** rate-limit; 404s when the key is unset (it is unset in prod). Returns aggregates only, no PII. |
| 10 | **Rate limiting** | 11.1 | `rate_ok(client_ip)` on the shared POST path (app.py:2328) and `/admin/stats` (:2159). |
| 11 | **SMS consent enforcement (TCPA)** | — | Server-side: no consent row can be written without an explicit checked box; `users` has no phone column, so `sms_consent` is the only phone store. Proven against the real parser (unchecked + empty both blocked). Disclosure string byte-identical on page and in code. |

---

## FAIL / GAP — remediation pending Nathan's approval

| # | Control | Sev | Gate | Finding & fix |
|---|---|---|---|---|
| F1 | **No `Cache-Control` on authenticated HTML** | **HIGH** | 1 | `_send()` sets CSP/HSTS/XFO but **no cache directive**, so the signed-in dashboard (email, watched courses, phone last-4) ships with none. Not leaking today (prod shows `cf-cache-status: DYNAMIC`) — but that is Cloudflare's *default*, not an assertion we control. Realistic path: **shared campus/library machine**, back-button after logout serving the previous user's page. Also any future "Cache Everything" rule. **Fix: one line** — `Cache-Control: private, no-store, max-age=0` (+ `Pragma`/`Expires` for old proxies) in `_send`. ~2 min. Deploy **isolated**. |
| ~~F2~~ | ~~SPF record missing~~ **RESOLVED 2026-07-28** | HIGH | 1 | Operator added it. Verified from 8.8.8.8: `v=spf1 include:_spf.google.com ~all`. |
| ~~F3~~ | ~~DMARC record missing~~ **RESOLVED 2026-07-28** | MED-HIGH | 1 | Operator added it. Verified from 8.8.8.8: `v=DMARC1; p=none; rua=mailto:support@seatwatchapp.com; fo=1` (fo=1 adds failure reporting — a good addition). |
| F5 | **`www.seatwatchapp.com` does not resolve** | LOW | 2 | No DNS record; anyone typing `www.` gets an error page, and a carrier reviewer visiting it sees nothing. **Fix (DNS, operator):** CNAME `www` → `seatwatchapp.com`, proxied. |
| F4 | **`/r/<token>` GET writes to DB, unrate-limited** | LOW | 2 | The click-tracking redirect stamps `clicked_at` on a GET and is not covered by `rate_ok` (that guards POSTs). Worst case is inflated click metrics / minor DB churn — no PII exposure, no auth bypass. Consider rate-limiting or making it idempotent-cheap. |

**Note (F2/F3 — now RESOLVED):** all three of SPF, DKIM and DMARC are live and verified. DKIM was already present (Google selector, valid key). Evidence-based recommendation
of record: SPF+DMARC are the load-bearing, provider-independent fix; Google Workspace SMTP is
adequate for Gate 0–1 beta volume; a dedicated provider (SES/Postmark/Resend) is deferred to
Gate 2–3 when bounce/complaint webhooks and volume justify it.

---

## UNKNOWN / not yet audited

- Accessibility (a11y) conformance — not started.
- Marketing/legal copy review (claims vs. reality) — not started.
- Anti-bot beyond IP rate-limiting (no CAPTCHA; abuse signals exist but are soft).
- Incident-response runbook — recovery is documented (`ops/RECOVERY.md`) and the data path is
  drill-proven, but **full host rebuild is never rehearsed**, and `/etc/seatwatch.env` secrets
  are **not backed up** (losing VAPID keys silently breaks every push subscription).
- Dependency/supply-chain review (`pywebpush` and its transitive deps).
- Adapter-layer security (SSRF surface from 804 outbound hosts) — outbound only, no
  user-controlled URLs, but not formally reviewed.
