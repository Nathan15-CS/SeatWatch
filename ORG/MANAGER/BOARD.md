# SEATWATCH EXECUTION BOARD
Manager Agent · opened 2026-07-29 · statuses: proposed · waiting_for_information ·
ready · queued · assigned · in_progress · blocked · waiting_for_approval ·
needs_revision · completed · rejected · cancelled

**SINGLE MOST IMPORTANT NEXT ACTION: M-3 — activate email (CEO, ~2 minutes).**
Every other item is downstream of having a channel that actually reaches a stranger.

---

## PROJECT 1 — DEMAND (the real bottleneck)
Objective: one unrelated student signs up, receives an alert, and comes back.
Priority: **P1** · Status: in_progress · Deadline pressure: Fall add/drop closes ~mid-September.

| ID | Task | Owner | Status | Output | Definition of done |
|---|---|---|---|---|---|
| M-3 | ✅ **ACTIVATED 2026-07-29 19:36 UTC.** Google App Password installed transactionally into `/etc/seatwatch.env` (candidate validated: 16 keys, no duplicates; atomic rename; backup `/root/seatwatch.env.bak.20260729T193547Z`). Service restarted healthy, 4 SMTP keys present, site 200. `EMAIL_ENABLED: True`, `send_email(...) -> True`. **Remaining proof: inbox-vs-spam placement, then one real alert through the poller path.** ~~Activate SMTP per `ops/EMAIL-SETUP.md`~~ (Google App Password on support@, 3 env lines, restart, send-test, **check spam placement**) | **CEO** | waiting_for_approval | Email channel live | A real test alert lands in a normal inbox (not spam) for a non-CEO address |
| M-4 | Remove the fabricated testimonial (`app.py:1744`: ★★★★★ "Saved my semester." — real students) — LIVE on prod today with zero real users | Build | waiting_for_approval | Honest copy | Line replaced with a non-claim; deployed via `ops/deploy.sh app --app-approved`; verified by curl |
| M-5 | Beachhead beta: UMD / impacted courses (CMSC216 class), competitive-FOMO framing, small and measurable — not a broadcast | CEO (+ future Growth Agent) | proposed | 10–25 real students watching real courses | ≥1 non-family account creates a watch, receives an alert, returns |
| M-6 | Verify the feedback box + beta instrumentation are actually live (commits `a263771`,`7787f5d`,`438ec36` appear undeployed — footer box not found on prod HTML) | Build | ready | Deploy-state answer | Footer box present on prod, or deployed under CEO go |

## ✅ CLOSED 2026-07-29 — TRUST CLEANUP IS LIVE (no deploy performed)
Prod verified byte-identical to `cfeb366` for all four deploy-managed files (Manager hashed the
VM directly): app.py `51eefdc5…`, schools.py `e71f6db6…`, guardian.py `7c13c0ea…`,
confidence.py `92d85a84…`. `9b7c7f5` is an ancestor of `cfeb366`, so Build's undeclared app.py
deploy carried the trust cleanup with it. Live page: all ten prohibited strings return **0**;
both disclosure labels present. **Release packet cancelled — running it would have been a no-op
restart.** Record repaired: RECONSTRUCTED line in `DEPLOYED.log`, `deployed` tag moved to
`91f32b2` (labelled reconstructed — verified state, not verified procedure).
**Honest caveat: this landed by luck, not by process.** The fix shipped because it happened to
be an ancestor of an unrelated deploy. The same mechanism could as easily have shipped something
unreviewed — and on 07-29 it shipped four app.py deploys nobody recorded.

## ⚠️ M-20 (P1) — A THIRD LANE IS WRITING app.py
Build confirms commits `594c88c` and `4f2f7f1` (both em-dash work, 07-29 10:38 and 11:01) are
**not theirs and not mine**. Build measured 205 em dashes, then found only 143 on its own run —
~62 had already been removed by someone else. Git identity is shared ("SeatWatch"), so commits
cannot be attributed. **Duplicate writers produced duplicate work, not just a moving HEAD.**
Owner: CEO. Options: per-lane git worktrees, distinct git identities per lane, or a hard
single-writer rule for app.py.

## SECURITY EVENT 2026-07-29 — CLOSED, no compromise indicated
Unrequested **Link** verification SMS (shortcode 37542, genuine Stripe sender). CEO believes the
07-19 **Stripe** code was his own — that was the serious branch, now probably excluded. Link codes
require only knowledge of the email/phone at a Link-enabled checkout; no password is involved.
**Ruled out as cause:** SeatWatch infrastructure — `PAID_ENABLED=0`, zero Stripe API calls in 24h,
no payment commits, SSH key-only (`passwordauthentication no`, `permitrootlogin no`), last
interactive login 07-24 from the CEO's own IP; the 217 failed auth lines are bot noise that cannot
succeed against key-only auth.
**2026-07-29 CLOSED BY CEO ACTION: saved cards removed from the Link wallet.** The verification
code now protects nothing, so the SMS vector is neutralised at the source. No further Link work
required; passkey (M-27) is moot. Remaining items are unrelated hygiene, not incident response.
~~M-27 passkey on Link~~ (closes the SMS vector entirely) · M-28 trim/empty the
Link wallet if Link isn't used deliberately · M-29 finish moving the public business number to
Google Voice — personal cell on public business records is the likely harvest vector (already open
in the privacy-cleanup thread) · M-30 confirm whether the SeatWatch **Stripe merchant** account is
registered to the LLC or to the CEO personally (feeds M-23; must be settled before any student pays).
Also noted: Cloudflare and GPTZero charges are business expenses on a personal wallet — commingling,
feeds M-23.

## PROJECT 9 — RISK TRANSFER & LEGAL (opened 2026-07-29, from Grab's handoff)
**All CEO-owned and non-delegable. No agent may be author of record for legal text.**
| ID | Item | Owner | Priority |
|---|---|---|---|
| M-21 | Tech E&O + cyber insurance — WRITTEN confirmation of TCPA/SMS, privacy, breach, regulatory-defense and defense-cost coverage vs exclusions | CEO + broker | P2 |
| M-22 | Attorney review packet: TCPA posture, university-scraping exposure, Terms + arbitration/class-waiver + assent UX, privacy accuracy, governing law | CEO + attorney | P2 |
| M-23 | LLC corporate formalities — separate finances/records, contracts in the LLC name | CEO + accountant | P2 |
| M-24 | One-time professional appsec review before broad launch (mitigates AI-authored-security-code risk) | CEO | P2 |
| M-25 | Gate-1 copy drafts: "not affiliated with any university", alerts-not-guaranteed, COPPA under-13 line, privacy-accuracy pass, incident-response runbook, per-adapter ToS/robots risk classification | **Manager drafts → CEO + attorney approve** | P2 |
M-25 routing note: Grab offered to own these. **Declined — outside Grab's charter** (college discovery only,
`REGISTRY.md` §3) and the CEO has just refocused Grab on colleges. Manager drafts; attorney approves.
Timing: none of these blocks the demand sprint at ~10 students; all of them precede *broad* launch.

## ⚠️ M-20 LEAD (2026-07-29): Grab names the likely third writer as the **"Agent Research"** lane
and its "parallel-chip template". Two sessions match the window: `Agent Research` (local_3ad9fc5d)
and `Internet Problem Discovery Agent` (local_f1169c34). **Unconfirmed** — shared git identity still
prevents attribution. Fixing identity (Manager's recommendation 1) would have made this a lookup.

## ⚠️ M-26 (P1) — LANE CONFLICT, CEO MUST RESOLVE
CEO told Grab to **resume college hunting**; D-5 (CEO-approved 2026-07-29) **pauses broad discovery**
for the 14-day demand sprint, permitting targeted work only for a real student request, a clear
high-value opportunity, or production maintenance. Grab surfaced the conflict rather than picking a
side — correct behaviour. Per D-8 precedence, an explicit current CEO decision outranks the board, so
the instruction stands unless the CEO says it was casual. **Needs one word: resume, or hold to sprint.**

## SPRINT — 14-DAY DEMAND SPRINT (CEO-approved 2026-07-29 → ends 2026-08-12)
Goal: **~10 genuine external student users** (not Nathan, not family, not test accounts).
Coverage posture: broad autonomous college discovery PAUSED. Targeted college work allowed
only for (a) an actual student request, (b) a clear high-value opportunity, (c) production
maintenance. Grab's research and state preserved, nothing dismantled.

**Gate — nothing gets invited until these three are true:**
| # | Prerequisite | Owner | Status |
|---|---|---|---|
| G1 | Email channel live and spam-checked against an *external* inbox | CEO | waiting_for_approval |
| G2 | Fabricated testimonial removed from the live landing page | CEO go → Build | waiting_for_approval |
| G3 | Feedback box deployed (commits `a263771`,`7787f5d` appear undeployed) | Build | ready |

**Sprint tasks**
| ID | Task | Owner | Priority | Definition of done |
|---|---|---|---|---|
| S-1 | Pick 3–5 genuinely impacted UMD Fall courses (CMSC216-class demand) as the wedge | CEO | P1 | Named list, each verified full or near-full in the live registry |
| S-2 | One channel, done well: post where those students already are (course GroupMe/Discord, r/UMD) — competitive-FOMO framing, not feature copy | CEO | P1 | Posted; link is instrumented so signups are attributable |
| S-3 | Watch the first real alert end-to-end and confirm the human received it | Guardian | P1 | Human-confirmed receipt logged in the journal (also closes Guardian SC3) |
| S-4 | Log every request for an unsupported school, verbatim, with the requester | CEO | P2 | A simple running list — this is the metric that decides D-5's successor |

**Restart-expansion decision rule (evaluated 2026-08-12, minimum metric set)**
| # | Metric | Source | Target |
|---|---|---|---|
| 1 | External signups (users beyond the known 5) | `/admin/stats` `users`, `signups_by_day` | **≥ 10** |
| 2 | Activation: external signups creating ≥1 watch | `watches`, `watches_by_school` | **≥ 60%** |
| 3 | Reachability: external users with a provable channel (email or push) | beta instrumentation | **≥ 90%** |
| 4 | One real alert delivered to an external student, and acted on | `alert_attempt`, time-to-action | **≥ 1 delivered, action rate measurable** |
| 5 | Distinct external students requesting an unsupported school | S-4 list | **≥ 3** |

Decision: restart broad expansion **only if metric 1 ≥10 AND metric 5 ≥3.**
- Signups < 10 ⇒ the constraint is distribution or product. More colleges cannot fix it.
- Signups ≥ 10 but requests = 0 ⇒ coverage is already sufficient; work conversion instead.
Sprint stop conditions: ends 2026-08-12 regardless of outcome; no new governance artifacts;
$0 external spend; any P0 production issue preempts it.

## PROJECT 8 — SECURITY AUDIT FINDINGS + EMAIL DNS (2026-07-29)
Source: audit session's read-only security review, relayed by CEO. Manager re-verified both
load-bearing claims independently.
| ID | Item | Owner | Priority | Status |
|---|---|---|---|---|
| M-14 | ✅ **DONE 2026-07-29.** SPF + DMARC published at Cloudflare and verified by `dig`: `v=spf1 include:_spf.google.com ~all` at the apex, `v=DMARC1; p=none; rua=mailto:support@seatwatchapp.com; fo=1` at `_dmarc`. Both google-site-verification TXT records preserved. Aggregate reports begin arriving in 1–2 days; revisit tightening to `p=quarantine` only after reports show clean alignment. ~~SPF + DMARC missing~~ — Manager-verified by `dig`: no `v=spf1` record, no `_dmarc` record; DKIM present at `google._domainkey`; MX = `smtp.google.com`. DNS-only, no deploy, no code. | CEO | **P1** | ready |
| M-15 | **No `Cache-Control` on signed-in HTML** — `_send` (app.py:1985-2003) sets HSTS/CSP/XFO/Referrer-Policy but no cache directive. Latent, not an active leak. **Batch into the trust-cleanup release — it is one line of source but a four-file deploy.** | Build | P2 | blocked on running-code audit |
| M-19 | ✅ **RESOLVED 2026-07-29.** Proxied CNAME `www → seatwatchapp.com` added. Verified independently of the local resolver: `1.1.1.1` and `8.8.8.8` both return Cloudflare IPs; `--resolve`-bypassed fetch gives `301 → https://seatwatchapp.com/ → 200` serving the real page. TLS handshake succeeds, so Universal SSL covers www. Closes Build's security-tracker F5. ~~does not resolve~~ — Manager-verified 07-29: `dig www` returns nothing; apex resolves to Cloudflare `104.21.36.116`/`172.67.192.213`; `https://www…` returns 000 (connection failed). Anyone typing the www form gets a dead link. Fix = one proxied CNAME. **Do before any beta invite goes out.** Originally logged by Build as security-tracker F5. | CEO | **P1** | ready |
| M-16 | **Resolve where the two audit accounts were created.** "Read-only audit" and "I created two accounts" are contradictory. If prod: user count is polluted and sprint metric #1 is contaminated. | CEO | **P1** | waiting_for_information |
Verified-good from the same audit: 8/8 IDOR sweep, user-scoped destructive queries, signed
session cookies. Accepted as evidence **conditional on M-16** (environment unknown).

## ✅ RESOLVED 2026-07-29 — DEPLOYED-CODE IDENTITY ESTABLISHED
Read-only audit output (CEO-run). **Production runs HEAD `7787f5d` exactly.** All four
deployed files are byte-identical to their HEAD blobs:
| File | SHA-256 (VM == HEAD) | VM mtime |
|---|---|---|
| app.py | `98e61b41…8348c` | 2026-07-29 02:13:08 UTC |
| schools.py | `e71f6db6…56056` | 2026-07-29 01:14:58 UTC |
| guardian.py | `7c13c0ea…896a8` | 2026-07-26 06:14:28 UTC |
| confidence.py | `92d85a84…16a19e` | 2026-07-26 06:14:29 UTC |
Process: PID 102636, `/usr/bin/python3.10 app.py`, user `ubuntu`, cwd `/home/ubuntu/seatwatch`,
started 02:13:08 UTC, ActiveEnter 02:13:09 — **after** app.py's write, so the running process
loaded the current bytes. No git repo on the VM (file-level scp deploys only).

**Manager claims RETRACTED as a result:**
1. "24 commits of undeployed delta" — FALSE. The code shipped; only the *record* didn't. The
   deploy-truth gap was bookkeeping, not divergence.
2. "Feedback box appears undeployed" (M-6) — FALSE. It is live; it renders in the signed-in
   footer (app.py:1759/1872), not the landing page, which is why the landing-page grep missed it.
3. "A testimonial deploy would carry an undetermined pile of changes" — FALSE. HEAD ≡ prod, so
   a release now ships **only** the trust cleanup.
**Consequence: the hotfix-branch / reconstructed-baseline / `--ref` machinery is UNNECESSARY.**
Contingency design for a scenario the evidence ruled out. Do not build it.

**New finding — M-17 (P2): `.prev` rollback snapshots are STALE (2026-07-26).** Only
`app.py.prev` and `schools.py.prev` exist, both from the Guardian deploy. Rolling back *right
now* would revert 3 days of changes. `deploy.sh` refreshes `.prev` before overwriting, so the
next deploy self-corrects — but until then the rollback target is wrong.
**M-18 (P2): two un-logged deploys tonight** — schools.py 01:14:58, app.py 02:13:08. Build
session's last activity was 02:13:32, corroborating. Neither wrote a DEPLOYED.log line.

## PROJECT 2 — DEPLOY TRUTH (regression of a solved problem)
Objective: "what is running in production" is answerable from the record, not from archaeology.
Priority: **P1** · Status: blocked on CEO fact.

| ID | Task | Owner | Status | Output | Definition of done |
|---|---|---|---|---|---|
| M-1 | **ROOT CAUSE CONFIRMED 2026-07-29 (no CEO input needed):** `ops/deploy.sh:43-44` writes `DEPLOYED.log` **locally**, commits it, and moves the `deployed` tag. Exactly one such commit exists (`29da856`) and the `deployed` tag still points at it. Therefore **every deploy since 2026-07-26 bypassed `ops/deploy.sh`.** Remaining work: reconstruct the record. | Build | ready | Reconstructed `DEPLOYED.log` | Each post-07-26 deploy has a line with its sha + date, marked `reconstructed`; `deployed` tag moved to the true live sha |
| M-2 | Mandate `ops/deploy.sh` for ALL lanes (schools lane included) and record it in `CONTRIBUTING_AGENT.md` | Build | ready | Enforced discipline | Rule committed; next schools deploy produces a DEPLOYED.log line |

**Why this is P1:** the Guardian's confidence model applies a structural **P0 deployed-code-identity cap** — if we can't prove what's live, system confidence is capped regardless of everything else. This gap silently invalidates shadow-window evidence.

## PROJECT 3 — GUARDIAN SHADOW WINDOW
Objective: earn the evidence needed for the Phase E (enforcement) decision.
Priority: **P1** · Status: in_progress, **evidence collection has stalled**.

| ID | Task | Owner | Status | Output | Definition of done |
|---|---|---|---|---|---|
| M-7 | Catch-up checkpoint (day 1/2/3 checkpoints were due 07-27+; journal has NO checkpoint entries since 07-26) and a fixed checkpoint cadence to 08-09 | Guardian | blocked (needs CEO to run read-only commands) | Journal entries scoring SC1–SC7 | Each remaining checkpoint logged with pasted evidence, not assertions |
| M-8 | Close SC3: end-to-end alert proof + 2 drills — must include the **push leg**, not just ntfy 200 | Guardian | queued | Human-confirmed delivery | A human confirms receipt on a device, recorded in the journal |
| M-9 | Phase E enforcement decision packet (after window evidence) | Guardian → CEO | proposed | Go/no-go packet | CEO decision recorded in DECISIONS |

**Risk to flag now:** the hourly monitor only runs while the Claude app is open. It is quiet-unless-breach. **Quiet is currently indistinguishable from not running.** Healthchecks.io is the only real 24/7 alarm.

## PROJECT 4 — SEMESTER-BOUNDARY CLIFF
Objective: 804 schools survive the Fall→Spring term roll without silent death.
Priority: **P2 now, becomes P0 by late September.**

| ID | Task | Owner | Status | Output | Definition of done |
|---|---|---|---|---|---|
| M-10 | Term-bump plan for ~804 schools with auto-roll disarmed (manual bump obligation created 07-26); prior audit flagged an Oct-1 backward-roll false-open detonation | Guardian + Build | proposed | Written procedure + guarded re-arm design (ORD-A) | Procedure exists, rehearsed on ≥5 schools, CEO-approved |

## PROJECT 5 — SURVIVABILITY
Priority: **P2**

| ID | Task | Owner | Status | Output | Definition of done |
|---|---|---|---|---|---|
| M-11 | Verify the off-server backup ring is actually *scheduled and firing* (code committed 07-28; schedule unverified) | Run/Build | ready | Proof of a backup taken without a human | Two consecutive automatic backups + one rehearsed restore |
| M-12 | Post-window hardening: Healthchecks ping-URL rotation, VM IP exposure, STATS_KEY rotation | Guardian | queued (post 08-09) | Rotated secrets | All three rotated and verified |

---

## PROJECT 6 — GRAB CLOUD WORKER + MISSION CONTROL (from Operating Package, Project 1)
Objective: durable, recoverable, cloud-based college-research workers + routing/approval/reporting.
Package priority: P1 · **Manager priority: P3, status `proposed` — recommend DEFER.** Awaiting decision D-7.

Assessment (this is a challenge, not an endorsement):
- **It scales the wrong side of the business.** It industrializes supply — more colleges,
  faster — while the verified constraint is that no stranger has ever used the product.
- **Part of it already exists.** `send_message` routes to Grab and Build today; the `Agent`
  tool + `school-dash-researcher` dispatch research; scheduled tasks run cron work. Building
  Mission Control from scratch would duplicate working capability (your own rule).
- **The package's own instinct kills it.** It says "do not assume cloud hosting increases
  speed — identify the actual bottleneck." Applied one level up: the company bottleneck is
  demand, not Grab's throughput.
- **What's genuinely worth salvaging now:** durable state, leases, retries, idempotency, and
  cost ceilings for *any* unattended work. Those belong to the reliability lane and are
  cheap. The worker fleet is not.
Stop condition if approved anyway: **one** worker, one week, no concurrency until recovery
is proven, no auto-deploy of any integration, hard cost ceiling set in D-6 first.

### DECISION 2026-07-29: **POSTPONE until 2026-08-12.** Evidence below.
**Measured throughput baseline** (git log of `schools.py`, 07-20 → 07-29): 747 → 804 =
**57 schools in 8.5 days ≈ 6.7/day**, delivered in batches of 1–7, several per day. The premise
"one or two per run, sometimes none" describes *per-session* yield; *pipeline* output is 6.7/day.
At that rate 804 → 1,000 takes ~29 days **with the process that already exists**.
**The binding constraint is candidate supply, not session durability.** Recorded discovery
evidence: blind Banner/Colleague hostname guessing "NEARLY EXHAUSTED" (~640 domains re-tested,
2 net-new), crt.sh CT-log enumeration dead (wildcard cert), search-index yield ~1–2/round.
A durable 24/7 worker run against an exhausted candidate pool produces nothing faster —
**continuous operation does not refill a dry well.**
Therefore the upgrade would optimize a pipeline that (a) already works, and (b) currently
produces output of ~zero marginal value (0 confirmed external users; 0 logged requests for
unsupported schools). Re-decide on 2026-08-12 using sprint metric #5.

**2026-07-29 — CEO requested a full decision packet**: reconstructed business objective,
proceed/partial/postpone/reject call, value vs. the demand sprint, smallest useful version,
what evidence identifies Grab's *actual* bottleneck, phased plan + first task + owner +
acceptance criteria + stop conditions + a copy-paste Build packet if it proceeds. CEO said
it need not be immediate. **Queued as the Manager lane's next deliverable, after the email
and testimonial actions clear.** Do not lose this.

## PROJECT 7 — SESSION SPRAWL (opened by Manager 2026-07-29)
Priority: P2 · Status: ready
Observed: the hourly Guardian monitor spawns a **new session every hour** — 11 in the last
14 hours. Two consequences: (a) each run starts with no memory of the prior run, so it can
detect a point-in-time breach but **cannot see a trend** (slow degradation is invisible to
it); (b) the session list is now unusable for finding real work. M-13: decide whether the
monitor should write a durable append-only health log the next run reads. Owner: Guardian.

## Standing stop conditions (apply to every task on this board)
No task runs open-ended. Unless a task states otherwise:
- **Max attempts:** 2. A third attempt requires a written reason and CEO acknowledgement.
- **Max runtime:** one working session. Longer ⇒ report partial findings and re-scope.
- **Cost ceiling:** $0 external spend. Model usage: stop and report if a task needs more
  than one session of effort to produce its first verifiable output.
- **Completion condition:** the Definition-of-Done cell, proven by pasted evidence.
- **Failure condition:** the acceptance test fails twice, OR the owner lacks the access
  required (see `PERMISSIONS.md`) ⇒ status `blocked`, escalate, do not improvise around it.
- **Escalation condition:** anything touching money, credentials, public copy, prod
  behavior, or customer data ⇒ CEO before action, not after.
- **Cancellation:** the CEO says stop, or a higher-priority P0/P1 preempts it — recorded
  in `DECISIONS-AND-RISKS.md`, not silently dropped.

## Evidence decay rule
Any production claim carries its as-of date. The Manager lane has **no live prod read
access** (`PERMISSIONS.md`). Prod facts older than 7 days are `waiting_for_information`,
not facts. Last CEO-pasted prod truth: **2026-07-26** (users=5, watches=17).

## Held for specialists that do not exist yet
- **Growth Agent** — M-5 execution, channel tests, funnel metrics. Justified only once M-3/M-5 prove a channel works; premature today.
- **Support Agent** — inbound from the feedback box. Volume is ~0; CEO handles it manually until it isn't.
