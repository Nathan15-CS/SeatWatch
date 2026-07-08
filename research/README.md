# Cross-session research handoff

Validated research artifacts shared between parallel SeatWatch expansion sessions.
Commit new findings here so other sessions don't redo probing work.

## Minnesota State (eservices.minnstate.edu) — research COMPLETE, build NOT started
One public search serves all 33 MN State colleges/universities. Verified live July 8, 2026.

- `mn_subjects.json` — Fall 2026 subject code -> title maps for all 33 campuses (rcid-keyed)
- `mn_examples.json` — validated example course per campus (picked = most sections in BIOL/ENGL/etc, Fall 2026)

**Endpoint recipe (all verified):**
- Search (single unauthenticated GET, no cookies):
  `https://eservices.minnstate.edu/registration/search/advancedSubmit.html?campusid={CID}&searchrcid={RCID}&searchcampusid={CID}&yrtr=20273&subject={SUBJ}&courseNumber={NUM}&resultNumber=250`
  where RCID = 4-digit id from mn_subjects.json keys, CID = RCID with ONE leading zero dropped ("0071"->"071" — exact string matters, "71" serves a broken slim page).
- yrtr: 20273 = Fall 2026 (year+1, digit 1=Summer 3=Fall 5=Spring). Bump manually per semester.
- Status: each section row has `<span class="status-open">Open</span>` / `<span class="status-closed">Full</span>`. No seat numbers -> seats=None, open-only reads (CUNY model, can't false-alert).
- Results page echoes `Search Results for <b>Fall 2026` — use as term/format sanity guard.
- ALWAYS pass courseNumber (exact match, letter suffixes like 515G work): subject-wide queries hit the 250-row cap (Mankato BIOL = 247 rows).
- Sections keyed by "Sec" column ("01","54"); verified unique per (subj,num) incl. two-campus Anoka-Ramsey. Row order: ID#(6-digit), Subj, #, Sec, ..., status span.
- Subject dropdown scrape (per campus): `basic.html?campusid={CID}&searchrcid={RCID}&searchcampusid={CID}&yrtr=20273` — searchrcid param is REQUIRED or you get the slim no-campus page.
- Native waitlist exists but is per-department opt-in, email-only, 24h claim window (same posture as CUNY -> shipped anyway).

## KCTCS (Kentucky, 16 colleges) — probing IN PROGRESS (this section: July 8, 2026)

**Public JSON API found**: `https://class-search.kctcsweb.com/api` (the official kctcs.edu/class-search.aspx widget backend, Laravel, no auth):
- `/terms` -> `{term_code: 4264, term_description: "Fall 2026"}` (also 4256 Spring, 4262 Summer 2026)
- `/subjects?college={NAME}&term=4264`, `/courses?college=...&term=...&subject=BIO` (catalog numbers)
- `/search?college={NAME}&term=4264&subject=BIO&page=N` — 20/page fixed, ordered by catalog_number,
  rows have EVERYTHING: section, number (PS class nbr), catalog_number, **enrolled, max_enrollment,
  enrollment_status (O/C)**, instructor, meeting info. (cat,section) unique; dedupe rows by `number`
  (multi-meeting rows repeat with meeting_number>1).
- College keys = uppercase names: ASHLAND, BIG SANDY, BLUEGRASS, ELIZABETHTOWN, GATEWAY, HAZARD,
  HENDERSON, HOPKINSVILLE, JEFFERSON, MADISONVILLE, MAYSVILLE, OWENSBORO, SOMERSET, SOUTHCENTRAL,
  SOUTHEAST, WEST KENTUCKY. `kctcs_subjects.json` = Fall 2026 subject maps for all 16.

**⚠️ FRESHNESS UNRESOLVED — DO NOT BUILD ON THIS YET**: every row (1,462 sampled across all 16
colleges) has created_at == updated_at == 2026-05-05. Either a dead May snapshot (fails
[[flawless-accuracy-nonnegotiable]]) or a sync that bulk-upserts without touching timestamps.
Delta-watch running (enrollment diffs over ~2h of active fall registration) — verdict pending.

**Live-PeopleSoft fallback (if mirror is dead)**: students.kctcs.edu/psc/stdsaprd/EMPLOYEE/SA/c/
SSR_STUDENT_FL.SSR_CLSRCH_MAIN_FL.GBL loads as guest (no login) incl. deep-link params, but results
render via ICAJAX; blind replay attempts got blank envelopes (state advances, no content). Needs a
real browser session to capture the exact ICAction/payload (Chrome extension was disconnected).
Classic CLASS_SEARCH.CLASS_SEARCH.GBL is also a JS shell. COMMUNITY_ACCESS.K_OLA_LANDING_FL.GBL is
just the application portal — dead end.
