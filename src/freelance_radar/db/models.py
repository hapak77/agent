"""SQLAlchemy 2.0 ORM models."""

from __future__ import annotations

import enum
from datetime import datetime
from typing import Any, Optional

from sqlalchemy import (
    JSON,
    Boolean,
    DateTime,
    Enum,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    pass


class OrderKind(str, enum.Enum):
    real_order = "real_order"
    discussion = "discussion"
    advertisement = "advertisement"
    spam = "spam"
    free_test = "free_test"
    vacancy = "vacancy"
    uncertain = "uncertain"


class ContactStatus(str, enum.Enum):
    not_contacted = "not_contacted"
    queued = "queued"
    sent = "sent"
    failed = "failed"
    skipped = "skipped"
    manual_contact_required = "manual_contact_required"
    replied = "replied"
    paused = "paused"


class OrderStatus(str, enum.Enum):
    new = "new"
    processing = "processing"
    analyzed = "analyzed"
    rejected = "rejected"
    ready_for_outreach = "ready_for_outreach"
    contacted = "contacted"
    archived = "archived"


class SourceStatus(str, enum.Enum):
    active = "active"
    disabled = "disabled"
    error = "error"
    unavailable = "unavailable"


class Source(Base):
    __tablename__ = "sources"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    key: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    name: Mapped[str] = mapped_column(String(128), nullable=False)
    adapter: Mapped[str] = mapped_column(String(64), nullable=False)
    enabled: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    status: Mapped[SourceStatus] = mapped_column(
        Enum(SourceStatus), default=SourceStatus.active, nullable=False
    )
    config_json: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    capabilities: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    last_success_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    last_error: Mapped[Optional[str]] = mapped_column(Text)
    last_error_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )

    orders: Mapped[list[Order]] = relationship(back_populates="source")


class DuplicateGroup(Base):
    __tablename__ = "duplicate_groups"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    fingerprint: Mapped[str] = mapped_column(String(128), unique=True, nullable=False)
    canonical_order_id: Mapped[Optional[int]] = mapped_column(ForeignKey("orders.id"))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class Order(Base):
    __tablename__ = "orders"
    __table_args__ = (
        UniqueConstraint("source_id", "external_id", name="uq_order_source_external"),
        Index("ix_orders_priority", "priority_score"),
        Index("ix_orders_status", "status"),
        Index("ix_orders_discovered", "discovered_at"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    source_id: Mapped[int] = mapped_column(ForeignKey("sources.id"), nullable=False)
    external_id: Mapped[str] = mapped_column(String(255), nullable=False)
    title: Mapped[Optional[str]] = mapped_column(String(512))
    raw_text: Mapped[str] = mapped_column(Text, nullable=False)
    normalized_text: Mapped[str] = mapped_column(Text, nullable=False, default="")
    url: Mapped[Optional[str]] = mapped_column(String(1024))
    author_id: Mapped[Optional[str]] = mapped_column(String(255))
    author_name: Mapped[Optional[str]] = mapped_column(String(255))
    author_contact: Mapped[Optional[str]] = mapped_column(String(512))
    published_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    discovered_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    content_hash: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    semantic_fingerprint: Mapped[Optional[str]] = mapped_column(String(128), index=True)
    duplicate_group_id: Mapped[Optional[int]] = mapped_column(ForeignKey("duplicate_groups.id"))
    is_duplicate: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    status: Mapped[OrderStatus] = mapped_column(
        Enum(OrderStatus), default=OrderStatus.new, nullable=False
    )
    contact_status: Mapped[ContactStatus] = mapped_column(
        Enum(ContactStatus), default=ContactStatus.not_contacted, nullable=False
    )
    categories: Mapped[list[Any]] = mapped_column(JSON, default=list)
    budget_amount: Mapped[Optional[float]] = mapped_column(Float)
    budget_currency: Mapped[Optional[str]] = mapped_column(String(16))
    budget_unknown: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    deadline_text: Mapped[Optional[str]] = mapped_column(String(255))
    requirements: Mapped[Optional[str]] = mapped_column(Text)
    expected_result: Mapped[Optional[str]] = mapped_column(Text)
    order_kind: Mapped[Optional[OrderKind]] = mapped_column(Enum(OrderKind))
    complexity: Mapped[Optional[float]] = mapped_column(Float)
    feasibility: Mapped[Optional[float]] = mapped_column(Float)
    risk_score: Mapped[Optional[float]] = mapped_column(Float)
    priority_score: Mapped[Optional[float]] = mapped_column(Float)
    rating_explanation: Mapped[Optional[str]] = mapped_column(Text)
    risks: Mapped[list[Any]] = mapped_column(JSON, default=list)
    passed_prefilter: Mapped[Optional[bool]] = mapped_column(Boolean)
    prefilter_reason: Mapped[Optional[str]] = mapped_column(String(255))
    llm_summary: Mapped[Optional[str]] = mapped_column(Text)
    contact_message: Mapped[Optional[str]] = mapped_column(Text)
    extra_json: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )

    source: Mapped[Source] = relationship(back_populates="orders")
    analysis: Mapped[Optional[AnalysisResult]] = relationship(
        back_populates="order", uselist=False
    )
    contacts: Mapped[list[ContactAttempt]] = relationship(back_populates="order")


class AnalysisResult(Base):
    __tablename__ = "analysis_results"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    order_id: Mapped[int] = mapped_column(ForeignKey("orders.id"), unique=True, nullable=False)
    model_name: Mapped[str] = mapped_column(String(128), nullable=False)
    prompt_version: Mapped[str] = mapped_column(String(32), default="v1")
    raw_response: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    cached: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    order: Mapped[Order] = relationship(back_populates="analysis")


class ContactAttempt(Base):
    __tablename__ = "contact_attempts"
    __table_args__ = (
        Index("ix_contact_order_status", "order_id", "status"),
        Index("ix_contact_order_recipient", "order_id", "channel", "recipient"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    order_id: Mapped[int] = mapped_column(ForeignKey("orders.id"), nullable=False)
    channel: Mapped[str] = mapped_column(String(64), nullable=False)
    recipient: Mapped[str] = mapped_column(String(255), nullable=False)
    message_text: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[ContactStatus] = mapped_column(Enum(ContactStatus), nullable=False)
    confirmed: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    error_code: Mapped[Optional[str]] = mapped_column(String(64))
    error_message: Mapped[Optional[str]] = mapped_column(Text)
    provider_message_id: Mapped[Optional[str]] = mapped_column(String(128))
    reply_text: Mapped[Optional[str]] = mapped_column(Text)
    reply_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    attempted_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    order: Mapped[Order] = relationship(back_populates="contacts")


class ErrorLog(Base):
    __tablename__ = "error_logs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    component: Mapped[str] = mapped_column(String(64), nullable=False)
    source_key: Mapped[Optional[str]] = mapped_column(String(64))
    message: Mapped[str] = mapped_column(Text, nullable=False)
    details: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class AppState(Base):
    """Runtime flags persisted across restarts."""

    __tablename__ = "app_state"

    key: Mapped[str] = mapped_column(String(64), primary_key=True)
    value_json: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )
