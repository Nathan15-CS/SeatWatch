# SeatWatch SMS — go-live runbook (Nathan-run steps)

Credentials are placed by **Nathan directly on the server** — never pasted into a chat or
handed to Claude, exactly like the Stripe keys. Claude never sees the Auth Token.

## A. Twilio credentials → /etc/seatwatch.env  (secure, Nathan-only)

1. In the Twilio Console (console.twilio.com), copy from **Account Info**:
   - **Account SID** (starts `AC…`)
   - **Auth Token** (click to reveal)
2. SSH to the server:
   `ssh -i ~/.ssh/seatwatch-vm.key ubuntu@141.148.27.134`
3. Open the env file with sudo (it already holds the Stripe keys — same file, same pattern):
   `sudo nano /etc/seatwatch.env`
4. Add these three lines (paste your real values; TWILIO_FROM is the sender number):
   ```
   TWILIO_ACCOUNT_SID=AC_your_account_sid
   TWILIO_AUTH_TOKEN=your_auth_token
   TWILIO_FROM=+14437264415
   ```
   Do **not** set `SMS_ENABLED=1` yet — that is the go-live flip, a separate later step.
5. Save (Ctrl-O, Enter) and exit (Ctrl-X). The file is root-only (0600) — good.
6. Restart: `sudo systemctl restart seatwatch`

Placing `TWILIO_AUTH_TOKEN` alone makes the **inbound** webhook (`/sms/inbound`) live and
signature-validating, WITHOUT sending any outbound A2P text (outbound still needs
`SMS_ENABLED=1` + campaign approval). That's what lets us test the signature now.

## B. Inbound signature test (closes the circular-signature gap — pre-approval)

Prereq: the current app.py prep code is deployed, and step A is done.
1. In the Twilio Console → Phone Numbers → **+1 443 726 4415** → Messaging:
   set **"A message comes in"** to **Webhook**, `https://seatwatchapp.com/sms/inbound`, **HTTP POST**. Save.
2. From your phone, text the number: `HELP`, then `STOP`, then `START`.
3. Claude checks the server log for each: it prints
   `[sms] inbound from ****NNNN body='...' signature=VALID` — proving a REAL Twilio-signed
   request validated against our HMAC check (this is the gap that was only tested against
   itself before). `STOP` also writes a durable revocation; `START` re-subscribes.
   No outbound reply is sent during this test (replies are gated behind `SMS_ENABLED`).

## C. Dry-run (prove detection → message on real data — pre-approval)

1. With credentials placed, set `SMS_DRYRUN=1` in /etc/seatwatch.env, restart.
2. On a paid account, opt in at /text-alerts and watch a class likely to open a seat.
3. When a seat opens, the log prints
   `[sms DRY-RUN] would text ****NNNN segs=N cost=Nc body='...'` — the exact text that
   WOULD send, never sent. Confirms the whole pipeline. Unset `SMS_DRYRUN` when done.

## D. GO-LIVE (separate, explicit — only after 10DLC campaign is APPROVED)

Do NOT do this until the A2P campaign clears. Then, and only on Nathan's explicit word:
1. Twilio prepaid balance funded, **auto-recharge OFF** (the un-bypassable cost ceiling).
2. `SMS_ENABLED=1` in /etc/seatwatch.env, restart.
3. Real end-to-end self-test: opt in with your own number, trigger a real alert, confirm
   the text arrives and STOP works. THEN it's live for customers.

Cost note: `SMS_COST_CENTS` is the per-**segment** estimate (default 1¢). The ledger now
counts real segments per message (a 2-part alert bills 2), so the daily `SMS_DAILY_CAP_CENTS`
ceiling is accurate. Set `SMS_COST_CENTS` to your true Twilio per-segment rate before go-live.
