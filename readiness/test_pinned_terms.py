"""READINESS #7 — Pinned-term schools must still serve live data (dead-listing guard).

Most schools auto-roll their term. A minority are PINNED (auto_term=False) because their
host exposes a trap the picker would fall into — a View-Only future term, a med-school or
"Extension" sub-population, a quarter calendar. Pinning is correct, but it cannot self-heal:
at semester rollover a pinned school keeps asking for a term that has ENDED and silently
returns nothing forever.

The runtime health guard does NOT cover this: it only alarms for courses a user is actively
watching, so a school with no watchers can go dead unnoticed. That is exactly how a listed
school becomes a lie (the reason Princeton was removed).

This checks every pinned school still returns sections for its example course. It hits the
real hosts, so it is the slowest suite — but it is the only thing standing between a
rollover and a silently dead school.
"""
import os, sys, concurrent.futures as cf


def run():
    sys.path.insert(0, os.path.expanduser("~/seatwatch"))
    import schools
    S = schools.SCHOOLS
    pinned = [s for s in S.values() if getattr(s, "auto_term", True) is False]
    results = []

    def check(s):
        try:
            r = {k: v for k, v in s.fetch([s.example]).get(s.example, {}).items() if k != "none"}
            return (s.name, len(r), None)
        except Exception as e:
            return (s.name, 0, f"{type(e).__name__}")

    with cf.ThreadPoolExecutor(7) as ex:
        rows = sorted(ex.map(check, pinned))

    for name, n, err in rows:
        detail = f"({err})" if err else "(0 sections — term likely rolled past its pin)"
        results.append((f"pinned school still live: {name[:38]}", n > 0, detail))

    # A pinned school is a standing maintenance obligation; make the count visible so it
    # can't quietly grow without anyone owning the bumps.
    results.append((f"pinned-school count is tracked ({len(pinned)} need manual term bumps)",
                    True, ""))

    p = sum(ok for _, ok, _ in results)
    f = sum(not ok for _, ok, _ in results)
    return p, f, results


if __name__ == "__main__":
    import warnings; warnings.filterwarnings("ignore")
    p, f, res = run()
    for name, ok, detail in res:
        print(f"  [{'PASS' if ok else '*** FAIL'}] {name}{('  ' + detail) if detail and not ok else ''}")
    print(f"\n  {p} passed, {f} failed")
    sys.exit(1 if f else 0)
