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

---

# Operator v2 — objectives and typed handoffs

v1 keeps the system healthy. v2 keeps work moving, without you prompting each step.

- **State layer:** `ops/objectives.py` · **Worker CLI:** `ops/opctl.py`
- **Tick duty:** `objective_tick` (R1, 900s) · **Worker prompt:** `ops/worker-skill/SKILL.md`
- **Tests:** `ops/test_objectives.py`

## The division of labour

| Who | Decides | How |
|---|---|---|
| **Manager** | *What* should happen | writes an Objective |
| **Operator** | *Whether* work may proceed, and what is TRUE | deterministic: routing table, budget arithmetic, `COUNT` over evidence |
| **Workers** (Grab/Build) | *How* | judgment — an LLM, and only here |
| **Critic** | Whether the work is *acceptable* | certification or rejection, citing evidence |

The Operator never calls a model. That is the point: it is the component that answers
"what is true", and a probabilistic answer to that question is not an answer.

## Authority — creating an objective is not a spending decision

An objective is born `proposed` with a budget of **zero**. Nothing can be queued
against it and no work can occur. There is deliberately no path that activates one at
its default budget: *turn it on* and *authorise it to spend* are the same decision,
made once, by a human.

```bash
python3 ~/seatwatch/ops/opctl.py status
python3 ~/seatwatch/ops/opctl.py show --objective fall-school-expansion
python3 ~/seatwatch/ops/opctl.py objective-activate --id fall-school-expansion --budget 10
python3 ~/seatwatch/ops/opctl.py enqueue --objective fall-school-expansion --key marshall
python3 ~/seatwatch/ops/opctl.py objective-stop --id fall-school-expansion --reason "..."
```

`fall-school-expansion` exists today, parked, target 7 (the seven batches held in
BOARD.md). It stays parked until you activate it — it does **not** self-activate on
any date.

## Stop conditions (no open-ended loops)

The tick closes an objective and raises a finding when:

- **target met** — enough certified items;
- **budget exhausted** — spent its whole allowance short of target. Raising the
  budget is a human decision, never automatic;
- **dry well** — N completed items and not one `BUILD` verdict. The measured lesson
  from BOARD.md: continuous operation does not refill a dry well.

## The typed contract (why workers go through `opctl`)

A worker's result is validated before the system believes any of it. `verdict` is an
**enum** — text scraped from a university website cannot become one. A `BUILD`
verdict requires all eight accuracy gates recorded and passing; a `BUILD` that
contradicts a failed gate is refused. A violation fails **closed**: the item is
parked as `failed` with the rejected payload kept as evidence, and is not retried.

The Operator does not run the gates and never claims to — Build re-runs them before
shipping. It only refuses to carry an unevidenced `BUILD`.

## Rejection is not a retry

A Critic rejection is a judgement, recorded as one. The first returns the item for
one rework. The **second** raises an adjudication request and the item stops — no
third attempt. Otherwise "retry until the checker agrees" becomes maker-grades-own-
work through the back door (AI Operating System §5.3).

## Enabling the worker bridge

`ops/worker-skill/SKILL.md` is the worker prompt: claim one item, do the work, return
a typed result, stop. Install it as a scheduled task to let work flow unattended.

**Do this when you activate the first objective, not before** — with no active
objective a worker run claims nothing and exits, so scheduling it early is model
usage bought for no benefit.

## Honest limitation

The Operator runs unattended under launchd. The **workers do not**: a scheduled
Claude task runs only while the Claude app is open, and this is a laptop that sleeps.
So this is real unattended automation, but it is **not 24/7**, and it will not be
until the model-bearing workers run on an always-on cloud runner. Until then, "the
queue is quiet" and "nothing is claiming" are different statements, and only the
Operator's heartbeat distinguishes them.
