# Lane status — Fable 5 (research agent A)

**Only Fable writes this file. Codex reads it but never edits it.**
Update the "NOW" line whenever I start/finish a vein, then commit + push immediately.

## NOW (July 10, current)
- **My status: IDLE, awaiting Nathan's next instruction.** Not actively probing anything right now —
  zero risk of colliding with whatever Codex picks up as it comes online. Will resume once Codex has
  claimed a lane (so I can naturally steer clear of it) or Nathan gives a new steer.
- I just refreshed `research/PARTNER-NOTE-codex.md` with current findings + a concrete, non-overlapping
  starter-task list for Codex (newer-Colleague-API investigation / CT-log discovery / per-school
  alt-search hunt at named big flagships still untried). Codex has not yet claimed a lane —
  `lane-codex.md` is still unclaimed as of this write.
- **Open lead, unclaimed (flagged to Codex first, but fair game):** 11 Colleague hosts on a newer API
  version (405/400 on PostSearchCriteria: augustana/bridgeport/brookdalecc/camdencc/gac/gustavus/lvc/
  mcdaniel/sunyocc/twu/walshcollege .edu). Not gateable with the current adapter.

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
- Batch 16: Edison State CC (Ohio) + Georgia Military College — sent, awaiting builder

## Last push
- see `git log --oneline -1` for the current commit
