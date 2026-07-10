# Note to Codex Sol 5.6 — SeatWatch college-discovery partner

From: the Fable 5 research session. We've been paired by Nathan to hunt new schools for SeatWatch
(course-seat-alert app, live at seatwatchapp.com, ~639 schools live as of July 10 2026, goal 1,000).
Welcome aboard. This note is how we work together without colliding. Read `research/README.md`
end-to-end first — it's the full history of what's been tried, shipped, and killed. This file is the
coordination layer on top of it.

## The two hard rules that override everything

1. **We are RESEARCH ONLY. Neither of us edits `schools.py`, commits code, or "builds into" anything.**
   There is a separate session, **SeatWatch-Builder**, that owns all code. Our job: find + verify
   candidate schools, then hand a spec to the builder — but ONLY after Nathan explicitly says go-ahead
   for that batch. Never message the builder on your own initiative. Report to Nathan, wait, then send.

2. **Accuracy and efficiency must be FLAWLESS — this is Nathan's reputation.** A single false
   "seat open!" alert on a full class is worse than never finding the school. When in doubt, cut it.
   Details in the gate below. Same for efficiency: a slow host stalls the poller for everyone.

## Sync discipline (READ THIS FIRST)

- **PULL before you probe, PUSH after every finding.** We may be working in the same folder or in two
  separate copies — neither of us can tell which. This one habit makes it not matter: `git pull` (or
  just re-read the lane files) before starting a vein, `git commit && git push` right after any
  meaningful write. Never sit on uncommitted changes — a second agent in the same folder can clobber them.
- **Live "who's on what" lives in per-agent files, NOT in README:** I write only `research/lane-fable.md`,
  you write only `research/lane-codex.md`. Each of us READS both but EDITS only our own. This makes
  merge conflicts on the coordination layer structurally impossible (we never touch the same file).
  Claim your vein in `lane-codex.md` before probing.
- **Quick sync test (do this once at the start):** run `pwd` and `git log --oneline -3`. If you see
  Fable's recent commits (the newest is the one that added these lane files) you're on the same repo
  and in sync. Fill in your latest commit hash in `lane-codex.md` so I can confirm I see you too.

## How we avoid bumping into each other

- **`research/README.md` is the append-only FINDINGS ARCHIVE** — verified/shipped/killed specs. Only
  ever ADD a new dated entry; never rewrite existing ones. It's shared memory, not the live channel.
- **Dedup + lane-claim rules below still apply.** Whoever claims a vein (in their lane file) owns it
  until they release it.
- **DEDUP BY SCHOOL NAME, not host.** Before claiming ANY school is "new," run
  `grep -i "<school name>" schools.py` AND check for the school under a bespoke adapter on a different
  host. We have already shipped 4 duplicate handoffs this way (UNC Charlotte ×2, Ashland, Penn — Penn
  is live via a custom `Penn` class, not on its fose host). Grep the name every single time.
- **Proposed lane split (so we're never in the same file at once):**
  - **Me (Fable):** CSU public-schedule campuses (in progress — see below) + PeopleSoft **Fluid/HighPoint
    HCX** guest-API vein (Coppin/Towson/BU family).
  - **You (Codex):** please take one of these fresh veins so we don't overlap — pick whichever suits you
    and claim it in README: (a) **Colleague Ellucian-cloud grind** over the remaining IPEDS 4-years
    (`{label}-ss.colleague.elluciancloud.com` — highest-yield private-4-year pattern, big pool left);
    (b) **Banner Ellucian-cloud** (`reg-prod.{code}.elluciancloud.com/StudentRegistrationSsb`);
    or (c) **CT-log / certspotter discovery** to surface hidden registration hosts that hostname-guessing
    can't (the one proven way to find non-pattern hosts; needs sequential requests, ~1 per 5–10s).
  - If you'd rather trade lanes, say so in README and I'll take the other. The point is one owner per vein.
- **HELD, do not grab (mine, pending Nathan's go-ahead):** Sacramento State (bespoke JSON API) and
  CSU Northridge (custom PS bolt-on) — both gated clean, waiting on Nathan to approve sending. Cal Poly
  Pomona is mine too (ASP.NET, crackable, deferred until a browser can reach schedule.cpp.edu).

## The accuracy gate — every candidate must pass ALL of these before handoff

- **Real live status, proven by a MIXED result set.** A school only counts if a search returns a
  genuine mix of open/closed/waitlisted sections with real seat integers. **All-one-status = fake or
  broken guest data → REJECT.** This killed the entire classic-PeopleSoft `COMMUNITY_ACCESS.CLASS_SEARCH.GBL`
  segment: its guest view shows EVERY section "Open" regardless of real enrollment.
- **The completed-term test (mandatory for any status-only source).** Search a big intro course (ENGL/
  MATH 101-level) in a *finished* term. If every section shows "Open," the status field is fake → SKIP.
  Only a source that shows real *closed* sections in a done term is buildable. (Confirmed the CSUN
  bolt-on this way; it's why CSUN is shippable and Fullerton's classic search is not.)
- **False-freshness check.** A host can advertise a live term yet serve ARCHIVE sections underneath.
  Confirm the probed term is real live data (timestamps, or a delta over active registration).
  Permanent-cut examples: Lafayette, TESU, Bryant&Stratton, Victor Valley (all in README — never re-send).
- **Verify the EXAMPLE course actually returns sections using the school's OWN subject-code format.**
  Don't assume "ENGL" — Oregon State's English is "ENG", San Francisco State needs "MATH 226" exact,
  Wisconsin uses "COMP SCI". A wrong example nearly scrapped valid schools. Pick a large guaranteed
  course and confirm it returns 2+ live sections in the target term.
- **Section-key uniqueness / no collapse.** Confirm each section has a distinct key (CRN / class_number /
  class_section). Watch for the zero-sequence trap (Banner installs returning sequenceNumber="0" on every
  row collapse all sections into one) and multi-meeting duplicate rows (dedupe by class_number).
- **No sibling leak.** For any custom HTML/search adapter, verify an exact course-code search doesn't
  also return suffixed siblings (searching "MATH 2A" must not return "2AX"). Test before handoff.
- **No section-hiding filters in the spec.** Strip any time-of-day / day-of-week / open-only / campus
  filter from a captured browser flow and request ALL statuses — a filter can silently hide a watched
  section (a silent miss, the quiet cousin of a false-open). Learned the hard way on UCLA.

## The efficiency gate

- **Latency screen.** Full fetch should be well under a few seconds; auto-cut cold-start hosts (a Drake
  host took 137s — it would stall a poller worker every cycle). Multi-poll if you can (a one-shot pass
  hides intermittency).
- **Pagination.** Confirm you're reading ALL sections, not a silently capped first page (Banner capped at
  100 rows/course once — sections past 100 could never alert).

## Known-good discovery patterns (reuse these)
- Banner 9 SSB: `/StudentRegistrationSsb`, JSON, reads `seatsAvailable` (NOT `openSection`).
- Colleague: `/Student/Courses` public JSON.
- PeopleSoft **Fluid** guest API (real `enrl_stat` O/W/C + `enrollment_available`): the HighPoint HCX
  `WEBLIB_HCX_CM.H_CLASS_SEARCH...IScript_ClassSearch` endpoints (Coppin/Towson/BU). Hosts idiosyncratic —
  search-harvest, can't brute-force.
- Fose: `classes.{domain}/api/?page=fose&route=search` with srcdb auto-discovered from the homepage.
- Bespoke public schedules (the alt public search a gated flagship often still exposes): UConn→Fose,
  UC Irvine→WebSoc, UCSC→pisa, SFSU→a JSON classservices API, Sac State→a React JSON API. Always look for
  the alt public search, not just the primary SIS.

## Dead ends already exhausted (do NOT re-tread — full reasons in README)
Classic PeopleSoft `COMMUNITY_ACCESS.CLASS_SEARCH.GBL` (fake all-open status); Workday Student (auth);
Coursedog/CourseLeaf public views (catalog only, no live seats); most big-flagship primary SIS
(login/SSO-gated); CSU standard guest search on most campuses (Shibboleth/PS login — Fullerton/Fresno/
SDSU confirmed walled). Blind Banner/Colleague hostname-guessing is ~mined out — count only confirmed
non-duplicate installs, never project yield from a raw "host reachable" rate.

## Handoff format (when Nathan approves a batch)
Per school: name + rough enrollment + 4-year/CC · host/site/inst/term codes · example course in the
school's own subject format · which adapter it fits (or "needs bespoke") · your gate evidence (the
mixed-status counts, completed-term result, latency) · explicit dedup confirmation. Write it into
README under a dated batch heading so the builder and I both see it.

Looking forward to working with you. Keep it flawless. — Fable 5
