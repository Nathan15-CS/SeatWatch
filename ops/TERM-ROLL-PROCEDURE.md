# Term-roll procedure (M-10) — what to do at a semester boundary

Written 2026-07-30 by the Manager lane. Grounded in `research/TERM-ROLL-AUDIT-2026-07-20.md`
and verified against the code as deployed at `7e95a24`.

## The situation, precisely

`AUTO_ROLL_TERMS` is **disarmed**, so no school changes term on its own. That is deliberate and
correct — the audit proved an automatic roll on 2026-10-01 could pick a *completed* winter term
(the `_SEASON["winter"] = 12` bug) and point a school at dead data.

The false-alert cascade the audit warned about is **now mitigated**. `app.py:2808` blocks any watch
whose stamped term differs from the school's current term, records `blocked_wrong_term`, and logs it
once per (school, watch_term, school_term).

**But the guard trades a false alert for a silent death.** When a school's term moves, existing
watches stop alerting entirely. The student is not told. Their watch simply never fires again.
That is the correct trade — a false alert is worse — but it means a term roll silently strands
every watch created before it.

## The real gap: nothing surfaces it

`blocked_wrong_term` is recorded in `guardian_watch_results` and logged once. **Nothing pages on it.**
The hourly monitor is quiet-unless-breach and this is not one of its breach conditions. So the cliff
would arrive, strand every watch, and nobody would know until a student complained.

**Fix (small, not yet done):** add `blocked_wrong_term > 0` as a paging condition. Owner: Guardian
lane. Until then, run the detection command below manually — weekly now, daily from mid-September.

## Detection — run this to see if any school has rolled

```bash
ssh -i ~/.ssh/seatwatch-vm.key ubuntu@141.148.27.134 'cd ~/seatwatch && sudo python3 -c "
import sqlite3
c=sqlite3.connect(\"file:watches.db?mode=ro\",uri=True)
rows=c.execute(\"SELECT school, term, adapter_term, COUNT(*) FROM guardian_watch_results \"
  \"WHERE outcome=(?) AND cycle_id IN (SELECT cycle_id FROM guardian_cycles ORDER BY started DESC LIMIT 50) \"
  \"GROUP BY school, term, adapter_term\", (\"blocked_wrong_term\",)).fetchall()
print(\"STRANDED WATCHES:\", rows or \"none — no school has rolled\")
"'
```

**Baseline 2026-07-30: none.** All watches stamped `202608`/`202610`, matching their schools.

## Response when it fires

1. **Do not bump the term to make the error go away.** First confirm the school's new term is the
   genuinely upcoming registration term, not a completed one. The audit's failure mode is a school
   pointing at a term that *ended*, which returns plenty of data and looks healthy.
2. **Check the direction.** A term number that moved *backward* (e.g. Fall 2026 → a 2026 winter term)
   is the known bug, not a real roll. Investigate before touching anything.
3. **Decide what happens to stranded watches.** They are blocked, not deleted. Either:
   - tell those students to re-create the watch for the new term (honest, no data surgery), or
   - deliberately re-stamp the watch rows after confirming the new term is correct.
   Re-stamping is a production DB write and needs the CEO's explicit approval.
4. **Never re-stamp in bulk across schools.** MinnState's `_active_term` is CLASS-level: one roll
   moves all 33 colleges at once. Verify per school.

## Known unfixed, from the audit — still true

**Parallel same-season populations.** On a delta tie the first list entry wins, which is usually a
sub-population: Roosevelt "Fall 2026 Pharmacy", Ramapo "Fall 2026 Cont Ed", UNM "MD & PHARMD Fall
2026", Earlham, Emporia. These are currently safe only because the example course isn't in that
catalog — **luck, not design.** Suggested fix from the audit: break delta ties on shortest
description, precedent in the Colleague `_pick_term`. Needs its own gate; it changes tie-break
behaviour fleet-wide.

## Timing

Nothing is due now. Fall 2026 registration runs through add/drop. The risk window opens as schools
publish Spring 2027 terms — historically from **late September**, with the audit's specific
detonation date of **2026-10-01**.

**Before then:** get `blocked_wrong_term` paging, and decide the stranded-watch policy in advance
rather than during an incident.
