"""Service layer for Agent Identity and Registry operations."""

import uuid
from typing import List, Optional
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.agent import Agent, AgentStatus
from app.db.models.organization import Organization, OrganizationStatus
from app.schemas.agent import AgentCreate, AgentUpdate
from app.schemas.organization import slugify


class OrganizationNotFoundError(Exception):
    """Raised when an organization does not exist."""
    def __init__(self, org_id: uuid.UUID):
        super().__init__(f"Organization '{org_id}' not found")
        self.org_id = org_id


class OrganizationSuspendedError(Exception):
    """Raised when attempting to create an agent inside a suspended organization."""
    def __init__(self, org_id: uuid.UUID):
        super().__init__(f"Cannot create agent in suspended organization '{org_id}'")
        self.org_id = org_id


class AgentNotFoundError(Exception):
    """Raised when an agent is not found within the tenant organization context."""
    def __init__(self, org_id: uuid.UUID, agent_id: uuid.UUID):
        super().__init__(f"Agent '{agent_id}' not found in organization '{org_id}'")
        self.org_id = org_id
        self.agent_id = agent_id


class AgentSlugAlreadyExistsError(Exception):
    """Raised when an agent slug is already in use within the same organization."""
    def __init__(self, org_id: uuid.UUID, slug: str):
        super().__init__(f"Agent with slug '{slug}' already exists in organization '{org_id}'")
        self.org_id = org_id
        self.slug = slug


class InvalidLifecycleTransitionError(Exception):
    """Raised when an illegal lifecycle transition is requested (e.g. modifying a revoked agent)."""
    def __init__(self, message: str):
        super().__init__(message)


async def create_agent(
    session: AsyncSession, organization_id: uuid.UUID, data: AgentCreate
) -> Agent:
    """Register a new Agent entity strictly bound to an active Organization."""
    # 1. Validate organization existence
    org_query = select(Organization).where(Organization.id == organization_id)
    org_res = await session.execute(org_query)
    org = org_res.scalar_one_or_none()
    if org is None:
        raise OrganizationNotFoundError(organization_id)

    # 2. Validate organization status
    if org.status == OrganizationStatus.suspended.value:
        raise OrganizationSuspendedError(organization_id)

    # 3. Deterministic slug generation
    slug = data.slug or slugify(data.name)
    if not slug:
        slug = f"agent-{uuid.uuid4().hex[:8]}"

    # 4. Check composite uniqueness: (organization_id, slug)
    existing_query = select(Agent).where(
        Agent.organization_id == organization_id,
        Agent.slug == slug,
    )
    existing_res = await session.execute(existing_query)
    if existing_res.scalar_one_or_none() is not None:
        raise AgentSlugAlreadyExistsError(organization_id, slug)

    # 5. Create authoritative agent identity
    agent = Agent(
        organization_id=organization_id,
        name=data.name,
        slug=slug,
        description=data.description,
        agent_type=data.agent_type.value,
        status=AgentStatus.active.value,
        environment=data.environment.value,
        last_seen_at=None,
    )
    session.add(agent)
    await session.flush()
    await session.refresh(agent)
    return agent


async def get_agent(
    session: AsyncSession, organization_id: uuid.UUID, agent_id: uuid.UUID
) -> Optional[Agent]:
    """Retrieve an agent strictly isolated within the specified organization."""
    query = select(Agent).where(
        Agent.organization_id == organization_id,
        Agent.id == agent_id,
    )
    res = await session.execute(query)
    return res.scalar_one_or_none()


async def list_agents(
    session: AsyncSession,
    organization_id: uuid.UUID,
    limit: Optional[int] = None,
    offset: Optional[int] = None,
) -> List[Agent]:
    """List all agents scoped strictly to the specified organization."""
    # Verify organization exists
    org_query = select(Organization).where(Organization.id == organization_id)
    org_res = await session.execute(org_query)
    if org_res.scalar_one_or_none() is None:
        raise OrganizationNotFoundError(organization_id)

    query = (
        select(Agent)
        .where(Agent.organization_id == organization_id)
        .order_by(Agent.created_at.desc())
    )
    if offset is not None:
        query = query.offset(offset)
    if limit is not None:
        query = query.limit(limit)
    res = await session.execute(query)
    return list(res.scalars().all())


async def update_agent(
    session: AsyncSession,
    organization_id: uuid.UUID,
    agent_id: uuid.UUID,
    data: AgentUpdate,
) -> Agent:
    """Update configuration attributes of an agent without changing its lifecycle status."""
    agent = await get_agent(session, organization_id, agent_id)
    if agent is None:
        raise AgentNotFoundError(organization_id, agent_id)

    if agent.status == AgentStatus.revoked.value:
        raise InvalidLifecycleTransitionError("Cannot update configuration of a revoked agent")

    if data.name is not None:
        agent.name = data.name
    if data.description is not None:
        agent.description = data.description
    if data.agent_type is not None:
        agent.agent_type = data.agent_type.value
    if data.environment is not None:
        agent.environment = data.environment.value

    session.add(agent)
    await session.flush()
    await session.refresh(agent)
    return agent


async def suspend_agent(
    session: AsyncSession, organization_id: uuid.UUID, agent_id: uuid.UUID
) -> Agent:
    """Suspend an active agent, preventing it from performing future runtime actions."""
    agent = await get_agent(session, organization_id, agent_id)
    if agent is None:
        raise AgentNotFoundError(organization_id, agent_id)

    if agent.status == AgentStatus.revoked.value:
        raise InvalidLifecycleTransitionError("Cannot suspend a revoked agent")

    if agent.status != AgentStatus.suspended.value:
        agent.status = AgentStatus.suspended.value
        session.add(agent)
        await session.flush()
        await session.refresh(agent)

    return agent


async def revoke_agent(
    session: AsyncSession, organization_id: uuid.UUID, agent_id: uuid.UUID
) -> Agent:
    """Permanently revoke an agent. Revocation is a terminal state."""
    agent = await get_agent(session, organization_id, agent_id)
    if agent is None:
        raise AgentNotFoundError(organization_id, agent_id)

    if agent.status != AgentStatus.revoked.value:
        agent.status = AgentStatus.revoked.value
        session.add(agent)
        await session.flush()
        await session.refresh(agent)

    return agent


async def reactivate_agent(
    session: AsyncSession, organization_id: uuid.UUID, agent_id: uuid.UUID
) -> Agent:
    """Reactivate a suspended agent. Terminal revoked agents cannot be reactivated."""
    agent = await get_agent(session, organization_id, agent_id)
    if agent is None:
        raise AgentNotFoundError(organization_id, agent_id)

    if agent.status == AgentStatus.revoked.value:
        raise InvalidLifecycleTransitionError("Cannot reactivate a permanently revoked agent")

    if agent.status == AgentStatus.suspended.value:
        agent.status = AgentStatus.active.value
        session.add(agent)
        await session.flush()
        await session.refresh(agent)

    return agent
