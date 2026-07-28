"""READINESS #6 — Synthetic canary: controlled seat-opening through the REAL path,
verifying alert CONTENT, not just "delivered".

Injects a seat opening into a synthetic school, runs the real run_cycle -> real _alert ->
the real channel fan-out, and asserts the student would receive the RIGHT information:
correct course, correct section, correct seat count, and a working registration link. A
delivered-but-wrong alert (wrong course, wrong count, dead link) is its own reputation
failure, so "it sent something" is not a pass.

Also proves the fallback chain: when web-push fails, the alert still reaches the student
by another channel, and if NOTHING reaches them the operator is paged (delivered-to-nobody).
"""
import os, tempfile, sys


def run():
    os.environ["SEATWATCH_DB"] = os.path.join(tempfile.mkdtemp(), "t.db")
    sys.path.insert(0, os.path.expanduser("~/seatwatch"))
    import app, schools
    app.init_db()
    results = []
    def check(name, cond, detail=""): results.append((name, bool(cond), detail))

    REG_URL = "https://reg.canary.edu/register?crn=12345"
    class FakeSchool:
        id = "canary"; name = "Canary University"; example = "CS 101"
        def __init__(self): self._data = {}
        def cur_term(self): return "202608"
        def reg_url(self, course): return REG_URL
        def fetch(self, courses): return {c: self._data[c] for c in courses if c in self._data}
    fake = FakeSchool(); schools.SCHOOLS = {"canary": fake}
    app.BASE_URL = "https://seatwatchapp.com"

    pushes, ntfys, emails, paged = [], [], [], []
    app.send_web_push = lambda uid, title, body, url: (pushes.append((title, body, url)), 1)[1]
    app.sw.notify = lambda title, msg, click_url=None, topic=None: (ntfys.append((title, msg, click_url)), True)[1]
    app.send_email = lambda to, subj, body, url: (emails.append((to, subj, body, url)), True)[1]
    app.send_sms = lambda *a, **k: False
    app.operator_alert = lambda m: paged.append(m)

    with app.db() as c:
        c.execute("INSERT INTO users(google_sub,email,topic,created) VALUES('g_cy','cy@x.edu','t_cy',0)")
        cur = c.execute("INSERT INTO watches(school,topic,course,section,term,alerted,created,user_id) "
                  "VALUES('canary','t_cy','CS 101','0101','202608',0,0,1)")
        WID = cur.lastrowid

    # --- inject the seat opening ---
    fake._data = {"CS 101": {"0101": {"open": True, "seats": 3}}}
    app.run_cycle()

    check("canary alert was delivered by web-push", len(pushes) == 1)
    if pushes:
        title, body, url = pushes[0]
        blob = f"{title} {body}"
        check("CONTENT: names the right course (CS 101)", "CS 101" in blob)
        check("CONTENT: names the right section (0101)", "0101" in blob)
        check("CONTENT: states the real seat count (3)", "3" in body)
        # The link is now a tracked /r/<token> redirect (so we can measure whether an alert
        # produced ACTION). That must NOT cost the student the destination — assert the
        # token actually resolves to this school's registrar, i.e. the redirect the handler
        # would issue. A tracked link that loses the student is worse than no tracking.
        if url.startswith(f"{app.BASE_URL}/r/") if getattr(app, "BASE_URL", "") else False:
            token = url.rsplit("/r/", 1)[1]
            with app.db() as c:
                row = c.execute("SELECT school, course FROM alert_attempt WHERE token=?",
                                (token,)).fetchone()
            dest = schools.SCHOOLS[row["school"]].reg_url(row["course"]) if row else None
            check("CONTENT: tracked link resolves to the school's registration URL",
                  dest == REG_URL, f"token={token} dest={dest}")
        else:
            check("CONTENT: link is the school's registration URL", url == REG_URL)
        check("CONTENT: tells the student to act", any(w in body.lower() for w in ("register", "go now", "tap")))
        check("CONTENT: no template placeholder leaked", "__" not in blob and "{" not in blob)
    check("ledger recorded the webpush delivery",
          _count(app, "webpush") == 1)

    # --- fallback chain: web-push dies, student must STILL be reached ---
    pushes.clear(); ntfys.clear(); emails.clear()
    app.send_web_push = lambda *a, **k: 0            # every device gone
    app.EMAIL_ENABLED = True
    with app.db() as c:                               # re-arm the watch
        c.execute("UPDATE watches SET alerted=0 WHERE id=?", (WID,))
    app.run_cycle()
    reached = len(ntfys) > 0 or len(emails) > 0
    check("FALLBACK: web-push fails -> student still reached by another channel", reached)
    if emails:
        eurl = emails[0][3]
        eok = (eurl == REG_URL) or eurl.startswith(f"{getattr(app,'BASE_URL','')}/r/")
        check("FALLBACK: email carries the course + a working link",
              "CS 101" in emails[0][2] and eok, f"url={eurl}")

    # --- delivered-to-nobody: every channel fails -> operator paged, watch NOT latched ---
    paged.clear()
    app.send_web_push = lambda *a, **k: 0
    app.sw.notify = lambda *a, **k: False
    app.send_email = lambda *a, **k: False
    with app.db() as c:
        c.execute("UPDATE watches SET alerted=0 WHERE id=?", (WID,))
    app.run_cycle()
    check("NOBODY REACHED: operator is paged", any("UNDELIVERED" in m or "NOT notified" in m for m in paged))
    with app.db() as c:
        latched = c.execute("SELECT alerted FROM watches WHERE id=?", (WID,)).fetchone()[0]
    check("NOBODY REACHED: watch stays un-latched so it retries", latched == 0)

    p = sum(ok for _, ok, _ in results); f = sum(not ok for _, ok, _ in results)
    return p, f, results


def _count(app, channel):
    with app.db() as c:
        return c.execute("SELECT COUNT(*) FROM alert_log WHERE channel=?", (channel,)).fetchone()[0]


if __name__ == "__main__":
    import warnings; warnings.filterwarnings("ignore")
    p, f, res = run()
    for name, ok, detail in res:
        print(f"  [{'PASS' if ok else '*** FAIL'}] {name}{('  ' + detail) if detail and not ok else ''}")
    print(f"\n  {p} passed, {f} failed")
    sys.exit(1 if f else 0)
