"""Service functions for Agent Credential lifecycle management."""

import uuid
from datetime import datetime, timezone
from typing import List, Optional, Tuple
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import generate_agent_api_key, hash_api_key
from app.db.base import utc_now
from app.db.models.agent import Agent, AgentStatus
from app.db.models.agent_credential import AgentCredential, CredentialStatus
from app.db.models.organization import Organization, OrganizationStatus
from app.schemas.agent_credential import AgentCredentialCreate
from app.services.agent import AgentNotFoundError, OrganizationNotFoundError, OrganizationSuspendedError


class AgentNotActiveError(Exception):
    """Raised when attempting to issue credentials for a suspended or revoked agent."""
    def __init__(self, agent_id: uuid.UUID, status: str):
        super().__init__(f"Cannot create credentials for agent '{agent_id}' in state '{status}'")
        self.agent_id = agent_id
        self.status = status


class CredentialNotFoundError(Exception):
    """Raised when a credential cannot be found within the scoped agent and organization."""
    def __init__(self, credential_id: uuid.UUID):
        super().__init__(f"Credential '{credential_id}' not found")
        self.credential_id = credential_id


async def create_agent_credential(
    session: AsyncSession,
    organization_id: uuid.UUID,
    agent_id: uuid.UUID,
    data: AgentCredentialCreate,
) -> Tuple[AgentCredential, str]:
    """Create a new agent credential, returning the persistent model and raw API key once."""
    # 1. Validate organization existence and status
    org_res = await session.execute(
        select(Organization).where(Organization.id == organization_id)
    )
    org = org_res.scalar_one_or_none()
    if org is None:
        raise OrganizationNotFoundError(organization_id)
    if org.status == OrganizationStatus.suspended.value:
        raise OrganizationSuspendedError(organization_id)

    # 2. Validate agent existence within tenant organization
    agent_res = await session.execute(
        select(Agent).where(
            Agent.id == agent_id,
            Agent.organization_id == organization_id,
        )
    )
    agent = agent_res.scalar_one_or_none()
    if agent is None:
        raise AgentNotFoundError(organization_id, agent_id)

    if agent.status != AgentStatus.active.value:
        raise AgentNotActiveError(agent_id, agent.status)

    # 3. Generate high-entropy API key and prefix
    raw_api_key, prefix = generate_agent_api_key()
    hashed_key = hash_api_key(raw_api_key)

    credential = AgentCredential(
        agent_id=agent_id,
        name=data.name,
        credential_prefix=prefix,
        credential_hash=hashed_key,
        status=CredentialStatus.active.value,
        expires_at=data.expires_at,
        revoked_at=None,
        last_used_at=None,
    )
    session.add(credential)
    await session.flush()
    await session.refresh(credential)
    return credential, raw_api_key


async def list_agent_credentials(
    session: AsyncSession,
    organization_id: uuid.UUID,
    agent_id: uuid.UUID,
) -> List[AgentCredential]:
    """List metadata for all credentials belonging to an agent within an organization."""
    # Validate agent scoping
    agent_res = await session.execute(
        select(Agent).where(
            Agent.id == agent_id,
            Agent.organization_id == organization_id,
        )
    )
    if agent_res.scalar_one_or_none() is None:
        raise AgentNotFoundError(organization_id, agent_id)

    query = (
        select(AgentCredential)
        .where(AgentCredential.agent_id == agent_id)
        .order_by(AgentCredential.created_at.desc())
    )
    res = await session.execute(query)
    return list(res.scalars().all())


async def revoke_agent_credential(
    session: AsyncSession,
    organization_id: uuid.UUID,
    agent_id: uuid.UUID,
    credential_id: uuid.UUID,
) -> AgentCredential:
    """Revoke an agent credential immediately and permanently."""
    # Validate agent scoping
    agent_res = await session.execute(
        select(Agent).where(
            Agent.id == agent_id,
            Agent.organization_id == organization_id,
        )
    )
    if agent_res.scalar_one_or_none() is None:
        raise AgentNotFoundError(organization_id, agent_id)

    query = select(AgentCredential).where(
        AgentCredential.id == credential_id,
        AgentCredential.agent_id == agent_id,
    )
    res = await session.execute(query)
    cred = res.scalar_one_or_none()
    if cred is None:
        raise CredentialNotFoundError(credential_id)

    if cred.status != CredentialStatus.revoked.value:
        cred.status = CredentialStatus.revoked.value
        cred.revoked_at = utc_now()
        session.add(cred)
        await session.flush()
        await session.refresh(cred)

    return cred
