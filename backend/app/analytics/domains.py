from __future__ import annotations

import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.analytics.entities import list_entity_metrics
from app.models.dimensions import Domain
from app.models.metrics import DomainMetrics


def list_domains(db: Session, dataset_id: uuid.UUID, **kwargs) -> dict:
    return list_entity_metrics(
        db,
        metrics_model=DomainMetrics,
        dimension_model=Domain,
        dimension_id_col_name="domain_id",
        name_col="domain",
        dataset_id=dataset_id,
        extra_fields={"unique_recipients": "unique_recipients"},
        **kwargs,
    )


def get_domain_profile(db: Session, dataset_id: uuid.UUID, domain_id: uuid.UUID) -> dict | None:
    domain = db.execute(select(Domain).where(Domain.id == domain_id)).scalar_one_or_none()
    if domain is None:
        return None
    metrics = db.execute(
        select(DomainMetrics).where(DomainMetrics.dataset_id == dataset_id, DomainMetrics.domain_id == domain_id)
    ).scalar_one_or_none()
    return {
        "id": str(domain.id),
        "domain": domain.domain,
        "provider": domain.provider,
        "metrics": None if metrics is None else {
            "total_emails": metrics.total_emails,
            "successful": metrics.successful,
            "hard_bounces": metrics.hard_bounces,
            "soft_bounces": metrics.soft_bounces,
            "failures": metrics.failures,
            "delivery_rate": metrics.delivery_rate,
            "bounce_rate": metrics.bounce_rate,
            "failure_rate": metrics.failure_rate,
            "unique_recipients": metrics.unique_recipients,
        },
    }
