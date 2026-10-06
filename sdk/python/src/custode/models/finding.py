"""Security finding models for CUSTODE SDK."""

from typing import Any, Dict, List, Optional
from pydantic import Field

from custode.models.base import CUSTODEModel


class SecurityFinding(CUSTODEModel):
    """Authoritative vulnerability finding detected by Sentinel security scans."""

    id: str
    organization_id: str
    runtime_action_id: Optional[str] = None
    scan_id: Optional[str] = None
    scanner: str
    category: str
    severity: str
    confidence: float = 1.0
    title: str
    description: str
    evidence: Optional[str] = None
    remediation: Optional[str] = None
    source: str = "sentinel"
    finding_metadata: Optional[Dict[str, Any]] = None
    created_at: Any

    @property
    def is_critical(self) -> bool:
        """True if finding severity is CRITICAL."""
        return self.severity.upper() == "CRITICAL"

    @property
    def is_high(self) -> bool:
        """True if finding severity is HIGH."""
        return self.severity.upper() == "HIGH"


class SecurityFindingList(CUSTODEModel):
    """Paginated collection of security findings."""

    items: List[SecurityFinding] = Field(default_factory=list)
    total: int = 0

    def __iter__(self):
        return iter(self.items)

    def __len__(self) -> int:
        return len(self.items)

    def __getitem__(self, index: int) -> SecurityFinding:
        return self.items[index]
