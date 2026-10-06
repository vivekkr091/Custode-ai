"""Asynchronous CUSTODE Client implementation."""

from __future__ import annotations

from typing import Any, Dict, Optional
import httpx

from custode.config import CUSTODEConfig
from custode.models.agent import AuthenticatedAgent
from custode.resources.agents import AsyncAgentsResource
from custode.resources.approvals import AsyncApprovalsResource
from custode.resources.audit import AsyncAuditResource
from custode.resources.decisions import AsyncDecisionsResource
from custode.resources.executions import AsyncExecutionsResource
from custode.resources.findings import AsyncFindingsResource
from custode.resources.integrations import AsyncIntegrationsResource
from custode.resources.llm import AsyncLLMResource
from custode.resources.mcp import AsyncMCPResource
from custode.resources.runtime_actions import AsyncRuntimeActionsResource
from custode.security.masking import mask_secret
from custode.transport.transport import AsyncTransport


class AsyncCUSTODEClient:
    """Asynchronous developer client for interacting with the CUSTODE Control Plane.

    Provides non-blocking access to CUSTODE security engines:
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
    from custode import AsyncCUSTODEClient

    async with AsyncCUSTODEClient(
        base_url="http://localhost:8000",
        api_key="cst_ag_...",
        organization_id="...",
    ) as client:
        action = await client.runtime_actions.create(
            tool_id="...",
            operation_id="...",
            parameters={"query": "test"},
        )
        decision = await client.runtime_actions.decide(action.id)
        if decision.is_allowed:
            result = await client.runtime_actions.execute(action.id)
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
        http_client: Optional[httpx.AsyncClient] = None,
    ) -> None:
        self.config = CUSTODEConfig(
            base_url=base_url,
            api_key=api_key,
            organization_id=organization_id,
            timeout=timeout,
            max_retries=max_retries,
            default_headers=default_headers,
        )
        self._transport = AsyncTransport(self.config, client=http_client)

        # Initialize resources
        self.agents = AsyncAgentsResource(self._transport, self.config)
        self.runtime_actions = AsyncRuntimeActionsResource(self._transport, self.config)
        self.decisions = AsyncDecisionsResource(self._transport, self.config)
        self.approvals = AsyncApprovalsResource(self._transport, self.config)
        self.executions = AsyncExecutionsResource(self._transport, self.config)
        self.llm = AsyncLLMResource(self._transport, self.config)
        self.mcp = AsyncMCPResource(self._transport, self.config)
        self.findings = AsyncFindingsResource(self._transport, self.config)
        self.audit = AsyncAuditResource(self._transport, self.config)
        self.integrations = AsyncIntegrationsResource(self._transport, self.config)

    async def verify_identity(self) -> AuthenticatedAgent:
        """Call /api/v1/auth/me to verify credentials and cache the organization_id if omitted."""
        identity = await self.agents.me()
        if not self.config.organization_id:
            self.config.organization_id = identity.organization_id
        return identity

    async def aclose(self) -> None:
        """Close underlying asynchronous HTTP transport connections."""
        await self._transport.aclose()

    async def __aenter__(self) -> AsyncCUSTODEClient:
        return self

    async def __aexit__(self, *args: Any) -> None:
        await self.aclose()

    def __repr__(self) -> str:
        return (
            f"AsyncCUSTODEClient("
            f"base_url={self.config.base_url!r}, "
            f"api_key={mask_secret(self.config.api_key)!r}, "
            f"organization_id={self.config.organization_id!r})"
        )

    def __str__(self) -> str:
        return self.__repr__()
