"""RuntimeAction SQLAlchemy model representing a concrete action requested by an agent."""

import enum
from datetime import datetime
from typing import Any, Dict, Optional
import uuid

from sqlalchemy import (
    DateTime,
    Float,
    ForeignKey,
    Index,
    Numeric,
    String,
    Uuid,
)
from sqlalchemy import JSON
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class ActionEnvironment(str, enum.Enum):
    """Runtime execution environment tier."""
    dev = "dev"
    staging = "staging"
    prod = "prod"


class ActionStatus(str, enum.Enum):
    """Lifecycle status of a RuntimeAction.

    Note: Status is an operational lifecycle state, not the final authorization decision.
    """
    pending = "pending"
    evaluating = "evaluating"
    approved = "approved"
    denied = "denied"
    executed = "executed"
    failed = "failed"
    cancelled = "cancelled"


class RuntimeAction(Base):
    """Authoritative representation of a single action invocation requested by an AI agent."""

    __tablename__ = "runtime_actions"
    __table_args__ = (
        Index("ix_runtime_actions_organization_id", "organization_id"),
        Index("ix_runtime_actions_org_agent", "organization_id", "agent_id"),
        Index("ix_runtime_actions_org_created_at", "organization_id", "created_at"),
        Index("ix_runtime_actions_request_id", "request_id"),
        Index("ix_runtime_actions_status", "status"),
        Index("ix_runtime_actions_environment", "environment"),
    )

    organization_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("organizations.id", ondelete="CASCADE"),
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

    # Action Identity & Context
    request_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        nullable=False,
        default=uuid.uuid4,
    )
    environment: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default=ActionEnvironment.dev.value,
    )
    resource: Mapped[Optional[str]] = mapped_column(
        String(500),
        nullable=True,
    )
    resource_type: Mapped[Optional[str]] = mapped_column(
        String(100),
        nullable=True,
    )

    # Action Payload
    action_type: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
    )
    parameters: Mapped[Dict[str, Any]] = mapped_column(
        JSON().with_variant(JSONB, "postgresql"),
        nullable=False,
        default=dict,
    )

    # Optional Contextual Fields
    amount: Mapped[Optional[float]] = mapped_column(
        Numeric(precision=18, scale=4, asdecimal=False),
        nullable=True,
    )
    currency: Mapped[Optional[str]] = mapped_column(
        String(10),
        nullable=True,
    )
    ip_address: Mapped[Optional[str]] = mapped_column(
        String(45),
        nullable=True,
    )
    user_agent: Mapped[Optional[str]] = mapped_column(
        String(500),
        nullable=True,
    )

    # Lifecycle State
    status: Mapped[str] = mapped_column(
        String(30),
        nullable=False,
        default=ActionStatus.pending.value,
    )

    # Lifecycle Timestamps
    evaluated_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        default=None,
    )
    completed_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        default=None,
    )

    # Relationships
    organization: Mapped["Organization"] = relationship(  # type: ignore[name-defined]
        "Organization",
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

    def __repr__(self) -> str:
        return (
            f"<RuntimeAction id={self.id} org={self.organization_id} "
            f"agent={self.agent_id} tool={self.tool_id} op={self.operation_id} "
            f"status={self.status!r}>"
        )
