#!/usr/bin/env bash
# One-time setup of FuneralOS on a fresh Ubuntu 24.04 server.
#
#   sudo DOMAIN=yourfuneralhome.co.za REPO_URL=https://github.com/Mpho17r/funeral-platform.git \
#        bash setup-server.sh
#
# Result: app at https://app.DOMAIN, API at https://api.DOMAIN, with HTTPS,
# PostgreSQL on localhost only, a firewall, automatic security updates, and
# three services (api, web, scheduler). Safe to re-run: it keeps an existing
# .env and database.
#
# Before running: point DNS A records for app.DOMAIN and api.DOMAIN at this
# server, otherwise HTTPS certificates cannot be issued.
set -euo pipefail

: "${DOMAIN:?Set DOMAIN, for example DOMAIN=yourfuneralhome.co.za}"
APP_HOST="app.${DOMAIN}"
API_HOST="api.${DOMAIN}"
SRV=/srv/funeralos
RUN_USER=funeralos
DB_NAME=funeralos
DB_USER=funeralos

[ "$(id -u)" -eq 0 ] || { echo "Run as root (sudo)."; exit 1; }

echo "==> Packages"
export DEBIAN_FRONTEND=noninteractive
apt-get update -y
apt-get install -y curl git ufw ca-certificates gnupg postgresql postgresql-contrib \
  debian-keyring debian-archive-keyring apt-transport-https unattended-upgrades

# Node 22
if ! command -v node >/dev/null || [ "$(node -v | cut -d. -f1 | tr -d v)" -lt 22 ]; then
  curl -fsSL https://deb.nodesource.com/setup_22.x | bash -
  apt-get install -y nodejs
fi

# Caddy (HTTPS certificates are fetched and renewed automatically)
if ! command -v caddy >/dev/null; then
  curl -1sLf 'https://dl.cloudsmith.io/public/caddy/stable/gpg.key' | gpg --dearmor -o /usr/share/keyrings/caddy-stable-archive-keyring.gpg
  curl -1sLf 'https://dl.cloudsmith.io/public/caddy/stable/debian.deb.txt' > /etc/apt/sources.list.d/caddy-stable.list
  apt-get update -y
  apt-get install -y caddy
fi

echo "==> Firewall (only SSH, HTTP, HTTPS)"
ufw allow OpenSSH
ufw allow 80/tcp
ufw allow 443/tcp
ufw --force enable

echo "==> Service user and code"
id "$RUN_USER" >/dev/null 2>&1 || useradd --system --create-home --shell /bin/bash "$RUN_USER"
mkdir -p "$SRV"
if [ ! -d "$SRV/.git" ]; then
  : "${REPO_URL:?Set REPO_URL (a private repo needs a token in the URL or a deploy key)}"
  git clone "$REPO_URL" "$SRV"
fi
chown -R "$RUN_USER":"$RUN_USER" "$SRV"

echo "==> Database (localhost only)"
ENV_FILE="$SRV/backend/.env"
if [ ! -f "$ENV_FILE" ]; then
  DB_PASS="$(python3 -c 'import secrets; print(secrets.token_urlsafe(24))')"
  JWT="$(python3 -c 'import secrets; print(secrets.token_urlsafe(48))')"
  sudo -u postgres psql -v ON_ERROR_STOP=1 <<SQL
DO \$\$ BEGIN
  IF NOT EXISTS (SELECT FROM pg_roles WHERE rolname = '${DB_USER}') THEN
    CREATE ROLE ${DB_USER} LOGIN PASSWORD '${DB_PASS}';
  ELSE
    ALTER ROLE ${DB_USER} PASSWORD '${DB_PASS}';
  END IF;
END \$\$;
SQL
  sudo -u postgres psql -tAc "SELECT 1 FROM pg_database WHERE datname='${DB_NAME}'" | grep -q 1 \
    || sudo -u postgres createdb -O "$DB_USER" "$DB_NAME"
  cat > "$ENV_FILE" <<ENV
DATABASE_URL=postgresql+psycopg://${DB_USER}:${DB_PASS}@localhost:5432/${DB_NAME}
JWT_SECRET_KEY=${JWT}
APP_ENV=production
CORS_ORIGINS=https://${APP_HOST}
BACKUP_DIR=/srv/funeralos/backups
# Email (optional): fill in to send reminders automatically.
SMTP_HOST=
SMTP_PORT=587
SMTP_USER=
SMTP_PASSWORD=
SMTP_FROM=
ENV
  chown "$RUN_USER":"$RUN_USER" "$ENV_FILE"
  chmod 600 "$ENV_FILE"
fi
mkdir -p /srv/funeralos/backups
chown "$RUN_USER":"$RUN_USER" /srv/funeralos/backups

echo "==> Backend (Python 3.13 via uv)"
sudo -u "$RUN_USER" bash -lc '
  set -e
  command -v uv >/dev/null || curl -LsSf https://astral.sh/uv/install.sh | sh
  export PATH="$HOME/.local/bin:$PATH"
  cd /srv/funeralos/backend
  [ -d venv ] || uv venv --python 3.13 venv
  uv pip install --python venv/bin/python -r requirements.txt
  venv/bin/alembic upgrade head
  venv/bin/python -m app.seed_permissions
'

echo "==> Frontend build"
sudo -u "$RUN_USER" bash -lc "
  set -e
  cd /srv/funeralos/frontend
  npm ci
  NEXT_PUBLIC_API_URL=https://${API_HOST} npm run build
"

echo "==> Services"
cat > /etc/systemd/system/funeralos-api.service <<UNIT
[Unit]
Description=FuneralOS API
After=network.target postgresql.service
[Service]
User=${RUN_USER}
WorkingDirectory=${SRV}/backend
ExecStart=${SRV}/backend/venv/bin/uvicorn app.main:app --host 127.0.0.1 --port 8000 --workers 2
Restart=always
[Install]
WantedBy=multi-user.target
UNIT

cat > /etc/systemd/system/funeralos-scheduler.service <<UNIT
[Unit]
Description=FuneralOS scheduler (run exactly one copy)
After=network.target postgresql.service
[Service]
User=${RUN_USER}
WorkingDirectory=${SRV}/backend
ExecStart=${SRV}/backend/venv/bin/python -m app.run_scheduler
Restart=always
[Install]
WantedBy=multi-user.target
UNIT

cat > /etc/systemd/system/funeralos-web.service <<UNIT
[Unit]
Description=FuneralOS web app
After=network.target
[Service]
User=${RUN_USER}
WorkingDirectory=${SRV}/frontend
Environment=PORT=3000
ExecStart=/usr/bin/npm start -- -H 127.0.0.1
Restart=always
[Install]
WantedBy=multi-user.target
UNIT

systemctl daemon-reload
systemctl enable --now funeralos-api funeralos-scheduler funeralos-web

echo "==> HTTPS in front"
cat > /etc/caddy/Caddyfile <<CADDY
${APP_HOST} {
	encode gzip
	reverse_proxy 127.0.0.1:3000
}

${API_HOST} {
	encode gzip
	# Simple brake on abuse is best added with a rate-limit plugin later.
	reverse_proxy 127.0.0.1:8000
}
CADDY
systemctl reload caddy || systemctl restart caddy

cat <<DONE

Done. Next steps (once):
  1. Create the first business and its administrator:
       sudo -u ${RUN_USER} bash -lc 'cd ${SRV}/backend && venv/bin/python -m app.create_owner'
  2. Create your platform operator login (Saccharum):
       sudo -u ${RUN_USER} bash -lc 'cd ${SRV}/backend && venv/bin/python -m app.create_platform_admin'
  3. Open https://${APP_HOST} and sign in.
  4. Check https://${API_HOST}/health says "ok".
  5. Follow the checklist in docs/PRODUCTION_READINESS.md section 4
     (restore drill, off-server backup copy, uptime monitor).
DONE
