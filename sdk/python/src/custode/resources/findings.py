"""Security findings resources for CUSTODE SDK."""

from __future__ import annotations

from typing import Any, Dict, Optional
from custode.models.finding import SecurityFinding, SecurityFindingList
from custode.resources.base import AsyncBaseResource, BaseResource


class FindingsResource(BaseResource):
    """Synchronous interface for querying Sentinel security findings."""

    def get(
        self, finding_id: str, organization_id: Optional[str] = None
    ) -> SecurityFinding:
        """Retrieve security finding details by ID."""
        org_id = self._resolve_org_id(organization_id)
        data = self._transport.request(
            "GET", f"/api/v1/organizations/{org_id}/findings/{finding_id}"
        )
        return SecurityFinding.model_validate(data)

    def list(
        self,
        organization_id: Optional[str] = None,
        severity: Optional[str] = None,
        limit: int = 50,
        offset: int = 0,
    ) -> SecurityFindingList:
        """List detected security findings."""
        org_id = self._resolve_org_id(organization_id)
        params: Dict[str, Any] = {"limit": limit, "offset": offset}
        if severity:
            params["severity"] = severity

        data = self._transport.request(
            "GET",
            f"/api/v1/organizations/{org_id}/findings",
            params=params,
        )
        items = [SecurityFinding.model_validate(it) for it in data.get("items", [])]
        return SecurityFindingList(
            items=items,
            total=data.get("total", len(items)),
        )


class AsyncFindingsResource(AsyncBaseResource):
    """Asynchronous interface for querying Sentinel security findings."""

    async def get(
        self, finding_id: str, organization_id: Optional[str] = None
    ) -> SecurityFinding:
        """Retrieve security finding details by ID."""
        org_id = self._resolve_org_id(organization_id)
        data = await self._transport.request(
            "GET", f"/api/v1/organizations/{org_id}/findings/{finding_id}"
        )
        return SecurityFinding.model_validate(data)

    async def list(
        self,
        organization_id: Optional[str] = None,
        severity: Optional[str] = None,
        limit: int = 50,
        offset: int = 0,
    ) -> SecurityFindingList:
        """List detected security findings."""
        org_id = self._resolve_org_id(organization_id)
        params: Dict[str, Any] = {"limit": limit, "offset": offset}
        if severity:
            params["severity"] = severity

        data = await self._transport.request(
            "GET",
            f"/api/v1/organizations/{org_id}/findings",
            params=params,
        )
        items = [SecurityFinding.model_validate(it) for it in data.get("items", [])]
        return SecurityFindingList(
            items=items,
            total=data.get("total", len(items)),
        )
