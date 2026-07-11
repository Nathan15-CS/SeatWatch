# Lane status — Fable 5 (research agent A)

**Only Fable writes this file. Codex reads it but never edits it.**
Update the "NOW" line whenever I start/finish a vein, then commit + push immediately.

## NOW (July 10, current)
- **Flagship hunt: 3 gated-clean finds. Batch 17 (TAMU + Iowa State) SENT. Purdue AWAITING GO-AHEAD.**
  - Texas A&M College Station (~58-60k, status-only) + Iowa State (~30k, real numeric seats) → SENT to
    builder (batch 17).
  - University of Bridgeport (Codex's find) → relayed as batch 18.
  - **Purdue (~50k, Banner 8, real numeric seats, completed-term PASSED) → STILL in README under
    AWAITING GO-AHEAD; will relay when Nathan says "check the README." (Batches 17+18 shipped, 646 live;
    Purdue was NOT in those — it's the one queued item.)**
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
