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
