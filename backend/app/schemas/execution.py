"""Pydantic schemas for Controlled Execution layer."""

from datetime import datetime
import enum
from typing import Any, Dict, List, Optional
import uuid
from pydantic import BaseModel, ConfigDict, Field


class ExecutionStatus(str, enum.Enum):
    """Lifecycle status of a controlled tool execution."""
    pending = "pending"
    running = "running"
    succeeded = "succeeded"
    failed = "failed"
    blocked = "blocked"
    skipped = "skipped"


class ExecutionResponse(BaseModel):
    """Authoritative representation of a tool execution record."""

    id: uuid.UUID
    organization_id: uuid.UUID
    runtime_action_id: uuid.UUID
    agent_id: uuid.UUID
    tool_id: uuid.UUID
    operation_id: uuid.UUID
    decision_id: Optional[uuid.UUID] = None
    approval_id: Optional[uuid.UUID] = None
    status: str
    result: Optional[Dict[str, Any]] = None
    error_code: Optional[str] = None
    error_message: Optional[str] = None
    started_at: datetime
    completed_at: Optional[datetime] = None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class ExecutionListResponse(BaseModel):
    """Paginated collection of execution records."""

    items: List[ExecutionResponse]
    total: int
