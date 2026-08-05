"""READINESS #23 — term auto-roll may never move a school onto a dead term.

Auto-roll is what carries ~651 pinned schools from Fall 2026 to Spring 2027. It was
disarmed all year with a blunt warning in the production log ("a roll against a stale watch
stamp silently kills watches"), so before arming it the guards have to be demonstrated, not
read.

Spring 2027 makes this urgent AND dangerous in the same breath: several schools already
list the term while marking it "View Only" with zero sections behind it. A roll onto one of
those points every student at that school at nothing, and the failure is silent — watches
simply never fire again.

What is pinned here:
  DEAD TERM     a detected term that returns no data is REJECTED, keeping last-known-good
  LIVE TERM     a detected term that returns real sections IS adopted
  BACKWARD      a term earlier than the current one is never adopted
  OPT-OUT       auto_term = False (parallel same-season terms) is honoured absolutely
  NO CANDIDATE  resolve_term returning None changes nothing
Every case asserts on the school's term AFTER the attempt, because a guard that logs a
refusal while still mutating the term would look identical in the logs and be catastrophic.
"""
import os
import sys
import tempfile
import warnings

warnings.filterwarnings("ignore")


def run():
    os.environ.setdefault("SEATWATCH_DB", os.path.join(tempfile.mkdtemp(), "roll2.db"))
    sys.path.insert(0, os.path.expanduser("~/seatwatch"))
    import schools

    results = []
    def check(n, c, d=""): results.append((n, bool(c), d))

    class Fake(schools.Banner):
        """A Banner school whose network is entirely under this test's control."""
        id = "faketest"; name = "Fake University"
        example = "ENG 101"; term = "202608"        # Fall 2026, last-known-good
        host = "example.invalid"; base_path = "X"
        _candidate = None
        _live_terms = ()                            # terms that return real sections

        def resolve_term(self):
            return self._candidate

        def fetch(self, courses, *a, **k):
            if self.cur_term() in self._live_terms:
                return {c: {"001": {"open": True, "seats": 3}} for c in courses}
            return {}                               # dead term: nothing comes back

    # ------------------------------------------------------- dead term rejected
    s = Fake()
    s._active_term = None
    s._candidate = "202701"                          # Spring 2027, published but empty
    s._live_terms = ("202608",)                      # only Fall has data
    s.refresh_term()
    check("a detected term with NO data is REJECTED", s.cur_term() == "202608",
          f"school moved to {s.cur_term()} — every student there would watch nothing")
    check("...and the school keeps its last-known-good term", s.cur_term() == "202608")

    # -------------------------------------------------------- live term adopted
    s2 = Fake()
    s2._active_term = None
    s2._candidate = "202701"
    s2._live_terms = ("202608", "202701")            # Spring now has real sections
    s2.refresh_term()
    check("a detected term WITH data IS adopted", s2.cur_term() == "202701",
          "otherwise no school ever reaches Spring 2027")

    # ----------------------------------------------------------------- backward
    # Exercised through the REAL picker, not through a stubbed resolve_term. The backward
    # guard lives in _pick_current_term because it compares parsed season+year; term CODES
    # are not comparable across schools ("202608", "2267", "26/FA*1" are all Fall 2026), so
    # a lexical check bolted onto refresh_term would look safer and quietly break the odd
    # formats. Testing the stub instead of the picker is what made this look broken.
    import datetime as _dt
    back = [{"code": "202608", "description": "Fall 2026"},
            {"code": "202701", "description": "Spring 2027"}]
    got = schools._pick_current_term(back, today=_dt.date(2026, 11, 5), cur="202701")
    check("a BACKWARD term is refused by the picker even though it has data",
          got != "202608",
          f"picked {got} — walking a school back a semester strands everyone on the new one")

    # ------------------------------------------------------------------ opt-out
    s4 = Fake()
    s4.auto_term = False                             # parallel same-season terms
    s4._active_term = None
    s4._candidate = "202701"
    s4._live_terms = ("202608", "202701")
    s4.refresh_term()
    check("auto_term=False is honoured absolutely", s4.cur_term() == "202608",
          "these schools run parallel terms the picker cannot tell apart")

    # ------------------------------------------------------------ no candidate
    s5 = Fake()
    s5._active_term = None
    s5._candidate = None                             # term list unreadable
    s5._live_terms = ("202608",)
    s5.refresh_term()
    check("an unreadable term list changes nothing", s5.cur_term() == "202608",
          "a network blip must never be able to move a school")

    # --------------------------------------------------- the real picker's bias
    # The guard that matters most in August: the CURRENT term must keep winning while it
    # is still in season, or arming auto-roll today would hand every school to Spring and
    # kill Fall add/drop — the busiest seat-watching week of the year.
    import datetime
    aug = datetime.date(2026, 8, 5)
    terms = [{"code": "202608", "description": "Fall 2026"},
             {"code": "202701", "description": "Spring 2027"}]
    pick_aug = schools._pick_current_term(terms, today=aug, cur="202608")
    check("in August the picker KEEPS Fall 2026", pick_aug == "202608",
          f"picked {pick_aug} — arming auto-roll would strand Fall watchers")
    nov = datetime.date(2026, 11, 5)
    pick_nov = schools._pick_current_term(terms, today=nov, cur="202608")
    check("by November it moves to Spring 2027", pick_nov == "202701",
          f"picked {pick_nov} — schools would never reach Spring")

    p = sum(ok for _, ok, _ in results)
    f = sum(not ok for _, ok, _ in results)
    return p, f, results


if __name__ == "__main__":
    p, f, res = run()
    for n, ok, d in res:
        print(f"  [{'PASS' if ok else '*** FAIL'}] {n}{('  ' + d) if d and not ok else ''}")
    print(f"\n  {p} passed, {f} failed")
    sys.exit(1 if f else 0)
