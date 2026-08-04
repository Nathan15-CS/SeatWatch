#!/usr/bin/env python3
"""
SeatWatch Reliability Guardian — deterministic prove-it-worked layer.

Wraps every poll cycle with: an expected-watch snapshot, per-watch terminal
outcomes, expected-vs-actual IDENTITY reconciliation, alert-safety gates,
adapter health, incidents, damped operator paging, a machine+human report,
and the Reliability Confidence Engine (confidence.py).

Modes (GUARDIAN_MODE env, wired in app.main):
  off     — plumbing only: alerts/latching/ping byte-identical to legacy,
            nothing recorded. The rollback position.
  shadow  — DEFAULT. Records everything, evaluates every gate, logs what
            WOULD have been blocked/withheld — and changes NOTHING the user
            or Healthchecks can observe. Proven by differential tests.
  enforce — gates become real: unsafe alerts blocked, honest delivery latch,
            mass-alert freeze, Healthchecks ping withheld on RED.

Invariants (the whole point — do not weaken):
  * No Guardian failure may ever break the poller: every public entry point
    catches its own exceptions. In shadow a Guardian bug degrades to legacy
    behavior + a telemetry-integrity mark; it never blocks an alert.
  * In enforce, a gate that cannot evaluate FAILS CLOSED (block + page):
    "never guess" outranks "never miss" once enforcement is earned.
  * An LLM is never consulted for anything in this file. All thresholds are
    named constants below; changing one is a reviewed diff.
  * Evidence is written before success is claimed: finalize() persists the
    cycle before ping_ok() may say True.
"""
import collections
import hashlib
import json
import os
import threading
import time

import confidence as _conf

# ---------------------------------------------------------------- tuning
# Every operational knob in one place. Env-overridable where the operator may
# need to turn it without a deploy; plain constants otherwise.
TUNING = {
    # TWO TRIPWIRES, AND THE SECOND IS NOT VESTIGIAL — see the long note in flush_alerts.
    # Per-school is the primary gate: a parse break is a property of ONE school's page
    # format, so freezing the platform for it punishes schools whose data is fine.
    "MAX_SCHOOL_TRANSITIONS": int(os.environ.get("MAX_SCHOOL_TRANSITIONS", "10")),
    # Global backstop, deliberately ABOVE the per-school gate. Hundreds of schools share
    # one adapter family, so a vendor-side Banner/Colleague change can break many at once
    # while each school stays individually under its own threshold. Per-school scoping
    # cannot see that by construction. DO NOT DELETE THIS AS REDUNDANT.
    "MAX_ALERTS_PER_CYCLE": int(os.environ.get("MAX_ALERTS_PER_CYCLE", "25")),
    "FRESHNESS_MAX_S": 180,          # data older than this can never justify an alert
    "PAGE_COOLDOWN_S": 6 * 3600,     # damper: 1 operator page per failure class / 6h
    "RATE_WINDOW_S": 6 * 3600,       # adapter success-rate window (~1080 cycles)
    "RESULTS_RETENTION_S": 7 * 86400,  # per-watch/cycle evidence kept this long
    "PRUNE_EVERY_S": 6 * 3600,       # retention sweep cadence (cheap, but not per-cycle)
    "FREEZE_CLEAR_CYCLES": 3,        # calm cycles before a mass-freeze releases itself
    # Fraction of a school's sections reading FULL-while-holding-seats that stops looking
    # like waitlists and starts looking like an unread open flag (i.e. silent alerting).
    "HELD_SEATS_ALARM_FRAC": 0.25,
}

OUTCOMES = (
    "checked_no_change", "checked_open_latched", "checked_open_already",
    "checked_closed_reset", "blocked_wrong_term", "blocked_stale_data",
    "blocked_gate", "blocked_mass_freeze", "adapter_failed", "section_missing",
    "school_missing", "alert_delivered", "alert_undelivered", "write_failed",
    "unaccounted", "aborted",
)

# ---------------------------------------------------------------- wiring
# Dependency injection instead of importing app (avoids a circular import and
# makes every test deterministic: fake clock, fake pager, temp DB).
_CFG = {
    "mode": "off",
    "db": None,            # () -> sqlite3.Connection (row_factory=Row)
    "state_get": lambda k, d=None: d,
    "state_set": lambda **kv: None,
    "log": lambda *a: None,
    "notify_operator": lambda msg: None,
    "now": time.time,
    "deploy_sha": "",      # SEATWATCH_DEPLOY_SHA once the deploy script stamps it
}
_LOCK = threading.Lock()   # guards _CFG["..."] one-shot mutations + page damper


def configure(db_factory, state_get, state_set, log_fn, notify_operator_fn,
              now_fn=time.time, mode="shadow", deploy_sha=""):
    _CFG.update(db=db_factory, state_get=state_get, state_set=state_set,
                log=log_fn, notify_operator=notify_operator_fn, now=now_fn,
                mode=(mode if mode in ("off", "shadow", "enforce") else "shadow"),
                deploy_sha=deploy_sha)
    if _CFG["mode"] != "off":
        log_fn(f"[guardian] active, mode={_CFG['mode']} "
               f"(alerts {'GATED' if _CFG['mode'] == 'enforce' else 'observed only'})")


def mode():
    return _CFG["mode"]


def _now():
    return _CFG["now"]()


def now():
    """The Guardian's clock (injectable for tests). app code uses this for any
    timestamp a gate will later compare, so fake-clock tests stay coherent."""
    return _now()


def _active():
    return _CFG["mode"] != "off" and _CFG["db"] is not None


# ---------------------------------------------------------------- schema
def init_schema(c):
    """Additive only — safe against any existing DB, never migrates destructively."""
    c.execute("""CREATE TABLE IF NOT EXISTS guardian_cycles(
        cycle_id TEXT PRIMARY KEY, started REAL NOT NULL, finished REAL,
        mode TEXT, expected INTEGER, accounted INTEGER, status TEXT,
        binding TEXT, notes TEXT)""")
    c.execute("""CREATE TABLE IF NOT EXISTS guardian_watch_results(
        cycle_id TEXT NOT NULL, watch_id INTEGER NOT NULL, user_id INTEGER,
        school TEXT, course TEXT, section TEXT, term TEXT,
        outcome TEXT NOT NULL, adapter_term TEXT, fetched_at REAL,
        seats INTEGER, detail TEXT, created REAL NOT NULL)""")
    c.execute("CREATE INDEX IF NOT EXISTS ix_gwr_cycle ON guardian_watch_results(cycle_id)")
    c.execute("CREATE INDEX IF NOT EXISTS ix_gwr_watch ON guardian_watch_results(watch_id, created)")
    c.execute("""CREATE TABLE IF NOT EXISTS guardian_adapter_health(
        school TEXT PRIMARY KEY, checks INTEGER NOT NULL DEFAULT 0,
        failures INTEGER NOT NULL DEFAULT 0, empties INTEGER NOT NULL DEFAULT 0,
        consec_fail INTEGER NOT NULL DEFAULT 0, last_ok REAL, last_fail REAL,
        avg_ms INTEGER, max_ms INTEGER, yield_base REAL,
        sanity_violations INTEGER NOT NULL DEFAULT 0, clean_since REAL,
        window_start REAL, updated REAL)""")
    c.execute("""CREATE TABLE IF NOT EXISTS guardian_incidents(
        id INTEGER PRIMARY KEY AUTOINCREMENT, kind TEXT NOT NULL,
        severity TEXT NOT NULL, school TEXT NOT NULL DEFAULT '',
        watch_id INTEGER NOT NULL DEFAULT 0, first_seen REAL NOT NULL,
        last_seen REAL NOT NULL, count INTEGER NOT NULL DEFAULT 1,
        evidence TEXT, contained TEXT, status TEXT NOT NULL DEFAULT 'open',
        UNIQUE(kind, school, watch_id))""")
    c.execute("""CREATE TABLE IF NOT EXISTS guardian_confidence(
        entity_type TEXT NOT NULL, entity_id TEXT NOT NULL, date TEXT NOT NULL,
        score INTEGER NOT NULL, tier TEXT NOT NULL, binding TEXT,
        factors TEXT, PRIMARY KEY(entity_type, entity_id, date))""")


# ---------------------------------------------------------------- paging
def page(class_key, message, severity="warn"):
    """Damped operator page: first occurrence pages immediately, then at most
    one page per failure class per PAGE_COOLDOWN_S. Everything is logged.
    Damper state persists in the state file so restarts don't re-page."""
    try:
        _CFG["log"](f"  [guardian:{severity}] ({class_key}) {message}")
        with _LOCK:
            last = dict(_CFG["state_get"]("guardian_page_last", {}) or {})
            prev = float(last.get(class_key, 0))
            if _now() - prev < TUNING["PAGE_COOLDOWN_S"]:
                return False
            last[class_key] = _now()
            _CFG["state_set"](guardian_page_last=last)
        _CFG["notify_operator"](message)
        return True
    except Exception as e:                       # a broken pager must not break the poller
        _telemetry_mark(f"page:{type(e).__name__}")
        return False


_TELEMETRY_FAULTS = []   # in-process marks of Guardian's OWN failures (P4 input)


def _telemetry_mark(what):
    _TELEMETRY_FAULTS.append((_now(), what))
    del _TELEMETRY_FAULTS[:-200]
    try:
        _CFG["log"](f"  [guardian:self] telemetry fault: {what}")
    except Exception:
        pass


# ---------------------------------------------------------------- cycle
class Cycle:
    __slots__ = ("id", "t0", "mode", "expected", "results", "fetches",
                 "pending", "transitions", "would_block", "notes", "finalized", "ping")

    def __init__(self, cid, t0, mode_, expected):
        self.id, self.t0, self.mode = cid, t0, mode_
        self.expected = expected      # watch_id -> identity dict
        self.results = {}             # watch_id -> (outcome, detail dict)
        self.fetches = {}             # school -> {ok, ms, courses, sections}
        self.pending = []             # queued (row, msg, url) alert candidates
        self.transitions = set()      # DISTINCT (school, course, section) that flipped open
        self.would_block = []         # shadow divergences this cycle
        self.notes = []
        self.finalized = False
        self.ping = True


_SEQ = [0]   # per-process monotonic tiebreaker: two cycles in the same second must
             # never share an id, or the later row silently REPLACEs the earlier one


def begin_cycle(rows):
    """Snapshot the expected active-watch identities. Called first thing in
    run_cycle; returns a Cycle in every mode (off-mode cycles are inert
    plumbing so run_cycle stays single-path)."""
    t0 = _now()
    _SEQ[0] += 1
    cid = (f"c{int(t0)}-{_SEQ[0]}-"
           f"{hashlib.sha1(repr(sorted(r['id'] for r in rows)).encode()).hexdigest()[:8]}")
    expected = {}
    if _active():
        for r in rows:
            expected[r["id"]] = {
                "user_id": r["user_id"] if "user_id" in r.keys() else None,
                "school": r["school"], "course": r["course"],
                "section": r["section"], "term": r["term"],
            }
        _close_orphan_cycles()
    cyc = Cycle(cid, t0, _CFG["mode"], expected)
    _CUR["cycle"] = cyc
    return cyc


_CUR = {"cycle": None}   # last begun cycle, so a poller-level crash can be attributed


def poller_recover(exc):
    """Called from the poller's catch-all. Attributes the failure to the
    in-flight cycle (unprocessed watches -> 'aborted', evidence persisted)
    and pages ONCE per damper window instead of every 20 seconds."""
    try:
        cyc = _CUR["cycle"]
        if cyc is not None and not cyc.finalized and cyc.mode != "off":
            abort_cycle(cyc, exc)
        else:
            page("poller_error", f"Engine hit an error (contained, retrying): {exc}")
    except Exception as e:
        _telemetry_mark(f"poller_recover:{type(e).__name__}")


def _close_orphan_cycles():
    """A cycle that began but never finalized = the process died mid-cycle
    (crash-before-ping). Surface it instead of letting it vanish."""
    try:
        with _CFG["db"]() as c:
            orphans = c.execute("SELECT cycle_id, started FROM guardian_cycles "
                                "WHERE finished IS NULL").fetchall()
            for o in orphans:
                c.execute("UPDATE guardian_cycles SET finished=?, status='aborted', "
                          "notes='process died before finalize' WHERE cycle_id=?",
                          (_now(), o["cycle_id"]))
                _incident(c, "crash_before_finalize", "red", "", 0,
                          f"cycle {o['cycle_id']} started {o['started']} never finalized")
        if orphans:
            page("crash_before_finalize",
                 f"🚨 {len(orphans)} cycle(s) died before completing reconciliation "
                 "— the process crashed mid-check. Evidence preserved.", "red")
    except Exception as e:
        _telemetry_mark(f"orphans:{type(e).__name__}")


def note_fetch(cycle, school_id, ok, ms, data):
    if cycle.mode == "off":
        return
    try:
        # THE CONTRACT IS ASYMMETRIC, because the two ways a row can disagree with itself
        # have opposite consequences:
        #
        #   open=True, seats=0   DANGEROUS. We would alert a student to a seat that is not
        #                        there. They drop what they are doing, race to the
        #                        registrar, find nothing, and never trust an alert again.
        #                        Always pages.
        #
        #   open=False, seats>0  USUALLY FINE. A waitlisted section shows a seat you cannot
        #                        simply take, and reading it as closed is CORRECT. The cost
        #                        of being wrong is that we stay quiet — conservative, not
        #                        harmful. Butte paged on 50 of 50 fetches for exactly two
        #                        such rows out of ~52, and treating that as "parse drift,
        #                        do not trust this school" is how an operator learns to
        #                        ignore the pager.
        #
        # But it is not ALWAYS fine: if a parser stopped reading the open flag entirely,
        # every section would look full-while-holding-seats and we would go silent on a
        # whole school. So it pages when it is WIDESPREAD — a handful is waitlists, most of
        # the catalogue is a broken flag.
        nsecs, bad, held = 0, 0, 0
        for course_secs in (data or {}).values():
            nsecs += len(course_secs)
            for info in course_secs.values():
                seats = info.get("seats")
                if seats is None:
                    continue
                op = bool(info.get("open"))
                if not isinstance(seats, int) or seats < 0 or (op and seats == 0):
                    bad += 1                     # a seat we might advertise that isn't real
                elif not op and seats > 0:
                    held += 1                    # waitlisted / restricted: safe to ignore
        cycle.fetches[school_id] = {"ok": bool(ok), "ms": int(ms),
                                    "courses": len(data or {}), "sections": nsecs,
                                    "violations": bad, "held": held}
        if bad:
            page(f"sanity:{school_id}",
                 f"🚨 {school_id}: {bad} section row(s) claim a seat that is not there "
                 "(open with 0 seats, or a negative count) — this is the shape that "
                 "produces FALSE ALERTS. Inspect before trusting this school.", "red")
        elif nsecs and held >= max(4, int(nsecs * TUNING["HELD_SEATS_ALARM_FRAC"])):
            page(f"held:{school_id}",
                 f"⚠️ {school_id}: {held} of {nsecs} sections read as FULL while showing "
                 "seats. A few is normal (waitlists); this many suggests the open flag is "
                 "no longer being read, which would make this school silently stop "
                 "alerting.")
    except Exception as e:
        _telemetry_mark(f"note_fetch:{type(e).__name__}")


def record(cycle, watch_id, outcome, **detail):
    """One terminal outcome per watch per cycle. A second write for the same
    watch keeps the FIRST (terminal means terminal) unless it upgrades a
    checked_* to an alert_* outcome."""
    if cycle.mode == "off":
        return
    try:
        prev = cycle.results.get(watch_id)
        if prev and outcome != "write_failed" and \
                not (prev[0].startswith("checked") and outcome.startswith("alert")):
            return                    # terminal stays terminal; write_failed always wins
        cycle.results[watch_id] = (outcome, detail)
    except Exception as e:
        _telemetry_mark(f"record:{type(e).__name__}")


# ---------------------------------------------------------------- gates
def gate(cycle, r, cur_term, fetched_at):
    """Alert-safety gate for one candidate. Returns (allow, reason).
    Pure checks only — every input is passed in. In enforce, an internal
    error fails CLOSED; in shadow/off it fails OPEN (legacy behavior rules)."""
    try:
        checks = []
        # the watch must still exist and still be unlatched (deletion race)
        with _CFG["db"]() as c:
            live = c.execute("SELECT alerted FROM watches WHERE id=?", (r["id"],)).fetchone()
        checks.append(("watch_exists", live is not None))
        checks.append(("not_latched", bool(live) and live["alerted"] == 0))
        # term: a DEFINITE mismatch is blocked upstream; here we assert equality
        # when both sides are known. Empty stamps are allowed through but marked
        # term_unverified — blocking them would silence 249 schools' watches
        # entirely (see backlog item BL-EMPTY-TERM for the real fix).
        if r["term"] and cur_term:
            checks.append(("term_match", r["term"] == cur_term))
        # freshness: this cycle's own fetch must be recent
        checks.append(("fresh_data", fetched_at is not None
                       and _now() - fetched_at <= TUNING["FRESHNESS_MAX_S"]))
        failed = [name for name, ok in checks if not ok]
        return (not failed, ",".join(failed) or "ok")
    except Exception as e:
        _telemetry_mark(f"gate:{type(e).__name__}")
        if _CFG["mode"] == "enforce":
            page("gate_error", f"🚨 alert gate crashed ({type(e).__name__}) — failing "
                 "CLOSED per policy; alerts blocked until this is fixed.", "red")
            return (False, "guardian_error")
        return (True, "guardian_error_failopen")


def queue_alert(cycle, r, msg, url, sections=None):
    """Defer the send so the mass-alert tripwire can see the WHOLE cycle's
    would-fire count before any message leaves (send-none-on-mass, not
    send-some).

    `sections` is the section list that ACTUALLY flipped open in the registrar's data.
    An any-section watch ("" section) alerts once for the whole course but may represent
    many sections changing at once, and that count is the tripwire's entire signal — so
    it must be passed in rather than inferred from the watch row, which does not know it.
    """
    cycle.pending.append((r, msg, url))
    for sec_ in (sections if sections else [r["section"]]):
        cycle.transitions.add((r["school"], r["course"], sec_))


def flush_alerts(cycle, alert_fn, set_alerted_fn, cur_term_by_school, fetched_at_by_school):
    """Run the per-alert gate + the mass tripwire, then deliver.
    off/shadow: every queued alert sends exactly as legacy would; gate results
    are recorded as would-blocks only. enforce: blocks are real.
    Exceptions from alert_fn/set_alerted_fn propagate in off/shadow (legacy
    abort semantics — the differential guarantee) after being recorded."""
    # COUNT SEAT OPENINGS, NOT STUDENTS.
    #
    # This was len(cycle.pending) — one entry per WATCH about to fire. That makes the
    # threshold a function of how many students use the product: one genuine seat opening
    # in a popular course produces one pending entry per watcher. At today's concentration
    # (CMSC216 holds 7 of 14 watches) a single real opening would trip a cap of 25 at
    # roughly 50 students, and a cap of 100 at roughly 200. Under enforcement that is a
    # platform-wide alert outage caused by the single most valuable event this product can
    # observe — a seat opening in its most-watched course. The freeze would have fired
    # first, and hardest, on the best day the product ever had. Raising the number only
    # picks the user count at which it happens; any watcher-based threshold has that shape.
    #
    # Distinct section transitions are bounded by what the REGISTRAR changed, not by how
    # many people are looking. Measured over all production history: the worst 60s window
    # was 3 alerts from 1 section, and every window ever recorded was exactly 1 section.
    # Real openings arrive a section at a time; a parse break flips dozens at once. That
    # separation is the thing worth gating on, and it does not drift as the userbase grows.
    n = len(cycle.transitions)
    per_school = collections.Counter(sch for sch, _, _ in cycle.transitions)

    # TWO TRIPWIRES, AND THE GLOBAL ONE IS NOT VESTIGIAL.
    #
    # PER-SCHOOL is the primary gate. A parse break is a property of ONE school's page
    # format. A single global freeze meant a UMD break stopped alerting USF and OU
    # students whose data was perfectly fine — collateral damage with no diagnostic
    # value. Scoping per school contains the blast radius to the school that is actually
    # lying, and makes the threshold meaningful: each school is compared against itself
    # rather than against the sum of everything, so the number stops drifting as coverage
    # grows. UMD's entire watched surface is 7 sections today; a per-school cap of 10 sits
    # above it, and stays correct however many schools we add.
    #
    # GLOBAL is the backstop, deliberately set ABOVE the per-school gate. Hundreds of
    # schools share one adapter family, so a vendor-side Banner or Colleague change can
    # break many at once while each individual school sits comfortably under its own
    # threshold — catastrophic in aggregate, invisible to per-school scoping BY
    # CONSTRUCTION. If you are reading this because a global cap above a per-school cap
    # looks redundant: it is not, and removing it reopens exactly that hole.
    frozen_schools, frozen_global = set(), False

    if cycle.mode == "enforce":
        latched, calm = {}, {}
        try:
            latched = _CFG["state_get"]("guardian_freeze") or {}
            calm = _CFG["state_get"]("guardian_freeze_calm") or {}
            frozen_global = bool(_CFG["state_get"]("guardian_freeze_global"))
        except Exception as e:
            _telemetry_mark(f"freeze_read:{type(e).__name__}")
        # Before scoping, this key held a bare {"at":..,"n":..} meaning "everything is
        # frozen". Nothing was latched in production when scoping shipped, so this is
        # belt-and-braces — but read as school ids an old value would "freeze" two
        # schools named at/n while silently releasing every real one.
        if isinstance(latched, dict) and "at" in latched:
            frozen_global, latched = True, {}
        if not isinstance(latched, dict):
            latched = {}
        if not isinstance(calm, dict):
            calm = {}

        # ---- release, per school, judged on THAT SCHOOL'S own load ----
        for sch in list(latched):
            if per_school.get(sch, 0) <= TUNING["MAX_SCHOOL_TRANSITIONS"]:
                c = int(calm.get(sch, 0) or 0) + 1
                if c >= TUNING["FREEZE_CLEAR_CYCLES"]:
                    latched.pop(sch, None)
                    calm.pop(sch, None)
                    page(f"freeze_cleared_{sch}",
                         f"✅ {sch}: alert freeze CLEARED automatically — {c} consecutive "
                         f"cycles back under {TUNING['MAX_SCHOOL_TRANSITIONS']} section "
                         "changes. Alerts flowing again for this school. A real parse "
                         "break would have kept the load high and held the freeze.",
                         "warn")
                else:
                    calm[sch] = c
            else:
                calm[sch] = 0                      # still cascading; restart the count
                page(f"freeze_{sch}_still",
                     f"🚨 {sch}: alert freeze STILL ACTIVE — {per_school.get(sch, 0)} "
                     "sections still changing per cycle. Other schools are unaffected.",
                     "red")

        # ---- release, global ----
        if frozen_global:
            if n <= TUNING["MAX_ALERTS_PER_CYCLE"]:
                c = int(_CFG["state_get"]("guardian_freeze_calm_global", 0) or 0) + 1
                if c >= TUNING["FREEZE_CLEAR_CYCLES"]:
                    frozen_global = False
                    _CFG["state_set"](guardian_freeze_global=None,
                                      guardian_freeze_calm_global=0)
                    page("mass_freeze_cleared",
                         f"✅ GLOBAL alert freeze CLEARED automatically — {c} consecutive "
                         f"cycles back under {TUNING['MAX_ALERTS_PER_CYCLE']} total "
                         "section changes. Alerts flowing again platform-wide.", "warn")
                else:
                    _CFG["state_set"](guardian_freeze_calm_global=c)
            else:
                _CFG["state_set"](guardian_freeze_calm_global=0)

        # ---- trip, per school ----
        for sch, cnt in sorted(per_school.items()):
            if cnt > TUNING["MAX_SCHOOL_TRANSITIONS"] and sch not in latched:
                latched[sch] = {"at": _now(), "n": cnt}
                calm[sch] = 0
                page(f"freeze_{sch}",
                     f"🚨 {sch}: ALERT FREEZE — {cnt} sections changed state in one cycle "
                     f"(cap {TUNING['MAX_SCHOOL_TRANSITIONS']}). Likely a parse break or "
                     "term roll at this school, not real seats. Nothing sent FOR THIS "
                     "SCHOOL; every other school is unaffected. Clears itself once this "
                     "school's load returns to normal.", "red")
        try:
            _CFG["state_set"](guardian_freeze=latched or None, guardian_freeze_calm=calm or None)
        except Exception as e:
            _telemetry_mark(f"freeze:{type(e).__name__}")
        frozen_schools = set(latched)

    elif cycle.mode == "shadow":
        for sch, cnt in sorted(per_school.items()):
            if cnt > TUNING["MAX_SCHOOL_TRANSITIONS"]:
                d = (f"{sch}: {cnt} section changes in one cycle "
                     f"(cap {TUNING['MAX_SCHOOL_TRANSITIONS']})")
                cycle.would_block.append({"kind": "school_freeze", "school": sch, "detail": d})
                page(f"freeze_{sch}_shadow", "⚠️ [shadow] per-school tripwire WOULD have "
                     f"frozen {sch}: {d} (alerts still sent — shadow mode)")

    # ---- the global backstop: adapter-family events per-school scoping cannot see ----
    if n > TUNING["MAX_ALERTS_PER_CYCLE"]:
        detail = (f"{n} section changes across {len(per_school)} schools in one cycle "
                  f"(global cap {TUNING['MAX_ALERTS_PER_CYCLE']}) — an adapter-FAMILY "
                  "event: many schools breaking together, each possibly still under its "
                  "own per-school threshold.")
        if cycle.mode == "enforce":
            frozen_global = True
            try:
                _CFG["state_set"](guardian_freeze_global={"at": _now(), "n": n},
                                  guardian_freeze_calm_global=0)
            except Exception as e:
                _telemetry_mark(f"freeze:{type(e).__name__}")
            page("mass_freeze", "🚨 GLOBAL ALERT FREEZE: " + detail +
                 " NOTHING was sent, platform-wide. Clears itself once the load returns "
                 "to normal.", "red")
        elif cycle.mode == "shadow":
            cycle.would_block.append({"kind": "mass_freeze", "detail": detail})
            page("mass_freeze_shadow", "⚠️ [shadow] global tripwire WOULD have frozen "
                 "this cycle: " + detail + " (alerts still sent — shadow mode)")

    for r, msg, url in cycle.pending:
        wid = r["id"]
        school = r["school"]
        allow, reason = (True, "off") if cycle.mode == "off" else gate(
            cycle, r, cur_term_by_school.get(school), fetched_at_by_school.get(school))
        blocked = frozen_global or school in frozen_schools
        if cycle.mode == "enforce" and (blocked or not allow):
            record(cycle, wid, "blocked_mass_freeze" if blocked else "blocked_gate",
                   reason=reason)
            continue
        if cycle.mode == "shadow" and (not allow):
            cycle.would_block.append({"kind": "gate", "watch_id": wid, "reason": reason})
        try:
            delivered = alert_fn(r, msg, url)
        except Exception:
            record(cycle, wid, "write_failed", stage="alert_fn")
            raise                                   # legacy semantics: cycle aborts
        record(cycle, wid, "alert_delivered" if delivered else "alert_undelivered",
               gate="ok" if allow else reason)
        if delivered:
            try:
                set_alerted_fn(wid, 1)
            except Exception:
                record(cycle, wid, "write_failed", stage="set_alerted")
                raise
    cycle.pending = []
    cycle.transitions = set()


def latch_decision(r, ntfy_ok, pushed, emailed, texted):
    """The honest-delivery latch. Legacy: any channel (incl. a bare ntfy 200)
    latches. Honest: a human-reaching channel must succeed when the account
    has one enrolled; ntfy alone latches only for accounts with no push sub
    and no email (topic-only legacy users).
    off/shadow return the LEGACY answer (behavior-neutral); enforce returns
    the honest one. Shadow records the divergence for the report."""
    legacy = bool(ntfy_ok) or (pushed > 0) or bool(emailed) or bool(texted)
    if _CFG["mode"] == "off":
        return legacy
    try:
        uid = r["user_id"] if "user_id" in r.keys() else None
        has_push = has_email = False
        if uid:
            with _CFG["db"]() as c:
                has_push = c.execute("SELECT 1 FROM push_subs WHERE user_id=? LIMIT 1",
                                     (uid,)).fetchone() is not None
                u = c.execute("SELECT email FROM users WHERE id=?", (uid,)).fetchone()
                has_email = bool(u and u["email"])
            # ENROLLED means enrolled AND ENABLED. A channel the user switched off is one
            # we never attempt, so counting it as enrolled makes the honest latch demand
            # delivery on a channel that was never tried. In shadow that logs divergences
            # which are not real; once enforcement is on it is worse — a correctly
            # delivered alert fails to latch and the watch re-fires every single cycle.
            # Read through app so sender and latch share one definition.
            try:
                import app as _app
                want_push, want_email = _app.notify_prefs(uid)[:2]
                has_push = has_push and want_push
                has_email = has_email and want_email
            except Exception:
                pass          # prefs unreadable: fall back to enrolment alone (today's rule)
        honest = (pushed > 0) or bool(emailed) or bool(texted) or \
                 (bool(ntfy_ok) and not (has_push or has_email))
        if _CFG["mode"] == "enforce":
            return honest
        if legacy and not honest:
            _LAST_DIVERGENCE.append({"kind": "dishonest_latch", "watch_id": r["id"],
                                     "at": _now()})
            del _LAST_DIVERGENCE[:-100]
        return legacy
    except Exception as e:
        _telemetry_mark(f"latch:{type(e).__name__}")
        return legacy if _CFG["mode"] != "enforce" else False


_LAST_DIVERGENCE = []   # latch divergences observed since start (shadow evidence)


# ---------------------------------------------------------------- finalize
def _incident(c, kind, severity, school, watch_id, evidence, contained=""):
    c.execute("""INSERT INTO guardian_incidents(kind,severity,school,watch_id,
        first_seen,last_seen,count,evidence,contained)
        VALUES(?,?,?,?,?,?,1,?,?)
        ON CONFLICT(kind,school,watch_id) DO UPDATE SET
        last_seen=excluded.last_seen, count=count+1,
        evidence=excluded.evidence, status='open'""",
              (kind, severity, school, watch_id, _now(), _now(), evidence, contained))


def finalize(cycle):
    """Reconcile identities, persist everything in one transaction, update
    adapter health + confidence, classify GREEN/YELLOW/RED, decide the ping.
    Returns the status string. Never raises."""
    if cycle.mode == "off" or cycle.finalized:
        cycle.finalized = True
        return "off"
    try:
        return _finalize_inner(cycle)
    except Exception as e:
        _telemetry_mark(f"finalize:{type(e).__name__}:{e}")
        cycle.finalized = True
        cycle.ping = _CFG["mode"] != "enforce"    # can't prove it worked -> don't claim it
        page("guardian_write", f"Guardian could not persist cycle evidence "
             f"({type(e).__name__}) — telemetry degraded; investigating required.")
        return "RED"


def _finalize_inner(cycle):
    now = _now()
    # identity reconciliation — every expected watch needs a terminal outcome
    unaccounted = [wid for wid in cycle.expected if wid not in cycle.results]
    for wid in unaccounted:
        cycle.results[wid] = ("unaccounted", {"why": "no terminal outcome recorded"})
    outcomes = {}
    for wid, (oc, _d) in cycle.results.items():
        outcomes[oc] = outcomes.get(oc, 0) + 1
    # status rules — deterministic, ordered worst-first
    status, binding = "GREEN", ""
    # school_missing was in NEITHER list, so a watch pointing at a school that no longer
    # exists in the registry finalized the cycle GREEN while raising a RED orphan_watch
    # incident. Measured, not inferred: driving one school_missing through finalize()
    # produced status=GREEN. That watch is permanently dead and the dashboard said fine.
    yellow_ocs = ("adapter_failed", "section_missing", "alert_undelivered",
                  "blocked_wrong_term", "blocked_stale_data", "blocked_gate",
                  "school_missing")
    if unaccounted:
        status, binding = "RED", f"{len(unaccounted)} watch(es) unaccounted"
    elif outcomes.get("write_failed"):
        status, binding = "RED", "database write failed mid-cycle"
    elif outcomes.get("blocked_mass_freeze"):
        status, binding = "RED", "mass-alert freeze tripped"
    elif any(outcomes.get(o) for o in yellow_ocs):
        worst = next(o for o in yellow_ocs if outcomes.get(o))
        status, binding = "YELLOW", f"{outcomes[worst]}x {worst}"
    with _CFG["db"]() as c:
        c.execute("INSERT OR REPLACE INTO guardian_cycles VALUES(?,?,?,?,?,?,?,?,?)",
                  (cycle.id, cycle.t0, now, cycle.mode, len(cycle.expected),
                   len(cycle.expected) - len(unaccounted), status, binding,
                   json.dumps({"outcomes": outcomes,
                               "would_block": cycle.would_block[:20]})))
        for wid, (oc, d) in cycle.results.items():
            ident = cycle.expected.get(wid, {})
            c.execute("""INSERT INTO guardian_watch_results(cycle_id,watch_id,user_id,
                school,course,section,term,outcome,adapter_term,fetched_at,seats,
                detail,created) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                      (cycle.id, wid, ident.get("user_id"), ident.get("school"),
                       ident.get("course"), ident.get("section"), ident.get("term"),
                       oc, d.get("adapter_term"), d.get("fetched_at"),
                       d.get("seats"), json.dumps({k: v for k, v in d.items()
                                                   if k not in ("adapter_term", "fetched_at", "seats")}),
                       now))
        _update_adapter_health(c, cycle, now)
        for wid in unaccounted:
            ident = cycle.expected.get(wid, {})
            _incident(c, "unaccounted_watch", "red", ident.get("school", ""), wid,
                      f"cycle {cycle.id}: watch {wid} had no terminal outcome")
        for oc, kind, sev in (("school_missing", "orphan_watch", "red"),
                              ("section_missing", "section_missing", "yellow"),
                              ("blocked_wrong_term", "term_stale_watch", "yellow"),
                              ("alert_undelivered", "undelivered_alert", "red")):
            for wid, (o, d) in cycle.results.items():
                if o == oc:
                    ident = cycle.expected.get(wid, {})
                    _incident(c, kind, sev, ident.get("school", ""), wid,
                              f"cycle {cycle.id}: {json.dumps(d)[:200]}",
                              contained="alert suppressed by existing fail-closed skip"
                              if oc != "alert_undelivered" else "retrying every cycle")
        _maybe_prune(c, now)
        conf = _compute_confidence(c, cycle, now)
    if status == "RED":
        page("cycle_red", f"🚨 Guardian cycle RED: {binding}. Evidence in guardian_* "
             "tables, cycle " + cycle.id, "red")

    # ---- surfacing: which recorded conditions actually reach a human --------------
    # Until now ONLY a RED cycle paged, so every condition below recorded faultless
    # evidence that nobody ever read. Each of these is a state where a student's watch
    # has silently stopped working -- the watch still exists, the cycle still looks
    # healthy, and no alert will ever fire again for it.
    #
    # These page at "warn", NOT by promotion to RED: in enforce mode RED suppresses the
    # ping and fails the dead-man, which is far too aggressive for conditions that are
    # the fail-closed guards behaving exactly as designed.
    #
    # page() dedupes per class_key on PAGE_COOLDOWN_S, and the key carries the school so
    # one rolled school cannot page every 20 seconds and a second school is not muted by
    # the first.
    for oc, key, why in (
            ("blocked_wrong_term", "term_stale",
             "watches are stamped for a term the school has rolled past. They are "
             "blocked (correctly, no false alerts) but will NEVER fire again until the "
             "stamps are bumped. This is the semester-boundary cliff"),
            ("school_missing", "orphan_watch",
             "watches point at a school id no longer in the registry. Permanently dead"),
            ("section_missing", "section_gone",
             "the exact section a student is watching is no longer in the catalogue. "
             "That watch can never fire again"),
    ):
        n = outcomes.get(oc)
        if n:
            schools_hit = sorted({(cycle.expected.get(w) or {}).get("school", "?")
                                  for w, (o, _d) in cycle.results.items() if o == oc})
            page(f"{key}:{','.join(schools_hit)[:60]}",
                 f"⚠️ {n} watch(es) at {', '.join(schools_hit) or '?'}: {why}. "
                 f"Cycle {cycle.id}.", "warn")

    # DELIBERATE non-pagers, so the next person does not have to rediscover the reasoning:
    #   alert_undelivered — app.py already pages per-watch via operator_alert() the first
    #       time a seat reaches NOBODY, and retries every cycle. Paging here too would
    #       double-page the single most urgent condition we have.
    #   blocked_stale_data / blocked_gate — these ARE the fail-closed guards working. They
    #       fire during ordinary operation (a slow adapter, a gate refusing thin data) and
    #       suppress nothing a student would have received. Paging them is alert fatigue.
    #   adapter_failed — rolls up into adapter_down below, which pages on persistence
    #       rather than on a single bad fetch.
    cycle.finalized = True
    cycle.ping = (status != "RED") if _CFG["mode"] == "enforce" else True
    _write_report(cycle, status, binding, outcomes, conf)
    return status


def _maybe_prune(c, now):
    """Bound evidence growth: watch-result and finalized-cycle rows older than
    RESULTS_RETENTION_S are deleted (at 17 watches the results table grows
    ~73k rows/day — unbounded would be ~27M rows/yr). Runs at most once per
    PRUNE_EVERY_S. Kept forever: daily confidence snapshots (7 rows/day),
    deduped incidents, adapter health (one row/school), and any UNFINALIZED
    cycle row — the crash-before-finalize detector needs those."""
    try:
        last = float(_CFG["state_get"]("guardian_last_prune", 0) or 0)
        if now - last < TUNING["PRUNE_EVERY_S"]:
            return
        cut = now - TUNING["RESULTS_RETENTION_S"]
        c.execute("DELETE FROM guardian_watch_results WHERE created<?", (cut,))
        # cycles age from FINISHED, not started: a stale orphan closed as 'aborted'
        # just now must survive a full retention window from its discovery
        c.execute("DELETE FROM guardian_cycles WHERE finished IS NOT NULL AND finished<?",
                  (cut,))
        _CFG["state_set"](guardian_last_prune=now)
    except Exception as e:
        _telemetry_mark(f"prune:{type(e).__name__}")


def _update_adapter_health(c, cycle, now):
    for school, f in cycle.fetches.items():
        row = c.execute("SELECT * FROM guardian_adapter_health WHERE school=?",
                        (school,)).fetchone()
        if row and now - (row["window_start"] or 0) < TUNING["RATE_WINDOW_S"]:
            checks, fails, empties = row["checks"] + 1, row["failures"], row["empties"]
            wstart = row["window_start"]
        else:
            checks, fails, empties, wstart = 1, 0, 0, now
        consec = (row["consec_fail"] if row else 0)
        avg = (row["avg_ms"] if row and row["avg_ms"] else f["ms"])
        clean_since = row["clean_since"] if row and row["clean_since"] else now
        viol = (row["sanity_violations"] if row else 0) + f.get("violations", 0)
        ybase = row["yield_base"] if row and row["yield_base"] else float(f["sections"] or 0)
        if f["ok"] and f["sections"] > 0:
            consec, last_ok, last_fail = 0, now, (row["last_fail"] if row else None)
            ybase = ybase * 0.95 + f["sections"] * 0.05   # slow baseline for yield drift
            if f.get("violations"):
                clean_since = now                          # a contract violation is an anomaly
        else:
            fails, consec = fails + 1, consec + 1
            empties += (0 if f["ok"] else 1)
            last_ok, last_fail, clean_since = (row["last_ok"] if row else None), now, now
        c.execute("""INSERT OR REPLACE INTO guardian_adapter_health VALUES
            (?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                  (school, checks, fails, empties, consec, last_ok, last_fail,
                   int(avg * 0.9 + f["ms"] * 0.1), max(f["ms"], row["max_ms"] if row and row["max_ms"] else 0),
                   ybase, viol, clean_since, wstart, now))
        if consec >= 5:    # persistent adapter outage is an INCIDENT, not just a page
            _incident(c, "adapter_down", "red" if consec >= 15 else "yellow", school, 0,
                      f"{consec} consecutive failed/empty fetches; last ok "
                      f"{'never' if not last_ok else '%.0fs ago' % (now - last_ok)}",
                      contained="fail-closed: no data -> no alerts from this school")
            # ...and it now also TELLS someone. This raised an incident at 5 consecutive
            # failures and a red one at 15, and paged at neither: a school could be
            # unreachable for hours with every watch on it silently dead, while the cycle
            # read YELLOW and nobody was notified. Keyed per school so one dead host
            # cannot mute the others, and damped by PAGE_COOLDOWN_S.
            page(f"adapter_down:{school}",
                 f"{'🚨' if consec >= 15 else '⚠️'} {school}: {consec} consecutive failed "
                 f"or empty fetches (last good "
                 f"{'never' if not last_ok else '%.0f min ago' % ((now - last_ok) / 60)}). "
                 "Fail-closed, so no false alerts — but NO seat alerts will fire for any "
                 "watch at this school until it recovers.",
                 "red" if consec >= 15 else "warn")
        elif row and row["consec_fail"] >= 5:
            c.execute("UPDATE guardian_incidents SET status='resolved', last_seen=? "
                      "WHERE kind='adapter_down' AND school=? AND status='open'",
                      (now, school))


def _compute_confidence(c, cycle, now):
    """Assemble evidence and hand it to the pure engine. Snapshot once/day."""
    try:                                  # P6 maturity anchor: persisted first-run stamp,
        started_at = _CFG["state_get"]("guardian_started_at")   # so retention pruning
        if not started_at:                # can never shrink the operating-age evidence
            started_at = now
            _CFG["state_set"](guardian_started_at=now)
    except Exception:
        started_at = None
    ev = _conf.gather_evidence(c, cycle, now, TUNING,
                               started_at=started_at,
                               deploy_sha=_CFG["deploy_sha"],
                               drill_age_s=_drill_age(now),
                               telemetry_faults=len([t for t, _ in _TELEMETRY_FAULTS
                                                     if now - t < 86400]),
                               divergences=len(cycle.would_block) + len(_LAST_DIVERGENCE))
    result = _conf.compute(ev, TUNING)
    day = time.strftime("%Y-%m-%d", time.localtime(now))
    for ent_type, ent_id, score, tier, binding, factors in result["snapshots"]:
        c.execute("INSERT OR REPLACE INTO guardian_confidence VALUES(?,?,?,?,?,?,?)",
                  (ent_type, ent_id, day, score, tier, binding, json.dumps(factors)))
    return result


def _drill_age(now):
    try:
        last = float(_CFG["state_get"]("last_drill", 0) or 0)
        return (now - last) if last else None
    except Exception:
        return None


def abort_cycle(cycle, exc):
    """Poller-level exception: mark every unprocessed watch, keep the evidence.
    The legacy operator page becomes a damped page (C6)."""
    if cycle.mode == "off" or cycle.finalized:
        return
    try:
        for wid in cycle.expected:
            if wid not in cycle.results:
                cycle.results[wid] = ("aborted", {"why": f"cycle exception: {exc}"})
        finalize(cycle)
    except Exception as e:
        _telemetry_mark(f"abort:{type(e).__name__}")
    page("poller_error", f"Engine hit an error (contained, retrying): {exc}")


def ping_ok(cycle):
    """off/shadow: always True (Healthchecks semantics unchanged until
    enforcement is earned). enforce: only a finalized non-RED cycle pings."""
    if _CFG["mode"] != "enforce":
        return True
    return bool(cycle and cycle.finalized and cycle.ping)


# ---------------------------------------------------------------- reporting
def _report_path():
    dbp = os.environ.get("SEATWATCH_DB", "watches.db")
    return dbp + ".guardian.json"


def _write_report(cycle, status, binding, outcomes, conf):
    try:
        rep = {
            "cycle_id": cycle.id, "mode": cycle.mode, "status": status,
            "binding": binding, "started": cycle.t0, "finished": _now(),
            "expected": len(cycle.expected),
            "outcomes": outcomes,
            "would_block": cycle.would_block,
            "confidence": conf.get("summary") if conf else None,
            "note": "RCI is measured evidence strength, not a probability.",
        }
        tmp = _report_path() + ".tmp"
        with open(tmp, "w") as f:
            json.dump(rep, f, indent=1)
        os.replace(tmp, _report_path())
    except Exception as e:
        _telemetry_mark(f"report:{type(e).__name__}")


def summary_line():
    """One line for the existing daily operator digest — the single channel."""
    if not _active():
        return ""
    try:
        with _CFG["db"]() as c:
            cyc = c.execute("SELECT * FROM guardian_cycles WHERE finished IS NOT NULL "
                            "ORDER BY finished DESC LIMIT 1").fetchone()
            n_open = c.execute("SELECT COUNT(*) FROM guardian_incidents "
                               "WHERE status='open'").fetchone()[0]
            sysrow = c.execute("SELECT score, tier, binding FROM guardian_confidence "
                               "WHERE entity_type='system' ORDER BY date DESC LIMIT 1").fetchone()
        if not cyc:
            return f"Guardian[{_CFG['mode']}]: no finalized cycles yet."
        conf_s = (f"RCI {sysrow['score']} {sysrow['tier']} (binding: {sysrow['binding']})"
                  if sysrow else "RCI n/a")
        return (f"Guardian[{_CFG['mode']}]: {cyc['accounted']}/{cyc['expected']} reconciled, "
                f"{cyc['status']}"
                + (f" ({cyc['binding']})" if cyc["binding"] else "")
                + f" · {conf_s} · {n_open} open incident(s)")
    except Exception as e:
        _telemetry_mark(f"summary:{type(e).__name__}")
        return f"Guardian[{_CFG['mode']}]: summary unavailable (telemetry fault)"


def report_block():
    """Machine block for /admin/stats — aggregates only, no PII."""
    if not _active():
        return {"mode": _CFG["mode"]}
    try:
        with _CFG["db"]() as c:
            cyc = c.execute("SELECT * FROM guardian_cycles WHERE finished IS NOT NULL "
                            "ORDER BY finished DESC LIMIT 1").fetchone()
            conf = c.execute("SELECT entity_type, entity_id, score, tier, binding FROM "
                             "guardian_confidence WHERE date=(SELECT MAX(date) FROM "
                             "guardian_confidence) ORDER BY score ASC LIMIT 25").fetchall()
            inc = c.execute("SELECT kind, severity, school, count, status FROM "
                            "guardian_incidents WHERE status='open' "
                            "ORDER BY last_seen DESC LIMIT 25").fetchall()
            return {"mode": _CFG["mode"],
                    "last_cycle": dict(cyc) if cyc else None,
                    "confidence_worst_first": [dict(r) for r in conf],
                    "open_incidents": [dict(r) for r in inc],
                    "backlog": build_backlog(c)}
    except Exception as e:
        _telemetry_mark(f"report_block:{type(e).__name__}")
        return {"mode": _CFG["mode"], "error": "telemetry fault"}


# ------------------------------------------------- engineering improvement
# Evidence-driven backlog: deterministic rules over recorded incidents,
# adapter health, and confidence bindings. Read-only — it PROPOSES work,
# ranked by measured impact; it never changes code and never invents items
# without evidence rows behind them. IDs are stable hashes so week-over-week
# diffs track the same item.
_SEV_RANK = {"red": 0, "yellow": 1, "info": 2}


def build_backlog(c=None):
    if not _active():
        return []
    own = c is None
    conn = None
    try:
        if own:
            conn = _CFG["db"]()
            c = conn
        items = []

        def add(key, title, severity, evidence, affected):
            items.append({
                "id": "BL-" + hashlib.sha1(key.encode()).hexdigest()[:8],
                "title": title, "severity": severity,
                "evidence": evidence, "watches_affected": affected,
            })

        for r in c.execute("SELECT kind, school, COUNT(*) n, SUM(count) hits, "
                           "MAX(severity) sev FROM guardian_incidents "
                           "GROUP BY kind, school HAVING SUM(count) >= 3"):
            add(f"inc:{r['kind']}:{r['school']}",
                f"Recurring {r['kind']} at {r['school'] or 'system level'} "
                f"({r['hits']} occurrences) — eliminate the class, not the instance",
                r["sev"] or "yellow",
                f"{r['hits']} recorded occurrences across {r['n']} incident row(s)",
                _watches_at(c, r["school"]))
        for r in c.execute("SELECT school, consec_fail, failures, checks FROM "
                           "guardian_adapter_health WHERE consec_fail >= 3 OR "
                           "(checks >= 20 AND failures*4 >= checks)"):
            add(f"adapter:{r['school']}",
                f"Adapter {r['school']}: {r['failures']}/{r['checks']} recent failures "
                f"(streak {r['consec_fail']}) — harden or replace",
                "red" if r["consec_fail"] >= 5 else "yellow",
                f"adapter health window: {r['failures']} fail / {r['checks']} checks",
                _watches_at(c, r["school"]))
        n_empty = c.execute("SELECT COUNT(*) FROM watches WHERE term=''").fetchone()[0]
        if n_empty:
            add("empty-term",
                f"{n_empty} active watch(es) carry an empty term stamp — extend term "
                "stamping/current-term to the non-.term adapter families; removes the "
                "false-alert-after-roll class entirely",
                "yellow", f"SELECT COUNT(*) FROM watches WHERE term='' -> {n_empty}", n_empty)
        n_ntfy = c.execute("SELECT COUNT(DISTINCT w.id) FROM watches w LEFT JOIN "
                           "push_subs p ON p.user_id=w.user_id WHERE p.id IS NULL "
                           "AND w.user_id IS NOT NULL").fetchone()[0]
        if n_ntfy:
            add("no-push",
                f"{n_ntfy} watch(es) belong to accounts with NO push subscription — "
                "delivery rests on ntfy/email; drive push enrollment",
                "yellow", f"push_subs join -> {n_ntfy} uncovered watches", n_ntfy)
        cutoff = time.strftime("%Y-%m-%d", time.localtime(_now() - 7 * 86400))
        for r in c.execute("SELECT binding, COUNT(*) n FROM guardian_confidence "
                           "WHERE entity_type='system' AND date >= ? "
                           "GROUP BY binding ORDER BY n DESC LIMIT 1", (cutoff,)):
            if r["binding"]:
                add(f"binding:{r['binding']}",
                    f"System confidence was bound by '{r['binding']}' on {r['n']} of the "
                    "last 7 days — the highest-leverage reliability investment",
                    "info", f"guardian_confidence 7-day binding histogram", 0)
        items.sort(key=lambda i: (_SEV_RANK.get(i["severity"], 2),
                                  -i["watches_affected"]))
        return items[:20]
    except Exception as e:
        _telemetry_mark(f"backlog:{type(e).__name__}")
        return []
    finally:
        if conn is not None:
            try:
                conn.close()
            except Exception:
                pass


def _watches_at(c, school):
    if not school:
        return 0
    return c.execute("SELECT COUNT(*) FROM watches WHERE school=?", (school,)).fetchone()[0]
