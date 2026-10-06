"""Pydantic schemas for Agent identity and registry."""

import uuid
from datetime import datetime
from typing import List, Optional
from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.db.models.agent import AgentEnvironment, AgentStatus, AgentType
from app.schemas.organization import slugify


class AgentCreate(BaseModel):
    """Request payload for registering a new agent within an organization."""

    name: str = Field(..., min_length=1, max_length=255, description="Agent display name")
    description: Optional[str] = Field(None, max_length=1000, description="Agent operational purpose")
    agent_type: AgentType = Field(default=AgentType.assistant, description="Architecture type")
    environment: AgentEnvironment = Field(default=AgentEnvironment.development, description="Deployment tier")
    slug: Optional[str] = Field(None, min_length=1, max_length=100, description="Optional custom unique slug")

    @field_validator("name")
    @classmethod
    def validate_name(cls, v: str) -> str:
        trimmed = v.strip()
        if not trimmed:
            raise ValueError("Agent name cannot be empty or only whitespace")
        return trimmed

    @field_validator("slug")
    @classmethod
    def validate_slug(cls, v: Optional[str]) -> Optional[str]:
        if v is not None:
            cleaned = slugify(v)
            if not cleaned:
                raise ValueError("Custom slug cannot be empty after normalization")
            return cleaned
        return None


class AgentUpdate(BaseModel):
    """Request payload for updating agent configuration details (excluding lifecycle status)."""

    name: Optional[str] = Field(None, min_length=1, max_length=255, description="Updated name")
    description: Optional[str] = Field(None, max_length=1000, description="Updated description")
    agent_type: Optional[AgentType] = Field(None, description="Updated architecture type")
    environment: Optional[AgentEnvironment] = Field(None, description="Updated deployment tier")

    @field_validator("name")
    @classmethod
    def validate_name(cls, v: Optional[str]) -> Optional[str]:
        if v is not None:
            trimmed = v.strip()
            if not trimmed:
                raise ValueError("Agent name cannot be empty or only whitespace")
            return trimmed
        return None


class AgentResponse(BaseModel):
    """Response payload representing an authoritative agent identity."""

    id: uuid.UUID
    organization_id: uuid.UUID
    name: str
    slug: str
    description: Optional[str]
    agent_type: str
    status: str
    environment: str
    created_at: datetime
    updated_at: datetime
    last_seen_at: Optional[datetime]

    model_config = ConfigDict(from_attributes=True)


class AgentListResponse(BaseModel):
    """Response payload containing a list of agents scoped to an organization."""

    items: List[AgentResponse]
    total: int
