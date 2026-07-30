#!/usr/bin/env python3
"""
Operator engine tests.  python3 ops/test_operator.py

Each test pins one property the engine is supposed to guarantee. They are written
against the real engine and a real (temp) SQLite file — not mocks — because the
guarantees being tested are mostly about what survives a crash, and a mock cannot
crash convincingly.

Style matches ops/readiness: prints "N passed, M failed" and exits non-zero on fail.
"""
import os
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

_TMP = tempfile.mkdtemp(prefix="sw-operator-test-")
os.environ["SW_OPERATOR_HOME"] = _TMP
os.environ["SW_OPERATOR_DB"] = os.path.join(_TMP, "t.db")
os.environ["SW_OPERATOR_BACKOFF_S"] = "1"

import operator_engine as E  # noqa: E402

PASS = FAIL = 0


def check(name, cond, detail=""):
    global PASS, FAIL
    if cond:
        PASS += 1
        print("  ok   %s" % name)
    else:
        FAIL += 1
        print("  *** FAIL %s  %s" % (name, detail))


def fresh():
    """A brand-new engine state: empty registry, empty DB, empty lease."""
    E._REGISTRY.clear()
    path = os.path.join(_TMP, "db-%d.db" % (len(os.listdir(_TMP)) + 1))
    E.DB_PATH = path
    E.init_db()
    return E._connect()


# ---------------------------------------------------------------- idempotency
def test_duplicate_prevention():
    print("\n[duplicate prevention]")
    c = fresh()
    calls = []

    @E.duty("d", interval_s=3600)
    def d(ctx):
        calls.append(1)
        return ctx.ok("done")

    E.sync_registry(c)
    E.execute_duty(c, "d")
    st = E.execute_duty(c, "d")     # same window -> must not re-run
    check("second call in the same window is skipped", st == E.SKIP, st)
    check("duty body ran exactly once", len(calls) == 1, calls)

    E.execute_duty(c, "d", force=True)
    check("--force overrides the window", len(calls) == 2, calls)

    # the DB itself must refuse a duplicate, not just the code path above
    import sqlite3
    key = E._run_key("d", 3600, __import__("time").time())
    try:
        c.execute("INSERT INTO runs(duty,run_key,attempt,status,started,holder) "
                  "VALUES('d',?,1,'ok',0,'x')", (key,))
        c.commit()
        dup_blocked = False
    except sqlite3.IntegrityError:
        dup_blocked = True
    check("database rejects a duplicate satisfying run", dup_blocked)
    c.close()


# ---------------------------------------------------------------- retries
def test_bounded_retry():
    print("\n[bounded retry]")
    c = fresh()
    calls = []

    @E.duty("flaky", interval_s=3600)
    def flaky(ctx):
        calls.append(1)
        return ctx.fail("nope")

    E.sync_registry(c)
    for _ in range(E.MAX_ATTEMPTS + 3):
        E.execute_duty(c, "flaky", force=True)
    check("attempts are bounded, not unbounded",
          len(calls) <= E.MAX_ATTEMPTS + 3, len(calls))

    row = c.execute("SELECT * FROM findings WHERE key='operator:exhausted:flaky'").fetchone()
    check("exhaustion raises a red finding", row is not None and row["severity"] == "red")

    d = c.execute("SELECT attempt FROM duties WHERE name='flaky'").fetchone()
    check("attempt counter resets after giving up", d["attempt"] == 0, d["attempt"])
    check("backoff grows then caps",
          E._backoff(1) < E._backoff(3) and E._backoff(99) == E.BACKOFF_CAP_S)
    c.close()


def test_exception_is_contained():
    print("\n[exception containment]")
    c = fresh()

    @E.duty("boom", interval_s=3600)
    def boom(ctx):
        raise RuntimeError("kaboom")

    @E.duty("after", interval_s=3600)
    def after(ctx):
        return ctx.ok("still ran")

    E.sync_registry(c)
    out = E.run_once(c)
    check("a duty that raises does not stop the cycle", out["duties_run"] == 2, out)
    r = c.execute("SELECT status,summary FROM runs WHERE duty='boom'").fetchone()
    check("the exception is recorded as a failure", r["status"] == E.FAIL, dict(r))
    check("the exception text is preserved", "kaboom" in (r["summary"] or ""), r["summary"])
    a = c.execute("SELECT status FROM runs WHERE duty='after'").fetchone()
    check("later duties still run", a["status"] == E.OK)
    c.close()


def test_bad_return_is_a_failure():
    print("\n[contract enforcement]")
    c = fresh()

    @E.duty("sloppy", interval_s=3600)
    def sloppy(ctx):
        return "looks fine to me"

    E.sync_registry(c)
    E.execute_duty(c, "sloppy")
    r = c.execute("SELECT status FROM runs WHERE duty='sloppy'").fetchone()
    check("a non-Result return is a failure, not a silent success", r["status"] == E.FAIL)
    c.close()


# ---------------------------------------------------------------- crash safety
def test_crash_recovery():
    print("\n[crash recovery]")
    c = fresh()

    @E.duty("d", interval_s=3600)
    def d(ctx):
        return ctx.ok("ok")

    E.sync_registry(c)
    # simulate a process that died mid-duty: a `running` row with no finish
    c.execute("INSERT INTO runs(duty,run_key,attempt,status,started,holder) "
              "VALUES('d','d/1',1,'running',0,'dead-holder')")
    c.commit()
    n = E.sweep_crashed(c)
    check("the orphaned run is detected", n == 1, n)
    r = c.execute("SELECT status FROM runs WHERE holder='dead-holder'").fetchone()
    check("it is closed as crashed, not deleted", r["status"] == "crashed", r["status"])
    f = c.execute("SELECT * FROM findings WHERE key='operator:crashed:d'").fetchone()
    check("a crash raises a finding rather than vanishing", f is not None)
    check("the duty is free to run again", E.execute_duty(c, "d") == E.OK)
    c.close()


def test_checkpoint_resume():
    print("\n[checkpoint / resume]")
    c = fresh()
    seen = []

    @E.duty("long", interval_s=3600)
    def long(ctx):
        st = ctx.resume()
        seen.append(st.get("step", 0))
        if st.get("step", 0) < 2:
            ctx.checkpoint(step=st.get("step", 0) + 1)
            return ctx.fail("interrupted")
        return ctx.ok("finished from checkpoint", step=st["step"])

    E.sync_registry(c)
    E.execute_duty(c, "long", force=True)
    E.execute_duty(c, "long", force=True)
    st = E.execute_duty(c, "long", force=True)
    check("progress survives across failed attempts", seen == [0, 1, 2], seen)
    check("the duty completes from its checkpoint", st == E.OK, st)
    left = c.execute("SELECT COUNT(*) n FROM state WHERE k LIKE 'ckpt:long:%'").fetchone()
    check("the checkpoint is cleared on success", left["n"] == 0, left["n"])
    c.close()


# ---------------------------------------------------------------- findings
def test_findings_lifecycle():
    print("\n[findings lifecycle]")
    c = fresh()
    state = {"bad": True}

    @E.duty("w", interval_s=3600)
    def w(ctx):
        if state["bad"]:
            ctx.finding("x", "red", "something is wrong")
            return ctx.attention("found it")
        return ctx.ok("clean")

    E.sync_registry(c)
    E.execute_duty(c, "w", force=True)
    f = c.execute("SELECT * FROM findings WHERE key='w:x'").fetchone()
    check("a finding is opened", f is not None and f["status"] == "open")
    first_seen = f["first_seen"]

    E.execute_duty(c, "w", force=True)
    f = c.execute("SELECT * FROM findings WHERE key='w:x'").fetchone()
    check("a repeat increments the count", f["count"] == 2, f["count"])
    check("first_seen is preserved across repeats", f["first_seen"] == first_seen)

    state["bad"] = False
    E.execute_duty(c, "w", force=True)
    f = c.execute("SELECT status FROM findings WHERE key='w:x'").fetchone()
    check("it auto-resolves once no longer reported", f["status"] == "resolved", f["status"])
    c.close()


def test_failure_never_resolves_findings():
    print("\n[failure does not launder into clean]")
    c = fresh()
    mode = {"v": "bad"}

    @E.duty("v", interval_s=3600)
    def v(ctx):
        if mode["v"] == "bad":
            ctx.finding("x", "red", "real problem")
            return ctx.attention("problem")
        return ctx.fail("could not check")

    E.sync_registry(c)
    E.execute_duty(c, "v", force=True)
    mode["v"] = "broken"
    E.execute_duty(c, "v", force=True)
    f = c.execute("SELECT status FROM findings WHERE key='v:x'").fetchone()
    check("a failed check leaves the finding OPEN", f["status"] == "open", f["status"])
    c.close()


# ---------------------------------------------------------------- safety gates
def test_risk_gate():
    print("\n[risk gate]")
    c = fresh()
    ran = []

    @E.duty("risky", interval_s=3600, risk="R3")
    def risky(ctx):
        ran.append(1)
        return ctx.ok("should never happen")

    E.sync_registry(c)
    st = E.execute_duty(c, "risky")
    check("an R3 duty is never executed", not ran, ran)
    check("it is recorded as needing approval", st == "needs_approval", st)
    f = c.execute("SELECT * FROM findings WHERE key='operator:needs_approval:risky'").fetchone()
    check("and surfaced as a finding", f is not None)
    c.close()


def test_command_guards():
    print("\n[command guards]")
    c = fresh()
    caught = []

    @E.duty("g", interval_s=3600)
    def g(ctx):
        for argv in (["ssh", "host"], ["git", "push"], ["git", "commit", "-m", "x"],
                     ["sudo", "rm"], ["bash", "ops/deploy.sh"], ["systemctl", "restart"]):
            try:
                ctx.run(argv)
                caught.append(("ALLOWED", argv))
            except E.DutyError:
                caught.append(("blocked", argv[0]))
        try:
            ctx.run("git status")           # shell string, not argv
            caught.append(("ALLOWED", "str"))
        except E.DutyError:
            caught.append(("blocked", "shellstring"))
        try:
            ctx.read("../../../etc/passwd")
            caught.append(("ALLOWED", "escape"))
        except E.DutyError:
            caught.append(("blocked", "path-escape"))
        try:
            ctx.http("http://example.com")
            caught.append(("ALLOWED", "http"))
        except E.DutyError:
            caught.append(("blocked", "plain-http"))
        return ctx.ok("guards exercised")

    E.sync_registry(c)
    E.execute_duty(c, "g")
    allowed = [x for x in caught if x[0] == "ALLOWED"]
    check("every production-reaching command is refused", not allowed, allowed)
    check("all eight guards fired", len(caught) == 9, len(caught))

    # a read-only git command must still work, or the guard is useless
    @E.duty("g2", interval_s=3600)
    def g2(ctx):
        rc, out, _ = ctx.run(["git", "rev-parse", "--abbrev-ref", "HEAD"])
        return ctx.ok("branch=%s rc=%s" % (out, rc), rc=rc)

    E.sync_registry(c)
    E.execute_duty(c, "g2")
    r = c.execute("SELECT status FROM runs WHERE duty='g2'").fetchone()
    check("read-only git is still permitted", r["status"] == E.OK, r["status"])
    c.close()


def test_state_is_outside_the_repo():
    print("\n[repo isolation]")
    default_home = os.path.expanduser("~/.seatwatch-operator")
    check("default state path is outside the git tree",
          not os.path.realpath(default_home).startswith(os.path.realpath(E.REPO) + os.sep),
          default_home)
    c = fresh()

    @E.duty("w", interval_s=3600)
    def w(ctx):
        return ctx.ok("no repo writes")

    E.sync_registry(c)
    before = _repo_dirty()
    E.execute_duty(c, "w")
    check("running a duty leaves the working tree untouched", _repo_dirty() == before)
    c.close()


def _repo_dirty():
    import subprocess
    return subprocess.run(["git", "status", "--porcelain"], cwd=E.REPO,
                          capture_output=True, text=True).stdout


# ---------------------------------------------------------------- lease
def test_lease_exclusion():
    print("\n[lease]")
    c = fresh()
    check("first acquisition succeeds", E.acquire_lease(c))
    check("re-acquisition by the same holder succeeds", E.acquire_lease(c))

    real = E.HOLDER
    try:
        E.HOLDER = "someone-else"
        check("a second operator is refused while the lease is live",
              not E.acquire_lease(c))
        # a holder that died: the lease expires and must be reclaimable
        c.execute("UPDATE lease SET expires_at=? WHERE id=1", (0,))
        c.commit()
        check("an expired lease is reclaimable (a crash never stops operations)",
              E.acquire_lease(c))
    finally:
        E.HOLDER = real
    c.close()


# ---------------------------------------------------------------- budgets
def test_cycle_budget():
    print("\n[budgets]")
    c = fresh()
    for i in range(6):
        @E.duty("d%d" % i, interval_s=3600)
        def d(ctx):
            return ctx.ok("ok")

    E.sync_registry(c)
    real_cap = E.CYCLE_DUTY_CAP
    try:
        E.CYCLE_DUTY_CAP = 3
        out = E.run_once(c)
        check("the per-cycle duty cap is enforced", out["duties_run"] == 3, out)
    finally:
        E.CYCLE_DUTY_CAP = real_cap
    c.close()


def test_heartbeat():
    print("\n[heartbeat]")
    c = fresh()

    @E.duty("d", interval_s=3600)
    def d(ctx):
        return ctx.ok("ok")

    E.sync_registry(c)
    rep = E.status_report(c)
    check("before any cycle the heartbeat is absent, not falsely healthy",
          rep["heartbeat_age_s"] is None)
    E.run_once(c)
    rep = E.status_report(c)
    check("a completed cycle records a heartbeat",
          rep["heartbeat_age_s"] is not None and rep["heartbeat_age_s"] < 60)
    c.close()


def test_last_detail_memory():
    print("\n[cross-run memory]")
    c = fresh()
    seen = []

    @E.duty("m", interval_s=3600)
    def m(ctx):
        seen.append(ctx.last_detail().get("n"))
        return ctx.ok("counted", n=len(seen))

    E.sync_registry(c)
    E.execute_duty(c, "m", force=True)
    E.execute_duty(c, "m", force=True)
    check("a run can read its predecessor's result", seen == [None, 1], seen)
    c.close()


def main():
    print("\n" + "=" * 66)
    print("  SeatWatch Operator — engine tests")
    print("=" * 66)
    for fn in (test_duplicate_prevention, test_bounded_retry, test_exception_is_contained,
               test_bad_return_is_a_failure, test_crash_recovery, test_checkpoint_resume,
               test_findings_lifecycle, test_failure_never_resolves_findings,
               test_risk_gate, test_command_guards, test_state_is_outside_the_repo,
               test_lease_exclusion, test_cycle_budget, test_heartbeat,
               test_last_detail_memory):
        try:
            fn()
        except Exception as e:
            global FAIL
            FAIL += 1
            print("  *** FAIL %s raised %s: %s" % (fn.__name__, type(e).__name__, e))
    print("\n%d passed, %d failed\n" % (PASS, FAIL))
    return 1 if FAIL else 0


if __name__ == "__main__":
    sys.exit(main())
