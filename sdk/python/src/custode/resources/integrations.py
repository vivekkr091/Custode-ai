"""Integrations & Webhook Deliveries SDK resource implementation."""

from __future__ import annotations

from typing import Any, Dict, List, Optional, Union
import uuid

from custode.models.integration import (
    Integration,
    IntegrationCreateResponse,
    IntegrationList,
    SupportedEvents,
    WebhookDelivery,
    WebhookDeliveryList,
)
from custode.resources.base import AsyncBaseResource, BaseResource


class IntegrationsResource(BaseResource):
    """Synchronous resource for managing external webhooks and viewing deliveries."""

    def list(
        self,
        organization_id: Optional[Union[uuid.UUID, str]] = None,
        status: Optional[str] = None,
        limit: int = 50,
        offset: int = 0,
    ) -> IntegrationList:
        """List configured external webhook destinations."""
        org_id = self._resolve_org_id(organization_id)
        params: Dict[str, Any] = {"limit": limit, "offset": offset}
        if status:
            params["status"] = status

        response = self._transport.request(
            "GET",
            f"/api/v1/organizations/{org_id}/integrations",
            params=params,
        )
        return IntegrationList.model_validate(response)

    def get(
        self,
        integration_id: Union[uuid.UUID, str],
        organization_id: Optional[Union[uuid.UUID, str]] = None,
    ) -> Integration:
        """Retrieve details of a configured integration."""
        org_id = self._resolve_org_id(organization_id)
        response = self._transport.request(
            "GET",
            f"/api/v1/organizations/{org_id}/integrations/{integration_id}",
        )
        return Integration.model_validate(response)

    def create(
        self,
        name: str,
        url: str,
        subscribed_events: List[str],
        description: Optional[str] = None,
        provider: str = "webhook",
        headers: Optional[Dict[str, str]] = None,
        organization_id: Optional[Union[uuid.UUID, str]] = None,
    ) -> IntegrationCreateResponse:
        """Create a new webhook integration and receive the one-time signing secret."""
        org_id = self._resolve_org_id(organization_id)
        payload = {
            "name": name,
            "url": url,
            "subscribed_events": subscribed_events,
            "description": description,
            "provider": provider,
            "headers": headers,
        }
        response = self._transport.request(
            "POST",
            f"/api/v1/organizations/{org_id}/integrations",
            json=payload,
        )
        return IntegrationCreateResponse.model_validate(response)

    def suspend(
        self,
        integration_id: Union[uuid.UUID, str],
        organization_id: Optional[Union[uuid.UUID, str]] = None,
    ) -> Integration:
        """Temporarily suspend webhook dispatches for an integration."""
        org_id = self._resolve_org_id(organization_id)
        response = self._transport.request(
            "POST",
            f"/api/v1/organizations/{org_id}/integrations/{integration_id}/suspend",
        )
        return Integration.model_validate(response)

    def revoke(
        self,
        integration_id: Union[uuid.UUID, str],
        organization_id: Optional[Union[uuid.UUID, str]] = None,
    ) -> Integration:
        """Permanently revoke an integration. Cannot be reactivated."""
        org_id = self._resolve_org_id(organization_id)
        response = self._transport.request(
            "POST",
            f"/api/v1/organizations/{org_id}/integrations/{integration_id}/revoke",
        )
        return Integration.model_validate(response)

    def test_ping(
        self,
        integration_id: Union[uuid.UUID, str],
        organization_id: Optional[Union[uuid.UUID, str]] = None,
    ) -> WebhookDelivery:
        """Send a signed diagnostic ping event to verify destination connectivity."""
        org_id = self._resolve_org_id(organization_id)
        response = self._transport.request(
            "POST",
            f"/api/v1/organizations/{org_id}/integrations/{integration_id}/test",
        )
        return WebhookDelivery.model_validate(response)

    def list_deliveries(
        self,
        integration_id: Union[uuid.UUID, str],
        organization_id: Optional[Union[uuid.UUID, str]] = None,
        status: Optional[str] = None,
        event_type: Optional[str] = None,
        limit: int = 50,
        offset: int = 0,
    ) -> WebhookDeliveryList:
        """Retrieve delivery history for an integration."""
        org_id = self._resolve_org_id(organization_id)
        params: Dict[str, Any] = {"limit": limit, "offset": offset}
        if status:
            params["status"] = status
        if event_type:
            params["event_type"] = event_type

        response = self._transport.request(
            "GET",
            f"/api/v1/organizations/{org_id}/integrations/{integration_id}/deliveries",
            params=params,
        )
        return WebhookDeliveryList.model_validate(response)

    def get_delivery(
        self,
        integration_id: Union[uuid.UUID, str],
        delivery_id: Union[uuid.UUID, str],
        organization_id: Optional[Union[uuid.UUID, str]] = None,
    ) -> WebhookDelivery:
        """Retrieve full details of an individual delivery and its attempt history."""
        org_id = self._resolve_org_id(organization_id)
        response = self._transport.request(
            "GET",
            f"/api/v1/organizations/{org_id}/integrations/{integration_id}/deliveries/{delivery_id}",
        )
        return WebhookDelivery.model_validate(response)

    def retry_delivery(
        self,
        integration_id: Union[uuid.UUID, str],
        delivery_id: Union[uuid.UUID, str],
        organization_id: Optional[Union[uuid.UUID, str]] = None,
    ) -> WebhookDelivery:
        """Manually retry a failed delivery."""
        org_id = self._resolve_org_id(organization_id)
        response = self._transport.request(
            "POST",
            f"/api/v1/organizations/{org_id}/integrations/{integration_id}/deliveries/{delivery_id}/retry",
        )
        return WebhookDelivery.model_validate(response)

    def get_supported_events(
        self,
        organization_id: Optional[Union[uuid.UUID, str]] = None,
    ) -> SupportedEvents:
        """Retrieve the catalog of supported security events eligible for subscription."""
        org_id = self._resolve_org_id(organization_id)
        response = self._transport.request(
            "GET",
            f"/api/v1/organizations/{org_id}/integrations/supported-events",
        )
        return SupportedEvents.model_validate(response)


class AsyncIntegrationsResource(AsyncBaseResource):
    """Asynchronous resource for managing external webhooks and viewing deliveries."""

    async def list(
        self,
        organization_id: Optional[Union[uuid.UUID, str]] = None,
        status: Optional[str] = None,
        limit: int = 50,
        offset: int = 0,
    ) -> IntegrationList:
        org_id = self._resolve_org_id(organization_id)
        params: Dict[str, Any] = {"limit": limit, "offset": offset}
        if status:
            params["status"] = status

        response = await self._transport.request(
            "GET",
            f"/api/v1/organizations/{org_id}/integrations",
            params=params,
        )
        return IntegrationList.model_validate(response)

    async def get(
        self,
        integration_id: Union[uuid.UUID, str],
        organization_id: Optional[Union[uuid.UUID, str]] = None,
    ) -> Integration:
        org_id = self._resolve_org_id(organization_id)
        response = await self._transport.request(
            "GET",
            f"/api/v1/organizations/{org_id}/integrations/{integration_id}",
        )
        return Integration.model_validate(response)

    async def create(
        self,
        name: str,
        url: str,
        subscribed_events: List[str],
        description: Optional[str] = None,
        provider: str = "webhook",
        headers: Optional[Dict[str, str]] = None,
        organization_id: Optional[Union[uuid.UUID, str]] = None,
    ) -> IntegrationCreateResponse:
        org_id = self._resolve_org_id(organization_id)
        payload = {
            "name": name,
            "url": url,
            "subscribed_events": subscribed_events,
            "description": description,
            "provider": provider,
            "headers": headers,
        }
        response = await self._transport.request(
            "POST",
            f"/api/v1/organizations/{org_id}/integrations",
            json=payload,
        )
        return IntegrationCreateResponse.model_validate(response)

    async def suspend(
        self,
        integration_id: Union[uuid.UUID, str],
        organization_id: Optional[Union[uuid.UUID, str]] = None,
    ) -> Integration:
        org_id = self._resolve_org_id(organization_id)
        response = await self._transport.request(
            "POST",
            f"/api/v1/organizations/{org_id}/integrations/{integration_id}/suspend",
        )
        return Integration.model_validate(response)

    async def revoke(
        self,
        integration_id: Union[uuid.UUID, str],
        organization_id: Optional[Union[uuid.UUID, str]] = None,
    ) -> Integration:
        org_id = self._resolve_org_id(organization_id)
        response = await self._transport.request(
            "POST",
            f"/api/v1/organizations/{org_id}/integrations/{integration_id}/revoke",
        )
        return Integration.model_validate(response)

    async def test_ping(
        self,
        integration_id: Union[uuid.UUID, str],
        organization_id: Optional[Union[uuid.UUID, str]] = None,
    ) -> WebhookDelivery:
        org_id = self._resolve_org_id(organization_id)
        response = await self._transport.request(
            "POST",
            f"/api/v1/organizations/{org_id}/integrations/{integration_id}/test",
        )
        return WebhookDelivery.model_validate(response)

    async def list_deliveries(
        self,
        integration_id: Union[uuid.UUID, str],
        organization_id: Optional[Union[uuid.UUID, str]] = None,
        status: Optional[str] = None,
        event_type: Optional[str] = None,
        limit: int = 50,
        offset: int = 0,
    ) -> WebhookDeliveryList:
        org_id = self._resolve_org_id(organization_id)
        params: Dict[str, Any] = {"limit": limit, "offset": offset}
        if status:
            params["status"] = status
        if event_type:
            params["event_type"] = event_type

        response = await self._transport.request(
            "GET",
            f"/api/v1/organizations/{org_id}/integrations/{integration_id}/deliveries",
            params=params,
        )
        return WebhookDeliveryList.model_validate(response)

    async def get_delivery(
        self,
        integration_id: Union[uuid.UUID, str],
        delivery_id: Union[uuid.UUID, str],
        organization_id: Optional[Union[uuid.UUID, str]] = None,
    ) -> WebhookDelivery:
        org_id = self._resolve_org_id(organization_id)
        response = await self._transport.request(
            "GET",
            f"/api/v1/organizations/{org_id}/integrations/{integration_id}/deliveries/{delivery_id}",
        )
        return WebhookDelivery.model_validate(response)

    async def retry_delivery(
        self,
        integration_id: Union[uuid.UUID, str],
        delivery_id: Union[uuid.UUID, str],
        organization_id: Optional[Union[uuid.UUID, str]] = None,
    ) -> WebhookDelivery:
        org_id = self._resolve_org_id(organization_id)
        response = await self._transport.request(
            "POST",
            f"/api/v1/organizations/{org_id}/integrations/{integration_id}/deliveries/{delivery_id}/retry",
        )
        return WebhookDelivery.model_validate(response)

    async def get_supported_events(
        self,
        organization_id: Optional[Union[uuid.UUID, str]] = None,
    ) -> SupportedEvents:
        org_id = self._resolve_org_id(organization_id)
        response = await self._transport.request(
            "GET",
            f"/api/v1/organizations/{org_id}/integrations/supported-events",
        )
        return SupportedEvents.model_validate(response)
