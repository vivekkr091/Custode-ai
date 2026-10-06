"""Pydantic schemas for RuntimeAction requests, responses, normalization, and context."""

from datetime import datetime
from typing import Any, Dict, List, Optional
import uuid
from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.db.models.runtime_action import ActionEnvironment, ActionStatus


class RuntimeResource(BaseModel):
    """Resource descriptor targeted by a runtime action."""

    resource: Optional[str] = Field(None, max_length=500, description="Resource URI, identifier, or path")
    resource_type: Optional[str] = Field(None, max_length=100, description="Resource category/type")


class RuntimeActionCreate(BaseModel):
    """Request payload to create and register an intended runtime action.

    Note: organization_id, agent_id, and lifecycle state are server-controlled.
    """

    tool_id: uuid.UUID = Field(..., description="Target tool capability UUID")
    operation_id: uuid.UUID = Field(..., description="Target tool operation UUID")
    environment: str = Field(..., description="Target runtime environment: dev, staging, prod")
    action_type: str = Field(..., min_length=1, max_length=100, description="Operation or action discriminator")
    resource: Optional[str] = Field(None, max_length=500, description="Resource identifier or path")
    resource_type: Optional[str] = Field(None, max_length=100, description="Resource type classification")
    parameters: Optional[Dict[str, Any]] = Field(default_factory=dict, description="Structured action parameters")
    amount: Optional[float] = Field(None, description="Optional operational or transaction amount")
    currency: Optional[str] = Field(None, max_length=10, description="Optional ISO currency code")
    ip_address: Optional[str] = Field(None, max_length=45, description="Caller IP address")
    user_agent: Optional[str] = Field(None, max_length=500, description="Client or agent user-agent string")
    request_id: Optional[uuid.UUID] = Field(None, description="Optional client-supplied request correlation UUID")

    # Extra fields forbidden so clients cannot inject organization_id, agent_id, status, etc.
    model_config = ConfigDict(extra="forbid")

    @field_validator("parameters")
    @classmethod
    def validate_parameters(cls, v: Optional[Dict[str, Any]]) -> Dict[str, Any]:
        if v is None:
            return {}
        if not isinstance(v, dict):
            raise ValueError("Parameters must be a JSON object dictionary")
        return v


class RuntimeActionTransitionRequest(BaseModel):
    """Payload to request an explicit lifecycle transition for a runtime action."""

    target_status: ActionStatus = Field(..., description="Target lifecycle state")


class RuntimeActionContext(BaseModel):
    """Canonical, normalized in-memory context representing an action for evaluation."""

    organization_id: uuid.UUID
    agent_id: uuid.UUID
    tool_id: uuid.UUID
    operation_id: uuid.UUID
    request_id: uuid.UUID
    environment: str
    action_type: str
    resource: Optional[str] = None
    resource_type: Optional[str] = None
    parameters: Dict[str, Any] = Field(default_factory=dict)
    amount: Optional[float] = None
    currency: Optional[str] = None
    ip_address: Optional[str] = None
    user_agent: Optional[str] = None

    model_config = ConfigDict(frozen=True)


class RuntimeActionResponse(BaseModel):
    """Authoritative API representation of a registered RuntimeAction."""

    id: uuid.UUID
    organization_id: uuid.UUID
    agent_id: uuid.UUID
    tool_id: uuid.UUID
    operation_id: uuid.UUID
    request_id: uuid.UUID
    environment: str
    action_type: str
    resource: Optional[str]
    resource_type: Optional[str]
    parameters: Dict[str, Any]
    amount: Optional[float]
    currency: Optional[str]
    ip_address: Optional[str]
    user_agent: Optional[str]
    status: str
    created_at: datetime
    updated_at: datetime
    evaluated_at: Optional[datetime]
    completed_at: Optional[datetime]

    model_config = ConfigDict(from_attributes=True)


class RuntimeActionListResponse(BaseModel):
    """List of RuntimeActions with total count."""

    items: List[RuntimeActionResponse]
    total: int
