"""End-to-end ETL orchestration: Upload -> Validate -> Detect Schema -> Parse
-> Normalize -> Enrich -> Classify -> Deduplicate -> Validate -> Persist.

Metric calculation and anomaly detection are separate jobs (CALCULATE_METRICS,
DETECT_ANOMALIES) triggered after this pipeline completes -- see
app.workers.tasks.
"""
from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.logging import get_logger
from app.ingestion.application_classifier import CategoryRule
from app.ingestion.csv_loader import load_csv
from app.ingestion.hashing import compute_raw_record_hash
from app.ingestion.registry import get_adapter
from app.ingestion.retry_detection import detect_retries
from app.models.dimensions import ApplicationCategoryRule
from app.models.email_event import EmailEvent, EmailStatus
from app.repositories.dimensions import sync_dimensions
from app.schemas.canonical import CanonicalEmailEvent, CanonicalStatus, ParsedRow
from app.schemas.data_quality import DataQualityReport, IssueSample

logger = get_logger(__name__)

def _truncate(value: str | None, max_len: int) -> str | None:
    """Real-world bounce diagnostic text (esp. Outlook/O365 NDRs) routinely
    exceeds our VARCHAR limits. Truncating here -- the single point where
    every adapter's output becomes an EmailEvent row -- means one long field
    on one row can never fail the whole dataset's bulk insert."""
    if value is None or len(value) <= max_len:
        return value
    return value[:max_len]


_STATUS_MAP = {
    CanonicalStatus.SUCCESS: EmailStatus.SUCCESS,
    CanonicalStatus.HARD_BOUNCE: EmailStatus.HARD_BOUNCE,
    CanonicalStatus.SOFT_BOUNCE: EmailStatus.SOFT_BOUNCE,
    CanonicalStatus.FAILED: EmailStatus.FAILED,
    CanonicalStatus.DEFERRED: EmailStatus.DEFERRED,
    CanonicalStatus.UNKNOWN: EmailStatus.UNKNOWN,
}


@dataclass
class PipelineResult:
    total_rows: int
    processed_rows: int
    failed_rows: int
    duplicate_rows: int
    date_start: datetime | None
    date_end: datetime | None
    quality_report: DataQualityReport


def _load_category_rules(db: Session, tenant_id: uuid.UUID) -> list[CategoryRule] | None:
    rows = db.execute(
        select(ApplicationCategoryRule).where(ApplicationCategoryRule.tenant_id == tenant_id)
    ).scalars().all()
    if not rows:
        return None
    return [CategoryRule(category=r.category, match_type=r.match_type, pattern=r.pattern, priority=r.priority) for r in rows]


def run_ingestion_pipeline(
    db: Session,
    *,
    tenant_id: uuid.UUID,
    dataset_id: uuid.UUID,
    file_path: str,
    source: str = "zoho_mail",
) -> PipelineResult:
    logger.info("ingestion.start", dataset_id=str(dataset_id), source=source)

    loaded = load_csv(file_path)
    adapter = get_adapter(source)
    mapping = adapter.detect(loaded.columns)

    parsed_rows: list[ParsedRow] = list(
        adapter.parse(loaded.df, mapping, tenant_id=str(tenant_id), dataset_id=str(dataset_id))
    )

    valid_events: list[CanonicalEmailEvent] = []
    valid_indices: list[int] = []
    issue_samples: list[IssueSample] = []
    malformed_emails = 0
    missing_timestamps = 0
    missing_recipient = 0
    missing_bounce_info = 0

    for parsed in parsed_rows:
        for issue in parsed.issues:
            if len(issue_samples) < 50:
                issue_samples.append(IssueSample(**issue.model_dump()))
            if issue.issue == "malformed_email":
                malformed_emails += 1
            elif issue.issue == "unparseable_timestamp" or (issue.issue == "missing_value" and issue.field == "event_time"):
                missing_timestamps += 1
            elif issue.issue == "missing_value" and issue.field == "recipient_email":
                missing_recipient += 1
        if parsed.is_valid and parsed.event is not None:
            valid_events.append(parsed.event)
            valid_indices.append(parsed.row_index)
            if parsed.event.status in (CanonicalStatus.HARD_BOUNCE, CanonicalStatus.SOFT_BOUNCE) and not parsed.event.bounce_reason:
                missing_bounce_info += 1

    retry_map = detect_retries(valid_events)

    hashes = [
        compute_raw_record_hash(
            tenant_id=str(tenant_id),
            sender=e.sender,
            recipient=e.recipient,
            subject=e.subject,
            timestamp=e.timestamp,
            mail_reference=e.mail_reference,
        )
        for e in valid_events
    ]
    seen_hashes: set[str] = set()
    duplicate_flags: list[bool] = []
    for h in hashes:
        duplicate_flags.append(h in seen_hashes)
        seen_hashes.add(h)

    category_rules = _load_category_rules(db, tenant_id)
    dim_cache = sync_dimensions(db, tenant_id, valid_events, category_rules)

    orm_rows: list[EmailEvent] = []
    now = datetime.now(timezone.utc)
    date_start: datetime | None = None
    date_end: datetime | None = None

    for local_pos, event in enumerate(valid_events):
        retry_group_id, retry_count, is_retry = retry_map.get(local_pos, (None, 0, False))
        row = EmailEvent(
            tenant_id=tenant_id,
            dataset_id=dataset_id,
            event_time=event.timestamp,
            sender_id=dim_cache.sender_ids.get(event.sender) if event.sender else None,
            recipient_id=dim_cache.recipient_ids.get(event.recipient) if event.recipient else None,
            subject_id=dim_cache.subject_ids.get(event.subject) if event.subject else None,
            domain_id=dim_cache.domain_ids.get(event.recipient_domain) if event.recipient_domain else None,
            sender_email=_truncate(event.sender, 320),
            recipient_email=_truncate(event.recipient, 320),
            status=_STATUS_MAP.get(event.status, EmailStatus.UNKNOWN),
            bounce_type=event.bounce_type or "NONE",
            bounce_code=_truncate(event.bounce_code, 20),
            bounce_category=event.bounce_category or "NONE",
            bounce_reason=_truncate(event.bounce_reason, 2000),
            remote_ip=_truncate(event.remote_ip, 64),
            remote_mta=_truncate(event.remote_mta, 255),
            relay_server=_truncate(event.relay_server, 255),
            mail_reference=_truncate(event.mail_reference, 255),
            processing_time=event.processing_time,
            is_retry=is_retry,
            retry_group_id=retry_group_id,
            retry_count=retry_count,
            is_duplicate=duplicate_flags[local_pos],
            raw_record_hash=hashes[local_pos],
            raw_record=event.raw_record,
            created_at=now,
        )
        orm_rows.append(row)
        if date_start is None or event.timestamp < date_start:
            date_start = event.timestamp
        if date_end is None or event.timestamp > date_end:
            date_end = event.timestamp

    db.bulk_save_objects(orm_rows)
    db.flush()

    # A source row can now fan out into multiple events (comma/semicolon-
    # separated recipients), so "invalid rows" is counted by distinct source
    # row_index that produced zero valid events, not total_rows - valid_events
    # (which can go negative once one row yields more than one event).
    valid_row_indices = {p.row_index for p in parsed_rows if p.is_valid}
    quality_report = DataQualityReport(
        rows=loaded.row_count,
        valid_rows=len(valid_events),
        invalid_rows=loaded.row_count - len(valid_row_indices),
        duplicate_rows=sum(duplicate_flags),
        retry_rows=sum(1 for _, count, is_retry in retry_map.values() if is_retry),
        malformed_emails=malformed_emails,
        missing_timestamps=missing_timestamps,
        missing_recipient=missing_recipient,
        missing_bounce_information=missing_bounce_info,
        missing_open_data=not mapping.has_field("total_opens"),
        missing_click_data=not mapping.has_field("total_clicks"),
        unmapped_source_columns=mapping.unmapped_columns,
        missing_optional_fields=mapping.missing_optional_fields,
        issue_samples=issue_samples,
    )

    logger.info(
        "ingestion.complete",
        dataset_id=str(dataset_id),
        total_rows=loaded.row_count,
        valid_rows=len(valid_events),
        duplicate_rows=quality_report.duplicate_rows,
    )

    return PipelineResult(
        total_rows=loaded.row_count,
        processed_rows=len(valid_events),
        failed_rows=quality_report.invalid_rows,
        duplicate_rows=quality_report.duplicate_rows,
        date_start=date_start,
        date_end=date_end,
        quality_report=quality_report,
    )
