"""Pydantic schemas for Contextual Risk Assessment Engine, factors, and responses."""

from datetime import datetime
from typing import Any, Dict, List, Optional
import uuid
from pydantic import BaseModel, ConfigDict, Field

from app.db.models.risk_assessment import RiskLevel


class RiskFactor(BaseModel):
    """Structured representation of an individual risk contributor."""

    factor: str = Field(..., description="Unique factor identifier/slug")
    category: str = Field(..., description="Category (operation, tool, environment, resource, amount, behavioral, etc.)")
    score: float = Field(..., description="Numeric risk score contribution")
    severity: str = Field(..., description="Severity rating: low, medium, high, critical")
    reason: str = Field(..., description="Human-understandable justification")
    metadata: Optional[Dict[str, Any]] = Field(default_factory=dict, description="Contextual metadata for the factor")


class RiskEvaluationResult(BaseModel):
    """In-memory calculation outcome produced by the Risk Engine."""

    risk_score: float = Field(..., ge=0.0, le=100.0, description="Normalized score 0-100")
    risk_level: str = Field(..., description="Risk level (LOW, MEDIUM, HIGH, CRITICAL)")
    factors: List[RiskFactor] = Field(default_factory=list, description="All contributing risk factors")
    triggered_rules: List[str] = Field(default_factory=list, description="Rule IDs that were triggered")
    explanation: str = Field(..., description="Synthesized explainability text")
    engine_version: str = Field(default="1.0.0", description="Version of the risk engine ruleset")


class RiskAssessmentResponse(BaseModel):
    """Authoritative representation of a persisted RiskAssessment."""

    id: uuid.UUID
    organization_id: uuid.UUID
    runtime_action_id: uuid.UUID
    risk_level: str
    risk_score: float
    factors: List[RiskFactor]
    triggered_rules: List[str]
    explanation: str
    engine_version: str
    assessed_at: datetime
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class RiskAssessmentListResponse(BaseModel):
    """List of persisted risk assessments."""

    items: List[RiskAssessmentResponse]
    total: int
