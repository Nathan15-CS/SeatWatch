"""READINESS #24 — an operator alert must reach a human, not just a channel.

On 2026-08-02 USF went dark for 1h48m: 272 consecutive failed fetches with two live
watches on it. Every guard worked. The incident was raised, the page fired five seconds
after the fifth failure, and fail-closed containment meant not one false alert went out.

And nobody found out for two days, because the operator alert went to web push and ntfy —
channels with nobody watching. It surfaced only because a scheduled checkpoint happened to
read the incidents table.

That is the same defect students had until this week: a channel that reports success while
reaching no one. Every guard in this system terminates in a human being told; if that last
step is unreliable, the guards are decoration.

Pinned here:
  REACHES       an operator alert sends EMAIL, not only push/ntfy
  DAMPED        an escalating outage is one email, not one per 20-second cycle
  INDEPENDENT   a NEW problem is not muted behind an old one
  NEVER RAISES  a broken mailer cannot take down the poller, which would turn one
                school's problem into every student's problem
"""
import os
import sys
import tempfile
import time
import warnings

warnings.filterwarnings("ignore")


def run():
    os.environ["SEATWATCH_DB"] = os.path.join(tempfile.mkdtemp(), "op.db")
    sys.path.insert(0, os.path.expanduser("~/seatwatch"))
    import app
    app.init_db()

    results = []
    def check(n, c, d=""): results.append((n, bool(c), d))

    with app.db() as c:
        c.execute("INSERT INTO users(google_sub,email,topic,created) "
                  "VALUES('g_op','ops@seatwatchapp.com','t_op',?)", (time.time(),))
        uid = c.execute("SELECT id FROM users WHERE google_sub='g_op'").fetchone()["id"]

    sent = []
    app.ADMIN_USER_ID = uid
    app.EMAIL_ENABLED = True
    app.send_email = lambda to, subj, body, url=None: (sent.append((to, subj, body)) or True)
    app.send_web_push = lambda *a, **k: 0
    app.sw.notify = lambda *a, **k: True
    app._op_mail_last.clear()

    # ------------------------------------------------------------------ reaches
    app.operator_alert("usf: 5 consecutive failed or empty fetches")
    check("an operator alert sends EMAIL", len(sent) == 1,
          f"sent {len(sent)} — push and ntfy alone is how USF went dark for 1h48m unnoticed")
    if sent:
        to, subj, body = sent[0]
        check("...to the operator's address", to == "ops@seatwatchapp.com")
        check("...carrying the actual problem", "usf" in body)
        check("...and says students were NOT contacted",
              "students were not contacted" in body.lower(),
              "an operator must never wonder whether this also went to users")

    # ------------------------------------------------------------------- damped
    for n in (6, 7, 8, 9, 12, 40, 272):
        app.operator_alert(f"usf: {n} consecutive failed or empty fetches")
    check("an escalating outage is ONE email, not one per cycle", len(sent) == 1,
          f"sent {len(sent)} — the poller runs every 20s; USF alone would have been 272")

    # -------------------------------------------------------------- independent
    app.operator_alert("towson: 5 consecutive failed or empty fetches")
    check("a DIFFERENT school still gets through", len(sent) == 2,
          "damping must not mute a new problem behind an old one")
    app.operator_alert("🚨 UNDELIVERED: CMSC216 seat opened but email + text BOTH failed")
    check("a different KIND of problem gets through too", len(sent) == 3)

    # ------------------------------------------------------------ never raises
    def boom(*a, **k):
        raise RuntimeError("smtp is down")
    app.send_email = boom
    app._op_mail_last.clear()
    try:
        app.operator_alert("umd: 5 consecutive failed or empty fetches")
        crashed = False
    except Exception:
        crashed = True
    check("a broken mailer does NOT raise", not crashed,
          "this runs inside the poll cycle; raising turns one school's problem into "
          "every student's problem")

    # A failed send must not be recorded as sent, or the retry is lost forever.
    app.send_email = lambda to, subj, body, url=None: (sent.append((to, subj, body)) or True)
    app.operator_alert("umd: 6 consecutive failed or empty fetches")
    check("...and the alert still reaches them once the mailer recovers", len(sent) == 4,
          "stamping on a failed attempt would swallow the only warning")

    p = sum(ok for _, ok, _ in results)
    f = sum(not ok for _, ok, _ in results)
    return p, f, results


if __name__ == "__main__":
    p, f, res = run()
    for n, ok, d in res:
        print(f"  [{'PASS' if ok else '*** FAIL'}] {n}{('  ' + d) if d and not ok else ''}")
    print(f"\n  {p} passed, {f} failed")
    sys.exit(1 if f else 0)
