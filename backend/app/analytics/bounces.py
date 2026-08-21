from __future__ import annotations

import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.metrics import BounceReasonMetrics

# Executive-friendly translation of technical bounce categories (spec section 83):
# the dashboard should never force a non-technical user to interpret a raw
# SMTP code -- analysts can still expand a row to see it.
BUSINESS_LABELS: dict[str, str] = {
    "MAILBOX_NOT_FOUND": "Recipient mailbox does not exist",
    "INVALID_DOMAIN": "Recipient domain is invalid or unreachable",
    "MAILBOX_FULL": "Recipient mailbox is full",
    "RATE_LIMITED": "Sending was rate-limited by the receiving server",
    "POLICY_REJECTION": "Rejected by the receiving server's policy",
    "SPAM_REJECTION": "Flagged as spam by the receiving server",
    "DNS_ERROR": "Receiving domain's mail server could not be resolved",
    "TEMPORARY_FAILURE": "Temporary delivery failure",
    "AUTHENTICATION_FAILURE": "Sender authentication (SPF/DKIM/DMARC) failed",
    "BLOCKED": "Blocked by the receiving server",
    "NONE": "No bounce",
    "UNKNOWN": "Reason could not be determined",
}


def list_bounce_reasons(db: Session, tenant_id: uuid.UUID, dataset_id: uuid.UUID) -> list[dict]:
    rows = db.execute(
        select(BounceReasonMetrics)
        .where(BounceReasonMetrics.tenant_id == tenant_id, BounceReasonMetrics.dataset_id == dataset_id)
        .order_by(BounceReasonMetrics.count.desc())
    ).scalars().all()
    return [
        {
            "bounce_category": r.bounce_category,
            "business_label": BUSINESS_LABELS.get(r.bounce_category, r.bounce_category),
            "bounce_code": r.bounce_code,
            "bounce_type": r.bounce_type,
            "count": r.count,
            "percent_of_total": r.percent_of_total,
        }
        for r in rows
    ]
