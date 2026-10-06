"""Pydantic schemas for Policy Engine, Policy Versioning, and Rule Evaluation."""

import enum
import re
import uuid
from datetime import datetime
from typing import Any, List, Optional, Union
from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from app.db.models.policy import EnforcementMode, PolicyStatus
from app.db.models.policy_version import PolicyVersionStatus


ALLOWED_CONDITION_FIELDS = {
    "agent.id",
    "agent.environment",
    "tool.id",
    "tool.type",
    "operation.id",
    "operation.type",
    "operation.risk_level",
    "action.amount",
    "action.resource",
    "action.ip_address",
    "context.time.hour",
    "context.request_id",
    "behavior.anomaly.type",
    "behavior.anomaly.severity",
    "behavior.anomaly.score",
    "behavior.anomaly.confidence",
    "behavior.feature",
    "behavior.new_tool",
    "behavior.new_operation",
    "behavior.off_hours",
    "behavior.action_rate",
    "behavior.failure_rate",
}


class RuleOperator(str, enum.Enum):
    """Supported condition comparison operators."""
    eq = "eq"
    neq = "neq"
    gt = "gt"
    gte = "gte"
    lt = "lt"
    lte = "lte"
    in_ = "in"
    not_in = "not_in"
    contains = "contains"
    starts_with = "starts_with"
    ends_with = "ends_with"


class RuleEffect(str, enum.Enum):
    """Action effects produced by a matched policy rule."""
    allow = "allow"
    deny = "deny"
    require_approval = "require_approval"
    audit = "audit"


class PolicyDecision(str, enum.Enum):
    """Aggregate policy evaluation decisions (DENY > REQUIRE_APPROVAL > ALLOW > NO_MATCH)."""
    DENY = "DENY"
    REQUIRE_APPROVAL = "REQUIRE_APPROVAL"
    ALLOW = "ALLOW"
    NO_MATCH = "NO_MATCH"


class PolicyRuleCondition(BaseModel):
    """Single condition inside a policy rule evaluated with AND logic."""

    field: str = Field(..., description="Target attribute path to compare against action context")
    operator: str = Field(..., description="Comparison operator")
    value: Any = Field(..., description="Target reference value for comparison")

    @field_validator("field")
    @classmethod
    def validate_field(cls, v: str) -> str:
        if v not in ALLOWED_CONDITION_FIELDS:
            raise ValueError(
                f"Invalid condition field: '{v}'. Must be one of: {sorted(ALLOWED_CONDITION_FIELDS)}"
            )
        return v

    @field_validator("operator")
    @classmethod
    def validate_operator(cls, v: str) -> str:
        valid_ops = {op.value for op in RuleOperator}
        if v not in valid_ops:
            raise ValueError(
                f"Invalid operator: '{v}'. Must be one of: {sorted(valid_ops)}"
            )
        return v


class PolicyRule(BaseModel):
    """Named rule containing one or more conditions and an outcome effect."""

    name: str = Field(..., min_length=1, max_length=255, description="Human-readable rule name")
    description: Optional[str] = Field(None, max_length=1000, description="Optional rule description")
    conditions: List[PolicyRuleCondition] = Field(
        ..., min_length=1, description="List of conditions that all must evaluate to True"
    )
    effect: RuleEffect = Field(..., description="Effect produced when rule conditions match")


# --- Policy CRUD Schemas ---

class PolicyCreate(BaseModel):
    """Payload to create a new policy container."""

    name: str = Field(..., min_length=1, max_length=255, description="Policy name")
    slug: Optional[str] = Field(
        None,
        min_length=1,
        max_length=100,
        description="Unique URL-friendly slug within the organization",
    )
    description: Optional[str] = Field(None, max_length=1000, description="Policy description")
    enforcement_mode: EnforcementMode = Field(
        default=EnforcementMode.enforce,
        description="Whether rules are actively enforced or recorded in audit mode",
    )

    @field_validator("slug")
    @classmethod
    def validate_slug(cls, v: Optional[str]) -> Optional[str]:
        if v is not None:
            clean = v.strip().lower()
            if not re.match(r"^[a-z0-9]+(?:-[a-z0-9]+)*$", clean):
                raise ValueError("Slug must contain only lowercase alphanumeric characters and hyphens")
            return clean
        return v


class PolicyUpdate(BaseModel):
    """Payload to update an existing policy container."""

    name: Optional[str] = Field(None, min_length=1, max_length=255)
    description: Optional[str] = Field(None, max_length=1000)
    status: Optional[PolicyStatus] = Field(None, description="Updated policy lifecycle status")
    enforcement_mode: Optional[EnforcementMode] = Field(None, description="Updated enforcement mode")


class PolicyResponse(BaseModel):
    """Authoritative representation of a security policy."""

    id: uuid.UUID
    organization_id: uuid.UUID
    name: str
    slug: str
    description: Optional[str]
    status: str
    enforcement_mode: str
    active_version: Optional[int] = Field(None, description="Currently published policy version if any")
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class PolicyListResponse(BaseModel):
    """List of policies with total count."""

    items: List[PolicyResponse]
    total: int


# --- Policy Version Schemas ---

class PolicyVersionCreate(BaseModel):
    """Payload to draft a new policy version."""

    rules: List[PolicyRule] = Field(..., description="List of structured rules for this version")


class PolicyVersionResponse(BaseModel):
    """Authoritative representation of a policy version."""

    id: uuid.UUID
    policy_id: uuid.UUID
    version: int
    status: str
    rules: List[PolicyRule]
    published_at: Optional[datetime]
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)

    @model_validator(mode="before")
    @classmethod
    def parse_rules(cls, data: Any) -> Any:
        if isinstance(data, dict):
            rules_val = data.get("rules")
            if isinstance(rules_val, dict) and "rules" in rules_val:
                data["rules"] = rules_val["rules"]
            elif isinstance(rules_val, list):
                data["rules"] = rules_val
        elif hasattr(data, "rules"):
            # SQLAlchemy model instance
            rules_val = getattr(data, "rules", None)
            if isinstance(rules_val, dict) and "rules" in rules_val:
                # Return a dict to avoid modifying model
                return {
                    "id": data.id,
                    "policy_id": data.policy_id,
                    "version": data.version,
                    "status": data.status,
                    "rules": rules_val["rules"],
                    "published_at": data.published_at,
                    "created_at": data.created_at,
                    "updated_at": data.updated_at,
                }
            elif isinstance(rules_val, list):
                return {
                    "id": data.id,
                    "policy_id": data.policy_id,
                    "version": data.version,
                    "status": data.status,
                    "rules": rules_val,
                    "published_at": data.published_at,
                    "created_at": data.created_at,
                    "updated_at": data.updated_at,
                }
        return data


class PolicyVersionListResponse(BaseModel):
    """List of policy versions with total count."""

    items: List[PolicyVersionResponse]
    total: int


# --- Evaluation Context & Result Schemas ---

class ActionContext(BaseModel):
    """Action context representing the execution request to evaluate against policies."""

    agent_id: uuid.UUID = Field(..., description="Authenticated agent ID")
    agent_environment: Optional[str] = Field(None, description="Agent environment tier")
    tool_id: uuid.UUID = Field(..., description="Target tool ID")
    tool_type: Optional[str] = Field(None, description="Target tool category/type")
    operation_id: uuid.UUID = Field(..., description="Target tool operation ID")
    operation_type: Optional[str] = Field(None, description="Target tool operation type")
    operation_risk_level: Optional[str] = Field(None, description="Operation risk rating")
    amount: Optional[float] = Field(None, description="Transaction or operational amount")
    resource: Optional[str] = Field(None, description="Resource identifier or path")
    ip_address: Optional[str] = Field(None, description="Client or caller IP address")
    time_hour: Optional[int] = Field(None, ge=0, le=23, description="Hour of day (0-23)")
    request_id: Optional[str] = Field(None, description="Unique trace or request identifier")
    behavior_anomaly_type: Optional[str] = Field(None, description="Dominant anomaly type if any")
    behavior_anomaly_severity: Optional[str] = Field(None, description="Highest anomaly severity: LOW, MEDIUM, HIGH, CRITICAL")
    behavior_anomaly_score: Optional[float] = Field(None, description="Aggregate behavioral anomaly score (0-100)")
    behavior_anomaly_confidence: Optional[float] = Field(None, description="Anomaly confidence (0-1)")
    behavior_feature: Optional[str] = Field(None, description="Triggering behavioral feature")
    behavior_new_tool: Optional[bool] = Field(None, description="Whether tool is newly observed")
    behavior_new_operation: Optional[bool] = Field(None, description="Whether operation is newly observed")
    behavior_off_hours: Optional[bool] = Field(None, description="Whether action is off-hours")
    behavior_action_rate: Optional[float] = Field(None, description="Recent action rate per min")
    behavior_failure_rate: Optional[float] = Field(None, description="Recent failure rate")

    def get_field(self, field_path: str) -> Any:
        """Resolve dot-notation condition field path to the context value."""
        mapping = {
            "agent.id": str(self.agent_id),
            "agent.environment": self.agent_environment,
            "tool.id": str(self.tool_id),
            "tool.type": self.tool_type,
            "operation.id": str(self.operation_id),
            "operation.type": self.operation_type,
            "operation.risk_level": self.operation_risk_level,
            "action.amount": self.amount,
            "action.resource": self.resource,
            "action.ip_address": self.ip_address,
            "context.time.hour": self.time_hour,
            "context.request_id": self.request_id,
            "behavior.anomaly.type": self.behavior_anomaly_type,
            "behavior.anomaly.severity": self.behavior_anomaly_severity,
            "behavior.anomaly.score": self.behavior_anomaly_score,
            "behavior.anomaly.confidence": self.behavior_anomaly_confidence,
            "behavior.feature": self.behavior_feature,
            "behavior.new_tool": self.behavior_new_tool,
            "behavior.new_operation": self.behavior_new_operation,
            "behavior.off_hours": self.behavior_off_hours,
            "behavior.action_rate": self.behavior_action_rate,
            "behavior.failure_rate": self.behavior_failure_rate,
        }
        return mapping.get(field_path)


class MatchedRuleInfo(BaseModel):
    """Metadata describing a matched rule from an evaluated policy."""

    policy_id: uuid.UUID
    policy_name: str
    policy_version: int
    rule_name: str
    effect: str
    enforcement_mode: str
    policy_version_id: Optional[uuid.UUID] = None


class PolicyEvaluationRequest(BaseModel):
    """Input payload to evaluate an action context against organization policies."""

    context: ActionContext


class PolicyEvaluationResult(BaseModel):
    """Comprehensive, explainable output of policy evaluation."""

    decision: str = Field(..., description="Final decision: ALLOW, DENY, REQUIRE_APPROVAL, or NO_MATCH")
    reason: str = Field(..., description="Human-explainable justification")
    matched_rules: List[MatchedRuleInfo] = Field(
        default_factory=list, description="All rules that matched context conditions"
    )
    enforced_rules: List[MatchedRuleInfo] = Field(
        default_factory=list, description="Matched rules from enforced policies that contributed to decision"
    )
    audit_rules: List[MatchedRuleInfo] = Field(
        default_factory=list, description="Matched rules from audit policies that were recorded only"
    )
