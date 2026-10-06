"""MCPTool SQLAlchemy model representing a discovered capability from an MCP server."""

from datetime import datetime
import enum
from typing import Any, Dict, Optional
import uuid

from sqlalchemy import (
    Boolean,
    DateTime,
    ForeignKey,
    Index,
    String,
    Text,
    UniqueConstraint,
    Uuid,
)
from sqlalchemy import JSON
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, utc_now


class MCPToolStatus(str, enum.Enum):
    """Lifecycle state of an MCP tool."""
    DISCOVERED = "DISCOVERED"
    ACTIVE = "ACTIVE"
    SUSPENDED = "SUSPENDED"
    REVOKED = "REVOKED"


class MCPToolRiskLevel(str, enum.Enum):
    """Baseline risk tier assigned to the MCP tool."""
    low = "low"
    medium = "medium"
    high = "high"
    critical = "critical"


class MCPTool(Base):
    """Representation of an MCP tool discovered from an untrusted MCP server."""

    __tablename__ = "mcp_tools"
    __table_args__ = (
        UniqueConstraint("mcp_server_id", "slug", name="uq_mcp_tools_server_slug"),
        Index("ix_mcp_tools_org_status", "organization_id", "status"),
        Index("ix_mcp_tools_org_schema_drift", "organization_id", "schema_changed"),
        Index("ix_mcp_tools_mcp_server_id", "mcp_server_id"),
    )

    organization_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    mcp_server_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("mcp_servers.id", ondelete="CASCADE"),
        nullable=False,
    )

    # Scoped mapping to CUSTODE Tool & ToolOperation
    tool_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("tools.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    operation_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("tool_operations.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )

    name: Mapped[str] = mapped_column(String(255), nullable=False)
    slug: Mapped[str] = mapped_column(String(100), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    input_schema: Mapped[Dict[str, Any]] = mapped_column(
        JSON().with_variant(JSONB, "postgresql"),
        nullable=False,
        default=dict,
    )
    output_schema: Mapped[Optional[Dict[str, Any]]] = mapped_column(
        JSON().with_variant(JSONB, "postgresql"),
        nullable=True,
    )

    status: Mapped[str] = mapped_column(
        String(30),
        nullable=False,
        default=MCPToolStatus.DISCOVERED.value,
    )
    risk_level: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default=MCPToolRiskLevel.medium.value,
    )

    schema_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    previous_schema_hash: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    schema_changed: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)

    discovered_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=utc_now,
    )
    activated_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    tool_metadata: Mapped[Optional[Dict[str, Any]]] = mapped_column(
        "metadata",
        JSON().with_variant(JSONB, "postgresql"),
        nullable=True,
    )

    # Relationships
    server: Mapped["MCPServer"] = relationship("MCPServer", back_populates="tools")
