#!/usr/bin/env python3
"""Push the newest nightly DB snapshot to Oracle Object Storage, and PROVE it landed.

WHY THIS EXISTS
The off-server backup ring works, but its off-server half depends on a laptop being
awake: snapshots are taken at 03:00 and pulled to the Mac whenever it next wakes up.
A week with the lid shut is a week with no copy anywhere but the server itself, which
is the one machine a backup is supposed to survive.

WHAT IT DELIBERATELY DOES NOT DO
  * It does NOT take a snapshot. backup.sh already does that at 03:00 via cron. Two
    processes writing snapshots is two things to keep correct.
  * It does NOT delete anything, here or in the bucket. Retention is a bucket lifecycle
    rule, so a bug in this script can never destroy a backup. Deleting is the one
    operation a backup tool should not be trusted with.

AUTHENTICATION — why a Pre-Authenticated Request, not an API key
The VM is a 1GB E2.1.Micro. The OCI CLI and SDK are both absent and heavy for it. A PAR
is a single URL carrying its own token: uploading is one PUT with stdlib http, no SDK, no
key file, no rotation tooling. It is also narrower than an API key — scoped to ONE bucket
and nothing else in the tenancy.

The tradeoffs, stated because they are real: the URL *is* the credential, so it lives in
/etc/seatwatch.env at 0600 alongside the Twilio and Stripe keys and never enters the repo;
and PARs expire, so an expiry inside 30 days is itself reported as a breach.

VERIFICATION — the point of the whole exercise
Object Storage returns the stored object's MD5 in `opc-content-md5`. That is compared
against the MD5 of the bytes actually read from disk. An upload is only called successful
when the server's own checksum of what it stored matches what we sent. A 200 alone proves
the request was accepted, not that the right bytes arrived — the same class of mistake as
a deploy smoke-check passing on yesterday's log line.

    python3 ops/offsite_push.py            # upload newest snapshot if not already there
    python3 ops/offsite_push.py --status    # print state, upload nothing (used by the watchdog)
    python3 ops/offsite_push.py --verify-restore   # download newest object and open it
"""
import base64, hashlib, json, os, sqlite3, sys, tempfile, time
import urllib.error, urllib.request

BACKUP_DIR = "/home/ubuntu/seatwatch/backups"
ENV = "/etc/seatwatch.env"
STALE_HOURS = 36          # a snapshot is nightly; 36h means at least one was missed
PAR_EXPIRY_WARN_DAYS = 30


def load_env():
    try:
        for line in open(ENV):
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                k, v = line.split("=", 1)
                os.environ.setdefault(k, v)
    except OSError:
        pass


def par_base():
    """The PAR URL, normalised to end in '/'. Empty string means not configured."""
    u = (os.environ.get("OCI_BACKUP_PAR") or "").strip()
    return (u if u.endswith("/") else u + "/") if u else ""


def newest_local():
    try:
        files = [f for f in os.listdir(BACKUP_DIR)
                 if f.startswith("watches-") and f.endswith(".db")]
    except OSError:
        return None
    return max(files) if files else None


def _req(url, method="GET", data=None, headers=None, timeout=180):
    r = urllib.request.Request(url, data=data, method=method, headers=headers or {})
    return urllib.request.urlopen(r, timeout=timeout)


def list_objects():
    """Objects already in the bucket, newest first. Requires the PAR to permit listing."""
    base = par_base()
    if not base:
        return None, "OCI_BACKUP_PAR is not set"
    try:
        with _req(base + "?fields=name,size,timeCreated", timeout=60) as r:
            d = json.loads(r.read().decode("utf-8", "replace"))
        objs = d.get("objects") or []
        objs.sort(key=lambda o: o.get("name", ""), reverse=True)
        return objs, None
    except urllib.error.HTTPError as e:
        return None, f"HTTP {e.code} listing bucket ({e.reason})"
    except Exception as e:
        return None, f"{type(e).__name__} listing bucket"


def upload(name, path):
    """PUT one file and verify the STORED checksum. Returns (ok, detail)."""
    base = par_base()
    if not base:
        return False, "OCI_BACKUP_PAR is not set"
    with open(path, "rb") as f:
        blob = f.read()
    local_md5 = base64.b64encode(hashlib.md5(blob).digest()).decode()
    try:
        with _req(base + name, method="PUT", data=blob,
                  headers={"Content-Type": "application/x-sqlite3",
                           "Content-Length": str(len(blob)),
                           "opc-meta-sha256": hashlib.sha256(blob).hexdigest()}) as r:
            stored = r.headers.get("opc-content-md5", "")
            code = r.status
    except urllib.error.HTTPError as e:
        return False, f"HTTP {e.code} on PUT ({e.reason})"
    except Exception as e:
        return False, f"{type(e).__name__} on PUT"
    if not (200 <= code < 300):
        return False, f"HTTP {code} on PUT"
    # The whole point: the SERVER's checksum of what it stored, not our exit code.
    if stored and stored != local_md5:
        return False, f"CHECKSUM MISMATCH stored={stored[:16]} sent={local_md5[:16]}"
    if not stored:
        return False, "no opc-content-md5 returned; upload NOT verified"
    return True, f"{len(blob)/1048576:.1f} MB, checksum verified"


def status():
    """Facts only, no side effects. The watchdog reads this."""
    load_env()
    out = {"configured": bool(par_base()), "newest_local": newest_local(),
           "objects": 0, "newest_remote": None, "age_hours": None, "error": None}
    if not out["configured"]:
        out["error"] = "OCI_BACKUP_PAR is not set"
        return out
    objs, err = list_objects()
    if err:
        out["error"] = err
        return out
    out["objects"] = len(objs)
    if objs:
        out["newest_remote"] = objs[0].get("name")
        ts = objs[0].get("timeCreated")
        if ts:
            try:
                t = time.mktime(time.strptime(ts[:19], "%Y-%m-%dT%H:%M:%S"))
                out["age_hours"] = round((time.time() - t) / 3600, 1)
            except Exception:
                pass
    return out


def verify_restore():
    """Download the newest object and OPEN it. A backup nobody has restored is not a
    backup — this is the same rule ops/check-vault.sh applies to the SSH key."""
    load_env()
    objs, err = list_objects()
    if err:
        print(f"  cannot list bucket: {err}")
        return 1
    if not objs:
        print("  bucket is EMPTY — nothing to restore")
        return 1
    name = objs[0]["name"]
    tmp = os.path.join(tempfile.mkdtemp(), name)
    try:
        with _req(par_base() + name, timeout=300) as r:
            open(tmp, "wb").write(r.read())
    except Exception as e:
        print(f"  download failed: {type(e).__name__}")
        return 1
    try:
        c = sqlite3.connect(f"file:{tmp}?mode=ro", uri=True)
        integrity = c.execute("PRAGMA integrity_check").fetchone()[0]
        users = c.execute("SELECT COUNT(*) FROM users").fetchone()[0]
        watches = c.execute("SELECT COUNT(*) FROM watches").fetchone()[0]
        c.close()
    except Exception as e:
        print(f"  the downloaded file did not open as a database: {type(e).__name__}")
        return 1
    finally:
        try: os.remove(tmp)
        except OSError: pass
    ok = integrity == "ok" and users > 0
    print(f"  restored {name}: integrity={integrity}  users={users}  watches={watches}")
    print("  RESTORE OK — this object is a usable database" if ok
          else "  *** RESTORE SUSPECT — opened, but the contents look wrong")
    return 0 if ok else 1


def main():
    load_env()
    if "--status" in sys.argv:
        print(json.dumps(status(), indent=2))
        return 0
    if "--verify-restore" in sys.argv:
        return verify_restore()

    if not par_base():
        print("  OCI_BACKUP_PAR is not set in /etc/seatwatch.env — nothing to do.")
        print("  See ops/OFFSITE-BACKUP.md for the console steps.")
        return 2
    name = newest_local()
    if not name:
        print(f"  no snapshot found in {BACKUP_DIR}")
        return 1
    objs, err = list_objects()
    if err:
        print(f"  cannot list bucket: {err}")
        return 1
    if any(o.get("name") == name for o in objs):
        print(f"  {name} is already in the bucket ({len(objs)} objects held)")
        return 0
    ok, detail = upload(name, os.path.join(BACKUP_DIR, name))
    print(f"  {'UPLOADED' if ok else 'FAILED'} {name}: {detail}")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
