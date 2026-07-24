# Lane status — Grab (research agent, successor to Grabber/Fable's research lane)

**Only Grab writes this file.** Codex/Build read it. Continuation of `lane-fable.md` (archived).
Single relay point to Build is unchanged: gated finds → README under `AWAITING GO-AHEAD` → on
Nathan's go, relay to Build (session local_f4c9ee6c-cfaa-41e0-bf31-348d87326105) as "Batch N" → mark SENT.
School adds relay DIRECT per deploy policy; money/UI/legal stay gated behind Nathan.

## ⭐⭐⭐ VSB (Visual Schedule Builder) CRACKED (July 20) — reusable platform, token solved, gated live
The anti-scrape token that blocked VSB for weeks is SOLVED. VSB Software Inc. runs ONE engine (unity.js/engine.js)
across MANY colleges → this crack is reusable across every VSB school = potential College-Scheduler-scale unlock.
Proven live on Contra Costa CCD (vsb.4cd.edu, guest/no-login):
- **TOKEN (nWindow, in unity.js):** t = Math.floor(Date.now()/60000) % 1000 ; e = t%3 + t%39 + t%42 ; append "&t="+t+"&e="+e.
  (My old lane note said t=epoch_ms — WRONG; it's epoch MINUTES mod 1000. Changes each minute; server accepts it — NO more "correct your timezone" rejection.)
- **Course keys:** GET /api/courses/suggestions?term={term}&cams={cams}&course_add={SUBJ}&page_num=0&sco=0&sio=1&already=
  → XML <rs ...>SUBJ NUM</rs>. Key format is "SUBJ NUM" with a SPACE (e.g. "MATH 114"), NOT a dash (my ENGL-1100 tries 500'd).
- **Seat data:** GET /api/class-data?term={term}&course_0_0={SUBJ NUM}&t={t}&e={e}&nouser=1 → XML.
  <classdata date="{epoch_ms}"> = request time (real-time server-render, NOT stale). Per <selection>=section; os= attribute (on <block>) = OPEN SEATS (os>0 open, os=0 FULL). enr/waiting also present. Campus= attr + cams param scope per-college.
- **GATE:** MATH 114 (Summer 2026 term=202620) sections os=[2,2,0] → FULL section (os=0) mixed with open = disproof HOLDS. MATH 135 os=[19,18]. Real numeric per-section open seats. Dedup: CCC/DVC/LMC all net-new.
- **4CD = 3 net-new colleges** (cams CCC_BRT_SRC_DVC_LMC; degree-granting = CCC Contra Costa, DVC Diablo Valley, LMC Los Medanos; BRT/SRC = centers). Campus-scope like SDCCD/VCCCD.
- Term select: javascript:UU.caseTermContinue(202620) (Summer 2026); Fall/Spring codes via the term menu.
✅ SHIPPED + DEPLOYED by Build (743→746: Contra Costa College, Diablo Valley College, Los Medanos College). Reusable VSB base + 3 subclasses. 104 sec gated, 0 mismatches, 0 cross-college leaks, prod-verified.
⚠️ MY GATE SPEC HAD 3 ERRORS — Build caught + fixed; THIS is the AUTHORITATIVE VSB spec now:
  1. os>0 ≠ OPEN (RESERVED-SEAT FALSE-OPEN, the big one): a section can have os>0 WITH isFull=1 when its remaining seats are RESERVED (os==nres exactly; verified on 5 sections). My "os>0 open, os=0 full" rule would have false-alerted all of them. CORRECT RULE = os>0 AND isFull==0. isFull is the authority; nres is NOT a discriminator (26 genuinely-open sections carry nres>0 with isFull=0).
  2. cams does NOT filter class-data (cams=CCC / DVC / all-five → BYTE-IDENTICAL payload). cams REQUIRED by /suggestions only (drop it → 0 keys). Campus isolation = CLIENT-SIDE on the block's campus= attr, and a college OWNS its satellites (DVC+SRC San Ramon, LMC+BRT Brentwood — verify each satellite on the COLLEGE's own site; guessing = silent miss). campuses = a SET per college, not a string.
  3. TERM: use the CURRENT registration term. Fall 2026 = 202630 (I wrongly gated 202620 = Summer, near-over). Codes = YYYY + 10 Spring / 20 Summer / 30 Fall.
  + LAB1 blocks carry os/me/ws = -1 (no seat data) and share the parent's secNo → dedup by secNo + skip os<0 (else the lab sentinel reads as a seat count). /suggestions resolves a full code in ONE hop but is FUZZY (course_add=BIOL → ANTHR 141L) → exact-match the space-stripped form, never "first result". HTTP 500 = course not offered that term → silence.
📋 BULK-BATCH RECIPE (per VSB host, Build needs exactly 4): (a) host (vsb.X.edu / schedulebuilder.X.edu); (b) CURRENT registration term code from criteria.jsp (inline term JSON, e.g. {"202630":{"name":"Fall 2026"...}}); (c) full underscore-joined cams string; (d) campus-code → COLLEGE ownership INCL satellites (verify each satellite against the college's own site — this is the care item; guessing causes silent misses). Then a subclass is 5 lines; single-college hosts trivial. Build is adding a verify-before-adopt refresh_term for the VSB family (term list is machine-readable on criteria.jsp) so the pinned-term per-semester bump doesn't become toil at 30+ schools.
   ⭐ NEXT (bulk): ENUMERATE VSB customer domains (vsb.*/schedulebuilder.* — VSB Software's client list) → each gate-able with this EXACT pattern. This is the path to a big batch. Build accuracy-verify os=0⟺full per adapter contract.
   ENUMERATION (July 20, in progress) — reusable token CONFIRMED on 2nd instance (UNT nWindow identical), but guest access VARIES per school, must check each:
   · 4CD (vsb.4cd.edu) = GUEST + CURRENT + real seats ✅ USABLE → 3 colleges relayed.
   · UNT (vsb.unt.edu) = guest + token works, but STALE (only past terms Fall2025 2025080 / Spring2026 2026010; ©2017 footer = legacy deploy). NOT usable for live alerts. 7-digit term codes (format varies per school).
   · Valdosta (vsb.valdosta.edu) = 302→ADFS/SAML SSO. Kent (vsb.kent.edu) = NXDOMAIN (VSB behind FlashLine). SSO-gated, SKIP.
   · CCBC vsb.ccbc.edu = conn refused (VSB likely portal-gated; find real URL). KCTCS = PeopleSoft-integrated VSB, likely SSO (verify).
   LESSON: the crack is reusable, but guest+CURRENT instances are a SUBSET — CA community-college districts (public-class-search culture, like 4CD) are the best bet.
   ENUMERATION CONCLUSION (July 20): crt.sh CANNOT do the pan-.edu search — `q=vsb.%.edu` → "Unsupported use of '%'" (crt.sh rejects leading-position wildcards). Domain-guessing (probed ~28 CA-CC vsb.{abbr}.edu) = 0 hits. KCTCS/Valdosta/Kent = SSO or NXDOMAIN; UNT = stale. So there is NO cheap way to enumerate guest VSB instances right now. HONEST RECALIBRATION: I over-hyped VSB as a "dozens of schools" bulk unlock; reality = most schools SSO-gate their VSB, guest instances (4CD-style) are UNCOMMON. Realistic VSB yield = 4CD (3 colleges) + the reusable crack (permanent: any future guest VSB is instant-gate). To find more guest instances later, need a VSB-client list WITH guest URLs (Modern Campus/vsbuilder.com case-studies, or stumble on them via other leads) — not worth grinding now (efficiency). Crack + 3 banked; move on.

## ⭐ CODEX BATCHES 87-97 re-gated (July 18) — 7 stock Banner PASS + USI buildable (net-new ~50k)
Re-gated Codex's newest GATED pile LIVE through production gate_banner.py (→ schools.Banner.fetch). All 7
produce real numeric seatsAvailable with FULL sections (seats==0) mixed with open in the LIVE term = disproof
PASS. Dedup by NAME confirmed net-new (Guam CC ≠ shipped Univ of Guam/Colleague; SIU Carbondale ≠ shipped SIUE).
Stock 4-line Banner subclasses, no mepCode:
- SUNY Delhi (~3k)         prod.banner.delhi.edu                     term 202609  ex ENGL 100  38sec 17o/21f
- Guam Comm College (~1.6k) reg-prod.gcctmsaas.elluciancloud.com:8103 term 202680  ex EN 110    19sec 16o/3f
- Washburn Univ (~6k)      banssb-lb-prod.washburn.edu               term 202630  ex EN 101    34sec 18o/16f
- Murray State (~10k)      prodssbstureg.murraystate.edu             term 202680  ex ENG 105   71sec 62o/9f  ⚠GUARD
- Univ N Alabama (~10k)    selfserve.una.edu                         term 202710  ex EN 111    62sec 31o/31f ⚠GUARD
- SIU Carbondale (~11k)    banssb1.siu.edu                           term 202660  ex ENGL 101  29sec 22o/7f
- Pasco-Hernando (~10k)    reg-prod.phsc.elluciancloud.com:8103      term 202701  ex ENC 1101  63sec 35o/28f
GUARDS (relay to Build):
 · Murray REQUIRED: reject instructionalMethodDescription=="Racer Academy" rows (concurrent/HS, not registerable = eligibility false-open).
 · UNA REQUIRED: reject "Taught at High School" rows (instructionalMethodDescription) — same eligibility risk.
 · SIU: seatsAvailable=-1 over-enrolled rows already closed by >0 rule (safe); Carbondale is the only campus.
 · PHSC: zero-capacity W10 row (maxEnroll=0) already closed by >0 rule.
 · All: clean wait/crosslist/reserved per Codex; adapter already requires seatsAvailable>0 (inherent false-open guard).
- USI (Univ Southern Indiana, ~10k) banproxyp.usi.edu 202710 = HELD-BUILDABLE. Stock fetch=0 because USI stores
  courseNumber with a LITERAL TRAILING PERIOD ("ENG 101."); _code regex \d{1,5}[A-Za-z]?$ strips/rejects it →
  txt_courseNumber=101 misses. RAW probe txt_courseNumber="101." → totalCount=34, 10o/24f REAL. FIX for Build:
  USI subclass preserving the trailing period in txt_courseNumber (+ Codex ENG-101 title-prefix guard). Real+net-new.
BESPOKE tier (Codex-gated — DATA-real [seats appear in a plain page fetch] but ENDPOINT UNTRACED = NOT handoff-ready; PARKED, low-ROI per Build):
 · Northwest College WY (~2k) area10.nwc.edu/nwcforms/Syllabi JSON: GetCurrentTerm→26/FA; GetScheduleDownload?term={t}&sub=ENG.
   ENGL-1010 current 7 safe-open/7 (6 CONC dual-enroll excl via cap=0); completed 25/FA 9 full = disproof. Open = SEC_CAPACITY>0
   AND (SEC_CAPACITY-ACTIVE_COUNT)>0 AND no CONC token; key=COURSE_SECTIONS_ID. VERIFIED.
 · Southern U A&M LA (~6k) myaccess.southern.edu/apps/courseschedule/Default.aspx?Departments=English&PageSize=100&Page=1&Term=F26.
   ENGL-101 17/17, Results(54), server-rendered numeric Enr/Cap/Wait. Open = Cap>0 AND Cap-Enr>0 AND Wait==0 AND no crosslist. VERIFIED.
 · UMaine Augusta (~4k) uma.edu/academics/courseguide/?doClassSearch=1&strm=2710&subject=ENG-busunit-UMS01&keywords=ENG+101&includeClosedClassSections=1.
   "N of M seats" (N=enrolled,M=cap) + explicit Open/Closed/Waitlisted; live mixed. GUARD: reject nonempty Combined Section ID; alert only status==Open AND M-N>0. VERIFIED.
 · UMaine Presque Isle (~1k) umpi.edu/academics/course-registration/?...subject=ENG-busunit-UMS07... same UMS pattern; 4 Open+4 Waitlisted mixed. wp-json pagination if it appears. VERIFIED.
→ Relayed 7 stock + USI-buildable + 4 bespoke to Build as school-adds (DIRECT; Nathan wants volume→1000). Session yield = 12 net-new validated (~55k students).
✅ SHIPPED (Build, 735→743): all 8 Banner live. USI trailing-period tweak works (34 sec 11/23). Eligibility guards live via additive Banner._eligible hook (Murray Racer Academy, UNA Taught-at-High-School removed cleanly; base no-op; 400-school regression clean). ZERO false-opens across all 8. Bespoke 4 pending Build custom adapters.
   COUNT RECONCILIATION: my per-school section counts above (Delhi 38 / Guam 19 / UNA 62 / Murray 71) were gate_banner's DISPROOF AGGREGATE over ~14 auto-discovered courses, NOT the example-course totalCount. Build's authoritative example-course counts: UNA EN 111=46 (23 eligible after Taught-at-HS filter), Guam EN 110=8, Murray ENG 105=56→54 eligible. No gating error — both real, different scope.
   LESSON (relay hygiene): label gate numbers by SCOPE — "gate-aggregate over K discovered courses (disproof)" vs "example course = N sec" — so Build doesn't read the aggregate as the example count.
   LESSON (bespoke endpoint-trace gate, Build caught July 19): for NON-Banner/Colleague bespoke sources, confirming seat data appears in a plain page fetch (grep "N of M seats") is NOT enough to relay as handoff-ready. Must BROWSER-TRACE the real data request the page fires (exact URL + method + params + response shape) + prove completeness (pagination) — like West Valley /data/ + IU catalog API. I relayed UMaine w/ Codex's wp-json pagination route unverified → it 404s (rest_no_route). Stock Banner/Colleague are exempt (production adapter IS the traced endpoint); bespoke needs a real trace before "buildable." Only trace bespoke when systems run dry or Nathan wants the specific school.

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

## CODEX OLD-GATED PILE re-swept (July 14, Nathan "codex did a lot of work") — 2 clean wins + freshness skips
Extracted un-actioned value from Codex batches 12-19 GATED leads that I never re-gated:
- **UVI (University of the Virgin Islands, ~2k)** ✅ READY: real-time .aspx schedclass.uvi.edu/stxschedule.aspx?term=202608 (Fall 202608/Spring 202601). Cols CRN/MAX/ENROLL/AVAIL/STATUS. Open=STATUS==ACTIVE AND AVAIL>0; key=CRN. Gate 376/8 live, 350/41 completed (disproof). 3 campuses = 1 school. Relayed.
- **Cayuga CC (NY, ~4k)** ✅ READY: cayuga-cc.edu/academics/schedule-of-classes/fall/, FRESH (29-min stamp). Availability embedded in title cell (col2), key=CRN. Gate 438/35 (real mix). Relayed.
- **Cal Poly Humboldt (~6k) SKIP**: pine.humboldt.edu daily report "as of 07:45 AM" fetched at 9:57 PM = ~14h STALE = false-open risk (like SJSU). Real-time is PeopleSoft-gated. Concordia Chicago SKIP (PDF export=stale). Lawrence (~1.5k) parked (Banner-8 real-time but need fuller disproof, small).
- NEW STANDARD GATE (saved to memory): staleness-timestamp check — any "as of/generated/updated" stamp gets compared to current time; hours-stale = skip. Caught SJSU + Humboldt; UVI/Cayuga passed.

## HUNT July 17-18: LACCD dead / Los Rios confirmed-defer / Batch 81 clean / VSB = TOP NEXT LEAD
- **Batch 81 (Illinois Eastern 3 colleges)** re-gated CLEAN through prod Banner + campus filter (Wabash Valley 5/1,
  Olney Central 2/2, Lincoln Trail 4/0, all EXACT to Codex, 0 false-opens). banprodss1.iecc.edu:8447, term 202730,
  campus first-token WABASH/OLNEY/LINCOLN. Relayed. Completes Codex Batch 80-84 re-gate (~15 net-new validated).
- **LACCD (9 colleges, ~200k) = DEAD/HOLD, fake-status.** Classic PeopleSoft COMMUNITY_ACCESS.CLASS_SEARCH.GBL —
  my documented fake-all-open trap. Codex caught it (LASC completed-term 14 rows all Open after they ended). I probed
  the IScript JSON API → returns HTML shell (no numeric enrollment_available), only stateful GBL w/ fake textual Open.
  Cannot gate without false-open risk. Do NOT chase the 9-college mirage. Same class as NAU/UCF/UH.
- **Los Rios ×4 (~75k) = CONFIRMED DEFER (cap).** Cracked the real param (searchBar= not my earlier subs=), but hard
  20/call cap, no pagination (offset ignored, no page ctrl, scroll fires no new calls), ENGWR 300 truncates 80 of 292.
  Silent-miss on flagship course = Delaware verdict. Parked unless LRCCD exposes a complete endpoint.
- **⭐ VSB (Visual Schedule Builder) = TOP NEXT-SESSION LEAD (reusable pattern).** Contra Costa CCD vsb.4cd.edu: live,
  campus-ENABLED, real seat data (XML os= open-seats attribute), 3 colleges. Endpoint: GET vsb.{school}.edu/api/class-data
  ?term={code}&course_0_0={SUBJ}-{NUM}&t={epoch_ms}&e={?}&nouser=1. BLOCKER: the &e= timezone anti-scrape token (server
  rejects with "correct your device timezone" unless t/e valid; t=(new Date()).getTime() confirmed, e-formula obfuscated
  in engine.js). CRACK VIA BROWSER CAPTURE of one real class-data request → replicate t/e → then ENUMERATE all VSB
  schools (VSB is used by many CA CCs + others = potential College-Scheduler-scale unlock). Highest ROI forward item.

## ⭐⭐ CODEX BATCHES 80-84 re-gated (July 15) — 12 net-new validated (~245k students!), directive worked
Codex pivoted HARD to system-shaped/self-screened/adapter-reuse work (my directive). Re-gated all through
PRODUCTION base Colleague.fetch(), reproduces Codex's numbers, ZERO false-opens (textual-Open withholds waitlist):
- **10 CLEAN base-Colleague drop-ins (~215k)** relayed to ship: Wake Tech(72k), Schoolcraft(30k), DuPage(28k),
  Southwestern(32k), Victor Valley(20k, salvaged from old IPEDS-exclude), Elgin(17k, :8173 port), Central
  Carolina(7k), Kellogg(5k), Coalinga(4.5k), Brunswick(2.6k). All 4-line subclasses, no RegisterableColleague needed.
- **Rancho Santiago x2 (~30k)** Santa Ana + Santiago Canyon: SHARED host colss-prod.cloud.rsccd.edu, needs
  LocationCodes campus hook (base returns first-model=SAC only, SCC invisible). Relayed w/ isolation spec.
- **Alamance HELD**: production fetch=NO DATA (diverges from Codex 38 rows), term/bootstrap issue.
- **Batch 81** (Illinois Eastern 3 tiny Banner schools, campus isolation) pending, lower priority.
KEY: Codex Batch 84 explicitly says "exact-software enumeration after multi-college-system screen, not famous-flagship"
+ did its own 4-killer screening. The directive I wrote (hunt systems, reuse adapters, self-screen) is exactly what
it is now doing. This is the pipeline working at scale.

## ⭐ CODEX BATCH 84 re-gated (July 15) — 4 CLEAN + net-new (~112k, Wake Tech 72k!), 1 held
Codex finally shipping system-shaped/self-screened work (batches 80-84 = multi-school Colleague/Banner reuse).
Batch 84 re-gated through PRODUCTION base Colleague.fetch(): Wake Tech (72k, selfserve.waketech.edu) 54o/142wl,
Schoolcraft (30k, self-service.schoolcraft.edu) 46o/20 EXACT, Central Carolina (ss-prod.cloud.cccc.edu) 25o/43,
Brunswick (ss2-prod-cloud.brunswickcc.edu) 14o/7 EXACT — all reproduce Codex, 0 open-with-0-seats, waitlist-with-
seats correctly withheld by base adapter (no RegisterableColleague needed). ALAMANCE HELD: production fetch=NO DATA
(3 host forms), diverges from Codex 38 rows — term-picker/bootstrap issue, my re-gate caught it. All 5 dedup net-new.
Relayed 4 ship + Alamance hold to Build. TODO: re-gate batches 80-83 (Rancho Santiago 2, Illinois Eastern 3, WHCCD+2,
DuPage/Elgin/Kellogg 3) — same Colleague/Banner family, ~13 more schools.

## ⭐ LOS RIOS CCD ×4 lead (July 14) — applied "hunt systems" strategy; discovered + characterized, 2 open Qs
Sacramento district: American River + Cosumnes River + Folsom Lake + Sacramento City, ~75k combined, ONE feed.
CONFIRMED: plain-client hub.losrios.edu/classSearch/getCourses.php (no auth, HTML fragments, Referer losrios.edu).
Per-college isolation built in via arcFilter/crcFilter/flcFilter/sccFilter (0 overlap verified). closedFilter=true
MANDATORY (default hides full=Maricopa trap). strm=1269,Fall2026. Real Open/Full/Waitlist status (CSS-classed),
class#=LEC/LAB &nbsp; 5-digit key, real-time (seconds-precision "accurate as of" stamp). OPEN QUESTIONS (relayed
to Build, NOT gate-passed): (1) pagination/completeness — single call caps ~20 for lecture subjects (MATH/HIST/PSYC=20;
BIOL=28,CHEM=49); browser got all 330 so pagination exists but offset=20 returned empty — must crack + verify a
huge subject returns complete (Delaware-cap check). (2) exact status parse. High ROI if pagination cracks = 4 colleges.
This is the strategy working (found a multi-college system) even though I couldnt fully close it solo.

## Great Falls + Quinsigamond BOTH DEPRIORITIZED (July 14) — fragile stateful portals
Traced both remaining bench leads; both are fragile stateful portals = poor ROI, NOT clean ships:
- **Great Falls College MSU** (~2k): Oracle APEX interactive report. Data REAL (Fall 202670 = 304 sec,
  gated page1 88 open/10 CLOSED, real Avail/Enr/Cap + "Consent of Registrar" soft-open nuance) BUT served
  via stateful wwv_flow.ajax (per-session id + checksums + 4-page pagination), no CSV export. Fragile APEX
  scrape for a 2k school. Verdict: skip. Relayed to Build.
- **Quinsigamond** (~13k): Jenzabar ICS ASP.NET portal (__VIEWSTATE 23KB, session cookie). Plain-client
  viewstate postback did NOT reproduce results (no __EVENTVALIDATION, postback returned 25KB no-data shell);
  needs full stateful Jenzabar flow. Data real per Codex but fragile viewstate scrape. Verdict: deprioritize.
- PATTERN: the clean plain-client public feeds in the queue are exhausted; remaining leads are stateful
  portals (APEX/Jenzabar/PeopleSoft) = fragile. Pipeline needs FRESH clean-feed leads (Codex/new discovery).

## VCCCD SHIPPED (718) + Great Falls / Quinsigamond next (July 14)
Build shipped VCCCD x3 off my trace (715->718). Re-gate found a cleaner structured CAMPUS_DESC field
(beats my Location-prefix, 0 residual) + 1073 dup CRNs at full scale my 1574-row sample missed (lesson
saved: sample uniqueness checks can miss dupes that only appear at full scale). Gate: Moorpark 53/20,
Oxnard 20/12, Ventura 47/19, status==seats>0 agreed on all 3672 rows post-dedup. Last 2 traced-needed
leads: Great Falls College MSU (Oracle APEX, Codex has a concrete 311-row gate already) + Quinsigamond
(Jenzabar portal). Moving to trace these next per Nathan standing request for more colleges.

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

---

## 2026-07-20 — SEARCH-ENGINE DISCOVERY LEVER (reusable) + 3 clean net-new for Build

**The lever (works, repeatable):** Google-index search surfaces LIVE Ellucian self-service tenants
directly, even though the cloud TLS cert is a wildcard. Queries that hit:
  - `"colleague.elluciancloud.com/Student/Courses/Search"` + subject/state/term words → Colleague cloud tenants
  - `"-ss.colleague.elluciancloud.com" course sections search subjects`
  - `"selfservice" "Student/Courses/Search" community college` (surfaces SELF-HOSTED Colleague on own domains)
  - `inurl:StudentRegistrationSsb ... classSearch site:.edu` → Banner-9 hosts
Each round surfaces ~10 hosts; dedup by full host string AND by school name against schools.py.

**DEAD-END confirmed — CT enumeration of Ellucian cloud tenants is IMPOSSIBLE.** crt.sh for
`%.colleague.elluciancloud.com` returns only the WILDCARD cert `*.colleague.elluciancloud.com` — individual
tenant subdomains never appear in CT. Same reason VSB enumeration failed. Search-index is the ONLY
enumeration path for cloud tenants; self-hosted (`selfservice.<college>.edu`) DO appear in CT under their .edu.

**Coverage is now ~90%** — most surfaced hosts are already shipped. Clean net-new yield ≈ 1-2 per search
round. Two structural filters on Colleague net-new:
  (a) **public-catalog vs login-gated.** If the tenant's page title says "…Sign in", the course catalog is
      login-gated → base Colleague.fetch returns EMPTY on every code → NOT monitorable, permanent defer.
      (login-gated this session: Alpena `acc-ss`, Garden City `gccc-ss`, Coffeyville `coffey-ss`, Columbus State `selfservice.cscc.edu`.)
  (b) **code convention.** Oregon common-course-numbering uses Z-suffixes (WR 121Z, MTH 111Z); CA CCs use
      ENGL 1A; TX uses ENGL 1301. Empty-on-all-codes at a PUBLIC catalog usually = wrong convention, not dead.

### READY FOR BUILD — 3 clean net-new (base Colleague `.fetch()`, all gated LIVE, disproof holds, addressable):
1. **Vernon College (TX)** — host `vernon-ss.colleague.elluciancloud.com`, adapter=Colleague, example `ENGL 1301`.
   Gated: ENGL 1301 = 26 sec (23 open/3 full), PSYC 2301 = 11 (9/2), MATH 1314 = 15 (15/0). TX common numbering.
2. **Clatsop CC (OR)** — host `clatsop-ss.colleague.elluciancloud.com`, adapter=Colleague, example `WR 121Z`.
   Gated: WR 121Z = 3 sec (1 open/2 full), BI 101 = 2 (2/0), MTH 111Z = 1 (1/0). **Oregon Z-suffix codes.**
3. **Southwest Texas Junior College (TX)** — host `colss-prod.swtxc.elluciancloud.com` (note `swtxc.elluciancloud.com`
   cloud, not `colleague.`), adapter=Colleague, example `ENGL 1301`. Gated: ENGL 1301 = 57 (44/13),
   MATH 1314 = 38 (31/7), HIST 1301 = 42 (38/4), PSYC 2301 = 40 (37/3). Uvalde TX; net-new by name.

**VERIFICATION RECEIPT for the 3 above (Grab, re-checked 2026-07-20 before handoff — every silent-miss vector):**
- **Term correctness (explicitly measured, not assumed):** all three `_pick_term` → **Fall 2026**. Note SWTJC's
  term description is **`'Fall 2026 Semester'`** (not bare "Fall 2026") — seed accordingly.
- **⚠️ ACCUMULATING FEEDS CONFIRMED — the term filter is load-bearing on these hosts, not decorative:**
  Clatsop WR 121Z raw = Winter 2026 (3) + Spring 2026 (1) + Summer 2026 (1) + **Fall 2026 (3 KEPT)**;
  SWTJC ENGL 1301 raw = Summer I (9) + Summer II (7) + **Fall 2026 (57 KEPT)**; Vernon = Summer (3) + **Fall (26 KEPT)**.
  Unfiltered, every one of these would fire wrong-term alerts. My reported counts are the KEPT (Fall-only) numbers.
- **My "57 looks high" flag — RESOLVED, legitimate:** 57 is a genuine single-term count (dual-credit volume across
  SWTJC's Uvalde/Del Rio/Eagle Pass service area), NOT accumulation.
- **Multi-catalog-row (IU Bloomington variable-topic trap): CLEAR** — every gated course returns exactly 1 row,
  so the adapter's first-match `break` (line 6707) drops nothing.
- **Completeness reconciles exactly:** MatchingSectionIds == sum across all terms (Vernon 29=3+26, Clatsop 8=3+1+1+3,
  SWTJC 73=9+7+57).
- **Collapse/skip surface: ZERO** — kept-term rows == usable == unique section keys for all 3 (26/26/26, 3/3/3,
  57/57/57); 0 skipped for missing seat counts, 0 unparseable Available, 0 duplicate keys.
- Dedup done by BOTH host string and school name. Live query (no cached snapshot) → no staleness risk.
- **Observation for Build (NOT proven harmful, no impact on these 3):** the term filter at line 6714 is a SUBSTRING
  test (`term.lower() not in description.lower()`). A host exposing both "Fall 2026" and e.g. "Fall 2026 Late Start"
  would match BOTH. None of these 3 hosts have such a collision — worth a glance on future Colleague adds.

### DISTRICT-WITH-CAVEATS (Build decides how to model, NOT a clean single ship):
- **North Orange County CCD** — Banner `ssb.nocccd.edu`. Fullerton + Cypress (credit) + NOCE (noncredit) on ONE
  host. **Two parallel term ladders:** credit term = **202610 "Fall 2026"**; gate_banner auto-heuristic wrongly
  picked **202615 "NOCE Fall 2026"** (highest code = continuing-ed subjects ABED/ESLA/ECED). Disproof PASSES on
  202615 (CC 215/415 seats=0 full). For the credit colleges, target 202610 + campus-split (like SCCCD). Fullerton/
  Cypress net-new by name.

### DEFERRED (need Build adapter work, not gate-able as-is):
- **Clemson** `regssb.sis.clemson.edu` — Banner getTerms returns HTML not JSON (WAF / session-prime needed).
- **Henderson State (AR)** — shared Banner mepCode=HENDSN → needs MEP multi-entity support.
- **Langston University** — shares OKState Banner via mepCode=LU → needs MEP support.

## 2026-07-20 — FLEET HEALTH SWEEP (all 747 schools, read-only through production `.fetch()`)
Ran every school's own `example` course through the production adapter. Script: scratchpad/fleet_health.py.
RESULT: **OK_MIXED 395 (52.9%) | ALL_OPEN 302 (40.4%) | ALL_FULL 44 (5.9%) | NO_DATA 6 (0.8%) | ERROR 0**.
Zero adapter crashes fleet-wide. ALL_OPEN at 40% is EXPECTED in July (pre-registration) and is not evidence of
breakage — the families' ability to detect "full" is proven by the 395 mixed + 44 all-full on the same adapters.

**All 6 NO_DATA diagnosed to root cause (do NOT treat NO_DATA as "dead" — 2 of 6 were false alarms):**
| school | verdict | evidence |
|---|---|---|
| `midmich` Mid Michigan | **KEEP — stale example** | ENG 111 = 34 sec (18 open/16 full); BIO/MAT/PSY all live. Example `MAT 104` no longer offered → change example to `ENG 111`. |
| `centenarynj` Centenary NJ | **KEEP — stale example** | ENG 2099 returns live data. 12 of 30 ENG models have sections. Example `EDU 3073` has no Fall sections → change to `ENG 2099`. |
| `rhodesstate` Rhodes State | **REMOVE** | Banner host gone: `/` serves the Apache Tomcat 9.0.104 default page, `/Student/Courses` 404, term menu 502. Pinned to stale term 202620. |
| `edisonoh` Edison State OH | **REMOVE** | TLS `CERTIFICATE_VERIFY_FAILED` — cannot connect securely at all. |
| `lvc` Lebanon Valley | **REMOVE** | Resolves term correctly ('Fall 2026') but **0 alive of 24 courses tested across 6 subjects** (ENG/BIO/PSY/MAS/CHM/HIS) despite 17+ courses having MatchingSectionIds. Serves nothing for the current term. |
| `princeton` Princeton | **REMOVE unless someone owns refresh** | API returns **HTTP 401** — the pinned anonymous `_TOKEN` has been rotated, exactly as the class docstring predicted. Fail-safe (returns {} → never a false open, trips operator_alert) but serves nothing. Revival = manually re-capturing a token from a browser behind a Cloudflare challenge, and it WILL rotate again = recurring liability. Nathan's call given elite-brand value. |

Method note that matters: NO_DATA has THREE distinct causes — dead host, stale example course, and "course exists in
catalog but has no sections in the current term." Distinguishing them requires (a) alternative courses, (b) pulling
REAL course codes from the school's own catalog, (c) checking `MatchingSectionIds` before blaming the adapter. I
nearly recommended removing 2 healthy schools by skipping (b).

## 2026-07-20 (late) — PEOPLESOFT VEIN: 2 gated net-new + KCTCS VSB lead (16 colleges)
**Why this vein:** PeopleSoft is only 39 of 743 shipped, and 34 of those are ONE system (WA ctcLink on
`csprd.ctclink.us`) — so only 5 standalone PS schools exist. The adapter is proven (50 fulls, 11 mixed members)
and its own docstring says each school is a ~4-line subclass. Discovery signature that works in search:
`WEBLIB_HCX_CM.H_CLASS_SEARCH` / `H_BROWSE_CLASSES` / `IScript_Main`.

### READY FOR BUILD — 2 net-new (dedup'd by BOTH host and name; new gate checks applied):
1. **CSU Chico** — `host=cmsweb.csuchico.edu site=CCHIPRD inst=CHICO term=2268` (Fall 2026), **STOCK PeopleSoft
   adapter, no changes needed**. Gated live: MATH 105 = 26 sec (7 open/19 full), PSYC 101 = 5 (0/5 — proves
   full-detection), CHEM 111 = 16 (4/12), BIOL 102 = 11 (6/5), HIST 130 = 17 (13/4). `resolve_term()` -> 2268
   correctly, ignoring both Winter 2026 (2261) and Spring 2027 (2272). **Suggested example = `MATH 105`**
   (NOT ENGL 130 — returned empty).
   - Gate check 1 (quarter): Chico is a SEMESTER school; its Winter 2026 is an intersession, and the new
     `_auto_season` winter guard refuses it anyway -> **no `auto_term=False` needed**.
   - Gate check 2 (populations): term list has exactly ONE term per season -> **no flag needed**.
2. **Illinois Central College (IL)** — `host=eservices.icc.edu site=eservices inst=ICC term=2273` (Fall 2026).
   Gated live: ENGL 110 = 46 sec (36 open/10 full), MATH 110 = 16 (11/5), BIOL 110 = 6 (4/2). `resolve_term()`
   -> 2273. **NEEDS A SMALL ADAPTER VARIANT:** its URL path segment is **`/CAMP/`** where `PeopleSoft` hardcodes
   `/SA/` (in `reg_url`, `_cs`, and `_session`). Suggest a class attr e.g. `SEG = "SA"` overridden to `"CAMP"`.
   I verified the data by overriding those three methods. No winter term; one term per season -> no flags.

### ⚠️ TRAP FOUND — do NOT use "the institution code worked" as validation
On these SINGLE-institution hosts the `?institution=` param is **ignored**: every bogus code I tried
(CCHIC/CHI01/CSUCH/CHIC/CCHI/CHICO1/CSUCO for Chico; ICC01/ILCC/ICCOL/ICCTL/ICENT for ICC) returned the
IDENTICAL term list. So a code "working" proves nothing — only a multi-institution host (ctcLink-style) actually
validates it. Pick the real code from the school's own URLs, don't infer it from a successful response.

### CSU SYSTEM SWEEP (2026-07-21) — 1 more gated, and a big vein correctly REJECTED
Hypothesis: CSU Chico worked on `cmsweb.csuchico.edu`, and all 23 CSU campuses share the "Common
Management System" PeopleSoft platform → possible system-level unlock. Probed `cmsweb.<domain>` across
22 campuses: 11 hosts alive. **But the unlock does NOT exist, for a good reason:**
- Most CSU campuses expose only the CLASSIC `COMMUNITY_ACCESS.CLASS_SEARCH.GBL` guest search — the
  KNOWN ALL-OPEN TRAP (every section reads "Open" regardless of real enrollment; proved on NAU, killed
  the 22-flagship batch 7). **NEVER SHIP THESE.**
- Only campuses with the MODERN Fluid search (`WEBLIB_HCX_CM.H_CLASS_SEARCH`) are gate-able.
- **Confirmed CLASSIC-only (do not re-probe):** CSU Maritime (`cmsweb.csum.edu`, CMAPRD), CSU San Marcos
  (`cmsweb.csusm.edu`, CSMPRDP), CSU East Bay (`cmsweb.cs.csueastbay.edu`, CEBPRD), CSU Bakersfield
  (`cmsweb.cms.csub.edu`, CBAKPRD). Fullerton / Fresno State / Cal State LA / Humboldt / Sonoma /
  Dominguez Hills returned nothing on any reasonable site-name guess — almost certainly classic too.
- **Decisive test (reusable):** hit
  `/psc/{site}/EMPLOYEE/{seg}/s/WEBLIB_HCX_CM.H_CLASS_SEARCH.FieldFormula.IScript_ClassSearchOptions?institution=X`
  after opening the browse page for a session. JSON with a `terms` array = MODERN, gate-able.
  HTML back = classic-only = skip. (Chico as control returns terms; that's how you know the probe works.)
- NOTE `cmsweb.<domain>/` root is a 157-byte "CMS Redirect" stub pointing at calstate.edu on EVERY campus
  incl. Chico — a live root proves nothing. Only the modern-endpoint probe above is meaningful.

**READY FOR BUILD — CSU Channel Islands** (~7k, 4-year public; net-new by name AND host):
  `host=cmsweb.csuci.edu  site=CCIPRD  inst=CI  term=2268` (Fall 2026), STOCK PeopleSoft adapter.
  Gated live: ENGL 105 = 11 sec (0 open/11 full), BIOL 200 = 7 (4/3), HIST 271 = 3 (1/2), CHEM 121 = 4
  (0/4), MATH 105 = 3 (0/3), MATH 150 = 3 (3/0), PSY 100 = 3 (0/3). Suggested example = **`BIOL 200`**
  (real mix). `resolve_term()` -> 2268, correctly ignoring Winter 2026 (2261) and Summer 2026 (2265).
  Gate checks: (1) QUARTER? No — semester school, its Winter 2026 is an intersession and the
  `_auto_season` guard refuses winter regardless -> no `auto_term=False`. (2) POPULATIONS? One term per
  season, no Pharmacy/Cont-Ed/Grad split -> no flag. Note `seg` works as BOTH `SA` and `HRMS`; use `SA`.

### ✅ KCTCS — 16 NET-NEW colleges SHIPPED + DEPLOYED (2026-07-21): 746 → 762 live
### ⚠️ CORRECTION: my prefix-isolation recommendation was WRONG — Build reversed it (see below)
Traced kctvsbprd.ps.kctcs.edu VSB via browser + production VSB.fetch(). All 16 pass every gate.
- **host** = `kctvsbprd.ps.kctcs.edu`  **term seed** = `4264` (Fall 2026; menu = Summer 2026 + Fall 2026 only,
  no premature future term; auto-rolls via existing VSB.refresh_term).
- **cams** (for /suggestions only; the adapter comment confirms cams does NOT filter class-data) = the 36
  `KCTCSi*` campus codes joined by `_`. Derive by joining all `mscams` codes from
  `https://kctvsbprd.ps.kctcs.edu/api/v2/multiselectdata.js`, or hardcode the 36-code string. Same for all 16.
- **class-data `campus=` attribute carries the `KCTCSi*` codes** → maps to college via multiselectdata's
  `college` field (authoritative). Isolation is per-college campus SET, like 4CD (DVC+SRC).
- **`KCTCSiMYCEC` — I misread this as a Maysville orphan to sweep in. IT IS NOT. Build corrected me:** the
  three-level multiselectdata (16 colleges / 36 campuses / ~1,590 LOCATIONS — I only parsed the campus level)
  names MYCEC = **"Maysville CT E KY Correctional"** — sections taught INSIDE the Eastern Kentucky Correctional
  Complex. KCTCS DELIBERATELY omits it from the public campus picker. My prefix rule would have alerted regular
  Maysville students about seats in PRISON sections they cannot enroll in = eligibility FALSE-OPEN (Racer-Academy
  class). **Silent exclusion is CORRECT here, by the host's own design.** Prefix is ALSO structurally unsafe:
  location-level codes cross college lines (Ashland's own locations carry a Maysville MYCRC code), so prefix can
  MIS-ASSIGN across colleges. **SHIPPED = exact per-college sets from the mscams authority, MYCEC EXCLUDED.**
  Live-proven: class-data campus= uses exactly the 36 mscams ids over 5,931 sections / 60 courses; MYCEC was the
  ONLY non-mscams value in the wild, and the registered Maysville adapter returns 26 ENG 101 sections without the
  MYCEC (CZEC) prison section, byte-equal to an independent raw parse.
- **GATE-KIT LESSON (my error, worth keeping):** when a multi-college host PUBLISHES its own college→campus map,
  USE IT VERBATIM — never derive ownership from code-pattern/prefix. A campus code the host OMITS from its public
  picker is a DELIBERATE EXCLUSION to investigate (prison / restricted-enrollment / non-public), NOT an orphan to
  sweep in — sweeping it in is an eligibility false-open. Same instinct as "don't validate a code by 'it worked'".
- **Disproof HOLDS** (district-wide ENG 101): 215 sections isFull=1 (FULL) vs 411 os>0 & isFull=0 (OPEN).
  isFull is the authority (existing adapter rule os>0 AND isFull==0; LAB1 os=-1 skip; secNo dedup — all handled).
- **Production-adapter gate, term 4264, per-college isolation proven** (Bluegrass=1 campus vs Jefferson=6 → different counts):
  Bluegrass ENG 101 = 134 sec (78 open/56 full), MAT 150 = 55 (33/22), BIO 112 = 23 (13/10).
  Jefferson  ENG 101 =  86 sec (61 open/25 full), MAT 150 = 40 (31/9),  BIO 112 = 15 (11/4).
- **Dedup:** all 16 net-new by name. The 3 namesake hits are DIFFERENT schools (Ashland University OH ≠ Ashland CTC KY;
  GateWay CC AZ ≠ Gateway C&TC KY; SUNY Jefferson CC NY ≠ Jefferson C&TC KY). Host kctvsbprd = net-new.
- **example** = `ENG 101` works at all 16 (universal writing course; Build confirm per-college returns data).

**THE 16 COLLEGES → campus stem (prefix) / explicit KCTCSi* set:**
  Ashland C&TC → ACTC  | Big Sandy C&TC → BSC | Bluegrass C&TC → BLC | Elizabethtown C&TC → ECTC (ECTC,ECTCL,ECTCS)
  Gateway C&TC → GTW | Hazard C&TC → HZC (HZC,HZCKN,HZCLE,HZCLC,HZCTC) | Henderson CC → HEC
  Hopkinsville CC → HPC (HPC,HPCFC) | Jefferson C&TC → JFC (JFC,JFCBC,JFCCA,JFCSC,JFCSW,JFCTC)
  Madisonville CC → MDC | Maysville C&TC → MYC (MYC,MYCRC,MYCLV,MYCMC,**MYCEC-orphan**)
  Owensboro C&TC → OWC | Somerset CC → SMC | Southcentral KY C&TC → SKY
  Southeast KY C&TC → SEC (SEC,SECHA,SECKC,SECMD,SECPV,SECWH) | West Kentucky C&TC → WKCTC
Net: 743 → 759 if all 16 land. Per Build, each VSB college ≈ 5 lines + the (recommended) prefix-isolation tweak once.

### 🔬 DEEP-RESEARCHER BATCH 2 (2026-07-22) — 10 regional 4-year universities. RESULT: 3 BUILD + 1 dup, much better hit rate than CCs
- **Sam Houston State (~21k, TX): BUILD ✓** — clean 3-line Banner subclass. host `banxeappx.shsu.edu` term 202680.
  Independently gate_banner-verified (27 open/20 full, real seats). RELAYED to Build.
- **Cleveland State (~15k, OH): BUILD ✓** — BESPOKE Jenzabar CampusNet (~50-70 lines). host `campusnet.csuohio.edu`,
  guest session (/guest/search_guest.jsp) → GET /AJAX/AJAXMasterServlet?...function=getClasessResults&termVal=117-Fall 2026
  &acadVal=UGRD&subject=<X>. Stat col O=open/C=full/X=cancel(fail-closed); Enrl/Tot seats; ClassNr key. auto_term=NO
  (future terms listed). Careers UGRD/GRAD/LAW/CNED = separate queries, merge by ClassNr. INDEP-VERIFIED 51 full/46 open.
  RELAYED. ⭐ Jenzabar CampusNet = possible FAMILY.
- **Texas A&M-Commerce (~12k, TX): BUILD ✓** — BESPOKE ASP.NET (~40-80 lines). host `appsprod.tamuc.edu`,
  GET /Schedule/Schedule.aspx?Term=202680&Dept=<DEPT>. NO status flag → open iff Enrolled<Seats; over-enrolled(23/20)=FULL.
  CRN key. auto_term=FALSE. ⚠️ latency FLAG (one >120s hang — verify p95). Dept≠prefix (map prefix→Dept). RELAYED.
- **Stephen F Austin: DUP** (existing SFAustin/ListcrseBanner8, schools.py:2332) — batch-23 blocker CLEARED, catalog route
  now returns live Fall 2026 (term_in=202710). Build to verify/ENABLE. Free 4th.
- **SCRAP (5):** James Madison + Northern Illinois (classic COMMUNITY_ACCESS all-open trap; modern JSON guest-blocked
  "Authorization Error"); Illinois State (public = Algolia batch snapshot, no real-time timestamp → stale); Boise State
  (all-open trap + :8443 host TLS-RESETS datacenter IPs → cloud poller can't connect); Eastern Michigan (Banner but NO
  public guest host — registrar page confirms search is inside authenticated myEmich = login-gated).
- **NEAR-DONE LEAD — Bowling Green (~19k, OH):** bespoke JS app `services.bgsu.edu/ClassSearch/`. Traced via browser:
  PUBLIC (no login), Fall 2026 = strm 2268, clean JSON API (`/ClassSearch/subjectsForAdvancedSearch.json` etc.); results
  come from a FORM SUBMIT (a results .json endpoint not yet captured — the `search.htm?...&subject=X&undergraduate=true`
  URL only pre-loads the form). REMAINING: submit the form (subject + Undergraduate + Search) in a browser, capture the
  results-JSON endpoint, prove open/full. ~90% done. Likely BUILD (bespoke). Good finish-target for a follow-up.
KEY LESSON: 4-YEAR regional universities are the clean net-new vein (3/10 BUILD vs mega-CCs 0/6). Wins split: guest
Banner cloud (SHSU, ECU) + bespoke public schedule apps (Jenzabar CampusNet=Cleveland; ASP.NET=TAMU-Commerce). Losers:
classic PeopleSoft COMMUNITY_ACCESS (all-open trap), Algolia-snapshot front-ends (stale), self-hosted Banner behind SSO.
The school-dash-researcher (fail-closed spec-or-SCRAP) is the right tool; run 8-12 at a time; I finish NEEDS-HUMAN/
NEEDS-BROWSER ones with the in-app browser (which the field agents lack).

### 🔬 DEEP-RESEARCHER BATCH (2026-07-22) — 6 biggest un-shipped schools; school-dash-researcher agents
Spawned 6 parallel school-dash-researcher agents on the 6 biggest net-new schools (~455k students total). Results:
- **East Carolina U (~28k, 4-year NC): BUILD ✓** — host `banprd-ssb-cld.ecu.edu`, base_path StudentRegistrationSsb,
  term 202680 (Fall 2026). Independently gate_banner-verified: 100 subjects, 22 open/20 FULL, real seat counts
  (ACCT 2401 = 10 sec all seats=0). Net-new. RELAYED to Build. (Also flagged in memory seatwatch-ecu-build-candidate.)
- **Broward College (~60k, FL): BUILD (conditional)** — bespoke FCCSC HTML scraper, host `mybc.broward.edu`,
  GET /FCCSC/servlet/registration.IAS012N2s (prime via coursesearch.jsp). "Seats Left" 0=FULL/>0=OPEN, classStatus=A
  MANDATORY. Disproof PROVEN (ENC1101 = 18 full/60 open). ⚠️ ONLY Summer 2026 (20263) is public NOW; FALL 2026 not
  yet in the guest term dropdown → human re-check in ~2-3 wks before counting for Fall. RELAYED to Build.
  ⭐ `/FCCSC/servlet/` = SHARED Florida statewide platform → possible FCCSC FAMILY (other FL colleges TBD; NOT MDC/Valencia).
- **SCRAP (correctly — the reputation bar working):**
  - Miami Dade (~100k): clean Fluid JSON login-gated; only guest path = classic COMMUNITY_ACCESS all-open trap.
  - Houston CC (~55k): PeopleSoft fully login-gated (classic + Fluid → ?cmd=login); also the known trap. (Already SCRAP-noted schools.py:8072.)
  - Valencia (~70k): guest Banner JSON EXISTS but FLOORS seatsAvailable at 1 — 0 full / 2453 sections in a completed
    term = FAKE-OPEN. Would false-alert on everything. host banner.aws.valenciacollege.edu (do NOT build).
  - Dallas College (~80k): public Colleague `selfsrv.dcccd.edu` is CONTINUING-ED ONLY; credit courses are login-gated Workday.
- **NEEDS-HUMAN:** Lone Star (~90k) — guest access real (published guest creds), but clean CX JSON is auth-blocked
  ("Authorization Error"); only a STATEFUL Fluid guest search; open/full UNPROVEN → fail-closed, needs a browser check.
LESSON: the biggest un-shipped schools are mega-CCs that are login-gated / fake-open / CE-only. The clean net-new are
4-YEAR universities on guest Banner cloud (ECU). The school-dash-researcher agent is the right tool for these (deep
per-school trace + fail-closed disproof); parallelize it. Valencia's seatsAvailable-floored-at-1 is a NEW fake-open
variant to watch for on guest Banner JSON.

### 📉 SYSTEMATIC DOMAIN-PROBE (2026-07-21) — 40 colleges, 0 flawless net-new; remaining pool is enriched for UN-gate-able
Probed 40 community/state colleges against domain-based patterns (selfservice./reg-prod.ec./ssb./bannerweb.<domain>).
5 live hosts surfaced, ALL net-new by name — but ALL failed the flawless bar on gating:
  - Austin CC (~40k): public schedule EXPLICITLY not real-time; real-time seats login-gated → stale = false-open risk.
  - South Plains, Sinclair OH: Colleague `selfservice.<domain>` returns EMPTY on every code = login-gated catalog.
  - Delaware County PA `banner.dccc.edu`: 522 (down/Cloudflare).
  - South Texas College (~30k): public Banner `registration.southtexascollege.edu` is CONTINUING-ED ONLY (all
    terms "CE Quarter"); credit catalog is login-gated JagNet.
KEY LESSON: at 762, the un-shipped pool is ENRICHED for un-gate-able schools — the easy public real-time catalogs
are already shipped, so a "live host found" no longer implies "flawlessly gate-able". Domain-probe hit-rate for
LIVE host ≈ 13%, but for FLAWLESS-GATE ≈ 0%. Scaling the probe just scales the login-gated/stale failures.
Verdict: coverage growth now needs fresh discovery INFRA (Codex/ctlog), not more manual probing.

### 📉 EFFICIENT VEINS MINED OUT (2026-07-21) — fresh discovery now surfaces ONLY already-in schools
Ran 3 fresh discovery rounds (Colleague cloud, Banner cloud `reg-prod.*.elluciancloud.com`, modern-PeopleSoft) +
tested GA TCSG. EVERY candidate surfaced was ALREADY IN: Eastern Oregon, Georgetown, Kern/Bakersfield, Johnson
County CC, Middlesex College NJ, Goodwin U CT. 0 net-new. Georgia TCSG + Wisconsin Technical both fail the
efficiency bar (non-discoverable/bespoke hosts). CONCLUSION: at 762 the discoverable+efficiently-gateable veins are
exhausted; net-new now requires bespoke per-school traces (fails the flawless+efficient bar) or fresh Codex leads.
Periodic search-discovery still worth a cheap occasional round (relay anything net-new), but expect ~0/round.

### ❌ WISCONSIN TECHNICAL — TESTED, FAILS the efficiency bar (2026-07-21), do NOT re-attempt as a batch
Probed all 14 not-already-in WTCS colleges: only Western Tech resolved a host (westerntc-ss.colleague.elluciancloud.com)
and it is ALREADY IN + returned empty on every standard code (WTCS uses a non-obvious numbering scheme). The other 13
have NON-DERIVABLE cloud codes (Nicolet = "nicoletcollege" not "nicolet") and DON'T surface via search-discovery
(query returned Moraine VALLEY IL, a namesake). So WTCS = per-college host-hunt + per-college code-format reverse-
engineering = 13 bespoke efforts. Fails "efficient." Nathan's explicit rule = don't force it; DROPPED. (Georgia TCSG
below likely same shape — untested, treat as low-ROI individual grind, not a system unlock.)

### (superseded) VEIN NOTE — Wisconsin Technical (16) + Georgia TCSG (22)
Dedup confirms mostly NET-NEW (only Waukesha County Technical is in). BUT these are NOT a KCTCS-style single-host
outlet: each college is on its own/varied platform, and at least Madison College uses a BESPOKE site search
(madisoncollege.edu/academics/search), not standard Banner/Colleague self-service. Common host patterns
(ssb./banner./selfservice.<domain>) did NOT resolve for Madison/Chattahoochee/Gwinnett — hosts need per-college
discovery. So this is an INDIVIDUAL-COLLEGE GRIND (host-find + platform-ID + gate, some bespoke → per lesson 11 an
endpoint-trace each), ~38 small technical colleges. Legit net-new coverage, LOW ROI/hour vs. a system unlock.
Georgia TCSG has "eCampus" but that's ONLINE-only enrollment, not the full schedule. Verdict: a focused future
grind or a Codex-style batch, not a quick win. Lists: WTCS 16 (Madison/Milwaukee/Gateway/Fox Valley/Northeast WI/
Chippewa Valley/Western/Blackhawk?/Lakeshore/Mid-State/Moraine Park/Nicolet[IN]/Northcentral/Southwest WI/Waukesha[IN]/
Wisconsin Indianhead); TCSG 22 (Chattahoochee/Gwinnett/Athens/Savannah/Wiregrass/Albany/Central Georgia/Georgia
Piedmont/Columbus/Coastal Pines/West Georgia/South Georgia/Southern Crescent/Southeastern/North Georgia/Ogeechee/
Oconee Fall Line/Lanier/Georgia Northwestern/Augusta/Atlanta Metro?[USG]/Gwinnett). Verify each net-new before gating.

### DEFERRED single-school VSB lead (2026-07-21): UNT Dallas `vsbdallas.unt.edu`
NEW by name. VSB engine confirmed, term menu has Fall 2026 (2026030) BUT also a stale Summer 2024 (staleness-check
before trusting the menu). SINGLE institution — mscols/mscams=0, so no KCTCS-style multi-college payoff and the
cams derivation differs (needs its own trace). ~4k students, login text present (guest access unconfirmed — KCTCS
tripped the same heuristic yet was guest-open, so not decisive). Low ROI: heavy per-school trace for one small
school. Only worth it if Nathan wants UNT Dallas specifically or the systems veins stay dry. Multi-college VSB
jackpots (4CD, KCTCS) are DONE; remaining VSB instances found are login-gated (Kent State, Valdosta, McGill, UNT-main).

### (superseded lead note) — KCTCS via VSB, 16 colleges on one host
`https://kctvsbprd.ps.kctcs.edu/criteria.jsp` — confirmed a genuine VSB instance (Modern Campus / vsbuilder.com,
original authors Sean+Alan Weeks) with **explicit public guest access** ("If you're not one of our students... you
can still check out all the classes"). Has a THREE-level `#collegeSelector` / `#campusSelector` /
`#locationSelector` hierarchy. Config is JS-loaded (no terms/cams in the HTML), so it needs the API trace to
produce Build's recipe items (b) term seed, (c) full cams string, (d) campus->college ownership. Item (d) is the
one with no automated fallback — must be verified against each college's own site. NOTE KCTCS's PeopleSoft
(`students.kctcs.edu`, site `stdsaprd`) has a PUBLIC browse page but its JSON API returns HTML = auth-gated,
so **VSB is the way in, not PeopleSoft.**

### DEAD ENDS (don't re-probe)
- **Univ of Pittsburgh** `pitcsprd.csps.pitt.edu` — browse page redirects to SIGN-IN; no guest class search.
- **NDUS connectND** `studentadmin.connectnd.us` — returns a 435-byte POST-redirect shell, no content.
- **Classic PeopleSoft `COMMUNITY_ACCESS.CLASS_SEARCH.GBL`** — surfaced CWU (`cwucsprd.peoplesoft.cwu.edu`),
  NAU (`peoplesoft.nau.edu`), Glendale (`psprd.glendale.edu`). **NEVER SHIP** — this is the known all-open trap
  (every section reads "Open" regardless of real enrollment; NAU is the school that proved it). Skipped on sight.

## 2026-07-20 — SECOND term bug found by reading PROD LOGS: `_pick_current_term` picks SUB-POPULATION terms
Prod `[term]` lines look benign ("detected X but no live data yet — keeping Y") but are a STANDING ALARM: the
picker is trying to select a sub-population term and ONLY the data-gate is preventing a wrong-term flip.
- emporia wants **202651 "Fall 2026 Accelerated"** over 202650 "Fall 2026"; ramapo wants "Fall 2026 Cont Ed"
  over "Fall 2026"; roosevelt wants "Fall 2026 Pharmacy"; earlham wants "Seminary Fall 2026-27" over
  "EC Fall Semester 2026-27"; unm wants 202686 over 202680.
- **Root cause (two gaps, both absent from the Banner picker but PRESENT in the Colleague one):**
  (1) `_pick_current_term` has **NO sub-term penalty and NO deterministic tie-break** — same-season terms tie at
      the same delta and the FIRST one in list order wins (`delta < best_delta`, strict). Colleague `_pick_term`
      instead uses `key=(delta, subpenalty, len(desc))` → plainest same-delta term wins, deterministically.
  (2) the Banner `_SUBTERM` tuple MISSES these: 'accelerated' absent; 'continuing' present but does NOT match
      the literal "Cont Ed"; 'seminary'/'pharmacy' absent. Colleague's `_SUBTERM_RE` catches accelerated + cont ed
      (still not seminary/pharmacy — those are POPULATIONS, not formats).
- **Risk:** the moment any of those sub-terms publishes sections, that school flips to the wrong population and
  its main-semester watchers silently starve. Same silent-miss class as the delta fix.
- **Note:** Banner.refresh_term's own docstring already prescribes `auto_term = False` for schools with PARALLEL
  same-season terms — these 5 qualify and are NOT pinned. So the documented mitigation exists but wasn't applied.
- **Suggested fix (Build's call):** give `_pick_current_term` the Colleague tie-break `(delta, subpenalty, len)`
  + extend the screen ('accelerated', 'cont ed'); set `auto_term=False` for genuine parallel-population schools
  (pharmacy/seminary) since no text rule can distinguish those safely.
- **CURRENT USER EXPOSURE: ZERO** — live watches cover only umd/usf/ou; none of the 5 has a real watcher.
- **Separate flag: `umd` has NO refresh_term at all** (term hardcoded 202608 = Fall 2026, correct today) yet is
  **14 of 17 live watches (~82% of all usage)** — 11 of those are CMSC216 alone. Needs a manual bump at semester
  turnover or it silently serves a stale term to most of the user base. Worth auto-roll or a calendar reminder.
  (Corrected from an earlier miscount of 13/17 in the message to Build; substance unchanged.)

## 2026-07-20 — ACCURACY FINDING relayed to Build: term roll-off threshold `delta < 1` vs `delta < -1`
Investigated Build's hypothesis (Banner/fose/PS/MinnState/UIUC pickers may early-roll like the VSB rule he
rejected). Every picker IS calendar-anchored (parses "Fall 2026" from human descr, picks min delta) — so the
naive "newest-with-data" selector is NOT the bug. Real exposure = the roll-off cutoff, split inconsistently:
  - **`delta < 1`** (rolls off CURRENT term at its START month — Aug 1 for Fall): **~24 pickers**, incl. the
    shared Banner `_pick_current_term` (whole vanilla Banner fleet), Fose (11 hosts), UIUC, all UC+CSU
    campuses, Berkeley, USC, Rice, TAMU, Purdue, UOregon, Maricopa, RCCD, WVMCCD, IUBloomington, Wabash,
    SynthTermColleague, QuarterColleague.
  - **`delta < -1`** (keeps current term through add/drop, rolls ~Oct): only 4 — PeopleSoft, MinnState,
    Colleague base, CollegeScheduler. (UIUC docstring line 542 misdescribes PeopleSoft as delta<1 → fingerprint
    of an incomplete refactor: corrected in the 4 newest, never back-ported to the ~24 older.)
  - **Consequence:** delta<1 refresh_term still data-gates + keeps last-known-good, so a school whose next term
    ISN'T published early stays safe. But a school whose next term goes live BEFORE add/drop ends (the exact
    early-publish case Build proved on VSB) → gate passes → adopts the future term mid-add/drop → silently
    starves every current-Fall watcher. delta<-1 is immune (calendar holds Fall until Oct regardless).
  - **✅ RESOLVED 2026-07-20 — Build verified independently, fixed all 24 → `delta < -1` (28 correct sites), DEPLOYED + prod-verified.**
  - **Impact was WORSE than I first wrote (Build's correction, and my own test output already showed it):** on a
    menu containing a Winter term it doesn't merely roll off Fall for a fortnight — it LATCHES onto Winter and
    never returns (Aug 5 / Aug 25 / Sep 15 / Oct 15 all → Winter 2026). That's the ENTIRE Fall semester on the
    wrong term including all of add/drop, fleet-wide, with no false opens — pure silence. Lesson for me: I had
    the Oct-15 row in my own output and still characterized it as an add/drop-window problem; read the last row.
  - Sharper tell of the incomplete refactor than the docstring: **SynthTermColleague and QuarterColleague
    SUBCLASS the already-corrected Colleague base but carried their own buggy `delta < 1` copies.**
  - Why direct-deploy was safe: provably a no-op the day it shipped — the two thresholds differ only for a term
    at delta 0 or -1 (one starting this month or last), and no season starts in June/July (spring=1, summer=5,
    fall=8, winter=12), so no adapter could change term that day by construction. Empirically confirmed too
    (Fose 11/11 + UIUC/UCI/UCLA/SFSU/Purdue/TAMU/Rice/IU/USC all unchanged). Post-fix boundary: holds Fall
    Aug 1 / Sep 15 / Sep 30, rolls Oct 15; spring & summer symmetric.
  - **Process lesson (any fleet-wide sweep): 8 of the 24 sat at a different indentation, so the first bulk pass
    silently missed them — only a site-COUNT assertion caught it. Count matching sites before AND after; never
    trust a bulk replace.**
  - Prevalence sweep: **dropped** by agreement — the fix is shipped and safe regardless, so prevalence would
    only size the historical bite, not change any decision.
  - Follow-up debt (logged, NOT done): collapse the ~24 duplicated pickers into a shared helper. The duplication
    is precisely what let the original correction reach only 4 of 28 families. Deferred as real risk (differing
    term formats/return shapes) vs. the time-boxed threshold fix.


═══════════════════════════════════════════════════════════════════════
2026-07-23 — TAMU-CORPUS CHRISTI: SHIPPED 775, then a LIVE silent-miss I caused + caught + fixed
═══════════════════════════════════════════════════════════════════════
Build shipped TAMU-CC (banner.tamucc.edu/schedule/BPROD.php, bespoke ASP.NET, ~11k students) = 775 live.
Gated ENTIRELY on prod box (only env that TLS-handshakes it; my env + Build's dev both get SSLV3_ALERT).

MY ERROR (went live ~1hr): Build asked "monitor all 3 Fall codes or full-term-only; campus M sufficient?"
I answered "full-term/M-only" off a MATH+ENGL sample. Build BIOL-checked, agreed. ALL THREE coincidentally
full-term/M-only. Reality (all-subjects count from poller):
  202609/M=2232 (full term) | 202609/R=50 (Firelands) | 202610/M=29 | 202611/M=33 | 202610-11/R empty
The 62 mini-term sections = ONE dept family (grad accelerated business MGMT/ACCT/BAIS/ECON/OPSY 5xxx),
exist in NO full-term code. Campus R = 50 Firelands general sections. M-only+full-term-only silently
dropped ~48 course-sections that exist nowhere else → watched grad-biz course never resolves = silent-miss.

CAUGHT: re-verified with ALL-SUBJECTS selector (not 2 subjects), proved real CRNs+seats
  (CRN 90027 ACCT-5301 40/59; CRN 90019 ACCT-5312 1/59). Flagged own earlier answer to Build.
FIXED (Build): fetch unions {202609,202610,202611}x{M,R}, merge by CRN (unique), FAIL-CLOSED — any leg
  fails => last-known-good, never a partial union (partial = its own silent-miss). Re-gated prod: 7 courses
  0 mismatch; 4 previously-invisible courses now appear (MGMT 5330=2, ACCT 5341=1, BAIS 5310=4, FINA 4396=1/R).
  Cost owned: 6 POSTs/subject/5min-cache (heavier than Banner) — right trade vs silent-miss. 775 correct.

ALSO caught in same build (Build): frmPrefix options are SINGLE-quoted in raw HTTP (value='ACCT-Accounting')
  but researcher read them from browser-rendered DOM (double-quote normalized) => double-quote-only regex
  scraped 0 prefixes, adapter empty on first gate. Fixed to match both.

TWO STANDING LESSONS (added to memory seatwatch-gate-addressability #13):
  (1) NARROW-SAMPLE MATRIX TRAP — never declare a term/campus empty or a sub-scope sufficient off 1-3 named
      subjects; MATH/ENGL/BIOL are all coincidentally full-term/main-campus = worst sample. Use ALL-SUBJECTS
      selector or sample across many dept families. Same shape as KCTCS-prefix miss (narrow slice -> wrong
      whole-surface conclusion).
  (2) DOM-vs-RAW-HTTP gap — form values off rendered DOM differ from raw HTTP (quotes, entities, JS-populated).
      Note the read-source in every bespoke spec.
  => Bespoke specs need BREADTH checks (all subjects/campuses/terms/raw-HTTP quoting), not just DEPTH.

Net: system worked — my miss caught before any real user (zero external users), verified, fixed same session,
lesson burned in both sides. Fort Hays still HELD (freshness-unproven WebForms). 775 live + clean.
