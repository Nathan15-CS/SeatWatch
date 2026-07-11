# SeatWatch research — working summary (LEAN)

Cross-session research log for SeatWatch school expansion. **This file is kept lean on purpose** —
the full chronological batch-by-batch history lives in `research/ARCHIVE.md` (grep it for any past
detail). Read THIS file + the lane files; only open ARCHIVE for a specific past finding.

- **Live count: 646 schools** (goal 1,000). Session start was 634.
- **Who's doing what right now:** `research/lane-fable.md` + `research/lane-codex.md` (short, always current).
- **How we work / accuracy+efficiency gate:** `research/PARTNER-NOTE-codex.md` and repo-root
  `CONTRIBUTING_AGENT.md`. Handoffs to the builder go through Fable; gated-but-unapproved candidates
  get a heading containing the phrase **`AWAITING GO-AHEAD`** (grep for it to find every pending item).

---

## PENDING HANDOFFS (grep `AWAITING GO-AHEAD`)
- None from Fable right now (Purdue was sent as batch 19). New gated finds appear here under an
  `AWAITING GO-AHEAD` heading until Nathan says "check the README," then Fable relays + marks them sent.

## ACTIVE LEADS
- **Newer-Colleague API (BUILD DECISION for Nathan).** Confirmed real: `SearchAsync`/`SectionsAsync`
  with a JSON-string `searchParameters` payload and a NUMERIC status (0=open; "full" code varies:
  Lebanon Valley 0/1, Augustana 0/2). Two schools gated on it (Lebanon Valley, Augustana) but NOT
  shippable on the current Colleague adapter (it reads textual "Open" only). If Nathan greenlights a
  newer-Colleague variant, safe rule = open ONLY when status==0 AND Available>0, with a MANDATORY
  completed-term test per school. Unlocks a batch of the 11 redirect-hosts. Codex owns this vein.
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
