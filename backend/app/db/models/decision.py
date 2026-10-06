"""Decision SQLAlchemy model representing a persisted authorization decision."""

import enum
from datetime import datetime
from typing import Any, Dict, List, Optional
import uuid

from sqlalchemy import (
    DateTime,
    ForeignKey,
    Index,
    Numeric,
    String,
    Text,
    Uuid,
)
from sqlalchemy import JSON
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, utc_now


class DecisionType(str, enum.Enum):
    """Authoritative authorization decision outcomes."""
    allow = "allow"
    block = "block"
    require_approval = "require_approval"


class Decision(Base):
    """Persisted authoritative authorization decision record for a RuntimeAction.

    Decisions are immutable historical audit records. Every decision evaluation
    creates a new record without mutating or overwriting past decisions.
    """

    __tablename__ = "decisions"
    __table_args__ = (
        Index("ix_decisions_organization_id", "organization_id"),
        Index("ix_decisions_runtime_action_id", "runtime_action_id"),
        Index("ix_decisions_org_decision", "organization_id", "decision"),
        Index("ix_decisions_org_created_at", "organization_id", "created_at"),
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

    # Decision outcome
    decision: Mapped[str] = mapped_column(
        String(30),
        nullable=False,
    )
    reason: Mapped[str] = mapped_column(
        Text,
        nullable=False,
    )

    # Evaluated context & contributing engine outcomes
    risk_level: Mapped[Optional[str]] = mapped_column(
        String(20),
        nullable=True,
    )
    risk_score: Mapped[Optional[float]] = mapped_column(
        Numeric(precision=5, scale=2, asdecimal=False),
        nullable=True,
    )
    permission_effect: Mapped[Optional[str]] = mapped_column(
        String(20),
        nullable=True,
    )
    policy_effect: Mapped[Optional[str]] = mapped_column(
        String(30),
        nullable=True,
    )
    policy_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        Uuid(as_uuid=True),
        nullable=True,
    )
    policy_version_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        Uuid(as_uuid=True),
        nullable=True,
    )

    # Explainability & trace
    factors: Mapped[List[Dict[str, Any]]] = mapped_column(
        JSON().with_variant(JSONB, "postgresql"),
        nullable=False,
        default=list,
    )
    evaluation_trace: Mapped[Dict[str, Any]] = mapped_column(
        JSON().with_variant(JSONB, "postgresql"),
        nullable=False,
        default=dict,
    )
    engine_version: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default="1.0.0",
    )

    evaluated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=utc_now,
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

    def __repr__(self) -> str:
        return (
            f"<Decision id={self.id} org={self.organization_id} "
            f"action={self.runtime_action_id} decision={self.decision!r} "
            f"risk={self.risk_level!r}>"
        )
