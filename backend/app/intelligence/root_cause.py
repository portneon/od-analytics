"""Root-cause analysis (spec section 41).

Given a metric that went abnormal (typically bounce_rate or failure_rate,
optionally scoped to a specific date), break down which domains/subjects/
bounce-reasons/infrastructure components contributed the most to the
affected events, as a share of total affected events.

Language discipline matters here: this reports *association*, not causation.
Every contributor is phrased as "associated with" / "contributed to" -- we
have no controlled experiment, so we never say "caused".
"""
from __future__ import annotations

import uuid
from datetime import date as date_type

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.dimensions import Domain, Subject
from app.models.email_event import EmailEvent, EmailStatus

_FAILURE_STATUSES_BY_METRIC = {
    "bounce_rate": [EmailStatus.HARD_BOUNCE, EmailStatus.SOFT_BOUNCE],
    "failure_rate": [EmailStatus.HARD_BOUNCE, EmailStatus.SOFT_BOUNCE, EmailStatus.FAILED, EmailStatus.DEFERRED],
}

TOP_N_PER_DIMENSION = 5


def _contribution_breakdown(db: Session, base_filters: list, group_col, count_only: bool = False) -> list[dict]:
    count_col = func.count(EmailEvent.id)
    stmt = (
        select(group_col, count_col)
        .select_from(EmailEvent)
        .where(*base_filters, group_col.is_not(None))
        .group_by(group_col)
        .order_by(count_col.desc())
        .limit(TOP_N_PER_DIMENSION)
    )
    return [{"value": row[0], "count": int(row[1])} for row in db.execute(stmt).all()]


def analyze_root_cause(
    db: Session,
    tenant_id: uuid.UUID,
    dataset_id: uuid.UUID,
    *,
    metric: str = "bounce_rate",
    on_date: date_type | None = None,
) -> dict:
    failure_statuses = _FAILURE_STATUSES_BY_METRIC.get(metric, _FAILURE_STATUSES_BY_METRIC["bounce_rate"])

    filters = [
        EmailEvent.tenant_id == tenant_id,
        EmailEvent.dataset_id == dataset_id,
        EmailEvent.status.in_(failure_statuses),
    ]
    if on_date is not None:
        filters.append(func.date(EmailEvent.event_time) == on_date)

    total_affected = db.execute(select(func.count(EmailEvent.id)).where(*filters)).scalar_one()
    if total_affected == 0:
        return {
            "metric": metric,
            "date": on_date.isoformat() if on_date else None,
            "total_affected_events": 0,
            "contributors": [],
            "note": "No affected events found for the given metric/period; no root-cause breakdown available.",
        }

    domain_names = {d.id: d.domain for d in db.execute(select(Domain).where(Domain.tenant_id == tenant_id)).scalars()}
    subject_names = {s.id: s.subject for s in db.execute(select(Subject).where(Subject.tenant_id == tenant_id)).scalars()}

    dimensions: list[dict] = []

    for dim_key, group_col, name_lookup in (
        ("domain", EmailEvent.domain_id, domain_names),
        ("subject", EmailEvent.subject_id, subject_names),
        ("bounce_category", EmailEvent.bounce_category, None),
        ("infrastructure_mta", EmailEvent.remote_mta, None),
    ):
        breakdown = _contribution_breakdown(db, filters, group_col)
        contributors = []
        for entry in breakdown:
            raw_value = entry["value"]
            label = name_lookup.get(raw_value, str(raw_value)) if name_lookup else (
                raw_value.value if hasattr(raw_value, "value") else str(raw_value)
            )
            contributors.append({
                "value": label,
                "count": entry["count"],
                "contribution_percent": round((entry["count"] / total_affected) * 100, 1),
            })
        if contributors:
            dimensions.append({"dimension": dim_key, "contributors": contributors})

    return {
        "metric": metric,
        "date": on_date.isoformat() if on_date else None,
        "total_affected_events": total_affected,
        "dimensions": dimensions,
        "note": (
            "Contribution percentages describe association with the affected events, "
            "not confirmed causation."
        ),
    }
