"""Runtime action resources for CUSTODE SDK."""

from __future__ import annotations

from typing import Any, Dict, Optional, Union
from custode.models.decision import Decision
from custode.models.execution import Execution
from custode.models.runtime_action import (
    RuntimeAction,
    RuntimeActionCreate,
    RuntimeActionList,
)
from custode.resources.base import AsyncBaseResource, BaseResource


class RuntimeActionsResource(BaseResource):
    """Synchronous interface for RuntimeAction creation, lookup, decisioning, and execution."""

    def create(
        self,
        tool_id: str,
        operation_id: str,
        *,
        environment: str = "development",
        action_type: str = "tool_call",
        resource: Optional[str] = None,
        resource_type: Optional[str] = None,
        parameters: Optional[Dict[str, Any]] = None,
        amount: Optional[float] = None,
        currency: Optional[str] = None,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None,
        organization_id: Optional[str] = None,
        request_id: Optional[str] = None,
    ) -> RuntimeAction:
        """Register and canonicalize an intended agent runtime action."""
        org_id = self._resolve_org_id(organization_id)
        payload = {
            "tool_id": tool_id,
            "operation_id": operation_id,
            "environment": environment,
            "action_type": action_type,
            "resource": resource,
            "resource_type": resource_type,
            "parameters": parameters or {},
            "amount": amount,
            "currency": currency,
            "ip_address": ip_address,
            "user_agent": user_agent,
        }
        # Filter None values
        body = {k: v for k, v in payload.items() if v is not None}
        data = self._transport.request(
            "POST",
            f"/api/v1/organizations/{org_id}/runtime-actions",
            json=body,
            request_id=request_id,
        )
        return RuntimeAction.model_validate(data)

    def get(
        self, action_id: str, organization_id: Optional[str] = None
    ) -> RuntimeAction:
        """Retrieve a registered runtime action by its UUID."""
        org_id = self._resolve_org_id(organization_id)
        data = self._transport.request(
            "GET", f"/api/v1/organizations/{org_id}/runtime-actions/{action_id}"
        )
        return RuntimeAction.model_validate(data)

    def list(
        self,
        organization_id: Optional[str] = None,
        agent_id: Optional[str] = None,
        limit: int = 50,
        offset: int = 0,
    ) -> RuntimeActionList:
        """List runtime actions scoped to the organization."""
        org_id = self._resolve_org_id(organization_id)
        params: Dict[str, Any] = {"limit": limit, "offset": offset}
        if agent_id:
            params["agent_id"] = agent_id

        data = self._transport.request(
            "GET",
            f"/api/v1/organizations/{org_id}/runtime-actions",
            params=params,
        )
        items = [RuntimeAction.model_validate(it) for it in data.get("items", [])]
        return RuntimeActionList(
            items=items,
            total=data.get("total", len(items)),
        )

    def decide(
        self,
        action_id: str,
        organization_id: Optional[str] = None,
        request_id: Optional[str] = None,
    ) -> Decision:
        """Trigger backend decision arbitration (ALLOW, BLOCK, REQUIRE_APPROVAL) for the action."""
        org_id = self._resolve_org_id(organization_id)
        data = self._transport.request(
            "POST",
            f"/api/v1/organizations/{org_id}/runtime-actions/{action_id}/decide",
            request_id=request_id,
        )
        return Decision.model_validate(data)

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


class AsyncRuntimeActionsResource(AsyncBaseResource):
    """Asynchronous interface for RuntimeAction creation, lookup, decisioning, and execution."""

    async def create(
        self,
        tool_id: str,
        operation_id: str,
        *,
        environment: str = "development",
        action_type: str = "tool_call",
        resource: Optional[str] = None,
        resource_type: Optional[str] = None,
        parameters: Optional[Dict[str, Any]] = None,
        amount: Optional[float] = None,
        currency: Optional[str] = None,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None,
        organization_id: Optional[str] = None,
        request_id: Optional[str] = None,
    ) -> RuntimeAction:
        """Register and canonicalize an intended agent runtime action."""
        org_id = self._resolve_org_id(organization_id)
        payload = {
            "tool_id": tool_id,
            "operation_id": operation_id,
            "environment": environment,
            "action_type": action_type,
            "resource": resource,
            "resource_type": resource_type,
            "parameters": parameters or {},
            "amount": amount,
            "currency": currency,
            "ip_address": ip_address,
            "user_agent": user_agent,
        }
        body = {k: v for k, v in payload.items() if v is not None}
        data = await self._transport.request(
            "POST",
            f"/api/v1/organizations/{org_id}/runtime-actions",
            json=body,
            request_id=request_id,
        )
        return RuntimeAction.model_validate(data)

    async def get(
        self, action_id: str, organization_id: Optional[str] = None
    ) -> RuntimeAction:
        """Retrieve a registered runtime action by its UUID."""
        org_id = self._resolve_org_id(organization_id)
        data = await self._transport.request(
            "GET", f"/api/v1/organizations/{org_id}/runtime-actions/{action_id}"
        )
        return RuntimeAction.model_validate(data)

    async def list(
        self,
        organization_id: Optional[str] = None,
        agent_id: Optional[str] = None,
        limit: int = 50,
        offset: int = 0,
    ) -> RuntimeActionList:
        """List runtime actions scoped to the organization."""
        org_id = self._resolve_org_id(organization_id)
        params: Dict[str, Any] = {"limit": limit, "offset": offset}
        if agent_id:
            params["agent_id"] = agent_id

        data = await self._transport.request(
            "GET",
            f"/api/v1/organizations/{org_id}/runtime-actions",
            params=params,
        )
        items = [RuntimeAction.model_validate(it) for it in data.get("items", [])]
        return RuntimeActionList(
            items=items,
            total=data.get("total", len(items)),
        )

    async def decide(
        self,
        action_id: str,
        organization_id: Optional[str] = None,
        request_id: Optional[str] = None,
    ) -> Decision:
        """Trigger backend decision arbitration (ALLOW, BLOCK, REQUIRE_APPROVAL) for the action."""
        org_id = self._resolve_org_id(organization_id)
        data = await self._transport.request(
            "POST",
            f"/api/v1/organizations/{org_id}/runtime-actions/{action_id}/decide",
            request_id=request_id,
        )
        return Decision.model_validate(data)

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
