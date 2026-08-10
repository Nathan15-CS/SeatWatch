#!/usr/bin/env python3
"""
Reliability Guardian test harness — the Phase B scenario matrix, executable.

Drives the REAL app.run_cycle / app._alert / guardian / confidence code with:
  * FakeSchool adapters scripted per cycle (ok/empty/crash/malformed/roll/...)
  * stubbed delivery channels (ntfy / web push recorded, success configurable)
  * an injected fake clock (no sleeps; decay and damper tests run instantly)
  * a fresh temp SQLite DB per test, real init_db schema

The load-bearing guarantee is the DIFFERENTIAL test: every externally visible
action (alerts sent, latches set, ping decisions) must be byte-identical
between GUARDIAN_MODE=off and =shadow across failure scenarios — shadow may
only ADD evidence, never change behavior. Enforce-mode gates are tested
separately and explicitly.

Run:  python3 -m unittest test_guardian -v      (stdlib only, no network)
"""
import json
import os
import shutil
import tempfile
import time
import unittest

os.environ.setdefault("SEATWATCH_DB", os.path.join(tempfile.gettempdir(),
                                                   "seatwatch-test-placeholder.db"))
import app                    # noqa: E402  (env must be set before import)
import confidence             # noqa: E402
import guardian               # noqa: E402
import schools as schools_mod  # noqa: E402


class FakeSchool:
    """Scriptable adapter. Each cycle pops the next step:
       {"data": {course: {sec: {"open": bool, "seats": int|None}}}}  normal
       {"crash": True}      fetch raises
       {"data": {}}         empty result (fail-closed contract)
    The last step repeats forever. cur_term is dynamic via .active."""

    def __init__(self, sid="fakeu", term="202608", steps=None, has_cur_term=True):
        self.id, self.name = sid, sid.upper()
        self.term = term
        self.example = "TEST101"
        self.active = None                 # set to simulate an auto-roll
        self.steps = list(steps or [])
        self.fetch_count = 0
        if not has_cur_term:
            self.cur_term = None           # not callable -> app falls back to .term

    def cur_term(self):
        return self.active or self.term

    def valid_course(self, course):
        return True

    def reg_url(self, course):
        return f"https://{self.id}.test/register"

    def fetch(self, courses):
        self.fetch_count += 1
        step = self.steps[0] if len(self.steps) == 1 else (
            self.steps.pop(0) if self.steps else {"data": {}})
        if step.get("crash"):
            raise RuntimeError("simulated adapter crash")
        return step.get("data", {})


def sec(open_, seats):
    return {"open": open_, "seats": seats}


class Base(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="swguard-")
        self.dbpath = os.path.join(self.tmp, "test.db")
        self._saved = {
            "DB": app.DB, "STATE": app.STATE_PATH, "SCHOOLS": schools_mod.SCHOOLS,
            "notify": app.sw.notify, "push": app.send_web_push,
            "email": app.send_email, "email_on": app.EMAIL_ENABLED,
            "env_db": os.environ.get("SEATWATCH_DB"),
        }
        app.DB = self.dbpath
        os.environ["SEATWATCH_DB"] = self.dbpath      # guardian report path
        app.STATE_PATH = os.path.join(self.tmp, "state.json")
        app.init_db()
        # in-memory app watchdogs: reset per test
        app.health.clear()
        app._ALLOPEN.clear()
        app._stale_logged.clear()
        app._undelivered.clear()
        app._RATE.clear()
        # Channel recorders. Students are alerted by EMAIL (and text); ntfy is the
        # operator's channel only, so counting student alerts there would count publishes
        # to a topic nobody is listening to. push is recorded purely to assert it stays
        # silent — it is retired.
        self.ntfy_ok = True
        self.email_ok = True
        self.push_devices = 0              # devices "reached" per send_web_push call
        self.notifies, self.pushes, self.emails = [], [], []

        def fake_notify(title, message, click_url=None, topic=None):
            self.notifies.append({"title": title, "topic": topic})
            return self.ntfy_ok

        def fake_push(user_id, title, body, url):
            self.pushes.append({"user_id": user_id, "title": title})
            return self.push_devices

        def fake_email(to, subject, body, url=None, **kw):
            self.emails.append({"to": to, "title": subject})
            return self.email_ok

        app.sw.notify = fake_notify
        app.send_web_push = fake_push
        app.send_email = fake_email
        app.EMAIL_ENABLED = True
        # guardian: fake clock + captured pages + dict state
        self.clock = [time.time()]
        self.state = {}
        self.pages = []
        guardian._TELEMETRY_FAULTS.clear()
        guardian._LAST_DIVERGENCE.clear()
        guardian._CUR["cycle"] = None
        guardian.TUNING["POLL_S"] = 20
        # Both tripwires pinned to their PRODUCTION defaults, so these tests exercise the
        # shipped configuration rather than a test-only one. Per-school is the primary
        # gate; the global cap sits above it to catch adapter-family events.
        guardian.TUNING["MAX_SCHOOL_TRANSITIONS"] = 10
        guardian.TUNING["MAX_ALERTS_PER_CYCLE"] = 25
        self.configure("shadow")

    def tearDown(self):
        app.DB = self._saved["DB"]
        app.STATE_PATH = self._saved["STATE"]
        schools_mod.SCHOOLS = self._saved["SCHOOLS"]
        app.sw.notify = self._saved["notify"]
        app.send_web_push = self._saved["push"]
        app.send_email = self._saved["email"]
        app.EMAIL_ENABLED = self._saved["email_on"]
        if self._saved["env_db"] is not None:
            os.environ["SEATWATCH_DB"] = self._saved["env_db"]
        guardian._CFG["mode"] = "off"
        shutil.rmtree(self.tmp, ignore_errors=True)

    # ---------- helpers
    def configure(self, mode):
        guardian.configure(
            app.db,
            lambda k, d=None: self.state.get(k, d),
            lambda **kv: self.state.update(kv),
            lambda *a: None,
            lambda msg: self.pages.append(msg),
            now_fn=lambda: self.clock[0],
            mode=mode,
            deploy_sha="")

    def install(self, *fakes):
        schools_mod.SCHOOLS = {f.id: f for f in fakes}

    def add_user(self, uid=1, email="s@x.edu", push_sub=False):
        with app.db() as c:
            c.execute("INSERT OR IGNORE INTO users(id,google_sub,email,topic,created) "
                      "VALUES(?,?,?,?,?)", (uid, f"sub{uid}", email, f"topic{uid}", time.time()))
            if push_sub:
                c.execute("INSERT OR IGNORE INTO push_subs(user_id,endpoint,p256dh,auth,created)"
                          " VALUES(?,?,?,?,?)", (uid, f"https://push.test/{uid}", "k", "a",
                                                 time.time()))
        return uid

    def add_watch(self, wid, school="fakeu", course="TEST101", section="0101",
                  term="202608", uid=1):
        with app.db() as c:
            c.execute("INSERT INTO watches(id,school,topic,course,section,term,alerted,"
                      "created,user_id) VALUES(?,?,?,?,?,?,0,?,?)",
                      (wid, school, f"topic{uid}", course, section, term, time.time(), uid))
        return wid

    def alerted(self, wid):
        with app.db() as c:
            return c.execute("SELECT alerted FROM watches WHERE id=?", (wid,)).fetchone()[0]

    def cycle(self, advance=20):
        cyc = app.run_cycle()
        ping = guardian.ping_ok(cyc)
        self.clock[0] += advance
        return cyc, ping

    def last_cycle_row(self):
        with app.db() as c:
            return c.execute("SELECT * FROM guardian_cycles WHERE finished IS NOT NULL "
                             "ORDER BY finished DESC LIMIT 1").fetchone()

    def outcomes(self, cycle_id):
        with app.db() as c:
            return {r["watch_id"]: r["outcome"] for r in c.execute(
                "SELECT watch_id, outcome FROM guardian_watch_results WHERE cycle_id=?",
                (cycle_id,))}

    def user_alerts(self):
        """What a STUDENT actually received. Email, not ntfy: an ntfy publish returns 200
        with nobody subscribed, so counting it here would call an unreachable student
        alerted — the exact confusion that retired push in the first place."""
        return self.emails

    def operator_msgs(self):
        return [n for n in self.notifies if n["topic"] == app.OPERATOR_TOPIC]


# ===================================================================== core
class TestReconciliation(Base):
    def test_happy_cycle_green_and_recorded(self):
        self.add_user(1, push_sub=True)
        self.add_watch(1, section="0101")
        self.add_watch(2, section="0202")
        self.install(FakeSchool(steps=[{"data": {"TEST101": {
            "0101": sec(False, 0), "0202": sec(False, 0)}}}]))
        cyc, ping = self.cycle()
        row = self.last_cycle_row()
        self.assertEqual(row["status"], "GREEN")
        self.assertEqual(row["expected"], 2)
        self.assertEqual(row["accounted"], 2)
        self.assertTrue(ping)
        self.assertEqual(self.outcomes(cyc.id),
                         {1: "checked_no_change", 2: "checked_no_change"})

    def test_silently_skipped_watch_is_red(self):
        # Harness-forced skip: the reconciler must catch a watch nobody processed.
        self.add_user(1)
        self.add_watch(1)
        self.add_watch(2)
        with app.db() as c:
            rows = c.execute("SELECT * FROM watches").fetchall()
        cyc = guardian.begin_cycle(rows)
        guardian.record(cyc, 2, "checked_no_change")   # watch 1 never gets an outcome
        status = guardian.finalize(cyc)
        self.assertEqual(status, "RED")
        self.assertEqual(self.outcomes(cyc.id)[1], "unaccounted")
        with app.db() as c:
            inc = c.execute("SELECT * FROM guardian_incidents WHERE "
                            "kind='unaccounted_watch'").fetchone()
        self.assertIsNotNone(inc)

    def test_matching_totals_different_identities_is_red(self):
        self.add_user(1)
        self.add_watch(1)
        self.add_watch(2)
        with app.db() as c:
            rows = c.execute("SELECT * FROM watches").fetchall()
        cyc = guardian.begin_cycle(rows)
        guardian.record(cyc, 2, "checked_no_change")
        guardian.record(cyc, 2, "checked_no_change")   # watch 2 "processed twice"
        status = guardian.finalize(cyc)                # count=1+dup, identity 1 missing
        self.assertEqual(status, "RED")

    def test_crash_before_finalize_detected_next_cycle(self):
        self.add_user(1)
        self.add_watch(1)
        self.install(FakeSchool(steps=[{"data": {"TEST101": {"0101": sec(False, 0)}}}]))
        with app.db() as c:
            rows = c.execute("SELECT * FROM watches").fetchall()
        dying = guardian.begin_cycle(rows)
        with app.db() as c:                            # emulate: cycle row opened, then the
            c.execute("INSERT OR REPLACE INTO guardian_cycles(cycle_id,started) VALUES(?,?)",
                      (dying.id, dying.t0))            # process dies before finalize
        self.cycle()
        with app.db() as c:
            orphan = c.execute("SELECT status FROM guardian_cycles WHERE cycle_id=?",
                               (dying.id,)).fetchone()
        self.assertEqual(orphan["status"], "aborted")
        self.assertTrue(any("died before completing" in p for p in self.pages))


# ============================================================ failure modes
class TestFailureModes(Base):
    def test_adapter_crash_and_empty_recorded_yellow(self):
        self.add_user(1)
        self.add_watch(1)
        self.install(FakeSchool(steps=[{"crash": True}, {"data": {}}]))
        cyc, ping = self.cycle()
        self.assertEqual(self.outcomes(cyc.id)[1], "adapter_failed")
        self.assertEqual(self.last_cycle_row()["status"], "YELLOW")
        self.assertTrue(ping)                          # shadow: ping unchanged
        cyc2, _ = self.cycle()
        self.assertEqual(self.outcomes(cyc2.id)[1], "adapter_failed")
        with app.db() as c:
            h = c.execute("SELECT * FROM guardian_adapter_health WHERE school='fakeu'").fetchone()
        self.assertEqual(h["consec_fail"], 2)

    def test_health_guard_pages_once_at_threshold(self):
        self.add_user(1)
        self.add_watch(1)
        self.install(FakeSchool(steps=[{"data": {}}]))
        for _ in range(7):
            self.cycle()
        self.assertEqual(len(self.operator_msgs()), 1)  # threshold page once, not 7x

    def test_section_vanishes_is_recorded_not_silent(self):
        self.add_user(1)
        self.add_watch(1, section="0101")
        self.install(FakeSchool(steps=[{"data": {"TEST101": {"9999": sec(True, 5)}}}]))
        cyc, _ = self.cycle()
        self.assertEqual(self.outcomes(cyc.id)[1], "section_missing")
        self.assertEqual(self.last_cycle_row()["status"], "YELLOW")
        self.assertEqual(self.user_alerts(), [])       # and of course: no alert

    def test_school_removed_from_registry_is_recorded(self):
        self.add_user(1)
        self.add_watch(1, school="ghostu")
        self.install(FakeSchool())                     # registry has fakeu, not ghostu
        cyc, _ = self.cycle()
        self.assertEqual(self.outcomes(cyc.id)[1], "school_missing")
        with app.db() as c:
            self.assertIsNotNone(c.execute("SELECT 1 FROM guardian_incidents WHERE "
                                           "kind='orphan_watch'").fetchone())

    def test_malformed_data_counts_sanity_violation(self):
        self.add_user(1)
        self.add_watch(1, section="0101")
        self.install(FakeSchool(steps=[{"data": {"TEST101": {
            "0101": sec(True, 0)}}}]))                 # open=True with 0 seats: contract breach
        self.cycle()
        with app.db() as c:
            h = c.execute("SELECT sanity_violations FROM guardian_adapter_health "
                          "WHERE school='fakeu'").fetchone()
        self.assertEqual(h["sanity_violations"], 1)
        # Assert the MEANING, not the phrasing: this is the shape that would advertise a
        # seat that is not there, so the page has to say so.
        self.assertTrue(any("not there" in p or "FALSE ALERT" in p for p in self.pages),
                        f"pages were {self.pages}")

    def test_waitlisted_section_is_not_treated_as_parse_drift(self):
        """open=False with seats>0 is a WAITLIST, and reading it as closed is correct.

        Butte paged on 50 of 50 fetches for exactly two such rows out of ~52 sections.
        Nothing was wrong: a waitlisted seat cannot simply be taken, so staying quiet is
        the right answer. Treating it as "parse drift, do not trust this school" is how an
        operator is trained to ignore the pager — and the pager still has to work on the
        day a parser really does break."""
        self.add_user(1)
        self.add_watch(1, section="0101")
        self.install(FakeSchool(steps=[{"data": {"TEST101": {
            "0101": sec(False, 2),                     # full, but holding a waitlisted seat
            "0202": sec(False, 0), "0303": sec(True, 5)}}}]))
        self.cycle()
        with app.db() as c:
            h = c.execute("SELECT sanity_violations FROM guardian_adapter_health "
                          "WHERE school='fakeu'").fetchone()
        self.assertEqual(h["sanity_violations"], 0,
                         "a waitlisted section was counted as a data-contract breach")
        self.assertFalse(any("not there" in p for p in self.pages),
                         f"paged about a false-alert risk that does not exist: {self.pages}")

    def test_widespread_full_with_seats_DOES_page(self):
        """The other half: if the open flag stopped being read at all, every section would
        look full-while-holding-seats and the school would go SILENT. A handful is
        waitlists; most of the catalogue is a broken parser, and that must still page."""
        self.add_user(1)
        self.add_watch(1, section="0101")
        data = {f"S{i:03d}": sec(False, 3) for i in range(12)}
        data["0101"] = sec(False, 3)
        self.install(FakeSchool(steps=[{"data": {"TEST101": data}}]))
        self.cycle()
        self.assertTrue(any("FULL while showing seats" in p for p in self.pages),
                        f"a school that went silent would never be noticed: {self.pages}")

    def test_term_roll_blocks_loudly_not_silently(self):
        self.add_user(1)
        self.add_watch(1, term="202608")
        f = FakeSchool(steps=[{"data": {"TEST101": {"0101": sec(True, 3)}}}])
        f.active = "202701"                            # school rolled; watch stamped fall
        self.install(f)
        cyc, _ = self.cycle()
        self.assertEqual(self.outcomes(cyc.id)[1], "blocked_wrong_term")
        # This used to assert the student received NOTHING, which was right when a rolled
        # term simply stopped the watch. It is wrong now: app.py:4345 tells the student the
        # watch ended and why. That notice IS the "loudly, not silently" this test is named
        # for — a watch that dies without telling anyone is the silent-death failure. So
        # pin both halves separately instead of banning all mail.
        mail = self.user_alerts()
        self.assertFalse([m for m in mail if "Seat open" in m["title"]],
                         f"a false SEAT alert went out for a rolled term: {mail}")
        self.assertTrue([m for m in mail if "watch has ended" in m["title"]],
                        f"student was never told their watch died — silent death: {mail}")
        self.assertTrue(any("STRANDED" in p for p in self.pages))   # ...and it was loud
        with app.db() as c:
            self.assertIsNotNone(c.execute("SELECT 1 FROM guardian_incidents WHERE "
                                           "kind='term_stale_watch'").fetchone())

    def test_stamp_term_uses_rolled_term_not_pin(self):
        f = FakeSchool(term="202608")
        f.active = "202701"
        self.assertEqual(app.stamp_term(f), "202701")  # new watches match cur_term()
        f2 = FakeSchool(term="202608", has_cur_term=False)
        self.assertEqual(app.stamp_term(f2), "202608")  # pin fallback unchanged

    def test_db_write_failure_surfaces_as_red(self):
        self.add_user(1, push_sub=True)
        self.push_devices = 1
        self.add_watch(1, section="0101")
        self.install(FakeSchool(steps=[{"data": {"TEST101": {"0101": sec(True, 2)}}}]))
        real = app._set_alerted
        app._set_alerted = lambda wid, v: (_ for _ in ()).throw(RuntimeError("disk full"))
        try:
            with self.assertRaises(RuntimeError):      # legacy abort semantics preserved
                app.run_cycle()
            guardian.poller_recover(RuntimeError("disk full"))
        finally:
            app._set_alerted = real
        row = self.last_cycle_row()
        self.assertEqual(row["status"], "RED")
        with app.db() as c:
            oc = c.execute("SELECT outcome FROM guardian_watch_results WHERE watch_id=1 "
                           "ORDER BY created DESC LIMIT 1").fetchone()
        self.assertEqual(oc["outcome"], "write_failed")


# ======================================================= alert path + latch
class TestAlertPath(Base):
    def _open_school(self, seats=2):
        return FakeSchool(steps=[{"data": {"TEST101": {"0101": sec(True, seats)}}}])

    def test_open_seat_alerts_once_and_latches(self):
        self.add_user(1, push_sub=True)
        self.push_devices = 1
        self.add_watch(1, section="0101")
        self.install(self._open_school())
        cyc, _ = self.cycle()
        self.assertEqual(len(self.user_alerts()), 1)
        self.assertEqual(self.alerted(1), 1)
        self.assertEqual(self.outcomes(cyc.id)[1], "alert_delivered")
        cyc2, _ = self.cycle()                         # still open: no duplicate
        self.assertEqual(len(self.user_alerts()), 1)
        self.assertEqual(self.outcomes(cyc2.id)[1], "checked_open_already")

    def test_flicker_realerts_once_per_episode(self):
        self.add_user(1, push_sub=True)
        self.push_devices = 1
        self.add_watch(1, section="0101")
        self.install(FakeSchool(steps=[
            {"data": {"TEST101": {"0101": sec(True, 1)}}},
            {"data": {"TEST101": {"0101": sec(False, 0)}}},
            {"data": {"TEST101": {"0101": sec(True, 1)}}}]))
        self.cycle(); self.cycle(); self.cycle()
        self.assertEqual(len(self.user_alerts()), 2)   # open, reset, re-open

    def test_total_delivery_failure_no_latch_and_pages(self):
        self.add_user(1, push_sub=False)
        self.ntfy_ok = False
        self.email_ok = False              # the student's only live channel is down
        self.push_devices = 0
        self.add_watch(1, section="0101")
        self.install(self._open_school())
        cyc, _ = self.cycle()
        self.assertEqual(self.alerted(1), 0)           # not latched -> retries next cycle
        self.assertEqual(self.outcomes(cyc.id)[1], "alert_undelivered")
        self.assertEqual(len(self.operator_msgs()), 1)  # UNDELIVERED page, exactly once

    def test_ntfy_success_never_latches_a_watch(self):
        """The bug this whole change exists to prevent, pinned in both modes.

        ntfy answers 200 for a publish to a topic with no subscriber. It used to be
        allowed to satisfy delivery, which meant a seat could be marked handled for a
        student who was never reached — no error, no page, just a missed class. Email is
        down here and ntfy is "fine": the watch must stay un-latched so it retries.
        """
        self.add_user(1, push_sub=False)
        self.email_ok = False
        self.ntfy_ok = True                            # the deceptive success
        self.push_devices = 0
        self.add_watch(1, section="0101")
        self.install(self._open_school())
        for mode in ("shadow", "enforce"):
            with app.db() as c:
                c.execute("UPDATE watches SET alerted=0 WHERE id=1")
            self.configure(mode)
            cyc, _ = self.cycle()
            self.assertEqual(self.alerted(1), 0, f"ntfy latched the watch in {mode}")
            self.assertEqual(self.outcomes(cyc.id)[1], "alert_undelivered")

    def test_push_is_never_used_for_a_student(self):
        """Push is retired. An account with a live subscription must still be alerted by
        email, and send_web_push must not be called at all — a retired channel that still
        fires is one nobody can reason about, and it was reporting false success."""
        self.add_user(1, push_sub=True)
        self.push_devices = 5                          # would "succeed" if ever called
        self.add_watch(1, section="0101")
        self.install(self._open_school())
        self.configure("enforce")
        self.cycle()
        self.assertEqual(len(self.pushes), 0, "push fired for a student")
        self.assertEqual(len(self.user_alerts()), 1)   # reached by email instead
        self.assertEqual(self.alerted(1), 1)


# ===================================================== mass freeze + gates
class TestGates(Base):
    def _mass(self, n=15):
        self.add_user(1, push_sub=True)
        self.push_devices = 1
        data = {}
        for i in range(n):
            self.add_watch(i + 1, course=f"C{i:03d}", section="0101", term="202608")
            data[f"C{i:03d}"] = {"0101": sec(True, 4)}
        self.install(FakeSchool(steps=[{"data": data}]))

    def test_mass_opening_enforce_sends_none_and_freezes(self):
        self._mass(15)
        self.configure("enforce")
        cyc, ping = self.cycle()
        self.assertEqual(self.user_alerts(), [])       # ZERO sends on a mass transition
        self.assertIn("guardian_freeze", self.state)
        self.assertEqual(self.last_cycle_row()["status"], "RED")
        self.assertFalse(ping)                         # enforce: RED withholds the ping
        self.assertEqual(set(self.outcomes(cyc.id).values()), {"blocked_mass_freeze"})

    def _surge_then(self, tail):
        """15 watches. Cycle 1 is a mass opening; later cycles are whatever `tail` says."""
        self.add_user(1, push_sub=True)
        self.push_devices = 1
        surge, calm, few = {}, {}, {}
        for i in range(15):
            self.add_watch(i + 1, course=f"C{i:03d}", section="0101", term="202608")
            surge[f"C{i:03d}"] = {"0101": sec(True, 4)}
            calm[f"C{i:03d}"] = {"0101": sec(False, 0)}
            few[f"C{i:03d}"] = {"0101": sec(i < 2, 4 if i < 2 else 0)}
        book = {"surge": surge, "calm": calm, "few": few}
        self.install(FakeSchool(steps=[{"data": surge}] + [{"data": book[t]} for t in tail]))

    def test_popularity_is_not_a_cascade(self):
        """THE BUG THIS GATE WAS BORN WITH: 40 students on ONE section is not an incident.

        The tripwire used to count queued alerts, i.e. WATCHERS. One real seat opening in a
        popular course produces one queued alert per student watching it, so the threshold
        was a function of how many people use the product. Under enforcement, the single
        most valuable event SeatWatch can observe — a seat opening in its most-watched
        course — would have frozen every alert on the platform. Success, read as failure."""
        for uid in range(1, 41):                       # 40 students, same section
            self.add_user(uid, email=f"s{uid}@x.edu", push_sub=True)
            self.add_watch(uid, course="TEST101", section="0101", term="202608", uid=uid)
        self.push_devices = 1
        self.install(FakeSchool(steps=[{"data": {"TEST101": {"0101": sec(True, 3)}}}]))
        self.configure("enforce")
        self.cycle()

        self.assertIsNone(self.state.get("guardian_freeze"),
                          "one seat opening froze the platform because it was POPULAR")
        self.assertEqual(len(self.user_alerts()), 40,
                         "all 40 students must be told; the seat is real")

    def test_one_watcher_many_sections_still_freezes(self):
        """The other direction, and the caveat the watcher metric could never express.

        An any-section watch fires ONCE for the whole course no matter how many sections
        flipped, so counting watches — or naively keying on the watch's own empty section —
        collapses a whole-course cascade to a single unit and sails under the cap. The
        section list that actually changed has to be carried into the tripwire."""
        self.add_user(1, push_sub=True)
        self.push_devices = 1
        self.add_watch(1, course="TEST101", section="", term="202608", uid=1)
        blown = {f"{i:04d}": sec(True, 5) for i in range(30)}    # parser breaks: all open
        self.install(FakeSchool(steps=[{"data": {"TEST101": blown}}]))
        self.configure("enforce")
        self.cycle()

        self.assertIsNotNone(self.state.get("guardian_freeze"),
                             "30 sections flipped open at once and the gate did not notice")
        self.assertEqual(self.user_alerts(), [])

    def test_a_frozen_school_cannot_silence_a_healthy_one(self):
        """THE POINT OF PER-SCHOOL SCOPING, and the easiest thing to get subtly wrong.

        A parse break is a property of ONE school's page format. Under a single global
        freeze, UMD breaking stopped alerting the USF and OU students whose data was
        perfectly fine — collateral damage with no diagnostic value whatsoever. The
        student at the healthy school loses their seat because of a bug at a school they
        have never heard of."""
        self.add_user(1, push_sub=True)
        self.push_devices = 1
        broken, fine, wid = {}, {}, 0
        for i in range(15):                       # fakeu: parser breaks, 15 sections flip
            wid += 1
            self.add_watch(wid, school="fakeu", course=f"C{i:03d}", section="0101",
                           term="202608")
            broken[f"C{i:03d}"] = {"0101": sec(True, 4)}
        wid += 1
        healthy_wid = wid                          # otheru: ONE genuine seat opening
        self.add_watch(healthy_wid, school="otheru", course="OK101", section="0101",
                       term="202608")
        fine["OK101"] = {"0101": sec(True, 2)}
        self.install(FakeSchool(sid="fakeu", steps=[{"data": broken}]),
                     FakeSchool(sid="otheru", steps=[{"data": fine}]))
        self.configure("enforce")
        self.cycle()

        self.assertEqual(self.alerted(healthy_wid), 1,
                         "a healthy school's student was silenced by ANOTHER school's "
                         "parse break")
        self.assertEqual(len(self.user_alerts()), 1,
                         "exactly one alert should survive: the real seat at otheru")
        for i in range(1, 16):
            self.assertEqual(self.alerted(i), 0, "the lying school still alerted")
        latched = self.state.get("guardian_freeze") or {}
        self.assertIn("fakeu", latched)
        self.assertNotIn("otheru", latched, "froze a school that never tripped")

    def test_adapter_family_break_trips_the_global_backstop(self):
        """The hole per-school scoping CANNOT see, by construction.

        Hundreds of schools share one adapter family. A vendor-side Banner or Colleague
        change breaks many at once, and each school can sit comfortably under its own
        per-school threshold while the aggregate is catastrophic. This is why the global
        cap survives above the per-school one and must not be deleted as redundant."""
        self.add_user(1, push_sub=True)
        self.push_devices = 1
        fakes, wid = [], 0
        for s in range(6):                        # 6 schools x 5 sections = 30 > global 25
            sid = f"fam{s}"
            data = {}
            for i in range(5):                    # 5 each: UNDER the per-school cap of 10
                wid += 1
                self.add_watch(wid, school=sid, course=f"C{i}", section="0101",
                               term="202608")
                data[f"C{i}"] = {"0101": sec(True, 3)}
            fakes.append(FakeSchool(sid=sid, steps=[{"data": data}]))
        self.install(*fakes)
        self.configure("enforce")
        self.cycle()

        self.assertEqual(self.user_alerts(), [],
                         "an adapter-family break slipped through: every school was "
                         "under its own cap, so only the global backstop could catch it")
        self.assertIsNotNone(self.state.get("guardian_freeze_global"))
        self.assertFalse(self.state.get("guardian_freeze") or {},
                         "no single school exceeded its own threshold")

    def test_mass_freeze_self_clears_once_the_load_is_normal_again(self):
        """A registrar releasing held seats in one block is not a parse break.

        The freeze is right to trip, but if clearing it needs a human at a terminal then a
        legitimate surge costs every student every alert until someone notices — on the one
        morning of the year they are watching the page. Sustained normal load releases it."""
        self._surge_then(["calm", "calm", "calm", "few"])
        self.configure("enforce")

        self.cycle()
        self.assertIsNotNone(self.state.get("guardian_freeze"))
        self.assertEqual(self.user_alerts(), [])       # the surge itself is still withheld

        for _ in range(3):
            self.cycle()
        self.assertIsNone(self.state.get("guardian_freeze"),
                          "freeze stayed latched after the load returned to normal")

        self.cycle()                                   # two real openings
        self.assertTrue(self.user_alerts(),
                        "alerts were still suppressed after the freeze cleared")

    def test_mass_freeze_holds_while_the_data_is_still_lying(self):
        """The other half: a parse break keeps producing a cascade, so it must NOT clear."""
        self._surge_then(["surge", "surge", "surge", "surge"])
        self.configure("enforce")
        for _ in range(5):
            self.cycle()
        self.assertIsNotNone(self.state.get("guardian_freeze"),
                             "a sustained cascade released itself — the gate is useless")
        self.assertEqual(self.user_alerts(), [])

    def test_mass_opening_shadow_sends_but_records(self):
        self._mass(15)
        cyc, ping = self.cycle()
        self.assertEqual(len(self.user_alerts()), 15)  # shadow: behavior unchanged
        self.assertTrue(ping)
        self.assertTrue(any("WOULD have" in p for p in self.pages))
        row = self.last_cycle_row()
        # 15 sections at ONE school: under the global cap, over that school's. Shadow now
        # records which school would have been frozen rather than a blanket platform
        # freeze — a strictly more precise divergence record, same "changes nothing" rule.
        self.assertIn("school_freeze", row["notes"])
        self.assertIn("fakeu", row["notes"])

    def test_stale_data_gate_blocks_in_enforce(self):
        self.configure("enforce")
        # direct gate check: fetched 10 minutes "ago" per the guardian clock
        self.add_user(1)
        self.add_watch(1, section="0101")
        with app.db() as c:
            r = c.execute("SELECT * FROM watches WHERE id=1").fetchone()
        cyc = guardian.begin_cycle([r])
        allow, reason = guardian.gate(cyc, r, "202608", self.clock[0] - 600)
        self.assertFalse(allow)
        self.assertIn("fresh_data", reason)

    def test_gate_error_fails_closed_in_enforce_open_in_shadow(self):
        self.add_user(1)
        self.add_watch(1, section="0101")
        with app.db() as c:
            r = c.execute("SELECT * FROM watches WHERE id=1").fetchone()
        cyc = guardian.begin_cycle([r])
        broken_db, guardian._CFG["db"] = guardian._CFG["db"], None   # force a crash
        try:
            allow, reason = guardian.gate(cyc, r, "202608", self.clock[0])
            self.assertTrue(allow)                     # shadow: fail OPEN (legacy rules)
            self.configure("enforce")
            guardian._CFG["db"] = None
            allow, reason = guardian.gate(cyc, r, "202608", self.clock[0])
            self.assertFalse(allow)                    # enforce: fail CLOSED
            self.assertEqual(reason, "guardian_error")
        finally:
            guardian._CFG["db"] = broken_db

    def test_page_damper_once_per_class_per_window(self):
        for _ in range(10):
            guardian.page("test_class", "same failure")
        self.assertEqual(len(self.pages), 1)
        self.clock[0] += 7 * 3600
        guardian.page("test_class", "same failure later")
        self.assertEqual(len(self.pages), 2)


# ========================================================== differential
class TestDifferential(Base):
    """shadow must be externally IDENTICAL to off across the scenario mix."""

    SCRIPT = [
        {"data": {"TEST101": {"0101": sec(False, 0), "0202": sec(False, 0)}}},
        {"data": {"TEST101": {"0101": sec(True, 3), "0202": sec(False, 0)}}},
        {"data": {}},                                   # adapter empty
        {"crash": True},                                # adapter crash
        {"data": {"TEST101": {"9999": sec(True, 1)}}},  # watched section vanishes
        {"data": {"TEST101": {"0101": sec(False, 0), "0202": sec(False, 0)}}},
        {"data": {"TEST101": {"0101": sec(True, 2), "0202": sec(True, 1)}}},
    ]

    def _run(self, mode):
        # rebuild the world from scratch under the given mode
        self.tearDown()
        self.setUp()
        self.configure(mode)
        self.add_user(1, push_sub=True)
        self.push_devices = 1
        self.add_watch(1, section="0101")
        self.add_watch(2, section="0202")
        self.install(FakeSchool(steps=[dict(s) for s in self.SCRIPT]))
        pings = []
        for _ in range(len(self.SCRIPT)):
            _, ping = self.cycle()
            pings.append(ping)
        return {"alerts": self.user_alerts(), "pushes": self.pushes,
                "latch": (self.alerted(1), self.alerted(2)), "pings": pings}

    def test_shadow_is_behavior_identical_to_off(self):
        off = self._run("off")
        shadow = self._run("shadow")
        self.assertEqual(off, shadow)
        with app.db() as c:                            # ...but shadow left evidence
            n = c.execute("SELECT COUNT(*) FROM guardian_cycles").fetchone()[0]
        self.assertEqual(n, len(self.SCRIPT))

    def test_off_mode_writes_no_guardian_rows(self):
        self._run("off")
        with app.db() as c:
            n = c.execute("SELECT COUNT(*) FROM guardian_cycles").fetchone()[0]
            m = c.execute("SELECT COUNT(*) FROM guardian_watch_results").fetchone()[0]
        self.assertEqual((n, m), (0, 0))


# ========================================================== confidence
class TestConfidence(Base):
    def _snap(self, etype, eid):
        with app.db() as c:
            return c.execute("SELECT * FROM guardian_confidence WHERE entity_type=? "
                             "AND entity_id=? ORDER BY date DESC LIMIT 1",
                             (etype, str(eid))).fetchone()

    def test_unknown_is_never_high(self):
        self.add_user(1)                               # no push sub, no evidence yet
        self.add_watch(1, section="0101")
        self.install(FakeSchool(steps=[{"data": {"TEST101": {"0101": sec(False, 0)}}}]))
        self.cycle()
        snap = self._snap("system", "system")
        self.assertLess(snap["score"], 70)             # brand-new system cannot be GOOD
        self.assertTrue(snap["binding"])               # and it must say WHY

    def test_confidence_is_earned_by_clean_cycles(self):
        self.add_user(1, push_sub=True)
        self.add_watch(1, section="0101")
        self.install(FakeSchool(steps=[{"data": {"TEST101": {"0101": sec(False, 0)}}}]))
        self.cycle()
        first = self._snap("watch", 1)["score"]
        for _ in range(30):
            self.cycle()
        later = self._snap("watch", 1)["score"]
        self.assertGreaterEqual(later, first)          # evidence accumulates, never assumed

    def test_empty_term_stamp_caps_watch_confidence(self):
        self.add_user(1, push_sub=True)
        self.add_watch(1, section="0101", term="")     # the 249-school exposure class
        self.install(FakeSchool(steps=[{"data": {"TEST101": {"0101": sec(False, 0)}}}]))
        for _ in range(3):
            self.cycle()
        snap = self._snap("watch", 1)
        self.assertLessEqual(snap["score"], confidence.CAP_TERM_EMPTY)
        self.assertEqual(snap["binding"], "W3_term")

    def test_stale_evidence_decays_without_any_failure(self):
        self.add_user(1, push_sub=True)
        self.add_watch(1, section="0101")
        self.install(FakeSchool(steps=[{"data": {"TEST101": {"0101": sec(False, 0)}}}]))
        for _ in range(10):
            self.cycle()
        fresh = self._snap("watch", 1)["score"]
        self.clock[0] += 2 * 3600                      # two silent hours, zero failures
        self.cycle()
        aged_row = self._snap("watch", 1)
        factors = json.loads(aged_row["factors"])
        self.assertLessEqual(factors["W2_cadence"], 40)  # the gap itself is evidence

    def test_no_push_caps_delivery_factor(self):
        self.add_user(1, push_sub=False)
        self.add_watch(1, section="0101")
        self.install(FakeSchool(steps=[{"data": {"TEST101": {"0101": sec(False, 0)}}}]))
        self.cycle()
        factors = json.loads(self._snap("watch", 1)["factors"])
        self.assertLessEqual(factors["W6_delivery"], confidence.CAP_ENROLLED_UNPROVEN)

    def test_adapter_failure_binds_watch_confidence(self):
        self.add_user(1, push_sub=True)
        self.add_watch(1, section="0101")
        self.install(FakeSchool(steps=[{"data": {}}]))
        for _ in range(6):
            self.cycle()
        snap = self._snap("adapter", "fakeu")
        self.assertLessEqual(snap["score"], 30)
        wf = json.loads(self._snap("watch", 1)["factors"])
        self.assertLessEqual(wf["W4_adapter"], 30)

    def test_compose_weakest_link_and_tiers(self):
        s, t, b = confidence.compose({"a": 90, "b": 42, "c": 77})
        self.assertEqual((s, t, b), (42, "LOW", "b"))
        s, t, b = confidence.compose({"a": None, "b": 90})
        self.assertEqual((s, b), (0, "a"))             # unknown is never high
        self.assertEqual(confidence.tier(85), "HIGH")
        self.assertEqual(confidence.tier(84), "GOOD")


# ========================================================== backlog + report
class TestBrainOutputs(Base):
    def test_backlog_is_evidence_driven_and_prioritized(self):
        self.add_user(1, push_sub=False)               # -> no-push item
        self.add_watch(1, section="0101", term="")     # -> empty-term item
        self.install(FakeSchool(steps=[{"data": {}}]))
        for _ in range(6):                             # -> recurring adapter incidents
            self.cycle()
        items = guardian.build_backlog()
        self.assertTrue(items)
        ids = {i["id"] for i in items}
        self.assertTrue(all(i["evidence"] for i in items))
        titles = " | ".join(i["title"] for i in items)
        self.assertIn("empty term stamp", titles)
        self.assertIn("push", titles)
        sevs = [guardian._SEV_RANK[i["severity"]] for i in items]
        self.assertEqual(sevs, sorted(sevs))           # red-first ordering
        again = {i["id"] for i in guardian.build_backlog()}
        self.assertEqual(ids, again)                   # stable IDs week over week

    def test_summary_line_and_report_written(self):
        self.add_user(1, push_sub=True)
        self.add_watch(1, section="0101")
        self.install(FakeSchool(steps=[{"data": {"TEST101": {"0101": sec(False, 0)}}}]))
        self.cycle()
        line = guardian.summary_line()
        self.assertIn("1/1 reconciled", line)
        self.assertIn("RCI", line)
        with open(self.dbpath + ".guardian.json") as f:
            rep = json.load(f)
        self.assertEqual(rep["expected"], 1)
        self.assertIn("not a probability", rep["note"])

    def test_retention_prunes_old_evidence_keeps_recent_and_unfinalized(self):
        self.add_user(1)
        self.add_watch(1, section="0101")
        self.install(FakeSchool(steps=[{"data": {"TEST101": {"0101": sec(False, 0)}}}]))
        old = self.clock[0] - 8 * 86400            # older than the 7-day retention
        with app.db() as c:
            c.execute("INSERT INTO guardian_watch_results(cycle_id,watch_id,outcome,"
                      "created) VALUES('cOLD',1,'checked_no_change',?)", (old,))
            c.execute("INSERT INTO guardian_cycles(cycle_id,started,finished,status) "
                      "VALUES('cOLD',?,?, 'GREEN')", (old, old))
            c.execute("INSERT INTO guardian_cycles(cycle_id,started) VALUES('cCRASH',?)",
                      (old,))                       # unfinalized: crash evidence, kept
        self.state.pop("guardian_last_prune", None)
        self.cycle()                               # finalize runs the due sweep
        with app.db() as c:
            self.assertIsNone(c.execute("SELECT 1 FROM guardian_watch_results WHERE "
                                        "cycle_id='cOLD'").fetchone())
            self.assertIsNone(c.execute("SELECT 1 FROM guardian_cycles WHERE "
                                        "cycle_id='cOLD'").fetchone())
            kept = c.execute("SELECT status FROM guardian_cycles WHERE "
                             "cycle_id='cCRASH'").fetchone()
            self.assertIsNotNone(kept)             # unfinalized row survived the sweep...
            self.assertEqual(kept["status"], "aborted")   # ...and was flagged as a crash
            self.assertEqual(c.execute("SELECT COUNT(*) FROM guardian_watch_results "
                                       "WHERE watch_id=1 AND outcome='checked_no_change' "
                                       "AND cycle_id!='cOLD'").fetchone()[0], 1)
        self.assertEqual(self.state.get("guardian_last_prune"), self.clock[0] - 20)
        with app.db() as c:                        # within the interval: sweep must not rerun
            c.execute("INSERT INTO guardian_watch_results(cycle_id,watch_id,outcome,"
                      "created) VALUES('cOLD2',1,'checked_no_change',?)", (old,))
        self.cycle()
        with app.db() as c:
            self.assertIsNotNone(c.execute("SELECT 1 FROM guardian_watch_results WHERE "
                                           "cycle_id='cOLD2'").fetchone())

    def test_maturity_anchor_survives_windowing_and_pruning(self):
        self.add_user(1, push_sub=True)
        self.add_watch(1, section="0101")
        self.install(FakeSchool(steps=[{"data": {"TEST101": {"0101": sec(False, 0)}}}]))
        self.state["guardian_started_at"] = self.clock[0] - 5 * 86400
        self.cycle()
        factors = json.loads(self._snapshot_factors("system"))
        self.assertEqual(factors["P6_maturity"], 70)   # 20 + 5 days * 10, from the anchor

    def _snapshot_factors(self, etype):
        with app.db() as c:
            return c.execute("SELECT factors FROM guardian_confidence WHERE entity_type=? "
                             "ORDER BY date DESC LIMIT 1", (etype,)).fetchone()["factors"]

    def test_admin_stats_block_present(self):
        self.add_user(1)
        self.add_watch(1)
        self.install(FakeSchool(steps=[{"data": {"TEST101": {"0101": sec(False, 0)}}}]))
        self.cycle()
        block = guardian.report_block()
        self.assertEqual(block["mode"], "shadow")
        self.assertIsNotNone(block["last_cycle"])
        self.assertIn("confidence_worst_first", block)


if __name__ == "__main__":
    unittest.main(verbosity=2)
