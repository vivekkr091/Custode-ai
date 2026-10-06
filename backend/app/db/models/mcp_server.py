"""MCPServer SQLAlchemy model representing a registered MCP server boundary."""

import enum
from typing import Any, Dict, List, Optional
import uuid

from sqlalchemy import (
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

from app.db.base import Base


class MCPServerType(str, enum.Enum):
    """Controlled MCP server types."""
    REMOTE = "REMOTE"
    LOCAL = "LOCAL"
    INTERNAL = "INTERNAL"
    THIRD_PARTY = "THIRD_PARTY"
    CUSTOM = "CUSTOM"


class MCPTransportType(str, enum.Enum):
    """Supported and controlled MCP transports."""
    HTTP = "HTTP"
    SSE = "SSE"
    STREAMABLE_HTTP = "STREAMABLE_HTTP"
    STDIO = "STDIO"
    MOCK = "MOCK"


class MCPServerStatus(str, enum.Enum):
    """Lifecycle states of an MCP server."""
    ACTIVE = "ACTIVE"
    SUSPENDED = "SUSPENDED"
    REVOKED = "REVOKED"


class MCPTrustLevel(str, enum.Enum):
    """Contextual trust tier of an MCP server."""
    UNTRUSTED = "UNTRUSTED"
    VERIFIED = "VERIFIED"
    TRUSTED = "TRUSTED"


class MCPServer(Base):
    """Authoritative representation of a registered MCP server."""

    __tablename__ = "mcp_servers"
    __table_args__ = (
        UniqueConstraint("organization_id", "slug", name="uq_mcp_servers_org_slug"),
        Index("ix_mcp_servers_org_status", "organization_id", "status"),
        Index("ix_mcp_servers_org_trust", "organization_id", "trust_level"),
        Index("ix_mcp_servers_org_created_at", "organization_id", "created_at"),
    )

    organization_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    name: Mapped[str] = mapped_column(String(255), nullable=False)
    slug: Mapped[str] = mapped_column(String(100), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    server_type: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        default=MCPServerType.REMOTE.value,
    )
    endpoint: Mapped[str] = mapped_column(String(500), nullable=False)
    transport: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        default=MCPTransportType.HTTP.value,
    )
    status: Mapped[str] = mapped_column(
        String(30),
        nullable=False,
        default=MCPServerStatus.ACTIVE.value,
    )
    trust_level: Mapped[str] = mapped_column(
        String(30),
        nullable=False,
        default=MCPTrustLevel.UNTRUSTED.value,
    )
    environment: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        default="development",
    )

    server_metadata: Mapped[Optional[Dict[str, Any]]] = mapped_column(
        "metadata",
        JSON().with_variant(JSONB, "postgresql"),
        nullable=True,
    )

    # Relationships
    tools: Mapped[List["MCPTool"]] = relationship(
        "MCPTool",
        back_populates="server",
        cascade="all, delete-orphan",
    )
