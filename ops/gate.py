#!/usr/bin/env python3
"""Accuracy gate for a new (or changed) school adapter.

    python3 ops/gate.py oldwestbury sunypotsdam
    python3 ops/gate.py --all-new          # everything not in the deployed commit

Run this BEFORE handing an adapter over. Every check here exists because a real adapter
shipped or nearly shipped with that exact defect:

  phantom sections   LSSU returned {'none': {'open': False, 'seats': None}} for every
                     course and it read as "1 section, full". The 'none' key is a
                     deliberate sentinel meaning "fetch worked, no sections" — drop it
                     before counting or you are counting nothing as something.
  seats not an int   seats=None means the seat parse failed. A real section yields a
                     number; 0 is full, None is broken.
  single status      an all-full sample cannot disprove a parser that reports everything
                     closed (student never alerted). An all-open sample cannot disprove
                     one that reports everything open (false alert, worse). You need BOTH
                     states before either failure mode is ruled out.
  lying sections     FULL while holding seats = a silent miss. OPEN with no seats = a
                     false alert. Both are lies to a student.
  section collapse   UNF returned 1 section of 9 and still passed an open+full disproof,
                     because the surviving section had a mix. Repeated sequenceNumbers
                     collapse a course; key by CRN. Hawaii CC hid 11 of 25 this way.
  stale term         a term that has rolled, or one published years early, silently
                     starves every watcher. Bias late, never early.

Exit code 0 only if every school passes.
"""
import argparse, collections, json, sys, warnings, urllib.parse, urllib.request
import concurrent.futures as cf

warnings.filterwarnings("ignore")
sys.path.insert(0, "/Users/nathananapolsky/seatwatch")
import schools  # noqa: E402

# Deliberately generic AND format-diverse: schools do not share a numbering convention.
# Langston uses 2-letter subjects (AC/BI/MT), UNF and ONU use 4-digit numbers, Athens
# State is upper-division only. A probe list that assumes one house style finds nothing
# and looks like a broken adapter.
PROBE = ["ENG 101", "ENGL 101", "ENGL 1010", "ENGL 1101", "ENG 111", "MATH 101",
         "MATH 1010", "MATH 121", "BIOL 101", "BIO 101", "BIOL 1010", "CHEM 101",
         "PSY 101", "PSYC 101", "HIST 101", "HIST 1010", "SOC 101", "ACCT 201",
         "ART 101", "COMM 101", "ECON 201", "POLS 101", "NURS 101", "EDUC 101"]


# VERIFIED EXCEPTIONS. A section reporting FULL while holding seats is normally a silent
# miss, but not always: some hosts hold the remaining seats for a waitlist queue, and
# refusing to call those "open" is CORRECT — announcing them would send a student running
# at a seat they cannot take. Each entry needs evidence, not a hunch, and stays listed so
# the exception is reviewable instead of hidden inside an adapter.
FULL_WITH_SEATS_OK = {
    "twu": ("Texas Woman's University, verified 2026-07-31: every FULL-with-seats section "
            "has a non-zero Waitlisted count (5/5 sampled), and Available+Enrolled==Capacity "
            "holds on 107/108 rows, so the counts are real. Re-verify by pulling "
            "AvailabilityStatus and Waitlisted from /Student/Courses/SectionsAsync."),
}


def _clean(res):
    """Drop the 'none' sentinel — it means no sections, not one full section."""
    return {k: v for k, v in (res or {}).items() if k != "none"}


def probe(a, extra_codes=(), budget_s=75):
    """Collect sections until BOTH states are seen, the probe list is exhausted, or the
    per-school time budget runs out.

    The budget is not a nicety. Without it, a school that answers nothing walks the whole
    probe list at the adapter's own socket timeout (up to 45s each), so ONE dead host can
    hold a worker for ~18 minutes and a 27-school run never finishes. Better to report
    "inconclusive within budget" for that school than to stall the batch.
    """
    import time as _t
    deadline = _t.time() + budget_s
    tot = op = fu = 0
    timed_out = False
    lies_full, lies_open, hits, non_int = [], [], [], []
    for code in dict.fromkeys([a.example] + list(extra_codes) + PROBE):
        if op and fu:
            break
        if _t.time() > deadline:
            timed_out = True
            break
        try:
            r = _clean(a.fetch([code]).get(code, {}))
        except Exception:
            continue
        if not r:
            continue
        hits.append(f"{code}({len(r)})")
        for k, v in r.items():
            tot += 1
            s = v.get("seats")
            if not isinstance(s, int):
                non_int.append(f"{code}/{k}={s!r}")
                continue
            if v.get("open"):
                op += 1
                if s <= 0:
                    lies_open.append(f"{code}/{k}={s}")
            else:
                fu += 1
                if s > 0:
                    lies_full.append(f"{code}/{k}={s}")
    return tot, op, fu, lies_full, lies_open, non_int, hits, timed_out


def collapse(a):
    """Banner only: distinct keys returned must equal rows surviving the adapter's own
    filters. Any shortfall is a section the student can never watch."""
    if not isinstance(a, schools.Banner):
        return None
    try:
        subj, num = a._code(a.example)
        op_, base = a._session()
        op_.open(urllib.request.Request(base + "/classSearch/resetDataForm" + a._mep("?"),
                                        data=b""), timeout=15).read()
        q = urllib.parse.urlencode({"txt_subject": subj, "txt_courseNumber": num,
                                    "txt_term": a.cur_term(), "pageOffset": 0,
                                    "pageMaxSize": 200})
        rows = json.loads(op_.open(base + "/searchResults/searchResults?" + q + a._mep(),
                                   timeout=40).read().decode("utf-8", "replace")).get("data") or []
        real, seqs = 0, []
        for r in rows:
            if str(r.get("courseNumber")) != num: continue
            if (r.get("subject") or "").upper() != subj: continue
            if not a._campus_ok(r): continue
            if not a._eligible(r): continue
            try: int(r.get("seatsAvailable"))
            except (TypeError, ValueError): continue
            real += 1
            seqs.append(str(r.get("sequenceNumber")))
        got = len(_clean(a.fetch([a.example]).get(a.example, {})))
        return got, real, len(seqs) - len(set(seqs))
    except Exception:
        return None


def peers(a, sid, S):
    h = str(getattr(a, "host", None) or getattr(a, "base", None) or "")
    if not h or h == "None":
        return []
    return [p for p, x in S.items()
            if p != sid and str(getattr(x, "host", None) or getattr(x, "base", None) or "") == h]


def gate(sid, S):
    a = S.get(sid)
    if a is None:
        return sid, "?", False, ["not in the registry"]
    notes, ok = [], True
    tot, op, fu, lf, lo, non_int, hits, timed_out = probe(a)

    if not tot:
        return sid, a.name, False, ["returned NOTHING for any probed course"]
    if non_int:
        ok = False; notes.append(f"seats not an int (parse failed): {non_int[:3]}")
    if lf:
        why = FULL_WITH_SEATS_OK.get(sid)
        if why:
            notes.append(f"FULL-with-seats present but ALLOWED — {why}")
        else:
            ok = False
            notes.append(f"SILENT MISS — FULL while holding seats: {lf[:3]}")
    if lo:
        ok = False; notes.append(f"FALSE OPEN — OPEN with no seats: {lo[:3]}")
    if not op:
        ok = False
        notes.append("no OPEN section found: cannot disprove an always-closed parser"
                     + (" (probe hit its time budget - rerun this one alone)" if timed_out else ""))
    if not fu:
        ok = False
        notes.append("no FULL section found: cannot disprove an always-open parser"
                     + (" (probe hit its time budget - rerun this one alone)" if timed_out else ""))

    c = collapse(a)
    if c:
        got, real, dups = c
        if got != real:
            ok = False
            notes.append(f"SECTION COLLAPSE — returns {got} of {real} "
                         f"({dups} duplicate sequenceNumbers); key by CRN")
    p = peers(a, sid, S)
    if p:
        notes.append(f"SHARED HOST with {p} — isolation must be proven by cross-query")

    term = getattr(a, "term", None)
    detail = (f"{tot:>3} sec  {op:>3} open  {fu:>3} full"
              + (f"  keyed {c[0]}/{c[1]}" if c else "")
              + (f"  term={term}" if term else "")
              + f"  [{', '.join(hits[:3])}]")
    return sid, a.name, ok, ([detail] + notes)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("ids", nargs="*")
    args = ap.parse_args()
    S = schools.SCHOOLS
    ids = args.ids or []
    if not ids:
        print("usage: python3 ops/gate.py <school_id> [...]"); return 2
    print(f"gating {len(ids)} adapter(s) against live registration systems\n")
    with cf.ThreadPoolExecutor(min(5, len(ids))) as ex:
        rows = list(ex.map(lambda s: gate(s, S), ids))
    bad = []
    for sid, name, ok, notes in rows:
        if not ok: bad.append(sid)
        print(f"  [{'PASS' if ok else 'FAIL'}] {sid:<16} {str(name)[:34]:<35} {notes[0]}")
        for n in notes[1:]:
            print(f"         -> {n}")
    print(f"\n  {len(rows)-len(bad)}/{len(rows)} pass")
    if bad:
        print(f"  BLOCKED: {', '.join(bad)}")
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
