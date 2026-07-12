#!/usr/bin/env python3
"""Second pass over the sweep's 'banner host, no live SSB' domains — close false negatives.

For every banner-ish host that failed the default StudentRegistrationSsb getTerms probe, try:
  1. Banner 9 SSB at the alternate base_path 'registration' (Drexel-style).
  2. Old Banner 8 route: bwckschd.p_disp_dyn_sched (the guest schedule form) — a live 200 with a
     term <select> means Banner 8 (gate via the catalog route bwckctlg.p_disp_listcrse, not SSB).
  3. Classify selfservice.* / *.elluciancloud hosts as COLLEAGUE leads -> hand to Codex.
Reads ctlog_sweep_results.json; writes ctlog_secondpass_results.json + colleague_leads_for_codex.json.
"""
import json, urllib.request, ssl, re, os

CTX = ssl.create_default_context(); CTX.check_hostname = False; CTX.verify_mode = ssl.CERT_NONE
UA = {"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36"}

def http(url, timeout=20, data=None):
    req = urllib.request.Request(url, headers=UA, data=data)
    with urllib.request.urlopen(req, timeout=timeout, context=CTX) as r:
        return r.getcode(), r.read().decode("utf-8", "replace")

def ssb_terms(host, base_path):
    url = f"https://{host}/{base_path}/ssb/classSearch/getTerms?searchTerm=&offset=1&max=10"
    try:
        code, body = http(url, 18)
        if code == 200 and body.strip().startswith("["):
            t = json.loads(body)
            if isinstance(t, list) and t and "code" in t[0]:
                return t
    except Exception:
        pass
    return None

def banner8(host):
    """Old Banner 8 guest schedule form. 200 + a term <select> or 'p_disp' body = Banner 8."""
    for path in (f"https://{host}/pls/prod/bwckschd.p_disp_dyn_sched",
                 f"https://{host}/pls/bprod/bwckschd.p_disp_dyn_sched",
                 f"https://{host}/prod/bwckschd.p_disp_dyn_sched"):
        try:
            code, body = http(path, 18)
            if code == 200 and ("p_term" in body or "SUB_BTN" in body or "Select a Term" in body
                                or "bwckgens" in body):
                return path
        except Exception:
            continue
    return None

def main():
    if not os.path.exists("ctlog_sweep_results.json"):
        print("no sweep results yet"); return
    d = json.load(open("ctlog_sweep_results.json"))
    todo = [r for r in d if r["ct_ok"] and r["banner_hosts"] and not r["ssb_hits"]]
    print(f"second-pass over {len(todo)} 'banner host, no live SSB' domains")
    ssb_new, b8_new, colleague = [], [], []
    for r in todo:
        dom = r["domain"]
        for host in r["banner_hosts"]:
            if "selfservice" in host or "elluciancloud" in host:
                colleague.append({"domain": dom, "host": host}); continue
            t = ssb_terms(host, "registration")
            if t:
                ssb_new.append({"domain": dom, "host": host, "base_path": "registration",
                                "terms": [x.get("code") for x in t[:6]]})
                print(f"  *** SSB(registration) HIT {dom}: {host} {[x.get('code') for x in t[:4]]}")
                continue
            b8 = banner8(host)
            if b8:
                b8_new.append({"domain": dom, "host": host, "route": b8})
                print(f"  *** BANNER-8 {dom}: {b8}")
    json.dump({"ssb_registration": ssb_new, "banner8": b8_new, "colleague": colleague},
              open("ctlog_secondpass_results.json", "w"), indent=1)
    json.dump(colleague, open("colleague_leads_for_codex.json", "w"), indent=1)
    print(f"\n=== 2ND-PASS DONE. SSB(registration)={len(ssb_new)}  Banner8={len(b8_new)}  "
          f"Colleague-leads={len(colleague)} ===")
    for x in b8_new:
        print("  banner8:", x["domain"], x["route"])

if __name__ == "__main__":
    main()
