# Fleet health sweep — 2026-07-31 (CORRECTED)

⚠️ **The first version of this document said "20 schools are dead — a student signing up
receives nothing." That was WRONG, and the error was in the tool, not the fleet.**

## What the first run actually measured

`ops/fleet-health.py` probed each school with its `example` course. But `example` is only a UI
placeholder and a gate fixture. It goes stale without the adapter being broken at all —
**Columbus State's example says `CSCI 1301K`; the school uses `CPSC`.** So the sweep measured
*"is the example course still valid"*, not *"does the adapter work."*

**Crucially, a stale example does not affect a single student.** Students type their own course
code. The example is placeholder text in a form field.

## Corrected findings

| | |
|---|---|
| schools swept | 838 |
| section collapse | **0** — Build's CRN fixes hold fleet-wide ✅ |
| open-with-0-seats | **0** — no false-alert risk anywhere ✅ |
| originally flagged "dead" | 23 |
| **of those, adapter demonstrably WORKS** | **11** |
| still returning nothing after 26 courses | 12 |

**Adapters proven working after the mis-flagging:**
`abac` (66 sections) · `columbusst` (86) · `daltonstate` (100) · `fvsu` (52) · `gordonstate` (98)
· `gsw` (88) · `jewell` (3) · `mga` (144) · `midway` (7) · `va-nova` (35) · `vincennes` (69)

**The USG Georgia "cluster" was not a cluster.** Verified directly: the dead and working
siblings all resolve the same host, all offer term `202608`, and all return a full subject list
for it. Host fine, term fine, content present. The only difference was our placeholder course.

**`va-nova` was not a VCCS problem either** — 35 sections for `HIS 101`.

## Still unexplained — 12

`asu-ga` `augusta` `brookdale` `chaminade` `cuboulder` `daemen` `kellogg` `mitchellcc`
`northgatech` `southwesterncc` `tamucc` `walshcollege`

**Not proven dead.** `chaminade` and `kellogg` returned data on an earlier probe and nothing on a
later one — they flake. Others may simply use course conventions none of the 26 test codes match.
Each needs per-school investigation: adapter class, endpoint, term, exact failure, and a verdict
of stale-config / outage / parse failure / course mismatch / unsupported.

## Tool fixed

`ops/fleet-health.py` now tries up to 20 real courses in two numbering conventions before
declaring anything unreachable, and reports `STALE EXAMPLE` separately from `DEAD`. A stale
placeholder is a UI nit; an unreachable adapter is an outage. Conflating them produced this
document's first version.

## Standing rules for anyone acting on this

1. **Never delete a school on one failed probe.** `abac` returned nothing and 66 sections minutes
   apart. `gsw` failed twice and then answered its own example course.
2. **A failed example course is not a broken adapter.** Check with real courses first.
3. **Re-run before acting.** Schools flake; two runs disagreeing is normal, not alarming.
4. Worth doing separately: refresh stale `example` values so the placeholder a student sees is a
   course their school actually offers. Cosmetic, but it is what caused this whole detour.

## The 12 — taxonomy started 2026-07-31

Profiled, and three have confirmed causes. Note they are **not** one cluster:

| school | adapter | term | endpoint | confirmed cause |
|---|---|---|---|---|
| `asu-ga` | AlbanyStateGA | 202608 | banner.asurams.edu | **DNS does not resolve** — stale hostname, permanent until fixed |
| `augusta` | AugustaUniversity | 202608 | pounce.augusta.edu | **HTTP 503** — outage or blocking us |
| `northgatech` | NorthGATech | **202712** | banner.northgatech.edu | **HTTP 503**, and pinned to a term far ahead of the 202608 everyone else uses — two suspects |
| `tamucc` | TAMUCorpusChristi | 202609 | banner.tamucc.edu | unknown; own host, unusual term |
| `cuboulder` | CUBoulder | None | *(no host/base attribute)* | unknown; endpoint not visible on the class |
| `brookdale` `chaminade` `daemen` `mitchellcc` `southwesterncc` `walshcollege` | Colleague family | None | selfservice.\*.edu | unknown; all have specialised example courses (`ED 405`, `LIT 147`, `ACC 316`, `CSC 151`) that the generic fallback list would not match |

**Key correction to the earlier "Georgia cluster" theory:** `asu-ga` and `augusta` are NOT on the
shared `gabest.usg.edu` host — they run their own Banner instances. That is why they did not
recover when the nine gabest schools turned out fine. Different infrastructure, different causes.

**`chaminade` and `kellogg` returned data on an earlier probe and nothing later — they flake.**
Neither should be touched without a third observation.
