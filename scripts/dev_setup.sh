#!/usr/bin/env bash
# One-shot local dev bootstrap: backend venv + deps, DB migration, sample data.
# Assumes Postgres is already reachable per backend/.env (or ./.env.example).
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

if [ ! -f "$ROOT_DIR/backend/.env" ]; then
  cp "$ROOT_DIR/.env.example" "$ROOT_DIR/backend/.env"
  echo "Created backend/.env from .env.example -- edit DATABASE_URL if needed."
fi

cd "$ROOT_DIR/backend"
python3 -m venv .venv
source .venv/bin/activate
pip install -q --upgrade pip
pip install -q -r requirements.txt

alembic upgrade head

cd "$ROOT_DIR"
python3 scripts/generate_sample_data.py

echo
echo "Backend ready. Next steps:"
echo "  1) cd backend && source .venv/bin/activate && uvicorn app.main:app --reload"
echo "  2) cd frontend && npm install && npm run dev"
