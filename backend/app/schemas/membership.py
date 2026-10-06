"""Pydantic schemas for Organization Membership entity."""

import uuid
from datetime import datetime
from pydantic import BaseModel, ConfigDict, Field
from app.db.models.membership import MembershipRole


class MembershipCreate(BaseModel):
    """Request payload for adding a user to an organization."""

    user_id: uuid.UUID = Field(..., description="UUID of the user to add")
    role: MembershipRole = Field(..., description="Role within the organization")


class MembershipResponse(BaseModel):
    """Response payload for an organization membership."""

    id: uuid.UUID
    organization_id: uuid.UUID
    user_id: uuid.UUID
    role: str
    status: str
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)
