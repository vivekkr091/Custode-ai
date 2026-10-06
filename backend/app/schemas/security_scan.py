"""Pydantic schemas for SecurityScan serialization."""

from datetime import datetime
from typing import Any, Dict, List, Optional
import uuid
from pydantic import BaseModel, ConfigDict, Field

from app.schemas.security_finding import SecurityFindingResponse


class SecurityScanResponse(BaseModel):
    """Authoritative API response schema for a SecurityScan."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    organization_id: uuid.UUID
    runtime_action_id: uuid.UUID
    scanner_count: int
    findings_count: int
    critical_count: int
    high_count: int
    medium_count: int
    low_count: int
    highest_severity: str
    status: str
    scanners_run: List[str]
    execution_time_ms: float
    error_message: Optional[str] = None
    scan_metadata: Optional[Dict[str, Any]] = Field(default=None, alias="scan_metadata")
    created_at: datetime
    findings: Optional[List[SecurityFindingResponse]] = None


class SecurityScanListResponse(BaseModel):
    """Paginated list of SecurityScans."""

    items: List[SecurityScanResponse]
    total: int


class SecurityMetricsResponse(BaseModel):
    """Aggregated security metrics across scans and findings."""

    total_scans: int = 0
    total_findings: int = 0
    critical_count: int = 0
    high_count: int = 0
    medium_count: int = 0
    low_count: int = 0
    category_distribution: Dict[str, int] = Field(default_factory=dict)
    scanner_distribution: Dict[str, int] = Field(default_factory=dict)
