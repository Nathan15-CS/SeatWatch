#!/usr/bin/env python3
"""Has the next semester been published yet? Ask the schools, don't guess the date.

    python3 ops/spring-watch.py                     the schools students actually use
    python3 ops/spring-watch.py --all               a sample across the whole registry
    python3 ops/spring-watch.py --season Fall --year 2027

WHY THIS EXISTS. The plan for a paid promotion was "late October", which is a guess about
900 registrars' calendars. On 2026-09-03 UMD's published term list still ended at Fall
2026 and Spring 2027 CMSC216 returned zero sections — so a campaign that day would have
sent students to a product that answers "couldn't find that course this term". That is the
worst first impression SeatWatch can make, and the student is gone before the funnel can
record why.

The trigger is not a date. It is an event this can observe: the school publishing a Spring
schedule with real seat data. Run it weekly through October; spend money when it says READY.

THREE OUTCOMES, deliberately distinct:
    READY        the term is listed AND the example course returns real sections
    LISTED       the term exists but has no live data yet — published, not loaded
    NOT PUBLISHED the school does not offer that term at all yet
    CANNOT CHECK the adapter errored. NOT the same as "not published", and never
                 reported as one — a network failure must not read as a calendar fact.

EXIT CODES
    0  at least one target is READY
    1  nothing ready yet (normal until October)
    2  nothing could be checked at all
"""
import argparse
import os
import re
import sys
import warnings

warnings.filterwarnings("ignore")
sys.path.insert(0, os.path.expanduser("~/seatwatch"))

# Schools where watches actually exist today. A campaign aimed anywhere else is aimed at
# a school whose readiness nobody has verified.
DEFAULT_TARGETS = ["umd", "towson"]


def _term_labels(school):
    """[(code, label)] however this adapter can supply it; None if it genuinely cannot.

    Adapters answer this two different ways and the first version only knew one, so
    Towson — a school with real students on it — reported CANNOT CHECK with a bare
    AttributeError. The TermAutoRoll family exposes term_options(); the PeopleSoft family
    has no such method but publishes the same list at its ClassSearchOptions endpoint,
    which is precisely where its own resolve_term() reads. Asking each adapter the way it
    can answer beats reporting 'unknown' about a school we simply asked wrongly.
    """
    fn = getattr(school, "term_options", None)
    if callable(fn):
        try:
            return fn() or []
        except Exception:
            return None
    if hasattr(school, "_session") and hasattr(school, "_cs"):
        try:
            import json
            op = school._session()
            url = (school._cs() + ".IScript_ClassSearchOptions?institution=" + school.inst)
            d = json.loads(op.open(url, timeout=25).read().decode("utf-8", "replace"))
            return [(t.get("strm") or "", t.get("descr") or "") for t in d.get("terms", [])]
        except Exception:
            return None
    return None


def _set_term(school, code):
    """Point an adapter at a term for one probe. Returns a restore callable."""
    for attr in ("_active_term", "term"):
        if hasattr(school, attr):
            prev = getattr(school, attr)
            setattr(school, attr, code)
            return lambda: setattr(school, attr, prev)
    return lambda: None


def probe(school, season, year):
    """(verdict, detail). Never raises — an adapter blowing up is CANNOT CHECK."""
    label_re = re.compile(r"\b%s\s+%s\b" % (season, year), re.I)
    code = None
    opts = _term_labels(school)
    if opts is None:
        return "CANNOT CHECK", "no readable term list for this adapter"
    if not opts:
        # An empty list is not evidence of anything. Saying "NOT PUBLISHED" here would be
        # a confident statement about a school we never actually got an answer from.
        return "CANNOT CHECK", "adapter returned an empty term list"
    for c, lab in opts:
        if label_re.search(lab or ""):
            code = c
            break
    if not code:
        newest = (opts[-1][1] if opts else "?")
        return "NOT PUBLISHED", "newest term offered: %s" % newest

    # Listed is not the same as loaded. A term code can exist for weeks before the
    # schedule behind it has any sections, and a student watching an empty term hears
    # nothing forever.
    restore = _set_term(school, code)
    try:
        data = school.fetch({school.example}) or {}
        secs = {k: v for k, v in data.get(school.example, {}).items() if k != "none"}
    except Exception as e:
        return "CANNOT CHECK", "term %s listed, fetch failed: %s" % (code, type(e).__name__)
    finally:
        restore()          # ALWAYS — a probe must never leave the poller on a new term

    if not secs:
        return "LISTED", "term %s exists but %s has no sections yet" % (code, school.example)
    seated = sum(1 for v in secs.values() if v.get("seats") is not None)
    return "READY", "term %s — %d sections for %s (%d with seat counts)" % (
        code, len(secs), school.example, seated)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--season", default="Spring")
    ap.add_argument("--year", default="2027")
    ap.add_argument("--all", action="store_true",
                    help="sample across the registry, not just schools with watches")
    ap.add_argument("--limit", type=int, default=25)
    a = ap.parse_args()

    import ca_chain
    ca_chain.install()
    import schools as S

    targets = DEFAULT_TARGETS
    if a.all:
        rollers = [s.id for s in S.SCHOOLS.values() if hasattr(s, "term_options")]
        targets = sorted(set(DEFAULT_TARGETS) | set(rollers[:a.limit]))

    print("\n  IS %s %s PUBLISHED YET?  (%d school(s))\n" % (
        a.season.upper(), a.year, len(targets)))
    print("  %-14s %-14s %-14s %s" % ("school", "now serving", "verdict", "detail"))
    print("  " + "-" * 88)

    counts = {}
    for sid in targets:
        s = S.SCHOOLS.get(sid)
        if not s:
            print("  %-14s %-14s %-14s %s" % (sid, "-", "CANNOT CHECK", "not in registry"))
            counts["CANNOT CHECK"] = counts.get("CANNOT CHECK", 0) + 1
            continue
        try:
            now = s.cur_term()
        except Exception:
            now = "?"
        verdict, detail = probe(s, a.season, a.year)
        counts[verdict] = counts.get(verdict, 0) + 1
        print("  %-14s %-14s %-14s %s" % (sid, now, verdict, detail[:44]))

    ready = counts.get("READY", 0)
    print("\n  " + "  ".join("%s=%d" % (k, v) for k, v in sorted(counts.items())))
    if ready:
        print("\n  %d school(s) READY. The semester students will be shut out of is now"
              "\n  watchable — this is the window a promotion should aim at." % ready)
        return 0
    if counts.get("CANNOT CHECK", 0) == len(targets):
        print("\n  NOTHING could be checked. That is UNKNOWN, not 'not published yet'.")
        return 2
    print("\n  Not yet. Expected around October, when schools publish Spring and"
          "\n  AUTO_ROLL_TERMS moves the adapters. Re-run weekly; do not buy traffic"
          "\n  until at least your target school reads READY.")
    return 1


if __name__ == "__main__":
    sys.exit(main())
