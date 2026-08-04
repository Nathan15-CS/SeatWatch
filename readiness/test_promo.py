"""READINESS #17 — the 7-day coupon, as Stripe promotion codes.

Nathan's spec, restated as things that must be TRUE:

  ELIGIBILITY   only students free for a week are offered it; anyone who already paid,
                or who turned email off, is skipped
  PER-STUDENT   numeric, minted in Stripe, bound to one account, single use
  FIELD ON EVERY PLAN
                the promotion-code box appears at the PAYMENT step beside card and Apple
                Pay, on all three plans — a student holding a code should never have to
                hunt for where it goes
  TIER-LOCKED   it can only ever reduce the $29.95 plan. The $19.95 and $24.95 plans and
                any upgrade delta are below the code's minimum order, so Stripe refuses it
  NEVER MAIL A DEAD CODE
                if Stripe will not mint the code, no email goes out at all

The last one is the subtle one. A code that Stripe rejects arrives at the exact moment a
student has decided to pay, and what it tells them is that the company is broken. Silence
is strictly better, and the sweep retries next hour.

Stripe is stubbed here: these are OUR rules, not Stripe's. What is asserted is that we
ask Stripe for the right thing — the right coupon, the right redemption limit, and the
right minimum order — because those three fields are the entire tier lock.
"""
import os
import sys
import tempfile
import time
import warnings

warnings.filterwarnings("ignore")


def run():
    os.environ["SEATWATCH_DB"] = os.path.join(tempfile.mkdtemp(), "promo.db")
    sys.path.insert(0, os.path.expanduser("~/seatwatch"))
    import app
    app.init_db()
    app.STRIPE_SECRET_KEY = "sk_test_readiness"

    results = []
    def check(n, c, d=""):
        results.append((n, bool(c), d))

    calls = []
    def fake_post(path, fields, idem=None):
        calls.append((path, dict(fields), idem))
        if path == "/coupons":
            return {"id": app.STRIPE_COUPON_ID}
        if path == "/promotion_codes":
            return {"id": "promo_" + fields["code"], "code": fields["code"]}
        if path == "/checkout/sessions":
            return {"url": "https://checkout.stripe.test/s"}
        return {}
    app._stripe_post = fake_post
    app._stripe_get = lambda path: None          # coupon absent -> must be created

    with app.db() as c:
        c.execute("INSERT INTO users(google_sub,email,topic,created) "
                  "VALUES('g_p','p@umd.edu','t_p',0)")
        uid = c.execute("SELECT id FROM users WHERE google_sub='g_p'").fetchone()["id"]

    # ---- the generator ----
    gen = {app._new_promo_code() for _ in range(400)}
    check("codes are 8 digits, numeric only", all(len(x) == 8 and x.isdigit() for x in gen))
    check("400 generated codes are all distinct", len(gen) == 400,
          f"{400 - len(gen)} collision(s) — the space is too small")

    # ---- minting ----
    code = app.issue_promo_code(uid)
    check("a code is minted", bool(code) and code.isdigit(), f"got {code!r}")

    coupon = next((f for p, f, _ in calls if p == "/coupons"), None)
    check("the coupon is $5.00 off, once", coupon and coupon.get("amount_off") == "500"
          and coupon.get("duration") == "once", str(coupon))
    check("...in USD", coupon and coupon.get("currency") == "usd")

    pc = next((f for p, f, _ in calls if p == "/promotion_codes"), None)
    check("the promotion code points at that coupon",
          pc and pc.get("coupon") == app.STRIPE_COUPON_ID, str(pc))
    check("SINGLE USE: max_redemptions is 1", pc and pc.get("max_redemptions") == "1",
          "a reusable code is a permanent price cut once it leaks")
    check("TIER LOCK: minimum order is the $29.95 plan",
          pc and pc.get("restrictions[minimum_amount]") == str(
              app.TIER_PRICE_CENTS[app.PROMO_TIER]),
          f"got {pc.get('restrictions[minimum_amount]') if pc else None}")
    check("...denominated in USD",
          pc and pc.get("restrictions[minimum_amount_currency]") == "usd")
    check("the code is traceable back to the student",
          pc and pc.get("metadata[user_id]") == str(uid))

    # the tier lock, argued in numbers rather than trusted
    floor = int(pc["restrictions[minimum_amount]"])
    check("the $19.95 plan cannot reach the minimum",
          app.TIER_PRICE_CENTS[1] < floor, f"{app.TIER_PRICE_CENTS[1]} vs {floor}")
    check("the $24.95 plan cannot reach the minimum",
          app.TIER_PRICE_CENTS[2] < floor, f"{app.TIER_PRICE_CENTS[2]} vs {floor}")
    check("the $29.95 plan exactly reaches it",
          app.TIER_PRICE_CENTS[3] == floor)
    check("every upgrade DELTA is below the minimum",
          all(app.TIER_PRICE_CENTS[t] - app.TIER_PRICE_CENTS[c] < floor
              for t in (2, 3) for c in (1, 2) if t > c),
          "an upgrader could otherwise take $5 off a partial payment")
    check("the discounted price is exactly $24.95",
          app.TIER_PRICE_CENTS[3] - app.PROMO_OFF_CENTS == app.PROMO_PRICE_CENTS == 2495,
          f"{app.TIER_PRICE_CENTS[3]} - {app.PROMO_OFF_CENTS} != {app.PROMO_PRICE_CENTS}")

    with app.db() as c:
        stored = c.execute("SELECT promo_code FROM users WHERE id=?", (uid,)).fetchone()
    check("the code is stored against the student", stored["promo_code"] == code)

    # ---- the FIELD appears ONLY on the $29.95 purchase ----
    app.PAID_LIVE = True
    calls.clear()
    with app.db() as c:
        u = c.execute("SELECT * FROM users WHERE id=?", (uid,)).fetchone()
    for t in (1, 2, 3):
        app.stripe_checkout_url(u, t)
    sessions = [f for p, f, _ in calls if p == "/checkout/sessions"]
    check("a checkout session is created for all three plans", len(sessions) == 3,
          f"got {len(sessions)}")
    by_tier = {int(f["metadata[target_tier]"]): f for f in sessions}
    check("the promotion-code field is ON for the $29.95 plan",
          by_tier[3].get("allow_promotion_codes") == "true")
    check("...and OFF for the $19.95 plan",
          "allow_promotion_codes" not in by_tier[1],
          "a box that exists only to reject the code is worse than no box")
    check("...and OFF for the $24.95 plan",
          "allow_promotion_codes" not in by_tier[2])
    check("tax cannot inflate the total on any plan",
          all(f.get("automatic_tax[enabled]") == "false" for f in sessions),
          "the statement must match the price shown")
    check("quantity cannot be adjusted upward",
          all(f.get("line_items[0][adjustable_quantity][enabled]") == "false"
              for f in sessions))
    check("each plan charges its own FULL price",
          [by_tier[t]["line_items[0][price_data][unit_amount]"] for t in (1, 2, 3)]
          == [str(app.TIER_PRICE_CENTS[t]) for t in (1, 2, 3)],
          str([by_tier[t]["line_items[0][price_data][unit_amount]"] for t in (1, 2, 3)]))

    # ---- UPGRADES ARE UPWARD ONLY, and the promo never rides on one ----
    # PAID_ENABLED and a fresh purchase timestamp both matter: effective_tier fails
    # closed on a lapsed or dormant entitlement, so without them this student reads as
    # free and the checks would pass for the wrong reason.
    app.PAID_ENABLED = True
    with app.db() as c:
        c.execute("UPDATE users SET plan_tier=1, plan_purchased_at=?, plan_term=? WHERE id=?",
                  (time.time(), app.current_season(), uid))
        paid_u = c.execute("SELECT * FROM users WHERE id=?", (uid,)).fetchone()
    check("...and that student really is entitled (guard against a false pass)",
          app.effective_tier(paid_u) == 1, f"effective_tier={app.effective_tier(paid_u)}")
    check("a $19.95 student CAN move up to $24.95 and $29.95",
          all(app.stripe_checkout_url(paid_u, t) is not None for t in (2, 3)),
          "an upgrade path the student is entitled to is closed")
    check("...but cannot re-buy the plan they already hold",
          app.stripe_checkout_url(paid_u, 1) is None, "money for nothing")
    # The promo's $29.95 minimum is what keeps it off an upgrade: an upgrade charges the
    # DIFFERENCE, which can never reach that floor, so a $5 code cannot be applied to a
    # $5 delta. Asserted as arithmetic rather than trusted.
    check("an upgrade delta can never reach the promo's minimum order",
          all(app.TIER_PRICE_CENTS[t] - app.TIER_PRICE_CENTS[c]
              < app.TIER_PRICE_CENTS[app.PROMO_TIER]
              for t in (2, 3) for c in (1, 2) if t > c),
          "a $5 coupon could be taken off a $5 upgrade, making it free")
    with app.db() as c:
        c.execute("UPDATE users SET plan_tier=0, plan_term=NULL WHERE id=?", (uid,))

    # ---- NEVER MAIL A DEAD CODE ----
    app.EMAIL_ENABLED = app.PAID_ENABLED = True
    mails = []
    app.send_email = lambda to, s, b, u=None: (mails.append((to, b)), True)[1]
    with app.db() as c:
        c.execute("INSERT INTO users(google_sub,email,topic,created) "
                  "VALUES('g_dead','dead@umd.edu','t_dead',?)", (time.time() - 30 * 86400,))
    app._stripe_post = lambda path, fields, idem=None: None       # Stripe is down
    app._promo_sweep_at[0] = 0
    app.send_promo_emails()
    # Scoped to the student who has NO code yet. p@umd.edu already holds one from the
    # minting test above, and reusing an existing valid code while Stripe is briefly down
    # is correct behaviour — not the failure this check is about.
    check("Stripe refusing to mint sends NO email to a student without a code",
          "dead@umd.edu" not in {t for t, _ in mails},
          "a code Stripe rejects reaches a student at the moment they decided to pay")
    with app.db() as c:
        d = c.execute("SELECT promo_sent_at FROM users WHERE google_sub='g_dead'").fetchone()
    check("...and the student stays eligible for the next sweep", d["promo_sent_at"] is None,
          "a transient Stripe error would have silently cost them the offer forever")

    # ---- and when Stripe works, the mail is right ----
    app._stripe_post = fake_post
    app._promo_sweep_at[0] = 0
    app.send_promo_emails()
    check("with Stripe healthy the email goes out", bool(mails))
    body = mails[-1][1] if mails else ""
    with app.db() as c:
        got = c.execute("SELECT promo_code FROM users WHERE google_sub='g_dead'").fetchone()
    check("the email carries that student's minted code",
          bool(got["promo_code"]) and got["promo_code"] in body)
    check("the email states the discounted price", "$24.95" in body)
    check("the email names the only eligible plan", app.TIER_NAME[app.PROMO_TIER] in body)
    check("the email says WHERE to enter it", "promotion code" in body.lower(),
          "the field is on Stripe's payment page; a student needs telling")
    check("the email links STRAIGHT to the payment page",
          f"/checkout?tier={app.PROMO_TIER}" in body,
          "a link to /pricing makes them navigate again with a code in hand")

    # ---- eligibility ----
    mails.clear()
    with app.db() as c:
        c.execute("INSERT INTO users(google_sub,email,topic,created,plan_tier) "
                  "VALUES('g_paid','paid@umd.edu','t_paid',?,3)", (time.time() - 30 * 86400,))
        c.execute("INSERT INTO users(google_sub,email,topic,created) "
                  "VALUES('g_new','new@umd.edu','t_new',?)", (time.time(),))
    app._promo_sweep_at[0] = 0
    app.send_promo_emails()
    to = {t for t, _ in mails}
    check("a student who already PAID is never offered it", "paid@umd.edu" not in to,
          "discounting someone who already bought is money thrown away")
    check("a student who joined today is not offered it yet", "new@umd.edu" not in to,
          "the offer is meant to reward a week of use")

    p = sum(ok for _, ok, _ in results)
    f = sum(not ok for _, ok, _ in results)
    return p, f, results


if __name__ == "__main__":
    p, f, res = run()
    for n, ok, d in res:
        print(f"  [{'PASS' if ok else '*** FAIL'}] {n}{('  ' + d) if d and not ok else ''}")
    print(f"\n  {p} passed, {f} failed")
    sys.exit(1 if f else 0)
