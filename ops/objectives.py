#!/usr/bin/env python3
"""
SeatWatch Operator v2 — objectives, work items, and typed handoffs.

v1 keeps the system healthy. This layer keeps work moving: the Manager declares a
measurable objective, the Operator holds the queue and the arithmetic, and
model-bearing workers (Grab, Build, Critic) claim typed items and return typed
results. The Operator never calls a model.

THE DIVISION OF LABOUR (the whole design in four lines)
    Manager  decides WHAT should happen  -> writes an Objective
    Operator decides WHETHER work may proceed, and records what is TRUE
    Workers  decide HOW  -> judgment lives here, and only here
    Critic   decides whether the work is ACCEPTABLE -> certification or rejection

Everything in this file is deterministic: routing is a lookup table, budgets are
arithmetic, progress is a COUNT over evidence rows. That is deliberate. The Operator
is the component that answers "what is true", and a probabilistic answer to that
question is not an answer. `guardian.py` states the same rule for the same reason:
"An LLM is never consulted for anything in this file."

FAIL-CLOSED (the rule that outranks throughput)
    A malformed result, an unknown work kind, an unroutable item, or any condition
    this file does not have an explicit branch for does NOT get improvised around.
    It stops, keeps the evidence, and raises a finding for a human. Novel situations
    are exactly where an autonomous system should be least creative.

Python 3.9+, stdlib only. Shares operator.db with the engine.
"""
import json
import re
import time

# --------------------------------------------------------------- vocabulary
OBJ_STATES = ("proposed", "active", "met", "stopped", "cancelled")
ITEM_STATES = ("queued", "claimed", "done", "ready_for_build",
               "rejected", "failed", "cancelled")
VERDICTS = ("BUILD", "SCRAP", "NEEDS-HUMAN")
REVIEW_KINDS = ("certification", "rejection")

# Deterministic routing. A work kind maps to exactly one role — no judgement, no
# model, no "decide which agent should work next". Adding a kind is a reviewed diff.
ROUTES = {
    "school_research": "grab",
    "adapter_build": "build",
    "loop_selftest": "selftest",
}

# Typed result contracts. A worker's return value must satisfy its kind's schema or
# the item fails closed. This is the boundary between "a model said something" and
# "the system believes something".
RESULT_CONTRACTS = {
    "school_research": {
        "required": ("verdict", "evidence_url", "gates"),
        "verdict_enum": True,
        # A BUILD verdict additionally requires every accuracy gate to be recorded.
        # The Operator does not RUN the gates and never claims to — Build re-runs
        # them before shipping. It only refuses to carry an unevidenced BUILD.
        "build_requires_gates": 8,
    },
    "adapter_build": {
        "required": ("verdict", "evidence_url"),
        "verdict_enum": True,
    },
    "loop_selftest": {
        "required": ("verdict",),
        "verdict_enum": True,
    },
}

MAX_CLAIM_ATTEMPTS = 3       # transient losses (worker died, lease expired)
MAX_REJECTIONS = 2           # second rejection -> adjudication, never a third attempt
DEFAULT_CLAIM_TTL_S = 1800

_ID_RE = re.compile(r"^[a-z0-9][a-z0-9-]{0,62}$")


class ContractError(Exception):
    """A typed contract was violated. Always fails closed — never retried blindly."""


# --------------------------------------------------------------- schema
def init_schema(c):
    """Additive only, like guardian.init_schema — safe against an existing DB."""
    c.execute("""CREATE TABLE IF NOT EXISTS objectives(
        id TEXT PRIMARY KEY, title TEXT NOT NULL, kind TEXT NOT NULL,
        state TEXT NOT NULL DEFAULT 'proposed', target INTEGER NOT NULL,
        budget_items INTEGER NOT NULL DEFAULT 0, dry_well_limit INTEGER NOT NULL DEFAULT 3,
        created REAL NOT NULL, activated_at REAL, closed_at REAL,
        stop_reason TEXT, params TEXT)""")
    c.execute("""CREATE TABLE IF NOT EXISTS work_items(
        id INTEGER PRIMARY KEY AUTOINCREMENT, objective_id TEXT NOT NULL,
        kind TEXT NOT NULL, item_key TEXT NOT NULL, role TEXT NOT NULL,
        state TEXT NOT NULL DEFAULT 'queued', payload TEXT, result TEXT,
        verdict TEXT, attempts INTEGER NOT NULL DEFAULT 0,
        rejections INTEGER NOT NULL DEFAULT 0, adjudication INTEGER NOT NULL DEFAULT 0,
        claim_holder TEXT, claim_expires REAL,
        created REAL NOT NULL, updated REAL NOT NULL)""")
    # Duplicate prevention at the DATABASE level: one item per (objective, key).
    # The same school cannot be researched twice under one objective, whatever the
    # calling code does.
    c.execute("""CREATE UNIQUE INDEX IF NOT EXISTS ux_item_key
                 ON work_items(objective_id, item_key)""")
    c.execute("CREATE INDEX IF NOT EXISTS ix_item_state ON work_items(state, role)")
    c.execute("""CREATE TABLE IF NOT EXISTS reviews(
        id INTEGER PRIMARY KEY AUTOINCREMENT, item_id INTEGER NOT NULL,
        kind TEXT NOT NULL, reviewer TEXT NOT NULL, evidence TEXT NOT NULL,
        created REAL NOT NULL)""")
    c.execute("CREATE INDEX IF NOT EXISTS ix_rev_item ON reviews(item_id, created)")


# --------------------------------------------------------------- objectives
def create_objective(c, oid, title, kind, target, budget_items=0,
                     dry_well_limit=3, params=None, now=None):
    """Objectives are born `proposed` with a budget of ZERO. Nothing can be queued
    against them and no work can occur until a human activates them with an explicit
    budget. Creating an objective is therefore never, by itself, a spending decision."""
    now = time.time() if now is None else now
    if not _ID_RE.match(oid or ""):
        raise ContractError("objective id must be lowercase kebab-case: %r" % oid)
    if kind not in ROUTES:
        raise ContractError("unknown objective kind %r (known: %s)"
                            % (kind, ", ".join(sorted(ROUTES))))
    if int(target) < 1:
        raise ContractError("target must be >= 1")
    if int(budget_items) < 0:
        raise ContractError("budget cannot be negative")
    c.execute("""INSERT INTO objectives(id,title,kind,state,target,budget_items,
                 dry_well_limit,created,params) VALUES(?,?,?,'proposed',?,?,?,?,?)""",
              (oid, title, kind, int(target), int(budget_items), int(dry_well_limit),
               now, json.dumps(params or {})))
    return get_objective(c, oid)


def get_objective(c, oid):
    return c.execute("SELECT * FROM objectives WHERE id=?", (oid,)).fetchone()


def activate_objective(c, oid, budget_items, now=None):
    """Activation is the ONLY moment authority is granted, and it requires a positive
    budget stated at that moment. There is deliberately no path that activates an
    objective with its default zero budget: 'turn it on' and 'authorise it to spend'
    are the same decision, made once, by a human."""
    now = time.time() if now is None else now
    o = get_objective(c, oid)
    if not o:
        raise ContractError("no such objective: %s" % oid)
    if o["state"] not in ("proposed", "stopped"):
        raise ContractError("cannot activate an objective in state %r" % o["state"])
    if int(budget_items) < 1:
        raise ContractError("activation requires an explicit budget of at least 1 item")
    c.execute("UPDATE objectives SET state='active', budget_items=?, activated_at=?, "
              "stop_reason=NULL, closed_at=NULL WHERE id=?",
              (int(budget_items), now, oid))
    return get_objective(c, oid)


def stop_objective(c, oid, reason, state="stopped", now=None):
    now = time.time() if now is None else now
    c.execute("UPDATE objectives SET state=?, stop_reason=?, closed_at=? WHERE id=?",
              (state, reason, now, oid))
    return get_objective(c, oid)


def progress(c, oid):
    """Completion measured from EVIDENCE, never from a counter.

    Counts items that reached `ready_for_build` with a BUILD verdict — that is, work
    a Critic certified. Note what this deliberately does NOT count: schools actually
    shipped. The Operator cannot write schools.py or deploy, so it must not report a
    number that implies it did."""
    return c.execute("SELECT COUNT(*) FROM work_items WHERE objective_id=? "
                     "AND state='ready_for_build' AND verdict='BUILD'", (oid,)).fetchone()[0]


def spent(c, oid):
    """Budget is consumed by items CREATED, not items completed — a worker that burns
    tokens and returns nothing has still spent the budget."""
    return c.execute("SELECT COUNT(*) FROM work_items WHERE objective_id=?",
                     (oid,)).fetchone()[0]


# --------------------------------------------------------------- queueing
def enqueue(c, oid, item_key, payload=None, kind=None, now=None):
    """Add one unit of work. Refuses when the objective is not active, when the
    budget is exhausted, or when the key already exists. Returns the item row, or
    None if it was a duplicate (which is a no-op, not an error — re-enqueueing the
    same candidate must be safe)."""
    now = time.time() if now is None else now
    o = get_objective(c, oid)
    if not o:
        raise ContractError("no such objective: %s" % oid)
    if o["state"] != "active":
        raise ContractError("objective %s is %r — nothing may be queued against it"
                            % (oid, o["state"]))
    kind = kind or o["kind"]
    role = ROUTES.get(kind)
    if role is None:
        raise ContractError("unroutable work kind %r" % kind)   # fail closed
    # Duplicate check BEFORE the budget check, deliberately. Re-enqueueing a key that
    # already exists consumes nothing, so it must stay a safe no-op even once the
    # budget is full — otherwise a caller that re-runs its enqueue loop (exactly what
    # a retry or a resumed session does) gets a spurious "budget exhausted" for work
    # that was already queued.
    existing = c.execute("SELECT * FROM work_items WHERE objective_id=? AND item_key=?",
                         (oid, item_key)).fetchone()
    if existing:
        return None
    if spent(c, oid) >= o["budget_items"]:
        raise ContractError("budget exhausted for %s (%d/%d items)"
                            % (oid, spent(c, oid), o["budget_items"]))
    c.execute("""INSERT INTO work_items(objective_id,kind,item_key,role,state,payload,
                 created,updated) VALUES(?,?,?,?,'queued',?,?,?)""",
              (oid, kind, item_key, role, json.dumps(payload or {}), now, now))
    return c.execute("SELECT * FROM work_items WHERE objective_id=? AND item_key=?",
                     (oid, item_key)).fetchone()


# --------------------------------------------------------------- claiming
def reclaim_expired(c, now=None):
    """A claim is a LEASE. A worker that dies holding one does not strand the item:
    the lease expires and the item returns to the queue. Attempts are bounded, so a
    poison item cannot be retried forever."""
    now = time.time() if now is None else now
    rows = c.execute("SELECT * FROM work_items WHERE state='claimed' AND claim_expires<=?",
                     (now,)).fetchall()
    returned, exhausted = [], []
    for r in rows:
        if r["attempts"] >= MAX_CLAIM_ATTEMPTS:
            c.execute("UPDATE work_items SET state='failed', claim_holder=NULL, "
                      "claim_expires=NULL, updated=? WHERE id=?", (now, r["id"]))
            exhausted.append(r["id"])
        else:
            c.execute("UPDATE work_items SET state='queued', claim_holder=NULL, "
                      "claim_expires=NULL, updated=? WHERE id=?", (now, r["id"]))
            returned.append(r["id"])
    return returned, exhausted


def claim(c, role, holder, ttl_s=DEFAULT_CLAIM_TTL_S, now=None):
    """Hand exactly one queued item to a worker of `role`. Returns the item or None.

    A worker may only claim kinds its role owns (ROUTES) — a Grab worker cannot pick
    up a Build item. The UPDATE's WHERE clause carries the state it expects, so two
    workers racing for the same item cannot both win: the loser's UPDATE matches zero
    rows and it moves on."""
    now = time.time() if now is None else now
    reclaim_expired(c, now)
    kinds = [k for k, v in ROUTES.items() if v == role]
    if not kinds:
        raise ContractError("unknown worker role %r" % role)
    ph = ",".join("?" * len(kinds))
    row = c.execute(
        "SELECT wi.* FROM work_items wi JOIN objectives o ON o.id=wi.objective_id "
        "WHERE wi.state='queued' AND wi.kind IN (%s) AND o.state='active' "
        "ORDER BY wi.created LIMIT 1" % ph, kinds).fetchone()
    if not row:
        return None
    n = c.execute("UPDATE work_items SET state='claimed', claim_holder=?, "
                  "claim_expires=?, attempts=attempts+1, updated=? "
                  "WHERE id=? AND state='queued'",
                  (holder, now + ttl_s, now, row["id"])).rowcount
    if n != 1:
        return None                       # lost the race; caller may claim again
    return c.execute("SELECT * FROM work_items WHERE id=?", (row["id"],)).fetchone()


# --------------------------------------------------------------- results
def validate_result(kind, result):
    """The typed contract. Raises ContractError on any violation — the caller turns
    that into a failed item plus a finding, never into a silent pass."""
    if not isinstance(result, dict):
        raise ContractError("result must be a JSON object, got %s"
                            % type(result).__name__)
    spec = RESULT_CONTRACTS.get(kind)
    if spec is None:
        raise ContractError("no result contract for kind %r" % kind)
    # Presence, not truthiness: an empty `gates` dict is a legitimate value for a
    # SCRAP verdict (no gates were reached), whereas an empty verdict or evidence_url
    # is not. Testing `not result.get(f)` conflated the two.
    missing = []
    for f in spec["required"]:
        if f not in result:
            missing.append(f)
            continue
        v = result[f]
        if v is None or (isinstance(v, str) and not v.strip()):
            missing.append(f)
    if missing:
        raise ContractError("result missing required field(s): %s" % ", ".join(missing))
    if spec.get("verdict_enum") and result["verdict"] not in VERDICTS:
        # The verdict is an ENUM, not free text. This is also the injection boundary:
        # whatever a researched website said, it cannot become a verdict.
        raise ContractError("verdict must be one of %s, got %r"
                            % ("/".join(VERDICTS), str(result["verdict"])[:60]))
    need = spec.get("build_requires_gates")
    if need and result["verdict"] == "BUILD":
        gates = result.get("gates")
        if not isinstance(gates, dict) or len(gates) < need:
            raise ContractError("a BUILD verdict requires all %d accuracy gates "
                                "recorded; got %s" % (need, len(gates or {})))
        failed = [g for g, ok in gates.items() if not ok]
        if failed:
            raise ContractError("BUILD verdict contradicts failed gate(s): %s"
                                % ", ".join(sorted(failed)))
    return True


def complete(c, item_id, holder, result, now=None):
    """A worker returns its typed result. On a contract violation the item fails
    CLOSED: evidence kept, no verdict recorded, no retry. Returns (state, detail)."""
    now = time.time() if now is None else now
    r = c.execute("SELECT * FROM work_items WHERE id=?", (item_id,)).fetchone()
    if not r:
        raise ContractError("no such work item: %s" % item_id)
    if r["state"] != "claimed":
        raise ContractError("item %s is %r, not claimed" % (item_id, r["state"]))
    if r["claim_holder"] != holder:
        raise ContractError("item %s is held by another worker" % item_id)
    try:
        validate_result(r["kind"], result)
    except ContractError as e:
        c.execute("UPDATE work_items SET state='failed', result=?, claim_holder=NULL, "
                  "claim_expires=NULL, updated=? WHERE id=?",
                  (json.dumps({"rejected_result": result, "error": str(e)},
                              default=str), now, item_id))
        return "failed", str(e)
    c.execute("UPDATE work_items SET state='done', result=?, verdict=?, "
              "claim_holder=NULL, claim_expires=NULL, updated=? WHERE id=?",
              (json.dumps(result, default=str), result["verdict"], now, item_id))
    return "done", "accepted"


def review(c, item_id, kind, reviewer, evidence, now=None):
    """Critic's verdict on completed work.

    A REJECTION IS NOT A RETRYABLE FAILURE. It is a judgement, and it is recorded as
    one. The first rejection returns the item for one rework; the second raises an
    adjudication request and the item stops. Nothing may resubmit it a third time —
    otherwise "retry until the checker agrees" becomes maker-grades-own-work through
    the back door (AI Operating System 5.3)."""
    now = time.time() if now is None else now
    if kind not in REVIEW_KINDS:
        raise ContractError("review kind must be one of %s" % "/".join(REVIEW_KINDS))
    r = c.execute("SELECT * FROM work_items WHERE id=?", (item_id,)).fetchone()
    if not r:
        raise ContractError("no such work item: %s" % item_id)
    if r["state"] != "done":
        raise ContractError("only a completed item can be reviewed; item %s is %r"
                            % (item_id, r["state"]))
    if not evidence:
        # A certification that cites nothing is the one unforgivable failure in the
        # AI-OS Verify charter. Refuse to store it.
        raise ContractError("a review must cite evidence")
    c.execute("INSERT INTO reviews(item_id,kind,reviewer,evidence,created) "
              "VALUES(?,?,?,?,?)",
              (item_id, kind, reviewer, json.dumps(evidence, default=str), now))
    if kind == "certification":
        c.execute("UPDATE work_items SET state='ready_for_build', updated=? WHERE id=?",
                  (now, item_id))
        return "ready_for_build", "certified"
    n = r["rejections"] + 1
    if n >= MAX_REJECTIONS:
        c.execute("UPDATE work_items SET state='rejected', rejections=?, "
                  "adjudication=1, updated=? WHERE id=?", (n, now, item_id))
        return "rejected", "adjudication_required"
    c.execute("UPDATE work_items SET state='queued', rejections=?, verdict=NULL, "
              "updated=? WHERE id=?", (n, now, item_id))
    return "queued", "returned_for_rework"


def fail(c, item_id, holder, reason, now=None):
    """A worker reporting it could not do the work. Transient by assumption, so the
    item returns to the queue — but attempts are already bounded by the claim, so
    this cannot loop forever."""
    now = time.time() if now is None else now
    r = c.execute("SELECT * FROM work_items WHERE id=?", (item_id,)).fetchone()
    if not r or r["state"] != "claimed" or r["claim_holder"] != holder:
        raise ContractError("item %s is not claimed by this worker" % item_id)
    state = "failed" if r["attempts"] >= MAX_CLAIM_ATTEMPTS else "queued"
    c.execute("UPDATE work_items SET state=?, claim_holder=NULL, claim_expires=NULL, "
              "result=?, updated=? WHERE id=?",
              (state, json.dumps({"worker_reason": str(reason)[:500]}), now, item_id))
    return state, reason


# --------------------------------------------------------------- reporting
def objective_report(c, oid):
    o = get_objective(c, oid)
    if not o:
        return None
    counts = {s: 0 for s in ITEM_STATES}
    for r in c.execute("SELECT state, COUNT(*) n FROM work_items WHERE objective_id=? "
                       "GROUP BY state", (oid,)):
        counts[r["state"]] = r["n"]
    return {
        "id": o["id"], "title": o["title"], "kind": o["kind"], "state": o["state"],
        "target": o["target"], "progress": progress(c, oid),
        "budget_items": o["budget_items"], "spent_items": spent(c, oid),
        "dry_well_limit": o["dry_well_limit"], "items": counts,
        "adjudications": c.execute("SELECT COUNT(*) FROM work_items WHERE "
                                   "objective_id=? AND adjudication=1", (oid,)).fetchone()[0],
        "stop_reason": o["stop_reason"],
    }


def all_objectives(c):
    return [objective_report(c, r["id"]) for r in
            c.execute("SELECT id FROM objectives ORDER BY created")]
