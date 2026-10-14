#!/usr/bin/env bash
# Runs once when the Codespace is created.
set -euo pipefail

cd "$(dirname "$0")/.."

echo "==> Waiting for Postgres"
for _ in $(seq 1 30); do
  pg_isready -h localhost -U mac >/dev/null 2>&1 && break
  sleep 1
done

echo "==> Creating the test database"
psql -h localhost -U mac -d funeralos -tc \
  "SELECT 1 FROM pg_database WHERE datname='funeralos_test'" | grep -q 1 \
  || psql -h localhost -U mac -d funeralos -c "CREATE DATABASE funeralos_test"

echo "==> Backend dependencies"
pip install --quiet -r backend/requirements.txt pytest httpx

echo "==> alembic upgrade head"
(cd backend && alembic upgrade head)

echo "==> Seeding permissions"
(cd backend && python -m app.seed_permissions)

echo "==> Frontend dependencies"
(cd frontend && npm ci)

# The browser only talks to port 3000; Next forwards /backend/* to the API.
cat > frontend/.env.local <<'ENV'
NEXT_PUBLIC_API_URL=/backend
API_PROXY_TARGET=http://127.0.0.1:8000
ENV

echo "==> Done. The API and app start automatically (see .devcontainer/start.sh)."
