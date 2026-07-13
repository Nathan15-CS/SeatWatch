#!/usr/bin/env python3
"""Re-sweep confirmed Banner-host domains through the NEW adapters (ListcrseBanner8 +
TabularBanner8 + widened CRN + real-term discovery). Resurrects 'falsely dead' Banner
schools (tabular listing / 4-digit CRN / wrong-term). Prints host + example + term for
any PASS so Builder can gate fast."""
import sys, re, json, ssl, urllib.request
sys.path.insert(0, "/Users/nathananapolsky/seatwatch")
import schools
ctx = ssl.create_default_context(); ctx.check_hostname=False; ctx.verify_mode=ssl.CERT_NONE
UA = {"User-Agent": "Mozilla/5.0"}
def get(url, t=12):
    return urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=t, context=ctx).read().decode("utf-8","replace")

PKGS = ["pls/PROD","pls/prod","prod","PROD","pls/BANPROD","prodssb/bwckschd","pls/DORA","pls/PRD"]
COURSES = ["ENGL 101","ENG 101","ENGL 1010","MATH 101","MATH 1010","BIOL 101","ENGL 1101","PSY 201","ENGL 100"]

def find_base(host):
    for pkg in PKGS:
        base = f"https://{host}/{pkg.split('/bwck')[0]}"
        try:
            b = get(f"{base}/bwckschd.p_disp_dyn_sched")
            if "p_term" in b or "term_in" in b.lower() or "<option" in b.lower():
                return base, b
        except Exception:
            continue
    return None, None

def fall_term(dyn_html):
    opts = re.findall(r'<option[^>]*value="(\d{6})"[^>]*>([^<]+)</option>', dyn_html, re.I)
    fall = [(c,l) for c,l in opts if "fall" in l.lower() and "2026" in l]
    if fall: return fall[0][0]
    y26 = [(c,l) for c,l in opts if "2026" in l]
    return y26[0][0] if y26 else (opts[0][0] if opts else None)

def gate(base, term, cls):
    ad = type("P",(cls,),{"id":"p","name":"P","example":COURSES[0],"term":term,"base":base})()
    best=None
    for c in COURSES:
        try: r=ad.fetch({c}).get(c)
        except Exception: continue
        if not r: continue
        rf=sum(1 for v in r.values() if (not v["open"]) and v["seats"]==0)
        o=sum(1 for v in r.values() if v["open"])
        if rf>0 and o>0: return (c,len(r),o,rf)   # clean mix
        if not best and len(r): best=(c,len(r),o,rf)
    return best

d = json.load(open("ctlog_sweep_results.json"))
hosts=[]
for r in d:
    for h in (r.get("banner_hosts") or []):
        hh = h["host"] if isinstance(h,dict) else h
        if any(x in hh for x in ("banweb","ssb","banner","prodssb")) and "www." not in hh:
            hosts.append(hh)
hosts=sorted(set(hosts))
print(f"probing {len(hosts)} banner hosts through new adapters\n")
for host in hosts:
    base, dyn = find_base(host)
    if not base: print(f"  {host:38s} no live pls package"); continue
    term = fall_term(dyn)
    if not term: print(f"  {host:38s} live but no term"); continue
    for cls in (schools.TabularBanner8, schools.ListcrseBanner8):
        res = gate(base, term, cls)
        if res and res[3]>0 and res[2]>0:
            print(f"  ✅ HIT {host}  base={base} term={term} {cls.__name__} {res[0]}={res[1]}sec {res[2]}o/{res[3]}full")
            break
    else:
        print(f"  {host:38s} base={base} term={term} -> no clean gate")
print("\nDONE")
