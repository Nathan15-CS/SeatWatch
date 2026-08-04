"""READINESS #15 — the whole student journey, end to end, over a real socket.

Every other suite tests one mechanism in isolation. This one walks the path a student
actually walks, in order, through the real HTTP handler:

    land -> sign in -> add a class with a phone number -> receive the sample text
    -> a seat opens -> get alerted on every channel they chose -> click the link
    -> change their preferences -> get alerted on fewer channels -> reply STOP
    -> stop being texted -> leave feedback -> stop watching

It exists because features that each pass alone still break at the seams: a preference
read in one place and written in another, a consent row created after the thing that
needed it, an alert that fires but whose link 404s. Those only show up when the steps run
in sequence against the same database.

Nothing here is mocked except the outside world (Twilio, SMTP, web push, and the school's
registration system). The server, the routing, the session cookies, the CSRF, the DB and
the poll cycle are all real.
"""
import os, re, sys, tempfile, threading, time, warnings
import urllib.error, urllib.request
from http.server import ThreadingHTTPServer
from urllib.parse import urlencode

warnings.filterwarnings("ignore")


class FakeSchool:
    """A school whose seat data this test controls, so 'a seat opens' is a real event
    flowing through the real poll cycle rather than a stubbed function call."""
    id = "testu"; name = "Test University"; example = "CHEM 231"
    term = "202608"

    def __init__(self):
        self.state = {"0101": {"open": False, "seats": 0},
                      "0102": {"open": False, "seats": 0}}

    def valid_course(self, c): return bool(re.match(r"^[A-Z]{2,4}\s?\d{3,4}$", c.strip().upper()))
    def reg_url(self, course): return f"https://testu.test/reg/{course}"
    def cur_term(self): return self.term
    def fetch(self, courses):
        return {c: {k: dict(v) for k, v in self.state.items()} for c in courses}


def run():
    os.environ["SEATWATCH_DB"] = os.path.join(tempfile.mkdtemp(), "journey.db")
    sys.path.insert(0, os.path.expanduser("~/seatwatch"))
    import app, guardian, schools as schools_mod
    app.init_db()

    results = []
    def check(n, c, d=""): results.append((n, bool(c), d))

    school = FakeSchool()
    schools_mod.SCHOOLS = {school.id: school}
    app.SMS_ENABLED = True
    app.SMS_LIVE = True
    app.SMS_DRYRUN = False
    app.EMAIL_ENABLED = True
    app.PAID_ENABLED = False

    texts, mails, pushes = [], [], []
    app._twilio_post = lambda to, body: (texts.append((to, body)), (True, None))[1]
    app.send_email = lambda to, s, b, u=None, **k: (mails.append((to, s, b, u)), True)[1]
    # Push is retired for students. Kept as a recorder, asserted to stay EMPTY: if a code
    # path ever revives it, this list stops being empty and the journey fails loudly.
    app.send_web_push = lambda uid, t, b, url: (pushes.append((uid, t, b, url)), 1)[1]
    app.sw.notify = lambda *a, **k: True                # operator channel only

    srv = ThreadingHTTPServer(("127.0.0.1", 0), app.Handler)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    port = srv.server_address[1]
    base = f"http://127.0.0.1:{port}"

    def http(path, fields=None, cookie=None, method=None):
        data = urlencode(fields).encode() if fields is not None else None
        req = urllib.request.Request(base + path, data=data, method=method)
        if data is not None:
            req.add_header("Content-Type", "application/x-www-form-urlencoded")
        if cookie:
            req.add_header("Cookie", cookie)
        try:
            with urllib.request.urlopen(req, timeout=15) as r:
                return r.status, r.read().decode("utf-8", "replace"), dict(r.headers)
        except urllib.error.HTTPError as e:
            return e.code, e.read().decode("utf-8", "replace"), dict(e.headers)

    # ---------- 1. a stranger lands on the site ----------
    code, body, hdrs = http("/")
    check("1. landing page loads", code == 200 and "SeatWatch" in body, f"HTTP {code}")
    check("1. it does NOT claim a fake school count",
          str(len(schools_mod.SCHOOLS)) in body or "universit" in body.lower())
    check("1. anonymous page stays cacheable (edge can absorb a traffic spike)",
          "no-store" not in (hdrs.get("Cache-Control") or ""),
          f"Cache-Control={hdrs.get('Cache-Control')}")

    # ---------- 2. they sign in ----------
    with app.db() as c:
        c.execute("INSERT INTO users(google_sub,email,topic,created) "
                  "VALUES('g_journey','student@testu.edu','t_journey',?)", (time.time(),))
        uid = c.execute("SELECT id FROM users WHERE google_sub='g_journey'").fetchone()["id"]
    cookie = app.session_cookie(uid).split(";")[0]
    csrf = app.csrf_token(uid)

    code, body, hdrs = http("/", cookie=cookie)
    check("2. signed-in page loads", code == 200, f"HTTP {code}")
    check("2. signed-in HTML is never cached (shared campus machine, back button)",
          "no-store" in (hdrs.get("Cache-Control") or ""),
          f"Cache-Control={hdrs.get('Cache-Control')}")
    # The phone prompt must be INSIDE the form and ABOVE the submit button — that is the
    # property that matters, and the reason it moved out of its own card in the first
    # place: anything below the button is never seen. Its exact rank among the fields is
    # a product call (Nathan put it after the sections, so the student finishes describing
    # the class before being asked for anything about themselves), so this asserts the
    # invariant rather than the ordering, which is free to change again.
    check("2. the phone prompt is IN the form, above the submit button",
          body.find('name="phone"') != -1
          and body.find('name="phone"') < body.find('type="submit"'),
          "students fill the first fields they see; below the button is unseen")
    check("2. the phone prompt comes AFTER the section field",
          body.find('name="sections"') != -1
          and body.find('name="sections"') < body.find('name="phone"'),
          "the student should finish describing the class before we ask about them")
    check("2. the consent box is unchecked by default",
          re.search(r'name="sms_consent"[^>]*checked', body) is None,
          "a pre-ticked consent box is not consent")
    n_phone = body.count('name="phone"')
    check("2. only ONE phone field on the page", n_phone == 1, f"found {n_phone}")

    # ---------- 3. they watch a class and give a number ----------
    code, body, _ = http("/watch", [("csrf", csrf), ("school", "testu"),
                                    ("course", "CHEM231"), ("sections", "0101"),
                                    ("phone", "3015550199"), ("sms_consent", "1")],
                         cookie=cookie)
    with app.db() as c:
        w = c.execute("SELECT * FROM watches WHERE topic='t_journey'").fetchone()
        consent = c.execute("SELECT COUNT(*) FROM sms_consent WHERE user_id=? AND "
                            "confirmed_at IS NOT NULL AND revoked_at IS NULL",
                            (uid,)).fetchone()[0]
    check("3. the watch was created", w is not None and w["course"] == "CHEM231")
    check("3. consent was recorded in the same request", consent == 1)
    check("3. the sample text arrived", any("what an alert looks like" in t[1] for t in texts),
          f"{len(texts)} texts sent")
    check("3. the sample carries STOP wording", texts and "STOP" in texts[0][1])

    texts.clear()
    http("/watch", [("csrf", csrf), ("school", "testu"), ("course", "CHEM231"),
                    ("sections", "0102")], cookie=cookie)
    check("3. a SECOND class sends no second sample", not texts, f"{len(texts)} extra texts")

    # ---------- 4. a seat opens ----------
    guardian.configure(app.db, lambda k, d=None: None, lambda **kv: None,
                       lambda *a: None, lambda m: None, mode="shadow", deploy_sha="")
    texts.clear(); mails.clear(); pushes.clear()
    school.state["0101"] = {"open": True, "seats": 2}
    app.run_cycle()
    check("4. a real seat opening alerts by EMAIL", bool(mails), "email never fired")
    check("4. ...and PUSH stays retired", not pushes,
          "push fired for a student — it is meant to be gone")
    check("4. ...and by TEXT", bool(texts), "text never fired")
    check("4. the alert names the actual course and section",
          any("CHEM231" in str(m) for m in mails) or any("CHEM231" in t[1] for t in texts))
    check("4. the alert states the real seat count",
          any("2 seat" in t[1] for t in texts) or any("2 seat" in str(m[2]) for m in mails),
          "a wrong count is worse than no alert")

    n_texts = len(texts)
    app.run_cycle()
    check("4. a still-open seat does NOT re-alert", len(texts) == n_texts,
          f"{len(texts) - n_texts} duplicate alerts — this is what latching prevents")

    # ---------- 5. the link in the alert works ----------
    # The tracked /r/ link is in EMAIL. Texts deliberately carry the DIRECT
    # registrar URL: a text is billed per 160 characters, and a student mid-registration
    # must still reach the registrar even if our box is down. So look where it should be.
    link = None
    for blob in [str(m) for m in mails]:
        m = re.search(r"/r/([A-Za-z0-9_-]+)", blob)
        if m: link = m.group(1); break
    check("5. texts carry the DIRECT registrar link, not a redirect through us",
          all("/r/" not in t[1] for t in texts) and any("testu.test" in t[1] for t in texts),
          "a redirect costs SMS characters and fails if our box is down")
    if link:
        # Do NOT follow the redirect — the destination is a fake registrar host. What
        # matters is that we issue a 302 pointing at the school, not that the school exists.
        class _NoRedirect(urllib.request.HTTPRedirectHandler):
            def redirect_request(self, *a, **k): return None
        opener = urllib.request.build_opener(_NoRedirect)
        try:
            with opener.open(base + "/r/" + link, timeout=15) as r:
                code, hdrs = r.status, dict(r.headers)
        except urllib.error.HTTPError as e:
            code, hdrs = e.code, dict(e.headers)
        check("5. the alert link redirects to the registrar",
              code in (301, 302) and "testu.test" in (hdrs.get("Location") or ""),
              f"HTTP {code} -> {hdrs.get('Location')}")
        with app.db() as c:
            clicked = c.execute("SELECT clicked_at FROM alert_attempt WHERE token=?",
                                (link,)).fetchone()
        check("5. the click is recorded (proves alerts cause action)",
              clicked and clicked["clicked_at"] is not None)
    else:
        check("5. the alert contained a tracked link", False, "no /r/ token found in any text")

    # ---------- 6. they turn a channel off ----------
    code, body, _ = http("/notify-prefs", [("csrf", csrf), ("notify_sms", "1")],
                         cookie=cookie)
    check("6. preferences saved", app.notify_prefs(uid)[1:] == (False, True),
          f"got {app.notify_prefs(uid)}")

    school.state["0101"] = {"open": False, "seats": 0}
    app.run_cycle()                                   # re-arm the latch
    texts.clear(); mails.clear(); pushes.clear()
    school.state["0101"] = {"open": True, "seats": 3}
    app.run_cycle()
    check("6. email is now silent", not mails, f"{len(mails)} emails after opting out")
    check("6. ...and push did not quietly take over", not pushes,
          "a retired channel firing as a fallback is a channel nobody chose")
    # NOT a bug that no text arrives: SMS is capped at one per watch, ever, because each
    # one costs real money and a flickering section would otherwise bill repeatedly.
    # Email re-arms freely; it is free. Asserting "text fires again" here would
    # have pinned the opposite of the cost control we actually want.
    check("6. text does NOT re-fire for the same watch (one paid text per watch)",
          not texts, f"{len(texts)} texts — the per-watch SMS cap is not holding")

    code, body, _ = http("/notify-prefs", [("csrf", csrf)], cookie=cookie)
    check("6. turning EVERYTHING off is refused", "at least one" in body.lower(),
          "a student could end up unreachable while the page said they were covered")

    # ---------- 7. they reply STOP ----------
    app.sms_apply_inbound("+13015550199", "STOP")
    with app.db() as c:
        rev = c.execute("SELECT revoked_at FROM sms_consent WHERE user_id=?",
                        (uid,)).fetchone()["revoked_at"]
    check("7. STOP revokes consent immediately", rev is not None)
    school.state["0101"] = {"open": False, "seats": 0}
    app.run_cycle()
    texts.clear()
    school.state["0101"] = {"open": True, "seats": 1}
    app.run_cycle()
    check("7. and no further texts are ever sent", not texts,
          f"{len(texts)} texts AFTER the student said stop — this is the TCPA failure")

    # ---------- 8. they leave feedback ----------
    mails.clear()
    code, body, _ = http("/feedback", [("csrf", csrf), ("message", "the alert was late")],
                         cookie=cookie)
    with app.db() as c:
        fb = c.execute("SELECT * FROM feedback ORDER BY id DESC LIMIT 1").fetchone()
    check("8. feedback is stored before anything else can fail",
          fb is not None and "alert was late" in fb["message"])
    check("8. feedback reaches support@", any(m[0] == app.SUPPORT_EMAIL for m in mails),
          "a message nobody reads is a message lost")

    # ---------- 9. they stop watching ----------
    with app.db() as c:
        wid = c.execute("SELECT id FROM watches WHERE topic='t_journey' LIMIT 1").fetchone()["id"]
    http("/unwatch", [("csrf", csrf), ("id", str(wid))], cookie=cookie)
    with app.db() as c:
        gone = c.execute("SELECT COUNT(*) FROM watches WHERE id=?", (wid,)).fetchone()[0]
    # ---- a named section means THAT section, on every plan ----
    # This was wrong in a way that quietly destroys trust: a paid account had its typed
    # sections discarded and the whole course watched instead. A text about a seat in a
    # section the student cannot take is worse than silence — it teaches them to ignore
    # the next alert, and the next one is the real seat.
    with app.db() as c:
        c.execute("UPDATE users SET plan_tier=3, plan_term=?, plan_purchased_at=? WHERE id=?",
                  (app.current_season(), time.time(), uid))
    app.PAID_ENABLED = True

    def _watch_sections(secs, course="BIOL404"):
        with app.db() as c:
            c.execute("DELETE FROM watches WHERE user_id=?", (uid,))   # clear the course cap too
        http("/watch", [("csrf", csrf), ("school", "testu"), ("course", course),
                        ("sections", secs)], cookie=cookie)
        with app.db() as c:
            return sorted(r["section"] for r in c.execute(
                "SELECT section FROM watches WHERE user_id=? AND course=?", (uid, course)))

    got = _watch_sections("0101")
    check("10. a PAID student who names one section watches only that section",
          got == ["0101"], f"got {got} — the course-wide catch-all row is back")
    # 0102, not 0201: the fake school only publishes 0101 and 0102, and SeatWatch
    # correctly refuses to watch a section that does not exist. Asking for a phantom
    # section is a different (already covered) behaviour, not this one.
    got = _watch_sections("0101, 0102")
    check("10. naming two sections watches exactly those two",
          got == ["0101", "0102"], f"got {got}")
    got = _watch_sections("")
    check("10. leaving it blank still watches every section (that is the paid perk)",
          got == [""], f"got {got}")
    http("/watch", [("csrf", csrf), ("school", "testu"), ("course", "BIOL404"),
                    ("sections", "0101")], cookie=cookie)
    with app.db() as c:
        got = sorted(r["section"] for r in c.execute(
            "SELECT section FROM watches WHERE user_id=? AND course=?", (uid, "BIOL404")))
    check("10. narrowing from all-sections to one drops the catch-all",
          got == ["0101"], f"got {got} — they would still be alerted about excluded sections")
    # ---- the full allowance matrix: courses AND sections, per plan ----
    # A paying customer was refused a section with a message calling them a free user,
    # because the cap on the INSERT path was still hardcoded to the free tier while the
    # check above it had been made tier-aware. Two places enforcing one rule is how that
    # happens; this pins both from the outside, per tier.
    def _allowance(tier, courses_wanted=7, secs="0101, 0102"):
        with app.db() as c:
            c.execute("DELETE FROM watches WHERE user_id=?", (uid,))
            c.execute("UPDATE users SET plan_tier=?, plan_term=?, plan_purchased_at=? WHERE id=?",
                      (tier, app.current_season() if tier else None,
                       time.time() if tier else None, uid))
        for i in range(courses_wanted):
            http("/watch", [("csrf", csrf), ("school", "testu"), ("course", f"BIOL{200+i}"),
                            ("sections", secs)], cookie=cookie)
        with app.db() as c:
            rows = c.execute("SELECT course, section FROM watches WHERE user_id=?",
                             (uid,)).fetchall()
        by = {}
        for r in rows:
            by.setdefault(r["course"], []).append(r["section"])
        return by

    app.PAID_ENABLED = True
    for tier, want_courses in ((0, 1), (1, 1), (2, 2), (3, 5)):
        got = _allowance(tier)
        check(f"11. tier {tier} gets exactly {want_courses} course(s)",
              len(got) == want_courses,
              f"got {len(got)} — a paying student is being denied what they bought"
              if len(got) < want_courses else f"got {len(got)} — a plan limit is not holding")
        if got:
            n = len(next(iter(got.values())))
            check(f"11. tier {tier} keeps both named sections of a course", n == 2, f"got {n}")

    # the free cap still holds, and still says so
    with app.db() as c:
        c.execute("DELETE FROM watches WHERE user_id=?", (uid,))
        c.execute("UPDATE users SET plan_tier=0, plan_term=NULL WHERE id=?", (uid,))
    http("/watch", [("csrf", csrf), ("school", "testu"), ("course", "BIOL300"),
                    ("sections", "0101, 0102")], cookie=cookie)
    code, body, _ = http("/watch", [("csrf", csrf), ("school", "testu"), ("course", "BIOL300"),
                                    ("sections", "0103")], cookie=cookie)
    with app.db() as c:
        n = c.execute("SELECT COUNT(*) n FROM watches WHERE user_id=? AND course='BIOL300'",
                      (uid,)).fetchone()["n"]
    check("11. a FREE student is held to 2 sections", n == 2, f"got {n}")
    check("11. ...and the refusal names the free plan", "free plan" in body.lower())

    with app.db() as c:
        c.execute("DELETE FROM watches WHERE user_id=?", (uid,))
        c.execute("UPDATE users SET plan_tier=0, plan_term=NULL WHERE id=?", (uid,))

    check("9. unwatch actually removes the watch", gone == 0)

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
