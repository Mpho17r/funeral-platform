#!/usr/bin/env bash
# Runs every time the Codespace starts: API on 8000, app on 3000.
cd "$(dirname "$0")/.."

mkdir -p /tmp/funeralos
fuser -k 8000/tcp 3000/tcp >/dev/null 2>&1 || true

(cd backend && nohup uvicorn app.main:app --reload --port 8000 \
  > /tmp/funeralos/api.log 2>&1 &)
(cd frontend && nohup npm run dev -- --port 3000 \
  > /tmp/funeralos/web.log 2>&1 &)

echo "API log: /tmp/funeralos/api.log   App log: /tmp/funeralos/web.log"
