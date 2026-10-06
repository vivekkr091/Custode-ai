"""PolicyVersion SQLAlchemy model representing immutable versioned policy rules."""

import enum
import uuid
from datetime import datetime
from typing import Any, Dict, Optional

from sqlalchemy import JSON, DateTime, ForeignKey, Index, Integer, String, UniqueConstraint, Uuid
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class PolicyVersionStatus(str, enum.Enum):
    """Lifecycle status of a policy version."""
    draft = "draft"
    published = "published"
    retired = "retired"


class PolicyVersion(Base):
    """Immutable version containing structured JSONB rules for security policy evaluation."""

    __tablename__ = "policy_versions"
    __table_args__ = (
        UniqueConstraint("policy_id", "version", name="uq_policy_versions_policy_version"),
        Index("ix_policy_versions_policy_id", "policy_id"),
        Index("ix_policy_versions_status", "status"),
        Index("ix_policy_versions_version", "version"),
    )

    policy_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("policies.id", ondelete="CASCADE"),
        nullable=False,
    )
    version: Mapped[int] = mapped_column(Integer, nullable=False)
    status: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default=PolicyVersionStatus.draft.value,
    )
    rules: Mapped[Dict[str, Any]] = mapped_column(
        JSON().with_variant(JSONB, "postgresql"),
        nullable=False,
        default=dict,
    )
    published_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        default=None,
    )

    # Relationship back to policy container
    policy: Mapped["Policy"] = relationship(  # type: ignore[name-defined]
        "Policy",
        back_populates="versions",
        lazy="noload",
    )

    def __repr__(self) -> str:
        return (
            f"<PolicyVersion id={self.id} policy_id={self.policy_id} "
            f"version={self.version} status={self.status!r}>"
        )
