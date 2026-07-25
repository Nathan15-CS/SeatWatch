#!/usr/bin/env bash
# SeatWatch rollback — restore every <file>.prev snapshot taken by deploy.sh
# and restart. ALWAYS permitted, no approval needed (safety inversion).
# Env: SEATWATCH_VM=ubuntu@<vm-host>; SEATWATCH_KEY optional.
set -euo pipefail
KEY="${SEATWATCH_KEY:-$HOME/.ssh/seatwatch-vm.key}"
VM="${SEATWATCH_VM:?set SEATWATCH_VM=ubuntu@<vm-host> first}"
ssh -i "$KEY" -o IdentitiesOnly=yes "$VM" '
  cd ~/seatwatch
  restored=""
  for f in app.py guardian.py confidence.py schools.py; do
    if [ -f "$f.prev" ]; then cp -f "$f.prev" "$f"; restored="$restored $f"; fi
  done
  echo "restored:${restored:- nothing (no .prev snapshots)}"
  sudo systemctl restart seatwatch && sleep 3 && systemctl is-active seatwatch'
echo ">> Rolled back to the pre-deploy snapshots. Note the event in DEPLOYED.log by hand."
