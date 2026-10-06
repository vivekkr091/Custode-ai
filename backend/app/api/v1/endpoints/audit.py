"""Security Audit Trail query API endpoints."""

from datetime import datetime
from typing import Optional
import uuid

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import require_any_member
from app.db.models.membership import Membership
from app.db.session import get_db_session
from app.schemas.audit import AuditEventListResponse, AuditEventResponse
from app.services.audit import get_audit_event, list_audit_events

router = APIRouter(
    prefix="/organizations/{organization_id}",
    tags=["Audit"],
)


@router.get(
    "/audit-events",
    response_model=AuditEventListResponse,
    summary="List Organization Audit Events",
)
async def list_organization_audit_events(
    organization_id: uuid.UUID,
    event_type: Optional[str] = Query(None, description="Filter by controlled event type"),
    action: Optional[str] = Query(None, description="Filter by event action name"),
    actor_type: Optional[str] = Query(None, description="Filter by actor type (USER, AGENT, SYSTEM)"),
    actor_id: Optional[str] = Query(None, description="Filter by actor identifier"),
    user_id: Optional[uuid.UUID] = Query(None, description="Filter by actor user ID"),
    resource_type: Optional[str] = Query(None, description="Filter by resource type"),
    resource_id: Optional[str] = Query(None, description="Filter by resource identifier"),
    outcome: Optional[str] = Query(None, description="Filter by outcome (e.g. success, denied, failure)"),
    request_id: Optional[str] = Query(None, description="Filter by request correlation ID"),
    start_time: Optional[datetime] = Query(None, description="Filter events on or after this timestamp"),
    end_time: Optional[datetime] = Query(None, description="Filter events on or before this timestamp"),
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0),
    membership: Membership = Depends(require_any_member),
    session: AsyncSession = Depends(get_db_session),
) -> AuditEventListResponse:
    """Retrieve immutable security audit trail events strictly scoped to the active organization."""
    events, total = await list_audit_events(
        session=session,
        organization_id=organization_id,
        event_type=event_type,
        action=action,
        actor_type=actor_type,
        actor_id=actor_id,
        user_id=user_id,
        resource_type=resource_type,
        resource_id=resource_id,
        outcome=outcome,
        request_id=request_id,
        start_time=start_time,
        end_time=end_time,
        limit=limit,
        offset=offset,
    )
    items = [AuditEventResponse.model_validate(e) for e in events]
    return AuditEventListResponse(items=items, total=total)


@router.get(
    "/audit-events/{event_id}",
    response_model=AuditEventResponse,
    summary="Get Audit Event Details",
)
async def get_organization_audit_event(
    organization_id: uuid.UUID,
    event_id: uuid.UUID,
    membership: Membership = Depends(require_any_member),
    session: AsyncSession = Depends(get_db_session),
) -> AuditEventResponse:
    """Retrieve details of a specific security audit event strictly within the organization boundary."""
    event = await get_audit_event(
        session=session,
        organization_id=organization_id,
        event_id=event_id,
    )
    if event is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Audit event '{event_id}' not found in organization '{organization_id}'",
        )
    return AuditEventResponse.model_validate(event)
