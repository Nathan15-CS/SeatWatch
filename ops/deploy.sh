#!/usr/bin/env bash
# SeatWatch deploy — CEO-run only (the SSH key never leaves the owner's machine).
#
#   ./ops/deploy.sh schools                  ships schools.py ONLY
#   ./ops/deploy.sh app --app-approved       ships app.py guardian.py confidence.py schools.py
#
# Required env (never committed anywhere):
#   SEATWATCH_VM=ubuntu@<vm-host>            the origin host
#   SEATWATCH_KEY=<path>                     optional; default ~/.ssh/seatwatch-vm.key
#
# Guarantees: refuses a dirty tree or a non-main branch; snapshots every target
# to <file>.prev on the VM before overwrite (rollback.sh restores them);
# restarts the service; smoke-checks process + poller + public site; appends
# the release record to DEPLOYED.log and moves the `deployed` git tag.
set -euo pipefail
MODE="${1:-}"; APPROVE="${2:-}"
KEY="${SEATWATCH_KEY:-$HOME/.ssh/seatwatch-vm.key}"
VM="${SEATWATCH_VM:?set SEATWATCH_VM=ubuntu@<vm-host> first (value is never committed)}"
SSH=(ssh -i "$KEY" -o IdentitiesOnly=yes "$VM")
cd "$(dirname "$0")/.."

[ "$(git branch --show-current)" = "main" ] || { echo "REFUSED: not on main"; exit 1; }
[ -z "$(git status --porcelain)" ] || { echo "REFUSED: dirty tree —"; git status --short; exit 1; }
case "$MODE" in
  schools) FILES=(schools.py) ;;
  app)     [ "$APPROVE" = "--app-approved" ] || {
             echo "REFUSED: app mode needs the CEO to type --app-approved"; exit 1; }
           FILES=(app.py guardian.py confidence.py schools.py) ;;
  *) echo "usage: ops/deploy.sh schools | app --app-approved"; exit 1 ;;
esac

SHA=$(git rev-parse --short HEAD)
echo ">> deploying ${FILES[*]} @ ${SHA} to ${VM}"
for f in "${FILES[@]}"; do
  "${SSH[@]}" "cp -f ~/seatwatch/$f ~/seatwatch/$f.prev 2>/dev/null || true"
  scp -i "$KEY" -o IdentitiesOnly=yes "$f" "$VM:~/seatwatch/$f"
done
"${SSH[@]}" "sudo systemctl restart seatwatch && sleep 3 && systemctl is-active seatwatch"
"${SSH[@]}" "sudo journalctl -u seatwatch -n 60 --no-pager | grep -m1 'Poller started'" \
  || { echo "!! SMOKE FAILED (no 'Poller started') — run ops/rollback.sh NOW"; exit 1; }
HTTP=$(curl -s -o /dev/null -w '%{http_code}' --max-time 20 https://seatwatchapp.com) || HTTP=000
[ "$HTTP" = "200" ] || { echo "!! SMOKE FAILED (site HTTP $HTTP) — run ops/rollback.sh NOW"; exit 1; }
echo "$(date -u +%FT%TZ) sha=${SHA} mode=${MODE} files=[${FILES[*]}]" >> DEPLOYED.log
git add DEPLOYED.log && git commit -q -m "deploy record: ${SHA} (${MODE})" && git tag -f deployed
echo ">> DONE. sha=${SHA} recorded in DEPLOYED.log; 'deployed' tag moved."
echo ">> Next: run the verification checklist from the deploy packet."
