#!/usr/bin/env bash
# Update a running FuneralOS server to the latest main.
#   sudo DOMAIN=yourfuneralhome.co.za bash /srv/funeralos/deploy/update.sh
set -euo pipefail
: "${DOMAIN:?Set DOMAIN}"
SRV=/srv/funeralos
RUN_USER=funeralos
[ "$(id -u)" -eq 0 ] || { echo "Run as root (sudo)."; exit 1; }

# A backup first, so any update can be undone.
sudo -u "$RUN_USER" bash -lc "cd $SRV/backend && venv/bin/python -m app.run_backup"

sudo -u "$RUN_USER" bash -lc "
  set -e
  cd $SRV && git pull --ff-only
  export PATH=\"\$HOME/.local/bin:\$PATH\"
  cd backend
  uv pip install --python venv/bin/python -r requirements.txt
  venv/bin/alembic upgrade head
  venv/bin/python -m app.seed_permissions
  cd ../frontend && npm ci
  NEXT_PUBLIC_API_URL=https://api.${DOMAIN} npm run build
"
systemctl restart funeralos-api funeralos-scheduler funeralos-web
sleep 3
curl -fsS "https://api.${DOMAIN}/health" && echo && echo "Updated."
