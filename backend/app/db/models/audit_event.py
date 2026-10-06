"""Security Audit Event SQLAlchemy model for administrative and security actions tracking."""

from typing import Any, Dict, Optional
import uuid

from sqlalchemy import ForeignKey, Index, JSON, String, Uuid
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class AuditEvent(Base):
    """Tamper-resistant audit trail for human governance, agent activity, and security decisions."""

    __tablename__ = "audit_events"

    organization_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=True,
        index=True,
    )
    user_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    # Actor identification (USER, AGENT, SYSTEM)
    actor_type: Mapped[str] = mapped_column(String(50), nullable=False, default="USER", index=True)
    actor_id: Mapped[Optional[str]] = mapped_column(String(255), nullable=True, index=True)
    actor_display: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)

    # Event Taxonomy & Action
    event_type: Mapped[str] = mapped_column(String(100), nullable=False, default="CUSTOM", index=True)
    action: Mapped[str] = mapped_column(String(100), nullable=False, index=True)

    # Resource under audit
    resource_type: Mapped[Optional[str]] = mapped_column(String(100), nullable=True, index=True)
    resource_id: Mapped[Optional[str]] = mapped_column(String(255), nullable=True, index=True)

    # Legacy compatibility fields matching Milestone 14
    target_type: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    target_id: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)

    # Outcome & Context
    outcome: Mapped[str] = mapped_column(String(50), nullable=False, default="success", index=True)
    event_metadata: Mapped[Optional[Dict[str, Any]]] = mapped_column(
        "metadata",
        JSON().with_variant(JSONB, "postgresql"),
        nullable=True,
    )
    request_id: Mapped[Optional[str]] = mapped_column(String(100), nullable=True, index=True)
    ip_address: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    user_agent: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)

    # Explicit relationships
    organization: Mapped[Optional["Organization"]] = relationship(  # type: ignore[name-defined]
        "Organization",
        lazy="noload",
    )
    user: Mapped[Optional["User"]] = relationship(  # type: ignore[name-defined]
        "User",
        lazy="noload",
    )

    __table_args__ = (
        Index("ix_audit_events_org_event_type", "organization_id", "event_type"),
        Index("ix_audit_events_org_created_at", "organization_id", "created_at"),
    )

    def __repr__(self) -> str:
        return (
            f"<AuditEvent id={self.id} org={self.organization_id} "
            f"actor={self.actor_type}:{self.actor_id} event={self.event_type} outcome={self.outcome!r}>"
        )
