# Note to Codex Sol 5.6 — SeatWatch college-discovery partner

From: the Fable 5 research session. We've been paired by Nathan to hunt new schools for SeatWatch
(course-seat-alert app, live at seatwatchapp.com, 641 schools live as of July 10 2026, goal 1,000).
Welcome aboard (or welcome back — if you've seen an earlier version of this note, re-read it, a lot
happened since: CSU is now fully worked, ASU/U Arizona are dead ends, and a full US-domain volume
sweep just ran). Read `research/README.md` end-to-end first — it's the full history of what's been
tried, shipped, and killed, newest entries at the bottom. This file is the coordination layer on top of it.

> **ALSO READ `CONTRIBUTING_AGENT.md` in the repo root** — the builder's full accuracy-gate + traps
> brief. It's the standard we BOTH hand off to. This note is the coordination layer; that file is the
> shared quality bar. Note: dedup-by-name is now ENFORCED IN CODE (the registry guard crashes the
> import on a duplicate id/name), so a dup from either of us gets caught at test time — but still grep
> the name before handoff so we don't waste a batch round-trip.

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
- **⚠️ DO NOT re-run a blind Banner/Colleague hostname sweep — it's been done, exhaustively, already.**
  I pulled the full Hipo world-universities dataset (2,393 US domains), deduped against every school
  already in `schools.py`, and swept all 2,014 uncovered domains against every known Banner pattern
  (`/StudentRegistrationSsb`, direct + `reg-prod.{code}.elluciancloud.com` cloud) AND every known
  Colleague pattern (`/Student/Courses`, direct + `{label}-ss.colleague.elluciancloud.com` cloud).
  Result: 11 Banner hits, all dup/already-cut; 53 Colleague hits, all but 2 dup/dead/gated. Re-running
  this exact method will re-find the same schools and burn your budget for zero yield. See README
  "Volume sweep over full US university-domains dataset" for the full method + result before you
  consider any variant of hostname-pattern guessing.
- **What IS fresh and unclaimed — pick one and claim it in `lane-codex.md`:**
  1. **Newer-Colleague-API-version investigation (concrete, scoped, recommended first task).** The
     volume sweep found 11 real Colleague-hosted colleges (augustana.edu, bridgeport.edu,
     brookdalecc.edu, camdencc.edu, gac.edu, gustavus.edu, lvc.edu, mcdaniel.edu, sunyocc.edu, twu.edu,
     walshcollege.edu) that serve a public course catalog page but return HTTP 405/400 (not JSON) when
     our adapter POSTs to `/Student/Courses/PostSearchCriteria`. That means they're running either a
     newer Colleague Self-Service API version with a different search contract, or they gate the guest
     search differently. Your job: pick 2-3 of these, inspect what their actual class-search page does
     in a browser (view the network requests it fires), figure out the real endpoint/payload shape, and
     determine if it's guest-accessible with real open/closed status. If yes for even one, that's a
     whole new adapter variant that could unlock all 11 (and probably more we haven't found yet, since
     we only checked hosts that were ALSO reachable at the old endpoint pattern).
  2. **CT-log / certspotter discovery** — surfaces hidden registration hosts that hostname-guessing
     structurally can't find (a school's real host may not match any pattern we've tried). The one
     proven way to find non-pattern hosts (confirmed once before: Eastern Kentucky's real host was only
     found this way). Needs sequential requests (~1 every 5-10s, certspotter free tier rate-limits hard).
  3. **Alt public class-search hunt at big gated flagships**, one school at a time (not pattern sweeps —
     these are individually gated behind SSO on their primary SIS, so each needs its own registrar-page
     recon to find a SEPARATE public schedule, the way UConn→Fose and UC Irvine→WebSoc worked). I tried
     Arizona State (OAuth-gated, dead) and University of Arizona (public data exists but sits behind a
     blocked-for-us SPA transport AND the classic-PS fake-status component — dead, see README). Untried:
     UCF, University of Houston, Purdue, Texas A&M, Michigan State, Iowa State, Clemson, University of
     Florida, Ohio State, Penn State. If you take this, claim it in your lane file so I don't also drift
     back into it — I'm not currently working it, but flagging the risk since I did related work here.
  - If none of these suit you, or you find a better lead, write your own choice into `lane-codex.md` —
    the only hard rule is claim-before-probe so we don't duplicate effort.
- **Nothing is currently HELD by me** — Sacramento State + CSU Northridge shipped (batch 15), Cal Poly
  Pomona is a PERMANENT SKIP (cracked the ASP.NET flow, but the public page only exposes Capacity, no
  seats/status — data isn't there at any access level, so don't re-attempt it either), Edison State CC
  (Ohio) + Georgia Military College are sent to the builder as batch 16 (from the volume sweep, awaiting
  ship). Full detail on all of these in README. My current status/next move is always in `lane-fable.md`.

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
Classic PeopleSoft `COMMUNITY_ACCESS.CLASS_SEARCH.GBL` (fake all-open status) — including when it's
hidden behind a modern SPA wrapper (e.g. GreyHeller/InFlight): check the config for a
`SA_LEARNER_SERVICES.CLASS_SEARCH.GBL` / `SSR_CLSRCH` component key, and if you find one, expect the
same fake-status trap regardless of how modern the frontend looks (confirmed on University of
Arizona). Workday Student (auth). Coursedog/CourseLeaf public views (catalog only, no live seats).
Most big-flagship primary SIS (login/SSO-gated) — confirmed again on Arizona State (full OAuth
authorization-code flow, authorize step bounces to interactive login). CSU standard guest search on
most campuses (Shibboleth/PS login — Fullerton/Fresno/SDSU confirmed walled); the 3 CSUs that DO work
(SFSU, Sacramento State, CSU Northridge) each needed a different bespoke crack, so CSU is not a
pattern you can sweep, it's one-school-at-a-time. Cal Poly Pomona: mechanically crackable (ASP.NET
viewstate, solved) but PERMANENT SKIP anyway — its public schedule only publishes Capacity, no
seats/status at all, so there's nothing to gate no matter how good the scrape is; if you ever hit a
school like this (real access, but the field just isn't published), that's a data-absence, not a
you-problem — stop and move on. Blind Banner/Colleague hostname-guessing (direct AND Ellucian-cloud,
both fully swept against the entire uncovered US-domain dataset as of July 10) is MINED OUT — count
only confirmed non-duplicate installs, never project yield from a raw "host reachable" rate.

## Findings workflow — write to README, that IS the handoff (do this for EVERY gate-passed school)

The builder session reads `research/README.md` as its source of truth. So the standard is: **as soon
as a candidate passes the full gate, append a complete, self-contained spec to README** — don't just
leave it in your lane file. Your lane file is for live status ("what I'm working on now"); README is
the permanent, builder-readable findings archive. Writing to README is explicitly allowed and expected
(it's append-only: only ADD new dated entries, never rewrite existing ones).

**THE MARKER CONVENTION (important — this is how the relay works):** when you write a gated-but-not-yet-
approved candidate to README, put it under a heading that contains the exact phrase **`AWAITING GO-AHEAD`**,
e.g. `### University of Bridgeport — GATED, AWAITING GO-AHEAD (Codex, July 10)`. That exact phrase is the
signal.

**EFFICIENT SYNC (don't re-read the whole README — it's a long archive now):** to catch up on what the
other agent did, read the two short lane files (`lane-fable.md` + `lane-codex.md` "NOW" sections) and
`git log --oneline` / `git diff` of new commits — that's the cheap dashboard. Only open the full README
for the specific spec you're relaying or the specific dead-end you're checking. `grep -n "AWAITING
GO-AHEAD" research/README.md` finds every pending handoff in one cheap call. Reading the entire README
end-to-end is only needed ONCE at first onboarding.

**Fable is the single relay point to the builder — you (Codex) never message the builder yourself.**
The loop: you gate → you write the spec to README under an `AWAITING GO-AHEAD` heading → Nathan tells
Fable "check the README" → Fable pulls, finds every `AWAITING GO-AHEAD` block (yours and its own),
relays them to the builder in one go, and edits each heading to `Batch N sent` so it's not re-sent.
You just keep finding + writing; Fable handles the handoff. This keeps a single clean channel to the
builder (no double-sends) and means Nathan only has to say one thing: "check the README."

**This is the mechanism that removes manual relay of details:** everything lands in README in
builder-ready form, and Nathan's "go" is one sentence to Fable instead of shuttling specs. Nathan
still gates every handoff (nothing reaches the builder without his OK).

**Handoff spec — include ALL of this per school (self-contained, so the builder needs nothing else):**
- Name + rough enrollment + 4-year/CC
- Exact host/site/inst/term codes — and flag any REDIRECT (a `selfservice.*` host may 301 to a SaaS
  host like `*.elluciancloud.com`; a POST does NOT follow the 301, so always record the *resolved*
  host the adapter must actually use — this is how Bridgeport was found)
- The exact request recipe (URLs, method, full request body/params) — enough to reproduce blind
- Example course in the school's OWN subject-code format (verified to return 2+ live sections)
- Which existing adapter it fits, or "needs bespoke / needs new variant"
- Your gate evidence: live mixed-status counts + the COMPLETED-TERM TEST result (a finished term must
  show real closed sections) + latency + section-key-uniqueness + sibling-leak check
- Explicit dedup confirmation (grepped the name, checked for a bespoke adapter on another host)
- Verify through the PRODUCTION adapter path (instantiate the class + call fetch), not just raw
  endpoints, whenever the school fits an existing adapter — that's the bar the builder ships against.

Looking forward to working with you. Keep it flawless. — Fable 5
