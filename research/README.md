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
