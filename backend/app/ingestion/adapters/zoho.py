from __future__ import annotations

import re
from collections.abc import Iterator
from datetime import datetime, timezone

import polars as pl

from app.ingestion.bounce_classifier import classify_bounce
from app.ingestion.normalize import extract_domain, is_valid_email, normalize_email, normalize_empty, parse_timestamp
from app.ingestion.schema_mapper import SchemaMapping, detect_schema
from app.ingestion.adapters.base import SourceAdapter
from app.models.email_event import BounceType
from app.schemas.canonical import CanonicalEmailEvent, CanonicalStatus, FieldQualityIssue, ParsedRow

_SUCCESS_HINTS = {"delivered", "sent", "success", "successful", "accepted", "processed"}
_HARD_HINTS = {"bounced", "hard bounce", "bounce", "rejected", "undeliverable", "permanent failure"}
_SOFT_HINTS = {"soft bounce", "deferred", "delayed", "temporary failure", "retry"}
_FAILED_HINTS = {"failed", "blocked", "error", "spam", "dropped"}


def _status_from_hint(hint: str | None) -> CanonicalStatus | None:
    if not hint:
        return None
    h = hint.strip().lower()
    if h in _SUCCESS_HINTS:
        return CanonicalStatus.SUCCESS
    if h in _HARD_HINTS:
        return CanonicalStatus.HARD_BOUNCE
    if h in _SOFT_HINTS:
        return CanonicalStatus.SOFT_BOUNCE
    if h in _FAILED_HINTS:
        return CanonicalStatus.FAILED
    return None


_RECIPIENT_SPLIT_RE = re.compile(r"[,;]")


def _split_recipients(raw: str | None) -> list[str | None]:
    """Zoho exports sometimes put multiple recipients in one CSV cell
    (comma- or semicolon-separated, e.g. a CC'd distribution list). Split
    them so each recipient becomes its own analytics-visible email event
    instead of the whole cell being rejected as one malformed address."""
    if not raw or not _RECIPIENT_SPLIT_RE.search(raw):
        return [raw]
    parts = [p.strip() for p in _RECIPIENT_SPLIT_RE.split(raw) if p.strip()]
    return parts or [raw]


class ZohoAdapter(SourceAdapter):
    source_name = "zoho_mail"

    def detect(self, columns: list[str]) -> SchemaMapping:
        return detect_schema(columns)

    def parse(
        self, df: pl.DataFrame, mapping: SchemaMapping, *, dataset_id: str
    ) -> Iterator[ParsedRow]:
        col = mapping.field_to_column

        for row_index, row in enumerate(df.iter_rows(named=True)):
            row_issues: list[FieldQualityIssue] = []

            def get(field_name: str) -> str | None:
                source_col = col.get(field_name)
                if source_col is None:
                    return None
                value = row.get(source_col)
                return None if value is None else str(value)

            raw_sender = get("sender_email")
            raw_recipient = get("recipient_email")
            raw_timestamp = get("event_time")

            sender = normalize_email(raw_sender)
            timestamp = parse_timestamp(raw_timestamp)

            if sender and not is_valid_email(sender):
                row_issues.append(FieldQualityIssue(row_index=row_index, field="sender_email", issue="malformed_email", raw_value=raw_sender))
            if raw_timestamp and timestamp is None:
                row_issues.append(FieldQualityIssue(row_index=row_index, field="event_time", issue="unparseable_timestamp", raw_value=raw_timestamp))
            if not raw_timestamp:
                row_issues.append(FieldQualityIssue(row_index=row_index, field="event_time", issue="missing_value", raw_value=None))

            status_hint = normalize_empty(get("status"))
            hard_flag = normalize_empty(get("hard_bounce"))
            soft_flag = normalize_empty(get("soft_bounce"))
            bounce_code = normalize_empty(get("bounce_code"))
            bounce_reason = normalize_empty(get("bounce_reason"))

            # Check for explicit MAIL FAILURE column if present in row
            mail_failure_col = next((c for c in row.keys() if str(c).strip().lower().replace("_", " ").replace("-", " ") in ("mail failure", "mail failures")), None)
            mail_failure_flag = normalize_empty(str(row[mail_failure_col])) if mail_failure_col and row.get(mail_failure_col) else None

            has_hard = bool(hard_flag and hard_flag.lower() not in ("0", "false", "no", "none", "null", ""))
            has_soft = bool(soft_flag and soft_flag.lower() not in ("0", "false", "no", "none", "null", ""))
            has_mail_fail = bool(mail_failure_flag and mail_failure_flag.lower() not in ("0", "false", "no", "none", "null", ""))

            if has_hard:
                status_hint = "hard bounce"
                if not bounce_reason or "STATUS: SUCCESS" in bounce_reason:
                    bounce_reason = hard_flag
            elif has_soft:
                status_hint = "soft bounce"
                if not bounce_reason or "STATUS: SUCCESS" in bounce_reason:
                    bounce_reason = soft_flag
            elif has_mail_fail:
                status_hint = "failed"
                if not bounce_reason or "STATUS: SUCCESS" in bounce_reason:
                    bounce_reason = mail_failure_flag

            classification = classify_bounce(smtp_code=bounce_code, reason_text=bounce_reason, status_hint=status_hint)

            # Resolved fully here unless it falls through to the "no hints at
            # all" case, which depends on whether *this particular* fanned-out
            # recipient is present/valid -- so that branch is deferred below.
            status = _status_from_hint(status_hint)
            if status is None:
                if classification.bounce_type == BounceType.HARD:
                    status = CanonicalStatus.HARD_BOUNCE
                elif classification.bounce_type == BounceType.SOFT:
                    status = CanonicalStatus.SOFT_BOUNCE
                elif bounce_reason or bounce_code:
                    status = CanonicalStatus.FAILED
                elif status_hint:
                    status = CanonicalStatus.UNKNOWN

            processing_time_raw = get("processing_time")
            processing_time: float | None = None
            if processing_time_raw:
                try:
                    processing_time = float(processing_time_raw)
                except ValueError:
                    row_issues.append(FieldQualityIssue(row_index=row_index, field="processing_time", issue="not_numeric", raw_value=processing_time_raw))

            subject = normalize_empty(get("subject"))
            remote_ip = normalize_empty(get("remote_ip"))
            remote_mta = normalize_empty(get("remote_mta"))
            relay_server = normalize_empty(get("relay_server"))
            mail_reference = normalize_empty(get("mail_reference"))

            # Zoho exports occasionally combine multiple recipients (e.g. a CC'd
            # distribution list) into one comma/semicolon-separated cell. Fan
            # those out into one canonical event per recipient instead of
            # rejecting the whole cell as a single malformed address.
            for recipient_raw in _split_recipients(raw_recipient):
                issues = list(row_issues)
                recipient = normalize_email(recipient_raw)

                if recipient and not is_valid_email(recipient):
                    issues.append(FieldQualityIssue(row_index=row_index, field="recipient_email", issue="malformed_email", raw_value=recipient_raw))
                if not recipient:
                    issues.append(FieldQualityIssue(row_index=row_index, field="recipient_email", issue="missing_value", raw_value=recipient_raw))

                event_status = status if status is not None else (
                    CanonicalStatus.SUCCESS if recipient and timestamp else CanonicalStatus.UNKNOWN
                )
                event_bounce_reason = bounce_reason
                if event_status == CanonicalStatus.SUCCESS and event_bounce_reason and (
                    "STATUS: SUCCESS" in event_bounce_reason or event_bounce_reason.startswith("RECIPIENT:")
                ):
                    event_bounce_reason = None

                # A malformed recipient address is never persisted as if it were a real
                # recipient (it would otherwise pollute the Recipients/Domains dimensions
                # with garbage) -- it's still fully visible via issue_samples in the
                # data-quality report, just excluded from the analytical fact table.
                is_valid = recipient is not None and is_valid_email(recipient) and timestamp is not None

                event = CanonicalEmailEvent(
                    dataset_id=dataset_id,
                    timestamp=timestamp or datetime(1970, 1, 1, tzinfo=timezone.utc),
                    sender=sender,
                    recipient=recipient,
                    sender_domain=extract_domain(sender),
                    recipient_domain=extract_domain(recipient),
                    subject=subject,
                    status=event_status,
                    bounce_type=classification.bounce_type.value,
                    bounce_code=classification.smtp_code,
                    bounce_category=classification.category.value,
                    bounce_reason=event_bounce_reason,
                    remote_ip=remote_ip,
                    remote_mta=remote_mta,
                    relay_server=relay_server,
                    mail_reference=mail_reference,
                    processing_time=processing_time,
                    raw_record=dict(row),
                    source=self.source_name,
                )

                yield ParsedRow(row_index=row_index, event=event, issues=issues, is_valid=is_valid)
