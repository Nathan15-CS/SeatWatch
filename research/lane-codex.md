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
- **July 11, 2026 — Framingham State University public classic Banner pass.** Official
  `https://selfservice.framingham.edu/PROD/bwckschd.p_disp_dyn_sched` exposes current Fall 2026
  (`202690`) and completed Spring 2026 (`202620`, View only). Detail pages publish stable CRNs and
  primary/waitlist `Capacity`, `Actual`, and `Remaining`. Current Fall GEOG 316 CRN `91208` is
  30/9/21. Completed Spring is mixed: ANTH 206 CRN `20424` = 30/30/0, BIOL 460 CRN `20095` =
  5/4/1, and COMM 280 CRN `20146` = 14/14/0. Future adapter must key exact term+subject+course+
  CRN, require primary `Remaining > 0`, ignore waitlist/cross-list remaining, and preserve
  restriction/prerequisite text. Net-new public four-year lead; classic `bwckschd` is not the
  tested JSON Banner path, so no production adapter or handoff.
- **July 12, 2026 — University of Nebraska Omaha public Class Search pass.** Official
  `https://www.unomaha.edu/registrar/students/before-you-enroll/class-search/` exposes exact
  term/subject query parameters and public result pages. Fall 2026 (`term=1268`) has explicit
  mixed sections: HIST 8030 section 001/class `11821` is Open at 16/18/2; HIST 8010 class `11607`
  is Closed at 0/0/0; HIST 8916 class `14370` is Closed at 5/5/0. Completed Spring 2026
  (`term=1261`) independently mixes CMST 1110 class `16231` Open at 6/20/14 with BLST 3410 class
  `12500` Closed at 10/10/0 and HIST 4910 class `19413` Closed at 2/2/0. Future adapter must key
  exact term+subject+catalog+section/class number, require explicit Open and positive Seats
  Available, and preserve notes/prerequisites/cross-listings/modality. Net-new public four-year
  lead; no production adapter or handoff.
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

## July 12 batch checkpoint
- **Batch 10 complete (10 net-new, validated colleges):** Moorpark, Ventura, Community College of Rhode
  Island, San José State, Lipscomb, Foothill, Mt. San Antonio/Mt. SAC, Lakeland, University of Georgia,
  and SUNY Potsdam. README has the official URLs, current/historical samples, authoritative seat/status
  fields, freshness caveats, and exact-key rules for all ten.
- Every candidate is source-gated pending a production adapter; no `schools.py` or builder handoff was made.
  Generic VCCCD triage and the old UGA Athena-CAS blocker are explicitly superseded by the live site-specific
  schedule viewers documented in the batch section.
- **Next:** continue the never-swept public-schedule/Colleague/CT-log search; keep accumulating a full batch
  before the next README update. Research-only boundary remains in force.

## July 12 Batch 11 checkpoint
- Batch 11 is appended to `research/README.md`: Sandhills, College of the Florida Keys,
  Horry-Georgetown Technical, Kenyon, Schoolcraft, Bentley, Grayson, Catawba Valley CC,
  University at Albany, and Illinois Tech.
- Five have direct current/historical numeric or status rows. Kenyon has a current static table plus a
  linked Fall table; Bentley, Catawba Valley CC, Albany, and Illinois Tech are explicitly marked as
  source-surface/partial leads pending browser, JSON, or missing-term capture. This confidence split is
  intentional—no inferred seats and no production handoff.
- Name/host dedup checks were clean for the ten names; no `schools.py` edit and no builder message.

## July 12 Batch 12 checkpoint
- Batch 12 appended to `research/README.md`: University of Oregon, University of the Virgin Islands,
  Cal Poly Humboldt, Lawrence University, Concordia University Chicago, and Nicholls State University.
- Oregon, UVI, Cal Poly Humboldt, Lawrence, and Concordia have direct current-plus-completed-term
  numeric evidence and are marked `GATED, AWAITING GO-AHEAD`; Nicholls is explicitly source-level
  partial because the current Fall PDF link was verified but not parsed in this pass (Spring PDFs are
  numeric and mixed).
- Exact term/course/section/CRN rules, snapshot freshness, reserved/cross-list/waitlist caveats, and
  dedup notes are in the README. Research-only boundary remains in force: no `schools.py` edit and no
  builder message.

## July 12 Batch 13 checkpoint
- Batch 13 appended to `research/README.md`: Monroe Community College (full gated source) and
  University of Alaska Anchorage (explicit department-level source lead).
- Monroe has mixed numeric `Seats Remaining` rows in current Fall 2026 and completed Spring 2026;
  exact term/course/section/CRN and repeated-meeting-row handling are documented. UAA has public
  numeric department pages plus one bounded Spring page, but remains partial until the full UAOnline
  index is captured. No `schools.py` edit and no builder message.

## July 12 Batch 14 checkpoint
- Batch 14 appended to `research/README.md`: Rio Hondo College and Laney College (Peralta CCD), both
  surfaced through official CVC Exchange pages with current and completed numeric seat examples.
- Both are explicitly source-level partials: CVC is a cross-college exchange and needs direct-college
  freshness/scope validation before any adapter or handoff. Exact term+college+course+CRN keys and
  stale/Already Started caveats are documented. No `schools.py` edit and no builder message.

## July 12 Batch 15 checkpoint
- Batch 15 appended to `research/README.md`: Clarkson University is a new PeopleSoft source lead,
  but direct guest access currently redirects to login and Spring 2026 was not reproduced.
- A direct CVC quality audit found contradictory “full” labels beside positive `Live Seat Count`
  values for Rio Hondo, Laney, Ohlone, College of the Siskiyous, and Santa Ana. The three newly
  checked CVC colleges were rejected rather than promoted; Batch 14 remains explicitly partial until
  direct-college reconciliation exists. No `schools.py` edit and no builder message.

## July 12 Batch 16 checkpoint
- Batch 16 appended to `research/README.md`: Austin Community College, limited explicitly to its
  official Continuing Education schedule. Fall 2026 and completed Spring 2026 rows publish numeric
  open seats plus enrollment/capacity and legend codes.
- This is a source-level partial, not a regular-credit ACC candidate. Scope, exact synonym/section
  keys, and CE-vs-credit policy must be confirmed before any adapter or handoff. No `schools.py` edit
  and no builder message.

## July 12 Batch 17 checkpoint
- Batch 17 appended to `research/README.md`: ten net-new CVC college leads — Cuesta, College of the
  Redwoods, San Jose City, Berkeley City, Contra Costa, Mendocino, Mission, Santa Barbara City,
  Compton, and Chaffey.
- Nine have numeric CVC term/section examples; Chaffey is identity-only because no section rows were
  rendered. Every entry is explicitly held at source-level partial because the CVC exchange has a
  demonstrated numeric-seat/status contradiction. No gate marker, `schools.py` edit, or builder
  message was made. Direct-college reconciliation is required before any handoff.

## July 12 Batch 18 checkpoint
- Batch 18 appended to `research/README.md`: Clark University, Wabash College, Long Beach City
  College, Butler County Community College (BC3), and Hawkeye Community College.
- Clark and Wabash have direct current-plus-completed numeric/status rows and are pending production
  gate tests. Long Beach remains a CVC contradiction hold; BC3, Farmingdale, and Hawkeye are explicit
  schedule/index leads without captured row-level availability. **Dedup correction:** Farmingdale was
  removed because `schools.py` already contains `SUNYFarmingdale`; it is not a new candidate. No
  `schools.py` edit and no builder message.

## July 12 Batch 19 checkpoint
- Batch 19 appended to `research/README.md`: Wesleyan University, Lakeland University, York College of
  Pennsylvania, and University of Houston.
- Wesleyan and Lakeland have reproducible current-plus-completed public seat evidence, with explicit
  reserve/bin, snapshot, duplicate-meeting, and exact-key caveats. York is a login-gated YCPWeb lead and
  Houston is limited to an embedded short-session search; neither has claimed numeric seats.
- Dedup checks were clean against `schools.py` and prior notes. No registry or builder changes; continue
  research-only until an explicit go-ahead.

## July 12 Batch 20 checkpoint
- Batch 20 appended to `research/README.md`: University of New Mexico and Dickinson College.
- UNM has public Banner current/completed detail examples with Capacity/Actual/Remaining, waitlist,
  cross-list, and restriction fields; it remains gated until all-subject guest fetch and a completed-term
  full-row test pass. Dickinson's public Banner term selector and registrar documentation confirm the
  seat-bearing detail surface, but no row values were claimed because the guest form was not reproduced.
- Dedup checks were clean. No `schools.py` or builder changes; research-only boundary remains in force.

## July 12 Batch 21 checkpoint
- Batch 21 appended to `research/README.md`: Las Positas College and Chabot College, both on the
  Chabot-Las Positas district Banner host.
- Las Positas has current Fall 2026 and completed Spring 2026 numeric detail rows, including open and full
  examples. Chabot has a completed-term over-capacity edge case and a public current schedule index, but no
  current detailed row was claimed. Campus identity must remain part of every key.
- Dedup checks were clean. No `schools.py` or builder changes; research-only boundary remains in force.

## July 12 Batch 22 checkpoint
- Batch 22 appended to `research/README.md`: fifteen net-new identities — Cayuga Community College,
  Washington College, California State University Long Beach, Indiana University Bloomington, Le Moyne
  College, Kalamazoo Valley Community College, Great Bay Community College, Wayne Community College,
  Hope College, Middlebury College, Shasta College, Navarro College, Wheaton College (IL), Westmont
  College, and Arcadia University.
- Cayuga has the clearest current public numeric `Availability` rows (including mixed zero/positive
  examples); Washington College and CSULB expose seat-bearing static/current fields. The other entries
  are explicitly bounded public schedule or dynamic-endpoint leads with no inferred seat values.
- All fifteen were deduped by exact name against `schools.py` and prior research notes. None passed the
  full production gate in this research-only pass; no `schools.py` or builder changes were made.

## July 12 Codex Batch 23 checkpoint
- Batch 23 appended to `research/README.md`: Portland Community College, MiraCosta College, Northern
  Arizona University, Purchase College, Massachusetts College of Liberal Arts, Honolulu Community
  College, Kapiolani Community College, University of Hawaiʻi Maui College, Windward Community College,
  and Hawaiʻi Community College.
- PCC, MiraCosta, and NAU are current public schedule/seat-field leads requiring guest replay and
  completed-term tests. Purchase and MCLA are registration-surface leads with no seat rows captured.
- The five UH identities are explicitly marked legacy/retiring because the official service warns it was
  unavailable after December 2025; they are historical/system leads only and were not handed off.
- All ten were deduped against `schools.py` and prior research notes. No `schools.py` or builder changes.

## July 12 Codex Batch 35 checkpoint
- Batch 35 appended five net-new identities: Claremont McKenna College, Pomona College, Harvey Mudd College,
  Pitzer College, and Occidental College.
- CMC has a live public no-login course-search form with term/status filters and a refresh timestamp; Oxy
  has a public Course Counts workflow scoped to Fall 2026 First Year Seminars. Pomona, HMC, and Pitzer are
  bounded portal/5C leads with no numeric guest rows captured. No seats were inferred, and all five require
  campus/eligibility isolation plus current/completed-term replay before adapter work. No `schools.py` or
  builder changes.

## July 12 Codex Batch 26 checkpoint
- Batch 26 recorded bespoke public-schedule reconnaissance: UH Mānoa and Kent State are new identities;
  KU is a previously documented revisit with stronger official seat-field confirmation; Louisville is
  explicitly login-gated.
- KU still needs a browser/network trace after public POST timeouts. UH Mānoa's Browse Classes is the
  current replacement for the retiring UH legacy pages, and Kent State's ePROD search is a public numeric
  seat lead. No adapter or builder handoff was made.

## July 12 Codex Batch 27 checkpoint
- Batch 27 appended two net-new public pathways: North Carolina A&T’s UNC-ECS Banner schedule and Wright
  State’s WINGS Express/Banner schedule.
- NC A&T’s public term selector exposes Fall 2026 and completed Spring 2026; historical detail pages
  expose Capacity/Actual/Remaining but current Fall 2026 row capture remains outstanding. Wright State
  exposes current Fall 2026 plus completed Spring 2026 numeric rows, including an over-cap negative value;
  replay, freshness, campus, restriction, and waitlist tests are still required. No `schools.py` or
  builder changes.

## July 12 Codex Batch 28 checkpoint
- Batch 28 appended two net-new California Colleague identities: West Valley College and Victor Valley
  College.
- West Valley has an official no-login schedule, historical Capacity/Actual/Remaining proof, and a current
  Fall 2026 schedule route; current row replay and West Valley-vs-Mission campus isolation remain open.
  Victor Valley’s official public guest search is reachable but returned no populated rows, so current
  numeric capture is still required. No `schools.py` or builder changes.

## July 12 Codex Batch 29 checkpoint
- Batch 29 appended three net-new CSU identities: CSUSB, CSU Monterey Bay, and CSU Dominguez Hills.
- CSUSB’s official client-rendered schedule documents public Seats available and waitlist formulas plus
  both San Bernardino and Palm Desert campuses; current Fall 2026 request replay is still needed. CSUMB
  and CSUDH advertise no-login class searches but their linked endpoints currently redirect to Okta/SSO,
  so both remain explicitly login-gated. No `schools.py` or builder changes.

## July 12 Codex Batch 30 checkpoint
- Batch 30 appended Santa Monica College and Truman State University as net-new schedule identities.
- SMC has a current Fall 2026 schedule and documented open-seat notification/waitlist semantics but no
  captured guest numeric row. Truman publishes a Fall 2026 PDF and describes a real-time current course
  list, but the live list appears TruView-gated. Both remain follow-up leads; no `schools.py` or builder
  changes.

## July 12 Codex Batch 31 checkpoint
- Batch 31 appended Montana State University–Bozeman as a net-new public schedule/open-seat lead.
- The official registrar surface documents term/subject search and separate Bozeman, Gallatin, CORE, and
  online pathways with an open-sections filter. Current Fall 2026 numeric replay and a completed-term
  comparison remain outstanding. No `schools.py` or builder changes.

## July 12 Codex Batch 32 checkpoint
- Batch 32 appended San Diego State University as a net-new public schedule/Open University lead.
- SDSU documents no-login schedule browsing, campus and class-status filters, and section seat counts;
  direct Fall 2026 export/replay plus campus, reserved-seat, waitlist, and completed-term checks remain
  open. No `schools.py` or builder changes.

## July 12 Codex Batch 33 checkpoint
- Batch 33 appended University of Vermont as a net-new current public course-page lead.
- UVM PACE pages expose refreshed Fall 2026 CRNs, explicit open/full status banners, and eligibility notes;
  the public index mixes “Only N seats available” with “This section is full - join waitlist.” Exact numeric
  field capture, completed-term replay, and separation of PACE/non-degree eligibility from the main catalog
  remain required. No `schools.py` or builder changes.

## July 12 Codex Batch 34 checkpoint
- Batch 34 appended five net-new identities: Eastern Kentucky University, College of Saint Benedict,
  Saint John’s University, Scripps College, and Colorado College.
- EKU is currently limited to a Corbin regional PDF with Cap/Enr fields; the main campus search is gated.
  CSB and SJU share a public Fall 2026 search but require campus isolation. Scripps advertises a public
  Claremont consortium search but its endpoint was not captured. Colorado College advertises a public
  catalog but returned HTTP 403 here. No `schools.py` or builder changes.

## July 12 Codex Batch 24 checkpoint
- Batch 24 appended to `research/README.md`: eleven net-new identities — University of Southern
  California, University at Buffalo (SUNY), University of Wisconsin–Eau Claire, University of Minnesota,
  Cal Poly San Luis Obispo, Los Angeles Mission College, UC San Diego, University of New Hampshire, NYU
  ITP (limited scope), Los Angeles Valley College, and Gettysburg College.
- USC has a captured Fall 2026 course-level `Available Seats` surface; the other entries are explicitly
  public-search, index, or login-gated leads with no inferred numeric seats. UCSD's TSS transition and NYU's
  ITP-only scope are called out to prevent overbroad adapters.
- All eleven were deduped against `schools.py` and prior research notes. No `schools.py` or builder changes.

## July 12 Codex Batch 25 checkpoint
- Batch 25 appended to `research/README.md`: ten net-new Maricopa campuses — Paradise Valley, Glendale,
  Phoenix, Rio Salado, Scottsdale, South Mountain, Mesa, Chandler-Gilbert, Estrella Mountain, and GateWay.
- The official public SIS exposes Fall 2026 class numbers, campus filters, Open/Closed status, dates, and
  numeric `x of y seats available` values. Every lead remains gated on campus isolation, restrictions,
  completed-term comparison, and freshness/cache checks.
- All ten were deduped against `schools.py` and prior research notes. No `schools.py` or builder changes.

## July 12 Codex Batch 36 checkpoint
- Batch 36 appended five net-new identities: Rutgers University, University of Delaware, San José State
  University, University of Maine, and University of Washington–Seattle.
- Delaware and SJSU expose public seat-oriented fields; Rutgers and UW expose public schedule/status paths;
  UMaine’s PeopleSoft Class Search redirected to sign-in. No seats were inferred. All five require campus,
  eligibility, reserve/waitlist, freshness, and current/completed-term checks before adapter work. No
  `schools.py` or builder changes.

## July 12 Codex Batch 38 checkpoint
- Batch 38 appended five net-new identities: Bowling Green State University, Marshall University, University
  of Northern Iowa, Duquesne University, and West Virginia University.
- BGSU, Marshall, Duquesne, and WVU expose public schedule routes; UNI is advertised as public but redirected
  to PeopleSoft sign-in. No seats were inferred. All five require campus/career, waitlist, eligibility,
  freshness, and current/completed-term checks before adapter work. No `schools.py` or builder changes.

## July 12 Codex Batch 37 checkpoint
- Batch 37 appended five net-new identities: University of Nevada, Las Vegas; University of Nevada, Reno;
  New Mexico State University; University of Colorado Denver; and Boise State University.
- UNLV, UNR, and NMSU expose public class-search/lookup routes; CU Denver and Boise State require guest-route
  confirmation. No seats were inferred. All five require campus, career, reserve/waitlist, freshness, and
  current/completed-term checks before adapter work. No `schools.py` or builder changes.

## July 12 Codex Batch 39 checkpoint
- Batch 39 appended five net-new identities: North Dakota State University, University of North Dakota,
  University of Nebraska at Kearney, University of Nebraska–Lincoln, and University of Missouri.
- Missouri has an explicit no-login current-class-offerings route; NDSU, UND, UNK, and UNL require guest-route
  confirmation. No seats were inferred. All five require campus/career, waitlist, eligibility, freshness, and
  current/completed-term checks before adapter work. No `schools.py` or builder changes.

## July 12 Codex Batch 40 checkpoint
- Batch 40 appended five net-new identities: James Madison University, University of Richmond, George Mason
  University, University of Wisconsin–Madison, and University of Maryland, Baltimore County.
- JMU and UW–Madison have public-search evidence; Richmond, GMU, and UMBC remain schedule/portal leads. No
  seats were inferred. All five require campus/career, waitlist, eligibility, freshness, and current/completed-
  term checks before adapter work. No `schools.py` or builder changes.

## July 12 Codex Batch 41 checkpoint
- Batch 41 appended five net-new identities: The University of Alabama, University of Colorado Colorado Springs,
  East Carolina University, Stetson University, and The George Washington University.
- GW has a public Fall 2026 schedule with campus/online partitions; ECU is a departmental public-search lead,
  while Alabama, UCCS, and Stetson require guest-route confirmation. No seats were inferred. All five require
  campus/career, waitlist, eligibility, freshness, and current/completed-term checks before adapter work. No
  `schools.py` or builder changes.

## July 12 Codex Batch 42 checkpoint
- Batch 42 appended five net-new identities: Central Michigan University, Northern Michigan University,
  PennWest University, University of Hartford, and University of Michigan–Ann Arbor.
- UMich has public schedule/class-search publication evidence; NMU is limited to Global Campus online search,
  while CMU, PennWest, and Hartford require guest-route confirmation. No seats were inferred. All five require
  campus/career, waitlist, eligibility, freshness, and current/completed-term checks before adapter work. No
  `schools.py` or builder changes.

## July 12 Codex Batch 43 checkpoint
- Batch 43 appended five net-new identities: University of Massachusetts Lowell, Harvard University, University
  of San Diego, Cedar Crest College, and Pennsylvania State University.
- UMass Lowell has public Fall 2026 status rows; Cedar Crest advertises an unauthenticated search, while Harvard,
  USD, and Penn State require school/campus/guest-route validation. No numeric seats were inferred. All five
  require campus/career, waitlist, eligibility, freshness, and current/completed-term checks before adapter work.
  No `schools.py` or builder changes.

## July 13 Codex Batch 44 checkpoint
- Batch 44 appended five net-new identities: Sierra College, Lewis & Clark College, University of Massachusetts
  Amherst, University of Massachusetts Dartmouth, and Trinity College.
- Trinity has a narrow Rome-campus numeric course-info row; Sierra and Lewis & Clark expose open-section filters,
  while both UMass entries are program/online subsets. All five require scope, campus/career, eligibility,
  waitlist, freshness, and current/completed-term checks before adapter work. No `schools.py` or builder changes.

## July 13 Codex Batch 45 checkpoint
- Batch 45 appended five net-new identities: Smith College, William & Mary, Frederick Community College,
  University of Massachusetts Boston, and Williston State College.
- Williston State has public numeric Fall 2026 status rows; Smith, William & Mary, and Frederick require guest/search
  validation, while UMass Boston is a limited non-degree graduate subset. All five require scope, campus/career,
  eligibility, waitlist, freshness, and current/completed-term checks before adapter work. No `schools.py` or builder
  changes.

## July 13 Codex Batch 46 checkpoint
- Batch 46 appended five net-new identities: Harper College, Mt. San Jacinto College, Bradley University,
  University of Chicago, and Cuyamaca College.
- UChicago has published undergraduate CRN/seat-field evidence; Harper, Mt. San Jacinto, and Bradley expose public
  schedule/search surfaces, while Cuyamaca requires live endpoint validation. All five require scope, campus/career,
  eligibility, waitlist, freshness, and current/completed-term checks before adapter work. No `schools.py` or builder
  changes.

## July 13 Codex Batch 47 checkpoint
- Batch 47 appended five net-new identities: Syracuse University, University of Pittsburgh, North Carolina State
  University, University of Rochester, and Case Western Reserve University.
- Rochester and Syracuse have the clearest documented schedule-search pathways; Pitt, NC State, and Case Western
  require public/guest endpoint confirmation. All five require scope, campus/career, eligibility, waitlist,
  freshness, and current/completed-term checks before adapter work. No `schools.py` or builder changes.

## July 13 Codex Batch 48 checkpoint
- Batch 48 appended five net-new identities: Brandeis University, Massachusetts College of Art and Design,
  Roxbury Community College, Boston College, and Antioch College.
- Brandeis has direct numeric Fall 2026 `Enrl / Lim / Wait` rows; RCC has searchable open-status rows with term,
  modality, dates, and room-capacity text. MassArt, Boston College, and Antioch require endpoint/scope validation.
  All five require scope, campus/career, eligibility, waitlist, freshness, and current/completed-term checks before
  adapter work. No `schools.py` or builder changes.

## July 13 Codex Batch 49 checkpoint
- Batch 49 appended five net-new identities: San Jose State University, University of Tennessee at Chattanooga,
  Mitchell College, University of North Texas, and West Liberty University.
- SJSU has public numeric `Open Seats` rows plus reserve-capacity/waitlist documentation. UTC, Mitchell, UNT, and
  West Liberty require public endpoint and scope validation; no seats were inferred from portal-only or static pages.
  All five require scope, campus/career, eligibility, waitlist, freshness, and current/completed-term checks before
  adapter work. No `schools.py` or builder changes.

## July 13 Codex Batch 50 checkpoint
- Batch 50 appended five net-new identities: East Tennessee State University, Manchester Community College (NH),
  Diné College, Duke University, and University of Wisconsin–Milwaukee.
- MCCNH has the clearest public interactive schedule surface; ETSU has a current Fall 2026 PDF plus GoldLink
  search. Diné, Duke, and UWM require live endpoint/scope validation. All five require scope, campus/career,
  eligibility, waitlist, freshness, and current/completed-term checks before adapter work. No `schools.py` or
  builder changes.

## July 13 Codex Batch 51 checkpoint
- Batch 51 appended five net-new identities: University of Maryland, College Park, Florida State University,
  Webster University, Hellenic College Holy Cross Greek Orthodox School of Theology, and Quinsigamond Community
  College.
- UMD has direct numeric public seat rows; FSU, Webster, HCHC, and QCC require live endpoint/response validation.
  All five require scope, campus/career, eligibility, waitlist, freshness, and current/completed-term checks before
  adapter work. No `schools.py` or builder changes.

## July 13 Codex Batch 52 checkpoint
- Batch 52 appended five net-new identities: Aims Community College, San Bernardino Valley College, Crafton Hills
  College, Santa Ana College, and SUNY Old Westbury.
- All five have official schedule/search surfaces; none received production approval. SBVC and Santa Ana have the
  clearest public open-class pathways, while Crafton’s PDFs and Old Westbury’s Browse Classes link require endpoint
  validation. All five require scope, campus/career, eligibility, waitlist, freshness, and current/completed-term
  checks before adapter work. No `schools.py` or builder changes.

## July 13 Codex Batch 53 checkpoint
- Batch 53 appended five net-new identities: Cañada College, College of San Mateo, Skyline College, Los Angeles
  City College, and West Los Angeles College.
- Cañada, CSM, and Skyline share the SMCCCD public schedule/search surface with dedicated open-class listings. LACC
  and WLAC require sanctioned endpoint validation after headless 403 responses; no bypass or seat inference was
  attempted. All five require scope, campus/career, eligibility, waitlist, freshness, and current/completed-term
  checks before adapter work. No `schools.py` or builder changes.

## July 13 Codex Batch 54 checkpoint
- Batch 54 appended five net-new identities: College of Lake County, Taylor University, Ithaca College,
  Seminole State College of Florida, and Carleton College.
- CLC and Taylor expose public search/browse surfaces; Seminole's official course pages show current Fall 2026
  open-class markers. Ithaca is portal-oriented and Carleton is currently only a bounded date/identity lead.
  All five require sanctioned endpoint, scope, restrictions, waitlist, freshness, and current/completed-term
  checks before adapter work. No `schools.py` or builder changes.

## July 13 Codex Batch 55 checkpoint
- Batch 55 appended five net-new identities: American University, University of Minnesota Crookston, Lawrence
  Technological University, University of Kentucky, and North Carolina Wesleyan University.
- Crookston has the clearest public class-search lead and requires campus isolation within the UMN system.
  American, Lawrence Tech, Kentucky, and NC Wesleyan are portal, BannerWeb, or static-schedule leads. All five require scope,
  restrictions, waitlist, freshness, and current/completed-term checks before adapter work. No `schools.py` or
  builder changes.

## July 13 Codex Batch 56 checkpoint
- Batch 56 appended five net-new identities: Moraine Valley Community College, College of DuPage, Florida State
  College at Jacksonville, Santiago Canyon College, and Community College of Beaver County.
- Moraine Valley and FSCJ have the strongest public-search signals; DuPage, Santiago Canyon, and Beaver County
  are guest-search, PDF, or schedule-release leads. All five require sanctioned endpoint, scope, restrictions,
  waitlist, freshness, and current/completed-term checks before adapter work. No `schools.py` or builder changes.

## July 13 Codex Batch 57 checkpoint
- Batch 57 appended five net-new identities: Canada College, Community College of Baltimore County, Missouri
  Southern State University, Suffolk County Community College, and Vanderbilt University.
- CCBC's official QuickReg late-start catalog is the strongest source and exposes labeled numeric `Open Seats`
  rows (for example ACDV 101 CRNs 90909/90911/90912 with 16/11/19 open). Canada and MSSU expose structured
  current Fall 2026 public schedule artifacts; Suffolk and Vanderbilt are official catalog/YES portal leads.
  All five require campus/career/section scope, restriction and waitlist semantics, freshness, and completed-term
  replay before adapter work. No `schools.py` or builder changes.

## July 13 Codex Batch 58 claim — numeric-lead promotion pass
- Claiming the five-lead promotion vein: Brandeis University, University of Maryland (College Park), San Jose State University,
  Roxbury Community College, and University of Massachusetts Lowell.
- I will promote only leads with reproducible current Fall 2026 seat/status data, a completed-term mixed-status check,
  unique section identity, and an adapter-ready request recipe; otherwise they remain explicitly gated. No `schools.py` edits.

## July 13 Codex Batch 58 supplement claim — Delaware numeric lead
- Adding University of Delaware to the same promotion pass after the original five-lead sweep yielded two
  status-only/seatless blockers. I will probe only the official public Courses Search, with a completed-term
  replay and campus/session/cross-list scope checks; no `schools.py` edits.

## July 13 Codex Batch 58 checkpoint — four gate-resolved candidates
- Brandeis University, University of Maryland (College Park), San José State University, and University of Delaware
  each cleared current/completed mixed-status evidence, native section identity, scope, and adapter recipe checks.
- Roxbury Community College remains status-only without a public completed-term replay; UMass Lowell has status-only
  full/waitlist labels without numeric capacity or completed-term seat replay. Both are held out.
- Detailed gate resolutions are appended to `research/README.md` under `Codex Batch 58 — gate-resolution supplements`.
  All four are `GATED, AWAITING GO-AHEAD`; no `schools.py`, builder, registry, or deployment changes were made.

## July 13 Codex Batch 59 claim — numeric public-search promotion pass
- Claiming five bounded public-search leads: Bowling Green State University, Marshall University, California State
  University San Bernardino, Claremont McKenna College, and Community College of Baltimore County.
- I will probe only official no-login/current-term surfaces and their completed-term equivalents, preserving campus,
  career, modality, section identity, restrictions, waitlists, and freshness. Only sources clearing the full gate will
  be appended to `research/README.md`; no `schools.py` edits.

## July 13 Codex Batch 59 checkpoint — five explicit hold-outs
- Bowling Green State University is status-only: its official result disclaimer excludes open/closed/current enrollment,
  and no completed-term status replay was found.
- Marshall exposes only Fall/Summer 2026; the submitted Fall listing exceeded the 30-second timeout, so no rows were
  promoted. CSUSB is an Angular client shell whose rows require a bearer-token API flow; no sanctioned no-login replay
  was obtained.
- Claremont McKenna has excellent Fall 2026 mixed numeric seats but only one selectable term, silently normalizes
  unsupported historical terms, and visibly mixes 5C campus codes. CCBC's late-start catalog has numeric open seats but
  no closed/waitlist rows; its Spring 2026 replay is empty. CCBC was already a Batch 57 identity, so no duplicate was
  added.
- README now records the exact official URLs, evidence, and blockers for all five. Zero candidates are gated or safe for
  builder handoff. No `schools.py` or production changes.

## July 13 Codex Batch 60 claim — Northwest public-schedule vein
- Claiming five bounded leads: Portland Community College, Pima Community College, North Seattle College, Seattle
  Central College, and South Seattle College.
- I will test only each institution's official public schedule/current-term and completed-term surfaces, preserving
  district/campus identity, section keys, modality, restrictions, waitlists, and freshness. Only fully reproducible
  gate-cleared evidence will be appended to `research/README.md`; no `schools.py` edits.

## July 13 Codex Batch 60 checkpoint — one gated candidate, four hold-outs
- Portland Community College cleared the current numeric gate through its official Fall 2026 BI 101 page plus the
  public capacity POST: native CRNs, mixed positive/zero seats, numeric waitlists, exact term, freshness, and a
  sub-30-second request path. It is `GATED, AWAITING GO-AHEAD` as a bespoke adapter candidate. The public selector
  has no completed-term archive; this limitation is explicit because PCC is numeric rather than status-only.
- Pima Community College's public form currently exposes only Fall/Summer 2026 and no seat/status payload; hold.
- North Seattle, Seattle Central, and South Seattle all route current and Spring schedule links to ctcLink login,
  so no unauthenticated rows or completed-term replay were obtained; hold all three independently.
- Full URLs, recipes, evidence, and blockers are recorded in `research/README.md` under “Codex Batch 60 —
  gate-resolution supplements.” No `schools.py` or production changes were made.

## July 13 Codex Batch 61 claim — Mountain West public class-search vein
- Claiming five bounded leads: University of Wyoming, Great Falls College MSU (the official `s_class_schedule_gf`
  route originally identified as the Montana State lead), University of Idaho, University of Nevada Las Vegas, and
  University of New Mexico.
- I will test only official no-login class-search/current-term and completed-term surfaces, checking numeric seats,
  mixed availability, waitlists, native section identity, campus scope, freshness, and latency. Only gate-cleared
  evidence will be appended to `research/README.md`; no `schools.py` edits or builder contact.

## July 13 Codex Batch 61 checkpoint — two gated candidates, three hold-outs
- Great Falls College MSU cleared the gate through the official `s_class_schedule_gf` APEX route: current Fall 2026
  and completed Spring 2026 rows, native CRNs, numeric Available/Enrolled/Capacity, explicit CLOSED rows, waitlist
  columns, restrictions, modality, and sub-30-second requests. The route is Great Falls College scope, not generic
  Montana State University; that identity correction is recorded in README.
- University of New Mexico cleared the gate through its public Albuquerque/Main schedule table: current Fall 2026
  plus Spring 2026 replay, native CRNs, mixed OPEN/WAIT LIST AVAILABLE/CLOSED statuses, numeric capacity/enrolled,
  branch-campus isolation, freshness guidance, and a bounded direct term/campus URL.
- University of Wyoming is login-gated; University of Idaho's public term shell produced no rows; UNLV redirects the
  public class-search route to MyUNLV login. All three are held out rather than inferred.
- Full recipes, evidence, and blockers are recorded in `research/README.md` under “Codex Batch 61 — gate-resolution
  supplements.” No `schools.py` or production changes were made.

## July 13 Codex Batch 62 claim — Great Plains public schedule vein
- Claiming five bounded leads: University of North Dakota, North Dakota State University, South Dakota State
  University, University of South Dakota, and University of Nebraska–Lincoln.
- I will test only official no-login class-search/current-term and completed-term surfaces, checking numeric seats,
  mixed availability, waitlists, native section identity, campus scope, freshness, and latency. Only gate-cleared
  evidence will be appended to `research/README.md`; no `schools.py` edits or builder contact.

## July 13 Codex Batch 62 checkpoint — two gated candidates, three hold-outs
- South Dakota State University cleared the official SDBOR guest-search gate: Fall 2026 and Spring 2026 replay,
  8,766/8,646 result counts, native CRNs, mixed positive/full numeric seats, explicit waitlist counts, institution
  labels, section identity, scope, and sub-30-second responses.
- University of South Dakota cleared the same gate when the `USD University of South Dakota` filter is explicitly
  selected: Fall 2026 and Spring 2026 replay, 2,536/2,677 result counts, native CRNs, mixed positive/full numeric
  seats, explicit waitlist counts, institution labels, and preserved scope.
- University of North Dakota and North Dakota State University are Campus Connection login-gated. University of
  Nebraska–Lincoln is MyRED/Enrollment Scheduler gated. None yielded public seat/status rows; all three are held.
- Full recipes, evidence, and blockers are recorded in `research/README.md` under “Codex Batch 62 — gate-resolution
  supplements.” No `schools.py`, registry, deployment, or builder changes were made.

## July 13 Codex Batch 63 claim — public numeric/search follow-up vein
- Claiming five bounded leads: University of Maryland, College Park; Webster University; Quinsigamond Community
  College; Massachusetts College of Art and Design; and Williston State College.
- I will test only official public current/completed schedule surfaces, checking real mixed statuses/seats,
  waitlists, exact section identity, campus/career scope, freshness, sibling leakage, pagination, and latency.
  Only gate-cleared evidence will be appended to `research/README.md`; no `schools.py` edits or builder contact.

## July 13 Codex Batch 63 checkpoint — two gated candidates, three explicit hold-outs
- Quinsigamond Community College cleared current Fall 2026 and completed Spring 2026 replay on the public Jenzabar
  search: native course-section labels, numeric seats, mixed Open/Closed/Reopened statuses, eight result pages,
  campus/method/date fields, and sub-30-second requests. It is `GATED, AWAITING GO-AHEAD`; bespoke adapter only.
- Massachusetts College of Art and Design cleared current Fall 2026 and completed Spring 2026 replay on the public
  Ellucian guest catalog: native section IDs, literal four-number seat fields, mixed Open/Closed/Waitlisted rows,
  two-page pagination, campus/meeting/faculty/career fields, and sub-30-second requests. It is `GATED, AWAITING
  GO-AHEAD`; preserve the seat string until field order is confirmed.
- UMD was a recheck of an existing gate; the completed-term page reused the current timestamp, so no new historical
  claim was made. Webster’s completed-term selector changed state but returned Fall 2026 rows (false freshness).
  Williston exposes numeric current/future rows but no completed-term selector and mixes future/high-school scope.
- README now contains the exact official URLs, recipes, examples, scope/freshness guards, and blockers. No
  `schools.py` or production changes were made; builder handoff remains blocked pending Nathan’s explicit go-ahead.

## July 13 Codex Batch 64 claim — public source-lead gate-resolution vein
- Claiming five bounded follow-ups: Lewis & Clark College; Wabash College; Hawkeye Community College; Butler
  County Community College (BC3); and University of Houston. Clark College was released immediately after the
  initial source check because its exact name is already present in `schools.py` (`wa-clark`); it is not a new lead.
- These are existing public schedule leads, not blind hostname guesses. I will test only official current and
  completed-term surfaces, seeking real mixed seat/status rows, exact section identity, scope/career controls,
  pagination, freshness, and sub-30-second request paths. Only full-gate results will be promoted in README; no
  `schools.py` edits or builder contact.

## July 13 Codex Batch 64 checkpoint — one gated candidate, four explicit hold-outs
- Wabash College cleared current Fall 2026 and completed Spring 2026 on the official public registrar table:
  407/422 rows, mixed OPEN/WAITLISTED/CLOSED statuses, numeric enrolled/available/waitlist triplets, unique csid
  detail links, cross-list/restriction fields, full-table pagination check, and roughly 3–4 second requests. It is
  `GATED, AWAITING GO-AHEAD`; bespoke HTML adapter only.
- Lewis & Clark College was checked as the replacement for Clark College; Clark was released as a duplicate already
  present in `schools.py`. Lewis & Clark redirects its Self-Service route to a login form, so it is held.
- Hawkeye has current numeric and waitlisted rows, but the completed Spring 2026 intro-course replay had no closed
  rows and no trustworthy closed/full status; hold. BC3 has a strong Fall 2026 public table, but its Spring 2026
  replay is empty. UH’s public iframe has mixed current Fall short-session statuses but no completed term and only a
  limited online/special-program scope; hold.
- README now records exact official URLs, recipes, examples, scope/freshness/latency guards, duplicate correction,
  and blockers. No `schools.py` or production changes were made.

## July 13 Codex Batch 65 claim — public-search follow-up vein
- Claiming five bounded follow-ups from the existing public-lead archive: Aims Community College; University of
  Rochester (NY); University of Vermont; University of Hawaiʻi at Mānoa; and University of Tennessee at Chattanooga.
  Name checks found no exact identity in `schools.py` for these five. I will probe only the official public search or
  schedule endpoints, with current/completed-term replay, mixed authoritative statuses or numeric seats, section-key
  uniqueness, scope/freshness, pagination, and latency checks. No `schools.py` edits or builder contact.

## July 13 Codex Batch 65 checkpoint — one gated candidate, four explicit hold-outs
- University of Tennessee at Chattanooga cleared the public Banner gate: exact Fall 2026 `ENGL 1010` returned
  41 rows over five pages with mixed numeric/full statuses, campus labels, waitlists, and unique CRNs; exact
  Spring 2026 (View Only) replay returned 7 rows with two positive-seat and five full sections. The route is
  `GATED, AWAITING GO-AHEAD`, pending builder production `Banner.fetch()` verification; no numeric term code was
  invented.
- Aims Community College has strong current OPEN/CLOSED numeric rows but an empty Spring 2026 replay. UVM's
  current/completed pages are PACE-only and expose no reliable machine-readable CRN/seat payload. UH Mānoa's
  Browse Classes port is blank/blocked. Rochester CDCS documents public status filters but produced no reproducible
  row-level current or completed results in this pass. All four remain hold-outs.
- README now contains the official URLs, exact UTC search recipe, evidence, scope/freshness/pagination/latency
  guards, and each blocker. No `schools.py` or production changes were made.

## July 13 Codex Batch 66 claim — public schedule follow-up vein
- Claiming five bounded leads from the archived public-schedule queue: Great Bay Community College; Wayne Community
  College (NC); Hope College; Navarro College; and Wheaton College (IL). Exact-name checks found no matching
  identity in `schools.py`. I will probe only official no-login schedule surfaces, requiring current and completed
  terms, authoritative mixed statuses or numeric seats, exact section identity/scope, pagination, freshness, and
  sub-30-second requests. No `schools.py` edits or builder contact.

## July 13 Codex Batch 66 checkpoint — zero gated candidates, five explicit hold-outs
- Hope College exposed strong current Fall 2026 exact `ACCT 321` evidence (CRNs 83346 open with 8 seats and 83507
  closed/full), but the same exact course had no Spring 2026 rows after replay; hold.
- Great Bay's CCSNH Banner shell exposed college/subject/course controls and Spring view-only, but no reproducible
  guest result rows; Wayne's Fall ENG catalog returned nine course matches while every section panel stalled at
  `Retrieving section information...`; both hold.
- Navarro's guest selector is current-only (Summer I/II and Fall 2026) with no completed term. Wheaton's official
  registrar page links static Spring/Fall PDFs and dynamic Banner, but no row-level seat payload was captured. Both
  hold.
- README now records official URLs, exact current evidence, replay failures, and resume conditions. No `schools.py`
  or production changes were made.

## July 13 Codex Batch 67 claim — archived public schedule gate-resolution vein
- Claiming five bounded leads from the remaining queue: Cayuga Community College; Washington College; California
  State University, Long Beach; Indiana University Bloomington; and Le Moyne College. Exact-name checks found no
  matching identity in `schools.py`. I will probe only official current/completed schedule surfaces, requiring
  authoritative mixed status/seat rows, exact section keys and campus scope, pagination, freshness, and sub-30-second
  response paths. No `schools.py` edits or builder contact.

## July 13 Codex Batch 67 checkpoint — one gated candidate, four explicit hold-outs
- Indiana University Bloomington cleared a bounded iGPS gate: exact Bloomington/English/ENG-L 111 Fall 2026
  returned class 23672 closed at 0/30; exact Spring 2026 replay returned class 29885 open at 1/24, with native
  class numbers, waitlist fields, dates, instructor, room, and regular-session scope. `ENG-G 901` supplied a
  second positive-seat cross-term check. It is `GATED, AWAITING GO-AHEAD`, pending production iGPS verification.
- Cayuga has a timestamped Fall table with 473 numeric-availability rows but no completed-term selector. Washington
  College is a static Fall PDF without a completed/live replay. CSULB's current static slice has blank OPEN SEATS
  cells and no completed term. Le Moyne's guest selector is current/future-only and its legacy table has no seat
  field. All four remain hold-outs.
- README now records official URLs, exact IU recipes/evidence, scope and key guards, and every blocker. No
  `schools.py` or production changes were made.

## July 13 Codex Batch 68 claim — remaining public-index follow-up vein
- Claiming five bounded leads from the untested queue: Kalamazoo Valley Community College; Middlebury College;
  Shasta College; Westmont College; and Arcadia University. Exact-name checks found no matching identity in
  `schools.py`. I will probe only official public schedule/search surfaces, requiring current/completed terms,
  authoritative mixed status or numeric seats, exact section identity/scope, freshness, pagination, and sub-30-second
  response paths. No `schools.py` edits or builder contact.

## July 13 Codex Batch 68 checkpoint — zero gated candidates, five explicit hold-outs
- Shasta's exact ENGL-31 Fall 2026 replay returned two numeric rows (open 20/30 and waitlisted 0/30 with waitlist
  2); Spring 2026 returned two numeric rows but both said `Open` and `THIS CLASS HAS ENDED`, a decisive freshness/
  status contradiction. Hold pending semantics clarification.
- Kalamazoo's public Fall table has CRNs and schedule metadata but no seats/status or completed replay. Middlebury's
  browse shell exposed a term picker but no reproducible guest rows. Westmont Waypoint is SSO-gated. Arcadia's
  advertised no-login Section Search redirected to login. All five remain hold-outs.
- README now records exact Shasta evidence, official URLs, the contradiction, and resume conditions. No `schools.py`
  or production changes were made.

## July 13 Codex Batch 69 claim — public interactive-search vein
- Claiming five bounded leads from the remaining queue: Florida State College at Jacksonville; College of Lake
  County; Webster University; Hellenic College Holy Cross Greek Orthodox School of Theology; and Seminole State
  College of Florida. Exact-name checks found no matching identity in `schools.py`. I will probe only official
  public search/course pages, requiring current/completed terms, authoritative mixed status or numeric seats, exact
  section identity/scope, pagination, freshness, and sub-30-second response paths. No `schools.py` edits or builder
  contact.

## July 13 Codex Batch 69 checkpoint — zero gated candidates, five explicit hold-outs
- Hellenic College Holy Cross exposed exact `ENGL 1101` Fall 2026 numeric evidence (`1/25`, Open) but its exact
  completed Fall 2025 replay still says `8/20`, Open after the 12/17/2025 end date; this is a decisive freshness /
  status contradiction. Spring 2026 exact replay was empty. Hold pending trustworthy historical semantics.
- FSCJ exposes a public PeopleSoft form but only Fall/Summer 2026 terms and no captured row payload; CLC exposes
  Summer 2026/Fall 2026/Spring 2027 only and omits completed Spring 2026; Webster exposes many term/status controls
  but the exact `ENGL 1010` test returned no verifiable row; Seminole's course page is an open-only current
  snapshot (one `MVK2121M` row, class 71262) with no closed/completed comparison. All four remain hold-outs.
- README records official URLs, exact recipes, current/completed evidence, contradictions, and resume conditions.
  No `schools.py` or production changes were made.

## July 13 Codex Batch 70 claim — western public-search vein
- Claiming five bounded leads from the remaining queue: Adams State University; Regis University; Idaho State
  University; Central Washington University; and Western Washington University. Exact-name checks found no
  matching identity in `schools.py`. I will probe only official public class-search/catalog surfaces, requiring
  current and completed terms, authoritative mixed status or numeric seats, exact section identity and campus
  scope, pagination, freshness, and sub-30-second response paths. No `schools.py` edits or builder contact.

## July 13 Codex Batch 70 checkpoint — zero gated candidates, five explicit hold-outs
- Adams State's official Banner schedule URL (`https://ssb.adams.edu/bannerweb/schedule/schedule_options/`) hit
  a repeatable redirect loop before any term or row payload could be read. Do not infer a feed from the URL; hold
  until a stable public schedule entry point is documented.
- Regis' official `https://catalog.regis.edu/course-search/` is a catalog-only course search: it exposes keyword
  and subject controls but no term selector, section rows, seats, status, or completed replay. Hold pending an
  authoritative registration/search surface with row-level availability.
- Idaho State's official registration information page explicitly routes Find Classes through a logged-in MyISU
  account. The public catalog URL is not a live seat feed. Hold until ISU documents a guest search or supplies a
  permitted public endpoint; no login was attempted.
- Central Washington's official PeopleSoft Class Search is publicly reachable and exposes Fall 2026, Spring 2026,
  Spring 2027, Summer 2026, and Winter 2027 terms, plus subject/course-number, career, campus, session, and an
  open-only checkbox. The form requires at least two criteria, but the exact ENG/101 row search could not be
  completed reliably in this pass (the site lost the active course-number target during interaction); no section
  key, seat count, or status was captured. Hold until a repeatable current/completed row replay is recorded.
- Western Washington's official Banner Browse Classes surface exposes a public term picker. It returned Fall 2026
  and Summer 2026 plus Spring 2026 (View Only), Winter 2026 (View Only), Fall 2025 (View Only), and older view-only
  terms. The term option could not be selected reliably after the dynamic list loaded, so no section rows,
  numeric seats, or status semantics were captured. Hold pending a repeatable row-producing search and completed
  replay.
- Batch result: zero new full-gate candidates. README records the official URLs, exact public evidence, and resume
  conditions. No `schools.py`, registry, deployment, or builder changes were made.

## July 13 Codex Batch 71 claim — northern public class-search vein
- Claiming five bounded leads from the remaining queue: Montana State University; Northern Arizona University;
  University of Alaska Fairbanks; University of Alaska Anchorage; and University of Nevada, Reno. Exact-name
  checks found no matching identity in `schools.py`. I will probe only official public schedule/search surfaces,
  requiring current and completed terms, authoritative mixed status or numeric seats, exact section identity and
  campus scope, pagination, freshness, and sub-30-second response paths. No `schools.py` edits or builder contact.

## July 13 Codex Batch 71 checkpoint — one gated candidate, four explicit hold-outs
- Northern Arizona University cleared the public PeopleSoft gate for a bounded ART 161 replay. Fall 2026 exact
  query returned four Flagstaff Mountain/In Person sections (native class keys 2710, 2712, 2771, 9493), all
  `Available Seats: 0`; the row status icons expose `Wait List` plus the PeopleSoft `Open` helper/legend. Spring
  2026 exact replay returned four sections (native class keys 2029, 2030, 2031, 2032): 2, 2, 0, and 0 available
  seats, with `Open` icons on 001/002 and `Closed` + `Open` helper icons on 004/005. Rows include section code,
  session, dates, campus, instruction mode, instructor, and meeting data. Official entry/query surface:
  `https://www.peoplesoft.nau.edu/psc/ps92prcs/EMPLOYEE/SA/c/COMMUNITY_ACCESS.CLASS_SEARCH.GBL` (Fall recipe
  uses `strm=1267&subj=ART&nbr=161`; Spring uses `strm=1261`). This is `GATED, AWAITING GO-AHEAD`, pending a
  production adapter replay and explicit interpretation of the helper icon; do not add to `schools.py` yet.
- Montana State's official APEX schedule (`https://apexprod.msu.montana.edu/apex/r/esg/s_class_schedule_gf/class-schedule`,
  linked from `https://www.montana.edu/registrar/ScheduleofClasses.html`) is publicly reachable and exposes Fall,
  Summer, and Spring 2026 plus older terms, subject/instructor comboboxes, course number, and an open-seats-only
  checkbox. No repeatable exact subject/course row payload was captured in this pass; hold until a current and
  completed row replay with section keys and numeric/status availability is recorded.
- University of Alaska Fairbanks' official class search (`https://catalog.uaf.edu/class-search/`) is public and
  states that section information updates overnight, but the guest term picker currently exposes only Fall 2026
  and Summer 2026. No completed-term comparison or seat-bearing row was captured; catalog pages are not enough.
- University of Alaska Anchorage's official registration page (`https://www.uaa.alaska.edu/students/registration/`)
  routes class schedules through UAOnline. The official UAOnline UAA entry (`https://www.alaska.edu/uaonline/`)
  redirects to the student self-service SAML sign-in (`https://idp.alaska.edu/...`) before any guest class-search
  or seat rows are exposed. Hold; no login bypass or inference from the marketing page.
- University of Nevada, Reno's official registrar page (`https://www.unr.edu/admissions/records/registration`)
  links a public PeopleSoft Class Search (`https://cs.nevada.unr.edu/psp/unrcsprd/EMPLOYEE/SA/c/SA_LEARNER_SERVICES.CLASS_SEARCH.GBL?`).
  The guest form currently exposes only 2026 Summer and Fall (no completed Spring term), with subject/course,
  career, campus/location, mode, and open-only controls. No exact row payload or completed replay was captured;
  hold pending a history-capable guest surface.
- Batch result: one gated lead (NAU) and four explicit hold-outs. README records official URLs, exact evidence,
  blockers, and resume conditions. No `schools.py`, registry, deployment, or builder changes were made.

## July 13 Codex Batch 72 claim — flagship alternate-public-search vein
- Claiming five exact-name-new leads from the untried flagship list: University of Central Florida; University of
  Houston; Michigan State University; Clemson University; and University of Florida. Exact-name checks found no
  matching identity in `schools.py`. I will inspect registrar/official class-search pathways one school at a time,
  looking for a permitted guest surface with current and completed terms, mixed real status or numeric seats, exact
  section keys and campus scope, pagination, freshness, and sub-30-second response paths. No `schools.py` edits or
  builder contact.

## July 13 Codex Batch 72 checkpoint — zero gated candidates, five explicit hold-outs
- University of Florida's official ONE.UF Schedule of Courses (`https://one.uf.edu/soc/`, linked by the registrar)
  is public and exposes Fall 2026 through Spring 2018 term selectors, course number/class number/title/instructor,
  department and program-level filters. A reproducible Fall 2026 `ENC1101` search returned many native class numbers
  and instructor/meeting-mode summaries, but the public result explicitly says to log in for locations, dates, times,
  and final-exam details and contains no seat, capacity, open, closed, or waitlist field. This is catalog/schedule
  metadata, not a seat-bearing feed; hold pending a permitted endpoint with numeric availability.
- University of Houston's official registrar page links a public Fluid PeopleSoft Class Search at
  `https://saprd.my.uh.edu/psc/saprd/UHM_SITE/HRMS/c/SSR_STUDENT_FL.SSR_CLSRCH_MAIN_FL.GBL?Page=SSR_TERM_STA2_FL`.
  The term picker exposes Summer/Fall 2026 and a collapsed “Terms prior to Summer 2026” group that expands to
  Spring 2026. Fall 2026 structured searches for English 1303 and Mathematics 1310 returned “No results were
  returned”; no section rows, native keys, seats, status, or pagination were captured. Hold until a row-producing
  exact-course recipe is repeatable in both current and completed terms.
- Michigan State's official SIS (`https://student.msu.edu/`) advertises “Class Schedules (No login required)” and
  routes to `https://student.msu.edu/search`. The public PeopleSoft homepage exposes a Class Search tile, but the
  tile did not produce a stable guest search form or row payload in this pass; no section key, seat count, status,
  term replay, or latency evidence is available. Hold rather than infer data from the public landing page.
- Clemson's official registrar page links a separate public schedule at
  `https://soc.app.clemson.edu/schedule/index.php`. It exposes Fall 2026 and Summer 2026 only, instruction method,
  subject, instructor, course level, and location filters, plus Search/Clear. No completed Spring 2026 selector or
  seat/status field was exposed before a row replay could be attempted; hold pending a history-capable, seat-bearing
  guest surface.
- University of Central Florida's public dashboard (`https://my.ucf.edu/public/dashboard`) has a Class Search tile
  linking `https://csprod-ss.net.ucf.edu/psc/CSPROD/EMPLOYEE/SA/c/COMMUNITY_ACCESS.CLASS_SEARCH.GBL`, but the official
  registrar instructions require logging into myUCF to use Class Search. No permitted guest row payload, completed
  replay, or seat/status evidence was captured; hold and do not bypass the login boundary.
- Batch result: zero new full-gate candidates. README records official URLs, exact public evidence, and resume
  conditions. No `schools.py`, registry, deployment, or builder changes were made.
