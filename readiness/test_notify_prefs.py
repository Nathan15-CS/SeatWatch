"""READINESS #13 — per-user channel preferences cannot strand a student.

A student who is paying should be able to stop receiving the same seat alert three ways.
But this feature's failure mode is the worst one we have: a preference that silences every
channel produces a watch that LOOKS active, generates an alert, delivers it nowhere, and
tells nobody — including us — that the seat was missed.

Two things are pinned here, and the second is the one that breaks quietly:

  THE FLOOR   at least one channel must stay enabled, enforced SERVER-SIDE. A UI-only
              guard is bypassed by anyone who can craft a POST.

  THE LATCH   guardian.latch_decision treats an account as needing human-channel delivery
              when it has push or email "enrolled". A channel the user switched OFF is one
              we never attempt, so counting it as enrolled makes the honest latch demand
              delivery on a channel that was never tried. In shadow that logs divergences
              that are not real; under enforcement a correctly-delivered alert fails to
              latch and the watch re-fires every cycle forever.
              So enrolled must mean ENROLLED AND ENABLED.
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
        c.execute("INSERT INTO push_subs(user_id,endpoint,p256dh,auth,created) "
                  "VALUES(?,?,?,?,?)", (uid, "https://push.test/np", "k", "a", time.time()))

    # ---- migration is behaviour-neutral for everyone who already exists ----
    check("existing accounts default to BOTH channels on",
          app.notify_prefs(uid) == (True, True, True),
          "the migration changed what a current user receives")
    check("an anonymous/absent user reads as both on", app.notify_prefs(None) == (True, True, True))
    check("an unknown user id fails OPEN, not closed", app.notify_prefs(999999) == (True, True, True),
          "failing closed here would silently stop alerting somebody")

    def setprefs(push, email, sms=1):
        with app.db() as c:
            c.execute("UPDATE users SET notify_push=?, notify_email=?, notify_sms=? WHERE id=?",
                      (int(push), int(email), int(sms), uid))

    # ---- the sender honours the preference ----
    sent = {"push": 0, "email": 0}
    app.EMAIL_ENABLED = True
    app.send_web_push = lambda u, t, b, url: (sent.__setitem__("push", sent["push"] + 1), 1)[1]
    app.send_email = lambda to, s, b, u: (sent.__setitem__("email", sent["email"] + 1), True)[1]
    app.send_sms = lambda *a, **k: False
    app.sw.notify = lambda *a, **k: False

    class R(dict):
        def keys(self): return list(super().keys())
    with app.db() as c:
        c.execute("INSERT INTO watches(school,topic,course,section,term,alerted,created) "
                  "VALUES('umd','t_np','CHEM231','0101','202608',0,?)", (time.time(),))
        w = dict(c.execute("SELECT * FROM watches WHERE topic='t_np'").fetchone())
    w["user_id"] = uid
    r = R(w)

    setprefs(True, True); sent.update(push=0, email=0)
    app._alert(r, "2 seats open", "https://x.test/reg")
    check("both on: push AND email both attempted", sent["push"] == 1 and sent["email"] == 1,
          f"got {sent}")

    setprefs(True, False); sent.update(push=0, email=0)
    app._alert(r, "2 seats open", "https://x.test/reg")
    check("email off: email NOT attempted, push still is",
          sent["push"] == 1 and sent["email"] == 0, f"got {sent}")

    setprefs(False, True); sent.update(push=0, email=0)
    app._alert(r, "2 seats open", "https://x.test/reg")
    check("push off: push NOT attempted, email still is",
          sent["push"] == 0 and sent["email"] == 1, f"got {sent}")

    # ---- THE LATCH: a disabled channel must not be treated as enrolled ----
    state, pages = {}, []
    guardian.configure(app.db, lambda k, d=None: state.get(k, d),
                       lambda **kv: state.update(kv), lambda *a: None,
                       lambda m: pages.append(m), mode="enforce", deploy_sha="")

    setprefs(True, True)
    check("[enforce] both on, delivered by push -> latches",
          guardian.latch_decision(r, False, 1, False, False) is True)
    check("[enforce] both on, nothing delivered -> does NOT latch",
          guardian.latch_decision(r, False, 0, False, False) is False,
          "a watch that reached nobody must retry, not latch")

    # email OFF, and email is the only thing that didn't deliver: push did.
    setprefs(True, False)
    check("[enforce] email disabled + push delivered -> latches",
          guardian.latch_decision(r, False, 1, False, False) is True)

    # BOTH the real coupling test: push disabled AND no push sub attempted, email disabled,
    # only ntfy succeeded. With enrolled==enrolled-and-enabled this account has no enabled
    # human channel, so ntfy alone is honest and must latch.
    setprefs(False, False)          # DB-level only; the handler refuses this state
    check("[enforce] all human channels disabled -> ntfy alone latches",
          guardian.latch_decision(r, True, 0, False, False) is True,
          "correctly-delivered alerts would fail to latch and re-fire every cycle")

    setprefs(True, True)
    check("[enforce] channels enabled but only ntfy fired -> does NOT latch",
          guardian.latch_decision(r, True, 0, False, False) is False,
          "ntfy is not proof a human was reached when a real channel is enrolled")

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

    def post(fields):
        req = urllib.request.Request(
            f"http://127.0.0.1:{port}/notify-prefs",
            data=urlencode([("csrf", csrf)] + fields).encode(),
            headers={"Content-Type": "application/x-www-form-urlencoded", "Cookie": cookie})
        try:
            with urllib.request.urlopen(req, timeout=10) as r:
                return r.read().decode("utf-8", "replace")
        except urllib.error.HTTPError as e:
            return e.read().decode("utf-8", "replace")

    setprefs(True, True)
    body = post([])                                     # both unchecked = both omitted
    check("POST with NO channels is refused", "at least one" in body.lower(),
          "a crafted POST could silence every channel")
    check("...and the refusal did not persist", app.notify_prefs(uid) == (True, True, True),
          "the rejected state was written anyway")

    body = post([("notify_push", "1")])
    check("POST with push only is accepted", app.notify_prefs(uid)[:2] == (True, False),
          f"got {app.notify_prefs(uid)}")
    body = post([("notify_email", "1")])
    check("POST with email only is accepted", app.notify_prefs(uid)[:2] == (False, True),
          f"got {app.notify_prefs(uid)}")

    # having already saved a single-channel state, try to remove the last one
    body = post([])
    check("cannot remove the LAST remaining channel", "at least one" in body.lower()
          and app.notify_prefs(uid)[:2] == (False, True),
          "a student could end up with no reachable channel at all")

    bad = urllib.request.Request(
        f"http://127.0.0.1:{port}/notify-prefs",
        data=urlencode([("csrf", "forged"), ("notify_push", "1")]).encode(),
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
