"""SQLAlchemy database models for Webhook Delivery records and Delivery Attempts."""

from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional
import uuid

from sqlalchemy import DateTime, ForeignKey, Index, Integer, JSON, String, Text, Uuid
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, utc_now


class DeliveryStatus(str, Enum):
    PENDING = "pending"
    DELIVERED = "delivered"
    RETRYING = "retrying"
    FAILED = "failed"


class AttemptStatus(str, Enum):
    SUCCESS = "success"
    FAILED = "failed"
    RETRYABLE_FAILURE = "retryable_failure"


class WebhookDelivery(Base):
    """Authoritative ledger entry for an external security event notification delivery."""

    __tablename__ = "webhook_deliveries"

    organization_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    integration_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("integrations.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    event_id: Mapped[Optional[str]] = mapped_column(String(100), nullable=True, index=True)
    event_type: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    request_id: Mapped[Optional[str]] = mapped_column(String(100), nullable=True, index=True)

    delivery_status: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        default=DeliveryStatus.PENDING.value,
        index=True,
    )
    attempt_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    max_attempts: Mapped[int] = mapped_column(Integer, nullable=False, default=3)

    # Versioned, sanitized payload snapshot
    payload: Mapped[Dict[str, Any]] = mapped_column(
        JSON().with_variant(JSONB, "postgresql"),
        nullable=False,
    )

    response_status_code: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    sanitized_response_summary: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    next_retry_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        index=True,
    )
    delivered_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    # Relationships
    integration: Mapped[Optional["Integration"]] = relationship(  # type: ignore[name-defined]
        "Integration",
        back_populates="deliveries",
        lazy="noload",
    )
    attempts: Mapped[List["WebhookAttempt"]] = relationship(
        "WebhookAttempt",
        back_populates="delivery",
        cascade="all, delete-orphan",
        lazy="noload",
        order_by="WebhookAttempt.attempt_number",
    )

    __table_args__ = (
        Index("ix_webhook_deliveries_org_status", "organization_id", "delivery_status"),
        Index("ix_webhook_deliveries_org_created_at", "organization_id", "created_at"),
        Index("ix_webhook_deliveries_integration_status", "integration_id", "delivery_status"),
    )

    def __repr__(self) -> str:
        return (
            f"<WebhookDelivery id={self.id} integration={self.integration_id} "
            f"event={self.event_type} status={self.delivery_status} attempts={self.attempt_count}>"
        )


class WebhookAttempt(Base):
    """Detailed audit attempt record for an individual HTTP delivery dispatch."""

    __tablename__ = "webhook_attempts"

    delivery_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("webhook_deliveries.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    attempt_number: Mapped[int] = mapped_column(Integer, nullable=False)
    status: Mapped[str] = mapped_column(String(50), nullable=False)
    response_status_code: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    duration_ms: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    sanitized_error: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    attempted_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=utc_now,
    )

    # Relationships
    delivery: Mapped[Optional["WebhookDelivery"]] = relationship(
        "WebhookDelivery",
        back_populates="attempts",
        lazy="noload",
    )

    __table_args__ = (
        Index("ix_webhook_attempts_delivery_attempt", "delivery_id", "attempt_number"),
    )

    def __repr__(self) -> str:
        return (
            f"<WebhookAttempt id={self.id} delivery={self.delivery_id} "
            f"attempt={self.attempt_number} status={self.status} code={self.response_status_code}>"
        )
