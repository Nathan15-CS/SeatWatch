"""READINESS #16 — real money. The paid path had ZERO test coverage until this file.

Everything else in this suite protects a student's seat. This one protects their money and
Nathan's Stripe account, and it is the only surface where a bug is a chargeback rather than
a missed alert.

The load-bearing claim is one sentence: **a verified webhook is the ONLY thing that grants
a paid tier.** Not the redirect back from Checkout, not a session cookie, not a form post.
If that fails, anyone who can send an HTTP request gets a free upgrade, and the failure is
silent — a real payment and a forged one produce identical database rows.

Pinned here, in descending order of what it would cost to get wrong:

  FORGERY     a bad/absent/tampered signature must NEVER unlock. Tested through the real
              socket, because the guard has to hold against a hand-crafted POST.
  REPLAY      a correctly-signed event from outside the 5-minute window is refused, so a
              captured webhook cannot be re-fired later.
  IDEMPOTENCE Stripe retries on any non-2xx and re-sends on its own schedule. The same
              event twice must unlock once.
  RATCHET     a stale or duplicate LOWER tier event must never downgrade a higher one.
  REFUND      a full refund or chargeback drops the account to free...
  PRECISION   ...but ONLY when it matches the payment_intent that granted the CURRENT
              entitlement. Refunding a superseded charge must not strip a plan the student
              re-bought and still holds. This is the one that quietly robs a paying user.
"""
import hashlib
import hmac
import json
import os
import sys
import tempfile
import threading
import time
import urllib.error
import urllib.request
import warnings

warnings.filterwarnings("ignore")

SECRET = "whsec_readiness_test_secret"


def run():
    os.environ["SEATWATCH_DB"] = os.path.join(tempfile.mkdtemp(), "pay.db")
    os.environ["STRIPE_WEBHOOK_SECRET"] = SECRET
    sys.path.insert(0, os.path.expanduser("~/seatwatch"))
    import app
    app.STRIPE_WEBHOOK_SECRET = SECRET
    app.init_db()

    results = []
    def check(n, c, d=""):
        results.append((n, bool(c), d))

    with app.db() as c:
        c.execute("INSERT INTO users(google_sub,email,topic,created) "
                  "VALUES('g_pay','pay@umd.edu','t_pay',0)")
        uid = c.execute("SELECT id FROM users WHERE google_sub='g_pay'").fetchone()["id"]

    def tier_of(u=None):
        with app.db() as c:
            r = c.execute("SELECT plan_tier FROM users WHERE id=?", (u or uid,)).fetchone()
        return int(r["plan_tier"] or 0)

    def set_tier(t, pi=None, u=None):
        with app.db() as c:
            c.execute("UPDATE users SET plan_tier=?, plan_payment_intent=? WHERE id=?",
                      (t, pi, u or uid))

    def sign(body, ts=None):
        ts = str(int(ts if ts is not None else time.time()))
        mac = hmac.new(SECRET.encode(), ts.encode() + b"." + body, hashlib.sha256).hexdigest()
        return f"t={ts},v1={mac}"

    def purchase_event(eid, tier, u=None, pi="pi_A"):
        return json.dumps({
            "id": eid, "type": "checkout.session.completed",
            "data": {"object": {"payment_intent": pi, "customer": "cus_1",
                                "metadata": {"user_id": str(u or uid),
                                             "target_tier": str(tier)}}}}).encode()

    def refund_event(eid, pi, amount, captured, etype="charge.refunded"):
        return json.dumps({
            "id": eid, "type": etype,
            "data": {"object": {"payment_intent": pi, "amount_refunded": amount,
                                "amount_captured": captured, "amount": captured}}}).encode()

    # ---- through the REAL socket: forgery must not pay ----
    from http.server import ThreadingHTTPServer
    srv = ThreadingHTTPServer(("127.0.0.1", 0), app.Handler)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    port = srv.server_address[1]

    def post(body, sig):
        req = urllib.request.Request(f"http://127.0.0.1:{port}/stripe/webhook", data=body,
                                     headers={"Content-Type": "application/json",
                                              "Stripe-Signature": sig})
        try:
            with urllib.request.urlopen(req, timeout=10) as r:
                return r.status
        except urllib.error.HTTPError as e:
            return e.code

    body = purchase_event("evt_forged", 3)
    set_tier(0)
    check("a webhook with NO signature is refused", post(body, "") == 400)
    check("...and granted nothing", tier_of() == 0, "a signature-less POST paid for itself")

    check("a webhook with a GARBAGE signature is refused",
          post(body, "t=%d,v1=deadbeef" % int(time.time())) == 400)
    check("...and granted nothing", tier_of() == 0)

    good = sign(body)
    tampered = purchase_event("evt_forged", 3).replace(b'"target_tier": "3"',
                                                       b'"target_tier": "1"')
    check("a signature from a DIFFERENT body is refused", post(tampered, good) == 400)
    check("...and granted nothing", tier_of() == 0,
          "the payload could be edited after signing")

    check("a correctly-signed event from 10 min ago is refused (replay)",
          post(body, sign(body, time.time() - 600)) == 400)
    check("...and granted nothing", tier_of() == 0,
          "a captured webhook could be re-fired forever")

    # ---- the happy path, through the same socket ----
    check("a VALID signed purchase is accepted", post(body, sign(body)) == 200)
    check("...and unlocks the paid tier", tier_of() == 3, f"tier is {tier_of()}")

    # ---- Stripe retries: same event twice must unlock once ----
    with app.db() as c:
        n_before = c.execute("SELECT COUNT(*) n FROM stripe_events").fetchone()["n"]
    check("re-delivering the SAME event is accepted (Stripe needs a 2xx)",
          post(body, sign(body)) == 200)
    with app.db() as c:
        n_after = c.execute("SELECT COUNT(*) n FROM stripe_events").fetchone()["n"]
    check("...but is recorded only once", n_after == n_before,
          "duplicate ledger rows on every Stripe retry")

    # ---- the ratchet: a stale lower event must not demote a paying user ----
    stale = purchase_event("evt_stale_low", 1)
    post(stale, sign(stale))
    check("a stale LOWER-tier event cannot downgrade a higher plan", tier_of() == 3,
          f"tier fell to {tier_of()} — a duplicate old event demoted a paying student")

    # ---- refunds ----
    set_tier(2, "pi_REF")
    full = refund_event("evt_ref_full", "pi_REF", 1995, 1995)
    post(full, sign(full))
    check("a FULL refund downgrades to free", tier_of() == 0, f"tier is {tier_of()}")

    set_tier(2, "pi_PART")
    part = refund_event("evt_ref_part", "pi_PART", 500, 1995)
    post(part, sign(part))
    check("a PARTIAL refund does NOT strip the plan", tier_of() == 2,
          "a $5 goodwill refund deleted a plan the student mostly paid for")

    set_tier(3, "pi_NEW")
    old = refund_event("evt_ref_old", "pi_OLD_SUPERSEDED", 1995, 1995)
    post(old, sign(old))
    check("refunding a SUPERSEDED charge leaves the current plan intact", tier_of() == 3,
          "refunding an old charge stripped the plan the student re-bought — "
          "they paid and lost access")

    set_tier(2, "pi_DISP")
    disp = refund_event("evt_disp", "pi_DISP", 1995, 1995, "charge.dispute.created")
    post(disp, sign(disp))
    check("a chargeback/dispute downgrades to free", tier_of() == 0, f"tier is {tier_of()}")

    # ---- an unknown tier in metadata must not be honoured ----
    set_tier(0)
    bogus = purchase_event("evt_bogus_tier", 99)
    post(bogus, sign(bogus))
    check("an out-of-range tier in metadata grants nothing", tier_of() == 0,
          f"tier is {tier_of()} — metadata is attacker-influenced if the signature ever leaks")

    # ---- config sanity, so a half-configured launch is loud ----
    check("tier prices are all positive integers",
          all(isinstance(v, int) and v > 0 for v in app.TIER_PRICE_CENTS.values()),
          str(app.TIER_PRICE_CENTS))
    check("every priced tier has a display name",
          all(t in app.TIER_NAME for t in app.TIER_PRICE_CENTS))

    srv.shutdown()
    p = sum(ok for _, ok, _ in results)
    f = sum(not ok for _, ok, _ in results)
    return p, f, results


if __name__ == "__main__":
    p, f, res = run()
    for n, ok, d in res:
        print(f"  [{'PASS' if ok else '*** FAIL'}] {n}{('  ' + d) if d and not ok else ''}")
    print(f"\n  {p} passed, {f} failed")
    sys.exit(1 if f else 0)
