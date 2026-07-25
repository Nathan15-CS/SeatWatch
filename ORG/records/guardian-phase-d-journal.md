# PHASE D DEPLOYMENT JOURNAL — Guardian V1 Shadow Mode

Maintained by: Guardian session (Principal Reliability Engineer role, CEO-appointed
2026-07-25) · Operator of record: Nathan (CEO — runs every command; holds all
credentials) · Protocol: one step at a time; per step: purpose → expected success →
expected failure → CEO-pasted evidence → explicit SAFE TO CONTINUE or STOP.
No step is skipped. Evidence over optimism. Rollback over unnecessary risk.

**CURRENT STATUS: PRE-DEPLOY** (allowed values: PRE-DEPLOY · IN-PROGRESS ·
DEPLOYED-VERIFYING · SHADOW-OBSERVING · ROLLED-BACK · COMPLETE)

---

## Baseline (recorded before any step)

| Item | Value |
|---|---|
| Repo HEAD at journal open | `e6c518d` (V1 freeze record) — clean tree, all commits LOCAL (push separately gated) |
| Frozen V1 scope | `d5723fe` + `a9e6777` + `a9678c3` per ORG/records/guardian-v1-freeze.md |
| Test evidence | 36/36 passing at freeze (unittest test_guardian; includes differential shadow≡off proof) |
| Deployed prod vintage | UNKNOWN — predates `b6532aa` (evidence: no alert_log table in prod DB, Stage-0a record 2026-07-23). Resolved by Step 2. |
| Prod DB last known | users=5, watches=17, push_subs=3 (all CEO/family — "own watches only" satisfied by fact) |
| Mode going live | GUARDIAN_MODE unset → **shadow** · AUTO_ROLL_TERMS unset → **auto-roll disarmed** (approved C4 flip) |
| Enforcement | OFF. Phase E is a separate future decision. |
| Known top risks | (1) deploy bundles full undeployed HEAD delta — biggest deploy to date; (2) first restart runs additive DB migrations on live DB; (3) operator fatigue — D3 only when CEO is fresh |
| Pre-committed STOP conditions | Step-2 hashes match no git blob · any smoke failure → immediate rollback.sh · Healthchecks ping gap post-deploy · any verification output differing from stated expectation |

## Step plan

| # | Step | Type | Status |
|---|---|---|---|
| 1 | Fresh `.backup` of prod DB → Vault + integrity check | read-only | PENDING |
| 2 | Skew audit: sha256 of VM app.py/schools.py → map to git history | read-only | PENDING |
| 3 | What-goes-live review (engineer-produced inventory) → CEO go | review | PENDING |
| 4 | `ops/deploy.sh app --app-approved` (clean tree enforced, .prev snapshots, smoke) | mutating | PENDING |
| 5 | Verification checklist (service, guardian shadow line, disarm line, cycle growth, report file, Healthchecks, test-watch stamp) | read-only | PENDING |
| 6 | 24h stability check → enter SHADOW-OBSERVING (14-day window, 7 success criteria per Phase D packet) | observe | PENDING |

## Entries

### 2026-07-25 — Journal opened (pre-deploy)
- Done: V1 frozen (`e6c518d`); packet delivered; step protocol ratified by CEO; deploy
  deferred to when CEO is fresh (engineer recommendation, CEO accepted).
- Evidence: freeze record; 36/36 test run; clean `git status`.
- Anomalies: none.
- Decisions: journal lives in this file, updated at every step; final deployment
  report will be produced when Step 6 completes.
