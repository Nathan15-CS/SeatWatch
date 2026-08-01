# BETA PULSE — is the launch working?

Goal being tracked: **ten real UMD students with a live watch before add/drop closes.**
Newest entry at the top. Baseline = launch night, 2026-08-01.

---

## 2026-08-01 20:37 UTC
Source: `watches-20260801-030001.db` (13h old). vs baseline: users 6→6, watches 15→14.

**1. Any new person sign up and create a watch?** No. Zero new signups since 2026-07-30,
and that one was family. The user table is still the same six accounts. Watches went
*down* by one (15→14). The only activity in the last 48h was Nathan himself: a new umd
CMSC216 watch and an SMS opt-in, both 2026-08-01 02:35 UTC.

**2. Did anyone outside Nathan/family get an alert and click?** No. Both clicked alerts
(email, avg 46s) belong to users 5 and 6 — Nathan's own accounts. The other 7 attempts are
ntfy on legacy anonymous watches, 0 clicked. Nothing has changed here since launch night.

**3. Anything broken that would stop an alert?** No. `NO_CHANNEL` 0 · `blocked_wrong_term` 0 ·
0 RED cycles (23,271/23,321 GREEN) · no adapter flagged · backup 13h old. 1 SMS consent,
not revoked, no STOP outstanding, no SMS sent yet. The system is fine. Nobody is using it.

**Recommendation:** Nathan posts once, today, in r/UMD *and* the UMD CS Discord —
"I built a free tool that texts you when a CMSC seat opens, need 10 people to break it."
Zero outreach has happened, which is exactly why zero users have arrived. Coverage (853
schools) is not the bottleneck and will not become one.
