"""Centralized Audit Service for tamper-resistant security, governance, and forensic tracking."""

from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple, Union
import uuid

from sqlalchemy import desc, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.correlation import get_current_request_id
from app.core.logging import log_security_event
from app.db.models.audit_event import AuditEvent


class AuditActorType(str, Enum):
    USER = "USER"
    AGENT = "AGENT"
    SYSTEM = "SYSTEM"


class AuditOutcome(str, Enum):
    SUCCESS = "success"
    DENIED = "denied"
    FAILURE = "failure"


class AuditEventType(str, Enum):
    # Authentication & Session
    AUTH_LOGIN_SUCCESS = "AUTH_LOGIN_SUCCESS"
    AUTH_LOGIN_FAILURE = "AUTH_LOGIN_FAILURE"
    AUTH_LOGOUT = "AUTH_LOGOUT"
    AUTH_ORGANIZATION_SWITCH = "AUTH_ORGANIZATION_SWITCH"

    # User & Membership Management
    USER_CREATED = "USER_CREATED"
    USER_UPDATED = "USER_UPDATED"
    USER_SUSPENDED = "USER_SUSPENDED"
    USER_DISABLED = "USER_DISABLED"
    MEMBERSHIP_CREATED = "MEMBERSHIP_CREATED"
    MEMBERSHIP_UPDATED = "MEMBERSHIP_UPDATED"
    MEMBERSHIP_REVOKED = "MEMBERSHIP_REVOKED"

    # Agent & Credential Governance
    AGENT_CREATED = "AGENT_CREATED"
    AGENT_UPDATED = "AGENT_UPDATED"
    AGENT_SUSPENDED = "AGENT_SUSPENDED"
    AGENT_REVOKED = "AGENT_REVOKED"
    AGENT_CREDENTIAL_ISSUED = "AGENT_CREDENTIAL_ISSUED"
    AGENT_CREDENTIAL_REVOKED = "AGENT_CREDENTIAL_REVOKED"

    # Tool & Operation Registry
    TOOL_CREATED = "TOOL_CREATED"
    TOOL_UPDATED = "TOOL_UPDATED"
    TOOL_SUSPENDED = "TOOL_SUSPENDED"
    TOOL_REVOKED = "TOOL_REVOKED"
    OPERATION_CREATED = "OPERATION_CREATED"
    OPERATION_UPDATED = "OPERATION_UPDATED"
    OPERATION_SUSPENDED = "OPERATION_SUSPENDED"
    OPERATION_REVOKED = "OPERATION_REVOKED"

    # Authorization & Policies
    PERMISSION_CREATED = "PERMISSION_CREATED"
    PERMISSION_UPDATED = "PERMISSION_UPDATED"
    PERMISSION_SUSPENDED = "PERMISSION_SUSPENDED"
    PERMISSION_REVOKED = "PERMISSION_REVOKED"
    POLICY_CREATED = "POLICY_CREATED"
    POLICY_UPDATED = "POLICY_UPDATED"
    POLICY_VERSION_CREATED = "POLICY_VERSION_CREATED"
    POLICY_PUBLISHED = "POLICY_PUBLISHED"
    POLICY_RETIRED = "POLICY_RETIRED"

    # Runtime Execution & Decision Engine
    RUNTIME_ACTION_CREATED = "RUNTIME_ACTION_CREATED"
    RUNTIME_ACTION_EVALUATED = "RUNTIME_ACTION_EVALUATED"
    RISK_ASSESSMENT_CREATED = "RISK_ASSESSMENT_CREATED"
    DECISION_CREATED = "DECISION_CREATED"

    # Human Governance & Approvals
    APPROVAL_CREATED = "APPROVAL_CREATED"
    APPROVAL_APPROVED = "APPROVAL_APPROVED"
    APPROVAL_REJECTED = "APPROVAL_REJECTED"
    APPROVAL_EXPIRED = "APPROVAL_EXPIRED"
    APPROVAL_CANCELLED = "APPROVAL_CANCELLED"

    # Controlled Execution Layer
    EXECUTION_CREATED = "EXECUTION_CREATED"
    EXECUTION_STARTED = "EXECUTION_STARTED"
    EXECUTION_SUCCEEDED = "EXECUTION_SUCCEEDED"
    EXECUTION_FAILED = "EXECUTION_FAILED"
    EXECUTION_BLOCKED = "EXECUTION_BLOCKED"

    # Sentinel Security Scanner Layer
    SECURITY_SCAN_STARTED = "SECURITY_SCAN_STARTED"
    SECURITY_SCAN_COMPLETED = "SECURITY_SCAN_COMPLETED"
    SECURITY_FINDING_CREATED = "SECURITY_FINDING_CREATED"

    # LLM Security Gateway Layer
    LLM_REQUEST_RECEIVED = "LLM_REQUEST_RECEIVED"
    LLM_INPUT_SCANNED = "LLM_INPUT_SCANNED"
    LLM_REQUEST_BLOCKED = "LLM_REQUEST_BLOCKED"
    LLM_APPROVAL_REQUIRED = "LLM_APPROVAL_REQUIRED"
    LLM_REQUEST_SENT = "LLM_REQUEST_SENT"
    LLM_RESPONSE_RECEIVED = "LLM_RESPONSE_RECEIVED"
    LLM_OUTPUT_SCANNED = "LLM_OUTPUT_SCANNED"
    LLM_OUTPUT_BLOCKED = "LLM_OUTPUT_BLOCKED"
    LLM_REQUEST_COMPLETED = "LLM_REQUEST_COMPLETED"
    LLM_PROVIDER_ERROR = "LLM_PROVIDER_ERROR"

    # MCP Security Layer
    MCP_SERVER_REGISTERED = "MCP_SERVER_REGISTERED"
    MCP_SERVER_UPDATED = "MCP_SERVER_UPDATED"
    MCP_SERVER_SUSPENDED = "MCP_SERVER_SUSPENDED"
    MCP_SERVER_REVOKED = "MCP_SERVER_REVOKED"
    MCP_DISCOVERY_STARTED = "MCP_DISCOVERY_STARTED"
    MCP_DISCOVERY_COMPLETED = "MCP_DISCOVERY_COMPLETED"
    MCP_DISCOVERY_FAILED = "MCP_DISCOVERY_FAILED"
    MCP_TOOL_DISCOVERED = "MCP_TOOL_DISCOVERED"
    MCP_TOOL_ACTIVATED = "MCP_TOOL_ACTIVATED"
    MCP_TOOL_SUSPENDED = "MCP_TOOL_SUSPENDED"
    MCP_TOOL_REVOKED = "MCP_TOOL_REVOKED"
    MCP_TOOL_SCHEMA_CHANGED = "MCP_TOOL_SCHEMA_CHANGED"
    MCP_TOOL_CALL_RECEIVED = "MCP_TOOL_CALL_RECEIVED"
    MCP_TOOL_CALL_BLOCKED = "MCP_TOOL_CALL_BLOCKED"
    MCP_TOOL_CALL_APPROVAL_REQUIRED = "MCP_TOOL_CALL_APPROVAL_REQUIRED"
    MCP_TOOL_CALL_EXECUTED = "MCP_TOOL_CALL_EXECUTED"
    MCP_TOOL_RESULT_SCANNED = "MCP_TOOL_RESULT_SCANNED"
    MCP_TOOL_RESULT_BLOCKED = "MCP_TOOL_RESULT_BLOCKED"
    MCP_TRANSPORT_ERROR = "MCP_TRANSPORT_ERROR"

    # Behavioral & Anomaly Detection Engine
    BEHAVIOR_BASELINE_CREATED = "BEHAVIOR_BASELINE_CREATED"
    BEHAVIOR_BASELINE_UPDATED = "BEHAVIOR_BASELINE_UPDATED"
    BEHAVIOR_ANOMALY_DETECTED = "BEHAVIOR_ANOMALY_DETECTED"
    BEHAVIOR_ANOMALY_REVIEWED = "BEHAVIOR_ANOMALY_REVIEWED"
    BEHAVIOR_ANOMALY_RESOLVED = "BEHAVIOR_ANOMALY_RESOLVED"
    BEHAVIOR_ANOMALY_SUPPRESSED = "BEHAVIOR_ANOMALY_SUPPRESSED"

    # Integrations & Webhooks Layer
    INTEGRATION_CREATED = "INTEGRATION_CREATED"
    INTEGRATION_UPDATED = "INTEGRATION_UPDATED"
    INTEGRATION_SUSPENDED = "INTEGRATION_SUSPENDED"
    INTEGRATION_REVOKED = "INTEGRATION_REVOKED"
    INTEGRATION_TEST_PING = "INTEGRATION_TEST_PING"
    WEBHOOK_DELIVERED = "WEBHOOK_DELIVERED"
    WEBHOOK_FAILED = "WEBHOOK_FAILED"


SENSITIVE_FIELD_NAMES = {
    "password",
    "password_hash",
    "raw_token",
    "raw_key",
    "api_key",
    "secret",
    "access_token",
    "credential_hash",
    "authorization",
    "client_secret",
}


def sanitize_metadata(data: Optional[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
    """Recursively strip passwords, credentials, and sensitive secrets from audit metadata."""
    if data is None:
        return None
    sanitized: Dict[str, Any] = {}
    for k, v in data.items():
        if k.lower() in SENSITIVE_FIELD_NAMES:
            sanitized[k] = "[REDACTED]"
        elif isinstance(v, dict):
            sanitized[k] = sanitize_metadata(v)
        elif isinstance(v, list):
            sanitized[k] = [
                sanitize_metadata(item) if isinstance(item, dict) else item
                for item in v
            ]
        else:
            sanitized[k] = v
    return sanitized


async def record_event(
    session: AsyncSession,
    event_type: Union[AuditEventType, str],
    action: str,
    organization_id: Optional[uuid.UUID] = None,
    actor_type: Union[AuditActorType, str] = AuditActorType.USER,
    actor_id: Optional[str] = None,
    actor_display: Optional[str] = None,
    resource_type: Optional[str] = None,
    resource_id: Optional[Union[uuid.UUID, str]] = None,
    outcome: Union[AuditOutcome, str] = AuditOutcome.SUCCESS,
    metadata: Optional[Dict[str, Any]] = None,
    request_id: Optional[str] = None,
    ip_address: Optional[str] = None,
    user_agent: Optional[str] = None,
    user_id: Optional[uuid.UUID] = None,
) -> AuditEvent:
    """Core centralized primitive to persist an immutable, tamper-evident security audit record."""
    safe_metadata = sanitize_metadata(metadata)
    effective_req_id = request_id or get_current_request_id()

    # Normalize enums
    ev_type_str = event_type.value if isinstance(event_type, Enum) else str(event_type)
    actor_type_str = actor_type.value if isinstance(actor_type, Enum) else str(actor_type)
    outcome_str = outcome.value if isinstance(outcome, Enum) else str(outcome)

    # Actor resolution fallback
    resolved_actor_id = actor_id
    resolved_user_id = user_id
    if actor_type_str == AuditActorType.USER.value:
        if resolved_user_id is None and actor_id:
            try:
                resolved_user_id = uuid.UUID(actor_id)
            except (ValueError, TypeError):
                pass
        elif resolved_user_id is not None and not resolved_actor_id:
            resolved_actor_id = str(resolved_user_id)

    res_id_str = str(resource_id) if resource_id is not None else None

    event = AuditEvent(
        organization_id=organization_id,
        user_id=resolved_user_id,
        actor_type=actor_type_str,
        actor_id=resolved_actor_id,
        actor_display=actor_display,
        event_type=ev_type_str,
        action=action,
        resource_type=resource_type,
        resource_id=res_id_str,
        target_type=resource_type,
        target_id=res_id_str,
        outcome=outcome_str.lower(),
        event_metadata=safe_metadata,
        request_id=effective_req_id,
        ip_address=ip_address,
        user_agent=user_agent,
    )

    session.add(event)
    await session.flush()

    # Emit structured log
    log_security_event(
        event=ev_type_str,
        level="INFO" if outcome_str.lower() == "success" else "WARNING",
        organization_id=organization_id,
        actor_id=resolved_actor_id,
        actor_type=actor_type_str,
        outcome=outcome_str,
        details={
            "action": action,
            "resource_type": resource_type,
            "resource_id": res_id_str,
            **(safe_metadata or {}),
        },
        request_id=effective_req_id,
    )

    # Deliver to subscribed webhooks (isolated: never alters or fails core audit/decision)
    if organization_id and ev_type_str not in ("WEBHOOK_DELIVERED", "WEBHOOK_FAILED"):
        try:
            from app.services.integrations.delivery import dispatch_event_to_integrations
            await dispatch_event_to_integrations(
                session=session,
                organization_id=organization_id,
                event_id=str(event.id),
                event_type=ev_type_str,
                action=action,
                outcome=outcome_str,
                actor_type=actor_type_str,
                actor_id=resolved_actor_id,
                actor_display=actor_display,
                resource_type=resource_type,
                resource_id=res_id_str,
                data=safe_metadata,
                request_id=effective_req_id,
                timestamp=event.created_at,
            )
        except Exception:
            # Notifications must never abort transactions or compromise security outcomes
            pass

    return event


async def record_user_event(
    session: AsyncSession,
    event_type: Union[AuditEventType, str],
    action: str,
    user_id: uuid.UUID,
    organization_id: Optional[uuid.UUID] = None,
    user_display: Optional[str] = None,
    resource_type: Optional[str] = None,
    resource_id: Optional[Union[uuid.UUID, str]] = None,
    outcome: Union[AuditOutcome, str] = AuditOutcome.SUCCESS,
    metadata: Optional[Dict[str, Any]] = None,
    request_id: Optional[str] = None,
    ip_address: Optional[str] = None,
    user_agent: Optional[str] = None,
) -> AuditEvent:
    """Convenience helper to record an action triggered by an authenticated human operator."""
    return await record_event(
        session=session,
        event_type=event_type,
        action=action,
        organization_id=organization_id,
        actor_type=AuditActorType.USER,
        actor_id=str(user_id),
        actor_display=user_display,
        resource_type=resource_type,
        resource_id=resource_id,
        outcome=outcome,
        metadata=metadata,
        request_id=request_id,
        ip_address=ip_address,
        user_agent=user_agent,
        user_id=user_id,
    )


async def record_agent_event(
    session: AsyncSession,
    event_type: Union[AuditEventType, str],
    action: str,
    agent_id: uuid.UUID,
    organization_id: Optional[uuid.UUID] = None,
    agent_display: Optional[str] = None,
    resource_type: Optional[str] = None,
    resource_id: Optional[Union[uuid.UUID, str]] = None,
    outcome: Union[AuditOutcome, str] = AuditOutcome.SUCCESS,
    metadata: Optional[Dict[str, Any]] = None,
    request_id: Optional[str] = None,
    ip_address: Optional[str] = None,
    user_agent: Optional[str] = None,
) -> AuditEvent:
    """Convenience helper to record an action executed by an AI agent identity."""
    return await record_event(
        session=session,
        event_type=event_type,
        action=action,
        organization_id=organization_id,
        actor_type=AuditActorType.AGENT,
        actor_id=str(agent_id),
        actor_display=agent_display,
        resource_type=resource_type,
        resource_id=resource_id,
        outcome=outcome,
        metadata=metadata,
        request_id=request_id,
        ip_address=ip_address,
        user_agent=user_agent,
    )


async def record_security_event(
    session: AsyncSession,
    event_type: Union[AuditEventType, str],
    action: str,
    organization_id: Optional[uuid.UUID] = None,
    resource_type: Optional[str] = None,
    resource_id: Optional[Union[uuid.UUID, str]] = None,
    outcome: Union[AuditOutcome, str] = AuditOutcome.SUCCESS,
    metadata: Optional[Dict[str, Any]] = None,
    request_id: Optional[str] = None,
    actor_id: Optional[str] = "custode_kernel",
    actor_display: Optional[str] = "CUSTODE Control Subsystem",
) -> AuditEvent:
    """Convenience helper to record an automated evaluation or security decision."""
    return await record_event(
        session=session,
        event_type=event_type,
        action=action,
        organization_id=organization_id,
        actor_type=AuditActorType.SYSTEM,
        actor_id=actor_id,
        actor_display=actor_display,
        resource_type=resource_type,
        resource_id=resource_id,
        outcome=outcome,
        metadata=metadata,
        request_id=request_id,
    )


async def list_events(
    session: AsyncSession,
    organization_id: uuid.UUID,
    event_type: Optional[str] = None,
    action: Optional[str] = None,
    actor_type: Optional[str] = None,
    actor_id: Optional[str] = None,
    user_id: Optional[uuid.UUID] = None,
    resource_type: Optional[str] = None,
    resource_id: Optional[str] = None,
    outcome: Optional[str] = None,
    request_id: Optional[str] = None,
    start_time: Optional[datetime] = None,
    end_time: Optional[datetime] = None,
    limit: int = 50,
    offset: int = 0,
) -> Tuple[List[AuditEvent], int]:
    """Retrieve filtered, paginated audit records strictly scoped to an organization."""
    query = select(AuditEvent).where(AuditEvent.organization_id == organization_id)
    count_query = select(func.count(AuditEvent.id)).where(AuditEvent.organization_id == organization_id)

    if event_type:
        query = query.where(AuditEvent.event_type == event_type)
        count_query = count_query.where(AuditEvent.event_type == event_type)

    if action:
        query = query.where(AuditEvent.action == action)
        count_query = count_query.where(AuditEvent.action == action)

    if actor_type:
        query = query.where(AuditEvent.actor_type == actor_type.upper())
        count_query = count_query.where(AuditEvent.actor_type == actor_type.upper())

    if actor_id:
        query = query.where(AuditEvent.actor_id == actor_id)
        count_query = count_query.where(AuditEvent.actor_id == actor_id)

    if user_id:
        query = query.where(AuditEvent.user_id == user_id)
        count_query = count_query.where(AuditEvent.user_id == user_id)

    if resource_type:
        query = query.where(
            (AuditEvent.resource_type == resource_type) | (AuditEvent.target_type == resource_type)
        )
        count_query = count_query.where(
            (AuditEvent.resource_type == resource_type) | (AuditEvent.target_type == resource_type)
        )

    if resource_id:
        query = query.where(
            (AuditEvent.resource_id == resource_id) | (AuditEvent.target_id == resource_id)
        )
        count_query = count_query.where(
            (AuditEvent.resource_id == resource_id) | (AuditEvent.target_id == resource_id)
        )

    if outcome:
        query = query.where(AuditEvent.outcome == outcome.lower())
        count_query = count_query.where(AuditEvent.outcome == outcome.lower())

    if request_id:
        query = query.where(AuditEvent.request_id == request_id)
        count_query = count_query.where(AuditEvent.request_id == request_id)

    if start_time:
        query = query.where(AuditEvent.created_at >= start_time)
        count_query = count_query.where(AuditEvent.created_at >= start_time)

    if end_time:
        query = query.where(AuditEvent.created_at <= end_time)
        count_query = count_query.where(AuditEvent.created_at <= end_time)

    total_res = await session.execute(count_query)
    total = total_res.scalar_one()

    query = query.order_by(desc(AuditEvent.created_at)).offset(offset).limit(limit)
    res = await session.execute(query)
    items = list(res.scalars().all())

    return items, total


async def get_event(
    session: AsyncSession,
    organization_id: uuid.UUID,
    event_id: uuid.UUID,
) -> Optional[AuditEvent]:
    """Retrieve a single audit event guaranteed to belong to the requested organization."""
    query = (
        select(AuditEvent)
        .where(
            AuditEvent.id == event_id,
            AuditEvent.organization_id == organization_id,
        )
    )
    res = await session.execute(query)
    return res.scalar_one_or_none()
