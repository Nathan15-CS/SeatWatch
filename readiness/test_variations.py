"""READINESS #20 — VARIATIONS. Every feature works alone. Do they work TOGETHER?

Each suite before this one tests a feature in isolation, and every bug that has reached a
real user recently lived in the space BETWEEN two of them:

  * the section fix made a second, older section cap reachable for the first time —
    and it still said "your free plan" to a paying customer
  * making POST redirect turned a 429 into a 303, silently deleting the rate-limit signal
  * a rule enforced in two places drifted apart in one of them

So this walks CROSS-PRODUCTS rather than features. It is deliberately repetitive: the
point is that no combination is special, and the ones nobody thought to try are exactly
where the next bug will be.

  A  POST/redirect/GET on EVERY form, not just the one that was reported
  B  no refusal anywhere answers with 200
  C  the watch list reads correctly for every tier x section-mode
  D  the sample channels respect every combination of notification preferences
  E  a plan change preserves what the student was already watching
  F  the alert path, end to end, for each tier x section-mode
"""
import os
import re
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


class FakeSchool:
    id = "varu"; name = "Variations U"; example = "CHEM 231"; term = "202608"

    def __init__(self):
        self.state = {f"{i:04d}": {"open": False, "seats": 0} for i in (101, 102, 103)}

    def valid_course(self, c):
        return bool(re.match(r"^[A-Z]{2,4}\s?\d{3,4}$", c.strip().upper()))

    def reg_url(self, course):
        return "https://varu.test/reg"

    def cur_term(self):
        return self.term

    def fetch(self, courses):
        return {c: {k: dict(v) for k, v in self.state.items()} for c in courses}


def run():
    os.environ["SEATWATCH_DB"] = os.path.join(tempfile.mkdtemp(), "var.db")
    sys.path.insert(0, os.path.expanduser("~/seatwatch"))
    import app, schools
    # Opening confirmation (CONFIRM_SECONDS) is OFF here: this suite drives
    # run_cycle expecting one cycle to equal one alert, and its subject is features in combination,
    # not alert timing. The confirmation contract is owned by test_churn_confirm
    # (real-timeline replay) and exercised through run_cycle by
    # test_alert_transitions, so turning it off here hides nothing.
    app.CONFIRM_SECONDS = 0
    app.init_db()
    app.PAID_ENABLED = app.PAID_LIVE = True
    app.EMAIL_ENABLED = True
    sch = FakeSchool()
    schools.SCHOOLS = {"varu": sch}

    results = []
    def check(n, c, d=""):
        results.append((n, bool(c), d))

    mails = []
    app.send_email = lambda to, s, b, u=None: (mails.append((to, s, b)), True)[1]

    srv = ThreadingHTTPServer(("127.0.0.1", 0), app.Handler)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    BASE = f"http://127.0.0.1:{srv.server_address[1]}"

    class NoFollow(urllib.request.HTTPRedirectHandler):
        def redirect_request(self, *a, **k):
            return None
    opener = urllib.request.build_opener(NoFollow)

    seq = [0]

    def new_user(tier=0, **cols):
        seq[0] += 1
        sub = f"var{seq[0]}"
        keys = "google_sub,email,topic,created,plan_tier,plan_term,plan_purchased_at"
        vals = [sub, f"{sub}@x.edu", f"t_{sub}", time.time(), tier,
                app.current_season() if tier else None, time.time() if tier else None]
        for k, v in cols.items():
            keys += "," + k
            vals.append(v)
        with app.db() as c:
            c.execute(f"INSERT INTO users({keys}) VALUES({','.join('?' * len(vals))})", vals)
            return c.execute("SELECT id FROM users WHERE google_sub=?", (sub,)).fetchone()["id"]

    def post(uid, path, fields, follow=False):
        ck = app.session_cookie(uid).split(";")[0]
        data = urlencode(dict({"csrf": app.csrf_token(uid)}, **fields)).encode()
        req = urllib.request.Request(BASE + path, data=data,
                                     headers={"Cookie": ck,
                                              "Content-Type": "application/x-www-form-urlencoded"})
        op = urllib.request.urlopen if follow else opener.open
        try:
            r = op(req, timeout=20)
            return r.status, r.read().decode("utf-8", "replace"), dict(r.headers)
        except urllib.error.HTTPError as e:
            return e.code, e.read().decode("utf-8", "replace"), dict(e.headers)

    def held(uid):
        with app.db() as c:
            rows = c.execute("SELECT course, section FROM watches WHERE user_id=?",
                             (uid,)).fetchall()
        by = {}
        for r in rows:
            by.setdefault(r["course"], []).append(r["section"])
        return by

    # ===================================================== A. PRG on EVERY form
    # Only /watch was ever checked. A form that still answers its POST with HTML leaves a
    # POST in history, and the student meets "Confirm Form Resubmission" on Back.
    uid = new_user(3)
    post(uid, "/watch", {"school": "varu", "course": "BIOL100", "sections": "0101"})
    with app.db() as c:
        wid = c.execute("SELECT id FROM watches WHERE user_id=?", (uid,)).fetchone()["id"]
    forms = [
        ("/watch", {"school": "varu", "course": "BIOL101", "sections": "0101"}),
        ("/unwatch", {"id": str(wid)}),
        ("/notify-prefs", {"notify_email": "1"}),
        ("/feedback", {"message": "a variation test"}),
    ]
    for path, fields in forms:
        code, body, hdrs = post(uid, path, fields)
        check(f"A. POST {path} redirects instead of returning HTML",
              code == 303 and (hdrs.get("Location") or "") == "/",
              f"HTTP {code}, Location={hdrs.get('Location')} — Back would offer to resubmit")
        check(f"A. ...and {path} sends no HTML body with it", len(body) == 0, f"{len(body)} bytes")

    # ===================================================== B. no refusal says 200
    uid = new_user(0)
    refusals = [
        ("forged CSRF", "/watch", {"csrf": "forged", "school": "varu",
                                   "course": "BIOL200", "sections": "0101"}),
        ("unknown school", "/watch", {"school": "nope", "course": "BIOL200",
                                      "sections": "0101"}),
        ("malformed course", "/watch", {"school": "varu", "course": "!!!",
                                        "sections": "0101"}),
        ("nonexistent section", "/watch", {"school": "varu", "course": "BIOL200",
                                           "sections": "9999"}),
    ]
    for label, path, fields in refusals:
        ck = app.session_cookie(uid).split(";")[0]
        f = dict({"csrf": app.csrf_token(uid)}, **fields)
        req = urllib.request.Request(BASE + path, data=urlencode(f).encode(),
                                     headers={"Cookie": ck,
                                              "Content-Type": "application/x-www-form-urlencoded"})
        try:
            code = opener.open(req, timeout=20).status
        except urllib.error.HTTPError as e:
            code = e.code
        check(f"B. a refusal ({label}) does not answer 200", code != 200,
              f"HTTP {code} — 'I refused you' must not look like 'done'")

    # ===================================================== C. the list reads right
    for tier in (0, 1, 2, 3):
        uid = new_user(tier)
        post(uid, "/watch", {"school": "varu", "course": "BIOL300",
                             "sections": "0101" if tier == 0 else ""})
        page = app.watches_html(uid, "tok")
        if tier == 0:
            check(f"C. tier {tier}: a named section shows its number", "§0101" in page, page[:120])
        else:
            check(f"C. tier {tier}: an all-sections watch says so in words",
                  "all sections" in page, page[:120])
        check(f"C. tier {tier}: no dangling section symbol",
              "§," not in page and "§<" not in page and "§ ·" not in page, page[:120])

    # ===================================================== D. preferences matrix
    # Every combination of the two live channels. The sample email must fire exactly when
    # email is on, and never otherwise — demonstrating a channel someone switched off is
    # spam, and NOT demonstrating one they switched on leaves it unproven until it matters.
    #
    # notify_push is still swept across both values on purpose. It is retired, so it must
    # make NO difference to anything: a stored 1 must not revive the channel, must not
    # change what notify_prefs reports, and must not stand in for a real one.
    for push in (0, 1):
        for email in (0, 1):
            for sms in (0, 1):
                if not (email or sms):
                    continue                    # the handler forbids zero real channels
                uid = new_user(0, notify_push=push, notify_email=email, notify_sms=sms)
                before = len(mails)
                app.send_sample_email(uid)
                fired = len(mails) > before
                check(f"D. push={push} email={email} sms={sms}: sample email fires "
                      f"{'yes' if email else 'no'}",
                      fired == bool(email),
                      "a student was emailed a demo of a channel they turned off"
                      if fired else "email was never proven before a real seat depended on it")
                check(f"D. push={push} email={email} sms={sms}: prefs read back exactly",
                      app.notify_prefs(uid) == (False, bool(email), bool(sms)),
                      "a stored notify_push must never change what we report or send")

    # ===================================================== E. a plan change keeps state
    for start, end in ((0, 1), (1, 2), (1, 3), (2, 3)):
        uid = new_user(start)
        post(uid, "/watch", {"school": "varu", "course": "BIOL400",
                             "sections": "0101" if start == 0 else ""})
        before = held(uid)
        with app.db() as c:
            c.execute("UPDATE users SET plan_tier=?, plan_term=?, plan_purchased_at=? WHERE id=?",
                      (end, app.current_season(), time.time(), uid))
        check(f"E. upgrading {start}->{end} keeps the existing watch", held(uid) == before,
              f"{before} became {held(uid)} — paying cost them a watch")
        post(uid, "/watch", {"school": "varu", "course": "CHEM400", "sections": ""})
        check(f"E. ...and the new capacity is usable immediately",
              "CHEM400" in held(uid) or app.TIER_COURSES[end] == 1,
              f"tier {end} allows {app.TIER_COURSES[end]} course(s); got {list(held(uid))}")

    # ===================================================== F. alerts, end to end
    # The database looking right is not the product working. Open a real seat through the
    # real cycle and assert the phone rings for exactly the right people.
    fired = []
    real_alert = app._alert
    app._alert = lambda r, msg, url: (fired.append((r["user_id"], r["course"], r["section"])), 1)[1]
    try:
        for tier in (1, 2, 3):
            for mode in ("named", "all"):
                uid = new_user(tier)
                course = f"BIOL{500 + tier}{0 if mode == 'named' else 1}"
                post(uid, "/watch", {"school": "varu", "course": course,
                                     "sections": "0102" if mode == "named" else ""})
                fired.clear()
                sch.state = {"0101": {"open": True, "seats": 3},
                             "0102": {"open": False, "seats": 0},
                             "0103": {"open": False, "seats": 0}}
                app.run_cycle()
                got = [f for f in fired if f[0] == uid]
                if mode == "all":
                    check(f"F. tier {tier} all-sections: fires when ANY section opens",
                          bool(got), "the paid headline feature is silent")
                else:
                    check(f"F. tier {tier} named 0102: stays SILENT when 0101 opens",
                          not got,
                          "alerting about a section they cannot take trains them to ignore us")
                fired.clear()
                sch.state = {"0101": {"open": False, "seats": 0},
                             "0102": {"open": True, "seats": 2},
                             "0103": {"open": False, "seats": 0}}
                app.run_cycle()
                got = [f for f in fired if f[0] == uid]
                if mode == "named":
                    check(f"F. tier {tier} named 0102: FIRES when 0102 opens", bool(got),
                          "they named the section, it opened, and nothing happened")
                with app.db() as c:
                    c.execute("DELETE FROM watches WHERE user_id=?", (uid,))
    finally:
        app._alert = real_alert
        sch.state = {f"{i:04d}": {"open": False, "seats": 0} for i in (101, 102, 103)}

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
