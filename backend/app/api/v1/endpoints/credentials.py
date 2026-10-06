"""Agent Credential API endpoints for issuing, listing, and revoking API keys."""

import uuid
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db_session
from app.schemas.agent_credential import (
    AgentCredentialCreate,
    AgentCredentialCreatedResponse,
    AgentCredentialListResponse,
    AgentCredentialResponse,
)
from app.services.agent import AgentNotFoundError, OrganizationNotFoundError, OrganizationSuspendedError
from app.services.credential import (
    AgentNotActiveError,
    CredentialNotFoundError,
    create_agent_credential,
    list_agent_credentials,
    revoke_agent_credential,
)

router = APIRouter(
    prefix="/organizations/{organization_id}/agents/{agent_id}/credentials",
    tags=["Agent Credentials"],
)


@router.post(
    "",
    response_model=AgentCredentialCreatedResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Issue Agent Credential",
)
async def create_agent_credential_endpoint(
    organization_id: uuid.UUID,
    agent_id: uuid.UUID,
    payload: AgentCredentialCreate,
    session: AsyncSession = Depends(get_db_session),
) -> AgentCredentialCreatedResponse:
    """Issue a high-entropy API key for an agent. Returns raw secret ONCE upon creation."""
    try:
        credential, raw_key = await create_agent_credential(
            session, organization_id, agent_id, payload
        )
        return AgentCredentialCreatedResponse(
            id=credential.id,
            agent_id=credential.agent_id,
            name=credential.name,
            api_key=raw_key,
            credential_prefix=credential.credential_prefix,
            status=credential.status,
            created_at=credential.created_at,
            expires_at=credential.expires_at,
        )
    except OrganizationNotFoundError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except OrganizationSuspendedError as e:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(e))
    except AgentNotFoundError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except AgentNotActiveError as e:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(e))


@router.get(
    "",
    response_model=AgentCredentialListResponse,
    summary="List Agent Credentials",
)
async def list_agent_credentials_endpoint(
    organization_id: uuid.UUID,
    agent_id: uuid.UUID,
    session: AsyncSession = Depends(get_db_session),
) -> AgentCredentialListResponse:
    """List metadata for all credentials issued to an agent. Never returns secret or hash."""
    try:
        credentials = await list_agent_credentials(session, organization_id, agent_id)
        items = [AgentCredentialResponse.model_validate(c) for c in credentials]
        return AgentCredentialListResponse(items=items, total=len(items))
    except AgentNotFoundError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))


@router.post(
    "/{credential_id}/revoke",
    response_model=AgentCredentialResponse,
    summary="Revoke Agent Credential",
)
async def revoke_agent_credential_endpoint(
    organization_id: uuid.UUID,
    agent_id: uuid.UUID,
    credential_id: uuid.UUID,
    session: AsyncSession = Depends(get_db_session),
) -> AgentCredentialResponse:
    """Permanently revoke an agent credential. Revoked credentials immediately fail authentication."""
    try:
        credential = await revoke_agent_credential(
            session, organization_id, agent_id, credential_id
        )
        return AgentCredentialResponse.model_validate(credential)
    except AgentNotFoundError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except CredentialNotFoundError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
