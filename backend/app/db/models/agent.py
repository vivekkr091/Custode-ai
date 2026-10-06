"""Agent SQLAlchemy model representing an autonomous or assistant AI agent entity."""

import enum
import uuid
from datetime import datetime
from typing import Optional

from sqlalchemy import DateTime, ForeignKey, Index, String, UniqueConstraint, Uuid
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class AgentType(str, enum.Enum):
    """Categorization of agent operational architecture."""
    autonomous = "autonomous"
    assistant = "assistant"
    workflow = "workflow"
    service = "service"


class AgentStatus(str, enum.Enum):
    """Lifecycle state of an agent."""
    active = "active"
    suspended = "suspended"
    revoked = "revoked"


class AgentEnvironment(str, enum.Enum):
    """Deployment tier of an agent."""
    development = "development"
    staging = "staging"
    production = "production"


class Agent(Base):
    """First-class AI agent security identity, tenant-scoped to an Organization."""

    __tablename__ = "agents"
    __table_args__ = (
        # Uniqueness boundary: slug is unique per organization, not globally.
        UniqueConstraint("organization_id", "slug", name="uq_agents_org_slug"),
        Index("ix_agents_organization_id", "organization_id"),
        Index("ix_agents_status", "status"),
        Index("ix_agents_environment", "environment"),
    )

    organization_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=False,
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    slug: Mapped[str] = mapped_column(String(100), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(String(1000), nullable=True)
    agent_type: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        default=AgentType.assistant.value,
    )
    status: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default=AgentStatus.active.value,
    )
    environment: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        default=AgentEnvironment.development.value,
    )
    last_seen_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        default=None,
    )

    # Relationship to owning organization (explicitly lazy loaded)
    organization: Mapped["Organization"] = relationship(  # type: ignore[name-defined]
        "Organization",
        back_populates="agents",
        lazy="noload",
    )

    # Relationship: one agent -> many credentials
    credentials: Mapped[list["AgentCredential"]] = relationship(  # type: ignore[name-defined]
        "AgentCredential",
        back_populates="agent",
        lazy="noload",
    )

    def __repr__(self) -> str:
        return (
            f"<Agent id={self.id} org_id={self.organization_id} "
            f"slug={self.slug!r} status={self.status!r}>"
        )
