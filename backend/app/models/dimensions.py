"""Dimension tables shared across email events: senders, recipients, subjects, domains.

Kept normalized (rather than duplicating email/domain strings on every fact row)
because recipient/domain/subject intelligence pages aggregate by these entities
directly and benefit from dedicated indexes and metrics tables keyed on their ids.
"""
import uuid

from sqlalchemy import ForeignKey, String, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base
from app.models.base import uuid_pk
from sqlalchemy import DateTime, func
from datetime import datetime


class Sender(Base):
    __tablename__ = "senders"
    __table_args__ = (UniqueConstraint("email", name="uq_senders_email"),)

    id: Mapped[uuid.UUID] = uuid_pk()
    email: Mapped[str] = mapped_column(String(320), nullable=False, index=True)
    domain: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    display_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class Recipient(Base):
    __tablename__ = "recipients"
    __table_args__ = (UniqueConstraint("email", name="uq_recipients_email"),)

    id: Mapped[uuid.UUID] = uuid_pk()
    email: Mapped[str] = mapped_column(String(320), nullable=False, index=True)
    domain: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class Subject(Base):
    __tablename__ = "subjects"
    __table_args__ = (UniqueConstraint("subject", name="uq_subjects_subject"),)

    id: Mapped[uuid.UUID] = uuid_pk()
    subject: Mapped[str] = mapped_column(String(998), nullable=False)  # RFC 2822 max header length
    category: Mapped[str | None] = mapped_column(String(100), nullable=True, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class Domain(Base):
    __tablename__ = "domains"
    __table_args__ = (UniqueConstraint("domain", name="uq_domains_domain"),)

    id: Mapped[uuid.UUID] = uuid_pk()
    domain: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    provider: Mapped[str | None] = mapped_column(String(100), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class ApplicationCategoryRule(Base):
    """Configurable rules mapping subjects to application/workflow categories.

    Evaluated in `priority` order (ascending); first match wins. Seeded with
    sensible defaults but fully editable so new workflow categories (beyond
    the ones shipped) can be added without a code change.
    """

    __tablename__ = "application_category_rules"

    id: Mapped[uuid.UUID] = uuid_pk()
    category: Mapped[str] = mapped_column(String(100), nullable=False)
    match_type: Mapped[str] = mapped_column(String(20), default="contains")  # contains | starts_with | regex
    pattern: Mapped[str] = mapped_column(String(500), nullable=False)
    priority: Mapped[int] = mapped_column(default=100)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
