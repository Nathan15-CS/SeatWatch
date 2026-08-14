# Guardian enforcement criteria — REPLACEMENT SET, authored 2026-08-14

## Read this first: these are NOT the original seven

`guardian-v1-freeze.md:20` instructs anyone judging Guardian V1 to score it against "the 7
success criteria in the Phase D packet." **Those criteria were never written into the
repository.** A grep across `ORG/` and `ops/` finds only references to them — the freeze
record, the Phase-D journal, two board rows citing SC1 and SC3 — never the criteria
themselves. This was first raised 2026-07-31 and remained open through the close of the
shadow window.

The AI Operating System's honesty law says: *"Pre-declared success criteria; no post-hoc
goalposts. An experiment that can't fail is not an experiment."*

Reconstructing seven criteria now, after the window has closed and its results are known,
and presenting them as the original pre-declared set **would violate that law directly**.
It would also be the same class of failure the product has been fighting all week: an
assertion dressed up as a measurement.

So this file does not pretend. **The originals are lost.** What follows is a new set,
authored on a stated date, by the Manager lane, with full knowledge of the window's
outcome — and it is labelled that way so nobody can later mistake it for pre-declared.

**What this costs:** the enforcement decision cannot claim to be scored against goalposts
set in advance. That is a real and permanent weakening of the evidence, and the correct
response is to say so, not to paper over it.

**What this fixes:** from today, there are written criteria. The next decision can be
pre-declared even though this one cannot.

---

## The criteria, for the shadow → enforce decision

Each is written so it can FAIL. Anything that cannot fail is not on this list.

### E1 — Deploy identity is provable
The exact code running in production is identifiable and matches a known commit, verified
by file hash rather than by a log line or anyone's memory.

**Evidence:** `ops/deploy.sh` byte-verification passing on all four shipped files, plus a
`DEPLOYED.log` line and the `deployed` tag at that sha.
**Fails if:** prod and HEAD diverge on a shipped file with no record explaining it.

### E2 — Enforcement would not have changed past behaviour
Across the shadow window, the honest latch agrees with the legacy latch on every alert
that actually occurred.

**Evidence:** `cycle.would_block` empty in every cycle, **reported alongside the number of
times the gate was actually evaluated.** A zero is meaningless without its sample size —
19,363 cycles produced 7 gate evaluations, and quoting the first number without the second
is how this was nearly got wrong on 2026-07-31.
**Fails if:** any non-empty `would_block`, or if the sample is too small to support a claim
and that is not stated.

### E3 — Every alert reached a human
No alert in the window failed to deliver on any channel.

**Evidence:** zero `no_channel` rows in `alert_attempt`.
**Fails if:** any exist. **This criterion is currently FAILING** — one `no_channel` row on
2026-08-14 00:35:28, watch 63, the first in the product's history.

### E4 — A dark school is detected and paged, not merely contained
A school that stops responding while live watches point at it produces a page to a human
within a bounded time.

**Evidence:** a real or forced `adapter_down` sustained past threshold producing an
operator page.
**Fails if:** it only records an incident. **Currently FAILING** — USF was dark 1h48m on
2026-08-02 and paged nobody; it surfaced two days later by accident.

### E5 — A rolled term is surfaced to both the operator and the student
A school moving to a new semester pages the operator AND tells every affected student their
watch has ended.

**Evidence:** `blocked_wrong_term` producing a page, plus the student notice at
app.py:4345. The student half is **passing** and pinned by
`test_term_roll_blocks_loudly_not_silently`. The operator half is **failing** — nothing
pages on `blocked_wrong_term`.

### E6 — The mass-alert freeze cannot cause a silent outage
If the tripwire fires, it is scoped, self-clearing, and audible.

**Evidence:** per-school scoping, self-clear after N clean cycles, pages on both trip and
release, and a metric counting seat openings rather than watchers — a threshold that counts
students trips on popularity, which is the product working.
**Fails if:** a freeze can outlive its cause or silence a school that never tripped.

### E7 — The accuracy gate can score every school it guards
No school is structurally unable to pass.

**Evidence:** `ops/gate.py` producing a verdict for status-only adapters.
**Fails if:** any school can never pass. **Currently FAILING** — `ops/gate.py:205` requires
an integer seat count, so CUNY (19), Fose (11), VCCS (23) and VSB (19) — **72 schools,
7.8% of the fleet** — can never be scored on the one field the gate exists to check.

---

## Current standing

| | status |
|---|---|
| E1 deploy identity | passing |
| E2 enforcement no-op | passing, on a 7-event sample that must be quoted with it |
| E3 every alert reached a human | **FAILING** — 1 `no_channel`, 2026-08-14 |
| E4 dark school pages | **FAILING** |
| E5 term roll — student half | passing |
| E5 term roll — operator half | **FAILING** |
| E6 freeze cannot cause silent outage | partially — metric and self-clear shipped; per-school scoping authorised, not built |
| E7 gate can score every school | **FAILING** — 72 schools |

**Four failing. The honest read is that enforcement is not ready to be judged a success,
and that has nothing to do with the latch logic — every failure above is a DETECTION gap.
Guardian contains faults correctly and tells nobody.**

---

## For the next window

Write the criteria **before** it opens, in this file, with a date. The reason this document
has to open with an apology is that nobody did that last time.
