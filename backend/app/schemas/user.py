"""Pydantic schemas for User entity."""

from datetime import datetime
import re
from typing import Optional
import uuid

from pydantic import BaseModel, ConfigDict, Field, field_validator

EMAIL_REGEX = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


class UserCreate(BaseModel):
    """Request payload for creating a user."""

    email: str = Field(..., max_length=320, description="User email address")
    display_name: str = Field(..., min_length=1, max_length=255, description="Display name")
    password: Optional[str] = Field(None, min_length=8, description="Optional initial user password")

    @field_validator("email")
    @classmethod
    def validate_and_normalize_email(cls, v: str) -> str:
        normalized = v.strip().lower()
        if not EMAIL_REGEX.match(normalized):
            raise ValueError("Invalid email format")
        return normalized

    @field_validator("display_name")
    @classmethod
    def validate_display_name(cls, v: str) -> str:
        trimmed = v.strip()
        if not trimmed:
            raise ValueError("Display name cannot be empty or whitespace only")
        return trimmed


class UserResponse(BaseModel):
    """Response payload for a user. Never exposes password hashes or credentials."""

    id: uuid.UUID
    email: str
    display_name: str
    status: str
    last_login_at: Optional[datetime] = None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)
