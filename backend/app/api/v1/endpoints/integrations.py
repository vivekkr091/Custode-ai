"""API Endpoints for External Integrations and Webhook Delivery Management."""

from typing import List, Optional
import uuid

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import require_admin, require_any_member
from app.db.models.membership import Membership
from app.db.session import get_db_session
from app.schemas.integration import (
    IntegrationCreate,
    IntegrationCreateResponse,
    IntegrationListResponse,
    IntegrationResponse,
    IntegrationUpdate,
    SupportedEventsResponse,
    WebhookDeliveryListResponse,
    WebhookDeliveryResponse,
)
from app.services.integrations.events import (
    ALL_SUPPORTED_EVENTS,
    SUPPORTED_EVENT_TAXONOMY,
)
from app.services.integrations.service import (
    DeliveryNotFoundError,
    IntegrationNotFoundError,
    InvalidIntegrationError,
    create_integration,
    get_delivery,
    get_integration,
    list_deliveries,
    list_integrations,
    retry_delivery,
    revoke_integration,
    suspend_integration,
    test_integration_ping,
    update_integration,
)

router = APIRouter(
    prefix="/organizations/{organization_id}/integrations",
    tags=["Integrations & Webhooks"],
)


@router.get(
    "/supported-events",
    response_model=SupportedEventsResponse,
    summary="List Supported Webhook Event Types",
)
async def get_supported_events(
    organization_id: uuid.UUID,
    membership: Membership = Depends(require_any_member),
) -> SupportedEventsResponse:
    """Retrieve the authoritative registry of security events eligible for webhook dispatch."""
    return SupportedEventsResponse(
        taxonomy=SUPPORTED_EVENT_TAXONOMY,
        all_events=ALL_SUPPORTED_EVENTS,
    )


@router.post(
    "",
    response_model=IntegrationCreateResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create Webhook Integration",
)
async def create_new_integration(
    organization_id: uuid.UUID,
    payload: IntegrationCreate,
    membership: Membership = Depends(require_admin),
    session: AsyncSession = Depends(get_db_session),
) -> IntegrationCreateResponse:
    """Create a new external integration destination with a securely generated signing secret.

    SECURITY NOTE:
    The signing secret is returned ONLY ONCE in the creation response.
    Subsequent GET requests display only the public secret prefix.
    """
    try:
        integration, raw_secret = await create_integration(
            session=session,
            organization_id=organization_id,
            data=payload,
            user_id=membership.user_id,
        )
        await session.commit()

        resp_dict = IntegrationResponse.model_validate(integration).model_dump()
        return IntegrationCreateResponse(
            **resp_dict,
            signing_secret=raw_secret,
        )
    except InvalidIntegrationError as e:
        await session.rollback()
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )


@router.get(
    "",
    response_model=IntegrationListResponse,
    summary="List Integrations",
)
async def list_org_integrations(
    organization_id: uuid.UUID,
    status_filter: Optional[str] = Query(None, alias="status", description="Filter by status (active, suspended, revoked)"),
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0),
    membership: Membership = Depends(require_any_member),
    session: AsyncSession = Depends(get_db_session),
) -> IntegrationListResponse:
    """Retrieve all external webhook integrations configured for the organization."""
    items, total = await list_integrations(
        session=session,
        organization_id=organization_id,
        status=status_filter,
        limit=limit,
        offset=offset,
    )
    return IntegrationListResponse(
        items=[IntegrationResponse.model_validate(item) for item in items],
        total=total,
    )


@router.get(
    "/{integration_id}",
    response_model=IntegrationResponse,
    summary="Get Integration Details",
)
async def get_org_integration(
    organization_id: uuid.UUID,
    integration_id: uuid.UUID,
    membership: Membership = Depends(require_any_member),
    session: AsyncSession = Depends(get_db_session),
) -> IntegrationResponse:
    """Retrieve configuration details for an integration without exposing raw signing secrets."""
    try:
        integration = await get_integration(
            session=session,
            organization_id=organization_id,
            integration_id=integration_id,
        )
        return IntegrationResponse.model_validate(integration)
    except IntegrationNotFoundError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e),
        )


@router.patch(
    "/{integration_id}",
    response_model=IntegrationResponse,
    summary="Update Integration Configuration",
)
async def update_org_integration(
    organization_id: uuid.UUID,
    integration_id: uuid.UUID,
    payload: IntegrationUpdate,
    membership: Membership = Depends(require_admin),
    session: AsyncSession = Depends(get_db_session),
) -> IntegrationResponse:
    """Update settings for an active integration."""
    try:
        updated = await update_integration(
            session=session,
            organization_id=organization_id,
            integration_id=integration_id,
            data=payload,
            user_id=membership.user_id,
        )
        await session.commit()
        return IntegrationResponse.model_validate(updated)
    except IntegrationNotFoundError as e:
        await session.rollback()
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e),
        )
    except InvalidIntegrationError as e:
        await session.rollback()
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )


@router.post(
    "/{integration_id}/suspend",
    response_model=IntegrationResponse,
    summary="Suspend Integration",
)
async def suspend_org_integration(
    organization_id: uuid.UUID,
    integration_id: uuid.UUID,
    membership: Membership = Depends(require_admin),
    session: AsyncSession = Depends(get_db_session),
) -> IntegrationResponse:
    """Temporarily pause webhook delivery to this destination."""
    try:
        suspended = await suspend_integration(
            session=session,
            organization_id=organization_id,
            integration_id=integration_id,
            user_id=membership.user_id,
        )
        await session.commit()
        return IntegrationResponse.model_validate(suspended)
    except IntegrationNotFoundError as e:
        await session.rollback()
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e),
        )
    except InvalidIntegrationError as e:
        await session.rollback()
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )


@router.post(
    "/{integration_id}/revoke",
    response_model=IntegrationResponse,
    summary="Revoke Integration",
)
async def revoke_org_integration(
    organization_id: uuid.UUID,
    integration_id: uuid.UUID,
    membership: Membership = Depends(require_admin),
    session: AsyncSession = Depends(get_db_session),
) -> IntegrationResponse:
    """Permanently revoke an integration. Revoked integrations cannot be reactivated."""
    try:
        revoked = await revoke_integration(
            session=session,
            organization_id=organization_id,
            integration_id=integration_id,
            user_id=membership.user_id,
        )
        await session.commit()
        return IntegrationResponse.model_validate(revoked)
    except IntegrationNotFoundError as e:
        await session.rollback()
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e),
        )


@router.post(
    "/{integration_id}/test",
    response_model=WebhookDeliveryResponse,
    summary="Test Integration Ping",
)
async def test_org_integration(
    organization_id: uuid.UUID,
    integration_id: uuid.UUID,
    membership: Membership = Depends(require_admin),
    session: AsyncSession = Depends(get_db_session),
) -> WebhookDeliveryResponse:
    """Send a signed diagnostic ping event to verify destination connectivity."""
    try:
        delivery = await test_integration_ping(
            session=session,
            organization_id=organization_id,
            integration_id=integration_id,
        )
        await session.commit()
        # Eager load delivery attempts
        full_delivery = await get_delivery(session, organization_id, delivery.id)
        return WebhookDeliveryResponse.model_validate(full_delivery)
    except IntegrationNotFoundError as e:
        await session.rollback()
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e),
        )
    except InvalidIntegrationError as e:
        await session.rollback()
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )


@router.get(
    "/{integration_id}/deliveries",
    response_model=WebhookDeliveryListResponse,
    summary="List Integration Deliveries",
)
async def list_org_deliveries(
    organization_id: uuid.UUID,
    integration_id: uuid.UUID,
    status_filter: Optional[str] = Query(None, alias="status", description="Filter by status (pending, delivered, retrying, failed)"),
    event_type: Optional[str] = Query(None, description="Filter by event type"),
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0),
    membership: Membership = Depends(require_any_member),
    session: AsyncSession = Depends(get_db_session),
) -> WebhookDeliveryListResponse:
    """Retrieve paginated delivery logs for an integration."""
    try:
        items, total = await list_deliveries(
            session=session,
            organization_id=organization_id,
            integration_id=integration_id,
            status=status_filter,
            event_type=event_type,
            limit=limit,
            offset=offset,
        )
        return WebhookDeliveryListResponse(
            items=[WebhookDeliveryResponse.model_validate(item) for item in items],
            total=total,
            limit=limit,
            offset=offset,
        )
    except IntegrationNotFoundError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e),
        )


@router.get(
    "/{integration_id}/deliveries/{delivery_id}",
    response_model=WebhookDeliveryResponse,
    summary="Get Delivery Details",
)
async def get_org_delivery_detail(
    organization_id: uuid.UUID,
    integration_id: uuid.UUID,
    delivery_id: uuid.UUID,
    membership: Membership = Depends(require_any_member),
    session: AsyncSession = Depends(get_db_session),
) -> WebhookDeliveryResponse:
    """Retrieve detailed delivery records and attempt history."""
    # Ensure integration belongs to organization
    try:
        await get_integration(session, organization_id, integration_id)
        delivery = await get_delivery(session, organization_id, delivery_id)
        if delivery.integration_id != integration_id:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Delivery '{delivery_id}' does not belong to integration '{integration_id}'",
            )
        return WebhookDeliveryResponse.model_validate(delivery)
    except IntegrationNotFoundError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e),
        )
    except DeliveryNotFoundError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e),
        )


@router.post(
    "/{integration_id}/deliveries/{delivery_id}/retry",
    response_model=WebhookDeliveryResponse,
    summary="Retry Failed Delivery",
)
async def retry_org_delivery(
    organization_id: uuid.UUID,
    integration_id: uuid.UUID,
    delivery_id: uuid.UUID,
    membership: Membership = Depends(require_admin),
    session: AsyncSession = Depends(get_db_session),
) -> WebhookDeliveryResponse:
    """Manually retry a failed webhook delivery."""
    try:
        await get_integration(session, organization_id, integration_id)
        updated_delivery = await retry_delivery(
            session=session,
            organization_id=organization_id,
            delivery_id=delivery_id,
        )
        await session.commit()
        full_delivery = await get_delivery(session, organization_id, updated_delivery.id)
        return WebhookDeliveryResponse.model_validate(full_delivery)
    except (IntegrationNotFoundError, DeliveryNotFoundError) as e:
        await session.rollback()
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e),
        )
    except InvalidIntegrationError as e:
        await session.rollback()
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )
