"""Executions resources for CUSTODE SDK."""

from __future__ import annotations

from typing import Any, Dict, Optional
from custode.models.execution import Execution, ExecutionList
from custode.resources.base import AsyncBaseResource, BaseResource


class ExecutionsResource(BaseResource):
    """Synchronous interface for inspecting and triggering controlled tool executions."""

    def get(
        self, execution_id: str, organization_id: Optional[str] = None
    ) -> Execution:
        """Retrieve execution record details by ID."""
        org_id = self._resolve_org_id(organization_id)
        data = self._transport.request(
            "GET", f"/api/v1/organizations/{org_id}/executions/{execution_id}"
        )
        return Execution.model_validate(data)

    def list(
        self,
        organization_id: Optional[str] = None,
        limit: int = 50,
        offset: int = 0,
    ) -> ExecutionList:
        """List historical tool execution records."""
        org_id = self._resolve_org_id(organization_id)
        data = self._transport.request(
            "GET",
            f"/api/v1/organizations/{org_id}/executions",
            params={"limit": limit, "offset": offset},
        )
        items = [Execution.model_validate(it) for it in data.get("items", [])]
        return ExecutionList(
            items=items,
            total=data.get("total", len(items)),
        )

    def execute(
        self,
        action_id: str,
        organization_id: Optional[str] = None,
        request_id: Optional[str] = None,
    ) -> Execution:
        """Dispatch authorized action to controlled execution guardrails."""
        org_id = self._resolve_org_id(organization_id)
        data = self._transport.request(
            "POST",
            f"/api/v1/organizations/{org_id}/runtime-actions/{action_id}/execute",
            request_id=request_id,
        )
        return Execution.model_validate(data)


class AsyncExecutionsResource(AsyncBaseResource):
    """Asynchronous interface for inspecting and triggering controlled tool executions."""

    async def get(
        self, execution_id: str, organization_id: Optional[str] = None
    ) -> Execution:
        """Retrieve execution record details by ID."""
        org_id = self._resolve_org_id(organization_id)
        data = await self._transport.request(
            "GET", f"/api/v1/organizations/{org_id}/executions/{execution_id}"
        )
        return Execution.model_validate(data)

    async def list(
        self,
        organization_id: Optional[str] = None,
        limit: int = 50,
        offset: int = 0,
    ) -> ExecutionList:
        """List historical tool execution records."""
        org_id = self._resolve_org_id(organization_id)
        data = await self._transport.request(
            "GET",
            f"/api/v1/organizations/{org_id}/executions",
            params={"limit": limit, "offset": offset},
        )
        items = [Execution.model_validate(it) for it in data.get("items", [])]
        return ExecutionList(
            items=items,
            total=data.get("total", len(items)),
        )

    async def execute(
        self,
        action_id: str,
        organization_id: Optional[str] = None,
        request_id: Optional[str] = None,
    ) -> Execution:
        """Dispatch authorized action to controlled execution guardrails."""
        org_id = self._resolve_org_id(organization_id)
        data = await self._transport.request(
            "POST",
            f"/api/v1/organizations/{org_id}/runtime-actions/{action_id}/execute",
            request_id=request_id,
        )
        return Execution.model_validate(data)
