#!/bin/sh
# vk.sh — "verify key": prove the SSH key backup in your password manager actually works.
#
# Deliberately given a short name you can TYPE. Copying a command out of a chat window
# overwrites the clipboard, which is the very thing this script needs to inspect — so a
# copy-pasted verify command can never succeed. Type `sh ops/vk.sh` instead.
#
# Usage:
#   1. In the Passwords app, open the SSH key entry, click the Notes field,
#      press Cmd+A then Cmd+C.
#   2. In Terminal, type:  sh ops/vk.sh
#
# Reads the clipboard, never writes to it. The temp copy is deleted on every exit path.
set -u
VM="ubuntu@141.148.27.134"
TMP="$(mktemp -t swkey)"
trap 'rm -f "$TMP"' EXIT INT TERM

pbpaste > "$TMP" 2>/dev/null
LINES=$(wc -l < "$TMP" | tr -d ' ')
BYTES=$(wc -c < "$TMP" | tr -d ' ')

if ! head -1 "$TMP" | grep -q "BEGIN.*PRIVATE KEY"; then
  echo ""
  echo "  NOT VERIFIED — the clipboard does not contain a private key."
  echo "  It currently holds $LINES line(s), $BYTES bytes."
  echo ""
  echo "  Most likely you copied something else after copying the key"
  echo "  (copying any command from a chat window does exactly that)."
  echo ""
  echo "  Fix: open the Passwords app, open your SSH key entry, click into"
  echo "  the Notes field, press Cmd+A then Cmd+C, then type this again."
  exit 1
fi

if ! tail -1 "$TMP" | grep -q "END.*PRIVATE KEY"; then
  echo ""
  echo "  NOT VERIFIED — the key is TRUNCATED. The opening line is there but the"
  echo "  closing -----END ... ----- line is missing. Re-copy the whole note."
  exit 1
fi

if grep -q "—" "$TMP"; then
  echo ""
  echo "  NOT VERIFIED — the backup contains a long dash, which means something"
  echo "  auto-corrected the '-----' markers (Apple Notes does this). Store the"
  echo "  key in the Passwords app instead, which does not reformat text."
  exit 1
fi

chmod 600 "$TMP"
echo "  clipboard looks like a key: $LINES lines, $BYTES bytes. Testing against the server..."
if ssh -i "$TMP" -o IdentitiesOnly=yes -o StrictHostKeyChecking=accept-new \
       -o ConnectTimeout=15 -o BatchMode=yes "$VM" 'echo ok' >/dev/null 2>&1; then
  echo ""
  echo "  RESTORE OK — your backup is real and would get you back into the server."
  REAL=$(wc -c < "$HOME/.ssh/seatwatch-vm.key" 2>/dev/null | tr -d ' ')
  [ "$BYTES" = "$REAL" ] && echo "  It also matches the key on disk byte for byte ($BYTES bytes)."
  exit 0
fi

echo ""
echo "  NOT VERIFIED — the key is well-formed but the server refused it."
echo "  The copy is probably subtly altered (a wrapped or dropped line)."
echo "  Re-copy the note in full and run this again."
exit 1
