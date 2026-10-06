"""Pydantic models for External Integrations and Webhook Deliveries."""

from datetime import datetime
from typing import Any, Dict, List, Optional
import uuid

from pydantic import Field

from custode.models.base import CUSTODEModel
from custode.models.pagination import PaginatedList


class Integration(CUSTODEModel):
    """External destination or connector configuration."""

    id: uuid.UUID
    organization_id: uuid.UUID
    name: str
    description: Optional[str] = None
    provider: str = "webhook"
    status: str
    url: str
    secret_prefix: str
    subscribed_events: List[str]
    headers: Optional[Dict[str, str]] = None
    last_delivery_at: Optional[datetime] = None
    created_at: datetime
    updated_at: datetime


class IntegrationCreateResponse(Integration):
    """Integration creation response containing one-time plain signing secret."""

    signing_secret: str
    warning: str


class IntegrationList(PaginatedList[Integration]):
    """Paginated collection of configured Integrations."""

    items: List[Integration] = Field(default_factory=list)


class WebhookAttempt(CUSTODEModel):
    """Historical record of an individual webhook dispatch attempt."""

    id: uuid.UUID
    delivery_id: uuid.UUID
    attempt_number: int
    status: str
    response_status_code: Optional[int] = None
    duration_ms: Optional[int] = None
    sanitized_error: Optional[str] = None
    attempted_at: datetime


class WebhookDelivery(CUSTODEModel):
    """Authoritative ledger entry for an external security event notification delivery."""

    id: uuid.UUID
    organization_id: uuid.UUID
    integration_id: uuid.UUID
    event_id: Optional[str] = None
    event_type: str
    request_id: Optional[str] = None
    delivery_status: str
    attempt_count: int
    max_attempts: int
    payload: Dict[str, Any]
    response_status_code: Optional[int] = None
    sanitized_response_summary: Optional[str] = None
    next_retry_at: Optional[datetime] = None
    delivered_at: Optional[datetime] = None
    created_at: datetime
    attempts: Optional[List[WebhookAttempt]] = None


class WebhookDeliveryList(PaginatedList[WebhookDelivery]):
    """Paginated collection of Webhook Deliveries."""

    items: List[WebhookDelivery] = Field(default_factory=list)


class SupportedEvents(CUSTODEModel):
    """Catalog of security event taxonomy eligible for webhook subscription."""

    taxonomy: Dict[str, Dict[str, Any]]
    all_events: List[str]
