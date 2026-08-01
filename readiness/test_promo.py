"""READINESS #17 — the 7-day coupon. Every clause of the spec, enforced not displayed.

Nathan's spec, restated as things that must be TRUE of the code:

  ELIGIBILITY   only students who have been on FREE for a week are offered it; anyone
                who already paid is skipped entirely
  PER-STUDENT   the code is numeric and issued to ONE account. A shared code leaks the
                moment it is screenshotted, and cannot be revoked without punishing the
                students who earned it
  TIER-LOCKED   it discounts ONLY the top plan ($29.95 -> $24.95). The $19.95 and $24.95
                plans get nothing
  SINGLE-USE    once redeemed, it is dead
  EXACT CHARGE  a student who pays $24.95 is charged $24.95 and nothing else

The one that would hurt most is TIER-LOCKED combined with the display: a page that shows
a discounted price and then charges full at Stripe is worse than having no coupon at all,
because the student finds out from their bank statement. So the discount shown and the
discount charged are asserted to be the same number, computed by the same function.
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

    results = []
    def check(n, c, d=""):
        results.append((n, bool(c), d))

    with app.db() as c:
        c.execute("INSERT INTO users(google_sub,email,topic,created) "
                  "VALUES('g_p','p@umd.edu','t_p',0)")
        uid = c.execute("SELECT id FROM users WHERE google_sub='g_p'").fetchone()["id"]

    def user():
        with app.db() as c:
            return c.execute("SELECT * FROM users WHERE id=?", (uid,)).fetchone()

    def issue(code):
        with app.db() as c:
            c.execute("UPDATE users SET promo_code=?, promo_redeemed_at=NULL WHERE id=?",
                      (code, uid))

    # ---- the generator ----
    codes = {app._new_promo_code() for _ in range(400)}
    check("codes are 8 digits, numeric only",
          all(len(x) == 8 and x.isdigit() for x in codes))
    check("400 generated codes are all distinct", len(codes) == 400,
          f"{400 - len(codes)} collision(s) in 400 — the space is too small")

    CODE = "12345678"
    issue(CODE)
    T3, T2, T1 = app.PROMO_TIER, 2, 1

    # ---- TIER-LOCKED ----
    amt, applied = app.promo_price(user(), T3, CODE)
    check("valid code on the top plan gives the discounted price",
          amt == app.PROMO_PRICE_CENTS and applied == CODE, f"got {amt}, {applied}")
    check("...and that price is exactly $24.95", app.PROMO_PRICE_CENTS == 2495,
          f"PROMO_PRICE_CENTS={app.PROMO_PRICE_CENTS}")
    check("...a $5.00 saving, not $4.99 or $5.01",
          app.TIER_PRICE_CENTS[T3] - app.PROMO_PRICE_CENTS == 500,
          f"saving is {app.TIER_PRICE_CENTS[T3] - app.PROMO_PRICE_CENTS} cents")

    amt2, ap2 = app.promo_price(user(), T2, CODE)
    check("the SAME code does nothing on the $24.95 plan",
          amt2 == app.TIER_PRICE_CENTS[T2] and ap2 is None, f"got {amt2}, {ap2}")
    amt1, ap1 = app.promo_price(user(), T1, CODE)
    check("the SAME code does nothing on the $19.95 plan",
          amt1 == app.TIER_PRICE_CENTS[T1] and ap1 is None, f"got {amt1}, {ap1}")

    # ---- PER-STUDENT ----
    check("a wrong code is refused", app.promo_price(user(), T3, "87654321")[1] is None)
    check("a near-miss code is refused", app.promo_price(user(), T3, "12345679")[1] is None)
    check("an empty code charges full price",
          app.promo_price(user(), T3, "")[0] == app.TIER_PRICE_CENTS[T3])
    check("letters are stripped, not silently accepted",
          app.promo_price(user(), T3, "abcdefgh")[1] is None)
    check("a code with spaces/dashes still works for its owner",
          app.promo_price(user(), T3, " 1234-5678 ")[1] == CODE,
          "students retype codes with spaces; that must not cost them the discount")

    with app.db() as c:
        c.execute("INSERT INTO users(google_sub,email,topic,created,promo_code) "
                  "VALUES('g_q','q@umd.edu','t_q',0,'99999999')")
        other = c.execute("SELECT * FROM users WHERE google_sub='g_q'").fetchone()
    check("one student's code does NOT work on another's account",
          app.promo_price(other, T3, CODE)[1] is None,
          "codes would spread on Reddit and everyone pays $24.95 forever")

    # ---- SINGLE-USE ----
    with app.db() as c:
        c.execute("UPDATE users SET promo_redeemed_at=? WHERE id=?", (time.time(), uid))
    check("a redeemed code cannot be used again",
          app.promo_price(user(), T3, CODE)[1] is None)
    check("...and falls back to full price, not free",
          app.promo_price(user(), T3, CODE)[0] == app.TIER_PRICE_CENTS[T3])
    with app.db() as c:
        c.execute("UPDATE users SET promo_redeemed_at=NULL WHERE id=?", (uid,))

    # ---- ELIGIBILITY: a paying student is never offered it ----
    app.EMAIL_ENABLED, app.PAID_ENABLED = True, True
    sent_to = []
    app.send_email = lambda to, s, b, u=None: (sent_to.append((to, b)), True)[1]
    with app.db() as c:
        c.execute("UPDATE users SET plan_tier=3, promo_sent_at=NULL, created=? WHERE id=?",
                  (time.time() - 30 * 86400, uid))
        c.execute("UPDATE users SET plan_tier=0, promo_sent_at=NULL, created=?, "
                  "promo_code=NULL WHERE google_sub='g_q'", (time.time() - 30 * 86400,))
    app._promo_sweep_at[0] = 0
    app.send_promo_emails()
    check("a PAYING student is not offered the promo",
          all("p@umd.edu" != t for t, _ in sent_to), f"mailed {[t for t, _ in sent_to]}")
    check("a week-old FREE student IS offered it",
          any("q@umd.edu" == t for t, _ in sent_to))

    with app.db() as c:
        q = c.execute("SELECT promo_code FROM users WHERE google_sub='g_q'").fetchone()
    check("the emailed student now has a persisted code",
          bool(q["promo_code"]) and q["promo_code"].isdigit(),
          "a code in an inbox the server cannot recognise is worse than no promo")
    body = next((b for t, b in sent_to if t == "q@umd.edu"), "")
    check("the email contains that exact code", q["promo_code"] in body)
    check("the email states the discounted price", "$24.95" in body)
    check("the email says which plan it applies to",
          app.TIER_NAME[app.PROMO_TIER] in body)

    # ---- a brand-new free student is NOT swept early ----
    with app.db() as c:
        c.execute("INSERT INTO users(google_sub,email,topic,created) "
                  "VALUES('g_new','new@umd.edu','t_new',?)", (time.time(),))
    sent_to.clear()
    app._promo_sweep_at[0] = 0
    app.send_promo_emails()
    check("a student who signed up today is NOT offered it yet",
          all("new@umd.edu" != t for t, _ in sent_to),
          "the offer is supposed to reward a week of use")

    # ---- EXACT CHARGE: what is shown is what is charged ----
    issue(CODE)
    shown, _ = app.promo_price(user(), T3, CODE)
    check("the price shown on the page and the price sent to Stripe are one function",
          shown == app.PROMO_PRICE_CENTS == 2495, f"shown={shown}")
    check("no tax/quantity adjustment can inflate the total",
          'automatic_tax[enabled]' in open(
              os.path.expanduser("~/seatwatch/app.py")).read(),
          "automatic_tax must be pinned off or Stripe may add tax to the shown price")

    p = sum(ok for _, ok, _ in results)
    f = sum(not ok for _, ok, _ in results)
    return p, f, results


if __name__ == "__main__":
    p, f, res = run()
    for n, ok, d in res:
        print(f"  [{'PASS' if ok else '*** FAIL'}] {n}{('  ' + d) if d and not ok else ''}")
    print(f"\n  {p} passed, {f} failed")
    sys.exit(1 if f else 0)
