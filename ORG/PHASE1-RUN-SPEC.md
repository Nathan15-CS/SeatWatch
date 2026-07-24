# Phase 1 — Run Foundation: Implementation Specification

> STATUS: APPROVED WORKING PLAN. Later CEO directives and ORG stage records supersede any conflicting details.

**Status: PLAN ONLY — nothing here is built, deployed, or executed until the CEO approves the plan and authorizes each change. 2026-07-23.**

Scope per CEO directive: (1) backups + tested restore, (2) deterministic health/liveness monitoring, (3) safe rollback/containment, (4) false-alert & silent-failure protection, (5) compute/spend limits, (6) auditable release record, (7) interfaces for future Verify/Grow/Grab/Build workflows. Grounded in a fresh code inspection of `app.py` (2,895 lines), `schools.py`, `seatwatch.py`, docs, and git state as of commit `2302ddf` (775 schools live).

---

## A. Current-State Assessment

### Exists and works (verified in code — do not rebuild)

| Capability | Where | Notes |
|---|---|---|
| Per-course health guard | app.py:2486-2501 | Consecutive-fail counter (threshold 5), pages operator once, pages recovery. Fail-closed: no data → no alert. |
| Fake-all-open watchdog | app.py:2293-2303, 2503-2515 | Status-only schools that never show a closed section get flagged after 400 observations. Page-only *by documented design* (a heuristic must not silence a real school). |
| Stale-term false-alert defense | app.py:2468-2484 | Watches from an old term are skipped on definite mismatch — deliberately, to prevent false alerts. The *skip* is correct; the *silence* around it is the defect (see below). |
| Delivery-failure honesty (partial) | app.py:2808-2853 | Alert latches only if ≥1 channel reports success; total failure pages the operator once and retries every cycle. Ledger comment already recognizes ntfy 200 ≠ human reached. |
| Per-school crash containment | app.py:2432-2441 | One adapter crashing cannot kill the cycle; concurrent fetch pool. |
| SMS cost controls | app.py:128-152, 2652+ | Dormant (env-gated), paid-tier-only, and every cap ledger-derived precisely so restarts can't reset a runaway's own breaker: $20/day site cap, per-watch latch, per-user daily, 1h dedup, velocity breaker with floor. Twilio auto-recharge OFF is the code-independent ceiling. This is the strongest subsystem in scope item 5 — already done. |
| Dead-man's switch (code side) | app.py:2354-2361 | Pings HEALTHCHECK_URL each cycle if set. **Unknown: whether the env var is actually set in prod** (verification step V0, below). |
| Weekly fire drill | app.py:2378-2428 | Rotates 7 schools, sanity-checks data (`open == seats>0`), proves fetch→publish weekly, pages PASS/FAIL. Proves the *ntfy leg only* — not web push (gap noted). |
| Restart-safe timers | app.py:2305-2336 | `watches.db.state.json`, atomic merge; summary/drill timers survive restarts (lesson already learned and documented in code). |
| Operator alerting | app.py:2342-2351 | Web push to admin + ntfy topic backup. |
| Stats endpoint | app.py:75-78 | `/admin/stats`, env-key-gated, aggregates only, 404 without key. |
| Deploy discipline (docs) | CONTRIBUTING_AGENT.md:66-73 | Builder commits+pushes then STOPS; owner deploys manually: `scp` two files + restart. Oracle Always-Free VM, systemd service, root-only `/etc/seatwatch.env`. |
| Secrets hygiene | verified | No `.db`/`.env`/key files tracked in git; secrets env-only. |

### Exists but incomplete

1. **Watchdog state is in-memory** — `health`, `_ALLOPEN`, `_undelivered`, `_stale_logged` all reset on every restart (the state file exists but doesn't carry them). A restart mid-outage re-pages; a flagged fake-open school unflags itself.
2. **Alert latch counts ntfy alone as "delivered"** (app.py:2839) — publishing to a topic with zero subscribers returns 200, latches the watch, and stops retries. The code's own comment (2830-2832) admits this. A push-first user whose push fails while ntfy "succeeds" loses the seat silently.
3. **Stale-term handling is log-only** (app.py:2481) — the skip prevents false alerts but nobody is told: no operator page, no user notice. A silent miss by the Product Charter's definition.
4. **Poller error paging has no damper** (app.py:2877-2882) — a *persistent* cycle-level error (e.g., DB lock) pages the operator every 20 seconds.
5. **Fire drill proves one leg** — ntfy publish, not web push delivery. Green drill ≠ working user channel.

### Genuinely missing

6. **Backups: zero, anywhere.** `watches.db` on the VM has never been copied. The single unrecoverable asset.
7. **Release record: none.** No log of what was deployed when; no `deployed` marker; the raw `scp` habit can ship whatever is in the working tree (the tree is dirty *right now* — see risks).
8. **Rollback: none.** No previous-version copy kept on the VM; recovery from a bad deploy = reconstruct from git by hand under pressure.
9. **Mass-alert circuit breaker: none.** If one adapter's format breaks into all-open (numeric-seat schools are *not* covered by the all-open watchdog), every watcher of that school gets a false alert in one cycle. At 5 family watches the blast radius is small; the day users arrive it is the company-ending event. The marketing page promises "never a fake alert" seven times.
10. **Restore procedure: none written, never rehearsed.**
11. **Ops metrics history: none** — `/admin/stats` is a live snapshot; no time series for funnel or health trends.

### Urgent (active risk today)

- **U1 — Zero backups** (item 6): one VM disk event erases every account and watch. *Most urgent item in this plan.*
- **U2 — Term auto-roll armed against a stamping mismatch:** the poller auto-rolls terms daily (app.py:2866-2872, verify-before-adopt); watches are stamped at creation with the *static seed term* `getattr(school,"term","")` (app.py:2262/2280) while the cycle compares the *dynamic* `cur_term()` (app.py:2465-2477). Consequences, verified in code: after any school auto-rolls, (a) all its pre-roll watches silently stop alerting (log-only), and (b) **every new watch created there is stamped with the stale seed term and is dead on arrival, silently**. An untracked `research/term-roll-fix.patch` + `TERM-ROLL-AUDIT-2026-07-20.md` exist from a prior session — to be *inspected, not trusted* during C4/C5.
- **U3 — Dirty working tree + active parallel sessions:** deleted `.claude/launch.json`, modified lane notes, 6+ untracked files (including the term-roll patch, one `git clean` from vanishing), and another session committed to this repo *today*. The raw-scp deploy ships whatever the tree holds — this is the standing gate-defeat mechanism.
- **U4 — Production SSH key in `~/Downloads/`** (`ssh-key-2026-06-30.key`) — one Downloads cleanup from permanent lockout (no second copy known).
- **U5 — Dead-man's switch unverified** — if HEALTHCHECK_URL was never set in prod, VM death is discovered by users, not by email.

### Deliberately deferred (see E)

Everything not listed above — including user-facing blindness notices, term-roll re-arm machinery, the fabricated-testimonial removal (R3, separately queued for CEO), visits/funnel instrumentation, watch.py deletion, backup encryption, staging/CI/tests.

---

## B. Minimal Phase 1 Architecture

Three small pieces of deterministic machinery + five contained code changes. No agents. No orchestration. No rewrites.

```
  Mac (~/SeatWatchVault/)               Oracle VM (production)
  ┌──────────────────────┐   pull    ┌────────────────────────────┐
  │ launchd: nightly scp │ ◄──────── │ cron: nightly sqlite3      │
  │ newest ring file +   │           │ .backup ring (7 days)      │
  │ metrics.jsonl        │           │ + healthchecks ping        │
  └──────────┬───────────┘           ├────────────────────────────┤
             │ restore drill          │ app.py (5 contained edits) │
  ┌──────────▼───────────┐  deploy   │  • auto-roll env-gate OFF  │
  │ repo: ops/deploy.sh  │ ────────► │  • persisted watchdogs +   │
  │  clean-tree check    │   scp     │    page damper             │
  │  schools|app modes   │  + .prev  │  • mass-alert breaker      │
  │  DEPLOYED.log append │  + smoke  │  • honest latch            │
  │  ops/rollback.sh     │           │  • stamp fix + loud stale  │
  └──────────────────────┘           │  • nightly metrics.jsonl   │
                                     └────────────────────────────┘
  healthchecks.io (free): process-alive · backup-ran · vault-pull
```

**How the scope maps:** (1) backups = ring + pull + rehearsed restore; (2) monitoring = existing guards persisted + healthchecks verified/expanded; (3) rollback = `.prev` copies + `rollback.sh`, containment = breaker freeze; (4) false alerts = breaker + honest latch, silent failures = loud stale-term + damper; (5) spend = SMS system already done + verify-SMS-off + UA landmine check (agent-token spend is governed by subscription limits and the CEO-set org-work cap — a process rule; no machinery built); (6) release record = `DEPLOYED.log` + `deployed` tag via the only deploy path; (7) interfaces = `DEPLOYED.log` (Build/Verify read what's live), `metrics.jsonl` (Grow's funnel floor, Verify's health evidence), `ops/` scripts (the release path future certification precedes), gate-evidence convention deferred to Verify's own standup.

**Explicitly NOT built in Phase 1:** any new agent, any orchestration layer, any new public endpoint, any framework/dependency (stdlib-only stands), any rewrite of working fetch/alert logic, term-roll *re-arming* machinery, Verify/Grow/Grab department tooling.

---

## C. Ordered Implementation Sequence

Every VM-touching command is executed by the CEO (agents never hold credentials); every code change deploys only via the C3 script from a clean tree with an explicit per-change CEO go. R2 changes additionally get the standing external reviewer handoff before deploy.

### Stage 0 — CEO manual acts (no code, ~25 minutes, do first)

**0a. First-ever backup** *(THE single smallest first change — see F)*
- **Failure prevented:** total, permanent loss of every account/watch on any VM disk event. Today there are zero copies.
- **Scope/deps:** none. Two commands, dictated, CEO-executed.
- **Method:** on the VM: `sqlite3 ~/seatwatch/watches.db ".backup /tmp/seatwatch-20260723.bak"` (the `.backup` API yields a consistent copy; a raw copy of a live SQLite file can be torn). From the Mac: `scp` that file into `~/SeatWatchVault/` (create dir).
- **Risk:** R1 (read-only against prod DB via SQLite's own API). **Verification:** locally `sqlite3 <file> "PRAGMA integrity_check;"` returns `ok`; spot-check row counts. **Rollback:** n/a (pure copy). **CEO approval:** is the executor. **Acceptance:** dated file on the Mac, integrity `ok`. **Why Phase 1:** it is the whole reason Phase 1 exists.

**0b. SSH key out of Downloads** — move `~/Downloads/ssh-key-2026-06-30.key` → `~/.ssh/` with `chmod 600`; second copy into password manager. *(Credential: CEO-executed; agents never touch it.)* Prevents lockout-by-cleanup + overexposure. Acceptance: key at `~/.ssh` (600), in password manager, gone from Downloads. Risk R1.

**0c. Verify the dead-man's switch** — CEO on VM: `sudo grep -c HEALTHCHECK /etc/seatwatch.env` (count only — no values printed) and confirm the healthchecks.io dashboard shows pings arriving. If unset: create the free check and add the URL (becomes a gated env change + restart). Prevents silent VM death. Acceptance: check shows green pings ≤ poll interval old.

**0d. Tree hygiene + lane freeze decision** — commit-or-resolve every in-flight file until `git status` is clean (the untracked term-roll audit/patch get committed to `research/` as inputs, not applied); **CEO decides:** school-add lanes may keep committing `schools.py` work, but `app.py` is frozen to this Phase-1 series until C5 lands (two-writers hazard is live — another session committed today). Prevents: deploys shipping unreviewed strays; parallel edits colliding. Acceptance: clean tree; decision logged.

### C1. Backup automation *(scope 1)*
- **Failure prevented:** the manual 0a copy rotting stale; "we had a backup from March."
- **Scope/deps:** VM crontab line (nightly `.backup` into `~/backups/`, keep 7, ping healthchecks on success); Mac `launchd` plist (nightly pull of newest ring file + `metrics.jsonl` once C9 lands, ping a second check). Pull-from-Mac direction because the Mac sleeps: a missed pull is *visible* (missed ping → email), and the VM never needs credentials to the Mac.
- **Files:** new `ops/backup-vm.sh`, `ops/com.seatwatch.vaultpull.plist` (repo-committed for auditability); one crontab line (CEO paste).
- **Risk:** R1. **Verification:** force-run both once; two green checks; pulled file passes `integrity_check`. **Rollback:** remove cron line / `launchctl unload`. **CEO:** pastes both installs. **Acceptance:** 3 consecutive nightly green pings on both checks; dated files accumulating both sides. **Why Phase 1:** scope item 1; the ring makes 0a continuous.

### C2. Restore procedure + rehearsal *(scope 1, 3)*
- **Failure prevented:** owning backups nobody can restore under pressure (a backup that hasn't been restored is a rumor).
- **Scope:** `RUNBOOK.md`: full VM rebuild (provision → clone → restore newest Vault copy → env template *names only, never values* → systemd unit → DNS) + the 10-line "restore DB only" path. One rehearsal: restore the Vault copy to a scratch dir on the Mac, integrity + row-count against expectations, and one timed CEO walk-through of the doc.
- **Files:** `RUNBOOK.md` (new). **Risk:** R0 (doc + local-only exercise). **Verification:** the rehearsal IS it. **Rollback:** n/a. **CEO:** participates once. **Acceptance:** written, timed, rehearsed; CEO states he could follow it alone. **Why Phase 1:** backups without restore are theater.

### C3. Deploy script + release record + rollback *(scope 3, 6, 7)*
- **Failure prevented:** (a) the 2026-07-13-class incident — a raw scp of a dirty tree carrying unreviewed changes live; (b) "what is actually deployed?" having no answer; (c) no fast path back from a bad deploy.
- **Scope:** `ops/deploy.sh`: mode `schools` ships `schools.py` **only**; mode `app` ships both and requires an explicit `--app-approved` flag the CEO types; refuses dirty tree and non-main branch; on the VM copies current files to `.prev` before overwrite; restarts the service; smoke-checks (HTTP 200 + "Poller started" in the journal); appends `UTC · git SHA · mode · files` to `DEPLOYED.log` and moves the `deployed` git tag; prints every command before running it. `ops/rollback.sh`: restore `.prev` + restart — *always* permitted (safety inversion). Dry-run mode for the first pass.
- **Files:** `ops/deploy.sh`, `ops/rollback.sh`, `DEPLOYED.log` (all new; no app code). **Risk:** R1 (tooling; changes nothing until used). **Verification:** dry-run prints correct commands; first real use is C4's deploy, observed end-to-end; rollback rehearsed once immediately after (deploy → roll back → re-deploy). **Rollback:** don't use the script (old path still exists until retired). **CEO:** runs every invocation (his key). **Acceptance:** C4 ships through it; `DEPLOYED.log` gains its first honest line; rollback rehearsal returns the service in <2 minutes. **Why Phase 1:** scope 3+6, and every later change depends on it.

### C4. Term auto-roll containment *(scope 4 — first code change, ~4 lines)*
- **Failure prevented:** U2's ongoing harm: any daily auto-roll silently killing a school's existing watches and rendering its *new* watches dead on arrival. Also removes the fall-boundary race (early roll to Spring '27 while fall is live).
- **Scope:** env-gate the daily `refresh_all_terms` spawn (app.py:2869-2872) behind `AUTO_ROLL_TERMS=1`, default **off**; log the disarmed state at startup. Terms freeze at last-known-good (all current terms are correct for fall). Fail-closed cost: manual term bumps at semester boundary until C5 + re-arm machinery exist — acceptable at 5 family watches; watch-death is not.
- **Files:** `app.py` (~4 lines), PROJECT_OVERVIEW env-var table. **Deps:** C3 (ships as its first gated `app` deploy), 0d (clean tree). **Risk:** **R2** (term system) → external reviewer handoff + CEO go. **Verification:** startup log shows "auto-roll disabled"; 24h of journal shows no refresh spawn; a family watch still alerts (fire drill + live behavior unchanged). **Rollback:** `rollback.sh` (.prev), or set env `AUTO_ROLL_TERMS=1` + restart. **CEO:** approves deploy. **Acceptance:** verified log lines + one normal alert cycle post-deploy. **Why Phase 1:** stops the one *currently armed* silent-miss machine.

### C5. Watch-stamp fix + loud stale terms *(scope 4)*
- **Failure prevented:** new watches born dead (stamped with the stale seed term while the school's active term moved — verified at app.py:2262/2280 vs 2465); stale-term skips that nobody ever hears about.
- **Scope:** stamp watches at creation with the school's *current* term (`cur_term()` fallback `.term`); on stale-term skip, page the operator once per (school, term-pair) via `operator_alert` and count it in the daily summary (the skip itself stays — it is correct). User-facing stranded-watch notices are deferred (UI + Serve work). Inspect the prior session's `term-roll-fix.patch` as input; verify against the code, do not apply blind.
- **Files:** `app.py` (2 INSERT sites + the stale branch + summary line). **Deps:** C4 (rolls are now deliberate), C3. **Risk:** **R2** (alert eligibility) → reviewer handoff + CEO go. **Verification:** local harness (fake school object; create → roll → observe skip + single page; new watch carries rolled term); then one live create/delete of a test watch by the CEO post-deploy. **Rollback:** `.prev`. **Acceptance:** harness passes; live test watch stamps the active term; summary shows stale-count line. **Why Phase 1:** completes the term-safety pair with C4; cheap now, catastrophic later.

### C6. Persisted watchdogs + page-storm damper *(scope 2)*
- **Failure prevented:** restart amnesia (fail counters, all-open flags, undelivered set silently reset — a flagged fake-open school unflags itself on every deploy); a persistent poller error paging every 20 seconds until the phone melts.
- **Scope:** carry `health`, `_ALLOPEN`, `_undelivered`, breaker state (C7) in the existing `watches.db.state.json` (write-on-change; trivial at this scale); wrap `operator_alert` with a per-failure-class damper: page once, then at most once per 6h per class, log everything.
- **Files:** `app.py` (state plumbing + damper wrapper). **Deps:** C3. **Risk:** R1 (monitoring behavior only). **Verification:** local: synthetic repeated exception → exactly 1 page + logs; kill/restart → counters persist. **Rollback:** `.prev`. **Acceptance:** restart carries state; simulated storm produces 1 page. **Why Phase 1:** makes every guard trustworthy across restarts before users depend on them.

### C7. Mass-alert circuit breaker + honest latch *(scope 4 — the Promise hardening)*
- **Failure prevented:** (a) one adapter format-break mass-firing false "seat open" to every watcher of a school in one cycle — the company-ending event the all-open watchdog does NOT cover (numeric-seat schools are exempt from it); (b) a push-first user losing a real seat because ntfy-to-nobody latched the watch.
- **Scope:** *(a)* deterministic pre-send gate in `run_cycle`: if the count of would-fire alerts in one cycle exceeds `MAX_ALERTS_PER_CYCLE` (default 10 — generous at 5 watches, env-tunable), send **none**, set a persisted freeze flag, page the operator; un-freeze = CEO-acknowledged env/restart or explicit clear. Respects the all-open watchdog's page-only philosophy for *heuristics* — this gate is not a heuristic, it is a volume tripwire. *(b)* latching requires a human-reaching channel (web push / email / SMS) when the user has one enrolled; ntfy-only success latches only for legacy topic-only watches (no enrolled channel) — preserving current behavior for them; ledger unchanged.
- **Files:** `app.py` (`run_cycle` gate + `_alert` latch condition). **Deps:** C6 (persisted flag + damped paging). **Risk:** **R2** (alert logic) → reviewer handoff + CEO go. **Verification:** local harness: N simulated open flips > cap → zero sends + freeze + one page; drill (1 alert) unaffected; latch matrix tested for topic-only vs push-enrolled users. **Rollback:** `.prev`. **Acceptance:** harness matrix passes; live fire drill still PASSES post-deploy. **Why Phase 1:** the breaker is the single strongest structural defense of the only claim the company has.

### C8. Spend/abuse verification *(scope 5 — mostly verification, not construction)*
- **Failure prevented:** dormant SMS path detonating on activation (`UA` at app.py:2643 — confirm defined; if not, NameError on first live SMS: 1-line fix); accidental `SMS_ENABLED` in prod env; email send-storms (add a simple per-hour send cap + page, mirroring the SMS pattern, only if inspection shows none).
- **Scope:** read-only env audit by CEO (`grep -c` counts for SMS_ENABLED/PAID_ENABLED — expect 0); code check for `UA`; email cap only if missing. Agent-token spend: explicitly out of app scope — bounded by subscription limits and the CEO-set org-work cap (OS §10); no machinery built.
- **Files:** possibly `app.py` (≤5 lines). **Risk:** R1. **Verification:** env counts = 0; SMS harness call path raises nothing with SMS off. **Rollback:** `.prev`. **Acceptance:** documented audit result in the commit message. **Why Phase 1:** cheap closure of the last spend hole; the heavy lifting already exists.

### C9. Nightly metrics line *(scope 2, 7 — the Grow/Verify interface)*
- **Failure prevented:** the funnel and health trends being unmeasurable (Grow's first packet would otherwise cite numbers no machinery produces); no history behind `/admin/stats`.
- **Scope:** at daily-summary time, append one JSON line to `metrics.jsonl` on the VM: date, users, external-account count (admin/family allowlist), watches by school-count, alerts by channel (from `alert_log`), health snapshot (fails/frozen/stale-pairs), breaker state. C1's pull copies it to the Mac nightly. No new endpoints; future workflows read the file.
- **Files:** `app.py` (~25 lines in `maybe_daily_summary`), `ops/backup-vm.sh` (+1 file to ring). **Deps:** C1, C6. **Risk:** R1 (write-only telemetry). **Verification:** 3 nightly lines with sane values vs `/admin/stats`. **Rollback:** `.prev`. **Acceptance:** file on Mac grows nightly; fields reconcile. **Why Phase 1:** it is the interface Grow and Verify stand up on; costs ~nothing now.

---

## D. Verification & Rollback Plan (global)

- **Every deploy:** via `ops/deploy.sh` only, from a clean main tree, per-change CEO go; `.prev` snapshot taken automatically; smoke check must pass or the script prints the rollback command.
- **Rollback:** `ops/rollback.sh` restores `.prev` + restarts — always permitted, no approval needed (safety inversion), rehearsed once at C3.
- **R2 changes (C4, C5, C7):** external reviewer handoff (standing rule) before deploy; local test harness run recorded in the commit message.
- **Backups:** verified by healthchecks pings (both legs separately) + monthly `integrity_check` on the newest Mac copy + the C2 rehearsal.
- **Monitoring of the monitors:** three free healthchecks checks (process-alive, backup-ran, vault-pull); a missed ping emails the CEO out-of-band.
- **Post-change watch:** after every deploy, the next fire drill and one live alert cycle are observed before the next change begins — one change in flight at a time, ever.

## E. Explicit Deferred-Work List

| Item | Why deferred | Earliest |
|---|---|---|
| Term auto-roll re-arm (guarded rolls, per-roll pages, one-tap bumps) | needs C5 proven + CEO gate; rolls are safely off | after C5 + CEO decision |
| User-facing blindness notices (watch-page banner, stranded-watch push) | UI + copy = R2/Serve territory; operator visibility (C5/C6) covers current scale | Serve/Grow standup |
| Fabricated-testimonial removal (app.py:1602) | R3 public claim, **already queued for CEO's one-line go** — flagged: still live today | CEO go, any time |
| Visits counter / funnel instrumentation | Grow's standup work; metrics.jsonl is the floor it builds on | Grow phase |
| Fire-drill web-push leg + operator ack-link check | valuable; not the binding risk this month | Phase 1.5 |
| `watch.py` deletion + repo housekeeping | dead prototype (verified unimported); zero risk, zero urgency | next app deploy, piggyback |
| Backup encryption at rest | Mac is FileVault-protected, family-only data today; revisit at first external user | Trust data-arm trigger |
| `/health` endpoint (proper) | smoke check uses HTTP 200 on `/` for now | with C9 follow-up |
| Staging env, CI, test framework, containers | excluded by OS design — $0 stdlib operability is load-bearing | not planned |
| SMS full go-live review | dormant by design; C8 only defuses the landmine | CEO decision |
| OPERATOR_TOPIC default rotation (guessable default in repo) | env-set in prod presumed; verify during 0c; web push is primary channel | 0c note |

## F. The Single Smallest First Change

**Stage 0a — the first backup of `watches.db`, today.** Two dictated commands, zero code, zero deploy risk, and it converts the company's only unrecoverable failure mode into a recoverable one. Everything else in this plan can wait a day; this shouldn't.

---

*Plan ends. Nothing is built, changed, or deployed until the CEO approves this plan and authorizes Stage 0a (or amends the sequence). Per the standing rule, this plan itself is committed nowhere yet — it exists as `ORG/PHASE1-RUN-SPEC.md`, untracked, awaiting direction.*
