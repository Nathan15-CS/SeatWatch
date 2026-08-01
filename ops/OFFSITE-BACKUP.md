# Offsite backup — Oracle console steps

**Who does what:** you do the console steps (they need your Oracle login). I do the wiring
and the verification. Nothing here costs money — see *Cost* at the bottom.

**What this closes.** The nightly snapshot already exists on the server, and a copy is
pulled to your Mac. But the Mac copy only happens when the laptop is awake — a week with
the lid shut is a week where the only copy lives on the one machine a backup is meant to
survive. This pushes it straight from the server, every night, whether anything else is on.

---

## 1. Confirm the account type first

**Oracle Cloud console → top-right profile menu → Tenancy**

Look for **Always Free** or **Pay As You Go**.

- **Always Free** — everything below is free forever. Continue.
- **Pay As You Go** — object storage is ~$0.0255/GB-month, so ~1.1 GB is about **3 cents a
  month**. Still trivial, but it is not zero. Tell me which you have before continuing, and
  set the budget alert in step 5 either way.

## 2. Create the bucket — **PRIVATE**

**Menu → Storage → Buckets → Create Bucket**

| Field | Value |
|---|---|
| Bucket Name | `seatwatch-backups` |
| Default Storage Tier | **Standard** |
| Visibility | **Private** — leave the "public access" box **unticked** |
| Encryption | Oracle-managed keys (default) |

**Visibility is the one that matters.** The database contains real email addresses, push
subscriptions and SMS consent records — your family's, and every future student's. A public
bucket is a personal-data breach, not a misconfiguration. My script refuses to run until it
has confirmed the bucket rejects unauthenticated reads, so if you get this wrong it will
tell you rather than quietly working.

## 3. Set the retention rule

**Open the bucket → Lifecycle Policy Rules → Create Rule**

| Field | Value |
|---|---|
| Name | `keep-14-days` |
| Lifecycle action | **Delete** |
| Number of days | `14` |
| Target | Objects |

Retention is a bucket rule on purpose. My script never deletes anything — a bug in code I
wrote should not be able to destroy your backups. Oracle enforces the ceiling instead.

## 4. Create the upload credential

**Open the bucket → Pre-Authenticated Requests → Create Pre-Authenticated Request**

| Field | Value |
|---|---|
| Name | `seatwatch-server-push` |
| PAR Type | **Bucket** |
| Access Type | **Permit object reads and writes** |
| Enable Object Listing | **ticked** |
| Expiration | one year from today |

Read + list are needed so the backup can be *verified* and *restored*, not just written. A
backup you cannot read is not a backup.

**Oracle shows the URL exactly once.** Copy it immediately. Treat it like the Twilio and
Stripe keys: it goes in `/etc/seatwatch.env` and nowhere else — not in chat, not in a note,
not in the repo. Anyone holding it can write to that bucket.

Then, on the server:

```bash
ssh -i ~/.ssh/seatwatch-vm.key ubuntu@141.148.27.134
sudo sed -i '/^OCI_BACKUP_PAR=/d' /etc/seatwatch.env
printf 'OCI_BACKUP_PAR=%s\n' 'PASTE_THE_URL_HERE' | sudo tee -a /etc/seatwatch.env >/dev/null
sudo chmod 600 /etc/seatwatch.env
```

## 5. Set a budget alert — do this even on Always Free

**Menu → Billing & Cost Management → Budgets → Create Budget**

| Field | Value |
|---|---|
| Scope | your root compartment |
| Amount | `1` (USD) |
| Alert Rule | **100%** of budget, email you |

At the expected size this should never fire. That is the point: if it ever does, something
is misconfigured and you find out by email instead of by invoice.

## 6. Tell me, and I will do the rest

Once the PAR is in the env file, I will:

- upload tonight's snapshot and verify Oracle's own checksum of the stored object
- **fetch the object URL with no credentials and confirm it is refused** — asserted in the
  script, not eyeballed once
- download an object, open it as a database, and check the school and user counts, so the
  first restore happens now rather than during an emergency
- add the nightly cron and a staleness alarm (newest object older than 36h emails you, even
  if every individual upload claimed success)

---

## Cost

| | |
|---|---|
| Snapshot size | ~73 MB at steady state |
| Retention | 14 days |
| **Total stored** | **~1.0 GB** |
| Always Free allowance | 20 GB |
| Requests | ~1/day against a very large allowance |

Roughly 5% of the free allowance. The snapshot grows with the evidence log, which self-prunes
at 7 days, so it plateaus rather than climbing.

**If anything here would cost money, stop and tell me** rather than proceeding.
