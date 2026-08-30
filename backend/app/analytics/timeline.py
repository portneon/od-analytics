from __future__ import annotations

import uuid
from collections import defaultdict

from sqlalchemy import extract, func, select
from sqlalchemy.orm import Session

from app.analytics.rates import compute_rates
from app.core.config import settings
from app.models.email_event import EmailEvent
from app.models.metrics import DailyEmailMetrics, HourlyEmailMetrics

_DAY_NAMES = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]


def get_daily_timeline(db: Session, dataset_id: uuid.UUID) -> list[dict]:
    stmt = (
        select(DailyEmailMetrics)
        .where(DailyEmailMetrics.dataset_id == dataset_id)
        .order_by(DailyEmailMetrics.date)
    )
    rows = db.execute(stmt).scalars().all()
    return [
        {
            "date": r.date.isoformat(),
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


def get_hourly_timeline(db: Session, dataset_id: uuid.UUID) -> list[dict]:
    """Aggregated across all days in the dataset, bucketed by hour-of-day (0-23)."""
    stmt = select(HourlyEmailMetrics).where(HourlyEmailMetrics.dataset_id == dataset_id)
    rows = db.execute(stmt).scalars().all()

    buckets: dict[int, dict[str, int]] = defaultdict(lambda: {"total_emails": 0, "successful": 0, "hard_bounces": 0, "soft_bounces": 0, "failures": 0})
    for r in rows:
        b = buckets[r.hour]
        b["total_emails"] += r.total_emails
        b["successful"] += r.successful
        b["hard_bounces"] += r.hard_bounces
        b["soft_bounces"] += r.soft_bounces
        b["failures"] += r.failures

    result = []
    for hour in range(24):
        b = buckets.get(hour, {"total_emails": 0, "successful": 0, "hard_bounces": 0, "soft_bounces": 0, "failures": 0})
        rates = compute_rates(total=b["total_emails"], successful=b["successful"], hard_bounces=b["hard_bounces"], soft_bounces=b["soft_bounces"], failures=b["failures"])
        result.append({"hour": hour, **b, **rates})
    return result


def get_day_of_week_timeline(db: Session, dataset_id: uuid.UUID) -> list[dict]:
    local_ts = func.timezone(settings.DEFAULT_TIMEZONE, EmailEvent.event_time)
    dow_col = extract("isodow", local_ts).label("dow")  # 1=Monday .. 7=Sunday
    total = func.count(EmailEvent.id)

    from sqlalchemy import case

    from app.models.email_event import EmailStatus

    successful = func.sum(case((EmailEvent.status == EmailStatus.SUCCESS, 1), else_=0))
    hard = func.sum(case((EmailEvent.status == EmailStatus.HARD_BOUNCE, 1), else_=0))
    soft = func.sum(case((EmailEvent.status == EmailStatus.SOFT_BOUNCE, 1), else_=0))
    failures = func.sum(case((EmailEvent.status.in_([EmailStatus.FAILED, EmailStatus.DEFERRED]), 1), else_=0))

    stmt = (
        select(dow_col, total, successful, hard, soft, failures)
        .where(EmailEvent.dataset_id == dataset_id)
        .group_by(dow_col)
    )
    by_dow = {int(row[0]): row[1:] for row in db.execute(stmt).all()}

    result = []
    for iso_dow in range(1, 8):
        vals = by_dow.get(iso_dow, (0, 0, 0, 0, 0))
        total_v, succ_v, hard_v, soft_v, fail_v = (int(v or 0) for v in vals)
        rates = compute_rates(total=total_v, successful=succ_v, hard_bounces=hard_v, soft_bounces=soft_v, failures=fail_v)
        result.append({
            "day_of_week": _DAY_NAMES[iso_dow - 1],
            "total_emails": total_v,
            "successful": succ_v,
            "hard_bounces": hard_v,
            "soft_bounces": soft_v,
            "failures": fail_v,
            **rates,
        })
    return result
