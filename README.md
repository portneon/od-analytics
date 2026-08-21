# Email Intelligence Platform

An executive email intelligence and analytics platform that turns Zoho Mail (and, via
its adapter architecture, any future provider) CSV exports into delivery analytics,
bounce analysis, recipient risk scoring, anomaly detection, root-cause analysis, and
natural-language "ask your data" reporting.

This is not a CSV viewer. Raw events are normalized into a canonical schema, persisted
in a multi-tenant Postgres database, aggregated into materialized metrics tables, and
served through a deterministic analytics/intelligence engine that an AI layer can query
via tools — but never fabricate numbers for.

## Project overview

```
Zoho Mail CSV
     │
     ▼
Ingestion (upload, validate) ─▶ Raw file storage (local fs / S3-compatible)
     │
     ▼
ETL (Celery job): parse → normalize → enrich → classify bounces → dedupe → persist
     │
     ▼
PostgreSQL (canonical email_events + dimension tables)
     │
     ├──▶ CALCULATE_METRICS job ─▶ materialized metrics tables (daily/hourly/recipient/
     │                              domain/subject/sender/bounce-reason/infra/application)
     │
     ├──▶ Recipient risk scoring
     ├──▶ Anomaly detection (z-score + IQR)
     └──▶ Root-cause analysis / executive insights
     │
     ▼
FastAPI (versioned REST API, tenant-scoped)
     │
     ├──▶ React dashboard (Vite + TS + Tailwind + TanStack Query + Recharts)
     └──▶ AI Analyst (tool-calling LLM, provider-agnostic; degrades gracefully with no key)
```

See [docs/architecture.md](docs/architecture.md) for the full write-up.

## Prerequisites

- Python 3.12+
- Node.js 20+
- PostgreSQL 16+ (local install or Docker)
- Redis 7+ (local install or Docker)
- Docker + Docker Compose (recommended for one-command local dev)

## Quick start (Docker Compose)

```bash
cp .env.example .env
docker compose up
```

This starts Postgres, Redis, MinIO, the FastAPI backend (with migrations applied
automatically), a Celery worker, and the React frontend. Visit:

- Frontend: http://localhost:5173
- API docs: http://localhost:8000/docs

## Quick start (one script, local dev)

```bash
scripts/run.sh
```

Starts Postgres/Redis/MinIO in Docker, then runs the backend, Celery worker, and
frontend as local processes (not containerized) so they hot-reload against your
working tree. Sets up the backend venv, `npm install`, `.env` files, and DB migrations
on first run. Logs go to `data/logs/`; Ctrl+C stops everything.

## Manual local setup

### Backend

```bash
cd backend
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp ../.env.example .env   # edit DATABASE_URL etc. if not using Docker Postgres/Redis

alembic upgrade head
uvicorn app.main:app --reload
```

In a second terminal, run the background worker (required for dataset processing):

```bash
source .venv/bin/activate
celery -A app.workers.celery_app worker --loglevel=info
```

For quick local testing without Redis/a worker process, set
`CELERY_TASK_ALWAYS_EAGER=true` in `.env` — uploads then process synchronously in the
request path. **Not recommended for anything beyond quick manual smoke testing.**

### Frontend

```bash
cd frontend
npm install
cp .env.example .env   # points at http://localhost:8000/api/v1 by default
npm run dev
```

### Sample data

No real Zoho export is bundled with this repo. Generate a realistic synthetic one:

```bash
python3 scripts/generate_sample_data.py
```

This writes `data/fixtures/okiedokie-app.csv` and `data/fixtures/od-erp-customers.csv` —
Zoho-shaped exports (see column aliases in `app/ingestion/schema_mapper.py`) with
injected bounces, a volume anomaly, and a handful of malformed rows so the data-quality
and anomaly-detection paths have something real to find.

## Environment variables

See [.env.example](.env.example) for the full list. Key ones:

| Variable | Purpose |
|---|---|
| `DATABASE_URL` | Postgres connection string |
| `REDIS_URL` | Celery broker/result backend |
| `STORAGE_USE_LOCAL_FS` | `true` for local filesystem raw storage, `false` for S3/MinIO |
| `LLM_PROVIDER` / `LLM_API_KEY` / `LLM_MODEL` | AI Analyst provider. `LLM_PROVIDER=none` (default) runs the AI Analyst in a safe fallback mode — no key required |
| `JWT_SECRET` | Auth token signing secret — change in production |
| `DEFAULT_TIMEZONE` | Timezone used for daily/hourly bucketing (default `Asia/Kolkata`) |

## Database setup

Schema is managed entirely through Alembic migrations — never hand-edit the schema.

```bash
cd backend
alembic upgrade head          # apply migrations
alembic revision --autogenerate -m "description"   # after changing app/models/*
```

## Running tests

```bash
cd backend
source .venv/bin/activate
pytest                        # unit + integration tests against a real Postgres test DB
pytest --cov=app tests/       # with coverage
```

Integration tests run against a dedicated `email_intel_test` Postgres database (create
it once: `createdb email_intel_test`, or point `DATABASE_URL` in your test environment
at any disposable Postgres instance) and run Celery in eager mode, so no Redis/worker
is required to run the suite.

## API documentation

FastAPI serves interactive docs automatically:

- Swagger UI: http://localhost:8000/docs
- ReDoc: http://localhost:8000/redoc

All endpoints are versioned under `/api/v1` and return the consistent envelope
documented in [docs/api.md](docs/api.md).

## Deployment

See [docs/deployment.md](docs/deployment.md). In short: build `backend/Dockerfile` and
`frontend/Dockerfile.prod` (nginx-served static build), run Alembic migrations as a
release step, run at least one Celery worker process, and point `STORAGE_USE_LOCAL_FS`
at a real S3-compatible bucket.

## Troubleshooting

- **Uploads stay `QUEUED` forever** — no Celery worker is running, or it can't reach
  Redis. Check `REDIS_URL` and that a `celery -A app.workers.celery_app worker` process
  is up.
- **`INVALID_FILE` on upload** — file isn't `.csv`, is empty, or exceeds
  `MAX_UPLOAD_FILE_SIZE_BYTES`.
- **AI Analyst says "AI narrative generation is unavailable"** — no `LLM_API_KEY` is
  configured. This is expected, not a bug — the platform never fabricates a narrative
  when no LLM is configured; it shows the same underlying data the narrative would have
  been built from.
- **`bcrypt` / password hashing errors** — this repo pins `bcrypt==4.0.1` alongside
  `passlib==1.7.4`; newer `bcrypt` releases break passlib's backend detection.

## Further reading

- [docs/architecture.md](docs/architecture.md) — system architecture and design decisions
- [docs/database.md](docs/database.md) — schema, multi-tenancy, indexing
- [docs/ingestion.md](docs/ingestion.md) — canonical schema, adapters, ETL pipeline
- [docs/analytics.md](docs/analytics.md) — metrics, aggregation, intelligence engine
- [docs/ai.md](docs/ai.md) — AI Analyst architecture and safety guarantees
- [docs/api.md](docs/api.md) — API reference
- [docs/deployment.md](docs/deployment.md) — production deployment guide
