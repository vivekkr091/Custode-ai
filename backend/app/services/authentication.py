"""Authentication service for validating agent API credentials and resolving tenant identity."""

from typing import Optional
from fastapi import Depends, Header, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import extract_prefix_from_key, verify_api_key
from app.db.base import utc_now
from app.db.models.agent import Agent, AgentStatus
from app.db.models.agent_credential import AgentCredential, CredentialStatus
from app.db.models.organization import Organization, OrganizationStatus
from app.db.session import get_db_session
from app.schemas.agent_credential import AuthenticatedAgent


class AuthenticationError(Exception):
    """Raised when agent authentication fails."""
    def __init__(self, message: str = "Invalid authentication credentials"):
        super().__init__(message)


async def authenticate_agent_token(
    session: AsyncSession, raw_token: str
) -> AuthenticatedAgent:
    """Cryptographically verify an agent API key and resolve its authoritative identity."""
    # 1. Extract prefix for indexed O(1) lookup
    prefix = extract_prefix_from_key(raw_token)
    if not prefix:
        raise AuthenticationError("Invalid authentication credentials")

    # 2. Look up credential record
    cred_query = select(AgentCredential).where(
        AgentCredential.credential_prefix == prefix
    )
    cred_res = await session.execute(cred_query)
    credential = cred_res.scalar_one_or_none()
    if credential is None:
        raise AuthenticationError("Invalid authentication credentials")

    # 3. Constant-time cryptographic verification against PBKDF2 hash
    if not verify_api_key(raw_token, credential.credential_hash):
        raise AuthenticationError("Invalid authentication credentials")

    # 4. Check credential lifecycle status
    if credential.status == CredentialStatus.revoked.value:
        raise AuthenticationError("Credential has been revoked")

    if credential.status == CredentialStatus.expired.value:
        raise AuthenticationError("Credential has expired")

    # 5. Check credential expiration timestamp
    now = utc_now()
    if credential.expires_at is not None:
        expires_at = credential.expires_at
        if expires_at.tzinfo is None:
            from datetime import timezone
            expires_at = expires_at.replace(tzinfo=timezone.utc)
        if now > expires_at:
            credential.status = CredentialStatus.expired.value
            session.add(credential)
            await session.flush()
            raise AuthenticationError("Credential has expired")

    # 6. Load agent and verify status
    agent_query = select(Agent).where(Agent.id == credential.agent_id)
    agent_res = await session.execute(agent_query)
    agent = agent_res.scalar_one_or_none()
    if agent is None:
        raise AuthenticationError("Agent identity unavailable")

    if agent.status == AgentStatus.suspended.value:
        raise AuthenticationError("Agent is suspended")
    if agent.status == AgentStatus.revoked.value:
        raise AuthenticationError("Agent is revoked")
    if agent.status != AgentStatus.active.value:
        raise AuthenticationError("Agent is not active")

    # 7. Load organization and verify status
    org_query = select(Organization).where(Organization.id == agent.organization_id)
    org_res = await session.execute(org_query)
    org = org_res.scalar_one_or_none()
    if org is None or org.status != OrganizationStatus.active.value:
        raise AuthenticationError("Organization is not active")

    # 8. Record credential usage timestamp
    credential.last_used_at = now
    session.add(credential)
    await session.flush()

    return AuthenticatedAgent(
        organization_id=agent.organization_id,
        agent_id=agent.id,
        credential_id=credential.id,
    )


async def get_authenticated_agent(
    authorization: Optional[str] = Header(None, alias="Authorization"),
    session: AsyncSession = Depends(get_db_session),
) -> AuthenticatedAgent:
    """FastAPI dependency that extracts and validates the Bearer token."""
    if not authorization:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing Authorization header",
            headers={"WWW-Authenticate": "Bearer"},
        )

    parts = authorization.strip().split(" ", 1)
    if len(parts) != 2 or parts[0].lower() != "bearer":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Malformed Authorization header. Format: Bearer <agent-api-key>",
            headers={"WWW-Authenticate": "Bearer"},
        )

    raw_token = parts[1].strip()
    try:
        authenticated_agent = await authenticate_agent_token(session, raw_token)
        return authenticated_agent
    except AuthenticationError as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=str(e),
            headers={"WWW-Authenticate": "Bearer"},
        )
