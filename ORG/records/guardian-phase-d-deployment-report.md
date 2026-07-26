# PHASE D FINAL DEPLOYMENT REPORT — Guardian V1 Shadow Mode
**2026-07-26 · Result: SUCCESS · Status: SHADOW-OBSERVING as of 06:14:32Z**

Companion to `guardian-phase-d-journal.md` (raw per-step entries). Operator:
Nathan (CEO) ran every command; engineer reviewed every output before the next
step.

## What was deployed
`sha 1ee417f` via `ops/deploy.sh app --app-approved` at 06:14:35Z — app.py,
guardian.py, confidence.py, schools.py (schools byte-identical to prod; no-op).
First entry in DEPLOYED.log; `deployed` tag set. `.prev` rollback snapshots now
exist on the VM. Live changes: exactly the six CEO-approved items (guardian
shadow · auto-roll disarmed · current-term stamping · damped operator paging ·
end-of-cycle sends · dormant internals). Zero public-page changes.

## What was verified (all PASS)
1. Fresh pre-deploy backup: integrity `ok`, 5 users / 17 watches, on Mac Vault
   (taken 18 min before use).
2. Prod identity resolved pre-overwrite: app.py=`b85c0f6`,
   schools.py=`0e47cec` — both matched to git blobs exactly.
3. Service-health baseline pre-deploy: pings arriving (last ping 8s old).
4. Post-deploy, new-code proof: `[guardian] active, mode=shadow` +
   `auto-roll DISARMED` journal lines (printable only by this build).
5. Recording: guardian_cycles 9 → 13 at ~20s cadence; report JSON fresh (600).
6. **Reconciliation: latest cycle GREEN, expected=17, accounted=17 — the first
   fully identity-reconciled production cycle in SeatWatch history.**
7. C5 stamp fix live: fresh UMD CMSC216 watch stamped `202608` (non-empty,
   equals comparator; pin-fallback path — cur_term() path rests on unit tests).
8. Dead-man continuity post-deploy: pings every ~20s (operator-observed).

## Issues encountered (all resolved or logged; none affected users)
- Placeholder `<VM-HOST>` pasted literally on first attempt → shell error, no-op.
- Idle SSH session reset pre-deploy → benign; baselined via Healthchecks.
- VM origin IP entered the chat transcript → post-shadow follow-up: rotate or
  tighten (with the already-pending Healthchecks ping-URL rotation).
- Operator ran rollback.sh before deploying (engineer handed a runnable command
  as "keep in hand") → harmless (no snapshots; one old-code restart, visible in
  journal as the 06:14:19 start). Corrective rule adopted: non-immediate
  commands are labeled DO-NOT-RUN—SAVE-THIS.
- deploy.sh smoke matched a stale `Poller started` (Jul 25) → service-active
  check still authoritative; Step 5 supplied the new-code proof. Backlog:
  smoke uses `--since` restart; rollback skips restart when nothing restored.
- DISCOVERY: an untracked deploy occurred ~02:54 EDT Jul 25 (app=`b85c0f6`),
  schools.py updated that evening likely without restart. Corrected the
  "prod is weeks old" assumption; prod DB already had alert_log/sms_consent.
  Recommendation adopted going forward: every lane deploys via ops/deploy.sh.

## Observation window — recommendation
**14 continuous days (through ~2026-08-09), judged against the 7 success
criteria** in the Phase D packet (coverage · zero unexplained divergences ·
end-to-end alert proof + 2 fire drills · adapter health · guardian self-health
· no regression · caps-only RCI binding).

Rhythm:
- **Daily (CEO, ~10s):** read the digest push — the Guardian line should say
  `17/17 reconciled` (or current watch count), GREEN/YELLOW, an RCI, and open
  incidents. Healthchecks email remains the out-of-band alarm.
- **Day-1 checkpoint (~24h in):** paste the standard status command to the
  engineer — expect ~4,300 cycles/day accumulating, GREEN latest, retention
  working.
- **Weekly (with engineer):** divergence classification (every would-block =
  real risk caught or false positive to fix), confidence trend + binding
  factors, incident review, backlog refresh.
- **Open a session immediately on:** any RED page · UNDELIVERED page ·
  mass-freeze shadow page · Healthchecks email · digest line missing or odd.

No term-pin action expected inside the window (fall terms current; spring-2027
publication is an October concern — the disarmed-roll horizon to plan for).

Parked for after the window: ping-URL + IP exposure hardening; deploy/rollback
script warts; backup automation (C1) + restore rehearsal (C2); fire-drill
web-push leg; **pushing the local-only git lineage to the private remote —
standing engineer recommendation, unchanged.**

Enforcement (Phase E) remains a separate CEO decision after the window closes
with a written evidence report against the 7 criteria.
