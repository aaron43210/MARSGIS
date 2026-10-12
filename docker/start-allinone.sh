#!/bin/sh
# MarsGIS all-in-one startup: boots uvicorn (backend+engine) then nginx (SPA).
# Both run in the same container: nginx on :8080, uvicorn on :8000 (loopback).
set -eu

# Ensure the SQLite database directory exists (the backend config defaults to
# ./storage/marsgis.db relative to the /app workdir).
mkdir -p /app/storage /data
export DATABASE_URL="sqlite+aiosqlite:////data/marsgis.db"
export STORAGE_ROOT="/data"
export CORS_ORIGINS='["http://localhost:8080","http://127.0.0.1:8080","http://localhost:5173","http://127.0.0.1:5173"]'

echo "[start] Starting MarsGIS backend (uvicorn on :8000)..."
python -m uvicorn app.main:app \
  --host 127.0.0.1 \
  --port 8000 \
  --workers 1 \
  --log-level info >/tmp/uvicorn.log 2>&1 &

UVICORN_PID=$!

# Wait for the backend to be ready (up to 30s)
echo "[start] Waiting for backend to be ready..."
i=0
until python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/api/health')" 2>/dev/null; do
  i=$((i+1))
  if [ $i -ge 30 ]; then
    echo "[start] ERROR: Backend did not start within 30s. Logs:"
    cat /tmp/uvicorn.log 2>/dev/null || true
    kill $UVICORN_PID 2>/dev/null || true
    exit 1
  fi
  sleep 1
done

echo "[start] Backend is ready. Starting nginx on :8080..."
exec nginx -g "daemon off;"
