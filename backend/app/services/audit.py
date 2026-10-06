"""Audit service for logging and querying tamper-resistant administrative events."""

from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple, Union
import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from app.audit.service import (
    AuditActorType,
    AuditEventType,
    AuditOutcome,
    get_event,
    list_events,
    record_event,
    record_user_event,
    record_agent_event,
    record_security_event,
    sanitize_metadata,
)
from app.db.models.audit_event import AuditEvent

_sanitize_metadata = sanitize_metadata


async def log_audit_event(
    session: AsyncSession,
    action: str,
    organization_id: Optional[uuid.UUID] = None,
    user_id: Optional[uuid.UUID] = None,
    target_type: Optional[str] = None,
    target_id: Optional[str] = None,
    outcome: str = "success",
    metadata: Optional[Dict[str, Any]] = None,
    request_id: Optional[str] = None,
    ip_address: Optional[str] = None,
    user_agent: Optional[str] = None,
    event_type: Optional[Union[AuditEventType, str]] = None,
    actor_type: Optional[Union[AuditActorType, str]] = None,
    actor_id: Optional[str] = None,
) -> AuditEvent:
    """Persist an immutable audit log entry (backwards compatible with Milestone 14)."""
    effective_event_type = event_type or action
    effective_actor_type = actor_type or (AuditActorType.USER if user_id else AuditActorType.SYSTEM)
    effective_actor_id = actor_id or (str(user_id) if user_id else None)

    return await record_event(
        session=session,
        event_type=effective_event_type,
        action=action,
        organization_id=organization_id,
        actor_type=effective_actor_type,
        actor_id=effective_actor_id,
        resource_type=target_type,
        resource_id=target_id,
        outcome=outcome,
        metadata=metadata,
        request_id=request_id,
        ip_address=ip_address,
        user_agent=user_agent,
        user_id=user_id,
    )


async def list_audit_events(
    session: AsyncSession,
    organization_id: uuid.UUID,
    action: Optional[str] = None,
    user_id: Optional[uuid.UUID] = None,
    outcome: Optional[str] = None,
    event_type: Optional[str] = None,
    actor_type: Optional[str] = None,
    actor_id: Optional[str] = None,
    resource_type: Optional[str] = None,
    resource_id: Optional[str] = None,
    request_id: Optional[str] = None,
    start_time: Optional[datetime] = None,
    end_time: Optional[datetime] = None,
    limit: int = 50,
    offset: int = 0,
) -> Tuple[List[AuditEvent], int]:
    """Retrieve paginated audit events strictly scoped to an organization."""
    return await list_events(
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


async def get_audit_event(
    session: AsyncSession,
    organization_id: uuid.UUID,
    event_id: uuid.UUID,
) -> Optional[AuditEvent]:
    """Retrieve a single audit event scoped to an organization."""
    return await get_event(
        session=session,
        organization_id=organization_id,
        event_id=event_id,
    )
