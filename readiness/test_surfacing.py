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

    # --- PER-SCHOOL PAGES ------------------------------------------------------------
    # A real student arrived 2026-09-15 from ChatGPT, which found the ONE landing page in
    # a web index. 899 school pages give it 899 things to match — but 899 pages differing
    # only by a NAME is what Google's spam policy calls scaled content abuse, and it
    # demotes the whole domain. What makes these legitimate is that every number on them
    # is that school's own, re-measured nightly. So these checks are mostly about honesty:
    # real data, no invented data, and no page for a school we cannot serve.
    _cov, _cs, _blk = app.coverage, app.coverage_stats, app.blocked_schools
    app.coverage = lambda: {"umd": "OK", "dark": "EMPTY"}
    app.coverage_stats = lambda: {
        "umd": {"name": "University of Maryland",
                "stats": {"sections": 17, "open": 4, "full": 13}},
        "dark": {"name": "Dark University", "stats": {}}}
    app.blocked_schools = lambda: set()
    try:
        import schools as _s
        check("the suite has a real school to render (not a vacuous pass)",
              "umd" in _s.SCHOOLS)
        body = app.school_page("umd") or ""
        check("a covered school renders a page", bool(body))
        check("...naming the school", "University of Maryland" in body)
        check("...carrying ITS OWN measured numbers, not boilerplate",
              "17 sections" in body and "4 open" in body,
              "pages differing only by a name are doorway pages")
        check("...showing that school's real course-code format",
              getattr(_s.SCHOOLS["umd"], "example", "?") in body)
        check("...and disclaiming affiliation", "not affiliated" in body)
        check("a school we CANNOT read has NO page",
              app.school_page("dark") is None,
              "a live URL promising alerts at a dark school is a promise we break")
        check("an unknown id has no page", app.school_page("no-such-school") is None)
        for junk in ("x'; DROP TABLE--", "../../etc/passwd", "", "%2e%2e"):
            check(f"hostile id {junk!r} yields no page", app.school_page(junk) is None)
        sm = app.sitemap_xml()
        check("the sitemap is GENERATED from coverage, not hardcoded", "/s/umd" in sm)
        check("...a dark school is absent from it", "/s/dark" not in sm)
        check("...and it is still valid XML",
              sm.startswith("<?xml") and sm.strip().endswith("</urlset>"))
        idx = app.schools_index_page()
        check("the index links the per-school pages (else they are orphans)",
              "/s/umd" in idx and "University of Maryland" in idx)
        # The failure mode that matters: a broken sweep must not print zeros as fact.
        app.coverage_stats = lambda: {}
        b2 = app.school_page("umd") or ""
        check("with NO measured data it falls back to prose, never '0 sections'",
              bool(b2) and "0 sections" not in b2,
              "an unmeasured zero printed as a seat count is a page lying confidently")
        app.coverage_stats = lambda: (_ for _ in ()).throw(RuntimeError("sweep broken"))
        check("a THROWING stats reader still yields a page, not a 500",
              app.school_page("umd") is not None)
        check("...and the sitemap survives it",
              app.sitemap_xml().strip().endswith("</urlset>"))
    finally:
        app.coverage, app.coverage_stats, app.blocked_schools = _cov, _cs, _blk

    p_ = sum(ok for _, ok, _ in results)
    f_ = sum(not ok for _, ok, _ in results)
    return p_, f_, results


if __name__ == "__main__":
    p, f, res = run()
    for n, ok, d in res:
        print(f"  [{'PASS' if ok else '*** FAIL'}] {n}{('  ' + d) if d and not ok else ''}")
    print(f"\n  {p} passed, {f} failed")
    sys.exit(1 if f else 0)
