# Hosting FuneralOS on one server

This puts everything on one small Linux server: the database, the API, the scheduler (backups, reminders, alerts), the website, and automatic HTTPS. It is enough for a pilot and for a small number of funeral homes.

**Status:** the kit in `deploy/` has been checked for correct configuration, but it has not been run on a real server yet. Expect to fix small things on the first deploy, and treat the first run as a rehearsal, not a launch.

## 1. What to rent
- A virtual private server located in South Africa (local data residency is easiest to explain under POPIA). Several South African hosts, and the Cape Town and Johannesburg regions of the big clouds, offer this. Compare current prices yourself.
- Ubuntu 24.04, 2 vCPU, 4 GB RAM, at least 40 GB SSD. Choose a plan with backups or snapshots if it is cheap; it is a second safety net, not a replacement for ours.
- A domain you control, with two names pointing at the server's IP address (an `A` record each):
  - `app.yourdomain.co.za` (the website)
  - `api.yourdomain.co.za` (the API)

## 2. Prepare the server (once)
SSH in, then:

    adduser deploy && usermod -aG sudo deploy
    # copy your SSH key to the deploy user, then disable password logins:
    #   edit /etc/ssh/sshd_config -> PasswordAuthentication no, PermitRootLogin no
    ufw allow OpenSSH && ufw allow 80 && ufw allow 443 && ufw enable
    apt update && apt -y upgrade
    curl -fsSL https://get.docker.com | sh
    usermod -aG docker deploy
    timedatectl set-timezone Africa/Johannesburg

Log in again as `deploy`.

## 3. Install the app

    git clone https://github.com/Mpho17r/funeral-platform.git
    cd funeral-platform/deploy
    cp .env.example .env
    nano .env          # fill in the two domains, DB_PASSWORD and JWT_SECRET_KEY

Make the two secrets with `python3 -c "import secrets; print(secrets.token_urlsafe(32))"`. Keep a copy of `.env` somewhere safe (a password manager): without the database password you cannot restore.

    docker compose up -d --build
    docker compose logs -f api      # wait for "Application startup complete", then Ctrl+C

The first start builds everything (several minutes), applies the database changes and sets up permissions. Certificates are fetched automatically once both domain names point at the server.

## 4. Create the first business and the operator

    docker compose exec api python -m app.create_owner
    docker compose exec api python -m app.create_platform_admin

Open `https://app.yourdomain.co.za` and sign in. Public sign-up is closed in production once a business exists.

## 5. Check it is healthy
- `https://api.yourdomain.co.za/health` should say the database is fine and show the scheduler's heartbeat.
- Settings, then Data, in the app shows the last backup and the scheduler. The first backup runs at 02:00; to run one now: `docker compose exec api python -m app.run_backup`.

## 6. Keep backups somewhere else (important)
Backups are written on the same server, so a lost server loses them too. Copy them off every night to another place (another provider, your office computer, or object storage). Simplest version, from any other Linux or Mac machine:

    docker compose cp api:/app/backups ./funeralos-backups   # run on the server, then copy that folder away
    # or mount/copy the "backups" volume with rsync or your host's backup tool

Do a **restore drill** before real customers: restore the latest backup into a throw-away database and open it. See [BACKUPS_AND_RECOVERY.md](./BACKUPS_AND_RECOVERY.md).

## 7. Updating later

    cd ~/funeral-platform && git pull
    cd deploy && docker compose up -d --build

Database changes are applied automatically on start. Take a manual backup first when the update is large.

## 8. Email
Add the `SMTP_*` values to `deploy/.env` and run `docker compose up -d` to switch on automatic email (see [MESSAGE_DELIVERY.md](./MESSAGE_DELIVERY.md)).

## Known limits of this setup
- One server: if it is down, the system is down. Monitor `/health` with a free uptime checker and have it message you.
- Uploaded files are not encrypted at rest (the server disk should be). No error-reporting service yet.
- Do not put real family data on it until the restore drill has passed.
