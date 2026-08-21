# Ingestion & ETL

## Canonical schema

`app/schemas/canonical.py` defines `CanonicalEmailEvent` — the only shape the rest of
the platform (analytics, intelligence, AI) ever sees. Every source adapter's job is to
produce a stream of these; nothing downstream knows Zoho's column names exist.

```
Zoho CSV ──▶ ZohoAdapter ──▶ CanonicalEmailEvent ◀── (future) Gmail/SES/SendGrid adapters
```

Adding a new provider means implementing `app/ingestion/adapters/base.py`'s
`SourceAdapter` interface (`detect(columns)`, `parse(df, mapping, ...)`) and registering
it in `app/ingestion/registry.py` — no changes anywhere else.

## Schema detection

`app/ingestion/schema_mapper.py` matches source CSV headers against an alias table per
canonical field (case/whitespace/punctuation-insensitive). This is what lets the
platform ingest CSVs with slightly different Zoho export column names without a code
change — extend `CANONICAL_FIELD_ALIASES` (or move it to a per-tenant DB-configured
table later) rather than hardcoding column name assumptions into the analytics layer.

## Pipeline stages

`app/ingestion/pipeline.py` runs, per dataset:

1. **Load & validate** the CSV (`csv_loader.py`) — extension, size, structural sanity.
   Everything is read as strings; type coercion happens per-field downstream so a bad
   value produces a data-quality issue instead of a silent null.
2. **Detect schema** — map columns to canonical fields.
3. **Parse & normalize** — trim whitespace, lowercase/normalize emails and domains,
   parse timestamps (multiple known formats, then a fuzzy fallback), normalize blank
   strings to `null`.
4. **Classify bounces** (`bounce_classifier.py`) — deterministic, rule-based:
   - Enhanced SMTP status code (`5.1.1` etc.) matched against a category table first.
   - SMTP class digit (`4xx`/`5xx`) as a soft/hard hint.
   - Keyword matching against the raw bounce reason text as a fallback.
   - Only genuinely unclassifiable cases fall through to `UNKNOWN` — the AI layer may
     optionally be used to classify these later, but the rule engine is always tried
     first and is what the system ships with by default (no LLM required).
5. **Retry detection** (`retry_detection.py`) — heuristic: same sender/recipient/subject
   within `RETRY_WINDOW_MINUTES` is grouped and flagged as a *probable* retry, never
   asserted as certain.
6. **Duplicate detection** (`hashing.py`) — SHA-256 over stable identity fields
   (tenant, sender, recipient, subject, timestamp bucket, mail reference). Duplicates
   are marked (`is_duplicate`), never deleted.
7. **Validate & persist** — malformed emails and rows missing required fields
   (recipient, timestamp) are excluded from `email_events` but never silently dropped:
   every issue is recorded in the dataset's `DataQualityReport` with row index, field,
   issue type, and raw value.
8. **Application/workflow classification** (`application_classifier.py`) — subjects are
   classified into workflow categories (Attendance, Payment, Admission, Employee, ERP,
   Notification, Cron, Other by default) via configurable keyword rules
   (`application_category_rules` table), not a hardcoded closed set.

## Data quality

`DataQualityReport` (`app/schemas/data_quality.py`) is produced for every import and
persisted on the `Dataset` row (`GET /datasets/{id}/quality`). Critically: if a source
CSV has no open/click columns, `missing_open_data`/`missing_click_data` are `true` and
the UI shows "Not available in source data" — the platform never fabricates a `0%` open
rate for data it was never given.
