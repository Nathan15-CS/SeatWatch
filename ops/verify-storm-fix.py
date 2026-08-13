#!/usr/bin/env python3
"""Did the repeat-alert cooldown hold during a REAL churn event?

    sudo python3 ops/verify-storm-fix.py

Manager's definition of done for the alert-storm fix has three parts. Tests failing before
and passing after is item 1; a gated deploy is item 2. This is item 3, and it is the one
that cannot be faked in a suite: the next time a contested section flips repeatedly, the
ledger must show MANY closed->open transitions against FEW delivered alerts — the exact
inverse of the 8-and-8 that started this.

The pre-fix incident, for comparison:
    watch 27 (CMSC216 0102)   8 checked_closed_reset   8 alert_delivered   8 emails
A passing result looks like many resets and one or two alerts, with the surplus visible in
the log as "repeat within cooldown — not re-sent".

Prints VERDICT: NO CHURN YET when there is nothing to judge, rather than claiming success
from an absence of evidence — a quiet night is not proof of a fix.
"""
import collections
import os
import sqlite3
import sys
import time

DB = "/home/ubuntu/seatwatch/watches.db"


def fix_live_since():
    """When the running app.py was last written — i.e. when this fix went live.

    NOT read from DEPLOYED.log: that file is committed locally and is NOT in the deploy
    set, so on the VM it is stale or missing. The first version of this script looked for
    the sha there, silently fell back to "24 hours ago", swept in the PRE-fix storm and
    printed HELD next to eight emails. A verifier that reports success on the exact
    incident it was written to detect is worse than no verifier.

    app.py's mtime is written by scp on every app deploy, lives on the machine being
    judged, and cannot disagree with the code actually running.
    """
    return os.path.getmtime("/home/ubuntu/seatwatch/app.py")


since = fix_live_since()
c = sqlite3.connect(DB)
c.row_factory = sqlite3.Row
print("  fix live since %s (%.1f h ago)\n"
      % (time.strftime("%Y-%m-%d %H:%M UTC", time.gmtime(since)), (time.time() - since) / 3600))

per = collections.defaultdict(dict)
for r in c.execute("SELECT watch_id, outcome, COUNT(*) n FROM guardian_watch_results "
                   "WHERE created > ? GROUP BY watch_id, outcome", (since,)):
    per[r["watch_id"]][r["outcome"]] = r["n"]

mails = collections.Counter()
for r in c.execute("SELECT watch_id, COUNT(*) n FROM alert_log WHERE sent_at > ? "
                   "AND channel != 'sms' GROUP BY watch_id", (since,)):
    mails[r["watch_id"]] = r["n"]

print("  %-8s %-14s %-16s %-8s %s" % ("watch", "closed_reset", "alert_delivered", "emails", "verdict"))
print("  " + "-" * 74)
churned = worst = 0
for w in sorted(per):
    resets = per[w].get("checked_closed_reset", 0)
    alerts = per[w].get("alert_delivered", 0)
    if resets < 2:
        continue                       # not a churn event; nothing to judge
    churned += 1
    n_mail = mails.get(w, 0)
    # The contract is at most ONE mail per watch per cooldown window — so measure the
    # busiest actual window, not the total. Allowing "one per elapsed window" was the
    # first version's other bug: after 24 hours it permitted 49 emails and would have
    # called the original storm compliant.
    times = [r["sent_at"] for r in c.execute(
        "SELECT sent_at FROM alert_log WHERE watch_id=? AND sent_at>? AND channel!='sms' "
        "ORDER BY sent_at", (w, since))]
    busiest = 0
    for i, t0 in enumerate(times):
        busiest = max(busiest, sum(1 for t in times[i:] if t - t0 < 1800))
    good = busiest <= 1
    worst = max(worst, busiest)
    print("  %-8s %-14s %-16s %-8s %s"
          % (w, resets, alerts, "%d (max %d/window)" % (n_mail, busiest),
             "HELD" if good else "*** STORMED ***"))

print()
if not churned:
    print("  VERDICT: NO CHURN YET — nothing has flipped repeatedly since the fix went live.")
    print("  This is NOT a pass. A quiet night proves nothing; re-run after add/drop churn.")
    sys.exit(2)
print("  VERDICT: %s — %d churn event(s); busiest 30-min window sent %d email(s)"
      % ("HELD" if worst <= 1 else "STORMED", churned, worst))
sys.exit(0 if worst <= 1 else 1)
