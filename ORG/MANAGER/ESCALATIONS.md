# ESCALATIONS — Manager inbox

Unattended lanes (scheduled tasks) cannot message the Manager session directly —
`send_message` is unavailable in unattended runs. They write here instead, and commit.

**Manager: read the OPEN items at the top of each working session.** Move an item to
RESOLVED with a date and one line of disposition once it is handled. Do not delete.

Format:

```
### YYYY-MM-DD HH:MM — <LANE> — <SEVERITY: INVESTIGATE | STOP> — <one-line headline>
Evidence: <verbatim numbers / error text / file+line — no paraphrase>
Impact: <who is affected, right now>
Asked of Manager: <the specific decision or action needed>
```

Severity: **STOP** = same-day action, users are affected now. **INVESTIGATE** = needs a
decision but is not actively harming anyone.

---

## OPEN

### 2026-07-31 19:40 — GUARDIAN — INVESTIGATE — Phase-E evidence is IN and unanimous; bring the enforcement decision forward
**CORRECTED 19:58.** My first version of this claimed shadow produced no durable evidence. That was
wrong and I am glad it was caught before Guardian acted on it. There are TWO shadow signals, and only
one of them is volatile:
- **`cycle.would_block` — DURABLE and COMPLETE.** Persisted as JSON in `guardian_cycles.notes`.
  All **19,363 of 19,363 cycles** carry the field; **every one is `"would_block": []`**. Zero cycles
  where enforcement would have blocked anything, across the entire 2026-07-26 06:14 → 07-31 02:59 window.
  This is the primary Phase-E evidence and it exists.
- **`_LAST_DIVERGENCE` — volatile.** guardian.py:428, in-memory, `del [:-100]`, reset on process start,
  never written to the DB (only consumer is guardian.py:670). This is the *dishonest-latch* signal.
  It only fires when an alert fires, so its whole possible population is the 12 alerts below — and
  that population is fully reconstructible from `alert_log`, which I did. Nothing was actually lost.
  Worth fixing so it is queryable, but it is not a gap in the decision.
- `guardian_incidents` = 0 rows, all kinds. `guardian_cycles` has no dedicated divergences column;
  the evidence lives in `notes`.
- 19,363 cycles (19,327 GREEN / 36 YELLOW / 0 RED) produced **12 alerts total**:
  ASTR100 uid 5 → ntfy+webpush+email; ASTR100 uid 6 → ntfy+email;
  MUSC205 ×5 → watch 4, `user_id` NULL, ntfy only (topic-only; the honest rule latches these by
  design via `ntfy_ok and not (has_push or has_email)`).
  **Enforcement would have been a no-op on 100% of alert history — zero dishonest latches.**

Impact: Beta students all sign in with Google, so all have email enrolled. Under **shadow**, an alert
where email fails and only ntfy succeeds still latches — student never told, system records it handled.
Under **enforce** it refuses to latch and retries until a human channel works. Enforce fails **loud and
recoverable** (duplicate alerts); shadow fails **quiet and permanent**. Live now, on every beta signup.

Asked of Manager → routed to Guardian:
1. Check this reading — especially whether divergence evidence persists somewhere I did not find.
2. Produce the Phase-E go/no-go packet **now, on the logic, not on the 08-09 calendar date**.
   A reasoned "no, keep shadow" is an acceptable answer; the lane is Guardian's.
3. **Hard prerequisite:** M-35 (`e7db421`, committed, NOT deployed) must ship first. Enforce + the old
   enrolment definition ⇒ correctly-delivered alerts fail to latch and re-fire every cycle. M-35
   redefines enrolled as *enrolled AND enabled* and pins it in enforce-mode tests.
4. Fix divergence persistence regardless of the mode decision.
5. **Dated, separate:** the M-10 term-roll paging gap — nothing pages on `blocked_wrong_term`; the
   hourly monitor's breach conditions omit it. Risk window opens **late September, inside the beta**.
6. Not a blocker: MUSC205 fired 5× on watch 4, two pairs ~64s apart (ids 8/9 at 1785421929/1785421993,
   ids 10/11 at 1785439954/1785440019). Genuine add/drop churn, or re-firing? Guardian's call.

Flipping `GUARDIAN_MODE` is a production change — CEO approval, Nathan's hands. Deliver the packet only.

**ADDENDUM 20:15 — the recommendation REVERSED. Do not flip enforce as a single step.**
Build refuted my sample-size inference (correctly: `would_block` is only evaluated inside
`flush_alerts` over `cycle.pending`, so "0 across 19,363 cycles" is really "0 across **7 gate
evaluations**" — an untested branch and a passing branch are indistinguishable from the stored value).
Chasing their "mass-freeze: 0 real evaluations" line found the reversal:

- guardian.py:337-362 — under **enforce**, `n > MAX_ALERTS_PER_CYCLE` (default **10**) sets
  `frozen=True`, writes the `guardian_freeze` state key, sends **nothing**, and is **sticky until a
  human clears the key on the server**. Under **shadow** the same event only appends to `would_block`
  and pages; **alerts still go out.**
- This inverts my central argument to Nathan. Enforce is loud but **not quickly recoverable** — it
  needs someone SSH'd in during a registration surge, which is exactly when it would trip.
- Reachable at beta scale in a way it never was at 14 watches: ~25 students × ~2 watches ≈ 50, and a
  registrar block-release can transition 11+ inside one 20s cycle.

**Live watch concentration (Build, from prod):** 14 watches — umd 11 (**79%**), usf 2, ou 1.
A parse break is *nearly all of one school at once*; a legitimate release is *whatever subset of
students wanted those courses*. **The two differ in shape, not volume — a global integer cannot see
shape**, so any constant is either too low (freezes real surges) or too high (misses cascades), and
it drifts wrong as watch count grows.

**Ordered sequence — step 2 is not one item:**
1. M-35 ships.
2. `MAX_ALERTS_PER_CYCLE=25` (Build's number; justified: a UMD parse break at this concentration
   yields ~40 simultaneous, over the cap; busiest cycle in all history was 1. Good for ~50-150
   watches, revisit before 200) **AND** resolve the stickiness question.
3. Only then `GUARDIAN_MODE=enforce`.

**ADDENDUM 2 — 2026-08-01, from Nathan's question "what if we grow and I hit 10 alerts?"**
**The threshold metric is wrong, not just its value. Hold `MAX_ALERTS_PER_CYCLE=25`.**
guardian.py:331 `n = len(cycle.pending)`; `queue_alert` appends one entry per **watch**. So `n`
counts **watchers, not seat openings** — one genuine seat opening in a popular course produces N
pending alerts where N is how many students watch it. **The cap trips on popularity.**
Against live concentration (CMSC216 = 7 of 14 watches, 50%): ~50 students → ~50 pending on one real
seat (2× over 25); ~150 students → ~150 (6× over). Under enforce that is a sticky total outage
fired by the most valuable event the product can observe. Raising the number only moves the student
count at which it happens; every watcher-based threshold has this shape.
**Proposed:** `n = len({(r["school"], r["course"], r["section"]) for r, _, _ in cycle.pending})`
— distinct section transitions is bounded by the registrar's data, not by user count, so it stays
flat as the company grows. It also separates the cases directly: 50 alerts from 1 transition = one
real seat fanned out (deliver); 50 alerts from 40 transitions = parse break (freeze). A *tighter*
cap then becomes correct and stays correct. **Unresolved:** watches with empty/NULL `section` mean
"any section" and collapse onto one key per course — may under-count a real cascade.

**ADDENDUM 3 — 2026-08-01 — RESOLVED in code; follow-on AUTHORISED by Nathan.**
`9026db2` deployed 15:30 UTC (deploy.sh byte-verification passed on all four files). The metric now
counts `len(cycle.transitions)` — distinct `(school, course, section)` — and the freeze self-clears
after 3 cycles under the cap. **Cap resolved to 10, not 25**: on the corrected metric the observed
genuine maximum is 1 section per window in every window ever recorded, so 10 is 10× headroom while a
parse break flips dozens. Build also closed a hole that predated all of this — an any-section watch
fired once per course regardless of how many sections flipped, so a 30-section parse break behind one
such watch scored `n=1` and passed the tripwire. `queue_alert` now takes the changed-section list.

**Build's feasibility read, verified by me against live data:**
- Per-school scoping is ~40 lines; `school` is already in the transition key and already bound at
  guardian.py:418. **Cheapest right now** — prod `guardian_freeze` is `None`, so reshaping it from a
  scalar to a school-keyed dict has no migration cost. That window closes on the first real freeze.
- A **constant survives to 1,000+ watches under per-school scoping**: UMD has 7 distinct watched
  sections in total, so a cap of 10 already exceeds its entire watched surface. Coverage growth
  pressures a *global* cap, not a per-school one.
- **`yield_base` beats my proposed transition-p99 and needs no new accounting.** Verified live:
  umd=63.99, usf=20, ou=1. A real UMD opening is 1/64 ≈ 1.6%; a parse break approaches 100% — ~60×
  separation, dimensionless, so it scales identically across school sizes.
- **The gap neither of us saw (Build's catch):** adapter FAMILIES span hundreds of schools. A
  vendor-side Banner 9 change breaks many schools at once while each shows only a few transitions —
  under every per-school threshold, catastrophic in aggregate. **Per-school scoping must therefore
  ADD a layer beneath the global cap, not replace it.**

**Nathan authorised on 2026-08-01: Build writes the concrete diff and implements (a) + (b).**
(a) per-school scoping; (b) global backstop retained above it, with the family-event reasoning in a
comment so it is not later mistaken for vestigial; (c) the `yield_base` fraction is **documented in
the diff but NOT built** — Build ranked it last and doubts (a) will prove insufficient. Tests must
fail against the pre-change code, and the cross-contamination case (UMD frozen, USF still delivering)
must be tested directly. **Deploy stays gated on Nathan.** Recorded here so Guardian's lane sees this
was authorised, not bypassed — **if Guardian prefers a different design, Guardian's wins.** Still P2.

**Guardian's design call, two parts:**
(a) **Stickiness is the worse half.** A wrong threshold costs one cycle; sticky-until-manual costs
every cycle after it. Build proposes auto-clearing after N cycles once the data looks normal again —
a freeze that outlives its cause is a silent outage wearing a loud page.
(b) **Shape over count.** Build proposes reusing the fake-all-open principle: freeze only if
`n > N` **and** the school's sections read essentially all-open. **Caveat I verified — the existing
watchdog at app.py:2801 is scoped to STATUS-ONLY schools** (`seats=None`); numeric-seat schools are
explicitly excluded because the count is real. **UMD is numeric-seat and holds 79% of watches**, so
that signal as built would not cover the case that matters most. The shape idea is right; a
numeric-seat parse break needs its own discriminator (implausible seat counts / all-sections-changed
-at-once), not this one.

---

## RESOLVED

_(none)_
