#!/usr/bin/env python3
"""Batch-gate CT-log Banner-9 candidates through production schools.Banner.fetch (lean, ~6 courses)."""
import sys
sys.path.insert(0, "/Users/nathananapolsky/seatwatch")
import schools, gate_banner

# (label, host) — Banner-9 hosts found by the CT-log sweep, deduped net-new
CANDS = [
    ("SUNY Delhi", "ssb.delhi.edu"),
    ("SUNY Delhi(alt)", "banner.delhi.edu"),
    ("Framingham State", "banner9prod.framingham.edu"),
    ("Guam CC", "prodssb.guamcc.edu"),
    ("Missouri Southern", "ssb.mssu.edu"),
    ("Northeastern Illinois", "ssb.neiu.edu"),
    ("NEOMED", "ssb.neomed.edu"),
]

def lean(host):
    ad = gate_banner.build(host, "StudentRegistrationSsb")
    try:
        terms = ad._get_terms()
    except Exception as e:
        return f"getTerms FAIL ({str(e)[:40]})"
    live = ad.resolve_term() or (terms[0]["code"] if terms else None)
    ad._active_term = live
    _, pairs = gate_banner.discover_courses(ad, live, max_pairs=6)
    tot = o = f = 0
    for c in pairs:
        r = ad.fetch({c}).get(c)
        if not r:
            continue
        tot += len(r); o += sum(1 for v in r.values() if v["open"]); f += sum(1 for v in r.values() if not v["open"])
    termdesc = next((t.get("description") for t in terms if t.get("code") == live), "?")
    verdict = "PASS" if f > 0 else ("SUSPECT(all-open)" if tot else "NO-DATA")
    return f"live={live}({termdesc}) {tot} sec {o} open/{f} full -> {verdict}"

for label, host in CANDS:
    try:
        print(f"{label:24s} {host:32s} {lean(host)}", flush=True)
    except Exception as e:
        print(f"{label:24s} {host:32s} ERR {str(e)[:50]}", flush=True)
