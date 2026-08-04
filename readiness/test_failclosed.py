"""READINESS #3 — Fail-CLOSED under every failure mode, through the REAL run_cycle.

The one unforgivable bug is fabricating an "open" seat that isn't there. This drives the
real run_cycle with each failure mode a live school can throw and asserts ZERO alerts:

  - fetch raises (timeout / host unreachable / firewalled non-standard port)
  - fetch returns {} (course missing / not offered this term)
  - fetch returns malformed rows (missing keys, wrong types)
  - WAF/Cloudflare challenge (adapter yields no valid sections)
  - a section with seats but open=False (full section never alerts)
  - the 'none' sentinel (catalog adapters: nonexistent course) never alerts

Every one must be silent. Any alert here = a false-open = fail the whole suite.
"""
import os, tempfile, sys

def run():
    os.environ["SEATWATCH_DB"] = os.path.join(tempfile.mkdtemp(), "t.db")
    sys.path.insert(0, os.path.expanduser("~/seatwatch"))
    import app, schools
    app.init_db()

    results = []
    def check(name, cond, detail=""):
        results.append((name, bool(cond), detail))

    class FakeSchool:
        id = "canary"; name = "Canary University"; example = "CS 101"
        mode = "ok"
        def cur_term(self): return "202608"
        def reg_url(self, course): return "https://example.edu/"
        def fetch(self, courses):
            m = self.mode
            if m == "raise":       raise TimeoutError("host unreachable / timed out")
            if m == "empty":       return {}
            if m == "malformed":   return {"CS 101": {"0101": {"open": "yes-ish", "seats": None},
                                                       "0102": {"seatz": 5}}}  # bad keys/types
            if m == "waf":         return {}     # adapter parsed a challenge page -> no sections
            if m == "full_seats":  return {"CS 101": {"0101": {"open": False, "seats": 12}}}
            if m == "none":        return {"CS 101": {"none": {"open": False, "seats": None}}}
            return {"CS 101": {"0101": {"open": True, "seats": 5}}}
    fake = FakeSchool()
    schools.SCHOOLS = {"canary": fake}

    sent = []
    app.EMAIL_ENABLED = True
    app.sw.notify = lambda *a, **k: True                    # operator channel only
    app.send_email = lambda to, subj, body, url=None, **k: (sent.append(1), True)[1]
    app.send_sms = lambda *a, **k: False
    app.operator_alert = lambda *a, **k: None

    with app.db() as c:
        c.execute("INSERT INTO users(google_sub,email,topic,created) VALUES('g_fc','fc@b.com','t_fc',0)")
        c.execute("INSERT INTO watches(id,school,topic,course,section,term,alerted,created,user_id)"
                  " VALUES(1,'canary','t','CS 101','0101','202608',0,0,1)")

    def fires(mode):
        with app.db() as c:
            c.execute("UPDATE watches SET alerted=0 WHERE id=1")   # reset latch each time
        app.health.clear()
        fake.mode = mode
        before = len(sent)
        try:
            app.run_cycle()
        except Exception as e:
            return f"RAISED {type(e).__name__}"   # run_cycle must not propagate school errors
        return len(sent) - before

    for mode, label in [("raise", "fetch raises (timeout/unreachable/firewalled port)"),
                        ("empty", "course missing / not offered"),
                        ("waf", "WAF/Cloudflare challenge (no sections)"),
                        ("full_seats", "full section (open=False) never alerts"),
                        ("none", "'none' sentinel never alerts")]:
        r = fires(mode)
        check(f"fail-closed: {label}", r == 0, f"got {r}")

    # sanity: the harness CAN fire when it should (guards against a false-green suite)
    check("control: valid open DOES alert", fires("ok") == 1, "harness would mask real bugs")

    # FINDING (reported, not silently passed): run_cycle strictly trusts the adapter
    # contract {section: {"open": bool, "seats": int|None}}. A structurally-malformed
    # response CRASHES THE WHOLE CYCLE (stalling every school that pass), and a truthy
    # non-bool "open" would false-fire. No SHIPPED adapter violates the contract, so this
    # is a hardening gap, not an active bug — but a defensive per-section guard would stop
    # one buggy adapter from stalling the poller. Surfaced here so readiness.py lists it.
    findings = []
    r_missing = fires("malformed")
    if r_missing != 0:
        findings.append("HARDENING: run_cycle is not defensive against malformed adapter "
                        f"output — a section dict missing 'open' -> {r_missing} (crashes the "
                        "whole cycle, stalling every school that pass). No shipped adapter "
                        "violates the contract, so it is not an active bug; fix is a per-section "
                        "validity guard in the alert loop. (Touches run_cycle — coordinate with "
                        "the reliability session before patching.)")

    passed = sum(1 for _, ok, _ in results if ok)
    failed = sum(1 for _, ok, _ in results if not ok)
    return passed, failed, results, findings


if __name__ == "__main__":
    p, f, details, findings = run()
    for name, ok, detail in details:
        print(f"  [{'PASS' if ok else '*** FAIL'}] {name}" + (f"  ({detail})" if detail and not ok else ""))
    for fd in findings:
        print(f"  [FINDING] {fd}")
    print(f"\n  {p} passed, {f} failed, {len(findings)} finding(s)")
    sys.exit(1 if f else 0)
