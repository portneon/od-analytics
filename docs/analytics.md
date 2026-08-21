# Analytics & Intelligence

## Materialized aggregation

`app/analytics/aggregation.py`'s `calculate_all_metrics` runs after every ingestion and
computes, via SQL `GROUP BY` against `email_events`:

- **Daily/hourly** volume + delivery/bounce/failure rates, timezone-aware
  (`DEFAULT_TIMEZONE`, default `Asia/Kolkata`; tenant-configurable timezone is a natural
  follow-on but not required for the MVP).
- **Recipient/domain/subject/sender** metrics, each upserted into its own materialized
  table keyed on `(tenant_id, dataset_id, <entity>)`.
- **Bounce reason** breakdown by category/SMTP code, with percent-of-total.
- **Infrastructure** breakdown by `remote_mta`/`relay_server`/`remote_ip`.
- **Application/workflow** breakdown by subject-derived category.

Every dashboard/analytics endpoint reads these tables — never raw `email_events` — so
requests stay fast regardless of dataset size. Re-running aggregation for the same
dataset is idempotent (`ON CONFLICT ... DO UPDATE`).

## Recipient risk engine

`app/intelligence/risk_scoring.py` produces an explainable 0–100 score per recipient
from a weighted combination of: hard bounce count, soft bounce count, failure rate,
consecutive-failure streak, and recency of last failure (exponential half-life decay).
Weights and saturation points are configuration (`app/core/config.py`), not magic
numbers. Every score ships with a human-readable reasons list (e.g. "6 hard bounces",
"3 consecutive recent failures", "Last failure occurred today") — never a bare number.

## Anomaly detection

`app/intelligence/anomaly_detection.py`:

- **Daily metric anomalies**: population z-score + IQR fencing over the dataset's own
  daily time series (volume, bounce rate, failure rate), requiring
  `ANOMALY_MIN_HISTORY_POINTS` days of history before flagging anything.
- **Entity anomalies**: one-sided z-score of bounce rate across domains/subjects/senders
  with enough volume (`MIN_ENTITY_VOLUME_FOR_ANOMALY`) to be statistically meaningful —
  flags entities meaningfully worse than the dataset's own average, not just any
  deviation.

This is intentionally the simplest defensible statistical approach; EWMA,
seasonality-aware detection, and Isolation Forest are natural follow-ons once there's
enough multi-dataset history per tenant to make them worth the complexity.

## Root-cause analysis

`app/intelligence/root_cause.py` breaks down which domains/subjects/bounce-reasons/
infrastructure components contributed the most affected events for a given metric
(optionally scoped to one day), as a percentage of total affected events. Language is
deliberately "associated with"/"contributed to", never "caused" — there is no
controlled experiment here, only correlation.

## Executive insights

`app/intelligence/insights.py` turns the top anomalies into structured,
business-readable insights (title, severity, observed vs. baseline, contributors via
root-cause, recommended actions) — this is what powers "3 important things happened" on
the dashboard.
