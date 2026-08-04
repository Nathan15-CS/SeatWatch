"""READINESS #2 — Crash-safety / no-duplicate-alert across a process restart.

Drives the REAL run_cycle. A systemd restart (Restart=always) wipes in-memory state but
keeps the DB. This proves the DB-backed `alerted` latch + `alert_log` ledger survive that
wipe without re-alerting an already-notified section, and that repeated identical poll
results never double-alert. Returns (passed, failed, details) for readiness.py.
"""
import os, tempfile, sys, time


def run():
    os.environ["SEATWATCH_DB"] = os.path.join(tempfile.mkdtemp(), "t.db")
    sys.path.insert(0, os.path.expanduser("~/seatwatch"))
    import app, schools
    app.init_db()
    results = []
    def check(name, cond, detail=""): results.append((name, bool(cond), detail))

    class FakeSchool:
        id = "canary"; name = "Canary"; example = "CS 101"
        def __init__(self): self._data = {}
        def cur_term(self): return "202608"
        def reg_url(self, c): return "https://x/"
        def fetch(self, courses): return {c: self._data[c] for c in courses if c in self._data}
    fake = FakeSchool(); schools.SCHOOLS = {"canary": fake}

    sent = []
    app.EMAIL_ENABLED = True
    app.sw.notify = lambda *a, **k: True                    # operator channel only
    app.send_email = lambda to, subj, body, url=None, **k: (sent.append(1), True)[1]
    app.send_sms = lambda *a, **k: False

    with app.db() as c:
        c.execute("INSERT INTO users(google_sub,email,topic,created) VALUES('g_cs','cs@b.com','t_cs',0)")
        cur = c.execute("INSERT INTO watches(school,topic,course,section,term,alerted,created,user_id) "
                  "VALUES('canary','t_cs','CS 101','0101','202608',0,0,1)")
        WID = cur.lastrowid

    def restart():
        """Exactly what a systemd restart clears: in-memory state. DB is untouched."""
        app.health.clear()
        for attr in ("_sms_paged", "_undelivered", "_dryrun_logged"):
            obj = getattr(app, attr, None)
            if obj is not None:
                obj.clear()

    fake._data = {"CS 101": {"0101": {"open": True, "seats": 3}}}
    app.run_cycle()
    check("seat opens -> exactly 1 alert", len(sent) == 1)
    with app.db() as c:
        check("watch latched in DB", c.execute("SELECT alerted FROM watches WHERE id=?", (WID,)).fetchone()[0] == 1)

    restart()
    app.run_cycle()
    check("after RESTART, same open seat -> NO duplicate", len(sent) == 1)

    for _ in range(5):
        app.run_cycle()
    check("5 repeated open cycles -> still 1 alert total", len(sent) == 1)

    restart()
    for _ in range(3):
        app.run_cycle()
    check("restart + 3 more cycles -> still 1", len(sent) == 1)

    # ledger durability: an SMS circuit-breaker trip must survive a restart (or a crashing
    # runaway loop could reset its own breaker by restarting)
    with app.db() as c:
        c.execute("INSERT INTO alert_log(channel,cost_cents,sent_at) VALUES('sms_breaker',0,?)", (time.time(),))
    restart()
    with app.db() as c:
        check("alert_log breaker survives restart",
              c.execute("SELECT COUNT(*) FROM alert_log WHERE channel='sms_breaker'").fetchone()[0] == 1)

    p = sum(ok for _, ok, _ in results); f = sum(not ok for _, ok, _ in results)
    return p, f, results


if __name__ == "__main__":
    import warnings; warnings.filterwarnings("ignore")
    p, f, res = run()
    for name, ok, detail in res:
        print(f"  [{'PASS' if ok else '*** FAIL'}] {name}{('  ' + detail) if detail and not ok else ''}")
    print(f"\n  {p} passed, {f} failed")
    sys.exit(1 if f else 0)
