#!/usr/bin/env python3
"""Gate a candidate newer-Colleague host THROUGH THE PRODUCTION adapter (schools.NewColleague.fetch).
Usage: python3 gate_colleague.py <host> <course1> [course2 ...] [--yearspan]
Reports the live open/full mix. Disproof for this family (per adapter docstring): current-term FULL
sections must carry status != 0 (fetch encodes that as open=False AND seats==0). A healthy live MIX
(some open, some full) through the production path is the ship bar.
"""
import sys
sys.path.insert(0, "/Users/nathananapolsky/seatwatch")
import schools

def main():
    args = [a for a in sys.argv[1:] if a != "--yearspan"]
    yearspan = "--yearspan" in sys.argv
    host, courses = args[0], args[1:]
    base = schools.YearSpanNewColleague if yearspan else schools.NewColleague
    cls = type("Probe", (base,), {"id": "probe", "name": "Probe",
                                  "example": courses[0], "host": host})
    ad = cls()
    print(f"# host={host} base={base.__name__} courses={courses}")
    total = openn = full = 0
    for c in courses:
        r = ad.fetch({c}).get(c)
        if not r:
            print(f"  {c:12s} -> no data")
            continue
        o = sum(1 for v in r.values() if v["open"])
        f = sum(1 for v in r.values() if not v["open"])
        total += len(r); openn += o; full += f
        seats = [v["seats"] for v in list(r.values())[:10]]
        print(f"  {c:12s} {len(r):3d} sec  {o} open {f} full  seats={seats}")
    print(f"  LIVE-TERM RESULT: {total} sections; {openn} open / {full} FULL")
    print("  DISPROOF:", "PASS (real full sections in live term)" if full > 0
          else "SUSPECT (all-open — do not ship)")

if __name__ == "__main__":
    main()
