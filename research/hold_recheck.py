#!/usr/bin/env python3
"""Re-check HOLD-listed schools for loaded Fall 2026 sections.

These schools are VERIFIED accessible — we can read their live seat data — but hadn't
published their Fall 2026 class schedule yet. Run this periodically (weekly). When a
school flips to FALL-LIVE=YES, it's a clean add: hand it to the builder.

Usage:  python3 research/hold_recheck.py
"""
import json, urllib.request, http.cookiejar, re

UA = "Mozilla/5.0"

# (name, host, sis)  — sis: "colleague" uses /Student/Courses
HOLD = [
    ("Aurora University",        "aurora-ss.colleague.elluciancloud.com", "colleague"),
    ("Colorado Mountain",        "selfservice.coloradomtn.edu",           "colleague"),
    ("American Samoa CC",        "amsamoa-ss.colleague.elluciancloud.com","colleague"),
    ("Columbus State (uncertain)","selfservice.cscc.edu",                 "colleague"),
]
FALL = ("fall 2026", "fall semester 2026", "2026 fall")

def colleague_fall_live(host):
    cj = http.cookiejar.CookieJar()
    op = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(cj))
    op.addheaders = [("User-Agent", UA)]
    body = op.open(f"https://{host}/Student/Courses", timeout=15).read().decode("utf-8", "replace")
    m = re.search(r'name="__RequestVerificationToken"[^>]*value="([^"]+)"', body)
    tok = m.group(1) if m else None
    def post(path, payload):
        req = urllib.request.Request(f"https://{host}{path}", data=json.dumps(payload).encode())
        req.add_header("Content-Type", "application/json")
        req.add_header("X-Requested-With", "XMLHttpRequest")
        if tok: req.add_header("__RequestVerificationToken", tok)
        return json.loads(op.open(req, timeout=18).read().decode("utf-8", "replace"))
    d = post("/Student/Courses/PostSearchCriteria", {"Keyword": "ENGL"})
    for c in (d.get("CourseFullModels") or [])[:5]:
        if not c.get("MatchingSectionIds"): continue
        try:
            sd = post("/Student/Courses/Sections",
                      {"sectionIds": c["MatchingSectionIds"], "courseId": c["Id"]})
        except Exception:
            continue
        for tm in (sd.get("SectionsRetrieved") or {}).get("TermsAndSections") or []:
            desc = ((tm.get("Term") or {}).get("Description") or "").lower()
            if any(f in desc for f in FALL):
                for wrap in tm.get("Sections") or []:
                    s = wrap.get("Section") or wrap
                    if s.get("AreSeatCountsAvailable"):
                        return True
    return False

ready = []
for name, host, sis in HOLD:
    try:
        live = colleague_fall_live(host)
    except Exception as e:
        print(f"{name:26s} ERROR {type(e).__name__}")
        continue
    print(f"{name:26s} FALL-LIVE={'YES ✅ READY TO ADD' if live else 'no (still waiting)'}")
    if live:
        ready.append((name, host))

if ready:
    print("\n*** SCHOOLS NOW READY — hand to builder: ***")
    for name, host in ready:
        print(f"  - {name}  ({host})")
else:
    print("\nNone ready yet. Re-run in ~1 week.")
