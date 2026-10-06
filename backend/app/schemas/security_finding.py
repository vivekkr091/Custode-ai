"""Pydantic schemas for SecurityFinding serialization."""

from datetime import datetime
from typing import Any, Dict, List, Optional
import uuid
from pydantic import BaseModel, ConfigDict, Field


class SecurityFindingResponse(BaseModel):
    """Authoritative API response schema for a SecurityFinding."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    organization_id: uuid.UUID
    runtime_action_id: uuid.UUID
    scan_id: Optional[uuid.UUID] = None
    scanner: str
    category: str
    severity: str
    confidence: float = 1.0
    title: str
    description: str
    evidence: Optional[str] = None
    remediation: Optional[str] = None
    source: str = "sentinel"
    finding_metadata: Optional[Dict[str, Any]] = Field(default=None, alias="finding_metadata")
    created_at: datetime


class SecurityFindingListResponse(BaseModel):
    """Paginated list of SecurityFindings."""

    items: List[SecurityFindingResponse]
    total: int
