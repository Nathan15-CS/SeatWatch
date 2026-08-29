#!/usr/bin/env python3
"""How many watches can one box actually poll? Measured, not estimated.

    python3 ops/loadtest.py                    the default sweep
    python3 ops/loadtest.py 400 12 5           schools, courses/school, watches/course

WHY THIS EXISTS. The capacity question was being answered with arithmetic on a napkin —
"12 workers times 20 seconds divided by 0.6s" — which is a hypothesis, not a measurement.
It ignores everything run_cycle does BESIDES fetching: loading every watch row, the
guardian's per-watch bookkeeping, the sequential alert pass. Those are exactly the parts
that stop being free at scale, and they are invisible to napkin math.

HOW IT IS HONEST. It drives the REAL run_cycle against synthetic schools. Network latency
is simulated with time.sleep, which releases the GIL precisely the way a blocking socket
read does, so thread behaviour is faithful. No real registrar is touched — a load test
that hammered live universities to prove we could hammer live universities would be
absurd, and would get us blocked exactly as Towson blocked us.

WHAT IT DOES NOT MODEL. Real network variance and TLS handshakes; a real DB under
concurrent web traffic; and the per-school politeness ceiling, which is a limit on what
registrars tolerate rather than on what this code can do. That last one is usually the
real ceiling, and no benchmark on our own hardware can find it.
"""
import os
import sys
import tempfile
import time
import warnings

warnings.filterwarnings("ignore")

PER_COURSE_S = 0.6      # measured: Banner 0.58s, PeopleSoft 0.77s, UMD 0.05-0.18s
BUDGET_S = 20.0         # POLL_SECONDS — the cycle must finish inside this


def build(n_schools, courses_per_school, watches_per_course, per_course_s=PER_COURSE_S):
    """A synthetic registry + the watches that point at it.

    The fake school must return the SAME section ids the watches reference. The first
    version returned only "0101" while the seeder created watches on 0000..000N, so every
    watch resolved to section_missing — a YELLOW outcome, correctly written to disk, which
    made a write-volume measurement report 0% improvement. The benchmark was wrong, not
    the code. A fixture that cannot produce the steady state cannot measure it.
    """
    import schools as schools_mod

    class Fake:
        """One school. fetch() sleeps proportionally to the number of courses asked for,
        because that is what the real adapters do: a request per course, in sequence."""
        def __init__(self, i):
            self.id = "s%04d" % i
            self.name = "Synthetic %d" % i
            self.example = "AAA 100"

        def valid_course(self, c): return True
        def reg_url(self, course): return "https://x.test/%s" % course
        def cur_term(self): return "202608"

        def fetch(self, courses):
            time.sleep(per_course_s * len(courses))       # sequential per-course I/O
            secs = {"%04d" % k: {"open": False, "seats": 0}
                    for k in range(watches_per_course)}
            return {c: dict(secs) for c in courses}

    reg = {}
    for i in range(n_schools):
        f = Fake(i)
        reg[f.id] = f
    schools_mod.SCHOOLS = reg
    return reg


def seed(app, reg, courses_per_school, watches_per_course):
    with app.db() as c:
        c.execute("DELETE FROM watches")
        c.execute("INSERT OR IGNORE INTO users(id,google_sub,email,topic,created) "
                  "VALUES(1,'g_load','load@x','t_load',0)")
        rows = []
        for sid in reg:
            for j in range(courses_per_school):
                for k in range(watches_per_course):
                    rows.append((sid, "t_load", "C%03d" % j, "%04d" % k, "202608", 0, 0, 1))
        c.executemany("INSERT INTO watches(school,topic,course,section,term,alerted,"
                      "created,user_id) VALUES(?,?,?,?,?,?,?,?)", rows)
    return len(rows)


def measure(n_schools, courses_per_school, watches_per_course, per_course_s=PER_COURSE_S):
    os.environ["SEATWATCH_DB"] = os.path.join(tempfile.mkdtemp(), "load.db")
    sys.path.insert(0, os.path.expanduser("~/seatwatch"))
    import app
    app.init_db()
    app.EMAIL_ENABLED = False
    app.SMS_ENABLED = False
    app.send_email = lambda *a, **k: False
    app.send_sms = lambda *a, **k: False
    app.sw.notify = lambda *a, **k: True
    app.send_web_push = lambda *a, **k: 0
    app.operator_alert = lambda *a, **k: None

    # The guardian is configured in app.main(), which a benchmark never calls. Without
    # this it sits inert, writes nothing, and a "100% fewer rows" result would measure
    # only that nothing was running — the same trap as reporting a school dark because
    # we could not look at it. Configure it so the per-watch bookkeeping is REAL work.
    import guardian
    guardian.TUNING["POLL_S"] = app.POLL_SECONDS
    _state = {}
    guardian.configure(app.db, lambda k, d=None: _state.get(k, d),
                       lambda **kw: _state.update(kw),
                       lambda *a, **k: None, lambda *a, **k: None,
                       mode=os.environ.get("GUARDIAN_MODE", "enforce"), deploy_sha="bench")

    reg = build(n_schools, courses_per_school, watches_per_course, per_course_s)
    n_watches = seed(app, reg, courses_per_school, watches_per_course)
    lookups = n_schools * courses_per_school

    t0 = time.time()
    app.run_cycle()
    elapsed = time.time() - t0

    # The fetch floor: what the same work would cost with unlimited concurrency, i.e. the
    # slowest single school. Anything above this is our own serialisation, not the network.
    floor = courses_per_school * per_course_s
    return {
        "watches": n_watches, "lookups": lookups, "schools": n_schools,
        "courses_per_school": courses_per_school, "elapsed": elapsed,
        "floor": floor, "over_budget": elapsed > BUDGET_S,
        "per_lookup_ms": 1000.0 * elapsed / max(lookups, 1),
    }


def main():
    if len(sys.argv) >= 4:
        cases = [tuple(int(x) for x in sys.argv[1:4])]
    else:
        cases = [
            (2, 3, 4),        # today: 20 watches, 5 lookups
            (12, 4, 5),
            (40, 4, 5),
            (100, 4, 5),
            (40, 30, 5),      # CONCENTRATED: few schools, many courses each
        ]
    print("\n  LOAD TEST — real run_cycle, synthetic registrars (%.2fs per course)" % PER_COURSE_S)
    print("  budget: %.0fs per cycle\n" % BUDGET_S)
    print("  %-8s %-8s %-9s %-9s %-9s %s" %
          ("schools", "crs/sch", "lookups", "watches", "cycle", "verdict"))
    print("  " + "-" * 68)
    for n_s, cps, wpc in cases:
        r = measure(n_s, cps, wpc)
        verdict = "OVER BUDGET" if r["over_budget"] else "ok"
        if r["elapsed"] > BUDGET_S * 0.5 and not r["over_budget"]:
            verdict = "near limit"
        print("  %-8d %-8d %-9d %-9d %-9.1fs %s" %
              (r["schools"], r["courses_per_school"], r["lookups"], r["watches"],
               r["elapsed"], verdict))
        print("           fetch floor %.1fs (slowest single school) | %.0f ms per lookup"
              % (r["floor"], r["per_lookup_ms"]))
    print()


if __name__ == "__main__":
    sys.exit(main())
