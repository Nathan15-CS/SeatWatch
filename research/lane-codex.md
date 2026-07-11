# Lane status — Codex Sol 5.6 (research agent B)

**Only Codex writes this file. Fable reads it but never edits it.**
Codex: claim your vein here BEFORE you start probing, then commit + push. Update when you start/finish.

## NOW (active claims — Fable will not touch these)
- **CLAIMED July 11, 2026: production newer-Colleague gate + fresh official-public-schedule discovery.**
  Production `NewColleague` fetches now pass for Lebanon Valley, Augustana, Camden County, and Walsh;
  their complete handoff blocks are in README under `AWAITING GO-AHEAD`. Fairfield remains conditional
  on a bespoke adapter; UC Davis and Johns Hopkins are blocked. A new SDCCD public JSON feed yielded
  three source-gated colleges (City, Mesa, Miramar), pending a production adapter. I am continuing
  registrar-linked public schedule discovery outside the exhausted Banner/Colleague hostname veins.
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
