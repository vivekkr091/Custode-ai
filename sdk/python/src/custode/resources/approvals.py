"""Approvals resources for CUSTODE SDK."""

from __future__ import annotations

from typing import Any, Dict, Optional
from custode.models.approval import ApprovalList, ApprovalRequest
from custode.resources.base import AsyncBaseResource, BaseResource


class ApprovalsResource(BaseResource):
    """Synchronous interface for inspecting human governance approval requests."""

    def get(
        self, approval_id: str, organization_id: Optional[str] = None
    ) -> ApprovalRequest:
        """Retrieve approval request details by ID."""
        org_id = self._resolve_org_id(organization_id)
        data = self._transport.request(
            "GET", f"/api/v1/organizations/{org_id}/approvals/{approval_id}"
        )
        return ApprovalRequest.model_validate(data)

    def list(
        self,
        organization_id: Optional[str] = None,
        status: Optional[str] = None,
        limit: int = 50,
        offset: int = 0,
    ) -> ApprovalList:
        """List human governance approvals with optional status filtering."""
        org_id = self._resolve_org_id(organization_id)
        params: Dict[str, Any] = {"limit": limit, "offset": offset}
        if status:
            params["status"] = status

        data = self._transport.request(
            "GET",
            f"/api/v1/organizations/{org_id}/approvals",
            params=params,
        )
        items = [ApprovalRequest.model_validate(it) for it in data.get("items", [])]
        return ApprovalList(
            items=items,
            total=data.get("total", len(items)),
        )

    def cancel(
        self,
        approval_id: str,
        reason: Optional[str] = None,
        organization_id: Optional[str] = None,
    ) -> ApprovalRequest:
        """Cancel a pending approval request."""
        org_id = self._resolve_org_id(organization_id)
        payload = {"reason": reason} if reason else {}
        data = self._transport.request(
            "POST",
            f"/api/v1/organizations/{org_id}/approvals/{approval_id}/cancel",
            json=payload,
        )
        return ApprovalRequest.model_validate(data)


class AsyncApprovalsResource(AsyncBaseResource):
    """Asynchronous interface for inspecting human governance approval requests."""

    async def get(
        self, approval_id: str, organization_id: Optional[str] = None
    ) -> ApprovalRequest:
        """Retrieve approval request details by ID."""
        org_id = self._resolve_org_id(organization_id)
        data = await self._transport.request(
            "GET", f"/api/v1/organizations/{org_id}/approvals/{approval_id}"
        )
        return ApprovalRequest.model_validate(data)

    async def list(
        self,
        organization_id: Optional[str] = None,
        status: Optional[str] = None,
        limit: int = 50,
        offset: int = 0,
    ) -> ApprovalList:
        """List human governance approvals with optional status filtering."""
        org_id = self._resolve_org_id(organization_id)
        params: Dict[str, Any] = {"limit": limit, "offset": offset}
        if status:
            params["status"] = status

        data = await self._transport.request(
            "GET",
            f"/api/v1/organizations/{org_id}/approvals",
            params=params,
        )
        items = [ApprovalRequest.model_validate(it) for it in data.get("items", [])]
        return ApprovalList(
            items=items,
            total=data.get("total", len(items)),
        )

    async def cancel(
        self,
        approval_id: str,
        reason: Optional[str] = None,
        organization_id: Optional[str] = None,
    ) -> ApprovalRequest:
        """Cancel a pending approval request."""
        org_id = self._resolve_org_id(organization_id)
        payload = {"reason": reason} if reason else {}
        data = await self._transport.request(
            "POST",
            f"/api/v1/organizations/{org_id}/approvals/{approval_id}/cancel",
            json=payload,
        )
        return ApprovalRequest.model_validate(data)
