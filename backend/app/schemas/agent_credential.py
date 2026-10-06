"""Pydantic schemas for Agent Credentials and Authenticated Agent context."""

import uuid
from datetime import datetime
from typing import List, Optional
from pydantic import BaseModel, ConfigDict, Field, field_validator


class AgentCredentialCreate(BaseModel):
    """Request payload for generating a new agent API credential."""

    name: str = Field(..., min_length=1, max_length=255, description="Human-readable credential name")
    expires_at: Optional[datetime] = Field(None, description="Optional UTC expiration timestamp")

    @field_validator("name")
    @classmethod
    def validate_name(cls, v: str) -> str:
        trimmed = v.strip()
        if not trimmed:
            raise ValueError("Credential name cannot be empty or only whitespace")
        return trimmed


class AgentCredentialCreatedResponse(BaseModel):
    """Response payload returned ONLY upon credential creation containing the raw API key."""

    id: uuid.UUID
    agent_id: uuid.UUID
    name: str
    api_key: str = Field(..., description="Raw API key — displayed ONCE and never retrievable again")
    credential_prefix: str
    status: str
    created_at: datetime
    expires_at: Optional[datetime] = None

    model_config = ConfigDict(from_attributes=True)


class AgentCredentialResponse(BaseModel):
    """Safe response payload for credential inspection. NEVER returns raw key or hash."""

    id: uuid.UUID
    agent_id: uuid.UUID
    name: str
    credential_prefix: str
    status: str
    created_at: datetime
    expires_at: Optional[datetime] = None
    revoked_at: Optional[datetime] = None
    last_used_at: Optional[datetime] = None

    model_config = ConfigDict(from_attributes=True)


class AgentCredentialListResponse(BaseModel):
    """List response for agent credentials metadata."""

    items: List[AgentCredentialResponse]
    total: int


class AuthenticatedAgent(BaseModel):
    """Immutable context representation of a cryptographically authenticated agent identity."""

    organization_id: uuid.UUID
    agent_id: uuid.UUID
    credential_id: uuid.UUID

    model_config = ConfigDict(frozen=True)
