"""Human Approval Workflow models for CUSTODE SDK."""

from typing import Any, Dict, List, Optional
from pydantic import Field

from custode.models.base import CUSTODEModel


class ApprovalRequest(CUSTODEModel):
    """Authoritative human governance approval record."""

    id: str
    organization_id: str
    runtime_action_id: str
    decision_id: str
    status: str
    reason: Optional[str] = None
    reviewer_id: Optional[str] = None
    reviewer_notes: Optional[str] = None
    rejection_reason: Optional[str] = None
    created_at: Any
    updated_at: Optional[Any] = None
    expires_at: Optional[Any] = None
    reviewed_at: Optional[Any] = None

    @property
    def is_pending(self) -> bool:
        """True if the approval is pending human review."""
        return self.status.lower() == "pending"

    @property
    def is_approved(self) -> bool:
        """True if authorized human reviewer approved the action."""
        return self.status.lower() == "approved"

    @property
    def is_rejected(self) -> bool:
        """True if human reviewer rejected the action."""
        return self.status.lower() == "rejected"


class ApprovalList(CUSTODEModel):
    """Paginated collection of approval requests."""

    items: List[ApprovalRequest] = Field(default_factory=list)
    total: int = 0

    def __iter__(self):
        return iter(self.items)

    def __len__(self) -> int:
        return len(self.items)

    def __getitem__(self, index: int) -> ApprovalRequest:
        return self.items[index]
