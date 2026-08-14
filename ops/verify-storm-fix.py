#!/usr/bin/env python3
"""Did the two alert gates hold during REAL churn?

    sudo python3 ops/verify-storm-fix.py

GATE 1, cooldown — how OFTEN we mail. Manager's definition of done for the alert-storm
fix had three parts: tests red-then-green (item 1), a gated deploy (item 2), and this,
the one that cannot be faked in a suite. The next time a contested section flips
repeatedly the ledger must show MANY closed->open transitions against FEW delivered
alerts — the exact inverse of the 8-and-8 that started this.

    pre-fix: watch 27 (CMSC216 0102)  8 closed_reset  8 alert_delivered  8 emails

GATE 2, confirmation — whether the seat was REACHABLE. Measured 2026-08-14 across every
alert SeatWatch had ever sent: 18 openings, median life 35 SECONDS, 14 of 18 gone inside
two minutes. Worse, a 23-second blip would fire, spend the 30-minute cooldown, and leave
nothing for the hour-long opening behind it — so only 2 of 4 genuine openings ever
reached anybody. Gate 2 asks the inverse question of gate 1: not "how many emails" but
"did we mail about a seat that had already vanished", and separately "did a real opening
go unmailed", which is the worse failure of the two.

Both gates print NO CHURN YET / nothing to judge rather than claiming success from an
absence of evidence — a quiet afternoon is not proof of a fix.
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
else:
    print("  VERDICT: %s — %d churn event(s); busiest 30-min window sent %d email(s)"
          % ("HELD" if worst <= 1 else "STORMED", churned, worst))


# ------------------------------------------------------------------ gate 2: confirmation
# The cooldown above caps how OFTEN we mail. It says nothing about whether the seat was
# reachable. Measured 2026-08-14: 18 openings, median life 35s, 14 of 18 gone inside two
# minutes — and because a blip spent the 30-minute cooldown, only 2 of the 4 hour-long
# openings ever reached anybody. So the question here is the inverse of gate 1: not "how
# many emails" but "did we mail about a seat that had already vanished".
CONFIRM = 120           # app.CONFIRM_SECONDS default
print("\n" + "=" * 78)
print("  CONFIRMATION GATE — did any email go out for a seat that died inside %ds?\n" % CONFIRM)

rows = [dict(r) for r in c.execute(
    "SELECT watch_id, course, section, outcome, created FROM guardian_watch_results "
    "WHERE created > ? AND outcome IN ('alert_delivered','checked_open_already',"
    "'checked_closed_reset','checked_unconfirmed','checked_no_change') "
    "ORDER BY watch_id, created", (since,))]

OPEN = ("checked_unconfirmed", "alert_delivered", "checked_open_already")
CLOSED = ("checked_closed_reset", "checked_no_change")

# An episode must begin with an observed closed->OPEN edge. The first version of this
# started one at the first OPEN row of any kind, which flagged watch 37 as a MISSED
# opening: an all-sections CMSC216 watch, correctly alerted on 08-02 and latched ever
# since, that emits nothing but checked_open_already. A standing 12-day opening is not
# a seat nobody was told about, and a verifier that cannot tell those apart fails on
# healthy traffic — which is how it would get ignored the day it is right.
#
# Episodes are also timed from the rising edge rather than from the alert: with
# confirmation live the alert lands ~CONFIRM seconds in, so measuring from it would
# under-report every episode by exactly the delay under test.
eps, cur, seen_closed = [], None, set()
for r in rows:
    w = r["watch_id"]
    if r["outcome"] in CLOSED:
        seen_closed.add(w)
        if cur is not None and cur["w"] == w:
            cur["t1"] = r["created"]
            eps.append(cur); cur = None
        continue
    if w not in seen_closed:
        continue                      # already open when the window opened — not new
    if cur is None or cur["w"] != w:
        cur = {"w": w, "c": r["course"], "s": r["section"],
               "t0": r["created"], "t1": r["created"], "mailed": False}
    cur["t1"] = r["created"]
    cur["mailed"] |= r["outcome"] == "alert_delivered"
if cur:
    eps.append(cur)                   # still open right now; judged on what it has done

# An episode whose last observation is only a cycle or two old is STILL RUNNING. It has
# not failed to mail, it simply has not finished — judging it would report a miss every
# time the script is run while a seat happens to be open.
now = time.time()
for e in eps:
    e["live"] = (now - e["t1"]) < 3 * 23
done = [e for e in eps if not e["live"]]

held = [e for e in done if not e["mailed"] and (e["t1"] - e["t0"]) < CONFIRM]
leaked = [e for e in done if e["mailed"] and (e["t1"] - e["t0"]) < CONFIRM]
real = [e for e in done if e["t1"] - e["t0"] >= CONFIRM]

print("  %-8s %-11s %-7s %-13s %s" % ("watch", "course", "sec", "seat lasted", "outcome"))
print("  " + "-" * 66)
for e in sorted(eps, key=lambda e: e["t0"]):
    d = e["t1"] - e["t0"]
    print("  %-8s %-11s %-7s %-13s %s"
          % (e["w"], e["c"], e["s"] or "(all)",
             ("%.0f sec" % d) if d < 120 else ("%.0f min" % (d / 60)),
             "still open" if e["live"] else
             ("MAILED" if e["mailed"] else "held (unreachable)")))

if not done:
    print("  (no COMPLETED openings since the fix went live — nothing to judge yet)")
    print("  Not a pass. Re-run after add/drop churn produces a closed->open->closed cycle.")
    sys.exit(2)
print("\n  %d opening(s): %d blip(s) held, %d real opening(s), %d of those mailed"
      % (len(eps), len(held), len(real), sum(1 for e in real if e["mailed"])))
if leaked:
    print("  *** LEAKED: %d email(s) for a seat that died inside %ds" % (len(leaked), CONFIRM))
missed = [e for e in real if not e["mailed"]]
if missed:
    # Worse than noise. A real opening nobody heard about is the failure this whole
    # change exists to prevent, so it is called out separately from the leak count.
    print("  *** MISSED: %d opening(s) over %ds never mailed — check the cooldown, not "
          "confirmation" % (len(missed), CONFIRM))
print("\n  VERDICT: %s" % ("HELD" if not leaked and not missed else "*** FAILED ***"))
sys.exit(0 if (worst <= 1 and not leaked and not missed) else 1)
