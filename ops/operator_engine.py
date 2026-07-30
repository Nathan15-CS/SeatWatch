#!/usr/bin/env python3
"""
SeatWatch Operator — durable execution engine for unattended operational duties.

    python3 ops/operator_engine.py once     run every duty that is due, then exit
    python3 ops/operator_engine.py loop     same, on a cadence, holding a lease
    python3 ops/operator_engine.py status   what ran, what is open, is the engine alive
    python3 ops/operator_engine.py list     registered duties and when they are next due

(Named `operator_engine`, not `operator`: Python puts a script's own directory first
on sys.path, so a module named `operator.py` here would shadow the stdlib `operator`
module for every import in the process — including ones the stdlib makes itself.)

WHAT THIS IS
    The deterministic half of "operations": the repeated, checkable work that must
    happen whether or not a human or a model is watching. It owns no product logic.
    It runs `duties` (ops/duties.py), records what happened, and reports honestly.

WHY IT EXISTS (each of these is a recorded, real failure — not a hypothetical)
    * Unattended checks today are silent-unless-actionable, so "nothing ran" and
      "nothing is wrong" look identical. Every cycle here writes a heartbeat, so
      silence becomes a measurable, alarmable condition instead of a comfort.
    * Each scheduled run starts with no memory of the last one, so a slow drift is
      invisible. State is durable and append-only; a finding carries first_seen.
    * Work has been repeated because nobody could tell it had already been done.
      A run is keyed and UNIQUE-indexed, so a duplicate invocation cannot re-do it.

THE INVARIANTS (do not weaken; each one is load-bearing)
    1. NEVER WRITES TO THE REPOSITORY. State lives outside the git tree by
       construction, not by promise — the Phase-1 freeze disables automated
       repo-writing tasks, and a path outside the tree cannot violate it by accident.
    2. NEVER DEPLOYS, NEVER SSHes, NEVER TOUCHES PRODUCTION. `Ctx.run` refuses the
       commands that could. Reaching production is a human action, permanently.
    3. RISK-GATED. Only R0/R1 duties execute. R2+ is recorded as needing approval
       and is never run, matching the authority ladder in the AI Operating System.
    4. EVIDENCE BEFORE CLAIM. The run row is written before an outcome is reported,
       so a crash leaves a visible `running` row rather than a silent gap.
    5. BOUNDED. Max attempts, backoff, per-cycle duty cap, wall-clock budget. No
       unbounded retries, no open-ended loops.
    6. FAILURE NEVER LAUNDERS INTO CLEAN. A duty that failed does not resolve its
       own prior findings — only a duty that actually completed may do that.

Stdlib only, to match the rest of the codebase. Python 3.9+.
"""
import argparse
import json
import os
import secrets
import sqlite3
import subprocess
import time
import urllib.error
import urllib.request

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# State lives OUTSIDE the repo — invariant 1. Overridable for tests only.
HOME_DIR = os.environ.get("SW_OPERATOR_HOME", os.path.expanduser("~/.seatwatch-operator"))
DB_PATH = os.environ.get("SW_OPERATOR_DB", os.path.join(HOME_DIR, "operator.db"))

AUTO_RISK = ("R0", "R1")        # invariant 3: everything above this needs a human
MAX_ATTEMPTS = int(os.environ.get("SW_OPERATOR_MAX_ATTEMPTS", "3"))
BACKOFF_BASE_S = int(os.environ.get("SW_OPERATOR_BACKOFF_S", "60"))
BACKOFF_CAP_S = 3600
CYCLE_DUTY_CAP = int(os.environ.get("SW_OPERATOR_CYCLE_CAP", "25"))
CYCLE_BUDGET_S = int(os.environ.get("SW_OPERATOR_BUDGET_S", "600"))
LEASE_TTL_S = int(os.environ.get("SW_OPERATOR_LEASE_TTL", "900"))
EVENT_RETENTION_S = 30 * 86400

HOLDER = "%d-%s" % (os.getpid(), secrets.token_hex(4))

# Commands the engine refuses outright (invariant 2). A duty that believes it needs
# one of these is a duty that should be producing a proposal for a human instead.
_FORBIDDEN_BIN = {"ssh", "scp", "rsync", "systemctl", "sudo", "rm", "shutdown", "reboot"}
_FORBIDDEN_GIT = {"commit", "push", "add", "rm", "mv", "reset", "checkout", "restore",
                  "clean", "merge", "rebase", "tag", "stash", "apply", "cherry-pick",
                  "revert", "fetch", "pull", "gc", "config", "switch", "branch"}

OK, ATTENTION, FAIL, BLOCKED, SKIP = "ok", "attention", "fail", "blocked", "skip"
TERMINAL_GOOD = (OK, ATTENTION)     # outcomes that satisfy a run_key


class Result(object):
    __slots__ = ("status", "summary", "detail")

    def __init__(self, status, summary, detail=None):
        self.status, self.summary, self.detail = status, summary, (detail or {})


class DutyError(Exception):
    """Raised by Ctx guards. Treated as a duty failure, never as an engine crash."""


# ------------------------------------------------------------------ registry
_REGISTRY = {}


def duty(name, interval_s, risk="R0", timeout_s=120, description=""):
    """Register a duty. `interval_s` is both the cadence and the idempotency window:
    two invocations inside one window share a run_key, so the second is a no-op."""
    def wrap(fn):
        if name in _REGISTRY:
            raise ValueError("duplicate duty name: %s" % name)
        if risk not in ("R0", "R1", "R2", "R3"):
            raise ValueError("bad risk class %r for duty %s" % (risk, name))
        fn.duty_name, fn.interval_s, fn.risk = name, interval_s, risk
        fn.timeout_s, fn.description = timeout_s, (description or fn.__doc__ or "").strip()
        _REGISTRY[name] = fn
        return fn
    return wrap


def registry():
    return dict(_REGISTRY)


# ------------------------------------------------------------------ storage
def _connect():
    d = os.path.dirname(DB_PATH)
    if d and not os.path.isdir(d):
        os.makedirs(d, mode=0o700)
    c = sqlite3.connect(DB_PATH, timeout=30)
    c.row_factory = sqlite3.Row
    c.execute("PRAGMA journal_mode=WAL")     # survives an abrupt kill mid-write
    c.execute("PRAGMA synchronous=FULL")
    return c


def init_db(conn=None):
    c = conn or _connect()
    try:
        c.execute("""CREATE TABLE IF NOT EXISTS duties(
            name TEXT PRIMARY KEY, interval_s INTEGER NOT NULL, risk TEXT NOT NULL,
            enabled INTEGER NOT NULL DEFAULT 1, next_due REAL NOT NULL DEFAULT 0,
            last_run REAL, last_status TEXT, last_summary TEXT,
            consec_fail INTEGER NOT NULL DEFAULT 0, attempt INTEGER NOT NULL DEFAULT 0)""")
        c.execute("""CREATE TABLE IF NOT EXISTS runs(
            id INTEGER PRIMARY KEY AUTOINCREMENT, duty TEXT NOT NULL,
            run_key TEXT NOT NULL, attempt INTEGER NOT NULL, status TEXT NOT NULL,
            summary TEXT, detail TEXT, started REAL NOT NULL, finished REAL,
            holder TEXT NOT NULL)""")
        # Duplicate prevention enforced by the DATABASE, not by a code path that can
        # be skipped: at most one satisfying run may exist per (duty, window).
        c.execute("""CREATE UNIQUE INDEX IF NOT EXISTS ux_runs_key ON runs(duty, run_key)
                     WHERE status IN ('ok','attention')""")
        c.execute("CREATE INDEX IF NOT EXISTS ix_runs_duty ON runs(duty, started)")
        c.execute("""CREATE TABLE IF NOT EXISTS findings(
            key TEXT PRIMARY KEY, duty TEXT NOT NULL, severity TEXT NOT NULL,
            summary TEXT NOT NULL, detail TEXT, first_seen REAL NOT NULL,
            last_seen REAL NOT NULL, count INTEGER NOT NULL DEFAULT 1,
            status TEXT NOT NULL DEFAULT 'open', resolved_at REAL)""")
        c.execute("CREATE INDEX IF NOT EXISTS ix_find_status ON findings(status, severity)")
        c.execute("""CREATE TABLE IF NOT EXISTS events(
            id INTEGER PRIMARY KEY AUTOINCREMENT, ts REAL NOT NULL, kind TEXT NOT NULL,
            duty TEXT, msg TEXT, detail TEXT)""")
        c.execute("CREATE INDEX IF NOT EXISTS ix_events_ts ON events(ts)")
        c.execute("CREATE TABLE IF NOT EXISTS state(k TEXT PRIMARY KEY, v TEXT NOT NULL)")
        c.execute("""CREATE TABLE IF NOT EXISTS lease(
            id INTEGER PRIMARY KEY CHECK(id=1), holder TEXT NOT NULL,
            expires_at REAL NOT NULL)""")
        c.commit()
    finally:
        if conn is None:
            c.close()


def _state_get(c, k, default=None):
    row = c.execute("SELECT v FROM state WHERE k=?", (k,)).fetchone()
    return json.loads(row["v"]) if row else default


def _state_set(c, k, v):
    c.execute("INSERT INTO state(k,v) VALUES(?,?) ON CONFLICT(k) DO UPDATE SET v=excluded.v",
              (k, json.dumps(v)))


def _event(c, kind, msg, duty_name=None, **detail):
    c.execute("INSERT INTO events(ts,kind,duty,msg,detail) VALUES(?,?,?,?,?)",
              (time.time(), kind, duty_name, msg, json.dumps(detail, default=str)))


# ------------------------------------------------------------------ lease
def acquire_lease(c, now=None):
    """Single-operator guarantee, same shape as the proven poller lease in app.py:
    the lease carries an EXPIRY, so a process that dies holding it is reclaimed
    automatically. A crash can never permanently stop operations."""
    now = time.time() if now is None else now
    row = c.execute("SELECT holder, expires_at FROM lease WHERE id=1").fetchone()
    if row is None:
        try:
            c.execute("INSERT INTO lease(id,holder,expires_at) VALUES(1,?,?)",
                      (HOLDER, now + LEASE_TTL_S))
            c.commit()
            return True
        except sqlite3.IntegrityError:
            row = c.execute("SELECT holder, expires_at FROM lease WHERE id=1").fetchone()
    # Take it only if it is ours already or has expired. The UPDATE's WHERE clause is
    # the atomic decision point; a racing process either loses it or re-reads.
    c.execute("UPDATE lease SET holder=?, expires_at=? WHERE id=1 AND (holder=? OR expires_at<=?)",
              (HOLDER, now + LEASE_TTL_S, HOLDER, now))
    c.commit()
    got = c.execute("SELECT holder FROM lease WHERE id=1").fetchone()["holder"]
    return got == HOLDER


def release_lease(c):
    c.execute("UPDATE lease SET expires_at=0 WHERE id=1 AND holder=?", (HOLDER,))
    c.commit()


# ------------------------------------------------------------------ context
class Ctx(object):
    """What a duty is allowed to do. Deliberately small: read the repo, run bounded
    read-only commands, fetch public HTTP, checkpoint, and report. There is no write
    helper — a duty that needs to change something must be R1+ and do it explicitly.

    Honest boundary: these guards make the shared path safe and make a boundary
    violation obvious in review. They are NOT a sandbox — a duty is trusted code and
    could import os and do anything. The guards exist so that crossing the line has
    to be deliberate and visible in a diff, which is the property that actually
    survives contact with a hurried future change."""

    def __init__(self, c, duty_name, run_key, deadline):
        self._c, self.duty = c, duty_name
        self.run_key, self.deadline = run_key, deadline
        self.repo = REPO
        self._findings = []
        self._log = []

    # -- guards ---------------------------------------------------------------
    def _check_deadline(self):
        """Bounds the duty's I/O, not arbitrary CPU — stated plainly rather than
        implied, because a timeout that only sometimes applies is worse than a
        documented one. Every capability below checks it before acting."""
        if time.time() > self.deadline:
            raise DutyError("duty exceeded its time budget")

    @staticmethod
    def _vet(argv):
        if not isinstance(argv, (list, tuple)) or not argv:
            raise DutyError("run() takes a non-empty argv list, never a shell string")
        binname = os.path.basename(str(argv[0]))
        if binname in _FORBIDDEN_BIN:
            raise DutyError("refusing %r: the Operator never reaches production" % binname)
        if binname == "git":
            sub = next((a for a in argv[1:] if not a.startswith("-")), "")
            if sub in _FORBIDDEN_GIT:
                raise DutyError("refusing 'git %s': the Operator never writes to the repo" % sub)
        for a in argv:
            if str(a).endswith("deploy.sh") or str(a).endswith("rollback.sh"):
                raise DutyError("refusing %r: deploying is a human action" % a)

    # -- capabilities ---------------------------------------------------------
    def run(self, argv, timeout=60, cwd=None):
        """Bounded subprocess. argv list only — never a shell string, so there is no
        command-injection surface even if a duty interpolates external text."""
        self._check_deadline()
        self._vet(argv)
        try:
            p = subprocess.run(list(argv), cwd=cwd or REPO, capture_output=True,
                               text=True, timeout=timeout)
        except subprocess.TimeoutExpired:
            raise DutyError("command timed out after %ss: %s" % (timeout, argv[0]))
        except OSError as e:
            raise DutyError("could not run %s: %s" % (argv[0], e))
        return p.returncode, p.stdout.strip(), p.stderr.strip()

    def http(self, url, timeout=20):
        """Public HTTP GET. Returns (status, body). Never raises on a bad response —
        a duty decides what a non-200 means; the engine does not guess for it."""
        self._check_deadline()
        if not url.startswith("https://"):
            raise DutyError("refusing non-HTTPS url: %s" % url)
        req = urllib.request.Request(url, headers={"User-Agent": "SeatWatch-Operator/1.0"})
        try:
            with urllib.request.urlopen(req, timeout=timeout) as r:
                return r.status, r.read().decode("utf-8", "replace")
        except urllib.error.HTTPError as e:
            return e.code, ""
        except Exception as e:
            raise DutyError("fetch failed for %s: %s" % (url, e))

    def read(self, relpath, limit=200000):
        """Read a repo file. Confined to the repo tree — a duty cannot wander."""
        self._check_deadline()
        full = os.path.realpath(os.path.join(REPO, relpath))
        if not (full == REPO or full.startswith(REPO + os.sep)):
            raise DutyError("refusing to read outside the repo: %s" % relpath)
        with open(full, "r", errors="replace") as f:
            return f.read(limit)

    def log(self, msg):
        self._log.append(msg)

    # -- durable partial progress --------------------------------------------
    def checkpoint(self, **kv):
        """Persist partial progress immediately. A duty that dies mid-way resumes
        from here instead of restarting, so long work is never lost to a crash."""
        cur = self.resume()
        cur.update(kv)
        _state_set(self._c, "ckpt:%s:%s" % (self.duty, self.run_key), cur)
        self._c.commit()
        return cur

    def resume(self):
        return _state_get(self._c, "ckpt:%s:%s" % (self.duty, self.run_key), {}) or {}

    def last_detail(self):
        """The detail this duty recorded on its previous successful run, or {}.

        This is the whole reason the Operator has a database. An unattended check
        that starts blank every time can see a threshold breach but never a TREND —
        it cannot say "this number moved". Comparing against the last run is what
        turns a point-in-time probe into drift detection."""
        # 'superseded' counts: it marks a completed observation that a forced re-run
        # replaced, not a failed one. Excluding it would blind drift detection exactly
        # when someone is actively re-running the duty to investigate that drift.
        row = self._c.execute(
            "SELECT detail FROM runs WHERE duty=? AND status IN ('ok','attention',"
            "'superseded') AND finished IS NOT NULL ORDER BY finished DESC LIMIT 1",
            (self.duty,)).fetchone()
        if not row or not row["detail"]:
            return {}
        try:
            return json.loads(row["detail"])
        except ValueError:
            return {}

    # -- findings -------------------------------------------------------------
    def finding(self, key, severity, summary, **detail):
        """Record a condition that a human should know about. Findings are deduped by
        key and auto-resolve when a later successful run stops raising them, so the
        open set is always the CURRENT state — never an append-only pile of history."""
        if severity not in ("red", "yellow", "info"):
            raise DutyError("bad severity %r" % severity)
        self._findings.append({"key": "%s:%s" % (self.duty, key), "severity": severity,
                               "summary": summary, "detail": detail})
        return self

    # -- outcomes -------------------------------------------------------------
    def ok(self, summary, **detail):
        return Result(OK, summary, detail)

    def attention(self, summary, **detail):
        """Ran fine; found something worth a human's attention. Distinct from `fail`,
        which means the check itself could not be completed."""
        return Result(ATTENTION, summary, detail)

    def fail(self, summary, **detail):
        return Result(FAIL, summary, detail)

    def blocked(self, summary, **detail):
        """Cannot proceed without a human or a permission this lane does not hold.
        Not retried — retrying a permissions wall just burns budget."""
        return Result(BLOCKED, summary, detail)

    def skip(self, summary, **detail):
        return Result(SKIP, summary, detail)


# ------------------------------------------------------------------ engine
def _run_key(duty_name, interval_s, now):
    """Idempotency window. Two invocations inside the same window produce the same
    key, so the second one is recognised as already-done rather than re-executed."""
    win = int(now // max(1, interval_s))
    return "%s/%d" % (duty_name, win)


def _backoff(attempt):
    return min(BACKOFF_CAP_S, BACKOFF_BASE_S * (2 ** max(0, attempt - 1)))


def sync_registry(c, now=None):
    """Registered duties become rows. Cadence/risk changes in code take effect; the
    row's runtime state (attempts, next_due) is preserved across restarts."""
    now = time.time() if now is None else now
    for name, fn in _REGISTRY.items():
        row = c.execute("SELECT name FROM duties WHERE name=?", (name,)).fetchone()
        if row:
            c.execute("UPDATE duties SET interval_s=?, risk=? WHERE name=?",
                      (fn.interval_s, fn.risk, name))
        else:
            c.execute("INSERT INTO duties(name,interval_s,risk,next_due) VALUES(?,?,?,?)",
                      (name, fn.interval_s, fn.risk, now))
    c.commit()


def sweep_crashed(c, now=None):
    """A `running` row means a previous process died mid-duty. Surface it rather than
    letting it vanish, and free the duty to run again. Mirrors the Guardian's
    crash-before-finalize detector, which exists because that failure was real."""
    now = time.time() if now is None else now
    rows = c.execute("SELECT * FROM runs WHERE status='running'").fetchall()
    for r in rows:
        c.execute("UPDATE runs SET status='crashed', finished=?, summary=? WHERE id=?",
                  (now, "process died mid-duty; evidence preserved", r["id"]))
        _upsert_finding(c, {"key": "operator:crashed:%s" % r["duty"], "severity": "yellow",
                            "summary": "duty %r died mid-run (run %d) — it was retried, but "
                                       "a repeat means the duty itself is unsafe"
                                       % (r["duty"], r["id"]),
                            "detail": {"run_id": r["id"], "holder": r["holder"],
                                       "started": r["started"]}},
                       r["duty"], now)
        _event(c, "crash_recovered", "recovered crashed run %d" % r["id"], r["duty"])
    if rows:
        c.commit()
    return len(rows)


def _upsert_finding(c, f, duty_name, now):
    c.execute("""INSERT INTO findings(key,duty,severity,summary,detail,first_seen,last_seen,
                 count,status) VALUES(?,?,?,?,?,?,?,1,'open')
                 ON CONFLICT(key) DO UPDATE SET
                   severity=excluded.severity, summary=excluded.summary,
                   detail=excluded.detail, last_seen=excluded.last_seen,
                   count=findings.count+1, status='open', resolved_at=NULL""",
              (f["key"], duty_name, f["severity"], f["summary"],
               json.dumps(f.get("detail", {}), default=str), now, now))


def _reconcile_findings(c, duty_name, raised, now):
    """Anything this duty previously reported and no longer reports is resolved.
    Only called after a duty actually COMPLETED — invariant 6. A failed duty proves
    nothing about the conditions it was supposed to check."""
    keys = set(f["key"] for f in raised)
    for f in raised:
        _upsert_finding(c, f, duty_name, now)
    open_rows = c.execute("SELECT key FROM findings WHERE duty=? AND status='open'",
                          (duty_name,)).fetchall()
    for row in open_rows:
        if row["key"] not in keys and not row["key"].startswith("operator:"):
            c.execute("UPDATE findings SET status='resolved', resolved_at=? WHERE key=?",
                      (now, row["key"]))
            _event(c, "finding_resolved", "no longer present: %s" % row["key"], duty_name)


def execute_duty(c, name, now=None, force=False):
    """Run one duty through the full lifecycle. Returns the recorded status string.
    Never raises: an engine that dies on one bad duty is not an operator."""
    now = time.time() if now is None else now
    fn = _REGISTRY.get(name)
    if fn is None:
        return SKIP
    row = c.execute("SELECT * FROM duties WHERE name=?", (name,)).fetchone()
    key = _run_key(name, fn.interval_s, now)

    # invariant 3 — the risk gate is checked BEFORE any work happens
    if fn.risk not in AUTO_RISK:
        _event(c, "needs_approval", "duty %r is %s — not auto-executed" % (name, fn.risk), name)
        _upsert_finding(c, {"key": "operator:needs_approval:%s" % name, "severity": "info",
                            "summary": "duty %r is risk %s and requires a human to authorise "
                                       "each run; the Operator will never execute it"
                                       % (name, fn.risk),
                            "detail": {"risk": fn.risk}}, name, now)
        c.execute("UPDATE duties SET last_status='needs_approval', next_due=? WHERE name=?",
                  (now + fn.interval_s, name))
        c.commit()
        return "needs_approval"

    # idempotency — a satisfying run already exists for this window
    done = c.execute("SELECT id, status FROM runs WHERE duty=? AND run_key=? "
                     "AND status IN ('ok','attention')", (name, key)).fetchone()
    if done and not force:
        _event(c, "skipped_duplicate", "run_key %s already satisfied by run %d"
               % (key, done["id"]), name)
        c.execute("UPDATE duties SET next_due=? WHERE name=?", (now + fn.interval_s, name))
        c.commit()
        return SKIP
    if done and force:
        # Forcing is a deliberate re-run, so the earlier result is SUPERSEDED rather
        # than deleted or duplicated: the unique index keeps holding (one satisfying
        # run per window), and the old row survives as evidence of what it said.
        c.execute("UPDATE runs SET status='superseded' WHERE duty=? AND run_key=? "
                  "AND status IN ('ok','attention')", (name, key))
        _event(c, "superseded", "forced re-run supersedes run %d for %s"
               % (done["id"], key), name)
        c.commit()

    attempt = (row["attempt"] if row else 0) + 1
    # invariant 4 — evidence before claim: the row exists before the work does
    cur = c.execute("INSERT INTO runs(duty,run_key,attempt,status,started,holder) "
                    "VALUES(?,?,?,'running',?,?)", (name, key, attempt, now, HOLDER))
    run_id = cur.lastrowid
    c.commit()

    ctx = Ctx(c, name, key, deadline=now + fn.timeout_s)
    try:
        res = fn(ctx)
        if not isinstance(res, Result):
            res = Result(FAIL, "duty returned %s, not a Result" % type(res).__name__)
    except DutyError as e:
        res = Result(FAIL, str(e))
    except Exception as e:                      # a broken duty must not stop the engine
        res = Result(FAIL, "%s: %s" % (type(e).__name__, e))

    fin = time.time()
    detail = dict(res.detail)
    if ctx._log:
        detail["log"] = ctx._log[-50:]
    try:
        _persist(c, run_id, name, row, fn, ctx, res, detail, attempt, fin)
    except Exception as e:
        # Recording the outcome must never take the engine down. The run row stays
        # `running`, which the next start's crash sweep will surface — a visible
        # anomaly is strictly better than a lost one.
        c.rollback()
        _event(c, "persist_failed", "could not record %s outcome: %s: %s"
               % (name, type(e).__name__, e), name)
        _upsert_finding(c, {"key": "operator:persist_failed:%s" % name, "severity": "red",
                            "summary": "the Operator could not record the outcome of %r "
                                       "(%s) — its reports about this duty cannot be "
                                       "trusted until this is fixed"
                                       % (name, type(e).__name__),
                            "detail": {"error": str(e)}}, name, fin)
        c.commit()
        return FAIL

    _event(c, "run", "%s -> %s: %s" % (name, res.status, res.summary), name,
           run_id=run_id, ms=int((fin - now) * 1000))
    c.commit()
    return res.status


def _persist(c, run_id, name, row, fn, ctx, res, detail, attempt, fin):
    """Write the outcome and advance the duty's schedule. One transaction: the run
    row, its findings, and the next-due time either all land or none do."""
    c.execute("UPDATE runs SET status=?, summary=?, detail=?, finished=? WHERE id=?",
              (res.status, res.summary, json.dumps(detail, default=str), fin, run_id))

    if res.status in TERMINAL_GOOD:
        _reconcile_findings(c, name, ctx._findings, fin)
        c.execute("DELETE FROM state WHERE k=?", ("ckpt:%s:%s" % (name, ctx.run_key),))
        c.execute("UPDATE duties SET last_run=?, last_status=?, last_summary=?, "
                  "consec_fail=0, attempt=0, next_due=? WHERE name=?",
                  (fin, res.status, res.summary, fin + fn.interval_s, name))
    elif res.status == BLOCKED:
        _upsert_finding(c, {"key": "operator:blocked:%s" % name, "severity": "yellow",
                            "summary": "duty %r is blocked: %s" % (name, res.summary),
                            "detail": detail}, name, fin)
        c.execute("UPDATE duties SET last_run=?, last_status=?, last_summary=?, "
                  "attempt=0, next_due=? WHERE name=?",
                  (fin, res.status, res.summary, fin + fn.interval_s, name))
    elif res.status == SKIP:
        c.execute("UPDATE duties SET last_run=?, last_status=?, last_summary=?, "
                  "attempt=0, next_due=? WHERE name=?",
                  (fin, res.status, res.summary, fin + fn.interval_s, name))
    else:                                        # FAIL — bounded retry, then give up loudly
        consec = (row["consec_fail"] if row else 0) + 1
        if attempt < MAX_ATTEMPTS:
            nxt, keep = fin + _backoff(attempt), attempt
            _event(c, "retry_scheduled", "attempt %d/%d failed: %s"
                   % (attempt, MAX_ATTEMPTS, res.summary), name, next_in_s=int(nxt - fin))
        else:
            nxt, keep = fin + fn.interval_s, 0   # window closed; try fresh next cadence
            _upsert_finding(c, {"key": "operator:exhausted:%s" % name, "severity": "red",
                                "summary": "duty %r failed %d consecutive attempts and was "
                                           "given up on: %s" % (name, MAX_ATTEMPTS, res.summary),
                                "detail": detail}, name, fin)
        c.execute("UPDATE duties SET last_run=?, last_status=?, last_summary=?, "
                  "consec_fail=?, attempt=?, next_due=? WHERE name=?",
                  (fin, res.status, res.summary, consec, keep, nxt, name))


def run_once(c, only=None, force=False, now=None):
    """One operator cycle: read state, pick what is due, execute, record, repeat until
    nothing is due or a budget is reached. Bounded by construction — invariant 5."""
    now = time.time() if now is None else now
    sync_registry(c, now)
    recovered = sweep_crashed(c, now)
    started, counts, ran = now, {}, []

    while True:
        if len(ran) >= CYCLE_DUTY_CAP:
            _event(c, "budget", "stopped after %d duties (per-cycle cap)" % len(ran))
            break
        if time.time() - started > CYCLE_BUDGET_S:
            _event(c, "budget", "stopped after %ds (wall-clock budget)" % CYCLE_BUDGET_S)
            break
        # `--only` filters here, in the query. It must never touch another duty's
        # schedule: an operator that silently postpones the checks you did not ask
        # for is worse than one that does nothing.
        where = ["enabled=1"]
        params = []
        if not force:                       # force means "run now", schedule included
            where.append("next_due<=?")
            params.append(time.time())
        if only:
            where.append("name=?")
            params.append(only)
        if ran:
            where.append("name NOT IN (%s)" % ",".join("?" * len(ran)))
            params.extend(ran)
        row = c.execute("SELECT name FROM duties WHERE %s ORDER BY next_due LIMIT 1"
                        % " AND ".join(where), params).fetchone()
        if row is None:
            break
        name = row["name"]
        st = execute_duty(c, name, force=force)
        counts[st] = counts.get(st, 0) + 1
        ran.append(name)

    # The heartbeat is the point: it converts "we heard nothing" from a comfort into
    # a checkable fact. A monitor that sees a stale heartbeat knows the Operator is
    # down, which silence alone could never tell it.
    _state_set(c, "heartbeat", {"at": time.time(), "holder": HOLDER,
                                "duties": len(ran), "counts": counts,
                                "recovered": recovered})
    c.execute("DELETE FROM events WHERE ts < ?", (time.time() - EVENT_RETENTION_S,))
    _event(c, "cycle", "cycle complete: %d duties, %s" % (len(ran), counts or "nothing due"))
    c.commit()
    return {"duties_run": len(ran), "counts": counts, "recovered": recovered}


# ------------------------------------------------------------------ reporting
def status_report(c):
    hb = _state_get(c, "heartbeat") or {}
    age = (time.time() - hb["at"]) if hb.get("at") else None
    findings = [dict(r) for r in c.execute(
        "SELECT key,duty,severity,summary,first_seen,last_seen,count FROM findings "
        "WHERE status='open' ORDER BY CASE severity WHEN 'red' THEN 0 WHEN 'yellow' "
        "THEN 1 ELSE 2 END, last_seen DESC")]
    duties = [dict(r) for r in c.execute(
        "SELECT name,risk,last_status,last_summary,last_run,next_due,consec_fail "
        "FROM duties ORDER BY name")]
    return {"heartbeat_age_s": age, "heartbeat": hb,
            "open_findings": findings, "duties": duties}


def _fmt_age(s):
    if s is None:
        return "never"
    if s < 90:
        return "%ds ago" % int(s)
    if s < 5400:
        return "%dm ago" % int(s / 60)
    if s < 172800:
        return "%.1fh ago" % (s / 3600.0)
    return "%.1fd ago" % (s / 86400.0)


def print_status(rep):
    hb_age = rep["heartbeat_age_s"]
    print("\nSeatWatch Operator")
    print("=" * 72)
    if hb_age is None:
        print("  heartbeat : NEVER RUN — the Operator has not completed a cycle")
    else:
        stale = " <-- STALE" if hb_age > 6 * 3600 else ""
        print("  heartbeat : %s%s" % (_fmt_age(hb_age), stale))
    print("  duties    : %d registered" % len(rep["duties"]))
    reds = [f for f in rep["open_findings"] if f["severity"] == "red"]
    yels = [f for f in rep["open_findings"] if f["severity"] == "yellow"]
    print("  findings  : %d open (%d red, %d yellow)"
          % (len(rep["open_findings"]), len(reds), len(yels)))
    if rep["open_findings"]:
        print("\n  OPEN FINDINGS")
        for f in rep["open_findings"]:
            print("   [%-6s] %s" % (f["severity"], f["summary"]))
            print("            %s · first seen %s · seen %dx"
                  % (f["key"], _fmt_age(time.time() - f["first_seen"]), f["count"]))
    print("\n  DUTIES")
    for d in rep["duties"]:
        print("   %-22s %-14s %-5s last %s"
              % (d["name"], d["last_status"] or "never", d["risk"],
                 _fmt_age(time.time() - d["last_run"] if d["last_run"] else None)))
        if d["last_summary"]:
            print("      %s" % d["last_summary"])
    print("=" * 72 + "\n")


# ------------------------------------------------------------------ cli
def main(argv=None):
    ap = argparse.ArgumentParser(description="SeatWatch Operator")
    ap.add_argument("command", choices=["once", "loop", "status", "list"])
    ap.add_argument("--only", help="run just this duty")
    ap.add_argument("--force", action="store_true", help="ignore the idempotency window")
    ap.add_argument("--interval", type=int, default=300, help="loop: seconds between cycles")
    ap.add_argument("--max-cycles", type=int, default=0, help="loop: stop after N cycles")
    ap.add_argument("--json", action="store_true")
    a = ap.parse_args(argv)

    import duties as _duties          # noqa: F401  (registers duties via decorator)
    init_db()
    c = _connect()
    try:
        if a.command == "status":
            rep = status_report(c)
            if a.json:
                print(json.dumps(rep, indent=2, default=str))
            else:
                print_status(rep)
            return 1 if any(f["severity"] == "red" for f in rep["open_findings"]) else 0

        if a.command == "list":
            sync_registry(c)
            for name, fn in sorted(_REGISTRY.items()):
                print("%-22s %-4s every %-7s %s"
                      % (name, fn.risk, "%ds" % fn.interval_s, fn.description.splitlines()[0]))
            return 0

        if not acquire_lease(c):
            print("another Operator holds the lease — standing down (this is correct).")
            return 0
        try:
            if a.command == "once":
                out = run_once(c, only=a.only, force=a.force)
                if a.json:
                    print(json.dumps(out, default=str))
                else:
                    print_status(status_report(c))
                return 0
            cycles = 0
            while True:
                if not acquire_lease(c):
                    print("lost the lease — standing down.")
                    return 0
                run_once(c, only=a.only, force=a.force)
                cycles += 1
                if a.max_cycles and cycles >= a.max_cycles:
                    return 0
                time.sleep(a.interval)
        finally:
            release_lease(c)
    finally:
        c.close()


if __name__ == "__main__":
    import sys
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    # Re-enter through the module's real name before doing anything. Run directly,
    # this file is `__main__`, while duties.py imports `operator_engine` — two copies
    # of the module, two separate registries, and every duty registers into the one
    # the CLI is not looking at. Delegating makes both sides the same module object.
    from operator_engine import main as _main
    raise SystemExit(_main())
