# Backups, exports and recovery

FuneralOS keeps two kinds of data: the **database** (PostgreSQL) and
**uploaded files** (the `backend/storage` folder: documents, photos, logos).
A backup must copy both.

## 1. Take a backup

From the `backend` folder with the virtual environment active:

```bash
python -m app.run_backup
```

This creates `backend/backups/funeralos-YYYYMMDD-HHMMSS/` containing

- `database.dump` – a full PostgreSQL dump
- `files.tar.gz` – everything in `storage/`

It then checks that the dump can be read back, records the result in
`backend/backups/status.json` (shown in **Settings → Data export & backups**),
and removes the oldest backups beyond the newest 14.

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

## 3. Keep a copy somewhere else

A backup on the same machine does not survive that machine breaking, being
stolen or flooded. Copy `backend/backups` to an external drive or cloud
storage regularly (for example `rclone sync backups remote:funeralos`).
Backups contain personal information: encrypt the drive or storage and
limit who can open it.

## 4. Restore (recovery drill)

Practise this once on a spare database before you ever need it.

```bash
# 1. Create an empty database and restore into it
createdb funeralos_restored
pg_restore --no-owner --dbname funeralos_restored \
  backups/funeralos-YYYYMMDD-HHMMSS/database.dump

# 2. Restore the uploaded files
tar -xzf backups/funeralos-YYYYMMDD-HHMMSS/files.tar.gz   # recreates ./storage

# 3. Point the app at it (DATABASE_URL in .env) and start it
```

Then sign in and check recent funerals, payments and a few documents.

## 5. Business data export (for the owner)

**Settings → Data export & backups → Download data** gives a ZIP of
spreadsheets (CSV, opens in Excel), one per kind of record, plus a README and
a manifest of row counts. "Data and uploaded files" also adds the documents,
photos and logos. Passwords are never included, and every download is written
to the audit trail. Only people holding the `data.export` permission (the main
administrator by default) can do this.

This is for portability and the owner's own records. It is **not** a
substitute for backups: only a backup can restore the system exactly.
