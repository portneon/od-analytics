#!/usr/bin/env bash
# Single entry point for local dev: brings up Postgres/Redis/MinIO via Docker Compose,
# then runs the backend API, Celery worker, and frontend dev server as local processes
# (not Docker) so they hot-reload against your working tree.
#
# Usage: scripts/run.sh
# Stop everything with Ctrl+C.

set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
LOG_DIR="$ROOT_DIR/data/logs"
mkdir -p "$LOG_DIR"

PIDS=()

cleanup() {
  echo
  echo "Shutting down..."
  for pid in "${PIDS[@]:-}"; do
    kill "$pid" 2>/dev/null || true
  done
  wait 2>/dev/null || true
  (cd "$ROOT_DIR" && docker compose stop postgres redis minio) >/dev/null 2>&1 || true
  echo "Stopped."
}
trap cleanup EXIT INT TERM

echo "==> Starting Postgres, Redis, MinIO (Docker Compose)"
(cd "$ROOT_DIR" && docker compose up -d postgres redis minio)

echo "==> Waiting for Postgres/Redis to be healthy"
until [ "$(cd "$ROOT_DIR" && docker compose ps -q postgres | xargs docker inspect -f '{{.State.Health.Status}}')" = "healthy" ]; do
  sleep 1
done
until [ "$(cd "$ROOT_DIR" && docker compose ps -q redis | xargs docker inspect -f '{{.State.Health.Status}}')" = "healthy" ]; do
  sleep 1
done

if [ ! -f "$ROOT_DIR/backend/.env" ]; then
  cp "$ROOT_DIR/.env.example" "$ROOT_DIR/backend/.env"
  echo "Created backend/.env from .env.example"
fi

if [ ! -d "$ROOT_DIR/backend/.venv" ]; then
  echo "==> Creating backend venv and installing dependencies"
  python3 -m venv "$ROOT_DIR/backend/.venv"
  "$ROOT_DIR/backend/.venv/bin/pip" install -q --upgrade pip
  "$ROOT_DIR/backend/.venv/bin/pip" install -q -r "$ROOT_DIR/backend/requirements.txt"
fi

echo "==> Applying database migrations"
(cd "$ROOT_DIR/backend" && ./.venv/bin/alembic upgrade head)

if [ ! -d "$ROOT_DIR/frontend/node_modules" ]; then
  echo "==> Installing frontend dependencies"
  (cd "$ROOT_DIR/frontend" && npm install)
fi
if [ ! -f "$ROOT_DIR/frontend/.env" ]; then
  cp "$ROOT_DIR/frontend/.env.example" "$ROOT_DIR/frontend/.env"
  echo "Created frontend/.env from .env.example"
fi

echo "==> Starting backend API (log: data/logs/backend.log)"
(cd "$ROOT_DIR/backend" && ./.venv/bin/uvicorn app.main:app --reload --host 0.0.0.0 --port 8000) \
  >"$LOG_DIR/backend.log" 2>&1 &
PIDS+=($!)

echo "==> Starting Celery worker (log: data/logs/worker.log)"
(cd "$ROOT_DIR/backend" && ./.venv/bin/celery -A app.workers.celery_app worker --loglevel=info) \
  >"$LOG_DIR/worker.log" 2>&1 &
PIDS+=($!)

echo "==> Starting frontend dev server (log: data/logs/frontend.log)"
(cd "$ROOT_DIR/frontend" && npm run dev -- --host 0.0.0.0) \
  >"$LOG_DIR/frontend.log" 2>&1 &
PIDS+=($!)

sleep 2
cat <<EOF

Running:
  Frontend  http://localhost:5173
  API       http://localhost:8000/docs
  MinIO     http://localhost:9001  (minioadmin / minioadmin)

Logs: tail -f data/logs/{backend,worker,frontend}.log
Press Ctrl+C to stop everything.
EOF

wait
