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
- **Winston-Salem State University (NC) — SOURCE-GATED, adapter needed (Codex, July 11 2026).**
  Official public schedule is `https://ssbprod-wssu.uncecs.edu/pls/WSSUPROD/bwckschd.p_disp_dyn_sched`;
  Fall 2026 is term `202680` and completed Spring 2026 is `202620` (View only). The public catalog
  route `bwckctlg.p_disp_listcrse` exposes Biology listings, while detail pages expose labeled numeric
  `Capacity`, `Actual`, and `Remaining`, plus stable CRN and exact section title. Fall Biology exposed
  73 unique CRNs and Spring 69. Exact `BIO 1113` had six Fall sections: two positive remaining (1 and
  5) and four full; Spring had five sections: three positive (1, 2, and 11) and two full. On all
  sampled detail rows, `Remaining == Capacity - Actual`. A future adapter must scope exact term,
  subject, course, and sequence/CRN, require `Remaining > 0`, and preserve restriction/waitlist
  notes. Official Fall 2025 student data reports 4,972 total students. Net-new public four-year
  candidate; production Listcrse/Banner integration is untested, so do not hand off yet.
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
