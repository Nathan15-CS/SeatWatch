# SEATWATCH COMPANY REGISTRY
Maintained by: Manager Agent · Established 2026-07-29 · CEO: Nathan

This file is the routing authority. If it disagrees with a chat, this file wins
until the CEO changes it.

## 1. Company
| Field | Value | Evidence |
|---|---|---|
| Product | Course-seat alerts for US university registration systems | seatwatchapp.com (HTTP 200) |
| Entity | LLC filed | prior record |
| Coverage | **804 universities live** | homepage string, verified 2026-07-29 |
| Users | **5 accounts / 17 watches — all CEO + family. ZERO external users.** | prod DB 07-26 backup |
| Revenue | $0. Stripe built, dormant. | env-gated |
| Governing doc | `ORG/SEATWATCH-AI-OPERATING-SYSTEM.md` v1.0 (adopted 2026-07-24) | |
| Current business goal | **Prove one stranger will use it before Fall add/drop closes (~mid-Sept).** Coverage is no longer the constraint. | [[seatwatch-zero-external-users]] |

## 2. Production systems
| System | State | Owner |
|---|---|---|
| Web app / poller | Oracle Ubuntu VM, systemd `seatwatch`, 20s cycle | Run lane |
| Prod DB | `/home/ubuntu/seatwatch/watches.db` (SQLite, no sqlite3 CLI on box — use python3) | Run lane |
| Guardian V1 | **SHADOW-OBSERVING** since 2026-07-26 06:14Z, sha `1ee417f`. Enforcement OFF. Window ends ~2026-08-09. | Guardian lane |
| Auto term-roll | **DISARMED** (AUTO_ROLL_TERMS unset) — deliberate; creates a manual-bump obligation at every semester boundary | Guardian lane |
| Alert channels | web push (works, 3/5 family had a device) · email (**BUILT BUT INERT — no SMTP creds**) · ntfy (proves nothing) · SMS (dry-run only) | Run lane |
| Monitoring | Healthchecks.io dead-man (only true 24/7 alarm) + hourly `seatwatch-guardian-hourly-monitor` (runs **only while the Claude app is open** — silence ≠ health) | Guardian lane |
| Backups | Manual `.bak` → `~/SeatWatchVault/`; off-server ring + `ops/pull_backup.sh` committed 07-28, **schedule unverified** | Run lane |
| Deploy | `ops/deploy.sh` (schools\|app modes) + `ops/rollback.sh`; record = `DEPLOYED.log` | Build lane |

## 3. Specialist registry (routing table)
| Specialist | Owns | Never gets |
|---|---|---|
| **Grab** | Finding/researching/validating new colleges; vendor detection; adapter specs; evidence packages | Code, deploys, marketing, strategy, general questions |
| **Build (Claude Code)** | Implementation, bugfixes, tests, migrations, infra config, internal tools, deploy scripts | Deciding whether to deploy; approving its own work |
| **Guardian (Reliability)** | Guardian V1, shadow evidence, reliability confidence, incident triage, the deployment journal | Feature work; auto-fixing prod |
| **CEO (Nathan)** | Money, legal, identity, credentials, public copy, pricing, deploy authorization, kill/pivot | Routine implementation detail |
| **Manager (this lane)** | Routing, decomposition, priority, tracking, review of evidence, escalation, OS improvement | Doing specialist work "because it can" |
| Growth / Support / Analytics / Finance / Security | **DO NOT EXIST.** Work for these roles is held in `BOARD.md` as specs, or routed to CEO/Build. | — |

## 4. Approval boundaries (standing)
- **Direct-deploy allowed:** school adds only (accuracy-gated, low-risk).
- **CEO go required:** anything touching money, pricing, public copy, legal text, UI, credentials, or app.py behavior outside a school add.
- **Never:** unreviewed prod deploy, secrets in chat, destructive DB change without a fresh verified backup, one agent creating+approving+deploying its own change.
- **Credential rule:** Claude never handles SMTP/Stripe/Twilio/STATS keys. Key material never enters chat, journal, repo, or task config.

## 5. Spending limits
Out-of-pocket target ≈ $0. No infra/service spend without explicit CEO approval and a stated cost ceiling. No unbounded model usage authorized.

## 6. Reconciliation with Production Operating Package v1.0 (2026-07-29)
The package's `COMPANY_REGISTRY.md` was accepted as intent, with corrections:
| Package field | Correction | Evidence |
|---|---|---|
| "Approximately 793 colleges; verify before operational use" | **804** | homepage, curled 07-29 |
| "[Founder name]" | Nathan | — |
| "Near-term college target: 1,000" | **CONTESTED — see decision D-5.** No proven discovery mechanism covers the gap, and coverage is not the binding constraint. | discovery-levers record; 0 external users |
| 7 primary objectives, none of which is acquiring a user | **Gap flagged.** Objectives 2–4 (expand coverage, Grab cloud worker, Mission Control) all scale supply. | verified user count |
| All budget fields `$[amount]` | **BLANK — pending D-6.** Package rule applies: *"Until completed, Manager must not assume unlimited authority."* | — |

### Governance precedence (proposed 07-29, awaiting CEO ratification)
Three governing documents now exist. Proposed order, strictest-wins on conflict:
1. **Production safety rules** — Phase-1 freeze (`CONTRIBUTING_AGENT.md`), Guardian V1
   freeze, deploy policy. These bind what may touch prod and are never relaxed by a
   management document.
2. **`ORG/SEATWATCH-AI-OPERATING-SYSTEM.md` v1.0** — company shape, risk classes,
   authority ladder, maker≠checker≠releaser.
3. **`MANAGER-AGENT.md` v1.0** — how this lane behaves.
Rationale: the newest document is not automatically the most authoritative. A manager
prompt must not be able to override a production freeze.

## 7. Open registry gaps (do not block work)
- Nightly backup schedule: committed, **not verified running**.
- iOS/Android store accounts: blocked on Apple/Play signup (D-U-N-S).
- Ping URL + VM IP rotation: parked post-shadow-window.
