"""READINESS #10 — Section-collapse detector (silent-miss guard).

THE BUG THIS EXISTS FOR: Banner adapters key sections by `sequenceNumber`. Some hosts
return the SAME sequenceNumber (often '0') on every row, so a whole course collapses into
one section and every other section becomes invisible — a student watching it is never
told about openings in the sections we dropped.

Total collapse (49 -> 1) is obvious. The one that actually got through was PARTIAL:
Hawaii CC returned 25 rows under 14 distinct sequence numbers, so it looked plausible
AND passed an open+full disproof while silently dropping 11 sections. A check that
returns believable output while being wrong is more dangerous than one that returns
nothing, so this asserts the exact invariant instead:

    distinct section keys == number of real rows for that course

Any shortfall is a silent miss. The fix when it fires is to key by CRN
(`courseReferenceNumber`), which is unique per term on every Banner host we've seen.
"""
import os, sys, json, urllib.parse, urllib.request, concurrent.futures as cf

# Bounded sample — hitting all 800+ live hosts would take far too long for a readiness
# run. Deliberately weighted to the risky shapes: shared/pooled hosts (where one campus's
# numbering can differ from another's), the CRN-keyed family (regression), and a spread of
# ordinary Banner schools. NOT a completeness proof — the coverage limit is stated in the
# result so it can never read as "all schools verified".
SAMPLE = [
    # UH pooled host — the family this bug was found on
    "uhmanoa", "uhhilo", "uhwestoahu", "uhmaui", "hawaiicc", "honolulucc",
    "kapiolanicc", "kauaicc", "leewardcc", "windwardcc",
    # ASU pooled host (mep-separated)
    "arkansasstate", "hendersonstate", "asubeebe", "asunewport",
    # ordinary Banner spread
    "umd", "utk", "fau", "angelostate", "shsu", "isu", "wwu", "uncp", "wcu",
    "msutexas", "ferris", "jsu", "oaklandu", "sulross", "fredonia", "ecu",
]


def run():
    sys.path.insert(0, os.path.expanduser("~/seatwatch"))
    import schools
    S = schools.SCHOOLS
    results = []

    def probe(sid):
        a = S.get(sid)
        if a is None or not isinstance(a, schools.Banner):
            return (sid, None, None, "not a Banner school")
        try:
            subj, num = a._code(a.example)
            op, base = a._session()
            op.open(urllib.request.Request(base + "/classSearch/resetDataForm" + a._mep("?"),
                                           data=b""), timeout=15).read()
            q = urllib.parse.urlencode({"txt_subject": subj, "txt_courseNumber": num,
                                        "txt_term": a.cur_term(),
                                        "pageOffset": 0, "pageMaxSize": 200})
            rows = json.loads(op.open(base + "/searchResults/searchResults?" + q + a._mep(),
                                      timeout=30).read().decode("utf-8", "replace")).get("data") or []
            # Count rows the adapter SHOULD return: same subject/course/campus/eligibility
            # filters it applies, and a usable seat count.
            real = 0
            for r in rows:
                if str(r.get("courseNumber")) != num: continue
                if (r.get("subject") or "").upper() != subj: continue
                if not a._campus_ok(r): continue
                if not a._eligible(r): continue
                try: int(r.get("seatsAvailable"))
                except (TypeError, ValueError): continue
                real += 1
            got = len(a.fetch([a.example]).get(a.example, {}))
            return (sid, real, got, None)
        except Exception as e:
            return (sid, None, None, f"{type(e).__name__}")

    with cf.ThreadPoolExecutor(8) as ex:
        rows = list(ex.map(probe, SAMPLE))

    checked = skipped = 0
    for sid, real, got, err in rows:
        name = S[sid].name[:34] if sid in S else sid
        if err or real is None:
            skipped += 1
            continue
        if real == 0:                      # course not offered right now — nothing to assert
            skipped += 1
            continue
        checked += 1
        lost = real - got
        results.append((f"no section collapse: {name} ({got}/{real} sections)",
                        got == real,
                        f"DROPPING {lost} of {real} sections — key by CRN"))

    results.append((f"coverage: {checked} schools asserted, {skipped} skipped "
                    f"(sample of {len(SAMPLE)}, NOT all {len(S)})", True, ""))

    p = sum(ok for _, ok, _ in results)
    f = sum(not ok for _, ok, _ in results)
    return p, f, results


if __name__ == "__main__":
    import warnings; warnings.filterwarnings("ignore")
    p, f, res = run()
    for n, ok, d in res:
        print(f"  [{'PASS' if ok else '*** FAIL'}] {n}{('  ' + d) if d and not ok else ''}")
    print(f"\n  {p} passed, {f} failed")
    sys.exit(1 if f else 0)
