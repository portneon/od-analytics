"""Cross-dataset executive rollup: the tenant-wide "how is email health
across everything we've imported" view, as opposed to app.analytics.overview
which is scoped to a single dataset. Reuses the same rate math (compute_rates)
and the same insight-generation path (generate_executive_insights) so the
executive dashboard can never drift from the per-dataset numbers it's built
from -- it's a rollup, not a separate calculation.
"""
from __future__ import annotations

import uuid

from sqlalchemy import case, func, select
from sqlalchemy.orm import Session

from app.analytics.rates import compute_rates
from app.intelligence.insights import generate_executive_insights
from app.models.dataset import Dataset, DatasetStatus
from app.models.email_event import EmailEvent, EmailStatus
from app.models.metrics import DailyEmailMetrics

_USABLE_STATUSES = (DatasetStatus.COMPLETED, DatasetStatus.PARTIAL)


def get_executive_daily_timeline(db: Session, tenant_id: uuid.UUID) -> list[dict]:
    """Daily volume/rates summed across every usable dataset for the tenant,
    grouped by calendar date -- the same DailyEmailMetrics rows the
    per-dataset timeline reads, just rolled up instead of filtered to one
    dataset_id, so it can never disagree with the per-dataset charts."""
    usable_ids = select(Dataset.id).where(Dataset.tenant_id == tenant_id, Dataset.status.in_(_USABLE_STATUSES))

    total = func.sum(DailyEmailMetrics.total_emails)
    successful = func.sum(DailyEmailMetrics.successful)
    hard = func.sum(DailyEmailMetrics.hard_bounces)
    soft = func.sum(DailyEmailMetrics.soft_bounces)
    failures = func.sum(DailyEmailMetrics.failures)

    stmt = (
        select(DailyEmailMetrics.date, total, successful, hard, soft, failures)
        .where(DailyEmailMetrics.tenant_id == tenant_id, DailyEmailMetrics.dataset_id.in_(usable_ids))
        .group_by(DailyEmailMetrics.date)
        .order_by(DailyEmailMetrics.date)
    )
    result = []
    for date_val, total_v, succ_v, hard_v, soft_v, fail_v in db.execute(stmt).all():
        total_v, succ_v, hard_v, soft_v, fail_v = (int(v or 0) for v in (total_v, succ_v, hard_v, soft_v, fail_v))
        rates = compute_rates(total=total_v, successful=succ_v, hard_bounces=hard_v, soft_bounces=soft_v, failures=fail_v)
        result.append({
            "date": date_val.isoformat(),
            "total_emails": total_v,
            "successful": succ_v,
            "hard_bounces": hard_v,
            "soft_bounces": soft_v,
            "failures": fail_v,
            **rates,
        })
    return result


def get_executive_summary(db: Session, tenant_id: uuid.UUID, *, insight_limit: int = 8, recent_datasets_limit: int = 8) -> dict:
    datasets = list(
        db.execute(select(Dataset).where(Dataset.tenant_id == tenant_id).order_by(Dataset.created_at.desc())).scalars()
    )
    status_counts: dict[str, int] = {}
    for d in datasets:
        status_counts[d.status.value] = status_counts.get(d.status.value, 0) + 1

    usable_ids = [d.id for d in datasets if d.status in _USABLE_STATUSES]

    total = func.count(EmailEvent.id)
    successful = func.sum(case((EmailEvent.status == EmailStatus.SUCCESS, 1), else_=0))
    hard = func.sum(case((EmailEvent.status == EmailStatus.HARD_BOUNCE, 1), else_=0))
    soft = func.sum(case((EmailEvent.status == EmailStatus.SOFT_BOUNCE, 1), else_=0))
    failures = func.sum(case((EmailEvent.status.in_([EmailStatus.FAILED, EmailStatus.DEFERRED]), 1), else_=0))
    unique_recipients = func.count(func.distinct(EmailEvent.recipient_id))
    unique_domains = func.count(func.distinct(EmailEvent.domain_id))

    if usable_ids:
        row = db.execute(
            select(total, successful, hard, soft, failures, unique_recipients, unique_domains).where(
                EmailEvent.tenant_id == tenant_id, EmailEvent.dataset_id.in_(usable_ids)
            )
        ).one()
        total_v, succ_v, hard_v, soft_v, fail_v, uniq_r, uniq_d = (int(v or 0) for v in row)
    else:
        total_v = succ_v = hard_v = soft_v = fail_v = uniq_r = uniq_d = 0

    rates = compute_rates(total=total_v, successful=succ_v, hard_bounces=hard_v, soft_bounces=soft_v, failures=fail_v)

    insights = generate_executive_insights(db, tenant_id, dataset_id=None, limit=insight_limit)
    dataset_names = {d.id: d.name for d in datasets}
    for insight in insights:
        insight["dataset_name"] = dataset_names.get(uuid.UUID(insight["dataset_id"]))

    recent = [
        {
            "id": str(d.id),
            "name": d.name,
            "status": d.status.value,
            "row_count": d.row_count,
            "date_start": d.date_start.isoformat() if d.date_start else None,
            "date_end": d.date_end.isoformat() if d.date_end else None,
            "created_at": d.created_at.isoformat(),
        }
        for d in datasets[:recent_datasets_limit]
    ]

    needs_attention = status_counts.get("FAILED", 0) + status_counts.get("PARTIAL", 0)

    return {
        "total_datasets": len(datasets),
        "usable_datasets": len(usable_ids),
        "status_counts": status_counts,
        "needs_attention": needs_attention,
        "total_emails": total_v,
        "unique_recipients": uniq_r,
        "unique_domains": uniq_d,
        "successful": succ_v,
        "hard_bounces": hard_v,
        "soft_bounces": soft_v,
        "failures": fail_v,
        **rates,
        "insights": insights,
        "recent_datasets": recent,
    }
