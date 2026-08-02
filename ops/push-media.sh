#!/usr/bin/env bash
# Push the ad media to the VM.
#
# NOTE THE FILENAMES. They were ad-web.mp4 / ad-poster.jpg and ad blockers refused them:
# a URL containing "/ad." matches standard advertising filters, so the browser rejected
# the media load BEFORE issuing a request. Do not name shipped assets ad*, promo*, banner*
# or sponsor*, however accurate the word is.
#
# SEPARATE from ops/deploy.sh on purpose. deploy.sh ships four .py files and restarts the
# service; these are static assets that change almost never and are far too large to sit
# in git — a 26 MB binary in git history is permanent and cannot be shrunk later. So they
# are pushed directly and gitignored, and this script is the record of how.
#
# No restart is needed: _send_media reads from disk per request, so a replaced file is
# live on the very next byte served.
#
#   SEATWATCH_VM=ubuntu@<host> ops/push-media.sh
set -euo pipefail
KEY="${SEATWATCH_KEY:-$HOME/.ssh/seatwatch-vm.key}"
VM="${SEATWATCH_VM:?set SEATWATCH_VM=ubuntu@<vm-host> first}"
cd "$(dirname "$0")/.."

FILES=(tour.mp4 tour-poster.jpg)
for f in "${FILES[@]}"; do
  [ -f "$f" ] || { echo "MISSING: $f — build it with marketing/webify.swift"; exit 1; }
done

echo ">> pushing ${FILES[*]} to ${VM}"
for f in "${FILES[@]}"; do
  scp -i "$KEY" -o IdentitiesOnly=yes "$f" "$VM:~/seatwatch/$f"
done

echo ">> verifying bytes arrived intact"
for f in "${FILES[@]}"; do
  L=$(shasum -a 256 "$f" | cut -d' ' -f1)
  R=$(ssh -i "$KEY" -o IdentitiesOnly=yes "$VM" "sha256sum ~/seatwatch/$f | cut -d' ' -f1")
  if [ "$L" = "$R" ]; then
    echo "   verified $f $L"
  else
    echo "   *** MISMATCH $f — local=$L remote=$R"; exit 1
  fi
done
echo ">> DONE. No restart needed; media is read from disk per request."
