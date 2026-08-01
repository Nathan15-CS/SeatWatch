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

---

## RESOLVED

_(none)_
