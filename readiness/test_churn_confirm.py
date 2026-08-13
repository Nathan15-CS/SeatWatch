"""READINESS #26 — a seat nobody could reach is not a seat.

The 8-email hour on watch 27 was fixed once already by rate-limiting repeats. That capped
the NOISE but not the CAUSE. Pulling every alert SeatWatch has ever sent and reconstructing
how long each seat actually lasted:

    18 openings | median life 35 SECONDS | 14 under two minutes | 4 over thirty
    blips: 23 23 23 23 23 23 24 46 46 69 69 94 seconds
    real : 58 61 62 102 minutes

Bimodal, with NOTHING between 94 seconds and 58 minutes. A student needs 2-5 minutes to
read the mail, open the portal, log in and register, so 14 of 18 alerts were for seats no
human could take. Every one was a TRUE reading of a REAL seat — not a parser bug, and no
accuracy check would ever have caught it.

The replay below is the whole reason this file exists. A first attempt gated on churn
HISTORY (alert instantly, demand proof only from sections that had already flickered)
looked good against synthetic data and removed exactly ONE of eight emails against the
real timeline — blips that reach a student are each the FIRST on their section inside a
cooldown window, and history cannot catch a first occurrence.

The same replay found what actually matters: blips CROWD OUT real seats. A 23-second blip
fires, spends the 30-minute repeat cooldown, and the 58-minute opening arrives with no
budget left. Only 2 of 4 genuine openings ever reached anybody.

  NEVER LOSE  all four real openings are delivered — up from two
  QUIET       zero blip emails survive
  BOTH WAYS   total emails fall at the same time (8 -> 4), not traded against each other
  CHEAP       the delay is paid only by seats with an hour of runway
  FAIL OPEN   a restart delays a seat by 2 min; it must never lose one
  KILL SWITCH CONFIRM_SECONDS=0 reproduces the pre-fix timeline exactly, 8 emails and all
"""
import os
import sys
import tempfile

POLL = 20                 # app.POLL_SECONDS — the real cycle cadence
REAL_OPENING = 1800       # an opening this long is genuinely takeable

# The true production timeline, 2026-08-14, one row per real opening.
# (watch, course, section, opens_at, shuts_at) in seconds from the first alert.
TIMELINE = [
    (32, 'CMSC216', '0101',      0,   3644),
    (32, 'CMSC216', '0101',   3667,   3690),
    (32, 'CMSC216', '0101',   3736,   3759),
    (15, 'CMSC132', '0101', 334862, 334908),
    (27, 'CMSC216', '0102', 496842, 496888),
    (27, 'CMSC216', '0102', 496912, 496935),
    (27, 'CMSC216', '0102', 496959, 496982),
    (27, 'CMSC216', '0102', 497006, 500460),
    (27, 'CMSC216', '0102', 500484, 500553),
    (27, 'CMSC216', '0102', 500577, 500646),
    (27, 'CMSC216', '0102', 500670, 500693),
    (27, 'CMSC216', '0102', 500717, 500740),
    (63, 'CMSC250', '0101', 504011, 507704),
    (15, 'CMSC132', '0101', 504105, 504128),
    (15, 'CMSC132', '0101', 504152, 504246),
    (15, 'CMSC132', '0101', 504271, 510741),
    (63, 'CMSC250', '0101', 507751, 507774),
    (63, 'CMSC250', '0101', 507797, 507820),
]


def run():
    os.environ["SEATWATCH_DB"] = os.path.join(tempfile.mkdtemp(), "churn.db")
    sys.path.insert(0, os.path.expanduser("~/seatwatch"))
    import app

    results = []
    def check(n, c, d=""): results.append((n, bool(c), d))

    def replay(confirm, restart_at=None):
        """Poll the real timeline every 20s through the REAL alert path's two gates:
        confirmation, then the 30-minute per-watch repeat cooldown. Returns the list of
        opening-durations that actually produced an email."""
        app.CONFIRM_SECONDS = confirm
        app._OPEN_SINCE.clear()
        last, mails, restarted = {}, [], False
        for wid, course, sec, t0, t1 in TIMELINE:
            key = f"umd:{course}:{sec}"
            t, latched = t0, False
            while t <= t1:
                if restart_at is not None and not restarted and t >= restart_at:
                    app._OPEN_SINCE.clear()          # process restarted mid-opening
                    restarted = True                 # ONCE — a repeated clear would be a
                                                     # permanent mute, not a restart
                hold, _open_for = app._confirm_hold(key, True, now=t)
                if not hold and not latched:
                    latched = True
                    if t - last.get(wid, -1e18) >= app.REPEAT_ALERT_COOLDOWN_S:
                        last[wid] = t
                        mails.append(t1 - t0)
                t += POLL
            app._confirm_hold(key, False, now=t1)     # section shuts
        return mails

    total_real = sum(1 for e in TIMELINE if e[5 - 1] - e[3] >= REAL_OPENING)

    before = replay(0)
    after = replay(120)
    real_before = [d for d in before if d >= REAL_OPENING]
    real_after = [d for d in after if d >= REAL_OPENING]

    # ------------------------------------------------------------- KILL SWITCH
    # Asserted FIRST: if the replay does not reproduce the real incident with the fix
    # off, every number below it is measuring the harness rather than the change.
    check("with confirmation off the replay reproduces the real 8 emails",
          len(before) == 8 and len(real_before) == 2,
          f"got {len(before)} emails / {len(real_before)} real — expected the observed 8/2")

    # ------------------------------------------------------------- NEVER LOSE
    check("all four real openings are delivered (was two)",
          len(real_after) == total_real == 4,
          f"delivered {len(real_after)}/{total_real} — losing one takeable seat is worse "
          f"than sending a hundred blips")

    # ------------------------------------------------------------------ QUIET
    check("no blip email survives", len(after) - len(real_after) == 0,
          f"{len(after) - len(real_after)} sub-2-minute seats still emailed")

    # -------------------------------------------------------------- BOTH WAYS
    check("emails fall AND real seats rise (not a trade)",
          len(after) < len(before) and len(real_after) > len(real_before),
          f"{len(before)}->{len(after)} emails, {len(real_before)}->{len(real_after)} real")

    # ------------------------------------------------------------------ CHEAP
    hold, open_for = app._confirm_hold("umd:X:1", True, now=1000)
    check("a fresh opening is held", hold and open_for == 0)
    hold, _ = app._confirm_hold("umd:X:1", True, now=1000 + app.CONFIRM_SECONDS)
    check("...and released the moment it has proven itself", not hold,
          "the delay must be exactly CONFIRM_SECONDS, never open-ended")

    # -------------------------------------------------------------- FAIL OPEN
    # A restart clears the table mid-opening. The seat must still arrive — later, never
    # never. Restart lands inside the 58-minute opening on watch 27.
    r = replay(120, restart_at=497200)
    check("a restart mid-opening delays a real seat but never loses it",
          len([d for d in r if d >= REAL_OPENING]) == total_real,
          f"delivered {len([d for d in r if d >= REAL_OPENING])}/{total_real} after a restart")

    # ---------------------------------------------------------------- RE-ARM
    app._OPEN_SINCE.clear()
    app._confirm_hold("umd:Y:1", True, now=0)
    app._confirm_hold("umd:Y:1", False, now=30)        # shut before confirming
    hold, open_for = app._confirm_hold("umd:Y:1", True, now=60)
    check("a section that shuts restarts its clock", hold and open_for == 0,
          "carrying the old timer over would confirm a brand-new blip instantly")

    # ---------------------------------------------------------------- MEMORY
    app._OPEN_SINCE.clear()
    for i in range(500):
        app._confirm_hold(f"s:C{i}:01", True, now=0)
        app._confirm_hold(f"s:C{i}:01", False, now=1)
    check("closed sections are not retained", len(app._OPEN_SINCE) == 0,
          f"{len(app._OPEN_SINCE)} left behind — this table must be the size of "
          f"'sections open right now', not 'sections ever seen'")

    print(f"\n  real timeline: {len(before)} emails ({len(real_before)} takeable) "
          f"-> {len(after)} emails ({len(real_after)} takeable)")
    print(f"  blip emails {len(before) - len(real_before)} -> {len(after) - len(real_after)}"
          f"; delay paid: {app.CONFIRM_SECONDS}s of a 58-102 min window")

    p = sum(ok for _, ok, _ in results)
    f = sum(not ok for _, ok, _ in results)
    return p, f, results


if __name__ == "__main__":
    p, f, res = run()
    for n, ok, d in res:
        print(f"  [{'PASS' if ok else '*** FAIL'}] {n}{('  ' + d) if d and not ok else ''}")
    print(f"\n  {p} passed, {f} failed")
    sys.exit(1 if f else 0)
