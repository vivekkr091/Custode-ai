"""ApprovalRequest SQLAlchemy model representing human governance approval workflows."""

from datetime import datetime
import enum
from typing import Any, Dict, Optional
import uuid

from sqlalchemy import (
    DateTime,
    ForeignKey,
    Index,
    String,
    Text,
    Uuid,
)
from sqlalchemy import JSON
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, utc_now


class ApprovalStatus(str, enum.Enum):
    """Lifecycle status of an approval request."""
    pending = "pending"
    approved = "approved"
    rejected = "rejected"
    expired = "expired"
    cancelled = "cancelled"


class ApprovalRequest(Base):
    """Authoritative representation of a human governance approval request.

    Created when a RuntimeAction evaluates to REQUIRE_APPROVAL.
    Tracks reviewer assignment, decision snapshots, and revalidation state.
    """

    __tablename__ = "approval_requests"
    __table_args__ = (
        Index("ix_approval_requests_organization_id", "organization_id"),
        Index("ix_approval_requests_runtime_action_id", "runtime_action_id"),
        Index("ix_approval_requests_org_status", "organization_id", "status"),
        Index("ix_approval_requests_reviewer_user_id", "reviewer_user_id"),
        Index("ix_approval_requests_org_created_at", "organization_id", "created_at"),
    )

    organization_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=False,
    )
    runtime_action_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("runtime_actions.id", ondelete="CASCADE"),
        nullable=False,
    )
    decision_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("decisions.id", ondelete="CASCADE"),
        nullable=False,
    )

    # Requester context
    requested_by_agent_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("agents.id", ondelete="CASCADE"),
        nullable=False,
    )

    # Reviewer context
    reviewer_user_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )

    # Lifecycle state
    status: Mapped[str] = mapped_column(
        String(30),
        nullable=False,
        default=ApprovalStatus.pending.value,
    )

    # Metadata & justifications
    reason: Mapped[str] = mapped_column(
        Text,
        nullable=False,
    )
    rejection_reason: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
    )
    expires_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    # Security & governance context snapshots
    decision_snapshot: Mapped[Dict[str, Any]] = mapped_column(
        JSON().with_variant(JSONB, "postgresql"),
        nullable=False,
        default=dict,
    )
    approval_context: Mapped[Dict[str, Any]] = mapped_column(
        JSON().with_variant(JSONB, "postgresql"),
        nullable=False,
        default=dict,
    )

    # Review timestamp
    reviewed_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    # Relationships
    organization: Mapped["Organization"] = relationship(  # type: ignore[name-defined]
        "Organization",
        lazy="noload",
    )
    runtime_action: Mapped["RuntimeAction"] = relationship(  # type: ignore[name-defined]
        "RuntimeAction",
        lazy="noload",
    )
    decision: Mapped["Decision"] = relationship(  # type: ignore[name-defined]
        "Decision",
        lazy="noload",
    )
    requested_by_agent: Mapped["Agent"] = relationship(  # type: ignore[name-defined]
        "Agent",
        lazy="noload",
    )
    reviewer_user: Mapped[Optional["User"]] = relationship(  # type: ignore[name-defined]
        "User",
        lazy="noload",
    )

    def __repr__(self) -> str:
        return (
            f"<ApprovalRequest id={self.id} org={self.organization_id} "
            f"action={self.runtime_action_id} status={self.status!r}>"
        )
