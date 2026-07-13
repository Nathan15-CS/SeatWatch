#!/usr/bin/env python3
"""Weekly scheduled CT-log batch (July 13 2026) — fresh 4-year HBCU/regional-public
candidates not present in schools.py or any prior ctlog queue. Same v2 discipline as
ctlog_sweep.py (crt.sh, low concurrency, hard ct_ok flag)."""
import json
import ctlog_sweep as cs
from concurrent.futures import ThreadPoolExecutor, as_completed

targets = [
    "fayettevillestate.edu",   # Fayetteville State University (NC)
    "ecsu.edu",                # Elizabeth City State University (NC)
    "bowiestate.edu",          # Bowie State University (MD)
    "savannahstate.edu",       # Savannah State University (GA)
    "alcorn.edu",              # Alcorn State University (MS)
    "jsums.edu",               # Jackson State University (MS)
    "desu.edu",                # Delaware State University (DE)
    "langston.edu",            # Langston University (OK)
    "centralstate.edu",        # Central State University (OH)
    "vsu.edu",                 # Virginia State University (VA)
    "nsu.edu",                 # Norfolk State University (VA)
]

results, done = [], 0
with ThreadPoolExecutor(max_workers=2) as ex:
    futs = {ex.submit(cs.work, d): d for d in targets}
    for fut in as_completed(futs):
        r = fut.result(); results.append(r); done += 1
        if r.get("ssb_hits"):
            tag = " *** SSB HIT: " + ", ".join(h["host"] for h in r["ssb_hits"])
        elif not r["ct_ok"]:
            tag = " [ct FAIL]"
        elif r["banner_hosts"]:
            tag = " (banner hosts, no live SSB: " + ",".join(r["banner_hosts"][:3]) + ")"
        else:
            tag = ""
        print(f"[{done}/{len(targets)}] {r['domain']}{tag}", flush=True)

json.dump(results, open("ctlog_weekly_2026-07-13_results.json", "w"), indent=1)
retry = [r["domain"] for r in results if not r["ct_ok"]]
ssb = [r for r in results if r.get("ssb_hits")]
checked = sum(1 for r in results if r["ct_ok"])
print(f"\n=== DONE. checked={checked}/{len(targets)}  ct_FAIL={len(retry)}  SSB_hits={len(ssb)} ===", flush=True)
for r in ssb:
    for h in r["ssb_hits"]:
        print(f"  {r['domain']}: {h['host']}  terms={[t.get('code') for t in h['terms']]}", flush=True)
if retry:
    print(f"needs_retry: {retry}", flush=True)
