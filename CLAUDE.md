# SeatWatch — working notes for any Claude session

## Start here, every session

```bash
python3 ops/triage.py
```

Asks **production** what is wrong right now: open incidents, alerts that reached nobody,
stranded watches, a stopped poller, schools gone dark. Exit `0` nothing needs you, `1`
something does, `2` it could not check — and `2` is never to be read as fine.

Nathan receives the operator mail and should not have to relay it into a session by hand.
A model has no inbox, so a session asking production on arrival is the mechanism that
actually closes that loop. Run it before proposing work; the queue is usually in
`ORG/MANAGER/` and the real state is on the VM.

## The one rule that keeps being relearned

**A check that cannot tell healthy traffic from a defect will eventually be believed about
the wrong one.** Three separate instances on 2026-08-14, each of which reported a healthy
system as broken:

- a `no_channel` row escalated as the first-ever silent delivery failure — the student had
  clicked through to the registrar **13 seconds earlier**. A deliberately suppressed repeat
  was being logged identically to "reached nobody".
- `ops/student-view.py` printed **DO NOT POINT STUDENTS AT THIS** about incidents that
  predated the fix, because it reads `DEPLOYED.log`, which is not in the deploy set and does
  not exist on the VM. Run it locally.
- the section-collapse detector reported `DROPPING 13 of 13 sections` at a school that had
  simply not answered. Zero is the one count a genuine collapse cannot produce.

When adding a check: make "I could not tell" a distinct outcome from "it is fine".

## Verifying, in order of what it actually proves

| | proves |
|---|---|
| `python3 ops/triage.py` | what is wrong in production **right now** |
| `python3 readiness.py` | the code is correct (local, synthetic, ~10 min) |
| `python3 ops/student-view.py` | whether a **student** would be annoyed — run LOCALLY |
| `sudo python3 ops/verify-storm-fix.py` | did the two alert gates hold under real churn (on the VM) |
| `python3 ops/gate.py <school>` | is a school's seat data trustworthy enough to ship |

`readiness.py` and the live suites make real network calls. **Do not run anything else
network-heavy alongside them** — doing so corrupted a wall-clock timeout assertion and
produced two phantom failures on 2026-08-14.

## Deploying

```bash
SEATWATCH_VM=ubuntu@<host> ./ops/deploy.sh app --app-approved
```

- School additions deploy direct (accuracy-gated). **Money, UI, pricing and paid changes
  need Nathan's explicit go.**
- Pipe deploy output through `set -o pipefail`, or a failed deploy reports success — in
  zsh the exit status comes from `tail`. A scp that dies midway leaves a PARTIAL deploy:
  the new file on disk, the old code still running.
- `ops/coverage.json` is deliberately NOT in the deploy set. It is a measurement the VM
  makes nightly, not source. Shipping it republished a stale local copy over the real one.

## Alert behaviour, and why

Two gates, both live, sharing one repeat constant so they cannot drift:

- **`CONFIRM_SECONDS=120`** — an opening must survive two minutes before anything is sent.
  Measured over every alert ever sent: 18 openings, **median life 35 seconds**, 14 of 18
  gone inside two minutes, the other 4 open for about an hour. Nothing in between. Worse,
  blips were spending the repeat cooldown, so only 2 of the 4 genuinely takeable seats ever
  reached anybody. Confirming took that timeline from 8 emails to 4 **and** raised real
  seats delivered from 2 to 4.
- **`REPEAT_ALERT_COOLDOWN_S=1800`** — one alert per watch per 30 minutes.

SMS rule (Nathan, 2026-08-14): **every genuine opening texts; the same opening never texts
twice.** The limit is per OPENING — any cap counted per term silences the seat somebody was
waiting for. `SMS_PER_WATCH_MAX` is a runaway detector, not a product limit.

Channels are **email and text only**. Push and ntfy were retired: they report success while
reaching nobody.

## Context worth having

- **Zero external users.** All accounts are Nathan and family. The bottleneck is
  distribution, not coverage or schools. 890 schools with no users is the same product as
  900 with no users.
- Site school count comes from `ops/coverage.json`, not `len(SCHOOLS)`.
- Accuracy is the reputation of the product and is never traded for growth or speed.
