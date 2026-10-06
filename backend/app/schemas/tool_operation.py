"""Pydantic schemas for ToolOperation entities."""

import uuid
from datetime import datetime
from typing import List, Optional
from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.db.models.tool_operation import OperationRiskLevel, OperationStatus, OperationType
from app.schemas.organization import slugify


class ToolOperationCreate(BaseModel):
    """Request payload for adding an operation under a Tool."""

    name: str = Field(..., min_length=1, max_length=255, description="Operation name")
    description: Optional[str] = Field(None, max_length=1000, description="Operation action details")
    operation_type: OperationType = Field(default=OperationType.read, description="Action categorization")
    risk_level: OperationRiskLevel = Field(default=OperationRiskLevel.medium, description="Baseline risk rating")
    slug: Optional[str] = Field(None, min_length=1, max_length=100, description="Optional custom unique slug")

    @field_validator("name")
    @classmethod
    def validate_name(cls, v: str) -> str:
        trimmed = v.strip()
        if not trimmed:
            raise ValueError("Operation name cannot be empty or only whitespace")
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


class ToolOperationUpdate(BaseModel):
    """Request payload for modifying an operation's attributes (excluding lifecycle status)."""

    name: Optional[str] = Field(None, min_length=1, max_length=255)
    description: Optional[str] = Field(None, max_length=1000)
    operation_type: Optional[OperationType] = None
    risk_level: Optional[OperationRiskLevel] = None

    @field_validator("name")
    @classmethod
    def validate_name(cls, v: Optional[str]) -> Optional[str]:
        if v is not None:
            trimmed = v.strip()
            if not trimmed:
                raise ValueError("Operation name cannot be empty or only whitespace")
            return trimmed
        return None


class ToolOperationResponse(BaseModel):
    """Authoritative response representation of a ToolOperation."""

    id: uuid.UUID
    tool_id: uuid.UUID
    name: str
    slug: str
    description: Optional[str]
    operation_type: str
    risk_level: str
    status: str
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class ToolOperationListResponse(BaseModel):
    """Response payload containing a list of operations belonging to a tool."""

    items: List[ToolOperationResponse]
    total: int
