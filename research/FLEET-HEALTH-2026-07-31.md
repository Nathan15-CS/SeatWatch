# Fleet health sweep — 2026-07-31

First live regression across the WHOLE registry. Readiness covers adapter *families* and
samples ~38 hosts; this hit all 838, one example course each. Tool: `ops/fleet-health.py`.

## Headline

| | |
|---|---|
| schools swept | 838 |
| reachable | **815 (97.3%)** |
| **confirmed dead** | **20 (2.4%)** — confirmed by a SECOND probe against 6 common courses |
| section collapse | **0** — Build's CRN fixes hold fleet-wide |
| open-with-0-seats | **0** — no false-alert risk anywhere in the registry |

**A student signing up for one of the 20 receives nothing, silently, forever.** No error, no
empty state they'd recognise as broken — the watch is simply created and never fires.

## The 20

`asu-ga` `augusta` `brookdale` `columbusst` `cuboulder` `daemen` `daltonstate` `fvsu`
`gordonstate` `gsw` `jewell` `mga` `midway` `mitchellcc` `northgatech` `southwesterncc`
`tamucc` `va-nova` `vincennes` `walshcollege`

**Cluster worth one investigation, not twenty:** nine are USG Georgia schools on the shared
`*.gabest.usg.edu` host (`asu-ga` `augusta` `columbusst` `daltonstate` `fvsu` `gordonstate`
`gsw` `mga` `northgatech`). **But 8 other USG siblings on the same host and same term 202608
work fine** (`gasou` `westga` `valdosta` `ggc` `gcsu` `clayton` `atlm` `ccga`), so this is
NOT a host-wide or term-wide outage. Per-school cause. `va-nova` is VCCS, another shared system.

## Method caveat — read before acting

**A single failed probe is not proof of death.** `abac` returned nothing in the sweep and 66
sections for the same course minutes later. Two other schools (`chaminade`, `kellogg`) had
merely stale example courses and work fine.

The 20 above failed **twice**: once in the sweep, once against 6 common course codes matched to
their numbering convention. That is strong evidence, not proof. Some may be temporary outages.
**Re-run before deleting anything from the registry.**

## Not alarming, but worth knowing

**351 schools showed no mixed status** — all sections open, or all full, for the probed course.
That is usually a quiet term or a small course, not a fault. It only matters if a school is
*always* all-open, which is the fake-open pattern the gates already screen for at add time.

## Recommended

1. Investigate the nine USG Georgia schools as one cause. Eight working siblings on the same
   host is the strongest available clue.
2. Re-run `ops/fleet-health.py` before treating any single school as permanently dead.
3. Run this sweep on a schedule — monthly, and always before a public launch. It is the only
   check that touches every host.
4. Consider surfacing dead adapters to the student at watch-creation time. Today the app accepts
   a watch on a dead school and says nothing.
