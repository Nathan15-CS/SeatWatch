# DRAFT — Refund Policy + revised Terms §6 (Grab, 2026-07-21)

**STATUS: DRAFT FOR NATHAN'S REVIEW → then Build implements. NOT legal advice.**
Written to commercial standard, not by a lawyer. A Maryland attorney should review before this
governs live transactions — especially its interaction with the existing §12 arbitration clause.

---

## WHY THIS CHANGE (the commercial argument, not the legal one)

Current §6 says *"Except where the law requires otherwise, all payments are final and non-refundable."*

The failure mode that will actually happen: a student pays $19.95, **no seat ever opens**, and they
feel cheated even though the service performed exactly as described. With no refund path, their only
lever is a **chargeback**. Each chargeback costs ~$15 + the disputed amount, is decided by the card
issuer (not by us), and a rising dispute rate threatens the Stripe account itself.

**A refund is always cheaper than a dispute.** At current volume (~0 paying users) a generous policy
costs essentially nothing and buys trust; a stingy one costs the payment processor relationship.

Second reason: card-network rules (Visa/Mastercard) expect a **clearly disclosed** refund policy at
point of purchase. "No refunds ever" disclosed nowhere near checkout is the weakest possible position
in a dispute.

---

## THE PROPOSED RULE (plain version)

> **Full refund within 14 days — as long as we haven't already sent you a seat-opening alert.**
> Once we've alerted you, you've received the thing you paid for.
> If we materially failed (outage, never monitored your class, wrong data), we refund regardless.

Why this shape:
- **Verifiable from our own logs** — the `alerted` column on each watch already records this exactly.
  No judgment calls, no he-said-she-said.
- **Fair both directions** — a student who changes their mind before getting any value gets out clean;
  a student who got the alert and grabbed the seat can't claw the money back after being served.
- **Kills the main chargeback scenario** — "no seat opened" is precisely the case where the customer
  has NOT been alerted, so they qualify for a full refund. The angriest customer is the one we refund.

---

## A. NEW STANDALONE REFUND POLICY (`/refunds`)

**Refund Policy** — Last updated: [DATE]

**1. The short version.** If you change your mind, email us within 14 days of your purchase and we'll
refund you in full — as long as we haven't already sent you an alert that a seat opened. If SeatWatch
materially failed to do its job, we'll refund you regardless of timing.

**2. Full refund, 14 days, before your first alert.** Paid plans are a one-time payment for a single
academic term. You may request a full refund within 14 days of purchase provided we have not yet sent
you a seat-opening alert for any class on your account. Email
[support@seatwatchapp.com](mailto:support@seatwatchapp.com) from the address on your account and ask.
You do not need to give a reason.

**3. After we've sent an alert.** Once we've sent you a seat-opening alert, the service has delivered
what you paid for — whether or not you got the seat — and the payment is no longer refundable under
section 2. Registering for a class is your responsibility and depends on your school, your timing, and
other students (see Terms §4 and §7).

**4. If we failed, we refund.** Regardless of the 14-day window, contact us and we will make it right —
including a full refund — if SeatWatch materially failed to perform: for example, an extended outage
during your watch, a failure to monitor a class we accepted, or seat data for your school that was
materially wrong on our side.

**5. "No seat ever opened" is not a service failure.** SeatWatch monitors and alerts; it cannot create
a seat. A class where no seat opens is the service working correctly, not failing. That said, if this
happened and you're inside the 14-day window without having been alerted, section 2 applies and you get
a full refund.

**6. How refunds are issued.** Approved refunds go back to the original payment method through Stripe,
normally within 5–10 business days depending on your bank. We refund the amount you paid; we cannot
refund your bank's currency-conversion or other third-party fees.

**7. What happens to your plan.** When a purchase is refunded, the paid plan ends and your account
returns to the free plan. Any watches beyond the free-plan limits stop being monitored.

**8. Purchases made through the Apple App Store or Google Play.** If you bought through an app store,
that store — not SeatWatch — processes the payment and controls refunds under its own policy. Request
those refunds directly from Apple or Google. We'll help where we can, but we cannot issue them.

**9. Please talk to us before disputing a charge.** If something's wrong, email
[support@seatwatchapp.com](mailto:support@seatwatchapp.com) first — we respond quickly and we'd rather
refund you than argue. Filing a chargeback without contacting us delays resolution for everyone and may
result in the account being closed.

**10. Your legal rights.** Nothing here limits any refund or cancellation right you have under
applicable consumer-protection law. Where the law gives you more than this policy does, the law wins.

---

## B. REVISED TERMS §6 (replaces current §6 Payments)

**6. Payments and refunds.** Your first class is free. Paid plans are one-time payments for a single
academic term — they are not subscriptions and do not auto-renew — at the prices shown when you buy.
Payments are processed by our payment provider (Stripe); we never see or store your full card details.
**Refunds are governed by our [Refund Policy](/refunds), which is part of these Terms: in short, a full
refund within 14 days of purchase if we have not yet sent you a seat-opening alert, and a refund
regardless of timing if we materially failed to perform.** Purchases made through the Apple App Store
or Google Play are refunded by that store under its own policy, not by us. You are responsible for any
applicable taxes. Prices and plans may change for future terms.

---

## C. IMPLEMENTATION NOTES FOR BUILD (all gated on Nathan's go)

1. Add `/refunds` route + `REFUNDS` constant alongside `TERMS` (app.py ~1112) using the same `_PSTYLE`.
2. Replace §6 in `TERMS` with section B above; bump BOTH "Last updated" dates.
3. Add a `/refunds` link to the Terms footer line and the Privacy footer line (they cross-link today).
4. **Link the Refund Policy at the point of purchase** — card-network expectations and dispute defense
   both favor it being visible at checkout, not buried. A one-line "14-day refund policy" link near the
   pay button is enough.
5. The 14-day/alerted test is decidable from existing data: `watches.alerted` + `users.plan_purchased_at`.
   Consider a tiny admin helper that answers "is this user refund-eligible?" so Nathan isn't reasoning
   about it manually under time pressure.
6. Terms §1 already allows 13+ with guardian permission. Worth Nathan noting that dual-credit HIGH
   SCHOOL sections exist across the shipped schools, so some purchasers genuinely may be minors —
   a lawyer should confirm the guardian-consent language is adequate for taking their money.

## D. WHAT I DID NOT TOUCH
- §12 arbitration / class-action waiver — highest legal risk, enforceability is jurisdiction-sensitive
  and evolving. Leave it to the attorney.
- The Privacy Policy — unchanged by this.
- §7 No guarantee and §9 Limitation of liability — already strong and consistent with the above.
