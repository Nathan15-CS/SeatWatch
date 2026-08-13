"""READINESS #13 — per-user channel preferences cannot strand a student.

A student should be able to stop receiving the same seat alert two ways. But this
feature's failure mode is the worst one we have: a preference that silences every channel
produces a watch that LOOKS active, generates an alert, delivers it nowhere, and tells
nobody — including us — that the seat was missed.

That is not hypothetical. A paid account really did sit in exactly that state: push
enabled, email and text off, and no push subscription ever registered. It passed the old
floor, because push counted toward it. A seat opened, an alert fired, and it reached
nobody. Push is now retired for students, and this suite pins the three things that stop
that from happening again:

  THE FLOOR    at least one channel that can reach a person must stay enabled, enforced
               SERVER-SIDE. A UI-only guard is bypassed by anyone who can craft a POST.
               Only email and a CONSENTED number count — never push.

  THE RESCUE   the migration that retires push must switch email back on for any account
               push was the only channel for. Retiring a channel without this would
               silently strand exactly the accounts it was meant to fix.

  THE LATCH    a watch may only latch when a channel that reaches a human delivered.
               ntfy returning 200 is not that: publishing to a topic with no listener
               succeeds. If ntfy could latch, the seat is marked handled and lost.
"""
import os, sys, tempfile, time, warnings

warnings.filterwarnings("ignore")


def run():
    os.environ["SEATWATCH_DB"] = os.path.join(tempfile.mkdtemp(), "np.db")
    sys.path.insert(0, os.path.expanduser("~/seatwatch"))
    import app, guardian
    app.init_db()

    results = []
    def check(n, c, d=""): results.append((n, bool(c), d))

    with app.db() as c:
        c.execute("INSERT INTO users(google_sub,email,topic,created) "
                  "VALUES('g_np','np@umd.edu','t_np',0)")
        uid = c.execute("SELECT id FROM users WHERE google_sub='g_np'").fetchone()["id"]
        # A leftover push subscription. It must not entitle this account to anything.
        c.execute("INSERT INTO push_subs(user_id,endpoint,p256dh,auth,created) "
                  "VALUES(?,?,?,?,?)", (uid, "https://push.test/np", "k", "a", time.time()))

    # ---- push is gone from the contract, email and text are not ----
    check("existing accounts read as email+text on, push off",
          app.notify_prefs(uid) == (False, True, True),
          "the migration changed what a current user receives")
    check("an anonymous/absent user reads as reachable", app.notify_prefs(None) == (False, True, True))
    check("an unknown user id fails OPEN, not closed", app.notify_prefs(999999) == (False, True, True),
          "failing closed here would silently stop alerting somebody")
    with app.db() as c:
        c.execute("UPDATE users SET notify_push=1 WHERE id=?", (uid,))
    check("a stored notify_push=1 is IGNORED, never revived",
          app.notify_prefs(uid)[0] is False,
          "an old column value could quietly put an account back on a dead channel")

    def setprefs(email, sms=1):
        with app.db() as c:
            c.execute("UPDATE users SET notify_email=?, notify_sms=? WHERE id=?",
                      (int(email), int(sms), uid))
            # Each scenario below is a FRESH question about preferences, asked of the same
            # watch. The repeat-alert cooldown would suppress every call after the first,
            # so the ledger is cleared between scenarios — otherwise this suite measures
            # the storm fix rather than the preference logic it is named for.
            c.execute("DELETE FROM alert_log")

    # ---- the sender honours the preference ----
    sent = {"push": 0, "email": 0, "sms": 0}
    app.EMAIL_ENABLED = True
    app.send_web_push = lambda u, t, b, url: (sent.__setitem__("push", sent["push"] + 1), 1)[1]
    app.send_email = lambda to, s, b, u=None, **k: (sent.__setitem__("email", sent["email"] + 1), True)[1]
    app.send_sms = lambda *a, **k: (sent.__setitem__("sms", sent["sms"] + 1), True)[1]
    app.sw.notify = lambda *a, **k: False

    class R(dict):
        def keys(self): return list(super().keys())
    with app.db() as c:
        c.execute("INSERT INTO watches(school,topic,course,section,term,alerted,created,user_id) "
                  "VALUES('umd','t_np','CHEM231','0101','202608',0,?,?)", (time.time(), uid))
        w = dict(c.execute("SELECT * FROM watches WHERE topic='t_np'").fetchone())
    r = R(w)

    setprefs(True, 1); sent.update(push=0, email=0, sms=0)
    app._alert(r, "2 seats open", "https://x.test/reg")
    check("both on: email AND text both attempted", sent["email"] == 1 and sent["sms"] == 1,
          f"got {sent}")
    check("PUSH IS NEVER ATTEMPTED, whatever the account says", sent["push"] == 0,
          "a retired channel that still fires is a channel we cannot reason about")

    setprefs(False, 1); sent.update(push=0, email=0, sms=0)
    app._alert(r, "2 seats open", "https://x.test/reg")
    check("email off: email NOT attempted, text still is",
          sent["email"] == 0 and sent["sms"] == 1, f"got {sent}")

    setprefs(True, 0); sent.update(push=0, email=0, sms=0)
    app._alert(r, "2 seats open", "https://x.test/reg")
    check("text off: text NOT attempted, email still is",
          sent["email"] == 1 and sent["sms"] == 0, f"got {sent}")

    # ---- THE RESCUE: retiring push must not strand the accounts it was the only channel for
    with app.db() as c:
        c.execute("INSERT INTO users(google_sub,email,topic,created,notify_push,notify_email,"
                  "notify_sms) VALUES('g_str','stranded@umd.edu','t_str',0,1,0,0)")
        stranded = c.execute("SELECT id FROM users WHERE google_sub='g_str'").fetchone()["id"]
        # ...and someone with no address at all, who cannot be rescued by email.
        c.execute("INSERT INTO users(google_sub,email,topic,created,notify_push,notify_email,"
                  "notify_sms) VALUES('g_noe','','t_noe',0,1,0,0)")
        noemail = c.execute("SELECT id FROM users WHERE google_sub='g_noe'").fetchone()["id"]
    check("before migration the stranded account has NO reachable channel",
          app.notify_prefs(stranded) == (False, False, False))
    app.init_db()                                    # re-run: migrations must be idempotent
    check("RESCUE: push-only account gets email switched back on",
          app.notify_prefs(stranded) == (False, True, False),
          "retiring push would otherwise silently strand this student forever")
    check("RESCUE: an account with no address is left alone, not faked reachable",
          app.notify_prefs(noemail) == (False, False, False),
          "turning on a channel with no destination is a different kind of unreachable")
    app.init_db()
    check("RESCUE is idempotent (a second run changes nothing)",
          app.notify_prefs(stranded) == (False, True, False))

    # ---- THE LATCH: only a channel that reaches a human may latch a watch ----
    state, pages = {}, []
    guardian.configure(app.db, lambda k, d=None: state.get(k, d),
                       lambda **kv: state.update(kv), lambda *a: None,
                       lambda m: pages.append(m), mode="enforce", deploy_sha="")

    setprefs(True, 1)
    check("[enforce] delivered by email -> latches",
          guardian.latch_decision(r, False, 0, True, False) is True)
    check("[enforce] delivered by text -> latches",
          guardian.latch_decision(r, False, 0, False, True) is True)
    check("[enforce] nothing delivered -> does NOT latch",
          guardian.latch_decision(r, False, 0, False, False) is False,
          "a watch that reached nobody must retry, not latch")
    check("[enforce] ntfy alone does NOT latch",
          guardian.latch_decision(r, True, 0, False, False) is False,
          "a topic publish with no listener would mark the seat handled and lose it")

    # ---- THE FLOOR, through the REAL endpoint ----
    # Tested over a socket, not by calling a helper, because the guard has to hold against
    # a hand-crafted POST. Anyone can uncheck both boxes in devtools and submit.
    import threading, urllib.request, urllib.error
    from urllib.parse import urlencode
    from http.server import ThreadingHTTPServer

    srv = ThreadingHTTPServer(("127.0.0.1", 0), app.Handler)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    port = srv.server_address[1]
    cookie = app.session_cookie(uid).split(";")[0]
    csrf = app.csrf_token(uid)

    class _NoRedirect(urllib.request.HTTPRedirectHandler):
        def redirect_request(self, *a, **k): return None

    def post(fields):
        """POST the form and return what the STUDENT would end up reading.

        The app answers a successful POST with 303 + a signed flash cookie (POST/Redirect/
        GET, so the back button never re-submits). urllib does not carry that cookie to the
        redirect target, so following it automatically lands on a page with the message
        stripped out. An earlier version of this test matched 'at least one' against the
        page's own static copy instead and passed no matter what the handler decided —
        it would not have caught a floor that silently stopped refusing. So: capture the
        flash cookie, then fetch the destination with it, exactly as a browser does.
        """
        opener = urllib.request.build_opener(_NoRedirect)
        req = urllib.request.Request(
            f"http://127.0.0.1:{port}/notify-prefs",
            data=urlencode([("csrf", csrf)] + fields).encode(),
            headers={"Content-Type": "application/x-www-form-urlencoded", "Cookie": cookie})
        try:
            resp = opener.open(req, timeout=10)
            status, body, hdrs = resp.status, resp.read().decode("utf-8", "replace"), resp.headers
        except urllib.error.HTTPError as e:
            status, body, hdrs = e.code, e.read().decode("utf-8", "replace"), e.headers
        if status not in (302, 303):
            return body                                  # rendered inline (error path)
        flash = [v.split(";")[0] for v in hdrs.get_all("Set-Cookie") or []
                 if v.startswith("sw_flash=") and not v.startswith("sw_flash=;")]
        follow = urllib.request.Request(
            f"http://127.0.0.1:{port}{hdrs.get('Location', '/')}",
            headers={"Cookie": "; ".join([cookie] + flash)})
        try:
            with urllib.request.urlopen(follow, timeout=10) as r2:
                return r2.read().decode("utf-8", "replace")
        except urllib.error.HTTPError as e:
            return e.read().decode("utf-8", "replace")

    setprefs(True, 1)
    body = post([])                                     # both unchecked = both omitted
    check("POST with NO channels is refused", "at least one" in body.lower(),
          "a crafted POST could silence every channel")
    check("...and the refusal did not persist", app.notify_prefs(uid) == (False, True, True),
          "the rejected state was written anyway")

    # Push must not satisfy the floor. This is the exact POST that stranded a paid account:
    # every real channel off, push on. It has to be REFUSED now.
    body = post([("notify_push", "1")])
    check("POST with push only is REFUSED", "at least one" in body.lower(),
          "push satisfying the floor is what left a paying student unreachable")
    check("...and push-only did not persist", app.notify_prefs(uid) == (False, True, True))

    body = post([("notify_email", "1")])
    check("POST with email only is accepted", app.notify_prefs(uid)[1:] == (True, False),
          f"got {app.notify_prefs(uid)}")

    # Text alone counts only for someone who actually consented — otherwise a student could
    # switch off their only real channel by ticking a box for a number we do not have.
    body = post([("notify_sms", "1")])
    check("text-only is REFUSED without consent on file", "at least one" in body.lower(),
          "a number we never confirmed cannot hold up the floor")
    with app.db() as c:
        c.execute("INSERT INTO sms_consent(user_id,phone,wording,ip,requested_at,confirmed_at) "
                  "VALUES(?,?,?,?,?,?)", (uid, "+15551230000", "w", "1.1.1.1", 0, time.time()))
    body = post([("notify_sms", "1")])
    check("text-only IS accepted once consent exists", app.notify_prefs(uid)[1:] == (False, True),
          f"got {app.notify_prefs(uid)}")

    # having saved a single-channel state, try to remove the last one
    body = post([])
    check("cannot remove the LAST remaining channel", "at least one" in body.lower()
          and app.notify_prefs(uid)[1:] == (False, True),
          "a student could end up with no reachable channel at all")

    bad = urllib.request.Request(
        f"http://127.0.0.1:{port}/notify-prefs",
        data=urlencode([("csrf", "forged"), ("notify_email", "1")]).encode(),
        headers={"Content-Type": "application/x-www-form-urlencoded", "Cookie": cookie})
    try:
        with urllib.request.urlopen(bad, timeout=10) as r:
            btext = r.read().decode("utf-8", "replace")
    except urllib.error.HTTPError as e:
        btext = e.read().decode("utf-8", "replace")
    check("a forged CSRF token is rejected", "expired" in btext.lower(),
          "preferences could be changed cross-site")

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
