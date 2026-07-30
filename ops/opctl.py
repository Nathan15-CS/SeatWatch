#!/usr/bin/env python3
"""
opctl — the typed boundary between the Operator and model-bearing workers.

Everything in and out is JSON on stdout, so an LLM worker session can drive it
without parsing prose, and every exchange is auditable afterwards.

    # Manager
    opctl.py objective-create --id fall-coverage --title "..." --kind school_research --target 5
    opctl.py objective-activate --id fall-coverage --budget 10     # the spending decision
    opctl.py enqueue --objective fall-coverage --key towson
    opctl.py status

    # Worker (Grab / Build / Critic)
    opctl.py claim --role grab --holder grab-session-1
    opctl.py complete --item 7 --holder grab-session-1 --result-file /tmp/r.json
    opctl.py fail --item 7 --holder grab-session-1 --reason "host unreachable"
    opctl.py review --item 7 --kind certification --reviewer critic --evidence-file /tmp/e.json

Exit codes: 0 success · 2 contract violation (fail closed) · 3 nothing to do.

A note on trust. `complete` takes the worker's result and validates it against the
kind's contract before the system believes any of it. A verdict is an enum; text
scraped from a university's website cannot become one. That check is the reason this
CLI exists rather than letting workers write the database directly.
"""
import argparse
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import objectives as O          # noqa: E402
import operator_engine as E     # noqa: E402

EXIT_OK, EXIT_CONTRACT, EXIT_EMPTY = 0, 2, 3


def _out(obj, code=EXIT_OK):
    print(json.dumps(obj, indent=2, default=str))
    return code


def _load(path, what):
    if not path:
        raise O.ContractError("--%s is required" % what)
    with open(path) as f:
        return json.load(f)


def _conn():
    E.init_db()
    c = E._connect()
    O.init_schema(c)
    c.commit()
    return c


def main(argv=None):
    ap = argparse.ArgumentParser(prog="opctl", description="Operator work queue")
    sub = ap.add_subparsers(dest="cmd", required=True)

    p = sub.add_parser("objective-create")
    p.add_argument("--id", required=True)
    p.add_argument("--title", required=True)
    p.add_argument("--kind", required=True, choices=sorted(O.ROUTES))
    p.add_argument("--target", type=int, required=True)
    p.add_argument("--dry-well-limit", type=int, default=3)

    p = sub.add_parser("objective-activate")
    p.add_argument("--id", required=True)
    p.add_argument("--budget", type=int, required=True,
                   help="hard cap on work items; activation IS the spending decision")

    p = sub.add_parser("objective-stop")
    p.add_argument("--id", required=True)
    p.add_argument("--reason", required=True)

    p = sub.add_parser("enqueue")
    p.add_argument("--objective", required=True)
    p.add_argument("--key", required=True, help="natural idempotency key, e.g. a school slug")
    p.add_argument("--payload-file")

    p = sub.add_parser("claim")
    p.add_argument("--role", required=True)
    p.add_argument("--holder", required=True)
    p.add_argument("--ttl", type=int, default=O.DEFAULT_CLAIM_TTL_S)

    p = sub.add_parser("complete")
    p.add_argument("--item", type=int, required=True)
    p.add_argument("--holder", required=True)
    p.add_argument("--result-file", required=True)

    p = sub.add_parser("fail")
    p.add_argument("--item", type=int, required=True)
    p.add_argument("--holder", required=True)
    p.add_argument("--reason", required=True)

    p = sub.add_parser("review")
    p.add_argument("--item", type=int, required=True)
    p.add_argument("--kind", required=True, choices=O.REVIEW_KINDS)
    p.add_argument("--reviewer", required=True)
    p.add_argument("--evidence-file", required=True)

    p = sub.add_parser("show")
    p.add_argument("--objective", required=True)

    sub.add_parser("status")
    sub.add_parser("routes")

    a = ap.parse_args(argv)
    c = _conn()
    try:
        if a.cmd == "routes":
            return _out({"routes": O.ROUTES, "verdicts": list(O.VERDICTS),
                         "contracts": O.RESULT_CONTRACTS})

        if a.cmd == "objective-create":
            o = O.create_objective(c, a.id, a.title, a.kind, a.target,
                                   dry_well_limit=a.dry_well_limit)
            c.commit()
            return _out({"created": dict(o),
                         "note": "born proposed with budget 0 — no work can be queued "
                                 "until a human activates it with an explicit budget"})

        if a.cmd == "objective-activate":
            o = O.activate_objective(c, a.id, a.budget)
            c.commit()
            return _out({"activated": dict(o)})

        if a.cmd == "objective-stop":
            o = O.stop_objective(c, a.id, a.reason)
            c.commit()
            return _out({"stopped": dict(o)})

        if a.cmd == "enqueue":
            payload = _load(a.payload_file, "payload-file") if a.payload_file else {}
            it = O.enqueue(c, a.objective, a.key, payload)
            c.commit()
            if it is None:
                return _out({"duplicate": a.key,
                             "note": "already queued under this objective; no-op"})
            return _out({"queued": dict(it)})

        if a.cmd == "claim":
            it = O.claim(c, a.role, a.holder, ttl_s=a.ttl)
            c.commit()
            if it is None:
                return _out({"item": None, "note": "nothing to claim"}, EXIT_EMPTY)
            d = dict(it)
            d["payload"] = json.loads(d.get("payload") or "{}")
            d["contract"] = O.RESULT_CONTRACTS.get(it["kind"])
            return _out({"item": d})

        if a.cmd == "complete":
            state, detail = O.complete(c, a.item, a.holder, _load(a.result_file, "result-file"))
            c.commit()
            if state == "failed":
                # Contract violation: recorded, evidence kept, NOT retried.
                return _out({"item": a.item, "state": state, "error": detail,
                             "note": "failed closed — the result did not satisfy the "
                                     "contract, so nothing was believed"}, EXIT_CONTRACT)
            return _out({"item": a.item, "state": state, "detail": detail})

        if a.cmd == "fail":
            state, reason = O.fail(c, a.item, a.holder, a.reason)
            c.commit()
            return _out({"item": a.item, "state": state, "reason": reason})

        if a.cmd == "review":
            state, detail = O.review(c, a.item, a.kind, a.reviewer,
                                     _load(a.evidence_file, "evidence-file"))
            c.commit()
            return _out({"item": a.item, "state": state, "detail": detail})

        if a.cmd == "show":
            rep = O.objective_report(c, a.objective)
            return _out(rep) if rep else _out({"error": "no such objective"}, EXIT_CONTRACT)

        if a.cmd == "status":
            return _out({"objectives": O.all_objectives(c)})

    except O.ContractError as e:
        c.rollback()
        return _out({"error": str(e), "fail_closed": True}, EXIT_CONTRACT)
    finally:
        c.close()
    return EXIT_OK


if __name__ == "__main__":
    raise SystemExit(main())
