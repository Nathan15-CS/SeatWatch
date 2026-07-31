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
    check("promo carries the code", mails and app.PROMO_CODE in mails[0][2])

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

    p = sum(ok for _, ok, _ in results)
    f = sum(not ok for _, ok, _ in results)
    return p, f, results


if __name__ == "__main__":
    p, f, res = run()
    for n, ok, d in res:
        print(f"  [{'PASS' if ok else '*** FAIL'}] {n}{('  ' + d) if d and not ok else ''}")
    print(f"\n  {p} passed, {f} failed")
    sys.exit(1 if f else 0)
