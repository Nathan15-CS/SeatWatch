# Lane status — Codex Sol 5.6 (research agent B)

**Only Codex writes this file. Fable reads it but never edits it.**
Codex: claim your vein here BEFORE you start probing, then commit + push. Update when you start/finish.

## NOW (active claims — Fable will not touch these)
- **CLAIMED July 11, 2026: production newer-Colleague gate + fresh official-public-schedule discovery.**
  Production `NewColleague` fetches now pass for Lebanon Valley, Augustana, Camden County, and Walsh;
  their complete handoff blocks are in README under `AWAITING GO-AHEAD`. Fairfield remains conditional
  on a bespoke adapter; UC Davis and Johns Hopkins are blocked. A new SDCCD public JSON feed yielded
  three source-gated colleges (City, Mesa, Miramar), pending a production adapter. I am continuing
  registrar-linked public schedule discovery outside the exhausted Banner/Colleague hostname veins;
  Berkeley's public class-search detail pages are the latest validated lead, with reserved-seat-aware
  gating still pending a production adapter. UNC Asheville's official React schedule API is another
  fresh source-gated lead, with exact numeric seat arithmetic validated across current and completed
  terms. NCCU's public Banner detail pages are a third fresh lead, with labeled Capacity/Actual/
  Remaining fields and completed-term mixed results. UNC Greensboro's current Banner SSB API is a
  fourth fresh lead, with explicit seat counts and waitlist-only edge cases documented.
  Winston-Salem State University's public Banner catalog is a fifth fresh lead, with exact
  Capacity/Actual/Remaining detail fields and mixed current/completed-term samples.
  Worcester State University's public newer-Colleague catalog is a sixth fresh lead, and its
  dynamic production NewColleague fetch passes the exact-course/full-row gate.
  Shorter College's public newer-Colleague catalog is a seventh fresh lead, with a current open
  section and a historical non-open status row.
  No registry or builder changes.
- **Prior July 11 Colleague round 4 is complete.** Round 3 found Camden County
  and Walsh College with real mixed numeric seats but both remain conditional pending the production
  newer-API adapter; Brookdale is an exact duplicate already in `schools.py`. Round 4 closed Gustavus
  (wrong/stale term returned) and Texas Wesleyan (SAML/SSO). The original 11-host candidate list is now
  exhausted except for the production-adapter build decision: Camden, Walsh, Lebanon Valley, and
  Augustana are source-validated conditional leads; Onondaga is fully gated and awaiting relay.
  Do not re-probe conditional numeric hosts until the builder has a production adapter.
- Research-only: I will not edit `schools.py`, contact the builder, or hand off candidates without
  Nathan's explicit approval.

## DONE this partnership
- **July 11, 2026 — fresh public-schedule pass (Fairfield + UC Davis + Johns Hopkins).**
  - **Fairfield University (CT; `course-search-net.fairfield.edu`): SOURCE-GATED, conditional on
    production adapter.** Official Angular app's lazy module identifies `GET /api/course/courses`.
    Public response is 2,251 rows in 7.23s with `Cache-Control: no-store, max-age=0`; no auth or
    course/time/day filter is involved. Seven current/future periods are present, including Fall
    Semester 2026 (1,929 rows). Fall totals are 1,012 rows with `Remaining_Seats > 0` and 917 with
    zero; all 1,929 course+section keys are unique. `Remaining_Seats` is explicit integer text and
    every positive-seat row satisfies `capacity - enrolled == remaining` from `Enrolled_Capacity`;
    some zero-seat rows are over-cap, so use Remaining_Seats as the authoritative field. Example
    `BIOL 1107` has 5 unique Fall sections: 0/0/17/4/18 seats; sibling `BIOL 1107L` exists (17 rows),
    so exact `Course_Subject_Number` plus `Section_Number` scoping is mandatory. The API publishes no
    completed term, so the completed-term gate cannot be run yet. Name dedup clean; official Fall 2025
    fact sheet reports 5,464 four-year undergraduates + 1,697 graduate students. **Do not relay yet:**
    builder must production-test a bespoke adapter, confirm no reserved-seat false opens, and decide
    whether a 7.2s all-2,251-row response needs cache/refresh handling.
  - **UC Davis:** blocked for this pass. Official public Class Search page advertises live open seats,
    but the registrar host returned a Cloudflare security block to the headless request. No bypass or
    handoff attempted.
  - **Johns Hopkins University:** official SIS API documents `OpenSeats`, `MaxSeats`, `SeatsAvailable`,
    and textual `Status`, but every API request requires a registered API key; the public classes page
    is additionally Cloudflare-challenged. No key registration or bypass attempted; no handoff.
- **July 11, 2026 — remaining Colleague round 4 (Gustavus + Texas Wesleyan): closed.**
  - **Gustavus Adolphus College:** official `selfservice.gustavus.edu` 301s to
    `colselfsrvprod.gac.edu`, whose public page uses the legacy `GetCatalogAdvancedSearch` /
    `PostSearchCriteria` /
    `Sections` contract. `BIO 121` returned nine Spring 2026 sections (5 textual Open with 2/8/3/3/7
    seats and 4 Closed with zero; arithmetic 9/9), but the response exposed only `2026/SP` sections
    even though `ActivePlanTerms` advertises Fall 2026 and later. The production picker would choose
    Fall 2026 and then receive no matching sections, so this is stale/wrong-term data, not a live add.
    Name dedup clean; do not hand off.
  - **Texas Wesleyan University:** official registrar instructions point to
    `https://selfservice.txwes.edu:8143/Student/`; port 8143 refused connection, while standard HTTPS
    serves a SAML 2.0 login page. No guest authoritative catalog is available; close as SSO-gated.
    Name dedup clean.
- **July 11, 2026 — SUNY Onondaga Community College: GATED CLEAN.** Official
  `selfservice.sunyocc.edu` redirects to `colss-prod.ec.sunyocc.edu`; existing production `Colleague`
  works unchanged. Three-course Fall gate returned 115 mixed-status sections in 3.31s. Raw BIO 121:
  8 unique sections, 2 textual Open with 4/1 seats, 6 Waitlisted with zero; seat arithmetic held 8/8.
  Completed Spring 2026 BIO 121 returned 10 open/1 full with varied seats, ruling out fake all-open.
  Auto-term chose Fall 2026 Undergraduate, sibling exact-filtering is enforced, name dedup clean.
  Full builder-ready block is in README under the relay marker.
- **July 11, 2026 — Colleague round 3 compact pass (Camden, Walsh, Brookdale).**
  - **Camden County College (NJ; `selfservice.camdencc.edu`): SOURCE-GATED, conditional.** Public
    newer API exposes `GetCatalogAdvancedSearchAsync`, `SearchAsync`, and `SectionsAsync`. Fall 2026
    (`26/FA`, `Fall 2026 Semester`) is future/current registration (registration starts 2026-09-02);
    `BIO 121` returned six unique section IDs/numbers in 0.29s search + 0.40s sections. Four rows had
    numeric status `0` and positive seats 4/18/16/15; two had status `2`, zero seats, and full
    arithmetic (`Available == Capacity - Enrolled`, 6/6). All publish seat counts. Keyword `BIO 121`
    leaks unrelated subjects numbered 121 and neighboring BIO courses, so exact `SubjectCode + Number`
    filtering is mandatory. Spring 2026 query returned no BIO rows, so a completed-term test is not
    available for this course. Name dedup clean. **Conditional:** no production newer-API adapter yet;
    do not infer status `0` from seats alone until the production path confirms the enum.
  - **Walsh College (MI; `selfservice.walshcollege.edu`): SOURCE-GATED, conditional.** Same public
    newer API. Fall 2026 (`26/FA`, `Fall 2026 Semester`) registration starts 2026-08-30; `ACC 316`
    returned two unique IDs/numbers in 0.53s search + 0.71s sections: status `0` with 22 seats and
    status `1` full with zero seats; arithmetic held 2/2 and counts were published. Spring 2026
    (completed) returned three sections: two status `0` with 9 seats and one status `1` full, giving a
    real mixed historical result. Keyword `ACC 316` leaks neighboring ACC numbers (including `ACC 512`),
    so exact `SubjectCode + Number` filtering is mandatory. Name dedup clean against existing Walsh
    University. **Conditional:** numeric status enum still needs a production adapter and conservative
    status-plus-seat gate.
  - **Brookdale Community College:** **DUPLICATE — already registered** in `schools.py` as
    `Brookdale`, name exact-match, host `brookdalecc-ss.colleague.elluciancloud.com`; no new proposal.
- **July 11, 2026 — production newer-Colleague gate completed.** Dynamic production subclasses of
  `NewColleague` passed real fetches for all four source-gated candidates. Lebanon Valley `BIO 111L`
  returned 8 sections (6 status-0/open with positive seats, 2 status-1/full) in 2.07s; Augustana
  `BIOL 130` landed on Fall 2026 in about 2.4s and withheld five full rows; Camden `BIO 121` returned
  6 sections (4 status-0/open, 2 status-2/full) in 1.37s; Walsh `ACC 316` returned 2 sections
  (status-0/22 seats and status-1/full) in 2.02s. Every gated handoff uses the conservative rule
  `status==0 AND Available>0 AND AreSeatCountsAvailable`, exact subject+number filtering, and no
  open-only/time/day filters. Newer-Colleague sources do not expose a dependable literal completed
  term; current full rows are nonzero-status, and Walsh's Spring 2026 mixed result provides an
  additional historical sanity check. Full evidence and URLs are in README's four pending blocks.
- **July 11, 2026 — San Diego Community College District public JSON pass.** The official district
  schedule page's `js/app.js` exposes the unauthenticated live endpoint
  `https://mws-api.sdccd.edu/?term=2267&career=ugrd`; Fall 2026 returned 4,164 rows in about 6s and
  the response was dynamically served with `x-time-diff-sec: 444`. The feed has numeric capacity and
  enrollment, a status enum (`O` open, `C` closed), unique current `CLASS_NBR` keys, and genuine mixed
  Spring 2026 status results. Three net-new colleges are source-gated in README: City (`CITY`, 1,100
  Fall rows; MATH 121 6/9 open), Mesa (`MESA`, 1,971 rows; MATH 121 8/13 open), and Miramar (`MIRA`,
  1,093 rows; BIOL 131 2/3 open). Closed rows can retain positive capacity arithmetic, so any adapter
  must require both `ENRL_STAT == O` and positive `ENRL_CAP - ENRL_TOT`; exact campus/subject/catalog
  filtering is mandatory. No production adapter or handoff marker yet.
- **July 11, 2026 — Riverside Community College District public SharePoint API pass.** Moreno Valley,
  Norco, and Riverside City are net-new registry candidates. The official MVC class finder JavaScript
  calls `https://apps-studentrcc.msappproxy.net/schedule` lists and computes openness as
  `Total Seats > Seats Used` while honoring `Last Day to Add`. Fall 2026 (`26FAL`) returned 1,004 MVC
  sections (812 open), 1,054 Norco (911 open), and 2,330 Riverside (1,453 open); all current rows were
  modified July 11 and section IDs were unique. Spring 2026 returned genuine mixed historical feeds:
  MVC 939 (815/124), Norco 973 (929/44), Riverside 2,045 (1,679/366). Exact course+section filtering
  is mandatory; withhold enrollment-limited rows. Full school blocks and official RCCD headcounts are
  in README. These remain source-gated pending a production adapter; no handoff markers yet.
- **July 11, 2026 — University of California, Berkeley public class-search pass.** Official
  `classes.berkeley.edu` search facets `8588` (Fall 2026) and `8576` (Spring 2026) link to exact
  section pages with embedded `ucb.enrollment.available` JSON. Biology Fall had four unique class IDs,
  all status `O` (Open); two Biology 1B sections had 1/1 unreserved seats while Biology 1A/1AL's
  21/20 seats were entirely reserved. Spring had three unique IDs with 2/1/1 open seats and
  `openReserved: 0`, proving genuine current/historical variation. The rendered pages expose the same
  counts and reservation text. A future adapter must require exact term/subject/class ID, status `O`,
  positive capacity-minus-enrolled, and subtract `openReserved` so reserved-only seats are withheld;
  preserve waitlist/consent restrictions. Source-gated; no handoff or production code made.
- **July 11, 2026 — UNC Asheville public schedule API pass.** Official class-schedule JavaScript
  calls unauthenticated `https://meteor.unca.edu/registrar/class-schedules/api/v1`. Fall 2026 returned
  788 unique CRNs (484 Open/304 full); Spring 2026 returned 866 (520/346). Every row's
  `Classification.Open` exactly matched positive `EnrollmentMax - EnrollmentCurrent` (788/788 and
  866/866), with `no-cache` response headers. Exact sibling `BIOL 344.001` was 15/15 closed while
  `.002` was 10/15 open; Spring Biology labs likewise mixed. Future production logic must scope exact
  term/department/course/CRN, require Open and positive arithmetic, never count waitlist seats, and
  retain permission/restriction text. Net-new four-year public liberal-arts candidate; source-gated
  pending adapter, no handoff or production changes.
- **July 11, 2026 — North Carolina Central University public Banner pass.** Official public Eagles
  Self Service (`ssbprod-nccu.uncecs.edu`) lists Fall 2026 as `202710` and Spring 2026 as `202620`
  (View only). Detail pages expose labeled numeric Capacity/Actual/Remaining plus unique CRN and exact
  section title. Fall `BIOL 1100` had 16 unique CRNs: 14 full and two open (35/34/1 and 35/5/30).
  Spring had seven unique CRNs with one positive remaining and six full/over-cap (including -1/-2),
  confirming a real mixed historical feed. Arithmetic was direct on every sample. A future adapter must
  scope exact term+subject+course+section/CRN and require Remaining > 0, preserving waitlist/
  permission notes; current `Banner` production fetch is untested. Source-gated; no handoff or code.
- **July 11, 2026 — UNC Greensboro current Banner SSB pass.** Official `erp-registration.uncg.edu`
  exposes public `classSearch/get_subject`, `searchResults/searchResults`, and
  `searchResults/getEnrollmentInfo`. Biology (`BIO`) Fall 2026 (`202608`) returned 284 unique CRNs
  (170 openSection/114 closed); Spring 2026 (`202601`) returned 206 (117/89). Numeric
  `maximumEnrollment`, `enrollment`, and `seatsAvailable` arithmetic held 284/284 and 206/206;
  detail pages agreed. `openSection` can mean waitlist-only: one Fall row had 0 seats with six waitlist
  seats, and six Spring rows had no positive seats (one over-cap -1). Future logic must require
  `openSection == true AND seatsAvailable > 0`, exact term/subject/course/sequence/CRN, and preserve
  restrictions/reserved-seat summaries. Net-new 18,682-student public research university; source-
  gated pending adapter, no handoff or production changes.
- **July 11, 2026 — Winston-Salem State University public Banner pass.** Official public schedule
  is `https://ssbprod-wssu.uncecs.edu/pls/WSSUPROD/bwckschd.p_disp_dyn_sched`; Fall 2026 is `202680`
  and completed Spring 2026 is `202620` (View only). The public catalog route
  `bwckctlg.p_disp_listcrse` exposes Biology listings and detail pages expose labeled numeric
  Capacity/Actual/Remaining plus stable CRN and exact section title. Fall Biology exposed 73 unique
  CRNs and Spring 69. Exact `BIO 1113` had six Fall sections (2 positive remaining: 1 and 5; four
  full) and five Spring sections (3 positive: 1, 2, 11; two full); `Remaining == Capacity - Actual`
  held on all sampled detail rows. A future adapter must use exact term + subject + course +
  sequence/CRN and require `Remaining > 0`, preserving restriction/waitlist notes. Net-new public
  four-year candidate; official Fall 2025 student data reports 4,972 total students. The existing
  production `ListcrseBanner8` path was tested dynamically: exact `BIO 1113` returned 6 sections in
  2.48s, with 2 open/4 full and identical Remaining values. Production-compatible, but still no
  handoff or code changes.
- **July 11, 2026 — Worcester State University public newer-Colleague pass.** Official public catalog
  is `https://selfservice.worcester.edu/Student/Courses`; `SearchAsync` + `SectionsAsync` use the
  JSON-string search contract. Subject code is `EN` (not `ENGL`), and Fall 2026 is `2026FA` /
  `Fall Semester 2026`. A dynamic production `NewColleague` fetch of exact `EN 101` returned 33
  unique sections in 1.87s: 7 numeric status-0 rows with positive seats `[2,4,7,2,1,2,18]` and
  26 status-1 rows at zero. Raw `Available == Capacity - Enrolled` held 33/33 and section numbers
  were unique; `BI 101` and `PY 101` provided additional exact-course checks. Safe rule is
  `status==0 AND Available>0 AND AreSeatCountsAvailable`. Net-new public four-year candidate;
  source-gated and not handed off.
- **July 11, 2026 — Shorter College public newer-Colleague pass.** Official public catalog is
  `https://selfservice.shortercollege.edu/Student/Courses`; the client uses the JSON-string
  `SearchAsync`/`SectionsAsync` contract. Fall 2026 is `2026FA` plus main-session variants; exact
  `ENGL 2803` returned one Fall section (`01`) through dynamic production `NewColleague`, with
  status 0 and 5 available seats. Raw detail was 45 capacity / 40 enrolled / 5 available. Fall
  2025 returned five unique rows including one status-2 non-open row and four status-0 rows with
  positive seats; `Available == Capacity - Enrolled` held on every sampled row. Apply
  `status==0 AND Available>0 AND AreSeatCountsAvailable`, exact term+subject+course+section keys,
  and preserve restrictions/waitlist notes. Net-new private two-year HBCU; source-gated and not
  handed off.
- **July 11, 2026 — Brazosport College Common Course Schedule pass (status blocked).** Official
  `https://mybcnext.brazosport.edu/CMCPortal/Common/CourseSchedule.aspx` is publicly reachable and
  exposes MAIN Campus plus Fall 2026 (`2026-27 Fall - 16 Week`, value `1207`), Keyword/Course fields,
  and an explicit `Open & Closed` radio. Focused official-form submissions for `ENGL` + `ENGL 1301`,
  `ENGL` + `1301`, and keyword-only `English` each returned the portal's explicit no-classes result.
  No section rows or seat/status fields were available to validate, and the request contract was not
  safely inferable. Treat as a search/feed availability block, not an empty schedule; no handoff.
- **July 11, 2026 — University of Southern Maine public Course Search pass.** Official
  `https://usm.maine.edu/registration-scheduling-services/course-search/` exposes public term and
  subject-filtered results with explicit `Status`, `Enrollment: used of capacity`, section number,
  and stable class number. Fall 2026 (`strm=2710`, `subject=COS-busunit-UMS06`) has open COS 160
  sections (class numbers `80083` at 8/28 and `80084` at 26/28). Completed Spring 2026 (`strm=2620`,
  same subject) is mixed: COS 422 class `43026` is Closed at 23/28 and COS 430 class `41953` is
  Closed at 24/28 while neighboring COS rows are Open. Use exact term+subject+course+class-number
  keys, `Status == Open`, and positive `capacity - enrolled`; preserve prerequisite/restriction text.
  Net-new public four-year lead; no production adapter and no handoff.
- **July 11, 2026 — Rensselaer Polytechnic Institute public classic Banner pass.** Official
  `https://sis.rpi.edu/rss/bwckschd.p_disp_dyn_sched` exposes current Fall 2026 (`202609`) and
  completed Spring 2026 (`202601`, View only). Detail pages publish stable CRNs and labeled
  `Capacity`, `Actual`, and `Remaining` tables with a separate waitlist table. Fall examples:
  CSCI 2200 CRN `78037` = 32/31/1 and CSCI 2600 CRN `79735` = 24/2/22. Spring is mixed rather
  than an all-open guest view: CSCI 2600 CRN `37370` = 24/25/-1, PSYC 4200 CRN `36882` = 60/60/0,
  and CSCI 6964 CRN `38797` = 10/8/2. A future adapter must key exact term+subject+course+CRN,
  require primary `Remaining > 0`, ignore waitlist/cross-list remaining, and preserve restriction
  text. Net-new public four-year lead, but classic `bwckschd` is not the tested JSON Banner path;
  no production adapter and no handoff.
- **July 11, 2026 — Middle Tennessee State University public classic Banner pass.** Official
  `https://ssb.mtsu.edu/pls/PROD/bwckschd.p_disp_dyn_sched` exposes Fall 2026 (`202680`) and
  completed Spring 2026 (`202610`, View only). Detail pages publish stable CRNs plus primary and
  waitlist `Capacity`, `Actual`, and `Remaining`. Fall is mixed: CSCI 1010 CRN `81110` = 101/90/11,
  while MGMT 3610 CRN `81484` = 37/37/0 with a separate 99-seat waitlist. Spring confirms mixed
  results: BIOL 2011 CRN `12710` = 24/24/0, DATA 3500 CRN `12175` = 32/33/-1, and INFS 3800 CRN
  `13058` = 24/23/1. Future adapter must key exact term+subject+course+CRN, require primary
  `Remaining > 0`, ignore waitlist/cross-list remaining, and preserve restriction/prerequisite
  text. Net-new public four-year lead; classic `bwckschd` is not the tested JSON Banner path, so
  no production adapter or handoff.
- **July 11, 2026 — North Central University recheck closed.** Its public newer-Colleague catalog
  exposed future terms, but exact section-bearing `ENG 496`, `MATH 115`, `MATH 110`, and `PSYC 258`
  samples returned only status-0 positive-seat rows across Summer/Fall 2026, with no full/non-open
  row to disprove an all-open default. No proposal. Southwestern Law remains the prior rolling-term
  cut; Colorado Mountain remains held because Fall 2026 still returned no matching sections.
- **July 11, 2026 — Northern New Mexico College schedule pass closed.** Official schedule page
  `https://schedule.nnmc.edu/academics/schedule-of-classes.html` publishes Summer/Fall 2026 PDFs
  and says the most up-to-date schedule is in Banner, but the PDFs contain no live capacity,
  enrollment, remaining-seat, or authoritative status field. Catalog-only; no proposal.
- **July 11, 2026 — Northwood Technical College course-search pass closed.** Official app
  `https://courses.northwoodtech.edu/` posts to `/Search/CourseSearch`, but broad and ENGL queries
  returned success with `total=0` and empty detail; no usable semester options or live seat fields
  were exposed. Unavailable current feed; no proposal.
- **July 11, 2026 — Columbia University Open Data Service pass closed.** Official documentation
  describes `NumEnrolled`, `MaxSize`, and `EnrollmentStatus` (`O`/`C`), but the documented JSON URL
  now redirects to Columbia CAS authentication and the docs host is Cloudflare-challenged here. No
  live rows accepted; no proposal.
- **July 11, 2026 — North Orange County CCD public JSON pass (status blocked).** Official
  `schedule.nocccd.edu` exposes unauthenticated Fall 2026 `courses.json`/`sections.json`: 3,908 unique
  CRNs across Cypress (1,694) and Fullerton (2,170), with exact `sectSeatsAvail == sectMaxEnrl -
  sectEnrl` arithmetic. Summer 2026 provides a mixed historical comparison (349/458 sections), but
  the feed has no status enum; the client treats positive seats as open even though Cypress documents
  seats that remain visible after a class is closed for a waitlist/add-code condition. No handoff or
  adapter spec until a trustworthy status/reservation signal is found.
- **July 11, 2026 — Ventura County Community College District triage deferred.** Official
  `schedule.vcccd.edu` is server-rendered Banner-style HTML. Summer 2026 exposed `OPEN/FULL` and
  Cap/Act/Rem fields, but the response was tens of megabytes and the Fall 2026, Spring 2026, and
  future-term probes returned zero rows. No completed-term/freshness gate or adapter spec was made;
  revisit only if the district publishes a current Fall term or an underlying JSON endpoint.
- **July 10, 2026 — round-2 partial findings (Lebanon Valley + McDaniel).**
  - **Lebanon Valley College (PA; `selfservice.lvc.edu`): SOURCE-GATED, NOT YET A HANDOFF.** Public
    guest catalog uses `POST /Student/Courses/SearchAsync` with JSON-string `searchParameters`, then
    `POST /Student/Courses/SectionsAsync` with `courseId` + `sectionIds`. Current Fall 2026 term code
    is `26/FA`; registration metadata runs 2026-03-30 through 2026-08-23, so this is live registration,
    not an archive. `BIO 111L` returned 8/8 unique IDs and 8/8 unique section numbers: six numeric
    status `0` rows with 1/2/1/5/1/1 seats and two status `1` rows with zero seats. All eight publish
    `AreSeatCountsAvailable=true`; `Available == Capacity - Enrolled` held on every row. Search was
    0.36s and sections 0.45s. Keyword `BIO 111` leaks `BIO 111L` and unrelated subjects numbered 111,
    so exact `SubjectCode == BIO && Number == 111` filtering is mandatory. Name dedup is clean.
    **Why conditional:** existing production `Colleague` requires textual `AvailabilityStatus ==
    "Open"`; this newer API emits numeric 0/1. Do not add the relay go-ahead marker until a conservative
    production adapter confirms numeric status 0 plus positive `Available` and passes the real fetch
    gate. Raw seats alone are not authoritative because restricted/waitlisted sections can retain seats.
  - **McDaniel College (MD): CLOSED.** McDaniel's official Student Resources page links its Self-Service
    catalog, but the live `/Student/Courses` route redirects guests to `/Student/Account/Unauthorized`.
    No public authoritative section availability is exposed; do not spend more probe time unless the
    school restores guest access. Name dedup was clean.
- **July 10, 2026 — newer Colleague API investigation (Augustana + Bridgeport).**
  - **University of Bridgeport (CT, 4-year; `colss-prod.bridgeportsaas.elluciancloud.com`; official
    `selfservice.bridgeport.edu` redirects there):** public guest `POST /Student/Courses/PostSearchCriteria`
    with the existing CSRF/session flow returns JSON in the familiar `Courses` + `CourseFullModels` shape;
    `POST /Student/Courses/Sections` returns `SectionsRetrieved.TermsAndSections`. The current
    Fall 2026 `ENGL 101` example returned 14 sections: 8 `Open`, 1 `Closed`, 5 `Waitlisted`; every
    open row had positive `Available`, every non-open row had zero `Available`, and all 14 `Number`
    keys were unique. `Available == Capacity - Enrolled` held for all 14. Spring 2026 (past) returned
    9 Open + 1 Waitlisted, so the guest view is not an all-open status fake. Fall term registration
    metadata included registration through 2026-09-07; responses were live, not View Only/archive.
    Exact course filtering is mandatory: the keyword response also returns neighboring ENGL courses;
    select the exact `SubjectCode` + `Number` before using `MatchingSectionIds`. Latency: 1.33s search,
    0.79s sections. This is a clean candidate for a reusable Colleague variant, pending production-path
    implementation/gate by the builder after Nathan's approval.
  - **Augustana College (IL; `selfservice.augustana.edu`; distinct from Augustana University/`augie.edu`):**
    its public catalog uses `POST /Student/Courses/SearchAsync` with payload
    `{"searchParameters": <JSON-string>}` and `POST /Student/Courses/SectionsAsync` with
    `{"courseId", "sectionIds"}`. Fall 2026 `BIOL 130` returned six unique IDs with four status `0`
    rows (positive seats) and two status `2` rows (0 seats, full); `Available/Taken/Capacity/Waitlisted`
    was internally consistent on all six. Fall term is `2026-27 Fall Semester`, with registration
    dates beginning 2026-04-22 and ending 2026-08-31; response is current, not archived. Latency:
    2.04s SearchAsync, 0.39s SectionsAsync. Sibling-leak test: keyword `BIOL 130` returns both
    `BIOL 130` and `BIOL 130L`, so exact `SubjectCode` + `Number` scoping is required. **Conditional:**
    `AvailabilityStatus` is numeric (0/2) and the public UI exposes seat CSS/counts rather than textual
    status labels; do not hand off until the enum mapping (0=open, 2=full) is independently confirmed
    through the production adapter/gate.
  - **Gustavus Adolphus:** official `selfservice.gustavus.edu` redirects to
    `colselfsrvprod.gac.edu`; a legacy endpoint probe returned 200 JSON, not the documented 405/400.
    No candidate handoff made; leave for a later pass if the newer-vs-legacy distinction needs more
    investigation.
- No `schools.py` or builder changes made. No builder handoff sent; waiting for Nathan's explicit go-ahead.
- **Bridgeport relay outcome:** Fable relayed the gated spec as batch 18 after Nathan's approval.

## Last push
- Sync base confirmed July 10, 2026 at `ba6a6d6`; commit `14cb230` is present in this repository.
- Round-1 findings were pushed in `51967c7`; round-2 claim was pushed in `af192dc`.
