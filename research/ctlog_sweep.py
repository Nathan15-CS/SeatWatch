#!/usr/bin/env python3
"""CT-log sweep v2 — crt.sh (unlimited but slow/flaky) -> banner-ish subdomains -> probe Banner9 SSB.

Correctness fixes over v1 (which false-negatived under concurrency):
 - LOW concurrency (crt.sh chokes under load; 6 workers -> ~all-empty).
 - RETRY crt.sh on 502/503/timeout/non-JSON (these are transient, not "no data").
 - Hard `ct_ok` flag: a domain is only "checked" if crt.sh returned real JSON. Domains that
   never succeeded go to needs_retry.json for a later pass — NEVER counted as Banner-free.
Writes ctlog_sweep_results.json incrementally + needs_retry.json at the end.
"""
import json, time, urllib.request, ssl
from concurrent.futures import ThreadPoolExecutor, as_completed

CTX = ssl.create_default_context(); CTX.check_hostname = False; CTX.verify_mode = ssl.CERT_NONE
UA = {"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36"}
BANNERISH = ("banner", "ssb", "banweb", "bannerweb", "banprod", "bandr",
             "selfservice", "ellucian", "reg.", "registration", "ssbprod", "xess", "xereg")
WORKERS = 2

def http(url, timeout=45):
    req = urllib.request.Request(url, headers=UA)
    with urllib.request.urlopen(req, timeout=timeout, context=CTX) as r:
        return r.getcode(), r.read().decode("utf-8", "replace")

def crtsh(domain, tries=4):
    """Return (names:set, ok:bool). ok=True only on a real 200+JSON; else retry with backoff."""
    url = f"https://crt.sh/?q=%25.{domain}&output=json"
    for i in range(tries):
        try:
            code, body = http(url, 45)
            if code == 200 and body.strip().startswith("["):
                names = set()
                for row in json.loads(body):
                    for k in ("common_name", "name_value"):
                        for n in str(row.get(k, "")).split("\n"):
                            n = n.strip().lower()
                            if n and "*" not in n:
                                names.add(n)
                return names, True
        except Exception:
            pass
        time.sleep(2 * (i + 1))
    return set(), False

def probe_ssb(host, base_path="StudentRegistrationSsb"):
    url = f"https://{host}/{base_path}/ssb/classSearch/getTerms?searchTerm=&offset=1&max=10"
    try:
        code, body = http(url, 20)
        if code == 200 and body.strip().startswith("["):
            terms = json.loads(body)
            if isinstance(terms, list) and terms and "code" in terms[0]:
                return terms
    except Exception:
        pass
    return None

def work(domain):
    out = {"domain": domain, "ct_ok": False, "banner_hosts": [], "ssb_hits": []}
    names, ok = crtsh(domain)
    out["ct_ok"] = ok
    out["total_names"] = len(names)
    if not ok:
        return out
    hits = sorted(s for s in names if any(t in s for t in BANNERISH))
    out["banner_hosts"] = hits
    for h in hits:
        terms = probe_ssb(h)
        if terms:
            out["ssb_hits"].append({"host": h, "terms": terms[:6]})
    return out

def main():
    targets = json.load(open("ctlog_targets_remaining.json"))
    results, done = [], 0
    with ThreadPoolExecutor(max_workers=WORKERS) as ex:
        futs = {ex.submit(work, d): d for d in targets}
        for fut in as_completed(futs):
            r = fut.result(); results.append(r); done += 1
            if r.get("ssb_hits"):
                tag = " *** SSB HIT: " + ", ".join(h["host"] for h in r["ssb_hits"])
            elif not r["ct_ok"]:
                tag = " [ct FAIL -> needs_retry]"
            elif r["banner_hosts"]:
                tag = " (banner hosts, no live SSB: " + ",".join(r["banner_hosts"][:3]) + ")"
            else:
                tag = ""
            print(f"[{done}/{len(targets)}] {r['domain']}{tag}", flush=True)
            if done % 10 == 0:
                json.dump(results, open("ctlog_sweep_results.json", "w"), indent=1)
    json.dump(results, open("ctlog_sweep_results.json", "w"), indent=1)
    retry = [r["domain"] for r in results if not r["ct_ok"]]
    json.dump(retry, open("needs_retry.json", "w"), indent=1)
    ssb = [r for r in results if r.get("ssb_hits")]
    checked = sum(1 for r in results if r["ct_ok"])
    print(f"\n=== DONE. checked={checked}/{len(targets)}  ct_FAIL={len(retry)}  "
          f"SSB_hits={len(ssb)} ===", flush=True)
    for r in ssb:
        for h in r["ssb_hits"]:
            print(f"  {r['domain']}: {h['host']}  terms={[t.get('code') for t in h['terms']]}", flush=True)
    if retry:
        print(f"needs_retry ({len(retry)}): {retry[:20]}{'...' if len(retry)>20 else ''}", flush=True)

if __name__ == "__main__":
    main()
