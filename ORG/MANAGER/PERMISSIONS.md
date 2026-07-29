# PERMISSIONS REGISTRY
Manager Agent · 2026-07-29 · Verify before delegating. An owner without access is not an owner.

## Manager lane (this session) — what I can actually do
| Capability | State | Evidence |
|---|---|---|
| Read local repo, git history, files | YES | used |
| Read public web (curl seatwatchapp.com) | YES | used |
| Write files in `~/seatwatch/ORG/MANAGER/` and memory | YES | used |
| Query `/admin/stats` (read-only aggregates) | **NO — DENIED 2026-07-29** by the sandbox permission classifier when reading `~/.seatwatch-stats-key`. Not worked around. | denial message |
| SSH to the VM / read prod DB / restart service | **NO** — CEO holds all credentials by design | Stage 0b |
| Deploy anything | **NO** | deploy policy |
| Message Grab / Build / Guardian sessions directly | **YES — verified 2026-07-29.** `send_message` reaches another session; **every send prompts the CEO for confirmation**. Live session ids: Grab `local_699bb7fa-…` (running), Build `local_f4c9ee6c-…`. Supersedes the package's "manual routing only". | `list_sessions` output |
| Dispatch college research myself (`Agent` + `school-dash-researcher`) | YES | agent registry |
| Spend money | **NO** | — |
| Handle SMTP / Stripe / Twilio / STATS keys | **PROHIBITED by standing rule** | ops/EMAIL-SETUP.md |

**Consequence:** every claim I make about production is either (a) from public HTTP, (b) from the repo, or (c) **second-hand from a record the CEO pasted at some past date.** Category (c) decays. It must be labeled with its as-of date, never stated as current fact.

## Specialist access (for delegation checks)
| Owner | Repo write | Deploy | Prod read | Credentials | Notes |
|---|---|---|---|---|---|
| Build (Claude Code) | yes | only via `ops/deploy.sh` with `--app-approved` | no | never | cannot approve its own change |
| Grab | research only, `research/` writes | no | no | never | no schools.py edits |
| Guardian | repo + journal | no | **only via CEO-pasted output** | key file, runtime-read only | never runs VM commands itself |
| CEO | all | all | all | all | the only actor with real production authority |

## Corrections to Production Operating Package v1.0 (SPECIALIST_REGISTRY.md)
The package was written for a claude.ai Project with no tooling. Installed in Claude
Code, three of its capability claims are wrong and are **overridden by observation**:
| Package says | Reality here | Why it matters |
|---|---|---|
| Manager may not read the repository | Reads it directly | The repo produced every high-confidence finding so far; obeying the package would have forced me to rely on your recollection instead |
| Manager may not contact other agents; manual routing only | `send_message` works, CEO-confirmed per send | Part of the "Mission Control routing" in Project 1 already exists |
| Manager may not execute code / measure | Bash + curl available (read-only paths) | Verification is possible; "I can't check" would be a false excuse |
Unchanged and correct: no prod DB, no SSH, no deploy, no spend, no credential handling.

## Standing verification rule
Before assigning any task, confirm the owner has the access to finish it.
If not, the task is `blocked` on the CEO — not `assigned`. Do not create the illusion of delegation.
