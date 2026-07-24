# STAGE 0c — DEAD-MAN MONITORING VERIFICATION — 2026-07-23 (UTC)

Operator: Nathan (CEO) · Verifier: Phase-1 Run session · Risk: R0 (read-only; no correction needed) · **Result: PARTIAL — monitoring verified; rotation closure pending** (CEO-directed status, 2026-07-24)

| Item | Finding |
|---|---|
| Service unit | `seatwatch` — active |
| Running process holds HEALTHCHECK_URL | Yes (verified by count against /proc/<pid>/environ) |
| /etc/seatwatch.env | Does NOT contain HEALTHCHECK_URL (anchored and unanchored counts: 0) |
| Actual source | ~~Inline `Environment=` in the unit file itself~~ **CORRECTED 2026-07-23 (rotation H1, CEO-reported):** the URL lives in the drop-in `/etc/systemd/system/seatwatch.service.d/healthcheck.conf` — not in the main unit file and not in `/etc/seatwatch.env`. `DropInPaths` also includes `env.conf`. Drop-ins load last and win. Rotation H7 closure: pending — will be recorded as technically verified (pasted evidence) or CEO-attested (statement), whichever the CEO provides. |
| Dashboard | Check Up · pings ~every 20s (matches poller cadence — pings prove completed cycles, not mere process existence) · period 5 min · grace 5 min |
| Corrections applied | None — functioning monitoring is a PASS, not a defect. No new check created; /etc/seatwatch.env not edited. |

**Config-topology note (context for future stages):** environment is split across two sources — `/etc/seatwatch.env` (via EnvironmentFile) and inline `Environment=` directives in the unit. Not a defect; recorded so Stage 2+ tooling and any future env audits look in both places. Consolidation is NOT proposed.

## Open security task (follow-up, NOT part of Stage 0c — CEO-flagged)

**Rotate the Healthchecks ping URL before production deployment continues** (i.e., before Stage 2's first real deploy). The URL was exposed during verification; anyone holding it can fake "alive" pings and blind the dead-man switch. Rotation outline (own approval when scheduled): regenerate/replace the check's ping URL in the healthchecks.io dashboard → update the unit's `Environment=` line (CEO types it; value never enters transcripts) → `sudo systemctl daemon-reload && sudo systemctl restart seatwatch` → confirm fresh pings. Risk R1.
