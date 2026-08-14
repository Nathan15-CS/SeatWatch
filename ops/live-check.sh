#!/usr/bin/env bash
# Run the student-view check against LIVE production data, right now.
#
# WHY: the nightly backup is taken at 03:00, so student-view.py is blind to everything
# since. On 2026-08-14 that meant it could not see a fix deployed at 12:16, and earlier the
# same day it gave a clean verdict on data ending 16 hours before the defect Nathan had just
# lived through. A check you can only run against yesterday is a check you cannot trust
# today.
#
# SAFE BY CONSTRUCTION:
#   * the snapshot is taken with sqlite3's own backup API, which is consistent against a
#     database being written to — a plain cp of a live SQLite file can copy a torn page
#   * everything server-side is read-only; nothing is written to watches.db
#   * the copy lands in /tmp on this Mac and is deleted afterwards. It contains real user
#     emails and phone numbers, so it does not go in the repo and does not linger.
#
# USAGE:  sh ops/live-check.sh [--hours 24] [--keep]
set -uo pipefail

KEY="$HOME/.ssh/seatwatch-vm.key"
HOST="ubuntu@141.148.27.134"
HERE="$(cd "$(dirname "$0")" && pwd)"
TMP="/tmp/seatwatch-live-$$.db"
HOURS="24"
KEEP=0
while [ $# -gt 0 ]; do
  case "$1" in
    --hours) HOURS="$2"; shift 2 ;;
    --keep)  KEEP=1; shift ;;
    *) echo "usage: sh ops/live-check.sh [--hours N] [--keep]"; exit 1 ;;
  esac
done

echo "taking a consistent snapshot on the server..."
ssh -i "$KEY" -o IdentitiesOnly=yes "$HOST" 'python3 -' <<'PY' || { echo "!! snapshot failed"; exit 1; }
import sqlite3, os
src = sqlite3.connect("file:/home/ubuntu/seatwatch/watches.db?mode=ro", uri=True)
out = "/tmp/sw-live-snapshot.db"
if os.path.exists(out):
    os.remove(out)
dst = sqlite3.connect(out)
src.backup(dst)          # consistent even while the poller is writing
dst.close(); src.close()
os.chmod(out, 0o600)
print("  snapshot %.1f MB" % (os.path.getsize(out) / 1e6))
PY

echo "copying it here..."
scp -q -i "$KEY" -o IdentitiesOnly=yes "$HOST:/tmp/sw-live-snapshot.db" "$TMP" \
  || { echo "!! copy failed"; exit 1; }
ssh -i "$KEY" -o IdentitiesOnly=yes "$HOST" 'rm -f /tmp/sw-live-snapshot.db'

echo
python3 "$HERE/student-view.py" --db "$TMP" --hours "$HOURS"
rc=$?

if [ "$KEEP" = "1" ]; then
  echo "kept: $TMP  (contains real user data — delete it when done)"
else
  rm -f "$TMP"
fi
exit $rc
