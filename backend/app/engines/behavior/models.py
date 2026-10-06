"""Pydantic schemas and dataclasses for the CUSTODE Behavioral & Anomaly Detection Engine."""

from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional
import uuid
from pydantic import BaseModel, ConfigDict, Field

from app.db.models.agent_behavior_baseline import BaselineState
from app.db.models.behavioral_anomaly import (
    AnomalySeverity,
    AnomalyStatus,
    AnomalyType,
)


class BehavioralFeature(BaseModel):
    """Normalized behavioral feature extracted from runtime action context and telemetry."""

    name: str
    value: Any
    baseline_value: Optional[Any] = None
    deviation: float = 0.0
    explanation: str

    model_config = ConfigDict(from_attributes=True)


class BehavioralFinding(BaseModel):
    """Structured behavioral anomaly finding produced by detection rules."""

    id: Optional[uuid.UUID] = None
    anomaly_type: AnomalyType
    severity: AnomalySeverity
    confidence: float = Field(ge=0.0, le=1.0)
    score: float = Field(ge=0.0, le=100.0)
    feature: str
    baseline_value: Dict[str, Any] = Field(default_factory=dict)
    observed_value: Dict[str, Any] = Field(default_factory=dict)
    deviation: float = 0.0
    explanation: str
    evidence: List[Any] = Field(default_factory=list)
    signals: List[str] = Field(default_factory=list)

    model_config = ConfigDict(from_attributes=True)


class BehaviorEvaluationResult(BaseModel):
    """Complete evaluation output from the Behavioral Engine."""

    baseline_state: BaselineState
    observation_count: int
    anomalies: List[BehavioralFinding] = Field(default_factory=list)
    behavioral_score: float = Field(ge=0.0, le=100.0, default=0.0)
    highest_severity: Optional[AnomalySeverity] = None
    features: Dict[str, Any] = Field(default_factory=dict)
    engine_version: str = "1.0.0"

    model_config = ConfigDict(from_attributes=True)


class AgentBehaviorProfile(BaseModel):
    """Summary of normal behavioral baseline and recent anomalies for an agent."""

    agent_id: uuid.UUID
    environment: str
    state: BaselineState
    action_count: int
    observation_window_seconds: int
    typical_tools: List[str] = Field(default_factory=list)
    typical_operations: List[str] = Field(default_factory=list)
    average_actions_per_hour: float = 0.0
    peak_actions_per_hour: float = 0.0
    average_risk_score: float = 0.0
    operational_hours: str = "08:00 - 20:00 UTC"
    last_observed_at: Optional[datetime] = None
    recent_anomalies_count: int = 0
    anomaly_counts_by_severity: Dict[str, int] = Field(default_factory=dict)

    model_config = ConfigDict(from_attributes=True)


class BehavioralAnomalyResponse(BaseModel):
    """API response schema for a persisted BehavioralAnomaly."""

    id: uuid.UUID
    organization_id: uuid.UUID
    agent_id: uuid.UUID
    runtime_action_id: Optional[uuid.UUID] = None
    anomaly_type: str
    severity: str
    confidence: float
    score: float
    feature: str
    baseline_value: Dict[str, Any]
    observed_value: Dict[str, Any]
    deviation: float
    explanation: str
    evidence: List[Any]
    environment: str
    status: str
    resolved_by: Optional[uuid.UUID] = None
    resolved_at: Optional[datetime] = None
    resolution_note: Optional[str] = None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class BehavioralAnomalyListResponse(BaseModel):
    items: List[BehavioralAnomalyResponse]
    total: int


class AnomalyResolutionRequest(BaseModel):
    note: Optional[str] = Field(None, max_length=1000, description="Optional resolution note or justification")


class BehaviorMetrics(BaseModel):
    """Real-time behavioral telemetry for the organization."""

    monitored_agents: int = 0
    established_baselines: int = 0
    learning_baselines: int = 0
    cold_start_agents: int = 0
    total_anomalies: int = 0
    open_anomalies: int = 0
    critical_anomalies: int = 0
    high_anomalies: int = 0
    action_rate_spikes: int = 0
    failure_spikes: int = 0
    off_hours_events: int = 0
    new_tool_events: int = 0
    action_loops: int = 0
