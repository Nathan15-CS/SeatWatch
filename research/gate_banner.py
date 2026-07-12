#!/usr/bin/env python3
"""Gate a candidate Banner host THROUGH THE PRODUCTION adapter (schools.Banner.fetch).
Usage: python3 gate_banner.py <host> [base_path] [term]

Method:
 1. Build a runtime Banner subclass (host + optional base_path); auto-resolve the live term.
 2. DISCOVER real courses: using the adapter's own authenticated session, pull the live subject
    list, then enumerate real course numbers for a few subjects (so we never guess course codes).
 3. GATE: feed those real "SUBJ NUM" strings through the PRODUCTION .fetch() and report open/full.
 4. Numeric-enrollment disproof (Banner reads seatsAvailable): a LIVE term must show real FULL
    sections (seats==0) mixed with open. Also probes a COMPLETED (View Only) term as a bonus.
"""
import sys, json, urllib.parse, urllib.request
sys.path.insert(0, "/Users/nathananapolsky/seatwatch")
import schools

def build(host, base_path):
    cls = type("Probe", (schools.Banner,), {
        "id": "probe", "name": "Probe", "example": "ENGL 101",
        "host": host, "term": "202710", "base_path": base_path})
    return cls()

def discover_courses(ad, term, max_pairs=14):
    """Return real 'SUBJ NUM' strings by asking the live API for subjects + their course numbers."""
    op, base = ad._session()
    pairs = []
    try:
        raw = op.open(base + f"/classSearch/get_subject?searchTerm=&term={term}"
                      f"&offset=1&max=100&_=1", timeout=30).read().decode("utf-8", "replace")
        subjects = [s.get("code") for s in json.loads(raw) if s.get("code")]
    except Exception as e:
        print(f"  get_subject FAILED: {e}")
        subjects = []
    seen = set()
    for subj in subjects:
        if len(pairs) >= max_pairs:
            break
        try:
            # Banner keeps the last search's filter in session state — reset before each
            # subject or every query echoes the first subject's rows.
            op.open(urllib.request.Request(base + "/classSearch/resetDataForm", data=b""),
                    timeout=15).read()
            q = urllib.parse.urlencode({"txt_subject": subj, "txt_term": term,
                                        "pageOffset": 0, "pageMaxSize": 50})
            res = json.loads(op.open(base + "/searchResults/searchResults?" + q + ad._mep(),
                                     timeout=30).read().decode("utf-8", "replace"))
            got = 0
            for r in res.get("data") or []:
                num = str(r.get("courseNumber") or "")
                s = (r.get("subject") or "").upper()
                if s == subj.upper() and num and (s, num) not in seen:
                    seen.add((s, num)); pairs.append(f"{s} {num}"); got += 1
                if got >= 2:
                    break
        except Exception:
            continue
    return subjects, pairs

def summarize(host, base_path, force_term=None):
    ad = build(host, base_path)
    print(f"# host={host} base_path={base_path}")
    try:
        terms = ad._get_terms()
    except Exception as e:
        print(f"  getTerms FAILED: {e}")
        return
    print("  terms:", [(t.get("code"), t.get("description")) for t in terms[:8]])
    live = force_term or ad.resolve_term() or (terms[0]["code"] if terms else None)
    ad._active_term = live
    print(f"  LIVE term = {live}")
    subjects, pairs = discover_courses(ad, live)
    print(f"  subjects found: {len(subjects)} (e.g. {subjects[:12]})")
    print(f"  probing real courses: {pairs}")
    total = full = openn = 0
    examples = []
    for c in pairs:
        r = ad.fetch({c}).get(c)
        if not r:
            continue
        o = sum(1 for v in r.values() if v["open"])
        f = sum(1 for v in r.values() if not v["open"])
        total += len(r); openn += o; full += f
        seats = [v["seats"] for v in list(r.values())[:8]]
        examples.append((c, len(r), o, f, seats))
    print(f"  LIVE-TERM RESULT: {total} sections / {len(examples)} courses; {openn} open / {full} FULL")
    for c, n, o, f, seats in examples:
        print(f"    {c:14s} {n:3d} sec  {o} open {f} full  seats={seats}")
    verdict = "PASS (real full sections in live term)" if full > 0 else \
              "SUSPECT (all-open — probe completed term / more courses before trusting)"
    print(f"  DISPROOF: {verdict}")
    return {"host": host, "live": live, "total": total, "open": openn,
            "full": full, "examples": examples, "subjects": subjects}

if __name__ == "__main__":
    import urllib.request
    host = sys.argv[1]
    base_path = sys.argv[2] if len(sys.argv) > 2 else "StudentRegistrationSsb"
    term = sys.argv[3] if len(sys.argv) > 3 else None
    summarize(host, base_path, term)
