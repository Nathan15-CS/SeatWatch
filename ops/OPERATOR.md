# The Operator — runbook

Deterministic runner for the repeated off-server operations checks. Not an LLM
agent: it is plain Python that answers the same questions the same way every time.

- **Engine:** `ops/operator_engine.py` · **Duties:** `ops/duties.py` · **Tests:** `ops/test_operator.py`
- **Schedule:** `ops/com.seatwatch.operator.plist` (launchd, every 900s)
- **State, logs, findings:** `~/.seatwatch-operator/` — deliberately **outside the git tree**

## Where it runs, and why not on the VM

It runs on **this Mac**, not on the SeatWatch server. That is a design decision, not
a shortcut:

| Duty | Reads | Exists on the VM? |
|---|---|---|
| `repo_hygiene` | git working tree | **No** — the VM has no git repo (file-level scp deploys only) |
| `deploy_truth` | `deployed` tag + `DEPLOYED.log` | **No** — same reason |
| `registry_guard` | local `schools.py` import | only the deployed copy, with nothing to compare it to |
| `guardian_journal` | `ORG/records/*.md` | **No** — not a deployed path |
| `backup_ring` | `~/seatwatch-backups` | **No, by design** — it is the *off-server* copy |
| `site_health` | public HTTPS | anywhere |

Five of six duties would be blind on the VM, and `backup_ring` would be actively
wrong: checking the backup from the same disk it lives on is the exact failure
`ops/pull_backup.sh` was written to fix ("that is a copy, not a backup").

`ops/deploy.sh` ships only `app.py schools.py guardian.py confidence.py`. The
Operator is **not** deployed and must not be added to that list.

**Honest limitation:** a laptop sleeps, so this is *not* a 24/7 monitor. It is a
frequent off-server observer. Healthchecks.io remains the only true always-on alarm
for the VM. The heartbeat below is what makes the difference detectable — a stale
heartbeat means the Operator is not running, which silence alone can never tell you.

## Commands

Status — what ran, what is open, is it alive. Exits `1` if any red finding is open,
so a monitor can consume the exit code:

```bash
python3 ~/seatwatch/ops/operator_engine.py status
```

Run now, without waiting for the schedule (runs only what is due):

```bash
python3 ~/seatwatch/ops/operator_engine.py once
```

Run everything now, ignoring both the schedule and the idempotency window:

```bash
python3 ~/seatwatch/ops/operator_engine.py once --force
```

Run a single duty:

```bash
python3 ~/seatwatch/ops/operator_engine.py once --only site_health --force
```

List duties, their risk class, and cadence:

```bash
python3 ~/seatwatch/ops/operator_engine.py list
```

Logs (written by launchd, newest at the bottom):

```bash
tail -40 ~/.seatwatch-operator/operator.log
```

Is the scheduled service loaded, and did its last run succeed:

```bash
launchctl print gui/$(id -u)/com.seatwatch.operator | grep -E "state|runs|last exit"
```

Restart the service (picks up an edited plist or duty file):

```bash
launchctl bootout gui/$(id -u)/com.seatwatch.operator; launchctl bootstrap gui/$(id -u) ~/Library/LaunchAgents/com.seatwatch.operator.plist
```

Stop it for now (it comes back at next login):

```bash
launchctl bootout gui/$(id -u)/com.seatwatch.operator
```

Disable it permanently — remove the symlink, then stop it. State and findings are
kept, so re-enabling resumes with history intact:

```bash
rm ~/Library/LaunchAgents/com.seatwatch.operator.plist && launchctl bootout gui/$(id -u)/com.seatwatch.operator
```

Re-enable:

```bash
ln -sfn ~/seatwatch/ops/com.seatwatch.operator.plist ~/Library/LaunchAgents/com.seatwatch.operator.plist && launchctl bootstrap gui/$(id -u) ~/Library/LaunchAgents/com.seatwatch.operator.plist
```

Tests (run these after touching the engine or any duty):

```bash
python3 ~/seatwatch/ops/test_operator.py
```

## What it will never do

Enforced in code, not by convention — see the invariants at the top of
`ops/operator_engine.py`:

- **Never writes to the repository.** State lives outside the git tree, and every
  mutating `git` subcommand is refused.
- **Never reaches production.** `ssh`, `scp`, `systemctl`, `sudo`, `rm`,
  `deploy.sh`, and `rollback.sh` are all refused.
- **Never executes anything above risk R1.** An R2+ duty is recorded as needing
  approval and is not run.
- **Never lets a failure look like a pass.** A duty that failed does not resolve its
  own prior findings.

## Reading a finding

Findings are deduped by key and carry `first_seen` and a count, so "new today" and
"been broken for a week" are distinguishable. A finding **auto-resolves** when a
later *successful* run stops reporting it — the open set is always current state,
not an append-only pile.

Findings whose key starts with `operator:` are about the Operator itself (a crashed
run, an exhausted retry, a duty needing approval). Those never auto-resolve; clear
one once it is genuinely handled:

```bash
python3 -c "import sqlite3,os,time; c=sqlite3.connect(os.path.expanduser('~/.seatwatch-operator/operator.db')); c.execute(\"UPDATE findings SET status='resolved', resolved_at=? WHERE key=?\", (time.time(), 'operator:crashed:site_health')); c.commit()"
```

## Adding a duty

Add a function to `ops/duties.py`:

```python
@duty("my_check", interval_s=3600, risk="R0", description="One line.")
def my_check(ctx):
    rc, out, _ = ctx.run(["git", "log", "-1", "--format=%H"])
    if rc != 0:
        return ctx.fail("git unavailable")
    if something_wrong:
        ctx.finding("key", "yellow", "what is wrong and why it matters")
        return ctx.attention("short summary", **evidence)
    return ctx.ok("short summary", **evidence)
```

Rules that keep this honest:

- `interval_s` is also the **idempotency window** — two runs inside it are one run.
- Return `attention` when the check ran and found something; `fail` only when the
  check itself could not complete. Conflating them is how a broken checker starts
  reading as a broken system.
- Return `blocked` when the duty needs access this machine does not have. It will
  not be retried, because retrying a permissions wall only burns budget.
- Anything that changes state must be `risk="R1"` at minimum, and the Operator will
  refuse to run anything above R1 at all.
- Use `ctx.last_detail()` to compare against the previous run — that is how a check
  reports a *trend* rather than a snapshot.
- Then run `python3 ops/test_operator.py`.
