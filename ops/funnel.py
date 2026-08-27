#!/usr/bin/env python3
"""Where do students stop? The activation funnel, read from production.

    python3 ops/funnel.py            the funnel, last 30 days
    python3 ops/funnel.py 90         a different window

WHY THIS EXISTS. Between 2026-08-16 and 2026-08-27 seven strangers signed in with Google
and six of them never created a watch. Nothing recorded what they saw or tried, so three
completely different problems were indistinguishable from the database:

    our coverage failed them      -> fix the adapter (an engineering problem)
    they mistyped a course code   -> fix the form    (a design problem)
    they looked and lost interest -> fix the pitch   (a product problem)

Each has a different fix and they are not interchangeable. This tells them apart.

WHAT IT DOES NOT DO. It reports only what was recorded, and says so when a stage has no
data rather than printing a confident zero. A funnel that cannot tell "nobody was refused"
from "we were not measuring yet" is the same cry-wolf failure this codebase has hit three
times; the instrumentation shipped on 2026-08-27, so anything before that reads UNMEASURED,
never 0.

EXIT CODES
    0  the funnel printed
    2  could NOT reach production — treat as "unknown", never as "fine"
"""
import os
import subprocess
import sys

VM = "ubuntu@141.148.27.134"
KEY = os.path.expanduser("~/.ssh/seatwatch-vm.key")

# Rejections, worst-first. The order is the order I would act on them: a student whose
# college we cannot read is a student we already earned and then lost.
REJECTIONS = [
    ("school_unlisted", "their college is supported but UNREADABLE right now"),
    ("course_not_found", "we could not find the course they typed"),
    ("course_format_bad", "the course code did not match the school's format"),
    ("section_not_found", "the course exists, the section they named does not"),
    ("no_sections_given", "they left the section box empty"),
    ("school_invalid", "no such school submitted"),
    ("wall_hit", "hit the free-plan section limit"),
    ("simultaneous_course_need", "wanted more than one class on free"),
    ("free_ineligible", "free class already used on another account"),
]

REMOTE = r'''
import sqlite3, time, sys
DB = "/home/ubuntu/seatwatch/watches.db"
WINDOW_D = float(sys.argv[1]) if len(sys.argv) > 1 else 30.0
now = time.time(); since = now - WINDOW_D * 86400
out = []
def p(k, v): out.append("%s\t%s" % (k, v))
try:
    c = sqlite3.connect("file:%s?mode=ro" % DB, uri=True); c.row_factory = sqlite3.Row
except Exception as e:
    print("FATAL\tcannot open db: %s" % e); raise SystemExit(0)

cols = {r[1] for r in c.execute("PRAGMA table_info(conv_signals)")}
p("has_detail", int("detail" in cols))
# The earliest signal of ANY kind bounds what this data can honestly answer.
first = c.execute("SELECT MIN(created) FROM conv_signals").fetchone()[0]
p("first_signal_age_d", round((now-first)/86400.0, 1) if first else -1)

p("signups", c.execute("SELECT COUNT(*) FROM users WHERE created>?", (since,)).fetchone()[0])
p("signups_all", c.execute("SELECT COUNT(*) FROM users").fetchone()[0])
p("viewers", c.execute("SELECT COUNT(DISTINCT user_id) FROM conv_signals "
                       "WHERE kind='dash_view' AND created>?", (since,)).fetchone()[0])
p("views", c.execute("SELECT COUNT(*) FROM conv_signals "
                     "WHERE kind='dash_view' AND created>?", (since,)).fetchone()[0])
p("creators", c.execute("SELECT COUNT(DISTINCT user_id) FROM conv_signals "
                        "WHERE kind='watch_created' AND created>?", (since,)).fetchone()[0])
# Ground truth, independent of the signal table: who actually holds a watch right now.
p("holders", c.execute("SELECT COUNT(DISTINCT user_id) FROM watches").fetchone()[0])

for r in c.execute("SELECT kind, COUNT(*) n, COUNT(DISTINCT user_id) u FROM conv_signals "
                   "WHERE created>? AND kind NOT IN ('dash_view','watch_created') "
                   "GROUP BY kind ORDER BY n DESC", (since,)):
    p("rej", "%s|%s|%s" % (r["kind"], r["n"], r["u"]))

if "detail" in cols:
    for r in c.execute("SELECT kind, detail, COUNT(*) n FROM conv_signals "
                       "WHERE created>? AND detail IS NOT NULL AND detail!='' "
                       "AND kind NOT IN ('dash_view','watch_created') "
                       "GROUP BY kind, detail ORDER BY n DESC LIMIT 15", (since,)):
        p("detail", "%s|%s|%s" % (r["kind"], r["detail"], r["n"]))

# Signed up, was SHOWN the form, and still never created a watch. The population the whole
# exercise is about — named, so they can be emailed and asked.
for r in c.execute(
        "SELECT u.id, u.email, u.signup_source,"
        " (SELECT COUNT(*) FROM conv_signals s WHERE s.user_id=u.id AND s.kind='dash_view') v"
        " FROM users u WHERE u.created>? AND NOT EXISTS"
        " (SELECT 1 FROM watches w WHERE w.user_id=u.id)"
        " ORDER BY u.created DESC LIMIT 20", (since,)):
    p("stalled", "%s|%s|%s|%s" % (r["id"], r["email"] or "?",
                                  r["v"], r["signup_source"] if r["signup_source"] else "-"))
print("\n".join(out))
'''


def main():
    days = sys.argv[1] if len(sys.argv) > 1 else "30"
    try:
        r = subprocess.run(
            ["ssh", "-i", KEY, "-o", "IdentitiesOnly=yes", "-o", "ConnectTimeout=20", VM,
             "sudo python3 - %s <<'PYEOF'\n%s\nPYEOF" % (days, REMOTE)],
            capture_output=True, text=True, timeout=120)
    except Exception as e:
        print(f"  CANNOT CHECK — {type(e).__name__}: {e}")
        print("  VERDICT: UNKNOWN. Production was not reached; this is not 'no problems'.")
        return 2
    if r.returncode != 0 or not r.stdout.strip():
        print(f"  CANNOT CHECK — ssh exited {r.returncode}: {(r.stderr or '').strip()[:200]}")
        print("  VERDICT: UNKNOWN. Production was not reached; this is not 'no problems'.")
        return 2

    d, multi = {}, {"rej": [], "detail": [], "stalled": []}
    for line in r.stdout.splitlines():
        if "\t" not in line:
            continue
        k, v = line.split("\t", 1)
        (multi[k].append(v) if k in multi else d.__setitem__(k, v))
    if "FATAL" in d:
        print(f"  CANNOT CHECK — {d['FATAL']}")
        return 2

    def n(k, default=0):
        try:
            return int(float(d.get(k, default)))
        except ValueError:
            return default

    age = float(d.get("first_signal_age_d", -1))
    measured = age >= 0
    signups, viewers, creators = n("signups"), n("viewers"), n("creators")
    holders = n("holders")

    print(f"\n  ACTIVATION FUNNEL — last {days} days"
          f"   (signals recorded for {age:.1f}d)" if measured else
          f"\n  ACTIVATION FUNNEL — last {days} days")
    print("  " + "=" * 66)

    def bar(label, value, note=""):
        if value is None:
            print(f"  {label:<34} {'UNMEASURED':>9}   {note}")
            return
        pct = ""
        if signups:
            pct = f"{100.0 * value / signups:5.0f}%"
        print(f"  {label:<34} {value:>9}  {pct}  {note}")

    bar("signed up", signups)
    bar("...shown the add-a-class form", viewers if measured else None,
        "" if measured else "instrumentation shipped 2026-08-27")
    bar("...created a watch", creators if measured else None,
        "" if measured else "instrumentation shipped 2026-08-27")
    print(f"  {'holding a watch right now':<34} {holders:>9}"
          f"          (ground truth, independent of signals)")

    if measured and viewers and not creators:
        print("\n  Everyone who saw the form left without adding a class.")

    print("\n  WHY THEY STOPPED")
    print("  " + "-" * 66)
    if not multi["rej"]:
        if not measured:
            print("  UNMEASURED — nothing was recording rejections in this window.")
        elif viewers:
            print("  NOT ONE REJECTION was recorded, yet people saw the form and did not")
            print("  convert. They are not being turned away — they are choosing to stop.")
            print("  That points at the pitch or the form itself, not at coverage.")
        else:
            print("  No rejections, and nobody reached the form either.")
    else:
        seen = {}
        for row in multi["rej"]:
            kind, cnt, users = row.split("|")
            seen[kind] = (int(cnt), int(users))
        for kind, why in REJECTIONS:
            if kind in seen:
                cnt, users = seen.pop(kind)
                print(f"  {cnt:>4} ({users} student{'s' if users != 1 else ''})  {kind:<26} {why}")
        for kind, (cnt, users) in seen.items():           # anything not in the table
            print(f"  {cnt:>4} ({users} student{'s' if users != 1 else ''})  {kind:<26} —")

    if multi["detail"]:
        print("\n  WHAT EXACTLY THEY TYPED  (school:course)")
        print("  " + "-" * 66)
        for row in multi["detail"]:
            kind, detail, cnt = row.split("|", 2)
            print(f"  {cnt:>4}x  {kind:<24} {detail}")
        print("\n  A code repeated by SEVERAL students is our adapter, not their typing.")

    if multi["stalled"]:
        print("\n  SIGNED UP, NEVER WATCHED ANYTHING")
        print("  " + "-" * 66)
        print(f"  {'id':<4} {'email':<34} {'form views':>10}  source")
        for row in multi["stalled"]:
            uid, email, views, src = row.split("|", 3)
            shown = views if measured else "?"
            print(f"  {uid:<4} {email[:34]:<34} {shown:>10}  {src}")
        print("\n  'form views 0' means they never even reached the form — the drop is at")
        print("  sign-in or immediately after, not at the class picker.")
    print()
    return 0


if __name__ == "__main__":
    sys.exit(main())
