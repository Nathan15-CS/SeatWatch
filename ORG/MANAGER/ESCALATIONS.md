# ESCALATIONS — Manager inbox

Unattended lanes (scheduled tasks) cannot message the Manager session directly —
`send_message` is unavailable in unattended runs. They write here instead, and commit.

**Manager: read the OPEN items at the top of each working session.** Move an item to
RESOLVED with a date and one line of disposition once it is handled. Do not delete.

Format:

```
### YYYY-MM-DD HH:MM — <LANE> — <SEVERITY: INVESTIGATE | STOP> — <one-line headline>
Evidence: <verbatim numbers / error text / file+line — no paraphrase>
Impact: <who is affected, right now>
Asked of Manager: <the specific decision or action needed>
```

Severity: **STOP** = same-day action, users are affected now. **INVESTIGATE** = needs a
decision but is not actively harming anyone.

---

## OPEN

### 2026-08-03 13:45 — BETA PULSE — INVESTIGATE — off-server backup pull has failed 2 days running; host refuses SSH, so the newest data copy is 54h old and the pulse is blind

Evidence: `~/seatwatch-backups/pull.log`, verbatim:
```
[2026-08-02 12:59:02] FAIL: no backups found on the server (/home/ubuntu/seatwatch/backups)
Read from remote host 141.148.27.134: Connection reset by peer
client_loop: send disconnect: Broken pipe
[2026-08-03 09:43:11] FAIL: no backups found on the server (/home/ubuntu/seatwatch/backups)
```
Earlier failure same pattern: `[2026-07-30] ssh: connect to host 141.148.27.134 port 22: Network is unreachable`.
Newest local backup is `watches-20260801-030001.db` (2026-08-01 03:00 UTC). `https://seatwatchapp.com/`
returns HTTP 200, so the app itself is serving. Note the correlation: `guardian_incidents` id 1
has USF dark 2026-08-02 12:03–13:51, overlapping the 12:59 pull failure — likely one host-level
network/VM event, not two.

Impact: No user is being harmed right now (site up, alert path clean, NO_CHANNEL 0). The damage is
to visibility and recovery: the only off-server copy of the database is 54h stale, and the beta
pulse can no longer tell whether a new student signed up — it re-read the same snapshot twice.
Goes STOP if the 2026-08-04 pull also fails.

Asked of Manager: get someone onto the box today to establish whether this is SSH/network only or
the nightly backup job itself has stopped writing to /home/ubuntu/seatwatch/backups. Both failure
messages say "no backups found on the server", which would mean the job is not producing files —
a different and worse problem than an unreachable host.

### 2026-08-04 04:30 — GUARDIAN (shadow checkpoint, day 8.9/14) — INVESTIGATE — first incident of the window: USF was dark for 1h48m and paged nobody

**Evidence — `guardian_incidents` id 1, verbatim:**
```
kind=adapter_down  severity=yellow  school=usf  watch_id=0  count=268
first_seen=2026-08-02 12:03   last_seen=2026-08-02 13:51
evidence="272 consecutive failed/empty fetches; last ok 6574s ago"
contained="fail-closed: no data -> no alerts from this school"
status=resolved
```
Window totals: 28,103 cycles, **27,787 GREEN / 316 YELLOW / 0 RED**. YELLOW by day is
5 / 10 / 4 / 12 / 7 / **273** / 5 / 0 — the 273 is 2026-08-02 and is entirely this incident.
USF recovered unaided: last 300 cycles show usf `checked_open_already` 600× with zero failures,
and the 20 most recent cycles are all GREEN. Confidence unchanged (score 40 / tier LOW / binding
`P0_deploy_identity`); `P6_maturity` rose 73 → 100; no factor dropped. Term-roll detector clear.

**Impact.** Two live USF watches went unmonitored for 1h48m on 08-02. Containment worked as designed
— fail-closed meant no data produced no alerts, so nothing was mis-alerted and no watch was dropped.
The exposure is detection, not correctness: `adapter_down` is classified **yellow**, and **only RED
pages**, so a school can go fully dark and no human is told. It surfaced here only because a
scheduled checkpoint happened to read the table two days later. This is the same shape as the
already-open M-10 term-roll paging gap (`blocked_wrong_term` is yellow, pages nobody).

**Asked of Manager:**
1. Decide whether `adapter_down` sustained past a threshold (e.g. >15 min of consecutive failures on
   a school with live watches) should page, or be promoted to RED. Right now nothing does.
2. Route with the existing M-10 paging gap — one fix to the paging predicate likely covers both;
   they should not be worked twice.
3. No action needed on USF itself; it is healthy and the incident is `status=resolved`.

**Also, unchanged and now dated:** the **7 success criteria are still not in the repository** (first
raised 07-31). `grep` over `ORG/` and `ops/` finds only references to them — `guardian-v1-freeze.md:20`
and the Phase-D journal — never the criteria. The shadow window closes **~2026-08-09, five days out**.
Reconstruct them before it closes or the Phase E enforcement decision is scored against goalposts no
lane can produce.

### 2026-07-31 19:40 — GUARDIAN — INVESTIGATE — Phase-E evidence is IN and unanimous; bring the enforcement decision forward
**CORRECTED 19:58.** My first version of this claimed shadow produced no durable evidence. That was
wrong and I am glad it was caught before Guardian acted on it. There are TWO shadow signals, and only
one of them is volatile:
- **`cycle.would_block` — DURABLE and COMPLETE.** Persisted as JSON in `guardian_cycles.notes`.
  All **19,363 of 19,363 cycles** carry the field; **every one is `"would_block": []`**. Zero cycles
  where enforcement would have blocked anything, across the entire 2026-07-26 06:14 → 07-31 02:59 window.
  This is the primary Phase-E evidence and it exists.
- **`_LAST_DIVERGENCE` — volatile.** guardian.py:428, in-memory, `del [:-100]`, reset on process start,
  never written to the DB (only consumer is guardian.py:670). This is the *dishonest-latch* signal.
  It only fires when an alert fires, so its whole possible population is the 12 alerts below — and
  that population is fully reconstructible from `alert_log`, which I did. Nothing was actually lost.
  Worth fixing so it is queryable, but it is not a gap in the decision.
- `guardian_incidents` = 0 rows, all kinds. `guardian_cycles` has no dedicated divergences column;
  the evidence lives in `notes`.
- 19,363 cycles (19,327 GREEN / 36 YELLOW / 0 RED) produced **12 alerts total**:
  ASTR100 uid 5 → ntfy+webpush+email; ASTR100 uid 6 → ntfy+email;
  MUSC205 ×5 → watch 4, `user_id` NULL, ntfy only (topic-only; the honest rule latches these by
  design via `ntfy_ok and not (has_push or has_email)`).
  **Enforcement would have been a no-op on 100% of alert history — zero dishonest latches.**

Impact: Beta students all sign in with Google, so all have email enrolled. Under **shadow**, an alert
where email fails and only ntfy succeeds still latches — student never told, system records it handled.
Under **enforce** it refuses to latch and retries until a human channel works. Enforce fails **loud and
recoverable** (duplicate alerts); shadow fails **quiet and permanent**. Live now, on every beta signup.

Asked of Manager → routed to Guardian:
1. Check this reading — especially whether divergence evidence persists somewhere I did not find.
2. Produce the Phase-E go/no-go packet **now, on the logic, not on the 08-09 calendar date**.
   A reasoned "no, keep shadow" is an acceptable answer; the lane is Guardian's.
3. **Hard prerequisite:** M-35 (`e7db421`, committed, NOT deployed) must ship first. Enforce + the old
   enrolment definition ⇒ correctly-delivered alerts fail to latch and re-fire every cycle. M-35
   redefines enrolled as *enrolled AND enabled* and pins it in enforce-mode tests.
4. Fix divergence persistence regardless of the mode decision.
5. **Dated, separate:** the M-10 term-roll paging gap — nothing pages on `blocked_wrong_term`; the
   hourly monitor's breach conditions omit it. Risk window opens **late September, inside the beta**.
6. Not a blocker: MUSC205 fired 5× on watch 4, two pairs ~64s apart (ids 8/9 at 1785421929/1785421993,
   ids 10/11 at 1785439954/1785440019). Genuine add/drop churn, or re-firing? Guardian's call.

Flipping `GUARDIAN_MODE` is a production change — CEO approval, Nathan's hands. Deliver the packet only.

**ADDENDUM 20:15 — the recommendation REVERSED. Do not flip enforce as a single step.**
Build refuted my sample-size inference (correctly: `would_block` is only evaluated inside
`flush_alerts` over `cycle.pending`, so "0 across 19,363 cycles" is really "0 across **7 gate
evaluations**" — an untested branch and a passing branch are indistinguishable from the stored value).
Chasing their "mass-freeze: 0 real evaluations" line found the reversal:

- guardian.py:337-362 — under **enforce**, `n > MAX_ALERTS_PER_CYCLE` (default **10**) sets
  `frozen=True`, writes the `guardian_freeze` state key, sends **nothing**, and is **sticky until a
  human clears the key on the server**. Under **shadow** the same event only appends to `would_block`
  and pages; **alerts still go out.**
- This inverts my central argument to Nathan. Enforce is loud but **not quickly recoverable** — it
  needs someone SSH'd in during a registration surge, which is exactly when it would trip.
- Reachable at beta scale in a way it never was at 14 watches: ~25 students × ~2 watches ≈ 50, and a
  registrar block-release can transition 11+ inside one 20s cycle.

**Live watch concentration (Build, from prod):** 14 watches — umd 11 (**79%**), usf 2, ou 1.
A parse break is *nearly all of one school at once*; a legitimate release is *whatever subset of
students wanted those courses*. **The two differ in shape, not volume — a global integer cannot see
shape**, so any constant is either too low (freezes real surges) or too high (misses cascades), and
it drifts wrong as watch count grows.

**Ordered sequence — step 2 is not one item:**
1. M-35 ships.
2. `MAX_ALERTS_PER_CYCLE=25` (Build's number; justified: a UMD parse break at this concentration
   yields ~40 simultaneous, over the cap; busiest cycle in all history was 1. Good for ~50-150
   watches, revisit before 200) **AND** resolve the stickiness question.
3. Only then `GUARDIAN_MODE=enforce`.

**ADDENDUM 2 — 2026-08-01, from Nathan's question "what if we grow and I hit 10 alerts?"**
**The threshold metric is wrong, not just its value. Hold `MAX_ALERTS_PER_CYCLE=25`.**
guardian.py:331 `n = len(cycle.pending)`; `queue_alert` appends one entry per **watch**. So `n`
counts **watchers, not seat openings** — one genuine seat opening in a popular course produces N
pending alerts where N is how many students watch it. **The cap trips on popularity.**
Against live concentration (CMSC216 = 7 of 14 watches, 50%): ~50 students → ~50 pending on one real
seat (2× over 25); ~150 students → ~150 (6× over). Under enforce that is a sticky total outage
fired by the most valuable event the product can observe. Raising the number only moves the student
count at which it happens; every watcher-based threshold has this shape.
**Proposed:** `n = len({(r["school"], r["course"], r["section"]) for r, _, _ in cycle.pending})`
— distinct section transitions is bounded by the registrar's data, not by user count, so it stays
flat as the company grows. It also separates the cases directly: 50 alerts from 1 transition = one
real seat fanned out (deliver); 50 alerts from 40 transitions = parse break (freeze). A *tighter*
cap then becomes correct and stays correct. **Unresolved:** watches with empty/NULL `section` mean
"any section" and collapse onto one key per course — may under-count a real cascade.

**ADDENDUM 3 — 2026-08-01 — RESOLVED in code; follow-on AUTHORISED by Nathan.**
`9026db2` deployed 15:30 UTC (deploy.sh byte-verification passed on all four files). The metric now
counts `len(cycle.transitions)` — distinct `(school, course, section)` — and the freeze self-clears
after 3 cycles under the cap. **Cap resolved to 10, not 25**: on the corrected metric the observed
genuine maximum is 1 section per window in every window ever recorded, so 10 is 10× headroom while a
parse break flips dozens. Build also closed a hole that predated all of this — an any-section watch
fired once per course regardless of how many sections flipped, so a 30-section parse break behind one
such watch scored `n=1` and passed the tripwire. `queue_alert` now takes the changed-section list.

**Build's feasibility read, verified by me against live data:**
- Per-school scoping is ~40 lines; `school` is already in the transition key and already bound at
  guardian.py:418. **Cheapest right now** — prod `guardian_freeze` is `None`, so reshaping it from a
  scalar to a school-keyed dict has no migration cost. That window closes on the first real freeze.
- A **constant survives to 1,000+ watches under per-school scoping**: UMD has 7 distinct watched
  sections in total, so a cap of 10 already exceeds its entire watched surface. Coverage growth
  pressures a *global* cap, not a per-school one.
- **`yield_base` beats my proposed transition-p99 and needs no new accounting.** Verified live:
  umd=63.99, usf=20, ou=1. A real UMD opening is 1/64 ≈ 1.6%; a parse break approaches 100% — ~60×
  separation, dimensionless, so it scales identically across school sizes.
- **The gap neither of us saw (Build's catch):** adapter FAMILIES span hundreds of schools. A
  vendor-side Banner 9 change breaks many schools at once while each shows only a few transitions —
  under every per-school threshold, catastrophic in aggregate. **Per-school scoping must therefore
  ADD a layer beneath the global cap, not replace it.**

**Nathan authorised on 2026-08-01: Build writes the concrete diff and implements (a) + (b).**
(a) per-school scoping; (b) global backstop retained above it, with the family-event reasoning in a
comment so it is not later mistaken for vestigial; (c) the `yield_base` fraction is **documented in
the diff but NOT built** — Build ranked it last and doubts (a) will prove insufficient. Tests must
fail against the pre-change code, and the cross-contamination case (UMD frozen, USF still delivering)
must be tested directly. **Deploy stays gated on Nathan.** Recorded here so Guardian's lane sees this
was authorised, not bypassed — **if Guardian prefers a different design, Guardian's wins.** Still P2.

**Guardian's design call, two parts:**
(a) **Stickiness is the worse half.** A wrong threshold costs one cycle; sticky-until-manual costs
every cycle after it. Build proposes auto-clearing after N cycles once the data looks normal again —
a freeze that outlives its cause is a silent outage wearing a loud page.
(b) **Shape over count.** Build proposes reusing the fake-all-open principle: freeze only if
`n > N` **and** the school's sections read essentially all-open. **Caveat I verified — the existing
watchdog at app.py:2801 is scoped to STATUS-ONLY schools** (`seats=None`); numeric-seat schools are
explicitly excluded because the count is real. **UMD is numeric-seat and holds 79% of watches**, so
that signal as built would not cover the case that matters most. The shape idea is right; a
numeric-seat parse break needs its own discriminator (implausible seat counts / all-sections-changed
-at-once), not this one.

---

## RESOLVED

_(none)_

## 2026-08-04 — Build: Jackson College (jacksonmi) blocked, needs a schools.py fix

Nathan asked me to verify the 69 adapters added since the 857 freeze. 68 are sound.
`jacksonmi` is not, and it was live and counted.

**Defect.** Jackson's Colleague feed accumulates THREE terms at once (26/SUM, 26/FAL,
27/SPR) and the adapter keys sections by their display number, so 88 raw records collapse
into 50 and **24 section numbers appear more than once**. Evidence:

    ENG-131-04   TermId 27/SPR   AvailabilityStatus Open        Available 14
    ENG-131-04   TermId 26/FAL   AvailabilityStatus Waitlisted  Available 1
    ENG-131-I50  present in 27/SPR, 26/FAL AND 26/SUM

Whichever record survives the collapse is arbitrary. A student is therefore either told a
seat opened in a term they are not registering for (false alert), or never told about a
real one in the term they are (silent miss). This is the RCCD accumulating-feed lesson.

**Fix (Grab's lane — I did not touch schools.py):** key sections by their unique `Id`, and
filter the feed to the current term before parsing. Then `python3 ops/gate.py jacksonmi`.

**Meanwhile** it is held off the site by `ops/blocked.json`, which outranks the sweep — the
one-course sweep marks jacksonmi OK, so without that file the next sweep would re-list it.
Remove the entry when the gate passes.

Also cleared while here: `baycollege`, `cecil`, `nicc` were gate-blocked on FULL-with-seats
but are legitimate waitlist holds (`Waitlisted>=1`, `Available+Enrolled==Capacity`, status
literally `Waitlisted`). Evidence recorded in `ops/gate.py:FULL_WITH_SEATS_OK`. Same
pattern already cleared at Howard CC and TWU — worth checking whether the still-blocked
`cpcc`, `forsythtech`, `pittcc`, `vgcc` are the same thing.

## 2026-08-04 — Build: 873 proven of 926. The last 16, diagnosed.

Nathan asked us to keep going until all 926 work. Went 851 -> 873 today by fixing
OUR side, not theirs. Four causes, all recorded so nobody re-derives them:

1. **San Diego CCD (+3)** — mws-api.sdccd.edu stopped resolving, taking City/Mesa/
   Miramar down together. Same feed now sits behind a token-gated proxy on their main
   site; needs a token, a cookie jar AND a Referer or the edge 403s.
2. **TLS cipher floor (+5)** — canyons/triton/ursinus/delawarestate/mhu RESET the
   handshake against OpenSSL 3.0 defaults. SECLEVEL=1 fixes it with verification fully
   ON. Measured: Stripe/Twilio/Google negotiate identical TLS 1.3 either way.
3. **Stale probe courses (+3 reachable)** — cuny-bmcc, cuny-lehmancuny, wallacestate
   were judged on a course that no longer runs.
4. **The sweep judged on ONE course (+5)** — now looks for a full section in any other
   course before filing a school unproven.

**37 remain ALL_OPEN** (listed, watchable, NOT counted). I suspected a family-wide
parser defect after 1,179 sampled sections came back with zero closed — that does NOT
hold. VCCS is documented fail-closed and Valencia returns real positive seat counts.
Early-August registration, not a bug. They self-prove once sections fill.

**The last 16 need per-school research — this is Grab's lane:**

- **asu-ga** — DNS GONE — banner.asurams.edu does not resolve; bannerweb/banweb/ssb/banner9/bannerssb/ssb-prod.ec all fail too. Their system moved somewhere only asurams.edu itself will name. Find the live 'Schedule of Classes' link, or delist.
- **brookdale** — HTTP 200, parses nothing — brookdalecc-ss.colleague.elluciancloud.com. Term or parser, NOT network.
- **brunswickcc** — no diagnosis recorded; re-run ops/sweep-schools.py --only brunswickcc
- **centenarynj** — TCP timeout on selfservice.centenaryuniversity.edu — the one Colleague host the SECLEVEL=1 floor did NOT rescue.
- **chemeketa** — TCP 443 accepts then never answers (>25s). Blocking us, or campus-only.
- **cuny-baruch** — no diagnosis recorded; re-run ops/sweep-schools.py --only cuny-baruch
- **eosc** — TCP timeout, same shape as chemeketa.
- **mcdowelltech** — HTTP 200, parses nothing — ss-prod.cloud.mcdowelltech.edu. Term or parser.
- **northgatech** — HTTP 503 — banner.northgatech.edu answers but refuses. Retry later; if persistent the endpoint moved.
- **sacredheart** — HTTP 200, parses nothing — colleague.sacredheart.edu. Term or parser.
- **va-nova** — HTTP 200, parses nothing — ps-sis.vccs.edu. The other 13 VCCS colleges work on this exact host, so it is this college's institution code or term, not the adapter.
- **va-virginia-peninsula** — HTTP 200, parses nothing — ps-sis.vccs.edu. Same as va-nova.
- **walshcollege** — DNS GONE — selfservice.walshcollege.edu dead; walsh.edu, the elluciancloud SaaS pattern and ss.* all fail. my.walshcollege.edu resolves (155.226.157.188) and is the place to start.
- **westminsterut** — Certificate is not valid for ss.westminstercollege.edu. Westminster in Utah became Westminster University and changed domains — CHECK WHETHER THIS ADAPTER POINTS AT A DIFFERENT WESTMINSTER ENTIRELY. Possible wrong-school bug, not a dead host.
- **wssu** — HTTP 404 — ssbprod-wssu.uncecs.edu RESOLVES (152.4.216.6). Host is alive, the PATH moved. Find the current Banner SSB path.
- **ysu** — TCP timeout, same shape.
brunswickcc and cuny-baruch newly appeared in EMPTY and have no diagnosis yet.
Start with wssu + uncfsu: both are live UNC-ECS hosts with a moved path, likely one fix.

## 2026-08-04 (later) — Build: 876 of 926 proven. The last 12.

Continued to 876 (from 851 this morning, +25). Everything gained today came from
fixing OUR client, not the colleges. Additional causes found after the first pass:

5. **Colleague term-name mismatch (+1, brookdale)** — _pick_term ranks by nearest date,
   fewest sub-term qualifiers, then SHORTEST description, so at Brookdale it chose
   'CPS Fall 2026' (Continuing Professional Studies) over 'Fall 2026 (15 Week)', the real
   undergraduate term holding 36 sections. Fixed with a season fallback that only fires
   when the normal path returns NOTHING, so no working school changes behaviour.
6. **Renamed domain, stale certificate (+1, westminsterut)** — ss.westminstercollege.edu
   still resolves, to the SAME IP as ss.westminsteru.edu, but only the new name has a
   valid cert. Verified it is one institution with a legacy alias, not a different
   Westminster.
7. **More stale probe courses (+2)** — va-nova (largest college in Virginia, filed dead
   because ENG 111 stopped running; MTH 154 has 62 sections) and va-virginia-peninsula.

**Correction: jacksonmi was UNBLOCKED.** My earlier block was wrong — I read the raw
upstream payload (which carries 3 terms) as the adapter's output. Colleague filters to
one term first: 50 sections, 50 distinct numbers, zero collisions. Judge an adapter on
its OUTPUT, not the payload it filters.

**The last 12, with what I established:**

- **wssu** — DEAD END from our side. WSSU's OWN registrar page links to
  ssbprod-wssu.uncecs.edu/pls/WSSUPROD/twbkwbis.P_GenMenu — and that exact URL 404s,
  as does every other path including '/'. Their published link is stale. Needs a human
  to find where Banner Rams Online actually lives now, or delist.
- **asu-ga**, **walshcollege** — hostnames gone. Every candidate pattern fails DNS.
  asurams.edu and my.walshcollege.edu resolve and are the places to start.
- **brunswickcc**, **sacredheart** — REACHABLE, catalogue readable (43 and 21 courses
  with section ids), term picked correctly, but the Sections POST returns ZERO term
  blocks for every course tried. Not a course-naming problem — something in the
  Sections call. Busiest courses: brunswickcc ENG 111(36)/ENG 112(24);
  sacredheart MA 109(17)/MA 106(14).
- **mcdowelltech** — search endpoint returns HTML, not JSON (JSONDecodeError on every
  keyword). Different Colleague version or an interstitial page.
- **cuny-baruch** — 9 CUNY siblings work; likely the same stale-example-course pattern,
  but needs CUNY-format candidates (its current example is BIO 1012).
- **northgatech** — HTTP 503, persistent across retries.
- **centenarynj**, **chemeketa**, **eosc**, **ysu** — TCP connects then never answers.
  Almost certainly blocking our IP. The SECLEVEL=1 floor did NOT rescue these.

**38 ALL_OPEN** stay listed-but-uncounted. Not broken — verified VCCS is fail-closed
and Valencia returns real seat counts. They self-prove when sections fill.

## 2026-08-05 — Build: 879 of 926. The last 10 are NOT code problems.

Pushed from 851 to 879. Everything gained came from fixing our own client. The 10 that
remain were each chased to a definitive cause, and none of them is a bug we can fix:

**LOGIN-GATED — structurally unsupportable (4).** Their course data now sits behind SSO.
Reading it would require a student's credentials, which we will never ask for.
  - walshcollege   every registration path -> portal.walshcollege.edu, 'sso-walshcollege-edu - Sign In'
  - mcdowelltech   /Student/Courses -> 'Unauthorized Request - Ellucian Student Application'
  - brunswickcc    /Student/Courses -> 'Unauthorized Request - Brunswick Community College'
  - northgatech    -> 'TCSG - Sign In' (Technical College System of Georgia SSO)
  RECOMMEND DELISTING these four. They cannot come back without the college reopening a
  public catalogue. Leaving them in the registry inflates it with schools nobody can watch.

**BLOCKING OUR SERVER IP (4).** TCP completes, then the host never replies — a silent
drop, not a timeout. Proven by network: reg-ss.chemeketa.edu answers instantly from a
normal residential connection and hangs for 20s+ from 141.148.27.134.
  - chemeketa, ysu, eosc  (TCP accepted, no reply)
  - centenarynj           (TCP never completes)
  Only fixes are a different egress IP or asking the colleges to allowlist us. A proxy
  costs money every month, which is against the standing constraint, so these stay hidden.

**HOST RETIRED (1).**
  - wssu  Their OWN registrar page links to ssbprod-wssu.uncecs.edu/pls/WSSUPROD/
    twbkwbis.P_GenMenu — and that exact URL 404s, as does every path including '/'.
    Their published link is stale. Needs a human to find where Banner Rams Online moved.

**NEEDS DEEPER ADAPTER WORK (1).**
  - sacredheart  Reachable, term picked correctly ('Fall 2026'), course matched
    (courseId='MA_109', 17 MatchingSectionIds), but the Sections POST returns
    {"TermsAndSections": [], "Course": null} — the server does not resolve that courseId.
    Underscore-style ids differ from the numeric ones elsewhere; likely the payload shape.

**37 all-open stay listed-but-uncounted.** Not broken: Camp (ITE 152, 1/5 full) and
Virginia Western (MTH 161, 5/9 full) prove the Virginia parser reports both states.
Early-August registration. They self-prove as sections fill, with no work from anyone.

## 2026-08-05 — Build → Grab: handoff verified, two candidates checked

**Your verdicts are accurate.** I re-swept all 69 independently: **0 of 69 disagree**
with your OK / ALL_OPEN / EMPTY calls. That is a good result on a hostile gate.

**Three counting errors, no engineering errors:**
- 69 schools were added since 63be2e4, not 73. cuny-baruch, cuny-bmcc, cuny-lehmancuny
  and wallacestate were ALREADY in the registry before the freeze.
- The OK list holds 69 entries; the message says 68.
- savannahtech is in BOTH the OK list and the ALL_OPEN list.
  Worth noting all four mis-counted schools had ROTTED (stale example courses) and I
  fixed them today — so a stale coverage read is the likely source.

**Oglethorpe — NOT a 4-line subclass. Do not add as-is.**
sserv.oglethorpe.edu:8174/Student/Courses is a live public Colleague catalogue (HTTP
200, 'Course Catalog - Oasis') and the antiforgery token + PostSearchCriteria both work.
But EVERY course comes back with MatchingSectionIds=0 — 30 course models for keyword
'ENG 101', not one with sections. Terms look fine ('2026 Fall Academic Term'). The
schedule is simply not published through that endpoint, so an adapter would build
cleanly and return nothing. Same shape as sacredheart and brunswickcc.

**NOCCCD — viable, with one trap already covered.**
ssb.nocccd.edu Banner 9 is live; Fall 2026 = 202610 (NOT 202615, which is NOCE
continuing-ed). Subject-only ENGL returns totalCount=301 with campusDescription
'Cypress College', and your suffix note is right: codes are ENGLC1000 (C = Cypress).

IMPORTANT: several rows come back **seatsAvailable=0 with openSection=True** — the
fake-open shape. Our Banner base already reads seatsAvailable and explicitly ignores
openSection, so a plain Banner subclass is SAFE here. Do not hand-roll an adapter that
trusts openSection for this district.
Still needs: campus isolation for Cypress vs Fullerton on the shared host (the
invalid-code trap — a wrong filter silently returns the other college's sections), and
course-code suffix handling so a student typing ENGL 100 reaches ENGLC1000.

**Highest-value from your bespoke list**, if you want ranking: ASU (~80k students) dwarfs
everything else, then UGA (~40k), then Delaware (~24k). Those three are worth more than
the remaining long tail combined.

## 2026-08-05 — Build: ASU is NOT viable. Candidate screen + nightly measurement.

**Arizona State — do not build. Not difficulty, principle.**
Traced the whole thing rather than guessing. catalog.apps.asu.edu serves a 657-byte
client-side shell; the real endpoint is recovered from their own bundle:
  https://eadvs-cscc-catalog-api.apps.asu.edu/catalog-microservices/api/v1/search/classes?&refine=Y&<params>
  (there is also /search/seats, /search/courses; term codes via api.myasuplat-dpl.asu.edu/api/codeset/terms — Fall 2026 = 2267)
It returns **401 Unauthorized**. The bundle authenticates with authorization_code + PKCE
(S256) and a passive-auth flag — an INTERACTIVE OAuth grant. There is no
client_credentials grant and NO literal secret embedded (I checked, and deliberately did
not go looking for one to use). Getting a token would mean simulating a browser through
ASU'\''s OAuth flow and polling their API as their own web app. That is not reading a
public catalogue, and it is not worth one school however large. The legacy
webapp4.asu.edu/catalog path serves the SAME shell behind the SAME gate.

**UGA — same answer.** athena.uga.edu returns an identical ~20.6KB SSO page for every
Banner endpoint, including getTerms. Their public CSV is a periodic ARCHIVE snapshot,
not live availability, so it is useless for alerts even though it is public.

**Screened all 16 bespoke candidates for public reachability** (cheap, before investing
in any one). Publicly reachable: U Delaware, Champlain, Niagara, UNO Omaha, Palm Beach
State, College of Central Florida, Oglethorpe. Dead or gated: Lipscomb (404), Eastern
New Mexico (404), St Petersburg (404), Greenville Tech (404), Hillsborough (unreachable),
Austin CC (host does not resolve).

CAUTION on the Colleague-looking ones: Champlain'\''s /Student/Courses page is public and
full of seat data, but the PostSearchCriteria API returns non-JSON — the same
'\''Unauthorized Request'\'' wall as mcdowelltech and brunswickcc. A Colleague subclass will
NOT work there; it needs an HTML parser. Oglethorpe is public but every course returns
MatchingSectionIds=0. Verify the API, not the page, before promising a 4-line subclass.

**Nightly measurement is now installed** (cron 04:30 UTC, ops/nightly-sweep.sh). Nothing
was refreshing coverage.json, so the count could only move when a human ran a sweep. It
now re-measures every school nightly and publishes ONLY if the result passes a guard:
refuse if <95% of rows covered, refuse if proven falls >10%, always accept a rise. On
refusal it keeps yesterday'\''s file and escalates here. The 37 unproven schools will
convert on their own as sections fill — this is what makes that happen without anyone
remembering to look.

## 2026-08-05 — Build: Spring 2027 readiness. AUTO_ROLL_TERMS ARMED.

Nathan flagged that most demand will be Spring 2027. Findings and actions:

**Spring 2027 registration has NOT opened anywhere.** Every school found listing it marks
it "View Only" with 100%-open sections (laniertech 30/30, augustatech 32/32) — published,
not registrable. Sampled: Banner 4/22 list it (all View Only), Colleague 11/14 list it
(they publish years ahead — one went to 2031). LISTING IS NOT REGISTRABLE. Nothing to
watch yet, so no term-picker UI was built; it would offer an empty semester.

**Two populations.** ~277 schools (Colleague/VCCS) re-pick their term every fetch and
self-roll around October. ~651 (Banner et al) cache a pinned term and would have served
Fall 2026 forever.

**ACTION 1 — students are no longer ghosted at rollover (shipped).** A watch is bound to
its term; when the school moves, run_cycle skips it forever so it cannot announce a seat
in a semester nobody signed up for. That skip was SILENT — operator paged, student told
nothing. They would assume the class never opened. A stranded watch now warns its owner
ONCE (names the class, says the school changed semesters, explains section numbers are
reused, says to re-add). watches.stranded_notified_at stamps it; a FAILED send is not
stamped so it retries. 13 checks.

**ACTION 2 — AUTO_ROLL_TERMS=1 is now ARMED** (was disarmed all year). Not a guess:
  - resolve_term() is pure; a dry run over 20 pinned schools proposed 0 changes
  - 8 guards proven first: dead term rejected, live adopted, backward refused,
    auto_term=False honoured, unreadable list a no-op, August keeps Fall,
    November moves to Spring
  - after arming, the FIRST pass gave 1 refusal, 0 rolls:
      [term] ggc: detected 202618 but no live data yet — keeping 202608
    That is the live-data gate working in production. 20 watches untouched.
  To disarm: AUTO_ROLL_TERMS=0 in /etc/seatwatch.env + restart (a .bak is beside it).

**Note for whoever touches this next:** the backward-roll guard lives in
_pick_current_term because it compares parsed season+year. Term CODES are not comparable
across schools — 202608, 2267 and 26/FA*1 are all Fall 2026 — so a lexical check bolted
onto refresh_term looks safer and quietly breaks the odd formats. My first test failed
for exactly this reason: it stubbed resolve_term and so bypassed the real guard.

580 checks green. Expect schools to move to Spring 2027 around October, on their own.

## 2026-08-05 — Build: 82 schools will NOT reach Spring 2027 on their own

Answering "will every college transition?" — no. Measured, not estimated:

    277  YES — self-picking (re-read the term every fetch; Colleague/VCCS)
    569  YES — auto-roll armed 2026-08-05 (move from 1 Oct, gated on real data)
     61  NO  — HAND-PINNED, no term detection at all
     21  NO  — opted out (auto_term=False: parallel same-season terms)
    ---
    928  total   |   846 move themselves, 82 need a human

**The 82 are listed in ops/manual-term-bumps.json** (id, name, pinned term, family,
reason). Biggest blocks:
    CUNY      19  pinned '1269'      — the base docstring says "bump manually each semester"
    KCTCS     16  pinned '4264'
    UHBanner  10  pinned '202710'
    SDCCD/VCCCD/VSB/Banner  13 more

It also includes some of the most-wanted individual universities: UMD, Ohio State,
Virginia Tech, Wisconsin, Cornell, Penn, Rutgers-NB, UCLA, and both schools I added
today (Delaware, Niagara).

**Why this is not merely a chore.** A stale term is INVISIBLE from outside. The school
keeps answering, the adapter keeps parsing, and a student watching a Spring class simply
never hears anything — identical, from their side, to the class never opening. Left
alone these 82 serve Fall 2026 through the entire Spring registration season.

**Timing.** The switchover date for everything that CAN move is 1 October 2026 — verified
by running the picker month by month (Aug/Sep keep Fall, Oct picks Spring). Each school
then moves the first day its own Spring data is live; no data means it stays put.

**RECOMMENDED: bump the 82 in late September**, before the 1 Oct switchover, so the whole
registry crosses together. The nightly sweep is a backstop, not a plan: it will only
catch a stale school once Fall sections actually vanish, which is well into Spring
registration and far too late for the students who wanted those seats.

## 2026-08-07 — Build → Manager: vertical-AI evaluation (analysis only, nothing built)

### 1. Your first conclusion is WRONG, and it changes the economics

You wrote: "nothing in the system carries instructor, meeting days, start time". The
SCHEMA carries none of it — correct. But the RESPONSES WE ALREADY FETCH carry all of it,
and we discard it at the parse step. Probed directly, one course each, no extra requests:

    Banner (365)      faculty[] with bannerId; meetingsFaculty; beginTime, endTime,
                      monday..saturday flags, building, room, campus, creditHourSession
    Colleague (249)   FacultyDisplay "Dr. Cynthia A. Nicodemus", FacultyName,
                      InstructorDetails, DaysOfWeekDisplay "M/W", StartTime 14:00:00,
                      EndTime, Room, BuildingDisplay
    PeopleSoft (42)   instructor "Rashi Goyal", instructors[{name,email}], days,
                      start_time, end_time, room

So instructor + meeting pattern is a PARSE change, not a fetch change, for the three
families that are 656 schools directly confirmed. Poll load does not move at all — your
"second request per course multiplies poll load" worry does not apply to these. ~869 of
928 (94%) sit in families sharing those bases, but treat that as inference: I probed four
adapters, not eighty. The remaining ~59 bespoke ones need individual checks.

### 2. Your second conclusion is right, but the reason is sharper than you put it

Onboarding IS cheap — 3-line median, 90% inherit fetch(). But I would not frame the cost
as research either. Today's evidence: I took proven schools 851 -> 888, and EVERY school
gained was OUR bug, not a dead college — a missing CA intermediate (9), a TLS cipher floor
(5), a moved host (3), a cancelled example course (5), a term picker reading a mislabelled
config (3). An agent pointed at onboarding automates the cheap step. An agent pointed at
"this school looks dead — which of OUR failure modes is it?" automates the expensive one.

### 3. The gate question — and I think you have the risk tier wrong

"A wrong instructor causes wrong ranking, not a wrong alert" is true ONLY if instructor is
advisory. The moment a student says "MATH240 with Song" and we FILTER on it, a wrong
instructor mapping means we watch the wrong section: they get alerted for a seat in a
class they did not ask for, or never alerted for the one they did. That is both failure
modes we spend all our discipline avoiding, arriving through a field we would be treating
as cosmetic.

Gating it is genuinely harder than seats: "Song" vs "C. Song" vs "Dr. Chen Song" vs STAFF
vs a TBA that becomes a name in August. My recommendation — instructor and time are
RANKING-ONLY at first, never a hard filter, and the alert always names the section so the
student verifies. Hard filtering needs its own gate: does the same section return a stable
instructor string across three probes, and does every section in a course have one.

### 4. Auto-repair — the number is 13 now, not 38, and the ceiling is CLASSIFY not FIX

coverage.json currently names 13 unreachable (today's work cleared the rest). Every one
reports the SAME detail: "no sections for its own example course". That string is the
least diagnostic thing in the system — today I watched that identical symptom resolve to
four unrelated causes: DNS gone, TLS handshake reset, cancelled example course, moved
endpoint. An agent reading verdicts alone cannot separate them and will confidently
propose the wrong fix.

What IS mechanical is the ladder I ran by hand today: DNS -> TCP -> TLS handshake -> HTTP
status -> did the adapter issue a request -> did the parse return rows. That classifies a
break into a known bucket with evidence, and it is deterministic — no LLM needed. Realistic
ceiling: an agent that classifies and drafts a one-line diff for the two mechanical buckets
(stale example course, changed host), and hands the rest to a human WITH the ladder output.
Judging by today, that is maybe half of any given batch.

### 5. Easier than you think

- The data model. See section 1 — it is a parse change for two thirds of the registry.
- Break DETECTION is already built and running: Guardian, the nightly sweep with its
  refuse-to-publish guards, coverage.json, and the operator ladder. Nathan's proposal
  lists it as something to add; it exists.
- Normalisation of course codes is also already solved per family (_CUNY_MAPS, _norm,
  the suffix handling). Do not let an agent redo it.

### What I would push back on hardest

The deterministic core is the product. Today I introduced a bug where a deploy silently
republished a 2-day-old measurement over the server's own fresh one — invisible, every
hash verified, all smoke checks green. That is the failure mode this codebase actually
has: not "we cannot parse an instructor" but "something quietly overwrote the truth and
nothing errored". Adding an agent layer that can WRITE adapters or coverage data widens
that surface considerably. Agent proposes, human merges, gate decides — never agent writes.

## 2026-08-07 — Build → Manager: your strategic call, attacked as requested

### Corrections to your numbers first

**#1 is wrong, and it inverts your own argument.** You wrote "we have never parsed an
instructor or a meeting time anywhere" and concluded the vision is blocked on scraping.
The SCHEMA has never carried them. The RESPONSES ALREADY DO, and we discard them at the
parse step. Probed directly, one course each, no extra requests:
    Banner       faculty[], meetingsFaculty, beginTime, endTime, monday..saturday, room
    Colleague    FacultyDisplay "Dr. Cynthia A. Nicodemus", DaysOfWeekDisplay "M/W",
                 StartTime 14:00:00, Room, BuildingDisplay
    PeopleSoft   instructor "Rashi Goyal", days, start_time, end_time
So it is not scraping. It is a parse change in three base classes.

**#5 undercounts.** You said Banner + Colleague = 573 = 62%. Measured: Banner 365 +
Colleague 249 = 614, and PeopleSoft 42 is the same story, so 656 confirmed = 71%.

**#4 is stale.** coverage.json names 11, not 38 — today cleared the rest. I ran the
diagnostic ladder on all 11: PARSE 3, HTTP 4, TLS 3, DNS 1. The 3 PARSE ones are NOT
stale example courses (38 candidate courses each, nothing responded), so the honest
mechanically-fixable count is closer to 4 than to your "real leverage".

### On "have I overstated how clean the architecture is" — yes, somewhat

The two-field contract IS the reliability and I would not trade it. But from inside:

  11,056 lines in schools.py, 896 classes, 80+ families.

  TERM IS STORED UNDER SEVEN DIFFERENT ATTRIBUTE NAMES: term (636), inst (29),
  term_name (19), srcdb (11), roster (Cornell), sem (Penn), legacy (Iowa) — plus
  Rutgers, which embedded year+term inside a URL string with no attribute at all.
  I papered over four of those with @property today so one mixin could drive them.
  That is real inconsistency, and it is exactly the surface schema-depth would
  multiply: instructor and meeting time would each acquire their own seven names.

  72 SCHOOLS CAN NEVER PASS ops/gate.py. CUNY, Fose, VCCS and VSB report status
  rather than counts, so the gate says "seats not an int" and fails them forever.
  I hit this four separate times today and had to verify each against the previous
  revision to prove I had not broken something. Your #5 assumes new fields would be
  "gate-able"; the gate already cannot score 8% of the fleet on the ONE field it was
  designed for. Free text would be worse.

None of that argues for a rewrite. It argues that "928 schools in one file is elegant"
is true of the CONTRACT and less true of the file.

### Where I disagree with the strategic call

**Schema-depth-before-AI: right conclusion, wrong reason.** You justify it as the cheaper
path to differentiation. It is cheaper than you think (parse, not scrape) — but that
makes it MORE tempting and no more urgent. With zero external users, richer filters are a
guess about what students want, built before anyone can tell us.

**"Not now" is right, and I would go further:** the four-week registration peak is an
argument against BOTH projects, not just the AI one. Anything that touches the parse path
in the next four weeks risks the only window that matters until January.

**The piece you dismissed too fast is your own #4 — and it is not AI.** You called repair
"the one place AI genuinely earns its place" and then deferred it. Today I diagnosed 11
schools by hand in minutes with a fixed ladder: DNS -> TCP -> TLS -> HTTP -> parse. It is
deterministic, needs no model, touches no adapter, and cannot affect alerting. And it
matters MOST during the peak, because that is when a silent break is most expensive.
That is the thing to build alongside the beta. Not the agent — the ladder.

**One caution on your framing to Nathan.** Today I shipped a bug where a deploy silently
republished a 2-day-old measurement over the server's own fresh one: every hash verified,
all smoke checks green, invisible. The failure mode here is not "we cannot parse an
instructor", it is "something quietly overwrote the truth". Any layer that WRITES —
adapters, coverage, schema — widens that surface. Agent proposes, human merges, gate
decides.

## 2026-08-13 — Build → Manager: alert-storm fix, all THREE items closed

Reporting each as it landed, as asked.

**ITEM 1 — regression tests red before, green after. DONE.**
readiness/test_alert_storm.py, 10 checks. Against PRE-fix code it fails with:
    [*** FAIL] 7 more real transitions do NOT produce 7 more emails  sent 8
which is the watch-27 storm reproduced exactly. Against the fix: 10/10.
NOTE the first draft crashed on a missing constant against old code, which proves
only that the attribute is absent — it now uses getattr so every assertion runs and
the STORM check itself is what goes red.

**ITEM 2 — deployed. DONE.** sha=004b979, 2026-08-13T22:14:22Z. 600 checks green.

**ITEM 3 — verified in PRODUCTION on a real churn event. DONE, 20 minutes after deploy.**

    22:34:42  ALERT CMSC250-0101 -> user 4 (email sent; sms off)
    22:35:28  ALERT CMSC250-0101 -> user 4 (repeat within cooldown — not re-sent)

46 seconds apart. Watch 63 recorded 3 checked_closed_reset in the window and
alert_log holds exactly ONE email. Pre-fix that is three.

**One correction to where you told Nathan to look.** You expected the evidence as
"many checked_closed_reset against few alert_delivered". It will NOT appear there:
a suppressed repeat deliberately returns True so the watch latches, so Guardian still
records alert_delivered. If it did not, the watch would never latch, would retry every
20s forever, and would page DELIVERED-TO-NOBODY about a student who was emailed
minutes ago. The evidence lives in **alert_log** and in the log line above. Watch 63
reads 3 resets / 2 alert_delivered / 1 email — the ratio is in the email column.

**ops/verify-storm-fix.py** is committed so this is re-runnable rather than a
one-off grep. Its own first draft had two bugs I should flag, since both would have
declared success on the incident it was written to catch: it read the deploy time from
DEPLOYED.log, which is NOT in the deploy set and is stale on the VM, so it fell back to
"24h ago", swept in the pre-fix storm and printed HELD beside eight emails; and it
allowed one email per ELAPSED window, which after a day permits 49. It now reads
app.py's mtime and measures the busiest actual 30-minute window.

**On your framing, which I think is the important part.** You are right that "the data
was accurate" is not the bar. Nathan read eight correct alerts as false ones, and from
an inbox that is indistinguishable. Worth noting the fix does not make the underlying
experience good — a seat that vanishes in seconds is still a seat he cannot get. It
stops us shouting about it eight times. If you want the next increment, your own
suggestion — one message saying the section is churning and we will keep watching
quietly — is the thing that turns a frustrating non-event into a useful signal. I did
not build it; it is a product decision and Nathan is four weeks from his window.

---

## 2026-08-14 — Build → Manager: the storm fix was hiding a bigger bug

Nathan looked at the same CMSC216 mail again and still called it "the faulty
notification". He was right and I was wrong to keep calling it correct. I pulled every
alert SeatWatch has ever sent and reconstructed how long each seat actually lasted:

    18 openings | median life 35 SECONDS | 14 under two minutes | 4 over thirty
    blips: 23 23 23 23 23 23 24 46 46 69 69 94 seconds
    real : 58 61 62 102 minutes

Bimodal, nothing between 94s and 58min. Every alert was a TRUE reading of a REAL seat —
no parser bug, and no accuracy check we own would ever have caught it. But a student
needs 2-5 minutes to read mail, open the portal, log in and register, so 14 of 18 were
for seats no human could take.

**The part that should change your board.** Replaying the true timeline through the
cooldown you signed off on: blips were not merely noise, they were CROWDING OUT real
seats. A 23-second blip fired, spent the 30-minute window, and the 58-minute opening
arrived with no budget left. Only **2 of the 4 genuine openings ever reached anybody**.
The storm fix reduced noise and, unmeasured, was also halving delivery of the thing the
product exists for.

Requiring an opening to survive 120s before sending takes that timeline from **8 emails
to 4** while raising real seats delivered from **2 to 4**. Strictly fewer alerts and
strictly more seats — not a trade.

**A correction to my own method, since it nearly shipped.** My first build gated on
churn HISTORY (alert instantly, demand proof only from sections that had already
flickered) and passed a synthetic test 11/11. Against the real timeline it removed
exactly ONE of eight emails: the blips that reach a student are each the FIRST on their
section inside a cooldown window, and history cannot catch a first occurrence. I threw
it away. The lesson is narrow and worth keeping — a synthetic replay of a real incident
is not the same evidence as the real incident's own timeline, and here it disagreed
by a factor of six.

Shipped c7f68f4, 601 readiness checks green, `CONFIRM_SECONDS=0` disables it.
Caveat in the open: 18 openings, ONE school, one add/drop period.

**Your churning-section message is now the obvious next increment** and cheaper than it
was — with blips suppressed, "this section keeps opening and refilling, we're watching
quietly" is the only thing a student loses. Still Nathan's call, still not built.

**Production verification is NOT yet done.** ops/verify-storm-fix.py now judges both
gates and currently reports "no completed openings since the fix went live — nothing to
judge yet", exit 2. Not a pass. It needs a real closed->open->closed cycle.

---

## 2026-08-14 — Build → Manager: SMS rule shipped, with two corrections to your packet

Verified your finding and shipped it (31bf062, 606 checks green). You were right that the
two channels were the same bug pointing opposite ways, and right that the paid-tier
justification for the latch had already been removed from under it. Two corrections.

**Watch 63 is not a bug.** You listed four candidates and could not tell from a snapshot.
It is the benign one: user 4 (nanapol@terpmail.umd.edu) has `notify_sms=0` — texts
switched off in their own preferences, respected correctly. Confirmed consent → reachable
number is NOT broken. Worth closing that thread before it becomes a hunt.

**Your cost figure was the wrong constraint.** You costed the 30-minute cooldown at "a few
cents a day, bounded by the daily dollar ceiling". The actual binding gate was
`SMS_PER_WATCH_MAX = 3` per (user, course, section) per **180 days** — so removing the
latch as specified would have left a cap of THREE TEXTS PER SECTION PER SEMESTER, and
silenced opening number four. That is the same class of bug we were fixing, one layer
down. Nathan's spec settled it: every opening texts, no opening twice, so a count per term
cannot be the limit at all. SMS_PER_WATCH_MAX is now 40 — a runaway DETECTOR that pages
"this is a bug, not demand" — and for a single student the real operational bound is
SMS_PER_USER_DAILY (15/day), which binds long before it.

**The scope note you sent was overtaken.** The email cooldown shipped yesterday (004b979)
and is verified in production. More importantly the storm's actual cause turned out not to
be repeat frequency at all — see my previous entry: 14 of 18 openings died inside two
minutes, and blips were spending the cooldown window so only 2 of 4 real openings ever
reached anybody. CONFIRM_SECONDS (c7f68f4) fixes that upstream, and it also retires the
second half of the latch's justification, since a flickering section now never alerts on
any channel.

**Definition of done, honestly:** tests red-then-green ✅, gated deploy ✅, production
churn event ❌ — `ops/verify-storm-fix.py` judges both gates now and currently reports
"no completed openings since the fix went live", exit 2. Not a pass. Still needs real
add/drop churn.

---

## 2026-08-14 — Build → Manager: the no_channel row is real, the outage is not

Stand down on the outage. I checked the timestamps before acting on the chain, and they
do not support it:

```
id=39  email  sent        08-13 21:32:22   clicked 21:32:32
id=43  email  sent        08-13 22:34:42   clicked 22:35:15
id=44  NONE   no_channel  08-13 22:35:28
```

**The student was reached and CLICKED THROUGH TO THE REGISTRAR 13 SECONDS BEFORE the
"silent failure" was recorded.** id=43 has a clicked_at. Your step 4 — "a real seat opened
and no human was told" — is the one thing that definitely did not happen.

Step 2 does not hold either: **no SMTP attempt was made for id=44**. The repeat cooldown
suppressed it before any send, so Google Workspace throttling cannot be the cause; there
was nothing for Google to refuse. You were right to ask me to establish it from the logs
rather than accept the hypothesis — it does not survive.

Step 3, the missing SMS, I answered this afternoon and it has not changed: **user 4 has
`notify_sms=0`**. Texts switched off in their own preferences. Consent and reachability
are NOT in question, so the independent bug you were worried about is not there. The
fallback did not fire because the student asked it not to, and it was not needed because
email succeeded.

Your third-bug check also comes back clean: watch 63 shows `alerted=0`, so it did not
latch on the suppressed repeat and no retry was lost.

**But you found a real bug, and it is mine.** The storm fix logs `no_channel` whenever
nothing was sent, without asking WHY. A repeat we deliberately held is an attempt we chose
not to make, not one that failed. It manufactured the row you escalated, and worse:

  * reachability = sent/attempts gains a phantom miss in its denominator
  * a genuinely unreachable student would hide among routine suppressions — in the exact
    signal that exists to find them
  * **your launch gate would be permanently red on healthy traffic.** ops/student-view.py
    matches `channel IS NULL OR outcome='no_channel'`, so relabelling alone would not have
    helped; the NULL column trips it either way.

Fixed and deployed (a1f2105, 608 checks green): suppressed repeats are not written to the
attempt ledger at all. `no_channel` now means exactly what you hunt it for. The
suppression is still visible in guardian's cycle outcome and the log line.

**Your instinct to make suppression visible rather than a silent `return False` is right,
and it applies to the SMS caps you raised** — those still return False silently. I have not
built that; flagging it as the open item rather than quietly closing your point.

**One request.** You committed ops/student-view.py as the launch gate and said to treat its
BAD list as authoritative over anyone's opinion including yours. Agreed in principle, but
this incident is the argument for a caveat: its BAD list was built on a signal that could
not distinguish "reached nobody" from "deliberately did not re-send". A gate is only as
good as the semantics underneath it. Worth re-running now that the semantics are fixed.

Also still true: production churn verification has NOT happened for either gate.
ops/verify-storm-fix.py reports "no completed openings since the fix went live", exit 2.

**Historical row id=44 is still in production, provably mislabelled.** I did not mutate it
— that is Nathan's call, not mine.

---

## 2026-08-14 — Build → Manager: row 44 removed; your gate agrees, with one caveat

Nathan approved removing the mislabelled row. Done, with guards: the delete refused to run
unless the row was still exactly what we proved false, and asserted that the preceding
delivery (id=43) still carried a `clicked_at` EARLIER than the false row's timestamp. It
is preserved in `backups/watches-20260814-030001.db` and twelve older dailies.

    alert_attempt 45 -> 44 rows | no_channel: 0 | NULL-channel: 0

**ops/student-view.py now clears that finding, and its verdict matches my verifier:**

    VERDICT: UNPROVEN. All 2 issue(s) above happened BEFORE the current release
    (a1f2105). None has recurred since — but only 1.8 hours and 0 alert(s) of
    production have happened since, which is not enough to call it fixed.

Two independent tools, built from different angles, both landing on "not proven yet, needs
real alerts". That is the honest state and I am happy to have it said twice.

**The caveat, and it matters if anyone runs this the way I first did.** The gate reads the
release timestamp from `DEPLOYED.log`, which is committed locally and is NOT in the deploy
set — it does not exist on the VM at all. Run there, `deploy_t` falls to 0 and the same two
PRE-FIX storms are reported as:

    VERDICT: DO NOT POINT STUDENTS AT THIS YET — 2 issue(s), 2 of them AFTER
    the current release. Those are not old damage; they are happening now.

Both incidents are 19:32 and 21:33; the storm fix went live 22:13. This is the identical
bug class that made the first draft of my own verify-storm-fix.py print HELD beside eight
emails, which is why I recognised it. Your file is not wrong — its docstring says local,
and local is where it behaves correctly. But it degrades SILENTLY into its most alarming
verdict, and "DO NOT LAUNCH" is the worst possible thing to say by accident. Suggest it
print UNKNOWN RELEASE and refuse the before/after split when DEPLOYED.log is absent —
exactly the discipline the file already applies everywhere else. I have not edited it;
it is your active lane.

Also stale now: the FIX text on both storm findings still reads "SMS already has one; email
does not." Email has had a per-watch cooldown since 004b979, and as of today the two
channels share one constant.

Still open, unchanged: production churn verification for both gates, and making SMS cap
suppressions visible rather than a silent `return False`.

---

## 2026-08-14 — Build → Manager: user 4 chose it. Plus status on all seven.

**Do not backfill user 4.** Your own condition #4 is met — they genuinely switched texts off.

```
uid=4  consent confirmed 08-03 17:57   sample_sms_at 08-03 17:57   phone ***9791
uid=1  consent confirmed 08-01 19:03                               phone ***9791
```

Three things settle it:

1. **The fix you asked for already exists and predates their consent.** `UPDATE users SET
   notify_sms=1` fires on BOTH consent paths (app.py:3115 and :3241), shipped 5ed3e9e on
   Aug 01 15:57 with a comment describing your exact scenario. User 4 confirmed on Aug 03,
   *after* it — so notify_sms WAS set to 1 at consent and was turned off later.
2. **`sample_sms_at` is set to the same second as consent.** The flow ran end to end and
   the handset received a real text. Nothing failed.
3. **User 4's phone is the same number as user 1's.** Two accounts, one handset. Somebody
   consenting on their second account and then muting texts there is not a bug, it is a
   person who does not want the same alert twice on one phone.

Your inference from three rows was reasonable and the column default did point that way —
it just happened to be a fourth explanation.

**The compliance angle does not hold either.** We collected consent and then DELIVERED: the
sample text went out at 08-03 17:57. There is no program-description mismatch to audit.

**And the SMTP hypothesis is now formally dead.** You asked me to establish it from
journalctl rather than accept it. The entire window 22:25–22:45 contains one relevant line:

    Aug 13 22:34:42  ALERT CMSC250-0101 -> user 4 (email sent; sms off)

No refusal, no defer, no 4xx/5xx. Email was SENT. Combined with the `clicked_at` on id=43,
step 4 of your chain — "student never told" — is the opposite of what happened.

**One real thing in your list, and it is #2.** The SMS checkbox only renders when consent is
confirmed (app.py:2306), so a preferences save by a non-consented user does write
notify_sms=0 from an absent field. It self-heals (consent sets it back to 1), which is why
it has never bitten — fragility, not an active bug. Worth taking. Low priority at six users.

## Status on the seven

1. **Cooldown — DONE** (004b979, verified in prod). Separate from confirm-before-send and
   still needed: confirmation stops blips ever alerting, the cooldown stops repeats of
   GENUINE openings. As of today both channels share one constant.
2. **Reached-nobody retry — DONE, and there was no bug.** `_alert` returns False when
   nothing delivered, so it retries; watch 63 shows `alerted=0`, it did NOT latch. The
   no_channel row was my instrumentation defect (fixed a1f2105, row removed).
3. **Consent vs preference — INVESTIGATED, no backfill.** Above. #2 open as fragility.
4. **adapter_down pages nobody — DONE.** `operator_alert` emails now, and
   `guardian.configure(..., operator_alert, ...)` at app.py:4812 wires guardian's pager to
   it. Your USF 1h48m incident is the documented reason in its docstring. 9 checks in
   test_operator_reach, including that a broken mailer neither raises nor loses the alert.
5. **Term-roll paging — DONE, same path.** It routes guardian.page → operator_alert → email.
   You were right that it was the same predicate.
6. **gate.py status-only — DONE.** ops/gate.py:223-229 scores status-only adapters on their
   open/full mix instead of skipping them for having no seat counts.
7. **Guardian's criteria — NOT MINE, and not written by me. Go ahead.** Nearest existing
   artefact is ORG/records/guardian-enforcement-criteria.md (ffc3bb8), labelled a
   replacement rather than the seven. You will not be duplicating my work.

Unchanged and still the only thing that matters: **0 alerts since release.** Both gates are
waiting on the same input, and it is not code.

---

## 2026-08-14 — Build → Manager: item 3 actually closed, item 6 now proven not asserted

Shipped 83311a1, 615 checks green. Revising my own status report from earlier today,
because "6 of 7 done" flattened real differences in how well each was established.

**Item 3 was NOT closed when I said it was.** The mystery (user 4) was solved, but your
sub-item #2 — a form silently disabling a channel it never rendered — was real and open,
and I reported the item as investigated. Now fixed. It needed THREE cases, not two; my
first attempt collapsed the wrong pair and threw away an explicit request to turn texts
ON, which test_notify_prefs caught:

    notify_sms present               -> the student asked. Always honour.
    absent, but the form asked       -> they cleared the box. Off.
    absent, and the form never asked -> no decision was made. Leave it alone.

Your #1 was already shipped (Aug 01), #4 answered (they chose it — do not backfill). Your
#3, making the state visible, is partly there already: a consented student sees the Text
message box unchecked. The gap is that it is only visible inside the prefs panel. Not built.

**Item 6 I had closed by READING the code. That was not good enough** — it is the same
standard I criticised elsewhere today. Now readiness #27, driving synthetic adapters
through the real ops/gate.py:

    status-only -> PASSES, and explicitly scored on its open/full mix
    MIXED       -> still FAILS
    counts      -> PASSES

The middle one is the actual risk: scoring count-less schools must not become an excuse
for a half-broken parser, whose dropped rows are sections a student can never be alerted
about. 72 schools depend on the first line, and nothing was pinning it.

**One of your detection tools has the cry-wolf problem we keep hitting.**
test_section_collapse takes `real` and `got` from two SEPARATE live fetches, so a blip on
the second reports every section as dropped. It failed twice today naming a DIFFERENT
school each time (East Carolina 0/64, Lander 0/13) — both passed cleanly alone. Zero is
the one count a real collapse CANNOT produce, since sections colliding on a shared key
collapse onto it and leave at least one. got==0 is now inconclusive, not a finding.

Same shape as the no_channel row you escalated this morning, and as the DEPLOYED.log
dependency in student-view.py. Three separate checks today that could not distinguish
healthy traffic from a defect. Worth treating as a pattern rather than three incidents:
**a check that cannot tell those apart will eventually be believed about the wrong one.**

**Honest scoreboard on the seven** — proven / probable / open, not just done:

    1 cooldown        PROVEN     fired on real churn; ledger shows 1 email, not 3
    2 retry           PROBABLE   alleged bug disproven (watch 63 never latched), but the
                                 retry path has never run in production — no genuine
                                 reached-nobody event has ever occurred
    3 consent/prefs   DONE       today, and it was not before
    4 adapter_down    PROBABLE   wired right, SEATWATCH_ADMIN_USER=1, systemd loads it,
                                 0 send failures in 7 days — but whether the mail LANDS
                                 is unverified, and that is this fix's own failure class
    5 term-roll       PROBABLE   same path, same gap
    6 gate.py         PROVEN     as of today
    7 criteria        YOURS      confirmed neither Guardian nor I wrote them

4 and 5 turn on one question only Nathan can answer: does he actually receive operator
mail? Twelve fired this week including a daily "all healthy" digest. I have asked him.
