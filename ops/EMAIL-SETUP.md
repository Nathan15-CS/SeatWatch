# Turning on email alerts (operator action — 2 minutes)

Email is the only alert channel with **zero friction**: no browser permission prompt, no
app install, no iOS add-to-home-screen step, and it works on every device. It costs
nothing. It's the free/slow lane next to SMS's paid/fast lane.

The code is already built and tested — `send_email()` uses STARTTLS, authenticates, and
sends from "SeatWatch <support@seatwatchapp.com>". It is inert only because no SMTP
credentials are set (`EMAIL_ENABLED` is False whenever host/user/pass are blank, so
nothing breaks — the other channels just carry on).

## Step 1 — create a Google App Password (Nathan)

support@seatwatchapp.com is a Google Workspace mailbox (the domain's MX points at Google),
so Gmail's SMTP works with an **App Password** — not the account password.

1. Sign in as **support@seatwatchapp.com**.
2. 2-Step Verification must be ON (App Passwords don't exist without it):
   https://myaccount.google.com/signinoptions/two-step-verification
3. Create the App Password: https://myaccount.google.com/apppasswords
   Name it `SeatWatch server`. Google shows a **16-character** code (like `abcd efgh ijkl mnop`).
   Copy it — **the spaces don't matter, they can be removed**.

⚠️ Claude never sees, stores, or types this value. You paste it on the server yourself,
the same rule used for the Stripe and Twilio keys.

## Step 2 — put it on the server (Nathan)

```bash
ssh -i ~/.ssh/seatwatch-vm.key ubuntu@141.148.27.134

sudo tee -a /etc/seatwatch.env >/dev/null <<'EOF'
SMTP_HOST=smtp.gmail.com
SMTP_PORT=587
SMTP_USER=support@seatwatchapp.com
SMTP_PASS=PASTE_THE_16_CHAR_APP_PASSWORD_HERE
EOF

sudo systemctl restart seatwatch
```

`SMTP_FROM` is not needed — it defaults to `SMTP_USER`, so mail comes from
support@seatwatchapp.com, which is also the address every legal/support page points to.

## Step 3 — verify (either of us)

```bash
ssh -i ~/.ssh/seatwatch-vm.key ubuntu@141.148.27.134 \
  "cd ~/seatwatch && python3 -c \"import app; print('EMAIL_ENABLED:', app.EMAIL_ENABLED)\""
```

Then a real send test — ask Claude to run it, or:

```bash
cd ~/seatwatch && python3 -c "
import app
print(app.send_email('support@seatwatchapp.com', 'SeatWatch email test',
                     'If you can read this, email alerts work.', 'https://seatwatchapp.com/'))"
```

`True` plus the message landing in the inbox = done. Check spam the first time; if it lands
there, that's worth knowing **before** students rely on it.

## Why this matters for the beta

Right now a student who declines the browser notification prompt — or is on an iPhone and
never completes the add-to-home-screen step — has **no working channel at all**. Live
example from the family accounts: only 3 of 5 had a push device registered, so 40% would
have received nothing. Email closes that hole for everyone, immediately, for free.

Once it's on, `alert_attempt` starts recording email delivery, clicks, and time-to-action
alongside push — which is the data that settles the fast-lane/slow-lane question with
evidence instead of assumption.
