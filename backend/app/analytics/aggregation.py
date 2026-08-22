"""CALCULATE_METRICS job: aggregates raw email_events into the materialized
metrics tables (daily/hourly/recipient/domain/subject/sender/bounce-reason/
infrastructure/application). Dashboards and analytics endpoints read these
tables instead of scanning email_events on every request.

Idempotent: re-running for the same dataset_id upserts (on_conflict_do_update)
rather than duplicating rows, so a job retry after partial failure is safe.
"""
from __future__ import annotations

import concurrent.futures
import uuid

from sqlalchemy import Date, case, cast, func, select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.orm import Session

from app.analytics.rates import compute_rates
from app.core.config import settings
from app.core.database import SessionLocal
from app.core.logging import get_logger
from app.models.dimensions import Subject
from app.models.email_event import EmailEvent, EmailStatus
from app.models.metrics import (
    ApplicationMetrics,
    BounceReasonMetrics,
    DailyEmailMetrics,
    DomainMetrics,
    HourlyEmailMetrics,
    InfrastructureMetrics,
    RecipientMetrics,
    SenderMetrics,
    SubjectMetrics,
)

logger = get_logger(__name__)


def _status_aggregates():
    total = func.count(EmailEvent.id)
    successful = func.sum(case((EmailEvent.status == EmailStatus.SUCCESS, 1), else_=0))
    hard = func.sum(case((EmailEvent.status == EmailStatus.HARD_BOUNCE, 1), else_=0))
    soft = func.sum(case((EmailEvent.status == EmailStatus.SOFT_BOUNCE, 1), else_=0))
    failures = func.sum(case((EmailEvent.status.in_([EmailStatus.FAILED, EmailStatus.DEFERRED]), 1), else_=0))
    return total, successful, hard, soft, failures


def _row_with_rates(total, successful, hard, soft, failures) -> dict:
    total, successful, hard, soft, failures = (int(v or 0) for v in (total, successful, hard, soft, failures))
    rates = compute_rates(total=total, successful=successful, hard_bounces=hard, soft_bounces=soft, failures=failures)
    return {
        "total_emails": total,
        "successful": successful,
        "hard_bounces": hard,
        "soft_bounces": soft,
        "failures": failures,
        **rates,
    }


def _upsert(db: Session, model, rows: list[dict], conflict_cols: list[str]) -> None:
    if not rows:
        return
    stmt = pg_insert(model).values(rows)
    update_cols = {c.name: getattr(stmt.excluded, c.name) for c in model.__table__.columns if c.name not in ("id", *conflict_cols)}
    stmt = stmt.on_conflict_do_update(index_elements=conflict_cols, set_=update_cols)
    db.execute(stmt)


def calculate_daily_metrics(db: Session, tenant_id: uuid.UUID, dataset_id: uuid.UUID) -> int:
    local_ts = func.timezone(settings.DEFAULT_TIMEZONE, EmailEvent.event_time)
    date_col = cast(local_ts, Date).label("date")
    total, successful, hard, soft, failures = _status_aggregates()
    unique_recipients = func.count(func.distinct(EmailEvent.recipient_id))

    stmt = (
        select(date_col, total, successful, hard, soft, failures, unique_recipients)
        .where(EmailEvent.tenant_id == tenant_id, EmailEvent.dataset_id == dataset_id)
        .group_by(date_col)
    )
    rows = []
    for date_val, total_v, succ_v, hard_v, soft_v, fail_v, uniq_v in db.execute(stmt).all():
        rows.append({
            "id": uuid.uuid4(),
            "tenant_id": tenant_id,
            "dataset_id": dataset_id,
            "date": date_val,
            "unique_recipients": int(uniq_v or 0),
            **_row_with_rates(total_v, succ_v, hard_v, soft_v, fail_v),
        })
    _upsert(db, DailyEmailMetrics, rows, ["tenant_id", "dataset_id", "date"])
    return len(rows)


def calculate_hourly_metrics(db: Session, tenant_id: uuid.UUID, dataset_id: uuid.UUID) -> int:
    local_ts = func.timezone(settings.DEFAULT_TIMEZONE, EmailEvent.event_time)
    date_col = cast(local_ts, Date).label("date")
    hour_col = func.extract("hour", local_ts).label("hour")
    total, successful, hard, soft, failures = _status_aggregates()

    stmt = (
        select(date_col, hour_col, total, successful, hard, soft, failures)
        .where(EmailEvent.tenant_id == tenant_id, EmailEvent.dataset_id == dataset_id)
        .group_by(date_col, hour_col)
    )
    rows = []
    for date_val, hour_v, total_v, succ_v, hard_v, soft_v, fail_v in db.execute(stmt).all():
        rows.append({
            "id": uuid.uuid4(),
            "tenant_id": tenant_id,
            "dataset_id": dataset_id,
            "date": date_val,
            "hour": int(hour_v),
            **_row_with_rates(total_v, succ_v, hard_v, soft_v, fail_v),
        })
    _upsert(db, HourlyEmailMetrics, rows, ["tenant_id", "dataset_id", "date", "hour"])
    return len(rows)


def calculate_recipient_metrics(db: Session, tenant_id: uuid.UUID, dataset_id: uuid.UUID) -> int:
    total, successful, hard, soft, failures = _status_aggregates()
    stmt = (
        select(
            EmailEvent.recipient_id,
            total, successful, hard, soft, failures,
            func.min(EmailEvent.event_time).label("first_seen"),
            func.max(EmailEvent.event_time).label("last_seen"),
            func.count(func.distinct(EmailEvent.subject_id)).label("unique_subjects"),
            func.count(func.distinct(EmailEvent.sender_id)).label("unique_senders"),
        )
        .where(
            EmailEvent.tenant_id == tenant_id,
            EmailEvent.dataset_id == dataset_id,
            EmailEvent.recipient_id.is_not(None),
        )
        .group_by(EmailEvent.recipient_id)
    )
    rows = []
    for recipient_id, total_v, succ_v, hard_v, soft_v, fail_v, first_seen, last_seen, uniq_subj, uniq_send in db.execute(stmt).all():
        rows.append({
            "id": uuid.uuid4(),
            "tenant_id": tenant_id,
            "dataset_id": dataset_id,
            "recipient_id": recipient_id,
            "first_seen": first_seen,
            "last_seen": last_seen,
            "unique_subjects": int(uniq_subj or 0),
            "unique_senders": int(uniq_send or 0),
            **_row_with_rates(total_v, succ_v, hard_v, soft_v, fail_v),
        })
    _upsert(db, RecipientMetrics, rows, ["tenant_id", "dataset_id", "recipient_id"])
    return len(rows)


def calculate_domain_metrics(db: Session, tenant_id: uuid.UUID, dataset_id: uuid.UUID) -> int:
    total, successful, hard, soft, failures = _status_aggregates()
    stmt = (
        select(
            EmailEvent.domain_id, total, successful, hard, soft, failures,
            func.count(func.distinct(EmailEvent.recipient_id)).label("unique_recipients"),
        )
        .where(EmailEvent.tenant_id == tenant_id, EmailEvent.dataset_id == dataset_id, EmailEvent.domain_id.is_not(None))
        .group_by(EmailEvent.domain_id)
    )
    rows = []
    for domain_id, total_v, succ_v, hard_v, soft_v, fail_v, uniq_recip in db.execute(stmt).all():
        rows.append({
            "id": uuid.uuid4(),
            "tenant_id": tenant_id,
            "dataset_id": dataset_id,
            "domain_id": domain_id,
            "unique_recipients": int(uniq_recip or 0),
            **_row_with_rates(total_v, succ_v, hard_v, soft_v, fail_v),
        })
    _upsert(db, DomainMetrics, rows, ["tenant_id", "dataset_id", "domain_id"])
    return len(rows)


def calculate_sender_metrics(db: Session, tenant_id: uuid.UUID, dataset_id: uuid.UUID) -> int:
    total, successful, hard, soft, failures = _status_aggregates()
    stmt = (
        select(
            EmailEvent.sender_id, total, successful, hard, soft, failures,
            func.count(func.distinct(EmailEvent.recipient_id)).label("unique_recipients"),
            func.count(func.distinct(EmailEvent.subject_id)).label("unique_subjects"),
        )
        .where(EmailEvent.tenant_id == tenant_id, EmailEvent.dataset_id == dataset_id, EmailEvent.sender_id.is_not(None))
        .group_by(EmailEvent.sender_id)
    )
    rows = []
    for sender_id, total_v, succ_v, hard_v, soft_v, fail_v, uniq_recip, uniq_subj in db.execute(stmt).all():
        rows.append({
            "id": uuid.uuid4(),
            "tenant_id": tenant_id,
            "dataset_id": dataset_id,
            "sender_id": sender_id,
            "unique_recipients": int(uniq_recip or 0),
            "unique_subjects": int(uniq_subj or 0),
            **_row_with_rates(total_v, succ_v, hard_v, soft_v, fail_v),
        })
    _upsert(db, SenderMetrics, rows, ["tenant_id", "dataset_id", "sender_id"])
    return len(rows)


def calculate_bounce_reason_metrics(db: Session, tenant_id: uuid.UUID, dataset_id: uuid.UUID) -> int:
    count_col = func.count(EmailEvent.id)
    stmt = (
        select(EmailEvent.bounce_category, EmailEvent.bounce_code, EmailEvent.bounce_type, count_col)
        .where(
            EmailEvent.tenant_id == tenant_id,
            EmailEvent.dataset_id == dataset_id,
            EmailEvent.bounce_type != "NONE",
        )
        .group_by(EmailEvent.bounce_category, EmailEvent.bounce_code, EmailEvent.bounce_type)
    )
    results = db.execute(stmt).all()
    total_bounces = sum(int(c) for *_rest, c in results) or 1

    rows = []
    for category, code, btype, count in results:
        rows.append({
            "id": uuid.uuid4(),
            "tenant_id": tenant_id,
            "dataset_id": dataset_id,
            "bounce_category": category.value if hasattr(category, "value") else str(category),
            "bounce_code": code,
            "bounce_type": btype.value if hasattr(btype, "value") else str(btype),
            "count": int(count),
            "percent_of_total": round((int(count) / total_bounces) * 100, 4),
        })
    _upsert(db, BounceReasonMetrics, rows, ["tenant_id", "dataset_id", "bounce_category", "bounce_code"])
    return len(rows)


def _run_metric(func, tenant_id: uuid.UUID, dataset_id: uuid.UUID) -> tuple[str, int]:
    db = SessionLocal()
    try:
        count = func(db, tenant_id, dataset_id)
        db.commit()
        return func.__name__, count
    finally:
        db.close()

def calculate_all_metrics(db: Session, tenant_id: uuid.UUID, dataset_id: uuid.UUID) -> dict[str, int]:
    metrics_funcs = [
        calculate_daily_metrics,
        calculate_hourly_metrics,
        calculate_recipient_metrics,
        calculate_domain_metrics,
        calculate_sender_metrics,
        calculate_bounce_reason_metrics,
    ]
    
    counts = {}
    with concurrent.futures.ThreadPoolExecutor(max_workers=6) as executor:
        futures = {
            executor.submit(_run_metric, func, tenant_id, dataset_id): func
            for func in metrics_funcs
        }
        for future in concurrent.futures.as_completed(futures):
            name, count = future.result()
            clean_name = name.replace("calculate_", "").replace("_metrics", "")
            counts[clean_name] = count

    logger.info("metrics.calculated", dataset_id=str(dataset_id), **counts)
    return counts
