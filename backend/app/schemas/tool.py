"""Pydantic schemas for Tool registry entities."""

import uuid
from datetime import datetime
from typing import List, Optional
from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.db.models.tool import ToolEnvironment, ToolStatus, ToolType
from app.schemas.organization import slugify


class ToolCreate(BaseModel):
    """Request payload for registering an external capability tool within an organization."""

    name: str = Field(..., min_length=1, max_length=255, description="Tool name")
    description: Optional[str] = Field(None, max_length=1000, description="Tool purpose and context")
    tool_type: ToolType = Field(default=ToolType.api, description="Category of external capability")
    environment: ToolEnvironment = Field(default=ToolEnvironment.development, description="Target environment")
    endpoint: Optional[str] = Field(None, max_length=500, description="Base URL, connection URI, or socket path")
    slug: Optional[str] = Field(None, min_length=1, max_length=100, description="Optional custom unique slug")

    @field_validator("name")
    @classmethod
    def validate_name(cls, v: str) -> str:
        trimmed = v.strip()
        if not trimmed:
            raise ValueError("Tool name cannot be empty or only whitespace")
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


class ToolUpdate(BaseModel):
    """Request payload for updating tool configuration (excluding lifecycle status)."""

    name: Optional[str] = Field(None, min_length=1, max_length=255)
    description: Optional[str] = Field(None, max_length=1000)
    tool_type: Optional[ToolType] = None
    environment: Optional[ToolEnvironment] = None
    endpoint: Optional[str] = Field(None, max_length=500)

    @field_validator("name")
    @classmethod
    def validate_name(cls, v: Optional[str]) -> Optional[str]:
        if v is not None:
            trimmed = v.strip()
            if not trimmed:
                raise ValueError("Tool name cannot be empty or only whitespace")
            return trimmed
        return None


class ToolResponse(BaseModel):
    """Authoritative response representation of a registered Tool entity."""

    id: uuid.UUID
    organization_id: uuid.UUID
    name: str
    slug: str
    description: Optional[str]
    tool_type: str
    status: str
    environment: str
    endpoint: Optional[str]
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class ToolListResponse(BaseModel):
    """Response payload containing a list of tools scoped to an organization."""

    items: List[ToolResponse]
    total: int
