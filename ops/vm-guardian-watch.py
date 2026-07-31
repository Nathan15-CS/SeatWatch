#!/usr/bin/env python3
"""Independent server-side watchdog. Runs from cron on the VM, emails only on breach.

WHY THIS EXISTS, AND WHY IT IS NOT REDUNDANT WITH THE GUARDIAN'S OWN PAGING:
an app that pages about its own health cannot page when it is the thing that broke.
The Guardian's page() runs inside the poller process; if that process is wedged,
crashed, or stuck holding a stale lease, it reports nothing and the silence looks
identical to health. This runs from cron, reads the DB directly, and mails out
through SMTP — it shares no code path with the thing it is watching.

It also does not depend on a laptop being open, which every Claude-scheduled task does.

DESIGN RULES
  * read-only on watches.db (mode=ro) — a watchdog must never be able to corrupt
    the thing it watches
  * silent unless something is wrong; a quiet channel stays a trusted channel
  * 12h per-condition cooldown so one persistent fault cannot bury the mailbox
  * exit 0 always — a cron that fails loudly every run trains you to ignore it
"""
import json, os, sqlite3, sys, time

DB = "/home/ubuntu/seatwatch/watches.db"
STATE = "/home/ubuntu/seatwatch/.watchdog-state.json"
APP_DIR = "/home/ubuntu/seatwatch"
ENV = "/etc/seatwatch.env"
COOLDOWN = 12 * 3600
STALE_CYCLE_SECS = 300          # ~15 missed cycles at 20s — well past a deploy's lease wait


def load_env():
    for line in open(ENV):
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            k, v = line.split("=", 1)
            os.environ.setdefault(k, v)


def breaches():
    """Return {condition_key: human_message}. Empty dict means healthy."""
    out, now = {}, time.time()
    c = sqlite3.connect("file:%s?mode=ro" % DB, uri=True)

    row = c.execute("SELECT MAX(started) FROM guardian_cycles").fetchone()
    last = row[0] if row and row[0] else 0
    if not last or now - last > STALE_CYCLE_SECS:
        age = int(now - last) if last else -1
        out["poller_stalled"] = (
            "POLLER STALLED: no completed cycle for %ss. Seats are NOT being checked and no "
            "student can be alerted. Check: systemctl is-active seatwatch" % age)
        return out            # nothing else is meaningful if it isn't cycling

    n_red = c.execute("SELECT COUNT(*) FROM guardian_cycles WHERE status='RED' AND started>?",
                      (now - 86400,)).fetchone()[0]
    if n_red:
        out["cycle_red"] = ("%d RED cycle(s) in the last 24h. Evidence in guardian_incidents."
                            % n_red)

    stale = c.execute(
        "SELECT school, term, adapter_term, COUNT(*) FROM guardian_watch_results "
        "WHERE outcome='blocked_wrong_term' AND cycle_id IN "
        "(SELECT cycle_id FROM guardian_cycles ORDER BY started DESC LIMIT 100) "
        "GROUP BY school, term, adapter_term").fetchall()
    if stale:
        lines = ["   %s: %d watches stamped %s, school now on %s" % (s, k, wt, at)
                 for s, wt, at, k in stale]
        out["term_roll"] = (
            "TERM ROLL — WATCHES STRANDED. These watches will never alert again and the "
            "students have not been told:\n" + "\n".join(lines) +
            "\n   Follow ops/TERM-ROLL-PROCEDURE.md. Do NOT bump the term to clear the error: "
            "a completed term returns plenty of data and looks healthy.")

    try:
        orph = c.execute("SELECT COUNT(*) FROM guardian_incidents WHERE kind='orphan_watch' "
                         "AND status!='resolved' AND last_seen>?", (now - 86400,)).fetchone()[0]
        if orph:
            out["orphan_watch"] = ("%d watch(es) point at a school no longer in the registry. "
                                   "Those watches are permanently dead." % orph)
    except sqlite3.Error:
        pass
    return out


def fresh(keys):
    """Filter to conditions not already mailed inside the cooldown, and persist."""
    now = time.time()
    try:
        seen = json.load(open(STATE))
    except Exception:
        seen = {}
    new = [k for k in keys if now - seen.get(k, 0) > COOLDOWN]
    for k in new:
        seen[k] = now
    for k in list(seen):
        if k not in keys and now - seen[k] > COOLDOWN:
            del seen[k]          # condition cleared; let it re-alert if it returns
    try:
        json.dump(seen, open(STATE, "w"))
        os.chmod(STATE, 0o600)
    except Exception:
        pass
    return new


def main():
    try:
        load_env()
        b = breaches()
        if not b:
            return
        send = fresh(list(b))
        if not send:
            return                       # still broken, already told them
        sys.path.insert(0, APP_DIR)
        os.chdir(APP_DIR)
        import app
        body = ("SeatWatch server-side watchdog found a problem.\n\n"
                + "\n\n".join(b[k] for k in send)
                + "\n\nThis check runs from cron on the VM and is independent of the app's own "
                  "paging, which cannot fire when the app itself is the fault.\n"
                  "You will not be mailed about the same condition again for 12 hours.")
        app.send_email(os.environ.get("WATCHDOG_TO", "nathananapolsky@gmail.com"),
                       "SeatWatch ALERT: " + ", ".join(send), body, "https://seatwatchapp.com/")
    except Exception:
        pass                             # never let the watchdog take the box down


if __name__ == "__main__":
    main()
