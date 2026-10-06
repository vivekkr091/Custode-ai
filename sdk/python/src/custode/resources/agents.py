"""Agents and authentication identity resources for CUSTODE SDK."""

from __future__ import annotations

from typing import Any, Dict, List, Optional
from custode.models.agent import Agent, AuthenticatedAgent
from custode.models.pagination import PaginatedList
from custode.resources.base import AsyncBaseResource, BaseResource


class AgentsResource(BaseResource):
    """Synchronous interface for agent identity validation and metadata."""

    def me(self) -> AuthenticatedAgent:
        """Verify the caller's agent API key and retrieve authoritative identity."""
        data = self._transport.request("GET", "/api/v1/auth/me")
        return AuthenticatedAgent.model_validate(data)

    def get(self, agent_id: str, organization_id: Optional[str] = None) -> Agent:
        """Retrieve agent security identity details."""
        org_id = self._resolve_org_id(organization_id)
        data = self._transport.request(
            "GET", f"/api/v1/organizations/{org_id}/agents/{agent_id}"
        )
        return Agent.model_validate(data)

    def list(
        self,
        organization_id: Optional[str] = None,
        limit: int = 50,
        offset: int = 0,
    ) -> PaginatedList[Agent]:
        """List registered agents for the tenant."""
        org_id = self._resolve_org_id(organization_id)
        data = self._transport.request(
            "GET",
            f"/api/v1/organizations/{org_id}/agents",
            params={"limit": limit, "offset": offset},
        )
        items = [Agent.model_validate(item) for item in data.get("items", [])]
        return PaginatedList[Agent](
            items=items,
            total=data.get("total", len(items)),
            limit=limit,
            offset=offset,
        )


class AsyncAgentsResource(AsyncBaseResource):
    """Asynchronous interface for agent identity validation and metadata."""

    async def me(self) -> AuthenticatedAgent:
        """Verify the caller's agent API key and retrieve authoritative identity."""
        data = await self._transport.request("GET", "/api/v1/auth/me")
        return AuthenticatedAgent.model_validate(data)

    async def get(self, agent_id: str, organization_id: Optional[str] = None) -> Agent:
        """Retrieve agent security identity details."""
        org_id = self._resolve_org_id(organization_id)
        data = await self._transport.request(
            "GET", f"/api/v1/organizations/{org_id}/agents/{agent_id}"
        )
        return Agent.model_validate(data)

    async def list(
        self,
        organization_id: Optional[str] = None,
        limit: int = 50,
        offset: int = 0,
    ) -> PaginatedList[Agent]:
        """List registered agents for the tenant."""
        org_id = self._resolve_org_id(organization_id)
        data = await self._transport.request(
            "GET",
            f"/api/v1/organizations/{org_id}/agents",
            params={"limit": limit, "offset": offset},
        )
        items = [Agent.model_validate(item) for item in data.get("items", [])]
        return PaginatedList[Agent](
            items=items,
            total=data.get("total", len(items)),
            limit=limit,
            offset=offset,
        )
