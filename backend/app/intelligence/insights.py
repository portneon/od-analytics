"""Executive Insight Engine (spec section 42).

Turns the top anomalies for a dataset into structured, business-readable
insights: title, severity, observed vs baseline, contributors (from root-
cause analysis), and recommended actions. This is what powers the "3
important things happened" experience on the executive dashboard.
"""
from __future__ import annotations

import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.intelligence.root_cause import analyze_root_cause
from app.models.anomaly import Anomaly, AnomalySeverity

_SEVERITY_ORDER = {
    AnomalySeverity.CRITICAL: 0,
    AnomalySeverity.HIGH: 1,
    AnomalySeverity.MEDIUM: 2,
    AnomalySeverity.LOW: 3,
    AnomalySeverity.INFO: 4,
}

_METRIC_TITLES = {
    "total_emails": "Email volume changed sharply",
    "bounce_rate": "Bounce rate changed sharply",
    "failure_rate": "Failure rate changed sharply",
}


def generate_executive_insights(
    db: Session, dataset_id: uuid.UUID | None = None, limit: int = 5
) -> list[dict]:
    """dataset_id=None scans anomalies across every dataset (the cross-dataset
    executive dashboard); each insight then also carries its dataset_id so
    the caller can link back to the right dataset."""
    conditions = []
    if dataset_id is not None:
        conditions.append(Anomaly.dataset_id == dataset_id)
    stmt = select(Anomaly)
    if conditions:
        stmt = stmt.where(*conditions)
    anomalies = list(db.execute(stmt.order_by(Anomaly.detected_at.desc())).scalars())
    anomalies.sort(key=lambda a: (_SEVERITY_ORDER.get(a.severity, 9), -abs(a.deviation)))

    insights = []
    for anomaly in anomalies[:limit]:
        change_percent = (
            round(((anomaly.observed_value - anomaly.expected_value) / anomaly.expected_value) * 100, 1)
            if anomaly.expected_value
            else None
        )

        contributors = []
        if anomaly.entity_type == "overall" and anomaly.metric in ("bounce_rate", "failure_rate"):
            on_date = anomaly.period_start.date() if hasattr(anomaly.period_start, "date") else anomaly.period_start
            root_cause = analyze_root_cause(db, anomaly.dataset_id, metric=anomaly.metric, on_date=on_date)
            for dim in root_cause.get("dimensions", [])[:2]:
                for c in dim["contributors"][:2]:
                    contributors.append({
                        "dimension": dim["dimension"],
                        "value": c["value"],
                        "contribution_percent": c["contribution_percent"],
                    })

        insights.append({
            "id": str(anomaly.id),
            "dataset_id": str(anomaly.dataset_id),
            "title": _METRIC_TITLES.get(anomaly.metric, f"{anomaly.metric} is anomalous"),
            "severity": anomaly.severity.value,
            "metric": anomaly.metric,
            "entity_type": anomaly.entity_type,
            "entity_id": anomaly.entity_id,
            "observed": anomaly.observed_value,
            "baseline": anomaly.expected_value,
            "change_percent": change_percent,
            "explanation": anomaly.explanation,
            "contributors": contributors,
            "recommendations": anomaly.recommendations or [],
            "detected_at": anomaly.detected_at.isoformat() if anomaly.detected_at else None,
        })
    return insights
