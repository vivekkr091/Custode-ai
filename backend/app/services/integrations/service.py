"""Integration Service for managing external webhooks, credentials, and deliveries."""

from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple
import uuid

import httpx
from sqlalchemy import desc, func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.audit.service import AuditEventType, log_security_event, record_event
from app.core.correlation import get_current_request_id
from app.db.models.audit_event import AuditEvent
from app.db.models.integration import Integration, IntegrationProvider, IntegrationStatus
from app.db.models.webhook_delivery import (
    AttemptStatus,
    DeliveryStatus,
    WebhookAttempt,
    WebhookDelivery,
)
from app.schemas.integration import IntegrationCreate, IntegrationUpdate
from app.services.integrations.crypto import (
    generate_webhook_signing_secret,
    get_secret_provider,
)
from app.services.integrations.delivery import execute_delivery_attempt
from app.services.integrations.events import (
    ALL_SUPPORTED_EVENTS,
    format_webhook_payload,
    is_event_type_supported,
)
from app.services.integrations.ssrf import (
    SSRFProtectionError,
    validate_destination_address,
)


class IntegrationNotFoundError(Exception):
    pass


class DeliveryNotFoundError(Exception):
    pass


class InvalidIntegrationError(Exception):
    pass


async def create_integration(
    session: AsyncSession,
    organization_id: uuid.UUID,
    data: IntegrationCreate,
    user_id: Optional[uuid.UUID] = None,
    allow_local: bool = False,
    allow_insecure: bool = False,
) -> Tuple[Integration, str]:
    """Create a new external integration with high-entropy signing secret and tenant isolation."""
    # 1. Validate destination URL against SSRF
    try:
        validate_destination_address(
            data.url,
            allow_insecure=allow_insecure,
            allow_local=allow_local,
        )
    except SSRFProtectionError as e:
        raise InvalidIntegrationError(f"Invalid webhook URL: {str(e)}")

    # 2. Validate subscribed event types against registry
    invalid_events = [evt for evt in data.subscribed_events if evt != "*" and not is_event_type_supported(evt)]
    if invalid_events:
        raise InvalidIntegrationError(f"Unsupported event types: {', '.join(invalid_events)}")

    # 3. Generate high-entropy signing secret and encrypt for storage at rest
    raw_secret, secret_prefix, secret_hash = generate_webhook_signing_secret()
    provider = get_secret_provider()
    encrypted_secret = provider.encrypt(raw_secret)

    integration = Integration(
        organization_id=organization_id,
        name=data.name,
        description=data.description,
        provider=data.provider,
        status=IntegrationStatus.ACTIVE.value,
        url=data.url,
        secret_prefix=secret_prefix,
        secret_hash=secret_hash,
        encrypted_secret=encrypted_secret,
        subscribed_events=data.subscribed_events,
        headers=data.headers,
    )
    session.add(integration)
    await session.flush()

    # 4. Record audit event
    await record_event(
        session=session,
        event_type=AuditEventType.INTEGRATION_CREATED.value,
        action="INTEGRATION_CREATED",
        organization_id=organization_id,
        actor_type="USER" if user_id else "SYSTEM",
        actor_id=str(user_id) if user_id else None,
        resource_type="integration",
        resource_id=str(integration.id),
        outcome="success",
        metadata={
            "name": integration.name,
            "provider": integration.provider,
            "url": integration.url,
            "secret_prefix": integration.secret_prefix,
            "subscribed_events": integration.subscribed_events,
        },
        user_id=user_id,
    )

    return integration, raw_secret


async def list_integrations(
    session: AsyncSession,
    organization_id: uuid.UUID,
    status: Optional[str] = None,
    limit: int = 50,
    offset: int = 0,
) -> Tuple[List[Integration], int]:
    """List integrations strictly scoped to the specified organization."""
    query = select(Integration).where(Integration.organization_id == organization_id)
    if status:
        query = query.where(Integration.status == status)

    count_query = select(func.count(Integration.id)).where(Integration.organization_id == organization_id)
    if status:
        count_query = count_query.where(Integration.status == status)

    total_res = await session.execute(count_query)
    total = total_res.scalar() or 0

    query = query.order_by(desc(Integration.created_at)).limit(limit).offset(offset)
    res = await session.execute(query)
    items = list(res.scalars().all())

    return items, total


async def get_integration(
    session: AsyncSession,
    organization_id: uuid.UUID,
    integration_id: uuid.UUID,
) -> Integration:
    """Retrieve an integration by ID, enforcing tenant isolation."""
    query = select(Integration).where(
        Integration.organization_id == organization_id,
        Integration.id == integration_id,
    )
    res = await session.execute(query)
    integration = res.scalar_one_or_none()
    if not integration:
        raise IntegrationNotFoundError(f"Integration '{integration_id}' not found in organization")
    return integration


async def update_integration(
    session: AsyncSession,
    organization_id: uuid.UUID,
    integration_id: uuid.UUID,
    data: IntegrationUpdate,
    user_id: Optional[uuid.UUID] = None,
    allow_local: bool = False,
    allow_insecure: bool = False,
) -> Integration:
    """Update integration settings with re-validation and audit tracking."""
    integration = await get_integration(session, organization_id, integration_id)

    if integration.status == IntegrationStatus.REVOKED.value:
        raise InvalidIntegrationError("Revoked integrations cannot be modified")

    if data.url is not None:
        try:
            validate_destination_address(
                data.url,
                allow_insecure=allow_insecure,
                allow_local=allow_local,
            )
            integration.url = data.url
        except SSRFProtectionError as e:
            raise InvalidIntegrationError(f"Invalid webhook URL: {str(e)}")

    if data.name is not None:
        integration.name = data.name
    if data.description is not None:
        integration.description = data.description
    if data.subscribed_events is not None:
        invalid_events = [evt for evt in data.subscribed_events if evt != "*" and not is_event_type_supported(evt)]
        if invalid_events:
            raise InvalidIntegrationError(f"Unsupported event types: {', '.join(invalid_events)}")
        integration.subscribed_events = data.subscribed_events
    if data.headers is not None:
        integration.headers = data.headers

    await session.flush()

    # Record audit event
    await record_event(
        session=session,
        event_type=AuditEventType.INTEGRATION_UPDATED.value,
        action="INTEGRATION_UPDATED",
        organization_id=organization_id,
        actor_type="USER" if user_id else "SYSTEM",
        actor_id=str(user_id) if user_id else None,
        resource_type="integration",
        resource_id=str(integration.id),
        outcome="success",
        metadata={
            "name": integration.name,
            "url": integration.url,
            "subscribed_events": integration.subscribed_events,
        },
        user_id=user_id,
    )

    return integration


async def suspend_integration(
    session: AsyncSession,
    organization_id: uuid.UUID,
    integration_id: uuid.UUID,
    user_id: Optional[uuid.UUID] = None,
) -> Integration:
    """Temporarily pause webhook dispatches for an integration."""
    integration = await get_integration(session, organization_id, integration_id)

    if integration.status == IntegrationStatus.REVOKED.value:
        raise InvalidIntegrationError("Revoked integrations cannot be suspended")

    integration.status = IntegrationStatus.SUSPENDED.value
    await session.flush()

    await record_event(
        session=session,
        event_type=AuditEventType.INTEGRATION_SUSPENDED.value,
        action="INTEGRATION_SUSPENDED",
        organization_id=organization_id,
        actor_type="USER" if user_id else "SYSTEM",
        actor_id=str(user_id) if user_id else None,
        resource_type="integration",
        resource_id=str(integration.id),
        outcome="success",
        user_id=user_id,
    )
    return integration


async def revoke_integration(
    session: AsyncSession,
    organization_id: uuid.UUID,
    integration_id: uuid.UUID,
    user_id: Optional[uuid.UUID] = None,
) -> Integration:
    """Permanently revoke an integration. Revoked integrations cannot be reactivated."""
    integration = await get_integration(session, organization_id, integration_id)

    integration.status = IntegrationStatus.REVOKED.value
    await session.flush()

    await record_event(
        session=session,
        event_type=AuditEventType.INTEGRATION_REVOKED.value,
        action="INTEGRATION_REVOKED",
        organization_id=organization_id,
        actor_type="USER" if user_id else "SYSTEM",
        actor_id=str(user_id) if user_id else None,
        resource_type="integration",
        resource_id=str(integration.id),
        outcome="success",
        user_id=user_id,
    )
    return integration


async def test_integration_ping(
    session: AsyncSession,
    organization_id: uuid.UUID,
    integration_id: uuid.UUID,
    client: Optional[httpx.AsyncClient] = None,
    allow_local: bool = False,
    allow_insecure: bool = False,
) -> WebhookDelivery:
    """Dispatch a synthetic diagnostic ping event to verify webhook connectivity."""
    integration = await get_integration(session, organization_id, integration_id)

    if integration.status == IntegrationStatus.REVOKED.value:
        raise InvalidIntegrationError("Cannot send test ping to a revoked integration")

    test_event_id = str(uuid.uuid4())
    req_id = get_current_request_id() or f"test-ping-{uuid.uuid4().hex[:8]}"

    payload = format_webhook_payload(
        event_id=test_event_id,
        event_type=AuditEventType.INTEGRATION_TEST_PING.value,
        organization_id=organization_id,
        action="TEST_PING",
        outcome="success",
        actor_type="SYSTEM",
        resource_type="integration",
        resource_id=str(integration.id),
        data={
            "message": "CUSTODE Webhook verification ping",
            "integration_name": integration.name,
            "provider": integration.provider,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        },
        request_id=req_id,
    )

    delivery = WebhookDelivery(
        organization_id=organization_id,
        integration_id=integration.id,
        event_id=test_event_id,
        event_type=AuditEventType.INTEGRATION_TEST_PING.value,
        request_id=req_id,
        delivery_status=DeliveryStatus.PENDING.value,
        attempt_count=0,
        max_attempts=1,  # Test pings do not retry
        payload=payload,
    )
    session.add(delivery)
    await session.flush()

    await execute_delivery_attempt(
        session=session,
        delivery=delivery,
        integration=integration,
        client=client,
        allow_local=allow_local,
        allow_insecure=allow_insecure,
    )
    return delivery


async def list_deliveries(
    session: AsyncSession,
    organization_id: uuid.UUID,
    integration_id: uuid.UUID,
    status: Optional[str] = None,
    event_type: Optional[str] = None,
    limit: int = 50,
    offset: int = 0,
) -> Tuple[List[WebhookDelivery], int]:
    """Retrieve delivery history for an integration with tenant scoping."""
    # Ensure integration belongs to organization
    await get_integration(session, organization_id, integration_id)

    query = select(WebhookDelivery).where(
        WebhookDelivery.organization_id == organization_id,
        WebhookDelivery.integration_id == integration_id,
    )
    if status:
        query = query.where(WebhookDelivery.delivery_status == status)
    if event_type:
        query = query.where(WebhookDelivery.event_type == event_type)

    count_query = select(func.count(WebhookDelivery.id)).where(
        WebhookDelivery.organization_id == organization_id,
        WebhookDelivery.integration_id == integration_id,
    )
    if status:
        count_query = count_query.where(WebhookDelivery.delivery_status == status)
    if event_type:
        count_query = count_query.where(WebhookDelivery.event_type == event_type)

    total_res = await session.execute(count_query)
    total = total_res.scalar() or 0

    query = query.order_by(desc(WebhookDelivery.created_at)).limit(limit).offset(offset)
    res = await session.execute(query)
    deliveries = list(res.scalars().all())

    return deliveries, total


async def get_delivery(
    session: AsyncSession,
    organization_id: uuid.UUID,
    delivery_id: uuid.UUID,
) -> WebhookDelivery:
    """Retrieve an individual delivery record and its historical attempts."""
    query = (
        select(WebhookDelivery)
        .where(
            WebhookDelivery.organization_id == organization_id,
            WebhookDelivery.id == delivery_id,
        )
        .options(selectinload(WebhookDelivery.attempts))
    )
    res = await session.execute(query)
    delivery = res.scalar_one_or_none()
    if not delivery:
        raise DeliveryNotFoundError(f"Webhook delivery '{delivery_id}' not found")
    return delivery


async def retry_delivery(
    session: AsyncSession,
    organization_id: uuid.UUID,
    delivery_id: uuid.UUID,
    client: Optional[httpx.AsyncClient] = None,
    allow_local: bool = False,
    allow_insecure: bool = False,
) -> WebhookDelivery:
    """Manually re-dispatch a failed webhook delivery."""
    delivery = await get_delivery(session, organization_id, delivery_id)

    if delivery.delivery_status == DeliveryStatus.DELIVERED.value:
        raise InvalidIntegrationError("Cannot retry a delivery that has already succeeded")

    integration = await get_integration(session, organization_id, delivery.integration_id)
    if integration.status == IntegrationStatus.REVOKED.value:
        raise InvalidIntegrationError("Cannot retry delivery for a revoked integration")

    await execute_delivery_attempt(
        session=session,
        delivery=delivery,
        integration=integration,
        client=client,
        allow_local=allow_local,
        allow_insecure=allow_insecure,
    )
    return delivery
