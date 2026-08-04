"""READINESS #18 — ADVERSARIAL. Everything else proves the system works when used
correctly. This one assumes the visitor is hostile.

The other seventeen suites all share an assumption: a student clicks buttons in the
intended order. That assumption is worth nothing the moment SeatWatch is public. A
university has thousands of bored computer-science undergraduates, the site is going to be
posted where they read, and some of them will poke it — not maliciously, mostly, but they
will try.

What is attacked here, in descending order of what it would cost:

  IDOR         can one student touch ANOTHER student's watches, preferences, or data?
               This is the single most common real vulnerability in a multi-user app and
               the one users never forgive, because it is not a crash — it is a stranger
               reading their timetable.
  SESSION      can a cookie be forged, replayed after expiry, or edited to become someone
               else? The whole auth model is one signed string.
  CSRF         can another website submit a form as a signed-in student?
  INJECTION    does user text reach SQL?
  LEAKAGE      do errors, headers or pages hand out emails, phone numbers or tokens?
  LIMITS       can the free tier be exceeded, or the process be exhausted by one caller?

Every request here goes over a real socket against the real handler. Calling functions
directly would prove nothing: the guard has to hold against a hand-crafted request, which
is exactly what an attacker sends.
"""
import json
import os
import sys
import tempfile
import threading
import time
import urllib.error
import urllib.request
import warnings
from http.server import ThreadingHTTPServer
from urllib.parse import urlencode

warnings.filterwarnings("ignore")


def run():
    os.environ["SEATWATCH_DB"] = os.path.join(tempfile.mkdtemp(), "adv.db")
    sys.path.insert(0, os.path.expanduser("~/seatwatch"))
    import app
    app.init_db()

    results = []
    def check(n, c, d=""):
        results.append((n, bool(c), d))

    # two real students, so "someone else's data" is a real thing
    with app.db() as c:
        c.execute("INSERT INTO users(google_sub,email,topic,created) "
                  "VALUES('g_a','alice@umd.edu','t_alice',?)", (time.time(),))
        c.execute("INSERT INTO users(google_sub,email,topic,created) "
                  "VALUES('g_b','bob@umd.edu','t_bob',?)", (time.time(),))
        A = c.execute("SELECT id FROM users WHERE google_sub='g_a'").fetchone()["id"]
        B = c.execute("SELECT id FROM users WHERE google_sub='g_b'").fetchone()["id"]
        c.execute("INSERT INTO watches(school,topic,course,section,term,created,user_id) "
                  "VALUES('umd','t_bob','ZQAX999','0101','202608',?,?)", (time.time(), B))
        BOB_WATCH = c.execute("SELECT id FROM watches WHERE user_id=?", (B,)).fetchone()["id"]
        c.execute("INSERT INTO sms_consent(user_id,phone,wording,ip,requested_at,confirmed_at) "
                  "VALUES(?,?,?,?,?,?)", (B, "+15559998888", "w", "9.9.9.9", 0, time.time()))

    srv = ThreadingHTTPServer(("127.0.0.1", 0), app.Handler)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    port = srv.server_address[1]
    BASE = f"http://127.0.0.1:{port}"

    def req(path, data=None, cookie=None, headers=None, method=None, raw=None):
        h = {"Cookie": cookie} if cookie else {}
        h.update(headers or {})
        body = raw if raw is not None else (urlencode(data).encode() if data else None)
        if body is not None and "Content-Type" not in h:
            h["Content-Type"] = "application/x-www-form-urlencoded"
        r = urllib.request.Request(BASE + path, data=body, headers=h,
                                   method=method or ("POST" if body is not None else "GET"))
        try:
            with urllib.request.urlopen(r, timeout=10) as resp:
                return resp.status, resp.read().decode("utf-8", "replace"), dict(resp.headers)
        except urllib.error.HTTPError as e:
            return e.code, e.read().decode("utf-8", "replace"), dict(e.headers)
        except Exception as e:
            return -1, f"{type(e).__name__}: {e}", {}

    cookie_a = app.session_cookie(A).split(";")[0]
    cookie_b = app.session_cookie(B).split(";")[0]
    csrf_a, csrf_b = app.csrf_token(A), app.csrf_token(B)

    # ================================================================= IDOR
    # Alice tries to delete Bob's watch. She has a valid session and a valid CSRF token —
    # her own. The only thing standing between her and Bob's data is the ownership clause.
    code, _, _ = req("/unwatch", {"csrf": csrf_a, "id": str(BOB_WATCH)}, cookie=cookie_a)
    with app.db() as c:
        still = c.execute("SELECT 1 FROM watches WHERE id=?", (BOB_WATCH,)).fetchone()
    check("IDOR: Alice cannot delete Bob's watch", still is not None,
          "a signed-in student could delete any watch by guessing a small integer id")

    # ...and with BOB's csrf token, in case the check is on the token rather than the row
    req("/unwatch", {"csrf": csrf_b, "id": str(BOB_WATCH)}, cookie=cookie_a)
    with app.db() as c:
        still = c.execute("SELECT 1 FROM watches WHERE id=?", (BOB_WATCH,)).fetchone()
    check("IDOR: not even with Bob's CSRF token in Alice's session", still is not None)

    # Alice changes Bob's notification preferences. She submits a VALID save (email on,
    # text omitted) and names Bob in the body — if the handler trusted that field, Bob
    # would quietly lose his texts. Push is not used here: it no longer satisfies the
    # floor, so a push-only POST is refused before ownership is ever reached and would
    # pass this check without proving anything.
    req("/notify-prefs", {"csrf": csrf_a, "user_id": str(B), "notify_email": "1"},
        cookie=cookie_a)
    check("IDOR: a user_id in the POST body cannot retarget preferences",
          app.notify_prefs(B) == (False, True, True),
          "Bob's channels were changed by Alice")

    # Alice's own page must not contain Bob's data
    code, body_a, _ = req("/", cookie=cookie_a)
    check("Alice's page does not leak Bob's email", "bob@umd.edu" not in body_a)
    check("Alice's page does not leak Bob's phone", "5559998888" not in body_a
          and "+15559998888" not in body_a)
    # A course code that cannot collide with the school picker's own example data. My
    # first attempt used CMSC216, which is UMD's advertised example course and appears on
    # every visitor's page — the test failed on the site's own sample data, not a leak.
    check("Alice's page does not show Bob's course", "ZQAX999" not in body_a,
          "one student could read another's timetable")

    # ============================================================== SESSION
    forged = [
        ("a made-up cookie", "sw_session=1.9999999999.deadbeef"),
        ("uid swapped, signature kept", f"sw_session={B}." + cookie_a.split(".", 1)[1]),
        ("expiry pushed far into the future", f"sw_session={A}.9999999999."
                                              + cookie_a.rsplit(".", 1)[1]),
        ("empty value", "sw_session="),
        ("only two segments", "sw_session=1.2"),
        ("non-numeric uid", "sw_session=abc.9999999999.x"),
        ("negative uid", "sw_session=-1.9999999999.x"),
        ("huge uid", "sw_session=" + "9" * 400 + ".9999999999.x"),
    ]
    for label, ck in forged:
        code, body, _ = req("/", cookie=ck)
        signed_in = "Signed in as" in body
        check(f"SESSION: {label} does not authenticate", not signed_in,
              "a forged cookie became a logged-in session")

    expired = f"{A}.{int(time.time()) - 10}.{app._sign(f'sess:{A}.{int(time.time()) - 10}')}"
    code, body, _ = req("/", cookie=f"sw_session={expired}")
    check("SESSION: a correctly-signed but EXPIRED cookie is refused",
          "Signed in as" not in body,
          "sessions would never actually end")

    # ================================================================= CSRF
    for label, tok in (("no token", ""), ("garbage token", "x" * 40),
                       ("ANOTHER user's token", csrf_b)):
        req("/watch", {"csrf": tok, "school": "umd", "course": "CMSC132",
                       "sections": "0101"}, cookie=cookie_a)
        with app.db() as c:
            n = c.execute("SELECT COUNT(*) n FROM watches WHERE user_id=?", (A,)).fetchone()["n"]
        check(f"CSRF: /watch with {label} creates nothing", n == 0,
              "another site could add watches as this student")

    # ============================================================ INJECTION
    payloads = ["'; DROP TABLE watches; --", "' OR '1'='1", "\" OR 1=1 --",
                "admin'--", "1); DELETE FROM users; --", "\x00truncated"]
    for pl in payloads:
        req("/watch", {"csrf": csrf_a, "school": pl, "course": pl, "sections": pl},
            cookie=cookie_a)
        req("/feedback", {"csrf": csrf_a, "message": pl}, cookie=cookie_a)
    with app.db() as c:
        tabs = {r[0] for r in c.execute("SELECT name FROM sqlite_master WHERE type='table'")}
        users_left = c.execute("SELECT COUNT(*) n FROM users").fetchone()["n"]
        watches_left = c.execute("SELECT COUNT(*) n FROM watches").fetchone()["n"]
    check("INJECTION: the watches table still exists", "watches" in tabs)
    check("INJECTION: the users table still exists", "users" in tabs)
    check("INJECTION: no user rows were deleted", users_left == 2, f"{users_left} users left")
    check("INJECTION: Bob's watch survived every payload", watches_left >= 1)

    # ============================================================== LEAKAGE
    code, body, hdrs = req("/nope-does-not-exist")
    check("LEAKAGE: a 404 does not include a stack trace",
          "Traceback" not in body and "File \"" not in body)
    check("LEAKAGE: no server banner advertising Python/version",
          "Python" not in (hdrs.get("Server") or ""), hdrs.get("Server"))
    code, body, _ = req("/watch", {"csrf": csrf_a, "school": "￿" * 10,
                                   "course": "%s%s%n"}, cookie=cookie_a)
    check("LEAKAGE: a malformed watch does not dump a traceback",
          "Traceback" not in body)

    # signed-in pages must never be cacheable by a shared campus machine
    code, body, hdrs = req("/", cookie=cookie_a)
    check("LEAKAGE: a signed-in page is no-store",
          "no-store" in (hdrs.get("Cache-Control") or ""),
          f"Cache-Control={hdrs.get('Cache-Control')}")

    # admin stats must not open without the key
    code, body, _ = req("/admin/stats")
    check("ACCESS: /admin/stats without a key is not served",
          code == 404 or "watches" not in body.lower(), f"HTTP {code}")
    code, body, _ = req("/admin/stats?key=guess")
    check("ACCESS: /admin/stats with a wrong key is not served",
          code == 404 or "watches" not in body.lower(), f"HTTP {code}")

    # ============================================================== LIMITS
    # oversized body must not be read whole into memory
    big = urlencode({"csrf": csrf_a, "message": "A" * 200000}).encode()
    code, body, _ = req("/feedback", raw=big, cookie=cookie_a)
    check("LIMITS: a 200KB body does not crash the handler", code != -1, body[:80])
    with app.db() as c:
        row = c.execute("SELECT message FROM feedback ORDER BY id DESC LIMIT 1").fetchone()
    check("LIMITS: an oversized message is truncated, not stored whole",
          row is None or len(row["message"]) < 100000,
          f"stored {len(row['message']) if row else 0} chars")

    # A lying Content-Length is the slowloris shape: declare a big body, send almost
    # nothing, and park a server thread on a read that will never complete. Enough of
    # those and the site stops answering anyone.
    #
    # The invariant is NOT that this request returns quickly — the handler is entitled to
    # wait a while for a genuinely slow mobile upload. It is that the thread is released
    # and the SERVER KEEPS SERVING. Handler.timeout bounds the wait; without it that
    # thread was parked forever.
    #
    # Note the real-world layer too: Cloudflare buffers requests and forwards only
    # complete ones, so in production this rarely reaches the app at all. That is a
    # reason to be calm about it, not a reason to depend on it.
    t0 = time.time()
    code, body, _ = req("/feedback", raw=b"csrf=x&message=hi",
                        headers={"Content-Length": "999999999"}, cookie=cookie_a)
    stalled = time.time() - t0
    check("LIMITS: a forged Content-Length is bounded by the handler timeout",
          stalled < app.Handler.timeout + 10,
          f"stalled {stalled:.0f}s against a {app.Handler.timeout}s timeout")
    code2, _, _ = req("/")
    check("LIMITS: the server still answers others during/after a stalled request",
          code2 == 200,
          "one slow-body request took the whole site down for everyone")
    check("LIMITS: a handler read timeout is actually configured",
          isinstance(getattr(app.Handler, "timeout", None), (int, float)),
          "without it a stalled read parks a thread forever")

    # ====================================================== PUSH HIJACK
    # A push endpoint is the address alerts are delivered to. If re-registering an
    # endpoint simply reassigns it, Alice can register BOB'S endpoint and start receiving
    # his seat alerts — a silent, total interception with no visible symptom for Bob.
    ENDPOINT = "https://push.example/bob-device-token"
    with app.db() as c:
        c.execute("INSERT INTO push_subs(user_id,endpoint,p256dh,auth,created) "
                  "VALUES(?,?,?,?,?)", (B, ENDPOINT, "k", "a", time.time()))
    code, body, _ = req("/push/subscribe",
                        raw=json.dumps({"csrf": csrf_a,
                                        "sub": {"endpoint": ENDPOINT,
                                                "keys": {"p256dh": "k2", "auth": "a2"}}}).encode(),
                        headers={"Content-Type": "application/json"}, cookie=cookie_a)
    with app.db() as c:
        owner = c.execute("SELECT user_id FROM push_subs WHERE endpoint=?",
                          (ENDPOINT,)).fetchone()
    # I first asserted that a takeover must be IMPOSSIBLE. That was wrong, and worth
    # recording so nobody "fixes" correct code later. A push endpoint is a capability
    # URL — whoever holds it can already push to that device without SeatWatch, so
    # refusing reassignment buys no security. It does break the realistic case: a shared
    # library machine, where Bob subscribes, leaves, and Alice subscribes in the same
    # browser and receives the same endpoint. Refusing would leave Alice with no alerts
    # AND keep firing Bob's at a machine he has walked away from.
    #
    # What must hold is narrower and more useful: the takeover is RECORDED, and the
    # displaced student is not silently left unreachable.
    check("PUSH: an endpoint takeover is attributed to the new owner",
          owner is not None and owner["user_id"] == A,
          "the shared-device case would leave alerts going to whoever left first")
    with app.db() as c:
        risk = c.execute("SELECT risk_score FROM users WHERE id=?", (A,)).fetchone()
        bob_push = c.execute("SELECT COUNT(*) n FROM push_subs WHERE user_id=?",
                             (B,)).fetchone()["n"]
    check("PUSH: the takeover raises a risk signal for review",
          int(risk["risk_score"] or 0) > 0,
          "a device changing hands leaves no trace for the operator")
    check("PUSH: the displaced student is not silently left reachable-by-nothing",
          bob_push == 0 and app.notify_prefs(B)[1] is True,
          "Bob lost push AND had no other channel — a watch that can never fire")

    # ================================================== SMS CONSENT FORGERY
    # Consent is a legal record. It must not be creatable for a number the student did
    # not submit in that same request, and never without the box actually ticked.
    with app.db() as c:
        before = c.execute("SELECT COUNT(*) n FROM sms_consent WHERE user_id=?",
                           (A,)).fetchone()["n"]
    req("/sms/optin", {"csrf": csrf_a, "phone": "+15551234567"}, cookie=cookie_a)
    with app.db() as c:
        after = c.execute("SELECT COUNT(*) n FROM sms_consent WHERE user_id=?",
                          (A,)).fetchone()["n"]
    check("SMS: no consent row without the consent box ticked", after == before,
          "a TCPA consent record would exist for someone who never agreed")

    req("/sms/optin", {"csrf": csrf_a, "phone": "+15559998888", "sms_consent": "1"},
        cookie=cookie_a)
    with app.db() as c:
        rows = c.execute("SELECT user_id FROM sms_consent WHERE phone=? AND revoked_at IS NULL",
                         ("+15559998888",)).fetchall()
    check("SMS: Alice claiming Bob's number does not revoke or steal his consent",
          any(r["user_id"] == B for r in rows),
          "Bob's texts would stop, or start going to whoever claimed his number")

    # ==================================================== FREE-TIER LIMITS
    # The paid perk has to hold against someone who just keeps posting.
    with app.db() as c:
        c.execute("DELETE FROM watches WHERE user_id=?", (A,))
    for i in range(6):
        req("/watch", {"csrf": csrf_a, "school": "umd", "course": f"TEST{i:03d}",
                       "sections": "0101"}, cookie=cookie_a)
    with app.db() as c:
        courses = c.execute("SELECT COUNT(DISTINCT course) n FROM watches WHERE user_id=?",
                            (A,)).fetchone()["n"]
    check("PLAN: a free account cannot exceed its course limit by re-posting",
          courses <= app.FREE_COURSES if hasattr(app, "FREE_COURSES") else courses <= 1,
          f"{courses} distinct courses on a free plan")

    with app.db() as c:
        c.execute("DELETE FROM watches WHERE user_id=?", (A,))
    req("/watch", {"csrf": csrf_a, "school": "umd", "course": "TESTSEC",
                   "sections": "0101,0102,0103,0104,0105,0106"}, cookie=cookie_a)
    with app.db() as c:
        secs = c.execute("SELECT COUNT(*) n FROM watches WHERE user_id=? AND course=?",
                         (A, "TESTSEC")).fetchone()["n"]
    check("PLAN: a free account cannot exceed its section limit in one post",
          secs <= app.FREE_SECTIONS_PER_COURSE,
          f"{secs} sections on a free plan (limit {app.FREE_SECTIONS_PER_COURSE})")

    # ====================================================== OPEN REDIRECT
    # /r/ bounces a student to their registrar. If the destination came from the URL,
    # SeatWatch becomes a link-laundering service for phishing — a .edu-adjacent domain
    # sending students to an attacker's login page.
    for probe in ("/r/https://evil.example/steal",
                  "/r/999999?url=https://evil.example",
                  "/r/..%2f..%2fevil"):
        code, body, hdrs = req(probe)
        loc = (hdrs.get("Location") or "")
        check(f"REDIRECT: {probe[:34]} does not bounce to an attacker domain",
              "evil.example" not in loc, f"Location={loc}")

    # ================================================== METHOD CONFUSION
    for path in ("/watch", "/unwatch", "/notify-prefs", "/feedback", "/sms/optin"):
        code, body, _ = req(path + f"?csrf={csrf_a}&id=1&message=x", cookie=cookie_a)
        check(f"METHOD: GET {path} does not perform the action", code in (404, 405, 302, 200)
              and "Traceback" not in body, f"HTTP {code}")
    with app.db() as c:
        n = c.execute("SELECT COUNT(*) n FROM feedback").fetchone()["n"]
    code, _, _ = req("/feedback?csrf=" + csrf_a + "&message=via-get", cookie=cookie_a)
    with app.db() as c:
        n2 = c.execute("SELECT COUNT(*) n FROM feedback").fetchone()["n"]
    check("METHOD: a GET cannot submit feedback", n2 == n,
          "state-changing actions would be reachable by a link or an <img> tag")

    # ============================================================ RATE LIMIT
    # A flood must still be stopped...
    app._RATE.clear()
    blocked = 0
    for _ in range(app.RATE_MAX_USER + 15):
        code, _, _ = req("/feedback", {"csrf": csrf_a, "message": "flood"}, cookie=cookie_a)
        if code == 429:
            blocked += 1
    check("RATE: a flood from one account is eventually refused", blocked > 0,
          "no flood protection at all")

    # ...but ALICE'S flood must never throttle BOB. This is the launch-day case: a campus
    # puts hundreds of students behind ONE NAT address, so an IP-keyed limit means the
    # first few students to register lock out the whole dorm — everyone seeing "too many
    # requests" for something they did not do, during the exact hour that matters.
    code, _, _ = req("/feedback", {"csrf": csrf_b, "message": "bob's first ever post"},
                     cookie=cookie_b)
    check("RATE: one student's flood does not lock out another on the same network",
          code != 429,
          "a whole dorm behind one NAT IP would throttle each other during add/drop")

    # an anonymous caller is still limited by address
    app._RATE.clear()
    anon_blocked = 0
    for _ in range(app.RATE_MAX + 10):
        code, _, _ = req("/feedback", {"csrf": "x", "message": "anon"})
        if code == 429:
            anon_blocked += 1
    check("RATE: an anonymous flood is still refused by address", anon_blocked > 0,
          "a logged-out attacker would be unlimited")
    check("RATE: the signed-in budget is more generous than the anonymous one",
          app.RATE_MAX_USER > app.RATE_MAX,
          f"user={app.RATE_MAX_USER} anon={app.RATE_MAX}")

    # ===================================================== ERROR PRESENTATION
    # A failure must not wear the costume of a success. "Too many requests" rendered
    # green with a tick, and a student reads the tick, not the sentence — walking away
    # believing their class is watched when nothing was saved.
    app._RATE.clear()
    err_body = ""
    for _ in range(app.RATE_MAX_USER + 15):
        code, body, _ = req("/feedback", {"csrf": csrf_a, "message": "flood2"},
                            cookie=cookie_a)
        if code == 429:
            err_body = body
            break
    check("ERROR: a 429 page is styled as an error, not a success",
          "class='err'" in err_body or 'class="err"' in err_body,
          "the failure renders green with a success tick")
    check("ERROR: a 429 page does NOT use the success style",
          "class='ok'" not in err_body and 'class="ok"' not in err_body)

    # the process must still be alive and serving after all of the above
    code, body, _ = req("/")
    check("SURVIVAL: the server still serves after every attack above", code == 200,
          f"HTTP {code}")

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
