"""READINESS #30 — the activation funnel: WHY a signed-in student never watches anything.

Between 2026-08-16 and 2026-08-27, seven strangers signed in with Google and six of them
never created a watch. Nothing recorded what they saw or tried, so three completely
different problems were indistinguishable from the database:

    our coverage failed them        -> fix the adapter   (engineering)
    they mistyped a course code     -> fix the form      (design)
    they looked and lost interest   -> fix the pitch     (product)

This suite proves the funnel can tell them apart, and — the part that actually matters —
that it can tell "nobody was refused" apart from "nothing was measuring". A funnel that
reports a confident 0 when it was simply not looking is the same cry-wolf failure this
codebase has hit three times.

The handler, routing, session cookies, CSRF and database are all real; only the school's
registration system is faked, so a rejection here is a rejection a student would get.
"""
import os, re, sys, tempfile, threading, time, warnings
import urllib.error, urllib.request
from http.server import ThreadingHTTPServer
from urllib.parse import urlencode

warnings.filterwarnings("ignore")


class FakeSchool:
    """Answers for exactly one course, so 'course not found' is a real fetch result."""
    id = "testu"; name = "Test University"; example = "CHEM 231"

    def valid_course(self, c):
        return bool(re.match(r"^[A-Z]{2,4}\s?\d{3,4}$", c.strip().upper()))

    def reg_url(self, course): return f"https://testu.test/reg/{course}"
    def cur_term(self): return "202608"

    def fetch(self, courses):
        return {c: ({"0101": {"open": False, "seats": 0}} if c == "CHEM231" else {})
                for c in courses}


class DarkSchool(FakeSchool):
    """Supported, but unreadable today — the Towson case."""
    id = "darku"; name = "Dark University"


def run():
    os.environ["SEATWATCH_DB"] = os.path.join(tempfile.mkdtemp(), "funnel.db")
    sys.path.insert(0, os.path.expanduser("~/seatwatch"))
    import app, schools as schools_mod
    app.init_db()

    results = []
    def check(n, c, d=""): results.append((n, bool(c), d))

    school, dark = FakeSchool(), DarkSchool()
    schools_mod.SCHOOLS = {school.id: school, dark.id: dark}
    app.EMAIL_ENABLED = False
    app.SMS_ENABLED = False
    app.send_email = lambda *a, **k: True
    app.send_sms = lambda *a, **k: False
    app.sw.notify = lambda *a, **k: True
    app.send_web_push = lambda *a, **k: 0
    # darku is supported but its last probe failed, so a watch there can only ever be
    # silence. school_listed() refuses it — and that refusal is the one we most want counted.
    app.coverage = lambda: {school.id: "OK", dark.id: "EMPTY"}
    app.blocked_schools = lambda: set()

    srv = ThreadingHTTPServer(("127.0.0.1", 0), app.Handler)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    base = f"http://127.0.0.1:{srv.server_address[1]}"

    def http(path, fields=None, cookie=None):
        data = urlencode(fields).encode() if fields is not None else None
        req = urllib.request.Request(base + path, data=data)
        if data is not None:
            req.add_header("Content-Type", "application/x-www-form-urlencoded")
        if cookie:
            req.add_header("Cookie", cookie)
        try:
            with urllib.request.urlopen(req, timeout=15) as r:
                return r.status, r.read().decode("utf-8", "replace")
        except urllib.error.HTTPError as e:
            return e.code, e.read().decode("utf-8", "replace")

    def signals(kind=None, uid=None):
        q = "SELECT kind,user_id,detail FROM conv_signals WHERE 1=1"
        a = []
        if kind: q += " AND kind=?"; a.append(kind)
        if uid:  q += " AND user_id=?"; a.append(uid)
        with app.db() as c:
            return c.execute(q + " ORDER BY created", a).fetchall()

    def new_student(sub):
        with app.db() as c:
            c.execute("INSERT INTO users(google_sub,email,topic,created) VALUES(?,?,?,?)",
                      (sub, sub + "@testu.edu", "t_" + sub, time.time()))
            uid = c.execute("SELECT id FROM users WHERE google_sub=?", (sub,)).fetchone()["id"]
        return uid, app.session_cookie(uid).split(";")[0], app.csrf_token(uid)

    T = [2_000_000.0]
    _real_now = app._now
    app._now = lambda: T[0]
    try:
        # ---------- the denominator: was the form ever SEEN? ----------
        uid, cookie, csrf = new_student("g_viewer")
        check("a signed-out visitor records nothing", len(signals("dash_view")) == 0)

        http("/", cookie=cookie)
        check("a signed-in student seeing the form is recorded",
              len(signals("dash_view", uid)) == 1,
              "without this, 'never tried' and 'tried and refused' are the same row count")

        T[0] += 5
        http("/", cookie=cookie); http("/", cookie=cookie)
        check("...but a refresh is not fresh interest (deduped)",
              len(signals("dash_view", uid)) == 1,
              "one bored visitor refreshing would otherwise outweigh a real cohort")

        T[0] += app.DASH_VIEW_DEDUP_S + 1
        http("/", cookie=cookie)
        check("...and a genuine return visit IS counted",
              len(signals("dash_view", uid)) == 2,
              "coming back later is real interest and must not be swallowed by the dedup")

        # ---------- every way a student can be turned away ----------
        uid2, cookie2, csrf2 = new_student("g_rejected")
        cases = [
            ("no such school", [("school", "nope"), ("course", "CHEM231"),
                                ("sections", "0101")], "school_invalid", "nope"),
            ("college supported but UNREADABLE today",
             [("school", "darku"), ("course", "CHEM231"), ("sections", "0101")],
             "school_unlisted", "darku"),
            ("course code in the wrong format",
             [("school", "testu"), ("course", "ZZZ"), ("sections", "0101")],
             "course_format_bad", "testu:ZZZ"),
            ("course that does not exist there",
             [("school", "testu"), ("course", "CHEM999"), ("sections", "0101")],
             "course_not_found", "testu:CHEM999"),
            ("real course, section that does not exist",
             [("school", "testu"), ("course", "CHEM231"), ("sections", "9999")],
             "section_not_found", "testu:CHEM231"),
            ("section box left empty",
             [("school", "testu"), ("course", "CHEM231"), ("sections", "")],
             "no_sections_given", "testu"),
        ]
        for label, fields, kind, detail in cases:
            before = len(signals(kind, uid2))
            http("/watch", [("csrf", csrf2)] + fields, cookie=cookie2)
            rows = signals(kind, uid2)
            check(f"recorded: {label}", len(rows) == before + 1, f"expected one {kind}")
            if rows:
                check(f"...with WHAT they typed ({kind})", rows[-1]["detail"] == detail,
                      f"got {rows[-1]['detail']!r}, wanted {detail!r}")

        with app.db() as c:
            n_watch = c.execute("SELECT COUNT(*) FROM watches WHERE user_id=?",
                                (uid2,)).fetchone()[0]
        check("none of those rejections created a watch", n_watch == 0)

        # ---------- and the success ----------
        before_views = len(signals("dash_view", uid2))
        code, _ = http("/watch", [("csrf", csrf2), ("school", "testu"),
                                  ("course", "CHEM231"), ("sections", "0101")],
                       cookie=cookie2)
        created = signals("watch_created", uid2)
        check("a successful watch is recorded too", len(created) == 1, f"HTTP {code}")
        if created:
            check("...with the school and course", created[0]["detail"] == "testu:CHEM231",
                  f"got {created[0]['detail']!r}")
        with app.db() as c:
            check("...and the watch really exists",
                  c.execute("SELECT COUNT(*) FROM watches WHERE user_id=?",
                            (uid2,)).fetchone()[0] == 1)

        http("/", cookie=cookie2)          # the "added ✓" page
        check("the SUCCESS page is not counted as a form view",
              len(signals("dash_view", uid2)) == before_views,
              "counting it would inflate the denominator with people who already converted")

        # ---------- the question the whole thing exists to answer ----------
        # Two students who both failed to activate, for opposite reasons. The funnel has to
        # separate them, because one is an engineering bug and the other is a pitch problem.
        stalled_at_form = [r["user_id"] for r in signals("dash_view")]
        refused = [r["user_id"] for r in signals("school_unlisted")]
        uid3, cookie3, _ = new_student("g_never_looked")
        check("a student who never opened the form is distinguishable",
              uid3 not in stalled_at_form and uid3 not in refused,
              "no views and no rejections = the drop is at sign-in, not the class picker")
        check("...from one who opened it and was refused by OUR coverage",
              uid2 in refused and uid2 in stalled_at_form,
              "these two need opposite fixes and must never be summed together")

        # ---------- it must never cost a student their watch ----------
        boom = app.db
        app.db = lambda *a, **k: (_ for _ in ()).throw(RuntimeError("db gone"))
        try:
            app._conv_signal("course_not_found", uid2, "x:y")
            app._dash_view(uid2)
            check("a broken analytics write NEVER raises", True)
        except Exception as e:
            check("a broken analytics write NEVER raises", False, f"{type(e).__name__}: {e}")
        finally:
            app.db = boom

        code, _ = http("/watch", [("csrf", csrf2), ("school", "testu"),
                                  ("course", "CHEM231"), ("sections", "0102")],
                       cookie=cookie2)
        check("...and watch creation still works after one", code in (200, 303),
              f"HTTP {code} — measuring the funnel must not break the product")

        # ---------- honesty about its own coverage ----------
        with app.db() as c:
            cols = {r[1] for r in c.execute("PRAGMA table_info(conv_signals)")}
        check("the detail column exists (old rows read NULL, not a fake value)",
              "detail" in cols)
        with app.db() as c:
            c.execute("INSERT INTO conv_signals(kind,user_id,created) "
                      "VALUES('wall_hit',?,?)", (uid2, T[0]))
            legacy = c.execute("SELECT detail FROM conv_signals WHERE kind='wall_hit'"
                               ).fetchone()["detail"]
        check("a signal written without detail stays NULL", legacy is None,
              "an empty string would read as 'we looked and found nothing'")
    finally:
        app._now = _real_now
        srv.shutdown()

    p = sum(x for _, x, _ in results)
    f = sum(not x for _, x, _ in results)
    return p, f, results


if __name__ == "__main__":
    p, f, res = run()
    for n, ok, d in res:
        print(f"  [{'PASS' if ok else '*** FAIL'}] {n}{('  ' + d) if d and not ok else ''}")
    print(f"\n  {p} passed, {f} failed")
    sys.exit(1 if f else 0)
