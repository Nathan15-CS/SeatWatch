# SeatWatch launch plan

**Written 2026-08-01.** Target window: UMD schedule adjustment (first 10 days of fall
classes, late Aug into Sept). Miss it and the next real window is January.

**Where you actually are:** the product works. 853 gated schools, guardian in enforce,
SMS live, 273 readiness checks green. **Zero external users.** Every account is you or
family. Nothing on this list below item 8 fixes that, and item 8 is the whole plan.

---

## PHASE 0 — Unblock SMS (tonight, ~10 minutes)

SMS is live right now with a **broken opt-out**. You texted STOP and we rejected your own
revocation with a 403. You are still opted IN. Zero students have consented so real
exposure is nil — but that ends the moment Phase 2 works.

### 0.1 Deploy — YOU

```bash
cd ~/seatwatch && ./ops/deploy.sh app --app-approved
```

Carries three things, all verified: the Twilio signature fix, per-school freeze scoping,
and 853 gated schools (845 → 853, all nine new/modified adapters gated against live
registration systems, two shared-host isolations proven by cross-query).

### 0.2 Text STOP to your SeatWatch number — YOU
### 0.3 Then text START — YOU
### 0.4 Tell me — I confirm both recorded in `sms_consent`

**GATE A: do not mention SMS to a single student until 0.4 passes.**
STOP is the one path with legal teeth, and it has never once worked against a real
Twilio request.

---

## PHASE 1 — Clear the runway (this week)

### 1.1 SMS copy fix — I DRAFT, YOU APPROVE  ← before any outreach

Your published SMS Terms, Privacy Policy 7a, and `/text-alerts` page all say texts are a
paid-plan feature. The code texts free students. **Twilio's toll-free verification was
approved on 2026-07-30 against that published description.** The gap opens the instant a
free student opts in — which is the instant Phase 2 succeeds.

Say go and I draft the revised wording for your review.

**GATE B: no outreach until this ships.** Otherwise you are racing your own compliance gap.

### 1.2 Finish the offsite backup — YOU (~5 min, console)

You are **not** currently exposed — five verified copies live on your Mac, newest hours
old. What you lack is one that survives the laptop being shut.

Bucket `seatwatch-backups` exists and is Private. Two steps left:

- **Lifecycle rule:** bucket → Lifecycle Policy Rules → Create Rule →
  name `keep-14-days`, action **Delete**, **14** days, target Objects.
- **PAR:** bucket → Pre-Authenticated Requests → Create →
  name `seatwatch-server-push`, type **Bucket**, access **Permit object reads and writes**,
  **tick** Enable Object Listing, expiry one year.

Oracle shows the PAR URL **once**. Copy it, then on the server (never in chat):

```bash
sudo sed -i '/^OCI_BACKUP_PAR=/d' /etc/seatwatch.env && printf 'OCI_BACKUP_PAR=%s\n' 'PASTE_URL_HERE' | sudo tee -a /etc/seatwatch.env >/dev/null && sudo chmod 600 /etc/seatwatch.env
```

Then tell me and I upload tonight's snapshot, verify Oracle's checksum, confirm the bucket
refuses an unauthenticated read, and restore a copy to prove it works.

### 1.3 Upload the ad — YOU

36-second vertical, built, at `marketing/SeatWatch-ad-vertical.mp4`. Only you can post it.

### 1.4 NOT DOING: payments

Dropped deliberately. Zero users means the promo has nothing to convert. Turning payments
on buys refunds, disputes and support obligations on Terms no attorney has read, against
revenue that does not exist. **Turn them on when a student asks to pay you.**

---

## PHASE 2 — The only item that decides anything (weeks 2–3)

### Get TEN real UMD students using it before classes start.

Not a hundred. Ten. They prove the alerts fire, and they are who tells everyone else
during add/drop.

**Why UMD:** 11 of your 14 existing watches are already there, it is your most-tested
adapter, and you know the campus. Fifty students at one school who talk to each other
beat 853 schools where nobody does.

**Where — in order of yield:**
1. GroupMe class groups (where students already panic about closed sections)
2. Department Discords, CS first
3. The CS building, in person

**Not Reddit first.** r/UMD reads a launch post as an ad and removes it. Reddit works
later, as a genuinely useful post, once you have users to point at.

I write the copy. You post it — it needs your name on it, not mine.

---

## PHASE 3 — The window (late Aug → mid Sept)

**Confirm the exact date first:** registrar.umd.edu → Calendars → Fall 2026 first day of
classes. Schedule adjustment is the first 10 days after it.

That is when demand for exactly this product peaks. Everything above exists to make sure
you are ready when it opens.

---

## Deliberately not on this list

**More schools.** You have 853 and zero users. Coverage stopped being the bottleneck long
ago, and adding more is the most comfortable way to avoid Phase 2.

---

## Order of operations

```
0.1 deploy → 0.2 STOP → 0.3 START → 0.4 verified   ══ GATE A ══
1.1 copy fix shipped                               ══ GATE B ══
1.2 backup · 1.3 ad   (anytime, not blocking)
2.  ten UMD students
3.  schedule adjustment push
```
