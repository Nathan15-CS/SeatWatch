#!/bin/sh
# check-vault.sh — prove the vault actually works, rather than assuming it does.
#
# Mounts the encrypted image (you will be asked for the password), confirms the SSH key
# inside it really logs into the server, confirms the env file is intact, then unmounts.
# A backup you have never restored is not a backup.
#
# Usage:  sh ops/check-vault.sh
set -u

ICLOUD="$HOME/Library/Mobile Documents/com~apple~CloudDocs"
DMG="$ICLOUD/seatwatch-vault.dmg"
MNT="/Volumes/SeatWatchVault"
VM="ubuntu@141.148.27.134"
FAIL=0

[ -f "$DMG" ] || { echo "  No vault found at $DMG — run: sh ops/make-vault.sh"; exit 1; }

SIZE=$(du -h "$DMG" | cut -f1 | tr -d ' ')
echo "  vault: $DMG ($SIZE)"
echo "  mounting (enter the vault password)..."
hdiutil attach "$DMG" -quiet || { echo "  could not mount — wrong password?"; exit 1; }
trap 'hdiutil detach "$MNT" -quiet 2>/dev/null' EXIT INT TERM
[ -d "$MNT" ] || { echo "  mounted but $MNT missing"; exit 1; }

# --- the SSH key must actually open the server ---
if [ -f "$MNT/seatwatch-vm.key" ]; then
  cp "$MNT/seatwatch-vm.key" /tmp/_vkey && chmod 600 /tmp/_vkey
  if ssh -i /tmp/_vkey -o IdentitiesOnly=yes -o StrictHostKeyChecking=accept-new \
         -o ConnectTimeout=15 -o BatchMode=yes "$VM" 'echo ok' >/dev/null 2>&1; then
    echo "  [OK] SSH key in the vault logs into the server"
  else
    echo "  [!!] SSH key in the vault DID NOT WORK"; FAIL=1
  fi
  rm -f /tmp/_vkey
else
  echo "  [!!] seatwatch-vm.key is MISSING from the vault"; FAIL=1
fi

# --- the env file must be present and complete (names only, never values) ---
if [ -f "$MNT/seatwatch.env" ]; then
  N=$(grep -cE '^[A-Z_]+=' "$MNT/seatwatch.env" | tr -d ' ')
  echo "  [OK] seatwatch.env present ($N settings)"
  for want in VAPID_PRIVATE_PEM VAPID_PUBLIC_KEY SEATWATCH_SECRET; do
    if grep -q "^$want=" "$MNT/seatwatch.env"; then
      echo "       - $want saved"
    else
      echo "       - $want MISSING"; FAIL=1
    fi
  done
else
  echo "  [!!] seatwatch.env is MISSING from the vault"; FAIL=1
fi

echo ""
if [ "$FAIL" = "0" ]; then
  echo "  VAULT VERIFIED — everything irreplaceable is backed up and proven to work."
else
  echo "  VAULT INCOMPLETE — see the [!!] lines above. Re-run: sh ops/make-vault.sh"
fi
exit "$FAIL"
