"""Materialized aggregation tables. Recomputed by the CALCULATE_METRICS job
after each dataset import so dashboard/analytics reads never scan raw
email_events at request time.
"""
import enum
import uuid
from datetime import date, datetime

from sqlalchemy import Date, DateTime, Enum, Float, ForeignKey, Integer, String, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base
from app.models.base import uuid_pk


class RiskLevel(str, enum.Enum):
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    CRITICAL = "CRITICAL"


class _RatesMixin:
    total_emails: Mapped[int] = mapped_column(Integer, default=0)
    successful: Mapped[int] = mapped_column(Integer, default=0)
    hard_bounces: Mapped[int] = mapped_column(Integer, default=0)
    soft_bounces: Mapped[int] = mapped_column(Integer, default=0)
    failures: Mapped[int] = mapped_column(Integer, default=0)
    delivery_rate: Mapped[float] = mapped_column(Float, default=0.0)
    bounce_rate: Mapped[float] = mapped_column(Float, default=0.0)
    failure_rate: Mapped[float] = mapped_column(Float, default=0.0)


class DailyEmailMetrics(Base, _RatesMixin):
    __tablename__ = "daily_email_metrics"
    __table_args__ = (UniqueConstraint("dataset_id", "date", name="uq_daily_metrics"),)

    id: Mapped[uuid.UUID] = uuid_pk()
    dataset_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("datasets.id"), index=True)
    date: Mapped[date] = mapped_column(Date, index=True)
    unique_recipients: Mapped[int] = mapped_column(Integer, default=0)
    computed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class HourlyEmailMetrics(Base, _RatesMixin):
    __tablename__ = "hourly_email_metrics"
    __table_args__ = (UniqueConstraint("dataset_id", "date", "hour", name="uq_hourly_metrics"),)

    id: Mapped[uuid.UUID] = uuid_pk()
    dataset_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("datasets.id"), index=True)
    date: Mapped[date] = mapped_column(Date, index=True)
    hour: Mapped[int] = mapped_column(Integer)
    computed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class RecipientMetrics(Base, _RatesMixin):
    __tablename__ = "recipient_metrics"
    __table_args__ = (UniqueConstraint("dataset_id", "recipient_id", name="uq_recipient_metrics"),)

    id: Mapped[uuid.UUID] = uuid_pk()
    dataset_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("datasets.id"), index=True)
    recipient_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("recipients.id"), index=True)

    first_seen: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_seen: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    unique_subjects: Mapped[int] = mapped_column(Integer, default=0)
    unique_senders: Mapped[int] = mapped_column(Integer, default=0)

    risk_score: Mapped[float] = mapped_column(Float, default=0.0)
    risk_level: Mapped[RiskLevel] = mapped_column(Enum(RiskLevel, name="risk_level"), default=RiskLevel.LOW)
    risk_reasons: Mapped[list | None] = mapped_column(JSONB, nullable=True)

    computed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class DomainMetrics(Base, _RatesMixin):
    __tablename__ = "domain_metrics"
    __table_args__ = (UniqueConstraint("dataset_id", "domain_id", name="uq_domain_metrics"),)

    id: Mapped[uuid.UUID] = uuid_pk()
    dataset_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("datasets.id"), index=True)
    domain_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("domains.id"), index=True)
    unique_recipients: Mapped[int] = mapped_column(Integer, default=0)
    computed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class SubjectMetrics(Base, _RatesMixin):
    __tablename__ = "subject_metrics"
    __table_args__ = (UniqueConstraint("dataset_id", "subject_id", name="uq_subject_metrics"),)

    id: Mapped[uuid.UUID] = uuid_pk()
    dataset_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("datasets.id"), index=True)
    subject_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("subjects.id"), index=True)
    unique_recipients: Mapped[int] = mapped_column(Integer, default=0)
    computed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class SenderMetrics(Base, _RatesMixin):
    __tablename__ = "sender_metrics"
    __table_args__ = (UniqueConstraint("dataset_id", "sender_id", name="uq_sender_metrics"),)

    id: Mapped[uuid.UUID] = uuid_pk()
    dataset_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("datasets.id"), index=True)
    sender_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("senders.id"), index=True)
    unique_recipients: Mapped[int] = mapped_column(Integer, default=0)
    unique_subjects: Mapped[int] = mapped_column(Integer, default=0)
    computed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class BounceReasonMetrics(Base):
    __tablename__ = "bounce_reason_metrics"
    __table_args__ = (
        UniqueConstraint("dataset_id", "bounce_category", "bounce_code", name="uq_bounce_reason_metrics"),
    )

    id: Mapped[uuid.UUID] = uuid_pk()
    dataset_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("datasets.id"), index=True)
    bounce_category: Mapped[str] = mapped_column(String(50))
    bounce_code: Mapped[str | None] = mapped_column(String(20), nullable=True)
    bounce_type: Mapped[str] = mapped_column(String(10))
    count: Mapped[int] = mapped_column(Integer, default=0)
    percent_of_total: Mapped[float] = mapped_column(Float, default=0.0)
    computed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class InfrastructureMetrics(Base, _RatesMixin):
    """Aggregates by remote_mta / relay_server (infrastructure component)."""

    __tablename__ = "infrastructure_metrics"
    __table_args__ = (
        UniqueConstraint("dataset_id", "component_type", "component_value", name="uq_infra_metrics"),
    )

    id: Mapped[uuid.UUID] = uuid_pk()
    dataset_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("datasets.id"), index=True)
    component_type: Mapped[str] = mapped_column(String(20))  # remote_mta | relay_server | remote_ip
    component_value: Mapped[str] = mapped_column(String(255))
    unique_recipients: Mapped[int] = mapped_column(Integer, default=0)
    computed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class ApplicationMetrics(Base, _RatesMixin):
    """Aggregates by application/workflow category derived from subject classification."""

    __tablename__ = "application_metrics"
    __table_args__ = (UniqueConstraint("dataset_id", "category", name="uq_application_metrics"),)

    id: Mapped[uuid.UUID] = uuid_pk()
    dataset_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("datasets.id"), index=True)
    category: Mapped[str] = mapped_column(String(100))
    unique_recipients: Mapped[int] = mapped_column(Integer, default=0)
    computed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
