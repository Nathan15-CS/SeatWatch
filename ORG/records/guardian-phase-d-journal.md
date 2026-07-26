# PHASE D DEPLOYMENT JOURNAL — Guardian V1 Shadow Mode

Maintained by: Guardian session (Principal Reliability Engineer role, CEO-appointed
2026-07-25) · Operator of record: Nathan (CEO — runs every command; holds all
credentials) · Protocol: one step at a time; per step: purpose → expected success →
expected failure → CEO-pasted evidence → explicit SAFE TO CONTINUE or STOP.
No step is skipped. Evidence over optimism. Rollback over unnecessary risk.

**CURRENT STATUS: IN-PROGRESS — Step 1 issued to operator** (allowed values:
PRE-DEPLOY · IN-PROGRESS · DEPLOYED-VERIFYING · SHADOW-OBSERVING · ROLLED-BACK ·
COMPLETE)

---

## Baseline (recorded before any step)

| Item | Value |
|---|---|
| Repo HEAD at journal open | `e6c518d` (V1 freeze record) — clean tree, all commits LOCAL (push separately gated) |
| Frozen V1 scope | `d5723fe` + `a9e6777` + `a9678c3` per ORG/records/guardian-v1-freeze.md |
| Test evidence | 36/36 passing at freeze (unittest test_guardian; includes differential shadow≡off proof) |
| Deployed prod vintage | **RESOLVED by Step 2 (2026-07-26):** app.py = `b85c0f6` · schools.py = `0e47cec` (=HEAD content, 777 schools). A deploy occurred ~2026-07-25 evening outside the new tooling (no DEPLOYED.log entry). Baseline's earlier "predates b6532aa" claim was true on 07-23, obsolete now — prod DB has alert_log + sms_consent (tonight's backup `.tables`). |
| Prod DB last known | users=5, watches=17, push_subs=3 (all CEO/family — "own watches only" satisfied by fact) |
| Mode going live | GUARDIAN_MODE unset → **shadow** · AUTO_ROLL_TERMS unset → **auto-roll disarmed** (approved C4 flip) |
| Enforcement | OFF. Phase E is a separate future decision. |
| Known top risks | (1) deploy bundles full undeployed HEAD delta — biggest deploy to date; (2) first restart runs additive DB migrations on live DB; (3) operator fatigue — D3 only when CEO is fresh |
| Pre-committed STOP conditions | Step-2 hashes match no git blob · any smoke failure → immediate rollback.sh · Healthchecks ping gap post-deploy · any verification output differing from stated expectation |

## Step plan

| # | Step | Type | Status |
|---|---|---|---|
| 1 | Fresh `.backup` of prod DB → Vault + integrity check | read-only | ✅ DONE 2026-07-26 |
| 2 | Skew audit: sha256 of VM app.py/schools.py → map to git history | read-only | ✅ DONE 2026-07-26 |
| 3 | What-goes-live review (engineer-produced inventory) → CEO go | review | ✅ DONE 2026-07-26 |
| 4 | `ops/deploy.sh app --app-approved` (clean tree enforced, .prev snapshots, smoke) | mutating | ✅ DONE 2026-07-26 06:14Z |
| 5 | Verification checklist (service, guardian shadow line, disarm line, cycle growth, report file, Healthchecks, test-watch stamp) | read-only | IN PROGRESS |
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

### 2026-07-26 ~06:20-06:40Z — STEP 5 EVIDENCE (all but one item)
- New-code proof: `[guardian] active, mode=shadow` + `auto-roll DISARMED` lines
  at 06:14:32 (only tonight's build prints these). The two process starts 13s
  apart = operator's pre-deploy rollback restart (old code, 06:14:19) followed
  by the deploy restart (new code, 06:14:32) — closes Anomaly A's loop.
- Recording: cycles 9 → 13 across ~80s (correct ~20s cadence). Report JSON
  fresh (06:17, mode 600). **latest cycle: GREEN, expected=17, accounted=17 —
  first full identity-reconciled cycle in production history.**
- C5 stamp fix proven live: operator-created UMD CMSC216 watch stamped
  `202608` (non-empty, = comparator). Exercises the pin-fallback path; the
  cur_term() path rests on unit tests.
- OUTSTANDING before Step 5 closes: one Healthchecks dashboard glance
  (post-deploy ping continuity — the dead-man signal is the one watcher that
  runs when nobody is looking; it gets its checkbox).

### 2026-07-26 06:14Z — STEP 4 EXECUTED: deploy mechanically successful (status → DEPLOYED-VERIFYING)
- Evidence: sha `1ee417f` (confirmed = intended HEAD) shipped app.py+guardian.py+
  confidence.py+schools.py; 4 transfers at expected sizes; `active` post-restart;
  DEPLOYED.log first line written; `deployed` tag moved; deploy-record commit
  `29da856`; `.prev` snapshots now exist on VM (rollback is live).
- Anomaly A (engineer communication defect): operator executed rollback.sh
  BEFORE deploying (was handed as "keep in your other hand"). No-op (no .prev
  yet) + one benign restart of old code. Corrective rule adopted: commands not
  meant for immediate execution are labeled DO-NOT-RUN—SAVE-THIS.
- Anomaly B (script wart): smoke grep matched a STALE 'Poller started' from
  Jul 25 02:54 (journalctl -n60 + grep -m1 finds oldest in window). Service
  `active` is the strong signal; new-code proof deferred to Step 5 by design.
  Post-shadow backlog: smoke should use --since restart; rollback.sh should
  skip restart when nothing restored.
- Timeline refinement: yesterday's untracked deploy = app restart ~02:54 EDT
  Jul 25; schools.py file updated ~evening likely WITHOUT restart (two newest
  schools not live-served until tonight's restart).
- Verdict: proceed to Step 5 — deployment not declared healthy until the
  running process proves new-code shadow behavior.

### 2026-07-26 02:12 — STEP 3 CLOSED: CEO GO RECEIVED
- CEO go, verbatim in chat: "lets goo all six" — covers the full six-item
  inventory (guardian shadow · auto-roll disarm · stamp fix · damped paging ·
  end-of-cycle sends · dormant internals). Nothing held back.
- Backup freshness at Step 4 open: 0.3h old (rule: <6h) — no re-backup needed.
- Tree clean at `f6d88d8`; 36/36 tests green at this HEAD (verified Step 2).
- Step 4 issued: single command via ops/deploy.sh (app mode, --app-approved);
  rollback command placed in operator's hands in the same message.

### 2026-07-26 — Step 3 gate (a) satisfied: service-health baseline
- Evidence: operator observed Healthchecks last ping **8 seconds ago** (cadence
  ~20s). Poller confirmed actively completing cycles immediately pre-deploy.
  Baseline established: any post-deploy ping gap is attributable to the deploy.
- Remaining Step 3 gate: CEO's explicit go on the six-item inventory.

### 2026-07-26 — STEP 2 CLOSED: SAFE TO CONTINUE (major findings)
- Evidence: `systemctl is-active` = active. VM hashes matched git exactly:
  app.py→`b85c0f6`, schools.py→`0e47cec`. Tonight's backup contains alert_log +
  sms_consent tables.
- FINDING 1 (assumption corrected): production is NEARLY CURRENT, not weeks old.
  A deploy happened ~07-25 evening (post-freeze, outside ops/deploy.sh, no
  DEPLOYED.log entry) — coherent with the CEO-authorized SMS-lane work (10DLC
  needs the consent page live). The feared "weeks of undeployed delta" already
  shipped then; prod restart also re-armed+ran the daily term auto-roll (as
  b85c0f6 has no gate) and executed the alert_log/sms_consent migrations.
- FINDING 2: sibling-lane commits landed on main DURING Phase D prep
  (0e47cec 777-schools; 183236c Stripe refund→auto-downgrade, dormant;
  e2d5163 SMS log tweak). None touch guardian files. Test suite re-verified at
  current HEAD `23f1223`: 36/36 OK. Working registry 777 = prod.
- FINDING 3 (delta inventory for Step 3): deploying HEAD changes only —
  guardian shadow start; auto-roll ARMED→DISARMED (C4); stamp fix (C5);
  damped/added operator pages; end-of-cycle sends; dormant internals
  (SMS dry-run plumbing, Twilio log clarity, Stripe refund-downgrade,
  /sms/inbound signature-prep gated on TWILIO_TOKEN). schools.py byte-identical.
  ZERO public-HTML changes (verified by diff scan).
- Recommendation logged: all lanes adopt ops/deploy.sh from now on;
  DEPLOYED.log's first honest line will be our Step 4.
- Verdict: SAFE TO CONTINUE. Step 3 gates: (a) Healthchecks dashboard glance
  (asked 3x, now explicitly blocking), (b) CEO's explicit go naming this
  inventory, (c) fresh re-backup at Step 4 open if the 01:57 backup is >6h old.

### 2026-07-26 — STEP 1 CLOSED: SAFE TO CONTINUE
- Evidence complete: `~/SeatWatchVault/pre-guardian-2026-07-25.bak` mtime Jul 26
  01:57 (fresh, taken minutes before verification), integrity `ok`, users=5,
  watches=17 (exact prod match). Size 81,920B vs 53,248B on 07-23 with identical
  counts — assessed as normal SQLite page churn from latch updates; counts are
  the load-bearing check. chmod 600 suggested (optional).
- Verdict: SAFE TO CONTINUE. Standing commitment: fresh re-backup immediately
  before Step 4.
- Step 2 issued: Healthchecks glance (carried over as service-health baseline)
  + `systemctl is-active` + sha256 of VM app.py/schools.py. Engineer side:
  per-commit hash tables precomputed for both files (181 + 166 versions) for
  instant match; STOP condition armed if a pasted hash matches no git blob.

### 2026-07-26 — Step 1 evidence received (partial)
- Evidence: operator pasted verification only — `pre-guardian-2026-07-25.bak`
  (note: 07-25 filename, from the first instruction block): integrity `ok`,
  users=5, watches=17 (exact match to last-known prod). Proves a real, intact
  backup exists on the Mac.
- Missing before verdict: (a) file mtime — WHEN the backup was taken (`ls -la
  ~/SeatWatchVault/` requested); (b) Healthchecks dashboard status after the
  earlier connection reset. `backup ok` line from the VM was not pasted —
  accepted per Stage-0a precedent (integrity + coherent counts are the
  stronger proof), logged as a repeat of that recorded exception.
- Decision: regardless of mtime, a fresh 2-minute re-backup will run
  immediately before Step 4 (the first mutating step). Verdict pending the
  two 10-second checks.

### 2026-07-26 — Step 1 first attempt: no-op, two anomalies noted
- Done: nothing reached production. Operator's paste showed (a) an idle SSH
  session dropping with "Connection reset by peer" — assessed as a routine idle
  timeout, to be confirmed via Healthchecks dashboard glance before retry; and
  (b) the backup command aborted by the shell because the `<VM-HOST>`
  placeholder was pasted literally (zsh redirect) — command never executed.
- Anomaly (recorded): the VM origin IP entered the chat transcript via the
  operator's paste, contrary to the operator's own ground rule. Assessed
  non-blocking (Cloudflare fronting + firewall unchanged); follow-up queued
  post-shadow: tighten/rotate decision.
- Decision: reissue Step 1 with fully literal commands (IP filled in, backup
  filename dated 2026-07-26); Healthchecks glance added as pre-check.

### 2026-07-25 — Journal opened (pre-deploy)
- Done: V1 frozen (`e6c518d`); packet delivered; step protocol ratified by CEO; deploy
  deferred to when CEO is fresh (engineer recommendation, CEO accepted).
- Evidence: freeze record; 36/36 test run; clean `git status`.
- Anomalies: none.
- Decisions: journal lives in this file, updated at every step; final deployment
  report will be produced when Step 6 completes.
