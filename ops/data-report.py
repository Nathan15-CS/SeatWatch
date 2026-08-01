#!/usr/bin/env python3
"""Full data extraction for SeatWatch — demand, delivery, reliability.

WHY THIS EXISTS: every question worth asking about this product has been answered so far by
someone hand-writing a one-off SQL query, which means the answers are not comparable across
weeks and nobody can re-run them. This is the repeatable version. Run it on any snapshot and
diff two runs to see what actually changed.

ORDER IS DELIBERATE. Demand comes first because it is the only section that can tell you
whether to keep going. Reliability is last because a perfectly reliable product nobody uses
is still a dead product, and a report that opens with 19,000 green cycles invites you to feel
good about the wrong number.

READ-ONLY by construction (mode=ro). This must be safe to point at production.

USAGE
  python3 ops/data-report.py                    # newest local backup
  python3 ops/data-report.py --db /path/to.db   # a specific snapshot, or live on the VM
  python3 ops/data-report.py --json out.json    # machine-readable, for diffing runs
"""
import argparse, glob, json, os, sqlite3, sys, time

DAY = 86400


def q1(c, sql, args=(), default=0):
    """Scalar query that tolerates a missing table — schemas drift, a report should not crash."""
    try:
        r = c.execute(sql, args).fetchone()
        return (r[0] if r and r[0] is not None else default)
    except sqlite3.Error:
        return default


def qa(c, sql, args=()):
    try:
        return c.execute(sql, args).fetchall()
    except sqlite3.Error:
        return []


def pct(n, d):
    return "%5.1f%%" % (100.0 * n / d) if d else "    —"


def bar(n, d, w=28):
    return "█" * int(round(w * n / d)) if d else ""


def section(t):
    print("\n" + "=" * 66 + "\n  " + t + "\n" + "=" * 66)


# ------------------------------------------------------------------ DEMAND
def demand(c, out):
    section("1. DEMAND  — the only section that can tell you to stop")

    users = q1(c, "SELECT COUNT(*) FROM users")
    watches = q1(c, "SELECT COUNT(*) FROM watches")
    watchers = q1(c, "SELECT COUNT(DISTINCT user_id) FROM watches WHERE user_id IS NOT NULL")
    alerted_u = q1(c, "SELECT COUNT(DISTINCT user_id) FROM alert_attempt "
                      "WHERE user_id IS NOT NULL AND outcome='sent'")
    clicked_u = q1(c, "SELECT COUNT(DISTINCT user_id) FROM alert_attempt WHERE clicked_at IS NOT NULL")
    out["demand"] = dict(users=users, watches=watches, watchers=watchers,
                         alerted_users=alerted_u, clicked_users=clicked_u)

    # The funnel is the product. Every step below is a place a real student silently left.
    print("\n  FUNNEL")
    for label, n in (("signed up", users), ("created a watch", watchers),
                     ("received an alert", alerted_u), ("clicked through", clicked_u)):
        print("    %-20s %4d  %s %s" % (label, n, pct(n, users), bar(n, users)))
    if users and not clicked_u:
        print("    ^ nobody has ever clicked an alert. Until one person does, the value")
        print("      proposition is untested — not disproven, untested.")

    print("\n  SIGNUPS BY DAY")
    for d, n in qa(c, "SELECT date(created,'unixepoch'), COUNT(*) FROM users "
                      "GROUP BY 1 ORDER BY 1 DESC LIMIT 14"):
        print("    %s  %3d  %s" % (d, n, "▪" * n))

    print("\n  WATCHES BY SCHOOL  (concentration decides whether a parse break looks like a surge)")
    rows = qa(c, "SELECT school, COUNT(*) FROM watches GROUP BY 1 ORDER BY 2 DESC LIMIT 12")
    for s, n in rows:
        print("    %-14s %3d  %s %s" % (s, n, pct(n, watches), bar(n, watches, 20)))
    if rows and watches and rows[0][1] / float(watches) > 0.6:
        print("    ^ %s holds %s of all watches. A parse break there fires nearly everything"
              % (rows[0][0], pct(rows[0][1], watches).strip()))
        print("      at once — which is why a raw alert-count threshold cannot tell a broken")
        print("      adapter apart from a real seat release. Shape, not volume.")

    print("\n  MOST-WATCHED COURSES  (what students actually want — your beachhead list)")
    for s, cr, n in qa(c, "SELECT school, course, COUNT(*) FROM watches "
                          "GROUP BY 1,2 ORDER BY 3 DESC LIMIT 10"):
        print("    %-8s %-12s %3d" % (s, cr, n))

    sig = qa(c, "SELECT kind, COUNT(*) FROM conv_signals GROUP BY 1 ORDER BY 2 DESC")
    if sig:
        print("\n  CONVERSION SIGNALS")
        for k, n in sig:
            print("    %-24s %4d" % (k, n))

    pp = q1(c, "SELECT COUNT(*) FROM price_probe")
    if pp:
        print("\n  WILLINGNESS TO PAY")
        print("    shown a price       %4d" % pp)
        print("    clicked checkout    %4d" % q1(c, "SELECT COUNT(*) FROM price_probe WHERE clicked_checkout_at IS NOT NULL"))
        print("    purchased           %4d" % q1(c, "SELECT COUNT(*) FROM price_probe WHERE purchased_at IS NOT NULL"))
        for r, n in qa(c, "SELECT decline_reason, COUNT(*) FROM price_probe "
                          "WHERE decline_reason IS NOT NULL AND decline_reason<>'' GROUP BY 1 ORDER BY 2 DESC LIMIT 6"):
            print("      declined: %-28s %3d" % (r, n))

    fb = qa(c, "SELECT date(created,'unixepoch'), message FROM feedback ORDER BY created DESC LIMIT 8")
    print("\n  FEEDBACK  (%d total)" % q1(c, "SELECT COUNT(*) FROM feedback"))
    for d, m in fb:
        print("    %s  %s" % (d, (m or "")[:70].replace("\n", " ")))
    if not fb:
        print("    none yet — the box is live, nobody has typed in it")


# ---------------------------------------------------------------- DELIVERY
def delivery(c, out):
    section("2. DELIVERY  — did a human actually find out?")

    # alert_attempt is the DENOMINATOR: it records failures too. alert_log holds successes
    # only, so any rate computed from alert_log alone is guaranteed to look perfect.
    total = q1(c, "SELECT COUNT(*) FROM alert_attempt")
    nochan = q1(c, "SELECT COUNT(*) FROM alert_attempt WHERE channel IS NULL OR outcome='no_channel'")
    out["delivery"] = dict(attempts=total, no_channel=nochan)

    print("\n  attempts recorded      %4d" % total)
    print("  reached NOBODY         %4d   %s" % (nochan, "<-- INVESTIGATE" if nochan else "(clean)"))

    print("\n  BY CHANNEL          sent   clicked   click-rate")
    for ch, n, ck in qa(c, "SELECT COALESCE(channel,'(none)'), COUNT(*), "
                           "SUM(CASE WHEN clicked_at IS NOT NULL THEN 1 ELSE 0 END) "
                           "FROM alert_attempt GROUP BY 1 ORDER BY 2 DESC"):
        print("    %-16s %5d %7d      %s" % (ch, n, ck or 0, pct(ck or 0, n)))
    print("    ^ this table answers 'is SMS worth paying for' with data instead of priors.")
    print("      Do not decide the channel question until these rates differ meaningfully.")

    lat = qa(c, "SELECT channel, COUNT(*), ROUND(AVG(clicked_at-attempted_at)) "
                "FROM alert_attempt WHERE clicked_at IS NOT NULL GROUP BY 1")
    if lat:
        print("\n  TIME TO CLICK  (seconds — seats close fast, this is the real product metric)")
        for ch, n, s in lat:
            print("    %-16s n=%-4d avg %ss" % (ch, n, int(s or 0)))

    print("\n  ENROLMENT  (what a student can be reached ON)")
    print("    users with email      %4d" % q1(c, "SELECT COUNT(*) FROM users WHERE email IS NOT NULL AND email<>''"))
    print("    push subscriptions    %4d" % q1(c, "SELECT COUNT(*) FROM push_subs"))
    print("    SMS consented         %4d" % q1(c, "SELECT COUNT(*) FROM sms_consent"))


# ------------------------------------------------------------- RELIABILITY
def reliability(c, out):
    section("3. RELIABILITY  — necessary, never sufficient")

    cyc = qa(c, "SELECT status, COUNT(*) FROM guardian_cycles GROUP BY 1")
    tot = sum(n for _, n in cyc) or 1
    span = qa(c, "SELECT datetime(MIN(started),'unixepoch'), datetime(MAX(started),'unixepoch') "
                 "FROM guardian_cycles")
    if span and span[0][0]:
        # tuple() is load-bearing: row_factory is sqlite3.Row, which does not implement
        # the %-format tuple protocol and raises "not enough arguments" instead.
        print("\n  window   %s  ->  %s" % tuple(span[0]))
    print("  cycles   %d" % tot)
    for s, n in sorted(cyc, key=lambda r: -r[1]):
        print("    %-8s %6d  %s" % (s, n, pct(n, tot)))

    print("\n  OUTCOMES across every watch check")
    res = qa(c, "SELECT outcome, COUNT(*) FROM guardian_watch_results GROUP BY 1 ORDER BY 2 DESC")
    rt = sum(n for _, n in res) or 1
    for o, n in res:
        print("    %-24s %8d  %s" % (o, n, pct(n, rt)))

    # The enforcement question. An empty would_block means one of two very different things,
    # and the stored value cannot tell them apart — so report the SAMPLE, not just the result.
    gate = q1(c, "SELECT COUNT(*) FROM guardian_watch_results WHERE outcome IN "
                 "('alert_delivered','blocked_gate','blocked_mass_freeze')")
    nonempty = q1(c, "SELECT COUNT(*) FROM guardian_cycles WHERE notes LIKE '%would_block%' "
                     "AND notes NOT LIKE '%\"would_block\": []%'")
    out["enforce"] = dict(gate_evaluations=gate, would_block_nonempty=nonempty)
    print("\n  ENFORCEMENT EVIDENCE")
    print("    cycles where enforce would have blocked   %d" % nonempty)
    print("    times the gate was actually evaluated     %d   <-- THE SAMPLE SIZE" % gate)
    print("    A zero above means nothing unless this second number is large. The gate only")
    print("    runs when an alert is pending; every other cycle leaves the field empty for")
    print("    a boring reason. Never quote the first number without the second.")

    inc = qa(c, "SELECT kind, severity, COUNT(*) FROM guardian_incidents GROUP BY 1,2 ORDER BY 3 DESC")
    print("\n  INCIDENTS  (%s)" % ("none recorded" if not inc else "%d kinds" % len(inc)))
    for k, sv, n in inc:
        print("    %-24s %-8s %4d" % (k, sv, n))

    bad = qa(c, "SELECT school, checks, failures, consec_fail FROM guardian_adapter_health "
                "WHERE failures > 0 ORDER BY 1.0*failures/NULLIF(checks,0) DESC LIMIT 10")
    print("\n  WORST ADAPTERS  (a school failing here alerts nobody who signs up for it)")
    if not bad:
        print("    no school has recorded a failure")
    for s, ch, f, cf in bad:
        print("    %-14s %6d checks  %4d fail  %s  consec=%d" % (s, ch, f, pct(f, ch), cf))

    stale = q1(c, "SELECT COUNT(*) FROM guardian_watch_results WHERE outcome='blocked_wrong_term'")
    print("\n  TERM-ROLL EXPOSURE")
    print("    watches blocked on a stale term   %d %s" % (
        stale, "<-- students are silently receiving NOTHING" if stale else "(clear)"))

    dbf = out.get("_dbfile")
    if dbf and os.path.exists(dbf):
        mb = os.path.getsize(dbf) / 1e6
        wr = q1(c, "SELECT COUNT(*) FROM guardian_watch_results")
        nw = q1(c, "SELECT COUNT(*) FROM watches") or 1
        print("\n  STORAGE")
        print("    database        %.1f MB" % mb)
        print("    evidence rows   %d  (~%.1f MB per watch at the current retention window)"
              % (wr, mb / nw))
        print("    Growth tracks WATCH COUNT, not calendar time. Multiply by your target")
        print("    student count before assuming the free storage tier still fits.")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--db", default="")
    ap.add_argument("--json", default="")
    a = ap.parse_args()

    db = a.db
    if not db:
        cands = sorted(glob.glob(os.path.expanduser("~/seatwatch-backups/watches-*.db")))
        if not cands:
            sys.exit("no --db given and no backups found in ~/seatwatch-backups/")
        db = cands[-1]
    if not os.path.exists(db):
        sys.exit("no such database: %s" % db)

    print("SeatWatch data report")
    print("source   %s" % db)
    print("size     %.1f MB" % (os.path.getsize(db) / 1e6))
    print("run      %s UTC" % time.strftime("%Y-%m-%d %H:%M:%S", time.gmtime()))

    c = sqlite3.connect("file:%s?mode=ro" % db, uri=True)
    c.row_factory = sqlite3.Row
    out = {"_dbfile": db, "generated": time.time()}
    demand(c, out)
    delivery(c, out)
    reliability(c, out)

    print("\n" + "=" * 66)
    print("  Re-run this after the beta and diff the two. A single run is a photograph;")
    print("  two runs are the only thing that can tell you whether anything is working.")
    print("=" * 66)

    if a.json:
        out.pop("_dbfile", None)
        json.dump(out, open(a.json, "w"), indent=1)
        print("\nmachine-readable: %s" % a.json)


if __name__ == "__main__":
    main()
