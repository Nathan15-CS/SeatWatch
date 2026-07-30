#!/usr/bin/env python3
"""
SeatWatch Operator — the registered duties.

Each duty is one repeated operational question that has ALREADY been answered by
hand at least once, badly or late. Nothing speculative is registered here: a duty
that has never mattered is maintenance cost with no payoff.

Scope is set by what this machine is actually permitted to do (ORG/MANAGER/
PERMISSIONS.md): read the repo and git history, read local backup files, and fetch
public HTTP. No SSH, no production database, no deploys. A question that needs
production access is not a duty — it is a packet for the CEO, and saying so is more
useful than a check that quietly always fails.

Every duty is R0 (internal, reversible, read-only). Nothing here changes anything.
"""
import os
import re
import sqlite3
import sys
import time

from operator_engine import duty

BACKUP_DIR = os.environ.get("SW_BACKUP_DIR", os.path.expanduser("~/seatwatch-backups"))
SITE = "https://seatwatchapp.com"
# The files ops/deploy.sh ships. Local edits to these are what silently reach users.
DEPLOYED_FILES = ("app.py", "schools.py", "guardian.py", "confidence.py")


# --------------------------------------------------------------------------- 1
@duty("repo_hygiene", interval_s=1800, risk="R0",
      description="Uncommitted work in deploy-managed files, and freeze compliance.")
def repo_hygiene(ctx):
    """A dirty tree is the standing gate-defeat mechanism here: `scp` deploys ship
    whatever the working tree holds, so an uncommitted edit is an unreviewed change
    one command away from production. Three lanes have collided in app.py already."""
    rc, out, err = ctx.run(["git", "status", "--porcelain"])
    if rc != 0:
        return ctx.fail("git status failed", stderr=err[:400])

    modified, untracked = [], []
    for line in out.splitlines():
        if len(line) < 4:
            continue
        code, path = line[:2], line[3:].strip()
        (untracked if code.strip() == "??" else modified).append(path)

    dirty_deployed = sorted(p for p in modified if os.path.basename(p) in DEPLOYED_FILES)
    branch = ctx.run(["git", "rev-parse", "--abbrev-ref", "HEAD"])[1]

    for path in dirty_deployed:
        # app.py is under an explicit CEO freeze; the others are still deploy-managed,
        # so an uncommitted edit to any of them is a live divergence risk.
        frozen = os.path.basename(path) == "app.py"
        ctx.finding(
            "dirty:%s" % path, "red" if frozen else "yellow",
            "%s has uncommitted local changes%s — ops/deploy.sh refuses a dirty tree, "
            "and an ad-hoc scp would ship these unreviewed"
            % (path, " and is under the Phase-1 freeze" if frozen else ""),
            path=path, frozen=frozen)

    if branch != "main":
        ctx.finding("branch", "yellow",
                    "on branch %r, not main — deploy tooling refuses to ship from here"
                    % branch, branch=branch)

    detail = {"modified": modified, "untracked": len(untracked),
              "dirty_deployed": dirty_deployed, "branch": branch}
    if dirty_deployed or branch != "main":
        return ctx.attention("%d deploy-managed file(s) dirty on %s"
                             % (len(dirty_deployed), branch), **detail)
    return ctx.ok("clean tree on %s (%d untracked)" % (branch, len(untracked)), **detail)


# --------------------------------------------------------------------------- 2
@duty("deploy_truth", interval_s=3600, risk="R0",
      description="Does the record still answer 'what is running in production'?")
def deploy_truth(ctx):
    """This exact question has been answered by archaeology twice, because deploys
    bypassed ops/deploy.sh and left no record. The check is cheap; the failure mode
    is that shadow-reliability evidence becomes uninterpretable."""
    head = ctx.run(["git", "rev-parse", "--short", "HEAD"])[1]
    rc_tag, tag, _ = ctx.run(["git", "rev-parse", "--short", "deployed"])
    tag = tag if rc_tag == 0 else ""

    logged = ""
    try:
        lines = [l for l in ctx.read("DEPLOYED.log").splitlines() if l.strip()]
        if lines:
            m = re.search(r"sha=(\w+)", lines[-1])
            logged = m.group(1) if m else ""
    except OSError:
        ctx.finding("no_log", "red", "DEPLOYED.log is missing — there is no release record",
                    )
        return ctx.attention("DEPLOYED.log missing", head=head)

    consistent = None
    if tag and logged:
        # The tag and the logged sha are NOT expected to be equal. deploy.sh appends
        # the log line, COMMITS it, and only then moves the tag — so the tag is always
        # the deploy-record commit, one ahead of the sha it records. The real invariant
        # is ancestry: the shipped commit must be reachable from the tag.
        consistent = ctx.run(["git", "merge-base", "--is-ancestor", logged, tag])[0] == 0

    # Only commits touching DEPLOY-MANAGED files are undeployed product delta. Work on
    # tests, ops tooling, or org records is not pending a release, and counting it
    # would train the reader to ignore this finding.
    behind, behind_shas = None, []
    if tag:
        rc, out, _ = ctx.run(["git", "log", "--oneline", "%s..HEAD" % tag, "--"]
                             + list(DEPLOYED_FILES))
        if rc == 0:
            behind_shas = [l.split()[0] for l in out.splitlines() if l.strip()]
            behind = len(behind_shas)

    if not tag:
        ctx.finding("no_tag", "yellow",
                    "no `deployed` git tag — the last shipped commit is not marked")
    elif consistent is False:
        ctx.finding("tag_log_mismatch", "red",
                    "the last DEPLOYED.log sha (%s) is not an ancestor of the `deployed` "
                    "tag (%s) — the release record is internally inconsistent and neither "
                    "value can be trusted alone" % (logged, tag), tag=tag, logged=logged)
    if behind:
        sev = "red" if behind >= 10 else "yellow"
        ctx.finding("undeployed_delta", sev,
                    "%d commit(s) touching deploy-managed files since the last recorded "
                    "deploy (%s) — either unshipped work, or a deploy that bypassed "
                    "ops/deploy.sh" % (behind, tag),
                    behind=behind, shas=behind_shas, head=head, tag=tag)

    detail = {"head": head, "tag": tag, "logged": logged, "consistent": consistent,
              "commits_behind": behind, "behind_shas": behind_shas}
    if not tag or consistent is False or behind:
        return ctx.attention("record vs HEAD: tag=%s log=%s head=%s (+%s deploy-managed)"
                             % (tag or "none", logged or "none", head, behind), **detail)
    return ctx.ok("release record consistent; no undeployed changes to shipped files "
                  "(head %s)" % head, **detail)


# --------------------------------------------------------------------------- 3
@duty("backup_ring", interval_s=21600, risk="R0",
      description="Is the off-server backup ring actually firing, and what does it hold?")
def backup_ring(ctx):
    """A backup nobody has restored is a rumour, and a backup schedule nobody has
    verified is a hope. This reads only aggregate COUNTS out of the newest copy —
    never a row, never an address — and compares them to the previous run so that a
    collapse in the data is visible rather than merely present."""
    if not os.path.isdir(BACKUP_DIR):
        ctx.finding("missing_dir", "red",
                    "no off-server backup directory at %s — the only copy of every "
                    "account and watch is on one VM disk" % BACKUP_DIR, dir=BACKUP_DIR)
        return ctx.attention("backup directory absent", dir=BACKUP_DIR)

    files = sorted(f for f in os.listdir(BACKUP_DIR)
                   if f.startswith("watches-") and f.endswith(".db"))
    if not files:
        ctx.finding("empty_ring", "red", "backup directory exists but holds no backups",
                    dir=BACKUP_DIR)
        return ctx.attention("no backups held", dir=BACKUP_DIR)

    newest = os.path.join(BACKUP_DIR, files[-1])
    age_h = (time.time() - os.path.getmtime(newest)) / 3600.0
    if age_h > 48:
        ctx.finding("stale", "red",
                    "newest off-server backup is %.0fh old (>48h) — the pull is not "
                    "running on schedule" % age_h, age_h=round(age_h, 1), newest=files[-1])
    elif age_h > 30:
        ctx.finding("aging", "yellow",
                    "newest off-server backup is %.0fh old; the ring targets daily" % age_h,
                    age_h=round(age_h, 1))

    users = watches = None
    integrity = "unknown"
    try:
        c = sqlite3.connect("file:%s?mode=ro" % newest, uri=True, timeout=20)
        try:
            integrity = c.execute("PRAGMA integrity_check").fetchone()[0]
            users = c.execute("SELECT COUNT(*) FROM users").fetchone()[0]
            watches = c.execute("SELECT COUNT(*) FROM watches").fetchone()[0]
        finally:
            c.close()
    except sqlite3.Error as e:
        ctx.finding("unreadable", "red",
                    "newest backup cannot be opened (%s) — we are holding a file we "
                    "cannot restore from" % e, newest=files[-1])

    if integrity not in ("ok", "unknown"):
        ctx.finding("corrupt", "red", "backup failed integrity_check: %s" % integrity)

    # Drift against the previous run — the point of durable state.
    prev = ctx.last_detail()
    if users is not None and prev.get("users") is not None:
        du, dw = users - prev["users"], (watches or 0) - (prev.get("watches") or 0)
        if du or dw:
            # Not a defect — a fact the operator should not have to notice by luck.
            # A new account during the demand sprint is the metric the sprint turns on.
            ctx.finding("counts_moved", "info",
                        "account/watch counts moved since the last check: users %d -> %d, "
                        "watches %d -> %d" % (prev["users"], users, prev.get("watches") or 0,
                                              watches or 0),
                        prev_users=prev["users"], users=users,
                        prev_watches=prev.get("watches"), watches=watches)

    detail = {"held": len(files), "newest": files[-1], "age_h": round(age_h, 1),
              "integrity": integrity, "users": users, "watches": watches}
    if age_h > 30 or integrity not in ("ok",) or users is None:
        return ctx.attention("ring: %d held, newest %.0fh old, integrity %s"
                             % (len(files), age_h, integrity), **detail)
    return ctx.ok("ring healthy: %d held, newest %.0fh old, %s users / %s watches"
                  % (len(files), age_h, users, watches), **detail)


# --------------------------------------------------------------------------- 4
@duty("site_health", interval_s=900, risk="R0",
      description="Is the public site up, and does it serve the coverage we have locally?")
def site_health(ctx):
    """The landing page renders its school count from len(schools.SCHOOLS) at request
    time, so the number the site serves is a direct readout of which schools.py is
    running. Comparing it to the local registry is the cheapest honest deploy check
    available without production access — it is how the count divergence was caught."""
    status, body = ctx.http(SITE, timeout=25)
    if status != 200:
        ctx.finding("down", "red", "%s returned HTTP %s" % (SITE, status), status=status)
        return ctx.attention("site HTTP %s" % status, status=status)

    live = _page_school_count(body)
    if live is None:
        ctx.finding("no_count", "yellow",
                    "could not read the school count from the live page — the landing "
                    "markup changed, or the page is not the one we think it is")

    local = _local_school_count(ctx)
    if live is not None and local is not None and live != local:
        ctx.finding("count_divergence", "yellow",
                    "live site serves %d schools but local schools.py has %d — schools.py "
                    "is not deployed at this commit (or the site is stale)"
                    % (live, local), live=live, local=local)

    detail = {"status": status, "live_count": live, "local_count": local,
              "bytes": len(body)}
    if live is None or (local is not None and live != local):
        return ctx.attention("site 200; count live=%s local=%s" % (live, local), **detail)
    return ctx.ok("site 200, serving %d schools (matches local)" % live, **detail)


def _page_school_count(body):
    """Read the coverage number off the live page.

    Deliberately tries several shapes. The landing markup has been redesigned at
    least once, and a checker that silently stops finding its anchor reports "the
    page changed" forever — noise that gets ignored, which is worse than no check.
    Every pattern is anchored on the count's own label so it cannot match a price
    or a year."""
    for pat in (r'data-count="(\d{2,5})"',
                r'WATCHING\s+(\d{2,5})\s+UNIVERSITIES',
                r'(\d{2,5})\s+universities'):
        m = re.search(pat, body, re.I)
        if m:
            return int(m.group(1))
    return None


def _local_school_count(ctx):
    """Import the registry in a SUBPROCESS. schools.py's import-time guard raises on a
    duplicate id or name, and that failure must be reported as a finding — not crash
    the Operator that is supposed to be reporting it."""
    # sys.executable, not "python3": under launchd the PATH is minimal and may not be
    # the interpreter this process is running under. A scheduled run must not silently
    # import a different Python's schools.py than an interactive run does.
    rc, out, err = ctx.run(
        [sys.executable, "-c", "import schools; print(len(schools.SCHOOLS))"], timeout=90)
    if rc != 0:
        ctx.finding("registry_import", "red",
                    "schools.py fails to import — the duplicate-registry guard is "
                    "rejecting it, so the site cannot start from this commit",
                    stderr=err[-600:])
        return None
    return int(out.strip()) if out.strip().isdigit() else None


# --------------------------------------------------------------------------- 5
@duty("registry_guard", interval_s=3600, risk="R0",
      description="Does schools.py still import cleanly under its duplicate guard?")
def registry_guard(ctx):
    """`_guard_registry` fails the import on a duplicate school so a dup can never
    reach the live site. That protection only works if someone actually runs the
    import — it has been a manual step in the workflow, which means it gets skipped."""
    n = _local_school_count(ctx)
    if n is None:
        return ctx.attention("schools.py does not import")
    prev = ctx.last_detail().get("count")
    if prev and n < prev:
        ctx.finding("coverage_dropped", "yellow",
                    "school count fell from %d to %d — schools were removed; intended?"
                    % (prev, n), prev=prev, count=n)
    return ctx.ok("registry imports cleanly: %d schools" % n, count=n, prev=prev)


# --------------------------------------------------------------------------- 6
@duty("guardian_journal", interval_s=43200, risk="R0",
      description="Is the Guardian shadow-window journal still being written?")
def guardian_journal(ctx):
    """The shadow window carries a checkpoint obligation. Checkpoints stopped being
    written on 07-26 and nobody noticed for days, which is how a two-week evidence
    window is spent producing no evidence. Staleness is the whole signal."""
    rel = "ORG/records/guardian-phase-d-journal.md"
    try:
        text = ctx.read(rel)
    except OSError:
        return ctx.blocked("journal not found at %s" % rel)

    dates = sorted(set(re.findall(r"^#{2,3}\s+(\d{4}-\d{2}-\d{2})", text, re.M)))
    if not dates:
        ctx.finding("unparseable", "yellow", "no dated entries found in the journal")
        return ctx.attention("no dated entries", path=rel)

    newest = dates[-1]
    try:
        age_d = (time.time() - time.mktime(time.strptime(newest, "%Y-%m-%d"))) / 86400.0
    except ValueError:
        return ctx.fail("could not parse journal date %r" % newest)

    if age_d > 3:
        ctx.finding("stale", "yellow",
                    "newest journal entry is %s (%.0f days old) — the shadow window is "
                    "elapsing without recorded evidence, which is the same as not "
                    "running it" % (newest, age_d), newest=newest, age_days=round(age_d, 1))

    detail = {"newest": newest, "age_days": round(age_d, 1), "entries": len(dates)}
    if age_d > 3:
        return ctx.attention("journal stale: newest %s (%.0fd)" % (newest, age_d), **detail)
    return ctx.ok("journal current: newest %s" % newest, **detail)
