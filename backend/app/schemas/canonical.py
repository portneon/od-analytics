"""The canonical email-event domain model.

Every ingestion adapter (Zoho, and future Gmail/SES/SendGrid/etc adapters)
must produce a stream of `CanonicalEmailEvent` objects. Nothing downstream
of ingestion (ETL, analytics, intelligence, AI) should ever look at a
provider-specific field name again -- that is the entire point of this
layer: it decouples the rest of the platform from Zoho's CSV schema.
"""
from __future__ import annotations

from datetime import datetime
from enum import Enum

from pydantic import BaseModel, Field


class CanonicalStatus(str, Enum):
    SUCCESS = "SUCCESS"
    HARD_BOUNCE = "HARD_BOUNCE"
    SOFT_BOUNCE = "SOFT_BOUNCE"
    FAILED = "FAILED"
    DEFERRED = "DEFERRED"
    UNKNOWN = "UNKNOWN"


class CanonicalEmailEvent(BaseModel):
    """One normalized email send event, independent of source provider."""

    tenant_id: str
    dataset_id: str

    timestamp: datetime

    sender: str | None = None
    recipient: str | None = None
    sender_domain: str | None = None
    recipient_domain: str | None = None
    subject: str | None = None

    status: CanonicalStatus = CanonicalStatus.UNKNOWN

    bounce_type: str | None = None  # HARD | SOFT | NONE
    bounce_code: str | None = None  # raw SMTP enhanced status code, e.g. 5.1.1
    bounce_category: str | None = None
    bounce_reason: str | None = None  # raw diagnostic text, preserved verbatim

    remote_ip: str | None = None
    remote_mta: str | None = None
    relay_server: str | None = None

    mail_reference: str | None = None
    processing_time: float | None = None

    is_retry: bool = False
    is_duplicate: bool = False

    raw_record: dict = Field(default_factory=dict)  # original source row, preserved for audit/drill-down
    source: str = "unknown"


class FieldQualityIssue(BaseModel):
    row_index: int
    field: str
    issue: str
    raw_value: str | None = None


class ParsedRow(BaseModel):
    """Result of parsing+normalizing a single source row: either a usable
    canonical event, or a rejected row with the reason it was rejected.
    Rows are never silently dropped -- rejects are always surfaced in the
    data-quality report.
    """

    row_index: int
    event: CanonicalEmailEvent | None = None
    issues: list[FieldQualityIssue] = Field(default_factory=list)
    is_valid: bool = True
