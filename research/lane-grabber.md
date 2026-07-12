# Lane status — Grabber (research agent, successor to Fable's research lane)

**Only Grabber writes this file.** Codex/Builder read it. Continuation of `lane-fable.md` (archived).
Single relay point to Builder is unchanged: gated finds → README under `AWAITING GO-AHEAD` → on
Nathan's go, relay to Builder (session local_475a2545) as "Batch N" → mark SENT.

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

## ★ CREATIVE-HUNT WIN (July 12) — College Scheduler / Civitas public GraphQL vein
Chased "biggest missing mega-schools" → found the system many of them use: **College Scheduler
(Civitas)** runs a PUBLIC no-auth GraphQL API (`api.collegescheduler.com/graphql`) with clean numeric
seats (`openSeats`/`totalSeats`). ONE bespoke adapter serves every school with public "Course Search" on.
**3 confirmed LIVE + CURRENT + net-new (deduped):** Ivy Tech (~65k), UT Arlington (~42k), Univ. of Alaska
system (~26k, campus-splittable) — ~133k students from one adapter. All gated PASS (live full rows,
disproof holds). Full recipe + caveats in README block "College Scheduler / Civitas GraphQL"; data in
collegescheduler_lead.json. CAVEAT: public search is opt-in (most CS clients — asu/duke/alamo — gate it
behind SSO); can't fully enumerate the roster. Source-gated → needs a `CollegeScheduler` adapter, awaiting
Nathan's go. This is the fresh vein Nathan asked for — highest-value find of the session.

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
