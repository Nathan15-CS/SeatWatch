"""READINESS #5 — Single-poller lease: no duplicate alerts, and a crash never stops polling.

The poller alerts INLINE, so two live processes would each alert for the same seat (a
duplicate text/push = spam = lost trust). This proves the DB lease makes exactly one
process the poller, AND — the more dangerous failure — that a process dying while holding
the lease does NOT permanently stop polling (the lease expires and is reclaimed).
"""
import os, tempfile, sys, time


def run():
    os.environ["SEATWATCH_DB"] = os.path.join(tempfile.mkdtemp(), "t.db")
    sys.path.insert(0, os.path.expanduser("~/seatwatch"))
    import app
    app.init_db()
    results = []
    def check(name, cond, detail=""): results.append((name, bool(cond), detail))

    real_id = app._LEASE_ID

    def as_process(pid, fn=app.acquire_poll_lease):
        """Run a lease call as if from a different process."""
        app._LEASE_ID = pid
        try:
            return fn()
        finally:
            app._LEASE_ID = real_id

    # 1. first start acquires
    check("process A acquires the lease", as_process("A") is True)

    # 2. simultaneous second start is refused (the duplicate-alert case)
    check("process B refused while A's lease is live", as_process("B") is False)

    # 3. A renews freely (its own lease)
    check("A renews its own lease", as_process("A") is True)
    check("B still refused after A renews", as_process("B") is False)

    # 4. A "crashes" holding the lease -> after expiry, B MUST take over.
    #    (A crash that permanently stopped polling is worse than a duplicate.)
    with app.db() as c:
        c.execute("UPDATE poll_lease SET expires_at=? WHERE id=1", (time.time() - 1,))
    check("expired lease (holder died) is reclaimed by B", as_process("B") is True)
    check("A now refused (B owns it)", as_process("A") is False)

    # 5. replacement starts before old stops: only one can hold it
    with app.db() as c:
        c.execute("UPDATE poll_lease SET expires_at=? WHERE id=1", (time.time() - 1,))
    got = [as_process(p) for p in ("C", "D", "E")]
    check("on expiry exactly ONE of 3 racing starts wins", sum(got) == 1, f"got={got}")

    # 6. restart-with-same-DB: a fresh process id takes over after expiry, polling resumes
    with app.db() as c:
        c.execute("UPDATE poll_lease SET expires_at=? WHERE id=1", (time.time() - 1,))
    check("after restart, new process resumes polling", as_process("restarted") is True)

    # 7. the lease never blocks forever: TTL is finite and sane
    check("lease TTL is finite and > one poll interval",
          0 < app.POLL_LEASE_TTL < 3600 and app.POLL_LEASE_TTL > app.POLL_SECONDS)

    # 8. a clean shutdown HANDS THE LEASE BACK. Without this the lease only cleared by
    #    expiry, so every deploy blinded the poller for the full TTL (~181s measured) with
    #    no seat alert able to fire in that window. Restarts are the one moment we fully
    #    control, so paying for them is waste.
    def held_by():
        with app.db() as c:
            r = c.execute("SELECT holder FROM poll_lease WHERE id=1").fetchone()
        return r["holder"] if r else None

    # earlier steps leave the lease owned by a SIMULATED process id, so expire it first
    # or this real process can never take it and the release is a no-op by construction
    with app.db() as c:
        c.execute("UPDATE poll_lease SET expires_at=? WHERE id=1", (time.time() - 1,))
    app.acquire_poll_lease()
    check("lease is held before shutdown", held_by() is not None)
    app.release_poll_lease()
    check("shutdown releases the lease", held_by() is None,
          "successor would stand down for the whole TTL after every deploy")
    check("successor acquires immediately after a release", app.acquire_poll_lease() is True)

    # ...but releasing must never evict a DIFFERENT process that already took over.
    with app.db() as c:
        c.execute("UPDATE poll_lease SET holder='someone-else' WHERE id=1")
    app.release_poll_lease()
    check("release never evicts another process's lease", held_by() == "someone-else",
          "a dying process would knock the live poller off and cause double-polling")

    p = sum(ok for _, ok, _ in results); f = sum(not ok for _, ok, _ in results)
    return p, f, results


if __name__ == "__main__":
    import warnings; warnings.filterwarnings("ignore")
    p, f, res = run()
    for name, ok, detail in res:
        print(f"  [{'PASS' if ok else '*** FAIL'}] {name}{('  ' + detail) if detail and not ok else ''}")
    print(f"\n  {p} passed, {f} failed")
    sys.exit(1 if f else 0)
