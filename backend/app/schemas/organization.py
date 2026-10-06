"""Pydantic schemas for Organization entity."""

import re
import uuid
from datetime import datetime
from typing import Optional
from pydantic import BaseModel, ConfigDict, Field, field_validator


def slugify(value: str) -> str:
    """Generate a clean URL-safe slug from a string."""
    value = value.lower().strip()
    value = re.sub(r"[^\w\s-]", "", value)
    value = re.sub(r"[\s_-]+", "-", value)
    return value.strip("-")


class OrganizationCreate(BaseModel):
    """Request payload for creating an organization."""

    name: str = Field(..., min_length=1, max_length=255, description="Organization name")
    slug: Optional[str] = Field(None, min_length=1, max_length=100, description="Optional custom slug")

    @field_validator("name")
    @classmethod
    def validate_name(cls, v: str) -> str:
        trimmed = v.strip()
        if not trimmed:
            raise ValueError("Organization name cannot be empty or only whitespace")
        return trimmed

    @field_validator("slug")
    @classmethod
    def validate_slug(cls, v: Optional[str]) -> Optional[str]:
        if v is not None:
            return slugify(v)
        return None


class OrganizationResponse(BaseModel):
    """Response payload for an organization."""

    id: uuid.UUID
    name: str
    slug: str
    status: str
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)
