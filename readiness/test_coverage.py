"""READINESS #21 — the public school count must be a MEASUREMENT, not a claim.

The homepage said "926 universities" because schools.py had 926 rows in it. Thirty-one of
those returned nothing at all: a student could pick their college, add a class, and wait
the whole term for an alert that could never arrive. Nothing errored, nothing was logged,
and the number on the marketing page stayed confidently wrong. It is the same shape as an
alert delivered to a channel nobody reads — a promise the system cannot keep, kept quiet.

What this pins:

  COUNT       only OK-verdict schools are counted. ALL_OPEN (returns data, but has never
              shown us a full section, so we have not seen it tell open from full) is
              watchable and deliberately NOT counted.
  LISTING     broken schools leave the picker; ALL_OPEN stays.
  ENFORCEMENT a POST naming a hidden school is refused BY THE SERVER and creates no row.
              The picker is a JSON blob in the page and cannot be the guard.
  RECOVERY    a fixed school returns to the count and the picker with no code change.
  FAIL-OPEN   an unreadable coverage file lists everything rather than emptying the site,
              and never publishes a count of zero.
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
    os.environ["SEATWATCH_DB"] = os.path.join(tempfile.mkdtemp(), "cov.db")
    sys.path.insert(0, os.path.expanduser("~/seatwatch"))
    import app
    app.init_db()

    results = []
    def check(n, c, d=""): results.append((n, bool(c), d))

    tmpdir = tempfile.mkdtemp()
    seq = [0]

    def load(mapping):
        """Point the app at a coverage file we control, loaded exactly as the real one is.

        A NEW path each time: the cache keys on mtime, and two writes inside one filesystem
        timestamp tick would otherwise look unchanged and serve stale verdicts — which is
        also the bug that would keep a recovered school hidden in production.
        """
        seq[0] += 1
        p = os.path.join(tmpdir, "cov%d.json" % seq[0])
        with open(p, "w") as f:
            json.dump({k: {"name": k, "verdict": v} for k, v in mapping.items()}, f)
        app.COVERAGE_PATH = p
        app._cov["mtime"] = -1.0
        app._cov["data"] = {}
        return p

    # Neutralise the REAL blocklist for the general checks. Whatever production is holding
    # off the site today is a moving list, and a suite whose arithmetic depends on it fails
    # every time someone blocks a school — noise that trains people to ignore red. The
    # blocklist gets its own section below, with contents this test controls.
    empty_block = os.path.join(tmpdir, "noblock.json")
    with open(empty_block, "w") as f:
        json.dump({}, f)
    app.BLOCKED_PATH = empty_block
    app._blocked["mtime"] = -1.0
    app._blocked["data"] = {}

    ids = list(app.schools.SCHOOLS)
    good, allopen, empty, fake = ids[0], ids[1], ids[2], ids[3]
    rest = ids[4:]
    base = {good: "OK", allopen: "ALL_OPEN", empty: "EMPTY", fake: "FAKE_OPEN"}
    base.update({s: "OK" for s in rest})
    load(base)

    # ------------------------------------------------------------------- count
    expected = 1 + len(rest)
    check("count includes only proven (OK) schools", app.proven_count() == expected,
          f"got {app.proven_count()}, expected {expected}")
    check("count excludes ALL_OPEN (watchable, never seen call a section full)",
          app.proven_count() < len(app.schools.SCHOOLS))
    check("count is below the raw registry size",
          app.proven_count() < len(app.schools.SCHOOLS),
          "if these ever match again, the number has stopped being a measurement")

    # ----------------------------------------------------------------- listing
    check("a proven school is listed", app.school_listed(good))
    check("an ALL_OPEN school is still listed", app.school_listed(allopen),
          "it returns usable data; hiding it would drop a school that works")
    check("an EMPTY school is hidden", not app.school_listed(empty),
          "a watch there could only ever be silence")
    check("a FAKE_OPEN school is hidden", not app.school_listed(fake),
          "worse than silence: alerts for seats that do not exist")
    listed = {s.id for s in app.listed_schools()}
    check("hidden schools absent from listed_schools()",
          empty not in listed and fake not in listed)
    js = app.schools_js()
    check("hidden schools absent from the picker payload",
          f'"{empty}"' not in js and f'"{fake}"' not in js)
    check("listed schools present in the picker payload", f'"{good}"' in js)

    # ------------------------------------------------------------- enforcement
    # Over real HTTP, with a real session and CSRF token — the picker is a blob in the
    # page, so anyone who can craft a POST can name a school that was never in it.
    with app.db() as c:
        c.execute("INSERT INTO users(google_sub,email,topic,created,plan_tier) "
                  "VALUES('g_cov','cov@umd.edu','t_cov',?,1)", (time.time(),))
        uid = c.execute("SELECT id FROM users WHERE google_sub='g_cov'").fetchone()["id"]

    srv = ThreadingHTTPServer(("127.0.0.1", 0), app.Handler)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    BASE = "http://127.0.0.1:%d" % srv.server_address[1]
    cookie = app.session_cookie(uid).split(";")[0]
    csrf = app.csrf_token(uid)

    def post(school_id):
        body = urlencode({"csrf": csrf, "school": school_id, "course": "ENG101"}).encode()
        r = urllib.request.Request(BASE + "/watch", data=body,
                                   headers={"Cookie": cookie,
                                            "Content-Type": "application/x-www-form-urlencoded"})
        try:
            with urllib.request.urlopen(r, timeout=10) as resp:
                return resp.status, resp.read().decode("utf-8", "replace")
        except urllib.error.HTTPError as e:
            return e.code, e.read().decode("utf-8", "replace")

    def watch_count(sid):
        with app.db() as c:
            return c.execute("SELECT COUNT(*) n FROM watches WHERE school=?",
                             (sid,)).fetchone()["n"]

    code, body = post(empty)
    check("POST naming a HIDDEN school is refused", code >= 400,
          f"got HTTP {code} — the server accepted a watch it can never deliver")
    check("...and explains why instead of failing silently",
          "seat data" in body.lower() or "can't read" in body.lower() or "cant read" in body.lower(),
          "a bare error teaches the student nothing")
    check("...and creates NO watch row", watch_count(empty) == 0,
          "the refusal must be real, not cosmetic")

    code_f, _ = post(fake)
    check("POST naming a FAKE_OPEN school is refused", code_f >= 400)
    check("...and creates no watch row", watch_count(fake) == 0)

    # The gate must not block schools that work — the expensive failure mode. Asserted on
    # the REFUSAL rather than on a created row: this course does not exist at that school,
    # so the handler rightly declines for its own reasons, and a row-exists assertion here
    # would be testing course lookup while claiming to test coverage.
    code_ok, body_ok = post(allopen)
    check("an ALL_OPEN school is NOT blocked by the coverage gate",
          "seat data" not in body_ok.lower(),
          "the gate is refusing a school that returns real data")
    check("...and the refusal it does give is about the course, not coverage",
          code_ok < 400 or "seat data" not in body_ok.lower())

    # ------------------------------------------------------------- blocklist
    # The sweep probes ONE course and asks whether the answer looks sane. Jackson College
    # passed it while collapsing three terms of sections into one namespace — confident,
    # wrong data. A human block has to outrank the sweep, or the next run puts it back.
    bp = os.path.join(tmpdir, "blocked.json")
    with open(bp, "w") as f:
        json.dump({"_README": ["docs, not a school"], good: {"reason": "term collapse"}}, f)
    app.BLOCKED_PATH = bp
    app._blocked["mtime"] = -1.0
    app._blocked["data"] = {}
    load(base)                                   # good is OK in coverage, blocked by hand

    check("a blocklist entry beats an OK sweep verdict", not app.school_listed(good),
          "the sweep would otherwise re-list a school we deliberately pulled")
    check("...and removes it from the picker", f'"{good}"' not in app.schools_js())
    check("...and from the published count", app.proven_count() == expected - 1,
          "hiding a school while still counting it would restate the same dishonesty")
    check("_README keys are documentation, not schools",
          "_README" not in app.blocked_schools(),
          "a comment key must never be mistaken for a school id")
    check("schools NOT on the blocklist are unaffected", app.school_listed(allopen))

    with open(bp, "w") as f:
        json.dump({}, f)
    app._blocked["mtime"] = -1.0
    check("clearing the blocklist restores the school", app.school_listed(good))

    app.BLOCKED_PATH = empty_block
    app._blocked["mtime"] = -1.0
    app._blocked["data"] = {}
    app._schools_js["key"] = None
    load(base)

    # -------------------------------------------------------------- recovery
    fixed = dict(base)
    fixed[empty] = "OK"
    load(fixed)
    check("a fixed school returns to the listing", app.school_listed(empty),
          "recovery must need no code change — the next sweep is enough")
    check("...and is counted again", app.proven_count() == expected + 1)
    check("...and reappears in the picker", f'"{empty}"' in app.schools_js(),
          "a cache keyed wrong would keep a recovered school hidden forever")
    code_r, _ = post(empty)
    check("...and can now be watched", code_r < 400)

    # -------------------------------------------------------------- fail-open
    app.COVERAGE_PATH = os.path.join(tmpdir, "gone.json")
    app._cov["mtime"] = -1.0
    app._cov["data"] = {}
    check("missing coverage lists every school rather than emptying the site",
          app.school_listed(empty) and app.school_listed(fake),
          "an unreadable data file must not look like a total outage")
    check("missing coverage falls back to the registry size",
          app.proven_count() == len(app.schools.SCHOOLS))
    load({})
    check("an EMPTY coverage file never publishes a count of 0",
          app.proven_count() == len(app.schools.SCHOOLS),
          "0 universities on the homepage is worse than an overstated number")

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
