import enum
import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, Enum, Float, ForeignKey, Index, Integer, String
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base
from app.models.base import uuid_pk


class EmailStatus(str, enum.Enum):
    SUCCESS = "SUCCESS"
    HARD_BOUNCE = "HARD_BOUNCE"
    SOFT_BOUNCE = "SOFT_BOUNCE"
    FAILED = "FAILED"
    DEFERRED = "DEFERRED"
    UNKNOWN = "UNKNOWN"


class BounceType(str, enum.Enum):
    HARD = "HARD"
    SOFT = "SOFT"
    NONE = "NONE"


class BounceCategory(str, enum.Enum):
    MAILBOX_NOT_FOUND = "MAILBOX_NOT_FOUND"
    INVALID_DOMAIN = "INVALID_DOMAIN"
    MAILBOX_FULL = "MAILBOX_FULL"
    RATE_LIMITED = "RATE_LIMITED"
    POLICY_REJECTION = "POLICY_REJECTION"
    SPAM_REJECTION = "SPAM_REJECTION"
    DNS_ERROR = "DNS_ERROR"
    TEMPORARY_FAILURE = "TEMPORARY_FAILURE"
    AUTHENTICATION_FAILURE = "AUTHENTICATION_FAILURE"
    BLOCKED = "BLOCKED"
    NONE = "NONE"
    UNKNOWN = "UNKNOWN"


class BounceSeverity(str, enum.Enum):
    NONE = "NONE"
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    CRITICAL = "CRITICAL"


class EmailEvent(Base):
    """Primary analytical fact table. One row per email send event.

    Denormalized sender_email/recipient_email are kept alongside the FK ids
    to `senders`/`recipients` deliberately: analytical queries (group-by,
    search, CSV export) read the raw string constantly and a join for every
    row would be wasteful at scale, while the FK still gives us cheap
    entity-level aggregation via recipient_id/sender_id.
    """

    __tablename__ = "email_events"
    __table_args__ = (
        # The single-column indexes here (status, recipient_id, domain_id,
        # raw_record_hash) are already covered by index=True on those
        # columns below -- only the composite index needs to be explicit.
        Index("ix_email_events_dataset_time", "dataset_id", "event_time"),
    )

    id: Mapped[uuid.UUID] = uuid_pk()
    dataset_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("datasets.id"), index=True)

    event_time: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, index=True)

    sender_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("senders.id"), nullable=True)
    recipient_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("recipients.id"), nullable=True, index=True
    )
    subject_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("subjects.id"), nullable=True)
    domain_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("domains.id"), nullable=True, index=True
    )

    sender_email: Mapped[str | None] = mapped_column(String(320), nullable=True)
    recipient_email: Mapped[str | None] = mapped_column(String(320), nullable=True)

    status: Mapped[EmailStatus] = mapped_column(Enum(EmailStatus, name="email_status"), index=True)

    bounce_type: Mapped[BounceType] = mapped_column(Enum(BounceType, name="bounce_type"), default=BounceType.NONE)
    bounce_code: Mapped[str | None] = mapped_column(String(20), nullable=True, index=True)
    bounce_category: Mapped[BounceCategory] = mapped_column(
        Enum(BounceCategory, name="bounce_category"), default=BounceCategory.NONE
    )
    bounce_reason: Mapped[str | None] = mapped_column(String(2000), nullable=True)
    bounce_severity: Mapped[BounceSeverity] = mapped_column(
        Enum(BounceSeverity, name="bounce_severity"), default=BounceSeverity.NONE
    )

    remote_ip: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)
    remote_mta: Mapped[str | None] = mapped_column(String(255), nullable=True)
    relay_server: Mapped[str | None] = mapped_column(String(255), nullable=True)

    mail_reference: Mapped[str | None] = mapped_column(String(255), nullable=True, index=True)
    processing_time: Mapped[float | None] = mapped_column(Float, nullable=True)

    is_retry: Mapped[bool] = mapped_column(Boolean, default=False)
    retry_group_id: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)
    retry_count: Mapped[int] = mapped_column(Integer, default=0)

    is_duplicate: Mapped[bool] = mapped_column(Boolean, default=False)
    raw_record_hash: Mapped[str] = mapped_column(String(64), nullable=False, index=True)

    raw_record: Mapped[dict | None] = mapped_column(JSONB, nullable=True)  # original row, for audit/inspection

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
