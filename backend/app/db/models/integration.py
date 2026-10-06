"""SQLAlchemy database models for external Integrations and Webhooks."""

from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional
import uuid

from sqlalchemy import DateTime, ForeignKey, Index, Integer, JSON, String, Text, Uuid
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class IntegrationProvider(str, Enum):
    WEBHOOK = "webhook"
    SLACK = "slack"


class IntegrationStatus(str, Enum):
    ACTIVE = "active"
    SUSPENDED = "suspended"
    REVOKED = "revoked"


class Integration(Base):
    """External destination or connector configuration scoped to an organization."""

    __tablename__ = "integrations"

    organization_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    provider: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        default=IntegrationProvider.WEBHOOK.value,
        index=True,
    )
    status: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        default=IntegrationStatus.ACTIVE.value,
        index=True,
    )
    url: Mapped[str] = mapped_column(String(500), nullable=False)
    
    # Secret protection: secret_prefix for indexed identification,
    # secret_hash for integrity validation, encrypted_secret for signing dispatch.
    secret_prefix: Mapped[str] = mapped_column(String(30), nullable=False, index=True)
    secret_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    encrypted_secret: Mapped[str] = mapped_column(Text, nullable=False)

    subscribed_events: Mapped[List[str]] = mapped_column(
        JSON().with_variant(JSONB, "postgresql"),
        nullable=False,
        default=list,
    )
    headers: Mapped[Optional[Dict[str, str]]] = mapped_column(
        JSON().with_variant(JSONB, "postgresql"),
        nullable=True,
    )
    last_delivery_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    # Relationships
    organization: Mapped[Optional["Organization"]] = relationship(  # type: ignore[name-defined]
        "Organization",
        lazy="noload",
    )
    deliveries: Mapped[List["WebhookDelivery"]] = relationship(  # type: ignore[name-defined]
        "WebhookDelivery",
        back_populates="integration",
        cascade="all, delete-orphan",
        lazy="noload",
    )

    __table_args__ = (
        Index("ix_integrations_org_status", "organization_id", "status"),
        Index("ix_integrations_org_provider", "organization_id", "provider"),
    )

    def __repr__(self) -> str:
        return (
            f"<Integration id={self.id} org={self.organization_id} "
            f"name={self.name!r} provider={self.provider} status={self.status}>"
        )
