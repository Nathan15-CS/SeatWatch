# Term auto-roll audit — 2026-07-20 (for Build; schools.py is Build's file)

Audited every term picker for early-roll exposure after the VSB work showed hosts publish
future terms months ahead. Found a worse bug than early-roll: a **backward** roll into a
COMPLETED term that reports seats as OPEN. Fix is written and gated; the patch is
`research/term-roll-fix.patch`, applies cleanly to `1761838`. Build owns landing it.

## The bug

`_SEASON["winter"] = 12` dates every winter term as December. At a **quarter** school
"Winter 2026" is the Jan–Mar 2026 quarter, named for the year it RUNS in — so the shared
model dates a term that ended last March ~11 months into the FUTURE. Once Fall drops off
the `delta < -1` cliff on **Oct 1**, that stale winter term is the nearest "upcoming"
candidate and wins.

`refresh_term`'s verify-before-adopt does NOT protect against it: a completed term returns
plenty of data.

### Live-verified 2026-07-20 (replayed at a frozen 2026-10-01, real fetches)

| School | Rolls to | Gate | Result |
|---|---|---|---|
| UCLA | `26W` Winter 2026 (ended Mar 2026) | passes | 3 sections, **all 3 OPEN — 42/43/23 seats** |
| UCI | `2026-03` (past) | passes | 5 sections, **all 5 OPEN** |
| UCSC | `2260` (past) | passes | 3 sections, **all 3 OPEN** |
| UCSB | `20261` (past) | passes | 28 sections, 0 open (silent miss) |
| Miami Ohio | "Winter Term 2026-27" | passes | 1 section vs 26 in Fall |
| Montclair | "WINTER 2027" | passes | 1 section vs 10 in Fall |
| Plattsburgh, Brockport, Corning | Winter | rejected *in July only* | winter schedules load by Oct |

UCLA's term menu carries BOTH `27W "Winter 2027"` (correct) and `26W "Winter 2026"` (past).
The picker prefers the past one: Dec 2026 is nearer than Dec 2027.

`63e4198` (delta<1 → delta<-1) was correct and necessary — it moved the detonation date
from **Aug 1 to Oct 1**. It did not remove the bug.

Fleet sizing: 120-school Banner sweep → 107 return None on Oct 1 and safely hold the pin,
12 roll, 5 to a winter term, 2 of those backward into a completed one.

## The fix (in the patch)

1. **`_auto_season()` / `_AUTO_SEASONS`** — winter is never auto-adopted. Applied at 26
   picker sites. A winter label cannot be dated: Dec intersession at semester schools,
   Jan–Mar quarter at quarter schools. Same "undateable ⇒ never adopt" line VSB already
   takes. Left alone: SacState + SynthTermColleague (hardcoded seasons, no winter) and
   QuarterColleague (dates by explicit month span — the pattern that actually works).
2. **Monotonic guard** in `_pick_current_term(terms, today, cur)` — drops candidates
   strictly EARLIER than the current term. `cur` itself stays in the running; it has the
   smallest delta of anything at-or-after it, so while in-window it keeps winning and the
   pick is a no-op. **Using `<=` here instead of `<` moves 8 live schools today** (SD
   regental ×3, Kettering, Lake Michigan, Touro, WCCS) — gate-caught, do not "simplify" it.
3. **Central `auto_term` opt-out** moved into `refresh_all_terms` so it binds every family,
   not just Banner.
4. **`auto_term = False`** on the 6 quarter schools: UCLA, UCI, UCSB, UCSC, UOregon,
   Oregon State. Necessary because blocking winter makes a quarter school jump Fall →
   Spring and skip the whole winter quarter (verified: UCLA `26F → 27S` on Oct 1) — trading
   a false open for a whole-quarter silent miss. Their pins are hand-bumped; all 6 verified
   still serving live current-term data.

## Gate results

- **Regression, full fleet: 477 schools, resolve_term baseline vs patched, live — 0
  differences.** Strict no-op today.
- **Oct-1 replay through production `refresh_all_terms`:** 6 quarter schools OPTOUT;
  Miami Ohio, Montclair, Plattsburgh, Brockport, Corning, UIUC, Brown all HELD; legitimate
  forward rolls preserved (Yale, MinnState, Kettering, Lake Michigan, SD regental, WCCS →
  correct next term).
- UIUC now detects `2027/spring` instead of `2026/winter`; Brown detects spring instead of
  the past Winter 2026.

## Two things the patch does NOT fix

1. **app.py — the bigger bug.** `app.py:2349` alerts on `open_secs and not alerted` with no
   term-change awareness. **Any** roll, including a correct one, fires alerts on stale
   watches whose section id happens to be open in the new term. MinnState's Spring 2027
   reads **29 of 29 sections open** and its `_active_term` is CLASS-level → one roll moves
   all 33 colleges and false-alerts every Fall watcher at once. Not touched (app.py holds
   undeployed gated paid/UI work).
2. **Parallel same-season populations.** On a delta tie the first list entry wins, which is
   usually the sub-population: Roosevelt "Fall 2026 Pharmacy", Ramapo "Fall 2026 Cont Ed",
   UNM "MD & PHARMD Fall 2026", Earlham, Emporia (Mercy already has `auto_term=False`). All
   currently held only because the example course isn't in that catalog — luck, not design.
   Suggested fix: break delta ties on shortest description; precedent already exists in the
   Colleague `_pick_term` (`key = (delta, subpenalty, len(desc))`). Needs its own gate —
   it changes tie-break behaviour fleet-wide.

## New pre-handoff gate checks (already relayed to Grab)

- **Quarter calendar?** → ship with `auto_term = False` and a hand-bumped pin.
- **Two same-season terms differing by population** (Pharmacy / Law / Cont Ed / MD /
  Quarter / Trimester / CPS)? → ship with `auto_term = False`.
