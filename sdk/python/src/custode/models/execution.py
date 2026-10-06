"""Controlled Execution models for CUSTODE SDK."""

from typing import Any, Dict, List, Optional
from pydantic import Field

from custode.models.base import CUSTODEModel


class Execution(CUSTODEModel):
    """Authoritative record of a controlled tool execution dispatched by CUSTODE."""

    id: str
    organization_id: str
    runtime_action_id: str
    agent_id: str
    tool_id: str
    operation_id: str
    decision_id: Optional[str] = None
    approval_id: Optional[str] = None
    status: str
    result: Optional[Dict[str, Any]] = None
    error_code: Optional[str] = None
    error_message: Optional[str] = None
    started_at: Any
    completed_at: Optional[Any] = None
    created_at: Any

    @property
    def is_succeeded(self) -> bool:
        """True if the controlled execution finished successfully."""
        return self.status.lower() in ("succeeded", "completed")

    @property
    def is_failed(self) -> bool:
        """True if execution failed."""
        return self.status.lower() == "failed"


class ExecutionList(CUSTODEModel):
    """Paginated collection of execution records."""

    items: List[Execution] = Field(default_factory=list)
    total: int = 0

    def __iter__(self):
        return iter(self.items)

    def __len__(self) -> int:
        return len(self.items)

    def __getitem__(self, index: int) -> Execution:
        return self.items[index]
