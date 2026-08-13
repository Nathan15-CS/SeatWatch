"""READINESS #25 — a correct alert repeated eight times is still a bug.

On 2026-08-13 watch 27 (CMSC216 0102, the most contested course at UMD) produced EIGHT
emails in one hour. Every one was CORRECT: guardian_watch_results shows 8 alert_delivered
against 8 checked_closed_reset, so each followed a real closed->open transition the poller
observed. Add/drop churn opened and refilled the seat within seconds.

SMS sent exactly one, because SMS has a one-text-per-watch rule built when texts cost
money. Email, the channel the entire free tier runs on, had no equivalent. So the protected
channel was the paid one and the unprotected channel was the one everybody uses.

Eight mails about a class they cannot get into is how a beta student unsubscribes on day
one — and then never hears about the seat they WOULD have got. A correct alert that drives
someone away is worse than no alert.

Each check below fails against the pre-fix code:

  STORM        8 transitions in an hour on one watch -> 1 immediate + at most 1 per window
  LATENCY      the FIRST alert is never delayed; speed is the product
  RETRY        an alert that reached NOBODY still retries every cycle — the cooldown gates
               on a previous DELIVERY, not on elapsed time, or it would resurrect the
               silent-failure class closed last week
  ISOLATION    a storm on watch A never delays watch B, another course, another student
  LATCH        a suppressed repeat counts as delivered, so it does not retry forever and
               does not page the operator about a student who WAS emailed
"""
import os
import sys
import tempfile
import time
import warnings

warnings.filterwarnings("ignore")


def run():
    os.environ["SEATWATCH_DB"] = os.path.join(tempfile.mkdtemp(), "storm.db")
    sys.path.insert(0, os.path.expanduser("~/seatwatch"))
    import app
    app.init_db()

    results = []
    def check(n, c, d=""): results.append((n, bool(c), d))

    sent, paged = [], []
    app.EMAIL_ENABLED = True
    app.send_email = lambda to, subj, body, url=None: (sent.append((to, subj)) or True)
    app.send_sms = lambda *a, **k: False
    app.operator_alert = lambda m: paged.append(m)

    with app.db() as c:
        c.execute("INSERT INTO users(google_sub,email,topic,created,notify_email,notify_sms) "
                  "VALUES('g_s','storm@umd.edu','t_s',?,1,0)", (time.time(),))
        uid = c.execute("SELECT id FROM users WHERE google_sub='g_s'").fetchone()["id"]
        for course, sec in (("CMSC216", "0102"), ("CMSC132", "0201")):
            c.execute("INSERT INTO watches(school,topic,course,section,term,created,user_id) "
                      "VALUES('umd','t_s',?,?,'202608',?,?)", (course, sec, time.time(), uid))
        wa = c.execute("SELECT * FROM watches WHERE course='CMSC216'").fetchone()
        wb = c.execute("SELECT * FROM watches WHERE course='CMSC132'").fetchone()

    # ------------------------------------------------------- first alert, immediate
    t0 = time.time()
    ok = app._alert(wa, "A seat opened in CMSC216 0102.", "https://umd.edu/x")
    first_latency = time.time() - t0
    check("the FIRST alert fires immediately", ok and len(sent) == 1,
          f"sent {len(sent)} — a debounce here would cost every student ~40s on the alert "
          f"that actually matters")
    check("...with no added latency", first_latency < 1.0, f"{first_latency:.2f}s")

    # -------------------------------------------------------------------- the storm
    for _ in range(7):
        app._alert(wa, "A seat opened in CMSC216 0102.", "https://umd.edu/x")
    check("7 more real transitions do NOT produce 7 more emails", len(sent) == 1,
          f"sent {len(sent)} — this is the exact shape of the 8-email hour on watch 27")

    # ------------------------------------------------------------------- isolation
    before = len(sent)
    ok_b = app._alert(wb, "A seat opened in CMSC132 0201.", "https://umd.edu/y")
    check("a DIFFERENT watch alerts immediately during the storm", ok_b and len(sent) == before + 1,
          "the cooldown is per watch; suppressing across courses would hide real seats")

    # ----------------------------------------------------------------------- latch
    check("a suppressed repeat reports DELIVERED", app._alert(wa, "again", "https://umd.edu/x"),
          "returning False would retry every 20s forever AND page the operator about a "
          "student who was emailed minutes ago")
    check("...and pages nobody", not paged, f"paged {len(paged)}x: {paged[:1]}")

    # ----------------------------------------------------------------------- retry
    # An alert that reached NOBODY leaves no ledger row, so the delivery retry must still
    # run. This is the case that separates "gate on a previous DELIVERY" from "gate on time".
    with app.db() as c:
        c.execute("INSERT INTO watches(school,topic,course,section,term,created,user_id) "
                  "VALUES('umd','t_s','MATH140','0301','202608',?,?)", (time.time(), uid))
        wc = c.execute("SELECT * FROM watches WHERE course='MATH140'").fetchone()
    app.send_email = lambda *a, **k: False            # every channel down
    n_before = len(paged)
    r1 = app._alert(wc, "seat", "https://umd.edu/z")
    r2 = app._alert(wc, "seat", "https://umd.edu/z")
    check("an alert that reached NOBODY does not latch", not r1 and not r2,
          "it must keep retrying until a channel works")
    check("...and the operator IS told once", len(paged) == n_before + 1,
          f"paged {len(paged) - n_before}x — once, not per cycle")
    app.send_email = lambda to, subj, body, url=None: (sent.append((to, subj)) or True)
    n = len(sent)
    check("...and it delivers the moment a channel recovers",
          app._alert(wc, "seat", "https://umd.edu/z") and len(sent) == n + 1,
          "the cooldown must never have applied to a watch that was never reached")

    # ------------------------------------------------------- the window does expire
    # getattr, not a direct read: against PRE-FIX code the constant does not exist, and a
    # suite that dies on an AttributeError proves only that the attribute is missing. It
    # has to run every assertion so the storm check itself is what fails.
    window = getattr(app, "REPEAT_ALERT_COOLDOWN_S", 1800)
    with app.db() as c:
        c.execute("UPDATE alert_log SET sent_at=? WHERE watch_id=?",
                  (time.time() - window - 60, wa["id"]))
    n = len(sent)
    check("once the window passes, a new opening alerts again",
          app._alert(wa, "seat again", "https://umd.edu/x") and len(sent) == n + 1,
          "a permanent mute would lose every later seat in the term")

    p = sum(ok for _, ok, _ in results)
    f = sum(not ok for _, ok, _ in results)
    return p, f, results


if __name__ == "__main__":
    p, f, res = run()
    for n, ok, d in res:
        print(f"  [{'PASS' if ok else '*** FAIL'}] {n}{('  ' + d) if d and not ok else ''}")
    print(f"\n  {p} passed, {f} failed")
    sys.exit(1 if f else 0)
