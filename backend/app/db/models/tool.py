"""Tool SQLAlchemy model representing a callable external capability."""

import enum
import uuid
from typing import Optional

from sqlalchemy import ForeignKey, Index, String, UniqueConstraint, Uuid
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class ToolType(str, enum.Enum):
    """Categorization of external capability."""
    api = "api"
    database = "database"
    filesystem = "filesystem"
    shell = "shell"
    mcp = "mcp"
    cloud = "cloud"
    internal = "internal"
    custom = "custom"


class ToolStatus(str, enum.Enum):
    """Lifecycle state of a registered tool."""
    active = "active"
    suspended = "suspended"
    revoked = "revoked"


class ToolEnvironment(str, enum.Enum):
    """Deployment tier of the tool capability."""
    development = "development"
    staging = "staging"
    production = "production"


class Tool(Base):
    """External callable capability registered within an organization tenant boundary."""

    __tablename__ = "tools"
    __table_args__ = (
        UniqueConstraint("organization_id", "slug", name="uq_tools_org_slug"),
        Index("ix_tools_organization_id", "organization_id"),
        Index("ix_tools_status", "status"),
        Index("ix_tools_environment", "environment"),
    )

    organization_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=False,
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    slug: Mapped[str] = mapped_column(String(100), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(String(1000), nullable=True)
    tool_type: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        default=ToolType.api.value,
    )
    status: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default=ToolStatus.active.value,
    )
    environment: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        default=ToolEnvironment.development.value,
    )
    endpoint: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)

    # Relationships
    organization: Mapped["Organization"] = relationship(  # type: ignore[name-defined]
        "Organization",
        back_populates="tools",
        lazy="noload",
    )
    operations: Mapped[list["ToolOperation"]] = relationship(  # type: ignore[name-defined]
        "ToolOperation",
        back_populates="tool",
        cascade="all, delete-orphan",
        lazy="noload",
    )

    def __repr__(self) -> str:
        return (
            f"<Tool id={self.id} org_id={self.organization_id} "
            f"slug={self.slug!r} status={self.status!r}>"
        )
