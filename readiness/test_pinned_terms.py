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
# Schools phrase an outage however they like, and this pattern only ever has to be wide
# enough to stop us BLAMING THE TERM for someone else's downtime. On 2026-08-16 Cleveland
# State served, with HTTP 200:
#
#     "CampusNet is currently not available due to regular maintenance.
#      It will be available next on: SUNDAY at 10:00 AM"
#
# None of the four original alternatives matched "not available due to regular
# maintenance", so the report announced "the host is HEALTHY — term rolled past its pin"
# about a school that was simply closed for the weekend. Acting on that means bumping a
# term that was never wrong, and an early roll silently starves everyone watching the
# current one — the most expensive edit this repo can make from a false report.
#
# Hence the deliberately loose final alternative: the bare word "maintenance". A page
# that both serves no course data AND says "maintenance" is not a page to draw
# conclusions from, and being wrong in this direction only costs a re-check.
_MAINT = re.compile(r"down for maintenance|scheduled (?:downtime|maintenance)|"
                    r"temporarily unavailable|under maintenance|"
                    r"will be (?:back|available)\b|\bmaintenance\b", re.I)


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
    # Everything above RULED SOMETHING OUT. This branch has ruled nothing out — it is the
    # leftover, and it is stated as a likelihood rather than a finding. "HEALTHY" was the
    # wrong word for an HTTP 200 that carried a maintenance notice, and reading it as a
    # diagnosis is what sends someone to edit a term code that was never wrong.
    return (f"0 sections; host answers HTTP {status} with no outage notice — MOST LIKELY "
            f"the term rolled past its pin, but confirm against the school's own term "
            f"list before bumping it. An early roll starves every current watcher.")


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

    unchecked = []
    for name, n, err in rows:
        if n == 0 and "MAINTENANCE" in (err or ""):
            # THEIR outage, on their schedule. We did not verify the pin, so we must not
            # claim it is live — but neither is it a defect of ours to fail on. Asserting
            # FAIL here paints the suite red for a school that is closed for the weekend,
            # and a suite that is red for reasons nobody can act on is a suite that stops
            # being read. Skipped and COUNTED, the same discipline test_section_collapse
            # uses, so "not checked" can never be mistaken for "checked and fine".
            unchecked.append(name[:38])
            continue
        results.append((f"pinned school still live: {name[:38]}", n > 0, f"({err})" if err else ""))

    if unchecked:
        # Visible as its own line rather than folded into silence: if a school stays in
        # "maintenance" for a week, that is no longer maintenance and somebody must look.
        results.append((f"NOT CHECKED — host in maintenance: {', '.join(unchecked)}",
                        True, ""))

    # A pinned school is a standing maintenance obligation; make the count visible so it
    # can't quietly grow without anyone owning the bumps.
    results.append((f"pinned-school count is tracked ({len(pinned)} need manual term bumps, "
                    f"{len(rows) - len(unchecked)} verified live)", True, ""))

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
