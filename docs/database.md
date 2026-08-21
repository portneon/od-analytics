# Database

PostgreSQL, managed entirely through Alembic migrations (`backend/alembic/versions/`).
Models live in `backend/app/models/` and are the source of truth for `alembic
revision --autogenerate`.

## Multi-tenancy

Every tenant-owned table has a `tenant_id` column (see `app/models/base.py`'s
`TenantScopedMixin` for the convention). `tenant_id` is **never** accepted from request
input — `app/core/deps.py`'s `get_current_user` derives it from the JWT, and every
repository/analytics/service function takes it as an explicit parameter, scoping every
query. Cross-tenant access attempts return `404 DATASET_NOT_FOUND` (or equivalent),
never a permission error that would confirm the resource exists.

## Core tables

- `tenants`, `users` — organizations and their members (`ADMIN`/`EXECUTIVE`/`ANALYST`/`VIEWER`)
- `datasets`, `import_jobs` — one row per CSV upload and its processing job/status
- `senders`, `recipients`, `subjects`, `domains` — normalized dimension tables
- `application_category_rules` — tenant-configurable subject → workflow category rules
- `email_events` — the primary fact table (see indexing below)
- `daily_email_metrics`, `hourly_email_metrics`, `recipient_metrics`, `domain_metrics`,
  `subject_metrics`, `sender_metrics`, `bounce_reason_metrics`, `infrastructure_metrics`,
  `application_metrics` — materialized aggregates, recomputed by the `CALCULATE_METRICS`
  job after each import (idempotent upsert, safe to re-run)
- `anomalies` — detected anomalies with explanation/contributors/recommendations

## Indexing

`email_events` carries indexes on `tenant_id`, `dataset_id`, `event_time`,
`recipient_id`, `sender_id`, `subject_id`, `domain_id`, `status`, `bounce_code`,
`remote_ip`, `raw_record_hash`, `retry_group_id`, plus compound indexes matching actual
query patterns (`tenant_id, dataset_id, event_time` for timeline queries; `tenant_id,
recipient_id` for recipient drill-down; `tenant_id, status` for status filtering).
Every materialized metrics table has a unique constraint on its natural key
(`tenant_id, dataset_id, <dimension>`) so upserts are conflict-safe.

## Data integrity rules enforced in code, not just schema

- Duplicate detection is hash-based (`raw_record_hash`, from stable identity fields
  bucketed by timestamp) and **marks** duplicates rather than deleting them.
- Retry detection is heuristic/probabilistic (`retry_group_id`, `retry_count`,
  `is_retry`) — same sender/recipient/subject within a configurable window — and is
  presented as such, never as confirmed fact.
- Malformed or incomplete rows are never silently dropped: they're excluded from the
  analytical fact table but fully visible in the dataset's `quality_report` (issue
  samples with row index, field, and raw value).
