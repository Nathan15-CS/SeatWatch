#!/usr/bin/env python3
"""Live fleet health sweep — hits every school's real host, one example course each.

WHY: readiness covers adapter FAMILIES and samples ~38 hosts. 831 schools are in the
registry and most are never fetched in production, because only the handful with watches
get polled. So a dead adapter on school #500 is invisible until a student signs up for it
and silently receives nothing. That is the failure this finds.

WHAT IT CHECKS, per school:
  reachable      the adapter returned anything at all
  sections       how many sections came back for the example course
  mixed          both a genuinely open and a genuinely full section (real seat data,
                 not a fake-open default)
  collapse       distinct section keys == sections returned (the UH/UNF silent-miss class)
  open_no_seats  a section marked open with 0 seats -> would fire a FALSE ALERT
  latency

POLITENESS: one request per host, bounded concurrency, and it is read-only. Each host sees
a single course lookup, which is less than one student browsing.

USAGE:  python3 ops/fleet-health.py [--limit N] [--workers N] [--out FILE]
"""
import argparse, json, sys, time
from concurrent.futures import ThreadPoolExecutor, as_completed

sys.path.insert(0, __file__.rsplit("/ops/", 1)[0])
import schools


def probe(sid):
    s = schools.SCHOOLS[sid]
    ex = getattr(s, "example", None)
    r = {"id": sid, "name": getattr(s, "name", sid), "adapter": type(s).__name__,
         "example": ex, "ok": False, "sections": 0, "mixed": False, "collapse": False,
         "open_no_seats": 0, "ms": 0, "err": ""}
    if not ex:
        r["err"] = "no example course"
        return r
    t0 = time.time()
    try:
        d = s.fetch([ex])
    except Exception as e:
        r["err"] = "%s: %s" % (type(e).__name__, str(e)[:70])
        r["ms"] = int((time.time() - t0) * 1000)
        return r
    r["ms"] = int((time.time() - t0) * 1000)
    secs = d.get(ex) or (list(d.values())[0] if d else {})
    if not secs:
        r["err"] = "no sections returned"
        return r
    r["ok"] = True
    r["sections"] = len(secs)
    opens = [k for k, v in secs.items() if v.get("open")]
    r["mixed"] = bool(opens) and len(opens) < len(secs)
    r["collapse"] = len(set(secs.keys())) != len(secs)
    # a section reported OPEN while showing zero seats would send a student to a full class
    r["open_no_seats"] = sum(1 for k, v in secs.items()
                             if v.get("open") and (v.get("seats") is not None and v["seats"] <= 0))
    return r


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--limit", type=int, default=0)
    ap.add_argument("--workers", type=int, default=6)
    ap.add_argument("--out", default="/tmp/fleet-health.json")
    a = ap.parse_args()

    ids = list(schools.SCHOOLS)
    if a.limit:
        ids = ids[:a.limit]
    print("sweeping %d schools with %d workers" % (len(ids), a.workers), flush=True)

    out, done = [], 0
    with ThreadPoolExecutor(max_workers=a.workers) as ex:
        futs = {ex.submit(probe, i): i for i in ids}
        for f in as_completed(futs):
            try:
                out.append(f.result())
            except Exception as e:
                out.append({"id": futs[f], "ok": False, "err": "probe crashed: %s" % e})
            done += 1
            if done % 50 == 0:
                print("  %d/%d" % (done, len(ids)), flush=True)

    json.dump(out, open(a.out, "w"), indent=1)
    dead = [r for r in out if not r["ok"]]
    coll = [r for r in out if r.get("collapse")]
    lies = [r for r in out if r.get("open_no_seats")]
    nomix = [r for r in out if r["ok"] and not r["mixed"]]
    print("\n==== FLEET HEALTH ====")
    print("total            %d" % len(out))
    print("reachable        %d (%.1f%%)" % (len(out) - len(dead), 100.0 * (len(out) - len(dead)) / max(1, len(out))))
    print("DEAD             %d   <- a student signing up here receives NOTHING" % len(dead))
    print("SECTION COLLAPSE %d   <- silent miss: sections invisible to the poller" % len(coll))
    print("OPEN w/ 0 SEATS  %d   <- would fire a FALSE ALERT" % len(lies))
    print("no mixed status  %d   (all-open or all-full: unproven seat data, or a quiet term)" % len(nomix))
    for label, rows in (("DEAD", dead), ("COLLAPSE", coll), ("FALSE-ALERT RISK", lies)):
        if rows:
            print("\n-- %s --" % label)
            for r in sorted(rows, key=lambda x: x["id"])[:40]:
                print("   %-16s %-34s %s" % (r["id"], r.get("adapter", "?"),
                                             r.get("err") or "sections=%s" % r.get("sections")))
    print("\nfull results: %s" % a.out)


if __name__ == "__main__":
    main()
