# STAGE 0d — REPOSITORY STABILIZATION — 2026-07-24 (UTC)

Operator: Nathan (CEO — itemized approvals) · Executor: Phase-1 Run session · Risk: R0 inspect / R1 commits · **Result: PASS** · **Pushed: no**

## Baseline and drift control
- Authoritative snapshot: **2026-07-24 04:05:32 UTC**, HEAD `2302ddf`, 17 dirty items (1 D, 3 M, 13 untracked incl. the one approved pre-D3 administrative write, `stage-0d-scout-task-disable.md`), single worktree, no stashes, no extra branches, local = origin.
- Pre-D4 drift recheck (2026-07-24 20:52:05 UTC): **DRIFT NONE** — 17/17 exact line match, HEAD unchanged.
- Origin classification of prior scout commits: **UNRESOLVED** (automation vs interactive; evidence in `stage-0d-scout-task-disable.md`); no second scheduled task exists.

## Dispositions executed (all CEO-itemized)
| Item | Disposition | Where |
|---|---|---|
| `.claude/launch.json` (was deleted in tree) | **RESTORED** — evidence showed tooling origin (f744929, 2026-07-05) but could not prove deliberate deletion; conservative default applied | working tree, matches HEAD |
| 3 lane notes (PARTNER-NOTE-codex, lane-codex, lane-grabber) | committed | `aa619f7` |
| TERM-ROLL-AUDIT-2026-07-20.md + term-roll-fix.patch | committed — **REFERENCE ONLY, never applied**; patch base `1761838` (2026-07-20), predates HEAD; `--check` trailing-whitespace hits are intrinsic to patch format, preserved verbatim by design | `fc9f48f` |
| DRAFT-refund-policy.md (draft label verified) + CONSTITUTION-DRAFT-v1.2.md (superseded-status line prepended per CEO approval) | committed | `9422103` |
| `research/cs_public_recheck.json` | **DELETED** (CEO-approved; no consumer in repo, scheduled task, or agent defs). Full content: `["alaska", "ptc", "una"]` | untracked — approval + this quote is the audit trail |
| `research/vsb_ctlog_domains.txt` | **DELETED** (CEO-approved; superseded by committed lane-grabber enumeration conclusion). Full content: `FOUND 0` | same |
| 6 ORG paths (OS blueprint = adopted; Phase-1 spec + CEO status note; records 0a PASS-with-exception, 0b **PARTIAL** (attestation pending), 0c **PARTIAL** (rotation closure pending), 0d-scout) | committed, itemized | `6e27002` |
| `.claude/agents/school-dash-researcher.md` | committed | `c77b9d1` |
| CONTRIBUTING_AGENT.md freeze marker (CEO text verbatim) | committed | `840ce9a` |
| This record | committed as the final Stage 0d act | (SHA in log) |

## Scout task state
`seatwatch-hold-and-ctlog-weekly`: **disabled** (2026-07-24 ~04:03 UTC), remains disabled after Stage 0d. Re-enable requires: staging review proving it stages **only** `research/README.md`, proof it cannot push unrelated local commits, and separate CEO approval.

## Freeze state
PHASE-1 FREEZE active per `CONTRIBUTING_AGENT.md` (commit `840ce9a`): app.py = Phase-1 Run session only; deploys only via approved packets + Stage-2 script; no dirty-tree deploys; automated repo-writers stay disabled. CEO notifies live lanes directly (file markers cannot stop a session that doesn't look).

## Deferred / open items
1. **0b attestation** — password-manager copy (manager + item name) still unconfirmed; record stays PARTIAL.
2. **0c rotation closure** — H7 facts (process env count, new check Up, old check paused) or explicit CEO-attested closure; record stays PARTIAL. Old Healthchecks check retained paused as rollback.
3. **Push** — all Stage 0d commits are local only; push is its own future CEO approval.
4. **HEAD-vs-deployed skew** — unknown what the VM actually runs vs current main; **mandatory pre-step in Stage 3: diff HEAD app.py/schools.py against the VM's running copies before any deploy** (the 2026-07-13 lesson; audit noted gated paid/UI work existed in app.py as of 7/20).
5. **Term-roll detonation date Oct 1** (backward-roll into completed terms; empty-stamp false-alert path) — Stage 3 containment remains urgent; audit + patch are its reference inputs.
6. `PHASE1-RUN-SPEC.md` file text unamended by later refinements (by design — CEO status note declares directives + records supersede).
7. Scout-task prompt hygiene at re-enable review: "append one line" has grown to 20-26 lines/run into a 606KB README (separate, minor).
