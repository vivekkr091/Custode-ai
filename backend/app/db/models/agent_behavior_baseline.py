"""AgentBehaviorBaseline SQLAlchemy model representing persistent behavioral baseline per agent and environment."""

from datetime import datetime
from enum import Enum
from typing import Any, Dict, Optional
import uuid

from sqlalchemy import (
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    JSON,
    String,
    UniqueConstraint,
    Uuid,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class BaselineState(str, Enum):
    COLD_START = "COLD_START"
    LEARNING = "LEARNING"
    ESTABLISHED = "ESTABLISHED"


class AgentBehaviorBaseline(Base):
    """Authoritative behavioral baseline representing typical operational profiles for an agent in a specific environment."""

    __tablename__ = "agent_behavior_baselines"

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
    environment: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        default="production",
        index=True,
    )

    # Maturity and lifecycle state
    state: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        default=BaselineState.COLD_START.value,
        server_default=BaselineState.COLD_START.value,
        index=True,
    )
    observation_window_seconds: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=86400,
        server_default="86400",
    )

    # Activity Counters
    action_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")
    successful_action_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")
    failed_action_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")
    blocked_action_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")
    approval_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")

    # Scoped Distributions (JSON dictionaries: key -> count)
    tool_counts: Mapped[Dict[str, Any]] = mapped_column(
        JSON().with_variant(JSONB, "postgresql"),
        nullable=False,
        default=dict,
        server_default="{}",
    )
    operation_counts: Mapped[Dict[str, Any]] = mapped_column(
        JSON().with_variant(JSONB, "postgresql"),
        nullable=False,
        default=dict,
        server_default="{}",
    )
    resource_counts: Mapped[Dict[str, Any]] = mapped_column(
        JSON().with_variant(JSONB, "postgresql"),
        nullable=False,
        default=dict,
        server_default="{}",
    )

    # Sensitivity & Severity Distributions
    sensitive_action_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")
    destructive_action_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")
    transfer_action_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")

    # Financial & Numeric Aggregations
    total_amount: Mapped[float] = mapped_column(Float, nullable=False, default=0.0, server_default="0.0")
    average_amount: Mapped[float] = mapped_column(Float, nullable=False, default=0.0, server_default="0.0")
    max_amount: Mapped[float] = mapped_column(Float, nullable=False, default=0.0, server_default="0.0")
    amount_variance: Mapped[float] = mapped_column(Float, nullable=False, default=0.0, server_default="0.0")

    # Rate & Temporal Profile
    average_actions_per_hour: Mapped[float] = mapped_column(Float, nullable=False, default=0.0, server_default="0.0")
    peak_actions_per_hour: Mapped[float] = mapped_column(Float, nullable=False, default=0.0, server_default="0.0")
    average_risk_score: Mapped[float] = mapped_column(Float, nullable=False, default=0.0, server_default="0.0")
    max_risk_score: Mapped[float] = mapped_column(Float, nullable=False, default=0.0, server_default="0.0")

    # Business Operating Hours (UTC hours 0-23)
    operational_hours_start: Mapped[int] = mapped_column(Integer, nullable=False, default=8, server_default="8")
    operational_hours_end: Mapped[int] = mapped_column(Integer, nullable=False, default=20, server_default="20")

    last_observed_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    baseline_version: Mapped[int] = mapped_column(Integer, nullable=False, default=1, server_default="1")

    __table_args__ = (
        UniqueConstraint("organization_id", "agent_id", "environment", name="uq_agent_env_baseline"),
        Index("ix_agent_behavior_baselines_org_state", "organization_id", "state"),
    )

    def __init__(self, **kwargs: Any) -> None:
        defaults = {
            "state": BaselineState.COLD_START.value,
            "observation_window_seconds": 86400,
            "action_count": 0,
            "successful_action_count": 0,
            "failed_action_count": 0,
            "blocked_action_count": 0,
            "approval_count": 0,
            "tool_counts": {},
            "operation_counts": {},
            "resource_counts": {},
            "sensitive_action_count": 0,
            "destructive_action_count": 0,
            "transfer_action_count": 0,
            "total_amount": 0.0,
            "average_amount": 0.0,
            "max_amount": 0.0,
            "amount_variance": 0.0,
            "average_actions_per_hour": 0.0,
            "peak_actions_per_hour": 0.0,
            "average_risk_score": 0.0,
            "max_risk_score": 0.0,
            "operational_hours_start": 8,
            "operational_hours_end": 20,
            "baseline_version": 1,
        }
        for k, v in defaults.items():
            if k not in kwargs:
                kwargs[k] = v
        super().__init__(**kwargs)

