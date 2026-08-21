# Architecture

## Layered design

```
frontend/   React + TS + Vite + Tailwind + TanStack Query + Zustand + Recharts
backend/
  app/api/         HTTP layer only — request parsing, auth, calls into services
  app/services/     Business orchestration (dataset lifecycle, auth, reports, storage)
  app/ingestion/    CSV loading, schema mapping, adapters, normalization, bounce
                     classification, dedup/retry detection, ETL pipeline orchestration
  app/analytics/    Aggregation (writes materialized metrics) + read-side query functions
  app/intelligence/ Risk scoring, anomaly detection, root-cause analysis, insights
  app/ai/           LLM provider abstraction, tool definitions, tool executor, orchestrator
  app/models/       SQLAlchemy ORM models (source of truth for schema, via Alembic)
  app/schemas/      Pydantic models: canonical event, API request/response shapes
  app/workers/      Celery app + background job definitions
  app/core/         Config, DB session, logging, security/auth dependencies
```

Nothing in `api/` contains business logic beyond request/response shaping — every route
handler calls into `services/`, `analytics/`, or `intelligence/`. This keeps HTTP,
business logic, persistence, analytics, and AI cleanly separated (spec section 72).

## Data flow

1. **Ingestion**: a CSV is uploaded, validated (extension/size), and stored via the
   `StorageService` abstraction (local filesystem in dev, S3-compatible in production).
   A `Dataset` + `ImportJob` row are created and a Celery task is queued.
2. **ETL** (`app/ingestion/pipeline.py`): the CSV is loaded with Polars, its schema is
   detected via alias matching (`schema_mapper.py`) against the canonical field set, an
   adapter (`adapters/zoho.py`) converts each row into a `CanonicalEmailEvent`, bounces
   are classified deterministically, duplicate/retry detection runs, dimension rows
   (`senders`/`recipients`/`subjects`/`domains`) are bulk-upserted, and `email_events`
   rows are bulk-inserted. A `DataQualityReport` is produced and stored on the dataset.
3. **Aggregation** (`app/analytics/aggregation.py`): SQL `GROUP BY` queries compute
   daily/hourly/recipient/domain/subject/sender/bounce-reason/infrastructure/application
   metrics and upsert them into materialized tables, so dashboard reads never scan raw
   events.
4. **Intelligence**: recipient risk scores (explainable 0–100 with reasons), anomaly
   detection (z-score + IQR over the dataset's own daily series, plus one-sided z-score
   across entities), and root-cause contribution breakdowns are computed from the
   metrics/event tables.
5. **API**: FastAPI serves all of the above under `/api/v1`, tenant-scoped via the JWT
   in every request — `tenant_id` is never trusted from client input.
6. **AI Analyst**: a question is answered by an LLM (or a deterministic fallback if none
   is configured) driving a tool-calling loop against the exact same analytics functions
   used by the dashboard. See [ai.md](ai.md).

## Why these tradeoffs

- **Celery task chaining**: the five conceptual jobs (ingest, classify, calculate
  metrics, calculate risk, detect anomalies) run as sequential stages inside one Celery
  task rather than five separately queued tasks. Simpler operationally for a
  single-dataset import, each stage's outcome is still logged and any stage's failure
  marks the whole job `FAILED` with the responsible stage recorded.
- **Denormalized `sender_email`/`recipient_email` on `email_events`**: kept alongside
  the FK to `senders`/`recipients` because analytical queries, CSV export, and search
  read the raw string constantly; a join for every row would be wasteful at the target
  scale (spec asks the design to tolerate 100M+ events eventually).
- **Postgres now, ClickHouse-ready later**: the analytics layer is entirely SQL through
  SQLAlchemy Core/ORM against well-indexed tables. If/when raw event volume outgrows
  Postgres for ad hoc analytical queries, `email_events` plus the aggregation jobs can
  move to ClickHouse behind the same `app/analytics` function signatures without
  touching the API or frontend.
