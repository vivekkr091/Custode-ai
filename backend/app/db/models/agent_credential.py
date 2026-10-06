"""Agent Credential SQLAlchemy model for cryptographic agent authentication."""

import enum
import uuid
from datetime import datetime
from typing import Optional

from sqlalchemy import DateTime, ForeignKey, Index, String, UniqueConstraint, Uuid
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class CredentialStatus(str, enum.Enum):
    """Lifecycle status of an agent credential."""
    active = "active"
    revoked = "revoked"
    expired = "expired"


class AgentCredential(Base):
    """Secure hashed credential representing an authenticatable agent identity token."""

    __tablename__ = "agent_credentials"
    __table_args__ = (
        UniqueConstraint("credential_prefix", name="uq_agent_credentials_prefix"),
        Index("ix_agent_credentials_agent_id", "agent_id"),
        Index("ix_agent_credentials_prefix", "credential_prefix"),
        Index("ix_agent_credentials_status", "status"),
    )

    agent_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("agents.id", ondelete="CASCADE"),
        nullable=False,
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    credential_prefix: Mapped[str] = mapped_column(String(64), nullable=False)
    credential_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    status: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default=CredentialStatus.active.value,
    )
    expires_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        default=None,
    )
    revoked_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        default=None,
    )
    last_used_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        default=None,
    )

    # Relationship to owning agent (loaded explicitly)
    agent: Mapped["Agent"] = relationship(  # type: ignore[name-defined]
        "Agent",
        back_populates="credentials",
        lazy="noload",
    )

    def __repr__(self) -> str:
        return (
            f"<AgentCredential id={self.id} agent_id={self.agent_id} "
            f"prefix={self.credential_prefix!r} status={self.status!r}>"
        )
