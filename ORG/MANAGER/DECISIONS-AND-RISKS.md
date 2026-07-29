# DECISIONS & RISK LOG
Manager Agent · opened 2026-07-29

## Decisions recorded
| Date | Decision | Reason | Owner | Consequence |
|---|---|---|---|---|
| 2026-07-29 | Manager Agent lane established; registry + board become the durable source of truth for routing and status | Chat-only tracking evaporates between sessions; four+ lanes have been running without a shared board | CEO | All lanes read `ORG/MANAGER/` before starting work |
| 2026-07-29 | **Demand outranks coverage.** School adds drop to P2 until one external user is proven | 804 schools / 0 external users; the marginal school is worth ~nothing today | Manager (CEO may override) | Grab's output queues rather than ships during the beta push |
| 2026-07-26 | Guardian V1 deployed to shadow; auto-roll disarmed | Recorded in `guardian-phase-d-journal.md` | CEO | Manual term-bump obligation created (M-10) |
| 2026-07-24 | AI Operating System v1.0 adopted as governing blueprint | Recorded in that doc | CEO | Constitution v1.2 is implementation input only |

## Decisions awaiting the CEO
| # | Decision | Recommendation | Cost of delay |
|---|---|---|---|
| D-1 | Activate email (M-3) | **Do it tonight or first thing.** ~2 minutes, $0. | Every beta signup who declines the push prompt gets *nothing*. 40% of family accounts had no push device. |
| D-2 | Remove the fabricated testimonial (M-4) | **Yes, immediately.** One line. | It is live right now, and you are about to point real students at it. Endorsement claims without real customers are an FTC exposure and a reputation risk you cannot buy back. |
| D-3 | Which deploy path is authoritative (M-1) | Mandate `ops/deploy.sh` for every lane, no exceptions | "What is live?" is again unanswerable from the record — the exact problem Phase D spent a week solving |
| D-4 | Beta go / no-go for Fall window (M-5) | Go, small and instrumented | The registration window closes ~mid-September and does not reopen until January |

## Decisions awaiting the CEO — added 2026-07-29 (Operating Package v1.0 install)
| # | Decision | Manager recommendation | Why it can't be assumed |
|---|---|---|---|
| D-5 | **1,000-college target vs. demand-first.** Package sets 1,000 as the near-term target and lists 7 objectives, none of which is acquiring a user. | **Demand-first.** Freeze coverage at 804 for ~6 weeks; spend everything on email activation, honest copy, and ~10 real students inside the Fall window. Resume coverage in October with evidence about what students actually want. | Changes every downstream priority, and the window closes ~mid-September. Not mine to decide. |
| D-6 | **Spending authority** (all package budget fields are `$[amount]`). | **$0 standing — every dollar asks first.** Model use inside the existing subscription; any external or recurring charge stops. Matches the standing minimize-out-of-pocket rule. | The package itself forbids assuming authority until this is set. |
| D-7 | **Grab Cloud Worker + Mission Control** (package P1). | **Defer to P3.** Salvage the cheap parts (durable state, leases, retries, idempotency, cost ceilings) into the reliability lane. See BOARD Project 6. | Large build; duplicates capability that already exists; scales supply not demand. |
| D-8 | **Governance precedence** among the freeze rules, the AI Operating System v1.0, and MANAGER-AGENT v1.0. | Production safety rules > AI OS > Manager Core. **A management prompt must never be able to relax a production freeze.** Recorded as proposed; say so if you disagree. | Ambiguous authority is how freezes get bypassed. |
| D-9 | **Grab is running right now** (04:01 today). Under demand-first it is working the wrong side of the problem. | Let in-flight work finish, then stand down: commit findings to `research/`, start no new candidates. I can draft the message; the send prompts you for confirmation. | Wasting work in flight is worse than either extreme. |

## Risks
| Risk | Likelihood | Impact | Mitigation | Owner |
|---|---|---|---|---|
| Beta launches with only push as a working channel → students hear nothing and never return | High | High | M-3 email activation before any invite goes out | CEO |
| Deployed-code identity unknown → shadow evidence is uninterpretable, Phase E decision unsupported | **Certain today** | High | M-1 reconstruction + M-2 mandate | Build |
| Shadow window ends 08-09 with no checkpoint record → 14 days spent, no evidence | High | Medium | M-7 catch-up cadence | Guardian |
| Monitor silence read as health (only runs while the app is open) | High | Medium | Treat Healthchecks.io as the only alarm; state the limitation in every report | Guardian |
| Term roll silently kills ~804 schools' watches | Medium now, high by Oct | Critical | M-10 procedure + guarded re-arm | Guardian |
| Fabricated social proof discovered by a real user or platform reviewer | Medium | High | M-4 | CEO |
| Single laptop holds parts of the lineage / manual backups | Medium | High | M-11 verify the ring actually fires | Run |
| Parallel lanes collide in app.py again | Medium | Medium | Board ownership column; freeze rules in `CONTRIBUTING_AGENT.md` | Manager |
| **Governance outgrows the company** — 4 org documents in 8 days for a product with 0 users; each one costs founder attention inside a closing window | High | High | Freeze the OS at v1.0. No new governance artifact without a named problem it solves. Scorecard deferred until there is throughput to measure. | Manager |
| CEO mistakes prompt-writing for automation (package names this risk itself) | Medium | High | Manual/assisted-routing honesty rule; `PERMISSIONS.md` states what actually runs | Manager |
| Hourly monitor spawns a fresh session each hour → no cross-run memory, so slow degradation is invisible | High | Medium | BOARD Project 7 / M-13: durable append-only health log | Guardian |
| Coverage work continues on reflex while the Fall window closes | High | High | D-5, and a stand-down note to Grab | CEO |

## Change log
**v1.0 — 2026-07-29.** Production Operating Package v1.0 installed as
`MANAGER-AGENT.md` (core), reconciled into `REGISTRY.md`, `PERMISSIONS.md`,
`BOARD.md`, this file. Amendments to the package, all evidence-based:
1. Routing mode corrected from *manual* to *assisted* — repo read, bash, `send_message`,
   and agent dispatch verified available in Claude Code (the package assumed a
   tool-less claude.ai Project).
2. College count corrected 793 → 804.
3. 1,000-college target and the supply-shaped objective list contested (D-5).
4. Package Project 1 re-priced from P1 to P3 (D-7).
5. `OPERATING_STATE.md` **merged, not applied** — applying it verbatim would have
   erased the four live P1 items (email, testimonial, deploy truth, shadow window).
6. Scorecard adopted in principle, deferred in practice: no throughput to measure yet.
