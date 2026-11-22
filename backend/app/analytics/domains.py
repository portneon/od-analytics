from __future__ import annotations

import uuid

from sqlalchemy import case, func, select
from sqlalchemy.orm import Session

from app.analytics.entities import list_entity_metrics
from app.core.config import settings
from app.models.dimensions import Domain, Recipient, Subject
from app.models.email_event import EmailEvent, EmailStatus
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

    # What kind of message this domain/institute actually sends -- a
    # breakdown by the readable category (see the WhatsApp adapter's
    # template->category mapping for where that label comes from).
    category_rows = db.execute(
        select(Subject.subject, func.count(EmailEvent.id))
        .join(Subject, EmailEvent.subject_id == Subject.id)
        .where(EmailEvent.dataset_id == dataset_id, EmailEvent.domain_id == domain_id)
        .group_by(Subject.subject)
        .order_by(func.count(EmailEvent.id).desc())
    ).all()
    category_total = sum(count for _, count in category_rows) or 1
    category_breakdown = [
        {"category": name, "count": int(count), "percent": round(count / category_total * 100, 2)}
        for name, count in category_rows
    ]

    # Who within this domain/institute is driving volume and failures --
    # scoped to this domain specifically, not the dataset-wide recipient
    # ranking (a recipient could in principle appear under more than one
    # institute, so this can't just reuse RecipientMetrics).
    failure_expr = func.sum(case((EmailEvent.status.in_([EmailStatus.FAILED, EmailStatus.DEFERRED]), 1), else_=0))
    total_expr = func.count(EmailEvent.id)
    recipient_rows = db.execute(
        select(Recipient.id, Recipient.email, total_expr, failure_expr)
        .join(Recipient, EmailEvent.recipient_id == Recipient.id)
        .where(EmailEvent.dataset_id == dataset_id, EmailEvent.domain_id == domain_id)
        .group_by(Recipient.id, Recipient.email)
        .order_by(total_expr.desc())
        .limit(10)
    ).all()
    top_recipients = [
        {
            "id": str(recipient_id),
            "name": email,
            "total_emails": int(total),
            "failures": int(failures or 0),
            "failure_rate": round((failures or 0) / total * 100, 2) if total else 0.0,
        }
        for recipient_id, email, total, failures in recipient_rows
    ]

    timeline_rows = db.execute(
        select(EmailEvent, Subject.subject)
        .outerjoin(Subject, EmailEvent.subject_id == Subject.id)
        .where(EmailEvent.dataset_id == dataset_id, EmailEvent.domain_id == domain_id)
        .order_by(EmailEvent.event_time.desc())
        .limit(settings.MAX_PAGE_SIZE)
    ).all()

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
        "category_breakdown": category_breakdown,
        "top_recipients": top_recipients,
        "timeline": [
            {
                "id": str(e.id),
                "event_time": e.event_time.isoformat(),
                "recipient_email": e.recipient_email,
                "status": e.status.value,
                "subject": subject_name,
                "bounce_category": e.bounce_category.value if hasattr(e.bounce_category, "value") else e.bounce_category,
            }
            for e, subject_name in timeline_rows
        ],
    }
