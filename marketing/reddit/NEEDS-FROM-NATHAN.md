# What I need from you

Five things. Two are blocking, three are not. Nothing runs until you say so.

---

## 1. A Reddit account — BLOCKING

Everything else is built and tested; this is the only thing that stops the system running.

**Create it yourself.** Never paste the password here — same rule as the Stripe, Twilio and
SMTP credentials. I don't need it and shouldn't have it.

What I do need, because the safety gate checks subreddit minimums against it:

- the username
- **account age in days**
- **comment karma**

Those two numbers are not optional. Many campus subreddits silently remove posts from
accounts below a threshold, and the gate treats *unverifiable* as a failure rather than a
pass. A brand-new account will fail r/csMajors-style minimums and that is correct — it means
build some comment history first, in the communities you plan to post in, before the system
proposes anything.

**Honest note:** an account created today, posting a link tomorrow, is the exact pattern
spam filters are tuned for. The most valuable thing you can do this week is be a normal
person in r/UMD for a few days.

---

## 2. Approvals — BLOCKING, and by design

This is the interruption the whole system is built around, and the only one.

```bash
cd ~/seatwatch/marketing/reddit
python3 queue.py show
python3 queue.py approve 12
python3 queue.py close --minutes 4
```

The `--minutes` is not bookkeeping. It is the denominator of the only metric this system is
judged on, and an unmeasured cost always looks like zero. Be honest about it — if a batch
took fifteen minutes, say fifteen.

Then you post it yourself, and record it:

```bash
python3 queue.py posted 12 https://reddit.com/r/UMD/comments/...
```

---

## 3. One small app change — for real attribution, not blocking

Right now I can only estimate which subreddit produced a watch, by time correlation. That is
an upper bound and I will label it as one every single time. It cannot tell a Reddit signup
apart from a friend you texted.

To measure it properly, `app.py` needs to remember where a signup came from:

1. add a `source TEXT` column to `users`
2. when someone lands on `/?r=CODE`, store `CODE` in a cookie
3. on account creation, write that cookie value into `users.source`

That's roughly fifteen lines and it's a **gated app change** — Build prepares it, you approve
the diff, same as everything else. It also isn't urgent: with a handful of users, time
correlation is nearly as good. It starts mattering at around twenty.

---

## 4. Decisions only you can make — not blocking

- **Communities that are off-limits.** Anywhere you'd be embarrassed to be seen promoting,
  or any subreddit connected to people who know you. Say so and I'll mark them blocked.
- **Whether to use your real identity.** The pitch is "I'm a UMD student who got shut out of
  CMSC216 and built this," and it works because it's true. It also attaches your real name to
  it permanently. I'm assuming yes, since it's the honest version — tell me if not.
- **Any spending.** There is none in this design. If that ever changes I'll ask first.

---

## 5. The SMS copy fix — blocks one specific claim

The gate currently refuses any draft mentioning texts, because your published SMS Terms,
Privacy Policy §7a, and `/text-alerts` still describe texts as a paid-plan feature — and your
toll-free number was verified on 2026-07-30 against exactly that description.

Text alerts are your strongest hook and I'd like to use them. Once the copy is corrected and
STOP/START are confirmed against real Twilio webhooks, flip one line:

```json
"sms_claims_allowed": true
```

in `marketing/reddit/claims.json`. Until then the gate blocks it, and that's the right
behaviour.

---

## What I am NOT asking you for

Which subreddits to try, how to word a post, whether an opportunity is worth replying to,
what to do about a draft that failed the gate. Those are mine. If I'm asking you about them,
I've misunderstood the job.

---

## Where it stands

Built and tested: 22 regression tests pass, and `seed_demo.py` runs the full pipeline on
sample data — 1 draft passes, 6 fail on purpose, one per rule class.

Not run against real Reddit. Not posted anywhere. Waiting on item 1.
