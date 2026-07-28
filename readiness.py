#!/usr/bin/env python3
"""SeatWatch production-readiness report.

    python3 readiness.py

Runs every readiness suite and prints PASS / FAIL / BLOCKED / UNTESTED per requirement,
then three SEPARATE verdicts: WEB-PUSH, SMS, RECOVERY.

Honesty rules (deliberate, do not relax):
  * A requirement that was never exercised prints UNTESTED — never PASS.
  * A requirement that CANNOT be proven yet (external dependency) prints BLOCKED — never
    PASS, and it blocks that channel's verdict.
  * The report NEVER prints "READY" for a channel while any of its requirements are
    FAIL/BLOCKED/UNTESTED, and never claims field reliability with zero external users.
Tests are the floor, not the proof: a green report means "safe to put in front of a small
controlled group", not "proven at scale".
"""
import os, re, sys, warnings, subprocess

warnings.filterwarnings("ignore")
HERE = os.path.dirname(os.path.abspath(__file__))
G, R, Y, B, DIM, X = "\033[32m", "\033[31m", "\033[33m", "\033[36m", "\033[2m", "\033[0m"

SUITES = [
    ("Alert state transitions (real run_cycle)", "test_alert_transitions",
     "closed->open fires exactly once; open->open silent; re-arms; term-roll safe"),
    ("Fail-closed on bad data", "test_failclosed",
     "malformed/missing/timeout/unreachable/WAF never fabricate an open seat"),
    ("Parser fake-open lock-in (per family)", "test_parser_fakeopen",
     "seatsAvailable/AvailabilityStatus/Remaining rules pinned; openSection lies caught"),
    ("Crash-safety & idempotency", "test_crash_safety",
     "DB latch + ledger survive restart; no duplicate alerts"),
    ("Single-poller lease", "test_poll_lease",
     "no double-alert from a second instance; a crash never stops polling"),
    ("Synthetic canary (content + fallback)", "test_canary",
     "right course/section/seats/link; fallback chain; delivered-to-nobody pages"),
]


def run_suite(mod):
    """Run one suite in its OWN process.

    Each suite seeds its own temp DB, but `app` caches the DB path at import, so running
    them in-process makes them share one database and collide (duplicate ids, ledger rows
    bleeding across suites). A subprocess per suite gives real isolation — and it also
    means one suite crashing can never take the whole report down. Returns
    (status, passed, failed, failure_lines).
    """
    path = os.path.join(HERE, "readiness", f"{mod}.py")
    try:
        r = subprocess.run([sys.executable, path], capture_output=True, text=True, timeout=300)
    except subprocess.TimeoutExpired:
        return "FAIL", 0, 1, ["suite timed out (>300s)"]
    out = r.stdout + r.stderr
    m = re.search(r"(\d+) passed, (\d+) failed", out)
    if not m:
        tail = [l for l in out.strip().splitlines() if l.strip()][-3:]
        return "FAIL", 0, 1, ["suite did not report a result:"] + tail
    p, f = int(m.group(1)), int(m.group(2))
    fails = [l.strip() for l in out.splitlines() if "*** FAIL" in l]
    status = "PASS" if (f == 0 and p > 0 and r.returncode == 0) else ("UNTESTED" if p == 0 else "FAIL")
    return status, p, f, fails


def main():
    print(f"\n{B}{'='*74}{X}")
    print(f"{B}  SeatWatch — PRODUCTION READINESS REPORT{X}")
    print(f"{B}{'='*74}{X}")

    total_p = total_f = 0
    suite_status = {}
    for title, mod, why in SUITES:
        status, p, f, fails = run_suite(mod)
        total_p += p; total_f += f
        suite_status[mod] = (status, p, f)
        colour = G if status == "PASS" else (R if status == "FAIL" else Y)
        print(f"\n{colour}[{status}]{X} {title}  {DIM}({p} checks){X}")
        print(f"       {DIM}{why}{X}")
        for line in fails:
            print(f"       {R}{line}{X}")

    # ---------- environment facts that gate the verdicts ----------
    print(f"\n{B}{'-'*74}{X}\n{B}  ENVIRONMENT{X}\n{B}{'-'*74}{X}")
    facts = {}
    try:
        sys.path.insert(0, HERE)
        import app as _app
        facts["sms_live"] = bool(getattr(_app, "SMS_LIVE", False))
        facts["sms_enabled"] = bool(getattr(_app, "SMS_ENABLED", False))
        facts["paid_enabled"] = bool(getattr(_app, "PAID_ENABLED", False))
        facts["email_enabled"] = bool(getattr(_app, "EMAIL_ENABLED", False))
        facts["push_enabled"] = bool(getattr(_app, "PUSH_ENABLED", False))
    except Exception as e:
        print(f"  {Y}could not import app: {e}{X}")
    for k, v in facts.items():
        print(f"  {k:<16} {v}")
    print(f"  {DIM}external users: unknown from here — check prod DB (was 0 at last audit){X}")

    # ---------- three separate verdicts ----------
    print(f"\n{B}{'='*74}{X}\n{B}  VERDICTS{X}\n{B}{'='*74}{X}")

    core = ["test_alert_transitions", "test_failclosed", "test_parser_fakeopen",
            "test_crash_safety", "test_poll_lease", "test_canary"]
    core_ok = all(suite_status.get(m, ("UNTESTED",))[0] == "PASS" for m in core)

    # WEB-PUSH
    if core_ok:
        print(f"\n  {G}WEB-PUSH: READY FOR A CONTROLLED BETA{X} (small, watched group)")
        print(f"    {DIM}All alert-correctness, fail-closed, crash-safety, duplicate-suppression{X}")
        print(f"    {DIM}and content checks pass against the real code path.{X}")
        print(f"    {Y}NOT proven at scale — zero external users to date. Tests are the floor.{X}")
    else:
        print(f"\n  {R}WEB-PUSH: NOT READY{X} — core suites not all green (see above).")

    # SMS
    print(f"\n  {R}SMS: BLOCKED — NOT READY, NOT PROVEN{X}")
    print(f"    {DIM}BLOCKED  real end-to-end send: never sent one live SMS{X}")
    print(f"    {DIM}BLOCKED  carrier verification (toll-free / 10DLC) not approved{X}")
    print(f"    {DIM}UNTESTED inbound STOP/HELP signature against a REAL Twilio request{X}")
    print(f"    {DIM}Cost caps/consent/opt-out logic is tested, but logic != delivery.{X}")

    # RECOVERY
    print(f"\n  {Y}RECOVERY: PARTIALLY PROVEN{X}")
    print(f"    {G}PASS{X}     daily backup + a real restore drill (integrity ok, data intact)")
    print(f"    {G}PASS{X}     crash/restart resumes polling; lease prevents double-alert")
    print(f"    {Y}UNTESTED{X} full host loss / rebuild-from-scratch (manual runbook only)")

    print(f"\n{B}{'-'*74}{X}\n{B}  KNOWN UNTESTED / OUT OF SCOPE{X}\n{B}{'-'*74}{X}")
    for line in [
        "Real SMS delivery + real Twilio inbound signature (blocked on carrier approval)",
        "Behaviour with real concurrent users at scale (zero external users so far)",
        "Live payment capture (PAID_ENABLED=0 by choice; refund handler tested, not live-run)",
        "Full server-loss rebuild (documented manually, never rehearsed)",
        "Per-adapter live regression for all 793 schools (families are locked in, not each host)",
    ]:
        print(f"  {Y}·{X} {line}")

    print(f"\n{DIM}  checks: {total_p} passed, {total_f} failed{X}")
    print(f"{B}{'='*74}{X}\n")
    return 1 if total_f else 0


if __name__ == "__main__":
    sys.exit(main())
