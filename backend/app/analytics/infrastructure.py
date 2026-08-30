from __future__ import annotations

import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.metrics import InfrastructureMetrics


def list_infrastructure(db: Session, dataset_id: uuid.UUID, component_type: str | None = None) -> list[dict]:
    stmt = select(InfrastructureMetrics).where(InfrastructureMetrics.dataset_id == dataset_id)
    if component_type:
        stmt = stmt.where(InfrastructureMetrics.component_type == component_type)
    stmt = stmt.order_by(InfrastructureMetrics.total_emails.desc())

    rows = db.execute(stmt).scalars().all()
    return [
        {
            "component_type": r.component_type,
            "component_value": r.component_value,
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
