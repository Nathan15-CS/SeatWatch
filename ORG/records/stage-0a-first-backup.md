# STAGE 0a — FIRST OFF-VM BACKUP — 2026-07-23 (UTC)

Operator: Nathan (CEO) · Planner/Verifier: Phase-1 Run session · Risk: R1 · **Result: PASS** (CEO-recorded)

| Item | Value |
|---|---|
| Backup name | seatwatch-2026-07-23T161619Z.bak |
| VM path | /tmp/seatwatch-2026-07-23T161619Z.bak (RETAINED pending Stage 1 restore rehearsal) |
| Mac path | ~/SeatWatchVault/seatwatch-2026-07-23T161619Z.bak (mode -rw-------) |
| DB path confirmed | /home/ubuntu/seatwatch/watches.db (SEATWATCH_DB override count: 0) |
| Tooling | VM: **no sqlite3 CLI** → Python 3 stdlib route (standard for VM-side SQLite ops from now on); Mac: native sqlite3 |
| Size | 53,248 bytes (context only) |
| integrity_check | VM: ok · Mac: ok |
| Table counts (VM = Mac, matched) | conv_signals=9 · device_markers=1 · push_subs=3 · stripe_events=1 · users=5 · watches=17 |
| SHA-256 VM | 60d3f338921522a99e7bedeeb68b78b1bc32d167791ad20c1a55369e89f2c468 |
| SHA-256 Mac | 60d3f338921522a99e7bedeeb68b78b1bc32d167791ad20c1a55369e89f2c468 (**match**) |
| Non-modification | No application code, configuration, service state, credentials, or source database intentionally modified; artifacts additive only |

**Schema note:** no `alert_log` table exists in production — to reconcile against code during Stage 8 (metrics); non-fatal.

**Recorded exception (CEO-accepted):** the exact command that created the VM backup was executed off-transcript and was never pasted; source→backup consistency therefore rests on integrity_check=ok + coherent counts rather than a witnessed backup-API invocation. Mitigation: Stage 1's automated nightly backups use the Python `Connection.backup()` API explicitly and supersede this copy within one day of landing; the Stage 1 restore rehearsal re-validates. Logged per the no-silent-override rule.

**Deviation log:** P1–P3 outputs initially skipped, later supplied on request (NO-SQLITE-CLI; override=0); VM IP appeared in transcript contrary to operator's own ground rule (no action; noted).
