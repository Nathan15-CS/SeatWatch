# SeatWatch research — working summary (LEAN)

Cross-session research log for SeatWatch school expansion. **This file is kept lean on purpose** —
the full chronological batch-by-batch history lives in `research/ARCHIVE.md` (grep it for any past
detail). Read THIS file + the lane files; only open ARCHIVE for a specific past finding.

- **Live count: 703 schools** (goal 1,000); verified from `len(schools.SCHOOLS)` on July 13, 2026
  (684→691 Batch31+USC+Rice+Princeton+WrightState+Duquesne; →703 Maricopa ×10 + more, all Build). RCCD ×3
  cracked below = next.
- **Who's doing what right now:** `research/lane-grabber.md` (Grab) + `research/lane-codex.md` (short, always current).
- **How we work / accuracy+efficiency gate:** `research/PARTNER-NOTE-codex.md` and repo-root
  `CONTRIBUTING_AGENT.md`. Handoffs to the builder go through Fable; gated-but-unapproved candidates
  get a heading containing the phrase **`AWAITING GO-AHEAD`** (grep for it to find every pending item).

---

## PENDING HANDOFFS (grep `AWAITING GO-AHEAD`)

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
  sections are reserved for that program" warning. **Optional volume bonus:** DACC - Doña Ana CC (~8k,
  separately accredited) rides the same host — its 'DACC' first token DOES work with the existing filter
  (ENGL 1110G: 49 sec 25/24). Dedup clean in Python (UNM/Highlands/Western NM/CNM are different schools).
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
  (different host). DACC rider NOT taken (4-year priority; decision open to Nathan).
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
