#!/usr/bin/env bash
# Re-measure every school nightly and publish the result — with a sanity guard.
#
# The homepage count and the school picker both read ops/coverage.json. Nothing was
# refreshing it, so the number could only ever change when someone ran a sweep by hand.
# That matters right now: 37 schools are working but unproven purely because it is early
# August and nothing is full yet. They prove themselves the moment a section fills — but
# only if something looks again. Without this, the count stays frozen while reality moves.
#
# THE GUARD IS THE POINT. A sweep is 926 requests to other people's servers; a bad night
# here (our network, a DNS blip, an upstream provider having a bad hour) would mark
# hundreds of healthy schools EMPTY, and publishing that would hide most of the site and
# drop the count off a cliff. So the new file is written to a temp path, checked, and only
# then promoted. If it looks wrong we keep yesterday's numbers and page the operator: a
# stale-but-true count is strictly better than a fresh lie.
#
#   crontab:  30 4 * * *  /home/ubuntu/seatwatch/ops/nightly-sweep.sh
set -uo pipefail
cd /home/ubuntu/seatwatch || exit 1

LIVE=ops/coverage.json
TMP=/tmp/coverage-new.json
LOG=/tmp/nightly-sweep.log
ESC=ORG/MANAGER/ESCALATIONS.md
exec >>"$LOG" 2>&1
echo "=== $(date -u +%FT%TZ) nightly sweep starting ==="

python3 ops/sweep-schools.py --retries 2 --out "$TMP"
RC=$?
[ -s "$TMP" ] || { echo "sweep produced no file (rc=$RC) — keeping existing coverage"; exit 1; }

# Promote only if the new measurement is credible against the one we are already serving.
python3 - "$LIVE" "$TMP" <<'PY'
import json, sys, shutil
live_p, new_p = sys.argv[1], sys.argv[2]
new = json.load(open(new_p))
try:
    live = json.load(open(live_p))
except Exception:
    live = {}

def proven(d): return sum(1 for v in d.values() if v.get("verdict") == "OK")

n_new, n_live = proven(new), proven(live)
print("  proven: live=%d new=%d  (registry rows: live=%d new=%d)"
      % (n_live, n_new, len(live), len(new)))

# Two ways a sweep can be wrong in a way that would hurt: it covered far fewer schools
# than the registry, or proven collapsed. A rise is always fine — schools recovering is
# the thing this is for. Only a sharp FALL is treated as suspect.
if len(new) < len(live) * 0.95:
    print("  REFUSED: new file covers %d rows vs %d live — incomplete sweep" % (len(new), len(live)))
    sys.exit(2)
if n_live and n_new < n_live * 0.90:
    print("  REFUSED: proven fell %d -> %d (>10%%). Real breakage or a bad network night;"
          " either way a human should look before this reaches the site." % (n_live, n_new))
    sys.exit(3)

shutil.copyfile(new_p, live_p)
print("  PROMOTED: coverage.json now reports %d proven" % n_new)
sys.exit(0)
PY
CHECK=$?

if [ $CHECK -eq 0 ]; then
  # The app re-reads coverage.json when its mtime changes, so the live count follows
  # within a cycle. No restart, no deploy.
  echo "  published; site count follows on the next request"
else
  {
    echo
    echo "## $(date -u +%F) — nightly sweep REFUSED to publish (exit $CHECK)"
    echo
    echo "The sweep ran but its result failed the sanity guard, so ops/coverage.json was"
    echo "left as it was and the site is serving yesterday's numbers. That is the intended"
    echo "behaviour — a stale-but-true count beats a fresh lie — but it means the guard"
    echo "fired and something should be looked at. Detail in /tmp/nightly-sweep.log."
  } >> "$ESC"
  echo "  refused; escalation appended"
fi
echo "=== $(date -u +%FT%TZ) done ==="
