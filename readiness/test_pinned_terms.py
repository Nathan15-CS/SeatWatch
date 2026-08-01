"""READINESS #7 — Pinned-term schools must still serve live data (dead-listing guard).

Most schools auto-roll their term. A minority are PINNED (auto_term=False) because their
host exposes a trap the picker would fall into — a View-Only future term, a med-school or
"Extension" sub-population, a quarter calendar. Pinning is correct, but it cannot self-heal:
at semester rollover a pinned school keeps asking for a term that has ENDED and silently
returns nothing forever.

The runtime health guard does NOT cover this: it only alarms for courses a user is actively
watching, so a school with no watchers can go dead unnoticed. That is exactly how a listed
school becomes a lie (the reason Princeton was removed).

This checks every pinned school still returns sections for its example course. It hits the
real hosts, so it is the slowest suite — but it is the only thing standing between a
rollover and a silently dead school.
"""
import os, sys, re, urllib.request, urllib.error, concurrent.futures as cf

_UA = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
       "(KHTML, like Gecko) Chrome/126 Safari/537.36")
_MAINT = re.compile(r"down for maintenance|scheduled (?:downtime|maintenance)|"
                    r"temporarily unavailable|under maintenance", re.I)


def _probe(url, timeout=15):
    """(status, text). An HTTP error code is an ANSWER, not a failure, so it is returned."""
    try:
        req = urllib.request.Request(url, headers={"User-Agent": _UA})
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return r.status, r.read(4000).decode("utf-8", "replace")
    except urllib.error.HTTPError as e:
        try:
            return e.code, e.read(4000).decode("utf-8", "replace")
        except Exception:
            return e.code, ""
    except Exception as e:
        return type(e).__name__, ""


def _diagnose(s):
    """Why is this pinned school serving nothing?

    The default guess used to be 'the term rolled past its pin'. That is the most COMMON
    cause, but stating it as the cause when the host is simply down sends whoever reads this
    report to edit a term code that was never wrong. A monitor that misnames the fault is
    worse than one that says 'I don't know', because it is confidently wrong.
    """
    try:
        url = s.reg_url(getattr(s, "example", "") or "")
    except Exception:
        return "0 sections, and the adapter could not even build a registration URL"
    if not (url or "").startswith("http"):
        return "0 sections — term likely rolled past its pin"

    status, body = _probe(url)
    origin = "/".join(url.split("/")[:3])
    root_status, root_body = _probe(origin)

    if _MAINT.search(body) or _MAINT.search(root_body):
        return f"HOST IN MAINTENANCE ({origin}) — their outage, not a stale pin; recheck later"
    if isinstance(status, str):
        return f"host unreachable ({status} on {origin}) — network/DNS, not a stale pin"
    if status == 404 and root_status == 200:
        return (f"route is GONE (404) but {origin} answers — the school likely moved "
                f"platforms; this adapter needs re-research, not a term bump")
    if status >= 500:
        return f"host erroring (HTTP {status} on {origin}) — their fault, not a stale pin"
    return f"0 sections and the host is HEALTHY (HTTP {status}) — term rolled past its pin"


def run():
    sys.path.insert(0, os.path.expanduser("~/seatwatch"))
    import schools
    S = schools.SCHOOLS
    pinned = [s for s in S.values() if getattr(s, "auto_term", True) is False]
    results = []

    def check(s):
        try:
            r = {k: v for k, v in s.fetch([s.example]).get(s.example, {}).items() if k != "none"}
            if r:
                return (s.name, len(r), None)
            # Adapters fail CLOSED — most swallow errors and return {}. So an empty result
            # is ambiguous by construction, and the only way to tell a rolled term from a
            # dead host is to go ask the host. Only runs on failure, so it costs nothing
            # in the normal case.
            return (s.name, 0, _diagnose(s))
        except Exception as e:
            return (s.name, 0, f"{type(e).__name__}: {e}"[:90])

    with cf.ThreadPoolExecutor(7) as ex:
        rows = sorted(ex.map(check, pinned))

    for name, n, err in rows:
        results.append((f"pinned school still live: {name[:38]}", n > 0, f"({err})" if err else ""))

    # A pinned school is a standing maintenance obligation; make the count visible so it
    # can't quietly grow without anyone owning the bumps.
    results.append((f"pinned-school count is tracked ({len(pinned)} need manual term bumps)",
                    True, ""))

    p = sum(ok for _, ok, _ in results)
    f = sum(not ok for _, ok, _ in results)
    return p, f, results


if __name__ == "__main__":
    import warnings; warnings.filterwarnings("ignore")
    p, f, res = run()
    for name, ok, detail in res:
        print(f"  [{'PASS' if ok else '*** FAIL'}] {name}{('  ' + detail) if detail and not ok else ''}")
    print(f"\n  {p} passed, {f} failed")
    sys.exit(1 if f else 0)
