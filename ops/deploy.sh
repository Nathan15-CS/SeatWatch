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
# Guarantees: refuses uncommitted changes IN THE FILES IT SHIPS (other lanes' work in
# progress is reported, not blocked) or a non-main branch; snapshots every target
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
case "$MODE" in
  schools) FILES=(schools.py) ;;
  app)     [ "$APPROVE" = "--app-approved" ] || {
             echo "REFUSED: app mode needs the CEO to type --app-approved"; exit 1; }
           # ca_chain.py and its bundle ship WITH app.py: app.py imports ca_chain at module
           # scope, so shipping one without the other leaves the service unable to start.
           # coverage.json ships too — it decides the public school count and which schools
           # may be watched, so a stale one silently mis-states both.
           FILES=(app.py ca_chain.py guardian.py confidence.py schools.py
                  ops/edu-intermediates.pem ops/coverage.json ops/blocked.json
                  ops/nightly-sweep.sh ops/sweep-schools.py) ;;
  *) echo "usage: ops/deploy.sh schools | app --app-approved"; exit 1 ;;
esac

# DIRTY-TREE CHECK, scoped to the files this deploy actually SHIPS.
#
# It used to refuse on ANY uncommitted file, which is stricter than it sounds and wrong in
# practice: several lanes work in this repo at once, and a deploy has been blocked by a
# half-written adapter, and then by another session's markdown journal — a file that can
# never reach the VM under any mode. Refusing on those does not protect anything; it just
# trains whoever is deploying to find a way around the guard, which is the opposite of
# what a guard is for.
#
# What actually matters is unchanged and still enforced: nothing half-finished may ship,
# and the sha in DEPLOYED.log must honestly describe the bytes that went out. So the
# refusal is now scoped to FILES, and everything else is reported rather than blocked —
# visible in the record, without stopping an unrelated release.
DIRTY_SHIPPED=""
for f in "${FILES[@]}"; do
  if [ -n "$(git status --porcelain -- "$f")" ]; then DIRTY_SHIPPED="$DIRTY_SHIPPED $f"; fi
done
if [ -n "$DIRTY_SHIPPED" ]; then
  echo "REFUSED: uncommitted changes in files this deploy would ship —$DIRTY_SHIPPED"
  git status --short -- $DIRTY_SHIPPED
  echo "  Commit them (so DEPLOYED.log's sha describes what actually shipped) or stash them."
  exit 1
fi
OTHER_DIRTY="$(git status --porcelain | grep -vE "^.. ($(IFS='|'; echo "${FILES[*]}"))$" || true)"
if [ -n "$OTHER_DIRTY" ]; then
  echo ">> note: uncommitted files NOT shipped by this deploy (proceeding):"
  echo "$OTHER_DIRTY" | sed 's/^/     /'
fi

# PRE-FLIGHT: the committed tree must actually IMPORT before anything ships.
#
# Byte-verification below proves the file ARRIVED intact. It cannot prove the app can
# START. On 2026-08-01 a commit reached HEAD carrying two classes with the same school id
# ("wpcc"): _guard_registry raised on import, so schools.py was a valid file that would
# have taken the poller down on restart, and every byte would have verified perfectly.
# Two lanes write schools.py concurrently, so a half-finished edit reaching a commit is a
# WHEN, not an IF. This is the cheapest possible place to catch it: local, one second,
# before a single byte moves.
echo ">> pre-flight: importing the committed tree"
git stash list >/dev/null 2>&1
python3 - <<'PREFLIGHT' || { echo "REFUSED: the tree does not import — deploying it would take production DOWN"; exit 1; }
import sys, os, tempfile
os.environ.setdefault("SEATWATCH_DB", os.path.join(tempfile.mkdtemp(), "preflight.db"))
sys.path.insert(0, os.getcwd())
import schools, guardian, confidence, app          # noqa: F401
n = len(schools.SCHOOLS)
assert n > 0, "registry is empty"
dups = [k for k in schools.SCHOOLS if not k]
assert not dups, f"blank school ids: {dups}"
print(f"   import OK — {n} schools, app/guardian/confidence load clean")
PREFLIGHT

SHA=$(git rev-parse --short HEAD)
echo ">> deploying ${FILES[*]} @ ${SHA} to ${VM}"
for f in "${FILES[@]}"; do
  "${SSH[@]}" "cp -f ~/seatwatch/$f ~/seatwatch/$f.prev 2>/dev/null || true"
  scp -i "$KEY" -o IdentitiesOnly=yes "$f" "$VM:~/seatwatch/$f"
done
# T0 comes from the VM's own clock, not this Mac's, so clock skew cannot widen the
# window. Every piece of evidence below must have been generated AFTER this instant.
T0=$("${SSH[@]}" "date +%s")
"${SSH[@]}" "sudo systemctl restart seatwatch"
# Must exceed the unit's RestartSec=5. Type=simple means systemd reports 'active' the
# moment exec succeeds — before the Python has had a chance to fail — so the old 3s
# check proved only that the interpreter launched, and a crash-loop still inside its
# first restart looked identical to a healthy service.
sleep 12
"${SSH[@]}" "systemctl is-active seatwatch"
# Bounded to THIS restart. `journalctl -n 60` spans restarts: a service that dies on
# startup still shows the PREVIOUS run's 'Poller started' in the tail, so the grep
# passes on evidence that predates the deploy. Not hypothetical — the 71b9dac deploy
# matched a line from the day before.
"${SSH[@]}" "sudo journalctl -u seatwatch --since '@$T0' --no-pager | grep -m1 'Poller started'" \
  || { echo "!! SMOKE FAILED (no 'Poller started' since restart) — run ops/rollback.sh NOW"; exit 1; }
# The check that proves the right BYTES are live. The log line proves something started;
# this proves it was this release. Cheap, and the only one of these that cannot be
# satisfied by leftover state from a previous run.
for f in "${FILES[@]}"; do
  L=$(shasum -a 256 "$f" | cut -d' ' -f1)
  R=$("${SSH[@]}" "sha256sum ~/seatwatch/$f | cut -d' ' -f1")
  [ "$L" = "$R" ] || { echo "!! SMOKE FAILED ($f hash mismatch — vm is not running this release)"
                       echo "   local $L"; echo "   vm    $R"
                       echo "   run ops/rollback.sh NOW"; exit 1; }
  echo "   verified $f $L"
done
HTTP=$(curl -s -o /dev/null -w '%{http_code}' --max-time 20 https://seatwatchapp.com) || HTTP=000
[ "$HTTP" = "200" ] || { echo "!! SMOKE FAILED (site HTTP $HTTP) — run ops/rollback.sh NOW"; exit 1; }
echo "$(date -u +%FT%TZ) sha=${SHA} mode=${MODE} files=[${FILES[*]}]" >> DEPLOYED.log
git add DEPLOYED.log && git commit -q -m "deploy record: ${SHA} (${MODE})" && git tag -f deployed
echo ">> DONE. sha=${SHA} recorded in DEPLOYED.log; 'deployed' tag moved."
echo ">> Next: run the verification checklist from the deploy packet."
