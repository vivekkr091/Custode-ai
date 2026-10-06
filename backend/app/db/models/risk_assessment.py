"""RiskAssessment SQLAlchemy model representing a persisted contextual risk evaluation."""

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


class RiskLevel(str, enum.Enum):
    """Normalized risk classification levels."""
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    CRITICAL = "CRITICAL"


class RiskAssessment(Base):
    """Persisted record of a deterministic contextual risk assessment for a RuntimeAction."""

    __tablename__ = "risk_assessments"
    __table_args__ = (
        Index("ix_risk_assessments_organization_id", "organization_id"),
        Index("ix_risk_assessments_runtime_action_id", "runtime_action_id"),
        Index("ix_risk_assessments_org_risk_level", "organization_id", "risk_level"),
        Index("ix_risk_assessments_org_created_at", "organization_id", "created_at"),
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

    # Risk result
    risk_level: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
    )
    risk_score: Mapped[float] = mapped_column(
        Numeric(precision=5, scale=2, asdecimal=False),
        nullable=False,
    )

    # Assessment metadata
    factors: Mapped[List[Dict[str, Any]]] = mapped_column(
        JSON().with_variant(JSONB, "postgresql"),
        nullable=False,
        default=list,
    )
    triggered_rules: Mapped[List[str]] = mapped_column(
        JSON().with_variant(JSONB, "postgresql"),
        nullable=False,
        default=list,
    )
    explanation: Mapped[str] = mapped_column(
        Text,
        nullable=False,
    )
    engine_version: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default="1.0.0",
    )

    assessed_at: Mapped[datetime] = mapped_column(
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
            f"<RiskAssessment id={self.id} org={self.organization_id} "
            f"action={self.runtime_action_id} score={self.risk_score} "
            f"level={self.risk_level!r}>"
        )
