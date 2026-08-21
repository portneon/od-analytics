"""Duplicate-detection hashing.

Hash is computed from stable identity fields only (never from status/bounce
fields, which can legitimately differ between a retry and a true duplicate).
The event timestamp is bucketed to `DUPLICATE_TIMESTAMP_BUCKET_SECONDS` so
sub-minute clock jitter in the source export doesn't defeat matching.
"""
from __future__ import annotations

import hashlib
from datetime import datetime

from app.core.config import settings


def compute_raw_record_hash(
    *,
    tenant_id: str,
    sender: str | None,
    recipient: str | None,
    subject: str | None,
    timestamp: datetime,
    mail_reference: str | None,
) -> str:
    bucket_seconds = settings.DUPLICATE_TIMESTAMP_BUCKET_SECONDS
    epoch = int(timestamp.timestamp())
    bucketed = epoch - (epoch % bucket_seconds) if bucket_seconds > 0 else epoch

    parts = [
        tenant_id,
        (sender or "").lower(),
        (recipient or "").lower(),
        (subject or "").strip().lower(),
        str(bucketed),
        (mail_reference or "").strip(),
    ]
    digest_input = "|".join(parts).encode("utf-8")
    return hashlib.sha256(digest_input).hexdigest()
