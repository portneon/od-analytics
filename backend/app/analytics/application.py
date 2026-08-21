from __future__ import annotations

import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.metrics import ApplicationMetrics


def list_application_metrics(db: Session, tenant_id: uuid.UUID, dataset_id: uuid.UUID) -> list[dict]:
    rows = db.execute(
        select(ApplicationMetrics)
        .where(ApplicationMetrics.tenant_id == tenant_id, ApplicationMetrics.dataset_id == dataset_id)
        .order_by(ApplicationMetrics.total_emails.desc())
    ).scalars().all()
    return [
        {
            "category": r.category,
            "total_emails": r.total_emails,
            "successful": r.successful,
            "hard_bounces": r.hard_bounces,
            "soft_bounces": r.soft_bounces,
            "failures": r.failures,
            "delivery_rate": r.delivery_rate,
            "bounce_rate": r.bounce_rate,
            "failure_rate": r.failure_rate,
            "unique_recipients": r.unique_recipients,
        }
        for r in rows
    ]
