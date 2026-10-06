"""Pydantic schemas for CUSTODE Authorization Decision Engine."""

from datetime import datetime
import enum
from typing import Any, Dict, List, Optional, Union
import uuid
from pydantic import BaseModel, ConfigDict, Field


class DecisionType(str, enum.Enum):
    """Authoritative authorization decision outcomes."""
    allow = "allow"
    block = "block"
    require_approval = "require_approval"


class DecisionFactor(BaseModel):
    """Structured fact or contributing factor leading to the authorization decision."""

    source: str = Field(..., description="Engine or subsystem origin: permission, policy, risk, etc.")
    type: str = Field(..., description="Category or characteristic of the factor")
    value: Any = Field(..., description="Underlying factor value or state")
    effect: str = Field(..., description="Effect exerted by this factor: allow, deny, block, require_approval")
    reason: str = Field(..., description="Human-readable explanation of factor contribution")


class DecisionEvaluationResult(BaseModel):
    """Authoritative outcome produced by the Decision Engine evaluator."""

    decision: DecisionType = Field(..., description="Authoritative authorization decision")
    reason: str = Field(..., description="Human-readable explanation generated from structured facts")
    risk_level: Optional[str] = Field(None, description="Contextual risk level assessed")
    risk_score: Optional[float] = Field(None, description="Contextual numeric risk score (0-100)")
    permission_effect: Optional[str] = Field(None, description="Outcome from Permission Engine (allow, deny)")
    policy_effect: Optional[str] = Field(None, description="Outcome from Policy Engine (allow, deny, require_approval, no_match)")
    policy_id: Optional[uuid.UUID] = Field(None, description="ID of primary contributing policy if applicable")
    policy_version_id: Optional[uuid.UUID] = Field(None, description="ID of primary contributing policy version if applicable")
    factors: List[Union[DecisionFactor, Dict[str, Any]]] = Field(
        default_factory=list,
        description="Structured factors contributing to the evaluation",
    )
    evaluation_trace: Dict[str, Any] = Field(
        default_factory=dict,
        description="Detailed trace recording permission, policy, risk, and final resolution",
    )
    engine_version: str = Field("1.0.0", description="Decision engine semantic version")


class DecisionResponse(BaseModel):
    """API response model representing a persisted Decision audit record."""

    id: uuid.UUID
    organization_id: uuid.UUID
    runtime_action_id: uuid.UUID
    decision: str
    reason: str
    risk_level: Optional[str] = None
    risk_score: Optional[float] = None
    permission_effect: Optional[str] = None
    policy_effect: Optional[str] = None
    policy_id: Optional[uuid.UUID] = None
    policy_version_id: Optional[uuid.UUID] = None
    factors: List[Dict[str, Any]]
    evaluation_trace: Dict[str, Any]
    engine_version: str
    created_at: datetime
    evaluated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class DecisionListResponse(BaseModel):
    """Paginated collection of authorization decisions."""

    items: List[DecisionResponse]
    total: int
