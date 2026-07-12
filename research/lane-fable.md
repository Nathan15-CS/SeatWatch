# Lane status — Fable 5 (research agent A)

**Only Fable writes this file. Codex reads it but never edits it.**
Update the "NOW" line whenever I start/finish a vein, then commit + push immediately.

## NOW (July 10, current)
- **Flagship hunt: 3 gated-clean finds. Batch 17 (TAMU + Iowa State) SENT. Purdue AWAITING GO-AHEAD.**
  - Texas A&M College Station (~58-60k, status-only) + Iowa State (~30k, real numeric seats) → SENT to
    builder (batch 17).
  - University of Bridgeport (Codex's find) → relayed as batch 18.
  - **Purdue (~50k, Banner 8) → SENT to builder as batch 19 (July 10). Nothing of mine is queued now.**
- **Relay-hub role:** everything (mine + Codex's) lands in README under `AWAITING GO-AHEAD` headings;
  when Nathan says "check the README," I pull, relay all AWAITING blocks to the builder in one go, and
  mark each "Batch N sent." I am the single relay point; Codex never messages the builder.
- **Flagship list now fully worked (scorecard in README).** UF = API CRACKED (Referer + 4-digit term)
  but openSeats suppressed on public API = PERMANENT SKIP (data-absence, CPP class). MSU = Incapsula
  bot-wall (out of scope). Clemson = no public tool found. So of the 6: 3 wins (TAMU/ISU/Purdue), 3
  genuinely blocked. Flagship-bespoke-schedule vein is well-worked.
- **My status after this: idle / awaiting direction.** All my assigned veins are worked (CSU, HCX,
  host-guessing, flagships). Highest-value remaining lever is Codex's lane (newer-Colleague-API +
  the selfservice→SaaS redirect finding — could unlock a batch). Open to a new steer from Nathan.
- Not colliding with Codex ("newer-Colleague-API-version investigation", see below).
- **Codex is ACTIVE**, claimed "newer-Colleague-API-version investigation" in `lane-codex.md`, starting
  with Augustana, Bridgeport, Gustavus Adolphus. Builder independently narrowed this down technically:
  likely Ellucian's Angular Colleague rewrite using `/api/...` endpoints (old MVC-era adapter uses
  `/Student/Courses/PostSearchCriteria`). I posted this detail to README so Codex has it. DO NOT also
  work this lane — it's Codex's.
- Batch 16 SHIPPED (641->643): Edison State CC + Georgia Military College. Two new reusable term-format
  subclasses now exist: `AcadYearColleague`, `QuarterColleague`.
- **Correction posted to README (July 10):** builder's batch-16 reply suggested Long Beach/Fullerton/
  SDSU/SJSU as "worth individual effort" — these are NOT open, I already closed all 4 in "CSU sweep
  pass 2" with specific reasons (stale/ambiguous/SSO-walled). Do not re-propose without new evidence.

## CLOSED veins this partnership (fully worked, do not re-tread — see research/README.md for detail)
- **CSU public-schedule campuses: HARVESTED + CLOSED.** SFSU/Sac State/CSUN shipped. Cal Poly Pomona
  RESOLVED = permanent skip (ASP.NET flow cracked but the public page only exposes Capacity, no
  seats/status — data isn't there at any access level). Remainder walled/stale/classic-fake.
- **PeopleSoft Fluid / HighPoint HCX guest-API vein** — thin (420-host pattern sweep = 0; only
  search-harvested hosts like Coppin yield anything).
- **Big-university alt-search (ASU + University of Arizona):** ASU = OAuth-gated (authorize step
  bounces to interactive login). U Arizona = InFlight SPA over the classic-PS SSR_CLSRCH component
  (same fake-all-open family as the flagship batch that was scrapped) — not shippable even if the
  transport were cracked.
- **Full US-domain volume sweep (Banner + Colleague, 2,014 uncovered domains, both direct AND
  Ellucian-cloud host patterns):** CONFIRMED mechanical hostname-guessing is mined out. Only 2 net-new
  survived gating — Edison State CC (Ohio) + Georgia Military College — sent to builder as batch 16.

## DONE this partnership (see research/README.md for full specs)
- Batch 13: UCLA — shipped (639 live)
- Batch 14: Coppin State + San Francisco State — shipped
- Batch 15: Sacramento State + CSU Northridge — shipped (641 live, commit b5c5891)
- Batch 16: Edison State CC (Ohio) + Georgia Military College — SHIPPED (643 live, commit ba6a6d6)

## Last push
- see `git log --oneline -1` for the current commit

## NOW (July 10, continued) — flagship gaps beyond the builder's 6-school list
Alt-public-schedule hunt at big uncovered publics (non-overlapping with Codex).
- ✅ **University of Utah (~35k) — SENT to builder as batch 20** (real numeric seats, public
  class-schedule.app.utah.edu). Nothing of mine queued now.
- Dead: Cincinnati (classic-PS fake-open), LSU (daily-stale), UGA (SSO/CAS), Kansas State (WebISO SSO).
- REVISIT-LEADS (crackable, not gated): Kansas (public CourseSearch.action but times out 55s — latency
  or missing-param hang), Hawaii-Manoa (public avail.classes page, 502/301 on probe — retry params).
- Unresolved hosts (need real host recon): Nebraska-Lincoln, Louisville, Oregon, Nevada, URI, Kentucky.
- **Status: ALL my solo veins now exhausted (July 11).** HCX search-harvest (my last fresh angle) =
  USM, already live (dup). Fose full sweep = Penn (dup). Every SIS type swept across the 2014-domain set
  + ~20 flagships + CT-log = mined out at 648. CEDING public-schedule discovery to Codex (it claimed that
  vein July 11 — overlaps my worked flagship lane; my dead-ends are in README so it won't re-tread). No
  fresh non-overlapping solo lane remains. Real growth = the newer-Colleague adapter (Builder+Codex, in
  motion). I'll relay Codex's gated finds instantly; not burning tokens on more solo probes.

## BUILDER HANDOFF (July 11 2026)
The original SeatWatch-Builder session (local_224f8036...) is being retired; Nathan started a FRESH
builder chat, same role/standards. OPERATIONAL NOTE FOR RELAY: the new builder has a DIFFERENT session
id — the new builder chat "Builder" = session **local_475a2545-d0a3-4573-ba96-8b4f76cebbda** (found via
list_sessions July 11; old builder was local_224f8036, retired). Send all handoffs to local_475a2545.
Already messaged it: intro + pointed it at the newer-Colleague adapter as top build (with the hard
completed-term gate; do-not-ship-until-Codex-gates caveat). DEPLOY = RESOLVED July 11 (Builder confirmed:
Nathan deployed both reliability fixes, md5 matches HEAD, poller restarted clean, healthcheck.io
dead-man's-switch now ARMED). Builder is asking Nathan whether to greenlight scaffolding the Colleague
adapter now. Nothing queued for me to relay. (Note: `.claude/launch.json` shows deleted in the shared
working tree — not mine, left untouched.) State at handoff: 648 live, pushed through commit 7b07229,
origin caught up. ⚠️ DEPLOY-PENDING (Nathan action): two app.py reliability commits (fake-all-open
production watchdog + alert-delivery-retry fix) are committed+pushed but NOT yet deployed to the Oracle
box (needs scp + systemctl restart). Open leads for new builder unchanged: newer-Colleague API (Codex),
selfservice->SaaS redirect vein, untried big-flagship bespoke schedules (UNT/Kansas = browser-trace
revisit-leads). README = the new builder's bible; completed-term test stays mandatory every handoff.

## NEW VEIN claimed July 11 — Banner 8 public timetables (bwckschd) — NEVER SWEPT
Nathan's push was right: my 2014-domain sweep only probed Banner 9 (/StudentRegistrationSsb), never
Banner 8 (/prod/bwckschd.p_disp_dyn_sched). Banner 8's public Dynamic Schedule is how VT + Purdue were
found (real seats via detail pages / open_only filter). Sweeping it now across all uncovered domains.
Non-overlapping with Codex (Colleague/public-schedule). Also on deck if this yields: Jenzabar, Workday.

## Banner-8 parser-generalization: DECIDED — NOT worth it, moving on (July 11)
Tested rigorously (production Purdue adapter + a generalized-parser attempt) on the 5 cut schools.
Verdict: fragile, per-host HTML variation, and an accuracy landmine (detail pages have Seats / Waitlist
Seats / Cross List Seats rows — wrong-row grab = false-open). Production adapter returns garbage for
these hosts; my generalization attempts kept failing. Data is real but reliable+FLAWLESS extraction is
not achievable without significant fragile per-host work I can't vouch for. Per Nathan's "move on if not
good" → NOT sending to Builder; the 2 that shipped (Bristol, Clovis) are the Banner-8 yield. Do not
re-hand-off Missouri State/Toledo/SFA/AAMU/Utica without a proven generalized parser.
STATUS: my solo veins are genuinely tapped (host-guessing, CSU, flagships, HCX, fose, Banner-8 all
worked). Momentum is with Codex's source-gated leads (Fairfield/SDCCD/Berkeley/UNC Asheville/NCCU/UNCG)
+ Builder building their adapters. I'm in relay/support mode; will relay Codex's gated finds instantly.

## NEW LANE July 11 — mining Codex's cracked VENDOR patterns at scale (non-overlapping)
Codex finds one school per pattern; I sweep the pattern for MORE. Starting with Fairfield's
course-search-net.{domain} /api/course/courses vendor (fields Remaining_Seats/Enrolled_Capacity/
Course_Subject_Number). If multi-tenant → a whole vein for the ONE adapter Codex/Builder build for Fairfield.
Next candidates: SDCCD JSON feed (other CC districts?), the UNC-system Banner pattern is CODEX's (NCCU/UNCG/
UNCAsheville) — I will NOT touch UNC. Gating discipline (post-Banner-8 lesson): verify real data + completed-
term where possible; hand off as "same-as-Fairfield, needs that adapter" — do NOT claim production-gated
without the production adapter.

## Mining-Codex-patterns result July 11 — bespoke one-offs, NOT sweepable
Tested the two most-mineable: (1) Fairfield course-search-net vendor — course-search-net.{domain} sweep
across all 2014 domains = 0 hits; no vendor name in app; field signature (Course_Subject_Number/
Remaining_Seats) is NOT a standard product per web search = custom one-school build. (2) SDCCD feed =
district-specific host mws-api.sdccd.edu, not a shared vendor. CONCLUSION: Codex's finds are bespoke
per-institution APIs (that's WHY they each need a bespoke adapter) — nothing to sweep for siblings.
The sweepable veins (newer-Colleague full sweep, UNC-system Banner, UC/Berkeley) are all CODEX's active
lane — will not collide. REAL UNLOCK now = Builder building the bespoke adapters for the ~8 schools Codex
ALREADY found (Fairfield, SDCCD City/Mesa/Miramar, Berkeley, UNC Asheville, NCCU, UNCG) — that's 8 more
schools, a Builder task not a mining task. My solo mining is genuinely tapped.
