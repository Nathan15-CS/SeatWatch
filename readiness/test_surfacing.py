"""READINESS #12 — every silent-failure condition actually reaches a human.

THE PATTERN THIS EXISTS FOR: every bug found in the 24h before this was written was a
silent failure or evidence recorded without being surfaced. Not one was a wrong algorithm.
The Guardian was excellent at RECORDING and weak at TELLING SOMEONE:

  parse_qs dropping blanks  every inbound text 403'd, visible only in a log nobody watched
  blocked_wrong_term        recorded faithfully as an incident, paged nobody
  lease stand-down          logged; the TAKEOVER wasn't, so silence read as death
  deploy smoke check        passed on a "Poller started" line 15 hours stale
  feedback send failure     stored, logged once, never retried
  21610 self-heal           correct code, never executed, zero coverage

Only a RED cycle paged. Everything below finalized YELLOW (or, for school_missing,
GREEN) and told no one, while a student's watch had silently stopped working forever.

This pins the DECISION, not just the behaviour: conditions that must page, and conditions
deliberately kept quiet so the next person doesn't "fix" the silence and cause alert
fatigue. A condition moving between those lists should require editing this file.
"""
import os, sys, time, tempfile, warnings

warnings.filterwarnings("ignore")

# Conditions where a student's watch has silently stopped working. MUST page.
MUST_PAGE = {
    "blocked_wrong_term": "term rolled; watches blocked and can never fire again",
    "school_missing":     "watch points at a school id no longer in the registry",
    "section_missing":    "the watched section is gone from the catalogue",
}
# Deliberately quiet, with the reason. Paging these would be alert fatigue.
MUST_NOT_PAGE = {
    "blocked_stale_data": "fail-closed guard working normally; suppresses nothing real",
    "blocked_gate":       "gate refusing thin data is ordinary operation",
    "alert_undelivered":  "app.py already pages per-watch via operator_alert(); "
                          "paging here too would double-page the most urgent condition",
    "checked_no_change":  "the overwhelmingly common healthy outcome",
}


def run():
    os.environ["SEATWATCH_DB"] = os.path.join(tempfile.mkdtemp(), "surf.db")
    sys.path.insert(0, os.path.expanduser("~/seatwatch"))
    import app, guardian
    app.init_db()

    results = []
    def check(n, c, d=""): results.append((n, bool(c), d))

    state, pages = {}, []
    clock = [time.time()]
    guardian.configure(app.db,
                       lambda k, d=None: state.get(k, d),
                       lambda **kv: state.update(kv),
                       lambda *a: None,
                       lambda m: pages.append(m),
                       now_fn=lambda: clock[0], mode="shadow", deploy_sha="")

    class Row(dict):
        def keys(self): return list(super().keys())

    def run_cycle(outcome, school="umd", wid=1):
        pages.clear()
        r = Row({"id": wid, "user_id": 1, "school": school, "course": "CHEM231",
                 "section": "0101", "term": "202608"})
        cyc = guardian.begin_cycle([r])
        guardian.record(cyc, wid, outcome, why="readiness probe")
        st = guardian.finalize(cyc)
        with app.db() as c:
            c.execute("DELETE FROM guardian_incidents")
        return st, list(pages)

    # ---- the conditions that must reach a human ----
    for oc, why in MUST_PAGE.items():
        state.clear(); clock[0] += 7 * 3600          # clear the damper between probes
        st, p = run_cycle(oc)
        check(f"{oc} PAGES a human ({why})", bool(p),
              f"status={st}, no page — a dead watch would go unnoticed")
        check(f"{oc} does not finalize GREEN", st != "GREEN",
              f"status={st}: the dashboard would read healthy")

    # ---- the conditions deliberately kept quiet ----
    for oc, why in MUST_NOT_PAGE.items():
        state.clear(); clock[0] += 7 * 3600
        st, p = run_cycle(oc)
        check(f"{oc} stays quiet ({why[:46]}...)", not p,
              "now paging: check this is intended, alert fatigue is a real bug")

    # ---- genuinely broken states still page loudly ----
    for oc in ("write_failed", "blocked_mass_freeze"):
        state.clear(); clock[0] += 7 * 3600
        st, p = run_cycle(oc)
        check(f"{oc} still RED + pages", st == "RED" and bool(p), f"status={st} pages={len(p)}")

    # ---- damping: correct, but not a firehose and not a mute button ----
    state.clear(); clock[0] += 7 * 3600
    first = run_cycle("blocked_wrong_term")[1]
    repeat = 0
    for _ in range(5):
        clock[0] += 20
        repeat += len(run_cycle("blocked_wrong_term")[1])
    check("first occurrence pages immediately", bool(first))
    check("repeats within the window are damped", repeat == 0,
          f"{repeat} extra pages — a rolled school would page every 20s")

    clock[0] += 20
    other = run_cycle("blocked_wrong_term", school="usf", wid=2)[1]
    check("a DIFFERENT school still gets through", bool(other),
          "one bad school would mute every other school")

    clock[0] += guardian.TUNING["PAGE_COOLDOWN_S"] + 60
    again = run_cycle("blocked_wrong_term")[1]
    check("re-pages after the cooldown (not a one-shot)", bool(again),
          "an unresolved condition would be announced once and never again")

    # ---- a school going dark must be announced ----
    state.clear(); clock[0] += 7 * 3600
    pages.clear()
    for _ in range(6):
        clock[0] += 20
        r = Row({"id": 9, "user_id": 1, "school": "utk", "course": "X",
                 "section": "1", "term": "202608"})
        cyc = guardian.begin_cycle([r])
        guardian.note_fetch(cyc, "utk", False, 12, None)
        guardian.record(cyc, 9, "adapter_failed", why="host down")
        guardian.finalize(cyc)
    check("a persistently dead adapter pages", bool(pages),
          "a school could be unreachable for hours with every watch on it dead")
    check("the adapter page names the school", any("utk" in p for p in pages),
          "an unattributed page cannot be acted on")

    p_ = sum(ok for _, ok, _ in results)
    f_ = sum(not ok for _, ok, _ in results)
    return p_, f_, results


if __name__ == "__main__":
    p, f, res = run()
    for n, ok, d in res:
        print(f"  [{'PASS' if ok else '*** FAIL'}] {n}{('  ' + d) if d and not ok else ''}")
    print(f"\n  {p} passed, {f} failed")
    sys.exit(1 if f else 0)
