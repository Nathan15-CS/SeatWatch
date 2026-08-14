"""READINESS #27 — the accuracy gate must judge status-only schools, not skip them.

72 schools (7.8% of the fleet: CUNY, Fose, VCCS, VSB) publish an authoritative open/closed
status and NO seat counts, so `seats=None` is the correct and only possible answer for
them. ops/gate.py once treated a non-int seat count as a parse failure, which meant one
condition produced three separate failures — "seats not an int", "no OPEN found", "no FULL
found" — and those schools could never pass however healthy they actually were.

The fix scores them on what they DO expose, the open/full mix, which is the same disproof
a seat-count school gives. The risk in that fix is obvious and is the real subject of this
file: if "no seat count" becomes an excuse, a school that reports counts for SOME rows and
not others — a genuine parse failure, and the more dangerous kind, because the rows it
silently dropped are sections a student can never be alerted about — would sail through.

So both directions are asserted here, with no network:

  ALL rows status-only  -> PASSES  (scored on the open/full mix, not punished for None)
  SOME rows status-only -> FAILS   (a mixed response means the parse broke on those rows)
  ALL rows with counts  -> PASSES  (the ordinary case still works)

Driven through the REAL ops/gate.py gate(), not a copy of its logic.
"""
import importlib.util
import os
import sys


def _load_gate():
    """Import ops/gate.py by path — it is a script, not an importable module."""
    root = os.path.expanduser("~/seatwatch")
    sys.path.insert(0, root)
    sys.path.insert(0, os.path.join(root, "ops"))
    spec = importlib.util.spec_from_file_location("gatemod", os.path.join(root, "ops", "gate.py"))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


class FakeAdapter:
    """No network. `mode` decides only what the seats field looks like."""
    host = "synthetic.invalid"

    def __init__(self, name, mode):
        self.name, self.mode, self.example = name, mode, "CS 101"

    def fetch(self, codes):
        if not codes or codes[0] != self.example:
            return {}                      # probe walks a list; answer only our own code
        c = codes[0]
        if self.mode == "status_only":     # authoritative open/closed, no counts anywhere
            return {c: {"0101": {"open": True,  "seats": None},
                        "0102": {"open": False, "seats": None},
                        "0103": {"open": False, "seats": None}}}
        if self.mode == "mixed":           # counts on some rows only — a REAL parse failure
            return {c: {"0101": {"open": True,  "seats": 3},
                        "0102": {"open": False, "seats": None},
                        "0103": {"open": False, "seats": 0}}}
        return {c: {"0101": {"open": True,  "seats": 3},
                    "0102": {"open": False, "seats": 0}}}


def run():
    g = _load_gate()
    results = []
    def check(n, c, d=""): results.append((n, bool(c), d))

    def verdict(mode):
        S = {"synth": FakeAdapter("Synthetic U", mode)}
        _sid, _name, ok, notes = g.gate("synth", S)
        return ok, " | ".join(notes)

    ok, notes = verdict("status_only")
    check("a status-only school PASSES the gate", ok,
          f"notes: {notes[:150]} — 72 schools could otherwise never pass, however healthy")
    check("...and is explicitly scored on its open/full mix",
          "status-only" in notes and "open/full mix" in notes,
          f"notes: {notes[:150]} — a silent pass is indistinguishable from a skipped check")

    ok, notes = verdict("mixed")
    check("a MIXED response still FAILS", not ok,
          "counts on some rows and not others is a parse failure, and the rows it dropped "
          "are sections a student can never be alerted about")
    check("...and says which rows broke", "MIXED" in notes or "not an int" in notes,
          f"notes: {notes[:150]}")

    ok, notes = verdict("counts")
    check("an ordinary seat-count school still PASSES", ok, f"notes: {notes[:150]}")

    p = sum(x for _, x, _ in results)
    f = sum(not x for _, x, _ in results)
    return p, f, results


if __name__ == "__main__":
    p, f, res = run()
    for n, ok, d in res:
        print(f"  [{'PASS' if ok else '*** FAIL'}] {n}{('  ' + d) if d and not ok else ''}")
    print(f"\n  {p} passed, {f} failed")
    sys.exit(1 if f else 0)
