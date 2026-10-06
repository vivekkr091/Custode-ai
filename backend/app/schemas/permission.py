"""Pydantic schemas for Permission Engine and Agent-to-Tool Authorization."""

import uuid
from datetime import datetime
from typing import List, Optional
from pydantic import BaseModel, ConfigDict, Field

from app.db.models.permission import PermissionEffect, PermissionStatus
from app.db.models.tool import ToolEnvironment


class PermissionCreate(BaseModel):
    """Request payload for granting or denying permission to an agent."""

    agent_id: uuid.UUID = Field(..., description="Target agent identity")
    tool_id: uuid.UUID = Field(..., description="Target tool capability")
    operation_id: uuid.UUID = Field(..., description="Target tool operation")
    environment: ToolEnvironment = Field(default=ToolEnvironment.development, description="Target environment tier")
    effect: PermissionEffect = Field(default=PermissionEffect.allow, description="Allow or explicit deny grant")
    expires_at: Optional[datetime] = Field(None, description="Optional expiration timestamp in UTC")


class PermissionUpdate(BaseModel):
    """Request payload for modifying permission properties (e.g. expiration)."""

    expires_at: Optional[datetime] = Field(None, description="Updated expiration timestamp in UTC")


class PermissionResponse(BaseModel):
    """Authoritative representation of a permission grant."""

    id: uuid.UUID
    organization_id: uuid.UUID
    agent_id: uuid.UUID
    tool_id: uuid.UUID
    operation_id: uuid.UUID
    environment: str
    effect: str
    status: str
    created_at: datetime
    updated_at: datetime
    expires_at: Optional[datetime]

    model_config = ConfigDict(from_attributes=True)


class PermissionListResponse(BaseModel):
    """Response payload containing a list of permissions."""

    items: List[PermissionResponse]
    total: int


class PermissionEvaluationRequest(BaseModel):
    """Input payload for testing or executing authorization evaluation."""

    agent_id: uuid.UUID = Field(..., description="Target agent UUID")
    tool_id: uuid.UUID = Field(..., description="Target tool UUID")
    operation_id: uuid.UUID = Field(..., description="Target operation UUID")
    environment: ToolEnvironment = Field(..., description="Execution environment tier")


class PermissionEvaluationResponse(BaseModel):
    """Structured decision returned by the Permission Engine."""

    allowed: bool = Field(..., description="Whether action is permitted under least privilege")
    effect: str = Field(..., description="Effective result: 'allow' or 'deny'")
    reason: str = Field(..., description="Human-explainable justification")
    permission_id: Optional[uuid.UUID] = Field(None, description="Matched permission grant ID if any")
