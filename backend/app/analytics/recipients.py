from __future__ import annotations

import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.analytics.entities import list_entity_metrics
from app.core.config import settings
from app.models.dimensions import Recipient
from app.models.email_event import EmailEvent
from app.models.metrics import RecipientMetrics


def list_recipients(db: Session, tenant_id: uuid.UUID, dataset_id: uuid.UUID, **kwargs) -> dict:
    result = list_entity_metrics(
        db,
        metrics_model=RecipientMetrics,
        dimension_model=Recipient,
        dimension_id_col_name="recipient_id",
        name_col="email",
        tenant_id=tenant_id,
        dataset_id=dataset_id,
        extra_fields={
            "risk_score": "risk_score",
            "risk_level": "risk_level",
            "first_seen": "first_seen",
            "last_seen": "last_seen",
            "unique_subjects": "unique_subjects",
            "unique_senders": "unique_senders",
        },
        **kwargs,
    )
    for item in result["items"]:
        if item.get("risk_level") is not None and hasattr(item["risk_level"], "value"):
            item["risk_level"] = item["risk_level"].value
        for date_field in ("first_seen", "last_seen"):
            if item.get(date_field) is not None:
                item[date_field] = item[date_field].isoformat()
    return result


def get_recipient_profile(db: Session, tenant_id: uuid.UUID, dataset_id: uuid.UUID, recipient_id: uuid.UUID) -> dict | None:
    recipient = db.execute(
        select(Recipient).where(Recipient.tenant_id == tenant_id, Recipient.id == recipient_id)
    ).scalar_one_or_none()
    if recipient is None:
        return None

    metrics = db.execute(
        select(RecipientMetrics).where(
            RecipientMetrics.tenant_id == tenant_id,
            RecipientMetrics.dataset_id == dataset_id,
            RecipientMetrics.recipient_id == recipient_id,
        )
    ).scalar_one_or_none()

    timeline_rows = db.execute(
        select(EmailEvent)
        .where(EmailEvent.tenant_id == tenant_id, EmailEvent.dataset_id == dataset_id, EmailEvent.recipient_id == recipient_id)
        .order_by(EmailEvent.event_time.desc())
        .limit(settings.MAX_PAGE_SIZE)
    ).scalars().all()

    return {
        "id": str(recipient.id),
        "email": recipient.email,
        "domain": recipient.domain,
        "metrics": None if metrics is None else {
            "total_emails": metrics.total_emails,
            "successful": metrics.successful,
            "hard_bounces": metrics.hard_bounces,
            "soft_bounces": metrics.soft_bounces,
            "failures": metrics.failures,
            "delivery_rate": metrics.delivery_rate,
            "bounce_rate": metrics.bounce_rate,
            "failure_rate": metrics.failure_rate,
            "risk_score": metrics.risk_score,
            "risk_level": metrics.risk_level.value if metrics.risk_level else None,
            "risk_reasons": metrics.risk_reasons or [],
            "first_seen": metrics.first_seen.isoformat() if metrics.first_seen else None,
            "last_seen": metrics.last_seen.isoformat() if metrics.last_seen else None,
            "unique_subjects": metrics.unique_subjects,
            "unique_senders": metrics.unique_senders,
        },
        "timeline": [
            {
                "id": str(e.id),
                "event_time": e.event_time.isoformat(),
                "status": e.status.value,
                "subject": None,
                "bounce_category": e.bounce_category.value if e.bounce_category else None,
            }
            for e in timeline_rows
        ],
    }
