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

## Standing question (CEO-mandated): "Handing this to another engineer and
## walking away for a year — what would still make me uncomfortable?"

Baseline answer, 2026-07-25 (re-evaluated whenever evidence changes; changes are
surfaced to the CEO immediately):

1. **Semester-boundary human dependence.** With auto-roll disarmed (the correct
   near-term trade), every one of ~775 schools now needs a human term bump at
   each semester boundary or it goes fail-closed-stale. Safe, but on a one-year
   horizon the product decays to silence without human attention. The exit is
   the guarded re-arm (ORD-A-class machinery), driven by shadow evidence.
2. **Unpushed lineage.** Every commit since Stage 0d — SMS prep, the entire
   Guardian, ops tooling, freeze, this journal — exists only on the CEO's Mac.
   One laptop failure erases the code lineage while prod keeps running old
   bits. Engineer recommendation: approve a push to the private GitHub remote
   (one word; the gate is the CEO's per Stage 0d).
3. **Backups are still manual.** The dead-man email detects VM death, but
   nothing restores itself and the newest backup is whenever a human last ran
   one. C1 (nightly ring + Mac pull, each with its own healthchecks ping) and
   C2 (rehearsed restore) remain the highest-value non-Guardian reliability
   work after shadow is stable.
4. **Evidence-scale ceiling.** All trust the Guardian earns in shadow is earned
   at 5 accounts / 17 family watches. It proves mechanics, not scale behavior;
   the trust must be re-earned when real users arrive, and enforcement
   thresholds re-examined at that time.
5. **Transitional:** deployed-truth gap (resolves at Step 2) and the fabricated
   testimonial still live on the pricing page (integrity item, queued for the
   CEO's one-line go since 07-23).

None of these block Step 1; items 2 and 3 are the cheapest discomfort-reducers
on the board.

### 2026-07-25 — Journal opened (pre-deploy)
- Done: V1 frozen (`e6c518d`); packet delivered; step protocol ratified by CEO; deploy
  deferred to when CEO is fresh (engineer recommendation, CEO accepted).
- Evidence: freeze record; 36/36 test run; clean `git status`.
- Anomalies: none.
- Decisions: journal lives in this file, updated at every step; final deployment
  report will be produced when Step 6 completes.
