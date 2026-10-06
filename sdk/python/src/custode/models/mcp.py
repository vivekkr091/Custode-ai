"""MCP Security Layer models for CUSTODE SDK."""

from typing import Any, Dict, List, Optional
from pydantic import Field

from custode.models.base import CUSTODEModel


class MCPServer(CUSTODEModel):
    """Authoritative API representation of an MCP server."""

    id: str
    organization_id: str
    name: str
    slug: str
    description: Optional[str] = None
    server_type: str
    endpoint: str
    transport: str
    status: str
    trust_level: str
    environment: str
    metadata: Optional[Dict[str, Any]] = None
    created_at: Any
    updated_at: Any
    tool_count: int = 0


class MCPServerList(CUSTODEModel):
    """Paginated collection of registered MCP servers."""

    items: List[MCPServer] = Field(default_factory=list)
    total: int = 0

    def __iter__(self):
        return iter(self.items)

    def __len__(self) -> int:
        return len(self.items)

    def __getitem__(self, index: int) -> MCPServer:
        return self.items[index]


class MCPTool(CUSTODEModel):
    """Authoritative representation of a registered MCP tool."""

    id: str
    organization_id: str
    mcp_server_id: str
    tool_id: Optional[str] = None
    operation_id: Optional[str] = None
    name: str
    slug: str
    description: Optional[str] = None
    input_schema: Dict[str, Any]
    output_schema: Optional[Dict[str, Any]] = None
    status: str
    risk_level: str
    schema_hash: str
    previous_schema_hash: Optional[str] = None
    schema_changed: bool = False
    discovered_at: Any
    activated_at: Optional[Any] = None
    created_at: Any
    updated_at: Any


class MCPToolList(CUSTODEModel):
    """Paginated collection of registered MCP tools."""

    items: List[MCPTool] = Field(default_factory=list)
    total: int = 0

    def __iter__(self):
        return iter(self.items)

    def __len__(self) -> int:
        return len(self.items)

    def __getitem__(self, index: int) -> MCPTool:
        return self.items[index]


class MCPToolCallResponse(CUSTODEModel):
    """Result of an MCP tool invocation mediated by the CUSTODE control plane."""

    tool_id: str
    runtime_action_id: str
    decision: str
    status: str
    result: Optional[Any] = None
    approval_id: Optional[str] = None
    latency_ms: float = 0.0
    input_findings: List[Dict[str, Any]] = Field(default_factory=list)
    output_findings: List[Dict[str, Any]] = Field(default_factory=list)
    error: Optional[str] = None

    @property
    def is_allowed(self) -> bool:
        return self.decision.lower() == "allow"

    @property
    def is_blocked(self) -> bool:
        return self.decision.lower() == "block"

    @property
    def requires_approval(self) -> bool:
        return self.decision.lower() == "require_approval"
