"""Service layer for Permission persistence, validation, and evaluation coordination."""

import uuid
from typing import List, Optional
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.agent import Agent, AgentStatus
from app.db.models.organization import Organization, OrganizationStatus
from app.db.models.permission import Permission, PermissionStatus
from app.db.models.tool import Tool, ToolStatus
from app.db.models.tool_operation import OperationStatus, ToolOperation
from app.engines.permission.evaluator import (
    PermissionEngine,
    PermissionEvaluationResult,
    PermissionRequest,
)
from app.schemas.permission import PermissionCreate, PermissionEvaluationRequest, PermissionUpdate
from app.services.agent import InvalidLifecycleTransitionError, OrganizationNotFoundError, OrganizationSuspendedError
from app.services.tool import ToolNotFoundError
from app.services.tool_operation import OperationNotFoundError


class PermissionNotFoundError(Exception):
    """Raised when a permission grant cannot be found in the organization context."""
    def __init__(self, org_id: uuid.UUID, permission_id: uuid.UUID):
        super().__init__(f"Permission '{permission_id}' not found in organization '{org_id}'")
        self.org_id = org_id
        self.permission_id = permission_id


class DuplicatePermissionError(Exception):
    """Raised when an identical active permission grant already exists."""
    def __init__(self, message: str = "Identical permission grant already exists"):
        super().__init__(message)


class InactiveResourceError(Exception):
    """Raised when attempting to create a permission on a suspended or revoked resource."""
    def __init__(self, resource_type: str, resource_id: uuid.UUID, status: str):
        super().__init__(f"Cannot create permission for {resource_type} '{resource_id}' in state '{status}'")
        self.resource_type = resource_type
        self.resource_id = resource_id
        self.status = status


class ResourceHierarchyError(Exception):
    """Raised when a resource does not belong to the declared parent hierarchy."""
    def __init__(self, message: str):
        super().__init__(message)


async def create_permission(
    session: AsyncSession, organization_id: uuid.UUID, data: PermissionCreate
) -> Permission:
    """Create a new permission grant with full hierarchy and status validation."""
    # 1. Validate Organization
    org_res = await session.execute(
        select(Organization).where(Organization.id == organization_id)
    )
    org = org_res.scalar_one_or_none()
    if org is None:
        raise OrganizationNotFoundError(organization_id)
    if org.status != OrganizationStatus.active.value:
        raise OrganizationSuspendedError(organization_id)

    # 2. Validate Agent
    agent_res = await session.execute(
        select(Agent).where(
            Agent.id == data.agent_id,
            Agent.organization_id == organization_id,
        )
    )
    agent = agent_res.scalar_one_or_none()
    if agent is None:
        raise ResourceHierarchyError(f"Agent '{data.agent_id}' not found in organization '{organization_id}'")
    if agent.status != AgentStatus.active.value:
        raise InactiveResourceError("agent", data.agent_id, agent.status)

    # 3. Validate Tool
    tool_res = await session.execute(
        select(Tool).where(
            Tool.id == data.tool_id,
            Tool.organization_id == organization_id,
        )
    )
    tool = tool_res.scalar_one_or_none()
    if tool is None:
        raise ResourceHierarchyError(f"Tool '{data.tool_id}' not found in organization '{organization_id}'")
    if tool.status != ToolStatus.active.value:
        raise InactiveResourceError("tool", data.tool_id, tool.status)

    # 4. Validate Operation
    op_res = await session.execute(
        select(ToolOperation).where(
            ToolOperation.id == data.operation_id,
            ToolOperation.tool_id == data.tool_id,
        )
    )
    op = op_res.scalar_one_or_none()
    if op is None:
        raise ResourceHierarchyError(f"Operation '{data.operation_id}' not found under tool '{data.tool_id}'")
    if op.status != OperationStatus.active.value:
        raise InactiveResourceError("operation", data.operation_id, op.status)

    # 5. Check duplicate grant
    dup_res = await session.execute(
        select(Permission).where(
            Permission.organization_id == organization_id,
            Permission.agent_id == data.agent_id,
            Permission.tool_id == data.tool_id,
            Permission.operation_id == data.operation_id,
            Permission.environment == data.environment.value,
            Permission.effect == data.effect.value,
        )
    )
    if dup_res.scalar_one_or_none() is not None:
        raise DuplicatePermissionError(
            f"Permission with effect '{data.effect.value}' already exists for this agent, tool, operation, and environment"
        )

    permission = Permission(
        organization_id=organization_id,
        agent_id=data.agent_id,
        tool_id=data.tool_id,
        operation_id=data.operation_id,
        environment=data.environment.value,
        effect=data.effect.value,
        status=PermissionStatus.active.value,
        expires_at=data.expires_at,
    )
    session.add(permission)
    await session.flush()
    await session.refresh(permission)

    from app.audit.service import record_security_event, AuditEventType, AuditOutcome
    await record_security_event(
        session=session,
        event_type=AuditEventType.PERMISSION_CREATED,
        action="CREATE_PERMISSION",
        organization_id=organization_id,
        resource_type="PERMISSION",
        resource_id=permission.id,
        outcome=AuditOutcome.SUCCESS,
        metadata={
            "agent_id": str(data.agent_id),
            "tool_id": str(data.tool_id),
            "operation_id": str(data.operation_id),
            "effect": data.effect.value,
            "environment": data.environment.value,
        },
    )

    return permission


async def get_permission(
    session: AsyncSession, organization_id: uuid.UUID, permission_id: uuid.UUID
) -> Optional[Permission]:
    """Retrieve a single permission grant scoped to the organization."""
    query = select(Permission).where(
        Permission.organization_id == organization_id,
        Permission.id == permission_id,
    )
    res = await session.execute(query)
    return res.scalar_one_or_none()


async def list_permissions(
    session: AsyncSession,
    organization_id: uuid.UUID,
    agent_id: Optional[uuid.UUID] = None,
    tool_id: Optional[uuid.UUID] = None,
) -> List[Permission]:
    """List permission grants scoped to an organization with optional filters."""
    query = select(Permission).where(Permission.organization_id == organization_id)
    if agent_id:
        query = query.where(Permission.agent_id == agent_id)
    if tool_id:
        query = query.where(Permission.tool_id == tool_id)
    query = query.order_by(Permission.created_at.desc())
    res = await session.execute(query)
    return list(res.scalars().all())


async def update_permission(
    session: AsyncSession,
    organization_id: uuid.UUID,
    permission_id: uuid.UUID,
    data: PermissionUpdate,
) -> Permission:
    """Update permission attributes (such as expiration) without altering status."""
    perm = await get_permission(session, organization_id, permission_id)
    if perm is None:
        raise PermissionNotFoundError(organization_id, permission_id)

    if perm.status == PermissionStatus.revoked.value:
        raise InvalidLifecycleTransitionError("Cannot update configuration of a revoked permission")

    if data.expires_at is not None:
        perm.expires_at = data.expires_at

    session.add(perm)
    await session.flush()
    await session.refresh(perm)
    return perm


async def suspend_permission(
    session: AsyncSession, organization_id: uuid.UUID, permission_id: uuid.UUID
) -> Permission:
    """Suspend an active permission grant."""
    perm = await get_permission(session, organization_id, permission_id)
    if perm is None:
        raise PermissionNotFoundError(organization_id, permission_id)

    if perm.status == PermissionStatus.revoked.value:
        raise InvalidLifecycleTransitionError("Cannot suspend a revoked permission")

    if perm.status != PermissionStatus.suspended.value:
        perm.status = PermissionStatus.suspended.value
        session.add(perm)
        await session.flush()
        await session.refresh(perm)

    return perm


async def revoke_permission(
    session: AsyncSession, organization_id: uuid.UUID, permission_id: uuid.UUID
) -> Permission:
    """Permanently revoke a permission grant."""
    perm = await get_permission(session, organization_id, permission_id)
    if perm is None:
        raise PermissionNotFoundError(organization_id, permission_id)

    if perm.status != PermissionStatus.revoked.value:
        perm.status = PermissionStatus.revoked.value
        session.add(perm)
        await session.flush()
        await session.refresh(perm)

    return perm


async def evaluate_permission(
    session: AsyncSession,
    organization_id: uuid.UUID,
    data: PermissionEvaluationRequest,
) -> PermissionEvaluationResult:
    """Delegate authorization request to the Permission Engine."""
    req = PermissionRequest(
        organization_id=organization_id,
        agent_id=data.agent_id,
        tool_id=data.tool_id,
        operation_id=data.operation_id,
        environment=data.environment.value,
    )
    return await PermissionEngine.evaluate(session, req)
