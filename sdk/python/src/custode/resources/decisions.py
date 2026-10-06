"""Decisions resources for CUSTODE SDK."""

from __future__ import annotations

from typing import Any, Dict, Optional
from custode.models.decision import Decision, DecisionList
from custode.resources.base import AsyncBaseResource, BaseResource


class DecisionsResource(BaseResource):
    """Synchronous interface for querying and evaluating authorization decisions."""

    def get(self, decision_id: str, organization_id: Optional[str] = None) -> Decision:
        """Retrieve an immutable decision record by ID."""
        org_id = self._resolve_org_id(organization_id)
        data = self._transport.request(
            "GET", f"/api/v1/organizations/{org_id}/decisions/{decision_id}"
        )
        return Decision.model_validate(data)

    def list(
        self,
        organization_id: Optional[str] = None,
        limit: int = 50,
        offset: int = 0,
    ) -> DecisionList:
        """List historical decisions scoped to the tenant."""
        org_id = self._resolve_org_id(organization_id)
        data = self._transport.request(
            "GET",
            f"/api/v1/organizations/{org_id}/decisions",
            params={"limit": limit, "offset": offset},
        )
        items = [Decision.model_validate(it) for it in data.get("items", [])]
        return DecisionList(
            items=items,
            total=data.get("total", len(items)),
        )

    def get_for_action(
        self, action_id: str, organization_id: Optional[str] = None
    ) -> DecisionList:
        """Retrieve all decisions generated for a specific runtime action."""
        org_id = self._resolve_org_id(organization_id)
        data = self._transport.request(
            "GET",
            f"/api/v1/organizations/{org_id}/runtime-actions/{action_id}/decisions",
        )
        items = [Decision.model_validate(it) for it in data.get("items", [])]
        return DecisionList(
            items=items,
            total=data.get("total", len(items)),
        )


class AsyncDecisionsResource(AsyncBaseResource):
    """Asynchronous interface for querying and evaluating authorization decisions."""

    async def get(
        self, decision_id: str, organization_id: Optional[str] = None
    ) -> Decision:
        """Retrieve an immutable decision record by ID."""
        org_id = self._resolve_org_id(organization_id)
        data = await self._transport.request(
            "GET", f"/api/v1/organizations/{org_id}/decisions/{decision_id}"
        )
        return Decision.model_validate(data)

    async def list(
        self,
        organization_id: Optional[str] = None,
        limit: int = 50,
        offset: int = 0,
    ) -> DecisionList:
        """List historical decisions scoped to the tenant."""
        org_id = self._resolve_org_id(organization_id)
        data = await self._transport.request(
            "GET",
            f"/api/v1/organizations/{org_id}/decisions",
            params={"limit": limit, "offset": offset},
        )
        items = [Decision.model_validate(it) for it in data.get("items", [])]
        return DecisionList(
            items=items,
            total=data.get("total", len(items)),
        )

    async def get_for_action(
        self, action_id: str, organization_id: Optional[str] = None
    ) -> DecisionList:
        """Retrieve all decisions generated for a specific runtime action."""
        org_id = self._resolve_org_id(organization_id)
        data = await self._transport.request(
            "GET",
            f"/api/v1/organizations/{org_id}/runtime-actions/{action_id}/decisions",
        )
        items = [Decision.model_validate(it) for it in data.get("items", [])]
        return DecisionList(
            items=items,
            total=data.get("total", len(items)),
        )
