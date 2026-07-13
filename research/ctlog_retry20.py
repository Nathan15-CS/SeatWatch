#!/usr/bin/env python3
"""Retry the 20 stubborn ct_FAIL domains from needs_retry2.json (crt.sh came back up).
Same v2 discipline; writes ctlog_retry20_results.json + needs_retry3.json."""
import json
import ctlog_sweep as cs
from concurrent.futures import ThreadPoolExecutor, as_completed

targets = json.load(open("needs_retry2.json"))
results, done = [], 0
with ThreadPoolExecutor(max_workers=2) as ex:
    futs = {ex.submit(cs.work, d): d for d in targets}
    for fut in as_completed(futs):
        r = fut.result(); results.append(r); done += 1
        if r.get("ssb_hits"):
            tag = " *** SSB HIT: " + ", ".join(h["host"] for h in r["ssb_hits"])
        elif not r["ct_ok"]:
            tag = " [ct FAIL again]"
        elif r["banner_hosts"]:
            tag = " (banner hosts, no live SSB: " + ",".join(r["banner_hosts"][:3]) + ")"
        else:
            tag = ""
        print(f"[{done}/{len(targets)}] {r['domain']}{tag}", flush=True)
json.dump(results, open("ctlog_retry20_results.json", "w"), indent=1)
retry = [r["domain"] for r in results if not r["ct_ok"]]
json.dump(retry, open("needs_retry3.json", "w"), indent=1)
checked = sum(1 for r in results if r["ct_ok"])
ssb = [r for r in results if r.get("ssb_hits")]
print(f"\n=== DONE. checked={checked}/{len(targets)}  still_FAIL={len(retry)}  SSB_hits={len(ssb)} ===", flush=True)
for r in ssb:
    for h in r["ssb_hits"]:
        print(f"  {r['domain']}: {h['host']}  terms={[t.get('code') for t in h['terms']]}", flush=True)
