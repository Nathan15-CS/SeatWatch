#!/usr/bin/env python3
"""What a STUDENT would experience right now. Run it yourself; trust the output, not a person.

WHY THIS EXISTS: Nathan has twice been told the system was clean and then found a defect
himself. Both times the defect was visible in data someone had already read — nobody asked
the right question. The fix is not a better assurance, it is a check that asks the questions
in the student's voice and that he can run without me.

WHAT MAKES IT DIFFERENT FROM readiness.py AND guardian: those ask "is the code correct" and
"is the data accurate". Both answered YES on the night SeatWatch emailed one person eight
times in an hour about the same class. The data was right and the experience was wrong.
This file only asks: WOULD A STUDENT BE ANNOYED, MISLED, OR IGNORED?

THE RULE THIS FILE OBEYS: anything not actually measured prints UNVERIFIED, never OK.
A silent check is how "no known problems" gets mistaken for "no problems".

USAGE
  python3 ops/student-view.py                 # newest local backup
  python3 ops/student-view.py --db PATH       # a specific snapshot
  python3 ops/student-view.py --hours 48
"""
import argparse, glob, os, sqlite3, sys, time

DAY = 86400
STORM_PER_HOUR = 2          # more than this to one watch in an hour reads as spam
DARK_SECS = 900             # a school silent this long with live watches is dark
RAPID_REPEAT_SECS = 600     # two mails about the same class inside this is a bad experience

FINDINGS = []


def add(sev, title, detail, fix=""):
    FINDINGS.append({"sev": sev, "title": title, "detail": detail, "fix": fix})


def newest_db():
    c = sorted(glob.glob(os.path.expanduser("~/seatwatch-backups/watches-*.db")))
    return c[-1] if c else None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--db", default="")
    ap.add_argument("--hours", type=int, default=24)
    a = ap.parse_args()

    db = a.db or newest_db()
    if not db or not os.path.exists(db):
        print("NO DATA. No snapshot found under ~/seatwatch-backups/.")
        print("That is itself a finding: you cannot verify a system you cannot read.")
        return 2
    age_h = (time.time() - os.path.getmtime(db)) / 3600.0

    c = sqlite3.connect("file:%s?mode=ro" % db, uri=True)
    c.row_factory = sqlite3.Row

    # The window is measured from the NEWEST DATA IN THE FILE, not from wall-clock. Reading
    # a six-day-old snapshot with a 24h wall-clock window silently examines nothing and
    # prints a clean bill of health — the worst possible output. I made this exact mistake
    # twice while writing this file, which is why the rule is now applied in one place.
    newest = max(
        c.execute("SELECT COALESCE(MAX(sent_at),0) t FROM alert_log").fetchone()["t"] or 0,
        c.execute("SELECT COALESCE(MAX(started),0) t FROM guardian_cycles").fetchone()["t"] or 0,
        os.path.getmtime(db))
    cut = newest - a.hours * 3600

    print("=" * 72)
    print("  WOULD A STUDENT BE ANNOYED, MISLED, OR IGNORED?")
    print("  source %s" % os.path.basename(db))
    print("  data is %.1f hours old · window %dh" % (age_h, a.hours))
    print("=" * 72)

    if age_h > 26:
        add("WARN", "You are looking at stale data",
            "This snapshot is %.0f hours old, so anything after that is invisible here." % age_h,
            "Run ops/pull_backup.sh, then re-run this.")

    # ---- 1. ALERT STORMS. The defect of 2026-08-08: 8 emails, one watch, one hour.
    # SLIDING 60-minute window, not clock-hour buckets. The real storm of 2026-08-08 was at
    # 03:32, 04:33 and 04:34 — bucketing by hour split it across two buckets and the check
    # saw nothing. A storm does not wait for the top of the hour, and the first version of
    # this file made exactly the mistake it was written to catch.
    rows = c.execute("""SELECT watch_id, course, section, sent_at FROM alert_log
        WHERE sent_at > ? AND channel IN ('email','webpush','ntfy') AND watch_id IS NOT NULL
        ORDER BY watch_id, sent_at""", (cut,)).fetchall()
    by_watch = {}
    for r in rows:
        by_watch.setdefault(r["watch_id"], []).append(r)
    storms = []
    for wid, rs in by_watch.items():
        ts = [r["sent_at"] for r in rs]
        best, lo = 0, 0
        for hi in range(len(ts)):                     # widest count inside any 3600s window
            while ts[hi] - ts[lo] > 3600:
                lo += 1
            if hi - lo + 1 > best:
                best, span = hi - lo + 1, (ts[lo], ts[hi])
        if best > STORM_PER_HOUR:
            storms.append({"watch_id": wid, "course": rs[0]["course"],
                           "section": rs[0]["section"], "n": best,
                           "a": span[0], "b": span[1]})
        # Volume over an hour is not the only shape a storm takes. Two mails about the same
        # class 69 seconds apart is already a bad experience and it can hide under any
        # hourly threshold — that is precisely how the 2026-08-08 case slipped past the
        # first version of this check. Rapid repeats get flagged on their own terms.
        gaps = [(ts[i] - ts[i - 1], ts[i - 1], ts[i]) for i in range(1, len(ts))]
        tight = [g for g in gaps if g[0] < RAPID_REPEAT_SECS]
        if tight and not any(s["watch_id"] == wid for s in storms):
            g = min(tight)
            storms.append({"watch_id": wid, "course": rs[0]["course"],
                           "section": rs[0]["section"], "n": len(tight) + 1,
                           "a": g[1], "b": g[2], "rapid": int(g[0])})
    if storms:
        for s in storms:
            add("BAD", "Alert storm — a student got %d messages about one class within an hour"
                % s["n"] if not s.get("rapid") else
                "Rapid repeat — two messages about one class %ds apart" % s["rapid"],
                "%s %s (watch %s), %s to %s. Each may have followed a real seat opening, but "
                "from an inbox this is indistinguishable from spam, and the student "
                "unsubscribes — then never hears about the seat they would have gotten."
                % (s["course"], s["section"] or "", s["watch_id"],
                   time.strftime("%H:%M", time.localtime(s["a"])),
                   time.strftime("%H:%M", time.localtime(s["b"]))),
                "Per-watch repeat-alert cooldown. SMS already has one; email does not.")
    else:
        print("  OK    no alert storms in the last %dh" % a.hours)

    # ---- 2. ALERTS THAT REACHED NOBODY
    try:
        nob = c.execute("SELECT COUNT(*) n FROM alert_attempt WHERE (channel IS NULL OR "
                        "outcome='no_channel') AND attempted_at > ?", (cut,)).fetchone()["n"]
        if nob:
            add("BAD", "%d alert(s) reached nobody" % nob,
                "A seat opened, we tried, and no channel delivered. The student was never told.",
                "Check SMTP and VAPID config; the watch should still be retrying.")
        else:
            print("  OK    every alert reached a human (0 silent failures)")
    except sqlite3.Error as e:
        add("UNVERIFIED", "Could not check silent delivery failures", str(e)[:80])

    # ---- 3. SCHOOLS DARK WHILE SOMEONE IS WATCHING THEM
    # Measured against the SNAPSHOT's own clock, not wall-clock. A backup is hours old by
    # the time anyone reads it, so comparing to now() reports every school dark — which is
    # exactly the false alarm that teaches you to ignore a checker.
    try:
        snap = c.execute("SELECT MAX(started) t FROM guardian_cycles").fetchone()["t"] \
            or os.path.getmtime(db)
        dark = c.execute("""
            SELECT w.school, COUNT(DISTINCT w.id) watches, MAX(g.created) last
            FROM watches w LEFT JOIN guardian_watch_results g ON g.watch_id = w.id
            GROUP BY w.school HAVING last IS NULL OR last < ?""",
                         (snap - DARK_SECS,)).fetchall()
        for d in dark:
            when = ("never" if not d["last"] else
                    "%.0f min before the snapshot ended" % ((snap - d["last"]) / 60))
            add("BAD", "%s has not been checked (%s)" % (d["school"], when),
                "%d live watch(es) there. If a seat opens, nobody is told. The student sees "
                "silence and assumes the class is still full." % d["watches"],
                "Check the adapter and the poller for that school.")
        if not dark:
            print("  OK    every school with a live watch is being polled")
    except sqlite3.Error as e:
        add("UNVERIFIED", "Could not check for dark schools", str(e)[:80])

    # ---- 4. WATCHES QUIETLY STRANDED ON A ROLLED TERM
    try:
        st = c.execute("SELECT COUNT(*) n FROM guardian_watch_results "
                       "WHERE outcome='blocked_wrong_term' AND created > ?", (cut,)).fetchone()["n"]
        if st:
            add("BAD", "%d watch check(s) blocked on a stale term" % st,
                "The school moved to a new semester. Those watches can never fire again.",
                "ops/TERM-ROLL-PROCEDURE.md. Do NOT just bump the term.")
        else:
            print("  OK    no watches stranded on an old semester")
    except sqlite3.Error as e:
        add("UNVERIFIED", "Could not check term-roll stranding", str(e)[:80])

    # ---- 5. DID ANY ALERT GET ACTED ON?
    try:
        sent = c.execute("SELECT COUNT(*) n FROM alert_attempt WHERE outcome='sent' "
                         "AND attempted_at > ?", (cut,)).fetchone()["n"]
        clk = c.execute("SELECT COUNT(*) n FROM alert_attempt WHERE clicked_at IS NOT NULL "
                        "AND attempted_at > ?", (cut,)).fetchone()["n"]
        if sent and not clk:
            add("WARN", "%d alert(s) sent, none clicked" % sent,
                "Either they arrived too late to matter, went to spam, or the seat was gone. "
                "All three are worth knowing and none of them show up as an error.",
                "Ask a real recipient whether it arrived and whether it was useful.")
        elif sent:
            print("  OK    %d alert(s) sent, %d clicked" % (sent, clk))
        else:
            print("  --    no alerts in this window (nothing to judge)")
    except sqlite3.Error as e:
        add("UNVERIFIED", "Could not check click-through", str(e)[:80])

    # ---- 6. THINGS NOBODY HAS MEASURED. Silence here is how trust gets broken.
    add("UNVERIFIED", "Inbox placement",
        "Nothing in this database knows whether an email landed in the inbox or in spam. "
        "SMTP reports handoff, not delivery.",
        "Ask a recipient on a phone that has never marked SeatWatch 'not spam'.")
    add("UNVERIFIED", "The signup journey for a stranger",
        "No automated check walks signup -> pick school -> create watch -> receive alert.",
        "Watch someone do it who has never seen it before.")

    # ---- verdict
    bad = [f for f in FINDINGS if f["sev"] == "BAD"]
    warn = [f for f in FINDINGS if f["sev"] == "WARN"]
    unv = [f for f in FINDINGS if f["sev"] == "UNVERIFIED"]

    for group, label in ((bad, "WOULD UPSET A STUDENT"), (warn, "WORTH KNOWING"),
                         (unv, "NOT MEASURED — no one can tell you these are fine")):
        if group:
            print("\n" + "-" * 72 + "\n  %s\n" % label + "-" * 72)
            for f in group:
                print("  [%s] %s" % (f["sev"], f["title"]))
                print("        %s" % f["detail"])
                if f["fix"]:
                    print("        FIX: %s" % f["fix"])

    print("\n" + "=" * 72)
    if bad:
        print("  VERDICT: DO NOT POINT STUDENTS AT THIS YET — %d issue(s) above." % len(bad))
    else:
        print("  VERDICT: nothing here would upset a student, in the last %dh, in what this"
              % a.hours)
        print("  file knows how to check. That is not the same as 'no bugs', and the")
        print("  UNVERIFIED list above is the honest edge of what anyone can promise you.")
    print("=" * 72)
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
