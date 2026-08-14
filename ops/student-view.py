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
    cut = time.time() - a.hours * 3600

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
    storms = c.execute("""
        SELECT watch_id, course, section, COUNT(*) n,
               MIN(sent_at) a, MAX(sent_at) b
        FROM alert_log
        WHERE sent_at > ? AND channel IN ('email','webpush','ntfy') AND watch_id IS NOT NULL
        GROUP BY watch_id, strftime('%Y-%m-%d %H', sent_at, 'unixepoch')
        HAVING n > ?""", (cut, STORM_PER_HOUR)).fetchall()
    if storms:
        for s in storms:
            add("BAD", "Alert storm — a student got %d messages about one class in an hour"
                % s["n"],
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
    try:
        dark = c.execute("""
            SELECT w.school, COUNT(DISTINCT w.id) watches, MAX(g.created) last
            FROM watches w LEFT JOIN guardian_watch_results g ON g.watch_id = w.id
            GROUP BY w.school HAVING last IS NULL OR last < ?""",
                         (time.time() - DARK_SECS,)).fetchall()
        for d in dark:
            when = ("never" if not d["last"] else
                    "%.0f min ago" % ((time.time() - d["last"]) / 60))
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
