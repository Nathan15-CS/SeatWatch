# SeatWatch — Recovery Runbook

What to do when something breaks. Written to be followed under stress, in order.

## Backup layers (what exists now)

| Layer | Where | Cadence | Retained | Proven? |
|---|---|---|---|---|
| Live DB | server `~/seatwatch/watches.db` | continuous | — | — |
| Server backup | server `~/seatwatch/backups/` (cron 3:00 AM) | daily | 14 | ✅ restore drill passed |
| **Off-server copy** | **this Mac `~/seatwatch-backups/`** (launchd 9:15 AM) | daily | 30 | ✅ restore drill passed |

The off-server copy is the one that matters for a lost server. Every pull is
integrity-checked and refuses to keep a corrupt or empty file.

⚠️ The backups contain real user emails and watch history. They live **outside** the git
repo on purpose — never commit them, never put them in a public place.

---

## Scenario 1 — the app is down / not alerting

```bash
ssh -i ~/.ssh/seatwatch-vm.key ubuntu@141.148.27.134
systemctl status seatwatch          # is it running?
sudo journalctl -u seatwatch -n 50  # what did it say?
sudo systemctl restart seatwatch
```
`Restart=always` means systemd already retries. If it restarts in a loop, the log tail
names the cause. The poll lease is reclaimed automatically after ~3 minutes, so a crashed
process never permanently stops polling.

## Scenario 2 — bad data / accidental deletion (DB is corrupt but server is fine)

```bash
ssh -i ~/.ssh/seatwatch-vm.key ubuntu@141.148.27.134
cd ~/seatwatch
sudo systemctl stop seatwatch
cp watches.db watches.db.broken            # keep the evidence
ls -1t backups/watches-*.db | head         # pick the newest good one
cp backups/watches-YYYYMMDD-HHMMSS.db watches.db
sudo systemctl start seatwatch
```
Verify: `python3 -c "import sqlite3;c=sqlite3.connect('watches.db');print(c.execute('select count(*) from watches').fetchone())"`

## Scenario 3 — the server is GONE (deleted / dead disk / provider loss)

Data loss is bounded by the last off-server pull (≤ ~24h). Steps:

1. **Provision** a new Ubuntu VM (any provider). Note its IP.
2. **Install:** `sudo apt update && sudo apt install -y python3 git`
3. **Code:** `git clone <the private repo> ~/seatwatch` (code is fully in git — this is why
   nothing but data needs backing up).
4. **Data:** from this Mac —
   ```bash
   scp -i ~/.ssh/<key> ~/seatwatch-backups/watches-<newest>.db ubuntu@<NEW_IP>:~/seatwatch/watches.db
   ```
5. **Secrets:** recreate `/etc/seatwatch.env` (Google OAuth, VAPID, Stripe, Twilio,
   healthcheck URL). ⚠️ **These are NOT backed up anywhere** — see "Known gap" below.
6. **Service:** install `ops/seatwatch.service.template` from this repo (captured from the
   live VM 2026-07-31 — it was NOT in git before, so this step previously required rebuilding
   the unit from memory including the `SEATWATCH_ADMIN_TOPIC` token, which is unrecoverable
   that way). Fill that token from the env backup, then
   then `sudo systemctl enable --now seatwatch`.
7. **DNS:** point `seatwatchapp.com` at the new IP (Cloudflare).
8. **Verify:** `curl -s https://seatwatchapp.com/ | grep -o '[0-9]* universities'` and confirm
   the poller log shows a cycle.

**Drill:** `ops/REBUILD-DRILL.md` rehearses steps 1-2 and 5-8 without touching production
DNS. Run it before students depend on the service.

**Rehearsed?** The *data* half (steps 3–4) is proven — a drill restored the off-server copy
and the app opened it cleanly. Steps 1–2 and 5–8 are documented but **never rehearsed
end-to-end**; expect a few hours, not minutes.

---

## Known gap (do this yourself)

**~~Server secrets are not backed up~~ — CLOSED 2026-07-30.** The CEO took a copy of
`/etc/seatwatch.env` into a password manager after the credential rotation. What follows is
kept as the standing reason it matters:

**Originally:** `/etc/seatwatch.env` holds the Google OAuth client,
VAPID push keys, Stripe keys, and Twilio credentials. If the server is lost, they must be
re-created/re-issued from each provider's console. Losing the **VAPID keys specifically**
would silently break every existing web-push subscription (students would stop getting
alerts and wouldn't know why).

Recommended: keep a copy of `/etc/seatwatch.env` in a password manager (1Password, Bitwarden,
Apple Passwords). Claude deliberately does not copy or store these.

## Health checks

- `python3 readiness.py` — full readiness report (alert correctness, fail-closed, crash-safety,
  lease, canary).
- `bash ops/pull_backup.sh` — pull + verify an off-server backup on demand.
- `tail ~/seatwatch-backups/pull.log` — did the daily off-server pull run?
- healthchecks.io — pings only on a clean poll cycle; it emails if the poller goes silent.
