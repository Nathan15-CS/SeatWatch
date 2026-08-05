# SeatWatch — Reddit traction system

A mostly-autonomous pipeline that turns Reddit into created seat alerts, while costing Nathan
as close to zero minutes as possible.

**It cannot post.** There is no Reddit write path anywhere in this codebase, deliberately.
Everything here prepares; a human publishes. That is the difference between a marketing
system and a spam operation, and the accounts a spam operation burns are not recoverable.

---

## The metric

**Alerts created per founder-minute.**

Not upvotes, not impressions, not signups. A *watch created* is the moment a student commits
to the product. The denominator is real and logged: every minute spent reviewing a batch is
recorded, and `report.py` divides by it. A brilliant post that costs twenty minutes to
approve loses to a decent one that costs two.

---

## Pipeline

```
  subreddit-finder ──▶ subreddits(candidate)
                            │
  rules-checker ────────────┼──▶ subreddit_rules (verbatim, versioned)
                            │         │
                            ▼         ▼
                       approved   blocked ◀── sticky, survives rediscovery
                            │
  opportunity-finder ──▶ opportunities (a real student, stuck, right now)
                            │
  content-writer ──────▶ drafts (one per opportunity, never reused)
                            │
                            ▼
                  ┌─────────────────────┐
                  │  safety.py — GATE   │  deterministic · versioned · fails closed
                  └─────────────────────┘
                       │            │
                    fail         pass
                       │            │
                  (dead end)  safety-reviewer  ◀── may veto, may NOT approve
                                    │
                              batch_items(pending)
                                    │
                       ══ NATHAN APPROVES ══        ◀── the only interruption by design
                                    │
                            he posts it himself
                                    │
                       queue.py posted <id> <url>
                                    │
                  analytics-tracker ──▶ post_outcomes ──▶ report.py
```

A draft whose newest safety review is not `pass` cannot enter a batch. A draft with no
approved batch item cannot become a post — `store.record_post()` raises `PermissionError`,
so it cannot even be back-filled after the fact. Both are enforced in code, not convention.

---

## Why the gate is code and not a model

The three standing rules — no spam, no fake testimonials, no rule breaking — are exactly the
rules a language model can be argued out of, and the writer agent has every incentive to
argue. A regex cannot be persuaded that this one testimonial is illustrative.

SeatWatch has already shipped a fabricated testimonial to production once
(`★★★★★ "Saved my semester." — real students`, removed 2026-07-29, with zero real users
behind it). This gate exists to make that structurally impossible rather than culturally
discouraged.

The LLM safety reviewer still reads every passing draft. It runs **after** the gate and can
only ever be stricter — it may veto, it may not approve. A model is good at "this reads as
astroturf"; it is not trustworthy as the last line.

### What the gate enforces

| rule | why |
|---|---|
| `fabricated_testimonial`, `star_rating`, `invented_usercount` | there are no real ones |
| `false_claim` | numbers are checked against `ops/coverage.json` — **890 proven, not the 928 in the registry.** The 38-school gap is adapters that report everything open or return nothing; advertising them sends a student to a school that cannot alert them |
| `sms_claim_blocked` | texts may not be advertised until `claims.json` says the published SMS Terms stop describing them as paid-only. The toll-free number was verified against that description |
| `guarantee`, `superlative`, `false_scarcity` | promises the product cannot keep |
| `no_disclosure` | a post must say plainly that you built it; undisclosed promotion is astroturf |
| `blocked_subreddit`, `promo_forbidden`, `stale_rules`, `mod_permission_required` | community rules, read verbatim, no older than 14 days |
| `account_too_new`, `account_low_karma`, `account_unverified` | subreddit minimums — *unverifiable is a failure, not a pass* |
| `subreddit_cooldown`, `daily_cap` | 1 post per community per week, 2 per day total |
| `near_duplicate` | 75% token overlap — the same post in two communities is the clearest spam signal there is |
| `url_shortener`, `foreign_link`, `too_many_links` | auto-removal triggers |

**Fails closed** on everything: unknown subreddit, unread rules, stale rules, unreadable
coverage data. A false failure costs one rewrite. A false pass costs a community.

---

## Files

| file | does |
|---|---|
| `store.py` | schema + accessors; the state machine lives here |
| `safety.py` | the deterministic gate. `CHECKER_VER` is stamped on every review |
| `queue.py` | the approval queue CLI — build / show / approve / reject / close / posted |
| `report.py` | attribution + the weekly report |
| `claims.json` | which claims are currently true. Fails closed on anything missing |
| `seed_demo.py` | end-to-end run on sample data; 1 draft passes, 6 fail on purpose |
| `test_safety.py` | 22 regression tests |

Agents live in `~/seatwatch/.claude/agents/reddit-*.md`.

---

## Running it

```bash
cd ~/seatwatch/marketing/reddit
python3 seed_demo.py       # see the whole pipeline on sample data
python3 test_safety.py     # 22 tests
```

Real use, driven by the `reddit-marketing-manager` agent:

```bash
python3 safety.py          # gate every draft
python3 queue.py build     # gather passing drafts into a batch
python3 queue.py show      # review
python3 queue.py approve 12 14
python3 queue.py close --minutes 5
python3 queue.py posted 12 https://reddit.com/r/UMD/comments/...
python3 report.py --days 7
```

---

## Attribution — read this before trusting a number

Two modes, and the report always states which it used.

**`exact`** — requires a `users.source` column populated from the `?r=` code. That is the one
small app change this system needs; see `NEEDS-FROM-NATHAN.md`. Until it ships, this mode is
unavailable and the report says so rather than quietly degrading.

**`window`** — watches created within 72h of a post, at that subreddit's school. An
**upper bound**. It cannot separate a Reddit signup from a friend Nathan texted. At six
users, one misattributed watch moves the headline number by 100%, which is why the report
labels every window figure as an estimate on every line.

Reporting an estimate as a measurement is the failure this system is most likely to commit.

---

## Read-only against production

`report.py` opens the newest snapshot in `~/seatwatch-backups/` with `mode=ro`. Marketing
must never be able to write to, lock, or bloat the database that decides whether a student
gets alerted.
