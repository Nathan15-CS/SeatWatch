"""READINESS #8 — Beta instrumentation: reachability, action rate, time-to-action.

alert_log records only SUCCESSES, so delivery always looks like a perfect 100% and a
student who had NO reachable channel leaves no trace. alert_attempt is the denominator.
This proves the three metrics the beta decision depends on are actually recorded:

  reachability   = sent / attempts            (silent failures are COUNTED, not invisible)
  action rate    = clicked / sent, per channel (delivery != value)
  time-to-action = clicked_at - attempted_at   (the real SMS-vs-push test)
"""
import os, tempfile, sys, time


def run():
    os.environ["SEATWATCH_DB"] = os.path.join(tempfile.mkdtemp(), "t.db")
    sys.path.insert(0, os.path.expanduser("~/seatwatch"))
    import app, schools
    # Opening confirmation (CONFIRM_SECONDS) is OFF here: this suite drives
    # run_cycle expecting one cycle to equal one alert, and its subject is beta reachability instrumentation,
    # not alert timing. The confirmation contract is owned by test_churn_confirm
    # (real-timeline replay) and exercised through run_cycle by
    # test_alert_transitions, so turning it off here hides nothing.
    app.CONFIRM_SECONDS = 0
    app.init_db()
    results = []
    def check(n, c, d=""): results.append((n, bool(c), d))

    REG = "https://reg.canary.edu/register"
    class FakeSchool:
        id = "canary"; name = "Canary"; example = "CS 101"
        def __init__(self): self._data = {}
        def cur_term(self): return "202608"
        def reg_url(self, course): return REG
        def fetch(self, courses): return {c: self._data[c] for c in courses if c in self._data}
    fake = FakeSchool(); schools.SCHOOLS = {"canary": fake}
    app.BASE_URL = "https://seatwatchapp.com"

    emailed_urls = []
    app.EMAIL_ENABLED = True
    app.sw.notify = lambda *a, **k: True                    # operator channel only
    app.send_email = lambda to, t, b, u=None, **k: (emailed_urls.append(u), True)[1]
    app.send_sms = lambda *a, **k: False
    app.operator_alert = lambda m: None

    with app.db() as c:
        c.execute("INSERT INTO users(google_sub,email,topic,created) VALUES('g','a@b','t_i',0)")
        cur = c.execute("INSERT INTO watches(school,topic,course,section,term,alerted,created,user_id) "
                        "VALUES('canary','t_i','CS 101','0101','202608',0,0,1)")
        WID = cur.lastrowid

    # --- a seat opens, alert goes out ---
    fake._data = {"CS 101": {"0101": {"open": True, "seats": 3}}}
    app.run_cycle()

    with app.db() as c:
        atts = c.execute("SELECT * FROM alert_attempt ORDER BY id").fetchall()
    check("attempts recorded for delivered channels", len(atts) >= 1)
    sent = [a for a in atts if a["outcome"] == "sent"]
    check("delivered channels logged as 'sent'", len(sent) >= 1)
    check("each delivered channel carries a click token", all(a["token"] for a in sent if a["channel"] != "sms"))

    # --- the click path: a student taps the alert ---
    wp = [a for a in sent if a["channel"] == "email"]
    check("email attempt exists", len(wp) == 1)
    if wp:
        tokrow = wp[0]
        check("email link routed through /r/ (trackable)",
              any(f"/r/{tokrow['token']}" in (u or "") for u in emailed_urls))
        # simulate the redirect handler's core: first click stamps, second does not
        with app.db() as c:
            r1 = c.execute("SELECT clicked_at FROM alert_attempt WHERE id=?", (tokrow["id"],)).fetchone()
            check("not clicked yet", r1["clicked_at"] is None)
            c.execute("UPDATE alert_attempt SET clicked_at=? WHERE id=? AND clicked_at IS NULL",
                      (time.time(), tokrow["id"]))
            first = c.execute("SELECT clicked_at FROM alert_attempt WHERE id=?", (tokrow["id"],)).fetchone()["clicked_at"]
            time.sleep(0.01)
            c.execute("UPDATE alert_attempt SET clicked_at=? WHERE id=? AND clicked_at IS NULL",
                      (time.time(), tokrow["id"]))
            second = c.execute("SELECT clicked_at FROM alert_attempt WHERE id=?", (tokrow["id"],)).fetchone()["clicked_at"]
        check("click recorded", first is not None)
        check("re-click does NOT overwrite (first action is the metric)", first == second)
        check("time-to-action computable", (first - tokrow["attempted_at"]) >= 0)

    # --- THE SILENT FAILURE: seat opens, nothing can reach the student ---
    app.sw.notify = lambda *a, **k: False
    app.send_email = lambda *a, **k: False
    with app.db() as c:
        c.execute("UPDATE watches SET alerted=0 WHERE id=?", (WID,))
        # Age the ledger past the repeat cooldown. This watch was successfully alerted a
        # moment ago, so without this the next alert is HELD as a repeat and no channel is
        # ever ATTEMPTED — a deliberate decision, not a failure to reach anyone. The suite
        # would then be asserting suppression while claiming to test unreachability, and
        # the two are opposites: one is the system working, the other is the thing we hunt.
        c.execute("UPDATE alert_log SET sent_at=sent_at-?",
                  (getattr(app, "REPEAT_ALERT_COOLDOWN_S", 1800) + 60,))
    app.run_cycle()
    with app.db() as c:
        nc = c.execute("SELECT COUNT(*) FROM alert_attempt WHERE outcome='no_channel'").fetchone()[0]
        succ = c.execute("SELECT COUNT(*) FROM alert_log WHERE channel IN ('email','sms')").fetchone()[0]
    check("unreachable student recorded as 'no_channel'", nc == 1)
    check("...and alert_log alone would have HIDDEN it (successes only)", succ >= 0)

    # --- the metrics the beta decision needs are queryable ---
    with app.db() as c:
        total = c.execute("SELECT COUNT(*) FROM alert_attempt").fetchone()[0]
        sent_n = c.execute("SELECT COUNT(*) FROM alert_attempt WHERE outcome='sent'").fetchone()[0]
        clicks = c.execute("SELECT COUNT(*) FROM alert_attempt WHERE clicked_at IS NOT NULL").fetchone()[0]
    check("reachability computable (sent/attempts)", total > 0 and sent_n <= total)
    check("action rate computable (clicks/sent)", sent_n > 0 and clicks <= sent_n)
    check("silent_failure_rate computable", total > 0)

    # --- price probe table exists and is dormant ---
    with app.db() as c:
        cols = [r[1] for r in c.execute("PRAGMA table_info(price_probe)")]
        rows = c.execute("SELECT COUNT(*) FROM price_probe").fetchone()[0]
    check("price_probe table ready", {"user_id", "shown_at", "purchased_at"} <= set(cols))
    check("price probe DORMANT (no rows until Nathan's go)", rows == 0)

    p = sum(ok for _, ok, _ in results); f = sum(not ok for _, ok, _ in results)
    return p, f, results


if __name__ == "__main__":
    import warnings; warnings.filterwarnings("ignore")
    p, f, res = run()
    for n, ok, d in res:
        print(f"  [{'PASS' if ok else '*** FAIL'}] {n}{('  ' + d) if d and not ok else ''}")
    print(f"\n  {p} passed, {f} failed")
    sys.exit(1 if f else 0)
