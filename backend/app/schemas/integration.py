"""Pydantic schemas for external Integrations and Webhook Deliveries."""

from datetime import datetime
from typing import Any, Dict, List, Optional
import uuid

from pydantic import BaseModel, ConfigDict, Field


class IntegrationBase(BaseModel):
    name: str = Field(..., min_length=1, max_length=100, description="Integration display name")
    description: Optional[str] = Field(None, max_length=255)
    provider: str = Field("webhook", description="Provider type: webhook or slack")
    url: str = Field(..., max_length=500, description="Target HTTPS webhook URL")
    subscribed_events: List[str] = Field(..., min_length=1, description="List of subscribed event types")
    headers: Optional[Dict[str, str]] = Field(None, description="Optional custom headers")


class IntegrationCreate(IntegrationBase):
    pass


class IntegrationUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=100)
    description: Optional[str] = Field(None, max_length=255)
    url: Optional[str] = Field(None, max_length=500)
    subscribed_events: Optional[List[str]] = Field(None, min_length=1)
    headers: Optional[Dict[str, str]] = None


class IntegrationResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    organization_id: uuid.UUID
    name: str
    description: Optional[str]
    provider: str
    status: str
    url: str
    secret_prefix: str
    subscribed_events: List[str]
    headers: Optional[Dict[str, str]]
    last_delivery_at: Optional[datetime]
    created_at: datetime
    updated_at: datetime


class IntegrationCreateResponse(IntegrationResponse):
    signing_secret: str = Field(
        ...,
        description="High-entropy webhook signing secret. Displayed ONLY ONCE at creation.",
    )
    warning: str = "Store this signing secret safely. It will not be shown again."


class IntegrationListResponse(BaseModel):
    items: List[IntegrationResponse]
    total: int


class WebhookAttemptResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    delivery_id: uuid.UUID
    attempt_number: int
    status: str
    response_status_code: Optional[int]
    duration_ms: Optional[int]
    sanitized_error: Optional[str]
    attempted_at: datetime


class WebhookDeliveryResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    organization_id: uuid.UUID
    integration_id: uuid.UUID
    event_id: Optional[str]
    event_type: str
    request_id: Optional[str]
    delivery_status: str
    attempt_count: int
    max_attempts: int
    payload: Dict[str, Any]
    response_status_code: Optional[int]
    sanitized_response_summary: Optional[str]
    next_retry_at: Optional[datetime]
    delivered_at: Optional[datetime]
    created_at: datetime
    attempts: Optional[List[WebhookAttemptResponse]] = None


class WebhookDeliveryListResponse(BaseModel):
    items: List[WebhookDeliveryResponse]
    total: int
    limit: int
    offset: int


class SupportedEventsResponse(BaseModel):
    taxonomy: Dict[str, Dict[str, Any]]
    all_events: List[str]
