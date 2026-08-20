# SeatWatch

Get an instant phone alert the second a seat opens in a full college class —
across 880+ universities. Live at **https://seatwatchapp.com**.

SeatWatch watches the *specific section* a student wants and pushes them a
notification the moment a real seat opens, so they get the class, professor, and
time they actually want.

> **Operated by SeatWatch LLC (Maryland).** Not affiliated with any university.

## Quick facts

| | |
|---|---|
| Stack | Python 3 standard library only (no web framework) + SQLite |
| Hosting | Oracle Cloud Always-Free VM, Caddy reverse proxy, Cloudflare edge |
| Cost | ~$0/month |
| Schools | 120+ (Ellucian Banner pipeline + per-school custom adapters) |
| Auth | Google Sign-In (OAuth 2.0), signed session cookies |
| Alerts | Web Push (VAPID) — first-party, no third-party app required |

## Repository layout

```
seatwatch/
├── app.py          # web app: HTTP server, auth, routes, poller, web push, all HTML/CSS
├── schools.py      # school registry: one class per school/pipeline that returns live seat data
├── seatwatch.py    # shared engine helpers: notify() (ntfy), log(), the legacy single-user engine
├── watch.py        # legacy CLI watcher (superseded by app.py; kept for reference)
├── icon-192.png    # app icons (PWA / web push)
├── icon-512.png
├── PROJECT_OVERVIEW.md   # full project reference (features, DB, routes, env vars, limits)
├── ARCHITECTURE.md       # end-to-end walkthrough of how a request/alert flows
└── .gitignore            # excludes secrets (*.pem, .env) and user data (*.db)
```

The layout is intentionally **flat and dependency-free** — this is what makes
deployment a single `scp` of two files and keeps hosting at $0. See
`PROJECT_OVERVIEW.md` for why, and what NOT to reorganize.

## Running locally

```bash
# nothing to install — stdlib only
SEATWATCH_DEV=1 python3 app.py     # serves http://localhost:8080
```

Secrets (Google OAuth, VAPID keys) come from environment variables and are never
committed. See `PROJECT_OVERVIEW.md → Environment variables` for the full list.
