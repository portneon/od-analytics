"""Adapter for WhatsApp Business API (WABA) messaging-gateway exports.

These CSVs come from a WhatsApp template-messaging gateway (e.g. the
"7015613714 (1 Sep-30 Sep).csv" export): one row per outbound message, with
Sender/Recipient phone numbers, a multi-stage delivery timeline (Accept/Sent/
Delivered/Read timestamps) and a final Status instead of email's SMTP bounce
codes. It reuses the same CanonicalEmailEvent pipeline as the email adapters
-- "sender"/"recipient" just hold phone numbers here instead of addresses,
and there is no bounce/SMTP classification since WhatsApp has no such
concept; the gateway's own Status + Error description are preserved as-is.
"""
from __future__ import annotations

from collections.abc import Iterator
from datetime import datetime, timezone

import polars as pl

from app.ingestion.adapters.base import SourceAdapter
from app.ingestion.normalize import is_valid_phone, normalize_empty, normalize_phone, parse_timestamp
from app.ingestion.schema_mapper import SchemaMapping
from app.schemas.canonical import CanonicalEmailEvent, CanonicalStatus, FieldQualityIssue, ParsedRow

# Final per-message status -> canonical outcome. "Sent"/"Delivered"/"Read"
# are successive confirmations of the same successful send, not distinct
# outcomes, so they all collapse to SUCCESS; "Queued" has no outcome yet.
_STATUS_MAP: dict[str, CanonicalStatus] = {
    "read": CanonicalStatus.SUCCESS,
    "delivered": CanonicalStatus.SUCCESS,
    "sent": CanonicalStatus.SUCCESS,
    "not sent": CanonicalStatus.FAILED,
    "dropped": CanonicalStatus.FAILED,
    "queued": CanonicalStatus.UNKNOWN,
}

_EVENT_TIME_COLUMNS = ("Sent Date & Time", "Accept Date & Time", "Delivered Date & Time", "Read Date & Time")


class WhatsAppGatewayAdapter(SourceAdapter):
    source_name = "whatsapp_gateway"

    signature_columns = frozenset(
        {
            "accept date & time",
            "sent date & time",
            "delivered date & time",
            "read date & time",
            "waba pricing category",
            "template id",
            "conv id",
            "ack id",
        }
    )

    def detect(self, columns: list[str]) -> SchemaMapping:
        lookup = {c: c for c in columns}

        def pick(*names: str) -> str | None:
            for name in names:
                if name in lookup:
                    return lookup[name]
            return None

        mapping = SchemaMapping()
        field_columns = {
            "sender_email": pick("Sender"),
            "recipient_email": pick("Recipient"),
            "event_time": pick(*_EVENT_TIME_COLUMNS),
            "status": pick("Status"),
            "bounce_reason": pick("Error description", "Channel Error description"),
            "subject": pick("Template ID"),
            "mail_reference": pick("MID", "ACK ID"),
        }
        mapped_columns: set[str] = set()
        for canonical_field, column in field_columns.items():
            if column is not None:
                mapping.field_to_column[canonical_field] = column
                mapping.column_to_field[column] = canonical_field
                mapped_columns.add(column)

        mapping.unmapped_columns = [c for c in columns if c not in mapped_columns]
        required = {"sender_email", "recipient_email", "event_time"}
        mapping.missing_required_fields = sorted(required - set(mapping.field_to_column))
        mapping.missing_optional_fields = sorted(
            {"status", "bounce_reason", "subject", "mail_reference"} - set(mapping.field_to_column)
        )
        return mapping

    def parse(
        self, df: pl.DataFrame, mapping: SchemaMapping, *, dataset_id: str
    ) -> Iterator[ParsedRow]:
        col = mapping.field_to_column

        for row_index, row in enumerate(df.iter_rows(named=True)):
            issues: list[FieldQualityIssue] = []

            def get(field_name: str) -> str | None:
                source_col = col.get(field_name)
                if source_col is None:
                    return None
                value = row.get(source_col)
                return None if value is None else str(value)

            raw_sender = get("sender_email")
            raw_recipient = get("recipient_email")
            raw_timestamp = get("event_time")

            sender = normalize_phone(raw_sender)
            recipient = normalize_phone(raw_recipient)
            timestamp = parse_timestamp(raw_timestamp)

            if raw_timestamp and timestamp is None:
                issues.append(FieldQualityIssue(row_index=row_index, field="event_time", issue="unparseable_timestamp", raw_value=raw_timestamp))
            if not raw_timestamp:
                issues.append(FieldQualityIssue(row_index=row_index, field="event_time", issue="missing_value", raw_value=None))

            if sender and not is_valid_phone(sender):
                issues.append(FieldQualityIssue(row_index=row_index, field="sender_email", issue="malformed_email", raw_value=raw_sender))
            if recipient and not is_valid_phone(recipient):
                issues.append(FieldQualityIssue(row_index=row_index, field="recipient_email", issue="malformed_email", raw_value=raw_recipient))
            if not recipient:
                issues.append(FieldQualityIssue(row_index=row_index, field="recipient_email", issue="missing_value", raw_value=raw_recipient))

            status_hint = normalize_empty(get("status"))
            status = _STATUS_MAP.get(status_hint.lower(), CanonicalStatus.UNKNOWN) if status_hint else CanonicalStatus.UNKNOWN

            # The gateway's error-description column is populated on every
            # row (even "Read by the user" / "Delivered to User"), not just
            # failures -- only surface it as a bounce_reason when the send
            # actually failed, so it reads as a reason rather than noise.
            bounce_reason = normalize_empty(get("bounce_reason")) if status == CanonicalStatus.FAILED else None

            subject = normalize_empty(get("subject"))
            mail_reference = normalize_empty(get("mail_reference"))

            is_valid = recipient is not None and is_valid_phone(recipient) and timestamp is not None

            event = CanonicalEmailEvent(
                dataset_id=dataset_id,
                timestamp=timestamp or datetime(1970, 1, 1, tzinfo=timezone.utc),
                sender=sender,
                recipient=recipient,
                sender_domain=None,
                recipient_domain=None,
                subject=subject,
                status=status,
                bounce_type=None,
                bounce_code=None,
                bounce_category=None,
                bounce_reason=bounce_reason,
                mail_reference=mail_reference,
                raw_record=dict(row),
                source=self.source_name,
            )

            yield ParsedRow(row_index=row_index, event=event, issues=issues, is_valid=is_valid)
