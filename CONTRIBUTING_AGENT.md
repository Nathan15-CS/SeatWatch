# SeatWatch — Agent Onboarding Brief

## PHASE-1 FREEZE (2026-07-24, CEO-ordered — lift only by CEO)
app.py may be changed only by the Phase-1 Run session. schools.py lane commits may continue. No deployment is permitted unless an approved stage packet explicitly authorizes it and the deployment uses the Stage-2 deploy script. Deploying from a dirty tree is prohibited. Automated repository-writing tasks remain disabled unless separately re-approved after their staging and push behavior is reviewed.

You are a coding agent joining the SeatWatch project. Read this fully before writing any code.
Everything below is hard-won — most of it comes from real bugs already caught and fixed.

## What SeatWatch is
A course-seat alert tool: a student picks a full class section, we watch the school's live
registration system, and the instant a real seat opens we push them a phone alert. Live at
seatwatchapp.com. Python 3 **standard library only** (no framework, no pip deps — this is
deliberate: it keeps deploys to a single `scp` and eliminates dependency vulnerabilities).
Source at `~/seatwatch/`. ~640 schools and growing.

## THE PRIME DIRECTIVE — read this twice
**Never a false "open."** The product's entire value is trust: an alert must mean a seat is
genuinely available. A single false alert damages the owner's reputation permanently. This
overrides speed, coverage, everything. Concretely:
- Read the school's AUTHORITATIVE status/seat field. Only mark a section open when the source
  says it's truly open (e.g. Banner `seatsAvailable`, PeopleSoft `enrl_stat=='O'`, an explicit
  "Open" status). On ANY doubt or failure, return `{}` / not-open — never guess "open."
- The engine treats an empty result as "skip," so failing silent is SAFE; fabricating is FATAL.

## Non-negotiable gate — EVERY new school must pass this LIVE before shipping
1. **Fetch through the PRODUCTION code path** (instantiate the real adapter, call `.fetch()`),
   not a one-off script. If it doesn't work through production, it doesn't ship.
2. **Real mixed status**: confirm the source actually returns a mix of open AND closed/full —
   ideally run a COMPLETED-TERM test (a past term should show closed sections). If everything
   reads "open" even in a finished term, the guest view is FAKE (defaults to open) → SCRAP it.
   This exact trap killed the entire classic-PeopleSoft flagship segment (Penn State/UCF/etc).
3. **Section-collapse screen**: section keys must be UNIQUE per course. If the source zeroes
   sequence numbers (all sections key to "0"), you collapse N sections into 1 and miss opens —
   key by CRN/classNumber/enroll-code instead. (This was a LIVE bug on 9 Alabama schools.)
4. **Sibling-leak / exact-course scoping**: a search for "MATH 2A" must not return "MATH 2AX"
   rows. Scope parsed rows to the exact watched code. (Caught live at UC Irvine.)
5. **No hidden sections**: never send a time-of-day / day-of-week / open-only filter that could
   hide a watched section. A watched section that never appears = a silent miss. (Caught at UCLA.)
6. **Latency**: cut anything that takes >30s per fetch (a slow host stalls the poller). Drake
   was cut twice at 137s.
7. **Term freshness**: "returns data" ≠ "is live." Reject terms marked "(View Only)"/archive.
   (Lafayette + Victor Valley were scrapped for serving stale/archive terms as if current.)
8. **Dedup by NAME, not just host/id**: grep schools.py for the school's NAME before adding —
   the same school appears under different domains (UNC Charlotte was handed off 3x; Albany
   State shipped as a duplicate once). The registry guard now enforces this at import.

## Architecture
- `schools.py` — one adapter class per school or per shared system. Base families:
  `Banner`, `PeopleSoft`, `Fose`, `Colleague`, `MinnState`, `VCCS`, `CtcLink`, plus bespoke
  ones (UMD, UCI, UCSC, UCSB, UCLA, SFSU, UIUC...). Most schools are a ~4-line subclass.
  Adapter contract: `fetch(courses) -> {course: {section_id: {"open": bool, "seats": int|None}}}`.
  Return `{}` on any failure. `valid_course()`, `reg_url()`, and (for auto term-roll)
  `resolve_term()`/`refresh_term()` round it out.
- `app.py` — stdlib HTTP server, Google OAuth, SQLite, the background poller that diffs seat
  state and fires alerts, and all HTML. The poller only fetches schools that have ACTIVE
  watches, so registering a school costs nothing until someone uses it.
- Registry: `SCHOOLS = _guard_registry([... all school instances ...])`. `_guard_registry`
  FAILS THE IMPORT on duplicate id, duplicate exact name, or a shadowed duplicate class — so a
  dup can't reach the live site; it crashes tests first. Keep it that way.
- Term auto-roll: `refresh_all_terms()` lets each adapter self-update to the new semester,
  verify-before-adopt (only adopts a new term after it returns real data).

## Workflow (do this in order, every change)
1. Write/modify the adapter in `schools.py`.
2. Gate it live (all 8 checks above) through the production fetcher.
3. Bump the school count in `app.py` (title, meta, `data-count`, `data-count2`, badge — grep
   the old number).
4. `python3 -c "import schools; print(len(schools.SCHOOLS))"` must pass the guard.
5. Commit + push to GitHub. **Then STOP** — do NOT deploy. Deploy is the owner's manual step
   (a safety gate: nothing reaches the live site without a human). Hand the owner the
   deploy command and a short reviewer summary.
6. Record the outcome in `research/README.md` (what shipped, what was scrapped and WHY).

## Deploy (owner runs this, not the agent)
```
scp -i <ssh-key> ~/seatwatch/app.py ~/seatwatch/schools.py ubuntu@<host>:~/seatwatch/ && \
ssh -i <ssh-key> ubuntu@<host> "sudo systemctl restart seatwatch && sleep 2 && systemctl is-active seatwatch"
```
Credentials (SSH key, GitHub token) stay with the owner — never paste them into code or chat.

## RULES OF ENGAGEMENT (critical if another agent is also on this repo)
- **One builder of record per file at a time.** If another agent (or a parallel session) is
  editing `schools.py`, do NOT edit it simultaneously — uncommitted edits from two agents in
  one file is how work gets lost. Coordinate lanes; commit before handing off.
- Check `git log` / `git status` before starting so you don't clobber unpushed work.
- Never auto-apply another tool's suggestions blind. Verify against the live code first.
- If you find a bug in ALREADY-SHIPPED code, verify it's real against production before
  declaring "live breakage" (one false-alarm "urgent bug" was tested against the wrong
  school's term code — it wasn't broken).

## The expensive lessons, condensed (don't rediscover these)
- Guest views that show everything "Open" in a finished term are fake — scrap.
- Zero-sequence sources collapse sections — key by CRN/classNumber.
- Loose course-number matching leaks sibling courses — scope to exact code.
- Time-of-day filters hide night sections — never send them.
- Archive/"View Only" terms fetch cleanly but are stale — reject.
- Same school hides under multiple domains — dedup by name.
- Hand-pinned term codes die silently at semester rollover — auto-roll with verify-before-adopt.
