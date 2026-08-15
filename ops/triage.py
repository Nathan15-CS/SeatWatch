#!/usr/bin/env python3
"""What in PRODUCTION needs a human or an agent right now?

    python3 ops/triage.py

WHY THIS EXISTS. Nathan receives SeatWatch's operator mail and has to relay anything
important into a session by hand. He asked for the reverse: problems should reach whoever
can fix them without him acting as the router. A model has no inbox, so the only mechanism
that actually works is for a session to ASK production what is wrong the moment it starts.
CLAUDE.md points every session here.

WHAT IT IS NOT. It runs no checks of its own and duplicates no logic:

    readiness.py            is the CODE correct                (local, synthetic)
    ops/student-view.py     would a STUDENT be annoyed          (a backup snapshot)
    ops/verify-storm-fix.py did the two alert gates hold        (production ledger)
    ops/operator_engine.py  scheduled local duties — never SSHes, by invariant
    ops/triage.py           what is WRONG IN PRODUCTION, right now

THE ONE RULE IT OBEYS, learned the hard way three times on 2026-08-14. A check that
cannot tell healthy traffic from a defect will eventually be believed about the wrong
one. A no_channel row was reported as SeatWatch's first outage when the student had
clicked through 13 seconds earlier; student-view.py printed DO NOT LAUNCH about pre-fix
incidents because its deploy log is not on the VM; the section-collapse detector cried
"DROPPING 13 of 13" at a school that simply had not answered. So: this never reports
CLEAN when it could not look. Unreachable is its own verdict and its own exit code.

EXIT CODES
    0  nothing needs you
    1  something needs attention (details printed)
    2  could NOT check — treat exactly as "unknown", never as "fine"
"""
import subprocess
import sys

VM = "ubuntu@141.148.27.134"
KEY = "~/.ssh/seatwatch-vm.key"

# Runs ON the VM. Prints "KEY\tVALUE" lines; this side does the judging so the remote
# half stays trivially reviewable and has no opinions of its own.
REMOTE = r'''
import sqlite3, time, os
DB="/home/ubuntu/seatwatch/watches.db"
now=time.time(); out=[]
def p(k,v): out.append("%s\t%s"%(k,v))
try:
    c=sqlite3.connect("file:%s?mode=ro"%DB, uri=True); c.row_factory=sqlite3.Row
except Exception as e:
    print("FATAL\tcannot open db: %s"%e); raise SystemExit(0)

p("open_incidents", c.execute(
    "SELECT COUNT(*) FROM guardian_incidents WHERE status='open'").fetchone()[0])
for r in c.execute("SELECT kind,severity,school,count FROM guardian_incidents "
                   "WHERE status='open' ORDER BY last_seen DESC LIMIT 8"):
    p("incident", "%s|%s|%s|x%s"%(r[1],r[0],r[2] or "-",r[3]))

# Silent failures: an alert that reached NOBODY. Suppressed repeats are deliberately not
# logged here, so any row is a genuine miss.
p("silent_failures_24h", c.execute(
    "SELECT COUNT(*) FROM alert_attempt WHERE outcome='no_channel' AND attempted_at>?",
    (now-86400,)).fetchone()[0])

# Stranded watches: bound to a term the school has rolled past. They never fire.
try:
    p("stranded", c.execute(
        "SELECT COUNT(*) FROM watches w WHERE w.term IS NOT NULL AND w.term!='' "
        "AND EXISTS(SELECT 1 FROM guardian_watch_results g WHERE g.watch_id=w.id "
        "AND g.outcome='blocked_wrong_term' AND g.created>?)", (now-86400,)).fetchone()[0])
except Exception: p("stranded","?")

p("watches", c.execute("SELECT COUNT(*) FROM watches").fetchone()[0])
p("users", c.execute("SELECT COUNT(*) FROM users").fetchone()[0])

# Is the poller actually running? Last guardian result is the freshest proof of life.
last = c.execute("SELECT MAX(created) FROM guardian_watch_results").fetchone()[0] or 0
p("poller_idle_s", int(now-last) if last else -1)

# Adapters that failed repeatedly in the last day = schools effectively dark.
for r in c.execute("SELECT school, COUNT(*) n FROM guardian_watch_results "
                   "WHERE outcome='adapter_failed' AND created>? GROUP BY school "
                   "HAVING n>=20 ORDER BY n DESC LIMIT 6", (now-86400,)):
    p("dark", "%s|%s"%(r[0],r[1]))

# Alert gates: were there COMPLETED openings to judge since the running app went live?
since = os.path.getmtime("/home/ubuntu/seatwatch/app.py")
p("release_age_h", round((now-since)/3600.0,1))
p("alerts_since_release", c.execute(
    "SELECT COUNT(*) FROM alert_log WHERE sent_at>?", (since,)).fetchone()[0])
print("\n".join(out))
'''


def main():
    try:
        r = subprocess.run(
            ["ssh", "-i", KEY.replace("~", __import__("os").path.expanduser("~")),
             "-o", "IdentitiesOnly=yes", "-o", "ConnectTimeout=20", VM,
             "sudo python3 - <<'PYEOF'\n" + REMOTE + "\nPYEOF"],
            capture_output=True, text=True, timeout=120)
    except Exception as e:
        print(f"  CANNOT CHECK — {type(e).__name__}: {e}")
        print("  VERDICT: UNKNOWN. This is NOT 'fine'; production was not reached.")
        return 2
    if r.returncode != 0 or not r.stdout.strip():
        print(f"  CANNOT CHECK — ssh exited {r.returncode}: {(r.stderr or '').strip()[:200]}")
        print("  VERDICT: UNKNOWN. This is NOT 'fine'; production was not reached.")
        return 2

    d, multi = {}, {"incident": [], "dark": []}
    for line in r.stdout.splitlines():
        if "\t" not in line:
            continue
        k, v = line.split("\t", 1)
        (multi[k].append(v) if k in multi else d.__setitem__(k, v))
    if "FATAL" in d:
        print(f"  CANNOT CHECK — {d['FATAL']}")
        return 2

    def n(k, default=-1):
        try:
            return int(d.get(k, default))
        except ValueError:
            return default

    findings = []
    if n("open_incidents") > 0:
        findings.append(("OPEN INCIDENTS", "%s open" % d["open_incidents"],
                         multi["incident"]))
    if n("silent_failures_24h") > 0:
        findings.append(("SILENT FAILURE", "%s alert(s) reached NOBODY in 24h"
                         % d["silent_failures_24h"],
                         ["every row here is a student who missed a seat"]))
    if n("stranded") > 0:
        findings.append(("STRANDED WATCHES", "%s watch(es) bound to a rolled term"
                         % d["stranded"], ["they will never fire until re-created"]))
    idle = n("poller_idle_s")
    if idle < 0 or idle > 300:
        findings.append(("POLLER", "no cycle for %ss" % idle,
                         ["nothing is being watched at all"]))
    if multi["dark"]:
        findings.append(("SCHOOLS DARK", "%d school(s) failing repeatedly"
                         % len(multi["dark"]), multi["dark"]))

    print("  production: %s watch(es), %s user(s), poller idle %ss, "
          "release %sh old, %s alert(s) since"
          % (d.get("watches", "?"), d.get("users", "?"), d.get("poller_idle_s", "?"),
             d.get("release_age_h", "?"), d.get("alerts_since_release", "?")))
    print()
    if not findings:
        print("  VERDICT: NOTHING NEEDS YOU.")
        # Said out loud rather than implied. "No problems" and "no traffic to have
        # problems with" are different states, and only one of them is reassuring.
        if n("alerts_since_release", 0) == 0:
            print("  Note: ZERO alerts have fired since this release, so the alert path is")
            print("  unproven rather than proven. Clean here means 'nothing broke', not")
            print("  'it works'. Run ops/verify-storm-fix.py after real add/drop churn.")
        return 0

    print("  NEEDS ATTENTION")
    print("  " + "-" * 66)
    for title, summary, detail in findings:
        print("  [%s] %s" % (title, summary))
        for x in detail[:8]:
            print("        %s" % x)
    print("\n  VERDICT: %d thing(s) need attention." % len(findings))
    return 1


if __name__ == "__main__":
    sys.exit(main())
