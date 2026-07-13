# SeatWatch research — working summary (LEAN)

Cross-session research log for SeatWatch school expansion. **This file is kept lean on purpose** —
the full chronological batch-by-batch history lives in `research/ARCHIVE.md` (grep it for any past
detail). Read THIS file + the lane files; only open ARCHIVE for a specific past finding.

- **Live count: 649 schools** (goal 1,000; Onondaga committed, awaits Nathan's deploy). Session
  start was 634; verified from `len(schools.SCHOOLS)` on July 11, 2026.
- **Who's doing what right now:** `research/lane-fable.md` + `research/lane-codex.md` (short, always current).
- **How we work / accuracy+efficiency gate:** `research/PARTNER-NOTE-codex.md` and repo-root
  `CONTRIBUTING_AGENT.md`. Handoffs to the builder go through Fable; gated-but-unapproved candidates
  get a heading containing the phrase **`AWAITING GO-AHEAD`** (grep for it to find every pending item).

---

## PENDING HANDOFFS (grep `AWAITING GO-AHEAD`)

### Parser lever — ✅ BUILT + DEPLOYED July 12: CCRI + NC A&T + HGTC, 677->680 (~33k)
Re-diagnosed (seat parser was fine; gap = CRN discovery from non-standard LISTINGS). Refactored to a
_crns() hook + TWO reusable fixes: TabularBanner8 (column-table listings, strict exact Subj+Crse
match -> CCRI 136 sec 53 full); widened classic CRN pattern \d{5}->\d{4,5} (4-digit CRN hosts ->
HGTC 18 sec). NC A&T was plain ListcrseBanner8 all along (wrong term originally; Fall=202710). All 3
gated live, zero false-open, 5-digit regression clean. Both fixes REUSABLE to re-sweep hosts wrongly
cut as dead (tabular-listing or 4-digit-CRN Banner-8).

### Chabot + Las Positas — ✅ BUILT + DEPLOYED July 12: 675->677 (2 schools, 1 CampusBanner8 variant)
Chabot-Las Positas district shares ONE Banner-8 host; plain adapter mixes campuses. New
CampusBanner8(Purdue): sel_camp=<code> pre-filter (verified disjoint) + per-CRN structured
'{Campus} College Campus' verification (the shared-district chrome names both colleges — a bare
name regex false-matches; that trap cost real gate time, now guarded). Chabot ENGL 1 = 68 sec 40 full;
LP MATH 1 = 23 sec 6 full; cross-campus CRN overlap = EMPTY. LP uses own numbering. LIVE.

### University of New Mexico — ✅ BUILT + DEPLOYED July 12 (batch 30): 674->675 (commit 06d957d)
UNM Albuquerque flagship (~25k), drops into ListcrseBanner8. NM 4-digit course numbers.
Re-gated live: ENGL 1110 122 sec 25 open/97 FULL (123 real-full disproof across sample), zero
open-with-no-seat, completed 202610 reproduced. Latency: worst-case ENGL 1110 74s cold / 0ms warm
(cache-backed Purdue/TAMU pattern, confirmed NOT Drake per-poll-slow — warm 0ms). LIVE on prod.
Codex batches 13-20 rest: CVC/Quottly + stale-PDF holds (correct); bespoke leads (Monroe CC/Clark/
Wabash/Wesleyan/Dickinson-reserved) on Builder bench, lower priority.

### University of Oregon — ✅ BUILT July 12 (batch 12): 673->674
Bespoke UOregon DuckWeb adapter. Grabber's silent-miss concern RESOLVED: the per-CRN detail route
parses inconsistently, so seats are read from the LISTING's header-confirmed 'Avail' column (one POST
per course, no N+1). open=Avail>0. Exact-scope via colspan course-title group cell. Gate: MATH 251Z
12 sec 11/1, WR 121Z 18 real full rows, ENG 101 5 sec 2/3, ZERO seats=None anywhere; completed 202503
7/1; term auto-rolls (resolves 202601). Oregon renames courses w/ 'Z' suffix (251->251Z). USVI +
Lawrence still on bench (both bespoke, smaller). ⚑ COUNT-BUMP GOTCHA: app.py SVG path coords now contain
'673'/'674' — blind replace_all corrupts them; use targeted count-string replacement (the assert caught it).

### Batch 29 (MTSU + Framingham) — ✅ BUILT July 12: 671->673
Two Codex "adapter needed" leads that actually DROP INTO ListcrseBanner8 (catalog route, like
WSSU/NCCU). Re-gated live: MTSU ENGL 1010 147 sec 84 open/63 FULL (~42s cold N+1 then 10-min cache,
Purdue/TAMU pattern), completed 202610 16 full; Framingham live CHEM 107 2 FULL + completed 202620
ANTH 206/COMM 280 FULL — both independently reproduced. Per-host Fall codes differ (MTSU 202680,
Framingham 202690). RPI HELD by Grabber (live term all-open = fails numeric live-full disproof;
correct hold — revisit when it fills). Deploy pending Nathan (covers 656-673).

### Batch 28 (College Scheduler vein) — ✅ BUILT July 12: Ivy Tech + UT Arlington + U Alaska, 668->671
New CollegeScheduler GraphQL family. BOTH traps live-verified: fuzzy findCourses (exact filter
mandatory — 'BIOL 101' ranks 221/211/201/240 first) AND a pagination trap Grabber's spec missed:
getCourseSections caps at 60/page — Ivy Tech BIOL 101 is really 71 sections (handoff said 40).
Adapter paginates via Relay cursors and SKIPS any course still truncated at 360 (no hidden watched
sections, ever). open = openSeats>0, CRN keys, live-full-row disproof per school (1/7 full at Alaska,
18/71 Ivy Tech, 12/35 UTA). Term picker reads the API's own term list, handles both name orders
('Fall 2026' vs UTA's '2026 Fall'). ~133k students. Alaska ships as ONE system-wide entry (CRN-unique
across campuses). Deploy pending Nathan (covers 656-671).

### College Scheduler / Civitas GraphQL — Batch 28 SENT July 12 2026 (Grabber, Nathan-approved) — NEW VEIN, 3 big net-new schools, needs 1 bespoke adapter
Fresh system type (not Banner/Colleague/PeopleSoft). College Scheduler (Civitas Learning) runs a
PUBLIC, no-auth **GraphQL** API that returns clean numeric seats. ONE adapter serves every school that
has the public "Course Search" enabled. Confirmed 3 LIVE + CURRENT + net-new (all deduped vs schools.py):
- **Ivy Tech Community College (IN)** ~65k — slug `ivytech`, Fall 2026 `202620`; BIOL = 196 sec, 77 open/19 FULL.
- **University of Texas at Arlington** ~42k — slug `uta`, Fall 2026 `2268`; BIOL = 513 sec, 24 open/17 FULL sampled.
- **University of Alaska (system)** ~26k — slug `alaska`, Fall 2026 `202603`; campus field splits UAF/UAA/UAS;
  BIOL = 322 sec, 9 open/18 FULL sampled.
**Recipe (blind-reproducible):** `POST https://api.collegescheduler.com/graphql`, header
`Origin: https://{slug}.search.collegescheduler.com`, no auth.
- terms: `{ environment(name:"{slug}"){ courseSearchTerms{ code name } } }` (auto-pick current, like Banner picker)
- courses: `{ environment(name:"{slug}"){ findCourses(termCode:"{code}", query:"BIOL 201", includeFullCourses:true, first:20){ edges{ node{ id courseNumber title } } } } }`
- sections: `{ environment(name:"{slug}"){ getCourseSections(courseId:"{id}", includeFullSections:true, first:50){ edges{ node{ registrationNumber sectionNumber openSeats totalSeats campus } } } } }`
**⚠️ ACCURACY-CRITICAL:** `findCourses` is FUZZY/RANKED, not exact — query "BIOL 101" returns BIOL 221,
211, 201, 240, THEN 101. Adapter MUST filter edges to EXACT `subject.shortName == SUBJ AND courseNumber
== NUM` before taking the courseId (first result = wrong course = false alerts). `subject` fields are
`shortName`/`longName` (NOT `abbreviation`).
**Gate rule:** open = `openSeats > 0`; `totalSeats` = capacity. Section key = `registrationNumber` (CRN,
verified UNIQUE — no collapse). Disproof PASSED at all 3 (live FULL rows openSeats=0 with totalSeats>0 —
real enrollment, can't fake). No status enum to distrust. ~1-2s. Example courses (exact, 2+ live sec):
ivytech BIOL 101 (40 sec), uta BIOL 1441/1442, alaska BIOL F111L (8 sec).
**Caveats (honest):** public Course Search is OPT-IN — most CS clients gate it behind SSO (asu/duke/alamo/
bgsu/odu/vcu/ku resolve `environment` but `courseSearchTerms`=null). CT-log undercounts slugs (wildcard
certs), so the full public roster isn't enumerable; these 3 are confirmed, more may exist. Needs a bespoke
`CollegeScheduler` adapter (source-gated, NOT production-gated — no existing adapter). Relayed to Builder
as Batch 28 (Nathan-approved) with the exact-match rule above. Data: research/collegescheduler_lead.json.


### Winston-Salem State University — ✅ BUILT July 12 (batch 27): 667->668
ListcrseBanner8 on NCCU's UNC-ECS sibling host. Re-gated live: Fall BIO 1113 = 6 CRNs 2 open/4 FULL;
completed Spring 202620 = 5 CRNs 3/2 — both disproofs hold, Grabber's numbers reproduced exactly.
2.2s. RCCD×3 added to Builder's held-adapter bench (bespoke SharePoint API) alongside Fairfield +
SDCCD×3. Deploy pending Nathan (covers 656-668).

### Worcester State University — ✅ BUILT July 12 (batch 26): 666->667
Plain NewColleague subclass (EN not ENGL; != WPI). Re-gated live: 39 sections across EN/BI/PY 101,
9 open/30 FULL, zero open-with-no-seat; family disproof satisfied (30 live full rows, non-0 status).
2.4s. Grabber's first relay — evidence reproduced exactly. Deploy pending Nathan (covers 656-667).

### Winston-Salem State University (NC) — Batch 27 SENT July 12 2026 (Codex find, Grabber re-gated + relayed, Nathan-approved)
~4,972 students, public 4-year (HBCU). Sibling of already-shipped NCCU on the same UNC-ECS Banner-8
host pattern — fits existing `ListcrseBanner8`. Suggested subclass:
`base="https://ssbprod-wssu.uncecs.edu/pls/WSSUPROD"; term="202680"; example="BIO 1113"` (Fall 2026 =
202680 here; completed Spring 2026 = 202620, per-host term semantics — labels win, batch-23 lesson).
Re-gated LIVE through production `ListcrseBanner8.fetch()`: BIO 1113 = 6 sec (2 open/4 FULL, real seats
[0,1,0,5,0,0]); completed 202620 BIO 1113 = 5 sec (3 open/2 full) — BOTH disproofs hold, numeric
Cap/Act/Rem verified (Remaining==Capacity-Actual). Dedup clean. Relayed to Builder as Batch 27.

### Shorter College (AR) — HELD, NOT ship-ready (Grabber production re-gate July 11 2026)
Codex flagged it "production-compatible," but the production `NewColleague.fetch()` re-gate FAILS the
fake-open disproof TODAY: ENGL 2803 = 1 live section, OPEN, no full rows; ENGL 1301/BIOL 1101 = no data.
Tiny 2-yr HBCU (North Little Rock) — too few sections to show a live FULL row, and this Colleague family
can't query the completed term through the adapter (guest search indexes active plan terms only), so
Codex's Fall-2025 non-open evidence isn't reproducible via production. A single all-open section is
exactly the fake-open profile I won't ship. DO NOT relay until a live full row (or an adapter-verifiable
completed-term non-open row) exists. Handed back to Codex's lane to re-establish or drop.

### State College of Florida — ✅ BUILT July 11/12 (batch 25): 665->666 (commit follows Berkeley's)
CT-log-vein first ship. Plain Banner-9 subclass on non-guessable banner.banprod.scf.edu. Re-gated
live: ENC 1101 = 82 sec, 24 open/58 genuinely FULL (live Act==Cap disproof); completed Fall 2025
ENC 0022 reproduced spec exactly (1 open/5 full). 1.4s. Deploy pending Nathan (covers 656-666).

### UC Berkeley — ✅ BUILT July 11: reserved-seat adapter shipped, 664->665 (commit 4b0034d)
The held accuracy question is RESOLVED and live-verified: open = status 'O' AND
(maxEnroll - enrolledCount - openReserved) > 0. The trap case reproduces exactly — BIOLOGY 1A/1AL
read 'Open' with 21/20 seats, ALL cohort-reserved -> correctly WITHHELD; BIOLOGY 1B shows its real
1 unreserved seat per lecture; COMPSCI 61A 620 unreserved of 1,253 (phased reservations); completed
Spring status-C rows withheld. ENGLISH R1A stress 14 sections 21s cold/0ms warm (TTL cache).
Exact scoping by slug fragment; spaced subjects slugify by deletion (POL SCI->polsci). Term facet
auto-rolls from page labels verify-before-adopt. BONUS infra: refresh_all_terms now duck-types on
refresh_term (was a hardcoded isinstance list) — one-off adapters self-maintain. Deploy pending
Nathan (covers 656-665). Remaining held: Fairfield + SDCCD×3 (next).

### Batch-23 cuts RESURRECTED — ✅ BUILT July 11: all 5 shipped on ListcrseBanner8, 659->664 (commit 9751801)
Missouri State (~24k, 81 CRNs 49/32, 14s cold), Toledo (~20k, 31 CRNs 19/12, 9s — its 202710 =
SPRING 2027, pinned/detected 202640), Stephen F. Austin (58 CRNs 46/12, 18s — 202710 IS Fall 2026
there; per-host code semantics differ, labels win), Alabama A&M (61 CRNs 3 open/58 full, 15s),
Utica (3 CRNs 1/2, 1s). All re-gated through registered production adapters; warm fetches 0ms
(per-instance cache verified before adding 5 instances). Completed-term evidence per school in the
commit; NEW LESSON at Utica: completed terms on numeric-ENROLLMENT sources show end-of-semester
melt (can be all-open legitimately) — the fake-open disproof there is live-term Act==Cap full rows,
which can't be fabricated. South Texas College re-checked: dead as cut (Banner-9 host, no listcrse
route, empty subjects stand). Deploy pending Nathan (covers 656-664).

### Otis College of Art and Design — ✅ BUILT July 11 (batch 24): 658->659 (commit 016a5b9)
Plain Banner-9 subclass. Re-gated live through the registered production adapter: Fall 2026 ENGL 108
= 12 sec 8 open/4 full, real integer seats; completed-term reproduced through production (Fall 2025 =
11 sec, 3 genuinely full). 2.0s, letter section keys unique, dedup clean. Relay's own production-gate
numbers matched live exactly. Deploy pending Nathan (covers 656-659).

### Codex adapter queue, cleanest 3 — ✅ BUILT July 11: UNCG + NCCU + UNC Asheville, 655->658 (commits 701a38f + 90d23df)
All 3 gated through the registered production path; zero false-open risk. Deploy pending Nathan.
- **UNCG (~18k)**: plain Banner-9 subclass — no bespoke code needed (Codex's endpoints = the standard
  family flow). Verified AT THIS HOST: zero closed-but-seats>0 rows in current AND completed terms;
  completed Spring's 6 waitlist-only "open" rows correctly withheld by the family seats>0 rule. 1.4s.
- **NCCU (~8k)**: new `ListcrseBanner8` variant — guest search form answers "No classes were found"
  for everything, but catalog `bwckctlg.p_disp_listcrse` serves the sections. 16 CRNs 2 open/14 full
  (matches Codex exactly); Cap/Act/Rem detail verified; completed-term test reproduced through the
  production builder (Spring 202620: 7 CRNs, 6 full). 3.3s cold / 0ms warm (Purdue-pattern cache).
- **UNC Asheville (~2.8k)**: bespoke meteor.unca.edu JSON adapter; whole-term dump + 10-min TTL cache,
  stale-if-error. open = Classification.Open AND remaining>0 — flag agreed with arithmetic 1,654/1,654
  rows across live + completed terms, CRNs unique. Exact-course scoping via "SUBJ NUM." prefix. 0.4s.
- ⚑ FOLLOW-UP LEAD (big): the same listcrse route shows LIVE sections at the batch-23 cut hosts —
  Toledo 31 CRNs, Missouri State 81 (matching Fable's original counts!). They were search-form-blocked,
  not unpublished. All 5 cuts are re-gate candidates on `ListcrseBanner8` in a future pass.
- HELD per mandate (accuracy questions open, task-tracked): Berkeley (reserved-seat subtraction),
  Fairfield (no completed term + whole-dump cache), SDCCD×3 (status semantics + 4k-row dump cache).

### Batch 23 (Banner-8) — ✅ BUILT July 11: SHIPPED 2 of 7, CUT 5 — 653->655 (commit 60ba544)
Nathan's condition was "only send it if you can get flawless efficiency AND accuracy" → gated all 7
LIVE through the production Purdue Banner-8 adapter; shipped ONLY the clean passes.
- SHIPPED: **Bristol Community College (MA)** (ENG 101, 65 sec 57 open/8 full, Rem==Cap-Act verified on
  raw detail, CRN-keyed, 12s cold/~0ms warm) + **Clovis Community College (NM)** (real course is
  **ENGL 1110**, handoff's "ENGL 111" was wrong; 6 sec, Rem==Cap-Act verified). Both flawless.
- CUT 5: **Missouri State, Toledo, Stephen F. Austin, Alabama A&M, Utica** — every one returned Banner's
  "No classes were found" for ALL 6 subjects probed (Eng/Math/Bio/Psy/Hist/Chem) in the correct term;
  guest Fall schedule not published to guest search yet. Not a false-open risk (empty=safe) but a
  non-functional feature → cut per mandate. Revisit when their terms load.
- ⚑ PROCESS: handoff data was wrong for 6/7 (Toledo term 202710 = **Spring 2027** not Fall 2026;
  Clovis number wrong; 5 schools returned zero live data despite handoff claiming section counts). The
  live production gate caught all of it. Fable's gate and the relayed spec diverged from live — worth a
  look at why before the next Banner-8 pass.
- ADAPTER FIX (accuracy-critical): moved Purdue's _cache/_lock/_active_term to PER-INSTANCE state — the
  (term,subj,num) cache key has no school id, so a shared class-level cache would have cross-served seats
  between schools on the same term (Toledo/SFA/Purdue all 202710). Now 3 isolated instances.

### Batch 22 (Lebanon Valley, Augustana IL, Camden County, Walsh College) — ✅ BUILT July 11: 649->653 (commit 361008f)
All 4 newer-Colleague schools registered + re-gated LIVE through the production path this session
(NewColleague/YearSpanNewColleague infra had arrived pre-committed in dc5ffd0 from another builder
session; re-verified regardless of author). Accuracy gate PASSED on all 4 — the numeric-0-fake-open
trap is disproven on EVERY row: full-by-arithmetic sections (enrolled==capacity) ALWAYS carry non-0
status (LVC/Walsh full=1, Augustana/Camden full=2); status-0 rows ALWAYS have a bookable seat;
Available==Capacity-Enrolled held 19/19 rows; keys unique; exact-course scoping isolates the watched
course; Augustana term picker landed on '2026-27 Fall Semester' correctly; latency <=2.5s. Zero
false-open risk. Clears the entire newer-Colleague backlog. Awaiting Nathan's manual deploy (Onondaga
649 + these 4 all deploy together). Original relayed specs below for the record.

### Lebanon Valley College (PA) — Batch 22 SENT July 11 2026 (Codex find, Fable relayed)

Clean net-new newer-Colleague add. Official public catalog: `https://selfservice.lvc.edu/Student/Courses`;
production host `selfservice.lvc.edu`; endpoints are `POST /Student/Courses/SearchAsync` and
`POST /Student/Courses/SectionsAsync` with the JSON-string `searchParameters` payload. School is a
small four-year college (officially about 1,674 undergraduates and 416 graduate students).

- Production newer-Colleague fetch of `BIO 111L` returned 8 unique sections in 2.07s: six numeric
  `status=0` rows with 1/2/1/5/1/1 seats and two `status=1` rows with zero seats. Source search was
  0.36s and section detail 0.45s; all eight publish `AreSeatCountsAvailable=true` and
  `Available == Capacity - Enrolled` held 8/8.
- Current term is `26/FA` / Fall 2026 with registration 2026-03-30 through 2026-08-23. Use the
  current-term picker; this API family does not expose a reliable literal completed-term result.
  Full-by-arithmetic rows were nonzero-status, so the conservative production rule is
  **numeric `status==0` AND `Available>0` AND seat counts available**.
- Exact `SubjectCode + Number` filtering is mandatory: keyword `BIO 111` leaks `BIO 111L` and other
  subjects numbered 111. Section IDs/numbers were unique; name/host dedup is clean.

### Augustana College (IL) — Batch 22 SENT July 11 2026 (Codex find, Fable relayed)

Clean net-new newer-Colleague add, distinct from Augustana University. Official public catalog:
`https://selfservice.augustana.edu/Student/Courses`; endpoints are `SearchAsync` and `SectionsAsync`.
This is a four-year liberal-arts college with about 2,500 students.

- Builder's production `NewColleague` fetch lands on `2026-27 Fall Semester` in about 2.4s and
  withholds five full rows. Source `BIOL 130` returned 6 unique sections: four numeric `status=0`
  rows with positive seats and two `status=2` rows full at zero seats; `Available/Taken/Capacity/
  Waitlisted` arithmetic held 6/6. Source latency was 2.04s search + 0.39s sections.
- Registration runs 2026-04-22 through 2026-08-31. As with this newer API family, do not claim a
  literal completed-term feed; use the conservative production rule **numeric `status==0` AND
  `Available>0` AND seat counts available**.
- Exact `SubjectCode + Number` filtering is mandatory because keyword `BIOL 130` leaks `BIOL 130L`.
  Section IDs/numbers are unique; name/host dedup is clean.

### Camden County College (NJ) — Batch 22 SENT July 11 2026 (Codex find, Fable relayed)

Clean net-new newer-Colleague add. Official public catalog: `https://selfservice.camdencc.edu/Student/Courses`;
production host `selfservice.camdencc.edu`; endpoints are `GetCatalogAdvancedSearchAsync`, `SearchAsync`,
and `SectionsAsync`. This is a two-year community college with 11,000+ credit students in spring 2024
and more than 15,000 annually (NJ institutional profile).

- Production fetch of `BIO 121` returned 6 unique sections in 1.37s: four numeric `status=0` rows with
  4/18/16/15 seats and two `status=2` rows with zero seats; `Available == Capacity - Enrolled` held
  6/6 and all rows publish seat counts. Source search was 0.29s + sections 0.40s.
- Current term is `26/FA` / Fall 2026, registration starts 2026-09-02. Spring 2026 returned no BIO
  rows, so there is no literal completed-term sample for this course; current full rows are nonzero
  status. Apply **numeric `status==0` AND `Available>0` AND seat counts available**.
- Exact `SubjectCode + Number` filtering is mandatory: keyword `BIO 121` leaks unrelated subjects
  numbered 121 and neighboring BIO courses. Section IDs/numbers and name/host dedup are clean.

### Walsh College (MI) — Batch 22 SENT July 11 2026 (Codex find, Fable relayed)

Clean net-new newer-Colleague add, distinct from Walsh University. Official public catalog:
`https://selfservice.walshcollege.edu/Student/Courses`; production host `selfservice.walshcollege.edu`;
same `SearchAsync`/`SectionsAsync` family. Walsh is a small private four-year business college
(official average class size 11.3; exact enrollment not independently confirmed in this pass).

- Production fetch of `ACC 316` returned 2 unique sections in 2.02s: one numeric `status=0` row with
  22 seats and one numeric `status=1` full row with zero seats; source search was 0.53s + sections
  0.71s and arithmetic held 2/2. Spring 2026 production/source data returned two open sections at
  9 seats and one full section, providing a real mixed historical result.
- Current term is `26/FA` / Fall 2026, registration starts 2026-08-30. Apply **numeric `status==0`
  AND `Available>0` AND seat counts available**; never infer openness from seats alone.
- Exact `SubjectCode + Number` filtering is mandatory because keyword `ACC 316` leaks neighboring
  ACC numbers (including `ACC 512`). Section IDs/numbers and name/host dedup are clean.

### SUNY Onondaga Community College — ✅ BUILT July 11 (batch 21): 648->649
Builder re-gated everything independently through the registered production adapter before shipping
(commit follows): fetch 1.6-3.7s; Fall 2026 - Undergraduate picked (terms roll to 2028); BIO 121 =
8 unique sections, 6 Waitlisted correctly withheld, 2 Open (4/1 seats); completed-term REPRODUCED
(Spring 2026: 10 Open + 1 Closed w/ 0 seats — real history); dedup clean; classic textual-'Open'
Colleague, no new code paths. Host = resolved SaaS host colss-prod.ec.sunyocc.edu (Bridgeport
redirect lesson). Zero false-opens. Original relayed spec below for the record.

#### (original spec) Batch 21 SENT July 11 2026 (Codex find, Fable relayed)

Clean net-new Colleague add. The officially documented `https://selfservice.sunyocc.edu/Student/Courses`
redirects to the live public catalog at `https://colss-prod.ec.sunyocc.edu/Student/Courses`. Existing
production `Colleague` works unchanged. Builder subclass: `id="suny-onondaga"`,
`name="SUNY Onondaga Community College"`, `host="colss-prod.ec.sunyocc.edu"`, `example="BIO 121"`.
Name/host dedup is clean.

- Real production `fetch(["BIO 121","ENG 103","MAT 104"])`: 115 Fall sections in 3.31s, with mixed
  open/non-open results. BIO 121 = 8 sections (2 open/6 non-open); MAT 104 = 3 (1/2).
- Raw Fall BIO 121: 2 textual `Open` rows with 4/1 available; 6 textual `Waitlisted` rows with 0.
  `AreSeatCountsAvailable=true` and `Available == Capacity - Enrolled` held 8/8. Keep the existing
  conservative rule: ONLY textual `AvailabilityStatus == "Open"` is open.
- Completed-term production test passed: Spring 2026 BIO 121 = 11 unique sections, 10 open/1 full,
  varied integer seats `[0,1,2,3,4,5]`; not a fake all-open guest view.
- Auto-term passed: `ActivePlanTerms` extends through Summer 2028; existing picker selected
  `Fall 2026 - Undergraduate`, not archive/View Only. Latency is safely below 30s.
- Collapse/sibling/filter gates passed: Fall BIO 121 had 8/8 unique numbers. Search leaks BIO 121R and
  other BIO courses, but existing production exact-filters `SubjectCode + Number` before section IDs.
  Keyword-only request has no open-only, time, or day filter that could hide watched sections.

Research-only: Codex did not edit `schools.py` or contact Builder. Fable is the sole relay after Nathan
says “check the README.” Full chronology is also in `research/ARCHIVE.md` and Codex's lane.

## ACTIVE LEADS
- **San Diego City College (CA) — SOURCE-GATED, adapter needed (Codex, July 11 2026).** Official
  district class search is `https://www.sdccd.edu/students/class-search/search.html`; its public
  JavaScript calls `GET https://mws-api.sdccd.edu/?term=2267&career=ugrd` with no auth. Fall 2026
  returned 4,164 rows in about 6s, including 1,100 City rows (campus code `CITY`), 685 `O` (open)
  and 415 `C` (closed). `MATH 121` had 9 unique class numbers: 6 open with 1/2/16/31/34/35 seats
  and 3 closed at zero. Status is authoritative because 11 closed City rows retain positive
  capacity arithmetic (reserved-seat behavior). Spring 2026 (`2263`) also had mixed status (7 open/
  2 closed for MATH 121), ruling out an all-open fake. The API advertises automatic 10-minute refresh;
  response header reported `x-time-diff-sec: 444` and `cf-cache-status: DYNAMIC`. Exact
  `CAMPUS + SUBJECT + CATALOG_NBR` filtering and `CLASS_NBR` section keys are mandatory.
  **Conditional:** no production adapter yet; open only when `ENRL_STAT == O` and
  `ENRL_CAP - ENRL_TOT > 0`.
- **San Diego Mesa College (CA) — SOURCE-GATED, adapter needed (Codex, July 11 2026).** Same official
  district feed and endpoint; campus code `MESA`. Fall 2026 had 1,971 Mesa rows (1,106 `O`, 865 `C`).
  `MATH 121` had 13 unique class numbers: 8 open with 1/2/5/11/13/13/33/33 seats and 5 closed at
  zero. Spring 2026 had 12 sections with 7 open/5 closed, including over-cap historical closed rows;
  status must remain authoritative. The full feed is public and refreshed every 10 minutes; exact
  campus/subject/catalog filtering is mandatory. **Conditional:** no production adapter yet; apply
  `ENRL_STAT == O` plus positive `ENRL_CAP - ENRL_TOT` only.
- **San Diego Miramar College (CA) — SOURCE-GATED, adapter needed (Codex, July 11 2026).** Same official
  district feed; campus code is `MIRA` (not `MIRAMAR`). Fall 2026 had 1,093 rows (582 `O`, 511 `C`).
  `BIOL 131` had 3 unique class numbers: 2 open with 6/13 seats and 1 closed at zero; Spring 2026
  had 2 open and 1 closed (the closed row is over-cap), a genuine mixed historical result. Use exact
  campus/subject/catalog filtering and `CLASS_NBR` as the section key. **Conditional:** no production
  adapter yet; open only when `ENRL_STAT == O` and computed remaining seats are positive.
- **North Orange County CCD — Cypress College + Fullerton College (CA), source-gated but status-blocked.**
  Official app: `https://schedule.nocccd.edu/`; its public JavaScript loads `data/202610/courses.json`
  and `data/202610/sections.json` (Fall 2026) without auth. The feed returned 3,908 unique CRNs:
  Cypress (`campCode=1`) 1,694 sections, 1,083 with positive seats; Fullerton (`campCode=2`) 2,170,
  1,396 positive. `sectSeatsAvail == sectMaxEnrl - sectEnrl` held 3,908/3,908. Examples: Cypress
  `ENGL 100 C` = 59 sections with mixed 0/1 seats; Fullerton `ENGL 100 F` = 102 mixed sections.
  Summer 2026 (`202530`) is also public and mixed (Cypress 349, Fullerton 458), with unique CRNs and
  perfect arithmetic. **Do not hand off yet:** the JSON exposes seats, enrollment, waitlists and
  `sectResv`, but no authoritative registration-status enum; the app's “Open Classes” filter is
  seat-only and Cypress warns that a class can show seats while closed due to waitlist/add-code rules.
  A production adapter needs a status source or a proven safe reservation rule before any add.
- **Riverside CCD — Moreno Valley College (CA), SOURCE-GATED, adapter needed (Codex, July 11 2026).**
  Official [class finder](https://www.mvc.edu/class-finder/index.php) exposes a public SharePoint API
  at `https://apps-studentrcc.msappproxy.net/schedule`, list `ScheduleData_MOV`; Fall 2026 is term
  `26FAL`. The API returned 1,004 unique sections, all modified July 11, with 812 open by the official
  app rule `Total Seats > Seats Used` and add-deadline still current. `ENGL-C1000` had 92 sections
  with mixed full/open rows (0 and 1/6/21/27 seats); Spring 2026 (`26SPR`) had 939 sections and a
  genuine 815/124 open/full mix. Official RCCD FY2023-24 headcount is 17,118. Use exact
  `College + Primary Subject + Section Number`, honor `Last Day to Add`, and withhold any nonempty
  enrollment limitation/restriction. **Conditional:** no production adapter yet.
- **Riverside CCD — Norco College (CA), SOURCE-GATED, adapter needed (Codex, July 11 2026).** Same
  official API, list `ScheduleData_NOR`, term `26FAL`. Fall returned 1,054 unique sections, all modified
  July 11, with 911 open and 143 full by the app's date-aware `Total Seats > Seats Used` rule. Exact
  `ENGL-C1000` had 50 mixed sections; Spring 2026 had 973 sections with 929 open/44 full, confirming
  real historical variation. Official RCCD FY2023-24 headcount is 17,324. Apply exact course/section
  scoping, add-date gating, and restriction withholding. **Conditional:** no production adapter yet.
- **Riverside CCD — Riverside City College (CA), SOURCE-GATED, adapter needed (Codex, July 11 2026).**
  Same official API, list `ScheduleData_RIV`, term `26FAL`. Fall returned 2,330 unique sections, all
  modified July 11, with 1,453 open and 877 full. `ENGL-C1000` had 142 mixed sections; Spring 2026
  had 2,045 sections with 1,679 open/366 full. Official RCCD FY2023-24 headcount is 29,597. Use the
  app's date-aware `Total Seats > Seats Used` rule plus exact `Primary Subject + Section Number` and
  restriction checks. **Conditional:** no production adapter yet.
- **University of California, Berkeley (CA) — SOURCE-GATED, adapter needed (Codex, July 11 2026).**
  Official public class search is `https://classes.berkeley.edu/`; Fall 2026 is term facet `8588`
  and Spring 2026 is `8576`. Search results link to exact section pages whose embedded
  `drupal-settings-json` contains `ucb.enrollment.available`: stable numeric class ID, status code
  (`O` = Open), enrolled, capacity, waitlist, and reserved-seat fields. Fall Biology 2026 returned
  four unique sections for Biology 1A/1AL/1B (class IDs `21757`, `21747`, `21748`, `23322`), all
  status `O`; 1B-001 and 1B-002 each showed 1 unreserved open seat (345/346 enrolled), while 1A/1AL
  showed 21/20 open seats entirely reserved. Spring Biology returned three unique sections (IDs
  `21727`, `21754`, `21780`) with 2/1/1 open seats and `openReserved: 0`, providing a mixed
  current/historical sanity check. The rendered pages agree (`Total Open Seats`, `Enrolled`,
  `Capacity`, `Open Reserved Seats`), so this is not an all-open fake.
  **Safe rule:** require exact term + subject/course + class ID, status code `O`, and
  `capacity - enrolled > 0`; subtract `openReserved` and withhold rows when the remainder is zero
  (reserved-only seats must not alert general users). Preserve waitlist and consent/restriction text.
  Berkeley's search/detail pages are public but no production adapter exists yet; do not hand off.
- **University of North Carolina Asheville (NC) — SOURCE-GATED, adapter needed (Codex, July 11 2026).**
  The official [Class Schedules](https://www.unca.edu/class-schedules/) React app calls the public,
  no-auth API `https://meteor.unca.edu/registrar/class-schedules/api/v1`; its bundled code identifies
  `courses/{year}/{spring|summer|fall}`, `departments/...`, `term/max`, and a CSV route. Fall 2026
  (`courses/2026/fall`) returned 788 unique CRNs with 484 `Classification.Open=true` and 304 false;
  Spring 2026 returned 866 unique CRNs with 520 open and 346 full. Every row in both terms has
  numeric `EnrollmentCurrent`/`EnrollmentMax`, and `(EnrollmentMax - EnrollmentCurrent > 0)` agreed
  with the API's Open flag for 788/788 Fall and 866/866 Spring rows. Example exact Biology siblings
  `BIOL 344.001` (CRN 60180, 15/15, closed) and `.002` (CRN 60401, 10/15, open) prove real mixed
  status; Spring `BIOL 136` has both full and open lab CRNs. Responses are `200`, `no-cache`, and
  current/future dates are Fall 2026 (Aug 17–Dec 9); the completed Spring feed is not all-open.
  **Safe rule:** exact term + `Department` + course code + CRN, `Classification.Open == true`, and
  positive `EnrollmentMax - EnrollmentCurrent`; never treat `WaitlistAvailable` as class seats, and
  preserve title/permission/restriction text. This is a clean net-new four-year public liberal-arts
  candidate (official Spring 2025 headcount 2,801), but no production adapter exists; do not hand off.
- **North Carolina Central University (NC) — SOURCE-GATED, adapter needed (Codex, July 11 2026).**
  Official Eagles Self Service exposes public Banner schedule listings at
  `https://ssbprod-nccu.uncecs.edu/pls/NCCUPROD/`: Fall 2026 is term `202710`, and the term picker
  identifies completed Spring 2026 as `202620` (View only). Section detail pages expose a labeled
  `Registration Availability` table with numeric `Capacity`, `Actual`, and `Remaining`, plus a stable
  CRN and exact subject/course/section in the title. Fall `BIOL 1100` returned 16 unique CRNs: 14 full
  (Remaining 0) and 2 open (CRNs `43209` = 35/34/1 and `43210` = 35/5/30). Spring `BIOL 1100`
  returned 7 unique CRNs with 1 positive remaining (1/35) and six full/over-cap rows
  (including -1 and -2), proving genuine mixed historical data. Listing/detail arithmetic is direct
  `Remaining == Capacity - Actual`; exact CRN keys are mandatory and waitlist/permission notes must be
  preserved. **Safe rule:** use only current selected term, exact subject+course+section/CRN, and
  `Remaining > 0`; do not infer openness from listing presence. Public Banner pages are current and
  no-auth, but production `Banner` integration has not been tested for this host; do not hand off yet.
- **University of North Carolina at Greensboro (NC) — SOURCE-GATED, adapter needed (Codex, July 11 2026).**
  Official current class search is `https://erp-registration.uncg.edu/StudentRegistrationSsb/ssb/`;
  its public endpoints are `classSearch/get_subject`, `searchResults/searchResults`, and
  `searchResults/getEnrollmentInfo`. The Biology subject code is `BIO`; Fall 2026 term `202608`
  returned 284 unique CRNs (170 `openSection=true`, 114 false), and completed Spring 2026 term
  `202601` returned 206 unique CRNs (117 true, 89 false). Search rows publish numeric
  `maximumEnrollment`, `enrollment`, `seatsAvailable`, `waitCapacity`, `waitCount`, and
  `waitAvailable`; arithmetic `seatsAvailable == maximumEnrollment - enrollment` held 284/284 Fall
  and 206/206 Spring. The detail endpoint agreed exactly (Fall CRN `80061` = 19/24/5 seats;
  CRN `80053` = 24/24/0). `openSection` includes waitlist-only rows: Fall had one `openSection=true`
  row with 0 seats and waitlist available 6; Spring had six such rows (including an over-cap -1), so
  **safe rule is `openSection == true AND seatsAvailable > 0`**, never status alone or waitlist seats.
  Exact `term + subject + courseNumber + sequenceNumber + CRN` scoping is mandatory; preserve optional
  `reservedSeatSummary`, restrictions, and linked sections. Official Fall 2025 facts report 18,682 total
  students. Clean net-new large public research university, but no production adapter exists; do not hand off.
- **Winston-Salem State University (NC) — SOURCE-GATED, production-compatible but not handed off (Codex, July 11 2026).**
  Official public schedule is `https://ssbprod-wssu.uncecs.edu/pls/WSSUPROD/bwckschd.p_disp_dyn_sched`;
  Fall 2026 is term `202680` and completed Spring 2026 is `202620` (View only). The public catalog
  route `bwckctlg.p_disp_listcrse` exposes Biology listings, while detail pages expose labeled numeric
  `Capacity`, `Actual`, and `Remaining`, plus stable CRN and exact section title. Fall Biology exposed
  73 unique CRNs and Spring 69. Exact `BIO 1113` had six Fall sections: two positive remaining (1 and
  5) and four full; Spring had five sections: three positive (1, 2, and 11) and two full. On all
  sampled detail rows, `Remaining == Capacity - Actual`. A future adapter must scope exact term,
  subject, course, and sequence/CRN, require `Remaining > 0`, and preserve restriction/waitlist
  notes. Official Fall 2025 student data reports 4,972 total students. The existing production
  `ListcrseBanner8` path was then tested dynamically: exact `BIO 1113` returned 6 sections in 2.48s,
  with 2 open/4 full and the same Remaining values as the raw detail probe. Net-new public
  four-year candidate; no builder handoff or registry change.
- **Worcester State University (MA) — SOURCE-GATED, production-compatible but not handed off (Codex, July 11 2026).**
  Official public catalog is `https://selfservice.worcester.edu/Student/Courses`; its client exposes
  `POST /Student/Courses/SearchAsync` with JSON-string `searchParameters` and
  `POST /Student/Courses/SectionsAsync`. The subject code is `EN` (not `ENGL`); Fall 2026 is
  `2026FA` / `Fall Semester 2026`. A dynamic production `NewColleague` fetch of exact `EN 101`
  returned 33 unique sections in 1.87s: 7 numeric status-0 rows with positive seats
  `[2,4,7,2,1,2,18]` and 26 status-1 rows at zero; raw `Available == Capacity - Enrolled` held
  33/33 and all section numbers were unique. `BI 101` (4 full) and `PY 101` (2 open) gave additional
  exact-course checks. Safe rule remains numeric `status == 0 AND Available > 0 AND
  AreSeatCountsAvailable`; do not infer openness from seats alone. Official [Fall 2024 snapshot]
  (https://webcdn.worcester.edu/wp-content/uploads/2025/06/WSU-Fall-2024-Snapshot.pdf) reports
  5,772 total students. Net-new public four-year candidate; no builder handoff or registry change.
- **Shorter College (AR) — SOURCE-GATED, production-compatible but not handed off (Codex, July 11 2026).**
  Official public catalog is `https://selfservice.shortercollege.edu/Student/Courses`; its newer
  Colleague client uses `SearchAsync`/`SectionsAsync` with JSON-string search parameters. Fall 2026
  is `2026FA` (plus main-session variants); the exact subject/course is `ENGL 2803` (not a generic
  101 course). A dynamic production `NewColleague` fetch returned Fall section `01` with
  `status=0`, `Available=5`, and published counts. Raw Fall detail was 1 unique section with
  `Capacity=45`, `Enrolled=40`, `Available=5`; Fall 2025 returned 5 unique rows including one
  `status=2` non-open row and four status-0 rows with positive seats, so the guest view is not an
  all-open default. `Available == Capacity - Enrolled` held on every sampled row. Safe rule is
  `status==0 AND Available>0 AND AreSeatCountsAvailable`, with exact term + subject + course +
  section scoping; preserve restrictions/waitlist notes. Shorter’s official [history page]
  (https://shortercollege.edu/about-us/shorter-college-history/) identifies it as a private,
  two-year HBCU in North Little Rock. No builder handoff or registry change.
- **Brazosport College (TX) — STATUS BLOCKED, no handoff (Codex, July 11 2026).** Official public
  Common Course Schedule is `https://mybcnext.brazosport.edu/CMCPortal/Common/CourseSchedule.aspx`.
  The guest form exposes Brazosport MAIN Campus, Fall 2026 (`2026-27 Fall - 16 Week`, value `1207`),
  a Keyword field, a Course field, and an explicit `Open & Closed` section filter. Three focused
  browser submissions against the official form (Keyword `ENGL` + Course `ENGL 1301`; Keyword `ENGL`
  + Course `1301`; Keyword `English` with Course blank) all returned the site's explicit “There are no
  classes that meet your search criteria” result. No section rows, seat fields, status values, or
  underlying request contract could be validated, so this is a search/feed availability block rather
  than evidence that Brazosport has no courses. Revisit only after the portal exposes a working exact
  course query or a documented public endpoint; do not hand off.
- **University of Southern Maine (ME) — SOURCE-GATED, adapter needed (Codex, July 11 2026).**
  Official [Course Search](https://usm.maine.edu/registration-scheduling-services/course-search/)
  exposes Fall 2026 (`strm=2710`) and a public subject-filtered result with explicit `Status`,
  `Enrollment: used of capacity`, section number, and stable class number. A current Computer
  Science query (`subject=COS-busunit-UMS06`) shows open Fall 2026 sections such as COS 160 class
  numbers `80083` (8/28 enrolled) and `80084` (26/28); the page's closed-section checkbox is
  available for conservative filtering. The completed Spring 2026 query (`strm=2620`, same subject)
  returned a genuine mixed set: COS 160/161/184/280/350/398 had open rows, while COS 422 class
  `43026` was `Closed` at 23/28 and COS 430 class `41953` was `Closed` at 24/28 (COS 530 also
  closed at 5/28). Thus `Status` must remain authoritative; never infer openness from seats alone.
  Keys should be exact term + subject + course + class number (not course title), and the safe rule
  is `Status == Open` plus `capacity - enrolled > 0`, with restriction/prerequisite text preserved.
  This is a net-new public four-year candidate, but no SeatWatch production adapter exists; do not
  hand off or edit the registry.
- **Rensselaer Polytechnic Institute (NY) — SOURCE-GATED, adapter needed (Codex, July 11 2026).**
  Official [Rensselaer Self-Service Dynamic Schedule](https://sis.rpi.edu/rss/bwckschd.p_disp_dyn_sched)
  is public and exposes current Fall 2026 (`202609`) plus completed Spring 2026 (`202601`, View only).
  Public detail pages carry stable CRNs, exact subject/course/section labels, and a labeled
  `Registration Availability` table with `Capacity`, `Actual`, and `Remaining`, plus separate
  waitlist capacity/actual/remaining. Fall examples include CSCI 2200 CRN `78037` (32/31/1) and
  CSCI 2600 CRN `79735` (24/2/22). Completed Spring is genuinely mixed: CSCI 2600 CRN `37370`
  is 24/25/-1 and PSYC 4200 CRN `36882` is 60/60/0, while CSCI 6964 CRN `38797` is 10/8/2.
  Therefore use exact term + subject + catalog number + CRN/section keys and require
  `Remaining > 0`; never treat waitlist remaining or cross-list remaining as primary seats, and
  preserve prerequisites/restrictions. This is a net-new public four-year Banner-class candidate,
  but the host uses classic `bwckschd` pages rather than SeatWatch's tested JSON Banner path; no
  production adapter exists and no handoff is authorized.
- **Middle Tennessee State University (TN) — SOURCE-GATED, adapter needed (Codex, July 11 2026).**
  Official [MTSU PROD Dynamic Schedule](https://ssb.mtsu.edu/pls/PROD/bwckschd.p_disp_dyn_sched)
  exposes current Fall 2026 (`202680`) and completed Spring 2026 (`202610`, View only). Classic
  Banner detail pages publish stable CRNs, exact course/section labels, and labeled primary and
  waitlist `Capacity`, `Actual`, and `Remaining` tables. Fall examples are mixed already:
  CSCI 1010 CRN `81110` has 101/90/11 primary seats, while MGMT 3610 CRN `81484` is 37/37/0;
  the latter also demonstrates that waitlist capacity (99) must not be treated as class seats.
  Spring is independently mixed: BIOL 2011 CRN `12710` is 24/24/0, DATA 3500 CRN `12175` is
  32/33/-1, and INFS 3800 CRN `13058` is 24/23/1. Use exact term + subject + catalog number +
  CRN/section keys and require primary `Remaining > 0`; preserve restrictions, prerequisites,
  cross-list notes, and waitlist fields. This is a net-new public four-year candidate, but classic
  `bwckschd` is not the tested JSON Banner path; no production adapter or handoff exists.
- **Framingham State University (MA) — SOURCE-GATED, adapter needed (Codex, July 11 2026).**
  Official [Framingham Dynamic Schedule](https://selfservice.framingham.edu/PROD/bwckschd.p_disp_dyn_sched)
  exposes current Fall 2026 (`202690`) and completed Spring 2026 (`202620`, View only). Public
  detail pages provide stable CRNs, exact course/section labels, and primary plus waitlist
  `Capacity`, `Actual`, and `Remaining`. A current Fall detail (GEOG 316 CRN `91208`) shows 30/9/21
  primary seats. Completed Spring is genuinely mixed: ANTH 206 CRN `20424` is 30/30/0, BIOL 460
  CRN `20095` is 5/4/1, and COMM 280 CRN `20146` is 14/14/0. Use exact term + subject + catalog
  number + CRN/section keys, require primary `Remaining > 0`, ignore waitlist/cross-list remaining,
  and retain restrictions/prerequisites. Net-new public four-year candidate; classic `bwckschd` is
  not the tested JSON Banner path, so no production adapter or handoff exists.
- **University of Nebraska Omaha (NE) — SOURCE-GATED, adapter needed (Codex, July 12 2026).**
  Official [UNO Class Search](https://www.unomaha.edu/registrar/students/before-you-enroll/class-search/)
  is a public query surface with exact term/subject parameters and no login. Fall 2026 (`term=1268`)
  History results expose explicit section `Open`/`Closed`, stable Class Number, Enrolled, Class Max,
  and Seats Available fields: HIST 8030 section 001/class `11821` is Open at 16/18/2, while HIST
  8010 section 801/class `11607` is Closed at 0/0/0 and HIST 8916 section 001/class `14370` is
  Closed at 5/5/0. Completed Spring 2026 (`term=1261`) is also mixed: CMST 1110 class `16231`
  is Open at 6/20/14, while BLST 3410 class `12500` is Closed at 10/10/0 and HIST 4910 class
  `19413` is Closed at 2/2/0. Use exact term + subject + catalog number + section/class number,
  require explicit `Open` plus positive `Seats Available`, and preserve prerequisites, notes,
  cross-listings, and modality. This is a net-new public four-year candidate; no SeatWatch
  production adapter exists and no handoff is authorized.
- **North Central University (MN) — CLOSED FOR THIS PASS, no handoff.** Its public newer-Colleague
  catalog (`https://selfservice.northcentral.edu/Student/Courses`) exposes future `2026FL` and later
  terms, but exact section-bearing courses (`ENG 496`, `MATH 115`, `MATH 110`, `PSYC 258`) returned
  only numeric status-0 rows with positive seats across Summer/Fall 2026; no full or non-open row was
  available to disprove an all-open default. Keep this out until a mixed live/historical course is
  published. Southwestern Law remains the prior rolling-term cut; Colorado Mountain remains a hold
  because its advertised Fall 2026 term still produced no matching sections.
- **Northern New Mexico College (NM) — STATUS BLOCKED, no handoff.** Official schedule surface is
  `https://schedule.nnmc.edu/academics/schedule-of-classes.html`; it publishes Summer/Fall 2026
  schedule PDFs and explicitly says the most up-to-date schedule is in Banner. The PDFs provide
  course offerings but no live capacity, enrollment, remaining-seat, or authoritative open/closed
  field, so this is catalog-only and not suitable for SeatWatch without a public Banner/API route.
- **Northwood Technical College (WI) — STATUS BLOCKED, no handoff.** Official public course-search
  app is `https://courses.northwoodtech.edu/` and its client posts to `/Search/CourseSearch`. The
  endpoint answered successfully but returned `total=0` and an empty detail payload for both a broad
  query and an ENGL query; the rendered page exposes no usable semester options or live capacity/
  enrollment fields. Treat this as an unavailable current feed, not an empty schedule; do not hand off.
- **Columbia University (NY) — STATUS BLOCKED, no handoff.** Columbia’s official [Open Data Service]
  (https://opendataservice.columbia.edu/doc) documents a course JSON feed with `NumEnrolled`,
  `MaxSize`, and `EnrollmentStatus` (`O`/`C`). However, the documented live endpoint
  `https://academic.cuit.columbia.edu/opendataservice/doc/json` currently redirects to Columbia CAS
  authentication, and the documentation host is Cloudflare-challenged from this environment. No live
  rows were accepted; revisit only if the feed becomes publicly reachable again.
- **Ventura County Community College District (CA) — deferred triage, no handoff.** Its official
  `https://schedule.vcccd.edu/` page is a server-rendered Banner-style HTML schedule (Summer 2026
  only in this pass; current Fall/Spring term URLs returned zero rows). The Summer response is very
  large, exposes `OPEN/FULL` plus Cap/Act/Rem, and would need a term-availability check, completed-term
  sanity test, and production adapter before any college-level proposal. Do not duplicate this probe
  until a future pass finds a published Fall term or a smaller underlying endpoint.
- **Newer-Colleague API (BUILD DECISION for Nathan).** Confirmed real: `SearchAsync`/`SectionsAsync`
  with a JSON-string `searchParameters` payload and a NUMERIC status (0=open; full codes vary by
  school). The production `NewColleague` variant now passes real fetches for Lebanon Valley, Augustana,
  Camden County, and Walsh; their four full specs are under `AWAITING GO-AHEAD`. The safe rule is
  `status==0 AND Available>0 AND AreSeatCountsAvailable`; exact subject+number filtering is required.
  This family does not expose a dependable literal completed-term feed, so current full rows and the
  Walsh historical mixed result are documented instead of inventing a past-term claim.
- **selfservice.* -> SaaS-host redirect vein (Codex).** Several "405/400" Colleague hosts are just
  `selfservice.{school}.edu` 301-redirecting to a SaaS host (e.g. `colss-prod.*.elluciancloud.com`);
  a POST does NOT follow the 301, so the plain host looked dead. Re-testing the ~10 remaining hosts
  with redirect-following (+ program-prefixed-term check, see lessons) may land several clean adds.

---

## PERMANENT DEAD-ENDS — do NOT re-tread (accuracy-critical)
- **Classic PeopleSoft guest search = FAKE ALL-OPEN.** `COMMUNITY_ACCESS.CLASS_SEARCH.GBL` /
  `SA_LEARNER_SERVICES...SSR_CLSRCH` shows every section "Open" regardless of real enrollment (NAU:
  121/121 English "Open" in a COMPLETED term). Killed the 22-flagship batch. **Also when hidden behind
  a modern SPA** (GreyHeller/InFlight etc — confirmed on University of Arizona): check the config for
  an `SSR_CLSRCH` / `CLASS_SEARCH.GBL` component key; if present, expect fake status no matter how slick
  the frontend. The mandatory test to ever propose one: search a big intro course (ENGL) in a FINISHED
  term; all-Open => fake => skip.
- **Data-absence (public schedule real, but seat field not published):** Cal Poly Pomona (Capacity only,
  no seats/status) and University of Florida (API cracked — needs Referer header + 4-digit term "2268" —
  but `openSeats` is null for guests across ALL terms incl. completed). Nothing to gate. Do NOT re-attempt.
- **Permanent-CUT schools (never re-hand-off):** Lafayette (all terms View Only/archive), TESU (rolling
  monthly terms, no season), Bryant&Stratton (View Only), Victor Valley (advertises Fall 2026, serves
  Spring-2024 archive), McCormick Seminary + SEBTS (no sections in primary term).
- **SSO / bot / no-tool walls:** CSU Fullerton + Fresno + San Diego State (Shibboleth/PS login), San
  Jose State (public data is NIGHTLY-refresh = too stale; live search portal-gated), CSU Long Beach
  (once-daily snapshot, no closed-section indicator), Michigan State (Incapsula bot-wall — needs a real
  browser), Arizona State (full OAuth, authorize bounces to login), Clemson (no public class-search tool).
- **No live seats anywhere:** Workday Student (auth/RaaS), Coursedog & CourseLeaf public views (catalog
  descriptions only), KCTCS class-search mirror (stale snapshot). Don't chase these for seats.
- **Blind host-guessing is MINED OUT.** Banner + Colleague, direct AND Ellucian-cloud patterns, fully
  swept against the entire uncovered US-domain dataset (Hipo 2,014 domains) — every reachable host was
  already live or already cut. Count only confirmed non-duplicate installs; never project yield from a
  raw "host reachable" rate. Fresh volume needs the newer-Colleague API or per-school flagship recon,
  NOT another hostname sweep.

## KEY ACCURACY LESSONS (the gate every candidate must pass)
- **Completed-term test (mandatory for any status source).** A finished term MUST show real closed
  sections. All-open in a done term => fake status => scrap.
- **Numeric status is opaque — verify it.** Open ONLY when the open-code AND seats>0; run the
  completed-term test to prove the code isn't a default (0 could be a fake-open default).
- **Open needs seats>0; the reverse is NOT required** (Edison lesson): a seat behind a Waitlisted/
  restricted status is correctly withheld. Status stays authoritative; never mark open without a real seat.
- **No time/day/open-only filters in a handoff spec** (UCLA): a filter can silently hide a watched
  section (a silent miss). Strip every section-hiding filter; request ALL statuses.
- **Redirect gotcha** (Bridgeport): `selfservice.*` may 301 to a SaaS host and a POST won't follow it —
  always record the RESOLVED host the adapter must use.
- **Program-prefixed parallel terms** (Bridgeport -> `MainTermColleague`): schools with PA/Nutrition/ELI/
  Health-Sciences "Fall 2026" terms make `_pick_term` choose the wrong one -> 0 sections. Gate through the
  PRODUCTION adapter (`.fetch()`) and verify the picker lands on the MAIN term, not just that raw
  endpoints return data.
- **Section-key uniqueness / collapse guard:** zero-sequence Banner installs (all seq="0") ->
  `CrnKeyedBanner`; multi-meeting duplicate rows -> dedupe by class_number.
- **Numeric subject codes** (subject "101") -> `NumericSubjectBanner` / `NumSubjColleague`.
- **Sibling-leak:** exact course-code search can return suffixed siblings ("MATH 2A"->"2AX", "150"->"1500")
  — scope to exact SubjectCode+Number before reading sections.
- **Dedup BY SCHOOL NAME, not host** (UNCC x2, Penn, Ashland, Westminster-Utah rebrand): a school may be
  live via a bespoke adapter on a different host. `grep -i "<name>" schools.py` every time. (Now also
  enforced in code — duplicate id/name crashes the import.)

## REUSABLE DISCOVERY PATTERNS & adapters
- **Banner 9 SSB:** `/StudentRegistrationSsb`, JSON, read `seatsAvailable` (NOT `openSection`).
- **Colleague (old MVC):** `/Student/Courses` + `PostSearchCriteria`/`Sections`, textual AvailabilityStatus.
- **Colleague (NEWER):** `SearchAsync`/`SectionsAsync`, JSON-string params, numeric status — needs a new
  adapter variant (see Active Leads).
- **PeopleSoft Fluid / HighPoint HCX:** `WEBLIB_HCX_CM...IScript_ClassSearch`, real enrl_stat O/W/C +
  enrollment_available (Coppin/Towson/BU). Hosts idiosyncratic — search-harvest, can't brute-force.
- **Fose:** `classes.{domain}/api/?page=fose&route=search`, srcdb auto-discovered from homepage.
- **Banner 8** (VirginiaTech / Purdue family): `bwckschd` HTML scrape; seats on per-CRN detail page
  (`p_disp_detail_sched` -> Capacity/Actual/Remaining). N+1 — only detail-call watched sections, or find
  an open-only listing filter.
- **Full-term-dump + cache** (Texas A&M template): if an API ignores filters and returns the whole term
  (34MB/40s), it's still buildable — flag it "cache-needed" (TTL cache under a lock, per-course lookups
  from the cached dump). Don't reject on size alone.
- **Bespoke public schedules / alt-search:** a flagship gated on its primary SIS often exposes a SEPARATE
  public schedule — UConn->Fose, UC Irvine->WebSoc, UCSC->pisa, SFSU/Sac State->JSON APIs, TAMU->Howdy
  public API, Purdue->Banner 8. Always look for the alt public search, not just the primary SIS.
- **Builder's reusable subclasses** (match a candidate -> ~4-line add): `CrnKeyedBanner`,
  `NumericSubjectBanner`/`NumSubjColleague`, `CodedTermColleague`, `ShortYearTermColleague`,
  `AcadYearColleague` ("Fall 26/27"), `QuarterColleague` (Quarter-N terms), `DecimalColleague`,
  `ExactTermColleague` (suffix branch isolation), `MainTermColleague` (drops program-prefixed terms).

---

## Recent wins (this partnership; full detail in ARCHIVE.md)
UCLA, Coppin State, San Francisco State, Sacramento State, CSU Northridge, Edison State CC (OH),
Georgia Military College, **Texas A&M College Station (~58-60k)**, **Iowa State (~30k)**,
University of Bridgeport (Codex), **Purdue (~50k, batch 19)**. 634 -> 646.

## Handoff batch 19 (Purdue) — ✅ BUILT July 10: 1 added (646->647)
Purdue West Lafayette (~50k): new `Purdue` classic-Banner-8 adapter (bwckschd HTML scrape,
VirginiaTech family). Purdue suppresses seats from the course listing, so seats need one
detail GET per CRN — to avoid ~40 calls/poll it uses a per-(term,course) class-level cache
(10-min TTL, lock-guarded, same pattern as TAMU). Real numeric Banner seats from the
detail 'Availability' table (open = Remaining>0, seats = Remaining; Waitlist row ignored).
Completed-term test PASSED (Fall 2025 CS 18000 sampled: 3 full / 5 with-seats — real full
sections). CRN-keyed, term auto-rolls skipping '(View only)'. Cold cache ~77s for 39
sections, warm ~0ms. Gated: 39 secs, zero false-opens.
Note: batches 17/18 (TAMU cache-backed, Iowa State, Bridgeport) were already committed
(6b771af); I INDEPENDENTLY re-gated all three today — all safe, zero false-opens, TAMU
cache confirmed working (cold 46s / warm 0ms) and TAMU completed-term real (Fall 2025
7136 open / 7142 closed).

### University of Utah (~35k, Salt Lake City) — Batch 20 SENT July 10 2026 (Fable)
Flagship (distinct from Utah State + Southern Utah, both already live). Bespoke PUBLIC schedule, no
login, server-rendered HTML, REAL numeric seats. Registrar advertises it as "no security access
required."
- Endpoint (one GET per subject): GET https://class-schedule.app.utah.edu/main/{TERM}/seating_availability.html?subject={SUBJ}
  → server-rendered Bootstrap grid. TERM 1268=Fall 2026.
- Term auto-roll: GET https://class-schedule.app.utah.edu/ → landing lists `/main/{TERM}/index.html`
  with labels ("Fall 2026"=1268, "Summer 2026"=1266, "Spring 2026"=1264). Standard PeopleSoft strm;
  pick nearest upcoming, verify-before-adopt.
- PARSE: per-section `<div class="col-*">` cells in order: CRN(5-digit), Subject, CatalogNbr, Section,
  Title, **Cap, WaitList, CurrentlyEnrolled, SeatsAvailable**. open = SeatsAvailable>0, seats =
  SeatsAvailable. Section key = CRN (globally unique — verified). Filter client-side to the exact
  CatalogNbr (the page is subject-wide).
- GATE: Fall 2026 across ENGL/MATH/BIOL/CHEM/PSY = 155 sections, 113 open / 42 full — real mix;
  `SeatsAvailable == Cap - Enrolled` held on 100% (0 anomalies, so it's real arithmetic not a sentinel);
  CRNs unique. COMPLETED-TERM TEST Fall 2025 (1258) MATH = 73 sections with genuinely FULL sections
  (enr==cap, avail=0) alongside open ones → real historical enrollment, NOT fake-all-open (numeric
  enrollment can't be faked open anyway). PASSES.
- example="MATH 1050" (College Algebra; note UF's English subject is likely "WRTG" not "ENGL" — builder
  confirm the exact subject code, but MATH/BIOL/CHEM/PSY all verified working). NOTE: Fall 2026 is early-
  registration so some courses have few sections loaded — that's live/real, not stale (completed-term
  proves the mechanism shows real fills). ⚑ Freshness: registrar claims "real-time"; I did not
  independently measure refresh cadence — builder should confirm it's not a daily snapshot before ship
  (if daily, still likely acceptable but flag it). Needs a small bespoke HTML adapter (div.col parse).
  Dedup clean (University of Utah not in schools.py).

### Flagship gaps round 1 dead-ends (Fable, July 10 2026) — do NOT re-tread
Checked big uncovered publics for bespoke public schedules. WIN: University of Utah (above). Dead:
- **University of Cincinnati (~48k):** public search (classes.catalyst-services.uc.edu) is the CLASSIC
  PeopleSoft `COMMUNITY_ACCESS.CLASS_SEARCH.GBL` — fake-all-open family. Skip.
- **LSU (~35k):** courseofferings.lsu.edu exists (ASP.NET), but registrar states seats are "updated
  DAILY, may not reflect real-time" — too stale for alerts (same class as SJSU nightly / CSULB daily).
- **University of Georgia (~40k):** Athena redirects to sso.uga.edu CAS (Ellucian Experience cloud,
  uog744) — SSO-gated, no guest class search. The public UGA Bulletin is catalog-only.
STILL UNCHECKED this vein (for a later pass): Kentucky, Kansas, Kansas State, Nebraska-Lincoln, Oregon,
Louisville, Nevada (UNR/UNLV), Rhode Island, Hawaii-Manoa.

## University of Utah — ✅ BUILT July 11 (batch 20): 647->648
Bespoke public schedule (class-schedule.app.utah.edu), div.col HTML parse, REAL numeric seats (open=SeatsAvailable>0, ==Cap-Enrolled 100%). Freshness RESOLVED = real-time (Cache-Control no-store/must-revalidate, generated per request — not a daily snapshot). English subject = WRTG not ENGL. Completed-term test passed (Fall 2025 MATH 13 full sections). CRN-keyed, exact-CatalogNbr scoped (105 != 1050), term auto-rolls. Zero false-opens.

### Flagship gaps round 2 (Fable, July 10 2026) — mostly walled; 2 revisit-leads
Probed the remaining unchecked flagships. No clean win this round.
- **Kansas (KU, ~28k) — REVISIT LEAD.** classes.ku.edu is a real PUBLIC search app (Struts); search
  fires via `$.post("/Classes/CourseSearch.action", searchOptions)` with the classesSearch* form fields
  (term 4269=Fall2026, 4259=Fall2025 for completed-term test). BUT CourseSearch.action timed out at 55s
  on two probes — either a latency red flag (would stall the poller) or a missing-param hang (cascading
  dropdowns may need career→school→dept populated first). Crackable but needs a browser network-trace of
  one real search or more RE. Not gated.
- **Hawaii-Manoa — REVISIT LEAD.** www.sis.hawaii.edu/uhdad/avail.classes is a known PUBLIC availability
  page but returned 502/301 on my probes (transient? param format?). Worth a retry with correct params
  (i=campus, t=term, s=subject).
- DEAD: Kansas State (signin.k-state.edu WebISO SSO), UGA (CAS, see round 1). Hosts that don't resolve at
  guessed public-schedule names (need real host): Nebraska-Lincoln, Louisville, Oregon (classschedule.
  uoregon.edu NX; duckweb is the Banner-8 login portal), Nevada-Reno (404), URI (courses.uri.edu 200 but
  not obviously a class search). These need per-school registrar-page recon to find the real public tool.
NET flagship-gaps result: 1 clean win (University of Utah, batch 20) + 2 revisit-leads (KU, Hawaii).

### Batch 20 SHIPPED July 10 (648) + process finding
University of Utah shipped 647->648 (commit be294fd). Builder resolved both my flags: FRESHNESS =
real-time (server sends Cache-Control: no-cache/no-store/must-revalidate — generated per-request, not a
daily snapshot; SeatsAvailable==Cap-Enrolled exact live arithmetic). ENGLISH SUBJECT = **WRTG** (177
sections), not ENGL — record for any future Utah example. Completed-term reproduced, CRN-keyed, exact-
CatalogNbr scoped, zero false-opens.

⚑ PROCESS FINDING (builder flagged, verified by Fable): batches 17/18 adapter code reached schools.py
BEFORE the builder's production gate saw it ("arrived already-committed"). Investigation: NO research-
agent commit ever touched schools.py — every schools.py change is a builder-format "Add X — N->M" commit
(Fable and Codex only ever commit research/*.md in "research:"/"lane:" format; git-verified). So the
adapters were committed by a BUILDER-type session. Most likely cause = MORE THAN ONE builder session
committing (they share one git identity on Nathan's Mac, so commit format can't disambiguate sessions),
OR a single builder committing before its gate. The gate + registry-guard (crash-on-dup) + production
re-fetch caught everything — nothing ungated actually shipped. FOR NATHAN: ensure only ONE builder
session commits to schools.py; research agents stay hands-off (verified compliant).

## NewColleague adapter infra ✅ BUILT July 11 (builder) — no schools registered yet
Nathan greenlit the newer-Colleague build. `NewColleague(Colleague)` is now in schools.py
(SearchAsync with JSON-string `searchParameters` → SectionsAsync; TermsAndSections is TOP-level,
no SectionsRetrieved wrapper) plus `YearSpanNewColleague` for '2026-27 Fall Semester'-style term
labels (Augustana). SAFETY RULE implemented: open ONLY when numeric status==0 AND Available>0 AND
AreSeatCountsAvailable — the enum is never trusted alone.
- **Enum verified live on both known hosts** (builder-independent of Codex, production `.fetch()`
  path): LVC enum {0=open, 1=full}, Augustana {0=open, 2=full}. 162 rows sampled across 18 subjects
  per school: ZERO full rows (Enrolled>=Capacity) carrying status 0, ZERO status-0 rows without a
  bookable seat, `Available == Capacity-Enrolled` on every row but one.
- **Completed-term test caveat (IMPORTANT for handoffs):** guest search indexes ONLY active plan
  terms — a `terms:["25/FA"]` filter on a finished term returns no courses, so the literal
  completed-term test is IMPOSSIBLE on this API family. The per-school equivalent (now in the class
  docstring): current-term rows with Enrolled>=Capacity MUST carry a non-0 status. If a school shows
  full-by-arithmetic rows still coded 0 → fake default → scrap.
- **Reserved-seats note (LVC SOC 301):** `Available` can be LOWER than Cap-Enrolled (reserved
  capacity; Waitlisted=0) — conservative direction, same authoritative field classic Colleague
  trusts. Only av > cap-enr would be suspicious.
- Gate results through production fetch: LVC 3.6s (BIO 111 exact-scoped from 111L; 2 full labs
  correctly withheld), Augustana 2.4s (picker lands '2026-27 Fall Semester'; 5 full rows withheld).
- **NOT registered:** Lebanon Valley + Augustana are gate-READY builder-side but ship only when the
  formal gated handoff arrives (Codex → Nathan → Fable). Same for the round-4 conditional leads
  (Onondaga, Camden County, Walsh College) — the adapter they were waiting on now exists.

### Flagship gaps round 3 (Fable, July 11 2026) — no clean win; 2 big revisit-leads, rest walled
Probed a fresh set of big uncovered publics. Honest result: the headless-crackable flagship vein is
tapping out. Details so nobody re-treads:
- **UNT (~46k) — REVISIT-LEAD (high value, needs browser trace).** Public class search EXISTS (registrar
  links it): my.unt.edu/psc/ps PeopleSoft FLUID (NUI_FRAMEWORK.PT_LANDINGPAGE.GBL). Direct HCX IScript
  calls (WEBLIB_HCX_CM.H_CLASS_SEARCH...IScript_ClassSearchOptions) return 214-byte PeopleSoft stubs, not
  the guest JSON — the Fluid guest search needs the NUI landing→guest-session flow established first
  (browser network-trace of one real guest search would crack it). Worth it at 46k IF a browser can reach
  my.unt.edu. Not gated.
- **UMass Amherst (~32k) — LOW-PRIORITY LEAD.** SPIRE guest "Search Classes" exists but is classic-
  PeopleSoft (needs completed-term test, likely fake-status trap). The bespoke React "Explore" tool
  (umass.edu/universityplus/classes/explore) is under "universityplus" = continuing-ed/UWW — SCOPE likely
  a subset, not the full Amherst catalog; no clean JSON API surfaced. Skip unless scope confirmed full.
- WALLED/DEAD this round (no guessable Banner 9; PeopleSoft/Workday/bespoke): UT-Arlington, Kent State,
  UNM, Toledo, Akron, Illinois State, Ohio University. UW-Milwaukee enroll-API = 403 (Madison's API is
  Madison-only). Hawaii avail.classes = persistent 502 (server down, retry later). Kansas = 55s timeout
  (from round 2).
NET rounds 1-3: University of Utah shipped (648). Flagship-gaps vein now well-worked headlessly; the
biggest remaining prizes (UNT, Kansas) need browser network-traces, which are blocked for the in-app
browser on these domains. Diminishing returns confirmed — recommend pausing flagship grinding.

### Flagship round 4 + CT-log test (Fable, July 10 2026) — vein confirmed EXHAUSTED for headless work
Checked the last big uncovered publics + tested the CT-log lane. No clean win; documenting so it's not re-tread.
- UNT (~46k): registrar's "public class search" link → my.unt.edu PeopleSoft Fluid, but the HCX IScript
  returns "Authorization Error -- Contact your Security Administrator". GATED despite the "public" label.
- UMass Amherst (~32k): the public tool (umass.edu/universityplus/classes/explore) is a Drupal/React app
  under "universityplus" = the continuing-ed/UWW arm — scope is likely NOT the full SPIRE catalog, and its
  data API isn't readily reachable (guessed endpoints 404/406, bundle exposes no plain path). SPIRE's own
  guest "Search Classes" is classic PeopleSoft (fake-status risk). Low-value; not pursued further.
- UT-Arlington/Kent State/UNM/Toledo/Akron/Illinois State/Ohio U/North Texas: NO guessable Banner 9 host.
- CT-LOG TEST (certspotter free): probed unt/louisville/unl/uoregon/uky .edu for registration subdomains
  — rate-limited partial results; surfaced only infrastructure/library hosts, no class-search host. Free
  CT-log tooling is too incomplete to be productive (consistent with prior findings: crt.sh often 503,
  certspotter rate-limits). Would need a paid CT-log API to make this lane viable.
CONCLUSION: my hunting lanes (CSU, HighPoint/Fluid, full host-guess sweep, flagship bespoke schedules,
CT-log) are all now exhausted or blocked for headless work at 648. Remaining real yield is NOT in more
solo hunting — it's the new Builder building Codex's newer-Colleague adapter (SearchAsync/numeric status),
which unlocks Lebanon Valley + Augustana + likely more of the redirect-host population in one shot.

### Newer-Colleague round 3 — conditional findings (Codex, July 11 2026)

**Camden County College (NJ) — source-gated, production adapter required.** Official guest catalog
`https://selfservice.camdencc.edu/Student/Courses` exposes `GetCatalogAdvancedSearchAsync`,
`SearchAsync`, and `SectionsAsync`. Fall 2026 term `26/FA` (`Fall 2026 Semester`) is current for
registration (registration starts 2026-09-02). `BIO 121` returned six unique section IDs and numbers:
four numeric-status `0` rows with 4/18/16/15 seats and two numeric-status `2` rows with zero seats/full
enrollment. `Available == Capacity - Enrolled` held 6/6 and all rows published seat counts. Search and
sections latency was 0.29s + 0.40s. Keyword `BIO 121` also returned unrelated subjects numbered 121
and neighboring BIO courses, so exact `SubjectCode + Number` filtering is mandatory. Spring 2026
returned no BIO rows, so no completed-term result was available for this course. This is not ready for
relay: the numeric status enum still needs a conservative production adapter; raw seats alone must not
be treated as open.

**Walsh College (MI) — source-gated, production adapter required.** Official guest catalog
`https://selfservice.walshcollege.edu/Student/Courses` exposes the same three newer endpoints. Fall
2026 term `26/FA` (`Fall 2026 Semester`) has registration starting 2026-08-30. `ACC 316` returned two
unique sections in 0.53s + 0.71s: numeric status `0` with 22 seats and numeric status `1` full with zero
seats; arithmetic and published counts held 2/2. Completed Spring 2026 returned three sections with
two status-0 rows at 9 seats and one status-1 full row, proving the guest view is not all-open. Keyword
`ACC 316` leaks neighboring ACC numbers, so exact `SubjectCode + Number` filtering is mandatory. Name
dedup is clean against existing Walsh University. This is not ready for relay until production confirms
the numeric enum and applies status plus positive-seat gating.

**Brookdale Community College — duplicate, no proposal.** The exact name already exists in
`schools.py` as `Brookdale` with host `brookdalecc-ss.colleague.elluciancloud.com`; the official
`selfservice.brookdalecc.edu` page is therefore not a new school for SeatWatch.

### Newer-Colleague round 4 — closed candidates (Codex, July 11 2026)

**Gustavus Adolphus College — closed for freshness.** The official `selfservice.gustavus.edu` URL
redirects to `colselfsrvprod.gac.edu`, whose public catalog uses the legacy Colleague endpoints.
`BIO 121` returned nine Spring 2026 sections with five textual `Open` rows (2/8/3/3/7 seats) and
four `Closed` rows at zero seats; arithmetic held 9/9. However, the same response's `ActivePlanTerms`
advertised Fall 2026 and later while `Sections` returned only `2026/SP`. The production term picker
would select Fall 2026 and then find no matching sections. That is stale/wrong-term behavior, not a
current live source; no proposal.

**Texas Wesleyan University — SSO-gated.** The university's official registrar instructions point to
`https://selfservice.txwes.edu:8143/Student/`; port 8143 refused connection, and standard HTTPS
served a SAML 2.0 login page. No public guest authoritative catalog is available; no proposal.

**Round-4 conclusion:** the original newer-Colleague candidate list is exhausted for research-only
work. Onondaga is the only fully gated pending handoff. Lebanon Valley, Augustana, Camden County,
and Walsh College are validated numeric-API conditional leads that require one conservative production
adapter (`status == 0` plus `Available > 0`, exact course filtering, and completed-term validation).

### Fresh official-public-schedule pass — conditional findings (Codex, July 11 2026)

**Fairfield University (CT) — source-gated, production adapter required.** Official public app:
`https://course-search-net.fairfield.edu/`. Its Angular lazy module identifies `GET
/api/course/courses`, a no-auth JSON response containing 2,251 sections. The response is marked
`Cache-Control: no-store, max-age=0`; fetch latency was 7.23s. It includes seven current/future periods,
including `Fall Semester 2026 (09/08/2026-12/19/2026)` with 1,929 rows. Fall data had 1,012 rows with
positive `Remaining_Seats` and 917 at zero. The composite `Course_Subject_Number + Section_Number`
key was unique across all 1,929 Fall rows. `Remaining_Seats` is explicit integer text; every positive
row matched `capacity - enrolled` from `Enrolled_Capacity`. Some zero-seat rows are over-cap, so the
adapter must use `Remaining_Seats` as authoritative and never derive openness from the enrollment
pair. `BIOL 1107` had five unique Fall sections with 0/0/17/4/18 seats; sibling `BIOL 1107L` exists,
so exact course scoping is mandatory. The API publishes no completed term, so the completed-term gate
could not be run. Name dedup is clean. Fairfield's official 2025-26 fact sheet reports 5,464
four-year undergraduates plus 1,697 graduate students. This is **not** a relay marker yet: the builder
must production-test a bespoke adapter, validate reserved-seat behavior, and decide whether the
7.2-second all-section response needs refresh caching.

**UC Davis — blocked, no handoff.** The official registrar Class Search advertises live/open-seat data,
but `registrar-apps.ucdavis.edu` returned a Cloudflare security block to the headless request. No
bot-detection bypass was attempted.

**Drew University — unresolved Banner search, no handoff.** Drew’s registrar documents a public Dynamic
Schedule at `https://selfservice.drew.edu/prod/bwckschd.p_disp_dyn_sched`, and the Fall 2026 term page
is public. Narrow Biology form probes returned the search form/no matching classes rather than section
data, so no seat claim is made; leave for a browser/form-trace pass rather than guess at Banner fields.

**Johns Hopkins University — API/key-gated, no handoff.** The official [SIS API documentation](https://sis.jhu.edu/api)
defines authoritative `OpenSeats`, `MaxSeats`, `SeatsAvailable`, and textual `Status` fields, but API
requests require a registered API key. The public classes page was also Cloudflare-challenged in this
pass. No key registration or bot-detection bypass was attempted.

### Fose systematic sweep (Fable, July 11 2026) — 0 net-new
Swept classes./courses.{domain} for the fose srcDBs signature across all 2014 uncovered US domains. ONE
hit: courses.upenn.edu = Penn (already live via bespoke `Penn` adapter — the known 4th-dup). Fose vein
now confirmed EXHAUSTED via full sweep, not just spot-checks. No fose schools remain to find.

### Batch 22 BUILT July 11 (649->653, commit 361008f) — newer-Colleague backlog cleared
Lebanon Valley, Augustana IL, Camden County, Walsh College all shipped on NewColleague/YearSpanNewColleague.
Accuracy gate PASSED live across all 19 rows: full-by-arithmetic sections ALWAYS carry non-0 status
(fake-open-default trap disproven), status-0 rows ALWAYS have a bookable seat, Available==Cap-Enrolled
19/19, keys unique, exact-course scoping isolates the watched course. Zero false-open risk.
⚑ MULTI-BUILDER NOTE (correction): the NewColleague infra commit dc5ffd0 was made by a DIFFERENT builder
session (shared git identity on Nathan's Mac — the multi-builder pattern). The current "Builder" session
re-gated all 4 from scratch itself before shipping regardless, so no harm — but do NOT assume a given
schools.py commit came from the session you're talking to. (Relay accuracy: attribute code to "a builder
session," not "you," when I can't confirm the author.)
⚠️ DEPLOY PENDING (Nathan): registry is at 653 in the repo but NOT yet live on seatwatchapp.com. Onondaga
(649) + these 4 all go live together on Nathan's next scp + `sudo systemctl restart seatwatch`.

### Batch 23 SENT July 11 2026 — Banner 8 (bwckschd) real-seat batch (Fable) — SHIP ONLY IF FLAWLESS
Nathan-approved WITH an explicit condition: Builder ships each school ONLY if it clears BOTH accuracy AND
efficiency flawlessly through the production gate; cut any that don't. 7 net-new, all on the EXISTING
Purdue-family Banner-8 adapter. Real numeric enrollment (Actual vs Capacity) — cannot be faked open.
FLOW (per Purdue adapter): bwckschd.p_disp_dyn_sched (term form) -> bwckgens.p_proc_term_date (set term +
subjects) -> bwckschd.p_get_crse_unsec (listing; ⚑ needs the "%" re-sends of sel_schd/camp/ptrm/instr/attr,
NOT just "dummy", or you get "No classes found") -> per-CRN bwckschd.p_disp_detail_sched -> "Seats Cap
Actual Remaining" row. open = Remaining>0, seats = Remaining. Section key = CRN. Each host has its own
base_path (varies /PROD /prod /pls/prod). EFFICIENCY WATCH: seats are per-CRN detail (N+1, like Purdue) —
adapter only detail-calls WATCHED sections, but latency-screen every host under production polling and CUT
any slow/cold-start host (Drake-137s / Kansas-55s class). All 7 responded <3s in my gate; Builder confirm.

1. Missouri State University (Springfield, ~24k, 4-yr) — prodssb.missouristate.edu /PROD, term 202640, example "ENG 110" (81 sec; ENG 110-001 Cap16/Act15/Rem1). NET-NEW (≠ Northwest Missouri State, already live).
2. University of Toledo (~20k, 4-yr) — selfservice.utoledo.edu /prod, term 202710, example "ENGL 101" (7 sec; Cap10/Act1/Rem9). (Banner 8 — why the Banner-9 host probe missed it.)
3. Stephen F. Austin State University (~12k, TX 4-yr) — ssb.sfasu.edu /prod, term 202710, example "ENGL 1301" (58 sec; Cap24/Act23/Rem1).
4. Alabama A&M University (~6k, HBCU 4-yr) — ssb1.aamu.edu /PROD, term 202670, example "ENG 101" (84 sec; Cap20/Act20/Rem0 = real FULL section).
5. Bristol Community College (MA, CC) — selfservice.bristolcc.edu /PROD, term 202609, example "ENG 101" (65 sec; Cap22/Act21/Rem1).
6. Utica University (NY, 4-yr) — bannerweb.utica.edu /PROD, term 202680, example "ENG 101" (3 sec; Cap18/Act18/Rem0 full).
7. Clovis Community College (NM, CC) — prodssb.clovis.edu /PROD, term 202630, example "ENGL 111" (6 sec; Cap25/Act9/Rem16).
All 7: name+host dedup clean, live (non-View-only) term, Remaining==Cap-Actual verified, real open/full mix.
LEADS not gated (do NOT ship without gating): UNC Greensboro ssb.uncg.edu (~18k, threw HTTP 500 on my search — Codex also flagged UNCG as a fresh lead; coordinate), Florida SouthWestern ssb.fsw.edu (English subj likely "ENC"), Rollins bannerweb.rollins.edu (odd term 202711 — verify).

### Batch 23 OUTCOME + CORRECTION (Fable, July 11 2026) — 2 shipped, 5 cut; my gating was flawed
Builder built batch 23: SHIPPED 2 (Bristol CC, Clovis CC — commit 60ba544, 653->655), CUT 5 (Missouri
State, Toledo, Stephen F. Austin, Alabama A&M, Utica). Builder was RIGHT to cut. Root cause is MINE and
worth recording so nobody re-hands-off these 5 as "clean":
- I gated batch 23 with a PARALLEL PROBE (my own bwckschd requests + my own regex), NOT the production
  Purdue adapter. My probe parsed real sections (81/58/84/... with real detail-page seats — those
  sections DO exist live). But running the PRODUCTION Purdue adapter (subclassed per host, real .fetch())
  returns GARBAGE for all 5: "1 phantom section, seats=None." The Purdue adapter's HTML parsing is
  Purdue-SPECIFIC and does not generalize to these hosts' markup. So they are NOT shippable on the
  existing adapter, even though the underlying data is real.
- Handoff errors I also own: Toledo term was 202710=Spring 2027 (real Fall=202640); Clovis course was
  "ENGL 111" (real=ENGL 1110). Bristol + Clovis happened to parse close enough to Purdue's markup to ship.
- PROCESS FIX (permanent): gate through the PRODUCTION adapter (instantiate the real class, call .fetch()),
  never a parallel probe — a probe that parses what the adapter can't gives false-clean handoffs. This is
  how Codex gates (NewColleague.fetch); I will do the same for every future handoff.
- RECOVERABLE? The 5 have real live Banner-8 data (verified via raw bwckschd + detail pages). Recovering
  them requires GENERALIZING the Banner-8 parser (section-listing + detail-page seat extraction) beyond
  Purdue's markup — a builder decision, not a clean add. Correct Fall terms if pursued: Missouri State
  202640 / Toledo 202640 / SFA 202710 / AAMU 202670 / Utica 202680; codes Missouri State+AAMU+Utica use
  3-letter (ENG/MTH/BIO), Toledo+SFA use 4-letter (ENGL). Not re-handed-off; flagged as a parser project.
GOOD CATCH by Builder worth noting: Purdue held _cache/_lock as CLASS-level state keyed by (term,subj,num)
with no school id — subclassing for multiple schools would cross-serve one school's seats for another
when term+subj+num coincide (Toledo/SFA/Purdue all 202710). Builder moved it per-instance before adding
anyone. Real latent false-data bug, caught by gating through production. Net today: 648->655 real.

### NEVER-SWEPT IPEDS breakthrough (Fable, July 11 2026) — Otis GATED, + Colleague leads for Codex
Root realization: every prior sweep used the Hipo "universities" dataset (2348). Pulled the FULL IPEDS
directory (Urban Institute API, free) = 6,256 US institutions; 1,197 degree-granting NEVER swept (mostly
small private 4-yr on Colleague + public CCs). Swept Banner+Colleague, 2 host-pattern passes.

✅ OTIS COLLEGE OF ART AND DESIGN (LA, ~1.1k) — Batch 24 SENT July 11. Existing Banner adapter,
4-line add: host="ssb1.otis.edu", term 202630 (Fall 2026), example "ENGL 108". GATED THROUGH THE
PRODUCTION Banner adapter (not a probe — Banner-8 lesson applied): Fall 2026 ENGL 108 = 12 sections, 8
open/4 full, real integer seats [7,4,2,0,11,1]. COMPLETED-TERM TEST PASSED (Fall 2025 View-Only ENGL
108 = 11 sec, 8 open/3 full — real full sections). Dedup clean. Small but real. Art subjects use codes
ANIM/DRWG/FINA/FSHD etc.; ENGL/ENTR standard.

COLLEAGUE LEADS FOR CODEX (never-swept, Colleague = Codex's lane — pick up + gate through production):
- Worcester State University (MA public 4-yr ~5-6k) — selfservice.worcester.edu — looks genuinely NEW, most promising.
- Colorado Mountain College — selfservice.coloradomtn.edu — was HOLD (fall not loaded); RE-CHECK now.
- American Samoa CC — amsamoa-ss.colleague.elluciancloud.com — was HOLD; re-check.
- Northcentral University — selfservice.northcentral.edu — verify (likely online/rolling terms).
SKIP: South Texas College (registration.southtexascollege.edu) — term 520271 returns EMPTY subjects =
same odd-CE-terms wash-out it was cut for. Bryant&Stratton (reg-prod.ec) = still all-View-Only (perm cut).
VEIN STATUS: never-swept pool (1197) has more to mine — only 2 host-pattern passes done; also ~2600
non-degree institutions filtered out. This is genuinely fresh ground the "mined out" claim never covered.

### Adapter queue outcome + listcrse VINDICATION (Builder, July 11 2026) — 655->658 live
Built+shipped the cleanest 3: UNC Greensboro (plain Banner-9 subclass), NCCU (new ListcrseBanner8
variant), UNC Asheville (bespoke JSON + cache). HELD per mandate: Berkeley (reserved-seat rule),
Fairfield (no completed term + cache), SDCCD×3 (status + cache).
⭐ LISTCRSE DISCOVERY RESURRECTS FABLE'S BATCH-23 CUTS: NCCU's guest SEARCH form answers "No classes
found" for everything, but the CATALOG route bwckctlg.p_disp_listcrse serves the same sections. Builder
confirmed Toledo shows 31 live CRNs and Missouri State 81 via p_disp_listcrse — MATCHING Fable's original
counts. So Fable's data was RIGHT (sections exist); the guest SEARCH FORM is what's broken, and the
production gate correctly refused to ship on it. ALL 5 batch-23 cuts (Missouri State/Toledo/SFA/AAMU/
Utica) are now RE-GATE CANDIDATES on ListcrseBanner8 — Builder will run that pass after the held adapters.
⚑ REUSABLE TECHNIQUE (Fable, adopt going forward): when a Banner guest search form returns "No classes
found" but the school clearly has sections, try the CATALOG route bwckctlg.p_disp_listcrse — it often
serves what the search form hides. This is the fix for the batch-23 "production adapter returns garbage"
divergence. Gate Banner via ListcrseBanner8 when the search form is broken.
CORRECTION: deploy was NOT pending — seatwatchapp.com has been LIVE at 655 since this evening (batches
21/22/23 all serving, badge/login/manifest verified). Only the 658 commit awaits the next scp. (Fable's
"deploy pending" note was stale — corrected.)
ANDROID: signed Play-Store bundle com.seatwatchapp.app v1.0.0 built + verified; waiting only on DUNS ->
Play account (Nathan's D-U-N-S docs went to D&B today).

### HANDOFF TO CODEX — the never-swept degree-granting pool (Fable, July 11 2026)
My never-swept-IPEDS breakthrough gave me Otis (Banner, shipped batch 24), but the pool is DOMINATED by
small private 4-yr colleges on COLLEAGUE — that's Codex's lane. A quick Banner-8 pass on it = 0 (these
schools aren't on guessable Banner hosts). So handing the full pool to Codex to sweep comprehensively:
- FILE: research/never_swept_degree_granting.json = 1,197 US degree-granting institutions (IPEDS sectors
  1/2/3/4) that were NEVER in the Hipo universities dataset all prior sweeps used, and are NOT in
  schools.py. Source: Urban Institute IPEDS directory API (educationdata.urban.org, free, no key) —
  6,256 total US institutions minus Hipo minus schools.py.
- CODEX: sweep this for Colleague (old + newer SearchAsync API, WITH redirect-following + program-
  prefixed-term check). My limited pass already surfaced Worcester State (selfservice.worcester.edu,
  promising), Colorado Mountain (re-check), American Samoa (re-check), Northcentral (verify) — but a
  full Colleague sweep of all 1,197 with your tooling will find more. This is genuinely fresh ground:
  938 of these are private-nonprofit 4-yr (the Colleague goldmine). Gate through production NewColleague.
- Shorter College (AR, small HBCU 2yr) — selfservice.shortercollege.edu — Colleague, from sector-5/7 never-swept sweep. Add to Codex Colleague pile.

### CT-LOG DISCOVERY vein OPENED (Fable, July 11 2026) — finds Banner on NON-guessable hosts
crt.sh still 502, but certspotter API works. CT-logging the never-swept PUBLIC colleges reveals Banner
registration hosts that host-guessing structurally CANNOT find. First pass (10 targets) → 1 clean win:

✅ STATE COLLEGE OF FLORIDA-Manatee-Sarasota (~10k) — Batch 25 SENT July 11. Existing Banner
adapter, ~3-line add. ⚠️ HOST IS NON-GUESSABLE: banner.banprod.scf.edu (StudentRegistrationSsb at root)
— found ONLY via CT-log. term 202710 (Fall 2026), example "ENC 1101" (43 sections; Florida uses ENC for
English Composition, not ENGL). GATED THROUGH PRODUCTION Banner: Fall 2026 ENC 0022 = 5 sec 5 open real
seats [11,4,10,18,13]. COMPLETED-TERM TEST PASSED: Fall 2025 (View Only) ENC 0022 = 6 sec, 1 open / 5
full — real full sections. Dedup clean. Method proven: CT-log the ~130 never-swept public 4-yr + public
CCs for banner./reg./ssb. subdomains → probe StudentRegistrationSsb → gate through production.

### Batch-23 RESURRECTION shipped (Builder, July 11) — 659->664, all 5 vindicated
ListcrseBanner8 recovered all 5 cuts: Missouri State (49 open/32 full), Toledo (19/12; its 202710=Spring
2027, adapter pinned 202640), SFA (46/12; its 202710 IS Fall 2026 — per-host term-code semantics differ,
labels win), Alabama A&M (3 open/58 full — real July fill), Utica (1/2). Original Fable counts matched at
every host (81/31/58/61/3). Per-instance cache verified before adding 5 instances. Day: 648->664 (+16).

⚑⚑ NEW ACCURACY LESSON (adopt in Fable's gate — refines the completed-term test):
- ENROLLMENT-ARITHMETIC sources (Banner numeric Cap/Act/Rem): a COMPLETED term can legitimately show
  ZERO full sections (post-drop melt = end-of-semester state), so all-open in a finished term is NOT
  proof of fake-open here. The STRONGER fake-open disproof for these sources is LIVE-term Act==Cap FULL
  rows (real enrollment that cannot be fabricated). Confirmed at Utica (completed terms legitimately all-
  open across 5 courses).
- STATUS-ENUM sources (textual Open/Closed, numeric 0/1/2): classic completed-term test UNCHANGED (a
  finished term must show real closed sections, else fake default).
So: for a numeric-seat Banner school, prefer "live term has Act==Cap full sections" as the disproof; a
clean completed-term is a bonus, not required. (State College of Florida already satisfies BOTH — Fall
2025 had 5 full AND it's numeric enrollment.)
South Texas College: re-confirmed DEAD (Banner-9, no listcrse route, empty-subjects wash-out stands).

### Batch 10 — new official public seat sources (Codex, July 12 2026)

These ten colleges are net-new against `schools.py` and the prior research notes. Every source passed
the research gate with a current/upcoming term and a completed or historical term check. They are
source-gated only: no production adapter, registry edit, or builder handoff has been made. Exact term,
course, section/CRN keys are mandatory in every future adapter; the named seat/status field is authoritative.

1. **Moorpark College (CA; VCCCD).** Official schedule: `https://schedule.vcccd.edu/list/?pace=1&site=1`.
   Fall 2026 (`202607`) mixed ACCT M40 CRN 70892 FULL 1/1/0, ARTH M100 CRN 73180 OPEN 5/4/1, and
   CS M125 CRN 70570 WAITLISTED 0/0/0; Spring 2026 (`202603`) had CLOSED rows including ACCT M01
   CRN 32905 50/26/24 and COMM M04 CRN 30043 32/25/7. Gate `status == OPEN` and `Rem > 0`; FULL,
   CLOSED, and WAITLISTED remain closed even when arithmetic is positive. Site/term/CRN scoping is required.
2. **Ventura College (CA; VCCCD).** Official schedule: `https://schedule.vcccd.edu/list/?site=3&term=202603&ztc=1`
   (Fall current is the same viewer with `site=3`). Fall examples include ACCT V03 CRN 73714 OPEN 32/11/21,
   ASTR C1001 CRN 73090 OPEN 48/16/32, and a WAITLISTED 46/46/0 row; Spring includes ACCT V08 CRN 32492
   OPEN 46/37/9 plus CLOSED rows with positive arithmetic. Same conservative VCCCD gate as Moorpark.
   This supersedes the older generic VCCCD “zero-result” triage note; the site-specific viewers are live.
3. **Community College of Rhode Island (RI).** Official Banner schedule:
   `https://bannerweb.ccri.edu/pls/DORA/bwckschd.p_disp_dyn_sched`. Fall 2026 `202630` ENGL 1010 had
   CRNs 38635 (25/20/5), 37948 (25/24/1), and full 13/13/0 rows; completed Spring 2026 `202610` had
   positive and full rows (for example CRN 16785 12/8/4 and CRN 16768 12/12/0). Gate exact term+subject+
   course+CRN/section and primary `Rem > 0`; ignore waitlist capacity.
4. **San José State University (CA).** Official schedules: `https://www.sjsu.edu/classes/schedules/fall-2026.php`
   and `/spring-2026.php`. Tables publish section, class number, mode, dates, and Open Seats; Fall examples
   include ANI 31 class 49986 (10) and 49987 (12), alongside zero-seat rows; Spring examples include AAS 1
   class 27509 (4) and AAS 25 classes 29124/29125 (19/16), with full rows present. Gate exact term+section+
   class number and `Open Seats > 0`; preserve reserve/permission/modality notes. Page is refreshed nightly.
5. **Lipscomb University (TN).** Official static tables: `https://courseschedule.lipscomb.edu/ScheduleP2026FALL.html`
   and `ScheduleP2026SPRING.html`. Fall BY2424 sections show 40 total/38 filled/2 available and a full lab
   20/20/0; Spring has mixed rows such as AAI1013 18/2/16, AM1213 16/15/1, and full sections. Gate exact
   term+course+section code and `Seats Available > 0`; retain delivery, location, and course notes.
6. **Foothill College (CA).** Official quarter viewer: `https://foothill.edu/schedule/index.html?Quarter=2026F&availability=all&dept=every`
   (completed check `Quarter=2026S`). Fall 2026 viewer reports 1,077 scheduled classes and numeric “x of y
   seats open” plus Open/Closed text (e.g., ACTG 1A CRN 20487 40/40); Spring includes ART 5B CRN 40423
   Open 8/30 and mixed closed/open rows. Gate exact quarter+course/section+CRN, require textual Open and
   positive open-seat count, and preserve modality/footnotes. This is a quarter calendar, not semester.
7. **Mt. San Antonio College / Mt. SAC (CA).** Official open-class viewer:
   `https://prod8s.mtsac.edu/prod/pw_sigsched.p_oclsonly?term_in=202620` (Spring completed `term_in=202510`).
   Fall lists open-only rows such as AD 1 CRN 23400 (22 seats), AD 10 CRN 23402 (15), SIGN 101 CRN 23223
   (15); Spring lists ID 10 CRN 44461 (13), LATN 2 CRN 43528 (20), and LEAD 55 CRN 42473 (22). Viewer
   says it updates about every five minutes and lists at least two open seats. Gate listed `Seats Available > 0`;
   omission means unknown, not closed, because this feed does not expose full rows. Preserve dates/modality.
8. **Lakeland Community College (OH).** Official viewer: `https://lkn.lakelandcc.edu/internet/academics/schedule/`
   (Fall 2026 current; Spring 2026 is View Only). Fall ARTS examples include CRN 10080 20/30 remaining,
   10079 21/30, 10083 6/15, 10090 5/12, plus FULL rows; Spring examples include ENGL rows with 2, 4, and
   6 remaining and full rows. Gate exact term+subject+course+CRN using the primary `N Remaining / Cap` field;
   FULL and zero remaining are closed, and PERM/restriction notes must be retained.
9. **University of Georgia (GA).** Official registrar schedule app: `https://reg.uga.edu/enrollment-and-registration/schedule-of-classes/`.
   The public app supports Spring and Fall 2026 and reports a July 12, 2026 refresh. Spring examples include
   AAEC 2580 CRN 61007 avail 36/100 and AAEC 3020 CRN 61009 avail 1/30 with full rows nearby; Fall includes
   AAEC 2580 CRN 10752 avail 49/100 and AAEC 3010 CRN 45990 avail 25/87. Gate exact term+Course ID+CRN and
   `Avail Seats > 0`; preserve campus/part-of-term/restrictions. This current registrar app supersedes the old
   Athena-CAS blocker note; re-check the public app rather than assuming UGA is unavailable.
10. **SUNY Potsdam (NY).** Official schedule page: `https://www.potsdam.edu/about/offices/registrar/class-schedules/class-schedule-department`.
    Linked hourly PDFs expose `CODE SUBJ CRSE SEC ... REQ ENR AVL`; Fall 2026 examples include ANTH 106 CRN
    91102 50/14/36, ANTH 106 CRN 91103 50/17/33, and BIOL 105 24/23/1 alongside closed/negative rows.
    The completed Spring 2026 PDF has mixed WAYS 103 rows (25/1/24, 25/2/23, 25/21/4). Gate exact
    term+subject+course+section/CRN and `AVL > 0`; `Closed` or negative values are closed. PDFs are hourly
    snapshots (static after term), so do not describe them as real-time.

**Batch status:** all ten are research-only leads pending a production adapter and explicit go-ahead. No
`schools.py` edits or builder message were made. Name/host dedup was clean for each candidate.

### Batch 11 — new public schedule sources (Codex, July 12 2026)

These are net-new against `schools.py` and the prior research notes. Five have direct current-plus-
historical seat rows in this pass; the remaining five are explicit source leads or partial captures
whose JavaScript/form/term coverage still needs a small follow-up probe. All remain research-only and
source-gated.

1. **Sandhills Community College (NC).** Official nightly seat tables: `https://olympus.sandhills.edu/seatsAvailable/2026FASeatsAvailable.htm`
   and `https://olympus.sandhills.edu/seatsAvailable/2026SPSeatsAvailable.htm`. Both pages expose
   `Dept Num Sec ... Max Seats Remaining Seats Comments`; Fall 2026 BIO 111 rows include 25/2 and
   25/14 open sections alongside zero and negative rows, while Spring 2026 has mixed 25/8, 25/7,
   and full rows. Gate exact term+subject+course+section and `Remaining Seats > 0`; attach blank
   continuation rows to the preceding section. These are nightly snapshots, not real-time feeds.
2. **The College of the Florida Keys (FL).** Official Banner detail pages: Fall 2026
   `https://secure.cfk.edu/prod/bwckschd.p_disp_detail_sched?crn_in=11488&term_in=202710` (MAT 1033,
   30/15/15) and Spring 2026 `https://secure.cfk.edu/prod/bwckschd.p_disp_detail_sched?crn_in=20654&term_in=202620`
   (MAT 1033, 30/19/11). The same
   pages show waitlist capacity separately. Gate exact term+subject+course+CRN and primary
   `Remaining > 0`; ignore waitlist remaining and preserve credit-level restrictions.
3. **Horry-Georgetown Technical College (SC).** Official Banner detail pages use host
   `https://ssb.hgtc.edu/PROD9/bwckschd.p_disp_detail_sched`. Fall 2026 (`term_in=202610`, CRN 1108)
   shows EGR 282 I02 at 18/11/7; Spring 2026 (`term_in=202520`, CRN 1108) shows RAD 115 S01 at
   24/23/1, with restrictions and syllabus flags. Gate exact term+subject+course+CRN and primary
   `Remaining > 0`; host term codes are local to this Banner instance.
4. **Kenyon College (OH).** Official static seat tables: `https://registrar.kenyon.edu/schedgrid.htm`
   links Fall 2026 `sep26_seats.htm` and Spring 2026 `jan26_seats.htm`. Spring page is timestamped
   July 11, 2026 and lists CRN, subject/number, title, instructor, meeting data, and `SEATS`; rows
   include open counts from 1 through 35. Gate exact term+CRN/section and `SEATS > 0`; the page is an
   open-only view, so omission means unknown rather than closed.
5. **Schoolcraft College (MI).** Official schedule viewer: `https://my.schoolcraft.edu/course-schedules/2026/Fall/All`
   and `https://my.schoolcraft.edu/course-schedules/2026/Spring/All`. Fall rows publish timestamped
   `Seat Available/Capacity/Waitlist` plus `Status` (for example 24/25/0 Open beside 0/14/0 Closed);
   Spring page exposes the same fields and mixed open/closed rows. Gate exact term+course+section,
   require `Status == Open` and positive first number, and preserve location, modality, fees, and
   start-date/part-of-term headings.
6. **Bentley University (MA).** Official real-time listing: `https://bentleyapps.azurewebsites.net/course-listing/`.
   The public page exposes Fall 2026 and Spring 2026 selectors, Open/Closed status filters, section
   identity, and a statement that enrollment/seats are updated in real time. The text-only fetch did
   not render result rows, so treat this as source-gated pending a browser/API form probe; do not infer
   seats from catalog presence.
7. **Grayson College (TX).** Official public planner: `https://planner.grayson.edu/Planner/CourseSearch/607`
   (Fall 2026) and `/Planner/CourseSearch/596` (Spring 2026). Rows include stable course-section IDs,
   dates, campus, `Seats: open/maximum`, and `Status`; Fall has both open and closed sections, while
   Spring has mixed rows (including 23/30 Open and 0/1 Open). Gate exact term+course-section ID,
   require explicit `Status == Open` plus positive open seats, and retain campus/modality notes.
8. **Catawba Valley Community College (NC).** Official viewer `https://cvcc.edu/schedules/` states
   that its public interactive schedule is real-time, identifies open/closed sections, and shows seats;
   the changelog documents refreshed Fall, Summer, and Spring 2026 JSON exports and `get_schedules.php`.
   This is a source-level lead pending a direct JSON-row capture; do not add an adapter from the HTML
   shell alone. Gate exact term+section, explicit status, and positive seats once the export is probed.
9. **University at Albany (NY).** Official registrar schedule search: `https://www.albany.edu/registrar/schedule-classes`.
   Public selectors include Spring 2026 (`0007`) and Fall 2026 (`0009`), a `Seats Available` filter,
   and a freshness note (“updated every 30–60 minutes”). The result form is a public POST surface but
   was not rendered by the text fetch; keep as source-gated until a browser/form capture confirms the
   row schema and mixed-term status behavior.
10. **Illinois Institute of Technology (IL).** Official BANR detail source:
    `https://ssb.iit.edu/bnrprd/bwckschd.p_disp_detail_sched?crn_in=52298&term_in=202620` (Spring 2026,
    CAE 474, 30/19/11) and the same host's public Banner catalog/detail route for Fall 2026. Spring
    evidence is direct and numeric; Fall indexing was unavailable during this pass, so hold as a
    source-gated lead until a Fall 2026 detail row is captured. Do not infer current availability from
    the Spring row.

**Batch status:** five rows have direct current/historical seat evidence; Kenyon has a current static
seat table plus a linked Fall table, while Bentley, Catawba Valley CC, Albany, and IIT remain explicit
source-surface/partial leads awaiting a browser, JSON, or missing-term capture. No `schools.py` edit,
production adapter, or builder handoff was made.

### Batch 12 — new public seat sources (AWAITING GO-AHEAD; Codex, July 12 2026)

These are net-new against `schools.py` and the prior research archive. Five are direct numeric
current-plus-completed-term sources that clear the research gate; Nicholls is intentionally retained as
a source-level partial because the current Fall PDF was linked but not parsed in this pass. All remain
research-only: no adapter, `schools.py` edit, or builder handoff was made.

1. **University of Oregon (OR) — GATED, AWAITING GO-AHEAD.** Official DuckWeb detail pages expose
   exact `term` + CRN rows at `https://duckweb.uoregon.edu/duckweb/hwskdhnt.p_viewdetl?crn=15278&term=202601`
   (Fall 2026 STAT 243Z, Avail 52/Max 322) and
   `https://duckweb.uoregon.edu/duckweb/hwskdhnt.p_viewdetl?crn=36117&term=202503`
   (completed Spring 2026 UGST 101, Avail 29/Max 30); other tested rows include current MATH 281
   (7/30) and completed PPPM/CLAS sections with both open and full values. The page labels the term
   and publishes `CRN`, `Avail`, and `Max`; Spring explicitly says registration is over, so the
   historical mixed values are a completed-term test. Gate exact term+CRN (and subject/course when
   selecting the row), use `Avail > 0`, and preserve `!`, `U`, `A`, discussion/lab relationships and
   any restriction text. Direct detail URLs are required; do not infer seats from a catalog/search shell.
   This supersedes the older archive note that DuckWeb had not yet been tested; the current detail route
   is live and numeric.
2. **University of the Virgin Islands (USVI) — GATED, AWAITING GO-AHEAD.** Official public schedule
   tables are split by campus but belong to one institution: St Thomas/St John
   `https://schedclass.uvi.edu/stxschedule.aspx?term=202608` (Fall 2026) and St Croix
   `https://schedclass.uvi.edu/sttschedule.aspx?term=202608`; St Martin is exposed at
   `https://schedclass.uvi.edu/sxmschedule.aspx?term=202601` for completed Spring 2026. Rows publish
   `CRN`, `MAX`, `ENROLL`, `AVAIL`, wait fields, and `STATUS`. Fall examples include ACC 201 CRNs
   82901 (20/2/18), 82902 (20/9/11), BIO 141A CRN 82594 (16/16/0), and NUR 318C CRN 82441 (8/8/0);
   Spring examples include EDU 250 CRN 15389 (20/3/17), EDU 302 CRN 15390 (20/18/2), and EDU 354
   CRN 15392 (20/21/-1). `STATUS` is `ACTIVE` even for full rows, so it is not an open-seat signal;
   gate exact campus term+CRN and primary `AVAIL > 0`, treating zero/negative availability as closed
   and ignoring waitlist capacity for seat alerts. Do not create separate schools for the campuses.
3. **Cal Poly Humboldt / California State Polytechnic University, Humboldt (CA) — GATED, AWAITING
   GO-AHEAD.** Official Registrar schedule landing page: `https://www.humboldt.edu/registrar/register/class-schedule`.
   Its linked reports are current Fall (`https://pine.humboldt.edu/anstud/cgi-bin/filt_schd.pl?relevant=sched_ind_Fall.out`)
   and completed Spring (`https://pine.humboldt.edu/anstud/cgi-bin/filt_schd.pl?relevant=sched_ind_Spring.out`),
   with subject reports such as `https://pine.humboldt.edu/anstud/cgi-bin/filter.pl?relevant=.%2Fcschd%2FschedFallART.out`.
   Tables publish `Class`, `Sect`, `CN#`, `Cap`, `Enr`, `Rsrvd`, `Avail`, and wait columns. Fall ART
   rows include CN 41185 (45/40/5), CN 41186 (45/26/19), and full CN 41187 (24/24/0); Spring rows
   include CN 21115 (45/43/2), CN 21116 (24/18/6), and a negative-availability cross-list row.
   Reports are updated once daily and explain that `Avail` is seats open to all students and can be
   reduced by cross-listed enrollment. Gate exact term+subject+CN#/section and `Avail > 0`; preserve
   reserved, cross-list, and note fields. These are daily snapshots, not real-time feeds.
4. **Lawrence University (WI) — GATED, AWAITING GO-AHEAD.** Official schedule entry point:
   `https://www.lawrence.edu/offices/registrar/class-schedule-and-course-catalog`. Public Banner
   summary routes such as `https://bannerweb.lawrence.edu/pls/voyager/zwglolib.call_class_schd_from_web_p?p_attr_code=G046&p_attr_code=N011&p_subj_code=%25`
   expose exact CRNs and `L:<limit> R:<registered> W:<waitlist>` values; Fall 2026 CHJA 202 CRNs 5197/5198
   are 10/3/0 and 10/2/0, while CHJA 212 CRNs 5200/5201 are 10/2/0 and 10/0/0. Direct Banner detail
   pages also publish numeric enrollment/seat fields, e.g. Fall 2026 BIOL 130 CRN 5278
   (`https://bannerweb.lawrence.edu/pls/voyager/bwckschd.p_lu_call_unsec?crn_in=5278&crse_numb_in=130&last_term_in=202650&ptrm_in=1&seq_numb_in=A&subj_code_in=BIOL&term_in=202650`)
   has 16 seats remaining from a 24-seat limit. Completed Spring 2026 (`202630`) detail rows are
   available through the same route and are explicitly past-registration. Gate exact term+subject+
   course+CRN/sequence, use primary seats remaining (`L-R` or detail available seats), ignore waitlist
   capacity, and preserve cross-list/restriction notes.
5. **Concordia University Chicago (IL) — GATED, AWAITING GO-AHEAD.** Official timestamped PDFs:
   current Fall 2026 `https://webserv.cuchicago.edu/files/forms-repository/registrar/academic-schedules/Fall_UG_Schedule.pdf`
   and completed Spring 2026 `https://webserv.cuchicago.edu/files/forms-repository/registrar/academic-schedules/Spring_UG_Schedule.pdf`.
   The header defines `Seats=Available Seats/Enrollment Cap`; Fall examples include BIO-1201 CRNs
   15736/15737/15738/15739 at 1/18, 3/18, 0/18, and 11/18, and BUS-1001 CRNs 16112/16113 at 23/25 and
   25/25. Spring examples include COM-1100 CRNs 13136/13137/13138 at 2/25, 0/25, and 13/25, plus
   COM-2200 CRN 13143 at 1/25 and a negative-availability CRJ row. Gate exact term+course+section+CRN;
   use the first number in `Seats` as the primary availability, treating zero/negative as closed, and
   preserve `F`/`R`/`P` flags (fee/reserve/prerequisite), modality, and part-of-term. PDFs are dated
   snapshots (Fall file last updated 05/18/2026; Spring 04/08/2026), not real-time.
6. **Nicholls State University (LA) — SOURCE-LEVEL PARTIAL, AWAITING FOLLOW-UP.** Official registrar
   page `https://www.nicholls.edu/register/2026-fall-semester/` links the current Fall 2026 schedule
   PDF (`https://www.nicholls.edu/register/wp-content/uploads/sites/81/2026/07/07-10-Fall-2026.pdf`)
   and the web view. The same official archive exposes parsed Spring PDFs, including
   `https://www.nicholls.edu/register/wp-content/uploads/sites/81/2026/02/02-06-Spring-2026.pdf` and
   `https://www.nicholls.edu/register/wp-content/uploads/sites/81/2026/01/01-30-Spring-2026.pdf`.
   Rows publish `Subject`, `Num`, `Sec`, `CRN`, `Max`, `Enr`, `Avail`, `Wl Max`, and `Wl Actual`, with
   mixed completed-term values such as CULA 105 CRN 19454 (20/9/11), CULA 101 CRN 18586 (30/32/0),
   PSYC 101 CRN 19407 (75/29/46), PSYC 210 CRN 18386 (20/19/1), and NURS 255 CRN 18215 (90/87/3).
   The current Fall PDF is linked from the official page and dated 07/10, but its body was not parsed
   in this pass; do not claim current Fall rows until a direct download/parse confirms the same schema.
   Follow-up gate: exact term+subject+number+section+CRN and `Avail > 0`, with waitlist fields kept
   separate from primary seats.

**Batch status:** five candidates have direct current and completed-term numeric evidence and are
marked `GATED, AWAITING GO-AHEAD`; Nicholls is a deliberately explicit source-level partial pending
one PDF parse. Name/host dedup checks were clean for all six. No production adapter, `schools.py` edit,
or builder handoff was made.

### Batch 13 — new public seat sources (AWAITING GO-AHEAD; Codex, July 12 2026)

This smaller follow-up batch adds one clean, net-new full source and one explicitly bounded public
source lead. Both were deduped against `schools.py` and this archive. No production code or builder
handoff was made.

1. **Monroe Community College (NY) — GATED, AWAITING GO-AHEAD.** Official course pages expose
   current Fall 2026 sections, e.g. `https://www.monroecc.edu/classes/eng-101-sections/`, and the
   same route exposes completed Spring 2026 pages, e.g. `https://www.monroecc.edu/classes/202620/spc-141-sections/`
   and `https://www.monroecc.edu/classes/phl-250-sections/`. Each page publishes the exact course,
   section, CRN, modality/location, meeting dates, `Seats Remaining`, and `Already on Waitlist`.
   Fall ENG-101 examples include CRN 10048 (5 remaining), 10049 (21), 10051 (0), and 10073 (11);
   Fall MTH-211 includes CRNs 11960 (13), 11966 (17), 11968 (0 with waitlist 1), and 12733 (12).
   Completed Spring PHL-250 has CRNs 32789 (0), 33254 (14), and 35945 (3); Spring TRS-099 CRN
   33849 reports 7 remaining. The source has mixed positive/zero rows in both terms and is not an
   all-open status shell. Gate exact term + subject/course + section + CRN, use `Seats Remaining > 0`
   as the primary signal, keep waitlist count separate, and collapse repeated meeting rows for the
   same CRN. Preserve modality, campus, date range, corequisite/permission text, and late-start
   filters. The college page is per-course rather than one giant list, so discovery must follow the
   subject/course index or a bounded course set; do not treat catalog-only pages as availability.
2. **University of Alaska Anchorage (AK) — SOURCE-LEVEL PARTIAL, AWAITING FOLLOW-UP.** UAA
   department schedule pages are public and publish `CRN`, section, dates, and numeric `Open Seats`,
   for example Fall 2026 Philosophy (`https://www.uaa.alaska.edu/academics/college-of-arts-and-sciences/departments/philosophy/degree-programs/schedule.cshtml`)
   with PHIL A101 CRNs 71238 (6), 71236 (5), and 71237 (21), and Fall Alaska Native Studies with
   CRNs 70464 (4), 71626 (12), and 75021 (11). A completed-term page exists for a bounded program,
   Spring 2026 Civic Engagement (`https://www.uaa.alaska.edu/academics/office-of-academic-affairs/faculty-development-instructional-support/community-engagement/current-cel-course-offerings.cshtml`),
   where CEL A390 CRN 36352 reports 55 open seats. These pages explicitly direct users to UAOnline
   for the authoritative full schedule; only department/program pages were captured here, so this is
   not yet a college-wide gate. Follow-up must discover the public UAOnline/department index, prove
   current-plus-completed mixed rows across more than one department, and retain exact term+CRN keys;
   never infer closed rows from omitted sections.

**Batch status:** Monroe clears the direct current-plus-completed numeric gate and is marked
`GATED, AWAITING GO-AHEAD`. UAA is a deliberately bounded source lead pending a college-wide public
index/UAOnline capture. No production adapter, `schools.py` edit, or builder handoff was made.

### Batch 14 — CVC Exchange source leads (Codex, July 12 2026)

These are net-new colleges surfaced through the official California Virtual Campus (CVC) public
exchange. CVC publishes live/timestamped seat counts and term/CRN rows, but it is a cross-college
exchange rather than each college's primary schedule. They are therefore documented as source-level
leads only until a direct college schedule or a formally validated CVC adapter scope is established.

1. **Rio Hondo College (CA) — SOURCE-LEVEL PARTIAL, AWAITING FOLLOW-UP.** CVC course page
   `https://search.cvc.edu/courses/687657` identifies Rio Hondo College and publishes exact term,
   CRN, dates, modality, and `Live Seat Count`. The same course has Spring 2026 CRN 35358 with 20
   available seats (historical snapshot), Fall 2026 CRN 74332 with 10 available and `Open`, and Fall
   2025 CRN 74332 with 7 available. CVC warns that counts change rapidly and may not reflect the
   latest status; the repeated CRN across terms proves that the key must include term + CRN. Follow-up
   must compare CVC rows with Rio Hondo's direct schedule, preserve section dates/part-of-term and
   prerequisites, and reject stale/`Already Started` rows for current alerts.
2. **Laney College (Peralta Community College District, CA) — SOURCE-LEVEL PARTIAL, AWAITING
   FOLLOW-UP.** CVC page `https://search.cvc.edu/courses/1031669` identifies Laney College and
   exposes numeric live counts for both terms: Spring 2026 MATH 3C CRN 21753 has 5 available seats,
   while Fall 2026 CRN 41750 has 24 available; both rows include exact dates, synchronous modality,
   and meeting times. The page notes that counts are fast-changing and the college's own Peralta
   email/Canvas instructions are included, but CVC is still an exchange surface. Gate exact term +
   college + subject/course + CRN, use `Live Seat Count > 0`, retain term dates and notes, and verify
   against Laney/Peralta's direct schedule before any production handoff.

**Batch status:** both CVC entries have current-plus-completed numeric examples but remain deliberately
source-level partials because CVC is an exchange surface and its freshness/college-scope contract needs
to be validated. No production adapter, `schools.py` edit, or builder handoff was made.

### Batch 15 — reproducibility and status-quality audit (Codex, July 12 2026)

1. **Clarkson University (NY) — SOURCE-LEVEL PARTIAL, AWAITING FOLLOW-UP.** A public PeopleSoft
   enrollment table is indexed at `https://mycu-g.clarkson.edu/psc/guest/EMPLOYEE/SA/c/CU_SELF_SERVICE.CU_SR_CLSS_ENR.GBL`.
   The Fall 2026 snapshot advertises 1,736 rows and explicit `Capacity`, `Section Enrolled`, `Total
   Enrolled`, `Available Seats`, waitlist, class number, subject/catalog/section, dates, and meeting
   fields; examples include AC 202 class 8846 (50/37/13), COMM 217 class 8505 (20/19/1), and CS 141
   class 8331 (48/13/35). Direct guest fetch currently redirects to a PeopleSoft login/cookie gate,
   and a completed Spring 2026 table was not reproduced in this pass. Keep as a lead only: a follow-up
   must establish a stable guest session, capture both term selectors, and prove row freshness before
   any adapter or handoff.
2. **CVC Exchange contradiction audit — do not promote additional colleges yet.** Direct inspection
   of the Rio Hondo (`https://search.cvc.edu/courses/687657`), Laney (`https://search.cvc.edu/courses/1031669`),
   Ohlone (`https://search.cvc.edu/courses/15188594`), College of the Siskiyous
   (`https://search.cvc.edu/courses/1078969`), and Santa Ana (`https://search.cvc.edu/courses/1839541`)
   pages found positive `Live Seat Count` values alongside contradictory text such as “Sorry, this
   section is full. Open.” Because the numeric count and status label disagree, CVC `Live Seat Count`
   cannot be treated as a production open/closed signal by itself. Batch 14 remains source-level only;
   any future CVC candidate needs direct-college reconciliation or an independently verified status
   contract. The contradictory Ohlone, Siskiyous, and Santa Ana pages were intentionally rejected rather
   than added as candidates.

**Batch status:** Clarkson is a reproducibility-blocked source lead. The CVC audit is a deliberate
quality hold, not a handoff. No production adapter, `schools.py` edit, or builder handoff was made.

### Batch 16 — additional public schedule lead (Codex, July 12 2026)

1. **Austin Community College (TX) — SOURCE-LEVEL PARTIAL, CONTINUING-EDUCATION ONLY.** ACC's
   official Continuing Education schedule exposes timestamped HTML tables with `Open Seats`,
   enrollment/capacity, synonym, section, dates, campus, modality, and an explicit legend: a numeric
   first column is remaining seats, `c` is closed, and `x` is cancelled. Current Fall 2026 examples
   from `https://continue.austincc.edu/schedule/schedule.php?ct=CE&op=browse&snid=31632&term=226FCE`
   include ITSE 1091 synonym 54387 section 101 (2 open; 13/15 enrolled/capacity) and ITSE 1092
   synonym 55851 section 102 (11 open; 5/16). Completed Spring 2026 examples from
   `https://continue.austincc.edu/schedule/schedule.php?ct=CE&op=browse&snid=30986&term=226SCE`
   include MATX 0101 synonym 48992 (11 open; 9/20) and synonym 48995 (19 open; 1/20). These are
   continuing-education/non-credit offerings, not the regular ACC credit schedule; the feed is useful
   as a separate source lead but must not be merged into a credit-course adapter. Follow-up gate:
   confirm whether SeatWatch wants CE scope, key exact term+synonym/section, treat legend codes as
   authoritative, and validate freshness across a completed term before any handoff.

**Batch status:** Austin ACC is explicitly partial and scope-limited to Continuing Education. No
production adapter, `schools.py` edit, or builder handoff was made.

### Batch 17 — ten additional CVC college leads (contradiction hold; Codex, July 12 2026)

This batch deliberately records ten net-new college identities from the official California Virtual
Campus (CVC) exchange. CVC pages expose term/section keys and numeric `Live Seat Count`, but direct
inspection in Batch 15 found positive counts beside contradictory “Sorry, this section is full. Open.”
labels. Accordingly, **none of these ten is gated or ready for production**. They are research leads
for direct-college reconciliation; do not infer open/closed from the CVC count alone.

1. **Cuesta College (CA) — SOURCE-LEVEL PARTIAL, HOLD.** `https://search.cvc.edu/courses/1076303`
   identifies Cuesta and publishes Spring 2026 BIO212 section 30613 with 2 live seats, Summer 2026
   sections 51633/50052 with 0, Fall 2026 sections 75925 and 70902 with 0 and `Section Full`, and a
   completed Fall 2025 section 70902 with 0. Use exact term + subject/course + section; preserve
   delivery mode, dates, prerequisites, and the sample-syllabus/first-day-materials notes. Follow-up
   must reconcile CVC rows and statuses against Cuesta's own schedule before any adapter work.
2. **College of the Redwoods (CA) — SOURCE-LEVEL PARTIAL, HOLD.**
   `https://search.cvc.edu/courses/1051374` identifies BIOL7. Spring 2026 sections V0045/V1921 show
   1 and 5 live seats; Summer 2026 V2467/V3117 show 3 each; Fall 2026 V1313 is 0 and `Section Full`;
   completed Fall 2025 V0928/V9333 are 0. Rows warn that sections may be merged and include
   proctoring/lab-material notes. Key by term + section (not course title alone), and reconcile with
   Redwoods' direct schedule.
3. **San Jose City College (CA) — SOURCE-LEVEL PARTIAL, HOLD.**
   `https://search.cvc.edu/courses/1623201` identifies MATH78. Fall 2026 section MATH-078-101 reports
   0 seats; completed Fall 2025's same section reports 14. The page explicitly warns that the MATH78/
   MATH79 sequence should be completed at SJCC and that transfer institutions may reject split sequences.
   Preserve the exact section, prerequisite, WebAssign/Respondus notes, and the CVC snapshot timestamp.
4. **Berkeley City College (CA) — SOURCE-LEVEL PARTIAL, HOLD.**
   `https://search.cvc.edu/courses/4681398` identifies MMAN24. Fall 2026 CRN 43403 reports 37 live
   seats; completed Fall 2025 CRN 40487 reports 21. The page contains synchronous meeting times and
   Peralta portal instructions. Key by term + CRN, retain both meeting rows, and reconcile against
   Peralta/Berkeley City College's direct schedule.
5. **Contra Costa College (CA) — SOURCE-LEVEL PARTIAL, HOLD.**
   `https://search.cvc.edu/courses/1034345` identifies MATH292. Spring 2026 section 3694 reports 19
   live seats and is marked already started; the page includes Canvas/Zoom and webcam requirements.
   This capture did not reproduce a current Fall row, so do not claim a college-wide current-plus-
   completed gate. Follow-up must find the direct schedule and a current term before handoff.
6. **Mendocino College (CA) — SOURCE-LEVEL PARTIAL, HOLD.**
   `https://search.cvc.edu/courses/1055903` identifies BIO200. Spring 2026 sections 5290/4132 show
   positive CVC counts (23/1 in the captured page) while the rendered status text simultaneously says
   “Sorry, this section is full. Open.”; completed Fall 2025 sections 0122/0131 show 3/5. The page is
   a concrete example of the CVC contradiction, so status must be treated as untrusted until direct
   Mendocino data is reconciled.
7. **Mission College (CA) — SOURCE-LEVEL PARTIAL, HOLD.**
   `https://search.cvc.edu/courses/1834171` identifies MAT12. Spring 2026 sections 31734/31735 are
   0/0; Fall 2026 sections 71812/71810/71811 report 26/0/1, but the page renders contradictory
   full/open and low-availability labels beside those counts. Preserve exact section, term, ZTC badge,
   and prerequisite/placement text; verify with Mission's direct schedule.
8. **Santa Barbara City College (CA) — SOURCE-LEVEL PARTIAL, HOLD.**
   `https://search.cvc.edu/courses/1027746` identifies PHYS121. Spring 2026 sections 50169/50168
   report 3/0; Fall 2026 sections 42281/42280 report 21/17; completed Fall 2025 sections 42280/42281
   report 0/0. The page includes physics prerequisites and multiple online sections; reconcile exact
   term + section against SBCC's own schedule and ignore the CVC open label until that check passes.
9. **Compton College (CA) — SOURCE-LEVEL PARTIAL, HOLD.**
   `https://search.cvc.edu/courses/10699511` identifies MATH140. Spring 2026 section 30635 reports
   18 live seats; Fall 2026 section 70617 reports 19. Both rows carry ZTC and prerequisite information.
   CVC status/count disagreement is still possible, so verify direct Compton data and retain term +
   section as the key.
10. **Chaffey College (CA) — IDENTITY/SOURCE LEAD ONLY, HOLD.**
    `https://search.cvc.edu/courses/1049168` identifies Chaffey's ENGL1B (CCN ENGL C1001), location
    Rancho Cucamonga, and its OEI/online-support badges, but the captured page rendered no section rows
    or current/completed seat values. This is a discovery lead only; do not add a seat adapter unless a
    direct Chaffey schedule or a reproducible CVC section response is captured.

**Batch status:** ten new college names were archived, with nine having numeric CVC section evidence
and Chaffey held at identity-only. All ten remain `SOURCE-LEVEL PARTIAL`/`HOLD` because CVC is an
exchange surface and the numeric/status contradiction is known. No `schools.py` edit, production
adapter, or builder handoff was made. A follow-up should reconcile the strongest candidates (SBCC,
Compton, Mission, Cuesta, Redwoods) against their direct schedules before any gate marker is added.

### Batch 18 — additional direct registrar/schedule surfaces (Codex, July 12 2026)

This sweep moved off CVC where possible. Clark University and Wabash have reproducible current and
completed public rows; the remaining four are explicitly bounded source leads because the public page
does not yet expose a complete, numeric, mixed-term feed without an additional browser/session step.

1. **Clark University (MA) — SOURCE-GATED, AWAITING FOLLOW-UP.** Official registrar tables are
   public at `https://apps.clarku.edu/course-listings/course-grid-fall-2026-ug-gs/ugopen` (Fall 2026)
   and `https://apps.clarku.edu/course-listings/registrarSPRING26/undergraduate` (completed Spring
   2026). Rows expose CRN, course/section, title, capacity (`CAP`), enrollment (`Enr`), instructor,
   meeting pattern, room, prerequisites, and permission-only flags. Fall examples include PSYC 101-01
   CRN 20059 (CAP 90 / Enr 47), PHYS 130-01 CRN 20037 (16/11), and HEBR 101-01 CRN 20187 (19/16);
   Spring examples include MATH 119-01 CRN 30147 (25/10), MUSC 104-01 CRN 34700 (25/18), and
   PSYC 108-01 CRN 30193 (75/37). Use `CAP - Enr` only after validating the table's reserve-seat and
   permission semantics; preserve CRN + term + section and do not collapse cross-listed rows. The
   current Fall page also has dedicated “courses with seats remaining” views, but an adapter must
   fetch the all-courses table to retain closed and reserved sections.
2. **Wabash College (IN) — SOURCE-GATED, AWAITING FOLLOW-UP.** Official registrar pages expose a
   term selector and row-level status at `https://www.wabash.edu/apps/registrar/course-sections/?sortby=SectionName&term=26%2FFA`
   (Fall 2026) and the same route with `term=26%2FSP` (completed Spring 2026). Each row publishes
   section key, title, `OPEN`/`CLOSED`/`WAITLISTED`, dates, meeting fields, capacity, enrolled,
   available, and waitlist counts. Fall examples: ACC-201-01 (25 capacity, 18 enrolled, 7 available,
   open), ACC-301-01 (15/5/10, open), and ART-126-01 (10/10/0, waitlisted). Spring examples include
   ACC-202-01 (60/35/25, open), ART-125-01 (12/11/1, open), and ART-202-01 (35/35/0, waitlisted).
   Exact term + section is mandatory; cross-listed sections, senior/class-year restrictions, and
   waitlist counts must remain separate from primary availability. This is a strong reusable source,
   pending a production adapter's live-fetch and reserve/cross-list tests.
3. **Long Beach City College (CA) — SOURCE-LEVEL PARTIAL, CVC HOLD.**
   `https://search.cvc.edu/courses/12881068` identifies LBCC's ETHST1 and exposes Fall 2026 CRNs
   71016/71015/71018 with 11/11/18 live seats and CRN 71013 with 0 and `Section Full`. The page has
   exact dates, online format, CRNs, and a mixed current open/full set, but this capture did not
   reproduce a completed term. Treat the source as CVC-only and subject to the known CVC numeric/status
   contradiction; reconcile with LBCC's direct schedule before any handoff.
4. **Butler County Community College / BC3 (PA) — PUBLIC-INDEX LEAD, FOLLOW-UP REQUIRED.**
   `https://www.bc3.edu/credit-schedule/index.html` publishes official Summer 2026 and Fall 2026
   session links, registration dates, credit/online/hybrid format definitions, and links into the
   college's Colleague schedule. The linked schedule currently requires the authenticated myBC3 flow,
   so no numeric row or completed-term comparison was captured. Do not treat the term index as seat
   availability; follow up only if the guest Colleague route exposes `Available`, capacity, and status.
5. **Hawkeye Community College (IA) — COLLEAGUE INDEX LEAD, FOLLOW-UP REQUIRED.**
   `https://www.hawkeyecollege.edu/academics/credit-courses/` confirms that Summer/Fall 2026 course
   search is public and directs users to the official `colss-prod.hawksaas.elluciancloud.com` search;
   it also documents guest registration and exact Fall 2026 deadlines. The search route was not
   captured as a row-level guest feed in this pass, so no seats or status are claimed. Follow up only
   after reproducing a guest session with exact section IDs, capacity, available seats, and a completed
   term.

**Dedup correction:** Farmingdale State College was removed from this batch because `schools.py`
already contains the `SUNYFarmingdale` adapter. It is not a new candidate and must not be added again.

**Batch status:** five additional college identities were archived. Clark and Wabash meet the direct
current-plus-completed numeric/status evidence bar but remain pending production-gate tests; Long Beach
City is a CVC hold; BC3 and Hawkeye are clearly marked non-seat source leads. No
`schools.py` edit, production adapter, or builder handoff was made.

### Batch 19 — Wesleyan/Lakeland public schedules and two bounded follow-up leads (Codex, July 12 2026)

These four identities are net-new against `schools.py` and the prior research notes. Wesleyan and
Lakeland have reproducible current-plus-completed public seat data; York College of Pennsylvania and
University of Houston are deliberately recorded as source-surface leads only because the public pages
did not expose a complete guest row feed in this pass. No seat values are inferred for the latter two.

1. **Wesleyan University (CT) — SOURCE-GATED, AWAITING FOLLOW-UP.** Official WesMaps course pages are
   public and expose course/section, instructor, meeting data, total enrollment limit, `Seats Available`,
   class-year/major bins, permission/prerequisite notes, and update timestamps. The public Fall 2026
   all-offered index is `https://owaprod-pub.wesleyan.edu/reg/%21wesmaps_page.html?crse_list=XAMS&facid=NONE&offered=Y&stuid=`;
   example Fall pages include ECON 301 (`term=1269`) with sections showing 30 available and 0 available
   (`https://owaprod-pub.wesleyan.edu/reg/%21wesmaps_page.html?crse=003706&term=1269`), while the completed
   Spring 2026 ECON 103 page (`term=1261`) has sections with 9 and 22 available
   (`https://owaprod-pub.wesleyan.edu/reg/%21wesmaps_page.html?crse=016767&stuid=&term=1261`) and other
   Spring courses show zero/negative availability. Registrar guidance explains that the displayed bins
   can restrict seats by class year/major and that `X` means excluded
   (`https://www.wesleyan.edu/registrar/information/wesmaps_navigation.html`). Gate exact term+CID+section;
   do not turn a positive aggregate into universally open unless the eligible bin/permission state is
   satisfied. Preserve cross-listings, prerequisites, POI, and `Drop/Add Enrollment Requests`; current
   pages are live registration snapshots, not immutable catalog data.
2. **Lakeland University (WI) — SOURCE-GATED, STATIC SNAPSHOT.** Registrar-published undergraduate PDFs
   expose course, section, session, dates, meeting/location/instructor, and `Seats available: N of M`.
   Current Fall 2026 is `https://lakeland.edu/pdfs/catalog/2026/FA26%20UGRD.pdf` (revised July 7, 2026;
   e.g., GEN 110 sections with 8/18, 3/18, 18/18, and 0/18) and completed Spring 2026 is
   `https://lakeland.edu/pdfs/catalog/2026/SP26%20UGRD.pdf` (revised February 10, 2026; e.g., ACC 396
   rows with 30/30 and 10/30). The schedule index is `https://lakeland.edu/course-schedules`. Gate exact
   term+course+section+session and `Seats available > 0`; these are timestamped PDFs rather than
   real-time feeds. A section can appear on multiple meeting rows, so dedupe by course/section/session
   while retaining all meeting data; preserve online/face-to-face modality and notes.
3. **York College of Pennsylvania (PA) — PUBLIC-INDEX LEAD, FOLLOW-UP REQUIRED.** Official registrar
   documentation at `https://www.ycp.edu/offices-departments/registrar` and schedule index
   `https://www.ycp.edu/academics/calendars-schedules` state that YCPWeb's Schedule of Classes shows
   section status, available seats, and waitlist seats/markers. The actual YCPWeb schedule currently
   requires an authenticated student portal; this pass captured no guest rows, term IDs, or numeric
   seats. Treat this as a discovery lead only. Follow up only if a public schedule endpoint can be
   reproduced for Fall/Spring with exact CRN/section, capacity/available, status, and a completed-term
   mixed sanity check.
4. **University of Houston (TX) — LIMITED-SCOPE PUBLIC SEARCH LEAD.** The official online-session class
   search at `https://www.uh.edu/online/sessions/class-search.php` documents a public search for short
   Session 2–6 courses, including Fall 2026 dates, seat availability, and a twice-daily refresh. The
   results are delivered through an embedded search frame and this pass did not capture a complete row
   payload or a completed Spring 2026 comparison; it is not evidence for the regular UH schedule. Keep
   this scoped to the named online short sessions and require a guest row capture plus current/completed
   mixed status test before considering an adapter.

**Batch status:** two additional identities (Wesleyan and Lakeland) meet the direct current-plus-completed
numeric evidence bar but remain source-gated; York College of Pennsylvania and University of Houston are
clearly marked non-seat/limited-scope leads. No `schools.py` edit, production adapter, or builder handoff
was made.

### Batch 20 — New Mexico Banner source and Dickinson public-schedule lead (Codex, July 12 2026)

This pass found one new direct numeric source and one carefully bounded public-schedule lead. Both are
net-new against `schools.py` and prior notes; neither has been handed to the builder.

1. **University of New Mexico (NM) — SOURCE-GATED, AWAITING FOLLOW-UP.** UNM's public Banner dynamic
   schedule is `https://lobowebapp.unm.edu/ban_ssb/bwckschd.p_disp_dyn_sched`; it exposes Fall 2026,
   Spring 2026 (view-only), and older terms, with separate continuing/community-ed and MD/PharmD term
   families. Official detail pages publish `Capacity Actual Remaining`, waitlist counts, cross-listings,
   restrictions, prerequisites, campus, modality, and timestamps. Fall 2026 (`term_in=202680`) example
   MATH 401-002 CRN 81893 is 35/11/24 with waitlist 18/0/18 and a MATH 501 cross-list; completed Spring
   2026 (`term_in=202610`) MATH 536-002 CRN 57430 is 20/6/14. Example detail URLs are
   `https://lobowebapp.unm.edu/ban_ssb/bwckschd.p_disp_detail_sched?crn_in=81893&term_in=202680` and
   `https://lobowebapp.unm.edu/ban_ssb/bwckschd.p_disp_detail_sched?crn_in=57430&term_in=202610`. Gate
   exact term+CRN+subject/course/section and primary `Remaining > 0`; keep waitlist and cross-list seats
   separate, and preserve program/level restrictions. A production adapter still needs an all-subject
   guest fetch plus a completed-term full/closed-row sanity check before handoff.
2. **Dickinson College (PA) — PUBLIC BANNER LEAD, FOLLOW-UP REQUIRED.** Dickinson's official registrar
   FAQ confirms that its Class Schedule Search and Detailed Class Information screen are public and expose
   capacity, first-year reserved seats, actual enrollment, and remaining seats; it explicitly warns that
   remaining seats can be reserved for incoming students and that cross-listed classes require special
   handling (`https://www.dickinson.edu/info/20088/registrars_office/388/faculty_faqs/2`). The public
   Banner term selector is `https://bannerdprod.dickinson.edu/prod_ssb/bwckschd.p_disp_dyn_sched` and
   lists Fall 2026 plus Spring 2026 view-only. This pass did not reproduce a detail row or CRN through the
   guest form, so no numeric seat value is claimed. Follow up only after capturing current and completed
   detail pages, including FY-reserved, cross-list, and full-section examples; do not equate aggregate
   Remaining with universally open seats.

**Batch status:** University of New Mexico is a direct numeric source with current/completed examples but
remains source-gated pending all-subject and full-row tests. Dickinson is explicitly a public Banner lead
without captured row values. No `schools.py` edit, production adapter, or builder handoff was made.

### Batch 21 — Chabot-Las Positas district Banner surfaces (Codex, July 12 2026)

The Chabot-Las Positas Community College District exposes a public Banner host with campus-specific
sections. These identities are net-new against `schools.py`; the shared host must never be treated as one
college, and every adapter key must retain the campus identity.

1. **Las Positas College (CA) — SOURCE-GATED, AWAITING FOLLOW-UP.** Official detail pages on
   `https://banssprod.clpccd.cc.ca.us/ssbprod/bwckschd.p_disp_dyn_sched` expose `Capacity Actual Remaining`,
   waitlist counts, campus, CRN, course/section, modality, prerequisites, and restrictions. Fall 2026
   (`term_in=202602`) STAT L40-HC1 CRN 23124 is Las Positas campus, 31/22/9, with waitlist 20/0/20;
   completed Spring 2026 (`term_in=202505`) MATH 2-HC1 CRN 50852 is 31/30/1, while PHYS 1B-HC1 CRN
   53281 is full at 22/22/0. Example URLs:
   `https://banssprod.clpccd.cc.ca.us/ssbprod/bwckschd.p_disp_detail_sched?crn_in=23124&term_in=202602`,
   `https://banssprod.clpccd.cc.ca.us/ssbprod/bwckschd.p_disp_detail_sched?crn_in=50852&term_in=202505`,
   and `https://banssprod.clpccd.cc.ca.us/ssbprod/bwckschd.p_disp_detail_sched?crn_in=53281&term_in=202505`. Gate
   exact term+campus+CRN+subject/course/section and primary `Remaining > 0`; keep waitlist/cross-list seats
   separate and preserve honors/field restrictions. The all-subject guest fetch and campus selector still
   need a production test.
2. **Chabot College (CA) — SOURCE-LEVEL PARTIAL, FOLLOW-UP REQUIRED.** The same official host exposes
   Chabot campus rows and the district's public Fall 2026 schedule index
   (`https://banssprod.clpccd.cc.ca.us/clpccd/2026/02/l/sched_ntrn.htm`). A completed Spring 2026 detail
   for Chabot ENGL 1-O09 CRN 52280 shows 28/29/-1 (an over-capacity edge case) at
   `https://banssprod.clpccd.cc.ca.us/ssbprod/bwckschd.p_disp_detail_sched?crn_in=52280&term_in=202505`.
   This pass did not reproduce a Fall 2026 Chabot detail row, so no current seats are claimed. Follow up
   only after capturing a current Chabot CRN plus a mixed current/completed set; do not collapse Chabot and
   Las Positas rows under the district host.

**Batch status:** Las Positas has direct current-plus-completed numeric evidence but remains source-gated
pending all-subject/campus tests. Chabot is explicitly partial pending a current detailed row. No
`schools.py` edit, production adapter, or builder handoff was made.

### Batch 22 — Fifteen new public schedule surfaces (Codex, July 12 2026)

This batch contains fifteen net-new college identities after exact-name checks against `schools.py` and
the prior research notes. It deliberately mixes one strong numeric public schedule with bounded leads;
no seat value below is treated as production evidence unless the source and term scope are explicit.

1. **Cayuga Community College (NY) — SOURCE-GATED, AWAITING FOLLOW-UP.** Fall 2026 is a public row index,
   updated July 11, 2026, with CRN, course/section, dates, instructor, campus/modality and numeric
   `Availability`: `https://www.cayuga-cc.edu/academics/schedule-of-classes/fall/`. Mixed rows include
   BUS 225-701 at 0 and BUS 225-702 at 16; the page says myCayuga is the real-time lookup. Capture
   Spring 2026, exact CRN+subject/course+section keys, completed-term mixed status, and reserve/waitlist
   semantics before any adapter; do not assume `Availability` is universally registerable.
2. **Washington College (MD) — SOURCE-LEVEL PARTIAL, FOLLOW-UP REQUIRED.** The Fall 2026 PDF
   (`https://www.washcoll.edu/people_departments/offices/registrar/course-schedule/26fa-course-schedule-updated.pdf`)
   exposes `Section Cap`, `Currently Enrolled`, `Remaining Available Seats`, and `Seats Waitlisted`,
   with cross-list names/restrictions. The registrar index is `https://www.washcoll.edu/people_departments/offices/registrar/registration-instructions.php`.
   This is a timestamped snapshot; no completed Spring row or fresh live feed was captured.
3. **California State University, Long Beach (CA) — SOURCE-LEVEL PARTIAL, FOLLOW-UP REQUIRED.** The
   July 6, 2026 Fall schedule (`https://web.csulb.edu/depts/enrollment/registration/class_schedule/Fall_2026/By_College/EOP.html`)
   exposes section/class number, reserve-capacity information, and an `OPEN SEATS` field. Only the
   EOP slice was captured; follow up with all subjects, a completed term, and reserve-seat semantics.
4. **Indiana University Bloomington (IN) — PUBLIC SCHEDULE LEAD, FOLLOW-UP REQUIRED.** IU's official
   Fall 2026 page (`https://studentcentral.indiana.edu/register/schedule-classes/fall-2026.html`) says
   the public schedule is updated daily and links no-login iGPS for real-time availability. No iGPS rows
   or completed-term mix were captured; preserve component lecture/lab and exact class numbers.
5. **Le Moyne College (NY) — PUBLIC SCHEDULE LEAD, FOLLOW-UP REQUIRED.** The registrar index
   (`https://www.lemoyne.edu/academics/classes-calendars-catalogs/`) links a public Fall 2026 and prior-term
   table (`https://echo.lemoyne.edu/courseavail/Q09VUlNFLTI2L0ZB.htm`, last updated May 29, 2026).
   It exposes section/date/instructor/modality data but no authoritative seat/status field was reproduced;
   do not infer openness from listing presence.
6. **Kalamazoo Valley Community College (MI) — PUBLIC-INDEX LEAD, FOLLOW-UP REQUIRED.** The official
   announcement (`https://www.kvcc.edu/news/stories/2026-04-07_FallRegistration.php`) links the Fall
   2026 schedule and registration dates. No row feed was captured; require guest section IDs, availability,
   and a completed-term test.
7. **Great Bay Community College (NH) — PUBLIC DYNAMIC LEAD, FOLLOW-UP REQUIRED.** The schedule page
   (`https://mygbcc.greatbay.edu/academics/academic-affairs/course-schedule-offerings/`) lists Summer/Fall
   2026 and Spring 2027 and documents real-time Dynamic Schedule filtering. Endpoint:
   `https://sis.ccsnh.edu/ssb8/bwckschd.p_disp_dyn_sched`. No result rows were captured; verify campus
   identity, seat field, and completed-term mix.
8. **Wayne Community College (NC) — PUBLIC DYNAMIC LEAD, FOLLOW-UP REQUIRED.** Wayne says Self-Service
   provides up-to-date seating availability and links current Summer/Fall 2026 and completed Spring
   2026 schedules (`https://www.waynecc.edu/admissions/course-schedules/`). The guest endpoint is
   `https://ss-prod.cloud.waynecc.edu/Student/Courses`; no row payload was captured and linked PDFs are
   not live seat data.
9. **Hope College (MI) — PUBLIC DYNAMIC LEAD, FOLLOW-UP REQUIRED.** `https://schedule.hope.edu/` exposes
   Fall 2026/Spring 2026 terms, filters, and `Open`, `Closed`, `Completed`, `In Progress`, `Permission`,
   and `Waitlisted` statuses; the registrar confirms publication at `https://hope.edu/offices/registrar/registration-schedules/`.
   No query rows or seat number were captured; preserve status/waitlist semantics.
10. **Middlebury College (VT) — SOURCE-LEVEL PARTIAL, FOLLOW-UP REQUIRED.** Registrar guidance
    (`https://www.middlebury.edu/registrar/registration/fall-reg-dates`) says to subtract `Reserved Incoming`
    and `Reserved Cont.` from `Seats Avail`; `WL` denotes a waitlist. No current/completed row was
    captured. Retain all reservation columns and never equate aggregate seats with unrestricted seats.
11. **Shasta College (CA) — PUBLIC-INDEX LEAD, FOLLOW-UP REQUIRED.** The schedule index
    (`https://www.shastacollege.edu/academics/course-catalogs-and-class-schedules/`) links Fall and Spring
    2026 PDFs and says MyShasta is most current. The PDFs had no live seat field in this capture; follow
    up through guest/current MyShasta with a completed-term mixed test.
12. **Navarro College (TX) — PUBLIC DYNAMIC LEAD, FOLLOW-UP REQUIRED.** The registration calendar
    (`https://www.navarrocollege.edu/registration-calendar.html`) exposes no-login public Self-Service and
    printable Fall 2026 16-week/8-week schedules. No detail rows or completed comparison were captured;
    keep each session in the term key and require an authoritative availability/status field.
13. **Wheaton College (IL) — SOURCE-LEVEL PARTIAL, FOLLOW-UP REQUIRED.** Wheaton says Banner Self-Service
    is real-time and links Spring/Fall 2026 (`https://www.wheaton.edu/about-wheaton/offices-and-services/office-of-the-registrar/schedules`).
    The Fall packet (`https://www.wheaton.edu/__data/assets/file/0010/30403/Fall-2026-Registration-Packet.pdf`)
    has CRNs/capacities but warns Banner is most accurate; no available-seat rows were reproduced.
14. **Westmont College (CA) — PUBLIC-INDEX LEAD, FOLLOW-UP REQUIRED.** Westmont's registrar page
    (`https://www.westmont.edu/office-registrar/registration`) confirms Fall 2026 and Spring 2026 dates,
    but the current schedule is behind Waypoint/student access. No public seat rows or numeric availability
    are claimed; follow up only if a guest endpoint is reproducible.
15. **Arcadia University (PA) — PUBLIC-INDEX LEAD, FOLLOW-UP REQUIRED.** Arcadia's course-listings page
    (`https://www.arcadia.edu/academics/resources-advising/registrar/course-listings/`) directs users to
    current Self-Service data and its registrar documents Fall 2026 registration. No public row-level
    seat/status payload was captured; require exact section identifiers and current/completed tests.

**Batch status:** fifteen net-new identities were archived. Cayuga has the clearest current public
numeric availability surface; Washington College and CSULB expose seat-bearing static/current fields;
the rest are explicitly bounded schedule or dynamic-endpoint leads. None passed the full production gate
in this research-only pass. No `schools.py` edit, registry change, deployment, or builder handoff was made.

### Codex Batch 23 — Ten additional public schedule surfaces (July 12 2026)

These ten identities are net-new after exact-name checks against `schools.py` and all prior research
notes. They are intentionally separated into current public surfaces and legacy/retiring UH pages; no
stale or restricted row is presented as live production evidence.

1. **Portland Community College (OR) — SOURCE-LEVEL PARTIAL, FOLLOW-UP REQUIRED.** PCC's Fall 2026
   schedule pages (for example `https://www.pcc.edu/schedule/fall/fn/fn225/`) expose CRN, modality,
   dates, instructor, and a `Seats available` field; the public topic index is
   `https://www.pcc.edu/schedule/fall/`. Some captured rows returned `Available` while others said
   `Data currently unavailable`, so exact row freshness and a completed-term comparison are required.
2. **MiraCosta College (CA) — SOURCE-LEVEL PARTIAL, FOLLOW-UP REQUIRED.** The official PeopleSoft open-
   classes list (`https://surf.miracosta.edu/psc/ps/EMPLOYEE/SA/c/MCC_CUSTOM_FL.MZ_CLASS_LIST_FL.GBL?TERM=FALL`)
   advertises 1,122 Fall 2026 open-credit rows with class number, dates, modality, and `Seats Open`.
   Direct replay redirected to login in this pass; reproduce a guest session, exact class keys, and a
   completed-term full/closed sanity set before any adapter.
3. **Northern Arizona University (AZ) — PUBLIC PEOPLESOFT LEAD, FOLLOW-UP REQUIRED.** NAU's public Fall
   2026 class search (`https://www.peoplesoft.nau.edu/psc/ps92prcs/EMPLOYEE/SA/c/COMMUNITY_ACCESS.CLASS_SEARCH.GBL`)
   exposes section, session, available seats, status icons, and reserved-seat indicators. Search-result
   rows were visible for Fall 2026, but this pass did not reproduce a full current/completed comparison;
   preserve reserved seats and exact section/SUN keys.
4. **Purchase College (NY) — PUBLIC-INDEX LEAD, FOLLOW-UP REQUIRED.** The registrar's official guide
   (`https://www.purchase.edu/offices/registrar/registration-guide/`) documents Fall 2026 registration,
   add/drop, parts of term, and MyHeliotrope access. No public row-level seat payload was captured;
   follow up only if the schedule can be reproduced without student login and with exact CRN/status.
5. **Massachusetts College of Liberal Arts (MA) — PUBLIC-INDEX LEAD, FOLLOW-UP REQUIRED.** The official
   Fall 2026 registration PDF (`https://mcla.edu/_pdfs/administration/registrar/2026-fall-registration-info.pdf`)
   confirms the current term and CRN-based registration workflow, but no guest seat rows were captured.
   Do not infer availability from the registration guide; require a public current/completed schedule.
6. **Honolulu Community College (HI) — LEGACY PUBLIC SEAT LEAD, DO NOT HAND OFF YET.** The UH legacy page
   (`https://www.sis.hawaii.edu/uhdad/avail.classes?frames=y&i=HON&s=HAW&t=202630`) exposes Fall/Spring-
   style CRN rows with enrolled, seats available, waitlist, dates, and restrictions; a Spring 2026
   example shows 20 seats available. The page is explicitly marked as unavailable after December 2025,
   so this is historical evidence only until the replacement UH Banner route is found.
7. **Kapiolani Community College (HI) — LEGACY PUBLIC SEAT LEAD, DO NOT HAND OFF YET.** A Spring 2026
   detailed page (`https://www.sis.hawaii.edu/uhdad/bwckschd.p_disp_detail_sched?crn_in=33859&inst_in=KAP&term_in=202630`)
   shows `Seats 0 / Remaining 20`, term, campus, and restrictions. The UH service is a retiring legacy
   surface; capture the replacement before treating this as live.
8. **University of Hawaiʻi Maui College (HI) — LEGACY PUBLIC SEAT LEAD, DO NOT HAND OFF YET.** The
   Spring 2026 class-availability page (`https://www.sis.hawaii.edu/uhdad/avail.classes?i=MAU&s=IS&t=202630`)
   publishes CRN, enrolled, seats available, reserved seats, waitlist, dates, and restrictions. It
   explicitly says the page will not be available after December 2025; no current Fall replacement was
   captured, so retain only as a bounded historical lead.
9. **Windward Community College (HI) — LEGACY PUBLIC SCHEDULE LEAD, DO NOT HAND OFF YET.** The official
   institution page (`https://www.sis.hawaii.edu/uhdad/avail.classes?i=WIN`) lists Spring 2026 as a
   formerly active term and explicitly warns that the webpage will not be available after December 2025.
   No current replacement rows were captured; this is identity/system reconnaissance only.
10. **Hawaiʻi Community College (HI) — LEGACY PUBLIC SEAT LEAD, DO NOT HAND OFF YET.** The UH detailed
    page (`https://www.sis.hawaii.edu/uhdad/avail.class?c=15199&i=HAW&t=202610`) identifies the campus,
    term, CRN, section, course dates, and registration details for Fall 2025; the companion UH listing
    documents numeric seat fields on the legacy surface. It is not current Fall 2026 evidence and must
    not be promoted until a replacement guest feed is verified.

**Batch status:** ten additional identities were archived. PCC, MiraCosta, and NAU have the most useful
current public schedule/seat-field leads; Purchase and MCLA are registration-surface leads. The five UH
entries are explicitly legacy/retiring and are held out of any builder handoff. No `schools.py` edit,
registry change, deployment, or builder handoff was made.

### Codex Batch 38 — Ohio Valley and Midwest public schedule leads (July 12 2026)

1. **Bowling Green State University (OH) — PUBLIC NUMERIC-DETAIL CLASS-SEARCH LEAD, FOLLOW-UP REQUIRED.**
   BGSU’s public search at `https://services.bgsu.edu/ClassSearch/search.htm` exposes Fall 2026, career,
   Main/Firelands campus, distance/online, subject, course number, attributes, and class-number filters.
   BGSU’s official guide says course-title details include enrollment information. Capture current and completed
   terms, preserving Main versus Firelands, undergraduate/graduate career, instruction mode, capacity, and
   waitlist/restriction semantics.
2. **Marshall University (WV) — PUBLIC NUMERIC-SCHEDULE LEAD, FOLLOW-UP REQUIRED.** Marshall’s official
   registrar schedule at `https://mubert.marshall.edu/scheduleofcourses.php` currently exposes Fall 2026,
   campus choices (Huntington, Off-Campus, South Charleston, Electronic, WV Rocks, Technology Based), part-
   of-term filters, and an Open Class List route. Capture public section details and a completed term; preserve
   campus, modality, part-of-term, open/closed, waitlist, and permission fields before adapter work.
3. **University of Northern Iowa (IA) — PUBLIC REAL-TIME SCHEDULE LEAD, FOLLOW-UP REQUIRED.** UNI’s registrar
   explicitly publishes a Fall 2026 Online Public Search and says it is updated in real time
   (`https://registrar.uni.edu/schedule-of-classes`; linked search `https://sis.uni.edu/psp/cssprd/EMPLOYEE/HRMS/c/COMMUNITY_ACCESS.CLASS_SEARCH.GBL?Folder=MYFAVORITES&PAGE=SSR_CLSRCH_ENTRY`).
   The linked PeopleSoft page redirected to sign-in here, so no seats are inferred. Confirm a guest route,
   then replay current/completed terms and preserve UNI career, campus, status, waitlist, and restriction fields.
4. **Duquesne University (PA) — PUBLIC BANNER CLASS-SEARCH LEAD, FOLLOW-UP REQUIRED.** Duquesne’s registrar
   links a public Banner term-selection/class-search endpoint at `https://bannerprodss.duq.edu/StudentRegistrationSsb/ssb/term/termSelection?mode=search`.
   The official registrar identifies schedule publication, Banner support, and Fall 2026 academic services;
   this pass captured the guest term selector but no populated rows. Replay Fall 2026 and a completed term,
   preserving undergraduate/graduate career, cross-registration, reserve, waitlist, and permission semantics.
5. **West Virginia University (WV) — PUBLIC COURSE-LISTING/OPEN-SECTION LEAD, FOLLOW-UP REQUIRED.** WVU’s
   official FAQ directs users to `https://courses.wvu.edu`, and its ACCESS guide documents semester, subject,
   WVU-campus-only, and “Open Sections Only” filters for the same course listing. No numeric guest row was
   captured; verify Fall 2026 plus a completed term, isolate Morgantown/other campuses and Web-Based sections,
   and preserve seat, waitlist, eligibility, and non-degree/ACCESS restrictions.

**Batch status:** five net-new U.S. college identities were archived. BGSU, Marshall, Duquesne, and WVU expose
public schedule routes; UNI is advertised as public but redirected to PeopleSoft sign-in here. No seats were
inferred. All five were deduped against `schools.py` and prior research. No production approval, `schools.py`
edit, registry change, deployment, or builder handoff was made.

### Codex Batch 36 — Five new public schedule pathways (July 12 2026)

1. **Rutgers University (NJ) — PUBLIC MULTI-CAMPUS SCHEDULE LEAD, FOLLOW-UP REQUIRED.** Rutgers’ official
   Schedule of Classes at `https://classes.rutgers.edu/` exposes term, campus, level, school/subject/keyword,
   and Open/Closed section filters; the live page includes Fall 2026 campus/unit metadata. Capture section
   detail rows and a completed term, isolating New Brunswick, Newark, and Camden (and graduate versus
   undergraduate units) while preserving reserved seats, waitlists, cross-campus offerings, and restrictions.
2. **University of Delaware (DE) — PUBLIC NUMERIC COURSE-SEARCH LEAD, FOLLOW-UP REQUIRED.** UD’s official
   Courses Search at `https://www.udel.edu/courses` (redirecting to `https://udapps.nss.udel.edu/CoursesSearch/`)
   explicitly provides seat availability, Fall 2026 term 2268, “Courses with open seats,” campus/location,
   delivery-mode, session, and cross-list filters. Location/instructor details require login, so capture
   public Fall 2026 rows and a completed term without assuming those fields; preserve Newark/Dover/Georgetown/
   Wilmington/online campus identity and reserve-capacity semantics.
3. **San José State University (CA) — PUBLIC NUMERIC CLASS-SCHEDULE LEAD, FOLLOW-UP REQUIRED.** SJSU’s
   official Fall 2026 table at `https://www2.sjsu.edu/classes/schedules/fall-2026.php` is refreshed nightly and
   exposes class number, instruction mode, dates, and an explicit Open Seats column (including zero values).
   SJSU documents reserve capacities that can make seats appear unavailable to some students and directs users
   to MySJSU for real-time listings. Replay the public table and a completed term, preserving reserve groups,
   waitlist, campus/program, modality, and nightly-freshness semantics.
4. **University of Maine (ME) — CLASS-SEARCH/WAITLIST LEAD, FOLLOW-UP REQUIRED.** UMaine’s Office of Student
   Records links a Fall 2026 Class Search and current course-offerings snapshot at `https://studentrecords.umaine.edu/students/enrollment/`;
   the linked PeopleSoft search redirected to sign-in here. The same official page documents section waitlists,
   position numbers, automatic enrollment conditions, and permission courses. Treat this as login-gated until a
   sanctioned guest route is found; do not infer seats, and verify a completed term if access becomes public.
5. **University of Washington–Seattle (WA) — PUBLIC COURSE-OFFERINGS/STATUS LEAD, FOLLOW-UP REQUIRED.** UW
   states that its official schedule is updated daily and that Autumn 2026 has a limited public Course Offerings
   view plus a five-digit Schedule Line Number status inquiry at `https://www.washington.edu/students/timeschd/`.
   The complete Time Schedule requires NetID, so capture the public offering/status surface only if it exposes
   numeric availability; isolate Seattle from Bothell/Tacoma/PCE, and preserve quarter, SLN, waitlist, and
   completed-quarter semantics.

**Batch status:** five net-new U.S. college identities were archived. Delaware and SJSU expose explicit public
seat-oriented fields; Rutgers and UW expose public schedule/status pathways; UMaine is currently login-gated.
No seats were inferred for any entry. All five were deduped against `schools.py` and prior research. No
production approval, `schools.py` edit, registry change, deployment, or builder handoff was made.

### Codex Batch 24 — Eleven current public-search leads (July 12 2026)

These eleven identities are net-new after exact-name checks against `schools.py` and prior research
notes. Only USC has a captured current numeric row in this pass; the remaining entries are bounded
public-search or login-gated leads and must not be treated as live seat evidence until replayed.

1. **University of Southern California (CA) — PUBLIC NUMERIC LEAD, FOLLOW-UP REQUIRED.** USC's official
   Fall 2026 schedule (`https://classes.usc.edu/term/20263/catalogue/school/DRNS/program/CLAS`) publishes
   course-level `Available Seats` values and explicit `ALL SECTIONS FULL` markers (for example, CLAS 151
   shows 10 available seats). Verify section-level identifiers, reserved/D-clearance semantics, and a
   completed-term comparison before adapter work.
2. **University at Buffalo (SUNY) (NY) — PUBLIC-INDEX LEAD, FOLLOW-UP REQUIRED.** UB's registrar documents
   a guest Public Class Schedule that non-UB users can use to view available classes
   (`https://www.buffalo.edu/registrar/instructions-for-using-HUB/class-search.html`); the non-degree
   page explicitly points to Fall 2026 and the public schedule
   (`https://www.buffalo.edu/registrar/registration/non-degree-seeking-students/register-as-a-non-degree-seeking-student.html`).
   No result row or seat value was captured here; reproduce the Fall 2026 guest flow and preserve class,
   section, waitlist, and reserve fields.
3. **University of Wisconsin–Eau Claire (WI) — PUBLIC DYNAMIC LEAD, FOLLOW-UP REQUIRED.** UW–Eau Claire's
   official CampS guest-search guide (`https://kb.uwec.edu/articles/public-search-in-the-class-schedule`)
   identifies a no-login Class Search, an automatic `Show Open Classes Only` filter, and green-open/blue-
   closed status icons. Capture a current term and completed term, and confirm whether the guest payload
   exposes numeric seats or only status.
4. **University of Minnesota (MN) — PUBLIC DYNAMIC LEAD, FOLLOW-UP REQUIRED.** The University of
   Minnesota's official registration guide links a Public Class Search and says guests can filter to open
   classes and click a class number to view seats (`https://onestop.crk.umn.edu/registration/register-classes/search-classes`).
   The search spans multiple campuses; keep the selected institution/campus in every key and verify
   current/completed rows before any campus-specific adapter.
5. **Cal Poly, San Luis Obispo (CA) — PUBLIC DYNAMIC LEAD, FOLLOW-UP REQUIRED.** Cal Poly's registrar
   documents a public class schedule for the Fall 2026 cycle and a `Show Open Course` checkbox that limits
   results to sections with seats (`https://registrar.calpoly.edu/class-search`). Capture the public rows,
   exact class numbers, campus/location, and a completed-term full/closed sanity set.
6. **Los Angeles Mission College (CA) — PUBLIC-INDEX LEAD, FOLLOW-UP REQUIRED.** The official Fall 2026
   calendar (`https://www.lamission.edu/sites/lamc.edu/files/2026-04/2026%20Fall%20Calendar.pdf`) points
   students to the public schedule index/SIS and states that open classes may be enrolled during the first
   days. No live row-level seat payload was captured; follow the schedule link and require explicit status
   or available-seat fields.
7. **University of California, San Diego (CA) — LOGIN-GATED PUBLIC-INDEX LEAD, FOLLOW-UP REQUIRED.** UCSD's
   current registrar guidance covers Fall 2026, directs users to Schedule of Classes/WebReg, and says
   results include the number of available seats (`https://students.ucsd.edu/my-tritonlink/tools/tool-help/schedule-of-classes.html`).
   The TSS transition is scheduled for July 2026, so do not assume the old endpoint remains valid; capture
   the new guest surface and preserve quarter/session keys.
8. **University of New Hampshire (NH) — PUBLIC-INDEX LEAD, FOLLOW-UP REQUIRED.** UNH's official guidance
   explains that WebCat exposes open/available seats and distinguishes `Closed`/`Reserve Closed`, with
   Fall 2026 registration dates (`https://chhs.unh.edu/advising/course-registration`). The WebCat search
   redirected to login in this pass; no numeric rows are claimed.
9. **New York University — ITP program only (NY) — LIMITED-SCOPE PROGRAM LEAD, FOLLOW-UP REQUIRED.** NYU
   ITP's Fall 2026 registration guide says Albert Course Search exposes `Open`, `Wait list available`, and
   `Closed` statuses (`https://itp.nyu.edu/help/fa26-itp-registration/`). This is not evidence for NYU's
   general schedule: keep the adapter scope limited to ITP unless a separate guest feed is reproduced.
10. **Los Angeles Valley College (CA) — PUBLIC-INDEX LEAD, FOLLOW-UP REQUIRED.** LAVC's registrar page
    lists Fall 2026 dates, a searchable SIS schedule, and a Daily Course Listing that can be sorted by open/
    closed status (`https://www.lavc.edu/academics/class-schedule`). Capture section IDs and numeric seats
    from the linked public listing; do not infer seats from the calendar alone.
11. **Gettysburg College (PA) — LOGIN-GATED LEAD, FOLLOW-UP REQUIRED.** Gettysburg's current Fall 2026
    advising guide says its Class Search can show all classes with seats available and a number of open
    seats (`https://www.gettysburg.edu/offices/center-student-success/academic-support/first-year-advising-registration-guide`).
    The workflow requires Campus Experience credentials, so treat this as a discovery lead only until a
    guest schedule or sanctioned public endpoint is found.

**Batch status:** eleven net-new identities were archived. USC is the only captured current numeric
surface; UB, UW–Eau Claire, UMN, Cal Poly SLO, and LAVC are the best public-search follow-ups. UCSD,
UNH, NYU ITP, and Gettysburg are explicitly login- or scope-gated. No `schools.py` edit, registry change,
deployment, or builder handoff was made.

### Codex Batch 25 — Ten Maricopa public numeric campus leads (July 12 2026)

Maricopa's official public class search (`https://classes.sis.maricopa.edu/`) was queried with the
Fall 2026 term and institution filters. It exposes campus name, class number, delivery, dates, status,
and numeric availability such as `7 of 24 seats available`; closed rows explicitly say `No seats
available`. These are separate colleges on one district host: campus identity and the institution filter
must remain part of every key, and a completed-term mixed full/open test is still required.

1. **Paradise Valley Community College (AZ) — PUBLIC NUMERIC DYNAMIC LEAD, FOLLOW-UP REQUIRED.** Fall
   2026 public rows include Paradise Valley sections with `Open` status and examples such as 7/24 seats
   available. Reproduce with the institution filter and preserve class number, session dates, and campus.
2. **Glendale Community College (AZ) — PUBLIC NUMERIC DYNAMIC LEAD, FOLLOW-UP REQUIRED.** The same public
   search returns Fall 2026 Glendale sections, including open and closed statuses and examples such as
   13/24 seats available. Do not merge Glendale rows with other Maricopa campuses.
3. **Phoenix College (AZ) — PUBLIC NUMERIC DYNAMIC LEAD, FOLLOW-UP REQUIRED.** Phoenix College rows are
   visible through institution code `PCC01` (`https://classes.sis.maricopa.edu/?institutions%5B%5D=PCC01`),
   with Fall 2026 `Open`/`Closed` statuses and numeric availability (for example, 15/24). Preserve the
   institution code and all session/late-start notes.
4. **Rio Salado College (AZ) — PUBLIC NUMERIC DYNAMIC LEAD, FOLLOW-UP REQUIRED.** Fall 2026 Rio Salado
   online and flex-start rows publish numeric availability (examples include 23/35 and 34/35) and explicit
   status. Keep start/end dates and the online-session identity in the section key.
5. **Scottsdale Community College (AZ) — PUBLIC NUMERIC DYNAMIC LEAD, FOLLOW-UP REQUIRED.** Scottsdale
   rows are available under institution code `SCC05` (`https://classes.sis.maricopa.edu/?institutions%5B%5D=SCC05&terms%5B%5D=4266`),
   including Fall 2026 open rows with examples such as 15/25 seats. Preserve program restrictions and
   course-fee notes; an open row is not necessarily unrestricted.
6. **South Mountain Community College (AZ) — PUBLIC NUMERIC DYNAMIC LEAD, FOLLOW-UP REQUIRED.** South
   Mountain is available under `SMC07` (`https://classes.sis.maricopa.edu/?institutions%5B%5D=SMC07`),
   with Fall 2026 open/closed rows and examples such as 20/32 seats. Preserve campus-specific class numbers
   and any permission or cohort notes.
7. **Mesa Community College (AZ) — PUBLIC NUMERIC DYNAMIC LEAD, FOLLOW-UP REQUIRED.** Fall 2026 Mesa
   sections appear in the public search with numeric open-seat values (for example, 13/28 in a Chandler-
   Gilbert/Mesa-filtered result). Confirm the selected Mesa institution code before any adapter and retain
   every campus/session field.
8. **Chandler-Gilbert Community College (AZ) — PUBLIC NUMERIC DYNAMIC LEAD, FOLLOW-UP REQUIRED.** The
   public Fall 2026 search shows Chandler-Gilbert rows with Open/Closed status and numeric values such as
   18/28 seats. Use the institution filter rather than inferring campus from course location text.
9. **Estrella Mountain Community College (AZ) — PUBLIC NUMERIC DYNAMIC LEAD, FOLLOW-UP REQUIRED.** Fall
   2026 rows are directly reproducible with institution code `EMC10` (`https://classes.sis.maricopa.edu/?institutions%5B%5D=EMC10`),
   including open and closed rows and examples such as 18/24 seats. Keep the code, class number, and
   flex-start date range together.
10. **GateWay Community College (AZ) — PUBLIC NUMERIC DYNAMIC LEAD, FOLLOW-UP REQUIRED.** GateWay rows
    are directly visible under `GWC03` (`https://classes.sis.maricopa.edu/?institutions%5B%5D=GWC03`),
    including Fall 2026 open sections such as 24/24 and 13/20 seats. Preserve permission-required notes
    and do not treat every open seat as generally enrollable.

**Batch status:** ten net-new Maricopa campus identities were archived. All have current Fall 2026
public numeric/status evidence, but none has passed the completed-term, campus-isolation, restriction, and
cache/freshness tests required for production. No `schools.py` edit, registry change, deployment, or
builder handoff was made.

### Codex Batch 26 — Bespoke public-schedule reconnaissance (July 12 2026)

This pass targets institution-specific public searches rather than shared vendor endpoints. The entries
below are intentionally gated: a bespoke surface must still pass a real current/completed-term test and
freshness check before anyone builds it.

1. **University of Kansas (KS) — BESPOKE REVISIT LEAD, FOLLOW-UP REQUIRED (not a new identity).** KU's
   official Schedule of Classes help confirms that public search results carry class number, seats
   available, enrollment/capacity, meeting data, and a `Don't show full and unopened sections` filter
   (`https://classes.ku.edu/Classes/help.jsp`). The existing reconnaissance found the Struts search form
   at `https://classes.ku.edu/Classes/` but POST probes timed out; capture one successful browser/network
   trace with the Fall 2026 term before calling this production-ready.
2. **University of Hawaiʻi at Mānoa (HI) — BESPOKE PUBLIC-INDEX LEAD, FOLLOW-UP REQUIRED.** Mānoa's current
   registrar says schedules are now in Browse Classes and Fall 2026 was published April 13
   (`https://manoa.hawaii.edu/undergrad/schedule/`; calendar: `https://manoa.hawaii.edu/registrar/academic-calendar/fall-2026/`).
   UH's current class-availability guidance defines `Seats Avail` as the number of open seats
   (`https://www.hawaii.edu/myuhinfo/class-availability-information/`). This is a current replacement
   route, not the retiring UH legacy pages; capture guest rows, exact campus/term keys, and a completed
   term before adapter work.
3. **Kent State University (OH) — BESPOKE PUBLIC NUMERIC LEAD, FOLLOW-UP REQUIRED.** Kent's official
   department guide points to the no-login ePROD search
   (`https://keys.kent.edu:44220/ePROD/bwlkffcs.p_adv_unsecure_sel_crse_search`) and explicitly says it
   shows course details and the number of seats remaining, with subject/campus/course-level filters
   (`https://www.kent.edu/spcs/course-schedules-and-schedule-planning`). Capture Fall 2026 and a finished
   term, preserve CRN/campus/part-of-term fields, and verify that the seat value is current rather than a
   static department snapshot.
4. **University of Louisville (KY) — LOGIN-GATED BESPOKE LEAD, FOLLOW-UP REQUIRED.** Louisville's current
   registration guidance documents a Class Search and Enroll `Availability` column with waitlist states for
   Fall 2026 (`https://student.louisville.edu/registrar/courses-advising/find-classes-plan-your-coursework/waitlist-closed-classes`).
   No guest row was captured; only pursue if the registrar exposes a sanctioned public search separate from
   ULink login.

**Batch status:** two new bespoke identities (UH Mānoa and Kent State) plus one documented KU revisit and
one Louisville login-gated lead were archived. No numeric values were inferred for the non-KU entries, and
no `schools.py` edit, registry change, deployment, or builder handoff was made.

### Codex Batch 27 — Other public pathways (July 12 2026)

This pass moved beyond the previously exhausted shared-host sweep and checked institution-specific public
Banner/WINGS surfaces. These are source-level leads only; no adapter or builder handoff is implied.

1. **North Carolina A&T State University (NC) — PUBLIC BANNER NUMERIC LEAD, FOLLOW-UP REQUIRED.** The
   official visiting/non-degree guide links a public Class Schedule and says class detail pages show
   capacity and available seats (`https://ncat.edu/academics/summer-sessions/visiting-students.php`).
   The linked Dynamic Schedule is live at
   `https://ssbprod-ncat.uncecs.edu/pls/NCATPROD/bwckschd.p_disp_dyn_sched`; its selector includes Fall
   2026 and completed Spring 2026. Official detail pages expose labeled Capacity, Actual, and Remaining
   fields (for example, `https://ssbprod-ncat.uncecs.edu/pls/NCATPROD/bwckschd.p_disp_detail_sched?crn_in=10884&term_in=202210`
   shows 100/97/3; historical rows also include full and over-cap values). No current Fall 2026 course
   row was captured in this pass, so do not infer live seats. Follow up with exact Fall 2026 Biology or
   English CRNs plus a completed-term mixed test, preserving CRN, term, campus, restrictions, waitlist,
   and over-cap rows. Name dedup is clean.
2. **Wright State University (OH) — PUBLIC WINGS/BANNER NUMERIC LEAD, FOLLOW-UP REQUIRED.** Wright’s
   public Class Schedule is at `https://wingsexpress.wright.edu/pls/PROD/bwckschd.p_disp_dyn_sched` and
   explicitly supports searching current course offerings. Current Fall 2026 detail rows expose labeled
   Capacity/Actual/Remaining fields, e.g. Social Work Field Education II (CRN 80757) at
   `https://wingsexpress.wright.edu/pls/PROD/bwckschd.p_disp_detail_sched?crn_in=80757&term_in=202680`
   shows 15/15/0, while the same public surface exposes historical Spring 2026 rows with positive seats
   (CRN 14291 shows 60/53/7) and an over-cap example (CRN 27689 shows 27/32/-5). Preserve campus,
   part-of-term, restrictions, waitlist, cross-list, and negative-Remaining semantics; verify a current
   Fall 2026 mixed set through a direct schedule replay before production work. Name dedup is clean.

**Batch status:** two net-new public numeric pathways were archived. NC A&T still needs current Fall 2026
row capture; Wright State has both current and completed-term evidence but still needs replay/freshness and
eligibility tests. No `schools.py` edit, registry change, deployment, or builder handoff was made.

### Codex Batch 28 — Public Colleague pathways (July 12 2026)

This pass moved to public California community-college Colleague surfaces. Both identities are dedup-clean
and remain source-level until current-term replay, completed-term comparison, and eligibility semantics are
verified.

1. **West Valley College (CA) — PUBLIC COLLEAGUE NUMERIC LEAD, FOLLOW-UP REQUIRED.** The official
   instructions explicitly link a no-login searchable class schedule
   (`https://www.westvalley.edu/classes/search.html`), and the district’s public search surface is
   `https://schedule.wvm.edu/`. The underlying public Banner/Colleague detail host exposes labeled
   Capacity/Actual/Remaining fields; a historical West Valley row (Fall 2023 CRN 73036) shows 25/15/10
   at `https://ssb-prod.wvm.elluciancloud.com/PROD/bwckschd.p_disp_detail_sched?crn_in=73036&term_in=202370`.
   The official site publishes a Fall 2026 searchable schedule, but no current Fall 2026 numeric row was
   captured here. Follow up by selecting West Valley (not Mission), replaying Fall 2026 and a completed
   term, and preserving campus, restrictions, waitlist, cross-list, and over-cap semantics.
2. **Victor Valley College (CA) — PUBLIC COLLEAGUE GUEST-SURFACE LEAD, FOLLOW-UP REQUIRED.** VVC’s
   official registration page says Fall 2026 offerings can be viewed before applying through its public
   Self-Service search (`https://www.vvc.edu/register`; guest surface:
   `https://vvc-ss.colleague.elluciancloud.com/Student/Courses`). The guest page is reachable without
   login and exposes course/section search, but this pass returned no populated subject rows. Do not infer
   seats; capture Fall 2026 rows and a completed term, then confirm that Seats Available, waitlist, term,
   campus, and restriction fields are stable before adapter work.

**Batch status:** two net-new public Colleague identities were archived. West Valley has historical
numeric proof plus a current public schedule route; Victor Valley is a reachable guest catalog/search lead
without current numeric rows. No `schools.py` edit, registry change, deployment, or builder handoff was made.

### Codex Batch 29 — CSU public-search verification (July 12 2026)

This pass checked CSU campuses advertising current public class searches. One surface exposes a clear
public numeric schema; two advertised public routes currently redirect to SSO and are preserved only as
login-gated leads.

1. **California State University, San Bernardino (CA) — PUBLIC NUMERIC CLASS-SCHEDULE LEAD, FOLLOW-UP
   REQUIRED.** The official schedule at `https://www.csusb.edu/class-schedule` exposes term and campus
   filters, an Open Classes Only option, and explicit numeric formulas for Seats available (capacity minus
   enrollment) and waitlist spots. It also exposes San Bernardino and Palm Desert campus fields and a
   seats-available sort. The page is a live client-rendered source, so capture Fall 2026 rows and a
   completed term through the underlying request before adapter work; preserve campus, session, waitlist,
   restrictions, and zero/negative edge cases. No row values were inferred in this pass.
2. **California State University, Monterey Bay (CA) — ADVERTISED PUBLIC SEARCH, CURRENTLY SSO-GATED.
   FOLLOW-UP REQUIRED.** The official class-schedule page says its search supports term/subject filters and
   finding open classes (`https://csumb.edu/departments/academic-planning/academic-centralized-scheduling/class-schedule/`),
   while the official class-details guide defines Class Capacity, Enrollment Total, Available Seats,
   Waitlist Capacity, and Waitlist Total (`https://csumb.edu/oasis/class-details/`). The linked search
   currently redirects to OASIS/Okta sign-in, so no guest rows or seats were captured. Do not treat this as
   a public adapter until a sanctioned no-login route is confirmed.
3. **California State University, Dominguez Hills (CA) — ADVERTISED PUBLIC SEARCH, CURRENTLY SSO-GATED.
   FOLLOW-UP REQUIRED.** CSUDH’s official class-schedule page states Fall 2026 is published and says My
   Class Search requires no login (`https://www.csudh.edu/class-schedule/`); its Open University guide
   likewise directs users to a no-login Fall 2026 search. The linked My Class Search currently redirects
   to the CSUDH authentication service, so no numeric rows were captured. Preserve this discrepancy and
   only proceed if a registrar-sanctioned guest endpoint can be replayed.

**Batch status:** one net-new CSU public numeric schema and two net-new CSU login-gated leads were archived.
No current seat values were inferred for the client-rendered or SSO surfaces. No `schools.py` edit, registry
change, deployment, or builder handoff was made.

### Codex Batch 30 — Additional public schedule paths (July 12 2026)

1. **Santa Monica College (CA) — PUBLIC SCHEDULE/OPEN-SEAT WORKFLOW LEAD, FOLLOW-UP REQUIRED.** SMC’s
   official Fall 2026 schedule is published at `https://www.smc.edu/academics/classes/2026-27/fall-2026/general-information.php`
   (PDF: `https://www.smc.edu/academics/classes/2026-27/fall-2026/documents/263-SMCschedule.pdf`). The
   registrar documents an Open Seat Notification and waitlist workflow, and directs students to the online
   schedule at `smc.edu/schedules`; the schedule is current for Fall 2026. No guest numeric row was
   captured in this pass, so do not infer seats. Follow up with a no-login section query if available and
   preserve open-seat notifications, waitlist, campus, modality, and authorization-code semantics.
2. **Truman State University (MO) — PUBLIC SCHEDULE + REAL-TIME COURSE-LIST LEAD, FOLLOW-UP REQUIRED.**
   Truman publishes the Fall 2026 schedule of classes (`https://www.truman.edu/majors-programs/academic-resources/schedule-of-classes/`;
   PDF: `https://www.truman.edu/wp-content/uploads/2026/03/ClassSchedule-Fall2026.pdf`). Its registrar
   says the current course list is real-time and searchable by course, part of term, attribute, and time
   (`https://www.truman.edu/registrar/registration/open-courses/`), while the public PDF documents Fall
   2026 waitlist/add-drop behavior. The real-time list appears to require TruView access; no numeric guest
   rows were captured. Treat as a login-gated lead until a sanctioned public search or export is found.

**Batch status:** two net-new U.S. schedule identities were archived. Neither received inferred seat values
or production approval. No `schools.py` edit, registry change, deployment, or builder handoff was made.

### Codex Batch 31 — Montana public schedule pathway (July 12 2026)

1. **Montana State University–Bozeman (MT) — PUBLIC SCHEDULE/OPEN-SEAT LEAD, FOLLOW-UP REQUIRED.** The
   official registrar schedule page (`https://www.montana.edu/registrar/ScheduleofClasses.html`) directs
   users to select term and subject and recommends an “Only Sections with Open Seats” filter. It separately
   documents Bozeman, Gallatin College, CORE, and online searches, with CRNs used for registration. The
   page does not expose a captured numeric row in this pass, so no seats are inferred. Follow up through
   the linked schedule for Fall 2026 and a completed term, isolating Bozeman from Gallatin/online sections
   and preserving open-seat, waitlist, campus, and part-of-term semantics.

**Batch status:** one net-new public schedule identity was archived as a gated lead. No `schools.py` edit,
registry change, deployment, or builder handoff was made.

### Codex Batch 32 — SDSU public schedule pathway (July 12 2026)

1. **San Diego State University (CA) — PUBLIC CLASS-SCHEDULE/OPEN-UNIVERSITY LEAD, FOLLOW-UP REQUIRED.**
   SDSU Global Campus instructs non-degree/Open University users to browse the Fall 2026 public schedule,
   filter by San Diego Campus and class status (open, waitlist, or closed), and inspect each section’s
   number of seats (`https://globalcampus.sdsu.edu/open-university-registration/`). SDSU’s my.SDSU guide
   confirms the public schedule is viewable without login and that the Class Availability tab exposes
   seat counts (`https://my.sdsu.edu/guides/search-class-schedule`; public schedule instructions:
   `https://my.sdsu.edu/guides/public-schedule`). No current guest row was captured in this pass. Follow
   up with a direct Fall 2026 public export and completed-term replay, isolating San Diego Campus from
   Global Campus/Imperial Valley and preserving reserved seats, waitlist, prerequisites, and permission
   semantics.

**Batch status:** one net-new public schedule identity was archived. Numeric current-term replay and
eligibility checks remain outstanding. No `schools.py` edit, registry change, deployment, or builder handoff
was made.

### Codex Batch 33 — UVM public course pages (July 12 2026)

1. **University of Vermont (VT) — PUBLIC CURRENT COURSE/SEAT-STATUS LEAD, FOLLOW-UP REQUIRED.** UVM
   Professional and Continuing Education publishes no-login Fall 2026 section pages with CRNs, dates,
   instructors, modality, prerequisites/permission notes, and an explicit live status banner. The official
   course index (`https://learn.uvm.edu/courses/fall/`) currently mixes sections labeled “Only N seats
   available, register soon!” with sections labeled “This section is full - join waitlist”; individual
   pages are refreshed within hours (for example PEAC 1188 B, CRN 90253:
   `https://learn.uvm.edu/course/202609/90253/fall-2026/physical-education/scuba/`). A separate UVM
   registrar waitlist guide documents that apparent open seats may be reserved for waitlisted students
   (`https://www.uvm.edu/registrar/waitlisting-pilot-information-students`). This is a public PACE/non-degree
   surface rather than proof of the entire undergraduate catalog: capture the underlying course-list request,
   exact numeric seat fields, a full/waitlist row, and a completed term before adapter work, and preserve
   PACE eligibility, prerequisites, permission, waitlist, and cross-list semantics.

**Batch status:** one net-new U.S. college identity was archived as a current public status lead. No
numeric value was inferred from the status banner, and no `schools.py` edit, registry change, deployment,
or builder handoff was made.

### Codex Batch 34 — Additional public/registrar schedule leads (July 12 2026)

1. **Eastern Kentucky University (KY) — PUBLIC REGIONAL-SCHEDULE LEAD, FOLLOW-UP REQUIRED.** EKU’s
   official Fall 2026 Corbin regional-campus schedule PDF exposes CRN, course/section, meeting dates,
   campus, room capacity (`Cap`), and enrollment (`Enr`) fields (for example, MAT 105 CRN 11495 is
   Cap 12 / Enr 1): `https://www.eku.edu/wp-content/uploads/2026/04/Fall-2026-Corbin-Master-Schedule-4.7.26-NCCRN.pdf`.
   EKU’s registrar guide documents an `Open Sections Only` class-search option, but the main search is
   login-gated. Treat the PDF as Corbin-only evidence; capture a main-campus guest route, explicit
   available-seat/status fields, a full/waitlisted row, and a completed term before adapter work.
2. **College of Saint Benedict (MN) — PUBLIC SHARED COURSE-SEARCH LEAD, FOLLOW-UP REQUIRED.** The
   official CSB+SJU course-schedule page says the new no-login Class Search tool supports Fall 2026,
   campus selection (CSB, SJU, web, embedded, study abroad), and an “open sections” filter:
   `https://catalog.csbsju.edu/registration/course-schedule/`. The shared Banner registration hosts are
   `https://registration.csbsju.edu/StudentRegistrationSsb/ssb/registration/?mepCode=B` and the public
   search page is `https://catalog.csbsju.edu/course-search/`. No numeric guest rows were captured here;
   preserve CSB campus identity, reserved-seat groups, waitlists, prerequisites, and cross-registration.
3. **Saint John’s University (MN) — PUBLIC SHARED COURSE-SEARCH LEAD, FOLLOW-UP REQUIRED.** Saint John’s
   uses the same official CSB+SJU Fall 2026 public search and Banner host, with campus code `J`:
   `https://registration.csbsju.edu/StudentRegistrationSsb/ssb/registration/?mepCode=J`. The registrar
   explicitly states that faculty/staff/public users can Browse for Classes and filter to open sections
   (`https://catalog.csbsju.edu/registration/instructions/`). No guest numeric rows were captured; follow
   up by isolating campus `J` from CSB, web, and embedded sections and testing a completed term.
4. **Scripps College (CA) — PUBLIC CONSORTIUM-SEARCH LEAD, FOLLOW-UP REQUIRED.** Scripps’ official
   portal states that Fall 2026 course schedules are visible and that visitors may use the Public Course
   Search on the Claremont McKenna portal (`https://mycampus.scrippscollege.edu/ICS/Portal_Homepage.jnz`).
   The registrar’s calendar confirms Fall 2026 schedule visibility from April 6
   (`https://www.scrippscollege.edu/registrar/academic-calendar`). The CMC public-search endpoint was not
   captured in this pass, so no seats/status are inferred; follow up with the sanctioned public search,
   preserving Scripps/5C campus and cross-registration semantics.
5. **Colorado College (CO) — PUBLIC CATALOG/SCHEDULE LEAD, FOLLOW-UP REQUIRED.** The official registrar
   states that non-campus members may view course schedules through the public Catalog of Courses and
   documents Fall 2026 registration/add-drop deadlines (`https://www.coloradocollege.edu/offices/registrar/course-schedule.html`).
   The linked catalog returned HTTP 403 to this pass, so no rows or seat values are inferred. Follow up
   through the sanctioned catalog/search route and capture current open/full/waitlist status, a completed
   block/term, and block-plan semantics before adapter work.

**Batch status:** five net-new U.S. college identities were archived with bounded scope. No production
seat claims were made for any entry. No
`schools.py` edit, registry change, deployment, or builder handoff was made.

### Codex Batch 35 — Claremont consortium and adjacent public schedule leads (July 12 2026)

1. **Claremont McKenna College (CA) — PUBLIC NUMERIC COURSE-SEARCH LEAD, FOLLOW-UP REQUIRED.** CMC
   operates an official no-login course-search form at `https://webapps.cmc.edu/course-search/form.php`.
   The live form exposes term, course-area, faculty, and section-status filters and reports a data-refresh
   timestamp; CMC’s registrar says section details include seats available and that closed/restricted
   sections can require a PERM (`https://www.cmc.edu/registrar/adding-courses-on-portal`). Capture Fall
   2026 rows and a completed term from the public form, preserving CMC identity versus other 5C campuses,
   restrictions, cross-registration, and waitlist/closed semantics before adapter work.
2. **Pomona College (CA) — PORTAL SCHEDULE LEAD, FOLLOW-UP REQUIRED.** Pomona’s registrar says the Fall
   2026 schedule published to the portal April 6 and uses Coursedog for section scheduling
   (`https://www.pomona.edu/administration/registrar/course-scheduling-information-academic-departments`).
   The registration page states that My.Pomona is the authoritative schedule and that closed courses may
   require a PERM (`https://www.pomona.edu/administration/registrar/registration`). No guest numeric rows
   were captured; determine whether a sanctioned public/5C search is available, then replay Fall 2026 and
   a completed term with Pomona campus and enrollment-limit restrictions intact.
3. **Harvey Mudd College (CA) — 5C SCHEDULE LEAD, FOLLOW-UP REQUIRED.** HMC’s official registrar calendar
   confirms Fall 2026 dates and explicitly identifies the shared HMC/CMC/Pitzer course end date while
   distinguishing Pomona/Scripps (`https://www.hmc.edu/registrar/academic-calendar/`). No public numeric
   HMC row was captured; follow up through the sanctioned CMC/5C search, isolate HMC sections, and verify
   capacity, enrollment, waitlist, cross-registration, and a completed term before adapter work.
4. **Pitzer College (CA) — PORTAL SCHEDULE LEAD, FOLLOW-UP REQUIRED.** Pitzer’s registrar event states
   that the Fall 2026 course schedule became available on the MyCampus2 portal April 6
   (`https://www.pitzer.edu/events/fall-2026-course-schedule-available-portal`). No guest numeric rows
   were captured; test the sanctioned 5C/public search if available, isolating Pitzer from consortium
   sections and preserving restrictions, cross-registration, waitlist, and term semantics.
5. **Occidental College (CA) — PUBLIC COURSE-COUNTS/OPEN-SEAT WORKFLOW LEAD, FOLLOW-UP REQUIRED.** Oxy’s
   official first-year registration guide directs users to the public Course Counts surface, choose Fall
   2026 and First Year Seminars, and record four-digit CRNs; it says students should keep checking when a
   course is full and switch if needed (`https://www.oxy.edu/new-students/new-student-guide/advising-course-registration/fys-registration`,
   public link `https://counts.oxy.edu`). Confirm whether Course Counts exposes numeric seats/status without
   login, capture mixed open/full rows and a completed term, and preserve the FYS-only scope and Oxy CRNs.

**Batch status:** five net-new U.S. college identities were archived. CMC and Occidental have explicit
public search/workflow routes; Pomona, HMC, and Pitzer are portal/5C leads with no inferred numeric seats.
All five were deduped against `schools.py` and prior research. No production approval, `schools.py` edit,
registry change, deployment, or builder handoff was made.

### Codex Batch 39 — Northern Plains and Missouri public schedule leads (July 12 2026)

1. **North Dakota State University (ND) — CAMPUS-CONNECTION SCHEDULE LEAD, FOLLOW-UP REQUIRED.** NDSU’s
   official registration guidance documents Fall 2026 term code `2710`, the Class Search path in Campus
   Connection, and career/session definitions (`https://www.ndsu.edu/registrar/facstaff/cchelp/navigations`).
   The search is portal-authenticated in the documented workflow, so no seats are inferred. Confirm whether a
   sanctioned guest route exists, then replay Fall 2026 and a completed term with Fargo campus, career,
   session, cross-registration, waitlist, and permission semantics preserved.
2. **University of North Dakota (ND) — CAMPUS-CONNECTION CLASS-SEARCH LEAD, FOLLOW-UP REQUIRED.** UND’s
   official registration guide directs users to Campus Connection Class Search and an “Open Classes Only”
   option, with Fall 2026 dates published at `https://und.edu/academics/services/advising/course-registration.html`.
   The workflow requires login; no numeric guest rows were captured. Verify any sanctioned public listing,
   then preserve Grand Forks/online/law career, part-of-term, waitlist, and restriction fields.
3. **University of Nebraska at Kearney (NE) — MYBLUE SCHEDULE/COURSE-SEARCH LEAD, FOLLOW-UP REQUIRED.**
   UNK’s registrar says Fall 2026 schedules became available February 23 and directs students to MyBLUE/UNK
   Class Search (`https://www.unk.edu/offices/registrar/academic_policies_handbook/Academic_Calendar.php`,
   `https://www.unk.edu/offices/registrar/academic_policies_handbook/Class_Schedules.php`). The public-facing
   course-search documentation exposes Fall 2026 filters, but the authoritative schedule appears account-based;
   no seats were inferred. Confirm guest access and replay a completed term with Kearney, mini-session, online,
   and permission semantics intact.
4. **University of Nebraska–Lincoln (NE) — MYRED CLASS-SEARCH LEAD, FOLLOW-UP REQUIRED.** UNL publishes
   Fall 2026 term `1268` and registration dates, while its official registration guide directs users to MyRED
   “Search for Classes,” including Open Classes and mode-of-instruction filters
   (`https://registrar.unl.edu/student-resources/registration/fall-registration-dates/`,
   `https://admissions.unl.edu/information-for/nebraska-now/getting-started/`). No guest numeric row was
   captured. Verify whether a public sanctioned search exists, then preserve Lincoln campus, career, attributes,
   reserve/waitlist, and Nebraska Now/non-degree scope.
5. **University of Missouri (MO) — PUBLIC CURRENT-CLASS-OFFERINGS LEAD, FOLLOW-UP REQUIRED.** Mizzou’s
   registrar explicitly states that its Current Class Offerings link does not require login and directs users
   to the myZou class search (`https://registrar.missouri.edu/registration-classes/current-class-offerings/`).
   The page documents current term operation but this pass captured no populated Fall 2026 row. Replay Fall
   2026 and a completed term, preserving Columbia campus, career, session, online, cross-enrollment, waitlist,
   and permission semantics.

**Batch status:** five net-new U.S. college identities were archived. Missouri has an explicit no-login class-
offerings route; NDSU, UND, UNK, and UNL require guest-route confirmation. No seats were inferred. All five
were deduped against `schools.py` and prior research. No production approval, `schools.py` edit, registry
change, deployment, or builder handoff was made.

### Codex Batch 37 — Southwest public class-search pathways (July 12 2026)

1. **University of Nevada, Las Vegas (NV) — PUBLIC PEOPLESOFT CLASS-SEARCH LEAD, FOLLOW-UP REQUIRED.**
   UNLV exposes a guest Class Search at `https://my.unlv.nevada.edu/psc/lvporprd/EMPLOYEE/SA/c/COMMUNITY_ACCESS.CLASS_SEARCH.GBL`
   with institution/term selectors, subject/course-number filters, and “Show Open Classes Only.” The official
   search surface includes Fall 2026 as a selectable term, but no populated row was captured here. Replay a
   current and completed term, confirm numeric seats/status, and preserve UNLV campus, career, reserve,
   waitlist, and restriction semantics.
2. **University of Nevada, Reno (NV) — PUBLIC PEOPLESOFT CLASS-SEARCH LEAD, FOLLOW-UP REQUIRED.** UNR’s
   official guest Class Search is `https://cs.nevada.unr.edu/psc/unrcsprd/EMPLOYEE/SA/c/SA_LEARNER_SERVICES.CLASS_SEARCH.GBL`.
   The public page exposes term/subject/course filters; current Fall 2026 row and seat-field capture were not
   completed. Verify whether the guest response includes capacity, enrollment, available seats, and waitlist,
   then replay a completed term and keep Reno separate from Nevada Online/non-degree surfaces.
3. **New Mexico State University (NM) — PUBLIC BANNER COURSE-LOOKUP LEAD, FOLLOW-UP REQUIRED.** NMSU’s
   official Course Schedules page links a public “Look Up Classes” service (`https://www.nmsu.edu/course/`),
   and the Banner public term-selection endpoint is `https://banner-public.nmsu.edu/StudentRegistrationSsb/ssb/term/termSelection?mode=courseSearch`.
   NMSU documents Fall 2026 dates and warns that Global Campus sections are reserved for that program. Capture
   Fall 2026 and a completed term, isolating Las Cruces from Alamogordo/Carlsbad/Doña Ana/Grants and Global,
   and preserve reserved seats, waitlists, and campus codes.
4. **University of Colorado Denver (CO) — CLASS-SEARCH/AVAILABILITY LEAD, FOLLOW-UP REQUIRED.** CU Denver’s
   registrar directs users to its Class Search tool to find available classes (`https://www.ucdenver.edu/student/registration/register-for-classes/register/class-search`).
   The page also distinguishes non-degree registration and student-portal registration; no public numeric row
   was captured. Confirm whether a guest route exists, then capture current/completed terms with Downtown,
   Anschutz, online, career, reserve, and waitlist distinctions intact.
5. **Boise State University (ID) — MYBOISESTATE CLASS-SEARCH LEAD, FOLLOW-UP REQUIRED.** Boise State’s
   official Fall 2026 service-learning course page lists current sections and directs users to the Class Search
   in my.boisestate.edu for authoritative details (`https://www.boisestate.edu/servicelearning/sl-courses/`).
   The linked search appears portal-gated in this pass, so no seats are inferred. Confirm a sanctioned guest
   endpoint, then replay Fall 2026 and a completed term while preserving Boise/main-campus, regional, online,
   permission, reserve, and waitlist semantics.

**Batch status:** five net-new U.S. college identities were archived. UNLV, UNR, and NMSU expose public
class-search/lookup routes; CU Denver and Boise State require guest-route confirmation. No seats were inferred.
All five were deduped against `schools.py` and prior research. No production approval, `schools.py` edit,
registry change, deployment, or builder handoff was made.

### RCCD×3 hold RE-VERIFIED LIVE — still NO Fall term (July 13 2026, Build)

Live check through the real SharePoint REST API (`apps-studentrcc.msappproxy.net/schedule`, which
fronts `apps.rccd.edu` — visible in pagination nextLinks): `ScheduleTermOptions` currently offers ONLY
Winter 2026 (`26WIN`) and Summer 2026 (`26SUM`). `Term eq '26FAL'` returns ZERO rows on all three lists
(ScheduleData_MOV/NOR/RIV); `26SUM` has data on all three. Codex's July 11 claim of 1,004/1,054/2,330
Fall sections does NOT reproduce today — either the district purged/reloaded Fall or the claim was wrong.
Grabber's parting "Fall data rolled out" meant rolled OUT OF the feed, not arrived. **HOLD STANDS** — do
not build on 26SUM (in-progress term, Last-Day-to-Add date rule will mark nearly everything not-open;
useless for Fall-registration alerts). Adapter mechanics fully captured for when Fall lands, from the
official app's own `main.js`: PnPjs → REST `GET /schedule/_api/web/lists/getByTitle('ScheduleData_{MOV|NOR|RIV}')/items?$filter=Term eq '<term>' [and College eq '<name>']&$select=...&$top=5080`
(Accept: `application/json;odata=nometadata`). Fields: `Title` (course), `Section_x0020_ID` (unique key),
`Section_x0020_Number`, `Primary_x0020_Subject`, `College`, `Total_x0020_Seats`, `Seats_x0020_Used`,
`Last_x0020_Day_x0020_to_x0020_Ad` (sic, truncated internal name), `Start_x0020_Date_x0020_1`. Official
open rule (extracted verbatim from main.js): `isOpen = Total_Seats>0 && !(Seats_Used>=Total_Seats) &&
(LastDayToAdd!==undefined ? now<=LastDayToAdd : now<=StartDate1)`; separately `openSeatStatusUnknown =
!(Total_Seats>0)` — UNKNOWN MUST MAP TO NOT-OPEN in any adapter. Correction for the ledger: prior handoff
line "adapter ready" was wrong — NO RCCD adapter exists in schools.py or any branch/stash; it must be
built fresh when Fall data lands. Re-check cadence: query ScheduleTermOptions for a `26FAL` row; build
only after it appears AND returns mixed open/full rows. No schools.py edit, no registry change, no deploy.

### Codex Batch 40 — Virginia/Wisconsin/UMBC public schedule leads (July 12 2026)

1. **James Madison University (VA) — PUBLIC CLASS-SEARCH/PORTAL LEAD, FOLLOW-UP REQUIRED.** JMU’s official online-course guide directs users to a public Class Search tool and term/subject filters (`https://www.jmu.edu/online/class-search.shtml`); the registrar’s Fall 2026 enrollment page documents when that schedule is released (`https://www.jmu.edu/registrar/students/enrollment/fall.shtml`). Capture a sanctioned public row if available, otherwise mark portal-gated; preserve Harrisonburg/online, career, waitlist, and completed-term semantics.
2. **University of Richmond (VA) — FALL 2026 SCHEDULE/WAITLIST LEAD, FOLLOW-UP REQUIRED.** The official registrar calendar (`https://registrar.richmond.edu/_common/PDF/6_3-Academic-Calendars/Fall-2026.pdf`) confirms Fall 2026 registration, add/drop, and wait-list deadlines; the School of Professional & Continuing Studies site (`https://spcs.richmond.edu/`) is an official schedule/program surface. No public numeric row was captured; confirm main/continuing/graduate/online scope and replay current/completed terms.
3. **George Mason University (VA) — PATRIOTWEB SCHEDULE LEAD, FOLLOW-UP REQUIRED.** The official Fall 2026 registrar calendar (`https://registrar.gmu.edu/calendars-2/fall_2026/`) confirms registration timing and schedule availability through Mason’s student systems. No guest numeric row was captured; verify any sanctioned public browse-classes endpoint, preserving Fairfax/Arlington/online campus and career/restriction/waitlist semantics.
4. **University of Wisconsin–Madison (WI) — PUBLIC COURSE-SEARCH LEAD, FOLLOW-UP REQUIRED.** UW–Madison’s registrar explicitly links a General Public Access Course Search & Enroll surface (`https://registrar.wisc.edu/course-search-enroll/`) that browses sections by term; its enrollment-appointment documentation covers Fall 2026 schedule timing (`https://registrar.wisc.edu/enrollment-appointment-times/`). Capture numeric availability if exposed, replay a completed term, and preserve session, eligibility, and waitlist semantics.
5. **University of Maryland, Baltimore County (MD) — PROFESSIONAL-PROGRAM SCHEDULE LEAD, FOLLOW-UP REQUIRED.** UMBC’s official professional-program schedule page (`https://professionalprograms.umbc.edu/college-teaching-and-learning-science/schedule-of-classes/`) publishes Fall 2026 dates, course-schedule publication, and non-degree registration; the registrar’s academic calendar (`https://registrar.umbc.edu/wp-content/uploads/sites/31/2026/02/Fall-26-UGRD-Academic-Calendar.pdf`) documents undergraduate schedule/waitlist dates. Scope is professional programs/registrar only until a main guest search is verified; no seats inferred.

**Batch status:** five net-new identities archived; JMU and UW–Madison have public-search evidence, while Richmond, GMU, and UMBC remain schedule/portal leads. No seats were inferred, and no production approval was made.

### Codex Batch 41 — Southeast/Front Range schedule and class-search leads (July 12 2026)

1. **The University of Alabama (AL) — MYBAMA CLASS-SEARCH LEAD, FOLLOW-UP REQUIRED.** UA’s official registrar registration guide (`https://registrar.ua.edu/student-services/registration/`) documents Summer/Fall 2026 registration and the Register for Classes search, including section status and waitlist actions. The workflow is myBama-authenticated; no guest numeric row was captured. Verify a sanctioned public route or retain as portal-gated, preserving Tuscaloosa campus, career, restrictions, waitlist, and completed-term semantics.
2. **University of Colorado Colorado Springs (CO) — MYUCCS CLASS-SEARCH LEAD, FOLLOW-UP REQUIRED.** UCCS’s registrar publishes Fall 2026 deadlines (`https://registrar.uccs.edu/course-deadlines/fall-2026-deadlines`), while the university’s registration guidance places class search in myUCCS. No numeric guest row was captured; verify any public course-search surface and preserve Colorado Springs campus, online, career, waitlist, and session fields.
3. **East Carolina University (NC) — PUBLIC REGISTRAR SEARCH LEAD, SCOPE CHECK REQUIRED.** An official ECU department schedule page (`https://foreign.ecu.edu/courses/`) directs users to the ECU Registrar Course Search, with term and subject-prefix filtering and Fall 2026 course flyers. This pass verified only a departmental surface, not the complete ECU catalog or seat fields; confirm main-campus scope and replay a completed term before adapter consideration.
4. **Stetson University (FL) — CLASS-SCHEDULE/WAITLIST LEAD, FOLLOW-UP REQUIRED.** Stetson’s official registrar resources (`https://www.stetson.edu/administration/registrar/resources.php`) link the Class Schedule Search and document that the `WL Act` column exposes waitlist counts, while registration restrictions also apply to waitlists. The search is in Stetson’s registration dashboard; no numeric guest row was captured. Verify public access and preserve DeLand/Gulfport, career, restrictions, and waitlist semantics.
5. **The George Washington University (DC/VA) — PUBLIC SCHEDULE-OF-CLASSES LEAD, FOLLOW-UP REQUIRED.** GW’s official registrar schedule (`https://my.gwu.edu/mod/pws/`) exposes Fall 2026 categories for Main, Mount Vernon, Virginia Science & Technology, off-campus, and online courses. No seat counts were inferred; verify whether the linked course search returns capacity/status, isolate campuses and careers, and replay a completed term.

**Batch status:** five net-new identities archived. GW’s public schedule has explicit Fall 2026 campus/online partitions; ECU is currently a departmental public-search lead, and Alabama, UCCS, and Stetson require guest-route confirmation. No seats were inferred, and no production approval was made.

### Codex Batch 42 — Great Lakes/Mid-Atlantic registrar schedule leads (July 12 2026)

1. **Central Michigan University (MI) — COURSE-SEARCH/REGISTRATION LEAD, FOLLOW-UP REQUIRED.** CMU’s official registrar calendar (`https://www.cmich.edu/offices-departments/registrars-office/calendars/academic-calendar`) records Fall 2026 registration and directs users to Course Search and Registration. No public numeric row was captured; verify any sanctioned guest route, preserving Mount Pleasant/online scope, career, restrictions, waitlist, and completed-term semantics.
2. **Northern Michigan University (MI) — GLOBAL-CAMPUS ONLINE SEARCH LEAD, SCOPE REQUIRED.** NMU’s official Global Campus course search (`https://nmu.edu/online/course-search`) exposes Fall 2026 online-asynchronous, synchronous, hybrid, and off-campus filters, but explicitly warns that real-time seat availability must be confirmed in MyNMU. Treat this as online/global-campus only until the main catalog search is verified; no seats inferred.
3. **PennWest University (PA) — SELF-SERVICE SCHEDULE LEAD, FOLLOW-UP REQUIRED.** PennWest’s registrar (`https://www.pennwest.edu/about/offices-services/registrar/courses-registration/index.php`) says Summer/Fall 2026 schedules are available in Student Self-Service and directs students to browse courses there. No guest numeric row was captured; verify public access and preserve Clarion/Edinboro/California campus identity, online sections, career, restrictions, and waitlist fields.
4. **University of Hartford (CT) — COURSE-SEARCH/SCHEDULE LEAD, FOLLOW-UP REQUIRED.** Hartford’s registrar registration page (`https://www.hartford.edu/about/offices-divisions/office-registrar/registration/`) links Course Search and Schedule of Classes and documents Fall 2026 registration timing. No seat fields were captured; verify any public search response, preserve Hartford campus, undergraduate/graduate career, cross-listing, restrictions, and completed-term replay.
5. **University of Michigan–Ann Arbor (MI) — PUBLIC SCHEDULE/WOLVERINE ACCESS LEAD, FOLLOW-UP REQUIRED.** The registrar’s curriculum page (`https://ro.umich.edu/faculty-staff/curriculum`) documents Fall 2026 availability of the online PDF Schedule of Classes and Wolverine Access Class Search beginning March 6. This is distinct from the already-built University of Michigan–Flint entry; no seat counts were inferred. Verify Ann Arbor campus and public search semantics before any adapter work.

**Batch status:** five net-new identities archived. UMich has explicit public schedule/class-search publication timing; NMU is intentionally limited to Global Campus online search, while CMU, PennWest, and Hartford require guest-route confirmation. No seats were inferred, and no production approval was made.
