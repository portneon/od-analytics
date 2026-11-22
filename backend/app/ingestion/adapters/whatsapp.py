"""Adapter for WhatsApp Business API (WABA) messaging-gateway exports.

These CSVs come from a WhatsApp template-messaging gateway (e.g. the
"7015613714 (1 Sep-30 Sep).csv" export): one row per outbound message, with
Sender/Recipient phone numbers, a multi-stage delivery timeline (Accept/Sent/
Delivered/Read timestamps) and a final Status instead of email's SMTP bounce
codes. It reuses the same CanonicalEmailEvent pipeline as the email adapters
-- "sender"/"recipient" just hold phone numbers here instead of addresses,
and there is no bounce/SMTP classification since WhatsApp has no such
concept; the gateway's own Status + Error description are preserved as-is.

Two fields the gateway's own columns don't give us, but that are the
difference between "a wall of cryptic template ids" and actually-usable
insights:

- The organization that sent the message. The gateway's `Sender` column is
  the gateway's own phone number -- the same for every row, regardless of
  which school/institute the message was actually sent on behalf of. The
  institute name is only present as free text in the message body's
  "Regards, <institute>" signature, so we extract it there and carry it in
  `recipient_domain`, reusing the existing Domain dimension/metrics
  machinery (built for email's "which domain did this go to") to mean
  "which institute sent this" for this channel.
- A human-readable message category. The gateway's Template Category column
  is uselessly uniform (every row here is "UTILITY"), and the free-text
  body is often generic boilerplate ("Please find the notice attached")
  that carries no signal -- the template id itself (e.g. "stud_notice1",
  "fee_receipt2a") is the only reliable signal of *what kind* of message
  this is, so it's mapped to a readable label and carried as `subject`,
  which feeds the existing subject-classification/category pipeline.

Both transforms run as vectorized Polars expressions over the whole column
(see `_enrich`) rather than per-row Python, since this is the only point
that's cheap to vectorize before the per-row CanonicalEmailEvent loop below.
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

# Every message signs off with "Regards, <institute name>[ Powered by ...]"
# -- case-insensitive, DOTALL (the body is one long line but this is
# defensive against a literal newline), non-greedy so a stray second
# "Regards" in the body can't swallow the rest of the text.
_ENTITY_EXTRACT_PATTERN = r"(?is)Regards,?\s*(.+?)(?:\s*Powered by.*)?$"

# Some institutes' gateway account name has "Campus Automation" tacked on
# (the automation product, not part of the institute's actual name) -- the
# same institute shows up both with and without it (e.g. "Mata Rukmani Rai
# Arya Sen. Sec. School" vs "...School Campus Automation"), so stripping it
# also merges what would otherwise be two separate institute rows.
_ENTITY_SUFFIX_STRIP_PATTERN = r"(?i)\s*campus automation\s*$"

# Template ids seen in the field, mapped to a human-readable message
# category. An unmapped id (a template added by the gateway after this list
# was written) falls back to the raw id -- it still groups correctly, it's
# just unlabeled until someone adds it here.
_TEMPLATE_CATEGORY_LABELS: dict[str, str] = {
    "stud_notice1": "Notice",
    "stud_attendance_alert1": "Attendance Alert",
    "stud_attendance_alert2": "Attendance Alert",
    "stud_due_alert2": "Fee Due Reminder",
    "fee_receipt2a": "Fee Receipt",
    "stud_gate_alert3": "Gate Alert",
}


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
            "message_text": pick("Text"),
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
            {"status", "bounce_reason", "subject", "mail_reference", "message_text"} - set(mapping.field_to_column)
        )
        return mapping

    def _enrich(self, df: pl.DataFrame, mapping: SchemaMapping) -> pl.DataFrame:
        """Derive the readable category and sending-institute columns up
        front as vectorized Polars expressions over the whole dataset, so
        the per-row loop below (which has to run in Python regardless, to
        build one CanonicalEmailEvent per row) is just reading two
        already-computed columns instead of running a regex match and a
        dict lookup per row.
        """
        text_col = mapping.field_to_column.get("message_text")
        template_col = mapping.field_to_column.get("subject")

        exprs = []
        exprs.append(
            (
                pl.col(text_col)
                .str.extract(_ENTITY_EXTRACT_PATTERN, 1)
                .str.replace(_ENTITY_SUFFIX_STRIP_PATTERN, "")
                .str.strip_chars()
                if text_col is not None
                else pl.lit(None, dtype=pl.Utf8)
            ).alias("__entity")
        )
        exprs.append(
            (
                pl.col(template_col).replace_strict(_TEMPLATE_CATEGORY_LABELS, default=pl.col(template_col))
                if template_col is not None
                else pl.lit(None, dtype=pl.Utf8)
            ).alias("__category_label")
        )
        return df.with_columns(exprs)

    def parse(
        self, df: pl.DataFrame, mapping: SchemaMapping, *, dataset_id: str
    ) -> Iterator[ParsedRow]:
        col = mapping.field_to_column
        df = self._enrich(df, mapping)

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

            # Prefer the readable category label derived from the template
            # id (e.g. "Fee Receipt") over the raw template id itself --
            # falls back to the raw "subject" mapping when there's no
            # Template ID column to derive it from.
            subject = normalize_empty(row.get("__category_label")) or normalize_empty(get("subject"))
            mail_reference = normalize_empty(get("mail_reference"))

            # The gateway's Sender column is the gateway's own number for
            # every row -- it carries no org identity. The institute that
            # actually sent the message only appears in the body's
            # "Regards, <institute>" signature, so that's what we surface
            # as the "domain" dimension for this channel (see module
            # docstring for why this rides the Domain machinery).
            institute = normalize_empty(row.get("__entity"))

            is_valid = recipient is not None and is_valid_phone(recipient) and timestamp is not None

            event = CanonicalEmailEvent(
                dataset_id=dataset_id,
                timestamp=timestamp or datetime(1970, 1, 1, tzinfo=timezone.utc),
                sender=sender,
                recipient=recipient,
                sender_domain=None,
                recipient_domain=institute,
                subject=subject,
                status=status,
                bounce_type=None,
                bounce_code=None,
                bounce_category=None,
                bounce_reason=bounce_reason,
                mail_reference=mail_reference,
                raw_record={k: v for k, v in row.items() if not k.startswith("__")},
                source=self.source_name,
            )

            yield ParsedRow(row_index=row_index, event=event, issues=issues, is_valid=is_valid)
