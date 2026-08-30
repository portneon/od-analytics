# Deployment

## Images

- `backend/Dockerfile` — FastAPI app. Dataset processing runs inline via FastAPI
  `BackgroundTasks`, so this is the only backend image/process needed — no separate
  worker.
- `frontend/Dockerfile.prod` — multi-stage build, static assets served by nginx
  (`frontend/nginx.conf`). Use this for production; `frontend/Dockerfile` (Vite dev
  server) is for local development only.

## Release steps

1. Build and push both images.
2. Deploy the API (`uvicorn app.main:app`) behind a reverse proxy/load balancer with
   TLS termination. It creates any missing tables on startup (`Base.metadata.create_all`
   in `app/main.py`'s lifespan hook) — there's no separate migration step to run.
3. Deploy the frontend static build behind nginx/CDN, pointing `VITE_API_BASE_URL` at
   the production API's public URL (baked in at build time).

There are no schema migrations in this app. If a model's columns change after
production tables already exist, `create_all()` won't alter them — you need to drop
and recreate the affected table(s) (or the whole database) against the new schema.
That's a deliberate trade for a single-user tool with disposable data; see
[docs/database.md](database.md).

## Security

**The API has no authentication.** Anyone who can reach it can view and upload data.
This is a deliberate simplification for a single-user tool — do not deploy it
somewhere reachable by the public internet without adding your own access control in
front of it (e.g. a reverse proxy with basic auth, an IP allowlist, or a private
network/VPN). `render.yaml` deploys it as a public Render web service on the
assumption that's acceptable for the data involved; reconsider that if it isn't.

## Configuration for production

- `STORAGE_USE_LOCAL_FS=false` with real S3 (or another S3-compatible provider)
  credentials — local filesystem storage does not survive container restarts/scaling.
- `CORS_ORIGINS` — the exact production frontend origin(s), not `*`.
- `LLM_PROVIDER`/`LLM_API_KEY` — set if the AI Analyst should produce narratives in
  production; the platform runs safely without them (fallback mode).

## Scaling notes

- The API is stateless and horizontally scalable behind a load balancer, except that
  dataset processing (BackgroundTasks) runs on whichever instance received the upload
  request — a large CSV blocks that instance's event loop for the duration.
- `email_events` and its materialized metrics tables are indexed for the query patterns
  the API actually issues (see [docs/database.md](database.md)). If raw event volume
  outgrows Postgres for ad hoc analytical queries, the architecture's clean separation
  between `app/analytics` (aggregation + read functions) and everything above it means
  the fact table can move to ClickHouse without changing the API or frontend contracts.

## Observability

Structured JSON logs (`app/core/logging.py`) include `request_id`, method, path,
status, and duration for every HTTP request, with sensitive fields (API keys, secrets)
automatically redacted. Wire the JSON log stream into your log aggregator/APM of
choice; no vendor-specific SDK is baked into the app.
