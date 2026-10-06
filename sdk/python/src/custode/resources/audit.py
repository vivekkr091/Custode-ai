"""Audit Trail resources for CUSTODE SDK."""

from __future__ import annotations

from typing import Any, Dict, Optional
from custode.models.audit import AuditEvent, AuditEventList
from custode.resources.base import AsyncBaseResource, BaseResource


class AuditResource(BaseResource):
    """Synchronous interface for inspecting immutable security audit trails."""

    def get(
        self, event_id: str, organization_id: Optional[str] = None
    ) -> AuditEvent:
        """Retrieve audit event details by ID."""
        org_id = self._resolve_org_id(organization_id)
        data = self._transport.request(
            "GET", f"/api/v1/organizations/{org_id}/audit/{event_id}"
        )
        return AuditEvent.model_validate(data)

    def list(
        self,
        organization_id: Optional[str] = None,
        limit: int = 50,
        offset: int = 0,
    ) -> AuditEventList:
        """List historical audit events."""
        org_id = self._resolve_org_id(organization_id)
        data = self._transport.request(
            "GET",
            f"/api/v1/organizations/{org_id}/audit",
            params={"limit": limit, "offset": offset},
        )
        items = [AuditEvent.model_validate(it) for it in data.get("items", [])]
        return AuditEventList(
            items=items,
            total=data.get("total", len(items)),
        )


class AsyncAuditResource(AsyncBaseResource):
    """Asynchronous interface for inspecting immutable security audit trails."""

    async def get(
        self, event_id: str, organization_id: Optional[str] = None
    ) -> AuditEvent:
        """Retrieve audit event details by ID."""
        org_id = self._resolve_org_id(organization_id)
        data = await self._transport.request(
            "GET", f"/api/v1/organizations/{org_id}/audit/{event_id}"
        )
        return AuditEvent.model_validate(data)

    async def list(
        self,
        organization_id: Optional[str] = None,
        limit: int = 50,
        offset: int = 0,
    ) -> AuditEventList:
        """List historical audit events."""
        org_id = self._resolve_org_id(organization_id)
        data = await self._transport.request(
            "GET",
            f"/api/v1/organizations/{org_id}/audit",
            params={"limit": limit, "offset": offset},
        )
        items = [AuditEvent.model_validate(it) for it in data.get("items", [])]
        return AuditEventList(
            items=items,
            total=data.get("total", len(items)),
        )
