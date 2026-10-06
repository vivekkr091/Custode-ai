"""ToolOperation SQLAlchemy model representing a specific action exposed by a Tool."""

import enum
import uuid
from typing import Optional

from sqlalchemy import ForeignKey, Index, String, UniqueConstraint, Uuid
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class OperationType(str, enum.Enum):
    """Categorization of the operation action type."""
    read = "read"
    write = "write"
    delete = "delete"
    execute = "execute"
    transfer = "transfer"
    admin = "admin"
    custom = "custom"


class OperationRiskLevel(str, enum.Enum):
    """Baseline risk level assigned to the tool operation."""
    low = "low"
    medium = "medium"
    high = "high"
    critical = "critical"


class OperationStatus(str, enum.Enum):
    """Lifecycle state of a tool operation."""
    active = "active"
    suspended = "suspended"
    revoked = "revoked"


class ToolOperation(Base):
    """Callable sub-action belonging strictly to a parent Tool."""

    __tablename__ = "tool_operations"
    __table_args__ = (
        UniqueConstraint("tool_id", "slug", name="uq_tool_operations_tool_slug"),
        Index("ix_tool_operations_tool_id", "tool_id"),
        Index("ix_tool_operations_status", "status"),
        Index("ix_tool_operations_operation_type", "operation_type"),
        Index("ix_tool_operations_risk_level", "risk_level"),
    )

    tool_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("tools.id", ondelete="CASCADE"),
        nullable=False,
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    slug: Mapped[str] = mapped_column(String(100), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(String(1000), nullable=True)
    operation_type: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        default=OperationType.read.value,
    )
    risk_level: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        default=OperationRiskLevel.medium.value,
    )
    status: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default=OperationStatus.active.value,
    )

    # Relationship back to parent tool
    tool: Mapped["Tool"] = relationship(  # type: ignore[name-defined]
        "Tool",
        back_populates="operations",
        lazy="noload",
    )

    def __repr__(self) -> str:
        return (
            f"<ToolOperation id={self.id} tool_id={self.tool_id} "
            f"slug={self.slug!r} risk={self.risk_level!r} status={self.status!r}>"
        )
