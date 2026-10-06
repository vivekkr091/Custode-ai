"""Audit Trail models for CUSTODE SDK."""

from typing import Any, Dict, List, Optional
from pydantic import Field

from custode.models.base import CUSTODEModel


class AuditEvent(CUSTODEModel):
    """Authoritative representation of a security audit event."""

    id: str
    organization_id: Optional[str] = None
    user_id: Optional[str] = None
    actor_type: str = "AGENT"
    actor_id: Optional[str] = None
    actor_display: Optional[str] = None
    event_type: str = "CUSTOM"
    action: str
    resource_type: Optional[str] = None
    resource_id: Optional[str] = None
    target_type: Optional[str] = None
    target_id: Optional[str] = None
    outcome: str
    metadata: Optional[Dict[str, Any]] = None
    request_id: Optional[str] = None
    ip_address: Optional[str] = None
    user_agent: Optional[str] = None
    created_at: Any


class AuditEventList(CUSTODEModel):
    """Paginated collection of audit events."""

    items: List[AuditEvent] = Field(default_factory=list)
    total: int = 0

    def __iter__(self):
        return iter(self.items)

    def __len__(self) -> int:
        return len(self.items)

    def __getitem__(self, index: int) -> AuditEvent:
        return self.items[index]
