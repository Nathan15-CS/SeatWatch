# Cross-session research handoff

Validated research artifacts shared between parallel SeatWatch expansion sessions.
Commit new findings here so other sessions don't redo probing work.

## Minnesota State (eservices.minnstate.edu) — ✅ BUILT & SHIPPED July 8, 2026 (33 schools, 394->427)
One public search serves all 33 MN State colleges/universities. Verified live July 8, 2026.
Adapter: `MinnState` class + `_MINNSTATE` table in schools.py; all 33 verified through the
PRODUCTION fetcher (live sections at every campus; list-status cross-checked against
detail-page Size/Enrolled/Remaining at 3 campuses, 6/6 agree). Corrections vs the recipe
below, verified live: for the 3 multi-campus colleges the rcid-tail campusid renders an
UNBRANDED page — shipped the branded campus ids instead (Anoka-Ramsey 0152->141,
Southeast 0213->260, South Central 0309->270). Term auto-rolls via refresh_all_terms
(yrtr parsed from the form's own select + verified against live data before adoption).
Oregon Coast CC (0330, also hosted here) has no working public page — excluded.

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

## Colorado CCS (selfservice.cccs.edu) — ✅ BUILT & SHIPPED July 8, 2026 (13 colleges, 454->467)
ONE Banner 9 host, mepCode per college — same class of leverage as CUNY/ctcLink/MinnState/VCCS.
Adapter: `CCCS(Banner)` + 13 subclasses; verified mepCodes: ACC CCA CCD CNCC FRCC LCC MCC NJC
OJC PCC PPCC(->brand PPSC) RRCC TSJC(->brand TSC). Safe-probe note: this host fails LOUDLY on
bad codes (MepCodeNotFoundException) unlike ctcLink/VCCS, and every accepted code was ALSO
identity-verified against live campusDescription prefixes. Colorado common course numbering:
ENG 1021 works as the example at all 13. Term 202720 = Fall 2026 systemwide, auto-rolls.
SIDE FIX shipped with it: `Banner.fetch` now PAGINATES searchResults (was silently capped at
100 rows/course — FRCC ENG 1021 has 129 sections; watched sections past row 100 could never
alert at ANY Banner school). Fail-closed: if totalCount can't be fully read, skip the course.
Old erpdnssb.cccs.edu (Banner 8) is dead/unreachable — selfservice.cccs.edu is the live host.


## IPEDS-sourced schools — ✅ BUILT & SHIPPED July 8 2026: 60 of 78 added (469->529)
Gate results (every school through the PRODUCTION fetcher; examples from each school's own
search API; raw section-collapse screen; latency cut >30s):
- Banner 29/34 added. EXCLUDED: UNC Charlotte (already live as `uncc` — dedup miss),
  Drake (re-cut at 136.8s — same cold-start as original cut), Morehouse College,
  NMSU, Wilkes, Central Carolina Tech, South Texas, Virginia State, Middlebury (term
  picker lands on MIIS grad entity), Blackhawk Tech, Waukesha County Tech (subject
  catalogs return numeric codes / seats hidden — adapter-incompatible without rework).
- Colleague 22/29 added. EXCLUDED: Victor Valley, Colorado Mountain, Columbia MO,
  Campbell (term-filtered fetch empty / counts unpublished), Loras (dotted subjects),
  Southwestern TX (numbering), Washington Adventist (unreachable).
- Fose 3/3 added (UArk, SLU, South Carolina).
- CA districts 6/6 added via new `CACCD(Banner)` subclass — CA letter-prefixed course
  numbers (ENGL A101 / B1A) need a district-only _code override; campus-token isolation
  verified by full ENGL pagination on both hosts (Orange/Golden/Coastline, BC/CC/Porterville).

## Original handoff (for reference) — READY TO BUILD

Source: US Dept. of Education IPEDS public directory (public domain, no legal exposure — Coursicle was NOT used as a data source, only as approach confirmation). Every school below was verified LIVE Fall 2026 through the PRODUCTION adapter's own term-picker. Deduplicated against schools.py at time of writing. Each must still clear the section-collapse accuracy screen at add time.


### Banner adapter — 34 schools (host + term auto-detected)

- College of the Sequoias (CA) — `banweb.cos.edu`
- University of California-Merced (CA) — `reg-prod.ec.ucmerced.edu`
- University of the Pacific (CA) — `reg-prod.ec.pacific.edu`
- University of the District of Columbia (DC) — `reg-prod.ec.udc.edu`
- Morehouse College (GA) — `reg-prod.ec.morehouse.edu`
- Morehouse School of Medicine (GA) — `reg-prod.ec.msm.edu`
- Savannah College of Art and Design (GA) — `ssb.scad.edu`
- Drake University (IA) — `registrationssb.drake.edu`
- Bethel University (MN) — `banner.bethel.edu`
- Northwest Missouri State University (MO) — `banprod.nwmissouri.edu`
- University of North Carolina at Charlotte (NC) — `selfservice.charlotte.edu`
- Northeast Community College (NE) — `reg-prod.ec.northeast.edu`
- New Mexico State University-Main Campus (NM) — `banner.nmsu.edu`
- Alfred University (NY) — `banweb.alfred.edu`
- Fashion Institute of Technology (NY) — `banner.fitnyc.edu`
- Hofstra University (NY) — `xe.hofstra.edu`
- Jamestown Community College (NY) — `banprod.sunyjcc.edu`
- Mohawk Valley Community College (NY) — `banprod.mvcc.edu`
- Rockland Community College (NY) — `banner.sunyrockland.edu`
- SUNY College of Technology at Canton (NY) — `banweb.canton.edu`
- Schenectady County Community College (NY) — `banprod.sunysccc.edu`
- The New School (NY) — `selfservice.newschool.edu`
- Upstate Medical University (NY) — `bannerweb.upstate.edu`
- Wilkes University (PA) — `reg-prod.ec.wilkes.edu`
- Central Carolina Technical College (SC) — `ssb.cctech.edu`
- Presbyterian College (SC) — `banprod.presby.edu`
- Prairie View A & M University (TX) — `myssb.pvamu.edu`
- South Texas College (TX) — `registration.southtexascollege.edu`
- Virginia State University (VA) — `reg-prod.ec.vsu.edu`
- Middlebury College (VT) — `reg-prod.ec.middlebury.edu`
- Gonzaga University (WA) — `xe.gonzaga.edu`
- Pacific Lutheran University (WA) — `banweb.plu.edu`
- Blackhawk Technical College (WI) — `reg-prod.ec.blackhawk.edu`
- Waukesha County Technical College (WI) — `reg-prod.ec.wctc.edu`

### Colleague adapter — 29 schools (term auto-detected)

- College of the Desert (CA) — `ss.collegeofthedesert.edu`
- Victor Valley College (CA) — `selfservice.vvc.edu`
- Colorado Mountain College (CO) — `selfservice.coloradomtn.edu`
- University of Guam (GU) — `selfservice.uog.edu`
- Loras College (IA) — `selfservice.loras.edu`
- Simpson College (IA) — `ss.simpson.edu`
- Kankakee Community College (IL) — `selfservice.kcc.edu`
- Midway University (KY) — `ss.midway.edu`
- Washington Adventist University (MD) — `ss.wau.edu`
- Wor-Wic Community College (MD) — `selfservice.worwic.edu`
- Delta College (MI) — `ss.delta.edu`
- Columbia College (MO) — `selfservice.ccis.edu`
- William Jewell College (MO) — `ss.jewell.edu`
- Campbell University (NC) — `ss.campbell.edu`
- James Sprunt Community College (NC) — `ss.jamessprunt.edu`
- Lees-McRae College (NC) — `selfservice.lmc.edu`
- Lenoir Community College (NC) — `ss.lenoircc.edu`
- Piedmont Community College (NC) — `ss.piedmontcc.edu`
- Sampson Community College (NC) — `ss.sampsoncc.edu`
- Southwestern Community College (NC) — `ss.southwesterncc.edu`
- Daemen University (NY) — `selfservice.daemen.edu`
- Eastern Oklahoma State College (OK) — `ss.eosc.edu`
- Southeastern Oklahoma State University (OK) — `selfservice.se.edu`
- Western Oklahoma State College (OK) — `selfservice.wosc.edu`
- Holy Family University (PA) — `selfservice.holyfamily.edu`
- Montgomery County Community College (PA) — `selfservice.mc3.edu`
- Southwestern University (TX) — `selfservice.southwestern.edu`
- Westminster University (UT) — `ss.westminstercollege.edu`
- Western Wyoming Community College (WY) — `selfservice.westernwyoming.edu`

### Fose adapter — 3 schools

- University of Arkansas (AR) — `classes.uark.edu` srcdb=1269 (api=https://classes.uark.edu/api/?page=fose&route=search)
- Saint Louis University (MO) — `courses.slu.edu` srcdb=202710 (api=https://courses.slu.edu/api/?page=fose&route=search)
- University of South Carolina-Columbia (SC) — `classes.sc.edu` srcdb=202608 (api=https://classes.sc.edu/api/?page=fose&route=search)

### USG Georgia (shared gabest Banner, term=202608, ex 'ENGL 1101') — 6 schools

- Abraham Baldwin Agricultural College (GA) — `abac.gabest.usg.edu`
- Atlanta Metropolitan State College (GA) — `atlm.gabest.usg.edu`
- College of Coastal Georgia (GA) — `ccga.gabest.usg.edu`
- Dalton State College (GA) — `daltonstate.gabest.usg.edu`
- Gordon State College (GA) — `gordon.gabest.usg.edu`
- South Georgia State College (GA) — `sgsc.gabest.usg.edu`

### California districts (Banner, campus= filter, term=202670) — 2 hosts = 6 colleges

- Coast CCD — `reg-prod.ec.cccd.edu` → Orange Coast, Golden West, Coastline
- Kern CCD — `reg-prod.ec.kccd.edu` → Bakersfield (BC), Cerro Coso (CC), Porterville

**TOTAL: 78 net-new verified schools → 469 to 547.**

Still in progress (separate): CT-log (certspotter) discovery over the ~2,580 schools that matched no hostname pattern — finds hidden registration hosts. Results appended when complete. KCTCS confirmed DEAD (stale May-5 snapshot, 4/4 delta checks zero movement — do not add).
### Technical-college sweep (TCSG 22 + SCTCS 16) — result: 2 net-new
Probed all 38 Georgia + South Carolina technical colleges by domain. Most are login-gated
or on non-guessable hosts. SC TRAC (sctrac.org) confirmed a TRANSFER/ARTICULATION catalog
(no live seats — like Colorado courseleaf, do NOT use). No shared TCSG/SCTCS Banner host exists.
Only 2 with open guest Banner search, both verified live:
- North Georgia Technical College (GA) — `banner.northgatech.edu`
- Piedmont Technical College (SC) — `banner.ptc.edu`

### University of Illinois Urbana-Champaign — ✅ BUILT & SHIPPED July 8 2026 (528->529)
Public "Course Explorer" (courses.illinois.edu), fully guest-accessible, server-rendered HTML
(no login, no AJAX API — confirmed via manual DevTools Network inspection, 0 relevant XHR
requests fired; page is plain HTTP-rendered). robots.txt allows the /schedule/ path we need
(only disallows /cisapp/, /cisdocs/, /search/, /user/, PDFs). Page text confirms
"Section Status updates every 10 minutes" — live data, matches accuracy bar.

URL pattern: `https://courses.illinois.edu/schedule/{year}/{term}/{SUBJECT}/{NUM}`
  e.g. https://courses.illinois.edu/schedule/2026/fall/AE/100
Subject list per term: `https://courses.illinois.edu/schedule/{year}/{term}` (table of ~185 subject codes)
Section status field: `<dt>Availability:</dt><dd>{status}</dd>` per CRN/section.

Status enum (from page's own legend): Closed, Open, Open (Restricted), Pending, Unknown.
Cross-listed sections render as "CrossListOpen (Restricted)" (concatenated, no space).
TRUE-OPEN RULE: status contains "Open" AND does not contain "Closed" → open.
Treat Pending/Unknown as NOT open (conservative — never-false-alert rule).

NOTE: UIC (Chicago) and UIS (Springfield) do NOT use this system — checked, different platform,
not yet identified. This is UIUC only. Still a strong single add given its size.

New `UIUC` class in schools.py. Fixed one real bug caught during the gate: the naive
term picker computed delta-months wrong and resolved "2026/summer" (an in-progress term)
instead of "2026/fall" while mid-Fall-registration — since refresh_all_terms() runs daily
and adopts ANY term that returns data (not just the RIGHT term), this would have silently
mis-pointed the school at the wrong semester. Rewrote resolve_term() to use the same
delta>=1-skip-in-progress logic as every other adapter's term picker. CRNs are paired
with their own row's Availability status (not by parallel-list order, which would
silently misalign on a missing field); verified with a synthetic duplicate-CRN test that
the collapse guard actually fires. Live-verified: CS 101 (18 sections), CS 225
cross-listed (12 sections, "CrossListOpen (Restricted)" correctly read as open).

### Banner auto-discovery sweep #2 (univ-domains dataset, 2103 uncovered US domains) — 9 verified → sent to builder July 8 2026
Method: pulled the open Hipo university-domains dataset (2348 US institutions), excluded
all base domains already referenced in schools.py, then for each remaining domain probed
13 common Banner host patterns (registrationssb./banner./ssb./xe./myssb./banprod./
reg-prod.ec./ssb-prod.ec./banweb./bannerssb./ssbprod./selfservice./register.). Every
candidate host was VERIFIED end-to-end (guest term lookup → school's own subject list →
class search → confirm integer seatsAvailable) AND latency-screened (full fetch <2.5s;
Drake-style 137s hosts auto-cut). 40-worker concurrent probe. Only hosts passing BOTH
accuracy (real live counts) and efficiency (latency) gates were kept.

Verified NET-NEW (deduped vs every .edu domain in schools.py incl. cut-notes):
- Southern New Hampshire University — reg-prod.ec.snhu.edu (202687, ex "ACC 550") 1.0s
- DeVry University — reg-prod.ec.devry.edu (202720, ex "ACCT 207") 1.1s — multi-campus, check dup rows
- Touro College (NY) — reg-prod.ec.touro.edu (202670, ex "BSNV 453") 0.9s
- Lafayette College (PA) — selfservice.lafayette.edu (202550, ex "AFS 330") 0.8s
- Concordia College–Moorhead (MN) — banner.cord.edu (202609, ex "ANUR 425") 1.5s
- Southern Oregon University — reg-prod.ec.sou.edu (202504, ex "ARTH 205") 2.4s
- Massasoit Community College (MA) — banner.massasoit.mass.edu (202710, ex "ACCT 104") 1.6s [CC]
- Waukesha County Technical College (WI) — reg-prod.ec.wctc.edu (202710, ex "101 105") 1.0s [tech; numeric subj]
- Blackhawk Technical College (WI) — reg-prod.ec.blackhawk.edu (202702, ex "101 111") 1.7s [tech; numeric subj]

PARSE GOTCHA (accuracy-critical): WCTC & Blackhawk use purely numeric subject codes
("101"). Banner._code() regex requires subject to start with a letter, so "101 105"
won't parse → school silently returns nothing. Widen regex or skip those two.

Deduped OUT (already covered / already cut): Rutgers (banweb.rutgers.edu; have
classes.rutgers.edu), Prairie View A&M (built), Drake (CUT 137s latency).

Yield note: 9/2103 is modest — this dataset skews small private colleges, many login-
gated or on non-guessable hosts, and only Banner was probed. Biggest remaining levers to
1k = shared multi-school system hosts (state PeopleSoft/Banner pools) + Colleague sweep.

## Handoff batch 2 (9 Banner schools) — ✅ BUILT July 8 2026: 8 of 9 added (529->537)
- ADDED via new `CrnKeyedBanner(Banner)`: SNHU, DeVry, Concordia-Moorhead, Touro, SOU —
  ALL five zero out sequenceNumber on every row (would collapse all sections into one
  key). Touro/SOU passed the naive gate only because their example courses had a single
  section — multi-section probe exposed it. Keyed by CRN (unique per term, verified;
  it's what their students register with). New `Banner._seckey()` hook keeps the base
  class byte-identical for all existing schools (gatech regression-checked).
- ADDED via new `NumericSubjectBanner(Banner)`: WCTC + Blackhawk (purely numeric
  subject codes, e.g. subject '101'; space-separated parse, exact-match protected).
- ADDED plain: Massasoit.
- CUT: Lafayette College — EVERY guest-visible term incl. the newest ('Summer II
  2026') is '(View Only)' archive data; a fetch 'passing' on it is the false-freshness
  trap, not live seats. Do not re-add without evidence of a live guest term.
- DeVry multi-campus check: single 'Online' campusDescription on probe; CRN keying
  makes cross-campus collisions structurally impossible anyway.

### ACCS shared-host MEP expansion + East Georgia — 16 sent to builder July 9 2026 (537→553)
Alabama Community College System: shared Banner host reg-prod.ec.accs.edu, schools keyed
by MEP code (existing adapter). Had 9/24; discovered + verified the other 15 by guessing
MEP codes and CONFIRMING each mapping via Banner campusDescription vs the college's real
geography (not assuming the abbreviation). Applied builder's full gate: term-freshness
(skip "(View Only)" archive terms), zero-seq (2+ section course, distinct sequenceNumber),
numeric-subject. See [[seatwatch-banner-verification-gate]].

KEY FINDING: ACCS pervasively returns sequenceNumber="0" (mixes zero-seq & real-seq even
within one college) → MUST key by courseReferenceNumber (CrnKeyedBanner). Confirmed CRNs
distinct on zero-seq courses (NWSCC ART 100: 13 sections all seq=0, 13 distinct CRNs).
9/15 definitively fail plain-seq; recommended CRN for all 15. ALSO flagged: existing 9
ACCS schools (plain Banner) have a LIVE latent collapse bug on zero-seq multi-section
courses — recommended migrating them to CrnKeyedBanner too.

15 new ACCS (mep / confirmed location): JSCC Shelby-Hoover, LAWSON Bessemer, LBWCC
Andalusia, NWSCC Muscle Shoals, TSCC Patterson, WCCS Demopolis, BSCC Jasper-Sumiton,
ESCC Enterprise-Ozark, SNEAD Boaz, ISTC Draper-Fountain(prison), CACC AlexCity-Childersburg,
DRAKE Huntsville, MMI Marion, NACC Rainsville, WSCC Hanceville.
+1: East Georgia State College — ega.gabest.usg.edu (202605) — last missing USG-cluster school.

DIRECTION NOTE (Nathan, July 9): prefers 4-YEAR universities going forward even though they
come one-at-a-time (shared-host bulk wins are almost all community-college systems). Approved
this CC batch for the bulk, but next sweeps should target 4-year institutions.

## Handoff batch 3 (15 ACCS + East Georgia) — ✅ BUILT July 8 2026: 16/16 added (537->553)
ALL 15 new ACCS colleges shipped as CRN-keyed (ACCS._seckey -> courseReferenceNumber).
CRITICAL LIVE BUG the handoff flagged, CONFIRMED and FIXED: the 9 originally-shipped
ACCS colleges were sequence-keyed on a system that MIXES zero-seq and real-seq courses —
Southern Union HIS 101 had 23 live sections collapsing into ONE key ('0'x23); Wallace-
Dothan MTH 116 likewise. All 9 migrated to CRN keying; post-fix suscc HIS 101 correctly
shows 23 sections. ⚠️ MIGRATION NOTE: section keys on those 9 schools CHANGED (e.g. '01'
-> '12482'), so any pre-existing watch pinned to an old-style section on cvcc/wcc-al/
gscc/sscc/calhoun/suscc/bishop/coastal-al/reid is now unmatchable and must be re-created
— production watches.db must be checked at deploy time (query in the deploy handoff).
East Georgia (ega) added plain-Banner on gabest (term 202605 live; standard seqs but
verified through the gate like everything else). 25/25 gate pass incl. all 9 migrations.

### 4-year sweep (IPEDS HD2023, 2262 uncovered 4-year domains) — Banner + Colleague — 13 sent to builder July 9 2026 (~553→566)
Pulled IPEDS HD2023 (ICLEVEL=1 → 2830 four-year institutions w/ web addr; 2262 uncovered
after deduping every .edu in schools.py). Ran TWO sweeps over them: Banner
(/StudentRegistrationSsb) and Colleague (/Student/Courses public JSON). 40-worker concurrent,
full gate (term-freshness, zero-seq for Banner, dedup). See [[seatwatch-banner-verification-gate]].

Banner: only 4 raw hits, 1 usable — most 4-years aren't on guessable Banner hosts.
  ✅ UNC Charlotte (selfservice.charlotte.edu, 202680) — 30k public, clean.
  ✗ Bryant&Stratton (all terms View Only — archive trap, like Lafayette), North Orange County
    (community college + seats=999 sentinel), Lafayette (already cut).
Colleague: 12 hits, all net-new 4-years (KEY LEARNING: private 4-years mostly run COLLEAGUE,
not Banner — the Banner-only sweep missed them entirely; Colleague uses a different API so
needs its own probe). Sent 11 clean + Vermont conditional:
  Sacred Heart (colleague.sacredheart.edu), Thomas Edison State (selfservice.tesu.edu),
  Campbell (ss.campbell.edu), Southwestern TX (selfservice.southwestern.edu), College of Idaho
  (selfservice.collegeofidaho.edu), Northwestern Oklahoma State (selfservice.nwosu.edu),
  DigiPen (selfservice.digipen.edu), Loras (selfservice.loras.edu ⚠️dotted subj "L.ENG"),
  Washington Adventist (ss.wau.edu), Columbia College MO (selfservice.ccis.edu),
  Colorado Mountain (selfservice.coloradomtn.edu).
  CONDITIONAL: Vermont State Colleges (selfservice.vsc.edu) = VTSU (4-yr) + CCV (CC) on ONE
  Colleague instance, split by term-prefix ("VTSU …"/"CCV …"). Needs a term-prefix filter to
  separate; build only if accuracy+efficiency hold, else skip (mixing = cross-inst false alerts).

⚠️ README RECONCILE: the earlier "Colleague adapter — 29 schools" ready-to-build list here
OVERCOUNTED — Loras, Washington Adventist, Columbia College, Campbell, Southwestern, Colorado
Mountain were listed but never built into schools.py (0 code refs). Now handed off for real.

REMAINING LEVERS to 1k: private 4-years on Colleague Ellucian-CLOUD hosts
({code}-ss.colleague.elluciancloud.com) can't be guessed by domain (need the code) — a
different discovery path. Also PeopleSoft 4-years (big publics) untouched by these two sweeps.

## Handoff batch 4 (13 four-year candidates + VSC conditional) — ✅ BUILT July 8: 11 added (553->564)
ADDED: Sacred Heart, Washington Adventist, College of Idaho, DigiPen, Campbell
(AbbrevTermColleague: FA/SP/SU season abbreviations — base picker was choosing a term
13 months out), Loras (DottedColleague: 'L.ENG' subjects), Columbia MO (DigitTermColleague:
'Fall 16-Week, 2026/2027' terms — base picker was choosing Summer 2028/2029), NWOSU
(SynthTermColleague: host publishes EMPTY ActivePlanTerms; synthesize 'Fall 2026' format,
verified against real fall sections), Southwestern TX (AlnumSubjectColleague: 'HIS16 034'
digit-bearing subjects), and BOTH Vermont schools via VSC term-prefix isolation — VTSU +
CCV on one host, picker sees only own-prefix terms, verbatim term match excludes the other
institution structurally; proven live (same course code -> 31 vs 34 sections, 0 key overlap).
CUT: UNC Charlotte (SECOND dup handoff — already live as `uncc`; selfservice.charlotte.edu
is the rebranded domain for the same school, add it to the dedup list), TESU (monthly
rolling terms, no season semantics — poor seat-watch fit, do not re-hand-off).
HOLD: Colorado Mountain — picker correctly chooses '2026 Fall' but fall sections aren't
loaded yet (only Spring/Summer 2026 exist); re-gate when fall loads, likely a clean add.

### Batch 4 outcome (builder, July 9 2026): 11/13 shipped → 564. Exclusions to honor:
- UNC Charlotte = DUPLICATE of existing `uncc` (selfservice.uncc.edu). selfservice.charlotte.edu
  is the SAME school's rebranded domain. LESSON: dedup by INSTITUTION, not just base domain —
  schools rebrand domains. Both uncc.edu + charlotte.edu now excluded.
- Thomas Edison State Univ (tesu.edu) = CUT permanently — monthly rolling terms ("July 2026"…),
  open-enrollment online model doesn't fit seat-watching. Do NOT re-hand-off.
- Colorado Mountain (coloradomtn.edu) = HOLD — term picker correctly picks "2026 Fall" but the
  college hasn't loaded fall sections yet (only Spring/Summer). Re-verify in a few weeks; likely
  clean then (same as East Georgia earlier, which loaded and shipped).
Round-2 flags all landed: Campbell/Loras/Columbia-MO/Southwestern/NWOSU + both Vermont shipped
via contained subclass fixes (FA/SP abbrevs, dotted subjects, digit-bearing terms/subjects,
empty ActivePlanTerms, term-prefix isolation for VSC). Live count now 564.
DEDUP-EXCLUDE going forward: uncc.edu, charlotte.edu, tesu.edu (cut), coloradomtn.edu (hold).

### Expanded Colleague sweep (Ellucian-cloud pattern) — 38 four-year sent to builder July 9 2026 (564→~602)
Re-swept the 2249 remaining IPEDS 4-years with EXPANDED Colleague host patterns — the key
add was the Ellucian-CLOUD host `{school-label}-ss.colleague.elluciancloud.com`, which the
first sweep (selfservice./ss. only) completely missed. That one pattern is where private
4-year colleges live: 40 raw hits (vs 12 first sweep). After dedup (Loyola NO already built)
and the term-freshness gate (cut Southwestern Law = rolling/non-seasonal terms like TESU):
38 sent — 32 four-year universities (incl 6 HBCUs: Miles, Edward Waters, Fisk, Le Moyne-Owen,
Huston-Tillotson, Lincoln-MO + Lincoln-PA), 3 specialized graduate (McCormick/SEBTS seminaries,
Brooklyn Law), 3 community/tribal (Weatherford, Lac Courte Oreilles, American Samoa=HOLD no-Fall).
Flags to builder: Kean Univ has a Wenzhou CHINA branch (cross-inst isolation check like VSC);
Mercer/Aurora/St.Thomas have 26-62 sub-terms (verify _pick_term); Lincoln-PA probe example
"MAT LAB" has no digit (won't parse — use normal course); two distinct Lincoln Universities.

METHOD LEVERAGE for future sweeps: the {label}-ss.colleague.elluciancloud.com pattern is the
single highest-yield Colleague discovery vector for private 4-years. Also worth a follow-on:
Banner Ellucian-cloud hosts likely have an analogous {label}.elluciancloud.com pattern.

## Handoff batch 5 (38 Ellucian-Cloud Colleague) — ✅ BUILT July 8: 34 added (564->598)
Your Kean flag was even sharper than stated: base fetch uses SUBSTRING term matching, so
'Fall 2026' would have matched 'Fall 2026 Wenzhou' and leaked China-campus sections into
US results (VSC was safe only because its prefixes break substring containment). Kean
shipped via new ExactTermColleague (equality match). Lincoln MO needed
ShortYearTermColleague ('FA 26 Semester' — abbreviated seasons + 2-digit years; base
picker chose a 2029 term). Chaminade's timeout was transient (retried clean). 32 others
plain 4-line adds incl. all 6 HBCUs, Brooklyn Law, Weatherford, LCO Ojibwe. 34/34
final regression.
SCRAPPED: McCormick Seminary, SEBTS (no sections in picked terms — niche grad calendars).
HOLD (revisit when fall loads): Aurora University, American Samoa CC — same category as
Colorado Mountain.

### Batch 5 outcome (builder, July 9 2026): 34/38 shipped → 598. Findings:
- Kean: substring term-match would've leaked "Fall 2026 Wenzhou" (China branch) into US results —
  shipped via ExactTermColleague (equality). LESSON: multi-entity host marker as PREFIX (VSC
  "CCV …") → prefix-filter OK; as SUFFIX ("… Wenzhou") → base substring match LEAKS, needs exact.
- Lincoln-MO: "FA 26 Semester" abbreviated-season + 2-digit-year terms; base picker chose 2029 →
  shipped via ShortYearTermColleague.
- SCRAPPED (do NOT re-hand-off w/o verified live-section example in primary term): McCormick
  Theological Seminary, SEBTS — niche grad calendars, no sections in picked term.
- HOLD/revisit (fall not loaded yet, likely clean in weeks): Aurora University, American Samoa CC
  — add to revisit list with Colorado Mountain (+ East Georgia already shipped when it loaded).
- Shipped clean: all 6 HBCUs, Brooklyn Law, Weatherford, LCO Ojibwe. Worst latency 7.6s (Ashland).
Live count now 598 (session start was 529).

REVISIT LIST (recheck when fall sections load): Colorado Mountain (coloradomtn.edu), Aurora
University (aurora-ss.colleague.elluciancloud.com), American Samoa CC (amsamoa-ss.colleague.elluciancloud.com).

### Batch 6 sent (July 9 2026): 4 four-year universities + 28 community colleges = 32 in one batch
4-YEAR (Banner Ellucian-cloud reg-prod.{code}.elluciancloud.com — NEW vein, code==domain label):
Georgetown, Ole Miss (⚠️winter-intersession term trap), U Central Oklahoma, Eastern Oregon. All
gated live Fall 2026, distinct seq, identity-confirmed. This is the highest-value 4-year vein found.

CC (volume, IPEDS 2-year via {label}-ss.colleague + reg-prod.{label} cloud patterns): 20 clean +
8 flagged. Flags: Helena College & Metro-KC = Banner (plain); Indian Hills = short-year terms;
South Piedmont/Robeson = CODED terms ("2026FA"); Florence-Darlington = week-module; Western
Technical & Nicolet (WI) = NUMERIC subject codes (need numeric-subject Colleague variant).
IDENTITY TRAP caught: "Ashland Community & Technical College" derived host collided onto Ashland
UNIVERSITY's ashland-ss instance (identical data) — dropped. LESSON: {label}-ss cloud hosts can
collide when two schools share a domain label; always host-dedup + identity-check.
DEFER (no guest ActivePlanTerms): Columbus State CC (cscc.edu, 46k — worth a manual recheck), Pitt CC.

KEY DISCOVERY (reusable): Banner Ellucian-cloud = reg-prod.{code}.elluciancloud.com/StudentRegistrationSsb
(code usually == domain first-label). Colleague Ellucian-cloud = {label}-ss.colleague.elluciancloud.com.
These two cloud patterns are the highest-yield SIS discovery vectors found this session.

## Handoff batch 6 (32 schools) — ✅ BUILT July 8: 31 added (598->629)
Universities: Georgetown, Ole Miss (your intersession flag: the production term-picker
correctly chose full-Fall 202710 over the newest 202720 Winter Intersession — _SUBTERM
already excludes 'intersession'; only the example was dead, discovery found ENGL 2220
w/ 48 sections), UCO, Eastern Oregon. CCs: 25 incl. Helena/MCC-KC (Banner) and 23
Colleague. Two NEW reusable Colleague variants shipped: CodedTermColleague ('2026FA'
NC-style term codes — SPCC + Robeson) and NumSubjColleague ('804 123' WI numeric
subjects — Western TC + Nicolet); Indian Hills + Florence-Darlington ride the existing
ShortYearTermColleague ('Fall Term 26' / 'Fall 26-27 15-WK Term').
SCRAPPED PERMANENTLY: Victor Valley — course search serves ARCHIVE sections (Spring
2024) while advertising Fall 2026 terms; false-freshness, third failed gate. Do not
re-hand-off.
31/31 final regression; median ~1.6s, worst 5.8s (Nicolet).

### Batch 6 outcome (builder, July 9 2026): 31/32 shipped → 629. +235 schools today. Findings:
- All 4 universities shipped (Georgetown, Ole Miss, UCO, Eastern Oregon). Ole Miss intersession
  handled by production term-picker (excludes 'intersession', chose full Fall 202710).
- LESSON (refine gate): verify the EXAMPLE course itself has 2+ LIVE sections in the target term,
  not just that the term exists. My Ole Miss ex BISC 3800 had 0 live sections; discovery swapped to
  ENGL 2220 (48 sec). Going forward, pick examples that are large/guaranteed (ENGL/MATH 101-level).
- VICTOR VALLEY (selfservice.vvc.edu) = SCRAP PERMANENTLY. Returns ARCHIVE sections (Spring 2024)
  while advertising Fall 2026 in ActivePlanTerms — false-freshness like Lafayette. 3rd failed gate.
  DecimalColleague variant (for '101.0' numbering) works, but underlying data is stale. Do NOT re-add.
- New reusable builder variants now exist (future schools with these = 4-line adds):
  NumSubjColleague (numeric subjects: Western Tech, Nicolet), CodedTermColleague ('2026FA' terms:
  Robeson, South Piedmont), ShortYearTermColleague ('Fall Term 26', 'Fall 26-27 15-WK'), DecimalColleague,
  ExactTermColleague (suffix branch isolation e.g. Kean/Wenzhou), plus CrnKeyedBanner + NumericSubjectBanner.
PERMANENT-CUT list (never re-hand-off): Lafayette (archive), TESU (rolling monthly), Victor Valley
(archive), Bryant&Stratton (View Only), McCormick Sem + SEBTS (no sections in primary term).

### Batch 7 sent (July 9 2026) — BIG-PUBLIC CLASSIC-PEOPLESOFT UNLOCK + Winthrop/Guilford
THE highest-leverage 4-year vein. Big public flagships use neither Fluid IScript, Banner, nor
Colleague — they run the CLASSIC PeopleSoft guest class search, component
COMMUNITY_ACCESS.CLASS_SEARCH.GBL. It's the STOCK component (identical fields every school), so
ONE classic-PS adapter (VCCS is the template) unlocks the whole segment. Reverse-engineered the
flow: entry Page=SSR_CLSRCH_ENTRY, results SSR_CLSRCH_RESULT; fields CLASS_SRCH_WRK2_INSTITUTION/
STRM + SSR_CLSRCH_WRK_SUBJECT_SRCH/CATALOG_NBR; search ICAction=CLASS_SRCH_WRK2_SSR_PB_CLASS_SRCH;
stateful ICSID/ICStateNum. Authoritative Open/Closed/Waitlist status per section (read 'Open' only,
seats=None, like Fose/VT). NAU's ?search=true GET returns the FORM not results — needs the POST flow.

14 VERIFIED guest-accessible (guest=YES, confirmed): Penn State (public.lionpath.psu.edu/CSPRD),
UCF (csprod-ss.net.ucf.edu/CSPROD), FIU (pslinks.fiu.edu/cslinks), Houston (saprd.my.uh.edu/saprd),
Washington State (pub.my.wsu.edu/wsucsprd), UConn (student.studentadmin.uconn.edu/CSGUE), Northern
Arizona (peoplesoft.nau.edu/ps92prcs, inst=NAU00), UMKC (access.umkc.umsystem.edu/prdpa), Missouri
S&T (access.joess.mst.edu/prdpa), Central Washington (cwucsprd.peoplesoft.cwu.edu/cwucsprd), Northern
Iowa (sis.uni.edu/cssprd), UW-Stout (uwstout.sis.wisconsin.edu/stoprd-tb), Salisbury (gullnet.salisbury.edu/
csprdguest), Rhode Island College (pscs.ric.edu). Excluded OSU (already live, also on this system).

SHARED-SYSTEM MULTIPLIERS to roster once adapter proven: UW System (sis.wisconsin.edu — many UW
campuses), U Missouri System (umsystem.edu 'prdpa' — Mizzou/UMSL/UMKC/S&T). Potentially 20+ more.

Also sent Part D: Winthrop (prod-ssb.winthrop.edu) + Guilford (ssbp.guilford.edu) — plain Banner, gated.
STATUS: build request; roster is guest-verified but seat-scrape flow is the builder's to build.

### Pre-roster (HELD, not yet sent) — shared-system big publics for the classic-PS adapter, July 9 2026
Built while batch-7 classic-PS adapter awaits builder feasibility check. All verified guest=YES on
COMMUNITY_ACCESS.CLASS_SEARCH.GBL. Send as an ADD-ON to batch 7 once the classic adapter is proven.

UW SYSTEM (6 new; UW-Stout already in batch 7) — host www.{sub}.sis.wisconsin.edu, site {code}prd-tb:
- UW-La Crosse      uwlax   psp/lacprd-tb/EMPLOYEE/SA
- UW-Eau Claire     uwec    psp/eauprd-tb/EMPLOYEE/SA
- UW-Whitewater     uww     psc/wtwprd-tb/EMPLOYEE/SA
- UW-Stevens Point  uwsp    psp/stpprd-tb/EMPLOYEE/SA
- UW-Platteville    uwplatt psc/pltprd-tb/EMPLOYEE/SA
- UW-Oshkosh        uwosh   psp/oshprd-tb/EMPLOYEE/SA
  (UW-Milwaukee/Green Bay/Parkside/River Falls/Superior = separate hosts/systems, not on shared
   sis.wisconsin.edu classic pattern — deferred.)

U MISSOURI SYSTEM (2 new; UMKC + Missouri S&T already in batch 7) — site prdpa:
- Mizzou / U Missouri-Columbia  access.myzou.missouri.edu   psc/prdpa/EMPLOYEE/SA  (~31k flagship)
- UMSL / U Missouri-St. Louis   access.myview.umsl.edu      psp/prdpa/EMPLOYEE/SA

TOTAL pre-rostered: 8 more big-public campuses (on top of batch-7's 14). Classic-PS adapter unlocks
all of them. Held pending builder feasibility verdict + Nathan's go-ahead to send.

## Handoff batch 7 (classic-PS flagships + 2 Banner) — PARTIAL: 2 added, Part A/B SCRAPPED (628->630)
Part D shipped clean: Winthrop University, Guilford College (plain Banner, real seatsAvailable).
Part A/B (classic-PeopleSoft COMMUNITY_ACCESS.CLASS_SEARCH.GBL — Penn State/UCF/Houston/UConn/
NAU/... 14 flagships) SCRAPPED after live investigation — TWO independent disqualifiers:
1. STATUS IS NOT REAL ON THE GUEST VIEW. Reverse-engineered NAU's full stateful POST flow
   (ICSID/ICStateNum/ICAction, institution=NAU00, strm dropdowns, subject $0 + catalog exact-
   match, open-only unchecked) and parsed it correctly — but NAU shows EVERY section 'Open',
   including 121/121 English sections in the COMPLETED Fall 2025 term. The guest status icon
   defaults to Open; it does not reflect live enrollment. Shipping = false-alert on everything.
   This is the false-open the hard gate exists to prevent.
2. NOT A UNIFORM SINGLE-ADAPTER WIN. The 'stock component' is NOT identical across schools:
   subject field suffix varies (NAU SSR_CLSRCH_WRK_SUBJECT_SRCH$0 vs Houston $1), entry-page
   dropdown HTML/quoting differs (Penn State + UConn didn't parse), node/inst/strm all per-school.
   Each school needs individual reverse-engineering AND its own guest-status-reality proof.
BEFORE ANY RE-ATTEMPT: for a candidate school, run the completed-term test — search a big intro
course (e.g. ENGL) in a FINISHED term; if it shows all-Open, the guest status is fake, skip it.
Only build schools that show real closed/waitlist sections in a done term. Winthrop+Guilford
gated clean via the normal Banner path (real integer seatsAvailable, not this status trap).

### Batch 7 outcome (builder, July 9 2026): Winthrop+Guilford shipped (630); CLASSIC-PS SEGMENT SCRAPPED
⛔⛔ CRITICAL ACCURACY FINDING — classic-PeopleSoft COMMUNITY_ACCESS guest search is a DEAD END:
The builder fully reverse-engineered NAU's classic stateful flow — it WORKS mechanically. But the
GUEST STATUS IS FAKE: NAU shows EVERY section "Open", including 121/121 English sections in the
COMPLETED Fall 2025 term. A finished term is full of closed sections → all-Open means the guest
status icon defaults to Open and does NOT reflect live enrollment. Would fire a false "seat open!"
on every section of every course. Same class as Victor Valley/Lafayette/TESU, bigger.
ALSO: not a uniform adapter — subject field differs per school (NAU SSR_CLSRCH_WRK_SUBJECT_SRCH$0
vs Houston $1; Penn State/UConn parse differently). Each needs individual RE + its own status proof.

MANDATORY TEST before EVER proposing a classic-PS (COMMUNITY_ACCESS.CLASS_SEARCH.GBL) school:
search a big intro course (ENGL) in a COMPLETED term. If ALL sections show "Open" → guest status
is fake → SKIP. Only a school showing real closed/waitlist in a done term is buildable.
Builder suspects the whole guest segment is status-blind. => Batch-7 Parts A/B/C all MOOT, incl the
8 pre-rostered UW/Missouri campuses. DO NOT re-hand-off classic-PS schools without passing this test.
Live count: 630.

### Exhaustive mining sweep (July 9 2026 late) — ALL ANGLES TRIED, 0 net-new. Coverage thorough at 630.
Tried and documented as DEAD/exhausted so future sessions don't re-tread:
- Coursedog: multi-tenant SaaS but public view = CATALOG (course descriptions), NO live seats. Useless.
- Workday Student: course-section reports login-gated; API is SOAP/RaaS (auth). No public scrape.
- Banner 8 (bwckschd.p_get_crse_unsec): older self-service; Purdue's guest search returns no sections
  (moved to Banner 9). Not a live vein where tested.
- Shared state systems: Connecticut CSCU/CT State (reg-prod.ec.ct.edu already covered; the 4 CT State
  Universities SSO/Microsoft-login-gated). Louisiana LCTCS (all 13 colleges miss Banner/Colleague —
  on gated "LoLA"/non-standard host). No new shared bulk found.
- Banner host web-harvest ("StudentRegistrationSsb" search): surfaced ~10 big universities (Georgia
  State, Oklahoma, UC Riverside, Utah State, etc.) — ALL already covered, or login-gated (Clemson 403/SSO).
- CT-log discovery (certspotter): crt.sh is 503-down; certspotter free tier ~10/hr + incomplete cert
  data + reg hosts often don't match keyword filters (Toledo uses "pyxes-prd00.utad.utoledo.edu" — a
  Banner XE internal host, no guest SSB). Very low yield live; set up as a WEEKLY scheduled routine to
  grind slowly over time instead.
CONCLUSION: guessable + accuracy-safe universe is mined out at 630. Remaining uncovered schools are
login-gated, fake-status (classic PeopleSoft), catalog-only, or on hosts even CT-logs don't cleanly
reveal. Scheduled task "seatwatch-hold-and-ctlog-weekly" (Mon 8:37am) now runs HOLD-recheck + a small
CT-log batch weekly and pings ONLY on actionable finds.

### Batch 8 sent (July 9 2026) — Boston University (manual PeopleSoft-Fluid recon) — 1 school
BU (~34k) on the PeopleSoft Fluid guest API (same as UVA/Towson/USM/Palomar). Sent to builder.
  host=public.mybustudent.bu.edu site=BUPRD node=EMPLOYEE inst=BU001 term=2268 example="CASMA 123"
GATE PASSED — real status (CASMA 123: 16 sections mixed Open/Waitlist/Closed w/ real counts; NOT
the fake all-Open classic-PS). BU subject codes college-prefixed (CASMA=CAS Math). Fluid _norm handles it.
METHOD that works for one-at-a-time 4-year grind: web-search "WEBLIB_HCX_CM.H_CLASS_SEARCH...IScript_Main"
to harvest Fluid-guest hosts, then verify institution+term+example via IScript_ClassSearchOptions/ClassSearch.
Most harvested hosts are already covered (UVA/Towson/USM/Palomar/BU) or custom/catalog (IU IGPS=catalog,
no seats; ICC config empty). BU was the net-new win this pass.

## Handoff batch 8 (Boston University) — ✅ BUILT July 8: 1 added (630->631)
PeopleSoft Fluid guest API (same family as UVA/Towson/USM/Palomar). CAS-prefixed
subjects ("CASMA 123" = CAS Math 123) parse fine with the existing generic
PeopleSoft._norm regex. Gate confirmed REAL status before shipping (the batch-7
NAU lesson applied correctly by the research chat): example course has 16 sections
with genuine mixed Open/Waitlisted status and integer seat counts — not the
classic-PS always-Open trap. Term 2268 (Fall 2026) auto-resolves clean.

### Batch 9 sent (July 9 2026) — FOSE BREAKTHROUGH: 3 new flagship/Ivy + critical stale-srcdb bug fix
CRACKED Fose srcdb auto-discovery: the API errors leak the mechanism ({"fatal":"Cannot open database:
fose-clss1269"}) and the school homepage embeds `srcDBs: [{"code":"2267","name":"Fall 2026"...}]`.
Parse that, pick current Fall term → live search works. This is the key that was missing.
⛔ LIVE BUG FOUND: the 9 existing Fose subclasses have HARDCODED stale srcdb (CUBoulder 1269 = dead DB,
current is 2267) and NO auto-refresh → silently broken, no alerts firing. Builder must add srcdb
auto-refresh from homepage srcDBs (repairs all 9 + self-maintains).
3 NEW Fose (all real status A/F/C, Fall 2026): University of Connecticut (classes.uconn.edu, srcdb 1268 —
was SSO-gated on PeopleSoft, Fose is the public way in!), Oregon State (classes.oregonstate.edu, 202701),
University of Pennsylvania (courses.upenn.edu, 202630, Ivy). Host = classes./courses.{domain} so NO identity risk.
Fose sweep over 3231 uncovered (classes./courses./cab./catalog./coursecatalog./sched. + auto-srcdb) = these 3
net-new; prestigious-school probe (Harvard/Princeton/etc) = custom systems, not Fose. Fose vein now mined.
KEY LEARNING: Fose = real-status vein for selective schools; some (UConn) expose Fose publicly even when
their primary SIS is login-gated — worth checking Fose for any gated flagship.

## Handoff batch 9 (fose srcdb + 3 schools) — ✅ PARTIAL July 8: UConn added + auto-roll hardening (631->632)
FACT-CHECK FIRST: the 'URGENT live bug' claim was WRONG — all 9 live fose schools verified
working (CU Boulder's actual srcdb in schools.py is 2267, not the 1269 the research chat
tested; 1269 is UArk's code). No production breakage existed. HOWEVER the design concern was
right: srcdb was hand-pinned per semester and would die silently at rollover. HARDENED: Fose
now auto-rolls srcdb from each host's own srcDBs JS array (verified present on all 11 hosts),
verify-before-adopt, registered in refresh_all_terms. Gate: 11/11 hosts' discovery
independently matched the known-good hardcoded codes; simulated-stale recovery proven
(seeded CU Boulder with dead 1269 -> refresh healed to 2267 -> live sections).
ADDED: UConn (flagship, 199 sections ENGL 1007, real A/F mix; its classic-PS search is
SSO-gated — fose is the guest path).
REJECTED: Penn — FOURTH duplicate-class handoff (already live via bespoke `Penn` adapter).
Oregon State RESOLVED and ADDED (632->633): root cause was the handoff example's subject
code — OSU English is "ENG", not "ENGL". Corrected example ENG 104Z gated clean (4 secs,
real A/F mix); auto-roll verified to skip OSU's 999999 'All Terms' catch-all and pick
202701 Fall 2026. Research chat now greps schools.py by NAME before handoffs (post-Penn).

### Batch 9 CORRECTIONS (builder feedback, July 9 2026):
- "Urgent srcdb bug" was a FALSE ALARM — I tested UArk's code (1269) vs CU Boulder's host; CUB's real
  code is 2267, was fine. NO live breakage. Lesson: grep schools.py before declaring breakage. (The
  srcDBs auto-refresh design was still valid & implemented — self-heal proven.)
- PENN = DUPLICATE (4th dup). Live via bespoke `Penn` adapter (schools.py:701), not on courses.upenn.edu.
  Lesson: DEDUP BY SCHOOL NAME (grep name), not just host/id. Now standard in my process.
- OREGON STATE = valid, my example was wrong: its English subject is "ENG" not "ENGL" (I sent ENGL → 0 rows).
  Corrected: example="ENG 104Z", srcdb=202701. Re-sent to builder. OSU homepage srcDBs starts with
  999999="All Terms" — auto-refresh must pick the Fall-2026 entry (202701), not 999999.
NET real new tonight: BU (631), UConn (632), Oregon State (pending→633), + fose auto-refresh hardening.

### Batch 10 sent (July 9 2026) — UC Irvine WebSoc (NEW SOURCE TYPE, curl-able) + UC-campus leads
UCLA public SOC needs a browser token-flow (couldn't crack headless; Chrome ext blocks navigation).
PIVOTED to UC Irvine "WebSoc" — famous PUBLIC schedule of classes, GET-able, no auth, real status.
  URL: https://www.reg.uci.edu/perl/WebSoc?YearTerm=2026-92&Dept=MATH&Submit=Display+Web+Results
  Fall 2026 = YearTerm "2026-92". HTML table, 17 cells/section row; cell[16]=STATUS (OPEN/FULL/Waitl/
  NewOnly), cell[8]=Max cell[9]=Enr. 'OPEN' only = open (NewOnly = new-students-only = NOT open).
  Verified: MATH 322 rows, real Max/Enr, example "I&C SCI 31". Deduped by NAME (not in schools.py). ~30k.
Needs a small custom WebSoc HTML adapter (like UMD/Rutgers). Sent to builder.
UC-CAMPUS LEADS (status words visible, need param work — NOT handed off): UCSB (my.sa.ucsb.edu/public,
Full/Closed), UCSC (pisa.ucsc.edu, Open), UCSD (act.ucsd.edu/scheduleOfClasses). UC Merced = Banner 8
(xhwschedule). UC Davis = 403. UCLA = browser-token-flow (deferred).
KEY LEARNING: big schools gated/hard on their primary SIS often have a SEPARATE public schedule-of-
classes (UConn→Fose, UCI→WebSoc). Always look for the alt public search, not just the main SIS.

## Handoff batch 10 (UC Irvine WebSoc) — ✅ BUILT July 8: 1 added (633->634)
New bespoke `UCI` adapter for the public WebSoc schedule (plain GET, real Max/Enr counts,
authoritative OPEN/FULL/Waitl/NewOnly status — ONLY 'OPEN' is open; NewOnly seats are
reserved for incoming students). CRITICAL trap found during the gate and closed: WebSoc's
CourseNum filter matches LOOSELY (CourseNum=2A also returns MATH 2AX) — the adapter scopes
rows to the exact course-header block; verified MATH 2A vs 2AX share ZERO section codes.
Sections keyed by UCI's 5-digit enrollment codes. YearTerm auto-rolls from the landing
page's own select (2026-92 = Fall Quarter; Law/Summer/COM screened). Remaining UC leads
(UCSB/UCSC/UCSD param-cracking, UC Merced Banner-8 check) stay with the research chat.

### Batch 11 sent (July 9 2026) — UC Santa Cruz (pisa POST search) + UC pipeline
UCSC ~19k: POST https://pisa.ucsc.edu/class_search/index.php, action=results, binds[:term]=2268 (Fall
2026), binds[:subject]=SUBJ, reg_status=all. Status "Open"/"Closed"/"Wait List" (Open only=open). Verified
term 2268 real mix (24 Open/9 WL/2 Closed); CSE 30 example. Deduped by name. Custom pisa adapter.
UC batch so far: UC Irvine (b10 WebSoc) + UC Santa Cruz (b11 pisa). Leads: UCSB (ASP.NET postback),
UCSD (POST/session), UCLA (browser token). UC Merced=DUP, UC Davis=403.

### Loose-match trap (builder-found on UCI, checked on UCSC) — July 9 2026
WebSoc/pisa-style custom search adapters LOOSE-MATCH course numbers: UCI CourseNum=2A also returns
2AX (suffixed sibling) → a MATH 2A watcher could get 2AX false alerts. Builder fixed UCI by scoping
rows to the exact course-header block. CHECKED UCSC: prefix loose-matches ("11"→11A/11B) BUT exact
full codes are clean ("MATH 11A"→only 11A, "CSE 30"→only 30, no 30X). UCSC safe since users watch full
codes. LESSON: for every custom HTML/search adapter, test whether an exact course-code search leaks
suffixed siblings before handoff (invisible until someone watches a course with a suffixed sibling).

## Handoff batch 11 (UC Santa Cruz pisa) — ✅ BUILT July 8: 1 added (634->635)
New bespoke `UCSC` adapter: one urlencoded POST per course to pisa.ucsc.edu, status from
the per-section icon alt ('Open'/'Closed'/'Closed with Wait List' — verified real 23/9/1
mix on a MATH sweep; ONLY 'Open' is open). Course-scoped by exact label match (no sibling
leak), truncation-guarded (rec_dur page cap -> skip, never miss a watched section),
quarter codes synthesized (2268 = Fall 2026) with verify-before-adopt. SIDE FIX: UCI was
missing from refresh_all_terms' adapter tuple (added same commit, along with UCSC) — its
term would never have auto-rolled. UC status: Irvine ✅ SantaCruz ✅ Merced ✅(Banner);
UCSB/UCSD/UCLA still with research.

### Batch 12 sent (July 9 2026) — UC Santa Barbara (ASP.NET viewstate cracked) — CONDITIONAL on open-detection
Cracked UCSB's ASP.NET postback: GET coursesearch.aspx → scrape __VIEWSTATE/__VIEWSTATEGENERATOR/
__EVENTVALIDATION → POST with __EVENTTARGET=ctl00$pageContent1$searchButton (image button posts via
EVENTTARGET not value — the crux), quarterList=20264 (Fall 2026, SERVER-RENDERED select), courseList=SUBJ,
dropDownCourseLevels=All. Returns ~4.7MB subject-wide HTML, real Fall 2026 sections.
⛔ ACCURACY OPEN QUESTION (flagged to builder, do not ship until resolved): status in class="Status" cells
= "Full"/"Closed"; OPEN appears as BLANK Status cell (JS only styles Closed/Full). "blank=open" is an
INFERENCE — must confirm via Enrolled<Max (Enrolled column exists; couldn't cleanly parse per-section
labels). If unprovable → scrap (false-open risk). Genuinely new (0 by name).
UC scoreboard: Irvine ✅, Santa Cruz ✅, Merced ✅(already), Santa Barbara (conditional), UCSD (HOLD-fall-not-
loaded + redirect flow), UCLA (browser token). LESSON: don't assert open-detection on inference; hand the
cracked flow + the explicit accuracy question, let the gate resolve it.

## Handoff batch 11 (UC Santa Cruz pisa) — ✅ BUILT July 8: 1 added (634->635)
New bespoke `UCSC` adapter for the public pisa class search (PeopleSoft-backed, POST,
reg_status=all so closed sections are visible and marked not-open). REAL status confirmed
(full section reads WAITLIST w/ 15-of-15 enrolled; genuine open/closed mix — not NAU-style
all-open). CRITICAL parse bug caught during the gate: the status icon and section class_id
live in the SAME panel-heading, and a naive 'nearest icon' regex mis-paired CSE 30-01 as
OPEN when it was actually WAITLIST (spanned to a legend/prior-section icon). Fixed by
splitting results into per-panel blocks and reading status only within each section's own
panel. Exact catalog_nbr search confirmed no sibling leak (MATH 11A != 11B). Term auto-rolls
from the form's own dropdown (single-quoted option values — quote-agnostic parse). Also
retroactively added UCI to refresh_all_terms (it shipped in b10 without auto-roll registration
— not a live bug, hardcoded term was current, but now self-maintains). Remaining UC: UCSB
(ASP.NET viewstate) + UCSD (Fall not loaded yet, HOLD) + UCLA (browser token flow) with research chat.

### Batch 13 sent (July 9 2026) — UCLA CRACKED (~46k, the biggest remaining UC) + UCSD still HOLD
UCLA's "browser token-flow" blocker is SOLVED — it's fully HEADLESS (two plain GETs, no browser).
The token that gated the earlier headless attempts is EMBEDDED in the subject results page: each
course ships an inline `AddToCourseData("PATH",{...,"Token":"..."})` JS block with the full model.
So no token-reconstruction algorithm is needed (UCLA's catalog normalization is gnarly — "M51A"
becomes path "COMSCI0051AM" — but we never replicate it; we read the model straight from the page).

FLOW (bespoke `UCLA` adapter, like UCI/UCSC):
1. Term list (auto-roll source): GET https://sa.ucla.edu/ro/public/soc — raw HTML has
   `<option class="select_term" value="26F" data-yearText="Fall 2026">` (26F = Fall 2026;
   YY + F/W/S/1/2). Parse + pick nearest upcoming main term, verify-before-adopt like every adapter.
2. Per subject (fetch once per cycle, cache): GET
   https://sa.ucla.edu/ro/public/soc/Results?SubjectAreaName=x&t=26F&sBy=subject&subj=COM+SCI&catlg=&cls_no=&btnIsInIndex=btn_inIndex
   → regex `AddToCourseData\("[^"]+",(\{.*?\})\);` → dict keyed by exact CatalogNumber.strip()
   (e.g. "0031"). Keys are exact so no sibling leak: "0031" != "0031A" != "0035L" (distinct models).
3. Per watched course: GET .../Results/GetCourseSummary?model=<the course's model JSON>&FilterFlags=<...>&_=<ms>
   FilterFlags enrollment_status="O,W,C,X,T,S" (show ALL so closed sections are visible/marked-not-open).
4. Parse each section block: `id="(\d+)_[^"]*-status_data"><p>...</i>(STATUS)<br/>(DETAIL)</p>`.
   - class_id (9-digit) = section key, verified UNIQUE (35/35 in gate, no collapse risk).
   - STATUS word is AUTHORITATIVE. Open format: "Open<br/>12 of 240 Enrolled<br/>228 Spots Left".
     Closed format: "Closed<br/>Class Full (120)". Waitlist seen too. TRUE-OPEN = status=="Open" only
     (Closed/Waitlist/Cancelled never open — zero false-alert). seats = "N Spots Left" int, else 0.
GATE PASSED: subject: COM SCI (SubjectAreaCode has SPACES — "COM SCI","MATH"). Live Fall 2026 broad
sweep (COM SCI/MATH/PHYSICS/ECON, 35 sections) = REAL mix 24 Open / 11 Closed with true integer
seat counts (e.g. MATH 115A "79 of 80 Enrolled, 1 Spots Left"=Open; CS 131 "Class Full (120)"=Closed).
Completed-term test (Fall 2025 = 25F): shows real Closed sections — NOT the classic-PS all-Open fake.
Deduped by name: schools.py has UCI/UCSC/UCSB, NOT UCLA. Latency: subject page 1.9s (once/cycle),
per-course summary 0.34s. Example course: COM SCI 32 (Intro to CS II, live, real seats).
UC scoreboard: Irvine✅ Santa Cruz✅ Merced✅ Santa Barbara✅(built) UCLA(sent b13) UCSD(HOLD).

UCSD RECHECK: still HOLD — act.ucsd.edu term dropdown only goes through Spring 2026 (SP26/WI26/
Summer); no FA26 loaded yet (UCSD is on quarters; Fall quarter loads later). Re-check via the weekly
scheduled task.

## Handoff batch 12 (UC Santa Barbara ASP.NET) — ✅ BUILT July 8: 1 added (635->636)
New bespoke `UCSB` adapter (ASP.NET WebForms viewstate postback, __EVENTTARGET=image
search button, subject-wide POST). THE ACCURACY QUESTION RESOLVED: the research chat
correctly refused to assert "blank Status = open". Proven before shipping — cross-checked
every section's Status against its own Enrolled/Capacity across 390 live sections (WRIT+MATH):
BLANK<=>enrolled<cap and 'Full'<=>at-cap held with ZERO violations. Adapter treats open =
blank Status AND enrolled<capacity (double-safe); 'Closed' (can have empty seats but admin-
closed) is never open. Real seats = cap-enrolled. Term auto-rolls from the server-rendered
quarterList (20264=Fall 2026). UC scoreboard: Irvine, Santa Cruz, Santa Barbara, Merced live.

## Also this session: fixed a shadowed-duplicate-class bug + hardened the guard
The batch-11 UCSC shipped with a DEAD earlier UCSC class definition above the real one
(Python silently uses the last def, so the gated panel-based parser was live and correct,
but the stale alt-text copy sat in the file). The registry guard missed it because it checks
registered INSTANCES, not class definitions. Removed the dead copy and EXTENDED _guard_registry
to also fail on any adapter class used by >1 registered school that isn't a known shared base —
so a shadowed/duplicate class definition now crashes at import.

### Batch 12 outcome (builder, July 9 2026): UCSB SHIPPED → 636. Model handoff.
Builder confirmed blank-Status=open via cross-check: 390 live sections (WRIT+MATH), BLANK always
enrolled<capacity, 'Full' always at-cap, zero violations. Adapter requires BOTH blank Status AND
enrolled<capacity (double-safe); 'Closed' never treated as open even if seats show (admin-closed can
have empty seats — would've been a false-open). UCSB gives real seat COUNTS, not just status — bonus.
LESSON CONFIRMED: flagging an accuracy question honestly (not asserting) + pointing at the exact data
to resolve it (the Enrolled column) turned into a 5-minute clean gate instead of a scrap. Do this every time.
Also: builder found + fixed a dead duplicate UCSC class definition (stale draft shadowed by final one,
no prod impact, registry guard now hardened to catch shadowed classes too).
UC SCOREBOARD FINAL (this session): Irvine ✅ Santa Cruz ✅ Santa Barbara ✅ Merced ✅(already live).
Remaining: UCSD (HOLD, fall not loaded), UCLA (needs browser token-flow trace).
SESSION FINAL LIVE COUNT: 636 (started at 529, +107 today).

## Handoff batch 13 (UCLA) — ✅ BUILT July 9: 1 added (636->637)
New bespoke `UCLA` adapter (sa.ucla.edu/ro/public/soc, fully headless — 2 GETs, model+Token
read off the subject page's inline JS). Course lookup keys on the HUMAN-DISPLAYED number
('32','M51A','35L','C121') pulled from the page's own title buttons and joined to each model
by element id (SubjectAreaCode+CatalogNumber, spaces stripped; 25/25 join) — so users type
what UCLA shows and we never reconstruct the path encoding. Real seat ints ('N Spots Left'),
ONLY status=='Open' is open (completed-term test confirmed real Closed/Waitlist). One
accuracy improvement over the handoff spec: dropped the suggested 8am-8pm FilterFlags time
window entirely (start/end null) so an evening section can never be hidden from a watcher —
verified harmless on MATH but removed to be safe. Hourly-refreshed status (registrar, not
real-time) noted — same as Coursicle, still real. UC coverage: Irvine/Santa Cruz/Santa
Barbara/Merced/UCLA live; UCSD HOLD (no fall yet); Davis 403.

### Fluid-PeopleSoft grind pass 2 + SFSU breakthrough (July 9 2026 evening) — 2 gated-clean, awaiting go-ahead
Continued the BU-pattern HCX hunt. KEY INSIGHT: WEBLIB_HCX_CM = HighPoint CX (3rd-party PeopleSoft
add-on) — its customer base is the lead list, but hosts are idiosyncratic (420-host pattern sweep of
highpoint-prd./hcx./m./mobile./cx. across 60 PS domains = 0 hits; search-engine harvest is the only way in).

1) ✅ COPPIN STATE (~2.5k, Baltimore HBCU, 4-year, MD) — GATED CLEAN. Existing PeopleSoft adapter fit
   (4-line add): host=eaglecs.psoft.coppin.edu site=csucsprd inst=COPPN term 2268=Fall 2026 (2274=
   Spring 2027 also listed). Found via its QA host in Google, then coppin.edu registrar →
   eaglemobile.coppin.edu → redirects to the prod IScript. Gate: 109 Fall-2026 sections ENGL/BIOL/
   PSYC/MISY = REAL mix 57 O / 52 C; enrl_stat↔enrollment_available consistent 109/109; completed-term
   (Fall 2025=2258) shows 42 C / 10 O (not fake all-open); response shape {"pageCount":N,"classes":[...]}
   — NOTE pageCount pagination (my probes all pageCount=1; builder verify big subjects). Example:
   "ENGL 102" (22 sec, 19 O / 3 C, distinct class_section keys). Subject list has hyphenated collab
   codes (BIOL-MSU etc); plain ENGL/BIOL/PSYC behave normally. Dedup clean (no Coppin in schools.py).

2) ✅ SAN FRANCISCO STATE (~23k, 4-year public!) — GATED CLEAN, needs small bespoke adapter.
   CSU was "all PeopleSoft/gated" but SFSU runs a BESPOKE PUBLIC class schedule:
   webapps.sfsu.edu/public/classservices/. Flow (cookie jar, 2 GETs per course, no token):
   a. GET /public/classservices/classsearch/results?searchFor=MATH+226&term=2267&classCategory=REG
      (primes the session; searchFor="SUBJ NUM" exact — no sibling leak, verified)
   b. GET /public/classservices/searchresultsjson → {"aaData":[[...13 cols...]]}
      cols: [0] course+"[sec]" html, [1] LEC/LAB, [4] classNumber (UNIQUE section key, verified),
      [9] SEATS AVAILABLE (int), [10] capacity, [12] enrolled. Identity seats+enrolled==capacity
      holds on 46/46 sampled except over-enrolled sections (enrolled>cap → seats served already
      clamped to 0 — safe, matches Banner clamp semantics).
   Terms: search-page radio labels, 2267="Fall 2026" (auto-roll source; 2265=Summer 2026; past
   terms 2263/2257 also queryable w/ realistic mixes). FRESHNESS PROVEN: detail page
   (/classsearch/detail/{term}/REG/{classnbr}) prints "Seats As of July 09, 2026 18:20 PDT" —
   live-timestamped — plus full waitlist numbers (limit/filled/available). Open rule: seats>0
   (Banner semantic). BUILDER FLAG: waitlist counts exist only on the detail page, not in the JSON —
   decide whether open=seats>0 suffices (it's what every Banner school uses) or cross-check the
   detail-page waitlist before alerting. Example: "MATH 226" (24 sec, real mixed 0s/positives).
   Dedup clean by name (CCSF and USF are different institutions).

DEAD THIS PASS: Pitt HCX (SAML SSO), U Miami CaneLink (Microsoft SSO), UMBC highpoint-prd (times out
externally — likely campus-net-only), SDSU sunspot (now redirects to PS login; the Google hit was a
stale 2015 crawl), CSULB/CSUN/Sac State/Cal Poly schedule guesses (403/NX). ICC = config empty (prior).
FOLLOW-UP VEIN (unmined): the other ~18 CSU campuses may each run a bespoke public schedule like
SFSU's — one-at-a-time registrar-page recon, decent odds given the SFSU precedent. Also: HCX
customers announce migrations in campus-IT news ("HighPoint CX" + college name) — alternate harvest angle.

## Handoff batch 14 (Coppin State + SFSU) — ✅ BUILT July 9: 2 added (637->639)
Coppin State (Baltimore HBCU): 4-line PeopleSoft subclass (host eaglecs.psoft.coppin.edu,
inst COPPN). The flagged {pageCount,classes} object shape is a non-issue — the existing
PeopleSoft adapter already reads d.get('classes')/d.get('pageCount'). Gated: ENGL 102 22
secs/19 open, big subject ENGL 101 41 secs handled fine.
SFSU (first CSU on the platform!): new bespoke `SFSU` adapter for webapps.sfsu.edu's public
class schedule (2 cookie-shared GETs: prime /results then /searchresultsjson). Keys by
classNumber (col[4]), open=seats>0 (col[9], clamped >=0), scoped to exact watched code from
col[0]. Verified: no sibling leak (ENG 114 only ENG 114), unique classNumbers, real mix
(MATH 226 16 open/8 full), registrar-live freshness (detail page timestamps to the minute).
Term auto-rolls from the search page's term radios. CSU was thought all-login-gated — SFSU's
public schedule is the crack; other CSU campuses may have similar student-facing schedules
worth a look.

### CSU public-schedule sweep pass 1 (July 10 2026) — 2 more gated clean, 1 crackable-deferred, SSO walls mapped
SFSU proved CSUs run bespoke public schedules. Swept the big campuses. RESULT: the CSU system is
FRAGMENTED (every campus different tech), NOT one shared adapter — but several are individually clean.

1) ✅ SACRAMENTO STATE (~31k, 4-year public) — GATED CLEAN, best data of the batch (bespoke JSON API).
   React app at csus.edu/class-schedule; backend classschedule.webhost.csus.edu/api/cs/ (no auth, no token):
   - GET /api/cs/fall-2026            → [{subject_code, subject_ldesc}]  (subject list; term slug is
     "fall-2026" / "spring-2026" style — auto-roll by building the slug from nearest upcoming term)
   - GET /api/cs/fall-2026/{SUBJ}     → [{catalog_number, class_title, sections:[...]}]  (one call
     returns the WHOLE subject with all courses + sections inline — efficient)
   Section fields: class_number (5-digit, UNIQUE key), class_section ("01"), component,
     seats_total (int), seats_available (int) ← the money field, term_code ("2268"=Fall 2026).
   open = seats_available>0 (Banner semantic). GATE: 1035 Fall-2026 sections across CSC/ENGL/MATH/
   BIO/PSYC = real mix 571 open / 464 full; seats_available<=seats_total on 100% (no sentinel);
   completed-term (fall-2025) ENGL = 124 open / 94 full (real closed sections, not fake). Freshness:
   response Cache-Control max-age=3600 → hourly (same tier as UCLA, shipped). ⚠️ PARSE NOTE: multi-
   MEETING courses repeat the same class_number across rows with meeting_number 1/2 (seen on CSC/MATH,
   up to 63 dup class_numbers in MATH) — DEDUPE sections by class_number (the dup rows carry identical
   seats, just different meeting patterns). Example: "CSC 10A". Dedup clean (Sac State not in schools.py;
   CCSF/USF/SFSU are different). Needs a small bespoke JSON adapter (like Wisconsin/Iowa).

2) ✅ CSU NORTHRIDGE (~38k, 4-year public) — GATED CLEAN, custom PeopleSoft bolt-on (stateful POST).
   NOT the fake-status classic-PS trap — this is CSUN's own component NR_SSS_COMMON_MENU.NR_SSS_SOC_
   BASIC_C.GBL, and it returns REAL availability (completed-term test PASSED, see below). Host
   cmsweb.csun.edu, site CNRPRD. Flow: GET the .GBL entry TWICE (first bounces on cookie-check ckreq,
   second serves the form) → scrape ICSID + ICStateNum → POST with ICAction=NR_SSS_SOC_NWRK_BASIC_
   SEARCH_PB and fields: NR_SSS_SOC_NWRK_STRM (2267=Fall 2026), GROUP="1. Regular",
   NR_SSS_SOC_NWRK_SUBJECT (e.g. "ENGL"), NR_SSS_SOC_NWRK_NR_SRCH_MATCH="E" (Exact),
   NR_SSS_SOC_NWRK_CATALOG_NBR_SRCH ("115"). Response is a PeopleSoft grid; per-row fields (index $N):
   NR_SSS_SOC_NSEC_CLASS_NBR$N (5-digit, UNIQUE key), NR_SSS_SOC_NSEC_CLASS_SECTION$N ("01"),
   NR_SSS_SOC_NSEC_SSR_COMPONENT$N (LEC), NR_SSS_SOC_NWRK_AVAILABLE_SEATS$N (int),
   NR_SSS_SOC_NWRK_DESCRSHORT$N ("Open"/"Closed"). open = DESCRSHORT=="Open" (== seats>0, verified
   0 inconsistencies). GATE: live Fall-2026 ENGL 115 = 66 sections, 41 open / 25 closed, seats↔status
   consistent 66/66; COMPLETED-TERM TEST (Fall 2025 = 2257) ENGL 115 = 43 Closed / 22 Open → REAL
   closed sections in a done term, so NOT the NAU-style fake-all-open (this is why it's shippable
   where classic COMMUNITY_ACCESS is not). Subject codes are SPACE-BEARING on some depts (dropdown
   shows "A E", "A M", "A/R") — builder pass the code exactly as CSUN lists it. Example: "ENGL 115".
   Term strm codes standard CSU (2267=Fall26). Dedup clean. Needs a bespoke stateful-POST adapter.

3) ⏸️ CAL POLY POMONA (~30k) — CRACKABLE, DEFERRED (ASP.NET viewstate, same family as UCSB).
   schedule.cpp.edu is a public ASP.NET WebForms app (__VIEWSTATE/__EVENTVALIDATION/__EVENTTARGET),
   term dropdown server-rendered (2267=Fall 2026), free-text ClassSubject + CatalogNumber. Search
   button posts via WebForm_DoPostBackWithOptions (EVENTTARGET, like UCSB's image button). I got the
   viewstate handshake and term list but the exact search postback field-set returns a validation
   error / GenericErrorPage on my headless guesses — needs a browser NETWORK TRACE of one real search
   to capture the precise field payload (the Chrome extension BLOCKS navigation to schedule.cpp.edu,
   so couldn't trace it here). Status words ("Open"/"Closed"/"Full") ARE in the results HTML → real
   status likely present. Worth finishing when a browser that can reach the domain is available;
   mechanically it's the UCSB playbook. NOT handed off (unproven open-detection).

DEAD (SSO-walled, mapped so nobody re-treads): CSU Fullerton (SA_LEARNER_SERVICES.CLASS_SEARCH.GBL
"?public=" bounces to shibboleth.fullerton.edu SAML), Fresno State (cmsweb.fresnostate.edu same GBL,
no guest form served), San Diego State (sunspot redirects to cmsweb PS login), San Jose State
(one.sjsu.edu class-search is portal-gated; the sjsu.edu/classes static pages are "refreshed nightly"
= too stale + no per-section seats). CSUN's classic sibling and Fullerton's are the CSU-standard
COMMUNITY_ACCESS/SA_LEARNER guest search — mostly SSO-gated now; CSUN wins only because it exposes
its OWN bolt-on component publicly. NEXT CSU targets (unchecked): Long Beach, San Marcos, Chico,
Stanislaus, Bakersfield, Channel Islands, Dominguez Hills, East Bay, Maritime, Humboldt, San Bernardino.
