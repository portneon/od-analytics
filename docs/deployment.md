# Deployment

## Images

- `backend/Dockerfile` — FastAPI app; also used for the Celery worker (different
  `command`, same image).
- `frontend/Dockerfile.prod` — multi-stage build, static assets served by nginx
  (`frontend/nginx.conf`). Use this for production; `frontend/Dockerfile` (Vite dev
  server) is for local development only.

## Release steps

1. Build and push both images.
2. Run `alembic upgrade head` as a release/init step against the production database —
   never apply schema changes by hand.
3. Deploy the API (`uvicorn app.main:app`) behind a reverse proxy/load balancer with
   TLS termination.
4. Deploy at least one Celery worker process (`celery -A app.workers.celery_app
   worker`) — datasets will queue but never process without one.
5. Deploy the frontend static build behind nginx/CDN, pointing `VITE_API_BASE_URL` at
   the production API's public URL (baked in at build time).

## Configuration for production

- `STORAGE_USE_LOCAL_FS=false` with real S3 (or another S3-compatible provider)
  credentials — local filesystem storage does not survive container restarts/scaling.
- `JWT_SECRET` — a real random secret, not the development default.
- `CORS_ORIGINS` — the exact production frontend origin(s), not `*`.
- `LLM_PROVIDER`/`LLM_API_KEY` — set if the AI Analyst should produce narratives in
  production; the platform runs safely without them (fallback mode).
- `CELERY_TASK_ALWAYS_EAGER` — must be `false` (or unset) in production; eager mode is
  for local dev/tests only and blocks the request thread.

## Scaling notes

- The API is stateless and horizontally scalable behind a load balancer.
- Celery workers scale independently of the API — add workers to increase ETL/metrics
  throughput without touching the API tier.
- `email_events` and its materialized metrics tables are indexed for the query patterns
  the API actually issues (see [docs/database.md](database.md)). If raw event volume
  outgrows Postgres for ad hoc analytical queries, the architecture's clean separation
  between `app/analytics` (aggregation + read functions) and everything above it means
  the fact table can move to ClickHouse without changing the API or frontend contracts.
- Redis is used for both the Celery broker and result backend; a managed Redis instance
  is recommended in production over a single container.

## Observability

Structured JSON logs (`app/core/logging.py`) include `request_id`, method, path,
status, and duration for every HTTP request, with sensitive fields (passwords, tokens,
API keys) automatically redacted. Wire the JSON log stream into your log
aggregator/APM of choice; no vendor-specific SDK is baked into the app.
