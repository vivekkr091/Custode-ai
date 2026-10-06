"""Runtime action models for CUSTODE SDK."""

from datetime import datetime
from typing import Any, Dict, List, Optional
from pydantic import Field

from custode.models.base import CUSTODEModel


class RuntimeActionCreate(CUSTODEModel):
    """Payload to register an intended agent action with CUSTODE."""

    tool_id: str = Field(..., description="Target tool capability UUID")
    operation_id: str = Field(..., description="Target tool operation UUID")
    environment: str = Field(default="development", description="Runtime environment: development, staging, production")
    action_type: str = Field(default="tool_call", description="Action type discriminator")
    resource: Optional[str] = Field(default=None, description="Resource identifier or URI targeted")
    resource_type: Optional[str] = Field(default=None, description="Resource type classification")
    parameters: Dict[str, Any] = Field(default_factory=dict, description="Action payload parameters")
    amount: Optional[float] = Field(default=None, description="Operational amount for financial evaluation")
    currency: Optional[str] = Field(default=None, description="ISO currency code")
    ip_address: Optional[str] = Field(default=None, description="Client network IP")
    user_agent: Optional[str] = Field(default=None, description="Client application user agent")
    request_id: Optional[str] = Field(default=None, description="Client request correlation ID")


class RuntimeAction(CUSTODEModel):
    """Immutable authoritative record of an agent runtime action."""

    id: str
    organization_id: str
    agent_id: str
    tool_id: str
    operation_id: str
    request_id: Optional[str] = None
    environment: str
    action_type: str
    resource: Optional[str] = None
    resource_type: Optional[str] = None
    parameters: Dict[str, Any] = Field(default_factory=dict)
    amount: Optional[float] = None
    currency: Optional[str] = None
    ip_address: Optional[str] = None
    user_agent: Optional[str] = None
    status: str
    created_at: Any
    updated_at: Any
    evaluated_at: Optional[Any] = None
    completed_at: Optional[Any] = None


class RuntimeActionList(CUSTODEModel):
    """Paginated collection of runtime actions."""

    items: List[RuntimeAction] = Field(default_factory=list)
    total: int = 0

    def __iter__(self):
        return iter(self.items)

    def __len__(self) -> int:
        return len(self.items)

    def __getitem__(self, index: int) -> RuntimeAction:
        return self.items[index]
