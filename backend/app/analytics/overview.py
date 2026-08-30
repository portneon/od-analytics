from __future__ import annotations

import uuid

from sqlalchemy import case, func, select
from sqlalchemy.orm import Session

from app.analytics.rates import compute_rates
from app.models.email_event import EmailEvent, EmailStatus


def get_overview(db: Session, dataset_id: uuid.UUID) -> dict:
    total = func.count(EmailEvent.id)
    successful = func.sum(case((EmailEvent.status == EmailStatus.SUCCESS, 1), else_=0))
    hard = func.sum(case((EmailEvent.status == EmailStatus.HARD_BOUNCE, 1), else_=0))
    soft = func.sum(case((EmailEvent.status == EmailStatus.SOFT_BOUNCE, 1), else_=0))
    failures = func.sum(case((EmailEvent.status.in_([EmailStatus.FAILED, EmailStatus.DEFERRED]), 1), else_=0))
    unique_recipients = func.count(func.distinct(EmailEvent.recipient_id))
    unique_senders = func.count(func.distinct(EmailEvent.sender_id))
    unique_subjects = func.count(func.distinct(EmailEvent.subject_id))
    duplicates = func.sum(case((EmailEvent.is_duplicate.is_(True), 1), else_=0))
    retries = func.sum(case((EmailEvent.is_retry.is_(True), 1), else_=0))

    stmt = select(
        total, successful, hard, soft, failures, unique_recipients, unique_senders, unique_subjects, duplicates, retries
    ).where(EmailEvent.dataset_id == dataset_id)

    row = db.execute(stmt).one()
    total_v, succ_v, hard_v, soft_v, fail_v, uniq_r, uniq_s, uniq_subj, dup_v, retry_v = (int(v or 0) for v in row)

    rates = compute_rates(total=total_v, successful=succ_v, hard_bounces=hard_v, soft_bounces=soft_v, failures=fail_v)

    return {
        "total_emails": total_v,
        "unique_recipients": uniq_r,
        "unique_senders": uniq_s,
        "unique_subjects": uniq_subj,
        "successful": succ_v,
        "hard_bounces": hard_v,
        "soft_bounces": soft_v,
        "failures": fail_v,
        "duplicate_rows": dup_v,
        "retry_rows": retry_v,
        **rates,
    }
