#!/usr/bin/env bash
# Bring a BLANK Ubuntu box to a running SeatWatch. Run it ON the new machine.
#
#     scp -i ~/.ssh/<key> ops/provision.sh ubuntu@<NEW_IP>:~/
#     ssh -i ~/.ssh/<key> ubuntu@<NEW_IP> 'bash ~/provision.sh'
#
# WHY THIS EXISTS. ops/RECOVERY.md scenario 3 is a list of manual steps ending in "expect
# a few hours, not minutes", and it has never been rehearsed end to end. Hours of manual
# steps is exactly the wrong shape for the two moments it gets used: a dead server, or a
# migration nobody has done before. This makes it one command, so the untested half of the
# runbook becomes something that can actually be practised.
#
# WHAT IT DELIBERATELY DOES NOT DO
#   · It never writes /etc/seatwatch.env. Those are Google OAuth, VAPID, Twilio and
#     Stripe credentials; Claude does not copy or store them, and they come from the
#     operator's password manager. The script stops and says so if the file is missing.
#   · It does not touch DNS. Cutover stays a deliberate human act, so a half-built box
#     can never start answering for seatwatchapp.com.
#   · It does not copy the database. Data comes from the off-server backup, by hand, so
#     nobody accidentally starts a second live poller against a stale copy.
#
# ARCHITECTURE. SeatWatch imports nothing outside the standard library, so x86 -> ARM
# (Oracle's free Ampere tier) needs no wheels, no compilers and no changes. That was not
# free — it is the payoff of the stdlib-only rule.
set -euo pipefail

REPO="${SEATWATCH_REPO:-}"
APP_DIR="$HOME/seatwatch"
ENV_FILE="/etc/seatwatch.env"

say()  { printf "\n\033[36m>> %s\033[0m\n" "$*"; }
warn() { printf "\033[33m   %s\033[0m\n" "$*"; }
die()  { printf "\n\033[31m!! %s\033[0m\n" "$*" >&2; exit 1; }

say "1/7  system packages"
sudo apt-get update -qq
sudo apt-get install -y -qq python3 python3-venv git curl ca-certificates
python3 -c 'import sys; assert sys.version_info >= (3, 9), sys.version' \
  || die "python3 is older than 3.9"
echo "   python3 $(python3 -V 2>&1 | cut -d' ' -f2) on $(uname -m)"

say "2/7  application code"
if [ -d "$APP_DIR/.git" ]; then
  echo "   repo already present — pulling"
  git -C "$APP_DIR" pull --ff-only
elif [ -n "$REPO" ]; then
  git clone "$REPO" "$APP_DIR"
else
  warn "No repo URL. Set SEATWATCH_REPO=git@github.com:<you>/seatwatch.git and re-run,"
  warn "or copy the tree up manually. The code is entirely in git by design — this is"
  warn "why only DATA needs backing up."
  die  "cannot continue without the code"
fi

say "3/7  import check (before anything is enabled)"
cd "$APP_DIR"
python3 - <<'PYEOF'
import sys
sys.path.insert(0, ".")
import app, schools, guardian, confidence, ca_chain   # noqa: F401
print("   imports OK — %d schools in the registry" % len(schools.SCHOOLS))
PYEOF

say "4/7  secrets"
if [ ! -f "$ENV_FILE" ]; then
  warn "$ENV_FILE does not exist."
  warn ""
  warn "Restore it from the password manager copy (RECOVERY.md records this was taken"
  warn "on 2026-07-30). Without it the box cannot sign anyone in, send any email, or"
  warn "send any text — and the VAPID keys in particular cannot be re-derived: losing"
  warn "them silently breaks every existing push subscription."
  warn ""
  warn "   sudo nano $ENV_FILE && sudo chmod 600 $ENV_FILE"
  warn "then re-run this script."
  die  "stopping: refusing to start a service that cannot reach a single user"
fi
sudo chmod 600 "$ENV_FILE"
for key in GOOGLE_CLIENT_ID GOOGLE_CLIENT_SECRET SEATWATCH_SECRET; do
  sudo grep -q "^${key}=" "$ENV_FILE" || die "$ENV_FILE is missing $key"
done
echo "   $ENV_FILE present, 600, and carries the keys sign-in depends on"

say "5/7  database"
if [ -f "$APP_DIR/watches.db" ]; then
  n=$(python3 - <<'PYEOF'
import sqlite3
c = sqlite3.connect("file:watches.db?mode=ro", uri=True)
print(c.execute("SELECT COUNT(*) FROM watches").fetchone()[0])
PYEOF
)
  echo "   watches.db present — $n watch(es)"
else
  warn "No watches.db yet. From the Mac that holds the off-server backups:"
  warn "   scp -i ~/.ssh/<key> ~/seatwatch-backups/watches-<newest>.db \\"
  warn "       ubuntu@<THIS_IP>:~/seatwatch/watches.db"
  warn "Starting without it would create an EMPTY database and every existing watch"
  warn "would look deleted."
  die  "stopping: no data"
fi

say "6/7  service"
UNIT=/etc/systemd/system/seatwatch.service
if [ ! -f "$UNIT" ]; then
  sudo cp "$APP_DIR/ops/seatwatch.service.template" "$UNIT"
  warn "Installed the unit TEMPLATE. Fill SEATWATCH_ADMIN_TOPIC from the env copy:"
  warn "   sudo nano $UNIT"
  warn "An ntfy topic is a shared secret; a wrong one publishes operator alerts to a"
  warn "topic nobody is subscribed to, and fails silently."
  die  "stopping: finish the unit, then re-run"
fi
sudo systemctl daemon-reload
sudo systemctl enable --now seatwatch
sleep 5
sudo systemctl is-active --quiet seatwatch || {
  sudo journalctl -u seatwatch -n 30 --no-pager
  die "service did not come up — log above"
}
echo "   seatwatch is active"

say "7/7  proof of life"
sleep 20
sudo journalctl -u seatwatch -n 15 --no-pager | sed 's/^/   /'
cat <<'DONE'

  PROVISIONED — but NOT yet serving traffic.

  Still yours to do, deliberately:
    1. Caddy (or your TLS terminator) in front of the app.
    2. python3 readiness.py   on the Mac, against this checkout.
    3. Only then point Cloudflare at this IP.
    4. After cutover: python3 ops/triage.py  and confirm a cycle ran.

  Do NOT leave the old VM polling. Two live pollers on one database is what the poll
  lease exists to survive, but on two SEPARATE databases nothing coordinates them and
  students get duplicate alerts from the box you forgot to stop.
DONE
