#!/usr/bin/env python3
"""
SeatWatch Reliability Confidence Engine — deterministic, evidence-only.

Answers a different question than GREEN/YELLOW/RED health: "how strong is our
evidence that a real seat opening would have reached the student?"

The output is the Reliability Confidence Index (RCI, 0-100). It is NOT a
probability — nobody can measure the odds of catching an opening without
ground truth about openings missed. It is measured evidence strength for
every link in the chain that must hold (scheduled ∧ fetched ∧ parsed ∧
term-valid ∧ section-visible ∧ delivered), and every report saying "RCI"
carries that caveat.

Design rules (approved Phase B):
  * Weakest link: a score is the MINIMUM of its factors, never an average —
    averages manufacture comfort. The argmin is recorded as the "binding"
    factor, so "why is confidence X / what do I fix next" is a stored fact.
  * Unknown is never high: a factor with no evidence scores 0 (or a stated
    low cap for "enrolled but unproven"), and it binds.
  * Earned, not granted: tenure/streak factors start low and grow only with
    verified operation; they reset on anomaly.
  * Stale evidence decays: every factor embeds a freshness rule; quiet is not
    the same as healthy.
  * Structural caps encode unfixed risks (empty term stamps, ntfy-only
    delivery, unidentified deployed SHA, ntfy-only fire drill) and are lifted
    only by the evidence that removes the risk — never by time passing.

Pure functions over an evidence dict; all SQL lives in gather_evidence().
No imports from app/guardian (guardian imports us), nothing here can raise
into the poller (guardian wraps the call).
"""
import time

# Factor floors/caps — named so reports and tests speak the same language.
CAP_TERM_EMPTY = 20        # empty term stamp: staleness guard cannot protect it
CAP_TERM_UNKNOWABLE = 60   # school exposes no term signal at all (srcdb families)
CAP_ENROLLED_UNPROVEN = 55  # push/email enrolled but no delivery evidence yet
CAP_NTFY_ONLY = 40         # ntfy-topic-only account: no proven human channel
CAP_NO_DEPLOY_ID = 40      # deployed SHA unknown -> system evidence capped
CAP_DRILL_NTFY_LEG = 70    # fire drill proves ntfy only; push leg is V1.1
CAP_STALE = 40             # evidence exists but is older than its TTL
CAP_DIVERGENCE = 50        # unexplained shadow divergences pending human review
CAP_INSUFFICIENT = 55      # too few samples to trust a rate

TIERS = ((85, "HIGH"), (70, "GOOD"), (50, "MODERATE"), (25, "LOW"), (0, "MINIMAL"))


def tier(score):
    for floor, name in TIERS:
        if score >= floor:
            return name
    return "MINIMAL"


def compose(factors):
    """(score, tier, binding) = weakest link of the named factors.
    Factors with value None are treated as 0 (unknown is never high)."""
    if not factors:
        return 0, "MINIMAL", "no_evidence"
    norm = {k: (0 if v is None else max(0, min(100, int(v)))) for k, v in factors.items()}
    binding = min(norm, key=lambda k: (norm[k], k))
    score = norm[binding]
    return score, tier(score), binding


# ------------------------------------------------------------ gather (SQL)
def gather_evidence(c, cycle, now, tuning, deploy_sha="", drill_age_s=None,
                    telemetry_faults=0, divergences=0):
    """Pull everything compute() needs from the guardian tables in one place.
    Only reads; tolerates missing optional tables (alert_log pre-deploy)."""
    poll_s = tuning.get("POLL_S", 20)
    win0 = now - tuning["RATE_WINDOW_S"]
    ev = {"now": now, "poll_s": poll_s, "deploy_sha": deploy_sha,
          "drill_age_s": drill_age_s, "telemetry_faults": telemetry_faults,
          "divergences": divergences, "watches": {}, "adapters": {},
          "cycles": [], "undelivered_24h": 0, "delivered_24h": 0}
    for r in c.execute("SELECT started, finished, expected, accounted, status "
                       "FROM guardian_cycles WHERE finished IS NOT NULL "
                       "ORDER BY finished DESC LIMIT 200"):
        ev["cycles"].append(dict(r))
    for r in c.execute("SELECT * FROM guardian_adapter_health"):
        ev["adapters"][r["school"]] = dict(r)
    watch_rows = {r["id"]: r for r in c.execute(
        "SELECT id, user_id, school, term, alerted FROM watches")}
    for wid, ident in cycle.expected.items():
        w = watch_rows.get(wid)
        hist = [dict(h) for h in c.execute(
            "SELECT outcome, adapter_term, created FROM guardian_watch_results "
            "WHERE watch_id=? AND created>? ORDER BY created DESC LIMIT 200",
            (wid, win0))]
        uid = ident.get("user_id")
        has_push = has_email = push_proof = False
        if uid:
            has_push = c.execute("SELECT 1 FROM push_subs WHERE user_id=? LIMIT 1",
                                 (uid,)).fetchone() is not None
            u = c.execute("SELECT email FROM users WHERE id=?", (uid,)).fetchone()
            has_email = bool(u and u["email"])
            try:
                push_proof = c.execute(
                    "SELECT 1 FROM alert_log WHERE user_id=? AND channel IN "
                    "('webpush','webpush_test','email','sms') LIMIT 1",
                    (uid,)).fetchone() is not None
            except Exception:
                push_proof = False           # alert_log absent (pre-deploy DB)
        ev["watches"][wid] = {
            "ident": ident, "exists": w is not None,
            "alerted": (w["alerted"] if w else 0),
            "term": ident.get("term") or "",
            "school": ident.get("school"), "history": hist,
            "has_push": has_push, "has_email": has_email, "push_proof": push_proof,
        }
    try:
        day0 = now - 86400
        ev["delivered_24h"] = c.execute(
            "SELECT COUNT(*) FROM guardian_watch_results WHERE "
            "outcome='alert_delivered' AND created>?", (day0,)).fetchone()[0]
        ev["undelivered_24h"] = c.execute(
            "SELECT COUNT(*) FROM guardian_watch_results WHERE "
            "outcome='alert_undelivered' AND created>?", (day0,)).fetchone()[0]
    except Exception:
        pass
    return ev


# ------------------------------------------------------------ factors
_GOOD = ("checked_no_change", "checked_open_latched", "checked_open_already",
         "checked_closed_reset", "alert_delivered")


def watch_factors(w, ev):
    now, poll = ev["now"], ev["poll_s"]
    hist = w["history"]
    f = {}
    # W1 coverage: share of recorded cycles that truly checked the watch, and
    # how recently a successful check happened.
    if not hist:
        f["W1_coverage"] = 0                     # brand new / never seen: unproven
    else:
        good = [h for h in hist if h["outcome"] in _GOOD]
        rate = int(100 * len(good) / len(hist))
        age = now - good[0]["created"] if good else None
        if age is None:
            f["W1_coverage"] = 0
        elif age > 3600:
            f["W1_coverage"] = min(rate, 10)
        elif age > 10 * poll:
            f["W1_coverage"] = min(rate, CAP_STALE)
        else:
            f["W1_coverage"] = rate
    # W2 cadence: observed gaps between consecutive results for this watch.
    if len(hist) < 5:
        f["W2_cadence"] = 25                     # insufficient cadence evidence
    else:
        gaps = [hist[i]["created"] - hist[i + 1]["created"] for i in range(len(hist) - 1)]
        gaps.sort()
        # worst-case-biased p95: at small n this reaches the max gap, so a single
        # multi-hour blackout sinks the score — quiet is not the same as healthy
        p95 = gaps[min(len(gaps) - 1, int(len(gaps) * 0.95))]
        f["W2_cadence"] = 100 if p95 <= 2 * poll else 70 if p95 <= 5 * poll \
            else 40 if p95 <= 30 * poll else 15
    # W3 term validity: from what the cycle actually recorded.
    last = hist[0] if hist else None
    if last and last["outcome"] == "blocked_wrong_term":
        f["W3_term"] = 0
    elif not w["term"]:
        f["W3_term"] = CAP_TERM_EMPTY
    elif last and last.get("adapter_term") is None:
        f["W3_term"] = CAP_TERM_UNKNOWABLE
    else:
        f["W3_term"] = 100
    # W4 adapter evidence: inherited school score (computed by caller).
    f["W4_adapter"] = ev.get("_adapter_scores", {}).get(w["school"], 0)
    # W5 section visibility: a current section_missing streak is a silent-miss
    # in progress — exactly the failure class that used to be invisible.
    streak = 0
    for h in hist:
        if h["outcome"] == "section_missing":
            streak += 1
        else:
            break
    f["W5_section"] = 100 if streak == 0 else max(0, 100 - 30 * streak)
    # W6 delivery provability.
    if not w["exists"]:
        f["W6_delivery"] = 0
    elif w["push_proof"]:
        f["W6_delivery"] = 100
    elif w["has_push"] or w["has_email"]:
        f["W6_delivery"] = CAP_ENROLLED_UNPROVEN
    else:
        f["W6_delivery"] = CAP_NTFY_ONLY         # topic-only account, no human channel
    # W7 latch sanity: latched while the engine last saw the section closed
    # means the reset write was lost — future openings would never alert.
    if w["alerted"] == 1 and last and last["outcome"] == "checked_closed_reset":
        f["W7_latch"] = 30
    else:
        f["W7_latch"] = 100
    return f


def adapter_factors(a, ev):
    now = ev["now"]
    f = {}
    checks, fails = a["checks"] or 0, a["failures"] or 0
    if checks == 0:
        f["A1_success"] = 0
    else:
        rate = int(100 * (checks - fails) / checks)
        f["A1_success"] = min(rate, CAP_INSUFFICIENT) if checks < 10 else rate
    consec = a["consec_fail"] or 0
    f["A2_streak"] = 100 if consec == 0 else 60 if consec <= 2 else 30 if consec <= 4 else 0
    avg = a["avg_ms"] or 0
    f["A3_latency"] = 100 if avg <= 5000 else 70 if avg <= 15000 else 40 if avg <= 30000 else 15
    f["A6_sanity"] = max(0, 100 - 25 * (a["sanity_violations"] or 0))
    clean_days = max(0.0, (now - (a["clean_since"] or now)) / 86400)
    f["A7_tenure"] = min(100, int(40 + clean_days * 4))
    if a["last_ok"] and now - a["last_ok"] > 3600:
        f["A8_recency"] = 25                     # no successful fetch in an hour
    elif not a["last_ok"]:
        f["A8_recency"] = 0
    else:
        f["A8_recency"] = 100
    return f


def system_factors(ev, worst_watch_score):
    now, poll = ev["now"], ev["poll_s"]
    f = {}
    f["P0_deploy_identity"] = 100 if ev["deploy_sha"] else CAP_NO_DEPLOY_ID
    streak = 0
    for cyc in ev["cycles"]:
        if cyc["accounted"] == cyc["expected"] and cyc["status"] != "RED":
            streak += 1
        else:
            break
    f["P1_reconciliation"] = 0 if not ev["cycles"] else \
        (0 if streak == 0 else min(100, 30 + streak))
    if ev["undelivered_24h"]:
        f["P2_pipeline"] = 30
    elif ev["delivered_24h"]:
        f["P2_pipeline"] = 100
    else:
        f["P2_pipeline"] = 70                    # no attempts either way: unproven
    fins = [cyc["finished"] for cyc in ev["cycles"][:60]]
    if len(fins) < 3:
        f["P3_continuity"] = 25
    else:
        maxgap = max(fins[i] - fins[i + 1] for i in range(len(fins) - 1))
        f["P3_continuity"] = 100 if maxgap <= 3 * poll else 60 if maxgap <= 30 * poll else 30
    tf = ev["telemetry_faults"]
    f["P4_telemetry"] = 100 if tf == 0 else 60 if tf <= 3 else 25
    da = ev["drill_age_s"]
    if da is None:
        f["P5_verification"] = 40
    elif da <= 8 * 86400:
        f["P5_verification"] = CAP_DRILL_NTFY_LEG   # drill proves the ntfy leg only
    elif da <= 15 * 86400:
        f["P5_verification"] = 50
    else:
        f["P5_verification"] = 30
    first = ev["cycles"][-1]["started"] if ev["cycles"] else now
    days = (now - first) / 86400
    maturity = min(100, int(20 + days * 10))
    f["P6_maturity"] = min(maturity, CAP_DIVERGENCE) if ev["divergences"] else maturity
    f["P7_watches"] = worst_watch_score if ev["watches"] else 100
    return f


# ------------------------------------------------------------ compute
def compute(ev, tuning):
    """-> {"snapshots": [(etype, eid, score, tier, binding, factors)...],
          "summary": {...}}   Deterministic; safe on empty evidence."""
    snapshots = []
    adapter_scores = {}
    for school, a in sorted(ev["adapters"].items()):
        fa = adapter_factors(a, ev)
        s, t, b = compose(fa)
        adapter_scores[school] = s
        snapshots.append(("adapter", school, s, t, b, fa))
    ev["_adapter_scores"] = adapter_scores
    worst_watch, worst_id = 100, None
    for wid, w in sorted(ev["watches"].items()):
        fw = watch_factors(w, ev)
        s, t, b = compose(fw)
        if s <= worst_watch:
            worst_watch, worst_id = s, wid
        snapshots.append(("watch", str(wid), s, t, b, fw))
    fs = system_factors(ev, worst_watch if ev["watches"] else 100)
    s, t, b = compose(fs)
    snapshots.append(("system", "system", s, t, b, fs))
    return {"snapshots": snapshots,
            "summary": {"system_rci": s, "tier": t, "binding": b,
                        "watches": len(ev["watches"]),
                        "worst_watch_id": worst_id, "worst_watch_rci": worst_watch,
                        "note": "RCI = measured evidence strength, not a probability"}}
