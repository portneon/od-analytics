from __future__ import annotations

import uuid
from datetime import date as date_type

from fastapi import APIRouter, Depends, Query
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.analytics import domains as domains_analytics
from app.analytics import recipients as recipients_analytics
from app.core.config import settings
from app.core.database import get_db
from app.core.deps import ApiError
from app.intelligence.insights import generate_executive_insights
from app.intelligence.root_cause import analyze_root_cause
from app.models.anomaly import Anomaly
from app.models.email_event import EmailEvent
from app.schemas.common import ok
from app.services.dataset_service import get_dataset_or_404
from fastapi import status

router = APIRouter(prefix="/datasets/{dataset_id}", tags=["drilldown"])


@router.get("/recipients/{recipient_id}")
def recipient_profile(dataset_id: uuid.UUID, recipient_id: uuid.UUID, db: Session = Depends(get_db)):
    get_dataset_or_404(db, dataset_id=dataset_id)
    profile = recipients_analytics.get_recipient_profile(db, dataset_id, recipient_id)
    if profile is None:
        raise ApiError(status.HTTP_404_NOT_FOUND, "RECIPIENT_NOT_FOUND", "Recipient was not found")
    return ok(profile)


@router.get("/domains/{domain_id}")
def domain_profile(dataset_id: uuid.UUID, domain_id: uuid.UUID, db: Session = Depends(get_db)):
    get_dataset_or_404(db, dataset_id=dataset_id)
    profile = domains_analytics.get_domain_profile(db, dataset_id, domain_id)
    if profile is None:
        raise ApiError(status.HTTP_404_NOT_FOUND, "DOMAIN_NOT_FOUND", "Domain was not found")
    return ok(profile)


@router.get("/events")
def list_events(
    dataset_id: uuid.UUID,
    recipient_id: uuid.UUID | None = None,
    domain_id: uuid.UUID | None = None,
    subject_id: uuid.UUID | None = None,
    status_filter: str | None = Query(default=None, alias="status"),
    bounce_type: str | None = None,
    date_from: date_type | None = None,
    date_to: date_type | None = None,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=50, ge=1, le=500),
    db: Session = Depends(get_db),
):
    get_dataset_or_404(db, dataset_id=dataset_id)
    page_size = min(page_size, settings.MAX_PAGE_SIZE)

    filters = [EmailEvent.dataset_id == dataset_id]
    if recipient_id:
        filters.append(EmailEvent.recipient_id == recipient_id)
    if domain_id:
        filters.append(EmailEvent.domain_id == domain_id)
    if subject_id:
        filters.append(EmailEvent.subject_id == subject_id)
    if status_filter:
        filters.append(EmailEvent.status == status_filter)
    if bounce_type:
        filters.append(EmailEvent.bounce_type == bounce_type)
    if date_from:
        filters.append(EmailEvent.event_time >= date_from)
    if date_to:
        filters.append(EmailEvent.event_time <= date_to)

    from sqlalchemy import func

    total = db.execute(select(func.count(EmailEvent.id)).where(*filters)).scalar_one()
    rows = db.execute(
        select(EmailEvent).where(*filters).order_by(EmailEvent.event_time.desc()).offset((page - 1) * page_size).limit(page_size)
    ).scalars().all()

    items = [_serialize_event(e) for e in rows]
    return ok(items, meta={"page": page, "page_size": page_size, "total": total, "total_pages": (total + page_size - 1) // page_size})


@router.get("/events/{event_id}")
def event_detail(dataset_id: uuid.UUID, event_id: uuid.UUID, db: Session = Depends(get_db)):
    get_dataset_or_404(db, dataset_id=dataset_id)
    event = db.execute(
        select(EmailEvent).where(EmailEvent.dataset_id == dataset_id, EmailEvent.id == event_id)
    ).scalar_one_or_none()
    if event is None:
        raise ApiError(status.HTTP_404_NOT_FOUND, "EVENT_NOT_FOUND", "Event was not found")
    detail = _serialize_event(event)
    detail["raw_record"] = event.raw_record
    return ok(detail)


@router.get("/anomalies")
def list_anomalies(dataset_id: uuid.UUID, db: Session = Depends(get_db)):
    get_dataset_or_404(db, dataset_id=dataset_id)
    rows = db.execute(
        select(Anomaly).where(Anomaly.dataset_id == dataset_id).order_by(Anomaly.detected_at.desc())
    ).scalars().all()
    return ok([
        {
            "id": str(a.id),
            "metric": a.metric,
            "entity_type": a.entity_type,
            "entity_id": a.entity_id,
            "observed_value": a.observed_value,
            "expected_value": a.expected_value,
            "deviation": a.deviation,
            "method": a.method,
            "severity": a.severity.value,
            "period_start": a.period_start.isoformat() if a.period_start else None,
            "period_end": a.period_end.isoformat() if a.period_end else None,
            "explanation": a.explanation,
            "contributors": a.contributors,
            "recommendations": a.recommendations,
            "detected_at": a.detected_at.isoformat(),
        }
        for a in rows
    ])


@router.get("/insights")
def list_insights(dataset_id: uuid.UUID, db: Session = Depends(get_db)):
    get_dataset_or_404(db, dataset_id=dataset_id)
    return ok(generate_executive_insights(db, dataset_id))


@router.get("/root-cause")
def root_cause(
    dataset_id: uuid.UUID,
    metric: str = Query(default="bounce_rate", pattern="^(bounce_rate|failure_rate)$"),
    on_date: date_type | None = None,
    db: Session = Depends(get_db),
):
    get_dataset_or_404(db, dataset_id=dataset_id)
    return ok(analyze_root_cause(db, dataset_id, metric=metric, on_date=on_date))


def _serialize_event(e: EmailEvent) -> dict:
    return {
        "id": str(e.id),
        "event_time": e.event_time.isoformat(),
        "sender_email": e.sender_email,
        "recipient_email": e.recipient_email,
        "status": e.status.value,
        "bounce_type": e.bounce_type.value if hasattr(e.bounce_type, "value") else e.bounce_type,
        "bounce_code": e.bounce_code,
        "bounce_category": e.bounce_category.value if hasattr(e.bounce_category, "value") else e.bounce_category,
        "bounce_reason": e.bounce_reason,
        "remote_ip": e.remote_ip,
        "remote_mta": e.remote_mta,
        "relay_server": e.relay_server,
        "mail_reference": e.mail_reference,
        "processing_time": e.processing_time,
        "is_retry": e.is_retry,
        "retry_group_id": e.retry_group_id,
        "retry_count": e.retry_count,
        "is_duplicate": e.is_duplicate,
    }
