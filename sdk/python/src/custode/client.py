"""Synchronous CUSTODE Client implementation."""

from __future__ import annotations

from typing import Any, Dict, Optional
import httpx

from custode.config import CUSTODEConfig
from custode.models.agent import AuthenticatedAgent
from custode.resources.agents import AgentsResource
from custode.resources.approvals import ApprovalsResource
from custode.resources.audit import AuditResource
from custode.resources.decisions import DecisionsResource
from custode.resources.executions import ExecutionsResource
from custode.resources.findings import FindingsResource
from custode.resources.integrations import IntegrationsResource
from custode.resources.llm import LLMResource
from custode.resources.mcp import MCPResource
from custode.resources.runtime_actions import RuntimeActionsResource
from custode.security.masking import mask_secret
from custode.transport.transport import SyncTransport


class CUSTODEClient:
    """Synchronous developer client for interacting with the CUSTODE Control Plane.

    Provides typed access to CUSTODE security engines:
    - `agents`: Identity validation and caller verification
    - `runtime_actions`: Register intended actions and request evaluation
    - `decisions`: Query immutable authorization decision records
    - `approvals`: Human governance workflows
    - `executions`: Dispatch authorized actions to controlled execution
    - `llm`: Mediated LLM interactions via Security Gateway
    - `mcp`: MCP tool and server boundary enforcement
    - `findings`: Sentinel vulnerability findings
    - `audit`: Immutable audit trail records

    Usage example:
    ```python
    from custode import CUSTODEClient

    with CUSTODEClient(
        base_url="http://localhost:8000",
        api_key="cst_ag_...",
        organization_id="...",
    ) as client:
        action = client.runtime_actions.create(
            tool_id="...",
            operation_id="...",
            parameters={"query": "test"},
        )
        decision = client.runtime_actions.decide(action.id)
        if decision.is_allowed:
            result = client.runtime_actions.execute(action.id)
    ```
    """

    def __init__(
        self,
        base_url: Optional[str] = None,
        api_key: Optional[str] = None,
        organization_id: Optional[str] = None,
        timeout: Optional[float] = None,
        max_retries: int = 2,
        default_headers: Optional[Dict[str, str]] = None,
        http_client: Optional[httpx.Client] = None,
    ) -> None:
        self.config = CUSTODEConfig(
            base_url=base_url,
            api_key=api_key,
            organization_id=organization_id,
            timeout=timeout,
            max_retries=max_retries,
            default_headers=default_headers,
        )
        self._transport = SyncTransport(self.config, client=http_client)

        # Initialize resources
        self.agents = AgentsResource(self._transport, self.config)
        self.runtime_actions = RuntimeActionsResource(self._transport, self.config)
        self.decisions = DecisionsResource(self._transport, self.config)
        self.approvals = ApprovalsResource(self._transport, self.config)
        self.executions = ExecutionsResource(self._transport, self.config)
        self.llm = LLMResource(self._transport, self.config)
        self.mcp = MCPResource(self._transport, self.config)
        self.findings = FindingsResource(self._transport, self.config)
        self.audit = AuditResource(self._transport, self.config)
        self.integrations = IntegrationsResource(self._transport, self.config)

    def verify_identity(self) -> AuthenticatedAgent:
        """Call /api/v1/auth/me to verify credentials and cache the organization_id if omitted."""
        identity = self.agents.me()
        if not self.config.organization_id:
            self.config.organization_id = identity.organization_id
        return identity

    def close(self) -> None:
        """Close underlying HTTP transport connections."""
        self._transport.close()

    def __enter__(self) -> CUSTODEClient:
        return self

    def __exit__(self, *args: Any) -> None:
        self.close()

    def __repr__(self) -> str:
        return (
            f"CUSTODEClient("
            f"base_url={self.config.base_url!r}, "
            f"api_key={mask_secret(self.config.api_key)!r}, "
            f"organization_id={self.config.organization_id!r})"
        )

    def __str__(self) -> str:
        return self.__repr__()
