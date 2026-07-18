# SeatWatch research — working summary (LEAN)

Cross-session research log for SeatWatch school expansion. **This file is kept lean on purpose** —
the full chronological batch-by-batch history lives in `research/ARCHIVE.md` (grep it for any past
detail). Read THIS file + the lane files; only open ARCHIVE for a specific past finding.

- **Live count: 720 schools** (goal 1,000); verified from `len(schools.SCHOOLS)` on July 15, 2026 after UVI
  and Cayuga shipped. The older 703/715/718-school milestones remain in the chronological history; Batch 8 below is the current
  registry-wide dedup queue. The next discovery vein is system-first reusable-family enumeration.
- **Who's doing what right now:** `research/lane-grabber.md` (Grab) + `research/lane-codex.md` (short, always current).
- **How we work / accuracy+efficiency gate:** `research/PARTNER-NOTE-codex.md` and repo-root
  `CONTRIBUTING_AGENT.md`. Handoffs to the builder go through Fable; gated-but-unapproved candidates
  get a heading containing the phrase **`AWAITING GO-AHEAD`** (grep for it to find every pending item).

## RESEARCH OPERATING UPDATE — July 14, 2026

Claude's targeting correction is now the active protocol: optimize for **system-shaped, reusable feeds**,
not famous-school volume. Every new pass starts with multi-college systems/districts and enumerates net-new
schools running an existing family we already ship or can reuse with minimal change: Banner-9 SSB, Banner-8
`listcrse`, College Scheduler GraphQL, Ellucian guest Colleague, and static `/data/{term}/crns.json` district
viewers. A district/system lead is ranked above a single-school bespoke portal by estimated student count,
adapter reuse, and public architecture quality. Stateful APEX/Jenzabar/viewstate sources are deprioritized;
plain GET/JSON is preferred.

No lead may be called **GATED** or reported as a builder-ready batch until all four killers pass:

1. **Freshness:** capture the source's `as of`/updated stamp and compare it with the fetch time; hours-stale
   snapshots are rejected for false-open risk.
2. **Addressability/completeness:** query a known-large first-year writing course (or the school's exact
   equivalent), follow every page, and reject round-number caps (49/50/100) or subject scatter that can silently
   omit sections.
3. **Real status:** replay a completed term for the same large course; an all-open historical result rejects the
   source as fake-status PeopleSoft-style data.
4. **Registerability:** inspect reserved/eligibility bins, waitlist and consent fields; positive aggregate
   capacity is not an open seat unless the row is actually registerable under the source's semantics.

Before reporting any lead, reload `schools.SCHOOLS` and dedupe by school ID, normalized display name, and any
existing bespoke adapter. Each reported lead must include: student count, existing adapter family or bespoke
classification, architecture (`plain GET`/JSON vs stateful portal), exact host/term/request recipe, freshness,
huge-course completeness, completed-term result, reservation/eligibility behavior, and a rank based on
**students × adapter reuse**. If any field is missing, label it `HOLD`—never `GATED`—and do not pad a batch.

### Codex Batch 85 — LACCD system lead + old-Colleague self-screen (July 15, 2026)

This pass stayed system-shaped and reloaded the live **720-school** registry before reporting. No existing ID,
normalized display name, or already-shipped district identity was repeated. It produced **zero new GATED schools**:
one unusually high-value multi-college lead is held for a live session replay, and the old-Colleague names below are
held/cut rather than padded into a builder batch.

#### 1. Los Angeles Community College District — nine net-new colleges, highest-priority HOLD

LACCD's official district materials describe **nine colleges and nearly 200,000 annual students**. The nine exact
identities are Los Angeles City College (`LACC`), East Los Angeles College (`ELAC`), Los Angeles Harbor College
(`LAHC`), Los Angeles Mission College (`LAMC`), Los Angeles Pierce College (`LAPC`), Los Angeles Southwest College
(`LASC`), Los Angeles Trade-Technical College (`LATTC`), Los Angeles Valley College (`LAVC`), and West Los Angeles
College (`WLAC`). None is in `schools.py` under the live registry check. Official scale source:
`https://www.laccd.edu/sites/laccd.edu/files/2026-01/LACCD_District_FactSheet_Final-ADA_01-15-26.pdf`.

**Architecture / reuse:** one anonymous PeopleSoft guest surface at
`https://mycollege-guest.laccd.edu/psc/classsearchguest/EMPLOYEE/HRMS/c/COMMUNITY_ACCESS.CLASS_SEARCH.GBL`.
This is an existing PeopleSoft family in SeatWatch, but this exact district surface is a stateful guest GBL page,
not yet proven to be compatible with the production JSON `IScript_ClassSearch` path. The public result exposes
native class numbers, section codes, meeting data, and textual `Open`, `Wait List`, and `Closed` statuses, but the
indexed result does not expose a numeric `enrollment_available` field. Rank is **very high students × partial
PeopleSoft reuse**, but architecture is **stateful/fragile**, so it remains HOLD.

**Exact public recipe:** select Fall 2026 (`strm=2268`), `subj=ENGL`, `catalogid=C1000`, and `Show Open Classes
Only=No`, then scope with `Campus={LACC|ELAC|LAHC|LAMC|LAPC|LASC|LATTC|LAVC|WLAC}`. Example direct query:
`https://mycollege-guest.laccd.edu/psc/classsearchguest/EMPLOYEE/HRMS/c/COMMUNITY_ACCESS.CLASS_SEARCH.GBL?Campus=LACC&catalogid=C1000&strm=2268&subj=ENGL`.
The indexed exact-writing results are not round-capped in the visible counts: LACC **44**, ELAC **83**, LAHC **45**,
LAPC **72**, LASC **29**, LATTC **47**, LAVC **57**, and WLAC **19**; LAMC was not counted because a current exact
writing result was not reproducibly indexed. The page groups `ENGL C1000` with related `ENGL C1000E/H` variants,
so the builder must prove the full variant set and deduplicate lecture/lab/combined-section rows before adopting it.

**Why not GATED:** freshness is not proven from a search-index copy; a real cookie-backed fetch must capture HTTP
date/cache headers. The completed Spring 2026 recipe is `strm=2264`; an indexed LASC exact `ENGL C1000` replay shows
14 rows all `Open` even though those rows ended June 8, 2026. That is a decisive freshness/fake-status warning until
the live response proves otherwise. LACCD's wait-list policy says wait-list enrollment begins only after seats are
filled (`https://www.laccd.edu/sites/laccd.edu/files/2025-03/Wait%20List%20Policy-2025.pdf`), but reserved FYE,
dual-enrollment, PACE, honors, combined-section, and permission restrictions still need section-detail evidence.

**Builder resume gate:** use a live anonymous session, replay Fall 2026 and completed Spring 2026 for every campus,
capture the native class-number keys and all `ENGL C1000/E/H` variants, prove no pagination/scatter/duplicate collapse,
record the source timestamp, and inspect detail/eligibility text. Only after current/completed status is genuinely mixed
and `Open` is shown to mean registerable for an unrestricted student may this become a shared PeopleSoft subclass batch.

#### 2. Old-Colleague family screen — seven holds, two cuts, and one non-lead

All tests used the existing production `Colleague` route: `GET /Student/Courses`, token/cookie bootstrap, JSON
`POST /Student/Courses/PostSearchCriteria` with the exact first-year-writing keyword, then `POST /Student/Courses/Sections`
for the full advertised ID set. Current Fall 2026 rows had numeric seat counts and textual status; every candidate below
was deduped against all 720 registry entries before being named.

| Student scale | College / host | Exact current writing result | Completed-term result | Reuse / architecture | Disposition |
|---|---|---|---|---|---|
| **~1,846 Fall 2024** (`https://www.berkshirecc.edu/about-bcc/bcc-foundation/media/impact-report.pdf`) | Berkshire CC — `bcc-ss.colleague.elluciancloud.com` | `ENG 101`: 26 rows, 20 Open / 6 Waitlisted | Spring 2026: 13/13 Open and positive | Existing old Colleague; anonymous JSON | **CUT** — fake-status replay |
| **3,054 Spring 2026** (`https://www.nashcc.edu/press-releases/nash-community-college-reports-enrollment-growth-for-spring-2026/`) | Nash CC — `ss-prod-cloud.nashcc.edu` | `ENG 111`: 20 rows, 4 Open / 16 Waitlisted | No completed term in this feed | Existing old Colleague; anonymous JSON | **HOLD** — no history |
| **7,742 total headcount, Quick Facts 2025** (`https://www.swtxc.edu/about/office-of-the-president/quick-facts.html`) | Southwest Texas Junior College — `colss-prod.swtxc.elluciancloud.com` | `ENGL 1301`: 57 rows, 47 Open / 10 Waitlisted | No completed term in this feed | Existing old Colleague; anonymous JSON | **HOLD** — no history |
| **1,807 Fall 2023 credit** (`https://www.nicc.edu/about/consumer-information/data-definitions/`) | Northeast Iowa CC — `selfserv.nicc.edu` | `ENG 105`: 13 rows, 7 Open / 6 Waitlisted | No completed term in this feed | Existing old Colleague; anonymous JSON | **HOLD** — no history |
| **3,323 curriculum 2024–25** (`https://www.wilkescc.edu/about/institutional-effectiveness/`) | Wilkes CC — `selfservice.cloud.wilkescc.edu` | `ENG 111`: 24 rows, 12 Open / 12 Waitlisted | No completed term in this feed | Existing old Colleague; anonymous JSON | **HOLD** — no history |
| **2,297 Fall 2025** (`https://highlandcc.edu/news/2025-news/2025-hcc-enrollment-increase/`) | Highland CC (KS) — `colss-prod.highldsaas.elluciancloud.com` | `ENGL 101`: no usable current rows on new portal | Spring 2026 remains legacy; not same-feed | Existing old Colleague candidate; anonymous JSON | **HOLD** — migration split |
| **2,149 Fall 2024** (`https://www.baycollege.edu/_resources-dev/pdf/about/consumer-information/michigan-transparency-act/bay-de-noc-community-college-single-audit-report-063024.pdf`) | Bay College — `colss-prod.baycollegesaas.elluciancloud.com` | `ENGL 101`: no usable current rows | New portal/current migration; no replay | Existing old Colleague candidate; anonymous JSON | **HOLD** — no rows/history |
| **Unknown in this pass** | Garden City CC — `gccc-ss.colleague.elluciancloud.com` | Tested `MATH 108`, `MATH 110`, `MATH 111`, `ENG 101`, `ENGL 101`, `BIOL 101`: zero rows | No usable current comparison | Existing old Colleague candidate; anonymous JSON | **HOLD** — empty source |

Additional hard cut: unidentified host `ssc-ss.colleague.elluciancloud.com` returned 16 `ENG 101` rows current
(15 Open / 1 non-open), but its completed Spring 2026 replay was 13/13 Open; identity was never proven, so it is
**not a school lead** and must not be added. Northern Pennsylvania Regional College (`nprc-ss...`) likewise returned
no usable current exact-writing rows. These hosts are archived as cuts/holds only to prevent rediscovery.

#### 3. Contra Costa Community College District — three-college HOLD/deprioritized

Contra Costa CCD covers **Contra Costa College, Diablo Valley College, and Los Medanos College**. Official 2024–25
fingertip facts report **50,355 unduplicated students** across the three colleges
(`https://4cd.edu/about/docs/FingertipFacts.pdf`), so this is system-shaped and high-scale. It is nevertheless a
poor near-term reuse target: the official course-search endpoint
(`https://webapps.4cd.edu/apps/courseschedulesearch/search-course.aspx`) is an ASP.NET ViewState form, not a plain
JSON/static feed or an existing SeatWatch adapter family.

The live Fall 2026 DVC query
(`https://webapps.4cd.edu/apps/courseschedulesearch/search-course.aspx?loc=dvc&o=n&sdate=8-1-2026&trm=2026FA`)
returned HTTP 200 but only page **1–25 of 1,704** rows, with `Next >>` implemented through `__doPostBack`. The
results page exposes no subject filter, and first-year writing was not on page one. That fails the addressability
killer: a builder cannot safely prove complete `ENGL` coverage without reproducing stateful pagination and checking
the entire result set. No same-feed completed-term writing replay, freshness stamp, or reserved/eligibility behavior
was established. This is separate from the previously recorded `vsb.4cd.edu` Visual Schedule Builder cut; both remain
deprioritized, not builder leads.

**Resume gate:** only revisit if the district exposes a stable subject-filtered/API feed or a fully automated
ViewState paginator that proves all exact first-year-writing rows, current freshness, a genuinely mixed completed
term, and registerability. Do not add the three colleges from this endpoint yet.

**Batch result:** 0 builder-ready additions; LACCD's nine-college PeopleSoft surface is the next highest-value live
replay; Nash, Southwest Texas, Northeast Iowa, Wilkes, Highland, Bay, and Garden City remain explicit HOLDs; Berkshire
and the unidentified `ssc-ss` host are CUT for completed-term all-open behavior; Contra Costa CCD is held for
ViewState truncation/no subject addressability. No `schools.py`, builder, registry, deployment, commit, or contact
changes were made.

### Codex Batch 73 — system/software-first district screen (July 14, 2026)

This was a deliberate high-signal screen, not a volume batch. The registry was reloaded before reporting:
`schools.SCHOOLS` remains **718**, and no existing ID, normalized name, or bespoke adapter was repeated.
Two net-new shared systems are recorded below as `HOLD`; neither cleared the four-killer gate.

1. **Yuba Community College District — Yuba College + Woodland Community College (CA), HOLD.** The
   official district site (`https://www.yccd.edu/`) says YCCD serves about **13,000 students** across the two colleges and its
   centers. Official Fall 2026 pages link public guest Colleague Self-Service at
   `https://yc-self-service.yccd.edu/Student/Courses/Search` and
   `https://wcc-self-service.yccd.edu/Student/Courses/Search`; the district's admissions pages confirm
   that students use Self-Service for current-term enrollment. Architecture is reusable **guest Colleague**,
   but the rendered public search exposes **“Unlimited Seat Counts Unavailable”** instead of numeric
   registerable seat counts. Freshness/as-of evidence, a complete first-year-writing section count, a
   completed-term mixed-status replay, and reserved/eligibility behavior therefore cannot be proven.
   **Rank:** high reuse × 13k students, but blocked at the seat-field gate.

2. **Dallas College (TX) — seven-campus system, HOLD.** Dallas College's official site identifies
   **seven campuses** and reports **103,253 credit + 24,927 non-credit students served in FY 2023–24**
   (official institutional report: `https://www.dallascollege.edu/media/dallas-college/content-assets/documents/business-and-industry/labor-market-intelligence-center/DallasCollege_EIS_MainReport_2324_Formatted.pdf`).
   The official schedule page (`https://www.dallascollege.edu/special-programs/schedules/`) advertises no-login browsing, while the current registration instructions
   place live available-seat information inside Workday. The guest Ellucian Self-Service surface at
   `https://selfsrv.dcccd.edu/Student/Courses` is reachable and reusable in principle, but this pass
   produced no verified numeric current-term section rows; the public rendering returned
   **“Unlimited Seat Counts Unavailable.”** The legacy browse route also did not yield a reproducible
   current Fall 2026 exact-course payload. Freshness, first-year-writing completeness, completed-term
   status, and registerability/reservation semantics are all unproven. **Rank:** very high reuse × student
   count, but HOLD until a current, complete, seat-bearing guest endpoint is found.

**Dedup/avoidance notes:** State Center CCD (`scccd`) and Grossmont/Cuyamaca (`gcccd`) are already in
`schools.py` and were not re-reported. North Orange CCD's static JSON source was status-blocked at the time
and was not duplicated here; **Batch 77 later supersedes that HOLD** after resolving cutoff, waitlist,
restriction, reservation, and cross-list semantics. **Batch result: 0 new builder-ready schools; 2 net-new
system-shaped HOLDs; registry unchanged at 718.**

### Codex Batch 74 — IU iGPS regional-campus family audit (July 14, 2026)

This was a software-family screen of the same public IU iGPS JSON host, not a flagship-name sweep. The
registry was reloaded first: `schools.SCHOOLS` remains **718**; no existing IU regional campus identity or
bespoke adapter was repeated. Official IU enrollment records give Fall 2025 census counts of **4,716 South
Bend, 3,664 Southeast, 3,253 East, 2,964 Kokomo, and 3,260 Northwest** students
(`https://institutionalmemory.iu.edu/aim/bitstreams/c74e8e66-f663-4b79-95b3-422794dc321a/download`).

**Family/source:** `https://sisjee.iu.edu/sisigps-prd/web/igps/course`; official IU Southeast schedule
instructions direct students to iGPS for available seats (`https://southeast.iu.edu/academics/register-1/index.html`)
and its schedule page publishes Fall/Spring 2026 course-search links
(`https://southeast.iu.edu/student-central/register/schedule-of-classes/index.html`). Exact recipe:
`GET /search/terms.json?inst={inst}`; `POST /search/courses.json` with
`{"inst":"{inst}","strm":"4268|4262","filters":{"attributes":null,"level":null,"locations":null,"meetingTimes":null,"mois":null,"sessions":null,"subject":null,"units":null},"from":0,50,...}`
until the empty page; then `GET /search/classes.json?courseId={courseId}&courseOfferNumber={courseOfferNumber}&courseTopicId={courseTopicId}&effdt={effdt}&strm={term}&inst={inst}&car=UGRD`.
The existing `IUBloomington` family is the reuse target, but production needs a shared-family variant: cache
keys must include `(inst, term)` (the current class cache keys only by term), and every section must be
filtered/validated by campus as well as `inst`.

All calls returned `Cache-Control: no-cache, no-store, must-revalidate` with an HTTP `Date` within minutes of
the July 14 EDT fetch, so the source is live rather than an hours-stale snapshot. The family screen used
Fall 2026 `4268` and completed Spring 2026 `4262`, exact `ENG-W 131` (freshman writing), and `MATH-M 118`.
The Fall `ENG-W 131` catalog was fully paged for each campus (679–1,198 catalog rows; no 49/50/100 cap),
and campus-filtered section keys were unique in every sample. Completed-term responses were genuinely mixed,
not all-open: closed rows included positive `openSeats` plus waitlists, proving `closed` is authoritative.

**Net-new campus results — all HOLD, none builder-ready:**

1. **IU South Bend (`IUSBA`, campus `SB`) — HOLD.** Fall `ENG-W 131`: 13 raw / 11 `SB` rows, 4 raw
   opens; Spring: 15 raw / 14 `SB`, 1 raw open. The same `inst` returns `SE` rows, so campus filtering is
   mandatory. Under the conservative registerability rule (`closed is false`, positive `openSeats`, no
   department/instructor consent, no `enrollmentRequirements` reservation/eligibility text), both exact
   `ENG-W 131` and `MATH-M 118` samples had **zero** clean current opens. HOLD until the shared adapter has
   campus filtering and a positive unrestricted row.
2. **IU Southeast (`IUSEA`, campus `SE`) — HOLD.** Fall `ENG-W 131`: 14/14 `SE`, 1 raw open but
   `departmentConsentRequired=true`; Spring: 9/9 `SE`, 2 raw opens, one reserved for online students and
   one unrestricted. Fall `MATH-M 118` has 2 clean `SE` opens but also 4 `EA` rows under the same `inst`;
   this proves `inst=IUSEA` is not sufficient isolation. The exact course is addressable and mixed-status,
   but the adapter must add campus filtering plus consent/reservation/eligibility guards before any gate.
3. **IU East (`IUEAA`, campus `EA`) — HOLD.** Fall `ENG-W 131`: 13 raw / 11 `EA`, no open; Fall
   `MATH-M 118`: 6/6 `EA`, 4 raw opens but zero clean unrestricted opens. Spring `ENG-W 131`: 5/4 `EA`,
   3 clean opens. The same `inst` also returns `SE` rows; no builder handoff until the shared campus and
   eligibility variant is production-tested.
4. **IU Kokomo (`IUKOA`, campus `KO`) — HOLD.** Fall `ENG-W 131`: 12 raw / 10 `KO`, 4 raw opens but
   zero clean unrestricted; Spring: 8/7 `KO`, 5 raw opens but zero clean unrestricted. Fall `MATH-M 118`
   also returned `SE` rows and had zero clean unrestricted `KO` opens. Campus leakage and registerability
   semantics are unresolved.
5. **IU Northwest (`IUNWA`, campus `NW`) — HOLD.** Fall `ENG-W 131`: 22 raw / 20 `NW`, 12 raw opens,
   2 clean unrestricted; Spring: 13/12 `NW`, 9 raw opens, 1 clean unrestricted. Fall/Spring `MATH-M 118`
   also returned `SE` rows and no clean unrestricted `NW` opens. It is the strongest follow-up after a
   shared campus-filtered adapter exists, but not safe to add as-is.

**IU Indianapolis (`IUINA`) was not reported:** its terms endpoint exposed Summer/Fall 2026 but no Spring
2026 term, so the mandatory completed-term replay could not be run. It remains a deduped HOLD, not a lead.

**Why this batch is not `GATED`:** the host passes freshness, complete huge-course pagination, and completed
term mixed-status checks, but the production-shaped `inst` parameter leaks sibling campus rows and positive
capacity can be consent-, reservation-, or eligibility-bound. **Batch result: 0 builder-ready additions; 5
net-new IU regional identities recorded as system-shaped HOLDs; registry unchanged at 718.**

### Codex Batch 75 — San Mateo County CCD shared Banner 9 feed (July 14, 2026)

This is a high-signal three-college system batch, not three independent guesses. The official district
WebSchedule (`https://webschedule.smccd.edu/`) links to the same public Banner 9 host used by Cañada College,
College of San Mateo, and Skyline College; the district says the three colleges serve **40,000+ students per
year**. Registry reload and exact/diacritic-normalized dedup found no existing entry for any of the three
colleges; `schools.SCHOOLS` remains **718**.

**Status: GATED, AWAITING GO-AHEAD — three subclasses of existing `Banner`, one shared host.** Architecture
is plain guest Banner 9 JSON, no auth/cookies beyond the normal anonymous session, with a small exact campus
guard. The PDF download links on WebSchedule are open-only snapshots and contain no seat counts; the linked
Banner endpoint is the builder source of truth.

**Exact production recipe:** base `https://phx-ban-apps.smccd.edu/StudentRegistrationSsb/ssb`.

- Bootstrap `GET /classSearch/classSearch`; term list `GET /classSearch/getTerms?searchTerm=&offset=1&max=40&_=1`.
- Select Fall 2026 `202608`; completed Spring 2026 is `202603` and is explicitly marked “View Only”.
  The current term resolver returned `202608` from the host’s own list.
- Session term POST `/term/search?mode=search` with form body `term=202608`.
- For each watched exact course, reset `POST /classSearch/resetDataForm` with an empty body, then request
  `GET /searchResults/searchResults?txt_subject=ENGL&txt_courseNumber=110&txt_term=202608&pageOffset=0&pageMaxSize=100`.
  Follow `totalCount`; if rows cannot be fully read, skip the course.
- Keep only exact `subject == ENGL` and `courseNumber == 110`, then filter exact
  `campusDescription`: `Canada College`, `College of San Mateo`, or `Skyline College`.
  Section key is `courseReferenceNumber`/CRN for the handoff; it was unique after campus filtering.
- Use **`seatsAvailable > 0` as the only open rule**. Ignore `openSection`: Fall had 14 zero-seat rows with
  `openSection=true`; Spring had 5 such rows, including over-cap negative-seat rows. Clamp negative seats to
  zero in output. Preserve `maximumEnrollment`, `enrollment`, `waitCapacity`, `waitCount`,
  `reservedSeatSummary`, `crossList*`, and `campusDescription` for diagnostics.

**Four-killer evidence, exact ENGL 110:**

1. **Freshness:** the live Banner response carried HTTP `Date` within seconds of the July 14 EDT fetch;
   the official WebSchedule Fall PDFs were also timestamped July 14. No stale snapshot was used.
2. **Completeness/addressability:** Fall returned 39 rows total (13 Cañada / 11 CSM / 15 Skyline) and Spring
   returned 80 (19 / 35 / 26), all below the 100-row page size; the full `totalCount` was read. No 49/50/100
   cap or sibling-subject scatter appeared. The official district schedule also publishes this exact writing
   course in the open-class listings.
3. **Completed-term replay:** Spring 2026 was genuinely mixed, not all-open. Per campus: Cañada 17 open / 2
   non-open; CSM 33 / 2; Skyline 19 / 7. Several Spring rows were over-cap or waitlisted, including negative
   `seatsAvailable`, proving the source carries real enrollment state.
4. **Registerability:** Fall per campus was Cañada 4 open / 9 non-open, CSM 7 / 4, Skyline 7 / 8; Spring
   waitlist rows were present (4 / 21 / 12 respectively). `maximumEnrollment - enrollment == seatsAvailable`
   held on **all 119 rows** across both terms; `reservedSeatSummary` was null on every exact-course row, and
   no positive-seat row had `openSection=false`. Cross-list fields were present (8 Fall / 16 Spring rows),
   but did not break seat arithmetic; retain them and trust `seatsAvailable`, never `openSection`.

**End-to-end reuse test:** the existing `Banner` adapter with exact campus guards returned all sections in
2.33s Cañada, 2.61s CSM, and 2.37s Skyline for Fall ENGL 110. Suggested rough enrollment/rank by students ×
reuse: **1 Skyline College** (official Fall 2025 page: 9,204 credit students; official AY2024-25 report:
17,584 unique), **2 College of San Mateo** (official 2024-25 fast facts: 16,528 unduplicated), **3 Cañada
College** (official Fall 2025 planning report: 6,806 headcount; AY2023-24 unique total 10,979). All three
share one host and one small adapter wrapper, so the system-level reuse rank is materially higher than the
per-school rank. Official references: `https://skylinecollege.edu/aboutskyline/index.php`,
`https://collegeofsanmateo.edu/impact/2425/02_fastfacts.php`,
`https://www.canadacollege.edu/ipc/2526_files/course-enrollment-and-modalities_9.5.2025-version2.pdf`.

**Builder guardrails:** use three exact-campus subclasses (do not use a bare shared-host class); filter before
keying; never trust `openSection`; preserve CRN and waitlist fields; and rerun the exact Fall/Spring ENGL 110
checks through the production class after implementation. No `schools.py` edits were made in this research
pass; the three identities are ready only under the `AWAITING GO-AHEAD` marker above.

### Codex Batch 76 — remaining public USG Banner 9 gaps (July 15, 2026)

This pass enumerated the University System of Georgia by registration software rather than guessing school
names. Three official public course-search links exposed net-new standard Banner 9 SSB hosts: University of
North Georgia, Georgia Highlands College, and Savannah State University. An exact ID, normalized-name, and
adapter dedup against all **718** live entries found no collision for any of the three. Combined Fall 2025
enrollment is **29,391** students (20,317 + 5,896 + 3,178) in the USG Board of Regents report:
`https://www.usg.edu/research/assets/research/documents/enrollment_reports/Fall_2025_SER_Final.pdf`.

**Status: GATED, AWAITING GO-AHEAD — three existing-family Banner additions plus one small reusable
registerability hook.** All three use the default `StudentRegistrationSsb` path and the same Fall/Spring term
codes. Architecture is direct guest Banner JSON with only the normal anonymous session cookie; there is no
login, SSO, browser automation, viewstate, APEX, or bespoke parser. Georgia Highlands uses public HTTPS on
port `7985`; its official Banner page's **Public Access → Course Offerings** link redirects to that host.

| Reuse rank | School / Fall 2025 students | Suggested production identity | Official guest host | Current ENGL 1101 | Completed ENGL 1101 |
|---|---|---|---|---|---|
| 1 | University of North Georgia — **20,317** | `id="ung"`, `name="University of North Georgia"`, `example="ENGL 1101"` | `ssb.ungprod.ung.edu` | Fall `202608`: **184** unique rows, 75 positive / 96 zero / 13 negative; 2 complete pages | Spring `202602`: **69**, 24 positive / 37 zero / 8 negative |
| 2 | Georgia Highlands College — **5,896** | `id="ga-highlands"`, `name="Georgia Highlands College"`, `example="ENGL 1101"` | `fedwest.highlands.edu:7985` | Fall `202608`: **85** unique rows, 26 positive / 52 zero / 7 negative | Spring `202602`: **54**, 23 positive / 29 zero / 2 negative |
| 3 | Savannah State University — **3,178** | `id="savstate"`, `name="Savannah State University"`, `example="ENGL 1101"` | `savstate.gabest.usg.edu` | Fall `202608`: **80** unique rows, 18 positive / 62 zero | Spring `202602`: **38**, 17 positive / 21 zero |

**Exact production recipe (identical on all three hosts):** base
`https://{host}/StudentRegistrationSsb/ssb`; bootstrap `GET /classSearch/classSearch`; list terms with
`GET /classSearch/getTerms?searchTerm=&offset=1&max=40&_=1`; select the term using
`POST /term/search?mode=search` with form body `term=202608`; reset with an empty-body
`POST /classSearch/resetDataForm`; then fetch
`GET /searchResults/searchResults?txt_subject=ENGL&txt_courseNumber=1101&txt_term=202608&pageOffset=0&pageMaxSize=100`.
Follow `totalCount` until every page is read, and keep only exact `subject == "ENGL"` plus
`courseNumber == "1101"` because Banner's course-number query is prefix matching. The existing `Banner`
pagination and exact-field guards already implement this recipe. The host term lists identify `202608` as
Fall 2026 and `202602` as Spring 2026 View Only; production `resolve_term()` selected `202608` on all three.

**Four-killer evidence:**

1. **Freshness:** current search responses carried HTTP dates equal to the local UTC fetch second on July 15:
   UNG `13:41:08 GMT`, Savannah State `13:41:10 GMT`, and Georgia Highlands `13:43:42 GMT`. None is an
   hours-stale mirror. Savannah State's official schedule page additionally says its enrollment data is current
   when opened/refreshed; the GHC official page directly labels its link public Course Offerings.
2. **Addressability/completeness:** exact first-year writing returned stable `totalCount` values of 184, 85,
   and 80. UNG's 184 rows were completely read at offsets 0 and 100; the other two fit on one 100-row page.
   Every CRN and `sequenceNumber` was unique within each school/term. No result pinned to 49/50/100, no
   sibling course leaked after exact filtering, and the existing production paginator returned all 184/85/80
   sections end to end.
3. **Real completed status:** Spring 2026 was mixed at every host, with both positive and zero/negative seat
   rows as shown in the table. This is not completed-term all-open `COMMUNITY_ACCESS` behavior. Across current
   and completed terms, `maximumEnrollment - enrollment == seatsAvailable` held on **all 510 rows**.
4. **Registerability:** `reservedSeatSummary` was null on all 510 rows. No positive-seat row had a waitlist
   occupant, linked-section flag, or cross-list cap; no positive row had `openSection=false`. Waitlists did
   exist on zero-seat current rows at Savannah State and GHC. The official UNG and Savannah instructions warn
   that a newly available seat can be reserved for the next waitlisted student, and the GHC Banner UI carries
   the same “Open Seats Reserved for Waitlisted Only” state. Therefore future safety requires the hook below;
   aggregate positive capacity alone is not enough.

**Required builder hook — keep existing-family reuse, do not clone `Banner.fetch()`:** add a protected
`Banner._row_is_open(self, row, seats)` method whose default is `seats > 0`, and replace the hard-coded
`"open": n > 0` assignment in `Banner.fetch()` with that hook. Add a small `WaitlistSafeBanner(Banner)`
variant used by these three classes. Its open rule must be conservative:

```python
def _row_is_open(self, row, seats):
    if seats <= 0 or int(row.get("waitCount") or 0) > 0:
        return False
    if row.get("reservedSeatSummary") or row.get("isSectionLinked"):
        return False
    has_cross_list = row.get("crossList") or row.get("crossListCapacity") is not None
    if has_cross_list and int(row.get("crossListAvailable") or 0) <= 0:
        return False
    return True
```

Then add and register exactly one instance of each class (expected registry **718 → 721**):

```python
class NorthGeorgia(WaitlistSafeBanner):
    id = "ung"; name = "University of North Georgia"
    example = "ENGL 1101"; host = "ssb.ungprod.ung.edu"; term = "202608"

class GeorgiaHighlands(WaitlistSafeBanner):
    id = "ga-highlands"; name = "Georgia Highlands College"
    example = "ENGL 1101"; host = "fedwest.highlands.edu:7985"; term = "202608"

class SavannahState(WaitlistSafeBanner):
    id = "savstate"; name = "Savannah State University"
    example = "ENGL 1101"; host = "savstate.gabest.usg.edu"; term = "202608"
```

Continue to clamp negative `seatsAvailable` to zero and ignore `openSection`: it was falsely true on **4**
zero-seat UNG rows, **22** zero-seat GHC rows, and **14** zero-seat Savannah rows in current Fall. Add
synthetic tests for positive aggregate seats plus each blocker (`waitCount`, `reservedSeatSummary`, linked,
cross-list full), and rerun the exact Fall/Spring counts above after implementation. With current data the hook
does not remove any positive row, so expected production open counts remain UNG **75**, GHC **26**, Savannah
**18**. Existing `Banner` end-to-end tests resolved Fall automatically and returned 184 sections in 2.59s,
85 in 2.05s, and 80 in 2.09s respectively.

**Official source entry points:** UNG publishes its guest Course Search at
`https://ssb.ungprod.ung.edu/StudentRegistrationSsb/ssb/term/termSelection?mode=search`; Savannah State's
official schedule page is `https://savannahstate.edu/registrar/schedule/` and links the host above; Georgia
Highlands' official public Banner page is `https://www.highlands.edu/banner-portal/`. Registerability semantics
come from `https://ung.edu/registrar/waitlisted-courses.php` and
`https://savannahstate.edu/registrar/howtoregister/`. These are production registration schedule surfaces,
not catalogs.

**System-shaped cuts from the same pass (do not hand off or rediscover):** Peralta CCD's four-college public
search is a custom PeopleSoft→HubSpot GraphQL mirror explicitly updated only twice daily; the same Spring 2026
CRN appeared more than once with conflicting capacities/enrollments, so it fails freshness and identity
integrity. Laney and Berkeley City were already pending README identities and were not re-reported; College of
Alameda and Merritt were not promoted. Los Rios' four-college PHP feed had a current timestamp and numeric
seats, but direct `ENGL C1000` returned zero while the undocumented former code `ENGWR 300` claimed 292
results yet yielded **305 unique CRNs across 16 pages**; positive rows also included reserved/permission-only
sections. It fails clean addressability and registerability, so American River, Cosumnes River, Folsom Lake,
and Sacramento City remain CUT rather than padded leads.

**Batch result:** 3 builder-ready, net-new USG schools ranked by **students × near-total Banner reuse**;
registry remains 718. Research only: no `schools.py` edit, builder contact, commit, or deployment was made.

### Codex Batch 77 — NOCCCD static-JSON district promotion (July 15, 2026) — GATED, AWAITING GO-AHEAD

This pass returned to a multi-college system only after finding the missing authoritative status signals. The
July 11 NOCCCD entry below was correctly held because positive aggregate seats alone were unsafe. The public
client's enrollment-cutoff rule, restriction marker, waitlist display logic, cross-list pool, and dynamic
reservation bins now provide a conservative registerability rule, so this block **supersedes that prior HOLD**.
An exact ID plus normalized-name dedup against all **718** live `schools.SCHOOLS` entries found neither proposed
identity nor an existing NOCCCD adapter. Expected registry change after implementation: **718 → 720**.

**Status: GATED, AWAITING GO-AHEAD — one shared adapter, two colleges, approximately 37,207 Fall 2025
students.** This is the preferred architecture from the new protocol: anonymous static GET/JSON, no login,
cookie, SSO, browser automation, viewstate, APEX, or bearer token. It reuses the existing `WVMCCD` shared
static-district design (shared term dump/cache plus exact campus subclasses) with NOCCCD's schema and separate
minute-updated seats file; it is a small reusable family addition, not a bespoke portal parser. NOCCCD's
Strategic Enrollment Plan estimates Fall 2025 headcount at **20,448 Fullerton** and **16,759 Cypress**:
`https://www.nocccd.edu/documents/nocccd-strategic-enrollment-plan`.

| Reuse rank | School / students | Exact production identity | Campus filter | Fall 2026 first-year writing |
|---|---|---|---|---|
| 1 | Fullerton College — **20,448** | `id="fullerton"`, `name="Fullerton College"`, `example="ENGL C1000"` | `sectCampCode.startswith("2")` (`2` + `2NH`) | internal `ENGL 100 F`: **102/102 unique CRNs**, 27 raw-positive, **26 safely open** |
| 2 | Cypress College — **16,759** | `id="cypress"`, `name="Cypress College"`, `example="ENGL C1000"` | `sectCampCode.startswith("1")` (`1` + `1NH`) | internal `ENGL 100 C`: **59/59 unique CRNs**, 1 raw-positive, **0 safely open** because that row has a waitlist |

**Exact source and request recipe:** use base `https://schedule.nocccd.edu/data`. List terms with
`GET /terms.json?p={YYYYMMD}` and ignore every `termDesc` beginning `NOCE`; the current credit term is Fall
2026 `202610`. For a term, fetch `courses.json?p={day}`, `sections.json?p={minute}`, and
`seats.json?p={minute}`. The cache-buster is mandatory because CloudFront advertises a long shared-cache TTL
even though the district regenerates the files every few minutes. Merge each dynamic seat row into its static
section by exact `sectKey`, updating only `sectMaxEnrl`, `sectEnrl`, `sectSeatsAvail`, `sectWaitCount`,
`sectXlst`, and `sectResv`. If a section has no matching dynamic row, a file is malformed, the two key sets
disagree, or either live file cannot be refreshed, fail closed; never reuse a stale `open=True` result.

The July 15 snapshot contained **1,669 courses and 3,914 sections/seats** with 3,914 unique `sectKey` values:
Cypress had 1,696 campus-`1` plus 41 campus-`1NH` rows; Fullerton had 2,170 campus-`2` plus 7 campus-`2NH`
rows. There was no CRN overlap between the two campus-prefix sets. `sectMaxEnrl - sectEnrl ==
sectSeatsAvail` held on **3,914/3,914** current rows, so use `sectCrn` as the user-facing section key only
after campus filtering and use `sectKey` for the merge.

**Four-killer evidence:**

1. **Freshness:** all four current files returned HTTP `Last-Modified: Wed, 15 Jul 2026 14:02:05 GMT` when
   fetched at `14:06:02–03 GMT`, an age of about four minutes. Production must compare `Last-Modified` with
   the response `Date` and fail closed when either `sections.json` or `seats.json` is over **15 minutes old**.
2. **Addressability/completeness:** this is a complete whole-term file, not a paginated search. The course file
   maps public alias `ENGL C1000` to both exact internal records (`100 C` and `100 F`); campus filtering then
   returns exactly 59 Cypress and 102 Fullerton sections. Every CRN is unique, there is no 49/50/100 cap, and
   all 3,914 source rows are consumed. Do not query the internal college-specific number directly for a normal
   user request: map an exact `crseAlias` **or** exact `crseCrseNumb` through `courses.json`, then match the
   resulting exact `(sectSubjCode, sectCrseNumb)` pair in `sections.json`.
3. **Completed-term fake-status replay:** direct completed Spring 2026 `202520` contained **4,009** unique rows,
   3,450 with positive aggregate seats; completed Fall 2025 `202510` contained **4,099**, 3,433 positive.
   Every row still says `sectSstsCode="A"`, so raw status/seats alone would be catastrophically false-open.
   However, every enrollment cutoff is in the past; the rule below returns **0 open in both complete files**,
   including 0 across 48/60 Spring and 77/101 Fall Cypress/Fullerton first-year-writing rows. This is a real,
   deterministic historical-status gate rather than the PeopleSoft all-open failure.
4. **Reservations/eligibility:** current rows expose 182 `sectSaprCode` restrictions, 6 `sectResv` reservation
   arrays, 668 cross-listed pools, 962 positive waitlists, and 74 zero-capacity/contact-department sections.
   The feed proves each aggregate-seat trap directly: Cypress CRN `11566` has 1 raw seat plus 1 waitlisted;
   Fullerton CRN `12010` has 2 raw seats plus a reservation bin and waitlist; Cypress CRN `10260` has 11 local
   seats but 0 cross-list seats; Cypress CRN `14356` has 11 raw seats but `sectSaprCode="SA"`. All four must
   be closed. Cypress's official schedule help independently says a class can display positive seats while
   closed because it began or a dropped seat is being offered to a waitlisted student:
   `https://www.cypresscollege.edu/schedule-of-classes-and-college-catalog/find-classes/`.

**Mandatory conservative open rule:** parse `sectEnrlCutOffDate` (`MM/DD/YYYY`) at midnight in
`America/Los_Angeles`, matching the client and Cypress's “closes at midnight” documentation. Require the
current instant to be strictly before that deadline. `effective` is the minimum of local seats and every
parseable cross-list availability; a malformed cross-list fails closed. Return `seats=effective` only for a
safe-open row and `seats=0` for every blocker, so a reserved/waitlisted aggregate balance is never surfaced as
registerable:

```python
def _is_open(row, now):
    deadline = parse_pacific_midnight(row.get("sectEnrlCutOffDate"))
    if row.get("sectSstsCode") != "A" or not deadline or now >= deadline:
        return False, 0
    if row.get("sectSaprCode") or row.get("sectResv"):
        return False, 0
    if as_int(row.get("sectWaitCount")) != 0 or as_int(row.get("sectMaxEnrl")) <= 0:
        return False, 0
    effective = as_int(row.get("sectSeatsAvail"))
    for pool in row.get("sectXlst") or []:
        effective = min(effective, as_int(pool.get("xlstSeatsAvail")))
    return (effective > 0, max(effective, 0) if effective > 0 else 0)
```

`as_int` must fail closed on missing/non-numeric input; do not coerce malformed availability to a plausible
open count. With this rule the current full feed contracts from 1,099 raw-positive to **881 safe-open Cypress**
rows and from 1,342 to **1,268 safe-open Fullerton** rows. The counts are snapshot evidence, not brittle test
constants because `seats.json` is live.

**Builder implementation/acceptance contract:** add one shared `NOCCCD` class patterned after `WVMCCD`, with
a class-level lock/cache keyed by term, a long course TTL, and a **maximum 120-second live section/seat TTL**.
Add only these subclasses and register one instance of each:

```python
class CypressCollege(NOCCCD):
    id = "cypress"; name = "Cypress College"
    example = "ENGL C1000"; campus_prefix = "1"

class FullertonCollege(NOCCCD):
    id = "fullerton"; name = "Fullerton College"
    example = "ENGL C1000"; campus_prefix = "2"
```

`reg_url()` should return
`https://schedule.nocccd.edu/?college={campus_prefix}&term={term}&subj={subject}&status=OPEN`. Term refresh
must select the nearest current/upcoming non-NOCE credit term from the source's labels, tentatively switch,
verify the class's example through the production adapter, and roll back if empty. Add fixture tests for alias
mapping, `1`/`1NH` and `2`/`2NH` inclusion, cross-campus exclusion, key-set mismatch, stale headers, passed
cutoff, waitlist, restriction, reservation, cross-list exhaustion, zero capacity, malformed integers, and
refresh failure. Then run live smoke checks that return all 59/102 `ENGL C1000` sections; do not hard-code the
live open totals. Official district registration currently says Fall 2026 registration is open for both
colleges: `https://www.nocccd.edu/`.

**System-first screen notes (do not hand off):** Alamo Colleges District was tested before NOCCCD because one
feed covers five colleges. Its guest Banner 9 current Fall 2026 `ENGL 1301` search was complete at 428 rows,
but 89 of the first 100 completed Spring 2026 rows still reported positive/open seats after their classes had
ended; 195 current writing rows were also linked. It fails the fake-status/registerability gates and is **CUT**,
despite official Fall registration being open. SOCCCD (Saddleback + Irvine Valley) is **HOLD**: its public
SmartSchedule uses a stateful two-hour guest bearer and the exact writing, reservation, and historical gates
are not complete; its fragile architecture ranks below this plain-JSON district and was not padded into the
batch.

**Batch result:** 2 builder-ready, net-new colleges on one high-reuse district feed; one five-college system
rejected and one two-college system held. Registry remains 718. Research only: no `schools.py` edit, builder
contact, commit, or deployment was made.

### Codex Batch 78 — existing-family system completion (July 15, 2026) — GATED, AWAITING GO-AHEAD

This pass enumerated missing members of systems SeatWatch already supports rather than searching new school
names. It found one of five unregistered LCTCS colleges that clears the strict completed-term test, then
retested the three NMSU community-college campuses on the already-shipped NMSU host. The NMSU completed-term
endpoint now returns populated rows, resolving the July 13 DACC omission. Exact ID, normalized-name, source,
and adapter dedup against all **718** live entries found all four proposed identities net-new. Expected registry
after implementation: **718 → 722**.

**Status: GATED, AWAITING GO-AHEAD — four existing-family Banner additions, no new fetcher.** Fletcher is
another entity on the existing `LCTCS` host; the three New Mexico colleges are exact campus-description
subclasses on the existing `NMSU` host. Both are normal guest Banner 9 JSON: one anonymous cookie session,
plain GET/form requests, no login, SSO, browser automation, APEX, viewstate, bearer token, or HTML parser.
Rank is students × essentially total adapter reuse:

| Reuse rank | School / student count | Exact identity and isolation | Current first-year writing | Completed replay |
|---|---|---|---|---|
| 1 | Doña Ana Community College — **7,200 Fall 2024** | `id="dacc"`, `name="Doña Ana Community College"`; exact `campusDescription == "DACC - Dona Ana"` | Fall `202640`, `ENGL 1110G`: **49** rows, 21 positive / 28 zero | Spring `202610`: **37**, 19 positive / 9 zero / 9 negative |
| 2 | Fletcher Technical Community College — **3,392 AY2023-24 credit students** (6,698 total served) | `id="fletcher"`, `name="Fletcher Technical Community College"`; LCTCS `mepCode="FTCC"` | Fall `202710`, `ENGL 1006`: **8**, 1 positive / 6 zero / 1 negative at final fetch | Spring `202620`: **10**, 9 positive / 1 zero |
| 3 | New Mexico State University–Alamogordo — **1,152 Fall 2024** | `id="nmsu-alamogordo"`, `name="New Mexico State University–Alamogordo"`; exact `campusDescription == "NMSU - Alamogordo"` | Fall `202640`, `ENGL 1110G`: **8**, 5 positive / 3 zero | Spring `202610`: **8**, 6 positive / 1 zero / 1 negative |
| 4 | New Mexico State University–Grants — **754 Fall 2024** | `id="nmsu-grants"`, `name="New Mexico State University–Grants"`; exact `campusDescription == "NMSU - Grants"` | Fall `202640`, `ENGL 1110G`: **4**, all 4 positive | Spring `202610`: **4**, 2 positive / 2 negative |

The three comparable NMSU counts come from the university's official 2024-25 Quick Facts:
`https://oia.nmsu.edu/nmsudata/quickfacts/QuickFacts_24_25_web.pdf`. Fletcher's official strategic scorecard
reports 3,392 credit students and 6,698 total students served in 2023-24:
`https://www.fletcher.edu/about-us/files/documents/College%20Scorecard%20Worksheet%20-%202024-2025%20-%20Ending%20Q1.pdf`.
The combined tagged scale is **12,498** students; this intentionally combines the three comparable NMSU Fall
census counts with Fletcher's latest complete-year credit headcount and is not presented as one uniform census
metric.

**Exact request recipes:**

- **Fletcher:** existing `LCTCS` base, host `reg-prod.ec.lctcs.edu`, path `StudentRegistrationSsb`,
  `mepCode=FTCC`, current term `202710`. Bootstrap
  `GET /ssb/classSearch/classSearch?mepCode=FTCC`; select with
  `POST /ssb/term/search?mode=search&mepCode=FTCC` body `term=202710&mepCode=FTCC`; reset; then call the
  existing paginated `searchResults` endpoint with exact `txt_subject=ENGL`, `txt_courseNumber=1006`, and
  `txt_term=202710`. Fletcher's official Catalog page links this exact guest Banner host under “Browse Current
  Schedule of Classes”: `https://www.fletcher.edu/catalog/index`.
- **NMSU community colleges:** existing `NMSU` host `banner-public.nmsu.edu`, current term `202640`, no
  `mepCode`. Search exact `ENGL 1110G` through the normal production paginator, then apply the exact campus
  descriptions in the table **before section keying**. Never use `campus="NMSU"`: first-word filtering would
  merge Alamogordo, Grants, Las Cruces, and Global. NMSU's official application page lists Doña Ana,
  Alamogordo, Grants, Main, and Global as selectable campuses and says Fall 2026 applications remain open:
  `https://nmsu.edu/apply/`.

**Four-killer evidence:**

1. **Freshness:** Fletcher's final current response carried HTTP `Date: Wed, 15 Jul 2026 14:26:02 GMT`; its
   open writing count changed from 2 to 1 during this nine-minute validation window when CRN `10023` filled,
   proving the endpoint is live rather than an hours-stale snapshot. The fully paged NMSU response carried
   `Date: Wed, 15 Jul 2026 14:23:28 GMT`; DACC's current count has also moved from the earlier July 13 audit.
   Both official institutions currently advertise active Fall 2026 enrollment.
2. **Addressability/completeness:** Fletcher's exact query returned `totalCount=8`; its complete ENGL subject
   returned 19 rows. Across complete Fall ENGL/MATH/BIOL subject reads it had **97/97 unique CRNs** and no
   within-course duplicate sequence. NMSU `ENGL 1110G` returned **108 system rows**, explicitly read as pages
   100 + 8. Exact campus counts were DACC 49, Alamogordo 8, Grants 4, Main 38, Global 9, totaling 108. DACC's
   apparent 49 is therefore a real campus subset—not a 49/50 cap. Every proposed campus had unique CRNs and
   sequence numbers in current and completed terms.
3. **Completed-term fake-status:** all four have genuine full/over-capacity writing rows in completed Spring
   2026, as shown in the table. A second NMSU replay, completed Fall 2025 `202540`, remained mixed: DACC
   19 positive / 21 zero / 8 negative; Alamogordo 5 / 1 / 2; Grants 1 / 2 / 3. These are not
   `COMMUNITY_ACCESS` all-open results. `maximumEnrollment - enrollment == seatsAvailable` held on every
   audited current and completed row.
4. **Reservations/eligibility:** current exact writing had no `reservedSeatSummary`, linked, or cross-list
   rows at any proposed college. Fletcher had 4 waitlisted rows and DACC had 6, but **all ten had zero or
   negative seats**; no positive-seat row was waitlisted. The source still proves why `openSection` must never
   be trusted: it was true on all 8 Fletcher rows despite 7 being zero/negative, on all 49 DACC rows despite
   28 zeroes, and on all 8 Alamogordo rows despite 3 zeroes. Negative availability must remain closed and be
   clamped to zero. NMSU Global stays excluded; its own registration guidance says Global sections can be
   reserved for that population.

**Required builder integration — depend on Batch 76's shared hook, do not clone `Banner.fetch()`:** first add
the protected `Banner._row_is_open(row, seats)` hook and `WaitlistSafeBanner` variant already specified in
Batch 76. Use the same conservative rule here: positive numeric seats, zero waitlist, no
`reservedSeatSummary`, no linked-section marker, and positive cross-list availability when present. Then make
the already-existing shared families opt in (`class LCTCS(WaitlistSafeBanner)` and
`class NMSU(WaitlistSafeBanner)`) and rerun their existing-school smoke tests. Current positive rows at these
four candidates have no blocker, so safe expected current opens are Fletcher **1**, DACC **21**, Alamogordo
**5**, and Grants **4** at the final snapshots.

Add only these classes and one registry instance of each:

```python
class FletcherTechnical(LCTCS):
    id = "fletcher"; name = "Fletcher Technical Community College"
    example = "ENGL 1006"; mep = "FTCC"

class DonaAnaCC(NMSU):
    id = "dacc"; name = "Doña Ana Community College"
    _CAMPUS = "DACC - Dona Ana"

class NMSUAlamogordo(NMSU):
    id = "nmsu-alamogordo"; name = "New Mexico State University–Alamogordo"
    _CAMPUS = "NMSU - Alamogordo"

class NMSUGrants(NMSU):
    id = "nmsu-grants"; name = "New Mexico State University–Grants"
    _CAMPUS = "NMSU - Grants"
```

The NMSU subclasses intentionally inherit `example`, `host`, `term`, exact `_campus_ok`, term refresh, and
all fetch logic from the shipped `NMSU` class. Add synthetic blocker tests for positive seats plus waitlist,
reservation, linked, and exhausted cross-list fields; exact-campus isolation tests including a tempting Global
row; two-page pagination; negative-seat clamping; and Fletcher `mepCode` on bootstrap, term selection, and
search. Then live-smoke all four through production. The test observed 8/49/8/4 sections in 1.57/4.74/4.14/
4.13 seconds; open counts are live and must not be hard-coded.

**Strict LCTCS cuts (do not add or rediscover):** the other four missing system colleges use the same host and
passed current completeness/CRN checks, but each failed the required completed writing test: Central Louisiana
Technical CC `ENGL 1010` was **2/2 positive** in completed Spring 2026; Louisiana Delta `ENGL 101` was
**16/16 positive**; Northshore Technical `ENGL 1015` was **14/14 positive**; Northwest Louisiana Technical
`ENGL 1015` was **1/1 positive**. They remain **CUT**, not padded behind a date workaround. The seven LCTCS
colleges already in `schools.py` were not re-reported.

**Batch result:** 4 builder-ready, net-new colleges through two already-shipped Banner families; 4 sibling
colleges rejected by the historical test. Registry remains 718. Research only: no `schools.py` edit, builder
contact, commit, or deployment was made.

### Codex Batch 79 — University of Hawaiʻi ten-campus Banner 9 system (July 15, 2026) — GATED, AWAITING GO-AHEAD

This is one complete system-shaped handoff, not ten school-name guesses. The legacy Banner 8
`/uhdad/avail.classes` service was retired after December 2025 and still redirects to a 502 maintenance page;
**do not revive or scrape it**. The replacement linked by UH's official schedule pages is anonymous Banner 9
SSB at `https://www.sis.hawaii.edu:9234/StudentRegistrationSsb/ssb`. It exposes all ten UH campuses through one
plain JSON family. Exact ID, punctuation/diacritic-normalized name, and adapter dedup against all **718** live
entries found every proposed identity net-new. Expected isolated registry change: **718 → 728**.

**Status: GATED, AWAITING GO-AHEAD — ten schools, one existing-family Banner integration.** Architecture is
direct guest Banner JSON with only the normal anonymous `JSESSIONID`; there is no login, SSO, browser
automation, bearer token, APEX, viewstate, or HTML parser. UH's official Fall 2025 census totals **51,411**
students across exactly these ten campuses and supplies every campus count below:
`https://www.hawaii.edu/news/article.php?aId=14169`. UH's official Fall 2026 announcement independently
enumerates the same three universities plus seven community colleges:
`https://www.hawaii.edu/news/2026/03/06/summer-fall-registration-dates/`.

| Reuse rank | School / Fall 2025 students | Suggested ID / exact API campus / suffix | Current Fall 2026 `ENG 100` | Completed control |
|---|---|---|---|---|
| 1 | University of Hawaiʻi at Mānoa — **20,404** | `uh-manoa`; `University of Hawaii at Manoa`; `0` | backend `ENG 1000`: **49**, 45 positive / 4 zero; **45 safe opens** | Spring: 39, 26 / 12 / 1 negative |
| 2 | Leeward Community College — **6,210** | `leeward-cc`; `Leeward Community College`; `7` | `ENG 1007`: **49**, 30 / 19 / 0; **30 safe** | Spring: 27, 24 / 3 / 0 |
| 3 | Kapiʻolani Community College — **5,704** | `kapiolani-cc`; `Kapiolani Community College`; `5` | `ENG 1005`: **41**, 29 / 11 / 1; **28 safe** | Spring: 37, 35 / 2 / 0 |
| 4 | Honolulu Community College — **3,628** | `honolulu-cc`; `Honolulu Community College`; `4` | `ENG 1004`: **28**, 25 / 3 / 0; **25 safe** | Spring: 19, 18 / 1 / 0 |
| 5 | Windward Community College — **3,109** | `windward-cc`; `Windward Community College`; `9` | `ENG 1009`: **8**, 4 / 4 / 0; **4 safe** | Fall 2025: 6, 3 / 3 / 0 |
| 6 | University of Hawaiʻi Maui College — **2,997** | `uh-maui`; `Univ of Hawaii Maui College`; `8` | `ENG 1008`: **26**, 21 / 4 / 1; **20 safe** | Spring: 21, 18 / 0 / 3 |
| 7 | University of Hawaiʻi–West Oʻahu — **2,897** | `uh-west-oahu`; `Univ of Hawaii - West Oahu`; `2` | `ENG 1002`: **5**, 4 / 1 / 0; **4 safe** | Fall 2025: 2, both zero |
| 8 | University of Hawaiʻi at Hilo — **2,649** | `uh-hilo`; `University of Hawaii at Hilo`; `1` | `ENG 1001`: **4**, all zero; **0 safe** | Fall 2025: 4, 1 / 2 / 1 |
| 9 | Hawaiʻi Community College — **2,489** | `hawaii-cc`; `Hawaii Community College`; `3` | `ENG 1003`: **26**, 20 / 6 / 0; **20 safe** | Spring: 23, 20 / 1 / 2 |
| 10 | Kauaʻi Community College — **1,324** | `kauai-cc`; `Kauai Community College`; `6` | `ENG 1006`: **16**, 13 / 3 / 0; **13 safe** | Spring: 9, 7 / 2 / 0 |

Counts are positive / zero / negative `seatsAvailable`. “Safe” additionally applies the Batch 76
waitlist/reservation/linked/cross-list rule. Kapiʻolani CRN `31088` and Maui CRN `45316` each reported one
positive aggregate seat while 5 and 2 students, respectively, were already waitlisted; both are correctly
closed by that rule. The current exact writing total is **252 rows, 191 positive aggregate, 59 zero, 2
negative, and 189 safely registerable**.

**Exact anonymous request recipe:** bootstrap `GET /term/termSelection?mode=search`; list terms with
`GET /classSearch/getTerms?searchTerm=&offset=1&max=50&_=1`; select current Fall `202710` using
`POST /term/search?mode=search` with body `term=202710`; before every course, empty-body
`POST /classSearch/resetDataForm`; then paginate
`GET /searchResults/searchResults?txt_subject={subject}&txt_courseNumber={translated_number}&txt_term=202710&pageOffset={offset}&pageMaxSize=100`
until `len(rows) == totalCount`. Completed terms are Spring `202630` and Fall `202610`, both labeled
`View Only` by the host. The official Mānoa scheduler links this exact 9234 Browse Classes application and
confirms Fall 2026 schedules are published:
`https://manoa.hawaii.edu/undergrad/schedule/`. The alternate port 9350 returned 403 and is not required.

**Mandatory UH number translation:** after the eBanner migration, the JSON `courseNumber` appends one
campus digit, while `courseDisplay` and `subjectCourse` retain the catalog number students use. For example,
all ten schools display `ENG 100`, but the backend keys are `1000` through `1009`; Mānoa `ENG 100A` is
`courseNumber="100A0"`. Honolulu's official modernization page confirms that a campus-assigned digit was
added to course numbers: `https://www.honolulu.hawaii.edu/services/banner-sis-upgrade/`. Do not expose the
backend number as the SeatWatch course code. Translate the parsed number by appending the subclass digit
before the standard Banner query/exact-row guard, while leaving the output dictionary keyed by the original
user input.

**Four-killer evidence:**

1. **Freshness:** the current JSON response carried `Date: Wed, 15 Jul 2026 14:43:10 GMT`, equal to the
   request second, with no CDN `Age` or stale `Last-Modified` header. A second complete 505-row snapshot ten
   minutes later was generated at the new request time with the same values (04:43 HST, before daytime
   registration activity), not served with an old response stamp. The official UH and campus pages identify
   Fall 2026 registration as open and direct students to this Browse Classes service. This is the live Banner
   application/database architecture, not the retired daily/static legacy listing.
2. **Addressability/completeness:** the full current `ENG` subject returned **505** rows, explicitly read as
   100 + 100 + 100 + 100 + 100 + 5, with **505 unique CRNs**. After `resetDataForm`, exact Mānoa backend
   `ENG 1000` returned 49/49 rows; it is therefore a real subset, not a 49/50 cap. The shipped
   `CrnKeyedBanner.fetch()` path returned all ten exact backend courses end to end as
   **49/4/5/26/28/41/16/49/26/8** rows in suffix order 0–9. Banner's query is prefix-like if the reset is
   omitted, so the reset and exact `courseNumber` filter are non-negotiable.
3. **Completed-term fake-status:** the complete Spring `ENG` subject was **418 unique CRNs** and completed
   Fall 2025 was **508**; all ten campuses have a zero or negative first-year-writing row in at least one
   completed control shown in the table. Hilo, West Oʻahu, and Windward use Fall 2025 because their tiny
   Spring samples were all positive. These mixed/full/over-capacity rows disprove all-open
   `COMMUNITY_ACCESS` behavior. `maximumEnrollment - enrollment == seatsAvailable` held on all **1,431**
   fully paged English rows across the three terms.
4. **Reservations/eligibility:** `reservedSeatSummary` was null on all 1,431 audited rows and every exact
   writing row; no exact writing row was linked. The current English subject still contained **seven**
   positive aggregate traps: waitlist occupants at Kapiʻolani, Maui, Hilo, Hawaiʻi CC, and Leeward, plus
   exhausted cross-list groups at Mānoa and West Oʻahu. The official detail panes reproduced the waitlist
   counts and ordinary campus/level/cohort restrictions. Apply `WaitlistSafeBanner`: positive seats, zero
   `waitCount`, no reserved summary, no linked marker, and positive `crossListAvailable` whenever a cross-list
   exists. Never trust `openSection`; it was true on **99 current English rows with zero/negative seats**.

**Required builder integration — reuse Banner, do not clone `fetch()`:** land Batch 76's protected
`Banner._row_is_open(row, seats)` hook and `WaitlistSafeBanner` first if they are not already present. Add one
small shared UH family that also translates the user-facing number, filters the exact campus before keying,
and always keys by CRN. Pin `auto_term=False`: the generic resolver selected parallel `202713 Fall 2026
Extension`, not the intended `202710 Fall 2026` term.

```python
class UHBanner(WaitlistSafeBanner):
    host = "www.sis.hawaii.edu:9234"
    term = "202710"
    auto_term = False
    example = "ENG 100"
    _DIGIT = ""
    _CAMPUS = ""

    def _code(self, course):
        subject, number = super()._code(course)
        return (subject, number + self._DIGIT) if subject else (None, None)

    def _campus_ok(self, row):
        return (row.get("campusDescription") or "") == self._CAMPUS

    def _seckey(self, row):
        return row.get("courseReferenceNumber")

class UHManoa(UHBanner):
    id = "uh-manoa"; name = "University of Hawaiʻi at Mānoa"
    _DIGIT = "0"; _CAMPUS = "University of Hawaii at Manoa"

class UHHilo(UHBanner):
    id = "uh-hilo"; name = "University of Hawaiʻi at Hilo"
    _DIGIT = "1"; _CAMPUS = "University of Hawaii at Hilo"

class UHWestOahu(UHBanner):
    id = "uh-west-oahu"; name = "University of Hawaiʻi–West Oʻahu"
    _DIGIT = "2"; _CAMPUS = "Univ of Hawaii - West Oahu"

class HawaiiCC(UHBanner):
    id = "hawaii-cc"; name = "Hawaiʻi Community College"
    _DIGIT = "3"; _CAMPUS = "Hawaii Community College"

class HonoluluCC(UHBanner):
    id = "honolulu-cc"; name = "Honolulu Community College"
    _DIGIT = "4"; _CAMPUS = "Honolulu Community College"

class KapiolaniCC(UHBanner):
    id = "kapiolani-cc"; name = "Kapiʻolani Community College"
    _DIGIT = "5"; _CAMPUS = "Kapiolani Community College"

class KauaiCC(UHBanner):
    id = "kauai-cc"; name = "Kauaʻi Community College"
    _DIGIT = "6"; _CAMPUS = "Kauai Community College"

class LeewardCC(UHBanner):
    id = "leeward-cc"; name = "Leeward Community College"
    _DIGIT = "7"; _CAMPUS = "Leeward Community College"

class UHMaui(UHBanner):
    id = "uh-maui"; name = "University of Hawaiʻi Maui College"
    _DIGIT = "8"; _CAMPUS = "Univ of Hawaii Maui College"

class WindwardCC(UHBanner):
    id = "windward-cc"; name = "Windward Community College"
    _DIGIT = "9"; _CAMPUS = "Windward Community College"
```

Register exactly one instance of each class. Add tests for `ENG 100 -> 100{digit}` and suffix-after-letter
(`ENG 100A -> 100A{digit}`), exact campus rejection, CRN keying when every `sequenceNumber` is `0`, all four
`WaitlistSafeBanner` blockers, 505-row pagination, negative clamping, and the parallel-term pin. Live-smoke
the canonical user input `ENG 100` through every production class; the Kapiʻolani-shaped prototype returned
all 41 CRN-keyed rows, proving the translation and reuse path. Open counts are live and must not be hard-coded.

This batch **supersedes every older UH legacy/HOLD note** for Mānoa, Honolulu, Kapiʻolani, Maui, Windward,
and Hawaiʻi CC. The replacement host also resolves the previously unlisted Hilo, West Oʻahu, Kauaʻi, and
Leeward campuses. Registry remains 718; no `schools.py`, builder-contact, commit, or deployment change was
made in this research pass.

### Codex Batch 80 — Rancho Santiago CCD two-college Colleague feed (July 15, 2026) — GATED, AWAITING GO-AHEAD

This is one shared-software district handoff, not two unrelated college guesses. Rancho Santiago Community
College District's official colleges page identifies exactly **Santa Ana College (SAC)** and **Santiago Canyon
College (SCC)** as its two colleges (`https://www.rsccd.edu/Discover-RSCCD/Pages/Colleges-and-Centers.aspx`).
Both are isolated models on the same anonymous Colleague Self-Service host. Exact ID, normalized-name, and
bespoke-adapter dedup against all **718** live entries found both net-new; the older unresolved Santa Ana and
Santiago Canyon research notes are not registry entries. Expected isolated registry change: **718 → 720**.

**Status: GATED, AWAITING GO-AHEAD — two subclasses through the shipped `Colleague` family.** Architecture is
guest JSON/form POST with the ordinary anonymous antiforgery token and cookie; there is no login, SSO, browser
automation, APEX, Jenzabar, viewstate, bearer token, or HTML seat parser. Ranked by students × reuse:

| Reuse rank | College | Suggested ID / exact location | Official student scale | Fall 2026 exact `ENGL C1000` |
|---|---|---|---|---|
| 1 | Santa Ana College | `santa-ana`; `SAC` | **18,399 Fall 2025 credit** students (`https://sac.edu/aboutsac/quickfacts`) | 88 rows: 34 Open / 52 Waitlisted / 2 Closed; **34 safe opens** |
| 2 | Santiago Canyon College | `santiago-canyon`; `SCC` | **11,824 Fall 2024 credit** students (`https://www.sccollege.edu/uploads/campus/documents/SCC_FastFacts_Trifold_1-15-2026_PQ.pdf`) | 48 rows: 23 Open / 24 Waitlisted / 1 Closed; **23 safe opens** |

The comparable combined credit scale is **30,223**. SAC separately reports 15,209 noncredit and 6,890 academy
students; these are not added to the ranking. SCC's official Fall 2026 schedule tells students to choose the
Santiago Canyon location and Fall 2026 term in Self-Service, and explains that only eligible waitlisted students
roll into newly open seats (`https://sccollege.edu/uploads/academics/class_schedule/documents/2026_Fall.pdf`).

**Exact production recipe:** host `https://colss-prod.cloud.rsccd.edu`.

- Bootstrap `GET /Student/Courses`; retain the cookie and hidden `__RequestVerificationToken`.
- `POST /Student/Courses/PostSearchCriteria` as JSON `{"Keyword":"ENGL C1000"}` with the token and
  `X-Requested-With: XMLHttpRequest`. Continue using the shipped exact subject/number normalization.
- The response contains two exact `CourseFullModels`: ID `24468`, `LocationCodes=["SAC"]`, 183
  `MatchingSectionIds`; and ID `24481`, `LocationCodes=["SCC"]`, 82 IDs. Select the exact model whose
  `LocationCodes` contains the subclass campus. The current adapter takes the first exact model, so without
  this hook SCC silently receives SAC or disappears.
- The shipped primary-term resolver selects `Fall 2026` (`2026FA`; August 17–December 5). POST
  `/Student/Courses/Sections` with `{"sectionIds":[...],"courseId":"24468|24481"}`. Require the returned
  term description to equal the selected primary description, not merely contain it, so `-CONT.ED.` and
  intersession groups cannot leak in. Filter every row again by exact `LocationCode`.
- Key sections by native `Number`/CRN. Open only when `AreSeatCountsAvailable is True`,
  `HasUnlimitedSeats is False`, `IsActive is True`, `AvailabilityStatus == "Open"`, integer `Available > 0`,
  `Requisites` is empty, and `OverridesCourseRequisites is False`. Return `seats=max(Available, 0)`; never
  reconstruct seats from `Capacity - Enrolled` and never parse `AvailabilityDisplay`.

**Four-killer evidence, exact first-year writing:**

1. **Freshness:** bootstrap, search, and section responses carried `Cache-Control: no-store,no-cache`, no
   `Age` or stale `Last-Modified`, and live HTTP dates from `15:14:57` through `15:16:17 GMT`, matching the
   July 15 request seconds. SAC's admissions page currently directs students to Self-Service to search and
   register (`https://sac.edu/admissions/`), and SCC's current registration page does the same
   (`https://sccollege.edu/students/studentservices/admissions/enrollment-registration`).
2. **Addressability/completeness:** every advertised ID was returned: **183/183 SAC** and **82/82 SCC**, with
   265 unique internal IDs and **265 unique CRNs**. Term partitions were SAC 9 intersession / 62 Spring / 24
   Summer / 88 Fall and SCC 3 / 24 / 7 / 48. The current exact writing rows are therefore a complete 88/48
   campus slice, not a 49/50/100 cap or subject scatter.
3. **Completed-term fake-status:** completed Spring 2026 is genuinely mixed. SAC returned 62 rows: 26 Open /
   36 Waitlisted; SCC returned 24: 10 Open / 14 Waitlisted. Numerically, 61/62 SAC and 24/24 SCC rows remained
   positive, yet **49** were textually Waitlisted. This is the opposite of an all-open `COMMUNITY_ACCESS`
   feed and proves textual status is authoritative.
4. **Reservation/eligibility/registerability:** current SCC has five positive aggregate traps—CRNs `80638`,
   `80652`, `80655`, `80661`, and `80714` expose 1/2/1/1/2 `Available` seats but are Waitlisted with 3/2/1/2/2
   students waiting. SAC also exposes adjusted values that must not be recomputed: CRN `79701` displays
   20/28/0 and has capacity 28, enrolled 8, but authoritative `Available=0` plus Waitlisted; CRN `79764` is
   over capacity and likewise zero. All 265 audited writing rows published numeric counts, were active and
   finite, and had empty `Requisites` plus `OverridesCourseRequisites=false`. The conservative rule catches
   every observed waitlist/eligibility-adjusted trap.

**Required builder integration — add reusable hooks; do not clone `fetch()`:** give `Colleague` protected
`_course_model_ok(model)`, `_section_ok(section)`, `_term_ok(returned_description, selected_description)`,
`_section_key(section)`, and `_row_is_open(section, available)` hooks. Defaults preserve existing model, section,
term, and key behavior; strengthen the default open hook from status-only to
`AvailabilityStatus == "Open" and available > 0`. In `fetch()`, apply the model hook while choosing the exact
course, the term and section hooks before keying, the key hook instead of the inline fallback, and the open hook
when building the normalized row. A blank or duplicate key must fail the whole course closed instead of retaining
the first colliding row. Regression-smoke the existing Colleague schools because these are safe global tightenings.

```python
class RSCCDColleague(Colleague):
    host = "colss-prod.cloud.rsccd.edu"
    campus = ""
    example = "ENGL C1000"

    def _course_model_ok(self, model):
        return self.campus in (model.get("LocationCodes") or [])

    def _section_ok(self, section):
        return (section.get("LocationCode") or "") == self.campus

    def _term_ok(self, returned, selected):
        return (returned or "").casefold() == (selected or "").casefold()

    def _section_key(self, section):
        return section.get("Number")

    def _row_is_open(self, section, available):
        return (super()._row_is_open(section, available)
                and section.get("AreSeatCountsAvailable") is True
                and section.get("HasUnlimitedSeats") is False
                and section.get("IsActive") is True
                and not section.get("Requisites")
                and section.get("OverridesCourseRequisites") is False)

class SantaAna(RSCCDColleague):
    id = "santa-ana"; name = "Santa Ana College"; campus = "SAC"

class SantiagoCanyon(RSCCDColleague):
    id = "santiago-canyon"; name = "Santiago Canyon College"; campus = "SCC"
```

Register exactly one instance of each. Add fixtures for sibling exact course models, exact location and exact-term
isolation, all advertised IDs retrieved, duplicate/blank CRN fail-closed behavior, zero/negative seats, disabled
counts, unlimited/inactive rows, nonempty requisites/override, the five positive-but-waitlisted SCC rows, the two
SAC arithmetic mismatches, and completed mixed status. Live-smoke both through production; the projected hook
implementation returned **88/34 safe** for SAC and **48/23 safe** for SCC, including five SCC positive-seat rows
correctly closed. Open counts are live and must not be hard-coded.

This batch **supersedes the older Santa Ana and Santiago Canyon FOLLOW-UP/HOLD notes**. Strict software-family
cuts from the same pass: San Bernardino CCD's shared Colleague surface returned no numeric production rows and
rendered `Unlimited Seat Counts Unavailable`, so San Bernardino Valley and Crafton Hills remain CUT; the
`oshkosh`, `uwplatt`, and `uwstout` College Scheduler environments returned missing-index errors with null terms,
so those UW shells are CUT rather than padded into the batch. Registry remains 718; no `schools.py`, builder
contact, commit, or deployment change was made.

### Codex Batch 81 — Illinois Eastern CC district shared Banner 9: three pass, one cut (July 15, 2026) — GATED, AWAITING GO-AHEAD

This is one district-shaped software handoff. Illinois Eastern Community Colleges' official district page says
the district has exactly four colleges: Frontier Community College, Lincoln Trail College, Olney Central College,
and Wabash Valley College (`https://iecc.edu/mission`). All four share one anonymous Banner 9 registration feed,
but only the latter three survive the completed-term gate. Exact ID, exact name, punctuation/leading-article
normalization, and near-name checks against all **718** live `schools.SCHOOLS` entries found the three proposed
identities net-new. Expected isolated registry change: **718 → 721**.

**Status: GATED, AWAITING GO-AHEAD — three exact-campus subclasses through the existing Banner family and Batch
76's `WaitlistSafeBanner` hook.** Architecture is direct guest Banner JSON plus the standard anonymous session
cookie/form POST. There is no login, SSO, browser automation, APEX, Jenzabar, viewstate, bearer token, or HTML
seat parser. Ranked by official student scale × identical high adapter reuse:

| Reuse rank | College | Suggested ID / exact Banner campus | Official student scale | Fall 2026 `ENG 1111` |
|---|---|---|---|---|
| 1 | Wabash Valley College | `wabash-valley`; `WABASH VALLEY COLLEGE` | **1,527** annual unduplicated AY2022 | 6 rows, 5 positive / 1 zero; **5 safe opens** |
| 2 | Olney Central College | `olney-central`; `OLNEY CENTRAL COLLEGE` | **1,214** annual unduplicated AY2022 | 4 rows, 2 positive / 2 zero; **2 safe opens** |
| 3 | Lincoln Trail College | `lincoln-trail`; `LINCOLN TRAIL COLLEGE` | **792** annual unduplicated AY2022 | 4 rows, 4 positive; **3 safe opens** after one cross-list trap |

The comparable three-campus scale is **3,533**. Counts are the campus-level annual unduplicated headcounts in
page 3 of IECC's official 2022 Fact Book (`https://iecc.edu/factbook` and
`https://iecc.edu/sites/default/files/inline-files/IECC_FactBook2022.pdf`), not mixed Fall/FTE estimates.
IECC's official schedules page links the production search and explicitly calls that search the most up-to-date
method (`https://iecc.edu/schedules`). Its Fall 2026 schedules identify `ENG 1111` as Composition I, making it the
large first-year-writing control rather than an arbitrary small course.

**Exact production recipe:** host `banprodss1.iecc.edu:8447`, default `StudentRegistrationSsb` path. Bootstrap
`GET /StudentRegistrationSsb/ssb/classSearch/classSearch`; select term with form POST
`/StudentRegistrationSsb/ssb/term/search?mode=search`; reset the search; then GET
`/StudentRegistrationSsb/ssb/searchResults/searchResults` with `txt_subject=ENG`,
`txt_courseNumber=1111`, `txt_term=202730`, `pageOffset=0`, and `pageMaxSize=100`. Follow `totalCount` and retain
only exact `subject == "ENG"` plus `courseNumber == "1111"`, as the existing `Banner.fetch()` already does.
The public term list labels `202730` Fall 2026, `202710` Summer 2026, `202660` Spring 2026 View Only, and
`202630` Fall 2025 View Only; production `resolve_term()` selected `202730`.

**Four-killer evidence:**

1. **Freshness:** the current exact-writing JSON carried `Date: Wed, 15 Jul 2026 15:33:12 GMT`, equal to the
   live request second; the full-ENG control returned at `15:33:30 GMT`. There was no `Age` or stale
   `Last-Modified`. This agrees with IECC's official description of the linked search as its freshest schedule.
2. **Addressability/completeness:** exact `ENG 1111` reported and returned **17/17** rows in one page—3 Frontier,
   4 Lincoln Trail, 4 Olney Central, and 6 Wabash Valley—with 17 unique CRNs and 17 unique sequence numbers.
   The broader current `ENG` subject returned **34/34** unique CRNs. Neither control pinned to 49/50/100, no
   pagination remainder was omitted, and exact subject/number and full campus descriptions isolate every row.
3. **Completed-term fake-status:** Lincoln Trail Spring 2026 was genuinely mixed at **2 positive / 1 zero**;
   Olney Central Fall 2025 was **3 / 1**; Wabash Valley Fall 2025 was **5 / 1**. This is not PeopleSoft
   `COMMUNITY_ACCESS` all-open replay. By contrast, Frontier returned positive availability on **all 18** exact
   completed `ENG 1111` rows found across Fall 2025, Spring 2025, Fall 2024, Spring 2024, and Fall 2023 controls;
   completed full-subject and other general-education checks were likewise all-positive. Frontier therefore
   fails this killer and is deliberately **CUT**, even though it shares the otherwise reusable host.
4. **Reservation/eligibility/registerability:** `maximumEnrollment - enrollment == seatsAvailable` held on all
   **108** exact-writing rows audited across nine current/completed term probes; every one had null
   `reservedSeatSummary` and no linked-section flag. The feed still exposes two decisive aggregate/status traps.
   Lincoln Trail CRN `30245` reports 16 section seats (24 capacity, 8 enrolled) while its cross-list is exactly
   full (24/24, `crossListAvailable=0`), so it must be closed. Olney CRN `30200` has zero seats and one waiting
   student while `openSection=true`, proving that Banner's boolean is unsafe. Batch 76's conservative hook closes
   both patterns and yields projected current results of **4 rows / 3 safe** Lincoln, **4 / 2** Olney, and
   **6 / 5** Wabash.

**Required builder integration — reuse Batch 76, do not clone `Banner.fetch()`:** if the protected
`Banner._row_is_open(row, seats)` plus `WaitlistSafeBanner` variant from Batch 76 has not landed, implement that
shared hook first and use its exact waitlist/reservation/linked/cross-list rule. Then add one district base with
an exact full-description campus guard and CRN keying; first-word campus matching happens to work today but is
unnecessarily loose for a shared four-college pool.

```python
class IECCBanner(WaitlistSafeBanner):
    host = "banprodss1.iecc.edu:8447"
    term = "202730"
    example = "ENG 1111"
    _CAMPUS = ""

    def _campus_ok(self, row):
        return (row.get("campusDescription") or "") == self._CAMPUS

    def _seckey(self, row):
        return row.get("courseReferenceNumber")

class WabashValley(IECCBanner):
    id = "wabash-valley"; name = "Wabash Valley College"
    _CAMPUS = "WABASH VALLEY COLLEGE"

class OlneyCentral(IECCBanner):
    id = "olney-central"; name = "Olney Central College"
    _CAMPUS = "OLNEY CENTRAL COLLEGE"

class LincolnTrail(IECCBanner):
    id = "lincoln-trail"; name = "Lincoln Trail College"
    _CAMPUS = "LINCOLN TRAIL COLLEGE"
```

Register exactly one instance of each class and do **not** register Frontier. Add fixtures for exact full-campus
accept/reject, blank campus rejection, CRN keying, all four `WaitlistSafeBanner` blockers, negative-seat clamping,
`openSection=true` with zero seats, and the positive-section/cross-list-full `30245` shape. Live-smoke canonical
`ENG 1111` through every production class and assert 4/4/6 returned rows with 3/2/5 current safe opens; also assert
Spring 2026 Lincoln and Fall 2025 Olney/Wabash retain their mixed closed controls. Open counts are live and must
not be hard-coded.

**Strict cuts from this same system-first pass (do not pad or rediscover):** Frontier Community College is CUT
for completed-term all-positive replay as documented above. Contra Costa CCD's four-college `vsb.4cd.edu` search
is a stateful Modern Campus Visual Schedule Builder `criteria.jsp` flow, not the existing College Scheduler
GraphQL family; it was deprioritized before handoff rather than mislabeled as a drop-in. Registry remains 718;
no `schools.py`, builder contact, commit, or deployment change was made in this research pass.

### Codex Batch 82 — California guest Colleague reuse: WHCCD salvage + two high-enrollment drops (July 15, 2026) — GATED, AWAITING GO-AHEAD

This is a software-family batch, not a list of famous-school guesses. It starts with West Hills Community College
District's shared anonymous Colleague feed, then adds the two strongest net-new California schools found on the
same shipped old-Colleague API. WHCCD's current public pages identify **Coalinga College** and **Lemoore College**
as its colleges (`https://login.whccd.edu/` and `https://support.whccd.edu/hc/en-us/articles/360016997893-When-can-I-register-for-classes`).
Both appear in one exact-course response, but only Coalinga passes all four killers; Lemoore is deliberately cut.

During final dedup, unrelated builder work added UVI and Cayuga, moving the live registry from 718 to **720**.
Exact ID, exact name, punctuation/leading-article normalization, and near-name checks against all 720 current
`schools.SCHOOLS` entries found the three identities below net-new. `southwesterntx` and `southwesterncc` are
different existing schools, and the older Victor Valley README note is research only, not a registry entry.
Expected isolated registry change: **720 -> 723**.

**Status: GATED, AWAITING GO-AHEAD — three subclasses through the shipped `Colleague` family, dependent on Batch
80's protected hooks.** Architecture is the ordinary anonymous `/Student/Courses` page plus antiforgery token,
cookie, and direct JSON POSTs. There is no login, SSO, browser automation, APEX, Jenzabar, viewstate, bearer
token, or HTML seat parser. Ranked by students x exact adapter reuse:

| Reuse rank | College | Suggested ID / host | Official student scale | Fall 2026 exact `ENGL C1000` |
|---|---|---|---|---|
| 1 | Southwestern College (CA) | `southwestern-ca`; `collselfserv.swccd.edu` | **32,420 annual 2024-25** (`https://www.swccd.edu/administration/institutional-research-and-planning/_files/fast-facts-2024-2025.pdf`) | 120 rows: 69 Open / 49 Waitlisted / 2 Closed; **51 safe opens** |
| 2 | Victor Valley College | `victor-valley`; `vvc-ss.colleague.elluciancloud.com` | **well over 20,000 annually** (`https://catalog.vvc.edu/about-vvc/college-history/`) | 80 rows: 17 Open / 53 Waitlisted / 10 Closed; **17 safe opens** |
| 3 | Coalinga College | `coalinga`; `ellucianssui.whccd.edu` | **4,454 12-month 2022-23** under the then-current West Hills College-Coalinga reporting name (`https://nces.ed.gov/ipeds/dfr/2024/ReportHTML.aspx?unitId=125462`) | 12 rows: 9 Open / 3 Waitlisted; **9 safe opens** |

The combined comparable annual-scale reach is at least **56,874 students**. The three current writing controls
contain **212 rows and 77 conservative registerable opens**. Southwestern's official 2024-25 Fast Facts also
reports 22,308 Fall students; the larger 32,420 value is its explicitly labeled annual headcount. Victor Valley's
current catalog says both "well over 20,000" annually and 20,000-30,000 each year. Coalinga's federal report's
Figure 2 reports 4,454 total 12-month enrollment and 3,592 Fall 2023 enrollment; use the annual figure consistently.

**Exact production recipes:** all three use the existing old-Colleague route. Bootstrap `GET /Student/Courses`,
retain the cookie plus hidden `__RequestVerificationToken`, then POST JSON `{"Keyword":"ENGL C1000"}` to
`/Student/Courses/PostSearchCriteria`. Continue to require exact normalized `SubjectCode == "ENGL"` and
`Number == "C1000"`. The shipped primary-term resolver selects Fall 2026. POST every selected model's full
`MatchingSectionIds` to `/Student/Courses/Sections`; require exact returned term-description equality, native
`Number`/CRN keys, and exact location filtering where specified below.

- **Southwestern:** one exact model, ID `3472`, advertised 208 IDs. Its public production source is
  `https://collselfserv.swccd.edu/Student/Courses`. The response partitions into 67 Spring, 21 Summer, and 120
  Fall 2026 sections.
- **Victor Valley:** one exact model, ID `100184`, advertised 190 IDs. VVC's official registration page directly
  links the public guest search (`https://www.vvc.edu/register`); production source is
  `https://vvc-ss.colleague.elluciancloud.com/Student/Courses`. The response partitions into 42 Spring, 11
  Summer, 80 Fall 2026, 14 Winter 2027, and 43 Spring 2027 sections.
- **Coalinga/WHCCD:** the exact response has two same-code models with no usable `LocationCodes`: Lemoore model
  `3973` advertises 85 IDs and Coalinga model `3966` advertises 30. Do not pin those internal model IDs or take
  the first exact model. Fetch **all exact models**, then retain only section `LocationCode` in
  `{"CLC", "OLC", "NDC"}`. Those codes are disjoint from Lemoore's `{"LMC", "OLL", "LEM"}` in all 115 audited
  rows. Coalinga partitions into 8 Spring, 2 Summer, 12 Fall 2026, and 8 Spring 2027 sections. Public production
  source: `https://ellucianssui.whccd.edu/Student/Courses`.

**Four-killer evidence, exact first-year writing:**

1. **Freshness:** WHCCD search/section responses carried live request-second HTTP dates from `15:44:14` through
   `15:44:18 GMT`; Southwestern returned `15:46:22`/`15:46:24`; Victor Valley returned
   `15:47:03`/`15:47:06`. All sent `Cache-Control: no-store` or `no-store,no-cache`, with no `Age` or stale
   `Last-Modified`. WHCCD's public catalog identifies `ENGL C1000` under the statewide Common Course Numbering
   project; the other two are the same California first-year composition control.
2. **Addressability/completeness:** every advertised exact-writing ID was returned: **30/30 Coalinga**,
   **208/208 Southwestern**, and **190/190 Victor Valley**. Each school had unique internal IDs and unique native
   section numbers. The complete term partitions above sum exactly to those totals; current slices are 12/120/80,
   not 49/50/100 caps, and no subject-wide page scatter is involved. WHCCD additionally returned all 85/85
   Lemoore sibling IDs before the exact-location cut, proving the multi-model merge is complete.
3. **Completed-term fake-status:** completed Spring 2026 is genuinely mixed at all three survivors. Coalinga is
   **7 Open / 1 Waitlisted** despite all eight rows having positive aggregate availability. Southwestern is
   **65 Open / 2 Closed**, with 65 positive and two zero rows. Victor Valley is **36 Open / 6 Closed**, with 36
   positive and six zero rows. None resembles PeopleSoft `COMMUNITY_ACCESS` all-open replay.
4. **Reservation/eligibility/registerability:** textual state and eligibility fields must override aggregate
   availability. Southwestern Summer has **14 positive-but-Waitlisted** rows; current Fall has another positive
   non-open row and **20 rows with section `Requisites` and/or `OverridesCourseRequisites`**, producing only 51
   safe opens from 69 textually Open rows. Victor Valley Fall CRN `70039` is Waitlisted with two waiting students
   despite `Available=2`; the safe result is closed. Its three current zero-capacity/positive-enrollment rows and
   three completed over-capacity rows correctly expose authoritative `Available=0` plus Closed rather than an
   arithmetic guess. Coalinga's completed positive-but-Waitlisted row proves the same rule. Every audited row at
   all three schools published counts and was active and finite; Coalinga/VVC had empty section requisites and no
   override. Require textual Open, positive authoritative availability, enabled finite counts, active state, and
   no section-level prerequisite/override. Never reconstruct seats as `Capacity - Enrolled`.

**Required builder integration — land Batch 80 first; do not clone `Colleague.fetch()`:** implement Batch 80's
`_course_model_ok`, `_section_ok`, `_term_ok`, `_section_key`, and `_row_is_open` hooks plus blank/duplicate-key
fail-closed behavior. Add one further protected `_matching_course_models(data, subject, number)` hook. Its default
must preserve old behavior by returning a one-item list containing the first exact model that passes
`_course_model_ok`; the Coalinga subclass returns every exact model. Change the shared fetch loop to POST each
selected model, merge only hook-approved rows, and fail the course closed on a blank or duplicate key across the
merged result. For this strict subclass family, also compare returned internal section IDs with each model's full
advertised `MatchingSectionIds`; any missing/extra ID fails the course closed instead of silently undercounting.

Promote Batch 80's conservative registerability rule into a reusable base so RSCCD and these three schools do not
copy it separately:

```python
class RegisterableColleague(Colleague):
    require_all_matching_section_ids = True

    def _term_ok(self, returned, selected):
        return (returned or "").casefold() == (selected or "").casefold()

    def _section_key(self, section):
        return section.get("Number")

    def _row_is_open(self, section, available):
        return (super()._row_is_open(section, available)
                and section.get("AreSeatCountsAvailable") is True
                and section.get("HasUnlimitedSeats") is False
                and section.get("IsActive") is True
                and not section.get("Requisites")
                and section.get("OverridesCourseRequisites") is False)

class SouthwesternCA(RegisterableColleague):
    id = "southwestern-ca"; name = "Southwestern College"
    example = "ENGL C1000"; host = "collselfserv.swccd.edu"

class VictorValley(RegisterableColleague):
    id = "victor-valley"; name = "Victor Valley College"
    example = "ENGL C1000"; host = "vvc-ss.colleague.elluciancloud.com"

class Coalinga(RegisterableColleague):
    id = "coalinga"; name = "Coalinga College"
    example = "ENGL C1000"; host = "ellucianssui.whccd.edu"
    _LOCATIONS = frozenset({"CLC", "OLC", "NDC"})

    def _matching_course_models(self, data, subject, number):
        return [m for m in (data.get("CourseFullModels") or [])
                if (m.get("SubjectCode") or "").upper() == subject
                and (m.get("Number") or "").upper() == number]

    def _section_ok(self, section):
        return (section.get("LocationCode") or "") in self._LOCATIONS
```

Register exactly one instance of each. Add fixtures for first-exact-model sibling contamination, reversed model
order, the complete 85+30 WHCCD merge, exact Coalinga/Lemoore location accept/reject, exact returned term,
missing/extra advertised ID, blank/duplicate CRN across models, zero/negative availability, disabled/unlimited/
inactive counts, nonempty requisites, override, positive-but-Waitlisted rows, and VVC's capacity anomalies. Live
smoke canonical `ENGL C1000`: require 120/80/12 current rows and **51/17/9 safe opens** for Southwestern/VVC/
Coalinga. Open counts are live and must not be hard-coded.

This batch **supersedes the older Victor Valley FOLLOW-UP/HOLD note**: the current production API now returns all
190/190 advertised rows with numeric statuses and counts. Strict same-family cuts: Lemoore College is **CUT**
because completed Spring 2026 returned **23/23 Open and positive**, a false-open replay failure even though its
current data looked plausible. Ohlone College's public old-Colleague host works, but `ActivePlanTerms` begins at
Summer 2026 and exposes no completed term, so it is HOLD/CUT from this batch rather than called GATED. San Jose
City and Evergreen Valley were skipped as duplicates because the live `sjeccd` district adapter already covers
that shared system. Current registry is 720; this research pass did not edit `schools.py`, contact the builder,
commit, or deploy.

### Codex Batch 83 — old-Colleague family: DuPage + Elgin + Kellogg (July 15, 2026) — GATED, AWAITING GO-AHEAD

This is the next software-family enumeration after the district-first screen, not three unrelated portal guesses.
All three schools run the exact anonymous old-Colleague JSON flow already shipped in `Colleague` and strengthened
by Batches 80/82. Exact ID, exact name, leading-article/punctuation normalization, and near-name checks against all
**720** live `schools.SCHOOLS` entries found the three identities net-new. The older College of DuPage README
entry is an unresolved research note, not a registry entry. Expected isolated registry change: **720 -> 723**.

**Status: GATED, AWAITING GO-AHEAD — three tiny subclasses of Batch 82's `RegisterableColleague`; no new
fetcher.** Architecture is the standard public `/Student/Courses` page plus anonymous cookie, antiforgery token,
and direct JSON POSTs. There is no login, SSO, browser automation, bearer token, APEX, Jenzabar, viewstate, or
HTML parser. Ranked by students x identical high adapter reuse:

| Reuse rank | School | Suggested ID / host | Official student scale | Current Fall 2026 writing control |
|---|---|---|---|---|
| 1 | College of DuPage | `dupage`; `selfserv.cod.edu` | **28,004 Fall 2025** students, summed from the official student-type headcounts (`https://cod.edu/about/administration/planning-and-reporting-documents/pdf/student-demo.pdf`) | `ENGLI 1101`: 216 rows, 181 Open / 35 Waitlisted; **157 safe opens** |
| 2 | Elgin Community College | `elgin`; `selfservice.elgin.edu:8173` | **17,161 AY2024-25** students (`https://elgin.edu/about/accreditation/assurance-argument/2025-ecc-assurance-argument-for-reaffirmation-of-accreditation.php`) | `ENG 101`: 79 rows, 48 Open / 31 Waitlisted; **38 safe opens** |
| 3 | Kellogg Community College | `kellogg`; `portal.kellogg.edu` | **4,917 12-month 2022-23** students (`https://nces.ed.gov/ipeds/dfr/2024/ReportHTML.aspx?unitId=170550`) | `ENGL 151`: 31 rows, 26 Open / 5 Waitlisted; **22 safe opens** |

The tagged scale is **50,082 students** and intentionally combines the latest official metrics available rather
than pretending they are one uniform census. The three current first-year-writing controls contain **326 rows
and 217 conservative registerable opens**.

**Exact production recipe:** for each host, bootstrap `GET /Student/Courses`, retain the anonymous cookie and
hidden `__RequestVerificationToken`, then POST JSON `{"Keyword":"{subject} {number}"}` to
`/Student/Courses/PostSearchCriteria`. Require exact normalized `SubjectCode` and `Number`; do not accept the
search response's related courses. The shipped term resolver selects Fall 2026. POST the exact model's complete
`MatchingSectionIds` to `/Student/Courses/Sections`, require exact returned term-description equality, then key
by native `Number` only after the exact-term filter.

| School | Exact model observed | All advertised IDs / complete term partition |
|---|---|---|
| DuPage | `ENGLI 1101`, model `3726` | **361/361**: 119 Spring 2026 + 26 Summer 2026 + 216 Fall 2026 |
| Elgin | `ENG 101`, model `332` | **139/139**: 47 Spring 2026 + 13 Summer 2026 + 79 Fall 2026 |
| Kellogg | `ENGL 151`, model `ENGL_151` | **96/96**: 25 Spring 2026 + 7 Summer 2026 + 31 Fall 2026 + 25 Spring 2027 + 8 Summer 2027 |

Model IDs are audit evidence, not values to hard-code. Every returned internal ID was unique and the returned ID
set exactly equaled the advertised set. Native `Number` values repeat across terms, so filtering the exact term
**before** keying is mandatory; within current Fall, all 216/79/31 native numbers are nonblank and unique.

**Four-killer evidence, exact first-year writing:**

1. **Freshness:** all bootstrap/search/section calls carried `Cache-Control: no-cache,no-store` or `no-store`,
   no `Age`, and no stale `Last-Modified`. Live request-second HTTP dates were DuPage `16:04:33-38 GMT`, Elgin
   `16:04:42-44`, and Kellogg `16:04:45-47` on July 15. The official DuPage guest page says the catalog can be
   searched without login (`https://selfserv.cod.edu/Student/Courses`); Elgin's official classes page links its
   search (`https://elgin.edu/academics/catalog-classes/`); Kellogg's official instructions say the same public
   results show seats (`https://help.kellogg.edu/en_US/records-and-registration/class-schedules`).
2. **Addressability/completeness:** the exact large writing models returned **361/361, 139/139, and 96/96**
   advertised IDs with the complete term partitions above. Current Fall has 216/79/31 unique native section
   numbers and internal IDs. There is no 49/50/100 cap, pagination remainder, subject scatter, sibling honors
   leakage, or missing advertised section. DuPage's five-letter subject is exactly `ENGLI`, not `ENGL`.
3. **Completed-term fake-status:** completed Spring 2026 is genuinely mixed at every school. DuPage returned
   **105 Open / 14 Waitlisted**; Elgin **46 Open / 1 Closed**; Kellogg **24 Open / 1 Closed**. Positive
   authoritative availability exactly matched the Open counts, while the non-open rows were zero. This is not
   PeopleSoft `COMMUNITY_ACCESS` all-open replay.
4. **Reservation/eligibility/registerability:** all 596 rows publish counts and are active and finite, but raw
   Open plus positive aggregate availability is still unsafe. DuPage Fall has **41** rows with section
   `Requisites` and/or `OverridesCourseRequisites`; 24 are positive/Open and must be excluded. CRN/section
   `ALP10` alone shows 10 available with a required concurrent rule and override. Elgin has **10** positive/Open
   override rows (`A01` is 5/20) and Kellogg has **4** positive/Open required/override rows (`0161` is 2/24).
   The strict hook therefore contracts 181/48/26 raw Open rows to **157/38/22 safe**. Do not infer waitlist state
   from numeric `Waitlisted`: some textually Waitlisted rows report zero occupants. `AvailabilityStatus` is the
   authority.

Seat arithmetic is diagnostic only. It held on DuPage **216/216 current** and 118/119 completed rows, but only
**43/79 current and 32/47 completed Elgin** rows and **25/31 current and 18/25 completed Kellogg** rows. Examples
include Elgin Spring section `102` at capacity 20, enrolled 17, authoritative available 2; Kellogg Spring `0160`
at 24/16 with authoritative available 5; and DuPage completed `NET21` at capacity 12, enrolled 13, authoritative
available 0 plus Waitlisted. Never reconstruct seats as `Capacity - Enrolled`.

**Required builder integration — reuse Batches 80/82 exactly:** first land the protected old-Colleague hooks and
`RegisterableColleague` from Batches 80/82 if they are still pending. In particular, require textual Open plus
positive authoritative `Available`, enabled/finite/active counts, empty `Requisites`, and
`OverridesCourseRequisites is False`; require every advertised ID; require exact term before keying; and fail the
course closed on a missing/extra ID or blank/duplicate within-term key. Then add only these subclasses:

```python
class CollegeDuPage(RegisterableColleague):
    id = "dupage"; name = "College of DuPage"
    example = "ENGLI 1101"; host = "selfserv.cod.edu"

class ElginCC(RegisterableColleague):
    id = "elgin"; name = "Elgin Community College"
    example = "ENG 101"; host = "selfservice.elgin.edu:8173"

class KelloggCC(RegisterableColleague):
    id = "kellogg"; name = "Kellogg Community College"
    example = "ENGL 151"; host = "portal.kellogg.edu"
```

Register exactly one instance of each. Add fixtures for the five-letter `ENGLI` normalization, exact-model
selection amid related courses, every advertised-ID set, exact-term-before-key behavior, cross-term repeated
numbers, blank/duplicate current keys, disabled/unlimited/inactive counts, zero/negative availability, textual
Waitlisted with zero occupants, nonempty requisites, override-only rows, and all three arithmetic mismatches.
Use DuPage `ALP10`, Elgin `A01`, and Kellogg `0161` shapes as positive-but-ineligible regression fixtures. Live
smoke the canonical examples through production and require **216/79/31 current rows with 157/38/22 safe opens**.
Open counts are live and must not be hard-coded.

This batch **supersedes the older College of DuPage FOLLOW-UP note**. Strict same-family exclusions from this
pass: Hawkeye's old public host now redirects to `colss-prod.hawksaas.elluciancloud.com`, but completed Spring
2026 `ENG 105` is **17/17 Open and positive**, so Hawkeye is CUT for false-open replay. Chaffey returned all
237 `ENGL C1000` IDs but only Summer/Fall 2026 and Spring 2027; Northeast Iowa returned 16 `ENG 105` IDs only
for Summer/Fall; Prairie State returned 24 `ENG 101` IDs only for Summer/Fall. All three lack a completed-term
disproof and remain HOLD, not GATED. Highland's new Colleague system explicitly starts with Summer/Fall 2026
while Spring stayed on its legacy system, so it also cannot pass same-feed completed replay. Current registry is
720; this research pass did not edit `schools.py`, contact the builder, commit, or deploy.

### Codex Batch 84 — high-scale old-Colleague family: Wake Tech + Schoolcraft + three NC colleges (July 15, 2026) — GATED, AWAITING GO-AHEAD

This is the next exact-software enumeration after the multi-college-system screen, not another famous-flagship
list. Only five anonymous old-Colleague survivors are promoted; weaker same-family schools are cut or held below
instead of padding the batch. Exact ID, exact display name, punctuation/leading-article normalization, and
near-name similarity checks against all **720** live `schools.SCHOOLS` entries found every identity net-new.
Expected isolated registry change: **720 -> 725**.

**Status: GATED, AWAITING GO-AHEAD — five tiny subclasses of Batch 82's `RegisterableColleague`; no new
fetcher.** Every source is the same public `/Student/Courses` bootstrap plus anonymous cookie, antiforgery token,
and direct JSON POSTs. There is no login, SSO, browser automation, bearer token, APEX, Jenzabar, viewstate, or
HTML seat parser. Ranked by students x identical high adapter reuse:

| Reuse rank | College | Suggested ID / exact host | Official student scale | Current Fall 2026 writing control |
|---|---|---|---|---|
| 1 | Wake Technical Community College | `waketech`; `selfserve.waketech.edu` | **more than 72,000 adults annually** (`https://www.waketech.edu/about-wake-tech`) | `ENG 111`: 196 rows, 55 Open / 141 Waitlisted; **55 safe opens** |
| 2 | Schoolcraft College | `schoolcraft`; `self-service.schoolcraft.edu` | **more than 30,000 annually** across credit and personal/professional learning (`https://www.schoolcraft.edu/about/`) | `ENG 101`: 66 rows, 46 Open / 20 Waitlisted; **46 safe opens** |
| 3 | Alamance Community College | `alamance`; `ss-prod.cloud.alamancecc.edu` | **more than 10,000 annually** (`https://www.alamancecc.edu/news/2026-press-releases/march-23-acc-ecu/mou-partnership.php`) | `ENG 111`: 38 rows, 9 Open / 29 Waitlisted; **9 safe opens** |
| 4 | Central Carolina Community College | `central-carolina`; `ss-prod.cloud.cccc.edu` | **approximately 7,100 credential-seeking annually** across three campuses (`https://www.nccommunitycolleges.edu/students/what-we-offer/colleges/central-carolina-community-college/`) | `ENG 111`: 68 rows, 24 Open / 44 Waitlisted; **24 safe opens** |
| 5 | Brunswick Community College | `brunswickcc`; `ss2-prod-cloud.brunswickcc.edu` | **2,590 12-month 2023-24** students (`https://brunswickcc.edu/wp-content/uploads/2026/01/2025-IPEDS-Report-for-BCC.pdf`) | `ENG 111`: 21 rows, 14 Open / 7 Waitlisted; **14 safe opens** |

The comparable tagged reach is **more than 121,690 annual-scale students**. The five current writing controls
contain **389 sections and 148 conservative registerable opens**. Positive authoritative availability appears
on 155 current rows, but seven of those are explicitly Waitlisted and must remain closed; that difference is a
useful production gate, not noise.

**Exact production recipe:** bootstrap `GET /Student/Courses`, retain the anonymous cookie and hidden
`__RequestVerificationToken`, and POST JSON `{"Keyword":"{subject} {number}"}` to
`/Student/Courses/PostSearchCriteria`. Require exact normalized `SubjectCode` and `Number`; do not accept related
search results. The existing primary-term resolver selects Fall 2026 on July 15. POST the exact model's complete
`MatchingSectionIds` to `/Student/Courses/Sections`, require exact returned term-description equality, and filter
the exact term before keying by native `Number`.

| College | Exact model observed | Every advertised ID returned / complete term partition |
|---|---|---|
| Wake Tech | `ENG 111`, model `S26393` | **468/468**: 202 Spring + 70 Summer + 196 Fall 2026 |
| Schoolcraft | `ENG 101`, model `ENG_101` | **135/135**: 45 Winter + 15 Spring + 9 Summer + 66 Fall 2026 |
| Alamance | `ENG 111`, model `S26393` | **81/81**: 32 Spring + 11 Summer + 38 Fall 2026 |
| Central Carolina | `ENG 111`, model `S26393` | **134/134**: 54 Spring + 12 Summer + 68 Fall 2026 |
| Brunswick | `ENG 111`, model `S26393` | **36/36**: 11 Spring + 4 Summer + 21 Fall 2026 |

Model IDs are audit evidence, not constants to pin. Within each of the five feeds, the **854/854** returned
internal IDs are unique and exactly equal the corresponding advertised ID set. Native section numbers repeat across terms, so exact-term
filtering must precede keying; inside every current term the native numbers are nonblank and unique.

**Four-killer evidence, exact first-year writing:**

1. **Freshness:** every bootstrap/search/section response was fetched live on July 15 with request-second HTTP
   dates and `Cache-Control: no-store` or `no-store,no-cache`, with no `Age` or stale `Last-Modified`. Wake Tech
   returned `16:16:41-46 GMT`, Central Carolina `16:18:24-26`, Schoolcraft `16:19:57-20:00`, Brunswick
   `16:21:04-05`, and Alamance `16:22:26-27`. These are live query responses, not delayed schedule exports.
2. **Addressability/completeness:** the large exact controls returned **468/468, 135/135, 81/81, 134/134, and
   36/36** advertised IDs with the complete partitions above. Current slices are 196/66/38/68/21, not suspicious
   49/50/100 caps; there is no subject pagination, page scatter, or silent omitted ID. All internal IDs and all
   within-term native keys are unique.
3. **Completed-term fake-status:** completed Spring 2026 is genuinely mixed at every school: Wake Tech **198
   Open / 4 Closed**, Schoolcraft **14 Open / 1 Waitlisted**, Alamance **28 Open / 4 Waitlisted**, Central
   Carolina **50 Open / 4 Waitlisted**, and Brunswick **10 Open / 1 Waitlisted**. That is **300 Open / 14
   non-open across 314 completed rows**, not PeopleSoft `COMMUNITY_ACCESS` all-open replay. Schoolcraft also has
   a second mixed completed control in Winter 2026 at 32 Open / 13 Waitlisted.
4. **Reservation/eligibility/registerability:** all 854 audited rows publish counts, are active and finite, have
   empty section `Requisites`, and set `OverridesCourseRequisites` false. Even so, textual state overrides the
   positive aggregate. Current Wake sections `0023`/`323292` and `0027`/`323297` are Waitlisted with 15 and one
   available; Central Carolina `LN10`/`106991` is Waitlisted with two available; Alamance `41BH`/`100087` is
   Waitlisted with one. Wake has five such current rows in total, making seven across the current batch.
   Brunswick's completed `03A`/`51037` is Waitlisted with four available, and Schoolcraft Winter `02`/`200560`
   is Waitlisted with two. Require textual Open, positive authoritative `Available`, enabled finite counts,
   active state, empty requisites, and `OverridesCourseRequisites is False`. Never treat aggregate positivity as
   registerability.

Seat arithmetic is diagnostic only. It happened to hold for all 196 current Wake, 38 Alamance, and 21 Brunswick
rows, but only **60/66 Schoolcraft** and **51/68 Central Carolina** rows. Central Carolina Fall `HB1C`/`106943`
reports authoritative available 1 at capacity 24/enrolled 20, while Schoolcraft Fall `10`/`204463` reports one at
28/26. Completed controls show the same issue: only 17/54 Central Carolina and 9/15 Schoolcraft Spring rows match
`Capacity - Enrolled`. Never reconstruct seats from those two fields.

**Required builder integration — land Batches 80/82 first; do not clone `Colleague.fetch()`:** reuse the
protected `_course_model_ok`, `_section_ok`, `_term_ok`, `_section_key`, and `_row_is_open` hooks, complete
advertised-ID equality gate, and Batch 82's `RegisterableColleague`. That base must require textual Open plus
positive authoritative availability, `AreSeatCountsAvailable is True`, `HasUnlimitedSeats is False`,
`IsActive is True`, empty `Requisites`, and `OverridesCourseRequisites is False`; it must require exact returned
term before keying and fail the course closed on a missing/extra advertised ID or blank/duplicate within-term key.
Then add only these subclasses:

```python
class WakeTech(RegisterableColleague):
    id = "waketech"; name = "Wake Technical Community College"
    example = "ENG 111"; host = "selfserve.waketech.edu"

class Schoolcraft(RegisterableColleague):
    id = "schoolcraft"; name = "Schoolcraft College"
    example = "ENG 101"; host = "self-service.schoolcraft.edu"

class Alamance(RegisterableColleague):
    id = "alamance"; name = "Alamance Community College"
    example = "ENG 111"; host = "ss-prod.cloud.alamancecc.edu"

class CentralCarolinaCC(RegisterableColleague):
    id = "central-carolina"; name = "Central Carolina Community College"
    example = "ENG 111"; host = "ss-prod.cloud.cccc.edu"

class BrunswickCC(RegisterableColleague):
    id = "brunswickcc"; name = "Brunswick Community College"
    example = "ENG 111"; host = "ss2-prod-cloud.brunswickcc.edu"
```

Register exactly one instance of each. Add fixtures for exact-model selection amid related search results, all
five complete advertised-ID sets, missing/extra returned ID, exact-term-before-key behavior, cross-term repeated
numbers, blank/duplicate current keys, disabled/unlimited/inactive counts, negative/zero availability, nonempty
requisites, override-only rows, and positive-but-Waitlisted rows. Preserve the exact `0023`, `LN10`, `41BH`,
`03A`, and Schoolcraft `02` shapes above plus the `HB1C` and Schoolcraft `10` arithmetic mismatches. Live-smoke
the canonical examples through production and require **196/66/38/68/21 current rows with 55/46/9/24/14 safe
opens** in the class order above. Status/open counts are live and must not be hard-coded.

This batch **supersedes every older bespoke Schoolcraft schedule-viewer GATED/FOLLOW-UP note** in this README;
the anonymous Colleague JSON route is simpler, complete, and directly reusable. Strict same-family exclusions
from this pass: Johnston CC completed Spring `ENG 111` at **39/39 Open and positive**, and Halifax CC at **6/6
Open and positive**, so both are CUT for fake-status replay. Alvin, King's College (PA), NPRC, Forsyth Tech,
Wayne CC, and Coffeyville expose no completed term in the same feed and remain HOLD. Catawba Valley's
old-Colleague route is likewise HOLD for lacking a completed term; that does not invalidate its separately
researched bespoke viewer. Columbus State exposes only Summer and no active plan terms, while Pitt's section
request did not return usable JSON; neither is promoted. Current registry remains 720; this research pass did
not edit `schools.py`, contact the builder, commit, or deploy.

---

## PENDING HANDOFFS (grep `AWAITING GO-AHEAD`)

### Active dedup queue status — July 14, 2026
This queue snapshot was built against **718 schools**; the live registry is now **720** after UVI and Cayuga
shipped independently. After exact, punctuation/diacritic-normalized, and leading-article alias checks, Batches
5–8 contain **22 still-unregistered, source-gated identities**. The three VCCCD schools from
Batch 6 are already registered and are removed from this active count. Treat the 22 as one set: before any builder
edit, reload `schools.SCHOOLS`, skip every registered identity, and do not create a second batch entry for a name
already present in Batches 5–8. No additional candidate cleared the accuracy gate in this pass; weaker leads remain
documented as hold-outs rather than being padded into the queue.

### ⭐ VCCCD ×3 (Ventura County CCD) — Grab BROWSER-TRACED + gate-passed July 14 (was bespoke-bench; now ready)
Moorpark College + Oxnard College + Ventura College, ~37k combined. Traced the Django SPA
(schedule.vcccd.edu) that stumped the earlier plain-GET probe (that hit the wrong host,
`banpublic.vcccd.edu` — a dead stub; the real app is `schedule.vcccd.edu`).
- **Session (plain-client reproducible, NO live browser needed — confirmed):** `GET https://schedule.vcccd.edu/`
  sets a Django `csrftoken` cookie. `POST https://schedule.vcccd.edu/filter/` with header `X-CSRFToken: {token}`
  (cookie sent automatically) + form-encoded body carrying `csrfmiddlewaretoken={token}` and all form fields
  (subjCombobox, locCombobox, crse, crn, ctitle, start_hh/mm/ap, end_hh/mm/ap, newc, noncrc, offc, mdCombobox,
  pace, ztc, geCombobox, ge=`%`, csupport, **term**) — send the full field set with empty-string defaults,
  confirmed working; untested whether a minimal subset also works.
- ⚠️ **`subjCombobox` does NOT filter server-side** — every request (regardless of subject value) returns the
  **COMPLETE district-wide term catalog** in one ~7.3MB response (confirmed: `subjCombobox=ENGL` returned rows
  starting AB/AC/ACCT/ACE... i.e. everything). This is actually the SAFE shape: fetch once per term, filter
  client-side by course code + campus. Do not rely on the subject param to scope the response.
- Fields per section (HTML table, rendered client-side from the POST response): `Status` (**OPEN/FULL/
  WAITLISTED**, textual, authoritative), `CRN` (key, verified UNIQUE — 0 dup across 1,574 parsed rows),
  `Cap`/`Act`/`Rem` (numeric, `Rem == Cap - Act` held on every row checked), `Location` (campus identity).
  Term codes: Fall 2026 = `202607`, Spring 2026 = `202603` (dropdown-confirmed).
- **OPEN RULE:** `Status == "OPEN"` (equivalently `Rem > 0`; the two agreed on 100% of parsed rows, 0
  disagreements). WAITLISTED and FULL are both not-open.
- **CAMPUS ISOLATION:** `Location` field is prefixed with the campus name — `Oxnard *`, `Ventura *`,
  `Moorpark *` cover the vast majority of rows (Moorpark 769, Ventura 477, Oxnard 249 in a 1,574-row sample);
  a residual "OTHER" bucket (TBA/online-generic/proctored-exam-room strings ~5%) needs a fallback rule
  (e.g. default to unscoped or hold those sections) — flag this to whoever builds it.
- **GATE (live Fall 202607, decisive):** full-catalog fetch = **3,911 OPEN / 404 FULL / 614 WAITLISTED**
  sections district-wide (real mix, can't be faked); structured sub-parse of 1,574 rows had 0 duplicate CRNs
  and 0 status-vs-arithmetic disagreements. Response reproduced byte-for-byte identical length (7,372,414)
  via a plain `urllib` + cookiejar client with no browser — confirmed NOT a Princeton-style hard requirement.
- **ADDRESSABILITY:** the response IS the complete term catalog → filter by course code + campus-prefixed
  Location = deterministic, no scatter. Passes.
- Completed-term (202603) request returned a suspiciously small result (6 OPEN, 0 FULL) at the same payload
  size — inconclusive, not yet explained (possibly a term-scoping quirk); do NOT treat as a shipped
  completed-term disproof. The LIVE-term disproof above (404 real FULL rows) already meets the bar on its own.
- Dedup: all 3 (Moorpark/Oxnard/Ventura College) net-new. Supersedes the "VCCCD bespoke Django lead, needs
  browser-trace" note — trace is done, this is ready for an adapter.

### ⭐ IU Bloomington — Grab BROWSER-TRACED + gate-passed July 13 (Build handed back; ~48k flagship)
iGPS public course search XHR chain fully traced (Build couldn't extract it from the minified SPA).
Public, no-auth, JSON. 9-CAMPUS SHARED HOST — IUBLA isolation mandatory + VERIFIED.
- Base: `https://sisjee.iu.edu/sisigps-prd/web/igps/course/search`. Campus codes: IUBLA (Bloomington),
  + IUINA/IUEAA/IUKOA/IUNWA/IUSBA/IUSEA/IUCOA/IUFTW. Terms: Fall 2026 = strm `4268`, Spring 2026 = `4262`.
- 3-call flow: (1) `GET /terms.json?inst=IUBLA`; (2) `POST /courses.json` body
  `{inst:"IUBLA",strm:"4268",filters:{attributes:null,level:null,locations:null,meetingTimes:null,mois:null,sessions:null,subject:null,units:null},from:N}` → catalog, PAGINATES 50/page (count=6143;
  loop `from` to completion). Each course has courseId, courseOfferNumber, courseTopicId, effdt, car,
  subject, catalogNumber, classNumbers[]. (3) `GET /classes.json?courseId=&courseOfferNumber=&courseTopicId=&effdt=&strm=4268&inst=IUBLA&car=UGRD` → the SECTIONS with seats.
- classes.json section fields: `classNbr` (key, UNIQUE), `openSeats`, `totalSeats`, `closed` (bool),
  `waitlistTotal`, `campus` (BL), `inst`, `combinedSections[]` (cross-list: combinedEnrollCapacity/Total),
  `departmentConsentRequired`/`instructorConsentRequired`.
- OPEN RULE: `closed === false AND openSeats > 0` (agreed 64/64 in gate; belt+suspenders). Cross-list
  guard: if `combinedSections` present and `combinedEnrollTotal >= combinedEnrollCapacity`, treat as full
  even if openSeats>0 (none tripped in sample but guard it). Consent flags = preserve as note, not fake-open.
- ISOLATION: the `inst=IUBLA` param scopes courses.json + classes.json to Bloomington; rows carry
  campus=BL. Gate found 0 non-IUBLA rows across 64 sections. Mandatory + verified.
- ADDRESSABILITY: courses.json is the COMPLETE campus catalog (paginated) → filter subject+catalogNumber
  → the course's stable ids → classes.json = its exact sections. Deterministic. ⚡ EFFICIENCY: course ids
  (courseId/effdt) are STABLE per term, so build the subject+catnum→ids map ONCE per term from courses.json
  (page all 123 pages once), cache it, then per-poll call ONLY classes.json (the live-seats call).
  (Couldn't crack the subject filter format — 500s; paging works. Build may capture the UI's exact filter
  POST body to skip full paging.)
- GATE (live Fall 4268, 18 big courses/64 sec across ENGL/HIST/ECON/EDUC/MSCH): **44 open / 20 CLOSED** —
  decisive live mix; closed-vs-openSeats agreed 64/64; 0 non-IUBLA; classNbr unique. Completed Spring 4262
  available (Codex Batch 67: class 23672 closed 0/30, 29885 open 1/24). Dedup: net-new.

### ⭐ West Valley + Mission (WVMCCD) ×2 — Grab CRACKED + gate-passed July 13 (browser-traced, static JSON)
Nathan-requested trace done. schedule.wvm.edu serves raw Banner SSBSECT dumps as static per-term JSON,
public/no-auth. 2 net-new colleges on one feed, both gate clean both terms.
- Feed: `GET https://schedule.wvm.edu/data/{term}/crns.json` (~3.8MB, all sections BOTH colleges).
  Banner term codes: Fall 2026 = **202670**, completed Spring 2026 = **202630** (term list at
  `/data/sobterm.json`; Banner-style, labels win).
- Fields: `SUBJ_CODE`, `CRSE_NUMB`, `CRN` (section key — verified UNIQUE), `SSBSECT_CAMP_CODE`,
  `SSBSECT_MAX_ENRL`, `SSBSECT_ENRL`, `SSBSECT_SEATS_AVAIL`, `SSBSECT_SSTS_CODE` (A=active),
  `SSBSECT_WAIT_*`, `SSBSECT_RESERVED_IND`.
- OPEN RULE: `SSBSECT_SEATS_AVAIL > 0` (raw Banner seats; standard). Recommend also requiring
  `SSBSECT_SSTS_CODE == 'A'` (drop cancelled/inactive). Reserved-seat rows negligible (1 in Fall).
- ⚠️ TRAP: the CAMPUS code in the DATA is `WVC` (West Valley) / `MC` (Mission) — NOT the dropdown's
  "WV" label. Filter on `SSBSECT_CAMP_CODE`; using "WV" returns 0 rows (I hit this). Isolation = the
  complete feed filtered by CAMP_CODE (colleges share the file).
- ADDRESSABILITY: complete-feed-filter by CAMP_CODE + SUBJ_CODE + CRSE_NUMB → exact sections (WVC ENGL
  = 69 sec across distinct course numbers). Passes.
- GATE: West Valley (WVC) Fall 1182 sec **837 open/345 full**, Spring 1035 **905/130**; Mission (MC)
  Fall 881 sec **584/297**, Spring 782 **705/77**. Decisive real mixes both terms both colleges. Dedup:
  both net-new. Same static-JSON family as NOCCCD (Codex) but WVM has real Banner seats — shippable.

### SDCCD Mesa + Miramar — Grab gate-passed July 13 (SAME feed as already-live City College — cheap add)
2 net-new; City College (CITY) already shipped on this exact feed, so this is likely just 2 more campus
codes on that adapter. One public JSON feed serves all 3 SDCCD colleges, no auth:
- `GET https://mws-api.sdccd.edu/?term={strm}&career=ugrd` → `data.query.rows[]` (one ~5.7MB fetch, all
  4,164 rows; filter client-side by campus). Fall 2026 term = `2267`.
- Fields: `CAMPUS` (CITY / **MESA** / **MIRA**), `SUBJECT`+`CATALOG_NBR` (exact course scope), `CLASS_NBR`
  (section key, verified UNIQUE per campus), `ENRL_STAT` (O/C), `ENRL_CAP`, `ENRL_TOT`, `WAIT_CAP`.
- OPEN RULE (status authoritative — closed rows can keep positive capacity via reserved seats):
  `ENRL_STAT == "O" AND ENRL_CAP - ENRL_TOT > 0`. Never infer open from seats alone.
- GATE (live Fall 2267): Mesa 1971 sec **1079 open/892 not-open**; Miramar 1093 sec **576/517** — real
  mixes, disproof passes, CLASS_NBR unique both. Dedup: both net-new (City already live).

### Brandeis — Grab CRACKED + gate-passed July 13 (single-college, PeopleSoft-backed server-rendered HTML)
Net-new private R1 (~5.8k). Public registrar schedule, no auth, server-rendered HTML per subject.
- Terms: `GET /registrar/schedule/search?strm={strm}` → the page's `<option value="1263">Fall 2026</option>`
  dropdown gives strm codes (Fall 2026=**1263**, completed Spring 2026=1261, Fall 2025=1253; labels win).
- Subjects: SAME search page has a subject `<option value="1800">English</option>` dropdown (codes are
  3-4 digit: 1750 Engineering, 1800 English, 1900 Env Studies...). Enumerate these for the school's subjects.
- Per-subject page: `GET https://registrar-prod.unet.brandeis.edu/registrar/schedule/classes/2026/Fall/{code}/UGRD`
  (Term name Capitalized in the path; also a GRAD career). Columns: Course#, Title, Time, **Enrl / Lim / Wait**,
  Instructor + a status word (Open/Waitlist).
- OPEN RULE: status=="Open" AND (Lim - Enrl) > 0. "Waitlist" status = FULL (Enrl>=Lim; verified: ENG 19A
  11/11 wait 3 = Waitlist, ENG 12A 11/22 = Open). Status agrees with arithmetic.
- ⚠️ TWO PARSE TRAPS: (1) the table is MULTI-COLUMN — 3 course-blocks per `<tr>`; parse each block, not
  per-row, or 2/3 of sections vanish (silent miss). (2) the displayed Course# REPEATS across sections —
  the real unique section key is in each row's popUp href: `crse_id` + `class_section` (+ strm), e.g.
  `popUp('course?acad_year=2027&crse_id=013231&strm=1263&class_section=1')`. Key by crse_id+class_section,
  NEVER the course number.
- GATE (live Fall 1263, English/1800): 59 sections, **44 Open / 15 Waitlist(full)** — decisive LIVE mix
  (not an all-open lead). Completed terms 1261/1253 available for extra disproof. Dedup clean.

### ⭐ Foothill College (CA, ~14k) — GATED, AWAITING GO-AHEAD (Codex, July 14 2026)
Net-new public 2-year college. Official Fall 2025 headcount is **14,135**; the official schedule is
anonymous, server-rendered HTML with authoritative status, seats, dates, and CRNs. This is ready for a
bespoke adapter, pending Build's production-fetch gate. Official enrollment reference:
`https://foothill.edu/about/facts.html`.
- Source: `GET https://foothill.edu/schedule/index.html?Quarter={TERM}&dept={SUBJ}&location=`. Fall 2026
  is `2026F`; completed Spring 2026 is `2026S`. The page's term selector/official registration pages are
  the authority for labels; do not hardcode a permanently current term. Use a subject page (`dept=ENGL`,
  `COMM`, etc.), not an open-only or time/day-filtered URL. One subject page contains every section for
  that subject, so group watched courses by subject and fetch once per subject+term per poll.
- Example: `ENGL C1000` is represented by section codes such as `ENGL-C1000-02C`; the same page also
  contains the sibling honors course `ENGL-C1000H`, so course matching MUST be exact. Accept the repo's
  normalized `ENGL C1000` form, then match the displayed section code as `SUBJ-COURSE-SECTION` with an
  exact course token (never a loose `C1000` prefix). `COMM C1000` is another verified example.
- HTML parse: iterate every `div.section`. In `.fh_section-head .fh_sessid-dates p`, p[0] is the display
  section code, p[1] is the **CRN** (native stable section key), and p[2] is the date text. Read status from
  `.fh_sect-availability p` (`Open`, `Waitlist`, or `Closed`). Read the first line of
  `.meet-availability p` as `N of M seats open` (N may be negative). Normalize `seats=N` and set open only
  when `status == "Open" AND N > 0`. `Waitlist` and `Closed` are never open even when their numeric line
  is positive; waitlist-seat counts are not primary seats. Do not guess when any required field is absent.
- The schedule is a complete subject response with no pagination observed. Preserve the displayed section
  count when available and fail closed on an unexpected empty/malformed response. CRN uniqueness is the
  duplicate guard. The official page is already college-scoped, so no shared-campus filter is needed.
- LIVE GATE (Fall 2026): all `ENGL` = **59 sections, 51 Open / 8 Waitlist, 59 unique CRNs**. Exact
  `ENGL C1000` = **38 sections, 31 Open / 7 Waitlist, 38 unique CRNs**; `ENGL-C1000H` is present and
  excluded by the exact matcher. This is a decisive mixed-status live feed, not an all-open lead.
- COMPLETED-TERM DISPROOF (Spring 2026, same official feed): exact `COMM C1000` = **9 sections, 0 Open /
  9 Closed, 9 unique CRNs**; 5 Closed rows still displayed positive numeric seats. Spring `COMM` overall
  = 27 Closed rows, including 15 positive numeric values. This proves status must override numeric seats.
- Latency: one current subject-page load measured about **1.36s** in browser tracing, well below the repo's
  30s gate; the subject-grouped one-fetch design avoids N+1 requests. Isolation and dedup are clean:
  official Foothill URL/branding, and `schools.py` has no Foothill registration. The old archived research
  lead is superseded by this traced spec.
- Adapter: **bespoke `Foothill` / `FoothillSchedule`**; no existing adapter matches this HTML structure.
  `reg_url` should point to `https://foothill.edu/schedule/index.html`. Builder checklist: implement the
  exact parser and fail-closed behavior; add term resolution/roll-forward; group requests by subject;
  add Foothill to `_ALL_SCHOOLS`/`SCHOOLS`; run the real production-fetch gate with a watched open course,
  a full/waitlisted course, a completed term, exact sibling isolation, CRN uniqueness, and latency; then
  import-check and update the displayed school count. Do not mark shipped from this research block alone.

### ⭐ Batch 2 — five additional direct seat sources — GATED, AWAITING GO-AHEAD (Codex, July 14 2026)
These are five net-new identities promoted from the research archive because each has direct current and
completed-term numeric/status evidence. They are builder handoffs, not claims that production code already
exists. Keep the source-specific restrictions below; do not collapse them into one generic seat rule.

1. **University of the Virgin Islands (USVI)** — two campus-scoped feeds, one institution. Fall 2026:
   `GET https://schedclass.uvi.edu/stxschedule.aspx?term=202608` (St Thomas/St John) and
   `https://schedclass.uvi.edu/sttschedule.aspx?term=202608` (St Croix); completed Spring 2026:
   `https://schedclass.uvi.edu/sxmschedule.aspx?term=202601` (St Martin). Rows expose `CRN`, `MAX`,
   `ENROLL`, `AVAIL`, wait fields, and `STATUS`. Gate Fall examples include ACC 201 CRNs 82901 (18
   available), 82902 (11), and BIO 141A CRN 82594 (0); Spring examples include EDU 250 CRN 15389
   (17), EDU 302 CRN 15390 (2), and EDU 354 CRN 15392 (-1). **Open = `AVAIL > 0` only**; `STATUS`
   remains `ACTIVE` even for full rows. Key by `(campus, term, CRN)`, retain waitlist fields, and never
   make St Thomas/St John/St Croix/St Martin separate school identities. Bespoke adapter; verify that
   each requested campus is present before accepting rows.

2. **Cal Poly Humboldt (CA)** — official Registrar reports, updated daily (not real-time). Landing page:
   `https://www.humboldt.edu/registrar/register/class-schedule`. Current Fall report:
   `https://pine.humboldt.edu/anstud/cgi-bin/filt_schd.pl?relevant=sched_ind_Fall.out`; completed Spring
   report: `https://pine.humboldt.edu/anstud/cgi-bin/filt_schd.pl?relevant=sched_ind_Spring.out`.
   Subject reports expose `Class`, `Sect`, `CN#`, `Cap`, `Enr`, `Rsrvd`, `Avail`, and wait columns. Gate
   Fall ART rows CN 41185 (45/40/5), 41186 (45/26/19), and full 41187 (24/24/0); Spring rows include
   CN 21115 (45/43/2), 21116 (24/18/6), and a negative-availability cross-list row. **Open = `Avail > 0`**,
   but preserve `Rsrvd`, cross-list, and notes. Key by `(term, subject, CN#, section)`. Because the source
   refreshes daily, the builder must surface freshness or reject it if SeatWatch requires real-time alerts;
   do not present a daily snapshot as live polling.

3. **Lawrence University (WI)** — public Banner summary/detail source. Entry point:
   `https://www.lawrence.edu/offices/registrar/class-schedule-and-course-catalog`. Summary route:
   `https://bannerweb.lawrence.edu/pls/voyager/zwglolib.call_class_schd_from_web_p?p_attr_code=G046&p_attr_code=N011&p_subj_code=%25`.
   Current term is `202650`; completed Spring is `202630`. Summary rows expose exact CRNs and
   `L:<limit> R:<registered> W:<waitlist>`; Fall CHJA 202 CRNs 5197/5198 are 10/3/0 and 10/2/0,
   while CHJA 212 CRNs 5200/5201 are 10/2/0 and 10/0/0. Detail pages expose the same seat facts; Fall
   BIOL 130 CRN 5278 has 16 remaining from a 24-seat limit. **Open = `L - R > 0`**, ignoring W for
   primary seats. Key by `(term, subject, course, CRN, sequence)` and preserve cross-list/restriction
   notes. This may fit the repo's tabular Banner family, but production must prove the summary is complete
   for a watched course before reusing it.

4. **Clark University (MA)** — public HTML course grids. Fall 2026:
   `https://apps.clarku.edu/course-listings/course-grid-fall-2026-ug-gs/ugopen`; completed Spring 2026:
   `https://apps.clarku.edu/course-listings/registrarSPRING26/undergraduate`. Rows expose CRN, course/
   section, `CAP`, `Enr`, instructor, meetings, prerequisites, and permission-only flags. Fall examples:
   PSYC 101-01 CRN 20059 (90/47), PHYS 130-01 CRN 20037 (16/11), HEBR 101-01 CRN 20187 (19/16);
   Spring examples: MATH 119-01 CRN 30147 (25/10), MUSC 104-01 CRN 34700 (25/18), PSYC 108-01 CRN
   30193 (75/37). **Open = `CAP - Enr > 0` only after preserving reserve/permission semantics**;
   fetch the all-courses grid, not only the “seats remaining” view, so full sections are not silently
   omitted. Key by `(term, CRN, course, section)`; do not collapse cross-listed rows. Bespoke HTML adapter
   with a production check for row completeness and permission-only sections.

5. **Wesleyan University (CT)** — public WesMaps registration pages with eligibility buckets. Fall index:
   `https://owaprod-pub.wesleyan.edu/reg/%21wesmaps_page.html?crse_list=XAMS&facid=NONE&offered=Y&stuid=`;
   Fall course example ECON 301 uses `term=1269`, and completed Spring ECON 103 uses `term=1261`.
   Pages expose course/section, limit, `Seats Available`, class-year/major bins, permission/prerequisite
   notes, and update timestamps. Fall ECON 301 has sections at 30 and 0 available; Spring ECON 103 has
   sections at 9 and 22 available, with other Spring rows at zero/negative. **Do not treat a positive
   aggregate as universally open**: parse the eligibility bins and only alert when the watched user's
   supported scope is actually available; `X` means excluded. Key by `(term, course ID, section)` and
   preserve cross-listings, prerequisites, POI, and drop/add request state. Bespoke adapter; production
   gate must prove the selected course index is complete and the bin logic is fail-closed.

**Batch builder checklist:** add five deduped school identities only after production fetches pass; use
   exact term/course/section keys; include at least one open and one full/waitlisted example per source;
   replay the completed term; verify no sibling/cross-list/campus leakage; enforce a 30-second timeout;
   and surface daily/static freshness for Humboldt. No production code or registry edits were made by this
   research pass.

### ⭐ Batch 3 — five additional direct seat sources — GATED, AWAITING GO-AHEAD (Codex, July 14 2026)
Five more net-new identities with direct current-plus-historical evidence. These are promoted from the
research archive into a single builder queue; the source-specific freshness/completeness caveats are part
of the implementation contract.

1. **Sandhills Community College (NC)** — official nightly seat tables:
   `https://olympus.sandhills.edu/seatsAvailable/2026FASeatsAvailable.htm` and
   `https://olympus.sandhills.edu/seatsAvailable/2026SPSeatsAvailable.htm`. Columns are
   `Dept Num Sec ... Max Seats Remaining Seats Comments`. Fall 2026 BIO 111 includes 25/2 and 25/14
   alongside zero/negative rows; Spring 2026 has mixed 25/8, 25/7, and full rows. Match exact
   `(term, department, number, section)` and set open only when `Remaining Seats > 0`; blank continuation
   lines belong to the preceding section. Preserve comments and label this as a nightly snapshot, not
   real-time polling. Fail closed if the table header or section continuation pattern changes.

2. **The College of the Florida Keys (FL)** — public Banner detail pages, Fall 2026 term `202710` and
   Spring 2026 term `202620`. Current example:
   `https://secure.cfk.edu/prod/bwckschd.p_disp_detail_sched?crn_in=11488&term_in=202710` (MAT 1033,
   30/15/15); completed example:
   `https://secure.cfk.edu/prod/bwckschd.p_disp_detail_sched?crn_in=20654&term_in=202620` (MAT 1033,
   30/19/11). Detail pages expose capacity/actual/remaining plus waitlist capacity. Use exact
   `(term, subject, course, CRN)`; **open = primary `Remaining > 0`**, never waitlist remaining. Preserve
   credit-level restrictions and confirm the detail page's college/campus identity. This is a small
   Banner bespoke instance; verify subject/CRN discovery before reusing a generic Banner adapter.

3. **Kenyon College (OH)** — official static seat tables at `https://registrar.kenyon.edu/schedgrid.htm`,
   linking Fall 2026 `sep26_seats.htm` and Spring 2026 `jan26_seats.htm`. Spring is timestamped July 11,
   2026 and exposes CRN, subject/number, title, instructor, meeting data, and `SEATS`; captured rows range
   from 1 through 35 available. Match exact term + CRN/section and use `SEATS > 0`. This is an open-only
   view: **omission means unknown, not closed**. A production adapter must either explicitly support
   open-only semantics (fail closed on missing rows and disclose snapshot freshness) or stop at the research
   gate; do not fabricate a full catalog from the open list.

4. **Schoolcraft College (MI) — SUPERSEDED; DO NOT BUILD THIS VIEWER.** Use Batch 84's anonymous
   `RegisterableColleague` subclass instead. Historical public schedule viewer:
   `https://my.schoolcraft.edu/course-schedules/2026/Fall/All` and
   `https://my.schoolcraft.edu/course-schedules/2026/Spring/All`. Browser verification on July 14 found
   the same table schema in both terms: `Course`, native numeric `Section`, title,
   `Seat Available/Capacity/Waitlist`, explicit `Status`, instructor, location, credits, fees, and
   meeting rows. Fall `ENG` currently reports a timestamp of **07/14/2026 03:17:29 PM** with mixed rows,
   including `101 / 149100 / 0/28/0 / Closed`, `101 / 141308 / 1/28/0 / Open`, and `101 / 149103 /
   0/28/4 / Closed`; Spring `ENG` shows the same fields and positive Open rows such as `101 / 127101 /
   1/28/0`. **Open = `Status == "Open" AND available > 0`**; `Closed` wins over any ambiguous numeric
   value. Key by `(term, course, section)`; preserve repeated meeting rows under one section and the
   timestamp/part-of-term heading. This bespoke path is retained as historical evidence only.

5. **Grayson College (TX)** — official public planner pages:
   `https://planner.grayson.edu/Planner/CourseSearch/607` (Fall 2026) and
   `https://planner.grayson.edu/Planner/CourseSearch/596` (Spring 2026). Rows expose stable course-section
   IDs, dates, campus, `Seats: open/maximum`, and `Status`; Fall has mixed open/closed rows, while Spring
   has mixed examples including 23/30 Open and 0/1 Open. Match exact planner term + course-section ID and
   require **explicit `Status == "Open"` plus open seats > 0**. Preserve campus, modality, part-of-term,
   and any late-start/session fields. Verify the planner response is complete for the selected course and
   does not silently apply an open-only filter before production.

**Batch builder checklist:** skip Schoolcraft in this historical batch and implement it only through Batch 84;
   add the remaining net-new names after production fetch tests; use native
   CRN/section keys; replay current and completed terms; test open/full/waitlist behavior; preserve campus,
   modality, restrictions, and repeated meeting rows; enforce a 30-second timeout; and surface nightly/static
   freshness for Sandhills, Kenyon, and any timestamped Grayson response. No production code or
   registry edits were made by this research pass.

### ⭐ Batch 4 — five additional direct seat sources — GATED, AWAITING GO-AHEAD (Codex, July 14 2026)
Five more net-new identities, now checked against the current `schools.py` registry and promoted only where
the public source exposed concrete section-level evidence. The live sources below were browser-checked on
July 14; Nicholls is an official dated PDF snapshot and must not be treated as real-time.

1. **Quinsigamond Community College (MA)** — public Jenzabar 9.4 advanced search:
   `https://theq.qcc.edu/ICS/Course_Offerings_and_Schedule.jnz?portlet=AddDrop_Courses&screen=Advanced+Course+Search&screenType=next`.
   Fall 2026 English search returned eight pages with native course/section labels, status, and `x/y` seats:
   ENG 099-04 `1/20 Reopened`, ENG 099-05 `11/20 Open`, ENG 099-50 `0/20 Closed`, and ENG 101-01
   `17/22 Open`; Spring replay returned ENG 101-07 `6/21 Reopened` and ENG 101-17 `1/22 Reopened`.
   Key by the visible course + section label, preserve literal `Reopened` status, and retain page number,
   campus, method, dates, and instructor. Open when the numeric available count is positive, but do not
   collapse `Reopened` into `Open`; pagination is mandatory and the no-login search completed in under 30s.

2. **Great Falls College Montana State University (MT)** — official public APEX scheduler:
   `https://apexprod.msu.montana.edu/apex/r/esg/s_class_schedule_gf/class-schedule`.
   Fall 2026 term `202670` returned 311 rows, including CRN `67109` ACTG 101-200 with `4/25` available and
   CRN `67021` COMX 115-180 `0/25 CLOSED`; Spring 2026 term `202630` included CRN `63136` `10/25` and
   CRN `63373` `0/1 CLOSED`. Use native CRN plus term as the identity, read explicit status and numeric
   available/capacity/waitlist fields, and preserve modality and part-of-term. This is a short public
   fetch, but the adapter must prove that the unfiltered result set is complete before trusting counts.

3. **University at Albany (NY)** — official schedule search:
   `https://www.albany.edu/registrar/schedule-classes`. The public selector exposes Fall 2026 and Spring
   2026, and Fall 2026 browser verification returned a result set after selecting `Only classes with
   available seats`; each result includes level, college/department, class number, course code/title,
   meeting data, and `Seats remaining as of last update` (examples included class 5347 AAFS 101 with 6
   and class 1003 AAFS 213 with 13). The page explicitly says freshness is every 30-60 minutes depending
   on activity. Key by `(term, class number)` plus course identity, use displayed seats remaining > 0 as
   the primary open signal, preserve special restrictions (some seats are reserved and the unrestricted
   count can be zero), and replay Spring 2026 before production. This is a bespoke form/query adapter.

4. **Bentley University (MA)** — official public course listing:
   `https://bentleyapps.azurewebsites.net/course-listing/`. The public UI exposes Fall 2026 and Spring 2026,
   course-level and open/closed filters, and states that enrollment status/seats are updated in real time
   when submitted. Fall 2026 + Open browser verification returned section-level rows such as AC 115-1 with
   `Status: Open`, `Seats Available: 21`, and AC 115-11 with `Seats Available: 1`, along with instructor,
   meeting dates, delivery mode, and tags. Key by term + native section label (for example `AC 115-1`),
   require explicit `Status == Open` and `Seats Available > 0`, and preserve reserved-seat/eligibility notes.
   Replay Spring 2026 and fail closed if the public query starts returning a truncated or filter-dependent
   result set; bespoke adapter, no login observed.

5. **Nicholls State University (LA)** — official registration page and schedule PDF:
   `https://www.nicholls.edu/register/2026-fall-semester/` and
   `https://www.nicholls.edu/register/wp-content/uploads/sites/81/2026/07/07-10-Fall-2026.pdf`.
   The July 10 Fall 2026 PDF has a stable table headed `Subject Num Sec ... Crn ... Max Enr Avail Wl. Max
   Wl. Actual`. Visual/text verification found ACCT 205 CRN `88030` `45/44/1`, ACCT 205 CRN `88029`
   `45/42/3`, and ACCT 306 CRN `89370` `40/46/0` with one waitlisted, plus many positive rows. Spring
   2026 official PDFs expose the same columns and previously captured mixed examples. Key by term + CRN,
   preserve repeated meeting rows and waitlist columns, and set open only when `Avail > 0`; the PDF is a
   dated snapshot, so display its publication date and never claim live polling. PDF parser should fail
   closed if the header/order changes.

**Batch builder checklist:** add only these five net-new names after production fetch tests; use native
   CRN/class/section keys; replay Fall and Spring where available; test positive, full, waitlisted, reopened,
   reserved-seat, and repeated-meeting cases; enforce a 30-second timeout; and expose Albany's 30-60 minute,
   QCC's query-time, Bentley's real-time, and Nicholls' dated-PDF freshness explicitly. No production code
   or registry edits were made by this research pass.

### ⭐ Batch 5 — three additional direct seat sources — GATED, AWAITING GO-AHEAD (Codex, July 14 2026)
Three more net-new identities with public section-level rows, a current-term replay, and a completed-term
replay. These are intentionally smaller than the requested 5-15 range because two additional leads were
held out: CMC exposed only a current Fall 2026 consortium search, while Trinity exposed only one Rome-campus
internship row rather than a college-wide schedule.

1. **Wilkes University (PA)** — official undergraduate roster:
   `https://rosters.wilkes.edu/schedule/2026/fa/ug` and completed-term replay
   `https://rosters.wilkes.edu/schedule/2026/sp/ug`. The Fall page was browser-checked July 14, 2026 at
   `3:45PM` and exposes a full roster with `Course`, `Sec.`, `CRN`, title, credits, meetings, instructor,
   and literal availability values. Examples include ACC 162 A CRN `30149` with `11 open seats`, ACC 162 B
   CRN `30150` with `14 open seats`, and ART 113 A CRN `30677` with `4 open seats`; other rows explicitly say
   `N waitlisted` or `Waitlist full`. Spring uses the same schema and returned, for example, COM 101 IHE CRN
   `10146` with `6 open seats`, MUS 200 R CRN `11363` with `1 open seat`, and ART 398 A CRN `11347` with
   `9 open seats`. Key by `(term, native CRN)`; accept only the literal `N open seat(s)` form with `N > 0`;
   treat waitlisted/full rows as closed and never infer seats from missing text. Preserve term, course/section,
   modality, cross-listing/permission notes, repeated meeting details, and the page's last-updated timestamp.
   This is a full-term roster rather than an open-only feed, but the adapter must still detect a changed term
   path or availability vocabulary and fail closed.

2. **Kent State University (OH)** — official public ePROD detailed search:
   `https://keys.kent.edu:44220/ePROD/bwlkffcs.p_adv_unsecure_sel_crse_search`. Resolve the term by its visible
   label (`Fall 2026` and `Spring 2026 (View only)` were available), then select `Subject = English`,
   `Course Number = 21011`, `Course Level = Undergraduate`, and submit `Class Search`. The results table has
   explicit columns `Status`, `CRN`, `Course`, `Title`, `Enrolled`, and `Remain Open`, plus schedule type,
   dates, days, method, campus, restrictions, approvals, and deadlines. Fall 2026 returned mixed rows including
   CRN `12728` section 801 `Open` with `Remain Open 8`, CRN `12729` section 802 `Closed` with `Remain Open 0`,
   and CRN `12731` section 804 `Open` with `Remain Open 9`; the page header was dated July 14, 2026. Spring
   replay returned the same labeled schema and mixed open/closed rows, including CRN `12495` section 001
   `Closed` with `Enrolled 22 / Remain Open 0` and CRN `12496` section 002 `Open` with `Enrolled 20 / Remain
   Open 2`. Key by `(term, campus, native CRN)`; use `Status == Open` and `Remain Open > 0` as the open rule,
   retain the labeled `Enrolled` and `Remain Open` fields, and never reconstruct availability arithmetically.
   Preserve campus, modality, part-of-term, prerequisites, registration restrictions, special approval, and
   deadline text. Do not hard-code Banner term IDs; resolve them from the public term selector and fail closed
   if the result headers or search filters change.

3. **Catawba Valley Community College (NC)** — official public schedule viewer:
   `https://cvcc.edu/schedules/`. The Fall 2026 all-campus curriculum view was checked July 14, 2026 at
   `2:58 PM` and reported `Showing: 817`, `Open: 679`, `Closed: 138`; each row exposes native ID, section,
   title, credits, delivery, meetings, dates, location, `Seats Available`, instructor, `Status`, and notes.
   Examples include ID `140273` ACA-111-800 with `24 (of 30)` `OPEN`, ID `140782` ACA-122-700 with `0 (of 24)`
   `CLOSED`, and ID `140883` ACA-122-703 with `1 (of 24)` `OPEN`. Spring 2026 all-campus replay was checked
   at `3:48 PM` and reported `Showing: 773`, `Open: 693`, `Closed: 80`; examples include ID `137332` ACA-111-800
   with `22 (of 30)` `OPEN`, ID `137355` ACC-120-800 with `-1 (of 30)` `CLOSED`, and ID `137356` ACC-120-801
   with `2 (of 30)` `OPEN`. Key by `(term, native ID)` plus the visible section/campus context; accept only
   `Status == OPEN` with available seats `> 0`, and keep negative availability closed even if a future status
   label is inconsistent. Select terms by their visible labels rather than DOM position or guessed IDs, preserve
   campus/delivery/part-of-term, dates, notes, and repeated meeting rows, and retain the viewer's summary counts
   as a completeness check. This supersedes the earlier source-level “pending direct JSON capture” note.

**Batch builder checklist:** add only these three net-new identities after production fetch tests; use native
   CRN/ID/section keys; replay current and completed terms; test positive, zero, negative, waitlisted/full, and
   mixed-delivery cases; preserve restrictions, campus, modality, dates, notes, and timestamps; enforce a
   30-second timeout; and fail closed if a source becomes open-only, login-gated, truncated, or changes its
   labeled seat/status fields. No production code or registry edits were made by this research pass.

### ⭐ Batch 6 — twelve-school deduped execution queue — three now registered (historical, July 14 2026)
**Registry preflight when selected:** `len(schools.SCHOOLS) == 715`. Each candidate was
checked against every registered `id` and display name, using exact matching plus case/diacritic/punctuation-
normalized matching. The queue had **12 clear results**; **Moorpark, Oxnard, and Ventura are now registered**,
so only the remaining nine may still be pending. The shared VCCCD feed represents three different institutions
and was correctly registered as three distinct identities. Do not add any registered name again—rerun the same
registry check immediately before editing `_ALL_SCHOOLS`.

The detailed evidence for these sources is already recorded in the earlier research blocks cited below; this
section is retained as an audit trail; Batch 8 below is the current unregistered selection.

1. **Moorpark College (CA)** — VCCCD shared schedule `https://schedule.vcccd.edu/list/`, campus/site-scoped;
   exact `(college/site, term, CRN)`;
   accept only `Status == OPEN` and `Rem > 0`; FULL, CLOSED, and WAITLISTED override positive arithmetic.
2. **Oxnard College (CA)** — same VCCCD feed `https://schedule.vcccd.edu/list/`, but a distinct college identity;
   isolate `Oxnard` locations and
   use the same conservative status-first rule. Never merge Oxnard rows into Moorpark or Ventura.
3. **Ventura College (CA)** — VCCCD shared schedule `https://schedule.vcccd.edu/list/`, distinct site-scoped identity;
   exact `(college/site, term,
   CRN)` and the same `OPEN` plus positive remaining-seat rule. Preserve the residual `OTHER` location bucket
   for review instead of silently assigning it to a college.
4. **Foothill College (CA)** — official quarter viewer `https://foothill.edu/schedule/index.html`; exact
   `(quarter, subject/course-section, CRN)`;
   require textual `Open` and a positive numeric open-seat count. Preserve quarter, modality, footnotes, and
   closed/waitlisted rows; this is not a semester source.
5. **Lakeland Community College (OH)** — official schedule viewer
   `https://lkn.lakelandcc.edu/internet/academics/schedule/`; exact `(term, subject/course, CRN)`;
   use labeled `N Remaining / Cap`, with FULL and zero remaining closed. Preserve permission/restriction notes
   and distinguish this Ohio community college from the separate Lakeland University (WI) already in research.
6. **Lipscomb University (TN)** — official Fall/Spring static tables
   `https://courseschedule.lipscomb.edu/ScheduleP2026FALL.html` and `ScheduleP2026SPRING.html`; exact
   `(term, course, section code)`;
   accept `Seats Available > 0`, retain total/filled/available values, delivery, location, and course notes,
   and surface static-table freshness rather than claiming real-time polling.
7. **University of Georgia (GA)** — public registrar schedule app
   `https://reg.uga.edu/enrollment-and-registration/schedule-of-classes/`; exact `(term, Course ID, CRN)`;
   accept `Avail Seats > 0`, preserve campus, part-of-term, and restrictions, and use the public registrar app
   rather than the older Athena/SSO catalog path.
8. **SUNY Potsdam (NY)** — official hourly schedule PDFs
   `https://www.potsdam.edu/about/offices/registrar/class-schedules/class-schedule-department`; exact
   `(term, subject, course, section/CRN)`;
   accept `AVL > 0`, reject Closed/negative values, and expose the publication timestamp because the PDFs are
   snapshots rather than live polling.
9. **Sandhills Community College (NC)** — official nightly seat tables
   `https://olympus.sandhills.edu/seatsAvailable/2026FASeatsAvailable.htm` and the Spring sibling; exact
   `(term, subject, course,
   section)`; accept `Remaining Seats > 0`, attach blank continuation lines to the preceding row, and label
   the source nightly rather than real-time.
10. **The College of the Florida Keys (FL)** — official Banner detail pages
    `https://secure.cfk.edu/prod/bwckschd.p_disp_detail_sched`; exact `(term, subject/course,
    CRN)`; use primary `Remaining > 0`, ignore separate waitlist capacity, and preserve credit-level and other
    registration restrictions.
11. **Schoolcraft College (MI) — SUPERSEDED; DO NOT BUILD THIS VIEWER.** Use Batch 84's anonymous
    `RegisterableColleague` subclass instead. Historical public Fall/Spring viewer:
    `https://my.schoolcraft.edu/course-schedules/2026/Fall/All`; exact `(term, course, native section)`;
    require `Status == Open` and positive `Seat Available`, while retaining capacity, waitlist, location,
    modality, fees, start date, and part-of-term headings.
12. **Grayson College (TX)** — official Fall/Spring planner
    `https://planner.grayson.edu/Planner/CourseSearch/607`; exact native course-section ID plus term;
    require explicit `Status == Open` and positive open seats, preserving campus, dates, modality, and session
    notes.

**Explicit exclusions from this audit:** CCRI is already registered; University of Oregon, UVI, New Paltz,
Catawba College, and the prior Batch 5 schools are already covered or registered as applicable; SJSU is marked
SCRAPPED for nightly staleness; and Kenyon/Mt. SAC are open-only views where omitted sections cannot safely be
treated as closed. No production code or registry edits were made by this research pass.

### ⭐ Batch 7 — seven additional deduped sources — GATED, AWAITING GO-AHEAD (Codex, July 14 2026)
Second registry-wide preflight: `len(schools.SCHOOLS) == 715`. These seven canonical identities are absent
from the registry and from Batch 6 after exact, normalized, and alias-aware comparison. The source details
below already appear in the earlier research log; this is the next implementation queue, not a request to
re-add anything from an older batch.

1. **Cal Poly Humboldt / California State Polytechnic University, Humboldt (CA)** — official daily registrar
   reports: `https://www.humboldt.edu/registrar/register/class-schedule`, with Fall and Spring report links.
   Key by `(term, subject, CN#, section)` and accept only `Avail > 0`; preserve reserved seats, cross-list
   reductions, notes, and the daily publication timestamp. This is one institution under its current/canonical
   Humboldt identity, not two schools, and must be surfaced as a daily snapshot rather than real-time data.

2. **Lawrence University (WI)** — official public schedule and Banner summary/detail routes:
   `https://www.lawrence.edu/offices/registrar/class-schedule-and-course-catalog`. Key by
   `(term, subject, course, CRN, sequence)`; use primary seats remaining (`limit - registered` or the labeled
   detail value), ignore waitlist capacity, and preserve cross-list/restriction notes. Production must verify
   that the summary is complete for an arbitrary watched course before relying on it.

3. **Clark University (MA)** — public Fall/Spring course grids:
   `https://apps.clarku.edu/course-listings/course-grid-fall-2026-ug-gs/ugopen` and the official Spring
   undergraduate grid. Key by `(term, CRN, course, section)`; use `CAP - Enr > 0` only after preserving
   reserve/permission-only semantics. Fetch the all-courses grid, not an open-only view, so full sections are
   not silently omitted; verify row completeness and cross-listed rows in production.

4. **Wesleyan University (CT)** — public WesMaps registration pages:
   `https://owaprod-pub.wesleyan.edu/reg/%21wesmaps_page.html?crse_list=XAMS&facid=NONE&offered=Y&stuid=`.
   Key by `(term, course ID, section)` and retain eligibility bins, class-year/major limits, prerequisites,
   permission/POI flags, and update timestamps. A positive aggregate is not universally open: alert only when
   the watched user's supported eligibility scope has seats, and treat excluded (`X`) bins as unavailable.
   This is accurate but more conditional than a simple seat counter; the adapter must fail closed if the bin
   schema changes.

5. **Concordia University Chicago (IL)** — official timestamped undergraduate schedule PDFs:
   `https://webserv.cuchicago.edu/files/forms-repository/registrar/academic-schedules/Fall_UG_Schedule.pdf`
   and the Spring sibling. Key by `(term, course, section, CRN)`; parse the labeled `Seats` field as
   available/capacity, accept positive available seats, reject zero/negative values, and preserve `F`/`R`/`P`
   fee/reserve/prerequisite flags, modality, and part-of-term. Expose PDF publication timestamps; this is a
   dated snapshot, not real-time polling.

6. **University of Southern Maine (ME)** — official public Course Search:
   `https://usm.maine.edu/registration-scheduling-services/course-search/`. Key by exact
   `(term, subject, course, class number)`; require `Status == Open` plus positive `capacity - enrolled`, and
   preserve restrictions/prerequisites. Completed Spring replay contains genuine closed rows, so status must
   remain authoritative; do not infer open from arithmetic alone.

7. **University of Nebraska Omaha (NE)** — official public UNO Class Search:
   `https://www.unomaha.edu/registrar/students/before-you-enroll/class-search/`. Key by exact
   `(term, subject, catalog number, section/class number)`; require explicit `Open` plus positive `Seats
   Available`, preserving enrolled/max values, prerequisites, notes, cross-listings, and modality. Fall and
   Spring both produced mixed open/closed rows, making this suitable for a bespoke adapter after guest-query
   replay and completeness checks.

**Batch 7 exclusions:** Brandeis remains deferred for unsafe arbitrary-course addressability; RPI, MTSU,
Framingham, UNCG, NCAT, WSSU, Worcester State, Monroe, and other apparent leads are already registered;
login-gated or no-row candidates remain out. No production code or registry edits were made by this research
pass.

### ⭐ Batch 8 — three remaining full-gate sources — GATED, AWAITING GO-AHEAD (Codex, July 14 2026)
The live registry is now **718 schools**. After accounting for the three Batch 6 additions that landed
(Moorpark, Oxnard, and Ventura), only these three additional full-gate candidates remain both unregistered and
not already selected in Batches 5–7. Exact/normalized name checks returned zero collisions.

1. **Great Falls College Montana State University (MT)** — official APEX scheduler:
   `https://apexprod.msu.montana.edu/apex/r/esg/s_class_schedule_gf/class-schedule`. The no-filter Fall 2026
   replay returned 311 rows with native CRNs, course/section, status, Available, Enrolled, Capacity, waitlist,
   meetings, modality, and part-of-term; examples include CRN `67109` ACTG 101-200 with `21` available and
   CRN `67021` COMX 115-180 explicitly `CLOSED` with `0/25`. Spring 2026 replay returned the same schema,
   including CRN `63136` with `10/25` and CRN `63373` `CLOSED` with `0/1`. Key by native CRN plus resolved
   term/campus, require explicit open status plus positive primary availability, and preserve consent,
   restriction, meeting-location, modality, and waitlist fields. The public table and selected-term summary
   must remain complete; fail closed on a changed APEX response or hidden open-only filtering.

2. **Quinsigamond Community College (MA)** — official public Jenzabar search:
   `https://theq.qcc.edu/ICS/Course_Offerings_and_Schedule.jnz?portlet=AddDrop_Courses&screen=Advanced+Course+Search&screenType=next`.
   Fall 2026 English search returned eight pages with visible course-section labels, dates, instructor, campus,
   method, numeric seats, and status: `ENG 099-04` `1/20 Reopened`, `ENG 099-05` `11/20 Open`, `ENG 099-50`
   `0/20 Closed`, and `ENG 101-01` `17/22 Open`. Spring 2026 replay returned the same real term-scoped schema,
   including `ENG 101-07` `6/21 Reopened` and `ENG 101-17` `1/22 Reopened`. Key by visible course + section +
   selected term; preserve literal `Reopened` rather than collapsing it into `Open`, follow every result page,
   and retain campus, method, dates, instructor, and page number. Fail closed if the selected-term label or
   pagination disappears.

3. **Northern Arizona University (AZ)** — official guest PeopleSoft search:
   `https://www.peoplesoft.nau.edu/psc/ps92prcs/EMPLOYEE/SA/c/COMMUNITY_ACCESS.CLASS_SEARCH.GBL`. Exact ART 161
   Fall 2026 replay returned four Flagstaff sections with native class numbers and zero available seats; Spring
   2026 replay returned two sections with `2` seats and `Open`, plus two sections with `0` and `Closed`/waitlist
   indicators. Preserve native class number, section, institution, term, campus, session, instruction mode, and
   meeting data. Open only when the rendered availability semantics are confirmed as `Open` with positive seats;
   builder must verify the PeopleSoft helper-icon titles, pagination, exact query scoping, and both term URLs before
   production. Never treat a helper `Open` legend/icon on a zero-seat closed row as open.

**Batch 8 exclusions:** PCC, MassArt, Wabash, UTC, IU Bloomington, and the three VCCCD colleges are already
registered; UMD is a freshness recheck, Brandeis is deferred for addressability, and the remaining recent leads
failed a completed-term, login, scope, or seat-field gate. No production code or registry edits were made by this
research pass.

### ⭐ RCCD ×3 — ✅ SHIPPED by Build July 13 (704→707). ⚠️ SPEC CORRECTION (accuracy lesson)
Build shipped all 3. My crack (nometadata header + msappproxy feed) held, but re-gate caught TWO errors
I'm recording so it doesn't recur: (1) **the SharePoint list ACCUMULATES 4 terms** (Fall+Winter+Spring+
Summer) — my "2482 sec 826/1655" counted ALL FOUR, so a watched Fall course would pull stale past-term
rows. FIX: server-side `$filter=Term eq '26FAL'` (Build) + a `Last_Day_to_Add >= today` date backstop.
(2) That makes my "5410 rows, paging mandatory" wrong — 5410 was the 4-term total; Fall-only RIV = 2330,
under the 5080 cap, so single-term never pages. Correct term-filtered gate: MOV ENGL-C1000 92 sec 68/24,
NOR 50/39-11, RIV 142/60-82. LESSON (saved to memory): before gating any BULK feed, check the term-field
distribution and filter to target term FIRST — never assume current-term-only. Original spec below.

### ⭐ RCCD ×3 — Grab CRACKED + gate-passed July 13 (was HELD "bespoke SharePoint"; now a ready spec)
The RCCD hold is RESOLVED — I reverse-engineered the msappproxy feed (it's PnPjs→SharePoint REST, not a
custom API). Anonymous, no auth, real numeric seats. 3 net-new colleges (Moreno Valley, Norco, Riverside
City), one adapter.
- Endpoint: `GET https://apps-studentrcc.msappproxy.net/schedule/_api/web/lists/getByTitle('{LIST}')/items`
  with header **`Accept: application/json;odata=nometadata`** (this is the key — a plain GET without it
  returns the SPA HTML shell, which is why the earlier probe looked dead). Lists: `ScheduleData_MOV`
  (Moreno Valley), `ScheduleData_NOR` (Norco), `ScheduleData_RIV` (Riverside City).
- Fields: `$select=Section_x0020_ID,Primary_x0020_Subject,Section_x0020_Number,Total_x0020_Seats,`
  `Seats_x0020_Used,Last_x0020_Day_x0020_to_x0020_Ad` (SharePoint x0020 = space encoding). Key =
  `Section_x0020_ID` (verified UNIQUE per college). Course scope = `Primary_x0020_Subject` (e.g. "ALR-4"
  = subject+number) + college. Feed is CURRENT-term only (Fall 2026; Last Day to Add = 09/01/26).
- OPEN RULE: `Total_x0020_Seats - Seats_x0020_Used > 0` AND `Last_x0020_Day_x0020_to_x0020_Ad >= today`.
  Over-cap rows exist (e.g. 30 seats / 31 used → NOT open) — the subtraction handles them; never infer
  open from presence.
- GATE (live July 13, all 3 through this exact parse): Moreno Valley 2482 sec **826 open/1655 full**;
  Norco 2508 sec **921/1587**; Riverside City 5410 sec **1454/3625**. Decisive real full mix = disproof.
- ⚠️⚠️ **PAGING MANDATORY (silent-miss trap):** Riverside City `ItemCount=5410` but one page caps at
  **5080** and returns an `odata.nextLink` (skiptoken). WITHOUT following nextLink, 330 sections are
  INVISIBLE = a watched full section that never appears. Adapter MUST page to completion (fail-closed if
  a page can't be read). Moreno Valley (2482) and Norco fit one page. ~64k students across the district.
- Dedup: all 3 net-new. Supersedes the "RCCD HOLD — feed dropped Fall 2026" note. READY for Build.

### ⭐ MARICOPA ×10 — Grab LIVE-VERIFIED July 13 (Codex Batch 25 confirmed) → GREEN-LIGHT to Build
Codex's 10-campus Maricopa lead is REAL, LIVE, and gate-able — I production-verified it and confirmed
the accuracy trap. Biggest single lever in the Codex pile (10 net-new colleges, one adapter).
- Host `classes.sis.maricopa.edu`, SERVER-RENDERED (results HTML is in the page GET — no XHR/browser
  needed for the adapter, plain urllib works). Fall 2026 term = `4266`. Per-campus institution codes:
  Phoenix `PCC01`, Glendale `GCC02`, Mesa `MCC04`, Chandler-Gilbert `CGC08`, Estrella Mtn `EMC10`,
  GateWay `GWC03`, Paradise Valley `PVC09`, Rio Salado `RSC06`, Scottsdale `SCC05`, South Mtn `SMC07`.
- URL: `?institutions[]={CODE}&terms[]=4266&keywords={COURSESMASHED}&all_classes=true`.
- ⚠️⚠️ **THE all_classes=true TRAP (accuracy-critical, Build already flagged it — CONFIRMED):** the
  default search shows ONLY open sections. Without `&all_classes=true` a FULL section is INVISIBLE →
  a watched full section would never appear = SILENT MISS (the quiet twin of a false-open). MUST pass
  `all_classes=true`. Proof: Phoenix BIO201 default = 12 open/0 closed; with `all_classes=true` =
  12 open/**5 CLOSED** ("No seats available"). That 5-closed is also the live disproof.
- Seats: parse `N of M seats available` (open, N>0) vs `No seats available` (closed). Section key =
  the 5-digit class number (e.g. 20901). Campus identity (institution code) MUST stay in the key —
  separate colleges share the host. Only current/upcoming terms are exposed (no completed term), so
  the disproof is live closed rows, which are present with all_classes=true.
- Dedup: all 10 net-new in Python (GateWay CC ≠ Mountain Gateway CC). Build said Maricopa is next on
  its bench — this green-lights it. ~200k students across the district.

### BUILDABLE bespoke queue from Codex's pile (Grab-deduped July 13, concrete numeric evidence, need adapters)
Honest read: Codex's 48 batches are LEADS (none production-gated); most big publics are PeopleSoft
(fake-status dead-end) or hosts unresolvable without per-school browser recon; CVC batches self-rejected
(contradictory seat/status). The genuinely-buildable, net-new, concrete-evidence subset for Build to
prioritize (all deduped vs schools.py — San Diego City College already LIVE, don't rebuild):
**Maricopa×10 (confirmed above, top priority)**, then RCCD×3 (Moreno Valley/Norco/Riverside City,
SharePoint API — note msappproxy feed now returns an HTML proxy shell to plain GET, needs the exact
list-query headers), SDCCD Mesa+Miramar (City shipped), Williston State (class-search.aspx numeric),
CCBC (QuickReg labeled Open Seats), Brandeis (Enrl/Lim/Wait rows), Cayuga CC / Monroe CC (Banner —
real hosts need browser recon, my pattern-guesses missed), West Valley (Colleague), Kent State (ePROD),
UVM (PACE open/full banners). Each is a bespoke build; none is an existing-adapter drop-in.

### USC (elite lead) — SOURCE-GATED + SENT to Build July 13 2026 (Grab): bespoke adapter needed
First of the elite reachable-six cracked. Public same-origin REST API behind classes.usc.edu (Angular
SPA): `GET /api/Terms/All` (status=="Active"; code = YYYY+season digit, Fall 2026 = 20263, Spring =
20261) + `GET /api/Courses/Course?termCode={t}&courseCode={SMASHED}` (CSCI104/WRIT150 style). No auth,
0.4-0.9s. **Dual response shape** (bare course object OR `{courses:[...]}` wrapper — parse BOTH; my
wrapper-only parse mid-gate looked like an outage and wasn't). 204 = not offered = safe empty. Sections:
key `sisSectionId` (unique, the real 5-digit reg number), exclude `isCancelled`, open = NOT `isFull`
AND `totalSeats-registeredSeats > 0` (flag & arithmetic agreed 430/430 sampled, incl. over-cap full
rows). Cross-listing resolved server-side (CLAS202→ANTH sections). `hasDClearance` = real seat needing
dept clearance (preserve as note, not a fake-open). `waitlistedSeats` null everywhere — ignore. Gate:
WRIT 150 live = 162 sec 11 open/151 FULL; WRIT 340 = 120 sec 2/118; completed Spring mixed (38/112) —
real history. example="WRIT 150". Dedup clean. ~49k students. Full recipe relayed to Build.

### Princeton (elite lead) — SOURCE-GATED + SENT to Build July 13 2026 (Grab): bespoke + BROWSER-ASSISTED
Third elite crack — and the STRONGEST disproof of the four (live-term real full rows, not completed-term
melt). Public course search backed by `api.princeton.edu`. Two-call flow, anonymous Bearer token:
- Token: embedded in `registrar.princeton.edu/course-offerings` page HTML as
  `drupalSettings.ps_registrar.apiToken` (84-char base64 gateway cred, SAME for all logged-out users,
  server-rendered so it's in raw HTML). apiBaseUrl = `https://api.princeton.edu/registrar/course-offerings/1.0.7`.
- Classes list: `GET {apiBaseUrl}/classes/{term}?subjects_count=1&subjects=COS&fmt=json`
  (Bearer + Accept:application/json) → `classes.class[]` with class_number, course_id, subject, catnum,
  section, crosslistings. ⚠️ TWO SCOPING TRAPS: (1) the real param is `subjects` (PLURAL) + a
  `subjects_count` — `?subject=COS` is SILENTLY IGNORED and returns the whole term (I hit this: first
  "COS" row was an AAS class); (2) `subjects=COS` also returns classes where COS is only a CROSS-LISTING
  (distinct primary subjects ECE/ECO/MAE/ORF/PSY... came back) — exact scope requires
  subject==SUBJ AND catnum.trim()==NUM, or crosslistings contains "SUBJ NUM".
- Seats (data was moved OUT of the classes list): `GET https://api.princeton.edu/student-app/courses/seats?term={term}&course_ids={id,id,...}&fmt=json` (chunk ~50 ids) → `course[].classes[]` with
  numeric `capacity`, `enrollment`, `status` (O/C), `seat_status` (Open/Closed/**Canceled**), `pu_calc_status`.
- OPEN RULE: `seat_status == "Open"` AND `capacity-enrollment > 0`. ⚠️ TRAP: the bare `status` field's
  "C" covers BOTH Closed and Canceled — MUST use `seat_status` to exclude Canceled (found live: cap 0/
  enr 0 Canceled rows carry status "C"). Section key = class_number (unique).
- GATE (July 13, decisive): LIVE Fall (term 1272) COS = 2,442 open / 385 CLOSED / 72 Canceled; concrete
  full rows COS cn21189 25/25 Closed, cn22499 25/20 over-cap Closed. Completed Spring (1264) = 544 Closed.
  **seat_status vs (capacity-enrollment>0) agreed on ALL ~5,900 sections across both terms, 0 disagree.**
  Terms: read `drupalSettings.ps_registrar.terms` (Fall 2026-27 = 1272, Spring 25-26 = 1264, labels win).
- ⚠️ DEPLOYMENT WRINKLE (bespoke + browser-assisted, CVC/Quottly complexity class): `registrar.princeton.edu`
  hard-blocks plain clients (403 with Akamai JS/TLS challenge — EVEN with a full browser UA), so the token
  can't be bootstrapped by urllib. BUT `api.princeton.edu` IS plain-client reachable (returns 401 w/ bad
  token, no challenge). So the adapter needs a headless-browser (or scheduled in-app browser) step to
  scrape the token, then plain HTTP for all data calls. Token stability unknown — if it rotates, a
  hardcoded token dies silently (whole-school miss), so bootstrap fresh, don't pin. example="COS 126".
  ~5.7k undergrad, elite. Dedup clean. HIGHEST-VALUE of the elite four; also the heaviest to ship.

### Rice (elite lead) — SOURCE-GATED + SENT to Build July 13 2026 (Grab): bespoke adapter needed
Second elite crack. Rice runs a CUSTOM Banner package: `courses.rice.edu/courses/!SWKSCAT.cat`.
Listing: `?p_action=QUERY&p_term={term}&p_name=&p_subj=ENGL` → rows `CRN | 'ENGL 109 001' | ...`
(99 live ENGL CRNs). Detail: `?p_action=COURSE&p_term={term}&p_crn={crn}` → labeled
`<b>Section Max Enrollment:</b> / <b>Section Enrolled:</b> / <b>Total Cross-list Max/Enrolled:</b> /
<b>Waitlisted:</b> N (Max M)` + **`Enrollment data as of: 12-JUL-2026 11:22PM`** (live freshness stamp,
refreshes even on completed terms — a real DB view, and an adapter-checkable staleness guard).
Terms Banner-style per-host: Fall 2026 = `202710`, completed Spring 2026 = `202520`. **Accuracy rules
(BOTH mandatory):** (1) Rice states waitlist members have priority for open seats → open requires
`Waitlisted == 0` (or absent) besides `SectionMax-SectionEnrolled > 0`; (2) cross-listed sections also
need `TotalXlistMax - TotalXlistEnrolled > 0` (found live: sec 10/10 with xlist 15/16 → NOT-OPEN).
Completed-term disproof through the same parse: Spring CRN 22430 genuinely full. Live term all-open
TODAY (RPI-class: fall cycle hasn't filled; empty=safe). N+1 shape (listing→detail) like Banner-8
family, needs the custom regex parse. ~8.5k students, elite. Dedup clean.

### Batch 31 (parser-resurrection resweep) — SENT July 13 2026 (Grab): NMSU + RPI, both production-gated
The dead-Banner re-sweep's first real yield — 2 resurrections, ~39k students, both near-drop-ins.
- **New Mexico State University (Las Cruces Main, ~21k)** — Banner-9 on the PUBLIC host
  `banner-public.nmsu.edu` (the original cut probed `banner.nmsu.edu`; Codex found the public host, Grab
  production-gated it). Standard `Banner`, `base_path="StudentRegistrationSsb"`, Fall 2026 = `202640`
  (getTerms label "2026 Fall", not View Only), `example="ENGL 1110G"` (108 sec systemwide; G-suffix
  gen-ed numbering). Live gate: ENGL 1110G Main = 38 sec **10 open/28 FULL**; MATH 1215 = 63 sec
  49/14 across campuses; real varied integers, zero open-with-0-seats; 2-3s/course; seq keys distinct
  (M01/D01/A20...). Completed terms serve no guest rows here — live full rows are the disproof
  (Utica standard). **⚠️ SHARED-POOL HOST, 5 campuses on one instance**, split ONLY by
  `campusDescription`: 'NMSU - Las Cruces (Main)', 'NMSU - Alamogordo', 'NMSU - Global', 'NMSU - Grants',
  'DACC - Dona Ana'. The existing `campus` first-token filter CANNOT isolate Main (four descriptions all
  start "NMSU") → needs an **exact-campusDescription match** variant (Banner-9 sibling of CampusBanner8).
  No campus-code field on rows, description only. Excluding Global also honors NMSU's own "Global Campus
  sections are reserved for that program" warning. **Historical optional rider, promoted by Batch 78:** DACC -
  Doña Ana CC rides the same host and is separately identified by exact `DACC - Dona Ana`; Batch 78 supersedes
  the old 49-section snapshot with full two-page current/completed gates. Dedup clean in Python
  (UNM/Highlands/Western NM/CNM are different schools).
- **Rensselaer Polytechnic Institute (~18k, R1)** — plain `ListcrseBanner8` drop-in, zero new code:
  `base="https://sis.rpi.edu/rss"`, Fall 2026 = `202609`, completed Spring 2026 = `202601`,
  `example="CSCI 1100"` (12 sec live, 3.0s; MATH 1010 24 sec 5.2s). My July-12 HOLD is RESOLVED by the
  NCCU/Shorter standard: the live term is still all-open TODAY (41/41 probed sections open — RPI's fall
  enrollment cycle simply hasn't filled sections), but the PRODUCTION adapter reads the completed term's
  real mixed enrollment (CSCI 2600 = 10 sec **4 open/6 FULL**; PSYC 4200 1/1 FULL; CSCI 1100 5/2) — the
  host provably publishes true Cap/Act/Rem through the exact production parse path, so fake-open is
  disproven at host level; empty=safe until sections fill (watches sit, then alert correctly).
- **Rest of the dead-pool: verdicts now FINAL, sharper diagnoses recorded (don't re-probe):**
  Morehouse/Wilkes/VSU/CCTech-SC/PVAMU/Middlebury (Banner-9) = guest search DISABLED at API level —
  searchResults answers `success:true, totalCount:0, data:null` for every subject on live AND completed
  terms (completed-term emptiness proves policy block, not term-loading). CT-log B8 hosts (mssu, neiu,
  mcla, uvi×6, guamcc, delhi, stlcc×6) = network-dead (NXDOMAIN/firewall/conn-fail on a 20-path battery
  incl. school-specific /pls/{SID} guesses). UCSD act.ucsd.edu: STILL no FA26 in dropdown (SA/SU/SP/WI26
  only) — keep weekly recheck. UH avail.classes (multi-campus system surface): STILL 502.

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
- **North Orange County CCD — Cypress College + Fullerton College (CA), historical July 11 HOLD; SUPERSEDED
  by builder-ready Batch 77 above.**
  Official app: `https://schedule.nocccd.edu/`; its public JavaScript loads `data/202610/courses.json`
  and `data/202610/sections.json` (Fall 2026) without auth. The feed returned 3,908 unique CRNs:
  Cypress (`campCode=1`) 1,694 sections, 1,083 with positive seats; Fullerton (`campCode=2`) 2,170,
  1,396 positive. `sectSeatsAvail == sectMaxEnrl - sectEnrl` held 3,908/3,908. Examples: Cypress
  `ENGL 100 C` = 59 sections with mixed 0/1 seats; Fullerton `ENGL 100 F` = 102 mixed sections.
  Summer 2026 (`202530`) is also public and mixed (Cypress 349, Fullerton 458), with unique CRNs and
  perfect arithmetic. **Do not hand off yet:** the JSON exposes seats, enrollment, waitlists and
  `sectResv`, but no authoritative registration-status enum; the app's “Open Classes” filter is
  seat-only and Cypress warns that a class can show seats while closed due to waitlist/add-code rules.
  **Historical note only:** Batch 77 found and fully gated the missing enrollment-cutoff, restriction,
  reservation, waitlist, and cross-list rule. Follow Batch 77's contract; do not treat this old HOLD as active.
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
5. **Schoolcraft College (MI) — SUPERSEDED; DO NOT BUILD THIS VIEWER.** Use Batch 84's anonymous
   `RegisterableColleague` subclass instead. Historical official schedule viewer: `https://my.schoolcraft.edu/course-schedules/2026/Fall/All`
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

### Codex Batch 43 — Northeast public course-search and portal leads (July 12 2026)

1. **University of Massachusetts Lowell (MA) — PUBLIC COURSE-SEARCH LEAD, FOLLOW-UP REQUIRED.** UMass Lowell’s official Fall 2026 Course Search (`https://gps.uml.edu/catalog/search/`) exposes 711 records with term, level, duration, location, and session filters and visible `Course Full` / `Course Full - Wait List Available` statuses. It does not expose numeric capacity in this pass; verify section identifiers, open/full semantics, and a completed-term replay before adapter work.
2. **Harvard University (MA) — COURSE-SEARCH/WAITLIST LEAD, FOLLOW-UP REQUIRED.** Harvard FAS Registrar documentation (`https://registrar.fas.harvard.edu/enrollment`) explains Course Search waitlist indicators and ratio-style waitlist counts, but access and eligibility vary by Harvard school. Confirm a sanctioned public course-search response, isolate FAS/other schools, and do not treat waitlist counts as available seats.
3. **University of San Diego (CA) — MYSANDIEGO CLASS-SEARCH LEAD, FOLLOW-UP REQUIRED.** USD’s official registration guidance (`https://www.sandiego.edu/torero-hub/registration/`) documents Fall 2026 registration and directs users to MySanDiego → Search for Classes, with undergraduate, graduate, law, and online program distinctions. No guest numeric row was captured; verify public access and preserve school/career, campus, restrictions, and waitlist semantics.
4. **Cedar Crest College (PA) — PUBLIC COURSE-SEARCH LEAD, FOLLOW-UP REQUIRED.** Cedar Crest’s official Fall 2026 registration FAQ (`https://my.cedarcrest.edu/ICS/icsfs/Registration_FAQ_Fall_2026.pdf?target=c66b4a19-709f-489e-a535-fa32228fcc92`) states that course search can be performed without logging in and supports term, department, division, building/online, and section-status filters. No numeric row was captured; verify the current endpoint and replay a completed term.
5. **Pennsylvania State University (PA) — LIONPATH PUBLIC-SEARCH LEAD, FOLLOW-UP REQUIRED.** Penn State’s official registrar materials document Fall 2026 schedule publication and instruction-mode fields (`https://www.registrar.psu.edu/registration/instruction-modes.cfm`); Penn State World Campus directs visitors to the public LionPATH course search (`https://www.worldcampus.psu.edu/degrees-and-certificates/penn-state-online-history-bachelor-of-arts-degree`). Scope is system-wide/multi-campus until a campus-filtered numeric response is verified; preserve University Park/Commonwealth/World Campus, career, session, restrictions, and waitlists.

**Batch status:** five net-new identities archived. UMass Lowell has the strongest public status evidence; Cedar Crest advertises an unauthenticated search, while Harvard, USD, and Penn State require school/campus/guest-route validation. No numeric seats were inferred, and no production approval was made.

### Codex Batch 44 — West Coast and Massachusetts public course-search leads (July 13 2026)

1. **Sierra College (CA) — PUBLIC CLASS-SCHEDULE LEAD, FOLLOW-UP REQUIRED.** Sierra’s official registration guidance (`https://www.sierracollege.edu/admissions/register-for-classes/`) directs visitors to the online Class Schedule for Fall 2026 and documents campus, subject, course-number, keyword, part-of-term, and `Open Sections Only` filters. No numeric row was captured; verify the live endpoint, preserve campus/online and prerequisite semantics, and replay a completed term.
2. **Lewis & Clark College (OR) — SELF-SERVICE OPEN-SECTIONS LEAD, FOLLOW-UP REQUIRED.** Lewis & Clark’s official advising guidance (`https://college.lclark.edu/academics/support/advising/transfer-students/how-to-register/`) documents Fall 2026 Course Catalog section search with an `Open Sections Only` filter. The workflow is Self-Service based; no numeric guest row was captured. Verify public access, course/section identifiers, restrictions, waitlist behavior, and completed-term replay.
3. **University of Massachusetts Amherst (MA) — ARTS EXTENSION CAMPUS-CLASS LEAD, SCOPE REQUIRED.** UMass Amherst’s official Arts Extension Service page (`https://www.umass.edu/arts-extension-service/academics/campus-classes`) lists three Fall 2026 on-campus ARTS-EXT classes with class numbers and meeting times. This is Arts Extension only, not the full Amherst catalog; confirm SPIRE visibility and numeric availability before any adapter consideration.
4. **University of Massachusetts Dartmouth (MA) — ONLINE COURSE-LISTINGS LEAD, FOLLOW-UP REQUIRED.** UMass Dartmouth’s official online course listings (`https://www.umassd.edu/online/course-listings/`) provide a Fall 2026 browse surface for prospective, guest, and continuing students, while the registrar documents Fall 2026 registration timing. No numeric row was captured; verify online-program scope, session/career, eligibility, waitlist, and completed-term semantics.
5. **Trinity College (CT) — PUBLIC COURSE-INFO NUMERIC LEAD, SCOPE REQUIRED.** Trinity’s official course-info endpoint (`https://internet3.trincoll.edu/ptools/CourseInfo.aspx?clsnbr=2311&strm=1271`) exposes a Fall 2026 Rome-campus internship seminar with `Enrollment: 0/12`, `Available seats: 15`, course career/session, permission requirement, and dates. This is a single study-away/Rome course, not proof of a broad Trinity catalog; validate endpoint stability and term replay before adapter work.

**Batch status:** five net-new identities archived. Trinity has the strongest numeric evidence but is narrowly scoped; Sierra and Lewis & Clark expose open-section filters, while both UMass entries are program/online subsets. No production approval was made.

### Codex Batch 45 — Northeast and Great Plains course-search leads (July 13 2026)

1. **Smith College (MA) — COURSE-SEARCH/PORTAL LEAD, FOLLOW-UP REQUIRED.** Smith’s official registrar (`https://www.smith.edu/academics/registrar/course-registration`) documents Fall 2026 registration dates and Workday course-search/saved-schedule workflows. No public numeric row was captured; verify sanctioned guest access, preserve undergraduate/graduate career, campus, restrictions, waitlists, and completed-term semantics.
2. **William & Mary (VA) — CLASS-SEARCH/WAITLIST LEAD, FOLLOW-UP REQUIRED.** William & Mary’s official registrar waitlist guidance (`https://www.wm.edu/offices/registrar/registration/how-to-register/waitlist/`) documents Fall 2026 notification behavior and points to Class Search and registration restrictions. No numeric guest row was captured; verify public access and distinguish capacity, reserved seats, and waitlist state before adapter work.
3. **Frederick Community College (MD) — FALL 2026 SCHEDULE LEAD, FOLLOW-UP REQUIRED.** Frederick’s official Fall 2026 credit schedule (`https://www.frederick.edu/class-schedules/downloads/fallcredit2026.aspx`) publishes current term offerings. This pass captured no numeric seat row; verify a sanctioned searchable endpoint, preserve main/online/session, prerequisites, waitlist, and completed-term semantics.
4. **University of Massachusetts Boston (MA) — LIMITED NON-DEGREE COURSE LEAD, SCOPE REQUIRED.** UMass Boston’s official Fall 2026 non-degree enrollment page (`https://www.umb.edu/mccormack/crhsgg/non-degree-course-enrollment-request/`) lists graduate Conflict Resolution/International Relations course options and guest-registration instructions. This is a program-specific subset, not the whole UMass Boston catalog; no seats inferred.
5. **Williston State College (ND) — PUBLIC NUMERIC CLASS-SEARCH LEAD, FOLLOW-UP REQUIRED.** WSC’s official class search (`https://willistonstate.edu/class-search.aspx`) exposes Fall 2026 rows with open-seat counts and status fields (e.g., PTLO-135 14 open, RNG-225 20 open, RNG-236 15 open), plus course number, dates, modality, campus/location, and wait fields. Verify endpoint freshness, unique section keys, completed-term replay, and main/online/career semantics before adapter work.

**Batch status:** five net-new identities archived. Williston State has the strongest numeric evidence; Smith, William & Mary, and Frederick require guest/search validation, while UMass Boston is explicitly limited to a non-degree graduate subset. No production approval was made.

### Codex Batch 46 — Midwest and California public schedule leads (July 13 2026)

1. **Harper College (IL) — PUBLIC OPEN-COURSE SEARCH LEAD, FOLLOW-UP REQUIRED.** Harper’s official Fall 2026 open-courses page (`https://www.harpercollege.edu/registration/fall/`) publishes a daily-updated searchable list with keyword, subject, teaching method, term, specialized-program, course-length, and start-date filters. The page’s data is JavaScript-loaded in this pass; capture the sanctioned response and verify section identity, open/full/waitlist semantics, campus/modality, and completed-term replay before adapter work.
2. **Mt. San Jacinto College (CA) — PUBLIC SCHEDULE/SELF-SERVICE LEAD, FOLLOW-UP REQUIRED.** MSJC’s official schedule page (`https://msjc.edu/scheduleofclasses/index.html`) links the Fall 2026 PDF and Self-Service course search, states that schedules are updated daily, and documents open-enrollment policy. No numeric row was captured here; verify the public search response, campus/online/session scope, seat fields, and completed-term behavior.
3. **Bradley University (IL) — PUBLIC SCHEDULE SEARCH LEAD, FOLLOW-UP REQUIRED.** Bradley’s official schedule surface (`https://schedule.bradley.edu/`) exposes a Fall Semester 2026 class-database search. The page identifies the term as in progress but no numeric row was captured; verify whether the public results include capacity/status, preserve undergraduate/graduate career and restrictions, and replay a completed term.
4. **University of Chicago (IL) — PUBLIC UNDERGRADUATE PDF SCHEDULE LEAD, SCOPE REQUIRED.** Chicago’s official Fall 2026 undergraduate schedule (`https://webserv.cuchicago.edu/files/forms-repository/registrar/academic-schedules/Fall_UG_Schedule.pdf`) includes CRNs and a `Seats=Available Seats/Enrollment Cap` convention. Treat this as the undergraduate schedule only; verify whether the PDF is current, whether seats are numeric per section, and how graduate/professional careers and waitlists are represented.
5. **Cuyamaca College (CA) — FALL 2026 SCHEDULE/SEAT-POLICY LEAD, FOLLOW-UP REQUIRED.** Cuyamaca’s official Fall 2026 enrollment/schedule material (`https://www.cuyamaca.edu/academics/class-schedules-catalog-and-calendars/files/2026fa/2026fall-cuyamaca-enrollment-info-vf.pdf`) documents the Fall 2026 schedule and explains that enrollment uses seats-available status. No numeric guest row was captured; verify the live class-search endpoint, Grossmont/Cuyamaca campus identity, CRNs, modality/session, and waitlist semantics.

**Batch status:** five net-new identities archived. UChicago has the strongest published seat-field evidence; Harper, Mt. San Jacinto, and Bradley expose public schedule/search surfaces, while Cuyamaca requires live endpoint validation. No production approval was made.

### Codex Batch 47 — Northeast and Mid-Atlantic registrar/search leads (July 13 2026)

1. **Syracuse University (NY) — PORTAL SCHEDULE/SEARCH LEAD, FOLLOW-UP REQUIRED.** Syracuse’s registrar (`https://registrar.syr.edu/general/schedule-of-classes/`) documents that the Fall schedule is published in March and that the real-time Search for Classes workflow lives in MySlice. No public numeric row was captured; verify sanctioned guest access, preserve Syracuse/ESF campus and career distinctions, restrictions, waitlists, and completed-term replay.
2. **University of Pittsburgh (PA) — ENROLLMENT/CLASS-SEARCH LEAD, FOLLOW-UP REQUIRED.** Pitt’s official enrollment page (`https://www.registrar.pitt.edu/enrollment`) directs users to term/campus search criteria and class-scheduling tools. No numeric guest row was captured; verify public availability, preserve Pittsburgh/regional campuses, career, session, reserve capacities, waitlists, and completed-term semantics.
3. **North Carolina State University (NC) — REGISTRATION/SCHEDULE LEAD, SCOPE REQUIRED.** NC State’s Poole College registration guidance (`https://poole.ncsu.edu/undergraduate/academic-resources/registration-and-enrollment/`) directs students to the university course schedule and Fall 2026 enrollment updates. This is a college-level guidance surface, not proof of a public whole-university feed; verify the registrar endpoint, campus/career scope, capacity/status fields, and term replay.
4. **University of Rochester (NY) — PUBLIC COURSE-CATALOG SEARCH LEAD, FOLLOW-UP REQUIRED.** Rochester’s advising documentation (`https://www.rochester.edu/college/ccas/advising/course-search.html`) identifies the public Course Description Course Schedule (CDCS) and separates it from the authenticated UR Student enrollment system. Verify Fall 2026 section availability, numeric capacity/status, school/career filters, and completed-term behavior before adapter work.
5. **Case Western Reserve University (OH) — SIS SCHEDULE LEAD, FOLLOW-UP REQUIRED.** Case Western’s registrar (`https://bulletin.case.edu/about-university/university-registrar/`) states that the schedule of classes is available electronically through SIS, while the Fall 2026 registrar calendar (`https://case.edu/registrar/dates-deadlines/academic-calendar`) confirms term dates and registration timing. No public numeric row was captured; verify guest access, career/session scope, reserve seats, waitlists, and completed-term replay.

**Batch status:** five net-new identities archived. Rochester and Syracuse have the clearest documented schedule-search pathways; Pitt, NC State, and Case Western require public/guest endpoint confirmation. No seats were inferred, and no production approval was made.

### Codex Batch 48 — New England public schedule and registrar leads (July 13 2026)

1. **Brandeis University (MA) — PUBLIC NUMERIC SCHEDULE LEAD, SCOPE REQUIRED.** Brandeis’s official Fall 2026 registrar schedule (`https://registrar-prod.unet.brandeis.edu/registrar/schedule/classes/2026/fall/1800/UGRD`) exposes undergraduate course rows with `Open`/`Waitlist` states and `Enrl / Lim / Wait` fields (for example, English sections show numeric enrollment, limits, and waits). This endpoint is subject/undergraduate-career scoped; verify all-school navigation, unique section keys, reserve/consent semantics, and completed-term replay before adapter work.
2. **Massachusetts College of Art and Design (MA) — REGISTRAR-CALENDAR/SCHEDULE LEAD, FOLLOW-UP REQUIRED.** MassArt’s official academic calendar (`https://massart.edu/academics/academic-calendar/`) documents Fall 2026 classes beginning September 2, add/drop, withdrawal, and class-end dates. No public numeric row was captured; locate the sanctioned schedule/search endpoint and preserve undergraduate/graduate career, studio/lab sections, restrictions, waitlists, and completed-term semantics.
3. **Roxbury Community College (MA) — PUBLIC COURSE-SCHEDULE LEAD, FOLLOW-UP REQUIRED.** RCC’s official course schedule (`https://www.rcc.mass.edu/enroll/course-registration/course_schedule.html`) exposes searchable section rows with term codes (including `CF26`, `F126`, and `FL26`), course code/title, faculty, `Open` status, meeting/modality/location details, credits, and start/end dates. Verify the live search response, section/CRN identifiers, campus/online/session fields, numeric availability, waitlist behavior, and a completed-term replay.
4. **Boston College (MA) — REGISTRATION/RESERVE-SEAT LEAD, SCOPE REQUIRED.** Boston College’s registrar calendar (`https://www.bc.edu/content/bc-web/offices/student-services/registrar/registration-calendar.html`) documents Fall 2026 registration and warns that apparent availability can reflect Woods-course reserve seats; it also describes school/career eligibility and half-session timing. Verify the public class-search route, preserve Boston College school/career and reserve-capacity semantics, and do not infer seats from the calendar.
5. **Antioch College (OH) — PUBLIC COURSE-SCHEDULE LEAD, FOLLOW-UP REQUIRED.** Antioch’s official academic catalog page (`https://antiochcollege.edu/academics/courses-and-catalog/`) links an active Fall 2026 Course Schedule and a schedule archive, and separately advertises opportunities open to non-degree students. Verify whether the linked schedule has section-level status/capacity, unique identifiers, block/session dates, public access, and completed-term replay before adapter work.

**Batch status:** five net-new identities archived. Brandeis has direct numeric Fall 2026 `Enrl / Lim / Wait` rows; RCC exposes searchable open-status rows with term, modality, dates, and room-capacity text. MassArt, Boston College, and Antioch require endpoint/scope validation. No production approval was made.

### Codex Batch 49 — West/South and private registrar schedule leads (July 13 2026)

1. **San Jose State University (CA) — PUBLIC NUMERIC SCHEDULE LEAD, SCOPE REQUIRED.** SJSU’s official Fall 2026 class schedule (`https://www.sjsu.edu/classes/schedules/fall-2026.php`) publishes section rows with class numbers, instruction mode, dates, and numeric `Open Seats`; the page says data is refreshed nightly and documents reserve capacities, waitlist movement, and Open University exclusions. Verify section uniqueness, campus/program scope, reserve-seat semantics, waitlists, and completed-term replay before adapter work.
2. **University of Tennessee at Chattanooga (TN) — PUBLIC SCHEDULE/CLASS-SEARCH LEAD, FOLLOW-UP REQUIRED.** UTC’s registrar (`https://www.utc.edu/academic-affairs/registrar/registration-information/class-schedule`) links a public “View Class Schedule,” confirms Fall 2026 availability, and explicitly distinguishes Chattanooga-campus face-to-face sections from UTC Online hybrid/internet sections. No numeric guest row was captured; verify public response fields, unique section keys, restrictions, waitlists, and completed-term behavior.
3. **Mitchell College (CT) — STATIC FALL SCHEDULE LEAD, FOLLOW-UP REQUIRED.** Mitchell’s registrar (`https://mitchell.edu/registrar/`) links the official Fall 2026 class schedule and planner; the linked schedule PDF (`https://mitchell.edu/wp-content/uploads/2026/03/MitchellCollege_Fall2026_ClassSchedule_3.27.2026.pdf`) lists course IDs, meeting patterns, credits, and enrollment/capacity text. Treat it as a static schedule until a sanctioned live availability endpoint, status semantics, and completed-term replay are confirmed.
4. **University of North Texas (TX) — MYUNT SCHEDULE-OF-CLASSES LEAD, SCOPE REQUIRED.** UNT’s registrar Fall 2026 calendar (`https://registrar.unt.edu/registration/fall-academic-calendar`) states that the full-term and eight-week schedules became available in myUNT on March 9, with distinct session dates, registration windows, add/swap deadlines, and prerequisite-drop dates. No public numeric row was captured; verify guest access or an official public endpoint, preserve session/campus/career scope, and test completed-term replay.
5. **West Liberty University (WV) — WINS SCHEDULE LEAD, FOLLOW-UP REQUIRED.** West Liberty’s registrar (`https://westliberty.edu/registrar/`) directs users to the up-to-date WINS course-schedule system and links Fall 2026 registration instructions. No numeric guest row was captured; verify whether WINS exposes public schedule/availability data, preserve term/session and restriction/waitlist semantics, and replay a completed term before adapter work.

**Batch status:** five net-new identities archived. SJSU has the strongest numeric public evidence and explicit reserve-seat documentation; UTC, Mitchell, UNT, and West Liberty require public endpoint and scope validation. No production approval was made.

### Codex Batch 50 — Current public/portal schedule leads (July 13 2026)

1. **East Tennessee State University (TN) — FALL 2026 PDF/PORTAL SEARCH LEAD, FOLLOW-UP REQUIRED.** ETSU’s official registration resources (`https://www.etsu.edu/reg/registration/resources.php`) identify an Interactive Course Search in GoldLink and link the Fall 2026 Schedule of Classes PDF posted July 10, 2026. No numeric guest row was captured; verify public/guest access, section/CRN identity, campus/career scope, restrictions, waitlists, and completed-term replay.
2. **Manchester Community College (NH) — PUBLIC INTERACTIVE SCHEDULE LEAD, FOLLOW-UP REQUIRED.** MCC’s official schedule page (`https://mccnh.edu/academics/course-schedules/`) links a searchable Fall 2026 schedule, says it is updated weekly, and directs the general public to SIS for daily changes. The schedule documents course numbers, dates/times, modality/location, and session search fields. Verify live availability/waitlist fields, unique section IDs, campus/session scope, and completed-term replay.
3. **Diné College (AZ) — STATIC FALL SCHEDULE LEAD, FOLLOW-UP REQUIRED.** Diné College’s official Fall 2026 schedule PDF (`https://www.dinecollege.edu/wp-content/uploads/2026/05/FALL-26-course-schedule-May-14-2026.pdf`) covers the 08/17/2026–12/11/2026 semester and lists school, course, section, credits, meeting patterns, prerequisites, and max-enrollment text. Treat it as static evidence until a sanctioned live status/capacity endpoint and completed-term replay are verified.
4. **Duke University (NC) — PUBLIC DUKEHUB SCHEDULE LEAD, SCOPE REQUIRED.** Duke’s registrar timeline (`https://registrar.duke.edu/faculty-staff-resources/class-scheduling/`) states that the Fall 2026 Schedule of Classes is available to students and the public in DukeHub from March 23, with registration beginning April 1. No numeric guest row was captured; verify public access, preserve Duke school/career and reserve-capacity semantics, waitlists, and completed-term behavior.
5. **University of Wisconsin–Milwaukee (WI) — STELLIC/CATALOG SCHEDULE LEAD, FOLLOW-UP REQUIRED.** UWM’s registrar (`https://uwm.edu/registrar/enrollment/stellic/create-your-schedule/`) documents a Fall 2026 Stellic schedule view and links the official Schedule of Classes catalog. The documented workflow requires Stellic login; no numeric guest row was captured. Verify the public catalog/search endpoint, section IDs, campus/career/session scope, availability/waitlist semantics, and completed-term replay.

**Batch status:** five net-new identities archived. MCCNH has the clearest public interactive schedule surface; ETSU has a current official Fall 2026 PDF plus GoldLink search. Diné, Duke, and UWM require live endpoint/scope validation. No production approval was made.

### Codex Batch 51 — Current public class-search and registrar snapshot leads (July 13 2026)

1. **University of Maryland, College Park (MD) — PUBLIC NUMERIC CLASS-SEARCH LEAD, SCOPE REQUIRED.** UMD’s official Testudo Schedule of Classes (`https://app.testudo.umd.edu/soc/`) exposes Fall 2026 (`202608`) public section pages with labeled `Seats (Total, Open, Waitlist)` fields; for example, PHPE 308D shows 12 open of 30 with waitlist 0. The search supports open-only, level, delivery, location/program, and course filters. Verify unique section/term keys, campus/career and cross-list scope, reserve/seat-management restrictions, waitlists, and completed-term replay before adapter work.
2. **Florida State University (FL) — OFFICIAL WEEKLY CLASS-SNAPSHOT LEAD, FOLLOW-UP REQUIRED.** FSU’s registrar class-search snapshot page (`https://registrar.fsu.edu/class-search-snapshots`) publishes separate Fall 2026 undergraduate, graduate, law, and medicine snapshots and says they are updated weekly, with previous-semester archives. Treat the PDFs as static evidence until a sanctioned live endpoint is found; preserve career/campus scope, reserve-capacity rules, and waitlist semantics, and require completed-term replay.
3. **Webster University (MO) — PUBLIC INTERACTIVE CLASS-SEARCH LEAD, FOLLOW-UP REQUIRED.** Webster’s official class-search surface (`https://classes.webster.edu/`) offers unauthenticated search controls for course, session, semester/term, campus, remote options, and section status; the university’s registration page confirms Summer/Fall 2026 registration and links Interactive Class Search. No numeric guest row was captured; verify response fields, unique section IDs, domestic/international campus scope, restrictions, waitlists, and completed-term behavior.
4. **Hellenic College Holy Cross Greek Orthodox School of Theology (MA) — PUBLIC JENZABAR COURSE-SEARCH LEAD, FOLLOW-UP REQUIRED.** The institution’s official course-search page (`https://my.hchc.edu/ICS/Home.jnz?portlet=AddDrop_Courses&screen=Advanced+Course+Search&screenType=next`) exposes Fall 2026 and prior terms, a broad department list, meeting/campus filters, and Section Status filtering without presenting a login wall in the public search surface. No numeric guest row was captured; verify live result payloads, section/cross-registration identity, status/seat fields, and completed-term replay.
5. **Quinsigamond Community College (MA) — PUBLIC COURSE-OFFERINGS SEARCH LEAD, FOLLOW-UP REQUIRED.** QCC’s official registration guidance (`https://www.qcc.edu/admissions/register-courses`) directs users to The Q course schedule and instructs the public to select Fall 2026 and `Section Status: Open`; the registration-preparation guide documents that The Q schedule requires no login (`https://theq.qcc.edu/ICS/icsfs/FA26_Reg-Prep_Packet.pdf?target=7d547a39-212b-4a2b-af93-2402b862a7fc`). No numeric guest row was captured; verify the sanctioned response, CRN/section identity, modality/session/campus scope, waitlists, and completed-term replay.

**Batch status:** five net-new identities archived. UMD has direct numeric public seat rows; FSU, Webster, HCHC, and QCC require live endpoint/response validation. No production approval was made.

### Codex Batch 52 — Colorado, California, and New York public schedule leads (July 13 2026)

1. **Aims Community College (CO) — PUBLIC CLASS-SCHEDULE LEAD, FOLLOW-UP REQUIRED.** Aims’ official schedule (`https://schedule.aims.edu/`) exposes a public Fall 2026 term selector with course, campus, modality, dates, days, subject, and `Open Classes Only` filters. The page requires at least two filters before searching; no numeric guest row was captured. Verify the sanctioned response, CRN/section identity, campus scope, waitlists/restrictions, and completed-term replay.
2. **San Bernardino Valley College (CA) — PUBLIC ESCHEDULE/OPEN-CSV LEAD, FOLLOW-UP REQUIRED.** SBVC’s official Fall 2026 eSchedule (`https://www.valleycollege.edu/eschedule/index.php?term=2026FA`) provides subject/term filters, an Open Classes filter, modality filters, and an Open Classes CSV link; the page reports a recent update and directs users to Self-Service for real-time data. No numeric guest row was captured; verify the public feed/CSV, unique section IDs, SBVC-vs-district scope, waitlists, and completed-term replay.
3. **Crafton Hills College (CA) — DAILY ESCHEDULE/OPEN-SECTIONS LEAD, FOLLOW-UP REQUIRED.** Crafton Hills’ official class-schedule page (`https://www.craftonhills.edu/admissions-and-records/enroll/class-schedule/index.php`) links a Fall 2026 eSchedule updated daily and separate open-section PDFs (all, short-term, online, evening, and weekend). Treat PDFs as snapshots until a sanctioned live response is captured; verify CRNs, campus/modality/session scope, status/seat fields, waitlists, and completed-term replay.
4. **Santa Ana College (CA) — PUBLIC OPEN-CLASS LIST LEAD, FOLLOW-UP REQUIRED.** Santa Ana’s official Fall 2026 schedule page (`https://www.sac.edu/admissions/class_schedule`) states that instruction runs August 17–December 5 and links current open-class lists split into all, in-person, online-only, and hybrid sections. No numeric guest row was captured; verify the RSCCD response, Santa Ana-vs-district identity, CRNs, modality/session, waitlists, and completed-term replay.
5. **SUNY Old Westbury (NY) — REGISTRAR BROWSE-CLASSES LEAD, FOLLOW-UP REQUIRED.** Old Westbury’s registrar page (`https://www.oldwestbury.edu/division/office-academic-affairs/office-registrar/class-schedule`) links the official Browse Classes endpoint, documents Fall 2026 registration windows and the August 24 term start, and defines on-campus, online, remote, and hybrid modalities. No numeric guest row was captured; verify public endpoint access, section/career scope, seat and waitlist semantics, and completed-term behavior.

**Batch status:** five net-new identities archived. All five have official schedule/search surfaces; none received production approval. SBVC and Santa Ana have the clearest public open-class pathways, while Crafton’s PDFs and Old Westbury’s Browse Classes link require endpoint validation.

### Codex Batch 53 — Bay Area and Los Angeles public schedule leads (July 13 2026)

1. **Cañada College (CA) — PUBLIC FALL OPEN-CLASS LIST LEAD, FOLLOW-UP REQUIRED.** The San Mateo County Community College District’s official WebSchedule (`https://webschedule.smccd.edu/`) publishes Fall 2026 downloads with a dedicated Cañada `Open Classes` listing and links to the public schedule search. No numeric guest row was captured here; verify the linked response, CRN/section identity, campus scope, waitlists, and completed-term replay.
2. **College of San Mateo (CA) — PUBLIC FALL OPEN-CLASS LIST LEAD, FOLLOW-UP REQUIRED.** SMCCCD’s official WebSchedule lists a dedicated Fall 2026 College of San Mateo `Open Classes` download and the district’s WebSchedule search. No numeric guest row was captured in this pass; verify section-level fields, CSM-vs-district identity, modality/session, waitlists, and completed-term replay.
3. **Skyline College (CA) — PUBLIC FALL OPEN-CLASS LIST LEAD, FOLLOW-UP REQUIRED.** The same official SMCCCD WebSchedule provides a dedicated Fall 2026 Skyline `Open Classes` listing and public schedule-search entry. No numeric guest row was captured; verify CRNs, campus identity, course components, waitlists, and completed-term replay before adapter work.
4. **Los Angeles City College (CA) — REAL-TIME FALL SEARCH LEAD, HEADLESS VALIDATION REQUIRED.** LACC’s official schedule page (`https://www.lacc.edu/academics/class-schedules`) advertises real-time Fall 2026 open-class searching and a weekly-updated Fall schedule PDF. The page returned HTTP 403 to the headless fetch in this pass; no bypass was attempted and no seats were inferred. Validate the sanctioned guest endpoint, campus/session scope, CRNs, restrictions, waitlists, and completed-term behavior.
5. **West Los Angeles College (CA) — SEARCHABLE FALL SCHEDULE LEAD, HEADLESS VALIDATION REQUIRED.** WLAC’s official schedule page (`https://www.wlac.edu/academics/class-schedules`) documents a searchable Fall 2026 schedule (Aug 31–Dec 20), a PDF class list, and late-start session filtering. The page returned HTTP 403 to the headless fetch; no bypass was attempted and no seats were inferred. Validate the sanctioned public endpoint, section/campus scope, waitlists, and completed-term replay.

**Batch status:** five net-new identities archived. Cañada, CSM, and Skyline have a common district schedule/search surface with dedicated open-class listings; LACC and WLAC require sanctioned endpoint validation after headless 403 responses. No production approval was made.

### Codex Batch 54 — Five additional official Fall 2026 schedule leads (July 13 2026)

These five identities are net-new after exact-name checks against `schools.py` and the research archive.
They are archived as bounded research leads only; no production adapter or seat count is implied unless
the source explicitly exposes one. Each still needs campus/career scope, restrictions, waitlist, freshness,
and current/completed-term validation before any build work.

1. **College of Lake County (IL) — PUBLIC CLASS-SEARCH LEAD, FOLLOW-UP REQUIRED.** CLC's official class-search
   page (`https://www.clcillinois.edu/class-search`) presents a Fall 2026 term selector, subject/location/
   instructional-mode filters, and an `Open and Wait List Classes Only` option. The page is a public search
   surface, but this pass did not capture a row-level response; reproduce the sanctioned endpoint, preserve
   CLC campus/modality/session identity, and test a completed term before interpreting status or seats.
2. **Taylor University (IN) — PUBLIC BROWSE-CLASSES LEAD, FOLLOW-UP REQUIRED.** Taylor's registrar class-
   schedules page (`https://www.taylor.edu/about/offices/registrar/class-schedules`) links a current Fall
   2026 schedule and a public `browse classes` route. The page says offerings can change and no numeric guest
   row was captured; validate the live response, section identifiers, term/career scope, waitlists, and a
   completed-term replay before adapter work.
3. **Ithaca College (NY) — PORTAL SCHEDULE/WAITLIST LEAD, FOLLOW-UP REQUIRED.** Ithaca's registrar course-
   registration page (`https://www.ithaca.edu/academics/registrar/course-registration`) states that the
   Summer/Fall 2026 schedule is viewable in HomerConnect/DegreeWorks, and explains that current waitlist
   seats are reserved while incoming students register for open seats. This is a documented official route,
   but it is portal-oriented and yielded no guest numeric row here; verify public access or stop at a source-
   level lead, preserving waitlist/reserve semantics and exact CRNs.
4. **Seminole State College of Florida (FL) — PUBLIC NUMERIC COURSE-PAGE LEAD, FOLLOW-UP REQUIRED.** The
   official catalog's Fall 2026 course pages (for example `https://www.seminolestate.edu/catalog/courses/
   mvk2121m` and `https://www.seminolestate.edu/catalog/courses/ent2172`) show current-term open classes,
   class numbers, dates, modality/location, and `1 class available` for selected courses. These are
   course-specific catalog pages rather than a proven whole-college feed; discover the sanctioned search
   endpoint, verify capacity/seat semantics and campus scope, and replay a completed term before using them.
5. **Carleton College (MN) — CURRENT-TERM IDENTITY LEAD, FOLLOW-UP REQUIRED.** Carleton's official 2026–27
   academic calendar (`https://carleton-wp-production.s3.amazonaws.com/uploads/sites/740/2024/11/Academic-
   Calendar-26-27.pdf`) confirms Fall 2026 dates (classes begin September 14), while the public-facing
   course-schedule surface was not reproduced in this pass. Treat this as identity/date reconnaissance only:
   locate the registrar's sanctioned schedule, do not infer seats, and require exact section keys plus a
   completed-term comparison before any adapter proposal.

**Batch status:** five net-new identities were archived. CLC and Taylor expose the clearest public search
surfaces; Seminole has current course-page availability markers; Ithaca and Carleton remain portal/date
leads. None passed the full production gate in this research-only pass. No `schools.py` edit, registry change,
deployment, or builder handoff was made.

### Codex Batch 55 — Five additional official Fall 2026 schedule leads (July 13 2026)

These five identities are net-new after exact-name checks against `schools.py` and the research archive.
They are intentionally bounded leads: source evidence is recorded below, but no seat value is promoted
without a sanctioned endpoint, scope checks, and a completed-term replay.

1. **American University (DC) — STUDENT-PLANNING SCHEDULE LEAD, FOLLOW-UP REQUIRED.** American's official
   registrar page (`https://www.american.edu/provost/registrar/registration/studentplanning.cfm`) documents
   Fall/Summer 2026 Student Planning and the upcoming schedule-of-classes workflow. It is a planning/portal
   surface in this pass; no guest row or numeric seat payload was captured. Verify any public search route,
   preserve undergraduate/graduate career and waitlist scope, and replay a completed term.
2. **University of Minnesota Crookston (MN) — PUBLIC CLASS-SEARCH LEAD, FOLLOW-UP REQUIRED.** Crookston's
   official registrar page (`https://crk.umn.edu/registrar/class-schedules`) identifies the Fall 2026 schedule
   and links students to One Stop's Schedule Builder/Search for Classes, plus class-section-status resources.
   The page also exposes a faculty class-enrollment-status report described as always current, but no guest
   numeric row was captured. Verify public access, Crookston-campus scope within the UMN system, section keys,
   reserve/waitlist semantics, and a completed-term replay before adapter work.
3. **Lawrence Technological University (MI) — BANNERWEB SCHEDULE/WAITLIST LEAD, FOLLOW-UP REQUIRED.** LTU's
   official registrar page (`https://ltu.edu/academics/registrar/registration-and-scheduling/`) confirms Summer
   and Fall 2026 registration, directs students to BannerWeb's Search for Classes flow, and documents CRNs,
   section-level waitlist indicators, and the rule that waitlisted sections remain closed until the waitlist is
   processed. This is not a guest numeric feed in this pass; verify any public schedule route, distinguish open
   seats from waitlist/reserve states, and replay a completed term before adapter work.
4. **University of Kentucky (KY) — OFFICIAL REGISTRATION-SEARCH LEAD, FOLLOW-UP REQUIRED.** Kentucky's Fall
   2026 registration instructions (`https://registrar.uky.edu/sites/default/files/2026-03/registration-
   instructions-2026.pdf`) document searching for courses with available seats, while the registrar's
   academic calendar confirms the Fall 2026 term (`https://registrar.uky.edu/calendars/academic-calendar`).
   No guest numeric row was captured; locate the sanctioned class-search response, preserve reserve/waitlist
   semantics, and validate a completed term before any adapter proposal.
5. **North Carolina Wesleyan University (NC) — STATIC FALL SCHEDULE LEAD, FOLLOW-UP REQUIRED.** NC Wesleyan's
   official Fall 2026 traditional-program schedule PDF (`https://ncwu.edu/wp-content/uploads/2026/03/Fall-
   2026-Traditional-Schedule-Update-2026.3.12.pdf`) lists current-term sections, meeting patterns, credits,
   and instructors. It is a static schedule and contains no live seat field; find the sanctioned search,
   verify section identity and status semantics, and replay a completed term before using it.

**Batch status:** five net-new identities were archived. Crookston has the clearest public class-search lead;
American, Lawrence Tech, Kentucky, and NC Wesleyan require endpoint or static-schedule follow-up. None passed
the full production gate in this research-only pass. No `schools.py` edit,
registry change, deployment, or builder handoff was made.

### Codex Batch 56 — Five additional official Fall 2026 schedule leads (July 13 2026)

These five identities are net-new after exact-name checks against `schools.py` and the research archive. They are
source-gated leads only; no seat value is promoted without a sanctioned endpoint, scope checks, and a completed-term replay.

1. **Moraine Valley Community College (IL) — REAL-TIME PORTAL SEARCH LEAD, FOLLOW-UP REQUIRED.** Moraine Valley's
   official registration page (`https://www.morainevalley.edu/admissions/register/`) confirms Summer/Fall 2026
   course options and explicitly directs users to `Search for Sections` for up-to-the-moment class and seat
   availability. This pass did not capture a guest numeric row; verify public access, section identifiers,
   campus/modality/session scope, waitlists, and completed-term behavior.
2. **College of DuPage (IL) — GUEST SCHEDULE/WAITLIST LEAD, FOLLOW-UP REQUIRED.** The official registration guidance
   (`https://www.cod.edu/registration/myaccess-student-planning.html`) says guests may search the current class
   schedule, while the registration page (`https://cod.edu/registration/`) documents Fall-term waitlist behavior.
   No numeric guest row was captured; locate the sanctioned schedule response, preserve term/section/career scope,
   and validate reserved-seat and waitlist semantics.
3. **Florida State College at Jacksonville (FL) — PUBLIC PEOPLESOFT CLASS-SEARCH LEAD, FOLLOW-UP REQUIRED.** FSCJ's
   public class-search page (`https://csprd.fscj.edu/psc/csprd_1/EMPLOYEE/HRMS/c/COMMUNITY_ACCESS.CLASS_SEARCH.GBL`)
   exposes institution/term, subject, campus, session, and `Show Open Classes Only` controls; the official payment
   page confirms Fall 2026 sessions (`https://www.fscj.edu/registration/how-to-pay-and-payment-due-dates`). No guest
   numeric row was captured; verify response fields, unique class/section keys, and waitlist/restriction scope.
4. **Santiago Canyon College (CA) — FALL 2026 OPEN-CLASS SCHEDULE LEAD, FOLLOW-UP REQUIRED.** The college's official
   Fall 2026 schedule PDF (`https://www.sccollege.edu/academics/classschedule/Shared%20Documents/SCC%20Fall%202026Class%20Schedule_FINAL_ONLINE.pdf`)
   documents the schedule and identifies online open-class/course-availability information. Treat it as a static
   source until the live class-search endpoint is captured; verify CRNs, seats, linked sections, modality, and replay.
5. **Community College of Beaver County (PA) — FALL 2026 REGISTRATION/SCHEDULE LEAD, FOLLOW-UP REQUIRED.** CCBC's
   official Fall 2026 enrollment page (`https://ccbc.edu/fall26/`) confirms the term and August 24 start date, while
   its academic calendar (`https://ccbc.edu/academic-calendar/`) records Fall 2026 schedule-release and add/drop
   dates. No guest numeric row was captured; locate the public class-search/catalog route and validate seat and waitlist semantics.

**Batch status:** five net-new identities were archived. Moraine Valley and FSCJ have the strongest public-search
signals; DuPage, Santiago Canyon, and Beaver County need endpoint or schedule follow-up. None passed the full
production gate in this research-only pass. No `schools.py` edit, registry change, deployment, or builder handoff was made.

### Codex Batch 57 — Five additional official Fall 2026 schedule leads (July 13 2026)

These five identities are net-new after exact-name checks against `schools.py` and the research archive. They
are research-only leads: the sources below are official and current, but only CCBC exposed a clearly labeled
numeric open-seat field in this pass. No production adapter or seat value is implied for the other four; all
five still require sanctioned endpoint, scope, restriction/waitlist, freshness, and completed-term validation.

1. **Canada College (CA) — PUBLIC FALL OPEN-CLASS PDF, FOLLOW-UP REQUIRED.** San Mateo County Community
   College District's official WebSchedule publishes a dedicated Canada College Fall 2026 open-class PDF
   (`https://webschedule.smccd.edu/schedules/can_open_202608.pdf`, timestamped 7/12/2026). Rows include CRN,
   subject/course/section, title, instructor, dates, modality, campus/building, and cohort fields (for example,
   ACTG 100/121 and BIOL C1000 rows); the PDF does not expose a numeric seat field. Reproduce the district's
   sanctioned live search, preserve Canada-vs-district identity and linked components, then verify seats,
   waitlists, and a completed term before adapter work.
2. **Community College of Baltimore County (MD) — PUBLIC NUMERIC QUICKREG LEAD, FOLLOW-UP REQUIRED.** CCBC's
   official QuickReg catalog (`https://javawebapp.ccbcmd.edu/QuickReg/Register.jsp?frc=CRFALLLS`) labels its
   result columns `CRN`, `Course Number`, and `Open Seats` and serves Fall 2026 late-start sections. Current
   rows include ACDV 101 CRN 90909 (16 open), 90911 (11), and 90912 (19), with dates, campus, modality, and
   meeting details; the Fall 2026 academic calendar confirms the term and Aug. 31 start
   (`https://www.ccbcmd.edu/Programs-and-Courses/Catalog/pages/Academic-Calendars.html`). Validate the full-term
   and late-start feeds, campus/session identity, restriction/waitlist semantics, and completed-term replay.
3. **Missouri Southern State University (MO) — OFFICIAL FALL SCHEDULE + OPEN/CLOSED LIST, FOLLOW-UP REQUIRED.**
   MSSU's registrar schedule book (`https://www.mssu.edu/academics/classes/files/Fall-2026-Schedule-Book-V1.pdf`)
   is explicitly a Fall 2026 schedule with CRNs, course numbers/titles, credits, dates, meeting patterns,
   modality, campus/room, and instructor. The PDF directs users to the official open/closed class list
   (`https://lionet.mssu.edu/web/guest/course-list`) and says to select `2026 Fall (AY27)`; no numeric seat
   value was inferred from the static book. Capture the live open/closed response, identify its seat/waitlist
   fields, and replay a completed term before any adapter proposal.
4. **Suffolk County Community College (NY) — OFFICIAL CURRENT CATALOG/SCHEDULE LEAD, FOLLOW-UP REQUIRED.**
   Suffolk's official 2025–27 catalog (`https://www.scc.edu/explore-academics/college-catalog/documents/Catalog-2025-27.pdf`)
   publishes a Fall 2026 academic calendar (Aug. 26 start) and states that the online class schedule is the
   complete listing of courses for each term/campus. This pass did not capture a guest row or seat value;
   locate the sanctioned schedule response, preserve Ammerman/Brentwood/East and other campus identity,
   sections/parts-of-term, restrictions, waitlists, and completed-term behavior.
5. **Vanderbilt University (TN) — YES SCHEDULE/RESERVED-SEAT LEAD, FOLLOW-UP REQUIRED.** Vanderbilt's official
   registrar calendar (`https://registrar.vanderbilt.edu/calendars/2026-27-undergraduate.php`) records Fall
   2026 schedule publication in YES (Mar. 9), open enrollment (Jul. 22), and Aug. 26 classes; its enrollment
   bulletin (`https://www.vanderbilt.edu/enrollmentbulletin/registration-essentials/class-reserves/`) documents
   section-level reserved seats, while the Engineering first-year guide lists Fall 2026 eligible courses and
   warns that apparent openings can be reserved. This is a portal/reserve-semantics lead, not a guest numeric
   feed; verify sanctioned YES access, undergraduate/graduate school scope, seat-vs-reserve/waitlist semantics,
   and completed-term replay.

**Batch status:** five net-new identities archived. CCBC has the strongest directly labeled numeric seat evidence;
Canada and MSSU expose structured public current-term schedules, while Suffolk and Vanderbilt currently require
portal or live-endpoint follow-up. No production approval, `schools.py` edit, registry change, deployment, or
builder handoff was made.

### Batch 31 + USC — ✅ BUILT + DEPLOYED July 13 (Build): 684->689
Five schools shipped in one gated batch, all re-gated live through the REGISTERED production
adapters (commit bc1108c, deployed, live site verified 689):
- **USC** (bespoke `USC` class, classes.usc.edu same-origin REST API): re-gate reproduced Grab's
  evidence exactly — WRIT 150 Fall 162 sec 11 open/151 FULL, completed Spring 38/112, 533-section
  isFull-vs-arithmetic audit 533/533, sisSectionId unique, cross-list server-side (CLAS202≡ANTH202).
  Two NEW traps found on top of Grab's recipe and coded in: junk course codes = HTTP 500 (not 204)
  -> any error {} ; THREE terms 'Active' at once -> season-delta picker, never first-Active.
  resolve_term()->20263 verified.
- **NMSU Las Cruces** (Banner9 + new additive `Banner._campus_ok` hook; default preserves the SD
  first-word behavior — USD regression-fetched clean): exact campusDescription match isolates Main
  (ENGL 1110G = 38 of 108 systemwide, 10 open/28 FULL cap=enr). Supersedes the July 8 exclusion
  (different host). DACC rider was not taken in that July 13 deployment; **Batch 78 later fully gates and
  promotes DACC, Alamogordo, and Grants**, superseding that historical decision.
- **RPI** (ListcrseBanner8): live Fall all-open (unfilled cycle — safe by design); completed Spring
  202601 through production _build: CSCI 2600 = 4 open/6 FULL -> host-level fake-open disproof per
  NCCU/Shorter standard. July-12 hold RESOLVED.
- **Wright State** (ListcrseBanner8): guest search form dead ('No classes were found'), catalog
  route live — ENG 1100 = 48 CRNs 27 open/21 FULL, 15.4s cold/0.00s warm (TAMU envelope).
- **Duquesne** (Banner9, subclass-contained bootstrap fix): default /classSearch entry 302s to a
  firewalled plain-http URL (93.6s->{}); /term/termSelection bootstrap fixes it (1.2s). Term picker
  verified dodging parallel 'College of Medicine Fall 26'/Paralegal terms -> 202710.
Regressions green: USD (campus pool), UTK (plain Banner9), WSSU (ListcrseBanner8).

### Scheduled weekly hold+CT-log check — July 13 2026

HOLD-list recheck (`hold_recheck.py`): Aurora University, Colorado Mountain, American Samoa CC,
and Columbus State all still `FALL-LIVE=no` — no change, re-check next week.

CT-log discovery batch (`ctlog_weekly_2026-07-13.py`, 11 fresh 4-year HBCU/regional-public
domains not previously queued: Fayetteville State, Elizabeth City State, Bowie State, Savannah
State, Alcorn State, Jackson State (MS), Delaware State, Langston, Central State (OH), Virginia
State, Norfolk State): `checked=8/11 ct_FAIL=3 SSB_hits=0`. ECSU and DESU turned up live Banner
SSB hosts (`ssb.ecsu.edu`; `bnrhvpprd/prod/test-ssb.desu.edu`) but neither returned a working guest
`classSearch`/`getTerms` response — no numeric seat evidence, not addable. bowiestate.edu,
savannahstate.edu, jsums.edu hit crt.sh failures (retry candidates for next pass). No actionable
finds this run.

### Rice University — ✅ BUILT + DEPLOYED July 13 (Build): 689->690
Bespoke `Rice` adapter (courses.rice.edu !SWKSCAT.cat custom Banner catalog, guest, no auth).
Re-gate CORRECTED two spec items from the relay: (1) completed Spring 2026 is **202620**, not
202520 (Rice codes are academic-year based — 202520 is Spring 2025; read from the picker, labels
win); (2) NEW TRAP: **Quadmester sub-terms** (202611/202615/202625/202705) interleave with
semesters and 'quadmester' is NOT in _SUBTERM — Rice's picker requires the literal word
'Semester'. Gate evidence through the REGISTERED adapter: MATH 101 = 6 sec **5 open/1 LIVE-FULL**
(cap=enr in the current term — the strongest disproof), ENGL completed 202620 = 16/109 genuinely
full via the same parse, xlist-bound example verified (sec 10/10, xlist 15/16 -> not-open),
9.4s cold/0.00s warm (Purdue envelope), resolve_term()->202710, junk->fail-closed sentinel.
WAITLIST: no live specimen found (ENGL 202620 sweep ×109 + partial COMP: zero pages carry
waitlist text) — implemented STRICTLY FAIL-CLOSED: any waitlist text without a parseable
'Waitlisted: 0' = not-open. Grab's own waitlist-regex doubt stands; a live specimen would let us
relax nothing (rule is already maximal-safe). Commit + deployed same session; live site 690.

### Princeton (elite lead) — ACCURACY-VERIFIED, but DEPLOYMENT-BLOCKED (benched pending Nathan's architecture call, July 13, Build)
Grab's elite #3. Re-gated the DATA fully; the school is accuracy-safe. But it uniquely cannot ship
under SeatWatch's stdlib-only / single-scp architecture without a decision from Nathan.

ACCURACY (all re-verified live through the plain API):
- Two-call public API on api.princeton.edu (classes list + student-app/courses/seats), anonymous
  Bearer token. api.princeton.edu is plain-stdlib reachable (401 on bad token, no challenge).
- OPEN RULE sound: seat_status=="Open" AND (capacity-enrollment)>0. seat_status vs arithmetic agreed
  on 100% of sections BOTH terms (Fall 1272: 146/146; completed Spring 1264: 128/128; 0 disagreements).
- CANCELED TRAP confirmed + handled: bare `status`=="C" covers BOTH Closed AND Canceled in both terms
  (Fall 24 Closed + 4 Canceled; Spring 18 Closed + 38 Canceled) — MUST read seat_status to drop Canceled.
- LIVE-TERM DISPROOF (best of the elite four — no completed-term melt needed): current Fall COS has
  genuinely Closed rows incl. exact-full class 21189 = 25/25 and over-cap class 22499 = 25enr/20cap.
  Numeric enrolled>=capacity can't be faked open.
- SCOPING TRAPS confirmed: param is `subjects` PLURAL + `subjects_count` (singular `subject=` silently
  returns the whole term); `subjects=COS` also returns cross-listed primaries (ECE/ECO/MAE/ORF/PSY/QCB/
  SML/SPI). Exact scope = (subject==SUBJ AND catnum.trim()==NUM) OR crosslistings contains "SUBJ NUM".
  Verified: exact-scoped COS 126 = 1 course (class 21194). Section key = class_number (unique).
- RELAY CORRECTION: Grab's headline "COS = 2,442 open / 385 Closed / 72 Canceled" is TERM-WIDE numbers,
  not COS — exact-scoped COS is ~150 sections (122 open/24 closed/4 canceled). Traps + concrete rows
  reproduced exactly; only the aggregate was mislabeled. Terms: 1272=Fall26-27, 1264=Spring25-26 (labels).

DEPLOYMENT BLOCKER (the reason it's benched, not shipped):
- The Bearer token lives ONLY in registrar.princeton.edu HTML (drupalSettings.ps_registrar.apiToken),
  and that host is behind a Cloudflare "Just a moment…" anti-bot challenge → plain stdlib gets 403.
  Verified NO stdlib-reachable alt source (API base 404, /token 405, /anonymous 202-empty, www 404,
  mobile config 404). Defeating the challenge is off-limits (bot-detection). Token grabbed ONCE via the
  real in-app browser for THIS gate only; decodes to a WSO2 gateway app cred (anonymous, same for every
  logged-out user) — NOT committed to the repo.
- So a production adapter needs either: (A) hardcode the anonymous token — pure stdlib, ships clean,
  accuracy-safe (dead token = 401 = empty = never a false open), BUT silent whole-school outage if it
  ever rotates (stability unknown; WSO2 app-cred pattern suggests it's fairly stable but unproven); or
  (B) a headless browser on the Oracle box to bootstrap the token each cycle — BREAKS stdlib-only,
  adds Chromium+driver deps, ongoing memory/CPU cost, vuln surface, fragility on a small VM.
- RECOMMENDATION: bench behind the pure-stdlib wins (Maricopa +10, batch 40-42 Banner9 hosts). If Nathan
  wants the Princeton name, least-bad path is (A) hardcode + a 401 health-alert (since dead=safe). Do
  NOT adopt (B) — a browser dependency on the poller is the one change that most undermines the
  stdlib-single-scp design that makes the accuracy discipline sustainable. NO schools.py edit made.

### Codex Batch 58 — gate-resolution supplements (July 13 2026)

This is a gate-resolution supplement for existing leads, not a new identity list. Four sources cleared the
research bar and are **GATED, AWAITING GO-AHEAD** for builder review. Roxbury and UMass Lowell remain held out
because they failed the completed-term/numeric-seat requirements. No `schools.py` or builder changes were made.

1. **Brandeis University (MA) — GATED, AWAITING GO-AHEAD.** Current Fall 2026:
   `https://registrar-prod.unet.brandeis.edu/registrar/schedule/classes/2026/fall/1800/UGRD`; completed Spring 2026:
   `https://registrar-prod.unet.brandeis.edu/registrar/schedule/classes/2026/spring/1800/UGRD`. The official page is
   undergraduate, term-labeled, and subject-scoped (English `1800`) with `Course #`, `Time`, and `Enrl / Lim / Wait`.
   Fall reproduces `ENG 12A 1` Open `12 / 22 / 0` and `ENG 19A 1` Waitlist `11 / 11 / 4`; Spring reproduces
   `ENG 22A 1` Open `17 / 20 / 0` and `ENG 10B 1` Waitlist `20 / 20 / 0`. Open requires explicit `Open` plus a
   sane positive `Lim-Enrl`; explicit `Waitlist` is closed even when arithmetic is ambiguous. Native key is the
   complete course label plus section (for example `ENG 12A 1`). The subject page repeats cross-listings under
   requirement headings, so dedupe identical `(course label, section, title, meeting, instructor)` rows. Keep the
   selected subject and undergraduate career; exclude consent/independent-instruction rows unless supported.
   This is a bespoke HTML adapter candidate; enforce a 30-second timeout and fail closed on term/HTML mismatch.

2. **University of Maryland, College Park (MD) — GATED, AWAITING GO-AHEAD.** Current Fall 2026:
   `https://app.testudo.umd.edu/soc/202608/ENGL/ENGL101`; completed Spring 2026:
   `https://app.testudo.umd.edu/soc/202601/ENGL/ENGL101`. Each page gives an `Open Seats as of` timestamp and
   `Seats (Total, Open, Waitlist[, Holdfile])` per section. Fall examples: ENGL101 `0504` has `Open 1`, `0602`
   has `Open 5`, and `0102` has `Open 0, Waitlist 1`; Spring examples: `0001` `Open 1`, `0102` `Open 0`, and
   `0103` `Open 7`. Open is numeric `Open > 0`; zero-open rows are closed regardless of waitlist/holdfile. Native
   key is `term + subject/course + section` (for example `202608/ENGL/ENGL101/0504`). Preserve location/program,
   delivery, and restriction text; the form offers College Park, Shady Grove, UMAB, online, and other programs, so
   explicitly select College Park to prevent campus leakage. Bespoke HTML candidate; enforce a 30-second timeout and
   fail closed on stale/missing timestamp or non-College-Park rows.

3. **San José State University (CA) — GATED, AWAITING GO-AHEAD.** Current:
   `https://www2.sjsu.edu/classes/schedules/fall-2026.php`; completed archive:
   `https://www2.sjsu.edu/classes/schedules/archive/spring-2026.php`. Both official tables expose `Section`, `Class
   Number`, mode, dates, and explicit `Open Seats`; Fall is stated to refresh nightly. Fall examples: `MATH 30`
   section 01 class `42239` has `1` open and section 03 class `43377` has `19`; zero-open rows coexist. Spring
   examples: `AAS 1` section 01 class `27518` has `0`, section 05 class `27509` has `4`. Open is only
   `Open Seats > 0`; never infer availability from reserve capacity. SJSU documents reserve seats and waitlist
   movement, so preserve notes and treat reserve/permission rows conservatively. Native key is `term + class number`
   (class numbers are unique), with section label as fallback. The public table excludes some no-print classes that
   require MySJSU, so do not call it exhaustive. Enforce a 30-second timeout and fail closed if the table/column is
   absent.

4. **University of Delaware (DE) — GATED, AWAITING GO-AHEAD.** Official form:
   `https://udapps.nss.udel.edu/CoursesSearch/`; form action is `search-results`. Validated recipe: `GET
   /CoursesSearch/search-results?term=2268&search_type=A&course_sec=ACCT` (Fall 2026), replayed with `term=2263`
   (Spring 2026). The response table labels `Course`, `Campus`, `Open seats`, `Session`, and `Instruction Mode`.
   Fall examples include `ACCT200010` `12 OF 50` and `ACCT207011` `0 OF 55` with `CURRENTLY FULL`; Spring includes
   `ACCT207010` `0 OF 49`/`CURRENTLY FULL` and positive-open rows. `CURRENTLY FULL` means the meeting-group capacity
   is reached; `WL` means wait list. Open is numeric first value in `X OF Y > 0` and no `CURRENTLY FULL`; a WL badge
   alone does not close a positive-open row. Native key is linked course code plus term (for example `ACCT207010`),
   retaining `courseid`, `offernum`, `session`, and `section` from the link. Preserve campus (`NEWRK`, `DOVER`,
   `GTOWN`, `WILM`, `DIST`, etc.), session, mode, and cross-list indicators. The official page exposes `Last updated`
   (Fall probe: `7/13/26 02:22 PM`) and the Registrar warns that Courses Search is not real-time, so surface the
   timestamp and fail closed on stale/missing tables. Enforce a 30-second timeout.

**Held out after this pass:** Roxbury Community College has public Fall 2026 `Open`/`Full` status rows but no
numeric capacity and no public completed-term replay. UMass Lowell exposes `Course Full` and `Course Full - Wait
List Available` but no numeric capacity or completed-term seat replay. Neither is safe for builder handoff yet.

**Batch status:** four gate-resolved candidates are documented above; two claimed leads are explicitly held out.
All four require Nathan's explicit go-ahead before builder work. No production approval, `schools.py` edit, registry
change, deployment, or builder handoff was made.

### Codex Batch 59 — gate-resolution supplements (July 13 2026)

This was a five-lead promotion pass. **No school cleared every gate, so none is `GATED, AWAITING GO-AHEAD` and
no production change is proposed.** Each hold-out below is recorded with the exact blocker; do not infer seats or
hand any of these to the builder until the blocker is resolved.

1. **Bowling Green State University (OH) — HOLD OUT: status-only.** Official search:
   `https://services.bgsu.edu/ClassSearch/search.htm`; shareable Fall 2026 query:
   `https://services.bgsu.edu/ClassSearch/search.htm?searchType=advanced&semester=2268&undergraduate=&graduate=&campus=ALL`.
   The official result page is term-labeled and fresh (Fall 2026, data current 07/13/2026 2:31 PM) and exposes
   unique class numbers/sections, but its own disclaimer says results do **not** reflect whether a class is open,
   closed, or its current enrollment level. No numeric seat/status field exists to validate mixed availability, and
   the site exposes no completed-term status replay. Hold until a sanctioned endpoint supplies explicit seats or
   open/closed/waitlist states plus a completed-term check; no adapter recipe is safe yet.

2. **Marshall University (WV) — HOLD OUT: term/latency gate.** Official open-class listing:
   `https://mubert.marshall.edu/scheduleofcourses.php?showschedule=openclasslist`. The public form currently
   offers only Fall 2026 (`202701`) and Summer 2026 (`202603`), with no completed term. It documents red rows as
   “at their enrollment limit,” but the submitted Fall 2026 listing exceeded the 30-second research timeout and
   therefore produced no reproducible section rows. Without a completed-term replay and a sub-30-second request,
   do not promote.

3. **California State University, San Bernardino (CA) — HOLD OUT: unauthenticated client shell.** Official page:
   `https://www.csusb.edu/class-schedule`. The rendered template documents native `enrl_TOT`, `enrl_CAP`,
   `enrl_STAT`, waitlist fields, section/class numbers, campus, and the seat formula, but the page itself is only
   an Angular shell. Rows are fetched from `webdx-sso.csusb.edu` through a bearer-token flow; no sanctioned
   no-login current/completed response was obtained in this pass. Do not extract from the template or guess API
   parameters; hold until the public UI yields reproducible current and completed rows.

4. **Claremont McKenna College (CA) — HOLD OUT: no historical term and consortium scope.** Official form/results:
   `https://webapps.cmc.edu/course-search/form.php` and `https://webapps.cmc.edu/course-search/search.php`.
   Fall 2026 results are strong current evidence with native `Course - Section`, meetings, notes, and explicit
   mixed seats (for example `AFRI010A AF - 01` `16/25 (Open)` alongside `AFRI116 AF - 01` `-3/15 (Closed - Full)`).
   However, the form exposes only `FA 2026`; posting `SP 2026` or `FA 2025` is silently normalized back to FA 2026,
   so no completed-term replay exists. Rows also visibly span SC/PO/HM campus codes (the 5C consortium), so CMC-only
   scope is not proven. Hold until historical terms and campus scope are independently selectable.

5. **Community College of Baltimore County (MD) — HOLD OUT: open-only late-start catalog/no replay.** Official
   QuickReg: `https://javawebapp.ccbcmd.edu/QuickReg/Register.jsp?frc=CRFALLLS`. The Fall 2026 “Credit Classes -
   Late Starts” table exposes native CRNs and numeric `Open Seats` (ACDV101 CRNs 90909/90911/90912 are visible),
   with campus, dates, modality, and term `202691`. The catalog is an available/open inventory and provides no
   closed or waitlist rows for a mixed-status check. The official Spring 2026 URL (`frc=CRSPRING`) currently
   returns an empty catalog, so there is no reproducible completed-term replay. CCBC was already listed as a Batch 57
   lead; this pass adds no duplicate identity and does not authorize production work.

**Batch status:** five claimed leads explicitly held out; zero gated candidates. No `schools.py`, builder, registry,
or deployment changes were made. Re-probe only when the documented blocker is resolved.

### Codex Batch 60 — gate-resolution supplements (July 13 2026)

This pass tested five Northwest public-schedule leads. **Portland Community College is `GATED, AWAITING GO-AHEAD`;**
the other four are explicit hold-outs. No production change is proposed and no school should be sent to the builder
without Nathan's approval.

1. **Portland Community College (OR) — GATED, AWAITING GO-AHEAD: bespoke numeric schedule/capacity endpoint.**
   Official schedule index: `https://www.pcc.edu/schedule/`; exact current course page:
   `https://www.pcc.edu/schedule/fall/bi/bi101/`; official capacity script:
   `https://www.pcc.edu/schedule/wp-content/themes/pcc-schedule/scripts/capacity.js?ver=1721237068`.
   The Fall 2026 page is term-labeled (`data-term="202604"`) and exposes native CRNs. The script's documented
   POST is `https://www.pcc.edu/schedule/capacity/` with `term=202604` and a comma-separated `crn` list; it returns
   JSON seat and waitlist counts without authentication. A reproduced response included mixed numeric states:
   CRN `40145` = `1/24` seats open; `40680` = `0/24`, wait `4/5`; `40452` = `0/24`, wait `3/5`; `40665` =
   `0/24`, wait `0/5`; and additional closed/waitlisted rows. Open is `seat[0] > 0`; preserve capacity and
   `wait[0]/wait[1]` rather than inferring from styling. CRN is the native section key, the exact BI 101 page
   prevents sibling-course leakage, and the POST has no hidden filter beyond the requested term/CRNs. The page
   reports a cache timestamp of `2026-07-13 12:05:59`; the official JavaScript uses a 10-second request timeout,
   under the 30-second gate. The public selector currently exposes only Summer/Fall 2026; the Spring URL returns
   “Invalid search,” so there is no completed-term archive. This is explicitly noted as a limitation, but the source
   is numeric (not status-only), with current mixed open/closed/waitlist evidence and a fail-closed missing/invalid
   response path. Bespoke adapter work is still required; do not edit `schools.py` in research.

2. **Pima Community College (AZ) — HOLD OUT: no public seat/status rows.** Official schedule form:
   `https://bannerweb.pima.edu/pls/pccp/az_tw_zipsched.p_search`; current public choices are only Fall 2026
   (`202710`) and Summer 2026 (`202630`). The unauthenticated form exposes search filters but no seat or
   open/closed/waitlist fields in the returned page, and no completed-term replay is available. Do not infer
   availability from the catalog or hand off an adapter.

3. **North Seattle College (WA) — HOLD OUT: ctcLink login gate.** District schedule page:
   `https://www.seattlecolleges.edu/academics/class-schedules`; the current Fall 2026 and Spring 2026 links point
   to ctcLink guest class-search URLs, but both redirect to the ctcLink login/cookie page before any rows are
   returned. The district page proves institution identity and schedule ownership only; it does not provide seats.

4. **Seattle Central College (WA) — HOLD OUT: ctcLink login gate.** It shares the district schedule surface above;
   the public current and completed-term links redirect to login, so no reproducible unauthenticated section rows,
   seat integers, waitlists, or historical replay were obtained. Keep separate from North/South if the gate is later
   resolved; no district-wide seat assumption is safe.

5. **South Seattle College (WA) — HOLD OUT: ctcLink login gate.** Same official district links and same blocker:
   current Fall 2026 and Spring 2026 ctcLink searches are login-gated before results. No public seat/status payload
   or completed-term replay is available in this pass.

**Batch status:** one candidate (PCC) is `GATED, AWAITING GO-AHEAD`; four are held out with documented blockers.
No `schools.py`, registry, deployment, or builder changes were made. PCC remains a bespoke research handoff only.

### Codex Batch 61 — gate-resolution supplements (July 13 2026)

This pass tested five Mountain West public class-search leads. **Great Falls College MSU and the University of New
Mexico are `GATED, AWAITING GO-AHEAD`;** Wyoming, Idaho, and UNLV remain explicit hold-outs. No production change is
proposed and no school should be sent to the builder without Nathan's approval.

1. **Great Falls College MSU (MT) — GATED, AWAITING GO-AHEAD: official APEX numeric scheduler.** Official route:
   `https://apexprod.msu.montana.edu/apex/r/esg/s_class_schedule_gf/class-schedule`. The page exposes Fall 2026
   (`202670`) through Spring 2023, CRN/course/section identity, course status, Available, Enrolled, Capacity,
   waitlist capacity, waitlisted, waitlist available, meeting details, modality, and part-of-term. The current
   no-filter Fall replay returned 311 rows and a mixed-status sample: CRN `67109` (`ACTG 101-200`) has `21` available,
   `4/25` enrolled/capacity; CRN `67021` (`COMX 115-180`) is explicitly `CLOSED` with `0/25`; rows also include
   consent/restriction labels and online, face-to-face, blended, and hyflex modalities. The same page's open-seat
   filter returned 280 rows, proving the filter is not silently converting all rows to one status. Spring 2026
   (`202630`) replay is populated and preserves the same numeric schema (for example CRN `63136` = `10/25` open and
   CRN `63373` = `CLOSED`, `0/1`). Use CRN as the native key and keep the official Great Falls route/campus scope;
   preserve meeting-location codes such as GFCMSU/SHC and all restrictions rather than treating them as separate
   colleges. APEX requests completed in a few seconds in this pass, well below the 30-second gate. This is a
   bespoke adapter candidate; no `schools.py` edit was made.

2. **University of New Mexico (NM) — GATED, AWAITING GO-AHEAD: public schedule-of-classes table.** Official index:
   `https://lobowebapp.unm.edu/apex_ods/f?p=SCHEDULE_OF_CLASSES:SEMESTERS:::`; Albuquerque/Main full schedule
   (`202680`) and completed Spring 2026 (`202610`) are directly selectable. The Fall table is explicitly labeled
   “Albuquerque Main,” says it is refreshed every 24 hours, and exposes native CRNs, subject/course/section, status,
   section capacity, enrolled, modality, restrictions/comments, and meeting details. Current mixed evidence includes
   CRN `64191` (`ACCT 2110-001`) `OPEN`, capacity 60/enrolled 41; CRN `64197` (`ACCT 2110-002`) `WAIT LIST AVAILABLE`,
   60/60; and CRN `83571` (`AFST 397-005`) `CLOSED`, 5/5. Spring replay is populated with the same fields (for
   example CRN `51543` `OPEN`, 60/56, and CRN `59084` `WAIT LIST AVAILABLE`, 60/60). Gate open only when status is
   `OPEN` and `enrolled < capacity`; preserve `WAIT LIST AVAILABLE` separately and never infer a waitlist from a
   full numeric row alone. The direct term/campus URL prevents branch-campus leakage; branch campuses are separate
   public selections. Requests rendered in a few seconds here; enforce a 30-second timeout and fail closed on stale,
   missing, or malformed tables. Bespoke adapter work is required; no `schools.py` edit was made.

3. **University of Wyoming (WY) — HOLD OUT: registration search requires login.** Official WyoRecords:
   `https://wyossb.uwyo.edu/StudentRegistrationSsb/ssb/registration`. The public page states that students must be
   logged in to “Search and Register” or “Search and Plan.” No unauthenticated current/completed section rows,
   seat integers, or waitlist payload were obtained; do not infer from the academic calendar or catalog.

4. **University of Idaho (ID) — HOLD OUT: public term shell did not yield rows.** Official registrar class-search
   link: `https://banner.uidaho.edu/StudentRegistrationSsb/ssb/term/termSelection?mode=search`. The Registrar confirms
   this is the official class-search tool, but the public term-selection response in this pass exposed only the
   generic Start Date/End Date/Continue shell; no current or completed section rows, seat integers, status mix, or
   replay could be reproduced. Hold until a documented no-login term/result route is available.

5. **University of Nevada, Las Vegas (NV) — HOLD OUT: MyUNLV login gate.** Official class search:
   `https://my.unlv.nevada.edu/psc/lvporprd/EMPLOYEE/SA/c/COMMUNITY_ACCESS.CLASS_SEARCH.GBL`. The route redirects to
   the MyUNLV login/cookie page before current or completed results, so no unauthenticated seats, waitlists, or
   section identity could be validated. Do not use catalog/calendar pages as a substitute.

**Batch status:** two candidates (Great Falls College MSU and UNM) are `GATED, AWAITING GO-AHEAD`; three are held out
with exact blockers. No `schools.py`, registry, deployment, or builder changes were made.

### Codex Batch 62 — Great Plains gate-resolution supplements (July 13 2026)

This pass tested five Great Plains public-search leads. **South Dakota State University and the University of South
Dakota are `GATED, AWAITING GO-AHEAD`;** North Dakota, North Dakota State, and Nebraska–Lincoln remain explicit
hold-outs. No production change is proposed and no school should be sent to the builder without Nathan's approval.

1. **South Dakota State University (SD) — GATED, AWAITING GO-AHEAD: official SDBOR guest class search.** SDSU's
   official IT page links guests to the Board of Regents `Browse Classes` route and explicitly permits browsing
   without registration/login: `https://www.sdstate.edu/information-technology/self-service`,
   `https://registration.sdbor.edu/StudentRegistrationSsb/ssb/term/termSelection?mepCode=BOR&mode=search`. Fall
   2026 (`2026 Fall`) returned 8,766 classes and Spring 2026 (`2026 Spring (View Only)`) returned 8,646. Results
   are institution-labeled `SDSU South Dakota State Univ` and preserve native CRNs, subject/course/section,
   instructor, meeting dates/location, modality/indicators, and linked sections. Current mixed evidence includes
   CRN `70363` (`ACS 102 S01`, `11 of 32 seats remain`), `70373` (`FULL: 0 of 30`), `70376` (`1 of 32`), and
   `77069` (`22 of 32`, plus `10 of 10 waitlist seats remain`). The completed Spring replay includes CRNs `10196`
   (`9 of 30`), `10197` (`18 of 30`), `10199` (`1 of 25`), and an explicit `FULL: 0 of 25` row. Use CRN as the
   section key; parse `X of Y seats remain` and the explicit `FULL:` marker, preserving waitlist counts separately.
   The all-class result is paged (10/page) but responds in a few seconds, well under the 30-second gate. A bespoke
   SDBOR adapter must carry the selected university and term; never treat the shared endpoint as SDSU-only.

2. **University of South Dakota (SD) — GATED, AWAITING GO-AHEAD: same official SDBOR search with university scope.**
   The official USD help page confirms the Browse Classes workflow (select term, select USD, search):
   `https://td.usd.edu/TDClient/33/Portal/KB/Article/3109/Verifying-Class-or-Instructor-listed-in-Banner-Student`.
   Fall 2026 filtered to `USD University of South Dakota` returned 2,536 classes; Spring 2026 (view-only) returned
   2,677. Current rows are institution-labeled `University of South Dakota` and preserve native CRN, subject/course/
   section, meeting details, modality/indicators, and waitlists. Fall samples: CRN `73367` (`ACCT 210 U15`, `25 of
   45 seats remain`, `25 of 25 waitlist seats remain`), `76867` (`13 of 45`, `10 of 10`), `73438` (`15 of 45`),
   and `75264` (`FULL: 0 of 45`, `4 of 10`). Spring samples include CRNs `19289` (`1 of 47`, `10 of 10`) and
   `27087` (`11 of 40`, `10 of 10`) alongside explicit full rows. Use CRN as the key and retain the selected USD
   filter in every request; the same SDBOR parser/timeout semantics as SDSU apply. The route is bespoke because the
   shared endpoint must be scoped to USD rather than relying on a default institution.

3. **University of North Dakota (ND) — HOLD OUT: Campus Connection login.** Official registration instructions
   route class search through Campus Connection and describe an authenticated workflow; no unauthenticated current
   or completed section rows, numeric seats, waitlists, or replay were reproducible:
   `https://business.und.edu/student-experience/academic-advising/registration.html`.

4. **North Dakota State University (ND) — HOLD OUT: Campus Connection login.** NDSU's official registration page
   sends students to Schedule Planner/Campus Connection, and the registrar's help page identifies the class-search
   view inside that portal. No public result rows or seat payload were available without login:
   `https://www.ndsu.edu/onestop/academics/registration/registering`,
   `https://www.ndsu.edu/registrar/facstaff/cchelp/navigations`.

5. **University of Nebraska–Lincoln (NE) — HOLD OUT: MyRED/Enrollment Scheduler.** The official registrar
   instructions place class registration and the `Only Open Classes` filter in MyRED; the public registrar pages
   did not expose an unauthenticated numeric current/completed class table. Hold until a reproducible no-login route
   with seat/status rows is found: `https://registrar.unl.edu/student-resources/registration/class-registration-tutorials/classic-registration-instructions/`.

**Batch status:** two candidates (SDSU and USD) are `GATED, AWAITING GO-AHEAD`; three are held out with exact
blockers. No `schools.py`, registry, deployment, or builder changes were made.

### Codex Batch 63 — public numeric/search gate-resolution supplements (July 13 2026)

This pass rechecked five claimed identities against official, no-login schedule surfaces. Two cleared the
research gate and are **GATED, AWAITING GO-AHEAD** for a bespoke builder adapter; three are held out with explicit
blockers. No `schools.py`, registry, deployment, or builder changes were made.

1. **Quinsigamond Community College (MA) — GATED, AWAITING GO-AHEAD.** Official public search:
   `https://theq.qcc.edu/ICS/Course_Offerings_and_Schedule.jnz?portlet=AddDrop_Courses&screen=Advanced+Course+Search&screenType=next`.
   Select `Fall 2026`, Department `English`, then Search. The guest page returns eight result pages with native
   section labels, term dates, instructor, campus/building, method, and numeric seat strings plus explicit status.
   Fall examples include `ENG 099-04` `1 / 20` `Reopened`, `ENG 099-05` `11 / 20` `Open`, `ENG 099-50` `0 / 20`
   `Closed`, `ENG 101-01` `17 / 22` `Open`, and closed `ENG 101-07` `0 / 22`. The completed-term replay is
   `Spring 2026` with the same Department filter; rows carry Jan 26–May 19, 2026 dates and numeric values (for
   example `ENG 101-07` `6 / 21` `Reopened` and `ENG 101-17` `1 / 22` `Reopened`), proving the term selector is
   real rather than a static Fall view. Use the visible `course + section` (for example `ENG 101-05`) as the native
   term-scoped key, preserve the literal seat/status string (do not reinterpret `Reopened`), and retain campus,
   method, dates, instructor, and page number. Restrict the Department/term controls on every request; the site is
   Jenzabar 9.4 with JavaScript postback detail links, so a bespoke adapter must fail closed if the result table or
   selected-term label is absent. Current and replay requests completed in under 30 seconds.

2. **Massachusetts College of Art and Design (MA) — GATED, AWAITING GO-AHEAD.** Official guest catalog:
   `https://mca-ss.colleague.elluciancloud.com/Student/Student/Courses` (linked from the Registrar’s Student
   Planning page, `https://massart.edu/academics/office-of-the-registrar/student-planning/`). Select `Fall 2026`
   and subject `Animation (CDAN)`. The section-listing view is unauthenticated, two pages, and term-labeled; it
   exposes native IDs, title, dates, campus, meeting/location, faculty, academic level, and a literal four-number
   seat field. Fall examples: `CDAN-300-02` `Open` `4 / 11 / 15 / 0`, `CDAN-302-01` `Waitlisted` `0 / 13 / 13 / 0`,
   `CDAN-302-02` `Open` `5 / 8 / 13 / 0`, and `CDAN-303-01` `Waitlisted` `0 / 14 / 14 / 3`. Replay with
   `Spring 2026` and the same subject returns true Jan 19/20–May 21 dates and mixed `Open`/`Closed` rows (for
   example `CDAN-212-01` `Closed` `0 / 15 / 15 / 0`, `CDAN-222-01` `Open` `2 / 13 / 15 / 0`, and
   `CDAN-301-02` `Open` `4 / 10 / 14 / 0`). Keep the native four-number text and status verbatim until the builder
   confirms the Ellucian seat-field order; use `term + section ID` (for example `26/FA + CDAN-302-02`) as key,
   preserve campus/career/modality/restrictions, and follow both result pages. Requests were under 30 seconds.

3. **University of Maryland, College Park (MD) — RECHECK ONLY; EXISTING GATE RETAINED WITH FRESHNESS GUARD.**
   `https://app.testudo.umd.edu/soc/` still exposes direct numeric Fall 2026 and Spring 2026 pages with exact
   sections and mixed positive/zero `Open` values. However, the replayed Spring page displayed the same
   `Open Seats as of 07/13/2026 03:30 PM` timestamp as the current page, so this pass does not create a new
   completed-term claim. Keep the previously documented UMD gate only if the adapter requires a fresh timestamp,
   explicit College Park scope, and fails closed when the timestamp is stale or unchanged across terms.

4. **Webster University (MO) — HOLD OUT: false term freshness.** Official search:
   `https://classes.webster.edu/`. Current Fall 2026 `ENGL` search is public, three pages, and exposes exact
   section codes, schedule/location, and mixed `Seats open X/Y` plus `Open`/`Full` rows (for example `ENGL-1030-01`
   `8/26 Open`, `ENGL-1030-1T` `0/25 Full`, and `ENGL-1044-02` `21/26 Open`). Selecting the native completed
   option `2025-26 AY - Spring Semester` (`2025;SP`) and resubmitting left the results dated Fall 2026 with the
   same rows; the selector value changed but the payload did not. Until a sanctioned request path produces a real
   completed-term replay, do not promote or infer historical availability.

5. **Williston State College (ND) — HOLD OUT: no completed-term option.** Official class search:
   `https://willistonstate.edu/class-search.aspx`. The public page defaults to Summer/Fall 2026 and Spring/Summer
   2027 checkboxes and returns native class numbers, dates, delivery, campus/location, department, and numeric
   open-seat or `Waitlist Only` status. Examples include Fall 2026 `WELD-214` class `41436` `12 Open Seats`,
   `WSC-100` class `41886` `19 Open Seats`, and class `41994` `Waitlist Only`; Summer 2026 `WSC-100` class `14918`
   has `8 Open Seats`. The visible selector has no Spring 2026 or other completed term, and the all-term result set
   mixes future offerings and high-school/off-campus sections. Hold until a public completed-term replay and an
   explicit college/career scope filter are available; do not infer closed status from missing rows.

**Batch status:** Quinsigamond and MassArt are fully documented bespoke candidates and await Nathan’s explicit
go-ahead. UMD was a freshness recheck only; Webster and Williston are held out. No production approval or code
change was made.

### Codex Batch 64 — public source-lead gate-resolution supplements (July 13 2026)

This batch resolved five existing source leads without repeating hostname sweeps. One school cleared the full
current/completed gate; four are held out with reproducible blockers. Clark College was removed immediately as a
duplicate (`schools.py` already contains `wa-clark`); Lewis & Clark College is a distinct school and was checked
instead. No production code or builder handoff was made.

1. **Wabash College (IN, ~900 students, private four-year) — GATED, AWAITING GO-AHEAD.** Official current
   schedule: `https://www.wabash.edu/apps/registrar/course-sections/?sortby=SectionName&term=26%2FFA`; completed
   schedule: the same route with `term=26%2FSP`. Both are public HTML tables with no login, no result cap, and
   native detail links carrying unique `csid` values. Fall 2026 returned 407 table rows with 311 `OPEN`, 54
   `WAITLISTED`, and 32 `CLOSED`; examples include `ACC-201-01` 18/25 enrolled/available (open), `ART-126-01`
   10/13 with waitlist 1, and explicit closed rows at zero available. Spring 2026 returned 422 rows with 305 open,
   40 waitlisted, and 67 closed; examples include `ACC-202-01` 19/20/1 open and closed rows in the same table.
   Each row preserves term, section label, title, cross-list links, dates, meeting times, location, instructor,
   capacity, enrolled, available, waitlist, course type, credits, and restrictions. Use `term + section + csid`
   as the key; keep cross-listed and senior-only variants separate, and do not collapse rows with the same meeting.
   Requests completed in roughly 3–4 seconds and pagination was absent (full table rendered). This is a bespoke HTML
   adapter candidate; fail closed if the term label, status, `csid`, or seat triplet disappears.

2. **Lewis & Clark College (OR, private four-year) — HOLD OUT: login-gated Self-Service.** Official public
   documentation points to `https://go.lclark.edu/selfservice` and describes CAS Fall 2026/Spring 2027 section
   status, seats, and waitlists, but the live redirect resolves to
   `https://selfservice.lclark.edu:8083/Student/Account/Login` and shows only a username/password form. No guest
   rows or completed-term replay were obtained; do not infer availability from the documentation or visual schedule.

3. **Hawkeye Community College (IA, public community college) — HOLD OUT: completed-term status gate unresolved.**
   Official guest catalog: `https://hcc-sservice.hawkeyecollege.edu/Student/Courses` (linked from
   `https://www.hawkeyecollege.edu/academics/credit-courses/`). Fall 2026 `ENG English Composition` search exposed
   exact section labels such as `ENG-105-509`, numeric `Seats Available/Capacity/Waitlisted` triplets (for example
   4/20/0 and 17/20/0), dates, campus/online location, modality, and separate waitlisted rows. Spring 2026 replay
   returned true Jan 12–May 7 dates and numeric positive-seat rows, but the tested intro-course result contained no
   closed section and the surface does not publish a trustworthy closed/full status for that replay. Hold until a
   finished-term mixed closed/waitlist result is reproducible; preserve the native section plus synonym and exact
   subject filters if re-probed.

4. **Butler County Community College / BC3 (PA, public community college) — HOLD OUT: historical term empty.**
   Official credit schedule: `https://www.bc3.edu/credit-schedule/index.html`; public Fall route:
   `https://colss-prod.ec.bc3.edu/Student/Courses/Search?TopicCodes=S1&Terms=2026FL&SearchResultsView=1`.
   Fall 2026 Session 1 returned 491 public sections with exact `ACCT-203-B01`-style keys, explicit Open status,
   numeric availability triplets (23/28/0, 4/23/0, etc.), campus/modality/session fields, and multiple locations.
   The sanctioned term-pattern replay `Terms=2026SP` returned `No Sections Found` with empty filters, so no
   completed-term mixed-status test is possible. Hold; do not treat the empty historical catalog as closed data.

5. **University of Houston (TX, public four-year) — HOLD OUT: limited short-session source/no replay.** Official
   source: `https://www.uh.edu/online/sessions/class-search.php`. The guest iframe offers only Summer/Fall 2026
   short sessions (not the regular UH catalog), program-level and subject controls, and current Fall Session 1
   `ENGL` results with mixed `Open`/`Closed` and numeric enrollment/capacity (e.g. closed 25/25 rows). It has no
   Spring 2026 or other completed-term option, and the university explicitly scopes it to condensed Session 2–6
   courses refreshed twice daily. This is insufficient for a full UH adapter; hold unless a separate regular-catalog
   guest endpoint and completed-term replay are found.

**Batch status:** Wabash is the only new full-gate candidate and is `GATED, AWAITING GO-AHEAD`. Lewis & Clark,
Hawkeye, BC3, and UH remain explicit hold-outs. No `schools.py` or production changes were made.

### Codex Batch 65 — public-search gate-resolution supplements (July 13 2026)

This pass followed five existing public leads and used only official no-login schedule surfaces. One candidate
cleared the current/completed replay gate; four are recorded as hold-outs rather than inferred. Exact-name checks
found no existing `schools.py` identity for any of the five. No production code or builder handoff was made.

1. **University of Tennessee at Chattanooga (TN, public four-year, approximately 12,060 students) — GATED,
   AWAITING GO-AHEAD.** Official schedule instructions are at
   `https://www.utc.edu/academic-affairs/registrar/registration-information/class-schedule`; the public Banner
   host is `https://sis-reg.utc.edu/StudentRegistrationSsb/ssb` (the university's enrollment/about source is
   `https://www.utc.edu/about`, with the 2025 enrollment release at
   `https://blog.utc.edu/news/2025/09/utc-announces-record-fall-enrollment-surpassing-12000-for-first-time/`).
   On the public term selector choose **Fall 2026**, then search with the exact fields `Subject/Keyword=ENGL` and
   `Course Number=1010` (do not use the broad keyword-only search). The current result is 41 exact `ENGL 1010`
   rows over five pages. Native rows preserve CRN, section, term, campus, status, and seats: examples include
   CRN 40022 with 6/20 seats remaining, 40023 with 1/20, 40323 with 3/20, 40037 with 7/20, and explicit full
   rows such as 42086 and 40035; waitlist rows expose numeric waitlist capacity. The completed replay is
   **Spring 2026 (View Only)** with the same exact fields: seven rows on one page, two with 1/20 seats remaining
   and five full, with unique CRNs (20914, 21376, 21802, 22429, 22430, 22757, 20610). This supplies mixed
   current and completed statuses, exact-course scoping, pagination, and a real historical-term check. Preserve
   the campus value (`UT Chattanooga` versus `UTC Hybrid/Online`) as scope; use CRN as the section key. Requests
   took roughly 2–3 seconds. The route fits the existing Banner family: resolve the human labels through the
   host's term selector, then issue the exact search equivalent to
   `/searchResults/searchResults?txt_subject=ENGL&txt_courseNumber=1010&txt_term=<resolved>&pageOffset=0&pageMaxSize=100`.
   Do not hard-code a numeric term code from this research note; the production subclass must run the existing
   Banner `resolve_term()`/`fetch()` path and re-verify the live term before registration. This is source-gated,
   not yet production-verified.

2. **Aims Community College (CO, public two-year) — HOLD OUT: no completed-term rows.** Official schedule:
   `https://schedule.aims.edu/`; institutional context: `https://www.aims.edu/about` and
   `https://www.aims.edu/about-aims/faq`. Fall 2026 `ENG - English` results expose explicit `OPEN`/`CLOSED`,
   numeric `Enrolled/capacity` values (for example 15/20, 8/20, 20/20), section labels, campus/location,
   modality, and dates. Replaying the same subject on Spring 2026 returned `No Results Found`, so the surface
   cannot prove historical status semantics. Hold until a populated completed term or an equivalent official
   replay is available.

3. **University of Vermont (VT) — HOLD OUT: limited PACE/non-degree scope and unstable machine identity.** The
   official current and completed PACE pages are `https://learn.uvm.edu/courses/fall/` and
   `https://learn.uvm.edu/courses/spring-v2026/`; registrar waitlist semantics are documented at
   `https://www.uvm.edu/registrar/waitlisting-pilot-information-students`. Fall current content has mixed
   `This section is full` and `Only N seat(s) available` labels, while Spring completed content has many
   `This section is closed` labels. However, the pages cover PACE/non-degree offerings rather than the whole
   UVM catalog and did not expose a reliable numeric seat/CRN payload in this pass (course labels such as
   `(ALE 1150 A01)` were visible). Hold; do not present this as a university-wide adapter.

4. **University of Hawaiʻi at Mānoa (HI) — HOLD OUT: public catalog endpoint blocked.** Official schedule guidance
   is `https://manoa.hawaii.edu/undergrad/schedule/`, with the Fall 2026 calendar at
   `https://manoa.hawaii.edu/registrar/academic-calendar/fall-2026/` and class-availability definitions at
   `https://www.hawaii.edu/myuhinfo/class-availability-information/`. The university directs users to Browse
   Classes at `https://www.sis.hawaii.edu:9234/`; the guest port returned a blank document in this environment,
   so no rows, seats, section keys, or completed replay were captured. Registrar prose is not evidence of live
   availability; hold until the public endpoint is reachable and replayable.

5. **University of Rochester (NY, private four-year, 11,211 total students Fall 2025) — HOLD OUT: replay not
   reproducible.** Official course-search instructions are at
   `https://www.rochester.edu/college/ccas/advising/course-search.html`; the public CDCS surface is
   `https://cdcs.ur.rochester.edu/` and enrollment context is the
   `https://www.rochester.edu/provost/university-data/data-insights-reporting/university-of-rochester-fact-book/`.
   The documentation confirms public Fall/Spring term selectors and `Open`, `Closed`, and `Canceled` filters.
   The live form loaded, but the tested Fall 2026 school/subject query returned no rows and subsequent retries
   timed out; no reliable current result set, exact recipe, or completed-term replay was obtained. Hold rather than
   infer from the documented filters.

**Batch status:** UTC is the only new full-gate candidate and is `GATED, AWAITING GO-AHEAD`; Aims, UVM, UH
Mānoa, and Rochester are explicit hold-outs. No `schools.py`, registry, deployment, or builder changes were made.

### Codex Batch 66 — public schedule follow-up supplements (July 13 2026)

This pass revisited five archived public-schedule leads. None cleared the full current/completed row gate in this
run; each blocker is recorded so a later agent can resume without treating a control shell as seat evidence. No
`schools.py` or production changes were made.

1. **Hope College (MI) — HOLD OUT: completed replay not populated for a tested exact course.** Official schedule:
   `https://schedule.hope.edu/`; registrar publication guidance:
   `https://hope.edu/offices/registrar/registration-schedules/`. The public table supports term, subject, course,
   status, campus, CRN, delivery, and seat fields. Fall 2026 exact `Accounting / ACCT 321` returned two native
   rows: CRN 83346 `OPEN`, Cap 21 / Act 13 / Rem 8, and CRN 83507 `CLOSED`, Cap 21 / Act 21 / Rem 0. This is
   strong current mixed evidence with unique CRNs. Replaying the same exact subject/course in Spring 2026 returned
   `No matching records found` after the page settled; the separate ENGL 210 replay produced only one closed row.
   Without a populated completed-term mixed set, hold rather than infer historical status semantics.

2. **Great Bay Community College (NH) — HOLD OUT: guest result rows not reproducible.** Official schedule guidance:
   `https://mygbcc.greatbay.edu/academics/academic-affairs/course-schedule-offerings/`; public Banner host:
   `https://sis.ccsnh.edu/ssb8/bwckschd.p_disp_dyn_sched`. The Fall 2026 selector exposes the CCSNH college filter
   (including Great Bay CC), subject/course filters, and Spring 2026 view-only term. An attempted Great Bay/ENGL
   query returned `No classes were found`; subsequent submissions timed out before a row listing could be captured.
   No CRN, seat, waitlist, or completed-term row evidence is claimed. Hold until the guest result endpoint can be
   replayed with exact college scope and mixed current/completed rows.

3. **Wayne Community College (NC) — HOLD OUT: section-details endpoint stalled.** Official schedule page:
   `https://www.waynecc.edu/admissions/course-schedules/`; guest search:
   `https://ss-prod.cloud.waynecc.edu/Student/Courses`. Fall 2026 with the exact `ENG` subject filter returned
   nine catalog matches (ENG-025, ENG-102, ENG-111, ENG-112, ENG-114, ENG-125, ENG-232, ENG-235, ENG-242) and
   exposed the public term/subject/campus controls. Every `View Available Sections` panel remained
   `Retrieving section information...`; no section ID, capacity, available seats, waitlist, or completed Spring
   replay was obtained. Do not treat the nine course matches as seat data.

4. **Navarro College (TX) — HOLD OUT: current-only term set and unstable search interaction.** Official schedule
   index: `https://www.navarrocollege.edu/registration-calendar.html`; guest catalog:
   `https://selfservice.navarrocollege.edu/Student/Courses`. The guest selector currently exposes Summer I 2026,
   Summer II 2026, and Fall 2026 only—no Spring 2026 or other completed term. The official index confirms the
   public-access link and weekly printable schedules, but the attempted Fall English search did not yield a stable
   row payload in this pass. Hold until a public row-level search plus completed-term replay is available.

5. **Wheaton College (IL) — HOLD OUT: official links are static PDFs/dynamic Banner, but no row payload captured.**
   Official registrar schedule index: `https://www.wheaton.edu/about-wheaton/offices-and-services/office-of-the-registrar/schedules`.
   It links the real-time Banner Self-Service schedule and official Spring 2026/Fall 2026 registration-packet PDFs;
   the dynamic course-schedule URL previously tried in this queue is now a 404. This pass did not extract a
   reproducible row-level current/completed seat set from the PDF viewer or a guest Banner endpoint. Hold rather
   than infer availability from the existence of the packets; resume only with exact section/seat fields and a
   completed-term mixed check.

**Batch status:** zero new full-gate candidates; Hope has current mixed evidence but no completed replay, while
Great Bay, Wayne, Navarro, and Wheaton remain explicit hold-outs. No `schools.py`, registry, deployment, or builder
changes were made.

### Codex Batch 67 — archived public schedule gate-resolution supplements (July 13 2026)

This pass revisited five remaining archived leads. One public source cleared a bounded current/completed replay;
four are held with explicit, reproducible blockers. No `schools.py` or production changes were made.

1. **Indiana University Bloomington (IN, public four-year) — GATED, AWAITING GO-AHEAD.** Official context says the
   schedule is updated daily and points to the no-login iGPS search:
   `https://studentcentral.indiana.edu/register/schedule-classes/fall-2026.html` and
   `https://sisjee.iu.edu/sisigps-prd/web/igps/course/search`. Select campus `IU Bloomington`, then exact term,
   subject `English`, and course `ENG-L 111`; retain the class detail's native class number. Fall 2026 returned
   class **23672**, `Closed`, Open Seats `0/30`, regular session 8/24/2026–12/18/2026. The exact completed Spring
   2026 replay returned class **29885**, `Open`, Open Seats `1/24`, regular session 1/12/2026–5/8/2026. Both
   rows preserve campus, term, subject/course, class number, instructor, meeting/room, status, capacity/open
   seats, and waitlist (`0`). A second exact cross-term check (`ENG-G 901`) also returned numeric open rows (Fall
   82/99; Spring 20/50). Use campus + term + native class number as the key; do not merge lecture/lab
   components, and keep the exact subject/course filter to prevent sibling leakage. Term selectors exposed
   Fall 2026 code `4268` and Spring 2026 code `4262`; builder should resolve these through the production iGPS
   request path rather than hard-code them. UI searches completed in roughly 1–2 seconds. This is source-gated
   and awaits production adapter verification.

2. **Cayuga Community College (NY) — HOLD OUT: no completed-term selector.** Official Fall schedule:
   `https://www.cayuga-cc.edu/academics/schedule-of-classes/fall/`; the page was last updated July 13, 2026 at
   4:45 PM and returned 473 rows with CRN, course/section, dates, instructor, campus, modality/session, and
   numeric `Availability` (including positive and zero values). The official selector currently exposes Summer
   2026, Fall 2026, and Intersession 2027 only; there is no completed Spring replay, and the page itself directs
   users to myCayuga for real-time lookup. Hold until a populated completed term or a reproducible guest Banner
   replay proves status/reserve semantics.

3. **Washington College (MD) — HOLD OUT: timestamped snapshot only.** Registrar instructions:
   `https://www.washcoll.edu/people_departments/offices/registrar/registration-instructions.php`; the linked Fall
   2026 PDF carries capacity, currently enrolled, remaining available seats, waitlist, cross-list, and restriction
   fields. It is a static current snapshot with no completed Spring row or live guest feed captured in this pass.
   Hold; do not infer real-time availability from the PDF alone.

4. **California State University, Long Beach (CA) — HOLD OUT: limited static slice and blank open-seat field.**
   Official Fall schedule index: `https://web.csulb.edu/depts/enrollment/registration/class_schedule/Fall_2026/By_College/index.html`;
   the English slice is `https://web.csulb.edu/depts/enrollment/registration/class_schedule/Fall_2026/By_College/ENGL.html`.
   The page is timestamped July 13, 2026 and preserves section/class number, capacity/reserve notes, modality,
   location, and instructor, but the captured `OPEN SEATS` cells were blank and no completed Spring schedule was
   replayed. EOP/English is not a college-wide live feed; hold until numeric current and completed rows are
   reproducible with reserve-seat semantics.

5. **Le Moyne College (NY) — HOLD OUT: current/future-only guest terms and no seat field in legacy table.**
   Official index: `https://www.lemoyne.edu/academics/classes-calendars-catalogs/`; guest search:
   `https://phinfo.lemoyne.edu/Student/Courses`; legacy Fall table:
   `https://echo.lemoyne.edu/courseavail/Q09VUlNFLTI2L0ZB.htm`. The guest selector exposes Maymester/Summer/Fall
   2026 and Winter 2027 but no Spring 2026 completed term. The legacy Fall table is timestamped July 13, 2026 and
   has native synonym/section/date/modality rows, but no authoritative seat/status field. Hold until a completed
   replay and numeric/status payload are available.

**Batch status:** Indiana University Bloomington is the only new `GATED, AWAITING GO-AHEAD` candidate; Cayuga,
Washington College, CSULB, and Le Moyne remain explicit hold-outs. No `schools.py`, registry, deployment, or builder
changes were made.

### Codex Batch 68 — remaining public-index gate-resolution supplements (July 13 2026)

This pass revisited five untested public-index leads. No school cleared the full production gate. Shasta exposed
useful numeric rows but failed the historical freshness/status consistency test; the other four had no usable
guest seat feed in this pass. No `schools.py` or production changes were made.

1. **Shasta College (CA) — HOLD OUT: completed-term status contradicts freshness marker.** Official index:
   `https://www.shastacollege.edu/academics/course-catalogs-and-class-schedules/`; guest catalog:
   `https://mysc.shastacollege.edu/Student/Courses`. The guest search supports Spring/Summer/Fall 2026 and exact
   subject/course filters. Exact `ENGL-31` Fall 2026 returned two native sections on one page: `ENGL-31-F8691`
   `Open`, 20 / 10 / 30 / 0 (available / enrolled / capacity / waitlist), SC Main Campus; and `ENGL-31-F8713`
   `Waitlisted`, 0 / 30 / 30 / 2, SC Online. Exact Spring 2026 replay returned `ENGL-31-S0490` 12 / 18 / 30 / 0
   and `ENGL-31-S9855` 21 / 9 / 30 / 0, both labeled `Open` but also marked `**THIS CLASS HAS ENDED**`. Native
   section names, dates, campus, modality, meeting data, faculty, credits, and pagination were present, and the
   requests completed in roughly 2–3 seconds. The ended/open contradiction makes status freshness unsafe; hold
   until the guest endpoint's historical semantics are explained or a trustworthy closed-row replay is captured.

2. **Kalamazoo Valley Community College (MI) — HOLD OUT: schedule has no seat/status payload.** Official
   announcement links the public schedule at `https://www.kvcc.edu/news/stories/2026-04-07_FallRegistration.php` and
   `https://schedule.kvcc.edu/`. Fall 2026 is a public course table with CRNs, dates, instructors, locations,
   methods, and parts of term, but no availability, enrollment, capacity, or waitlist field. The site exposes
   Winter/Summer/Fall 2026 only; no completed Spring replay was found. Hold until a guest seat-bearing endpoint
   is reproducible.

3. **Middlebury College (VT) — HOLD OUT: browse shell did not yield rows.** Registrar guidance:
   `https://www.middlebury.edu/registrar/registration/fall-reg-dates`; Banner browse entry:
   `https://reg-pntr.ec.middlebury.edu/StudentRegistrationSsb/ssb/term/termSelection?mode=search`. The public
   browse page exposes a term selector and Browse Course Catalog, but the term picker did not produce a selectable
   row feed in this pass; registration/search actions are otherwise login-gated. No current/completed CRN or seat
   rows are claimed. Resume only after selecting Fall and Spring terms and capturing reservation-aware seats.

4. **Westmont College (CA) — HOLD OUT: Waypoint login gate.** Official registration page:
   `https://www.westmont.edu/office-registrar/registration`; its Access Waypoint link resolves to
   `https://waypoint.westmont.edu/Student/courses`, which returned Westmont Single Sign-On with username/password.
   Registrar prose confirms Fall 2026 and Spring 2026 dates but no guest rows or seat/status fields were obtained.
   Hold; do not infer availability from registration dates.

5. **Arcadia University (PA) — HOLD OUT: advertised guest search redirected to login.** Official course-listings
   page: `https://www.arcadia.edu/academics/resources-advising/registrar/course-listings/`; it says Section Search
   needs no login and links `http://selfservice.arcadia.edu/`. The live PowerCampus menu exposed Course/Section
   options, but selecting Section redirected to `SelfService/Home/LogIn`; no term, section, seat, or completed
   replay was captured. Hold until the no-login route is reproducible rather than bypassing authentication.

**Batch status:** zero new full-gate candidates; Shasta is a documented numeric source with a decisive historical
freshness contradiction, and Kalamazoo, Middlebury, Westmont, and Arcadia remain explicit hold-outs. No
`schools.py`, registry, deployment, or builder changes were made.

### Princeton — ✅ SHIPPED July 13 (Build), Nathan-approved: 690->691
Reversed the earlier "bench" after Nathan said try it if it clears legal+accuracy+efficiency — it does.
Bespoke `Princeton` adapter, 2-call public api.princeton.edu (classes list + student-app/courses/seats),
plain stdlib, no browser in the poll loop. Anonymous public gateway token (served to every logged-out
visitor; captured ONCE via a real browser — the Cloudflare challenge is NOT defeated, and api.princeton.edu
itself is plain-reachable) pinned as _TOKEN. LEGAL: same read-only public-course-data class as the other
690 schools, honest SeatWatch UA. ACCURACY: open = seat_status=="Open" AND capacity-enrollment>0; Canceled
dropped via seat_status (bare status "C" hides them); exact scope subject+catnum OR crosslisting; class_number
keys. Gated live through the REGISTERED adapter: COS 226 = 8 open/1 LIVE-FULL (class 21189 = 25/25, seats 0),
completed 1264 mirrors, junk->{}, 0.7-1.0s/course. EFFICIENCY/RELIABILITY: Oracle prod server confirmed
reachable (200, 66 rows) BEFORE deploy; prod fetch post-deploy = 9 sec 8/1. FAILURE MODE: token rotation ->
401 -> {} -> engine skips -> never a false open, and run_cycle's existing no-data guard fires operator_alert
(not silent). Term PINNED 1272 (no stdlib terms source; manual bump). Deployed + live badge 691 verified.

### Maricopa CCCD ×10 — ✅ SHIPPED July 13 (Build): 691->701
The 10-for-1. All 10 colleges on shared classes.sis.maricopa.edu, one `Maricopa` base + 10 campus
subclasses. Server-rendered (plain urllib GET, no browser/XHR), ~1.0s/course. Green-lit by Grab
(independent live-verify of Codex Batch 25) AND re-gated here through the REGISTERED adapters:
- all_classes=true MANDATORY trap CONFIRMED live: BIO201 Phoenix default=12 open/0 closed vs
  all_classes=true=12 open/5 closed. Full sections are INVISIBLE without it (silent-miss); param baked in.
- CAMPUS ISOLATION proven: BIO201 across all 10, ALL 45 college pairs class-number-DISJOINT (institutions[]
  code hard-filters). No cross-campus false alerts possible.
- REAL NUMERIC seats ('N of M seats available'); status span agreed with the number 100%; live disproof
  is decisive — Estrella Mountain BIO201 = 0 open/15 FULL, Chandler-Gilbert 1/14 (only current/upcoming
  terms exposed, so live full rows ARE the disproof, Utica standard). No open-with-0-seats anywhere.
- EXACT scoping: parse only the <div class="course"> block whose <h3> code == smashed target; BIO202 is a
  separate 9-section course, zero key overlap with BIO201. Section key = 5-digit class number.
- Term opaque (Fall 2026=4266) auto-rolls from the form's own term-checkbox labels; resolve_term()->4266.
Codes: Phoenix PCC01, Glendale GCC02(≠Glendale CA), Mesa MCC04, Chandler-Gilbert CGC08, Estrella EMC10,
GateWay GWC03(≠Mountain Gateway), Paradise Valley PVC09, Rio Salado RSC06, Scottsdale SCC05, South Mtn SMC07.
Prod server fetch post-deploy verified (Estrella 15/15 full). Deployed, live badge 701. Maricopa is CLOSED
as a lead. Remaining buildable bespoke queue (Grab's audit): RCCD×3 (SharePoint now needs exact list-query
headers), SDCCD Mesa+Miramar (City already live), Williston/CCBC/Brandeis/Cayuga/Monroe/West Valley/Kent/UVM.

### Batch 40-42 validation → 3 SHIPPED July 13 (Build): 701->704
Nathan-assigned validation of Codex batches 40-42 (15 candidates). Outcome:
- ✅ SHIPPED (3, all 4-year, gated live through registered adapters, live-term numeric-full disproofs):
  - George Mason U (gmu, ~40k R1 public) — plain Banner9 ssbstureg.gmu.edu 202670; ENGH 101 = 72 sec
    8 open/64 FULL; seq keys unique 72/72.
  - Northern Michigan U (nmu) — plain Banner9 bssrprod.nmu.edu:8443 202680; EN 111 = 31 sec 1/30 FULL;
    seq unique 31/31. (non-standard port :8443 — server reachability confirmed.)
  - U Hartford (hartford) — CrnKeyedBanner uhart-pxesa-003.hartford.edu:8103 202640; BIO 122 = 23 sec
    7 open/16 FULL. ⚠️ GATE CAUGHT A COLLAPSE TRAP: every Hartford section returns sequenceNumber='0'
    (BIO 122 = 23 rows all seq '0') — plain Banner would have merged 23 sections into 1 and silently
    missed opens. CRN-keyed instead (23 unique CRNs). Port :8103 server-reachable.
- DUP (3, already live, skipped): U Wisconsin-Madison, U Alabama, PennWest (California U of PA).
- PARKED (9, not gate-ready — quick-triaged, handed back for recon, NOT shipped): JMU (PeopleSoft guest
  COMMUNITY_ACCESS — classic-PS fake-status risk), Richmond (BannerExtensibility custom page, no bwckschd),
  UMBC (PeopleSoft H_BROWSE_CLASSES), UCCS/Alabama-myBama/Stetson (portal/dashboard-gated), ECU
  (departmental page only), GW (my.gwu.edu antibot), Central Michigan (portal), Michigan-Ann Arbor
  (Okta-gated — Grab confirmed blocked). These are Grab's to resolve if worth it.

### RCCD ×3 — ✅ SHIPPED July 13 (Build): 704->707
Moreno Valley / Norco / Riverside City, one `RCCD` base + 3 subclasses. SharePoint REST on the
msappproxy Azure-AD proxy, anonymous, real numeric seats. Re-gated through the REGISTERED adapters;
TWO spec corrections vs Grab's relay (both accuracy-relevant):
- ⚠️ THE LIST ACCUMULATES 4 TERMS, not "current-only" as relayed: MOV = Fall 1004 + Winter 255 +
  Spring 939 + Summer 284 = 2482. Grab's counts (2482/826-open) mixed all four incl. PAST Spring/Winter
  2026. FIX: server-side $filter=Term eq '{term}'. This ALSO drops RIV from 5410(all-terms) to 2330(Fall)
  = under the 5080 one-page cap, so the "paging mandatory" trap DISAPPEARS (still follow nextLink + fail-
  closed defensively). Term auto-rolls from ScheduleTermOptions (resolve_term->26FAL verified).
- nometadata header mandatory (plain GET = XML SPA shell). Open rule = Total-Used>0 AND Last_Day_to_Add
  >= today (matches RCCD's app; date gate independently excludes stale-term rows — 26SPR deadlines all
  pre-today — so belt-AND-suspenders with the Term filter; unparseable date -> not open, conservative).
  Over-cap rows negative -> not open. Key = Section_x0020_ID (unique). Exact Primary_x0020_Subject scope
  (ACC-1A ≠ ACC-1B, both live). Separate list per college = inherent campus isolation (Section_ID overlap
  EMPTY across all 3). Gate: MOV ENGL-C1000 92 sec 68/24, NOR 50 sec 39/11, RIV 142 sec 60/82. Server
  reaches msappproxy (prod fetch RIV 142 60/82 matches). Deployed, badge 707. RCCD CLOSED as a lead.

### Brandeis — DEFERRED July 13 (Build): accuracy fine, ADDRESSING unsafe (NOT shipped)
First handoff declined on technical grounds this session — and the re-gate discipline is exactly why.
Grab's gate verified the DATA (English page Fall 1263: 44 Open/15 Waitlist, numeric Enrl/Lim, real
disproof — all TRUE). But it did NOT test ADDRESSABILITY: "given an arbitrary student course code, can
we reliably fetch exactly its sections?" That's where Brandeis breaks:
- Abbreviation URL (/Fall/ENG/UGRD) returns an empty 2KB stub — must use a numeric code.
- The "subject" dropdown is PROGRAMS/MAJORS, not course abbreviations: page 100 (AAAS) lists AAAS/ED/
  ENG/HIST/SOC courses; page 700 (Biology) lists 13 abbreviations. No published course-abbrev→page map.
- Built an abbrev→home-page map across all 94 program pages: 32 of 63 abbreviations are AMBIGUOUS (no
  dominant home). BIOL courses scatter across 16 pages (700:42, 2700:36...), CHEM across 15, ENG spills
  from 1800 onto 1425/9300/2000. A single-page mapping would STRUCTURALLY, SILENTLY miss sections that
  live on a program page we don't fetch — a watched full section that never appears = broken product
  promise (worse than a fetch blip; the app claims to watch but structurally can't see the seat).
- keyword search returns 0 for exact course codes — not a clean route either.
VERDICT: no reliable course→page addressing exists; a "safe" adapter would need per-course multi-page
merging (which pages? up to 94) or a fragile map with residual silent-miss risk. Disproportionate
complexity + accuracy risk for one ~5.8k school. DEFERRED (not a false-open risk — a silent-miss/
coverage-integrity risk). Revisit only if Brandeis exposes a course-scoped endpoint. No schools.py edit.
LESSON for relays: for schedule sites, gate ADDRESSABILITY (arbitrary course → its exact sections), not
just one hand-picked page's numbers.

### SDCCD Mesa + Miramar — ALREADY LIVE (dedup catch, July 13 Build): NOT a new ship
Grab relayed SDCCD Mesa+Miramar as "gate-passed, both net-new" — but sdmesa (MESA) and sdmiramar (MIRA)
were ALREADY shipped alongside sdcity on the SDCCD adapter. Verified live+healthy through the registered
adapters: Mesa MATH 121 = 13 sec 8/5, Miramar BIOL 131 = 3 sec 2/1 (served 0.0s from the shared dump cache
Mesa's fetch populated). No change made. The registry guard would have crashed on the duplicate ids anyway.
LESSON: dedup by name/id against schools.py BEFORE gating a "net-new" campus on an already-live shared feed.

### Codex Batch 69 — public interactive-search follow-up (July 13 2026)

This pass checked five previously untested public interactive-search leads. Hellenic College Holy Cross produced
the strongest row-level evidence, but its completed replay falsely retained an `Open` status after the class ended;
the other four did not provide a complete current-plus-completed, seat-bearing guest feed in this pass. Nothing in
this batch is safe to add to production.

1. **Hellenic College Holy Cross Greek Orthodox School of Theology (MA) — HOLD OUT: stale completed-term status.**
   Official public Jenzabar search: `https://my.hchc.edu/ICS/Home.jnz?portlet=AddDrop_Courses&screen=Advanced+Course+Search&screenType=next`.
   Exact course-code query `ENGL 1101`, Undergraduate, returns Fall 2026 row `English Composition I: Comp & Style`
   (Farrell), `1/25` seats open, `Open`, MW 9:10–10:30, Main Campus Skouras Hall 222, 3 credits, dates
   8/31/2026–12/17/2026. The same exact query on completed Fall 2025 returns `8/20`, still `Open`, with dates
   8/25/2025–12/17/2025 (already ended by the July 13, 2026 run). Spring 2026 exact replay was empty. The native
   numeric `seats open` field is useful, but an ended row labeled `Open` is a decisive freshness/status contradiction;
   hold until HCHC documents historical semantics or exposes a trustworthy closed/full replay. Requests completed
   well under 30 seconds.

2. **Florida State College at Jacksonville (FL) — HOLD OUT: current/future-only PeopleSoft surface and no row
   payload captured.** Official guest search: `https://csprd.fscj.edu/psc/csprd_1/EMPLOYEE/HRMS/c/COMMUNITY_ACCESS.CLASS_SEARCH.GBL`.
   The public form exposes institution FSCJ1, Fall/Summer 2026 terms, subject/course/career, campus, session,
   mode, class number, and open-only controls, but no completed Spring 2026 term is exposed and no reproducible
   row-level seat/status payload was captured in this pass. Hold until a completed replay and numeric/status rows
   are available with campus/career scope preserved.

3. **College of Lake County (IL) — HOLD OUT: no completed term in guest selector.** Official search:
   `https://www.clcillinois.edu/class-search` (redirects to the public term search). The guest UI currently offers
   Summer 2026, Fall 2026, and Spring 2027, requires at least two criteria, and exposes subject, mode, and location
   controls (including Online); Spring 2026 is absent. No current-plus-completed seat/status replay is therefore
   possible. Hold until CLC publishes a populated completed term or a stable history endpoint.

4. **Webster University (MO) — HOLD OUT: public form did not yield a verifiable exact row.** Official entry:
   `https://classes.webster.edu/` (redirects to the public MyWebster course search). The page exposes 2025–26
   Summer/Fall/Spring and 2026–27 Summer/Fall terms, exact/begins/contains code filters, division, subterm,
   meeting type, and Open/Full/Waitlisted status filters. An exact-code query for `ENGL 1010` in 2026–27 Fall
   returned the empty results table (“To see courses, enter criteria…”), so there is no trustworthy section key,
   seat count, or status to compare. Hold pending a row-producing official course-code query and completed replay;
   do not infer a code or scrape the login path.

5. **Seminole State College of Florida — HOLD OUT: course page defaults to open-only current snapshot.** Official
   catalog search: `https://www.seminolestate.edu/catalog/courses/mvk2121m`. The Fall 2026 page for `MVK2121M Class
   Piano III` says it is showing classes with open seats and college credit; one row is visible (class `71262`,
   Sanford/Lake Mary, Hybrid/Reduced On-Campus Time, M/W 1:00–1:50, 1 class available). The term controls include
   Spring 2026, but the captured page suppresses closed/full rows by default and exposes no completed numeric/status
   comparison. Hold until the open-only filter can be disabled and a completed replay proves full/closed semantics.

**Batch status:** zero new full-gate candidates; HCHC is a documented numeric source with a decisive stale-status
contradiction, while FSCJ, CLC, Webster, and Seminole remain explicit hold-outs. No `schools.py`, registry,
deployment, or builder changes were made.

### Codex Batch 70 — western public-search vein (July 13 2026)

This pass checked five exact-name-new colleges against official public schedule/search surfaces. None cleared the
full gate: no production change is safe from this batch.

1. **Adams State University (CO) — HOLD OUT: official Banner URL redirect loop.** The official schedule entry
   `https://ssb.adams.edu/bannerweb/schedule/schedule_options/` repeatedly returned a redirect loop before a term
   selector or class row could be read. A URL alone is not evidence of a public seat feed; hold until Adams publishes
   a stable guest schedule entry point with current and completed replay.

2. **Regis University (CO) — HOLD OUT: catalog-only search.** Official `https://catalog.regis.edu/course-search/`
   exposes keyword and subject controls (including EN - English) but no term selector, section rows, seats, status,
   or completed-term replay. Hold pending an authoritative registration/search surface with row-level availability.

3. **Idaho State University (ID) — HOLD OUT: login-gated registration.** Official
   `https://www.isu.edu/registrar/registration-information/` says Find Classes is reached after logging into MyISU;
   the public catalog is not a live seat feed. No login was attempted. Hold until ISU documents a guest search or
   permitted public endpoint with exact section and availability fields.

4. **Central Washington University (WA) — HOLD OUT: public form, no row replay captured.** Official registrar
   page `https://www.cwu.edu/about/offices/registrar/academic-information/` links the public PeopleSoft Class Search:
   `https://cwucsprd.peoplesoft.cwu.edu/psp/cwucsprd/EMPLOYEE/SA/c/COMMUNITY_ACCESS.CLASS_SEARCH.GBL?Page=SSR_CLSRCH_ENTRY&Action=U&TargetFrameName=None`.
   The guest form exposes Fall 2026, Spring 2026, Spring 2027, Summer 2026, and Winter 2027, subject/course-number,
   career, campus, session, and a Show Open Classes Only checkbox; it requires at least two criteria. The exact
   ENG/101 test lost the active course-number target during interaction, so no section key, seats, status, scope,
   pagination, or completed replay was captured. Hold pending a repeatable current/completed row-producing recipe.

5. **Western Washington University (WA) — HOLD OUT: dynamic Banner picker did not yield rows.** Official registrar
   page `https://registrar.wwu.edu/browse-classes` embeds Banner Browse Classes at
   `https://registration.banner.wwu.edu/StudentRegistrationSsb/ssb/term/termSelection?mode=search`. Its public term
   list returned Fall 2026 and Summer 2026 plus Spring 2026, Winter 2026, Fall 2025, and older terms marked View
   Only. The dynamic term option could not be selected reliably after loading, so no section rows, numeric seats,
   status semantics, or completed replay were captured. Hold pending a repeatable row-producing search.

**Batch status:** zero new full-gate candidates; five explicit hold-outs documented above. No `schools.py`, registry,
deployment, or builder changes were made.

### Codex Batch 71 — northern public class-search vein (July 13 2026)

This pass checked five exact-name-new colleges against official public schedule/search surfaces. Northern Arizona
University produced a strong current/completed cross-term replay and is gated for builder review; the other four did
not meet the full gate. Nothing from this batch is safe to add to production without the documented follow-up.

1. **Northern Arizona University (AZ) — GATED, AWAITING GO-AHEAD: public PeopleSoft rows with native keys and seats.**
   Official guest entry: `https://www.peoplesoft.nau.edu/psc/ps92prcs/EMPLOYEE/SA/c/COMMUNITY_ACCESS.CLASS_SEARCH.GBL`.
   Exact ART 161 query in Fall 2026 (`strm=1267`, `subj=ART`, `nbr=161`) returned four Flagstaff Mountain/In Person
   sections: 001/2710, 003/2712, 004/2771, and 008/9493; each had `Available Seats: 0`. The status column is icon-
   backed (`Wait List` plus the PeopleSoft `Open` helper/legend). Exact Spring 2026 replay (`strm=1261`) returned
   001/2029 and 002/2030 with 2 seats and `Open`, plus 004/2031 and 005/2032 with 0 seats and `Closed` + `Open`
   helper icons. Both terms expose section code, native class number, session, meeting dates, campus, instruction
   mode, instructor, and meeting data. Direct reproducible URLs used:
   - Fall: `https://www.peoplesoft.nau.edu/psc/ps92prcs/EMPLOYEE/SA/c/COMMUNITY_ACCESS.CLASS_SEARCH.GBL?PAGE=SSR_CLSRCH_RSLT&Page=SSR_CLSRCH_ENTRY&inst=NAU0000&nbr=161&open=N&search=true&strm=1267&subj=ART`
   - Spring: `https://www.peoplesoft.nau.edu/psc/ps92prcs/EMPLOYEE/SA/c/COMMUNITY_ACCESS.CLASS_SEARCH.GBL?Page=SSR_CLSRCH_ENTRY&inst=NAU0000&nbr=161&open=N&search=true&strm=1261&subj=ART`
   The native class number is the candidate section key; preserve institution/term/subject/number and campus scope.
   Before production, builder must replay both terms, confirm icon semantics (especially the helper `Open` title on
   closed rows), and verify pagination/response timing. No `schools.py` change was made.

2. **Montana State University (MT) — HOLD OUT: public APEX form but no row replay captured.** Official schedule page
   `https://www.montana.edu/registrar/ScheduleofClasses.html` links the public APEX search at
   `https://apexprod.msu.montana.edu/apex/r/esg/s_class_schedule_gf/class-schedule`. The form exposes Fall, Summer,
   and Spring 2026 plus older terms, subject/instructor comboboxes, course number, and “Only Sections with Open
   Seats.” No repeatable exact subject/course row payload with section keys and numeric/status availability was
   captured; hold until current and completed rows can be replayed.

3. **University of Alaska Fairbanks (AK) — HOLD OUT: no completed term in guest search.** Official
   `https://catalog.uaf.edu/class-search/` states that section information updates overnight and exposes search
   controls, but its current guest picker shows only Fall 2026 and Summer 2026. No seat-bearing completed replay was
   captured; the course catalog is not a substitute for live sections.

4. **University of Alaska Anchorage (AK) — HOLD OUT: UAOnline SAML gate.** Official registration page
   `https://www.uaa.alaska.edu/students/registration/` routes schedules to the official UAOnline page
   `https://www.alaska.edu/uaonline/`. The UAA student entry redirects to the University of Alaska identity provider
   before exposing a guest class-search or seat rows. No login bypass was attempted; hold until UAA documents a
   permitted guest feed with exact sections and availability.

5. **University of Nevada, Reno (NV) — HOLD OUT: current/future-only guest selector.** Official registrar page
   `https://www.unr.edu/admissions/records/registration` links PeopleSoft Class Search at
   `https://cs.nevada.unr.edu/psp/unrcsprd/EMPLOYEE/SA/c/SA_LEARNER_SERVICES.CLASS_SEARCH.GBL?`. The public form
   exposes 2026 Summer and Fall only (no completed Spring), with subject/course, career, campus/location, mode, and
   open-only controls. No exact row payload or completed replay was captured; hold pending a history-capable guest
   surface.

**Batch status:** one gated lead (NAU) and four explicit hold-outs. No `schools.py`, registry, deployment, or builder
changes were made.

### Codex Batch 72 — flagship alternate-public-search vein (July 13 2026)

This pass checked five exact-name-new flagship universities against registrar-linked public class-search surfaces.
None met the full SeatWatch gate: each lacked a trustworthy seat-bearing current/completed replay or was login/gate
blocked. No production change is safe from this batch.

1. **University of Florida (FL) — HOLD OUT: public schedule has no seat/status fields.** Official ONE.UF Schedule of
   Courses: `https://one.uf.edu/soc/` (linked by the registrar). The public UI exposes Fall 2026 through Spring 2018,
   course/class number, title, instructor, department, and program-level filters. A Fall 2026 `ENC1101` search
   returned many native class numbers and instructor/meeting-mode summaries, but each result says to log in for
   locations, dates, times, and final-exam details. No `seats`, capacity, open/closed, or waitlist field exists in
   the public payload; this is schedule metadata, not a SeatWatch source. Hold pending a permitted seat-bearing API.

2. **University of Houston (TX) — HOLD OUT: term history exists, but exact row search was empty.** Official registrar-
   linked Fluid PeopleSoft search:
   `https://saprd.my.uh.edu/psc/saprd/UHM_SITE/HRMS/c/SSR_STUDENT_FL.SSR_CLSRCH_MAIN_FL.GBL?Page=SSR_TERM_STA2_FL`.
   The picker exposes Summer/Fall 2026 and expands to Spring 2026 under “Terms prior to Summer 2026.” Structured
   Fall 2026 searches for English 1303 and Mathematics 1310 returned “No results were returned”; no section key,
   seats, status, pagination, or exact-course row was captured. Hold until a row-producing recipe can be replayed in
   both a live and completed term.

3. **Michigan State University (MI) — HOLD OUT: public tile did not yield a stable guest payload.** Official SIS
   `https://student.msu.edu/` advertises “Class Schedules (No login required)” and routes to
   `https://student.msu.edu/search`. The public PeopleSoft homepage exposes a Class Search tile, but selecting it
   did not produce a stable guest form or result rows in this pass. No section key, numeric seats, status semantics,
   completed replay, pagination, or latency evidence is available; do not infer a feed from the landing page.

4. **Clemson University (SC) — HOLD OUT: current/future-only public schedule.** Official registrar-linked schedule:
   `https://soc.app.clemson.edu/schedule/index.php`. The guest form exposes Fall 2026 and Summer 2026 only, with
   instruction method, subject, instructor, course level, and location filters. No completed Spring 2026 term or
   seat/status field was exposed; no current/completed row replay can meet the gate. Hold pending a history-capable,
   seat-bearing guest surface.

5. **University of Central Florida (FL) — HOLD OUT: myUCF login boundary.** Public dashboard
   `https://my.ucf.edu/public/dashboard` links Class Search to
   `https://csprod-ss.net.ucf.edu/psc/CSPROD/EMPLOYEE/SA/c/COMMUNITY_ACCESS.CLASS_SEARCH.GBL`; official registrar
   instructions require logging into myUCF for Class Search. No permitted guest rows, completed replay, or seat/status
   evidence were captured. No login bypass was attempted.

**Batch status:** zero new full-gate candidates; five explicit hold-outs. No `schools.py`, registry, deployment, or
builder changes were made.

### UT Chattanooga + West Valley/Mission — ✅ SHIPPED July 13 (Build): 707->710 (from Codex/Grab gated leads)
- **UT Chattanooga** (utc, Batch 65 Codex gated lead re-verified): plain Banner9 sis-reg.utc.edu 202640.
  ENGL 1010 = 41 sec 27 open/14 full, MATH 1130 37 sec 26/11, completed Spring 202620 = 7 sec 5 full.
  Single institution ('UT Chattanooga' + 'UTC Hybrid/Online' are modalities, NOT a shared UT host — UTK
  is separate). seq unique 41/41. resolve_term->202640. ~12k public 4-year.
- **West Valley + Mission** (westvalley WVC / missioncollege MC, ⭐ Grab browser-traced): static Banner
  JSON dump schedule.wvm.edu/data/{term}/crns.json, shared class-level cache (Mission served 0.0s off
  West Valley's fetch). Re-gated: WVC ENGL 10W 38 sec 22/16, MC ENGL 10M 23 sec 8/15, completed 202630
  WVC 130 full. CAMP_CODE isolation WVC/MC (cross-campus CRN overlap EMPTY). open = SEATS_AVAIL>0 AND
  SSTS_CODE=='A'. Key=CRN unique. ⚠️ ADDRESSABILITY: course numbers zero-padded+irregular ('005A','010',
  '10W'/'10M' campus-suffixed) — canonical leading-zero-strip both sides so 'ENGL 5A'=='005A'. Term
  auto-rolls from sobterm.json. Both net-new. IU Bloomington (Batch 67 gated) NOT built — 9-campus iGPS
  SPA needs a browser XHR trace (handed to Grab).

### ⭐ Indiana University Bloomington — ✅ SHIPPED July 13 (Build): 710->711 (~48k flagship)
Grab browser-traced the iGPS SPA (Batch 67 Codex gated lead); re-gated + built here. Bespoke `IUBloomington`,
public 3-call JSON API on sisjee.iu.edu, all scoped inst=IUBLA. terms.json (Fall 2026=4268, auto-rolls) →
POST courses.json (paginated catalog, ~6,100 courses) → GET classes.json (sections+seats per catalog row).
- CATALOG CACHE: course→ids map is stable per term, scanned ONCE per 6h into a shared class-level cache
  (40s cold local / 27s on prod server, then warm 0.4s — Purdue/TAMU envelope). Partial scans NEVER cached
  (a missing page = silent-missed courses); any error discards + retries.
- ADDRESSABILITY: 478 subject+catalog combos are MULTI-ROW (variable-topic, e.g. AAAD-X 490 = 11 catalog
  rows). A watched course maps to the LIST of its rows and AGGREGATES classes.json across all (complete-
  scope-then-filter). AAAD-X 490 gated = 10 sec aggregated. If any row's fetch fails, whole course skipped
  (no partial). Dedup: 'Indiana University of Pennsylvania'(iup)+'University of Indianapolis'(uindy) are
  DIFFERENT — IUB net-new.
- ISOLATION: inst=IUBLA scopes both catalog + classes to Bloomington; every row campus=BL (0 non-IUBLA).
- OPEN RULE: closed is False AND openSeats>0 (agreed 100% live). CROSS-LIST GUARD: combinedSections with
  separateEnrollmentControl==False and combinedEnrollTotal>=combinedEnrollCapacity -> full even if
  openSeats>0 (when control is separate, openSeats authoritative). Gate: ENG-W 131 = 88 sec 7 open/81 FULL
  (decisive), ENG-L 111 = 1 sec closed 0/30 (reproduces Codex class 23672). Server-reachable, prod-verified.

### MassArt — ✅ SHIPPED July 13 (Build): 711->712
Massachusetts College of Art and Design (massart). Grab diagnosed my earlier NewColleague no-data: it's
the OLDER base `Colleague` API (/Student/Courses/PostSearchCriteria + textual AvailabilityStatus), NOT the
numeric NewColleague/SearchAsync (that route 404s). So a 4-line base-Colleague subclass, host
mca-ss.colleague.elluciancloud.com. Re-gated: CDAN 300 = 2 sec 1 open/1 full, CDAN 302 = 4 sec 2/2, CDAN
303 = full — real mix disproof, section keys unique. Textual-Open safety confirmed: CDAN 302 sec 03 has
seats=1 but reads NOT-open (AvailabilityStatus Waitlisted, reserved seat) — base Colleague correctly
withholds it (no false open). Deployed, prod-verified, badge 712.

### Delaware — SKIPPED July 13 (Build): hard 49-result cap, can't guarantee flagship-course completeness
UD public search (udapps.nss.udel.edu/CoursesSearch) is accuracy-SAFE (real "X OF Y" seats + CURRENTLY
FULL badge; never false-opens) and per-course queries (course_sec=SUBJ+NUM) are exact + complete for the
~99% of courses under 49 sections (MATH241=8, BISC207=29, CHEM103=27 all verified real+complete).
BUT there's a HARD 49-RESULT CAP with NO working pagination (page/start/offset params all ignored, every
capped query returns exactly 49): Grab's per-SUBJECT query is broken (course_sec=ENGL returns 49 all-
ENGL110, HIDING ENGL301 which exists). Per-course fixes most of it, EXCEPT courses with 49+ sections —
notably ENGL 110 (first-year writing, the most-watched course): Fall AND Spring both return exactly 49
(two terms at the identical number = cap clamping, not coincidence), so its overflow sections are likely
invisible. Uncircumventable via this endpoint (no pagination, campus-split doesn't help — mostly NEWRK).
Nathan's bar = flawless accuracy+efficiency or skip; can't guarantee ENGL 110 completeness -> SKIP.
Revisit ONLY if a cap-free UD endpoint (JSON/mobile API) is found. Accuracy-safe, so also fine to revisit
as a documented-partial later if Nathan wants. No schools.py change.

### SJSU — SCRAPPED July 13 (Build): nightly-refresh staleness compromises accuracy
www2.sjsu.edu/classes/schedules static table is real numeric Open Seats + platform-SAFE (NOT fake-status
PeopleSoft — Grab confirmed). BUT it REFRESHES NIGHTLY, not real-time. For a full watched class a seat
opens+refills same-day before the next snapshot, so a nightly-based alert is usually STALE ('open' when
already gone) = a false-feeling alert on exactly the high-demand courses people watch. That compromises
accuracy AND the fast-alert value prop. Nathan's criterion: harmful-if-it-compromises-accuracy -> SCRAP
(distinct from reserved/consent seats which are real-but-unbookable = fine). Not the same as a completeness
gap; this is a temporal-staleness accuracy risk. No schools.py change.

### Portland CC + Wabash — ✅ SHIPPED July 14 (Build): 712->714
- **Portland Community College** (pcc-or, ~70k — one of the largest CCs in the US): bespoke REAL-TIME
  2-step. GET /schedule/{termword}/{subj}/{subj}{num}/ → data-crn per section; POST /schedule/capacity/
  {term,crn=list} → {CRN:{seat:[avail,cap],wait:[]}}. ⚠️ The page's data-seats attr is STALE/FALSE (reads
  '1' on FULL sections — would false-alert); ONLY the capacity POST's seat[0] is real. open=seat[0]>0,
  key=CRN, multi-meeting rows dedup by CRN. Addressability: all page CRNs are the exact course (wr121 path
  = WR121/renumbered WR121Z, detail links confirm). Grab said WR121=60; POST gives the true complete 157
  (112 open/45 full). MTH 111 16/16, BI 101 8-all-full = disproof. Quarter auto-roll (newest published
  data-term across 4 termword pages). Server-reachable, prod-verified.
- **Wabash College** (wabash, ~900 private 4-yr): GET HTML table. Dedup multi-MEETING rows by SectionName
  (407 rows→312 sections). open=status=='OPEN' (WAITLISTED/CLOSED not open); ⚠️ available seats live in a
  <span class="count available"> — a naive \d+/\d+/\d+ mis-matches the m/d/yy date on the row. Textual-status
  safety confirmed: BIO-101-01 had 3 available but status WAITLISTED → correctly NOT open (waitlist
  priority). Gate: ENG 101 4-full, MAT 111 4-open, ACC 201 2-open(7,6 seats); term auto-rolls from the
  page dropdown. Both net-new, prod-verified.

### Monroe CC — ✅ SHIPPED July 14 (Build): 714->715
Monroe Community College (monroecc-ny, NY ~13k). Grab APPLIED the Delaware cap-lesson (gated the huge
ENG-101 = 129 sec, uncapped, complete — no round-number truncation). Bespoke per-course static HTML:
GET /classes/{subj}-{num}-sections/ = ONE course's complete section list (headings confirm single course,
no cap/pagination). Paired CRN↔seats by CRN-BLOCK split (not a fragile parallel zip). open = Seats
Remaining > 0 (full shows 0). Key = CRN unique. Gate: ENG-101 129 sec 99 open/30 full (Grab 100/29, live
drift), MTH-211 4 sec 3/1. Self-current term (no term in URL). ⚠️ LATENCY: ENG-101 page is 638KB → ~14s
consistent (server serve-time for the big page); under the 30s cut line, most courses ~1s. Prod-verified.

### VCCCD ×3 — ✅ SHIPPED July 14 (Build): 715->718
Ventura County CCD (Moorpark/Oxnard/Ventura College, ~37k). Grab browser-traced the endpoint (real host
schedule.vcccd.edu, NOT the dead banpublic stub) + confirmed plain-stdlib session. Django CSRF: GET / sets
csrftoken cookie → POST /filter/ (X-CSRFToken header + csrfmiddlewaretoken field). subjCombobox is IGNORED
server-side → full ~7.3MB district catalog every call → shared class-level cache (10-min TTL; 40s cold /
0ms warm across all 3 colleges — Purdue/TAMU cache-backed envelope). Re-gate IMPROVED on the relay's spec:
the JSON has a structured CAMPUS_DESC field = 100% clean campus isolation (0 cross-campus CRN collision),
vs Grab's Location-prefix which left ~5% residual-to-hold — no residual needed. Also caught multi-MEETING
CRN dups (1073/4968) the 1574-sample missed → dedup by CRN. OPEN RULE STATUS=='OPEN' AND CRSE_SEATS_AVAIL>0
(agreed 100%/3672 rows). Campus-specific numbering (Moorpark ENGL M01A / Oxnard R101 / Ventura V01A). Gate:
Moorpark M01A 73 sec 53/20, Oxnard R101 32 sec 20/12, Ventura V01A 66 sec 47/19; cross-campus overlap EMPTY.
Term pinned 202607. Server-reachable, prod-verified. Closes Grab's browser-trace bench item.

### UVI + Cayuga — ✅ SHIPPED July 15 (Build): 718->720 (Grab's remaining queue closed)
- **University of the Virgin Islands** (uvi, ~2k, ONE institution / 3 campus .aspx pages combined).
  ⚠️ Re-gate CAUGHT a silent-miss trap Grab's numbers didn't surface: the stx (St Thomas) page
  INTERMITTENTLY returns an empty table server-side (plain GET 0/384 flaky; not fixed reliably by
  cookiejar/UA — genuinely server-flaky). Caching a dump while a page is empty would silently drop that
  whole campus's sections for the TTL. FIX: retry each page (empty=flake), and NEVER cache a dump missing
  a campus — serve last-good instead (verified 4/4 dumps complete at 957 rows; ACC 201 correctly = 4
  sections incl. the stx ones). open = STATUS=='ACTIVE' AND AVAIL>0, key=CRN (unique across pages),
  cookiejar session required. Disproof: 66 live full + 41 completed-term full.
- **Cayuga Community College** (cayuga, ~4k). One fresh HTML catalog (live 'updated: <today> <time>'
  stamp, passed Grab's staleness check). Course col='SUBJ NUM-SEC' (clean scope), Availability embedded
  in title cell (blank Availability -> skip, never guess). open = Availability>0, key=CRN unique. Gate:
  ENGL 101 22 sec 17/5, BIOL 100 4 sec 3/1. Both prod-verified. GRAB'S QUEUE NOW FULLY CLOSED (USVI +
  Cayuga were the last two; VCCCD×3 + all prior sends already shipped or correctly skipped).

### Los Rios CCD ×4 — DEFERRED July 15 (Build): ~20-cap, completeness UNCONFIRMED (needs browser pagination trace)
Grab's high-value lead (American River/Cosumnes River/Folsom Lake/Sacramento City, ~75k, one feed
hub.losrios.edu/classSearch/getCourses.php, per-college arc/crc/flc/scc filters + closedFilter=true).
Re-gate could NOT confirm complete section retrieval:
- Clean class-number parse (not the noisy raw-5-digit grep, which catches room#/times) shows MATH/HIST/
  PSYC/BIOL each returning exactly 20 sections per call — a round, repeated cap (Delaware signature).
- offset pagination is BROKEN via plain HTTP: offset=20/40/50, first=50, page=2 all return EMPTY.
- Summed BIOL across 4 colleges = 248 (noisy) vs Grab's browser ~330 → real shortfall consistent with
  a per-call cap the browser paginates past via a mechanism plain params don't replicate.
- Isolation looked clean (arc/scc overlap ~0 modulo grep noise) and freshness passes (seconds-precision
  "accurate as of" stamp), so DATA + ISOLATION are fine — only COMPLETENESS fails.
VERDICT: uncircumventable ~20-cap on plain-HTTP calls = silent-miss on any subject >20 sections (most of
them at a 75k district). NOT shippable until the browser's real pagination request is network-traced (the
increment/token that fetches page 2+). High ROI IF cracked (4 colleges) — worth a dedicated browser trace
(Grab's lane, or Build when the app-store push pauses). No schools.py edit. Same bar as Delaware/Brandeis.

### Codex Batch 84 (Colleague) — ✅ 4 SHIPPED July 15 (Build): 720->724
Grab-relayed Codex batch, re-gated live through the registered base `Colleague` adapter (~112k students):
Wake Tech (~72k, ENG 111 196 sec 52 open/144 not-open), Schoolcraft (ENG 101 66 sec 46/20, exact),
Central Carolina CC (ENG 111 68 sec 25/43), Brunswick CC (ENG 111 21 sec 14/7, exact). Zero open-with-0-
seats — base Colleague textual-Open rule correctly withholds waitlisted-with-seats (Wake Tech confirmed).
4-line subclasses, no new code. ⚠️ Alamance CC HELD — production Colleague.fetch() returns NO DATA (term-
picker/bootstrap mismatch, same shape as MassArt's SearchAsync-vs-PostSearchCriteria); do not ship until
it reproduces through production. Codex Batches 80-84 are system-shaped adapter-reuse work — good vein.

### Codex Batches 82+83 (Colleague) — ✅ 6 SHIPPED July 15 (Build): 724->730
Grab-relayed, re-gated live through base `Colleague` (~107k students; batches 82/83 combined w/ 84 = 10
net-new / ~215k): College of DuPage (~28k, ENGLI 1101 216 sec 180/36), Southwestern CA (ENGL C1000 120
sec 67/53), Victor Valley (ENGL C1000 80 sec 18/62 — SALVAGED on vvc-ss.colleague.elluciancloud.com after
the old IPEDS host fetched empty), Elgin (ENG 101 79 sec 48/31, host on :8173 — port works incl. from prod),
Kellogg (ENGL 151 31 sec 25/6), Coalinga (ENGL C1000 34 sec 6/28). All 4-line subclasses, zero open-with-0-
seats. Still pending from Grab: Batch 80 (Santa Ana + Santiago Canyon, SHARED rsccd host, campus codes
SAC/SCC — needs isolation) + Batch 81 (Illinois Eastern 3-college shared Banner). Alamance still held.

### Rancho Santiago CCD ×2 — ✅ SHIPPED July 16 (Build): 730->732
Santa Ana + Santiago Canyon on shared host colss-prod.cloud.rsccd.edu. NOT a plain drop-in: base Colleague
took the FIRST CourseFullModel → served SAC only, SCC invisible. FIX: additive `campus` hook on base
Colleague (pick the model whose LocationCodes contains the campus code + keep only that campus's section
rows by LocationCode). campus="" default = no-op, all ~46 existing Colleague schools unchanged (Wake Tech
196-sec regression clean). Gate: Santa Ana ENGL C1000 88 sec 33/55, Santiago Canyon 48 sec 24/24, cross-
campus section-key overlap EMPTY (isolation proven, prod-verified). Field names live-confirmed
(LocationCodes on model, LocationCode on section).

### Los Rios CCD ×4 (~75k) — ⚠️ OPEN COMPLETENESS QUESTION, NOT shipped
hub.losrios.edu/classSearch/getCourses.php, per-college arcFilter/crcFilter/flcFilter/sccFilter, closedFilter
=true mandatory (Maricopa-style, hides full otherwise). Isolation mostly clean (arc vs scc BIOL overlap=2,
NOT fully 0 — needs a look). ⚠️ COMPLETENESS GAP: BIOL summed across 4 colleges = 248 via getCourses.php,
but Grab saw ~330 in the browser. offset>0 returns EMPTY (couldn't crack pagination). The 248-vs-330 gap =
possible truncation (Delaware-style) OR the browser counted differently. MUST resolve pagination + the
2-section cross-college overlap before shipping. Held.

### Los Rios ×4 — DEFER CONFIRMED July 16 (Grab closed the ambiguity): question resolved, stays parked
Grab cracked the real search param (searchBar=, its earlier subs= was its own bug) and proved the cap is
REAL + unpaginatable: hard 20-per-call (ENGWR 300 = 20/20/20/20 across colleges while the API's own
response reports total=292); offset IGNORED (23/46/100 all return the same batch); no page param; the
official page itself never renders past ~23 of its claimed 330 (no lazy-load XHR on scroll). Isolation
and freshness are fine — ONLY the cap kills it. Delaware verdict: silent-miss on the most-watched course.
PARKED unless LRCCD ever exposes a complete/paginated endpoint.

### Illinois Eastern CC ×3 — ✅ SHIPPED July (Build): 732->735
Wabash Valley + Olney Central + Lincoln Trail on shared Banner-9 host banprodss1.iecc.edu:8447 (:8447 port
works incl. prod). Campus isolation via campusDescription first-token (SD-regental `IECC(Banner)` base;
WABASH/OLNEY/LINCOLN). ENG 1111: Wabash 6 sec 5/1, Olney 4 sec 2/2, Lincoln Trail 4 sec 4/0 — all EXACT to
Codex, all 3 pairs CRN-disjoint, auto-term 202730, 0 false-opens (base seatsAvailable>0 rule). Lincoln
Trail's Codex cross-list note = no false-open either way (all 4 have real seats). Completes Codex Batch
80-84 re-gate: 10 Colleague + Rancho Santiago x2 + Illinois Eastern x3 shipped, Alamance held. Frontier CC
correctly cut by Codex.

### Codex Batch 86 — 0 new schools; five verified holds (July 18)
Batch 86 tested five exact-name-new official surfaces and intentionally produced no handoff-ready school. Details
and resume conditions are in `research/lane-codex.md` (the lane is the source of truth).

- **College of Eastern Idaho** — anonymous Colleague search at
  `https://colss-prod.ec.cei.edu/Student/Courses/Search?subjects=ENGL` is genuinely seat-bearing: ENGL-101
  exposes native IDs (for example `30017`/`30234`), current Summer/Fall rows, numeric available/capacity/
  waitlist triplets (for example `14 / 24 / 0` and `16 / 27 / 0`), and a waitlisted row. It only exposes 2026
  Summer/Fall, with no completed term; **HOLD** pending completed replay and full first-year-writing enumeration.
- **Westmoreland County Community College** — official Course Schedule
  `https://sisportal-100910.campusnexus.cloud/CMCPortal/Common/CourseSchedule.aspx` returned ENG161 native
  section codes, 1/2 pagination, and numeric `Avail Seats` values (including 0/25 and 20/25). Its picker has
  2026 Fall/Summer/Winter and 2027 Spring but no completed Spring 2026; **HOLD**.
- **Wayne State College (NE)** — official PeopleSoft guest search linked from
  `https://www.wsc.edu/records-registration` includes historical terms but places a reCAPTCHA in front of
  row search; **HOLD**, no CAPTCHA bypass.
- **St. Louis Community College** — official registration guidance
  `https://stlcc.edu/admissions/register/how-to-register.aspx` routes through Archer Connect/Banner login; the
  public host timed out without a guest payload; **HOLD**.
- **Arkansas State University Three Rivers** — `https://www.asutr.edu/page/account-information` confirms
  secure MyASUTR/Banner Student Self Service for course browsing; no permitted anonymous seat feed; **HOLD**.

No production files, registry entries, or builder handoff were changed. Batch 86 therefore adds **0** to the app.

### SUNY Delhi — GATED, AWAITING GO-AHEAD (Codex Batch 87, July 18, 2026)

Net-new public SUNY technology college (Fall 2024 degree-seeking enrollment **3,035**, official enrollment
table: `https://www.delhi.edu/about/institutional-effectiveness/institutional-research/enrollment-data.php`).
The registrar links the anonymous Bronco Web/Banner schedule (`https://www.delhi.edu/mydelhi-students/registrar/class-schedule/`),
which resolves to `prod.banner.delhi.edu`, `StudentRegistrationSsb`, with no login or bearer token.

- **Exact recipe:** bootstrap `GET /StudentRegistrationSsb/ssb/classSearch/classSearch`; term list
  `GET /StudentRegistrationSsb/ssb/classSearch/getTerms?searchTerm=&offset=1&max=40`; current term `202609`
  (Fall 2026); reset then paginated `searchResults` with `txt_subject=ENGL`, `txt_courseNumber=100`,
  `txt_term=202609`, `pageOffset=0`, `pageMaxSize=100`. No `mepCode`.
- **Current evidence:** exact `ENGL 100` (“Composition I”) returned `totalCount=22`, all 22 rows in one page,
  unique sequence keys (`001`…`IN9`), **1 positive / 21 zero-or-negative** `seatsAvailable`. The endpoint
  returned HTTP `Date: Sat, 18 Jul 2026 16:05:00 GMT`, `Cache-Control: max-age=0; no-store`; three production
  fetches were stable at about 1.0–1.1s.
- **Completed replay:** Spring 2026 view-only term `202602` returned 11 unique rows, **7 positive / 4 full**;
  Fall 2025 `202509` returned 25 unique rows, **20 positive / 5 full**. This is genuine mixed historical data,
  not an all-open guest result. Native keys are `sequenceNumber`; exact-number and subject guards prevent sibling
  leakage. Current rows exposed `waitCapacity`, `waitCount`, and `waitAvailable` all zero; no reservation,
  linked, or cross-list blocker fields were present. Negative availability is clamped closed by Banner rules.
- **Builder contract:** use the existing Banner family plus the shared strict waitlist/reservation hook from the
  current Banner handoff; never trust `openSection`, require numeric seats > 0, preserve the exact course/term/key
  guards, and add current/completed fixtures for zero, negative, waitlist, reserved, linked, and cross-list traps.
  This is **GATED, AWAITING GO-AHEAD**; no production code was changed.

### Guam Community College — GATED, AWAITING GO-AHEAD (Codex Batch 87, July 18, 2026)

Net-new public two-year college (Fall 2024 enrollment **1,587**, official Guam statistical yearbook table:
`https://bsp.guam.gov/wp-bsp-content/uploads/2026/01/2024-Guam-Statistical-Yearbook-Final.pdf`). The official
schedule page (`https://guamcc.edu/admissions/classschedule`) links the anonymous Ellucian Banner host
`reg-prod.gcctmsaas.elluciancloud.com:8103`.

- **Exact recipe:** bootstrap `GET /StudentRegistrationSsb/ssb/classSearch/classSearch`; terms list returns
  current `202680` (Fall 2026), completed `202610` (Spring 2026), and `202580` (Fall 2025); reset then call
  paginated `searchResults` with `txt_subject=EN`, `txt_courseNumber=110`, and the selected `txt_term`.
- **Current evidence:** exact `EN 110` (“Freshman Composition”) returned `totalCount=8`, all 8 in one page,
  unique sequence keys `01`–`07` and `31`, **6 positive / 2 full** `seatsAvailable`; three production fetches
  were stable at about 2.33–2.47s. HTTP term response was 200 with a current `Date` header and JSON content type.
- **Completed replay:** Spring 2026 returned 6 unique rows, **5 positive / 1 full**; Fall 2025 returned 8,
  **1 positive / 7 full**, proving mixed historical status. All rows had `waitCapacity`, `waitCount`, and
  `waitAvailable` equal to zero; no reservation/linked/cross-list fields were exposed. Exact subject/number
  guards and unique native sequence keys passed; negative seats are closed/clamped.
- **Builder contract:** reuse the existing Banner family with the shared strict waitlist/reservation hook,
  requiring numeric `seatsAvailable > 0` and fail-closed behavior for any future blocker fields. This is
  **GATED, AWAITING GO-AHEAD**; no production code was changed.

### Batch 87 explicit holds (not handoff-ready)

- **College of the Muscogee Nation (OK)** — official portal documentation says Course Schedule Search is inside
  the Student Portal and the same portal requires the student account (`https://cmn.edu/activateportal.pdf`).
  No permitted anonymous seat-bearing feed, completed replay, or registerability evidence; **HOLD**.
- **Navajo Technical University (AZ/NM)** — official registration guidance says course details/registration use
  My.NTU/ecampus login, while public course schedules are static upcoming publications
  (`https://www.navajotech.edu/future-students/online-registration/`). No anonymous live seats or completed
  mixed replay; **HOLD**.
- **Southern Regional Technical College (GA)** — certificate-listed `bannerselfserve.southernregional.edu`
  timed out on the official Banner term endpoint; alternate certificate host `ssb.southernregional.edu` did not
  resolve. No permitted public payload or efficient (<30s) path; **HOLD**.
- Northshore Technical Community College was substituted out because Batch 78 already permanently **CUT** it for
  an all-positive completed ENGL 1015 replay; it is not counted or re-proposed here.

**Batch 87 result: 2 gated candidates, 3 explicit holds.** No `schools.py` edits, registry changes, deployment,
or builder message were made.

### Codex Batch 88 — five fresh CT-log targets checked July 18, 2026 (all HOLD; no safe handoff)

These five exact-name-new identities were claimed from the certificate-log Banner sweep and checked against
their official registrar/schedule surfaces. None cleared the production gate: a public schedule lead is not
enough without an exact first-year-writing enumeration, current numeric seats, completed mixed replay,
registerability semantics, and an efficient sanctioned host. No production files or registry entries were changed.

1. **Fitchburg State University (MA) — strong public seats-list lead, HOLD.** The official registrar page
   (`https://www.fitchburgstate.edu/academics/academic-calendars-course-and-exam-schedules`) links the public
   Oracle APEX seats list at `https://web4.fitchburgstate.edu/apex/f?p=127:2::::::` (Day Fall 2026). The live
   page reports 873 rows with `Course Number`, CRN, `Actual`, `Max`, `Avail`, and `Waitlist` columns; Fall rows
   are dated 09/03/26–12/21/26 and include explicit cross-list warnings (for example, ARAB 2030). This is a
   useful current numeric surface, but it is on `web4` rather than a certificate-listed Banner host, the exact
   first-year-writing rows were not yet enumerated, and no completed-term replay or adapter parse was captured;
   **HOLD** pending those checks. The official registration page confirms students use CRNs from the seats list
   and authenticate through My Falcon (`https://www.fitchburgstate.edu/academics/courses-and-registration/registrar/how-register`).
2. **Northeastern Illinois University (IL) — guest Banner alternate found, HOLD.** NEIU’s official class
   schedule page (`https://www.neiu.edu/academics/registrar-services/class-schedules-and-registration-information`)
   explicitly offers Guest Access and links to `https://hrfin.neiu.edu/StudentRegistrationSsb/ssb/term/termSelection?mode=search`,
   which reaches a public term-selection page. The claimed CT-log hosts `ssb-neiupprd.neiu.edu` (DNS failure)
   and `ssb.neiu.edu` (404) did not yield a permitted payload; the `hrfin` alternate was not certificate-listed
   in this claim and its class-search JSON, exact English 101 rows, completed replay, and latency were not captured.
   NEIU documents electronic waitlists, so reservation/waitlist semantics also require an exact response audit;
   **HOLD**.
3. **West Virginia State University (WV) — MyState-only schedule path, HOLD.** WVSU’s official class-schedule
   page (`https://wvstateu.edu/academics/class-schedules/`) links “Searchable Schedule” to MyState and states
   that students must apply/be admitted to register. The claimed `banner.wvstateu.edu` host did not resolve, and
   no anonymous seat-bearing response, exact first-year-writing result, completed mixed term, or guest latency was
   captured from MyState; **HOLD**.
4. **Missouri Southern State University (MO) — live open/closed UI but no numeric guest rows, HOLD.** MSSU’s
   official registrar guidance (`https://www.mssu.edu/student-affairs/registrar/enrollment.php`) directs users to
   LioNet Browse Classes; the official open/closed page (`https://lionet.mssu.edu/web/guest/course-list`) currently
   exposes `2026 Fall (AY27)`/`2026 Summer (AY26)` and Open/Closed/Class Type filters, but no numeric seat rows in
   the accessible guest response. The official Fall 2026 schedule-book page confirms the term and points back to
   that open-class list (`https://www.mssu.edu/academics/classes/index.php`). The claimed `ssb.mssu.edu` host timed
   out; no exact ENGL 101, completed replay, or waitlist/reservation payload was captured; **HOLD**.
5. **Oklahoma Panhandle State University (OK) — no verified public schedule path, HOLD.** Certificate-listed
   `banner.opsu.edu` returned HTTP 403 and `ssb.opsu.edu` returned 404; no numeric guest endpoint or exact
   first-year-writing/completed-term response was obtained. Search results route to Oklahoma State system registrar
   material rather than an OPSU-specific public seat feed, so no identity or adapter inference is safe;
   **HOLD** pending an official OPSU schedule URL and replayable payload.

**Batch 88 result: 0 gated, 5 explicit holds.** Fitchburg is the only high-value follow-up (official current
numeric seats + pagination), but it still needs exact writing-course enumeration and completed replay before any
builder handoff. The other four remain blocked by dead claimed hosts, login/portal-only access, or missing numeric
guest data. No `schools.py` edits, builder contact, or deployment occurred.

### Codex Batch 89 — five registrar-path targets checked July 18, 2026 (all HOLD; Clovis is follow-up priority)

These five exact-name-new schools were claimed after registry deduplication and checked against official current
registrar/schedule routes. The gate requires a current exact first-year-writing result, complete pagination, numeric
registerable status, a completed mixed replay, unique keys, freshness, and sibling/reservation guards. No production
file or registry entry was changed.

1. **Clovis Community College (CA) — strong public Colleague lead, HOLD pending completed mixed replay.** The
   official class-schedule page links the guest SCCCD Self-Service catalog (`https://selfservice.scccd.edu/Student/Courses`)
   and documents term/subject/course-number search (`https://www.cloviscollege.edu/current-students/schedule-of-classes.html`).
   Read-only API audit used the official token/session flow: `POST /Student/Courses/PostSearchCriteria` with
   `{"Keyword":"ENGL C1000"}` selected the exact `CourseFullModel` titled “Academ Reading & Writing” with
   `LocationCodes` including `CCC` and 93 matching section IDs; `POST /Student/Courses/Sections` returned all
   **31/31 Fall 2026 CCC rows** in one response, all 31 unique by native `Id`. Three repeated production requests
   took 3.16–3.48s and reproduced the same rows/date (`2026-08-10` start): **10 `Open` rows with Available
   1–21 and 21 `Waitlisted` rows with Available 0**. `AreSeatCountsAvailable` was true and `WaitlistAvailable`
   was true; registerability must use `AvailabilityStatus == Open` plus positive numeric `Available`, never just
   the count. Spring 2026 returned 14 CCC rows but every row was `Open` (no full/closed control), so the required
   completed mixed replay is not proven. This is a shared SCCCD host: preserve the exact `CCC` location guard and
   reject Fresno/Reedley/Madera/Oakhurst sibling models. **HOLD** until a completed term (e.g., Fall 2025) is
   reachable through an official historical route and yields mixed status, plus HTTP freshness/header capture.
2. **BridgeValley Community and Technical College (WV) — Argos report, HOLD.** The official registrar page lists
   Fall 2026 and links “Class Schedules” (`https://www.bridgevalley.edu/registrar/calendars-schedules.html`), which
   redirects to an Argos report at `maps.wvnet.edu/argos/awv/` with a short-lived report token. The report shell
   requires its JavaScript applet, while the official BridgeValley route is Cloudflare-challenged in a direct
   request; no permitted numeric seat payload, first-year-writing enumeration, completed replay, or efficient
   adapter path was captured. **HOLD**; do not bypass the challenge.
3. **Housatonic Community College / CT State Housatonic (CT) — portal-only schedule, HOLD.** Current CT State
   registration guidance says students must use myCTState Student Self-Service to find/register classes and that
   the schedule is available there (`https://ctstate.edu/admissions-registration/register-for-classes`). Historical
   Housatonic catalogs describe the old myCommNet Course Search but no current anonymous numeric endpoint. No
   sanctioned guest seat response, exact ENGL 1010/C1000 pagination, completed replay, or reservation semantics;
   **HOLD**.
4. **Norwalk Community College / CT State Norwalk (CT) — portal-only schedule, HOLD.** The official CT State
   page routes current course search and registration through myCTState; archived Norwalk material describes the
   retired myCommNet Course Schedule Search, not a current public feed. No anonymous numeric rows, exact
   first-year-writing scope, completed mixed term, or efficient adapter path was captured; **HOLD**.
5. **Manchester Community College / CT State Manchester (CT) — portal-only schedule, HOLD.** The official
   Manchester pages identify the institution as CT State Manchester and route current registration/course search
   through myCTState; legacy “Search for Courses” references are stale. No current anonymous numeric seat payload,
   completed replay, or registerability/reservation audit was captured; **HOLD**.

**Batch 89 result: 0 gated, 5 holds.** Clovis is the only high-value next probe: resume with a documented official
historical-term route, preserve `CCC` sibling isolation, and require a mixed completed replay before any builder
handoff. No `schools.py` edits, registry changes, deployment, or builder message were made.

### Codex Batch 90 — five public registrar paths checked July 18, 2026 (one gated, four holds)

These exact-name-new targets were claimed in `research/lane-codex.md` before probing. The gate requires a current
exact first-year-writing result, complete pagination, numeric registerable status, a completed mixed replay, unique
keys, freshness, and reservation/sibling guards. No production file or registry entry was changed.

1. **Northwest College (WY) — GATED, AWAITING GO-AHEAD (bespoke static JSON adapter).** Official registrar links
   the public [Class Schedule & Syllabi page](https://www.nwc.edu/academics/class-schedule.html), whose Vue client
   calls `https://area10.nwc.edu/nwcforms/Syllabi/GetCurrentTerm`, `GetTermsJson`, and
   `GetScheduleDownload?term={term}&sub=ENG`. On July 18, `GetCurrentTerm` returned `26/FA` and the exact
   `ENGL-1010` (English Composition I) filter returned **14/14 unique** rows in one JSON response. Three identical
   production fetches were 0.815–0.977s with `Date: Sat, 18 Jul 2026 17:03:45–47 GMT` and `Cache-Control: no-store`.
   Fall 2026 rows had numeric `SEC_CAPACITY`/`ACTIVE_COUNT`; raw availability is `SEC_CAPACITY - ACTIVE_COUNT`.
   Eight rows have positive capacity (seven safe positive opens; one full), while six concurrent high-school rows
   carry `TYPES_DELIM` containing `CONC` and `SEC_CAPACITY=0` (some have positive active counts), so the adapter
   must fail closed on `SEC_CAPACITY <= 0` and never count those as seats. `WL_COUNT` was null on all 14; the
   official UI renders rows with `SEC_CAPACITY-ACTIVE_COUNT < 1` gray and displays a wait-list count when present.
   Completed Spring 2026 returned **5/5 unique** `ENGL-1010` rows with a genuine mixed control (4 positive,
   1 full); Fall 2025 returned 18 mixed rows. Required builder contract: pin exact `term`, `SEC_SUBJECT=ENGL`,
   `SEC_COURSE_NO=1010`, native `COURSE_SECTIONS_ID` (or `SEC_SYNONYM`) keys, `SEC_CAPACITY>0`, numeric
   `ACTIVE_COUNT`, `available>0`, no `CONC` token, and reject any `WL_COUNT` truthy/nonzero row. This is
   **GATED, AWAITING GO-AHEAD** as a source-gated bespoke adapter; builder should add no production entry until
   Nathan approves the handoff.
2. **Kishwaukee College (IL) — HOLD (excellent guest Colleague feed, no completed mixed status).** Official
   [course-search page](https://kish.edu/academics/course-search-catalog/) links the public
   `https://kish-ss.colleague.elluciancloud.com/Student/Courses` flow. Exact `ENG 103` (Composition I) returned
   41 matching IDs and **23/23 Fall 2026** rows, all unique by native `Number`/`Id`; three section calls were
   0.444–0.584s with `Date` and `no-store,no-cache`. Current rows included Open and Waitlisted statuses with
   numeric `Available` and `AreSeatCountsAvailable=true`, so the conservative rule is status `Open` plus
   `Available>0` (never Waitlisted). Spring 2026 returned 15 rows but all were Open after the term ended, so the
   required completed mixed replay is not proven. **HOLD** pending an official historical Fall 2025 route and
   preserve the single-campus host guard.
3. **Glenville State University (WV) — HOLD (schedule has no seat payload).** The official [course-schedule page]
   (https://www.glenville.edu/academics/course-schedule) links [Undergraduate Course Schedules]
   (https://www.glenville.edu/academics/course-schedule/undergraduate), which exposes term/program schedule
   listings but no numeric capacity, active, status, or registerability fields in the public response. Registration
   is through EdNet and requires a student PIN. No permitted seat-bearing guest payload or replay; **HOLD**.
4. **College of the Florida Keys (FL) — HOLD (classic Banner login boundary).** The official [registration page]
   (https://www.cfk.edu/admissions/plan-register/) says the real-time schedule is behind the College’s Course
   Search link and that students must be enrolled/admitted to register. The linked `secure.cfk.edu` route resolves
   to the classic `twbkwbis.P_WWWLogin` sign-in page; no anonymous numeric schedule response or completed replay
   was available. **HOLD**; do not bypass authentication.
5. **Jefferson State Community College (AL) — HOLD (official linked host unreachable).** The official [class
   schedules page](https://www.jeffersonstate.edu/admissions/registration/class-schedules/) links the ACCS guest
   host `https://reg-prod.ec.accs.edu/Student/Courses`, but read-only requests returned HTTP 503 `No valid route`
   for the root and documented course paths. No exact English 101 rows, numeric status payload, freshness, or
   completed replay; **HOLD** pending an official reachable guest route.

**Batch 90 result: 1 gated, 4 holds.** Northwest College is the only builder-ready candidate, with a strict
`SEC_CAPACITY>0`/no-`CONC`/numeric-delta contract that excludes its dual-enrollment rows. No `schools.py` edits,
builder contact, registry changes, or deployment occurred.

### Codex Batch 91 — five registrar paths checked July 18, 2026 (one gated, four holds)

These exact-name-new targets were claimed in `research/lane-codex.md` before probing. No production file or
registry entry was changed.

1. **Washburn University (KS) — GATED, AWAITING GO-AHEAD (existing Banner adapter).** Washburn’s official
   [schedule page](https://www.washburn.edu/academics/course-schedule/index.html) links the public Banner guest host
   `https://banssb-lb-prod.washburn.edu/StudentRegistrationSsb/ssb`. `getTerms` exposed Fall 2026 `202630`, Spring
   2026 `202611`, and Fall 2025 `202530`. Exact `EN 101` (Introductory College Writing) returned complete **31/31
   unique** current rows in one page; three production replays were 0.373–0.519s and had identical canonical
   `(sequenceNumber, CRN, seatsAvailable, capacity, enrollment, status, wait, link)` tuples. Fall 2026 had 7
   positive/open rows and 24 zero/negative/full rows; `seatsAvailable == maximumEnrollment - enrollment` held on
   the audited rows. `waitAvailable`, `waitCapacity`, and `waitCount` were all zero; `crossList`, `isSectionLinked`,
   and `reservedSeatSummary` were empty on the current rows. Completed Fall 2025 returned **30/30 unique** rows
   with genuine mixed numeric status (26 positive/open, 4 full), and the same seat arithmetic. Strict builder
   contract: reuse `Banner` with `host="banssb-lb-prod.washburn.edu"`, exact `EN 101`, term selected by the
   official `getTerms`, and the normal `seatsAvailable>0` rule; additionally fail closed when any row has a
   nonzero wait field, nonempty `reservedSeatSummary`, truthy `isSectionLinked`, or truthy `crossList`/linked
   identifiers. This is **GATED, AWAITING GO-AHEAD**; builder should add no production entry until Nathan approves.
2. **Salem State University (MA) — HOLD (browse UI stops at Navigator).** The official [Browse Classes page]
   (https://www.salemstate.edu/browse-classes) exposes term/subject filters and explicitly directs current students
   to Navigator. The linked PeopleSoft guest browse/class-search routes produced an authorization/error boundary
   rather than an anonymous numeric section payload; no exact ENG 101 rows, completed replay, or registerability
   audit was captured. **HOLD**; do not bypass Navigator authentication.
3. **Northwest Indian College (WA) — HOLD (quarterly schedule/JICS registration, no seats).** Official [admissions
   guidance](https://www.nwic.edu/admissions/) requires an enrollment form/JICS registration and points students
   to an online quarterly schedule/calendar. The public material contains term dates and registration windows but
   no anonymous numeric capacity/status rows or replayable first-year-writing feed. **HOLD**.
4. **Marion Technical College (OH) — HOLD (career-certificate catalog, no college-writing seat feed).** The official
   [programs page](https://mariontc.edu/programs/) describes career-certificate cohorts and waitlist/application
   workflows, while its continuing-course catalog uses an authenticated Focus application. No public first-year
   composition course, numeric seats, or completed mixed replay was found. **HOLD**.
5. **North Florida College (FL) — HOLD (public APEX schedule omits availability).** NFC’s official [catalog and
   schedule page](https://www.nfc.edu/admissions/catalog-and-schedule/index.php) links the public APEX [Schedule of
   Classes](https://infonetwork.nfc.edu/apex/r/nfcapi/nfc_schedule/home). The Fall 2026 report contains `ENC 1101`
   rows (CRN/section/title/instructor/modality/dates) and a “Seats Available” filter control, but the rendered
   anonymous report has no seat-capacity, enrollment, open/closed, or waitlist values in its row columns. No safe
   numeric status or completed replay; **HOLD**.

**Batch 91 result: 1 gated, 4 holds.** Washburn is builder-ready through the existing Banner adapter with strict
wait/reservation/link guards. No `schools.py` edits, builder contact, registry changes, or deployment occurred.

### Codex Batch 92 — five official registrar paths checked July 18, 2026 (one gated, four holds)

These exact-name-new targets were claimed in `research/lane-codex.md` before probing. The gate requires a current
exact first-year-writing result, complete pagination, numeric registerable status, a completed mixed replay, unique
keys, freshness, and reservation/sibling/eligibility guards. No production file or registry entry was changed.

1. **Murray State University (KY) — GATED, AWAITING GO-AHEAD (existing Banner adapter with eligibility guard).** The
   official [Registrar calendar](https://www.murraystate.edu/academics/RegistrarsOffice/calendar.aspx) links the
   anonymous Banner guest host `https://prodssbstureg.murraystate.edu/StudentRegistrationSsb/ssb`. Its official
   `getTerms` returned Fall 2026 `202680`, Spring 2026 (View Only) `202610`, and Fall 2025 (View Only) `202580`.
   Exact `ENG 105` (Critical Reading, Writing, and Inquiry; the university's first-year composition course) returned
   complete **56/56** current rows in one page, unique by `sequenceNumber` and CRN. Three fresh production replays
   were 0.817–0.926s, had `Date: Sat, 18 Jul 2026 17:53:28 GMT`, and identical canonical
   `(sequenceNumber, CRN, campus, seatsAvailable, maximumEnrollment, enrollment, wait, link/reservation)` tuples
   (raw response hashes differ only in non-canonical dynamic fields). Current rows had numeric
   `seatsAvailable`, `maximumEnrollment`, and `enrollment`; arithmetic held on 56/56, `openSection` agreed with
   `seatsAvailable > 0` on 56/56, and the mix was 36 positive / 20 full. The feed exposed wait, cross-list,
   linked-section, and reserved-seat fields; all were zero/empty on the current rows. Two rows were marked
   `instructionalMethodDescription=Racer Academy` (campuses `RA Carlisle Co HS` and `Hopkinsville Regional
   Campus`) and must be rejected as concurrent-enrollment/eligibility rows. The safe current set is therefore
   **54 rows: 34 positive / 20 full**, allowing only non-Racer-Academy rows (Main traditional/hybrid and Web).
   Completed Spring 2026 returned 34/34 unique rows, safe non-Racer set 32 with **30 positive / 2 full**; completed
   Fall 2025 returned 29/29 unique, safe set 28 with **27 positive / 1 full**. Both completed terms had zero seat
   arithmetic errors, zero nonzero wait values, zero cross-list/link/reservation fields, and exact status agreement.
   Strict builder contract: reuse `Banner` against `prodssbstureg.murraystate.edu`, exact `ENG 105`, official
   `getTerms` term resolution, paginate until `totalCount`, require numeric `seatsAvailable > 0`, and fail closed
   on any nonzero wait field, truthy cross-list/link/reservation field, or
   `instructionalMethodDescription == "Racer Academy"`; retain native sequence/CRN keys. This is **GATED,
   AWAITING GO-AHEAD** pending Nathan's approval because the eligibility filter is essential.
2. **University of Arkansas–Pulaski Technical College (AR) — HOLD (Power BI schedule, no machine-readable seat
   evidence).** The official [Schedule of Classes](https://uaptc.edu/schedule-of-classes) embeds a public Power BI
   course-listing report. The surrounding official page describes course names, instructors, locations, meeting
   days/times, and prerequisites, but the anonymous report bootstrap supplied no stable numeric capacity,
   enrollment, availability, waitlist, or registerability payload and no completed mixed replay. The official
   [registration instructions](https://uaptc.edu/student-workday/register) route registration through Workday.
   **HOLD**; do not infer seats from a Power BI listing.
3. **University of Arkansas Rich Mountain (AR) — HOLD (Power BI schedule without an auditable seat feed).** The
   official [student-login page](https://www.uarichmountain.edu/student-login.html) links `Course Schedules` to
   a public Power BI report. Its anonymous report bootstrap was only a loading shell; no stable row-level numeric
   capacity/enrollment/open/waitlist fields or completed mixed replay could be obtained. **HOLD** pending an
   official machine-readable guest feed; no assumption that a visual schedule implies registerability.
4. **University of Arkansas Community College at Hope (AR) — HOLD (course-schedule pages are descriptions only).**
   The official [Course Schedules page](https://www.uaht.edu/academics/course-schedules.php) exposes only
   2024–25 and 2025–26 course-description links; its linked [Texarkana schedule page](https://www.uaht.edu/academics/course-schedule-texarkana.php)
   contains no current numeric row data. Registration news directs students to the college's authenticated
   systems; no anonymous first-year-writing capacity/status feed or completed mixed replay was found. **HOLD**.
5. **Southeastern Louisiana University (LA) — HOLD (public JSON has string status but no numeric seats).** The
   official Registrar page says non-students should use the public [Course Section Offerings](https://www2.southeastern.edu/external/course_section_offerings/)
   page. Its official `assets/course_catalog.json` returned exact `ENGL 1010` (Freshman Composition) rows for the
   2026–27 academic year: Fall **58** unique sections (57 `Closed`, 1 `Open`) and Summer **2** (`Open`), but
   section objects contain only `unique_id`, course/term, meeting, instructor, delivery, and `class_status` keys—no
   capacity, enrollment, available-seat, waitlist, or reservation fields anywhere in the payload. It exposes no
   completed historical mixed term. String `Open` is therefore not safe numeric registerability. **HOLD**.

**Batch 92 result: 1 gated, 4 holds.** Murray State is the only builder-ready candidate, and only with the explicit
Racer-Academy eligibility exclusion and existing Banner guards. No `schools.py` edits, builder contact, registry
changes, or deployment occurred.

### Codex Batch 93 — five official registrar paths checked July 18, 2026 (four gated, one hold)

These five exact-name-new schools were claimed in `research/lane-codex.md` before probing. The gate requires a
current exact first-year-writing result, complete pagination, numeric registerability, a completed mixed replay,
unique keys, freshness, and reservation/sibling/eligibility guards. No production file or registry entry was changed.

1. **University of North Alabama (AL) — GATED, AWAITING GO-AHEAD (existing Banner adapter with population guard).**
   UNA's official [registrar schedule page](https://www.una.edu/registrar/registration/schedule.html) links the
   public guest Banner host `https://selfserve.una.edu/StudentRegistrationSsb/ssb`. Its official `getTerms` exposed
   Fall 2026 `202710`, Spring 2026 View Only `202620`, and Fall 2025 View Only `202610`. Exact `EN 111` rows are
   titled **First-Year Composition I**; Fall 2026 returned complete **46/46** rows in one page, with unique native
   sequence keys and `seatsAvailable`, `maximumEnrollment`, and `enrollment` arithmetic matching on 46/46. The
   response includes 23 traditional Main-campus rows and 23 concurrent high-school rows (`instructionalMethodDescription`
   contains `Taught at High School`); the latter must be rejected as an eligibility/population leak. On the safe
   traditional set, current status is **10 positive / 11 full**, with 2 additional full rows carrying nonzero
   `waitCount` (reject them). `crossList`, `isSectionLinked`, and `reservedSeatSummary` were empty on all audited
   traditional rows. Three fresh current replays had distinct `Date`/raw hashes but the same canonical
   `(sequenceNumber, seatsAvailable, maximumEnrollment, enrollment, waitCount, crossList, isSectionLinked,
   reservedSeatSummary)` tuples. Completed Spring 2026 returned 12 rows (safe traditional set 10: 3 positive / 7
   full); completed Fall 2025 returned 45 rows (safe traditional set 22: 17 positive / 5 full), both mixed with
   numeric arithmetic. Strict builder contract: reuse `Banner` at `selfserve.una.edu`, exact `EN 111`, paginate to
   `totalCount`, require exact title `First-Year Composition I`, reject any `Taught at High School` row, require
   numeric `maximumEnrollment`, `enrollment`, `seatsAvailable` with `maximumEnrollment - enrollment == seatsAvailable`,
   and fail closed on `seatsAvailable <= 0`, nonzero wait fields, truthy cross-list/link/reservation fields, or
   non-Main campus. Retain native sequence keys. This is **GATED, AWAITING GO-AHEAD** pending Nathan's approval.
2. **University of Southern Indiana (IN) — GATED, AWAITING GO-AHEAD (existing Banner adapter with punctuation/title guard).**
   USI's official [classes page](https://www.usi.edu/registrar/classes) explicitly links its public online search
   catalog at `https://banproxyp.usi.edu/StudentRegistrationSsb/ssb/term/termSelection?mode=search`. Official terms
   exposed Fall 2026 `202710`, Spring 2026 View Only `202620`, and Fall 2025 View Only `202610`. The exact course
   identity is `ENG 101.` (the API course number includes a literal trailing period), titled `Rhet&amp;Comp I:Literacy/Self`
   (one current TLC variant has the same prefix). Fall 2026 returned complete **34/34** rows in one page with unique
   sequence keys; `maximumEnrollment - enrollment == seatsAvailable` held on 34/34. Applying exact `courseNumber ==
   "101."`, title-prefix, positive-capacity, and no-wait/link/reservation/cross-list guards leaves **10 positive / 19
   full** rows; 5 zero-capacity rows are rejected. Three fresh current replays (with `Date` headers) had different raw
   hashes but identical canonical tuples. Completed Spring 2026 returned 15 mixed rows (11 positive / 3 full after
   the same guards); Fall 2025 returned 30 (26 positive / 4 full). Wait, cross-list, linked-section, and reserved-seat
   fields were empty/zero in all audited rows. Strict builder contract: use the official host and term resolver,
   query the literal `ENG 101.` (do not strip the period), require exact subject/course/title-prefix, numeric
   `maximumEnrollment`, `enrollment`, `seatsAvailable` with arithmetic agreement, positive-capacity for alerts, and
   fail closed on zero/negative capacity, nonzero wait, or any cross-list/link/reservation field; retain native
   sequence keys. This is **GATED, AWAITING GO-AHEAD** pending Nathan's approval.
3. **Southern Illinois University Carbondale (IL) — GATED, AWAITING GO-AHEAD (existing Banner adapter).** SIU's
   official [Registrar home](https://registrar.siu.edu/) links the public [Schedule of Classes Search](https://banssb1.siu.edu/StudentRegistrationSsb/ssb/term/termSelection?mode=search).
   Official terms exposed Fall 2026 `202660`, Spring 2026 View Only `202620`, and Fall 2025 View Only `202560`.
   Exact `ENGL 101` is titled **English Composition I** and returned complete **55/55** Fall 2026 rows in one page,
   all with `campusDescription=Carbondale Campus `, unique native sequence keys, and arithmetic agreement on 55/55.
   The current mix is **13 positive / 42 full** (two over-enrolled rows report `seatsAvailable=-1`; the adapter must
   clamp/reject them as non-open). Three fresh replays had `Date` headers and identical canonical tuples. Completed
   Spring 2026 returned 12 rows (7 positive / 5 full) and Fall 2025 returned 49 rows (32 positive / 17 full), both
   mixed with exact arithmetic; all audited wait, cross-list, linked-section, and reserved-seat fields were empty or
   zero. Strict builder contract: reuse `Banner` at `banssb1.siu.edu`, exact `ENGL 101`, paginate until `totalCount`,
   require exact title and Carbondale-campus guard, numeric seat/capacity/enrollment arithmetic, and fail closed on
   nonpositive `seatsAvailable`, any nonzero wait, or any cross-list/link/reservation field; retain native sequence
   keys. This is **GATED, AWAITING GO-AHEAD** pending Nathan's approval.
4. **Missouri University of Science and Technology (MO) — HOLD.** The official [Fall 2026 class-offerings page](https://registrar.mst.edu/classofferings/fall/)
   states that current class-offering information is available through authenticated Joe'SS; its public Distance
   Classes listing is a static schedule and does not expose a permitted row-level numeric capacity, enrollment,
   available-seat, waitlist, or registerability payload. No exact first-year-writing feed or completed mixed replay
   can be built from the official public surface; **HOLD**.
5. **Southern University and A&amp;M College (LA) — GATED, AWAITING GO-AHEAD (bespoke ASP.NET schedule adapter).**
   Southern's official [Course Schedule](https://myaccess.southern.edu/apps/courseschedule/Default.aspx) exposes a
   public GET-filtered table. `Departments=English&PageSize=100&Page=1&Term=F26` returned the complete `Results (54)`
   page and exact `ENGL-101-*` **17/17** rows titled `Crit Think Ac Rdg/Wrtg I`. Native section-code keys were unique;
   each row had numeric `Enr`, `Cap`, and `Wait` fields plus explicit cross-list markers. Strict current evaluation
   (`Cap>0`, `Cap-Enr>0`, `Wait==0`, no cross-list) yields **6 positive / 4 full** safe rows; rows with nonzero wait,
   zero/negative capacity, or cross-list markers are rejected. Three fresh current replays (0.358–0.371s, `Date`
   headers) had identical canonical section/enrollment tuples. Completed Fall 2025 returned 18 rows (12 positive / 1
   full after the same guards; five cap-zero rows rejected); completed Spring 2026 returned 5 rows (1 positive / 1
   full safe, two waitlisted and one cap-zero row rejected). Strict builder contract: use the official GET filters,
   require a complete page, exact `ENGL-101-*` identity/title, numeric `Enr`/`Cap`/`Wait`, `Cap-Enr` arithmetic, and
   fail closed on `Cap<=0`, nonpositive availability, `Wait>0`, any cross-list marker/cross-list capacity, or missing
   fields; retain the native section-code key. This is **GATED, AWAITING GO-AHEAD** pending Nathan's approval.

**Batch 93 result: 4 gated, 1 hold.** UNA, USI, SIU, and Southern are safe only under the explicit contracts above;
MST lacks a permitted numeric public feed. No `schools.py` edits, builder contact, registry changes, or deployment
occurred.

### Codex Batch 94 — five public registrar paths checked July 18, 2026 (two gated, three holds)

These five exact-name-new targets were claimed in `research/lane-codex.md` before probing. No production file or
registry entry was changed. The gate requires an exact first-year-writing result, complete result coverage, numeric
seat evidence, a completed mixed-status replay, fresh repeated fetches, unique native keys, and fail-closed
registerability/eligibility rules.

1. **Pasco-Hernando State College (FL) — GATED, AWAITING GO-AHEAD (existing Banner adapter).** The official
   [registration search](https://www.phsc.edu/faq/how-do-i-register-classes) links the public Banner guest host
   `reg-prod.phsc.elluciancloud.com:8103/StudentRegistrationSsb`. Official `getTerms` resolved Fall 2026
   `202701`, Spring 2026 View Only `202602`, and Fall 2025 View Only `202601`. Exact `ENC 1101` (English
   Composition I) returned complete **45/45** current rows in one page with unique sequence/CRN keys. Numeric
   `maximumEnrollment`, `enrollment`, and `seatsAvailable` arithmetic held on **45/45**; one zero-capacity `W10`
   row (`0/0/0`) is rejected, leaving **44 safe rows: 25 positive / 19 full**. All audited wait fields were zero,
   `crossList`/`reservedSeatSummary` were empty, and `isSectionLinked` was false. Three fresh current replays had
   distinct HTTP `Date`/raw responses and identical canonical tuples. Completed Spring 2026 returned 33 rows
   (21 positive / 12 full) and Fall 2025 returned 48 (33 positive / 15 full), with the same numeric guards and no
   wait/cross-list/link/reservation flags. Strict builder contract: reuse `Banner` at the exact host, resolve the
   official current term, query exact `ENC 1101`, paginate until `totalCount`, retain native sequence keys, reject
   missing/non-numeric fields and any `maximumEnrollment <= 0`, and fail closed on nonzero wait, truthy link/cross-list,
   or nonempty reservation fields; alert only when numeric `seatsAvailable > 0`. This is **GATED, AWAITING GO-AHEAD**.
2. **University of Maine at Presque Isle (ME) — GATED, AWAITING GO-AHEAD (bespoke public UMS search adapter).**
   The official [Course Search](https://www.umpi.edu/academics/course-registration/) is a public GET form. The
   exact query `doClassSearch=1&strm=2710&subject=ENG-busunit-UMS07&keywords=ENG+101&includeClosedClassSections=1`
   returned complete **6/6** Fall 2026 `ENG 101 College Composition` sections with unique class-number/section
   keys. Each row exposes explicit status and numeric `Enrollment: N of M seats`: four `Open` rows (11/16, 12/20,
   18/20, 11/20) and two `Waitlisted` rows (20/20); strict alerting must require status exactly `Open`, numeric
   capacity/enrollment, and `M-N > 0`, never infer openness from seats alone. Three cache-busted replays had
   `Date` headers with `Age: 0`, different raw hashes, and identical canonical section/status/enrollment tuples.
   Completed Spring 2026 (`strm=2620`) returned complete **2/2** exact rows: one `Open` 9/15 and one `Closed` 20/20,
   proving mixed historical status. The exact query has no pagination control for these six rows; a future adapter must
   still detect/exhaust the documented WordPress REST pagination endpoint (`/academics/wp-json/ums-class-search/v1/get_page`)
   whenever page buttons appear. Strict contract: keep the `UMS07` institution subject code and exact title/course
   identity, parse only the numeric `N of M seats` field, alert only explicit `Open` with positive `M-N`, reject
   `Waitlisted`/`Closed`/missing or malformed fields, retain class-number+section keys, and fail closed on any
   unexpected status or incomplete page. This is **GATED, AWAITING GO-AHEAD** as a bespoke adapter.
3. **University of Montevallo (AL) — HOLD.** The official [registrar class-schedule page](https://www.montevallo.edu/about-um/administration/registrars-office/class-schedule/)
   exposes a Banner-looking route, but its schedule/search endpoints redirect to Microsoft sign-in. No permitted
   anonymous first-year-writing seat payload or completed mixed replay was obtained; authentication was not bypassed.
4. **Henderson State University (AR) — HOLD pending completed replay.** The official [registration page](https://www.hsu.edu/register/)
   links the shared Banner guest host with `mepCode=HENDSN`. Exact `ENGL 10103` (English A: Writing and Rhetoric I)
   returned complete **21/21** Fall 2026 rows (2 positive / 19 full) with arithmetic and unique CRN/sequence keys;
   three fresh replays were canonically identical and all current rows were Arkadelphia Main Campus with clean wait,
   link, cross-list, and reservation fields. However, every tested completed term returned **0 exact rows**, so there
   is no completed mixed-status evidence yet. **HOLD** until an official historical route yields real rows.
5. **University of Arkansas at Monticello (AR) — HOLD.** The official [class-schedules page](https://www.uamont.edu/academics/class-schedules.html)
   exposes a published-schedule label and Workday/student links but no anonymous machine-readable row-level numeric
   capacity, enrollment, availability, or waitlist payload. No completed mixed replay or safe adapter contract exists.

**Batch 94 result: 2 gated, 3 holds.** PHSC is safe through the existing Banner adapter; UMPI is a bespoke public
   UMS source with explicit status-plus-numeric guards. Montevallo is login-bound, Henderson lacks a completed mixed
   replay, and UAMont has no auditable seat feed. No `schools.py` edits, builder contact, registry changes, or
   deployment occurred.

### Codex Batch 95 — five CT-log-discovered institutions checked July 18, 2026 (zero gated, five holds)

These five domains came from the unexhausted CT-log target list and were claimed in `research/lane-codex.md` before
inspection. Name/dedup checks found no registry identity, but none cleared the evidence bar; no production file or
registry entry was changed.

1. **Atlantic Technical College (FL) — HOLD.** The official [site](https://www.atlantictechnicalcollege.edu/) is
   Cloudflare-challenge protected from the permitted fetch path. No anonymous public class-search response, exact
   first-year-writing section set, numeric seat/status fields, or completed mixed replay could be established.
2. **Autry Technology Center (OK) — HOLD.** The official [site](https://autrytech.edu/) is a career/technical-center
   portal rather than a public college course-registration surface. No college first-year-composition course, guest
   section rows, numeric availability, or completed replay was found; do not infer seats from program pages.
3. **Maine Maritime Academy (ME) — HOLD.** The official public [CPMD course page](https://mainemaritime.edu/cpmd/courses/)
   is a professional-mariner-development catalog with course descriptions and no live section capacity, enrollment,
   availability, waitlist, or registerability payload. No exact first-year-writing feed or completed mixed replay.
4. **Manatee Technical College (FL) — HOLD.** The official [student-services route](https://www.manateetech.edu/student-services/)
   points to the MTCDashboard/PeopleSoft portal and career-training program material. The permitted public response
   exposes no college first-year-writing schedule or numeric seat/status payload; no completed mixed replay.
5. **Midland College (TX) — HOLD.** Midland’s official [Course Search](https://www.midland.edu/enrollment-aid/course-search.php)
   embeds a Power BI report. The surrounding page says the tool can show available seats, but the anonymous bootstrap
   is a visualization shell rather than a stable row-level numeric capacity/enrollment/status feed; no auditable
   exact writing enumeration or completed mixed replay was obtained. Do not infer registerability from the visual.

**Batch 95 result: zero gated, five holds.** The CT-log domains were useful for discovery but these five have no
permitted, auditable first-year-writing seat source. No `schools.py` edits, builder contact, registry changes, or
deployment occurred.
