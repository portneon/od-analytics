import enum
import uuid
from datetime import datetime

from sqlalchemy import DateTime, Enum, Float, ForeignKey, String, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base
from app.models.base import uuid_pk


class AnomalySeverity(str, enum.Enum):
    INFO = "INFO"
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    CRITICAL = "CRITICAL"


class Anomaly(Base):
    __tablename__ = "anomalies"

    id: Mapped[uuid.UUID] = uuid_pk()
    dataset_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("datasets.id"), index=True)

    metric: Mapped[str] = mapped_column(String(50), index=True)  # e.g. volume, bounce_rate, failure_rate
    entity_type: Mapped[str] = mapped_column(String(30))  # overall | domain | recipient | subject | sender | infra
    entity_id: Mapped[str | None] = mapped_column(String(255), nullable=True)

    observed_value: Mapped[float] = mapped_column(Float)
    expected_value: Mapped[float] = mapped_column(Float)
    deviation: Mapped[float] = mapped_column(Float)  # z-score or percent-change, depending on method
    method: Mapped[str] = mapped_column(String(30), default="z_score")

    severity: Mapped[AnomalySeverity] = mapped_column(Enum(AnomalySeverity, name="anomaly_severity"), index=True)
    detected_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    period_start: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    period_end: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    explanation: Mapped[str] = mapped_column(String(2000))
    contributors: Mapped[list | None] = mapped_column(JSONB, nullable=True)
    recommendations: Mapped[list | None] = mapped_column(JSONB, nullable=True)
