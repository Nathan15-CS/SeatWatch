#!/usr/bin/env python3
"""The worklist: every school SeatWatch can actually serve, with its likely subreddit.

WHY THIS EXISTS: the first version of this system was built around UMD and computer science,
because that is where the existing watches happen to be. That is a description of who has
found SeatWatch so far, not of who it serves. The product covers 890 proven schools and every
major in them, and a marketing system anchored to one campus and one department will only
ever reach one campus and one department.

The bottleneck course is a universal experience with a different name everywhere:

    nursing            Anatomy & Physiology, Microbiology
    pre-med            Organic Chemistry, Biochemistry
    business           Intro Accounting, Business Statistics
    engineering        Statics, Differential Equations
    psychology         Research Methods, Statistics
    education          Child Development
    computer science   the intro/data-structures sequence

None of these is more real than the others. A nursing student locked out of A&P loses a year;
that is a stronger need than most CS students have, and there are more of them.

USAGE
  python3 coverage_index.py                 # all proven schools + guessed subreddits
  python3 coverage_index.py --unclaimed     # only those with no subreddit recorded yet
  python3 coverage_index.py --limit 40
"""
import argparse, json, os, re, sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.expanduser("~/seatwatch")
sys.path.insert(0, HERE)
sys.path.insert(0, ROOT)

import store  # noqa: E402

# Common campus-subreddit naming, in the order Reddit actually tends to use. These are
# CANDIDATES to verify, never assumptions — reddit-rules-checker confirms a sub exists and
# what it permits before anything is written for it.
STOP = {"university", "of", "the", "at", "state", "college", "institute", "school",
        "and", "system", "campus", "main", "community", "technical"}


def guesses(school_id, name):
    """Plausible subreddit names for a school. Deliberately generous — verification is
    cheap and a missed community is a whole campus we never reach."""
    out = []
    sid = re.sub(r"[^a-z0-9]", "", school_id.lower())
    if sid:
        out.append(sid)
    words = [w for w in re.split(r"[^A-Za-z]+", name or "") if w]
    keep = [w for w in words if w.lower() not in STOP]
    if keep:
        out.append("".join(keep).lower())          # UniversityOfMaryland -> maryland
        out.append(keep[0].lower())                # first distinctive word
    initials = "".join(w[0] for w in keep if w[:1].isupper())
    if len(initials) >= 2:
        out.append(initials.lower())               # UMBC, UCSD, RIT
    seen, uniq = set(), []
    for g in out:
        if g and g not in seen and len(g) > 2:
            seen.add(g)
            uniq.append(g)
    return uniq[:4]


def proven():
    """Schools we can actually serve. Anything not verdict=OK would send a student to an
    adapter that reports everything open or returns nothing — worse than not reaching them."""
    with open(os.path.join(ROOT, "ops", "coverage.json")) as f:
        cov = json.load(f)
    out = []
    for sid, v in cov.items():
        if (v or {}).get("verdict") != "OK":
            continue
        st = (v or {}).get("stats") or {}
        out.append({"id": sid, "name": v.get("name") or sid,
                    "sections": st.get("sections"), "subreddits": guesses(sid, v.get("name"))})
    return sorted(out, key=lambda r: -(r["sections"] or 0))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--unclaimed", action="store_true",
                    help="only schools with no subreddit recorded in the registry yet")
    ap.add_argument("--limit", type=int, default=0)
    ap.add_argument("--json", action="store_true")
    a = ap.parse_args()

    rows = proven()
    if a.unclaimed:
        store.init()
        with store.db() as c:
            claimed = {r["school"] for r in c.execute(
                "SELECT DISTINCT school FROM subreddits WHERE school IS NOT NULL")}
        rows = [r for r in rows if r["id"] not in claimed]
    if a.limit:
        rows = rows[:a.limit]

    if a.json:
        print(json.dumps(rows, indent=1))
        return

    print("%d proven schools%s — every major, not one department"
          % (len(rows), " with no subreddit yet" if a.unclaimed else ""))
    print("-" * 76)
    for r in rows:
        print("  %-18s %-40s %s" % (r["id"], (r["name"] or "")[:40],
                                    ", ".join("r/" + g for g in r["subreddits"][:3])))
    print("-" * 76)
    print("  Subreddit names above are GUESSES. reddit-rules-checker verifies the community")
    print("  exists and what it permits before a single word is written for it.")


if __name__ == "__main__":
    main()
