#!/usr/bin/env python3
"""Attribution and the weekly report. Answers one question: is this worth Nathan's time?

THE METRIC: **alerts created per founder-minute.** Not upvotes, not impressions, not
signups. A watch created is the moment a student has committed to the product; everything
before it is noise, and everything after it is the alert engine's job.

TWO ATTRIBUTION MODES, AND THE REPORT ALWAYS SAYS WHICH IT USED:

  exact   `users.source` exists and is populated from the ?r= code. Requires the one small
          app.py change listed in NEEDS-FROM-NATHAN.md. Until then this mode is unavailable
          and the report says so rather than quietly falling back.

  window  Attribution by time: watches created within ATTRIB_WINDOW_H of a post, at a school
          plausibly served by that subreddit. This is an ESTIMATE and is labelled as one in
          every line it produces. It cannot distinguish a Reddit signup from a friend Nathan
          texted, so it is an upper bound.

Reporting an estimate as a measurement is the failure mode this file is written to avoid —
at six users, one misattributed watch changes the headline number by 100%.

READ-ONLY against watches.db, always. Marketing must never be able to write to the database
that decides whether a student gets alerted.

USAGE
  python3 report.py                 # weekly report
  python3 report.py --days 30
"""
import argparse, os, sqlite3, sys, time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import store

DAY = 86400
ATTRIB_WINDOW_H = 72        # a student who reads a post on Tuesday may act on Thursday
SEATWATCH_DB = os.environ.get(
    "SEATWATCH_REPORT_DB",
    os.path.expanduser("~/seatwatch-backups"))     # newest snapshot, or a path to a .db


def _seatwatch_db():
    """Newest local backup by default. Never the live file — a report is not worth a lock
    on the database the poller writes to every 20 seconds."""
    p = SEATWATCH_DB
    if os.path.isdir(p):
        import glob
        cands = sorted(glob.glob(os.path.join(p, "watches-*.db")))
        if not cands:
            return None
        p = cands[-1]
    return p if os.path.exists(p) else None


def _connect_ro(path):
    c = sqlite3.connect("file:%s?mode=ro" % path, uri=True)
    c.row_factory = sqlite3.Row
    return c


def has_source_column(c):
    try:
        cols = [r[1] for r in c.execute("PRAGMA table_info(users)")]
        return "source" in cols
    except sqlite3.Error:
        return False


def attribute(days=7):
    """Return (mode, rows) where rows are {subreddit, watches, users}."""
    path = _seatwatch_db()
    if not path:
        return "unavailable", [], "no SeatWatch snapshot found under %s" % SEATWATCH_DB
    sw = _connect_ro(path)
    since = time.time() - days * DAY

    if has_source_column(sw):
        rows = sw.execute(
            "SELECT u.source AS src, COUNT(DISTINCT u.id) users, COUNT(w.id) watches "
            "FROM users u LEFT JOIN watches w ON w.user_id=u.id "
            "WHERE u.created>? AND u.source IS NOT NULL AND u.source<>'' "
            "GROUP BY 1 ORDER BY 3 DESC", (since,)).fetchall()
        with store.db() as m:
            codes = {r["code"]: r["subreddit"]
                     for r in m.execute("SELECT code, subreddit FROM attrib_codes")}
        out = [{"subreddit": codes.get(r["src"], r["src"]),
                "users": r["users"], "watches": r["watches"]} for r in rows]
        return "exact", out, None

    # ---- window mode
    with store.db() as m:
        posts = m.execute("SELECT p.*, s.school FROM posts p "
                          "LEFT JOIN subreddits s ON s.name=p.subreddit "
                          "WHERE p.posted_at>?", (since,)).fetchall()
    agg = {}
    for p in posts:
        lo, hi = p["posted_at"], p["posted_at"] + ATTRIB_WINDOW_H * 3600
        if p["school"]:
            q = ("SELECT COUNT(*) n, COUNT(DISTINCT user_id) u FROM watches "
                 "WHERE created BETWEEN ? AND ? AND school=?")
            r = sw.execute(q, (lo, hi, p["school"])).fetchone()
        else:
            r = sw.execute("SELECT COUNT(*) n, COUNT(DISTINCT user_id) u FROM watches "
                           "WHERE created BETWEEN ? AND ?", (lo, hi)).fetchone()
        a = agg.setdefault(p["subreddit"], {"subreddit": p["subreddit"], "users": 0,
                                            "watches": 0})
        a["watches"] += r["n"] or 0
        a["users"] += r["u"] or 0
    return "window", sorted(agg.values(), key=lambda x: -x["watches"]), None


def founder_minutes(days):
    with store.db() as c:
        r = c.execute("SELECT COALESCE(SUM(minutes),0) m FROM founder_time WHERE at>?",
                      (time.time() - days * DAY,)).fetchone()
    return r["m"]


def weekly(days=7):
    store.init()
    print("=" * 72)
    print("  SEATWATCH REDDIT — %d-DAY REPORT   %s"
          % (days, time.strftime("%Y-%m-%d", time.gmtime())))
    print("=" * 72)

    with store.db() as c:
        subs = c.execute("SELECT status, COUNT(*) n FROM subreddits GROUP BY 1").fetchall()
        opp = c.execute("SELECT COUNT(*) n FROM opportunities WHERE found_at>?",
                        (time.time() - days * DAY,)).fetchone()["n"]
        drafted = c.execute("SELECT COUNT(*) n FROM drafts WHERE written_at>?",
                            (time.time() - days * DAY,)).fetchone()["n"]
        passed = c.execute("""SELECT COUNT(*) n FROM drafts d JOIN safety_reviews s
            ON s.id=(SELECT id FROM safety_reviews WHERE draft_id=d.id
                     ORDER BY reviewed_at DESC LIMIT 1)
            WHERE s.verdict='pass' AND d.written_at>?""",
                           (time.time() - days * DAY,)).fetchone()["n"]
        posts = c.execute("SELECT COUNT(*) n FROM posts WHERE posted_at>?",
                          (time.time() - days * DAY,)).fetchone()["n"]
        removed = c.execute("""SELECT COUNT(DISTINCT post_id) n FROM post_outcomes
            WHERE removed=1 AND checked_at>?""",
                            (time.time() - days * DAY,)).fetchone()["n"]

    print("\n  PIPELINE")
    print("    subreddits        %s"
          % ", ".join("%s %d" % (s["status"], s["n"]) for s in subs) or "none")
    print("    opportunities     %d found" % opp)
    print("    drafts            %d written, %d passed the gate" % (drafted, passed))
    print("    posts             %d published%s"
          % (posts, ("  ⚠ %d REMOVED" % removed) if removed else ""))
    if drafted and not passed:
        print("    ^ everything written was blocked. That is the gate working, but if it")
        print("      persists the writer is being asked for the wrong thing.")

    mode, rows, err = attribute(days)
    mins = founder_minutes(days)
    watches = sum(r["watches"] for r in rows)

    print("\n  ALERTS CREATED PER FOUNDER-MINUTE")
    if err:
        print("    unavailable: %s" % err)
    elif mode == "exact":
        print("    mode: EXACT (users.source)")
    else:
        print("    mode: WINDOW ESTIMATE — watches created within %dh of a post, at that"
              % ATTRIB_WINDOW_H)
        print("          subreddit's school. Cannot separate Reddit from word of mouth,")
        print("          so treat every number below as an UPPER BOUND.")
    print("    founder minutes   %.0f" % mins)
    print("    watches created   %d%s" % (watches, "" if mode == "exact" else "  (est.)"))
    if mins > 0:
        print("    per founder-min   %.2f%s" % (watches / mins,
                                                "" if mode == "exact" else "  (est.)"))
    else:
        print("    per founder-min   —  (no founder time logged; close a batch with"
              " --minutes)")

    if rows:
        print("\n  BY SUBREDDIT")
        for r in rows:
            print("    r/%-22s %3d watches  %3d users" % (r["subreddit"], r["watches"],
                                                          r["users"]))

    print("\n  SAFETY")
    with store.db() as c:
        fails = c.execute("""SELECT s.failures FROM safety_reviews s
            WHERE s.verdict='fail' AND s.reviewed_at>?""",
                          (time.time() - days * DAY,)).fetchall()
    import json as _j
    tally = {}
    for f in fails:
        for x in _j.loads(f["failures"] or "[]"):
            tally[x["rule"]] = tally.get(x["rule"], 0) + 1
    if not tally:
        print("    no gate failures this period")
    for k, v in sorted(tally.items(), key=lambda kv: -kv[1])[:8]:
        print("    %-26s %d" % (k, v))
    if removed:
        print("    ⚠ %d post(s) removed by moderators — treat the subreddit as blocked"
              " until a human reads why" % removed)

    print("\n" + "=" * 72)
    if watches == 0 and posts > 0:
        print("  %d post(s), zero watches. The channel is not converting — change the"
              % posts)
        print("  message or the community before writing more of the same.")
    elif posts == 0:
        print("  Nothing has been posted yet. Every number above is potential, not result.")
    print("=" * 72)


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--days", type=int, default=7)
    weekly(ap.parse_args().days)
