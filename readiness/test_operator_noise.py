"""READINESS #28 — the operator gets mailed about problems, not about weather.

Nathan asked not to be emailed unless something is really wrong. Every operator page he
received in the week of 2026-08-14 was a school that healed itself:

    MUSC204        no data 5x  ->  "recovered ✅"  24 SECONDS later
    Towson ENGL102 same shape, twice in one day
    plus a daily "all healthy ✅" that by definition never needed opening

Two mails apiece for an outage that was over before either could be read. This is the same
defect as the seat-alert storm one layer up: a true statement, delivered when nobody can
act on it, teaching the reader to archive SeatWatch mail unread — including the one that
matters.

The split that has to hold:

  PAUSE   immediate at FAIL_THRESHOLD. Correctness. A school we cannot read must stop
          producing alerts at once, and that is NOT what changed here.
  MAIL    waits for OUTAGE_CONFIRM_S. A blip that heals inside the window is never
          mailed — and neither is its recovery, since reporting the end of something the
          reader never heard begin is the more confusing half.
  DIGEST  silent when clean, and it must FAIL TOWARD SPEAKING: if the health check itself
          breaks, mail anyway. An unnecessary mail is a much cheaper mistake than silence.
"""
import os
import sys
import tempfile
import time


def run():
    os.environ["SEATWATCH_DB"] = os.path.join(tempfile.mkdtemp(), "noise.db")
    sys.path.insert(0, os.path.expanduser("~/seatwatch"))
    import app, guardian
    app.init_db()

    results = []
    def check(n, c, d=""): results.append((n, bool(c), d))

    mails = []
    _real_operator_alert = app.operator_alert   # the damping section below needs
                                               # the REAL one, not this stub
    app.operator_alert = lambda m: mails.append(m)
    app.OUTAGE_CONFIRM_S = 900
    app.FAIL_THRESHOLD = 5

    # --- the health dict as run_cycle keeps it, driven through the same transitions ---
    def outage(h, seconds, now):
        """Simulate a school unreadable for `seconds`, polling every 20s."""
        t = now
        while t < now + seconds:
            h["fails"] += 1
            if h["fails"] >= app.FAIL_THRESHOLD and not h.get("down_since"):
                h["down_since"] = t
            if (h.get("down_since") and not h["alerted"]
                    and t - h["down_since"] >= app.OUTAGE_CONFIRM_S):
                app.operator_alert(f"School X: no data for "
                                   f"{int((t - h['down_since']) / 60)} min")
                h["alerted"] = True
            t += 20
        return t

    def recover(h):
        if h["alerted"]:
            app.operator_alert("School X: recovered ✅")
        h.update(fails=0, alerted=False, down_since=0)

    # ---------------------------------------------------------------- the blip
    # 125s, which is the real MUSC204 shape once you read the log carefully: the mail says
    # "no data 5x in a row", so the outage had already run five 20s polls (~100s) BEFORE
    # the first mail, and "recovered ✅" landed 25s after it. The 24 seconds in the journal
    # is the gap between the two MAILS, not the length of the outage. Modelling it as a
    # 24s outage would never reach FAIL_THRESHOLD and would prove nothing about the pause.
    h = {"fails": 0, "alerted": False, "last_count": 0}
    t = outage(h, 125, 1_000_000.0)
    check("the real 2-minute blip mails NOTHING", not mails,
          f"{len(mails)} mail(s) — this exact shape mailed Nathan twice on 08-13")
    check("...and the PAUSE still engaged immediately", h["fails"] >= app.FAIL_THRESHOLD,
          "correctness must not have been traded for quiet: an unreadable school has to "
          "stop alerting at once")
    recover(h)
    check("...and its recovery is silent too", not mails,
          "announcing the end of an outage nobody was told about is worse than silence")

    # ------------------------------------------------------------ the real one
    mails.clear()
    h = {"fails": 0, "alerted": False, "last_count": 0}
    t = outage(h, 1800, 2_000_000.0)        # 30 minutes: a human can act on this
    check("a 30-minute outage DOES mail", len(mails) == 1,
          f"{len(mails)} mail(s) — a school genuinely dark must still reach the operator")
    check("...exactly once, not once per cycle", len(mails) == 1, f"{len(mails)}")
    recover(h)
    check("...and its recovery IS reported", len(mails) == 2,
          "having raised it, leaving it open is how an operator keeps checking a fixed thing")

    # ------------------------------------------------------- the daily digest
    mails.clear()
    app._last_summary[0] = 0
    guardian.summary_line = lambda: ""
    guardian.summary_needs_attention = lambda: False
    app.maybe_daily_summary()
    check("a clean daily digest is NOT mailed", not mails,
          f"{mails[:1]} — a mail that never needs opening trains you to ignore the ones "
          f"that do")

    mails.clear()
    app._last_summary[0] = 0
    guardian.summary_needs_attention = lambda: True
    app.maybe_daily_summary()
    check("a digest with something wrong IS mailed", len(mails) == 1,
          f"{len(mails)} — silence must be earned by health, not by a bug")

    mails.clear()
    app._last_summary[0] = 0
    def boom(): raise RuntimeError("telemetry down")
    guardian.summary_needs_attention = boom
    try:
        app.maybe_daily_summary()
    except Exception:
        pass
    check("a BROKEN health check still mails (fails toward speaking)", len(mails) == 1,
          "if we cannot tell whether anything is wrong we must not claim it is fine — "
          "that asymmetry is what makes a silent digest safe at all")

    # --- CHRONIC OUTAGES: loud when new, quiet when chronic, never silent -------------
    # Towson blocked the server's IP on 2026-08-04 and was still dark on 2026-08-23. The
    # cooldown was 30 minutes and held in memory, so it mailed Nathan roughly 48 times a
    # day for 19 days about one thing he already knew and could not fix from a keyboard,
    # and every redeploy reset the damping and mailed again immediately. That is how an
    # operator learns to ignore the channel — and then misses the one that mattered.
    mails2 = []
    app.operator_alert = _real_operator_alert      # stop mocking the thing under test
    app.send_email = lambda to, t, b, u=None, **k: (mails2.append(t), True)[1]
    app.sw.notify = lambda *a, **k: True
    app.send_web_push = lambda *a, **k: True
    app.EMAIL_ENABLED = True
    app.ADMIN_USER_ID = 1
    with app.db() as c:
        c.execute("INSERT OR IGNORE INTO users(id,google_sub,email,topic,created) "
                  "VALUES(1,'g_ops','ops@x','t_ops',0)")
        c.execute("DELETE FROM operator_mail")
    T = [5_000_000.0]
    _real_now = app._now
    app._now = lambda: T[0]
    try:
        DAYS, POLL = 19, 20
        for step in range(int(DAYS * 86400 / POLL)):
            T[0] += POLL
            app.operator_alert(f"Towson University ENGL 102: no data for {step} min")
        check("19 days of one dark school is a couple of dozen emails, not ~900",
              len(mails2) <= 40,
              f"sent {len(mails2)}; the old 30-minute timer would have sent "
              f"{int(DAYS * 86400 / 1800)}")
        check("...and it is NOT silenced entirely (a chronic fault still reports daily)",
              len(mails2) >= DAYS - 2,
              f"sent {len(mails2)} over {DAYS} days — silence would hide a real outage")
        check("the first day is still LOUD (backoff starts fast, not slow)",
              len(mails2) >= 5,
              "a new outage must not be damped into a 24-hour gap on its first report")

        before = len(mails2)
        with app.db() as c:                      # a redeploy cannot forget the damping
            pass
        T[0] += POLL
        app.operator_alert("Towson University ENGL 102: no data for 27360 min")
        check("damping survives a RESTART (it is on disk, not in memory)",
              len(mails2) == before,
              "the in-memory version re-mailed instantly on every redeploy")

        before = len(mails2)
        T[0] += 60
        app.operator_alert("Purdue CS 180: no data for 5 min")
        check("a DIFFERENT problem is still reported immediately", len(mails2) == before + 1,
              "backing off one fault must never mute an unrelated new one")

        before = len(mails2)
        T[0] += app.OPERATOR_MAIL_RESET_S + 60   # stopped recurring == over
        app.operator_alert("Towson University ENGL 102: no data for 5 min")
        check("a fault that went quiet and RETURNED is loud again",
              len(mails2) == before + 1,
              "otherwise August's outage would still be on a 24-hour backoff in December")

        before = len(mails2)
        app.send_email = lambda *a, **k: False   # SMTP down
        for _ in range(3):
            T[0] += 60
            app.operator_alert("Salisbury BIOL 101: no data for 9 min")
        app.send_email = lambda to, t, b, u=None, **k: (mails2.append(t), True)[1]
        T[0] += 60
        app.operator_alert("Salisbury BIOL 101: no data for 12 min")
        check("failed sends do NOT advance the backoff", len(mails2) == before + 1,
              "an SMTP hiccup must not escalate a fault into a 24-hour gap unreported")
    finally:
        app._now = _real_now

    p = sum(x for _, x, _ in results)
    f = sum(not x for _, x, _ in results)
    return p, f, results


if __name__ == "__main__":
    p, f, res = run()
    for n, ok, d in res:
        print(f"  [{'PASS' if ok else '*** FAIL'}] {n}{('  ' + d) if d and not ok else ''}")
    print(f"\n  {p} passed, {f} failed")
    sys.exit(1 if f else 0)
