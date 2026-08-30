"""Bulk get-or-create for the dimension tables (senders/recipients/subjects/domains).

Batches lookups and inserts per import rather than one query per row --
essential once datasets reach hundreds of thousands of rows.
"""
from __future__ import annotations

import uuid
from dataclasses import dataclass, field

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.orm import Session

from app.ingestion.application_classifier import CategoryRule, classify_subject
from app.ingestion.normalize import extract_domain
from app.models.dimensions import Domain, Recipient, Sender, Subject
from app.schemas.canonical import CanonicalEmailEvent


@dataclass
class DimensionCache:
    sender_ids: dict[str, uuid.UUID] = field(default_factory=dict)
    recipient_ids: dict[str, uuid.UUID] = field(default_factory=dict)
    subject_ids: dict[str, uuid.UUID] = field(default_factory=dict)
    domain_ids: dict[str, uuid.UUID] = field(default_factory=dict)


def _load_existing(db: Session, model, key_col: str, values: set[str]) -> dict[str, uuid.UUID]:
    if not values:
        return {}
    column = getattr(model, key_col)
    rows = db.execute(select(column, model.id).where(column.in_(values))).all()
    return {row[0]: row[1] for row in rows}


def _bulk_insert_missing(db: Session, model, key_col: str, rows: list[dict]) -> None:
    if not rows:
        return
    stmt = pg_insert(model).values(rows)
    stmt = stmt.on_conflict_do_nothing(index_elements=[key_col])
    db.execute(stmt)


def _truncate(value: str, max_len: int) -> str:
    return value if len(value) <= max_len else value[:max_len]


def sync_dimensions(
    db: Session,
    events: list[CanonicalEmailEvent],
    category_rules: list[CategoryRule] | None = None,
) -> DimensionCache:
    sender_emails = {e.sender for e in events if e.sender}
    recipient_emails = {e.recipient for e in events if e.recipient}
    subjects = {e.subject for e in events if e.subject}
    domains = {d for d in (e.sender_domain for e in events) if d} | {
        d for d in (e.recipient_domain for e in events) if d
    }

    cache = DimensionCache()
    cache.sender_ids = _load_existing(db, Sender, "email", sender_emails)
    cache.recipient_ids = _load_existing(db, Recipient, "email", recipient_emails)
    cache.subject_ids = _load_existing(db, Subject, "subject", subjects)
    cache.domain_ids = _load_existing(db, Domain, "domain", domains)

    # Emails/domains are pre-validated by the adapter, but truncate the
    # remaining free-text fields (subject in particular) defensively -- an
    # oversized value here would fail the whole bulk insert, same as the
    # bounce_reason case in the ingestion pipeline.
    missing_senders = [
        {"id": uuid.uuid4(), "email": _truncate(e, 320), "domain": _truncate(extract_domain(e) or "", 255)}
        for e in sender_emails
        if e not in cache.sender_ids
    ]
    missing_recipients = [
        {"id": uuid.uuid4(), "email": _truncate(e, 320), "domain": _truncate(extract_domain(e) or "", 255)}
        for e in recipient_emails
        if e not in cache.recipient_ids
    ]
    missing_subjects = [
        {
            "id": uuid.uuid4(),
            "subject": _truncate(s, 998),
            "category": classify_subject(s, category_rules),
        }
        for s in subjects
        if s not in cache.subject_ids
    ]
    missing_domains = [
        {"id": uuid.uuid4(), "domain": _truncate(d, 255)}
        for d in domains
        if d not in cache.domain_ids
    ]

    _bulk_insert_missing(db, Sender, "email", missing_senders)
    _bulk_insert_missing(db, Recipient, "email", missing_recipients)
    _bulk_insert_missing(db, Subject, "subject", missing_subjects)
    _bulk_insert_missing(db, Domain, "domain", missing_domains)
    db.flush()

    # Re-query rather than trust our locally-generated ids: on_conflict_do_nothing
    # means a concurrent import could have won the race, in which case the
    # authoritative id differs from the one we generated.
    if missing_senders:
        cache.sender_ids.update(_load_existing(db, Sender, "email", {r["email"] for r in missing_senders}))
    if missing_recipients:
        cache.recipient_ids.update(
            _load_existing(db, Recipient, "email", {r["email"] for r in missing_recipients})
        )
    if missing_subjects:
        cache.subject_ids.update(
            _load_existing(db, Subject, "subject", {r["subject"] for r in missing_subjects})
        )
    if missing_domains:
        cache.domain_ids.update(_load_existing(db, Domain, "domain", {r["domain"] for r in missing_domains}))

    return cache
