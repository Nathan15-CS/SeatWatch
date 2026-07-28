#!/bin/bash
# Pull SeatWatch's newest server backup to THIS machine, verify it, and rotate.
#
# Why: the server's daily backup lives on the same disk as the live database. If that VM
# is lost, deleted, or its disk fails, the backups die with it — that is a copy, not a
# backup. This makes a genuine off-server copy on separate hardware in a separate location.
#
# Verifies every pull (integrity_check + real row counts), so we never keep a corrupt file
# and believe we're covered. Also warns loudly if the SERVER's backup cron has gone stale.
#
# Restores are documented in ops/RECOVERY.md.
set -uo pipefail

KEY="$HOME/.ssh/seatwatch-vm.key"
HOST="ubuntu@141.148.27.134"
REMOTE_DIR="/home/ubuntu/seatwatch/backups"
# NOTE: outside the git repo on purpose — these contain real user emails/watches (PII).
LOCAL_DIR="$HOME/seatwatch-backups"
KEEP=30
STALE_HOURS=36

log() { echo "[$(date '+%Y-%m-%d %H:%M:%S')] $*"; }
mkdir -p "$LOCAL_DIR"

NEWEST=$(ssh -i "$KEY" -o ConnectTimeout=20 -o BatchMode=yes "$HOST" \
    "ls -1t $REMOTE_DIR/watches-*.db 2>/dev/null | head -1")
if [ -z "$NEWEST" ]; then
    log "FAIL: no backups found on the server ($REMOTE_DIR)"; exit 1
fi

# Is the server's own backup cron still running?
AGE_H=$(ssh -i "$KEY" -o BatchMode=yes "$HOST" \
    "echo \$(( ( \$(date +%s) - \$(stat -c %Y '$NEWEST') ) / 3600 ))")
if [ "$AGE_H" -gt "$STALE_HOURS" ]; then
    log "WARNING: server's newest backup is ${AGE_H}h old (>${STALE_HOURS}h) — the 3AM cron may have stopped"
fi

BASE=$(basename "$NEWEST")
DEST="$LOCAL_DIR/$BASE"
if [ -f "$DEST" ]; then
    log "already have $BASE — nothing new to pull (server backup age ${AGE_H}h)"
else
    log "pulling $BASE ..."
    scp -q -i "$KEY" "$HOST:$NEWEST" "$DEST.part" || { log "FAIL: scp failed"; rm -f "$DEST.part"; exit 1; }
    mv "$DEST.part" "$DEST"
fi

# Verify what we actually hold — a backup you haven't checked isn't a backup.
python3 - "$DEST" <<'PY' || { echo "FAIL: verification failed; removing bad copy"; rm -f "$DEST"; exit 1; }
import sqlite3, sys, os
p = sys.argv[1]
c = sqlite3.connect(p)
if c.execute("PRAGMA integrity_check").fetchone()[0] != "ok":
    print("  integrity_check FAILED"); sys.exit(1)
users = c.execute("SELECT COUNT(*) FROM users").fetchone()[0]
watches = c.execute("SELECT COUNT(*) FROM watches").fetchone()[0]
if users < 1:
    print("  refusing: 0 users in backup (suspect truncation)"); sys.exit(1)
print(f"  verified: integrity ok · {users} users · {watches} watches · {os.path.getsize(p)/1e6:.1f} MB")
PY

# Rotate: keep the newest $KEEP
ls -1t "$LOCAL_DIR"/watches-*.db 2>/dev/null | tail -n +$((KEEP + 1)) | xargs -r rm -f
COUNT=$(ls -1 "$LOCAL_DIR"/watches-*.db 2>/dev/null | wc -l | tr -d ' ')
log "OK — $COUNT off-server backup(s) held in $LOCAL_DIR"
