"""READINESS #22 — a student must be TOLD when a semester rollover ends their watch.

A watch is bound to the term it was created in. When the school moves to the next
semester, run_cycle skips that watch forever — correctly, because matching a Fall watch
against a same-numbered Spring section would alert about a semester the student never
asked for. But the skip was SILENT. The operator got paged; the student got nothing.

From their side that is indistinguishable from SeatWatch being broken: they set a watch in
August, never hear anything, and conclude the class never opened. It is the same silent
failure as an alert delivered to a channel nobody reads.

This is about to matter far more than it has all year. Roughly 277 schools re-pick their
term on every fetch and will move to Spring 2027 by themselves around October. Every Fall
watch at those schools goes quiet the moment they do.

What is pinned here:
  FIRES        a stranded watch produces exactly one message
  ONCE         a second cycle does not nag, and a third does not either
  HONEST       the message names the class and says to add it again
  SCOPED       watches on the CURRENT term are never touched
  RETRIES      a send failure is NOT stamped, so the one warning is not swallowed
  NO ACCOUNT   a watch with no user is skipped rather than crashing the cycle
"""
import os
import sys
import tempfile
import time
import warnings

warnings.filterwarnings("ignore")


def run():
    os.environ["SEATWATCH_DB"] = os.path.join(tempfile.mkdtemp(), "roll.db")
    sys.path.insert(0, os.path.expanduser("~/seatwatch"))
    import app
    app.init_db()

    results = []
    def check(n, c, d=""): results.append((n, bool(c), d))

    sent = []
    app.EMAIL_ENABLED = True
    app.send_email = lambda to, subj, body, url=None: (sent.append((to, subj, body)) or True)

    with app.db() as c:
        c.execute("INSERT INTO users(google_sub,email,topic,created,notify_email) "
                  "VALUES('g_roll','roll@umd.edu','t_roll',?,1)", (time.time(),))
        uid = c.execute("SELECT id FROM users WHERE google_sub='g_roll'").fetchone()["id"]
        for term, course in (("202608", "CMSC216"), ("202701", "CMSC250")):
            c.execute("INSERT INTO watches(school,topic,course,section,term,created,user_id) "
                      "VALUES('umd','t_roll',?,'0101',?,?,?)",
                      (course, term, time.time(), uid))
        stale = c.execute("SELECT * FROM watches WHERE term='202608'").fetchone()
        current = c.execute("SELECT * FROM watches WHERE term='202701'").fetchone()

    class FakeSchool:
        id, name = "umd", "University of Maryland"

    # ---------------------------------------------------------------- it fires
    ok = app.notify_stranded(stale, FakeSchool(), "202701")
    check("a stranded watch produces a message", ok and len(sent) == 1,
          f"sent {len(sent)} message(s)")
    if sent:
        to, subj, body = sent[0]
        check("...addressed to the student", to == "roll@umd.edu")
        check("...names the class", "CMSC216" in subj or "CMSC216" in body,
              "a warning that does not say WHICH class is nearly useless")
        check("...says the semester changed",
              "semester" in (subj + body).lower())
        check("...tells them what to DO about it",
              "add it again" in body.lower() or "add the class again" in body.lower(),
              "the student must know the watch is re-creatable, not gone forever")
        check("...explains WHY we stopped it rather than just announcing it",
              "reuse" in body.lower() or "never signed up" in body.lower(),
              "otherwise it reads as SeatWatch losing their watch")

    # ------------------------------------------------------------------- once
    again = app.notify_stranded(stale, FakeSchool(), "202701")
    check("a second cycle does NOT send again", (not again) and len(sent) == 1,
          "the poller runs every 20s — nagging would be worse than silence")
    app.notify_stranded(stale, FakeSchool(), "202701")
    check("...nor a third", len(sent) == 1)

    with app.db() as c:
        stamp = c.execute("SELECT stranded_notified_at FROM watches WHERE id=?",
                          (stale["id"],)).fetchone()["stranded_notified_at"]
    check("the send is recorded on the watch", bool(stamp))

    # ----------------------------------------------------------------- scoped
    before = len(sent)
    with app.db() as c:
        cur_row = c.execute("SELECT * FROM watches WHERE id=?", (current["id"],)).fetchone()
    check("a watch on the CURRENT term is untouched by the notifier",
          not cur_row["stranded_notified_at"] and len(sent) == before,
          "only a real term mismatch may end a watch")

    # ---------------------------------------------------------------- retries
    with app.db() as c:
        c.execute("INSERT INTO watches(school,topic,course,section,term,created,user_id) "
                  "VALUES('umd','t_roll','MATH140','0201','202608',?,?)", (time.time(), uid))
        failing = c.execute("SELECT * FROM watches WHERE course='MATH140'").fetchone()
    app.send_email = lambda *a, **k: False           # SMTP having a bad moment
    app.notify_stranded(failing, FakeSchool(), "202701")
    with app.db() as c:
        st = c.execute("SELECT stranded_notified_at FROM watches WHERE id=?",
                       (failing["id"],)).fetchone()["stranded_notified_at"]
    check("a FAILED send is not stamped, so it retries", st is None,
          "stamping on attempt would swallow the only warning the student gets")
    app.send_email = lambda to, subj, body, url=None: (sent.append((to, subj, body)) or True)
    app.notify_stranded(failing, FakeSchool(), "202701")
    check("...and the retry does reach them", len(sent) == before + 1)

    # ------------------------------------------------------------- no account
    with app.db() as c:
        c.execute("INSERT INTO watches(school,topic,course,section,term,created,user_id) "
                  "VALUES('umd','t_orphan','BIO101','','202608',?,NULL)", (time.time(),))
        orph = c.execute("SELECT * FROM watches WHERE topic='t_orphan'").fetchone()
    n = len(sent)
    try:
        r = app.notify_stranded(orph, FakeSchool(), "202701")
        crashed = False
    except Exception:
        r, crashed = None, True
    check("a watch with no account is skipped, not crashed on",
          (not crashed) and r is False and len(sent) == n,
          "an exception here would take down the whole poll cycle")

    p = sum(ok for _, ok, _ in results)
    f = sum(not ok for _, ok, _ in results)
    return p, f, results


if __name__ == "__main__":
    p, f, res = run()
    for n, ok, d in res:
        print(f"  [{'PASS' if ok else '*** FAIL'}] {n}{('  ' + d) if d and not ok else ''}")
    print(f"\n  {p} passed, {f} failed")
    sys.exit(1 if f else 0)
