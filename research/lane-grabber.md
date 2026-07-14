# Lane status — Grab (research agent, successor to Grabber/Fable's research lane)

**Only Grab writes this file.** Codex/Build read it. Continuation of `lane-fable.md` (archived).
Single relay point to Build is unchanged: gated finds → README under `AWAITING GO-AHEAD` → on
Nathan's go, relay to Build (session local_f4c9ee6c-cfaa-41e0-bf31-348d87326105) as "Batch N" → mark SENT.
School adds relay DIRECT per deploy policy; money/UI/legal stay gated behind Nathan.

## Monroe CC gated + Delaware confirmed-skip (July 14)
- **Monroe CC** (NY, ~13k) ✅ READY: GET monroecc.edu/classes/{subj}-{num}-sections/ (one course/page, complete+UNCAPPED). Seats in <p> after <h4>Seats Remaining</h4>; open=N>0; key=CRN. Gate ENG-101 129 sec 100/29 (flagship uncapped — cap-lesson applied), MTH-211 3/1. Relayed.
- **Delaware SKIP CONFIRMED**: hard 49-result cap, no pagination, params ignored, app.js 1KB shell no API, no public Banner/mobile host (real SIS = PeopleSoft). ENGL110 (most-watched) pinned at 49 both terms = truncation. Not revivable w/o a cap-free endpoint. LESSON (memory): gate a KNOWN-huge course, watch for round-cap across 2 terms.

## VOLUME PUSH (July 13, Nathan "need more colleges") — Portland CC ⭐ + strategy
- **Portland CC** ✅ READY (~70k, one of largest US CCs). Live capacity POST: course page pcc.edu/schedule/{term}/{subj}/{subj}{num}/ (data-term=202604, data-crn list) → POST pcc.edu/schedule/capacity/ {term,crn=csv} → {CRN:{seat:[avail,cap],wait:[..]}}. Open=seat[0]>0, key=CRN. Gate: WR121 39/21, MTH111 16/16, BI101 all-full — real mix, real-time. Relayed to Build.
- **SJSU SKIPPED** — page says "refreshed nightly" (date-only Updated stamp) = false-open risk (stale). Fails accuracy bar per Nathan's "no sacrifice" condition. Dropped.
- **Wabash College** (~900) ✅ READY: GET wabash.edu/apps/registrar/course-sections/?term=26%2FFA, textual OPEN/CLOSED/WAITLISTED + capacity/enrolled/available. Gate 238/74 live, 241/87 completed. TRAP: multi-meeting rows share section key — dedup by SectionName. Relayed.
- **VCCCD (Ventura ×3)** = bespoke Django lead for Build: banpublic.vcccd.edu POST /filter/ (needs CSRF from window.CSRF_TOKEN + cookie) → JSON CRSE_SEATS_AVAIL/COURSE_CRN/TERM_CODE; `site` filter splits Ventura/Moorpark/Oxnard. Plain-client 403 (CSRF); needs browser-trace. Documented, not gated.
- **STRATEGY finding:** CA CC district feeds are HETEROGENEOUS — no single-vendor unlock (WVM /data/ JSON ≠ VCCCD banpublic Django ≠ SDCCD mws-api ≠ RCCD SharePoint). schedule.{district}.edu sweep found only wvm/nocccd/vcccd. So volume = grind each district/school individually. The pipeline (Codex finds public feed → Grab gates → Build ships) IS the scaling mechanism; no shortcut.

## Delaware + SJSU gated (July 13) — Delaware CLEAN/ready; SJSU buildable but NIGHTLY-refresh (Nathan call)
- **University of Delaware** ✅ READY: GET udapps.nss.udel.edu/CoursesSearch/search-results?term=2268&search_type=A&course_sec={SUBJ} (Fall 2268/Spring 2263). Open = "X OF Y" X>0 AND no "CURRENTLY FULL". Key=concatenated code (ENGL110010). Gate: Fall ENGL 25/24, MATH 34/14 mixes; addressable; updates through the day. Relayed.
- **SJSU** ⚠️ HELD FOR NATHAN: static numeric table www2.sjsu.edu/classes/schedules/fall-2026.php (Open Seats col, class-number key). Platform SAFE (NOT fake-status PeopleSoft — Build's worry resolved). Gate: 5007/2006 live, 4133/2296 completed — real. BUT refreshes NIGHTLY (undercuts "alerts in seconds") + excludes no-print classes. Data real+safe but nightly lag = quality trade-off; Nathan decides.

## MassArt FIXED (July 13) — base Colleague, not NewColleague → 4-line drop-in, relayed to Build
Build's NewColleague.fetch got no-data because MassArt (mca-ss.colleague.elluciancloud.com) uses the
OLDER Colleague API: /Student/Courses/SearchAsync = 404; the working route is
/Student/Courses/PostSearchCriteria (textual "Open"/"Closed"/"Waitlisted"), i.e. base `Colleague` not
NewColleague. Gated live through production Colleague.fetch: CDAN 300 1 open/1 full, CDAN 302 2/2, CDAN
303 full — real mix, keys unique. 4-line Colleague subclass, example CDAN 300. Relayed. LESSON: when a
Colleague host 404s on SearchAsync, try PostSearchCriteria (base Colleague) before calling it dead —
Ellucian-cloud hosts run BOTH API generations.

## IU Bloomington SHIPPED (711) + elite tier maxed (July 13)
Build shipped IU Bloomington off my trace (710→711, ~48k). Elite reachable-six DONE: USC/Rice/Princeton/
IU-Bloomington live; Harvard/CMU/Michigan blocked. Build added 2 addressability refinements to my spec:
(1) 478 IU combos are MULTI-ROW (variable-topic, one code → many catalog rows → aggregate or silent-miss;
now in [[seatwatch-gate-addressability]]); (2) combinedSections.separateEnrollmentControl flag gates the
cross-list cap precisely.

## Codex batches 69-72 audit (July 13) — NOTHING shippable; NAU = fake-status trap (held)
Checked Codex's newest (69-72). All hold-outs except NAU (Batch 71, "GATED"), which I re-assessed and
HELD: it's classic PeopleSoft COMMUNITY_ACCESS.CLASS_SEARCH.GBL — our documented FAKE-ALL-OPEN dead-end
(we already cut NAU: 121/121 English "Open" in a completed term). Codex found a numeric "Available Seats"
field + Closed icons + a small completed-term mix (Spring ART 161 = 2,2,0,0), which COULD mean the numeric
field is real — but a bare GET returns a 2940-byte stateful shell (no results), so verifying it needs the
full stateful PeopleSoft flow (ICSID/InFlight — archive says historically not worth it), and the family
fails the completed-term status test by design. Not worth the browser-stateful gate for one already-cut
fake-status school. Rest of 69-72: UF (ONE.UF catalog-only, no seats), UH/MSU (PeopleSoft, no rows
captured), Clemson (current-only), + WA/MT/AK/ID publics all login/redirect-gated. Codex is now scraping
uniformly auth-gated/catalog-only flagships — low yield. Honest read for Nathan: no new clean lead here.

## NOW (July 13 later) — Codex-pile audit + Maricopa verified; ctlog vein CLOSED; live at 691
- **Elite: USC+Rice+Princeton ALL SHIPPED by Build (691).** Princeton's token-rotation risk solved by
  Build via existing safe-failure guard. Elite reachable-six done (Harvard/CMU/Michigan blocked, no anon seats).
- **⭐ MARICOPA ×10 LIVE-VERIFIED (Codex Batch 25) → green-lit to Build** (Build's next bench item).
  classes.sis.maricopa.edu server-rendered, term 4266, 10 institution codes, `all_classes=true` MANDATORY
  (default hides closed = silent miss; confirmed BIO201 12open/5closed only with the param). Biggest lever
  in Codex's pile. README block "MARICOPA ×10".
- **Codex-pile honest audit:** 48 batches = LEADS, none production-gated. Big publics mostly PeopleSoft
  (fake-status) or hosts unresolvable w/o per-school browser recon (blind-guess confirmed dead: MSSU/
  Cayuga/Monroe host guesses all missed). CVC batches self-rejected. Buildable net-new bespoke queue
  (deduped, README block "BUILDABLE bespoke queue"): Maricopa×10, RCCD×3, SDCCD Mesa+Miramar (City already
  LIVE), Williston, CCBC, Brandeis, Cayuga, Monroe, West Valley, Kent State, UVM. NOT drop-ins — each needs
  a Build adapter. Realistic: this pile is a bespoke-build backlog, not 20 quick adds.
- **ctlog vein CLOSED:** retry20 done → 15/20 checked, 0 SSB hits, 5 crt.sh-stubborn (needs_retry3.json).
  Net Banner yield across the ENTIRE 229-domain CT-log batch + all 3 retry passes = 0 net-new. Vein tapped.
- **RCCD hold:** msappproxy feed reachable but returns HTML proxy shell to plain GET — needs exact
  SharePoint list-query headers + bespoke adapter (unchanged; still bench, not drop-in).

## (earlier July 13) — parser-resurrection resweep EXECUTED; Batch 31 SENT (NMSU + RPI)
- **Dead-pool resweep done, verdicts final** (full detail in README Batch 31 block): Banner-9 IPEDS
  cuts re-gated through the current production adapter → **NMSU resurrected** on the public host
  banner-public.nmsu.edu (needs exact-campusDescription filter — 5-campus shared pool; DACC rides free);
  Morehouse/Wilkes/VSU/CCTech/PVAMU/Middlebury = guest-search disabled at API level (empty on completed
  terms too — policy block, FINAL). **RPI resurrected** via completed-term production disproof
  (ListcrseBanner8 drop-in; live all-open is real pre-registration emptiness). CT-log B8 leftovers
  network-dead on a 20-path battery. UCSD still no FA26 (weekly recheck). UH avail.classes still 502.
- **ELITE PASS July 13 (Grab): 3 of 6 cracked + SENT, 1 corrected to BLOCKED.**
  - **USC** ✅ SHIPPED same-day (Build, live at 689): public REST API behind classes.usc.edu, real
    registeredSeats/totalSeats/isFull per sisSectionId, live 151-FULL WRIT-150 disproof.
  - **Rice** ✅ SHIPPED (Build, 690): custom SWKSCAT Banner CGI, Section/Xlist/Waitlist enrollment.
  - **Princeton** SOURCE-GATED + SENT — api.princeton.edu two-call (classes + seats), anonymous Bearer.
    STRONGEST disproof of the four (live-term 385 real Closed COS, 25/25 + over-cap; 0 status/arith
    disagree across ~5,900 sec). BUT bespoke + BROWSER-ASSISTED: registrar page 403s plain clients
    (Akamai challenge, even browser UA) so token needs a headless bootstrap; api host is plain-reachable.
    README block "Princeton (elite lead)".
  - **Harvard** ❌ CORRECTED TO BLOCKED (prior handoff wrongly said "my.harvard exposes enrollment").
    my.harvard public search IS open (no login) and returns course cards + section times, but exposes
    NO live enrolled/capacity to anonymous users — only "Enrollment: No Limit" (a cap POLICY) + section
    times; the "Enrolled/Waitlist" strings are calendar/cart UI labels, not seat counts. No seat field =
    can't gate. Same catalog-only class as the other BLOCKED elites.
  - **CMU** ❌ BLOCKED (probed July 13): SOC (enr-apps.as.cmu.edu/open/SOC) is public + no-auth, but the
    COMPLETE public schedule dump (sched_layout_fall.htm, 1.6MB) has ZERO seat/enrollment/capacity/avail
    columns — times + catalog only; live seats are behind CMU's authed SIS. Same no-anon-seats class as Harvard.
  - **Michigan** ❌ no public seat surface found (Wolverine Access + LSA Course Guide both Okta-gated).
  - **ELITE PASS CLOSED:** of the original reachable-six — USC ✅ + Rice ✅ shipped, Princeton ✅ sent
    (browser-assisted), Harvard/CMU/Michigan all BLOCKED (no anonymous seat counts). Next elite growth
    needs either a Princeton-style browser-bootstrap build or a NEW angle on the auth-blocked tier
    (JHU/Columbia/MIT/Duke/Stanford/Northwestern/etc). Princeton's Drupal-registrar + api-gateway +
    embedded-token pattern is worth pattern-matching against other schools as a fresh vein.
- **RICE CRACKED + SENT to Build (July 13)** — custom Banner package (SWKSCAT CGI), labeled
  Section/Xlist/Waitlist enrollment + live freshness stamp; waitlist-priority + xlist-pool rules
  MANDATORY; completed-term full row through same parse. README block "Rice (elite lead)".
- **crt.sh retry pass DONE (July 13): 42/62 now checked clean, 0 SSB hits, 20 stubborn ct_FAILs →
  needs_retry2.json** (crt.sh keeps choking on those; retry another day, NOT counted clean). Every
  banner-ish host found was probed live: all dead/false-positive (enterpriseregistration.* = Windows
  device-enrollment, not Banner; fitchburg/nnmc/opsu/commonwealthu/wvsom hosts dead on B9+B8 routes).
  Unverified maybe-Colleague (NOT confirmed catalogs, low-pri CCs): selfservice.tsc.edu (5KB page),
  selfservice.swtjc.edu (timeout), selfservice.easternwv.edu (404 on /Student/Courses). CT-log vein on
  this pool = closed except the 20.
- Build's bench (theirs, track only): Batch 31 NMSU+RPI, USC bespoke, Oregon browser-trace, UGA seat
  endpoint, RCCD hold.

## RELAY — Codex-work sweep: Batches 26 + 27 SENT (July 12)
- **Worcester State (MA) → Batch 26, ✅ BUILT by Builder (667).** Re-gated live NewColleague: EN 101 33 sec
  7 open/26 full; 30 live full = disproof. Fits existing adapter.
- **WSSU (Winston-Salem State, NC) → Batch 27 SENT** (Nathan "send everything good"). Production-gated via
  `ListcrseBanner8` (sibling of shipped NCCU): live BIO 1113 2 open/4 full + completed 202620 3 open/2 full.
  ~4,972 students, 4-yr HBCU (corrected — earlier 18.7k was UNCG's number, not WSSU's).
- **Shorter College (AR) → HELD, NOT ship-ready.** Production NewColleague re-gate FAILS fake-open disproof
  (1 live open section, no full rows; completed term not adapter-queryable). Handed back to Codex.
- **Full Codex-ledger dedup done.** Already SHIPPED (do not re-send): UNCG, UNCA, NCCU (the "cleanest-3"),
  Otis, Onondaga, Berkeley, batch-22 four (LVC/Augustana/Camden/Walsh), Worcester. Blocked/closed: UC
  Davis, Johns Hopkins, Gustavus, Texas Wesleyan, N.Central, Columbia, Northwood, N.New Mexico, Ventura.
  ⚠️ DEDUP LESSON: an over-filtered `grep name= | grep class` FALSE-NEGATIVED the shipped UNCG/UNCA — always
  dedup with a simple host/name grep, never a piped filter.
- **Source-gated queue relayed to Builder as build-decisions** (NOT production-gated — no existing adapter,
  each needs a bespoke build; honest leads only): Fairfield (bench), SDCCD×3 City/Mesa/Miramar (bench),
  **RCCD×3 Moreno Valley/Norco/Riverside City (NET-NEW to Builder)** — SharePoint API, Codex source-gated.

## ✅ College Scheduler vein BUILT (Batch 28) — 668→671, ~133k students on one adapter
Ivy Tech + UT Arlington + Univ of Alaska (shipped as one system-wide entry; CRNs unique across campuses).
⚑⚑ **MY GATE MISSED A PAGINATION TRAP (Builder caught + fixed) — adopt for all future CS gating:**
`getCourseSections` PAGINATES at 60/page. I reported Ivy Tech BIOL 101 = 40 sections; it's really **71**.
My gate used `first:30/first:60` and reported the truncated count as complete — a SILENT-MISS risk (watched
sections invisible = a missed alert, the mirror of a false alert). **FIX: always follow Relay
pageInfo/endCursor to hasNextPage=false before counting/trusting sections; skip any course still truncated
at the cap (accuracy over coverage).** The vein CONCLUSION was still right (real full rows, gate PASS), but
the section COUNT was undercounted. Builder's adapter pages fully + skips >360-section courses. Also: term
auto-pick must handle BOTH label orders ("Fall 2026" Ivy Tech vs "2026 Fall" UTA) — Builder's parser covers
year-first. Any future public-search CS school = ~3-line add.

## ★ CREATIVE-HUNT WIN (July 12) — College Scheduler / Civitas public GraphQL vein
Chased "biggest missing mega-schools" → found the system many of them use: **College Scheduler
(Civitas)** runs a PUBLIC no-auth GraphQL API (`api.collegescheduler.com/graphql`) with clean numeric
seats (`openSeats`/`totalSeats`). ONE bespoke adapter serves every school with public "Course Search" on.
**3 confirmed LIVE + CURRENT + net-new (deduped):** Ivy Tech (~65k), UT Arlington (~42k), Univ. of Alaska
system (~26k, campus-splittable) — ~133k students from one adapter. All gated PASS (live full rows,
disproof holds). Full recipe + caveats in README block "College Scheduler / Civitas GraphQL"; data in
collegescheduler_lead.json. CAVEAT: public search is opt-in (most CS clients — asu/duke/alamo — gate it
behind SSO); can't fully enumerate the roster. **→ Batch 28 SENT to Builder** (Nathan-approved). Verified before sending: `findCourses` is FUZZY/RANKED
(query "BIOL 101" → 221,211,201,240,101) so the adapter MUST exact-match subject.shortName+courseNumber
(else wrong course = false alerts); registrationNumber keys unique. This is the fresh vein Nathan asked
for — highest-value find of the session (~133k students, one reusable adapter).

## SWEEP COMPLETE (July 12): 167/229 truly checked, 62 ct_FAIL need retry, 0 live Banner-9 SSB hits
crt.sh degraded under sustained load (my CS/Ellucian queries added to it) → 62 domains failed and are
queued in needs_retry.json (NOT swept — must retry before declaring done). 17 banner-host domains found.
**Second-pass DONE: 0 gate-able Banner (SSB-registration=0, Banner-8=0)** — banner hosts were internal/
unreachable and the banweb.* B8 hosts didn't answer the catalog route (possible false-neg on path guesses,
but these are tiny schools — MCLA ~1.4k, East Georgia ~2.5k — low priority). **Net Banner yield from this
229-domain CT-log batch = 0.** Honest read: CT-log on tiny never-swept publics is largely tapped.
→ **HANDOFF TO CODEX: 19 `selfservice.*` Colleague hosts** in research/colleague_leads_for_codex.json;
net-new worth a look: **stlcc (St. Louis CC ~13k)**, framingham, massart, westmoreland, asutr (rough dedup —
Codex verify). Still TODO: crt.sh RETRY pass on the 62 ct_FAIL domains (needs_retry.json) for completeness.

## CREATIVE-HUNT results (July 12) — 2 dead ends, 1 real-but-complex fresh vein
Pushed beyond CT-log per Nathan. Honest outcomes:
- **Coursedog → DEAD as a seat vein.** Its catalog product (`*.catalog.prod.coursedog.com`) is course
  descriptions only (no seats). Its scheduling product "sits on the SIS and syncs" — the student-facing
  search stays Banner/PeopleSoft. No distinct public-seat surface.
- **Ellucian-cloud CT-log (`crt.sh %.elluciancloud.com`) → DEAD.** 1,125 subdomains but Ellucian uses
  WILDCARD certs for real school tenants (so individual schools don't appear), and what's exposed is
  Ellucian's internal dev infra (numeric tenant IDs 10321/10005…, `*-api-*`, dev names). The visible
  numeric Banner tenants (`banner.10004…`) return empty getTerms. Can't enumerate schools this way.
- **CVC.edu / Quottly → REAL fresh vein, but COMPLEX (parked as a bespoke-adapter lead).** California
  Virtual Campus (`search.cvc.edu`, backend `courses.quottly.com`) is a PUBLIC no-auth course search
  across ~115 CA community colleges with real-time seats. Confirmed API: `/api/universities.json`
  (college list) + `/api/search.json?query=&university_id=` (course autocomplete, e.g. university_id 88
  = Cosumnes River → 159 bio courses). BUT seat_count loads REACTIVELY via StimulusReflex/ActionCable
  WEBSOCKET (`Sections#seat_count_reload`) — the `/search` results HTML is empty until the socket fills
  it; no clean REST/HTML seat endpoint. So gating needs a headless-browser or ActionCable-protocol
  adapter. Accuracy caveats: seats are opt-in per college ("unavailable" for many), timestamped
  (staleness), coverage skews to online/exchange sections. Verdict: genuine but a bespoke Builder build
  with a freshness check — lower priority than direct-SIS given our flawless-accuracy bar. Quottly may
  power other consortia (same complexity). Handed to Builder as a research lead, NOT ship-ready.

## SWEEP-YIELD reality (July 12): a banner-ish cert ≠ a reachable public SSB
Sweep found ~16 banner-host domains, but batch-gating the Banner-9 ones exposed the catch: many CT-log
banner hosts are INTERNAL/cert-only — `banner.delhi.edu`, `banner9prod.framingham.edu`,
`prodssb.guamcc.edu` = NXDOMAIN (cert exists, no public DNS); `ssb.mssu.edu`/`ssb.neiu.edu` resolve but
firewall/404. Net-new deduped candidates worth the 2nd-pass (Banner-8 listcrse route): Missouri Southern
(mssu, reachable), NE Illinois (neiu, 404→maybe B8), + banweb.* B8 hosts (MCLA, East Georgia). Colleague
`selfservice.*` leads for Codex: asutr, cei, gmc, lincolnu. Gordon State + Univ. of Guam already shipped
(guamcc = Guam COMMUNITY College, distinct, net-new). Run ctlog_secondpass.py after the sweep completes.

## NOW (July 11, evening) — CT-log vein, corrected sweep in progress
- **Running the CT-log sweep over the 229 never-swept public-college domains** (`ctlog_targets_remaining.json`).
  Method: crt.sh (recovered — HTTP 200 again, **unlimited**, replaces rate-limited certspotter) →
  filter banner-ish subdomains → probe Banner-9 SSB `getTerms` → gate promising hosts through the
  PRODUCTION `schools.Banner.fetch()`.
- **crt.sh is back up** — this is the unlock. certspotter's ~10/hr cap no longer blocks a full sweep.
- **⚠️ BUG FOUND + FIXED (false-negative trap):** my first sweep used 6 concurrent workers. crt.sh
  chokes under concurrency → returned empty/None for 209/210 domains, and the certspotter fallback was
  rate-limited (429) → **the whole run was a false "no Banner anywhere."** It even missed `ssb.calu.edu`
  (a real Banner host). **Fix (v2, `ctlog_sweep.py`):** low concurrency (2 workers), retry crt.sh on
  502/503/timeout/non-JSON with backoff, and a hard `ct_ok` flag — a domain is only counted as "checked"
  if crt.sh returned real JSON; failed lookups go to `needs_retry.json`, NEVER counted as clean. v2
  health: ct_ok ≈ 9/10 (vs v1's 1/210). Reinforces the meta-lesson: never trust an "exhausted/empty"
  result without checking the tool actually ran.
- **Targets file overlaps schools.py** (e.g. `calu.edu` = PennWest, already shipped as a `PASSHE`
  subclass on a shared mepCode host). So dedup MUST be by school NAME, not host. `shipped_ref.json` =
  all 587 shipped names / 466 hosts / 591 ids for fast dedup screening at gate time.
- **`selfservice.*` / `*.elluciancloud` hosts = COLLEAGUE, not Banner** → these correctly fail the SSB
  probe; I collect them into `colleague_leads_for_codex.json` for Codex's lane (I don't work Colleague).
- **Tooling ready:** `gate_banner.py` (gates ANY host through production Banner.fetch — discovers real
  courses via the live subject list, reports open/full mix; validated against Northeastern = 44 open/26
  full, PASS). `ctlog_secondpass.py` (re-probes every "banner host, no live SSB" domain against the
  alt base_path `registration` + the old Banner-8 route `bwckschd.p_disp_dyn_sched` — closes the
  base_path/Banner-8 false-negative gap before declaring a domain Banner-free).

## Gate discipline (unchanged, enforced)
- Gate through the PRODUCTION adapter (`.fetch()`), never a side probe (batch-23 lesson).
- Numeric-enrollment Banner (reads `seatsAvailable`): disproof = LIVE-term real FULL sections
  (seats==0) mixed with open. Completed-term all-open is NOT disqualifying (post-drop melt).
- Dedup by NAME; latency/sibling-leak screen; classic PeopleSoft COMMUNITY_ACCESS = never ship.

## In flight (Builder, track only): Berkeley ~45k, Fairfield, SDCCD×3; SCF (batch 25) building.
Deploy pending Nathan (site live at 655; commits ready through 664 + SCF).
