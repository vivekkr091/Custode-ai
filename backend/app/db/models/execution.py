"""Execution SQLAlchemy model representing controlled tool execution audit records."""

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


class ExecutionStatus(str, enum.Enum):
    """Lifecycle status of a controlled tool execution."""
    pending = "pending"
    running = "running"
    succeeded = "succeeded"
    failed = "failed"
    blocked = "blocked"
    skipped = "skipped"


class Execution(Base):
    """Authoritative persisted audit record of a controlled Tool + ToolOperation execution."""

    __tablename__ = "executions"
    __table_args__ = (
        Index("ix_executions_organization_id", "organization_id"),
        Index("ix_executions_runtime_action_id", "runtime_action_id"),
        Index("ix_executions_org_status", "organization_id", "status"),
        Index("ix_executions_org_created_at", "organization_id", "created_at"),
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
    agent_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("agents.id", ondelete="CASCADE"),
        nullable=False,
    )
    tool_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("tools.id", ondelete="CASCADE"),
        nullable=False,
    )
    operation_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("tool_operations.id", ondelete="CASCADE"),
        nullable=False,
    )

    # Security governance linkage
    decision_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("decisions.id", ondelete="SET NULL"),
        nullable=True,
    )
    approval_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("approval_requests.id", ondelete="SET NULL"),
        nullable=True,
    )

    # Execution disposition
    status: Mapped[str] = mapped_column(
        String(30),
        nullable=False,
        default=ExecutionStatus.succeeded.value,
    )
    result: Mapped[Optional[Dict[str, Any]]] = mapped_column(
        JSON().with_variant(JSONB, "postgresql"),
        nullable=True,
    )
    error_code: Mapped[Optional[str]] = mapped_column(
        String(100),
        nullable=True,
    )
    error_message: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
    )

    # Execution timestamps
    started_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=utc_now,
    )
    completed_at: Mapped[Optional[datetime]] = mapped_column(
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
    agent: Mapped["Agent"] = relationship(  # type: ignore[name-defined]
        "Agent",
        lazy="noload",
    )
    tool: Mapped["Tool"] = relationship(  # type: ignore[name-defined]
        "Tool",
        lazy="noload",
    )
    operation: Mapped["ToolOperation"] = relationship(  # type: ignore[name-defined]
        "ToolOperation",
        lazy="noload",
    )
    decision: Mapped[Optional["Decision"]] = relationship(  # type: ignore[name-defined]
        "Decision",
        lazy="noload",
    )
    approval: Mapped[Optional["ApprovalRequest"]] = relationship(  # type: ignore[name-defined]
        "ApprovalRequest",
        lazy="noload",
    )

    def __repr__(self) -> str:
        return (
            f"<Execution id={self.id} org={self.organization_id} "
            f"action={self.runtime_action_id} status={self.status!r}>"
        )
