# Lane status — Grabber (research agent, successor to Fable's research lane)

**Only Grabber writes this file.** Codex/Builder read it. Continuation of `lane-fable.md` (archived).
Single relay point to Builder is unchanged: gated finds → README under `AWAITING GO-AHEAD` → on
Nathan's go, relay to Builder (session local_475a2545) as "Batch N" → mark SENT.

## NOW (July 11, evening) — CT-log vein, corrected sweep in progress
- **Running the CT-log sweep over the 229 never-swept public-college domains** (`ctlog_targets_remaining.json`).
  Method: crt.sh (recovered — HTTP 200 again, **unlimited**, replaces rate-limited certspotter) →
  filter banner-ish subdomains → probe Banner-9 SSB `getTerms` → gate promising hosts through the
  PRODUCTION `schools.Banner.fetch()`.
- **crt.sh is back up** — this is the unlock. certspotter's ~10/hr cap no longer blocks a full sweep.
- **⚠️ BUG FOUND + FIXED (false-negative trap):** my first sweep used 6 concurrent workers. crt.sh
  chokes under concurrency → returned empty/None for 209/210 domains, and the certspotter fallback was
  rate-limited (429) → **the whole run was a false "no Banner anywhere."** It even missed `ssb.calu.edu`
  (a real Banner host). **Fix (v2, `ctlog_sweep.py`):** low concurrency (2 workers), retry crt.sh on
  502/503/timeout/non-JSON with backoff, and a hard `ct_ok` flag — a domain is only counted as "checked"
  if crt.sh returned real JSON; failed lookups go to `needs_retry.json`, NEVER counted as clean. v2
  health: ct_ok ≈ 9/10 (vs v1's 1/210). Reinforces the meta-lesson: never trust an "exhausted/empty"
  result without checking the tool actually ran.
- **Targets file overlaps schools.py** (e.g. `calu.edu` = PennWest, already shipped as a `PASSHE`
  subclass on a shared mepCode host). So dedup MUST be by school NAME, not host. `shipped_ref.json` =
  all 587 shipped names / 466 hosts / 591 ids for fast dedup screening at gate time.
- **`selfservice.*` / `*.elluciancloud` hosts = COLLEAGUE, not Banner** → these correctly fail the SSB
  probe; I collect them into `colleague_leads_for_codex.json` for Codex's lane (I don't work Colleague).
- **Tooling ready:** `gate_banner.py` (gates ANY host through production Banner.fetch — discovers real
  courses via the live subject list, reports open/full mix; validated against Northeastern = 44 open/26
  full, PASS). `ctlog_secondpass.py` (re-probes every "banner host, no live SSB" domain against the
  alt base_path `registration` + the old Banner-8 route `bwckschd.p_disp_dyn_sched` — closes the
  base_path/Banner-8 false-negative gap before declaring a domain Banner-free).

## Gate discipline (unchanged, enforced)
- Gate through the PRODUCTION adapter (`.fetch()`), never a side probe (batch-23 lesson).
- Numeric-enrollment Banner (reads `seatsAvailable`): disproof = LIVE-term real FULL sections
  (seats==0) mixed with open. Completed-term all-open is NOT disqualifying (post-drop melt).
- Dedup by NAME; latency/sibling-leak screen; classic PeopleSoft COMMUNITY_ACCESS = never ship.

## In flight (Builder, track only): Berkeley ~45k, Fairfield, SDCCD×3; SCF (batch 25) building.
Deploy pending Nathan (site live at 655; commits ready through 664 + SCF).
