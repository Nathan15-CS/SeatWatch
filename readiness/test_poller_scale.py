"""READINESS #32 — the poller scales without losing a watch or an outcome.

Two changes made for capacity, both in the safety-critical path:

  1. A school's courses are fetched in PARALLEL chunks instead of one sequential call.
     Measured effect: 400 lookups went from 21.6s to 4.2s, and a 30-course school from
     18s to under 5. The risk is that chunking silently changes WHAT comes back.

  2. Outcomes meaning "checked it, nothing happened" are no longer written per watch per
     cycle. That was 152 rows per watch per hour — 38 million rows/hour at 250k watches.
     The risk is that removing them removes evidence something depended on. (It already
     did: ops/triage.py inferred "school is dark" from the ABSENCE of success rows, so
     this change would have made every struggling school read as dark. That is why triage
     now reads guardian_adapter_health instead.)

The first version of the chunking deadlocked: a task per school that itself submitted a
task per chunk to the same pool, so every worker held a school task while waiting for
chunk tasks that needed a worker. It would have passed every small test and hung the
poller at exactly the scale it was written for. The plan is now built BEFORE anything is
submitted, and this suite asserts that structurally.
"""
import os
import sys
import tempfile
import time
import warnings

warnings.filterwarnings("ignore")


def run():
    os.environ["SEATWATCH_DB"] = os.path.join(tempfile.mkdtemp(), "scale.db")
    sys.path.insert(0, os.path.expanduser("~/seatwatch"))
    import app, guardian, schools as schools_mod
    app.init_db()

    results = []
    def check(n, c, d=""): results.append((n, bool(c), d))

    # ---------- the fetch plan ----------
    items = [{"course": "C%02d" % i} for i in range(10)]
    plan = app._plan_fetches({"sch": items})
    covered = [c for _sid, chunk in plan for c in chunk]
    check("every course appears in exactly one chunk",
          sorted(covered) == sorted({i["course"] for i in items}),
          f"plan covered {sorted(covered)}")
    check("the work is split, not left as one serial lump",
          1 < len(plan) <= app.SCHOOL_CONCURRENCY, f"{len(plan)} chunks")
    check("a school with ONE course makes exactly one chunk",
          len(app._plan_fetches({"sch": [{"course": "X"}]})) == 1)
    check("no empty chunks are submitted",
          all(chunk for _s, chunk in plan), "an empty fetch is a wasted request")

    big = app._plan_fetches({"a": [{"course": "C%03d" % i} for i in range(500)]})
    check("a HUGE school is still capped at SCHOOL_CONCURRENCY chunks",
          len(big) == app.SCHOOL_CONCURRENCY,
          f"{len(big)} chunks — this is a politeness budget; a registrar that decides we "
          f"are a nuisance is a school lost for every student")

    # Structural: the plan must be complete before submission, or the pool waits on itself.
    src = open(os.path.expanduser("~/seatwatch/app.py")).read()
    cyc = src[src.index("def run_cycle"):src.index("def run_cycle") + 2500]
    check("run_cycle submits a PRE-BUILT plan (no nested submission)",
          "_plan_fetches(by_school)" in cyc and "pool=ex" not in cyc,
          "a task that submits to its own pool deadlocks once every worker is busy")

    # ---------- chunking must not change the DATA ----------
    class Fake:
        id = "sch"; name = "Sch"; example = "C00"
        def valid_course(self, c): return True
        def reg_url(self, c): return "https://x.test"
        def cur_term(self): return "202608"
        def fetch(self, courses):
            return {c: {"0101": {"open": c == "C03", "seats": 3 if c == "C03" else 0}}
                    for c in courses}

    schools_mod.SCHOOLS = {"sch": Fake()}
    whole = Fake().fetch({i["course"] for i in items})
    merged = {}
    for job in app._plan_fetches({"sch": items}):
        _sid, part, _ms = app._chunk_fetch(job)
        merged.update(part or {})
    check("chunked fetch returns EXACTLY what one call returns", merged == whole,
          "if chunking altered seat data it would corrupt every alert decision")

    class HalfBroken(Fake):
        def fetch(self, courses):
            if "C00" in courses:
                raise RuntimeError("registrar hiccup")
            return Fake.fetch(self, courses)

    schools_mod.SCHOOLS = {"sch": HalfBroken()}
    merged2 = {}
    for job in app._plan_fetches({"sch": items}):
        _sid, part, _ms = app._chunk_fetch(job)
        merged2.update(part or {})
    check("one failing chunk does not erase the others", len(merged2) > 0,
          "a partial read must lose only its own courses")
    check("...and the failed chunk's courses are ABSENT, not reported empty",
          "C00" not in merged2,
          "reporting them as {} would read as 'the sections were deleted' and could "
          "cancel a student's watch on a course that is simply unreadable right now")

    # ---------- the write reduction, and what must survive it ----------
    check("quiet outcomes are named explicitly, not inferred",
          "checked_no_change" in guardian.QUIET_OUTCOMES
          and "checked_open_already" in guardian.QUIET_OUTCOMES)
    for loud in ("adapter_failed", "section_missing", "alert_delivered", "unaccounted",
                 "blocked_wrong_term", "write_failed", "school_missing"):
        check(f"'{loud}' is NEVER quiet", loud not in guardian.QUIET_OUTCOMES,
              "anything actionable must keep its own row")

    _state = {}
    guardian.TUNING["POLL_S"] = app.POLL_SECONDS
    guardian.configure(app.db, lambda k, d=None: _state.get(k, d),
                       lambda **kw: _state.update(kw),
                       lambda *a, **k: None, lambda *a, **k: None,
                       mode="enforce", deploy_sha="test")
    with app.db() as c:
        c.execute("INSERT OR IGNORE INTO users(id,google_sub,email,topic,created) "
                  "VALUES(1,'g_s','s@x','t_s',0)")
        c.executemany("INSERT INTO watches(school,topic,course,section,term,alerted,"
                      "created,user_id) VALUES('sch','t_s',?,?,'202608',0,0,1)",
                      [("C%02d" % i, "0101") for i in range(10)])
        rows = c.execute("SELECT * FROM watches").fetchall()

    cyc = guardian.begin_cycle(rows)
    for r in rows[:8]:
        guardian.record(cyc, r["id"], "checked_no_change")
    guardian.record(cyc, rows[8]["id"], "adapter_failed")
    guardian.record(cyc, rows[9]["id"], "section_missing")
    guardian.finalize(cyc)

    with app.db() as c:
        written = c.execute("SELECT outcome FROM guardian_watch_results").fetchall()
        cy = c.execute("SELECT expected,accounted,status,notes FROM guardian_cycles "
                       "ORDER BY rowid DESC LIMIT 1").fetchone()
    kinds = sorted(r["outcome"] for r in written)
    check("the 8 quiet outcomes wrote NO rows", len(written) == 2, f"wrote {kinds}")
    check("...but both LOUD ones did", kinds == ["adapter_failed", "section_missing"],
          f"wrote {kinds}")
    check("reconciliation still accounts for every watch",
          cy["expected"] == 10 and cy["accounted"] == 10,
          f"expected={cy['expected']} accounted={cy['accounted']}")
    check("the quiet outcomes SURVIVE as counts on the cycle row",
          '"checked_no_change": 8' in (cy["notes"] or ""),
          "dropping the rows must not drop the evidence that we looked")
    check("the cycle still reports the problem it found",
          cy["status"] == "YELLOW", f"status={cy['status']}")

    # A watch that gets no outcome at all must STILL be caught — that is the whole point
    # of the guardian, and it must not be a casualty of writing fewer rows.
    cyc2 = guardian.begin_cycle(rows)
    for r in rows[:9]:
        guardian.record(cyc2, r["id"], "checked_no_change")
    guardian.finalize(cyc2)
    with app.db() as c:
        cy2 = c.execute("SELECT expected,accounted,status,binding FROM guardian_cycles "
                        "ORDER BY rowid DESC LIMIT 1").fetchone()
        unacc = c.execute("SELECT COUNT(*) FROM guardian_watch_results "
                          "WHERE outcome='unaccounted'").fetchone()[0]
    check("a watch with NO outcome is still caught as unaccounted",
          cy2["status"] == "RED" and unacc == 1,
          f"status={cy2['status']} binding={cy2['binding']} rows={unacc}")

    # triage must not infer darkness from missing success rows any more
    tri = open(os.path.expanduser("~/seatwatch/ops/triage.py")).read()
    check("triage reads adapter_health, not the absence of success rows",
          "guardian_adapter_health" in tri
          and "SUM(outcome!='adapter_failed')" not in tri,
          "counting rows that are no longer written would report every school dark")
    # This dependency bit TWICE. The dark-school check was fixed with the same commit that
    # stopped writing quiet rows; the liveness check was missed, shipped, and told the
    # operator "nothing is being watched at all" while 40 watches polled normally on a
    # GREEN cycle. Both now read tables written unconditionally. Asserted together so the
    # next thing that stops writing a table has to come here and think.
    check("triage does not infer POLLER LIVENESS from per-watch rows either",
          "MAX(created) FROM guardian_watch_results" not in tri,
          "a healthy system writes no quiet rows, so that silence read as a dead poller")
    check("...it reads the cycle table, which is written every cycle regardless",
          "FROM guardian_cycles" in tri,
          "proof of life must not be confusable with proof of quiet")

    # ---------- the confidence engine: cheap when calm, fresh when not ----------
    # It reads history for EVERY watch and scores it, and it ran on every cycle to
    # maintain what its own docstring calls a once-a-day snapshot. At 300k watches that
    # was the dominant cost AND grew faster than linearly. It is now interval-gated — but
    # skipping work is only safe while nothing is wrong, so a cycle that is not GREEN must
    # still get current evidence. Otherwise the cheap path withholds exactly the diagnosis
    # the operator needs, which is this codebase's oldest mistake in a new costume.
    calls = []
    real_compute = guardian._compute_confidence
    guardian._compute_confidence = lambda c, cy, now: (calls.append(now), {"summary": "x"})[1]
    guardian._CONF_CACHE.update(at=0.0, result=None)
    try:
        t = 1_000_000.0
        guardian._confidence_cached(None, None, t, "GREEN")
        check("first call always computes (nothing cached yet)", len(calls) == 1)

        guardian._confidence_cached(None, None, t + 5, "GREEN")
        guardian._confidence_cached(None, None, t + 10, "GREEN")
        check("a calm cycle reuses the cached result", len(calls) == 1,
              f"computed {len(calls)}x — this is the whole saving")

        guardian._confidence_cached(None, None, t + guardian.CONF_EVERY_S + 1, "GREEN")
        check("...and refreshes once the interval elapses", len(calls) == 2,
              "a snapshot that never updates is not a snapshot")

        before = len(calls)
        guardian._confidence_cached(None, None, t + guardian.CONF_EVERY_S + 2, "YELLOW")
        check("a YELLOW cycle forces FRESH evidence, interval or not",
              len(calls) == before + 1,
              "stale evidence behind a real problem is worse than no shortcut at all")
        before = len(calls)
        guardian._confidence_cached(None, None, t + guardian.CONF_EVERY_S + 3, "RED")
        check("...and so does RED", len(calls) == before + 1)

        cached = guardian._confidence_cached(None, None, t + guardian.CONF_EVERY_S + 4, "GREEN")
        check("the report still receives a result between computations",
              cached is not None and cached.get("summary") == "x",
              "gating must not blank the status report")
    finally:
        guardian._compute_confidence = real_compute
        guardian._CONF_CACHE.update(at=0.0, result=None)

    # ---------- bulk evidence must equal what per-watch queries returned ----------
    import confidence as _conf
    with app.db() as c:
        c.execute("INSERT OR IGNORE INTO users(id,google_sub,email,topic,created) "
                  "VALUES(2,'g_e','has@mail','t_e',0)")
        c.execute("INSERT OR IGNORE INTO users(id,google_sub,email,topic,created) "
                  "VALUES(3,'g_n','','t_n',0)")
        c.execute("INSERT INTO alert_log(user_id,watch_id,school,course,section,channel,"
                  "sent_at,cost_cents) VALUES(2,1,'sch','C00','0101','email',?,0)",
                  (time.time(),))
        rows2 = c.execute("SELECT * FROM watches LIMIT 2").fetchall()

    class _Cyc:
        expected = {}
        would_block = []
    cy = _Cyc()
    cy.expected = {rows2[0]["id"]: {"user_id": 2, "school": "sch", "term": "202608"},
                   rows2[1]["id"]: {"user_id": 3, "school": "sch", "term": "202608"}}
    with app.db() as c:
        ev = _conf.gather_evidence(c, cy, time.time(), guardian.TUNING, started_at=0)
    w2 = ev["watches"][rows2[0]["id"]]
    w3 = ev["watches"][rows2[1]["id"]]
    check("bulk lookup: a user WITH an email is has_email", w2["has_email"] is True)
    check("bulk lookup: a user with an EMPTY email is not", w3["has_email"] is False,
          "an empty string must not read as a reachable address")
    check("bulk lookup: a user with a delivered alert has push_proof",
          w2["push_proof"] is True)
    check("bulk lookup: a user with none does NOT", w3["push_proof"] is False)
    check("bulk lookup: no push subscription reads False", w2["has_push"] is False)
    check("history is attached per watch", isinstance(w2["history"], list))

    p = sum(x for _, x, _ in results)
    f = sum(not x for _, x, _ in results)
    return p, f, results


if __name__ == "__main__":
    p, f, res = run()
    for n, ok, d in res:
        print(f"  [{'PASS' if ok else '*** FAIL'}] {n}{('  ' + d) if d and not ok else ''}")
    print(f"\n  {p} passed, {f} failed")
    sys.exit(1 if f else 0)
