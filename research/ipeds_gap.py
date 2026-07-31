#!/usr/bin/env python3
"""
IPEDS coverage gap — which real US institutions is SeatWatch missing, ranked by size.

    python3 research/ipeds_gap.py [--limit 60] [--csv out.csv]

WHY THIS EXISTS
    Discovery by hostname guessing is exhausted: a 640-domain re-sweep produced 2
    net-new schools, CT-log enumeration is dead to wildcard certs, and a probe of 16
    plausible Ellucian-cloud tenants resolved zero. What was never the bottleneck is
    *knowing which schools exist* — that is a public dataset.

    IPEDS (the federal institution directory, ~6,200 rows) is the complete universe.
    Joined against schools.py it answers the only question worth asking: of the
    institutions we do NOT cover, which have the most students? That turns "sweep an
    alphabetical .edu dump starting at aaart.edu" into a ranked worklist where the
    first entries are the ones a real student is most likely to attend.

    This is a data join. No model, no network beyond one file download, no guessing.

WHAT IT DOES NOT DO
    It does not decide whether a school is addable — that is the 8-gate accuracy
    check, run per candidate through the production adapter. This narrows the field;
    it never promotes anything.
"""
import argparse
import csv
import io
import os
import re
import sys
import urllib.request
import zipfile

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
# Institutional characteristics ("HD") — one row per institution, with name, web
# address, level, control, and a size band. The year is pinned deliberately: a
# silently-newer file would change the gap list under us between runs.
IPEDS_URL = "https://nces.ed.gov/ipeds/datacenter/data/HD2023.zip"
# Cached outside the repo: it is a 4.5MB regenerable download, not source. Same
# reasoning as the Operator's state directory — data the tool can re-fetch does not
# belong in git.
CACHE = os.path.join(os.path.expanduser("~/.seatwatch-operator"), "ipeds_hd2023.csv")

# IPEDS codes. ICLEVEL 1 = 4-year+, 2 = at least 2 but < 4 years.
ICLEVEL = {"1": "4-year", "2": "2-year", "3": "<2-year"}
CONTROL = {"1": "public", "2": "private-nonprofit", "3": "private-forprofit"}
# INSTSIZE is a band, not a headcount — IPEDS's own bucketing. Good enough to rank by,
# and honest about its resolution: we are ordering by size class, not by exact FTE.
INSTSIZE = {"1": "<1k", "2": "1k-5k", "3": "5k-10k", "4": "10k-20k", "5": "20k+"}
SIZE_RANK = {"5": 0, "4": 1, "3": 2, "2": 3, "1": 4, "-2": 9, "": 9}


def fetch(force=False):
    """Download once, then work from the cached CSV."""
    if os.path.exists(CACHE) and not force:
        return CACHE
    sys.stderr.write("downloading IPEDS HD2023 (~1MB) ...\n")
    with urllib.request.urlopen(IPEDS_URL, timeout=120) as r:
        blob = r.read()
    with zipfile.ZipFile(io.BytesIO(blob)) as z:
        name = next(n for n in z.namelist() if n.lower().endswith(".csv"))
        with z.open(name) as src, open(CACHE, "wb") as dst:
            dst.write(src.read())
    return CACHE


def _domain(webaddr):
    """IPEDS web addresses are hand-entered and messy: bare hosts, full URLs, mixed
    case, stray whitespace, occasional 'www.' Normalise to a registrable-ish domain
    so it can be matched against schools.py."""
    s = (webaddr or "").strip().lower()
    if not s or s in ("-2", "na"):
        return ""
    s = re.sub(r"^https?://", "", s)
    s = s.split("/")[0].split("?")[0].strip()
    if s.startswith("www."):
        s = s[4:]
    return s if "." in s else ""


def _norm_name(name):
    """Collapse the spelling differences between IPEDS and schools.py: punctuation,
    'University of X' vs 'X University', and the noise words that differ per source."""
    n = (name or "").lower()
    n = re.sub(r"[^a-z0-9 ]+", " ", n)
    n = re.sub(r"\b(the|of|at|and|a)\b", " ", n)
    return re.sub(r"\s+", " ", n).strip()


def covered_index():
    """What schools.py already covers, as (domains, normalised-name tokens).

    Read as TEXT, not by importing: importing runs the registry guard and pulls in
    every adapter, which is slow and can fail for reasons that have nothing to do
    with this join. The file is the source of truth either way."""
    with open(os.path.join(REPO, "schools.py"), encoding="utf-8", errors="replace") as f:
        src = f.read()
    domains = set()
    # Match hosts ANYWHERE, including inside URLs. An earlier version required the
    # host to be quote-delimited, which missed every adapter that embeds a full URL
    # — including UMD's "https://app.testudo.umd.edu/soc/...", i.e. the very first
    # school this product ever supported showed up as uncovered.
    for host in re.findall(r"\b([a-z0-9][a-z0-9-]*(?:\.[a-z0-9-]+)*\.(?:edu|com|org|net))\b", src):
        parts = host.split(".")
        if len(parts) >= 2:
            domains.add(".".join(parts[-2:]))          # registrable domain
            domains.add(host)
    names = set()
    for nm in re.findall(r"name\s*=\s*[\"']([^\"']{4,80})[\"']", src):
        names.add(_norm_name(nm))
    return domains, names, src.lower()


def gap(rows, domains, names, raw_src):
    out = []
    for r in rows:
        if r.get("CYACTIVE", "1") != "1":              # closed / inactive
            continue
        if (r.get("DEATHYR") or "-2") not in ("-2", ""):
            continue
        lvl = r.get("ICLEVEL", "")
        if lvl not in ("1", "2"):                      # skip <2-year certificate mills
            continue
        dom = _domain(r.get("WEBADDR"))
        if not dom:
            continue
        reg = ".".join(dom.split(".")[-2:])
        nm = _norm_name(r.get("INSTNM"))
        # Three independent ways to already have it: exact host, registrable domain,
        # or the name appearing anywhere in schools.py. Any hit means skip — the
        # dedup-by-NAME lesson (UNC Charlotte handed off three times) says a domain
        # check alone is not enough.
        if dom in domains or reg in domains:
            continue
        if nm and (nm in names or nm in raw_src):
            continue
        out.append({
            "name": r.get("INSTNM", "").strip(),
            "state": r.get("STABBR", "").strip(),
            "domain": dom,
            "level": ICLEVEL.get(lvl, "?"),
            "control": CONTROL.get(r.get("CONTROL", ""), "?"),
            "size": INSTSIZE.get(r.get("INSTSIZE", ""), "unknown"),
            "_rank": (SIZE_RANK.get(r.get("INSTSIZE", ""), 9),
                      0 if lvl == "1" else 1,          # 4-year first, per the standing priority
                      r.get("INSTNM", "")),
        })
    out.sort(key=lambda x: x["_rank"])
    for x in out:
        del x["_rank"]
    return out


def main():
    ap = argparse.ArgumentParser(description="IPEDS coverage gap for SeatWatch")
    ap.add_argument("--limit", type=int, default=60)
    ap.add_argument("--csv", help="write the FULL ranked gap to this file")
    ap.add_argument("--refresh", action="store_true", help="re-download the IPEDS file")
    ap.add_argument("--state", help="restrict to one state code, e.g. MD")
    a = ap.parse_args()

    path = fetch(force=a.refresh)
    with open(path, encoding="latin-1") as f:
        rows = list(csv.DictReader(f))
    domains, names, raw = covered_index()
    missing = gap(rows, domains, names, raw)
    if a.state:
        missing = [m for m in missing if m["state"] == a.state.upper()]

    print("\nIPEDS 2023: %d institutions · degree-granting 2yr+ with a usable web "
          "address and not already in schools.py: %d" % (len(rows), len(missing)))
    by_size = {}
    for m in missing:
        by_size[m["size"]] = by_size.get(m["size"], 0) + 1
    print("uncovered by size band: " + ", ".join(
        "%s=%d" % (k, by_size.get(k, 0)) for k in ("20k+", "10k-20k", "5k-10k", "1k-5k", "<1k")))
    big = sum(by_size.get(k, 0) for k in ("20k+", "10k-20k", "5k-10k"))
    print("uncovered with 5,000+ students: %d  <- the only pool worth working first\n" % big)

    print("%-52s %-3s %-9s %-18s %s" % ("INSTITUTION", "ST", "SIZE", "LEVEL/CONTROL", "DOMAIN"))
    print("-" * 118)
    for m in missing[:a.limit]:
        print("%-52s %-3s %-9s %-18s %s"
              % (m["name"][:52], m["state"], m["size"],
                 "%s %s" % (m["level"], m["control"][:9]), m["domain"]))

    if a.csv:
        with open(a.csv, "w", newline="") as f:
            w = csv.DictWriter(f, fieldnames=["name", "state", "domain", "level",
                                              "control", "size"])
            w.writeheader()
            w.writerows(missing)
        print("\nfull ranked gap written to %s (%d rows)" % (a.csv, len(missing)))


if __name__ == "__main__":
    main()
