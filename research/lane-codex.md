# Lane status — Codex Sol 5.6 (research agent B)

**Only Codex writes this file. Fable reads it but never edits it.**
Codex: claim your vein here BEFORE you start probing, then commit + push. Update when you start/finish.

## NOW (active claims — Fable will not touch these)
- **CLAIMED July 10, 2026: newer-Colleague-API investigation, round 2.** Bridgeport has been relayed
  as batch 18. I will now inspect Lebanon Valley College, McDaniel College, and SUNY Onondaga from
  the remaining 405/400 candidate list, identify each public guest-search contract, and run the
  complete accuracy/efficiency gate on any source exposing authoritative availability.
- Research-only: I will not edit `schools.py`, contact the builder, or hand off candidates without
  Nathan's explicit approval.

## DONE this partnership
- **July 10, 2026 — newer Colleague API investigation (Augustana + Bridgeport).**
  - **University of Bridgeport (CT, 4-year; `colss-prod.bridgeportsaas.elluciancloud.com`; official
    `selfservice.bridgeport.edu` redirects there):** public guest `POST /Student/Courses/PostSearchCriteria`
    with the existing CSRF/session flow returns JSON in the familiar `Courses` + `CourseFullModels` shape;
    `POST /Student/Courses/Sections` returns `SectionsRetrieved.TermsAndSections`. The current
    Fall 2026 `ENGL 101` example returned 14 sections: 8 `Open`, 1 `Closed`, 5 `Waitlisted`; every
    open row had positive `Available`, every non-open row had zero `Available`, and all 14 `Number`
    keys were unique. `Available == Capacity - Enrolled` held for all 14. Spring 2026 (past) returned
    9 Open + 1 Waitlisted, so the guest view is not an all-open status fake. Fall term registration
    metadata included registration through 2026-09-07; responses were live, not View Only/archive.
    Exact course filtering is mandatory: the keyword response also returns neighboring ENGL courses;
    select the exact `SubjectCode` + `Number` before using `MatchingSectionIds`. Latency: 1.33s search,
    0.79s sections. This is a clean candidate for a reusable Colleague variant, pending production-path
    implementation/gate by the builder after Nathan's approval.
  - **Augustana College (IL; `selfservice.augustana.edu`; distinct from Augustana University/`augie.edu`):**
    its public catalog uses `POST /Student/Courses/SearchAsync` with payload
    `{"searchParameters": <JSON-string>}` and `POST /Student/Courses/SectionsAsync` with
    `{"courseId", "sectionIds"}`. Fall 2026 `BIOL 130` returned six unique IDs with four status `0`
    rows (positive seats) and two status `2` rows (0 seats, full); `Available/Taken/Capacity/Waitlisted`
    was internally consistent on all six. Fall term is `2026-27 Fall Semester`, with registration
    dates beginning 2026-04-22 and ending 2026-08-31; response is current, not archived. Latency:
    2.04s SearchAsync, 0.39s SectionsAsync. Sibling-leak test: keyword `BIOL 130` returns both
    `BIOL 130` and `BIOL 130L`, so exact `SubjectCode` + `Number` scoping is required. **Conditional:**
    `AvailabilityStatus` is numeric (0/2) and the public UI exposes seat CSS/counts rather than textual
    status labels; do not hand off until the enum mapping (0=open, 2=full) is independently confirmed
    through the production adapter/gate.
  - **Gustavus Adolphus:** official `selfservice.gustavus.edu` redirects to
    `colselfsrvprod.gac.edu`; a legacy endpoint probe returned 200 JSON, not the documented 405/400.
    No candidate handoff made; leave for a later pass if the newer-vs-legacy distinction needs more
    investigation.
- No `schools.py` or builder changes made. No builder handoff sent; waiting for Nathan's explicit go-ahead.
- **Bridgeport relay outcome:** Fable relayed the gated spec as batch 18 after Nathan's approval.

## Last push
- Sync base confirmed July 10, 2026 at `ba6a6d6`; commit `14cb230` is present in this repository.
- Round-1 findings were pushed in `51967c7`; round-2 claim is pending push.
