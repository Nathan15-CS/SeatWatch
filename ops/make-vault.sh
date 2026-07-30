#!/bin/sh
# make-vault.sh — put the two irreplaceable secrets somewhere that survives losing this Mac.
#
# Creates an AES-256 encrypted disk image in iCloud Drive containing:
#   * ~/.ssh/seatwatch-vm.key   — the ONLY way into the server. Oracle cannot reissue it.
#   * /etc/seatwatch.env        — includes the VAPID keys, which cannot be regenerated
#                                 without silently breaking every existing push subscriber.
#
# Everything else in that env file (Stripe, Twilio, Google, SMTP) can be re-issued from the
# provider's dashboard in a few clicks. These two cannot, which is why they get a vault.
#
# No secret value is ever printed. The env file is piped straight from the server into the
# mounted image; it never appears on screen or in shell history.
#
# Usage:  sh ops/make-vault.sh
set -u

ICLOUD="$HOME/Library/Mobile Documents/com~apple~CloudDocs"
DMG="$ICLOUD/seatwatch-vault.dmg"
VOL="SeatWatchVault"
MNT="/Volumes/$VOL"
KEY="$HOME/.ssh/seatwatch-vm.key"
VM="ubuntu@141.148.27.134"

[ -d "$ICLOUD" ] || { echo "  iCloud Drive not found at $ICLOUD"; exit 1; }
[ -f "$KEY" ]    || { echo "  SSH key not found at $KEY"; exit 1; }
if [ -e "$DMG" ]; then
  echo "  A vault already exists: $DMG"
  echo "  Delete or rename it first if you want to make a fresh one."
  exit 1
fi

cat <<'EOF'

  This creates an encrypted vault in your iCloud Drive.

  You will be asked for a password TWICE. Choose something you will not forget,
  and write it down somewhere physical. If you lose this password the vault is
  unrecoverable -- that is the whole point of encrypting it.

EOF
printf "  Press Return to continue, or Ctrl-C to stop. "
read _ignored

echo "  creating encrypted image..."
hdiutil create -encryption AES-256 -size 20m -volname "$VOL" -fs APFS \
        -type UDIF -quiet "$DMG" || { echo "  could not create the image"; exit 1; }

echo "  mounting..."
hdiutil attach "$DMG" -quiet || { echo "  could not mount (wrong password?)"; exit 1; }
[ -d "$MNT" ] || { echo "  mounted, but $MNT is missing"; exit 1; }

echo "  copying the SSH key..."
cp "$KEY" "$MNT/seatwatch-vm.key" || { hdiutil detach "$MNT" -quiet; exit 1; }
chmod 600 "$MNT/seatwatch-vm.key"

echo "  pulling the server secrets (values are never displayed)..."
if ssh -i "$KEY" -o IdentitiesOnly=yes -o ConnectTimeout=15 -o BatchMode=yes \
       "$VM" 'sudo cat /etc/seatwatch.env' > "$MNT/seatwatch.env" 2>/dev/null \
   && [ -s "$MNT/seatwatch.env" ]; then
  chmod 600 "$MNT/seatwatch.env"
  ENVN=$(grep -cE '^[A-Z_]+=' "$MNT/seatwatch.env" | tr -d ' ')
  echo "  saved seatwatch.env ($ENVN settings)"
else
  rm -f "$MNT/seatwatch.env"
  ENVN=0
  echo "  WARNING: could not pull /etc/seatwatch.env. The SSH key is saved; re-run later."
fi

cat > "$MNT/README.txt" <<EOF
SeatWatch recovery vault
========================

seatwatch-vm.key   The private key for the server ($VM).
                   Oracle cannot reissue this. Without it you cannot deploy,
                   restart, or fix anything on the machine running SeatWatch.

                   To use it on a new Mac:
                       mkdir -p ~/.ssh
                       cp seatwatch-vm.key ~/.ssh/
                       chmod 600 ~/.ssh/seatwatch-vm.key
                       ssh -i ~/.ssh/seatwatch-vm.key $VM

                   The chmod is required. SSH refuses a key other accounts can read.

seatwatch.env      The server's environment file, restored to /etc/seatwatch.env.

                   The VAPID_* values are the ones that matter most: they cannot be
                   regenerated. Replacing them silently stops push notifications for
                   everyone already subscribed, with no error and no warning to them.

                   Everything else in it (Stripe, Twilio, Google, SMTP) can be
                   re-issued from the provider's own dashboard if lost.

Keep this vault in iCloud Drive so it survives losing the Mac. The password is not
stored anywhere -- if you forget it, this vault is gone.
EOF

echo "  unmounting..."
hdiutil detach "$MNT" -quiet

echo ""
echo "  DONE. Vault created:"
echo "    $DMG"
echo ""
echo "  Contents: seatwatch-vm.key, $( [ "$ENVN" -gt 0 ] && echo "seatwatch.env, " )README.txt"
echo "  It will sync to iCloud automatically. To open it later, double-click the file"
echo "  and enter your password."
echo ""
echo "  Verify it right now with:  sh ops/check-vault.sh"
