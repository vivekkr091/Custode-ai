"""Pydantic schemas for Security Audit Trail events."""

from datetime import datetime
from typing import Any, Dict, List, Optional
import uuid

from pydantic import BaseModel, ConfigDict, Field


class AuditEventResponse(BaseModel):
    """Authoritative representation of an administrative security audit event."""
    id: uuid.UUID
    organization_id: Optional[uuid.UUID] = None
    user_id: Optional[uuid.UUID] = None
    actor_type: str = "USER"
    actor_id: Optional[str] = None
    actor_display: Optional[str] = None
    event_type: str = "CUSTOM"
    action: str
    resource_type: Optional[str] = None
    resource_id: Optional[str] = None
    target_type: Optional[str] = None
    target_id: Optional[str] = None
    outcome: str
    metadata: Optional[Dict[str, Any]] = Field(None, alias="event_metadata")
    request_id: Optional[str] = None
    ip_address: Optional[str] = None
    user_agent: Optional[str] = None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True, populate_by_name=True)


class AuditEventListResponse(BaseModel):
    """Paginated collection of audit events."""
    items: List[AuditEventResponse]
    total: int
