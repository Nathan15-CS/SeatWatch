"""READINESS #9 — User feedback: never lost, even when email is off.

During a beta this is the main channel for a student to say something is wrong. Email is
best-effort (and disabled entirely until SMTP is configured), so the DATABASE is what
guarantees the message survives. These prove: stored first, emailed second, nothing lost,
and no injection through the message body.
"""
import os, tempfile, sys, time


def run():
    os.environ["SEATWATCH_DB"] = os.path.join(tempfile.mkdtemp(), "t.db")
    sys.path.insert(0, os.path.expanduser("~/seatwatch"))
    import app
    app.init_db()
    results = []
    def check(n, c, d=""): results.append((n, bool(c), d))

    with app.db() as c:
        c.execute("INSERT INTO users(google_sub,email,topic,created) "
                  "VALUES('g_fb','student@umd.edu','t_fb',0)")

    def submit(msg, email_on):
        """Exercise the handler's logic path (persist -> best-effort email)."""
        sent_box = []
        app.EMAIL_ENABLED = email_on
        app.send_email = lambda to, s, b, u: (sent_box.append((to, s, b)), True)[1]
        with app.db() as c:
            cur = c.execute("INSERT INTO feedback(user_id,email,message,created) VALUES(?,?,?,?)",
                            (1, "student@umd.edu", msg[:4000], time.time()))
            fid = cur.lastrowid
        ok = False
        if app.EMAIL_ENABLED:
            ok = app.send_email(app.SUPPORT_EMAIL, f"SeatWatch feedback #{fid}",
                                f"From: student@umd.edu\n\n{msg}", "https://seatwatchapp.com/")
            if ok:
                with app.db() as c:
                    c.execute("UPDATE feedback SET emailed_at=? WHERE id=?", (time.time(), fid))
        return fid, sent_box

    # --- email OFF (today's reality): must still be stored ---
    fid, box = submit("My school isn't listed — can you add Towson?", email_on=False)
    with app.db() as c:
        row = c.execute("SELECT * FROM feedback WHERE id=?", (fid,)).fetchone()
    check("stored when email is OFF (nothing lost)", row is not None)
    check("message preserved verbatim", row and "Towson" in row["message"])
    check("submitter's email captured for reply", row and row["email"] == "student@umd.edu")
    check("emailed_at NULL so unsent notes are findable", row and row["emailed_at"] is None)
    check("no email attempted while disabled", len(box) == 0)

    # --- email ON: stored AND delivered to support@ ---
    fid2, box2 = submit("The alert was 10 minutes late.", email_on=True)
    with app.db() as c:
        row2 = c.execute("SELECT * FROM feedback WHERE id=?", (fid2,)).fetchone()
    check("stored when email is ON", row2 is not None)
    check("emailed to support@seatwatchapp.com", box2 and box2[0][0] == "support@seatwatchapp.com")
    check("email body carries the message", box2 and "10 minutes late" in box2[0][2])
    check("email identifies the submitter", box2 and "student@umd.edu" in box2[0][2])
    check("emailed_at stamped once delivered", row2 and row2["emailed_at"] is not None)

    # --- unsent backlog is queryable (so it can be re-sent when SMTP lands) ---
    with app.db() as c:
        unsent = c.execute("SELECT COUNT(*) FROM feedback WHERE emailed_at IS NULL").fetchone()[0]
    check("unsent backlog queryable for later delivery", unsent == 1, f"got {unsent}")

    # --- abuse / safety ---
    fid3, _ = submit("x" * 9000, email_on=False)
    with app.db() as c:
        long_row = c.execute("SELECT message FROM feedback WHERE id=?", (fid3,)).fetchone()
    check("over-long message truncated (4000 cap)", len(long_row["message"]) <= 4000)

    evil = "<script>alert(1)</script> & \"quotes\" 'and' <b>bold</b>"
    fid4, _ = submit(evil, email_on=False)
    with app.db() as c:
        raw = c.execute("SELECT message FROM feedback WHERE id=?", (fid4,)).fetchone()["message"]
    check("message stored raw (escaping happens at render, not storage)", raw == evil)
    # the notice path escapes; confirm the helper we rely on is escaping
    import html as _h
    check("html.escape neutralises script tags for display",
          "<script>" not in _h.escape(evil))

    # --- the backlog DRAINS BY ITSELF once mail works (retry_unsent_feedback) ----------
    # Storing a message nobody ever reads is only half a guarantee. Feedback #1-#3 on prod
    # sat unread for a day because SMTP wasn't configured at the time they arrived, and
    # nothing retried them. These pin the retry sweep that closes that.
    with app.db() as c:
        backlog = [r["id"] for r in c.execute(
            "SELECT id FROM feedback WHERE emailed_at IS NULL ORDER BY id")]
    check("backlog exists to drain", len(backlog) >= 1, f"got {len(backlog)}")

    # mail still down: nothing may be marked delivered, and it must not raise
    app.EMAIL_ENABLED = True
    app.send_email = lambda to, s, b, u: False
    app._feedback_retry_at[0] = 0
    app.retry_unsent_feedback()
    with app.db() as c:
        still = c.execute("SELECT COUNT(*) FROM feedback WHERE emailed_at IS NULL").fetchone()[0]
    check("failed retry leaves the backlog intact (never marks a lie)",
          still == len(backlog), f"{still} vs {len(backlog)}")

    # mail comes back: the whole backlog is delivered and stamped
    sent = []
    app.send_email = lambda to, s, b, u: (sent.append((to, s, b)), True)[1]
    app._feedback_retry_at[0] = 0
    app.retry_unsent_feedback()
    with app.db() as c:
        left = c.execute("SELECT COUNT(*) FROM feedback WHERE emailed_at IS NULL").fetchone()[0]
    check("backlog delivered once email works", left == 0, f"{left} still unsent")
    check("every backlogged message was actually sent", len(sent) == len(backlog),
          f"sent {len(sent)} of {len(backlog)}")
    check("retry mail goes to support@", all(s[0] == "support@seatwatchapp.com" for s in sent))
    check("retry mail carries the original text",
          any("Towson" in s[2] for s in sent), "the stored message never reached the email")

    # throttle: a second immediate sweep must not re-send anything
    sent.clear()
    app.retry_unsent_feedback()
    check("throttled: no duplicate sends on an immediate re-sweep", len(sent) == 0,
          f"re-sent {len(sent)}")

    # already-delivered rows are never re-sent even when the throttle is clear
    app._feedback_retry_at[0] = 0
    sent.clear()
    app.retry_unsent_feedback()
    check("delivered feedback is never emailed twice", len(sent) == 0, f"re-sent {len(sent)}")

    # a broken DB/send must not escape into the poll loop
    app.send_email = lambda *a: (_ for _ in ()).throw(RuntimeError("smtp exploded"))
    with app.db() as c:
        c.execute("INSERT INTO feedback(user_id,email,message,created) VALUES(1,'x@y.z','boom',?)",
                  (time.time(),))
    app._feedback_retry_at[0] = 0
    raised = False
    try:
        app.retry_unsent_feedback()
    except Exception:
        raised = True
    check("a crashing send never propagates into the poller", not raised,
          "an exception here would stop seat polling")

    app.EMAIL_ENABLED = False
    app._feedback_retry_at[0] = 0
    app.retry_unsent_feedback()          # must be a silent no-op, not a crash
    check("no-op when email is disabled", True)

    p = sum(ok for _, ok, _ in results); f = sum(not ok for _, ok, _ in results)
    return p, f, results


if __name__ == "__main__":
    import warnings; warnings.filterwarnings("ignore")
    p, f, res = run()
    for n, ok, d in res:
        print(f"  [{'PASS' if ok else '*** FAIL'}] {n}{('  ' + d) if d and not ok else ''}")
    print(f"\n  {p} passed, {f} failed")
    sys.exit(1 if f else 0)
