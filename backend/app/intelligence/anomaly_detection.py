"""Statistical anomaly detection (spec section 38).

MVP implementation: rolling population z-score over the dataset's own daily
time series, plus IQR as a corroborating signal, plus one-sided z-score
across entities (domains/subjects/senders/infrastructure) with enough volume
to be statistically meaningful. Isolation Forest / EWMA / seasonality-aware
detection are natural follow-ons once there is enough multi-dataset history
per tenant to make them worthwhile -- not needed for a single-import MVP.
"""
from __future__ import annotations

import uuid

import numpy as np
from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.logging import get_logger
from app.models.anomaly import Anomaly, AnomalySeverity
from app.models.dimensions import Domain, Sender, Subject
from app.models.metrics import DailyEmailMetrics, DomainMetrics, SenderMetrics, SubjectMetrics

logger = get_logger(__name__)

# Minimum total_emails an entity needs before its bounce/failure rate is
# treated as statistically meaningful rather than noise from a tiny sample.
MIN_ENTITY_VOLUME_FOR_ANOMALY = 20


def _z_score(value: float, mean: float, std: float) -> float:
    if std == 0:
        return 0.0
    return (value - mean) / std


def _severity_for_abs_z(abs_z: float) -> AnomalySeverity | None:
    threshold = settings.ANOMALY_Z_SCORE_THRESHOLD
    if abs_z < threshold:
        return None
    if abs_z >= threshold + 1.5:
        return AnomalySeverity.CRITICAL
    if abs_z >= threshold + 1.0:
        return AnomalySeverity.HIGH
    if abs_z >= threshold + 0.5:
        return AnomalySeverity.MEDIUM
    return AnomalySeverity.LOW


def _pct_change(observed: float, expected: float) -> float:
    if expected == 0:
        return 0.0 if observed == 0 else 100.0
    return round(((observed - expected) / expected) * 100, 1)


def _detect_daily_metric_anomalies(
    tenant_id: uuid.UUID, dataset_id: uuid.UUID, daily_rows: list[DailyEmailMetrics], metric: str
) -> list[dict]:
    if len(daily_rows) < settings.ANOMALY_MIN_HISTORY_POINTS:
        return []

    values = np.array([getattr(r, metric) for r in daily_rows], dtype=float)
    mean, std = float(values.mean()), float(values.std())
    q1, q3 = float(np.percentile(values, 25)), float(np.percentile(values, 75))
    iqr = q3 - q1
    lower_fence = q1 - settings.ANOMALY_IQR_MULTIPLIER * iqr
    upper_fence = q3 + settings.ANOMALY_IQR_MULTIPLIER * iqr

    anomalies = []
    for row, raw_value in zip(daily_rows, values):
        value = float(raw_value)
        z = _z_score(value, mean, std)
        severity = _severity_for_abs_z(abs(z))
        outside_iqr = value < lower_fence or value > upper_fence
        if severity is None or not outside_iqr:
            continue
        direction = "increased" if value > mean else "decreased"
        pct = _pct_change(value, mean)
        anomalies.append({
            "id": uuid.uuid4(),
            "tenant_id": tenant_id,
            "dataset_id": dataset_id,
            "metric": metric,
            "entity_type": "overall",
            "entity_id": None,
            "observed_value": value,
            "expected_value": round(mean, 2),
            "deviation": round(z, 2),
            "method": "z_score+iqr",
            "severity": severity,
            "period_start": row.date,
            "period_end": row.date,
            "explanation": (
                f"{metric.replace('_', ' ').title()} on {row.date} {direction} to {value:.2f} "
                f"({pct:+.1f}% vs the dataset average of {mean:.2f})."
            ),
            "contributors": None,
            "recommendations": _recommendations_for_metric(metric),
        })
    return anomalies


def _recommendations_for_metric(metric: str) -> list[str]:
    if metric == "bounce_rate":
        return ["Review the top failing domains and recipients for this period", "Inspect bounce reasons for common causes"]
    if metric == "failure_rate":
        return ["Check infrastructure components (relay/MTA) active during this period", "Review affected subject/application workflows"]
    if metric == "total_emails":
        return ["Confirm whether a scheduled/bulk send explains the volume change"]
    return ["Investigate contributing dimensions via root-cause analysis"]


def _detect_entity_anomalies(
    tenant_id: uuid.UUID, dataset_id: uuid.UUID, rows: list, entity_type: str, name_lookup: dict[uuid.UUID, str], id_field: str
) -> list[dict]:
    eligible = [r for r in rows if r.total_emails >= MIN_ENTITY_VOLUME_FOR_ANOMALY]
    if len(eligible) < 3:
        return []

    rates = np.array([r.bounce_rate for r in eligible], dtype=float)
    mean, std = float(rates.mean()), float(rates.std())

    anomalies = []
    for row, raw_rate in zip(eligible, rates):
        rate = float(raw_rate)
        z = _z_score(rate, mean, std)
        if z < settings.ANOMALY_Z_SCORE_THRESHOLD:  # one-sided: only "worse than normal" is actionable
            continue
        severity = _severity_for_abs_z(abs(z)) or AnomalySeverity.LOW
        entity_id = getattr(row, id_field)
        label = name_lookup.get(entity_id, str(entity_id))
        anomalies.append({
            "id": uuid.uuid4(),
            "tenant_id": tenant_id,
            "dataset_id": dataset_id,
            "metric": "bounce_rate",
            "entity_type": entity_type,
            "entity_id": str(entity_id),
            "observed_value": rate,
            "expected_value": round(mean, 2),
            "deviation": round(z, 2),
            "method": "z_score",
            "severity": severity,
            "period_start": None,
            "period_end": None,
            "explanation": (
                f"{label} has a bounce rate of {rate:.1f}%, well above the dataset average of "
                f"{mean:.1f}% across comparable {entity_type}s."
            ),
            "contributors": None,
            "recommendations": [f"Investigate recent {entity_type} activity for {label}"],
        })
    return anomalies


def detect_anomalies(db: Session, tenant_id: uuid.UUID, dataset_id: uuid.UUID) -> int:
    db.execute(delete(Anomaly).where(Anomaly.tenant_id == tenant_id, Anomaly.dataset_id == dataset_id))

    daily_rows = list(
        db.execute(
            select(DailyEmailMetrics)
            .where(DailyEmailMetrics.tenant_id == tenant_id, DailyEmailMetrics.dataset_id == dataset_id)
            .order_by(DailyEmailMetrics.date)
        ).scalars()
    )

    all_anomalies: list[dict] = []
    for metric in ("total_emails", "bounce_rate", "failure_rate"):
        all_anomalies.extend(_detect_daily_metric_anomalies(tenant_id, dataset_id, daily_rows, metric))

    domain_rows = list(db.execute(select(DomainMetrics).where(DomainMetrics.tenant_id == tenant_id, DomainMetrics.dataset_id == dataset_id)).scalars())
    domain_names = {d.id: d.domain for d in db.execute(select(Domain).where(Domain.tenant_id == tenant_id)).scalars()}
    all_anomalies.extend(_detect_entity_anomalies(tenant_id, dataset_id, domain_rows, "domain", domain_names, "domain_id"))

    subject_rows = list(db.execute(select(SubjectMetrics).where(SubjectMetrics.tenant_id == tenant_id, SubjectMetrics.dataset_id == dataset_id)).scalars())
    subject_names = {s.id: s.subject for s in db.execute(select(Subject).where(Subject.tenant_id == tenant_id)).scalars()}
    all_anomalies.extend(_detect_entity_anomalies(tenant_id, dataset_id, subject_rows, "subject", subject_names, "subject_id"))

    sender_rows = list(db.execute(select(SenderMetrics).where(SenderMetrics.tenant_id == tenant_id, SenderMetrics.dataset_id == dataset_id)).scalars())
    sender_names = {s.id: s.email for s in db.execute(select(Sender).where(Sender.tenant_id == tenant_id)).scalars()}
    all_anomalies.extend(_detect_entity_anomalies(tenant_id, dataset_id, sender_rows, "sender", sender_names, "sender_id"))

    if all_anomalies:
        db.bulk_insert_mappings(Anomaly, all_anomalies)
    db.flush()
    logger.info("anomalies.detected", dataset_id=str(dataset_id), count=len(all_anomalies))
    return len(all_anomalies)
