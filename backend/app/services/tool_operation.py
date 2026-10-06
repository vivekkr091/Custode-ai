"""Service layer for ToolOperation management and lifecycle controls."""

import uuid
from typing import List, Optional
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.tool import Tool, ToolStatus
from app.db.models.tool_operation import OperationStatus, ToolOperation
from app.schemas.organization import slugify
from app.schemas.tool_operation import ToolOperationCreate, ToolOperationUpdate
from app.services.agent import InvalidLifecycleTransitionError
from app.services.tool import ToolNotFoundError


class OperationNotFoundError(Exception):
    """Raised when an operation is not found under the specified tool."""
    def __init__(self, tool_id: uuid.UUID, operation_id: uuid.UUID):
        super().__init__(f"Operation '{operation_id}' not found under tool '{tool_id}'")
        self.tool_id = tool_id
        self.operation_id = operation_id


class OperationSlugAlreadyExistsError(Exception):
    """Raised when an operation slug already exists under the same tool."""
    def __init__(self, tool_id: uuid.UUID, slug: str):
        super().__init__(f"Operation with slug '{slug}' already exists under tool '{tool_id}'")
        self.tool_id = tool_id
        self.slug = slug


class ToolNotActiveError(Exception):
    """Raised when attempting to add operations to a non-active tool."""
    def __init__(self, tool_id: uuid.UUID, status: str):
        super().__init__(f"Cannot add operations to tool '{tool_id}' in state '{status}'")
        self.tool_id = tool_id
        self.status = status


async def create_operation(
    session: AsyncSession,
    organization_id: uuid.UUID,
    tool_id: uuid.UUID,
    data: ToolOperationCreate,
) -> ToolOperation:
    """Create a new operation belonging strictly to a specified tool within an organization."""
    # 1. Validate parent tool exists within tenant organization
    tool_res = await session.execute(
        select(Tool).where(
            Tool.id == tool_id,
            Tool.organization_id == organization_id,
        )
    )
    tool = tool_res.scalar_one_or_none()
    if tool is None:
        raise ToolNotFoundError(organization_id, tool_id)

    if tool.status != ToolStatus.active.value:
        raise ToolNotActiveError(tool_id, tool.status)

    # 2. Slug generation and uniqueness within the tool
    slug = data.slug or slugify(data.name)
    if not slug:
        slug = f"op-{uuid.uuid4().hex[:8]}"

    existing_res = await session.execute(
        select(ToolOperation).where(
            ToolOperation.tool_id == tool_id,
            ToolOperation.slug == slug,
        )
    )
    if existing_res.scalar_one_or_none() is not None:
        raise OperationSlugAlreadyExistsError(tool_id, slug)

    operation = ToolOperation(
        tool_id=tool_id,
        name=data.name,
        slug=slug,
        description=data.description,
        operation_type=data.operation_type.value,
        risk_level=data.risk_level.value,
        status=OperationStatus.active.value,
    )
    session.add(operation)
    await session.flush()
    await session.refresh(operation)
    return operation


async def get_operation(
    session: AsyncSession,
    organization_id: uuid.UUID,
    tool_id: uuid.UUID,
    operation_id: uuid.UUID,
) -> Optional[ToolOperation]:
    """Retrieve an operation validating full hierarchy: organization -> tool -> operation."""
    # Verify tool belongs to organization
    tool_res = await session.execute(
        select(Tool).where(
            Tool.id == tool_id,
            Tool.organization_id == organization_id,
        )
    )
    if tool_res.scalar_one_or_none() is None:
        raise ToolNotFoundError(organization_id, tool_id)

    query = select(ToolOperation).where(
        ToolOperation.id == operation_id,
        ToolOperation.tool_id == tool_id,
    )
    res = await session.execute(query)
    return res.scalar_one_or_none()


async def list_operations(
    session: AsyncSession,
    organization_id: uuid.UUID,
    tool_id: uuid.UUID,
) -> List[ToolOperation]:
    """List all operations scoped to a parent tool within an organization."""
    # Verify tool belongs to organization
    tool_res = await session.execute(
        select(Tool).where(
            Tool.id == tool_id,
            Tool.organization_id == organization_id,
        )
    )
    if tool_res.scalar_one_or_none() is None:
        raise ToolNotFoundError(organization_id, tool_id)

    query = (
        select(ToolOperation)
        .where(ToolOperation.tool_id == tool_id)
        .order_by(ToolOperation.created_at.desc())
    )
    res = await session.execute(query)
    return list(res.scalars().all())


async def update_operation(
    session: AsyncSession,
    organization_id: uuid.UUID,
    tool_id: uuid.UUID,
    operation_id: uuid.UUID,
    data: ToolOperationUpdate,
) -> ToolOperation:
    """Update operation attributes without changing its lifecycle status."""
    operation = await get_operation(session, organization_id, tool_id, operation_id)
    if operation is None:
        raise OperationNotFoundError(tool_id, operation_id)

    if operation.status == OperationStatus.revoked.value:
        raise InvalidLifecycleTransitionError("Cannot update configuration of a revoked operation")

    if data.name is not None:
        operation.name = data.name
    if data.description is not None:
        operation.description = data.description
    if data.operation_type is not None:
        operation.operation_type = data.operation_type.value
    if data.risk_level is not None:
        operation.risk_level = data.risk_level.value

    session.add(operation)
    await session.flush()
    await session.refresh(operation)
    return operation


async def suspend_operation(
    session: AsyncSession,
    organization_id: uuid.UUID,
    tool_id: uuid.UUID,
    operation_id: uuid.UUID,
) -> ToolOperation:
    """Suspend an active operation."""
    operation = await get_operation(session, organization_id, tool_id, operation_id)
    if operation is None:
        raise OperationNotFoundError(tool_id, operation_id)

    if operation.status == OperationStatus.revoked.value:
        raise InvalidLifecycleTransitionError("Cannot suspend a revoked operation")

    if operation.status != OperationStatus.suspended.value:
        operation.status = OperationStatus.suspended.value
        session.add(operation)
        await session.flush()
        await session.refresh(operation)

    return operation


async def revoke_operation(
    session: AsyncSession,
    organization_id: uuid.UUID,
    tool_id: uuid.UUID,
    operation_id: uuid.UUID,
) -> ToolOperation:
    """Permanently revoke an operation. Revocation is terminal."""
    operation = await get_operation(session, organization_id, tool_id, operation_id)
    if operation is None:
        raise OperationNotFoundError(tool_id, operation_id)

    if operation.status != OperationStatus.revoked.value:
        operation.status = OperationStatus.revoked.value
        session.add(operation)
        await session.flush()
        await session.refresh(operation)

    return operation


async def reactivate_operation(
    session: AsyncSession,
    organization_id: uuid.UUID,
    tool_id: uuid.UUID,
    operation_id: uuid.UUID,
) -> ToolOperation:
    """Reactivate a suspended operation. Revoked operations cannot be reactivated."""
    operation = await get_operation(session, organization_id, tool_id, operation_id)
    if operation is None:
        raise OperationNotFoundError(tool_id, operation_id)

    if operation.status == OperationStatus.revoked.value:
        raise InvalidLifecycleTransitionError("Cannot reactivate a permanently revoked operation")

    if operation.status == OperationStatus.suspended.value:
        operation.status = OperationStatus.active.value
        session.add(operation)
        await session.flush()
        await session.refresh(operation)

    return operation
