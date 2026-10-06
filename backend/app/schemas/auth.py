"""Pydantic schemas for Human User Authentication and Session Management."""

from datetime import datetime
import re
from typing import Any, Dict, List, Optional
import uuid

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.schemas.membership import MembershipResponse
from app.schemas.organization import OrganizationResponse
from app.schemas.user import UserResponse

EMAIL_REGEX = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


class LoginRequest(BaseModel):
    """Payload for human user authentication."""
    email: str = Field(..., max_length=320, description="User email address")
    password: Optional[str] = Field(None, description="Password required in production mode")
    organization_id: Optional[uuid.UUID] = Field(None, description="Optional target organization context")

    @field_validator("email")
    @classmethod
    def validate_and_normalize_email(cls, v: str) -> str:
        normalized = v.strip().lower()
        if not EMAIL_REGEX.match(normalized):
            raise ValueError("Invalid email format")
        return normalized


class SwitchOrganizationRequest(BaseModel):
    """Payload to switch active organization context."""
    organization_id: uuid.UUID


class AuthenticatedUserContext(BaseModel):
    """Full authenticated human user session context."""
    id: uuid.UUID
    email: str
    display_name: str
    status: str
    last_login_at: Optional[datetime] = None
    active_organization: Optional[OrganizationResponse] = None
    active_membership: Optional[MembershipResponse] = None
    memberships: List[MembershipResponse] = Field(default_factory=list)
    # Compatibility aliases for client convenience
    user_id: Optional[uuid.UUID] = None
    organization_id: Optional[uuid.UUID] = None
    role: Optional[str] = None

    model_config = ConfigDict(from_attributes=True)


class AuthTokenResponse(BaseModel):
    """Safe token response returned on successful login or organization switch."""
    access_token: str
    token_type: str = "bearer"
    expires_in: int
    user: UserResponse
    active_organization: Optional[OrganizationResponse] = None
    organization: Optional[OrganizationResponse] = None
    role: Optional[str] = None
    memberships: List[MembershipResponse] = Field(default_factory=list)


class LogoutResponse(BaseModel):
    """Safe logout acknowledgement."""
    message: str = "Logged out successfully"
