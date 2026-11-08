# Backups, exports and recovery

LINDA keeps two kinds of data: the **database** (PostgreSQL) and
**uploaded files** (the `backend/storage` folder: documents, photos, logos).
A backup must copy both.

## 1. Take a backup

From the `backend` folder with the virtual environment active:

```bash
python -m app.run_backup
```

This creates `backend/backups/funeralos-YYYYMMDD-HHMMSS-xxxxxxxx/` containing

- `database.dump` – a full PostgreSQL dump
- `files.tar.gz` – everything in `storage/`

It checks that the dump can be read back, records the result in
`backend/backups/status.json` (shown in **Settings → Data export & backups**),
and removes the oldest backups beyond the newest 14. The backup root and each dated backup folder are restricted to owner-only permissions (0700).

Settings (in `backend/.env`, all optional):

| Setting | Default | Meaning |
| --- | --- | --- |
| `BACKUP_DIR` | `backups` | Where backups are written |
| `BACKUP_KEEP` | `14` | How many recent backups to keep |

The job needs the PostgreSQL client tools (`pg_dump`, `pg_restore`). On a Mac:
`brew install libpq` and add it to your PATH, or install Postgres.app.

## 2. Run it every night

**Easiest:** run the built-in scheduler (`python -m app.run_scheduler`), which
runs the backup nightly at 02:00 along with the other recurring jobs. See
`docs/PRODUCTION_READINESS.md`. The manual options below still work if you
prefer your own scheduler.

**Mac (launchd).** Save as `~/Library/LaunchAgents/com.funeralos.backup.plist`
(change the two paths), then run
`launchctl load ~/Library/LaunchAgents/com.funeralos.backup.plist`:

```xml
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN"
 "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
  <key>Label</key><string>com.funeralos.backup</string>
  <key>WorkingDirectory</key><string>/Users/YOU/funeral-platform/backend</string>
  <key>ProgramArguments</key>
  <array>
    <string>/Users/YOU/funeral-platform/backend/venv/bin/python</string>
    <string>-m</string><string>app.run_backup</string>
  </array>
  <key>StartCalendarInterval</key>
  <dict><key>Hour</key><integer>2</integer><key>Minute</key><integer>0</integer></dict>
  <key>StandardErrorPath</key><string>/tmp/funeralos-backup.log</string>
</dict>
</plist>
```

If the Mac is asleep at 02:00 the job runs when it wakes. **Linux server (cron):**

```
0 2 * * * cd /srv/funeralos/backend && venv/bin/python -m app.run_backup
```

The Settings screen turns amber if the last good backup is older than 26 hours
or the last run failed.

## 3. Encrypted off-site backups (production)

The production scheduler can make an encrypted remote copy of each newly
completed local backup using Restic and Backblaze B2's S3-compatible API.
Local backup creation remains independent: if B2 is unavailable, the local
backup stays successful and the separate `backups/offsite_status.json` records
the remote failure.

### Storage and encryption

1. Create a **private** Backblaze B2 bucket dedicated to LINDA.
2. Create a standard application key restricted to that bucket. Do not use the
   account master key. The key needs object listing, reading, writing and
   deleting for uploads, verification, and Restic retention. Enable
   **Allow List All Bucket Names** if the S3 client checks bucket listing.
3. Use the bucket's S3 endpoint and region shown by Backblaze. The repository
   URL format is
   `s3:https://s3.<region>.backblazeb2.com/<bucket-name>/linda/production`.
4. Generate a strong, unique Restic repository password. Store it in a password
   manager and in the private scheduler environment file. Losing this password
   makes encrypted remote backups unrecoverable.
5. Copy `deploy/offsite.env.example` to `deploy/offsite.env` on the VPS,
   enter the bucket endpoint, region, key ID, application key and Restic
   password, then set `OFFSITE_BACKUP_ENABLED=true`. Never commit or paste
   these credentials into chat. Restrict the file with `chmod 600`.
6. The scheduler alone receives `offsite.env`; the API, database and web
   containers do not receive the B2 or Restic secrets.

The backend image contains the pinned, checksum-verified Restic binary. The
first-time repository initialization is a deliberate manual step; the backup
job will not silently initialize a misspelled or incorrect repository.

After configuring the environment file, initialize the repository from the
scheduler container with:

```bash
sudo docker compose -f deploy/docker-compose.yml exec scheduler \
  restic init
```

This is only run once for a new repository. Keep the Restic password safely
outside the VPS as well.

### Upload and retention policy

Each nightly run uploads only the new dated local backup folder. Restic encrypts
the data before it leaves the VPS and deduplicates unchanged content. After the
new snapshot is verified in the repository, the scheduler applies this policy:

- Keep 30 daily recovery points.
- Keep 12 monthly recovery points.
- Prune data no longer referenced by retained snapshots.

The local backup retention remains 14 folders and is independent of remote
retention. Remote upload status is written separately to
`/app/backups/offsite_status.json`. A remote failure does not change
`status.json` or the last successful local backup timestamp.

### Verify remote backups

After the first upload, inspect the remote snapshots:

```bash
sudo docker compose -f deploy/docker-compose.yml exec scheduler \
  restic snapshots --tag linda-production
```

A snapshot must appear with the LINDA production tag. Check the separate
off-site status file:

```bash
sudo docker exec linda-scheduler-1 \
  cat /app/backups/offsite_status.json
```

A snapshot listing proves the repository can be read, but it does not prove
that files can be restored. Complete the isolated restore drill below using
the remote snapshot before relying on it.

## 4. Restore (recovery drill)

Practise this on a spare database before you ever need it. Never restore over
the live production database during a drill.

### Restore from a local backup

```bash
# 1. Create an empty database and restore into it
createdb funeralos_restored
pg_restore --no-owner --dbname funeralos_restored \
  backups/funeralos-YYYYMMDD-HHMMSS-xxxxxxxx/database.dump

# 2. Restore the uploaded files
tar -xzf backups/funeralos-YYYYMMDD-HHMMSS-xxxxxxxx/files.tar.gz

# 3. Point a test app at it and check records and documents
```

### Restore from the encrypted off-site repository

First list snapshots and select the required snapshot ID:

```bash
restic snapshots --tag linda-production
restic restore <snapshot-id> --target /tmp/linda-offsite-restore
```

The restored directory contains the original dated backup folder with
`database.dump` and `files.tar.gz`. Restore the dump into an isolated,
disposable PostgreSQL database and extract the file archive into a temporary
directory. Verify table counts and representative uploaded files. Do not point
the production application at the drill database.

## 5. Business data export (for the owner)

**Settings → Data export & backups → Download data** gives a ZIP of
spreadsheets (CSV, opens in Excel), one per kind of record, plus a README and
a manifest of row counts. "Data and uploaded files" also adds the documents,
photos and logos. Passwords are never included, and every download is written
to the audit trail. Only people holding the `data.export` permission (the main
administrator by default) can do this.

This is for portability and the owner's own records. It is **not** a
substitute for backups: only a backup can restore the system exactly.
