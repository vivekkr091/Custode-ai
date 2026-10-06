"""Permission SQLAlchemy model for Agent-to-Tool granular authorization."""

import enum
import uuid
from datetime import datetime
from typing import Optional

from sqlalchemy import DateTime, ForeignKey, Index, String, UniqueConstraint, Uuid
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class PermissionEffect(str, enum.Enum):
    """Authorization policy effect."""
    allow = "allow"
    deny = "deny"


class PermissionStatus(str, enum.Enum):
    """Lifecycle status of a permission grant."""
    active = "active"
    suspended = "suspended"
    revoked = "revoked"


class Permission(Base):
    """Granular authorization grant mapping an Agent to a Tool Operation in an Environment."""

    __tablename__ = "permissions"
    __table_args__ = (
        # Uniqueness: prevents duplicate identical permission grants
        UniqueConstraint(
            "organization_id",
            "agent_id",
            "tool_id",
            "operation_id",
            "environment",
            "effect",
            name="uq_permissions_identity_effect",
        ),
        # Composite index optimizing hot evaluation queries
        Index(
            "ix_permissions_eval_lookup",
            "organization_id",
            "agent_id",
            "tool_id",
            "operation_id",
            "environment",
            "status",
        ),
        Index("ix_permissions_organization_id", "organization_id"),
        Index("ix_permissions_agent_id", "agent_id"),
        Index("ix_permissions_tool_id", "tool_id"),
        Index("ix_permissions_operation_id", "operation_id"),
        Index("ix_permissions_environment", "environment"),
        Index("ix_permissions_status", "status"),
        Index("ix_permissions_effect", "effect"),
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
    environment: Mapped[str] = mapped_column(String(50), nullable=False)
    effect: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default=PermissionEffect.allow.value,
    )
    status: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default=PermissionStatus.active.value,
    )
    expires_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        default=None,
    )

    # Relationships (lazy loaded to prevent implicit overhead)
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
            f"<Permission id={self.id} org={self.organization_id} "
            f"agent={self.agent_id} tool={self.tool_id} op={self.operation_id} "
            f"env={self.environment!r} effect={self.effect!r} status={self.status!r}>"
        )
