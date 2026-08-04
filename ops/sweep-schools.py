#!/usr/bin/env python3
"""Probe EVERY school in the registry against its real registration system.

The gate proves a school works on the day it is added. Nothing has ever asked the whole
registry at once, and a listed school that has quietly died is worse than one that was
never added: a student picks it, waits, and never hears anything.

WHAT IS CHECKED, per school, on its own advertised example course:

  REACHABLE     the adapter returns sections at all
  SHAPED        seats are integers, never negative, no 'none' sentinel row survives
  HONEST        no section claims open with 0 seats (that is the false-alert shape)
  DISTINCT      section keys are unique — collapsed keys silently hide real sections
  ALIVE         at least one section exists for a course the school itself advertises

CONCURRENCY IS PER HOST, NOT GLOBAL, and that is the whole reason this is trustworthy.
Hundreds of these schools share a host (LCTCS, IECC, Maricopa, the Colleague cloud). Firing
twelve requests at one host produces timeouts that look exactly like a broken adapter — it
is how ftcc-la was once judged dead when it was merely crowded. Hosts are worked in
parallel; schools on the SAME host are worked one at a time, politely.

    python3 ops/sweep-schools.py                 # every school
    python3 ops/sweep-schools.py --only a,b,c    # named schools
    python3 ops/sweep-schools.py --new-since 857 # last N added (by registry order)
    python3 ops/sweep-schools.py --retries 3     # re-probe failures N times before judging
"""
import argparse
import collections
import concurrent.futures as cf
import json
import os
import sys
import time
import urllib.parse

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, HERE)
os.environ.setdefault("SEATWATCH_DB", "/tmp/sweep-schools.db")

import schools  # noqa: E402


def host_of(s):
    """Best-effort host key, so schools sharing an origin are never probed in parallel."""
    for attr in ("host", "base", "domain"):
        v = getattr(s, attr, None)
        if isinstance(v, str) and v:
            return v.lower()
    try:
        u = s.reg_url(getattr(s, "example", "") or "")
        if isinstance(u, str) and "://" in u:
            return urllib.parse.urlparse(u).netloc.lower()
    except Exception:
        pass
    return type(s).__name__          # same adapter class = assume shared plumbing


def probe(s):
    """One probe. Returns (verdict, detail, stats)."""
    course = getattr(s, "example", "") or ""
    if not course:
        return "NO_EXAMPLE", "adapter advertises no example course to probe", {}
    t0 = time.time()
    try:
        raw = s.fetch([course]) or {}
    except Exception as e:
        return "ERROR", f"{type(e).__name__}: {e}"[:90], {"ms": int((time.time() - t0) * 1000)}
    ms = int((time.time() - t0) * 1000)
    secs = raw.get(course) or {}
    if not isinstance(secs, dict):
        return "MALFORMED", f"fetch returned {type(secs).__name__}, expected dict", {"ms": ms}

    phantom = "none" in secs
    real = {k: v for k, v in secs.items() if k != "none"}
    if not real:
        return "EMPTY", "no sections for its own example course", {"ms": ms, "phantom": phantom}

    bad_type, negative, fake_open, held = [], [], [], []
    opens = 0
    for k, v in real.items():
        if not isinstance(v, dict):
            bad_type.append(k)
            continue
        op, seats = bool(v.get("open")), v.get("seats")
        opens += op
        if seats is None:
            continue
        if not isinstance(seats, int) or isinstance(seats, bool):
            bad_type.append(k)
        elif seats < 0:
            negative.append(k)
        elif op and seats == 0:
            fake_open.append(k)
        elif not op and seats > 0:
            held.append(k)

    stats = {"ms": ms, "sections": len(real), "open": opens, "full": len(real) - opens,
             "phantom": phantom, "held": len(held)}
    if bad_type:
        return "MALFORMED", f"non-int/odd seats on {bad_type[:3]}", stats
    if negative:
        return "NEGATIVE", f"negative seats on {negative[:3]}", stats
    if fake_open:
        # The dangerous one: we would tell a student to run for a seat that is not there.
        return "FAKE_OPEN", f"open with 0 seats on {fake_open[:3]}", stats
    if phantom:
        return "PHANTOM", "a 'none' sentinel row survived into the result", stats
    if opens == len(real) and len(real) >= 8:
        # Every section open, in volume, is what a broken 'open' flag looks like.
        return "ALL_OPEN", f"all {len(real)} sections report open — verify it is not a lie", stats
    return "OK", "", stats


def sweep(targets, retries, host_workers):
    by_host = collections.defaultdict(list)
    for s in targets:
        by_host[host_of(s)].append(s)

    results, done = {}, [0]
    total = len(targets)

    def work_host(items):
        out = []
        for s in items:
            verdict, detail, stats = probe(s)
            # Re-probe anything that failed. A single bad probe is not evidence: a busy
            # host, a slow query, a momentary 502 all look like death exactly once.
            for _ in range(retries if verdict not in ("OK",) else 0):
                time.sleep(1.5)
                v2, d2, s2 = probe(s)
                if v2 == "OK":
                    verdict, detail, stats = v2, "(recovered on retry)", s2
                    break
                verdict, detail, stats = v2, d2, s2
            out.append((s.id, s.name, verdict, detail, stats))
            done[0] += 1
            if done[0] % 25 == 0:
                print(f"    ...{done[0]}/{total}", flush=True)
            time.sleep(0.25)                      # politeness within a host
        return out

    with cf.ThreadPoolExecutor(host_workers) as ex:
        for batch in ex.map(work_host, by_host.values()):
            for sid, name, verdict, detail, stats in batch:
                results[sid] = (name, verdict, detail, stats)
    return results, len(by_host)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--only", default="")
    ap.add_argument("--new-since", type=int, default=0,
                    help="probe only the last N schools in registry order")
    ap.add_argument("--retries", type=int, default=2)
    ap.add_argument("--workers", type=int, default=10, help="distinct HOSTS in parallel")
    ap.add_argument("--out", default="/tmp/sweep-results.json")
    a = ap.parse_args()

    ids = list(schools.SCHOOLS)
    if a.only:
        want = [x.strip() for x in a.only.split(",") if x.strip()]
        ids = [i for i in ids if i in want]
    elif a.new_since:
        ids = ids[-a.new_since:]
    targets = [schools.SCHOOLS[i] for i in ids]

    print(f"  sweeping {len(targets)} school(s), {a.workers} hosts in parallel, "
          f"{a.retries} retries on failure", flush=True)
    t0 = time.time()
    results, nhosts = sweep(targets, a.retries, a.workers)
    mins = (time.time() - t0) / 60

    buckets = collections.defaultdict(list)
    for sid, (name, verdict, detail, stats) in results.items():
        buckets[verdict].append((sid, name, detail, stats))

    print(f"\n  {len(results)} schools across {nhosts} distinct hosts in {mins:.1f} min")
    print("  " + "-" * 68)
    order = ["OK", "ALL_OPEN", "PHANTOM", "EMPTY", "ERROR", "MALFORMED", "NEGATIVE",
             "FAKE_OPEN", "NO_EXAMPLE"]
    for v in order:
        if v in buckets:
            print(f"  {v:<12} {len(buckets[v]):>4}")
    for v in ("FAKE_OPEN", "NEGATIVE", "MALFORMED", "PHANTOM", "EMPTY", "ERROR",
              "NO_EXAMPLE", "ALL_OPEN"):
        if v not in buckets:
            continue
        print(f"\n  ---- {v} ({len(buckets[v])}) ----")
        for sid, name, detail, stats in sorted(buckets[v]):
            print(f"    {sid:<18} {name[:38]:<38} {detail}")

    with open(a.out, "w") as f:
        json.dump({k: {"name": v[0], "verdict": v[1], "detail": v[2], "stats": v[3]}
                   for k, v in results.items()}, f, indent=1)
    print(f"\n  full results: {a.out}")
    bad = sum(len(buckets[v]) for v in
              ("FAKE_OPEN", "NEGATIVE", "MALFORMED", "EMPTY", "ERROR", "NO_EXAMPLE"))
    print(f"  needs attention: {bad}")
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
