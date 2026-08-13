"""READINESS #19 — ENTITLEMENTS. Does every account get exactly what its plan promises?

Written because two bugs reached a real user that every other suite was blind to, and
they were blind for the same reason: the existing tests check SECURITY (can a stranger
touch my data) and ONE HAPPY PATH (a free student watches a class). Neither asks the
question a paying customer actually cares about — "I bought the 5-course plan, do I have
five courses?"

The two that got through:

  * a paid account's NAMED sections were discarded and the whole course watched instead
  * a paid account was then refused a section by a message calling it a free plan,
    because two different places enforced the section cap and only one knew about tiers

Both are the same shape: a rule enforced in more than one place, drifting apart. So this
suite tests the RULE from outside the process, over real HTTP, for every tier — not the
implementation, which is where the drift hides.

It also covers what happens when a plan CHANGES, which nothing tested at all: a refund, an
expiry, an upgrade. A student who bought five courses and then charged back should not
keep five courses, and finding that out from a customer would be worse than finding it
here.
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
    id = "entu"; name = "Entitlement U"; example = "CHEM 231"; term = "202608"

    def valid_course(self, c):
        return bool(re.match(r"^[A-Z]{2,4}\s?\d{3,4}$", c.strip().upper()))

    def reg_url(self, course):
        return "https://entu.test/reg"

    def cur_term(self):
        return self.term

    def fetch(self, courses):
        secs = {f"{i:04d}": {"open": False, "seats": 0}
                for i in (101, 102, 103, 104, 105, 106, 201, 202)}
        return {c: {k: dict(v) for k, v in secs.items()} for c in courses}


def run():
    os.environ["SEATWATCH_DB"] = os.path.join(tempfile.mkdtemp(), "ent.db")
    sys.path.insert(0, os.path.expanduser("~/seatwatch"))
    import app, schools
    # Opening confirmation (CONFIRM_SECONDS) is OFF here: this suite drives
    # run_cycle expecting one cycle to equal one alert, and its subject is what each paid plan delivers,
    # not alert timing. The confirmation contract is owned by test_churn_confirm
    # (real-timeline replay) and exercised through run_cycle by
    # test_alert_transitions, so turning it off here hides nothing.
    app.CONFIRM_SECONDS = 0
    app.init_db()
    app.PAID_ENABLED = True
    schools.SCHOOLS = {"entu": FakeSchool()}

    results = []
    def check(n, c, d=""):
        results.append((n, bool(c), d))

    srv = ThreadingHTTPServer(("127.0.0.1", 0), app.Handler)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    BASE = f"http://127.0.0.1:{srv.server_address[1]}"

    seq = [0]

    def new_user(tier):
        seq[0] += 1
        sub = f"ent{seq[0]}"
        with app.db() as c:
            c.execute("INSERT INTO users(google_sub,email,topic,created,plan_tier,plan_term,"
                      "plan_purchased_at) VALUES(?,?,?,?,?,?,?)",
                      (sub, f"{sub}@x.edu", f"t_{sub}", time.time(), tier,
                       app.current_season() if tier else None,
                       time.time() if tier else None))
            return c.execute("SELECT id FROM users WHERE google_sub=?", (sub,)).fetchone()["id"]

    def watch(uid, course, secs=""):
        ck = app.session_cookie(uid).split(";")[0]
        data = urlencode({"csrf": app.csrf_token(uid), "school": "entu",
                          "course": course, "sections": secs}).encode()
        req = urllib.request.Request(BASE + "/watch", data=data,
                                     headers={"Cookie": ck,
                                              "Content-Type": "application/x-www-form-urlencoded"})
        try:
            with urllib.request.urlopen(req, timeout=20) as r:
                return r.read().decode("utf-8", "replace")
        except urllib.error.HTTPError as e:
            return e.read().decode("utf-8", "replace")

    def held(uid):
        with app.db() as c:
            rows = c.execute("SELECT course, section FROM watches WHERE user_id=?",
                             (uid,)).fetchall()
        by = {}
        for r in rows:
            by.setdefault(r["course"], []).append(r["section"])
        return by

    PLANS = {0: ("Free", 1), 1: ("$19.95", 1), 2: ("$24.95", 2), 3: ("$29.95", 5)}

    # ============================================== A. the course allowance
    for tier, (label, want) in PLANS.items():
        uid = new_user(tier)
        for i in range(want + 3):                       # always ask for MORE than allowed
            watch(uid, f"BIOL{300+i}", "0101, 0102")
        got = held(uid)
        check(f"A. {label}: exactly {want} course(s)", len(got) == want,
              f"got {len(got)} — " + ("a paying student is denied what they bought"
                                      if len(got) < want else "the plan limit is not holding"))

    # ============================================== B. the section allowance
    for tier, (label, _) in PLANS.items():
        uid = new_user(tier)
        watch(uid, "BIOL400", "0101, 0102")
        got = held(uid).get("BIOL400", [])
        check(f"B. {label}: two NAMED sections are both kept", sorted(got) == ["0101", "0102"],
              f"got {got}")

    for tier, (label, _) in PLANS.items():
        uid = new_user(tier)
        watch(uid, "BIOL401", "0101, 0102, 0103, 0104")
        got = held(uid).get("BIOL401", [])
        if tier == 0:
            check(f"B. {label}: four sections is refused (cap is 2)", got == [], f"got {got}")
        else:
            check(f"B. {label}: four NAMED sections are all kept", len(got) == 4, f"got {got}")

    for tier, (label, _) in PLANS.items():
        uid = new_user(tier)
        body = watch(uid, "BIOL402", "")
        got = held(uid).get("BIOL402", [])
        if tier == 0:
            check(f"B. {label}: blank sections is refused, and says so",
                  got == [] and "section" in body.lower(), f"got {got}")
        else:
            check(f"B. {label}: blank sections watches EVERY section", got == [""], f"got {got}")

    # ============================================== C. the message matches the rule
    uid = new_user(0)
    watch(uid, "BIOL500", "0101, 0102")
    body = watch(uid, "BIOL500", "0103")
    check("C. a FREE student refused a 3rd section is told it is the free plan",
          "free plan" in body.lower(), "the refusal must explain which limit was hit")
    uid = new_user(3)
    body = watch(uid, "BIOL501", "0101")
    check("C. a PAID student is never shown free-plan language",
          "free plan" not in body.lower(),
          "a customer refused by a message calling them free is the worst version of this")

    uid = new_user(0)
    watch(uid, "BIOL502", "0101")
    body = watch(uid, "CHEM502", "0101")
    check("C. a FREE student refused a 2nd course is told about the course limit",
          "class" in body.lower() or "course" in body.lower(), body[:120])

    # ============================================== D. plan CHANGES
    # Nothing tested this at all, and it is where money and entitlement meet.
    uid = new_user(3)
    for i in range(5):
        watch(uid, f"BIOL{600+i}", "0101")
    check("D. a $29.95 student really holds 5 courses", len(held(uid)) == 5, str(len(held(uid))))

    with app.db() as c:                                    # refund / chargeback -> free
        c.execute("UPDATE users SET plan_tier=0, plan_term=NULL, plan_purchased_at=NULL "
                  "WHERE id=?", (uid,))
    body = watch(uid, "CHEM600", "0101")
    check("D. after a refund they cannot ADD a 6th course",
          len(held(uid)) == 5 and "CHEM600" not in held(uid),
          "a refunded account is still buying capacity it no longer owns")
    with app.db() as c:
        u = c.execute("SELECT * FROM users WHERE id=?", (uid,)).fetchone()
    check("D. ...and effective_tier reads them as free", app.effective_tier(u) == 0)

    uid = new_user(3)                                      # expiry by time
    watch(uid, "BIOL700", "0101")
    with app.db() as c:
        c.execute("UPDATE users SET plan_purchased_at=? WHERE id=?",
                  (time.time() - (app.PAID_TERM_DAYS + 2) * 86400, uid))
        u = c.execute("SELECT * FROM users WHERE id=?", (uid,)).fetchone()
    check("D. a plan older than the term window reads as free",
          app.effective_tier(u) == 0, f"got {app.effective_tier(u)}")
    body = watch(uid, "CHEM700", "0101")
    check("D. ...and an expired student cannot add a 2nd course",
          "CHEM700" not in held(uid), "an expired plan still grants paid capacity")

    uid = new_user(0)                                      # upgrade keeps what you had
    watch(uid, "BIOL800", "0101, 0102")
    before = held(uid)
    with app.db() as c:
        c.execute("UPDATE users SET plan_tier=3, plan_term=?, plan_purchased_at=? WHERE id=?",
                  (app.current_season(), time.time(), uid))
    check("D. upgrading does not lose the class they were already watching",
          held(uid) == before, "a student who pays should never lose a watch by paying")
    watch(uid, "CHEM800", "0101")
    check("D. ...and they can immediately use the new capacity", "CHEM800" in held(uid))

    # ============================================== E. repeats and odd input
    uid = new_user(3)
    watch(uid, "BIOL900", "0101")
    watch(uid, "BIOL900", "0101")
    check("E. re-submitting the same section does not duplicate it",
          held(uid).get("BIOL900") == ["0101"], str(held(uid).get("BIOL900")))

    uid = new_user(3)
    watch(uid, "BIOL901", "0101, 0101, 0101")
    check("E. a repeated section in one submission is deduped",
          held(uid).get("BIOL901") == ["0101"], str(held(uid).get("BIOL901")))

    uid = new_user(3)
    watch(uid, "BIOL902", " 0101 , 0102 ")
    check("E. whitespace around section numbers is tolerated",
          sorted(held(uid).get("BIOL902", [])) == ["0101", "0102"],
          str(held(uid).get("BIOL902")))

    uid = new_user(3)
    watch(uid, "BIOL903", "9999")
    check("E. a section that does not exist at the school is refused",
          held(uid).get("BIOL903") is None,
          "watching a phantom section is a watch that can never fire")

    uid = new_user(3)
    watch(uid, "BIOL904", "")
    watch(uid, "BIOL904", "0101")
    check("E. narrowing from every-section to one drops the catch-all",
          held(uid).get("BIOL904") == ["0101"],
          "they would keep being alerted about the sections they just excluded")

    uid = new_user(3)
    watch(uid, "BIOL905", "0101")
    watch(uid, "BIOL905", "")
    check("E. widening from one section to every section replaces it",
          held(uid).get("BIOL905") == [""], str(held(uid).get("BIOL905")))

    # ============================================== G. the paid perk actually FIRES
    # Every check above is about what lands in the database. This one asks the question
    # a customer would: I paid for "unlimited sections" — when a seat opens in one of
    # them, does my phone ring? A section="" row is a different code path in the alert
    # engine from a named one, and nothing exercised it end to end. If it were broken,
    # every paid all-sections watch would be silent and the database would look perfect.
    import guardian
    sch = schools.SCHOOLS["entu"]
    fired = []
    _real_alert = app._alert
    app._alert = lambda r, msg, url: (fired.append((r["course"], r["section"], msg)), 1)[1]
    try:
        uid = new_user(3)
        watch(uid, "BIOL950", "")                       # every section
        uid2 = new_user(3)
        watch(uid2, "BIOL951", "0102")                  # one named section

        # open a section that the named-watch student did NOT pick
        base = sch.fetch
        sch.fetch = lambda courses: {c: {**{k: {"open": False, "seats": 0}
                                            for k in ("0101", "0102", "0103")},
                                         "0103": {"open": True, "seats": 4}} for c in courses}
        app.run_cycle()
        got_all = [f for f in fired if f[0] == "BIOL950"]
        got_named = [f for f in fired if f[0] == "BIOL951"]
        check("G. an all-sections watch FIRES when any section opens", bool(got_all),
              "the paid headline feature is silent — customers would hear nothing")
        check("G. a named-section watch stays silent for a section they did NOT pick",
              not got_named,
              "alerting about a section they cannot take teaches them to ignore the next one")

        fired.clear()
        sch.fetch = lambda courses: {c: {**{k: {"open": False, "seats": 0}
                                            for k in ("0101", "0102", "0103")},
                                         "0102": {"open": True, "seats": 2}} for c in courses}
        app.run_cycle()
        check("G. a named-section watch DOES fire for the section they picked",
              any(f[0] == "BIOL951" for f in fired),
              "the student named 0102, a seat opened in 0102, and nothing happened")
    finally:
        app._alert = _real_alert
        sch.fetch = base

    # ============================================== H. what each plan may BUY
    # Upward only, priced at the difference. Selling DOWN is not a purchase — it is a
    # refund request wearing a checkout button, and charging someone to reduce their plan
    # is the kind of thing a student screenshots. Re-buying the SAME tier is money for
    # nothing. Both are refused server-side, so a hand-edited /checkout?tier= link cannot
    # do what the page declines to offer.
    app.PAID_LIVE = True
    app.STRIPE_SECRET_KEY = "sk_test_entitlements"
    _sent = []
    _real_post = app._stripe_post
    app._stripe_post = lambda path, fields, idem=None: (_sent.append(fields),
                                                        {"url": "https://checkout.test/s"})[1]
    try:
        def buyer(tier):
            with app.db() as c:
                c.execute("DELETE FROM users WHERE google_sub='buyer'")
                c.execute("INSERT INTO users(google_sub,email,topic,created,plan_tier,"
                          "plan_term,plan_purchased_at) VALUES('buyer','b@x.edu','tb',?,?,?,?)",
                          (time.time(), tier, app.current_season() if tier else None,
                           time.time() if tier else None))
                return c.execute("SELECT * FROM users WHERE google_sub='buyer'").fetchone()

        for cur in (0, 1, 2, 3):
            for want in (1, 2, 3):
                _sent.clear()
                url = app.stripe_checkout_url(buyer(cur), want)
                cl = "free" if cur == 0 else f"${app.TIER_PRICE_CENTS[cur]/100:.2f}"
                wl = f"${app.TIER_PRICE_CENTS[want]/100:.2f}"
                if want > cur:
                    charged = (int(_sent[-1]["line_items[0][price_data][unit_amount]"])
                               if url and _sent else None)
                    expect = app.TIER_PRICE_CENTS[want] - app.TIER_PRICE_CENTS.get(cur, 0)
                    check(f"H. {cl} -> {wl}: allowed, and charges only the difference",
                          url is not None and charged == expect,
                          f"url={'yes' if url else 'None'} charged={charged} expected={expect}")
                else:
                    label = "the SAME plan again" if want == cur else "a SMALLER plan"
                    check(f"H. {cl} -> {wl}: refused ({label})", url is None,
                          "a student can be charged to lose capacity, or charged twice "
                          "for what they already hold")

        # an upgrade must actually RAISE the tier, never lower it
        u = buyer(2)
        app.stripe_apply_event({"id": "evt_up", "type": "checkout.session.completed",
                                "data": {"object": {"payment_intent": "pi_up",
                                                    "metadata": {"user_id": str(u["id"]),
                                                                 "target_tier": "3"}}}})
        with app.db() as c:
            got = c.execute("SELECT plan_tier FROM users WHERE id=?", (u["id"],)).fetchone()
        check("H. a completed upgrade raises the tier", got["plan_tier"] == 3,
              f"got {got['plan_tier']}")

        u = buyer(3)
        app.stripe_apply_event({"id": "evt_down", "type": "checkout.session.completed",
                                "data": {"object": {"payment_intent": "pi_dn",
                                                    "metadata": {"user_id": str(u["id"]),
                                                                 "target_tier": "1"}}}})
        with app.db() as c:
            got = c.execute("SELECT plan_tier FROM users WHERE id=?", (u["id"],)).fetchone()
        check("H. a stale LOWER-tier event can never demote a paid student",
              got["plan_tier"] == 3,
              f"got {got['plan_tier']} — a replayed old webhook would strip capacity")
    finally:
        app._stripe_post = _real_post

    # ============================================== I. the watch list READS correctly
    # An all-sections watch stores section="" and rendered as "CMSC250 §," — a section
    # symbol pointing at nothing. It looked like a broken row rather than the feature the
    # student had just paid for, and it left the only question they have unanswered: is
    # this covering everything, or did something go wrong?
    uid = new_user(3)
    watch(uid, "BIOL960", "0101")
    watch(uid, "BIOL961", "")
    page_html = app.watches_html(uid, "tok")
    check("I. a NAMED section still shows its number",
          "§0101" in page_html, page_html[:160])
    check("I. an ALL-sections watch says 'all sections' in words",
          "all sections" in page_html,
          "the student cannot tell whether every section is covered")
    check("I. no dangling section symbol is left anywhere",
          "§," not in page_html and "§ " not in page_html.replace("§0101", ""),
          "a lone § reads as a rendering bug")
    check("I. the school is still named on every row",
          page_html.count("Entitlement U") == 2, page_html[:200])

    # ============================================== F. the ladder is coherent
    check("F. every priced tier grants at least as many courses as the one below",
          all(app.TIER_COURSES[t] >= app.TIER_COURSES[t - 1] for t in (2, 3)),
          str(app.TIER_COURSES))
    check("F. every priced tier costs more than the one below",
          all(app.TIER_PRICE_CENTS[t] > app.TIER_PRICE_CENTS[t - 1] for t in (2, 3)),
          str(app.TIER_PRICE_CENTS))
    check("F. the paid names match what the tiers actually grant",
          all(str(app.TIER_COURSES[t]) in app.TIER_NAME[t] for t in (2, 3)),
          "the plan a student reads must be the plan they get: "
          + str({t: app.TIER_NAME[t] for t in (1, 2, 3)}))

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
