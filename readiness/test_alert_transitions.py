"""READINESS #1 — Alert state-transition correctness, driven through the REAL run_cycle.

No mocks of the alert engine: we register a synthetic school whose fetch() we control,
seed a real watch, capture the delivery channels (send nothing), and drive the actual
app.run_cycle() cycle by cycle. Asserts the core promise:

  closed->closed : silent
  closed->open   : EXACTLY ONE alert
  open->open     : silent (latched)
  open->closed   : silent, re-arms
  closed->open   : re-alerts, but ONLY outside the repeat-alert cooldown

Plus the term-roll case (a stale-term watch must NOT fire — the stamping guard).
Returns (passed, failed, details) so readiness.py can aggregate.
"""
import os, tempfile, sys, time

def run():
    os.environ["SEATWATCH_DB"] = os.path.join(tempfile.mkdtemp(), "t.db")
    sys.path.insert(0, os.path.expanduser("~/seatwatch"))
    import app, schools
    app.init_db()

    results = []
    def check(name, cond, detail=""):
        results.append((name, bool(cond), detail))

    # --- controllable synthetic school ---
    class FakeSchool:
        id = "canary"; name = "Canary University"; example = "CS 101"
        def __init__(self): self._data = {}
        def cur_term(self): return "202608"
        def reg_url(self, course): return "https://example.edu/"
        def fetch(self, courses):
            # returns whatever set_state configured, filtered to requested courses
            return {c: self._data[c] for c in courses if c in self._data}
    fake = FakeSchool()
    schools.SCHOOLS = {"canary": fake}

    # Count alerts on EMAIL, the channel students are actually alerted on since push was
    # retired. sw.notify still answers True because operator_alert uses it; if the count
    # were taken there, a cycle that reached no student would look like a delivered alert.
    sent = []
    app.EMAIL_ENABLED = True
    app.sw.notify = lambda *a, **k: True                    # operator channel only
    app.send_email = lambda to, subj, body, url=None, **k: (
        sent.append(("email", subj, body)), True)[1]
    app.send_sms = lambda *a, **k: False
    app.operator_alert = lambda *a, **k: None

    with app.db() as c:
        c.execute("INSERT INTO users(google_sub,email,topic,created) VALUES('g','a@b.com','t',?)",
                  (0,))
        c.execute("INSERT INTO watches(id,school,topic,course,section,term,alerted,created,user_id)"
                  " VALUES(1,'canary','t','CS 101','0101','202608',0,?,1)", (0,))

    def set_state(open_):
        fake._data = {"CS 101": {"0101": {"open": open_, "seats": 5 if open_ else 0}}}
    def cycle():
        before = len(sent)
        app.run_cycle()
        return len(sent) - before

    # closed -> closed : silent
    set_state(False); cycle()
    check("closed->closed silent", cycle() == 0)
    # closed -> open : exactly ONE alert
    set_state(True)
    n = cycle()
    check("closed->open = exactly ONE alert", n == 1, f"got {n}")
    # open -> open : silent (latched)
    check("open->open silent (latched)", cycle() == 0)
    check("open->open silent again", cycle() == 0)
    # open -> closed : silent, re-arms
    set_state(False)
    check("open->closed silent", cycle() == 0)
    # closed -> open again. This is the exact shape of the storm: watch 27 saw eight of
    # these in an hour on 2026-08-13 and sent eight emails. Both halves are asserted, since
    # the contract now has two — silent INSIDE the repeat window, alerting outside it. A
    # test that only checked one half would call either the storm or a permanent mute
    # "correct".
    set_state(True)
    n = cycle()
    check("a re-open INSIDE the cooldown does not re-alert", n == 0,
          f"got {n} — this is how one contested section produced eight emails")

    with app.db() as c:
        c.execute("UPDATE alert_log SET sent_at=? WHERE watch_id=1",
                  (time.time() - getattr(app, "REPEAT_ALERT_COOLDOWN_S", 1800) - 60,))
        c.execute("UPDATE watches SET alerted=0 WHERE id=1")
    set_state(False); cycle()
    set_state(True)
    n = cycle()
    check("...but OUTSIDE it, a genuine new opening still alerts", n == 1,
          f"got {n} — a permanent mute would lose every later seat in the term")

    # --- TERM-ROLL: a stale-term watch must NOT fire (stamping guard) ---
    with app.db() as c:
        c.execute("UPDATE watches SET alerted=0, term='202601' WHERE id=1")  # watch now stale
    fake.cur_term = lambda: "202608"          # school rolled to a different term
    set_state(True)                            # section is OPEN in the new term
    before = len(sent)
    app.run_cycle()
    after = sent[before:]
    # A stale watch must never produce a SEAT alert — that would announce a seat in a
    # semester the student never signed up for. It SHOULD produce exactly one expiry
    # notice, because ending the watch silently is how someone concludes we are broken.
    # Asserted on the message CONTENT rather than on a bare count: counting alone cannot
    # tell "no false alert" from "no warning either", and both used to look identical here.
    seat_alerts = [m for m in after if "seat open" in (m[1] + m[2]).lower()]
    expiry = [m for m in after if "semester" in (m[1] + m[2]).lower()]
    check("stale-term watch does NOT false-alert on roll", not seat_alerts,
          f"fired {len(seat_alerts)} seat alert(s) for the wrong term")
    check("...but the student IS told the watch ended", len(expiry) == 1,
          f"got {len(expiry)} expiry notice(s) — silence here reads as SeatWatch failing")
    app.run_cycle()
    check("...and is not told twice", len(sent[before:]) == len(after),
          "the poller runs every 20s; a repeated notice would be worse than silence")

    passed = sum(1 for _, ok, _ in results if ok)
    failed = sum(1 for _, ok, _ in results if not ok)
    return passed, failed, results


if __name__ == "__main__":
    p, f, details = run()
    for name, ok, detail in details:
        print(f"  [{'PASS' if ok else '*** FAIL'}] {name}" + (f"  ({detail})" if detail and not ok else ""))
    print(f"\n  {p} passed, {f} failed")
    sys.exit(1 if f else 0)
