"""Base resource classes for CUSTODE SDK."""

from __future__ import annotations

from typing import Optional
from custode.config import CUSTODEConfig
from custode.exceptions import ValidationError
from custode.transport.transport import AsyncTransport, SyncTransport


class BaseResource:
    """Synchronous base resource."""

    def __init__(self, transport: SyncTransport, config: CUSTODEConfig) -> None:
        self._transport = transport
        self._config = config

    def _resolve_org_id(self, organization_id: Optional[str] = None) -> str:
        org_id = organization_id or self._config.organization_id
        if not org_id:
            raise ValidationError(
                "Organization ID is required. Pass 'organization_id' parameter or configure client with 'organization_id'."
            )
        return org_id


class AsyncBaseResource:
    """Asynchronous base resource."""

    def __init__(self, transport: AsyncTransport, config: CUSTODEConfig) -> None:
        self._transport = transport
        self._config = config

    def _resolve_org_id(self, organization_id: Optional[str] = None) -> str:
        org_id = organization_id or self._config.organization_id
        if not org_id:
            raise ValidationError(
                "Organization ID is required. Pass 'organization_id' parameter or configure client with 'organization_id'."
            )
        return org_id
