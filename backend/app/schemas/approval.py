"""Pydantic schemas for Human Approval Workflow and Revalidation."""

from datetime import datetime
import enum
from typing import Any, Dict, List, Optional
import uuid
from pydantic import BaseModel, ConfigDict, Field


class ApprovalStatus(str, enum.Enum):
    """Lifecycle status of an approval request."""
    pending = "pending"
    approved = "approved"
    rejected = "rejected"
    expired = "expired"
    cancelled = "cancelled"


class ApprovalCreate(BaseModel):
    """Payload to initiate a human approval request for a RuntimeAction."""

    decision_id: uuid.UUID = Field(..., description="ID of authoritative REQUIRE_APPROVAL Decision")
    reason: Optional[str] = Field(None, max_length=2000, description="Optional request rationale")
    expires_at: Optional[datetime] = Field(None, description="Optional expiration timestamp for approval")


class ApprovalApproveRequest(BaseModel):
    """Payload to approve a pending human governance approval request."""

    reviewer_note: Optional[str] = Field(None, max_length=2000, description="Optional reviewer comment")


class ApprovalRejectRequest(BaseModel):
    """Payload to reject a pending human governance approval request."""

    rejection_reason: str = Field(..., min_length=1, max_length=2000, description="Mandatory reason for rejection")


class ApprovalCancelRequest(BaseModel):
    """Payload to cancel an open approval request."""

    reason: Optional[str] = Field(None, max_length=2000, description="Optional reason for cancellation")


class ApprovalRevalidationResult(BaseModel):
    """Outcome of real-time security state revalidation prior to finalizing approval."""

    valid: bool = Field(..., description="Whether approval may proceed under current security state")
    current_decision: str = Field(..., description="Real-time decision outcome (ALLOW, BLOCK, REQUIRE_APPROVAL)")
    current_risk_level: Optional[str] = Field(None, description="Real-time assessed risk level")
    current_risk_score: Optional[float] = Field(None, description="Real-time assessed risk score")
    reason: str = Field(..., description="Human-readable explanation of revalidation result")
    stale: bool = Field(..., description="Whether previous decision snapshot is now stale")
    evaluation_trace: Dict[str, Any] = Field(default_factory=dict, description="Revalidation evaluation trace")


class ApprovalResponse(BaseModel):
    """Authoritative representation of an approval request."""

    id: uuid.UUID
    organization_id: uuid.UUID
    runtime_action_id: uuid.UUID
    decision_id: uuid.UUID
    requested_by_agent_id: uuid.UUID
    reviewer_user_id: Optional[uuid.UUID] = None
    status: str
    reason: str
    rejection_reason: Optional[str] = None
    expires_at: Optional[datetime] = None
    decision_snapshot: Dict[str, Any]
    approval_context: Dict[str, Any]
    created_at: datetime
    updated_at: datetime
    reviewed_at: Optional[datetime] = None

    model_config = ConfigDict(from_attributes=True)


class ApprovalListResponse(BaseModel):
    """Paginated collection of approval requests."""

    items: List[ApprovalResponse]
    total: int
