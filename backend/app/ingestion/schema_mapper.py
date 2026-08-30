"""Configurable source-column -> canonical-field mapping.

The whole point of this module is that the analytics/ETL layers never need
to know what a Zoho (or Gmail, or SES...) export actually calls its columns.
Detection is alias-based and fuzzy on whitespace/case/punctuation so minor
header variations across Zoho export versions don't break ingestion.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field

# Canonical field -> list of known source header aliases (lowercase, normalized).
# Extend this table (or make it configurable in the DB later) rather
# than adding new hardcoded parsing branches elsewhere.
CANONICAL_FIELD_ALIASES: dict[str, list[str]] = {
    "sender_email": ["from", "sender", "from address", "mail from", "sender email", "sent from"],
    "recipient_email": ["to", "recipient", "to address", "rcpt to", "recipient email", "sent to"],
    "subject": ["subject", "mail subject", "email subject"],
    "event_time": [
        "date", "sent time", "sent date", "timestamp", "event time",
        "delivery time", "mail date", "date time", "time", "processed time", "processed date",
    ],
    "status": ["status", "delivery status", "mail status", "delivery state"],
    "bounce_type": ["bounce type", "type of bounce"],
    "hard_bounce": ["hard bounce", "hard bounces", "is hard bounce"],
    "soft_bounce": ["soft bounce", "soft bounces", "is soft bounce"],
    "bounce_code": ["smtp code", "bounce code", "status code", "enhanced status code", "error code"],
    "bounce_reason": [
        "bounce reason", "delivery info", "delivery information", "reason", "error",
        "diagnostic", "diagnostic code", "failure reason", "error message", "mail failure",
    ],
    "remote_ip": ["remote ip", "ip", "server ip", "source ip"],
    "remote_mta": ["remote mta", "mta", "receiving mta"],
    "relay_server": ["relay", "relay server", "relay mta", "relayed via"],
    "mail_reference": ["message id", "mail reference", "reference id", "msg id", "message-id"],
    "processing_time": ["processing time", "delivery time ms", "latency", "processing time ms"],
    "total_opens": ["total opens", "opens", "open count"],
    "total_clicks": ["total clicks", "clicks", "click count"],
}

REQUIRED_CANONICAL_FIELDS = {"sender_email", "recipient_email", "event_time"}


def _normalize_header(header: str) -> str:
    h = header.strip().lower()
    h = re.sub(r"[_\-]+", " ", h)
    h = re.sub(r"\s+", " ", h)
    return h.strip()


@dataclass
class SchemaMapping:
    column_to_field: dict[str, str] = field(default_factory=dict)  # source column -> canonical field
    field_to_column: dict[str, str] = field(default_factory=dict)  # canonical field -> source column
    unmapped_columns: list[str] = field(default_factory=list)
    missing_required_fields: list[str] = field(default_factory=list)
    missing_optional_fields: list[str] = field(default_factory=list)

    def has_field(self, canonical_field: str) -> bool:
        return canonical_field in self.field_to_column


def detect_schema(source_columns: list[str]) -> SchemaMapping:
    """Match each source CSV column against the canonical alias table.

    First match wins per canonical field; a source column matches at most
    one canonical field. Unmatched source columns are kept (never dropped)
    so they can still be inspected in the raw_record payload.
    """
    alias_lookup: dict[str, str] = {}
    for canonical_field, aliases in CANONICAL_FIELD_ALIASES.items():
        for alias in aliases:
            alias_lookup[alias] = canonical_field

    mapping = SchemaMapping()
    for column in source_columns:
        normalized = _normalize_header(column)
        canonical_field = alias_lookup.get(normalized)
        if canonical_field and canonical_field not in mapping.field_to_column:
            mapping.column_to_field[column] = canonical_field
            mapping.field_to_column[canonical_field] = column
        else:
            mapping.unmapped_columns.append(column)

    mapping.missing_required_fields = sorted(REQUIRED_CANONICAL_FIELDS - set(mapping.field_to_column))
    all_known = set(CANONICAL_FIELD_ALIASES.keys())
    mapping.missing_optional_fields = sorted(all_known - REQUIRED_CANONICAL_FIELDS - set(mapping.field_to_column))
    return mapping
