"""BehavioralAnomaly SQLAlchemy model representing detected behavioral deviations and anomalies."""

from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional
import uuid

from sqlalchemy import (
    DateTime,
    Float,
    ForeignKey,
    Index,
    JSON,
    String,
    Text,
    Uuid,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class AnomalyType(str, Enum):
    ACTION_RATE_SPIKE = "ACTION_RATE_SPIKE"
    TOOL_USAGE_SPIKE = "TOOL_USAGE_SPIKE"
    NEW_TOOL_USAGE = "NEW_TOOL_USAGE"
    NEW_OPERATION_USAGE = "NEW_OPERATION_USAGE"
    NEW_SENSITIVE_RESOURCE = "NEW_SENSITIVE_RESOURCE"
    AMOUNT_DEVIATION = "AMOUNT_DEVIATION"
    FAILURE_SPIKE = "FAILURE_SPIKE"
    BLOCK_SPIKE = "BLOCK_SPIKE"
    PRIVILEGE_ESCALATION_PATTERN = "PRIVILEGE_ESCALATION_PATTERN"
    OFF_HOURS_ACTIVITY = "OFF_HOURS_ACTIVITY"
    ACTION_LOOP = "ACTION_LOOP"
    MULTI_SIGNAL_ANOMALY = "MULTI_SIGNAL_ANOMALY"


class AnomalySeverity(str, Enum):
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    CRITICAL = "CRITICAL"


class AnomalyStatus(str, Enum):
    OPEN = "OPEN"
    REVIEWED = "REVIEWED"
    RESOLVED = "RESOLVED"
    SUPPRESSED = "SUPPRESSED"


class BehavioralAnomaly(Base):
    """Authoritative behavioral anomaly finding detected by statistical and rule-based behavioral monitors."""

    __tablename__ = "behavioral_anomalies"

    organization_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    agent_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("agents.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    runtime_action_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("runtime_actions.id", ondelete="CASCADE"),
        nullable=True,
        index=True,
    )

    anomaly_type: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    severity: Mapped[str] = mapped_column(String(20), nullable=False, default=AnomalySeverity.LOW.value, index=True)
    confidence: Mapped[float] = mapped_column(Float, nullable=False, default=1.0)
    score: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    feature: Mapped[str] = mapped_column(String(100), nullable=False, index=True)

    baseline_value: Mapped[Dict[str, Any]] = mapped_column(
        JSON().with_variant(JSONB, "postgresql"),
        nullable=False,
        default=dict,
        server_default="{}",
    )
    observed_value: Mapped[Dict[str, Any]] = mapped_column(
        JSON().with_variant(JSONB, "postgresql"),
        nullable=False,
        default=dict,
        server_default="{}",
    )
    deviation: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    explanation: Mapped[str] = mapped_column(Text, nullable=False)
    evidence: Mapped[List[Any]] = mapped_column(
        JSON().with_variant(JSONB, "postgresql"),
        nullable=False,
        default=list,
        server_default="[]",
    )
    environment: Mapped[str] = mapped_column(String(50), nullable=False, default="production", index=True)
    status: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        default=AnomalyStatus.OPEN.value,
        server_default=AnomalyStatus.OPEN.value,
        index=True,
    )

    resolved_by: Mapped[Optional[uuid.UUID]] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )
    resolved_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    resolution_note: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    __table_args__ = (
        Index("ix_behavioral_anomalies_org_agent", "organization_id", "agent_id"),
        Index("ix_behavioral_anomalies_org_status", "organization_id", "status"),
        Index("ix_behavioral_anomalies_created_at", "organization_id", "created_at"),
    )

    def __init__(self, **kwargs: Any) -> None:
        defaults = {
            "severity": AnomalySeverity.LOW.value,
            "confidence": 1.0,
            "score": 0.0,
            "baseline_value": {},
            "observed_value": {},
            "deviation": 0.0,
            "evidence": [],
            "environment": "production",
            "status": AnomalyStatus.OPEN.value,
        }
        for k, v in defaults.items():
            if k not in kwargs:
                kwargs[k] = v
        super().__init__(**kwargs)

