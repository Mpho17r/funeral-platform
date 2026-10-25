# Production readiness

What it takes to run FuneralOS for a real funeral business with real
families' information. Written from what the code does today, so every
"done" below is something you can check, and every "open" is a real gap.

## 1. Where things stand

**Done in the code**

| Area | State |
| --- | --- |
| Safe settings | `APP_ENV=production` refuses to start with a short or placeholder `JWT_SECRET_KEY`, a missing `CORS_ORIGINS`, or a non-`https` address |
| Sign-up | Closed on a live system once the first business exists. Create owners with `python -m app.create_owner` |
| Recurring work | One process, `python -m app.run_scheduler`, runs the funeral status sync (5 min), mortuary and licence alerts (30 min), payment reminders (07:00) and the backup (02:00), South African time, with catch-up after downtime |
| Backups | Database dump plus uploaded files, verified, 14 kept, status shown in Settings (see `BACKUPS_AND_RECOVERY.md`) |
| Health | `GET /health` answers 503 when the database is down, and reports the scheduler (`ok`, `degraded`, `stale`, `never`) |
| Access control | Role and per-person permissions on every endpoint, one business never sees another's data, audit trail, sign-in lockout after 5 failures |
| Browser safety | `nosniff`, `X-Frame-Options: DENY`, `Referrer-Policy`, HSTS in production |
| Owner's own copy | Full data export (Settings, Data export and backups) |

**Open: needs a decision or work**

1. **Hosting is undecided** (section 2).
2. **Reminders are queued, not delivered.** The system prepares each payment
   reminder and a person sends it with one tap (WhatsApp, SMS or email link),
   then marks it sent. No SMS or WhatsApp provider is connected. This is a
   good default (consent, cost, no accidental messages to bereaved families)
   but it is not "automatic sending". Connecting a gateway is a separate piece
   of work and a cost per message.
3. **Uploaded files live on the server's disk** (`backend/storage`). They are
   backed up, but there is no encryption at rest and no separate file store.
   Encrypt the disk (FileVault, LUKS or your host's volume encryption).
4. **No automatic error reporting.** Failures are in the logs and in the
   Settings screen only. Add an uptime monitor on `/health` at minimum.
5. **No API rate limiting** beyond sign-in lockout. Put the rate limit in the
   reverse proxy.
6. **Legal and privacy set-up is yours** (section 5).

## 2. Choosing where it runs

| Option | Good | Watch out |
| --- | --- | --- |
| The business's own computer or mini-PC | Cheapest, data on site | Power cuts, theft, no one to fix it at 2 a.m.; needs a static address or tunnel and its own backups off the machine |
| A South African VPS or cloud region (for example AWS af-south-1 in Cape Town, or a local host) | Real uptime, data stays in South Africa, simple to back up | Monthly cost; someone must apply updates |
| A VPS outside South Africa | Often cheaper | POPIA limits sending personal information abroad unless conditions in section 72 are met; get advice first |

Either way you need: one small Linux machine (2 CPU, 4 GB RAM is plenty to
start), PostgreSQL 16, a domain name, and HTTPS. For a first live customer
the South African VPS is the sensible default.

## 3. Setting it up (single machine)

Short version: use the scripted setup in [DEPLOYING.md](./DEPLOYING.md). The manual steps below show what it does.

These are standard recipes, not tested on your server: try them on a spare
machine first.

**1. Prepare**
- Install PostgreSQL 16, Python 3.13, Node 22, and Caddy (or nginx).
- Create a database and a database user that only owns it. Postgres must
  listen on `localhost` only.
- Open only ports 80 and 443 in the firewall.

**2. Configure `backend/.env`** (see `backend/.env.example`)
```
DATABASE_URL=postgresql+psycopg://funeralos:STRONG-PASSWORD@localhost:5432/funeralos
JWT_SECRET_KEY=<python -c "import secrets; print(secrets.token_urlsafe(48))">
APP_ENV=production
CORS_ORIGINS=https://app.yourfuneralhome.co.za
```
Build the web app with `NEXT_PUBLIC_API_URL=https://api.yourfuneralhome.co.za`
set at build time (it is baked into the build).

**3. First run**
```bash
cd backend
alembic upgrade head
python -m app.seed_permissions
python -m app.create_owner          # the first business and its administrator
cd ../frontend && npm ci && npm run build
```

**4. Keep four things running** (systemd, shown for the API; copy the pattern)
```ini
# /etc/systemd/system/funeralos-api.service
[Service]
WorkingDirectory=/srv/funeralos/backend
ExecStart=/srv/funeralos/backend/venv/bin/uvicorn app.main:app --host 127.0.0.1 --port 8000 --workers 2
Restart=always
User=funeralos
# Same pattern for:
#   funeralos-web.service        npm start (port 3000) in /srv/funeralos/frontend
#   funeralos-scheduler.service  python -m app.run_scheduler   (exactly ONE copy)
```

**5. HTTPS in front** (Caddy gets and renews certificates by itself)
```
app.yourfuneralhome.co.za { reverse_proxy 127.0.0.1:3000 }
api.yourfuneralhome.co.za { reverse_proxy 127.0.0.1:8000 }
```

**6. Updating later**: pull the code, then `alembic upgrade head`,
`python -m app.seed_permissions`, `npm run build`, restart the services.

## 4. Before the first real family is entered

- [ ] `APP_ENV=production` and the app starts (it refuses if anything is unsafe)
- [ ] Reached over `https://` only; plain `http://` redirects
- [ ] The demo and test accounts do not exist on this database
- [ ] Each staff member has their own account, with the right role
- [ ] The main administrator's password is long and unique; consider a second
      administrator so the business is never locked out
- [ ] The scheduler service is running (Settings shows "Background jobs: running")
- [ ] A backup has completed **and you have restored one** onto a spare
      database (`BACKUPS_AND_RECOVERY.md`, section 4)
- [ ] Backups are copied somewhere off the server
- [ ] The disk is encrypted and the server's operating system updates itself
      for security fixes
- [ ] An uptime monitor checks `https://api.../health` every minute and
      alerts a person's phone
- [ ] Someone other than you knows how to restart the services and where the
      backups are (write it down)

## 5. Privacy and legal (South Africa)

FuneralOS holds personal information about deceased persons, families,
members and staff, including ID numbers, cause of death and payment details.
That falls under POPIA. This is not legal advice; confirm with a lawyer.

- [ ] Name an **Information Officer** and register them with the Information
      Regulator
- [ ] Give families and members a **privacy notice** saying what you keep, why
      and for how long; get consent for reminders by WhatsApp, SMS or email
      (the system records each member's channel choice)
- [ ] If a hosting company stores the data, sign an **operator agreement** with it
- [ ] Decide how long records are kept; the system can anonymise a member who
      has left (Members) while keeping the financial history
- [ ] Have a **breach plan**: who is told, and within what time, if data leaks
- [ ] Keep exports and backups as carefully as the live system: they hold
      everything

## 6. Day-to-day

- Settings, Data export and backups: last backup time and scheduler status.
- Audit trail: who did what, including every data export.
- Logs: `journalctl -u funeralos-api` (and `-scheduler`, `-web`).
- Once a quarter: repeat the restore drill. A backup nobody has restored is a
  hope, not a backup.
