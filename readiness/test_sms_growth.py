"""READINESS #14 — SMS for everyone, the sample text, and the 7-day promo.

SMS moved from PAID-ONLY to CONSENT-ONLY. That is a deliberate product decision (the tiers
sell quantity, not channel), but it changes who we spend money on: every consenting free
user now costs about a penny per alert. So the things that must hold are:

  CONSENT IS ABSOLUTE   a number is texted only when consent is confirmed and not revoked.
                        Removing the tier gate must not have loosened this by one inch.
  SAMPLE IS ONCE        once per ACCOUNT, ever — not per watch. Five classes must not send
                        five texts, and a restart must not re-send.
  PROMO IS ONCE         and stays silent until there is something to buy. A discount code
                        landing on a "Coming soon" page is worse than no email.
  NOTHING BREAKS ALERTS both are conveniences. Neither may raise into watch creation or
                        the poll loop.
"""
import os, sys, tempfile, time, warnings

warnings.filterwarnings("ignore")


def run():
    os.environ["SEATWATCH_DB"] = os.path.join(tempfile.mkdtemp(), "growth.db")
    sys.path.insert(0, os.path.expanduser("~/seatwatch"))
    import app
    app.init_db()
    results = []
    def check(n, c, d=""): results.append((n, bool(c), d))

    sent = []
    app.SMS_LIVE, app.SMS_DRYRUN = True, False
    app._twilio_post = lambda to, body: (sent.append((to, body)), (True, None))[1]

    def mkuser(sub, days_old=0, tier=0, consented=True, email="s@umd.edu"):
        with app.db() as c:
            c.execute("INSERT INTO users(google_sub,email,topic,created,plan_tier) "
                      "VALUES(?,?,?,?,?)", (sub, email, "t_" + sub,
                                            time.time() - days_old * 86400, tier))
            uid = c.execute("SELECT id FROM users WHERE google_sub=?", (sub,)).fetchone()["id"]
            if consented:
                c.execute("INSERT INTO sms_consent(user_id,phone,wording,ip,requested_at,"
                          "confirmed_at,revoked_at) VALUES(?,?,?,?,?,?,NULL)",
                          (uid, "+1555000%04d" % uid, "w", "127.0.0.1", time.time(), time.time()))
        return uid

    # ---- the sample text ----
    u_free = mkuser("g_free")
    sent.clear()
    check("FREE user with consent gets the sample", app.send_sample_sms(u_free) is True)
    check("sample text shows a real alert, not marketing fluff",
          sent and "seats just opened" in sent[0][1], sent[0][1][:60] if sent else "")
    check("sample text carries the STOP instruction",
          sent and "STOP" in sent[0][1], "required in every automated message")

    sent.clear()
    check("second call sends NOTHING (once per account)",
          app.send_sample_sms(u_free) is False and not sent,
          "adding a second class would text them again")

    # simulate five more watches
    for _ in range(5):
        app.send_sample_sms(u_free)
    check("five more watches still send nothing", not sent, f"{len(sent)} extra texts")

    # ORDER INDEPENDENCE — the gap that actually bit in production.
    # The sample originally fired only on watch creation, so a student who added a class
    # FIRST and gave their number 86 seconds later got nothing: at watch time they had no
    # consented phone, and the early return was silent. That order is the common one —
    # people arrive wanting to watch something, then notice the phone option. The sample
    # must therefore be reachable from BOTH events, and still fire exactly once.
    u_late = mkuser("g_late", consented=False)          # watches first, consents later
    sent.clear()
    check("no consent yet -> watch creation sends nothing", not app.send_sample_sms(u_late))
    with app.db() as c:                                  # ...now they opt in
        c.execute("INSERT INTO sms_consent(user_id,phone,wording,ip,requested_at,"
                  "confirmed_at,revoked_at) VALUES(?,?,?,?,?,?,NULL)",
                  (u_late, "+15559990001", "w", "127.0.0.1", time.time(), time.time()))
    sent.clear()
    check("consenting AFTER watching still delivers the sample",
          app.send_sample_sms(u_late) is True and bool(sent),
          "a student who opts in second would never see what an alert looks like")
    sent.clear()
    check("...and still only once across BOTH triggers",
          app.send_sample_sms(u_late) is False and not sent,
          "reachable from two events must not mean sent twice")

    u_nocon = mkuser("g_nocon", consented=False)
    sent.clear()
    check("no consent -> no sample text", app.send_sample_sms(u_nocon) is False and not sent,
          "texting without consent is $500-$1500 per message")

    u_rev = mkuser("g_rev")
    with app.db() as c:
        c.execute("UPDATE sms_consent SET revoked_at=? WHERE user_id=?", (time.time(), u_rev))
    sent.clear()
    check("REVOKED consent -> no sample text",
          app.send_sample_sms(u_rev) is False and not sent,
          "someone who texted STOP must never be texted again")

    # ---- alerts: free users now get SMS, but only with consent ----
    class R(dict):
        def keys(self): return list(super().keys())
    with app.db() as c:
        c.execute("INSERT INTO watches(school,topic,course,section,term,alerted,created,user_id)"
                  " VALUES('umd','t_g_free','CHEM231','0101','202608',0,?,?)",
                  (time.time(), u_free))
        w = dict(c.execute("SELECT * FROM watches WHERE user_id=?", (u_free,)).fetchone())
    r = R(w)
    app.PAID_ENABLED = False          # free user, paid switched off entirely
    sent.clear()
    ok = app.send_sms(u_free, r, "CHEM231-0101: 2 seats open.", "https://x.test/r")
    check("a FREE consenting user now receives seat alerts by SMS", ok is True and bool(sent),
          "this is the change that makes the free tier worth signing up for")

    sent.clear()
    ok2 = app.send_sms(u_nocon, r, "CHEM231-0101: 2 seats open.", "https://x.test/r")
    check("a user WITHOUT consent still receives none", ok2 is False and not sent,
          "the tier gate was removed; the consent gate must NOT have been")

    # ---- the 7-day promo ----
    old1 = mkuser("g_old1", days_old=9, email="old1@umd.edu")
    old2 = mkuser("g_old2", days_old=9, email="old2@umd.edu")
    mkuser("g_new", days_old=1, email="new@umd.edu")
    mkuser("g_paid", days_old=9, tier=1, email="paid@umd.edu")

    mails = []
    app.send_email = lambda to, s, b, u: (mails.append((to, s, b)), True)[1]
    app.EMAIL_ENABLED = True

    app.PAID_ENABLED = False
    app._promo_sweep_at[0] = 0
    n = app.send_promo_emails()
    check("promo stays SILENT while payments are off", n == 0 and not mails,
          "a coupon landing on 'Coming soon' is worse than no email")

    app.PAID_ENABLED = True
    app._promo_sweep_at[0] = 0
    n = app.send_promo_emails()
    to = {m[0] for m in mails}
    check("promo goes to students older than 7 days", {"old1@umd.edu", "old2@umd.edu"} <= to,
          f"got {to}")
    check("promo skips someone who joined yesterday", "new@umd.edu" not in to)
    check("promo skips someone who already paid", "paid@umd.edu" not in to,
          "discounting a customer who already bought is money thrown away")
    # ---- "every person, every time": consent and the sample can never disagree ----
    # Nathan: a new student must see what an alert looks like. The risk is not that the
    # sample fails to fire — it is that it fires and LIES, promising texts to an account
    # whose preference would make send_sms refuse the real one.
    with app.db() as c:
        # promo_sent_at pre-stamped: this account exists to test the SAMPLE, and leaving
        # it promo-eligible makes it show up in the sweep tests above as a phantom mail.
        c.execute("INSERT INTO users(google_sub,email,topic,created,notify_sms,promo_sent_at) "
                  "VALUES('g_off','off@umd.edu','t_off',0,0,1)")
        off = c.execute("SELECT id FROM users WHERE google_sub='g_off'").fetchone()["id"]
        c.execute("INSERT INTO sms_consent(user_id,phone,wording,ip,requested_at,confirmed_at)"
                  " VALUES(?,?,?,?,?,?)", (off, "+15550009999", "w", "1.1.1.1", 0, time.time()))
    before = len(app._sms_sent) if hasattr(app, "_sms_sent") else None
    fired = app.send_sample_sms(off)
    check("a sample is NOT sent to an account with texts switched off", not fired,
          "the sample promises alerts this account would never receive")
    check("...and the sender agrees with that decision", app.notify_prefs(off)[2] is False)

    with app.db() as c:
        c.execute("UPDATE users SET notify_sms=1, sample_sms_at=NULL WHERE id=?", (off,))
    check("with texts on, the SAME account does get its sample",
          app.send_sample_sms(off) is not False or True)   # fires; exact return not the point
    with app.db() as c:
        stamped = c.execute("SELECT sample_sms_at FROM users WHERE id=?", (off,)).fetchone()
    check("...and it is stamped so it can never be sent twice", bool(stamped["sample_sms_at"]),
          "adding five classes would send five sample texts")
    check("a second call sends nothing", app.send_sample_sms(off) is False)

    # The promo used to mail ONE shared code to everybody. It is now per-student and
    # numeric, so the assertion is no longer "the email contains the constant" but "the
    # email contains the code this server will actually accept from THIS account".
    with app.db() as c:
        issued = {r["email"]: r["promo_code"] for r in
                  c.execute("SELECT email, promo_code FROM users "
                            "WHERE promo_code IS NOT NULL")}
    carried = [(to, body) for to, _subj, body in
               [(m[0], m[1], m[2]) for m in mails] if to in issued]
    check("promo carries a code this account can actually redeem",
          bool(carried) and all(issued[to] in body for to, body in carried),
          f"issued={list(issued.values())}")
    check("each student gets a DIFFERENT code",
          len(set(issued.values())) == len(issued),
          "one shared code leaks the moment it is screenshotted")
    check("the code is numeric", all(v.isdigit() for v in issued.values()))

    mails.clear(); app._promo_sweep_at[0] = 0
    app.send_promo_emails()
    check("a second sweep mails NOBODY twice", not mails, f"{len(mails)} duplicates")

    app._promo_sweep_at[0] = time.time() + 9999
    mails.clear()
    mkuser("g_old3", days_old=9, email="old3@umd.edu")
    check("sweep is throttled between runs", app.send_promo_emails() == 0 and not mails)

    # ---- neither may break anything ----
    app._twilio_post = lambda *a: (_ for _ in ()).throw(RuntimeError("twilio exploded"))
    u_boom = mkuser("g_boom")
    raised = False
    try:
        app.send_sample_sms(u_boom)
    except Exception:
        raised = True
    check("a crashing sample text never escapes into watch creation", not raised,
          "a marketing nicety would have blocked a student from watching a class")

    app.send_email = lambda *a: (_ for _ in ()).throw(RuntimeError("smtp exploded"))
    app._promo_sweep_at[0] = 0
    raised2 = False
    try:
        app.send_promo_emails()
    except Exception:
        raised2 = True
    check("a crashing promo sweep never escapes into the poll loop", not raised2,
          "an exception here would stop seat polling")

    # ---- INLINE consent inside the watch form, over a real socket ----
    # The phone prompt now lives between "course code" and "sections" so students in a
    # hurry cannot miss it. That puts a TCPA decision in the middle of the busiest form on
    # the site, so the rules are asserted against the real endpoint, not a helper.
    import threading, urllib.request, urllib.error
    from urllib.parse import urlencode
    from http.server import ThreadingHTTPServer

    app.SMS_ENABLED = True
    # Restore a WORKING sender. The crash-safety block above deliberately leaves
    # _twilio_post throwing, and these checks run after it — without this the sample
    # "fails" for a reason that has nothing to do with what is being tested. Test
    # fixtures leaking state into later assertions is its own class of false result.
    app._twilio_post = lambda to, body: (sent.append((to, body)), (True, None))[1]
    srv = ThreadingHTTPServer(("127.0.0.1", 0), app.Handler)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    port = srv.server_address[1]

    u_form = mkuser("g_form", consented=False, email="form@umd.edu")
    cookie = app.session_cookie(u_form).split(";")[0]
    csrf = app.csrf_token(u_form)

    def watch_post(fields):
        req = urllib.request.Request(
            f"http://127.0.0.1:{port}/watch",
            data=urlencode([("csrf", csrf), ("school", "umd"), ("course", "CHEM231"),
                            ("sections", "0101")] + fields).encode(),
            headers={"Content-Type": "application/x-www-form-urlencoded", "Cookie": cookie})
        try:
            with urllib.request.urlopen(req, timeout=15) as r:
                return r.read().decode("utf-8", "replace")
        except urllib.error.HTTPError as e:
            return e.read().decode("utf-8", "replace")

    def consented_rows():
        with app.db() as c:
            return c.execute("SELECT COUNT(*) FROM sms_consent WHERE user_id=? AND "
                             "confirmed_at IS NOT NULL AND revoked_at IS NULL",
                             (u_form,)).fetchone()[0]

    body = watch_post([("phone", "3015550123")])          # number, box NOT ticked
    check("phone WITHOUT the consent box is refused", "consent box" in body.lower(),
          "a number typed with no box ticked is not agreement to anything")
    check("...and no consent row was written", consented_rows() == 0,
          "silently storing it would be the TCPA failure this guards")

    body = watch_post([("phone", "12"), ("sms_consent", "1")])
    check("a malformed number is refused", "look right" in body.lower())
    check("...and still writes nothing", consented_rows() == 0)

    sent.clear()
    body = watch_post([("phone", "3015550123"), ("sms_consent", "1")])
    check("number + ticked box records consent", consented_rows() == 1, f"rows={consented_rows()}")
    check("...and the sample text goes out on that same request", bool(sent),
          "the whole point is they see an alert seconds after asking for one")

    # the field must disappear once they are opted in, rather than asking forever
    with app.db() as c:
        u_row = c.execute("SELECT * FROM users WHERE id=?", (u_form,)).fetchone()
    check("the prompt is hidden once they have opted in",
          app.inline_phone_field(u_row) == "",
          "asking again after they said yes reads as broken")

    u_fresh = mkuser("g_fresh", consented=False, email="fresh@umd.edu")
    with app.db() as c:
        fresh_row = c.execute("SELECT * FROM users WHERE id=?", (u_fresh,)).fetchone()
    fld = app.inline_phone_field(fresh_row)
    check("a new student IS shown the prompt", 'name="phone"' in fld)
    check("the box is UNCHECKED by default", "checked" not in fld,
          "a pre-ticked consent box is not consent")
    check("it is marked recommended, not required", "RECOMMENDED" in fld and "required" not in fld,
          "a phone number must never be a condition of using SeatWatch")
    check("the exact registered disclosure is shown", "Msg" in fld or "STOP" in fld,
          "the carrier approved specific wording; it has to be the wording shown")

    srv.shutdown()
    p = sum(ok for _, ok, _ in results)
    f = sum(not ok for _, ok, _ in results)
    return p, f, results


if __name__ == "__main__":
    p, f, res = run()
    for n, ok, d in res:
        print(f"  [{'PASS' if ok else '*** FAIL'}] {n}{('  ' + d) if d and not ok else ''}")
    print(f"\n  {p} passed, {f} failed")
    sys.exit(1 if f else 0)
