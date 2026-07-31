# Full-rebuild drill (M-6) — rehearsing "the server is gone"

`ops/RECOVERY.md` documents Scenario 3 in eight steps and states honestly that steps 1–2 and
5–8 have **never been rehearsed**. Data recovery is proven; standing the whole thing up is not.
This drill closes that, and it is designed so **production is never touched**.

## Why bother, when it's already written

A runbook that has never been executed is a hypothesis. Every recovery plan contains a step
whose author assumed something they knew and you don't. Tonight's example: the systemd unit was
not in git, so step 6 — "recreate the systemd unit" — would have stopped a rebuild dead, and the
`SEATWATCH_ADMIN_TOPIC` token could not have been reconstructed at all. That was found by
*looking*, not by rebuilding. A drill finds the rest.

The output that matters is a number: **how long until students are being alerted again.** Right
now the honest answer is "hours, probably, nobody has tried."

## The key safety property: no DNS change

The scary step is 7, pointing `seatwatchapp.com` at a new IP. **The drill skips it entirely.**
Verify the rebuilt host by forcing the hostname at the client instead:

```bash
curl -sk --resolve seatwatchapp.com:443:<NEW_IP> https://seatwatchapp.com/ | grep -o '[0-9]* universities'
```

Production DNS is never edited, so the live site cannot be affected. If the drill goes badly you
delete a VM and nothing else happened.

## Before you start

- The `/etc/seatwatch.env` copy in your password manager (backed up 2026-07-30)
- The newest off-server DB backup on the Mac
- `ops/seatwatch.service.template` from this repo
- **Twilio/Stripe/Google consoles are NOT needed** — that is the point of having the env backed up.
  If you find yourself opening a provider console, stop and note it: the backup was incomplete.

## The drill

**Time-box it to 3 hours.** If it runs over, stop and write down where you were. An unfinished
drill that produces an honest blocker list is worth more than a finished one at 3am.

1. **Start a clock.** Note the time. This is the number the drill exists to produce.
2. **Provision** a fresh Ubuntu VM (Oracle free tier is fine — same provider means you also
   rehearse that console). Note the IP.
3. `sudo apt update && sudo apt install -y python3 git`
4. `git clone <private repo> ~/seatwatch`
5. `scp` the newest `watches-*.db` from the Mac to `~/seatwatch/watches.db`
6. Recreate `/etc/seatwatch.env` from the password manager. `sudo chmod 600` it.
7. Install the unit from `ops/seatwatch.service.template`, fill `SEATWATCH_ADMIN_TOPIC` from the
   env backup, `daemon-reload`, `enable --now`.
8. **Verify without DNS**, using the `--resolve` command above. Confirm the school count matches
   production and `journalctl -u seatwatch` shows a real poll cycle.
9. **Stop the clock.** That elapsed time is your recovery-time objective. Record it.
10. **Destroy the VM.** Confirm it is gone — a forgotten drill VM polling the same schools with the
    same DB is a duplicate-alert source, and its poll lease is not shared with production.

## What to write down, whatever happens

- **Elapsed time** — the RTO
- **Every step where the runbook was wrong, vague, or assumed knowledge you didn't have**
- **Anything you had to fetch from a provider console** — each one is a hole in the env backup
- **Anything you had to ask another person or an agent for** — that is a single point of failure
  wearing a different hat

Then update `ops/RECOVERY.md` so the next run is faster, and change its "Rehearsed?" line from
"never rehearsed end-to-end" to the date and the measured time.

## Not urgent, and say so honestly

Data loss is already bounded at ~24h by the off-server ring, and that half is proven. This drill
converts an unknown recovery *time* into a known one. Worth doing before students depend on the
service; not worth doing at the end of a twenty-hour day.
