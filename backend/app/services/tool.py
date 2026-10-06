"""Service layer for Tool registry and lifecycle operations."""

import uuid
from typing import List, Optional
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.organization import Organization, OrganizationStatus
from app.db.models.tool import Tool, ToolStatus
from app.schemas.organization import slugify
from app.schemas.tool import ToolCreate, ToolUpdate
from app.services.agent import InvalidLifecycleTransitionError, OrganizationNotFoundError, OrganizationSuspendedError


class ToolNotFoundError(Exception):
    """Raised when a tool is not found within the scoped organization context."""
    def __init__(self, org_id: uuid.UUID, tool_id: uuid.UUID):
        super().__init__(f"Tool '{tool_id}' not found in organization '{org_id}'")
        self.org_id = org_id
        self.tool_id = tool_id


class ToolSlugAlreadyExistsError(Exception):
    """Raised when a tool slug is already registered in the organization."""
    def __init__(self, org_id: uuid.UUID, slug: str):
        super().__init__(f"Tool with slug '{slug}' already exists in organization '{org_id}'")
        self.org_id = org_id
        self.slug = slug


async def create_tool(
    session: AsyncSession, organization_id: uuid.UUID, data: ToolCreate
) -> Tool:
    """Register a new external capability tool under an active organization."""
    # 1. Validate organization exists and is active
    org_query = select(Organization).where(Organization.id == organization_id)
    org_res = await session.execute(org_query)
    org = org_res.scalar_one_or_none()
    if org is None:
        raise OrganizationNotFoundError(organization_id)
    if org.status == OrganizationStatus.suspended.value:
        raise OrganizationSuspendedError(organization_id)

    # 2. Slug generation and uniqueness check within organization
    slug = data.slug or slugify(data.name)
    if not slug:
        slug = f"tool-{uuid.uuid4().hex[:8]}"

    existing_res = await session.execute(
        select(Tool).where(
            Tool.organization_id == organization_id,
            Tool.slug == slug,
        )
    )
    if existing_res.scalar_one_or_none() is not None:
        raise ToolSlugAlreadyExistsError(organization_id, slug)

    tool = Tool(
        organization_id=organization_id,
        name=data.name,
        slug=slug,
        description=data.description,
        tool_type=data.tool_type.value,
        status=ToolStatus.active.value,
        environment=data.environment.value,
        endpoint=data.endpoint,
    )
    session.add(tool)
    await session.flush()
    await session.refresh(tool)
    return tool


async def get_tool(
    session: AsyncSession, organization_id: uuid.UUID, tool_id: uuid.UUID
) -> Optional[Tool]:
    """Retrieve a tool scoped strictly to the specified organization."""
    query = select(Tool).where(
        Tool.organization_id == organization_id,
        Tool.id == tool_id,
    )
    res = await session.execute(query)
    return res.scalar_one_or_none()


async def list_tools(
    session: AsyncSession,
    organization_id: uuid.UUID,
    limit: Optional[int] = None,
    offset: Optional[int] = None,
) -> List[Tool]:
    """List all tools scoped strictly to the specified organization."""
    org_query = select(Organization).where(Organization.id == organization_id)
    org_res = await session.execute(org_query)
    if org_res.scalar_one_or_none() is None:
        raise OrganizationNotFoundError(organization_id)

    query = (
        select(Tool)
        .where(Tool.organization_id == organization_id)
        .order_by(Tool.created_at.desc())
    )
    if offset is not None:
        query = query.offset(offset)
    if limit is not None:
        query = query.limit(limit)
    res = await session.execute(query)
    return list(res.scalars().all())


async def update_tool(
    session: AsyncSession,
    organization_id: uuid.UUID,
    tool_id: uuid.UUID,
    data: ToolUpdate,
) -> Tool:
    """Update tool configuration details without changing its lifecycle status."""
    tool = await get_tool(session, organization_id, tool_id)
    if tool is None:
        raise ToolNotFoundError(organization_id, tool_id)

    if tool.status == ToolStatus.revoked.value:
        raise InvalidLifecycleTransitionError("Cannot update configuration of a revoked tool")

    if data.name is not None:
        tool.name = data.name
    if data.description is not None:
        tool.description = data.description
    if data.tool_type is not None:
        tool.tool_type = data.tool_type.value
    if data.environment is not None:
        tool.environment = data.environment.value
    if data.endpoint is not None:
        tool.endpoint = data.endpoint

    session.add(tool)
    await session.flush()
    await session.refresh(tool)
    return tool


async def suspend_tool(
    session: AsyncSession, organization_id: uuid.UUID, tool_id: uuid.UUID
) -> Tool:
    """Suspend an active tool, blocking it from future runtime authorization."""
    tool = await get_tool(session, organization_id, tool_id)
    if tool is None:
        raise ToolNotFoundError(organization_id, tool_id)

    if tool.status == ToolStatus.revoked.value:
        raise InvalidLifecycleTransitionError("Cannot suspend a revoked tool")

    if tool.status != ToolStatus.suspended.value:
        tool.status = ToolStatus.suspended.value
        session.add(tool)
        await session.flush()
        await session.refresh(tool)

    return tool


async def revoke_tool(
    session: AsyncSession, organization_id: uuid.UUID, tool_id: uuid.UUID
) -> Tool:
    """Permanently revoke a tool capability. Revocation is terminal."""
    tool = await get_tool(session, organization_id, tool_id)
    if tool is None:
        raise ToolNotFoundError(organization_id, tool_id)

    if tool.status != ToolStatus.revoked.value:
        tool.status = ToolStatus.revoked.value
        session.add(tool)
        await session.flush()
        await session.refresh(tool)

    return tool


async def reactivate_tool(
    session: AsyncSession, organization_id: uuid.UUID, tool_id: uuid.UUID
) -> Tool:
    """Reactivate a suspended tool. Terminal revoked tools cannot be reactivated."""
    tool = await get_tool(session, organization_id, tool_id)
    if tool is None:
        raise ToolNotFoundError(organization_id, tool_id)

    if tool.status == ToolStatus.revoked.value:
        raise InvalidLifecycleTransitionError("Cannot reactivate a permanently revoked tool")

    if tool.status == ToolStatus.suspended.value:
        tool.status = ToolStatus.active.value
        session.add(tool)
        await session.flush()
        await session.refresh(tool)

    return tool
