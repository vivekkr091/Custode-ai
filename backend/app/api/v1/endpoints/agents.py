"""Agent Identity and Registry API endpoints."""

import uuid
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db_session
from app.schemas.agent import AgentCreate, AgentListResponse, AgentResponse, AgentUpdate
from app.services.agent import (
    AgentNotFoundError,
    AgentSlugAlreadyExistsError,
    InvalidLifecycleTransitionError,
    OrganizationNotFoundError,
    OrganizationSuspendedError,
    create_agent,
    get_agent,
    list_agents,
    revoke_agent,
    suspend_agent,
    update_agent,
)

router = APIRouter(
    prefix="/organizations/{organization_id}/agents",
    tags=["Agents"],
)


@router.post(
    "",
    response_model=AgentResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Register Agent Identity",
)
async def create_agent_endpoint(
    organization_id: uuid.UUID,
    payload: AgentCreate,
    session: AsyncSession = Depends(get_db_session),
) -> AgentResponse:
    """Register a new first-class Agent identity within an organization."""
    try:
        agent = await create_agent(session, organization_id, payload)
        return AgentResponse.model_validate(agent)
    except OrganizationNotFoundError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e),
        )
    except OrganizationSuspendedError as e:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(e),
        )
    except AgentSlugAlreadyExistsError as e:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(e),
        )


@router.get(
    "",
    response_model=AgentListResponse,
    summary="List Agents for Organization",
)
async def list_agents_endpoint(
    organization_id: uuid.UUID,
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0),
    session: AsyncSession = Depends(get_db_session),
) -> AgentListResponse:
    """List all agents scoped strictly to the specified organization."""
    try:
        agents = await list_agents(session, organization_id, limit=limit, offset=offset)
        items = [AgentResponse.model_validate(a) for a in agents]
        return AgentListResponse(items=items, total=len(items))
    except OrganizationNotFoundError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e),
        )


@router.get(
    "/{agent_id}",
    response_model=AgentResponse,
    summary="Retrieve Agent Identity",
)
async def get_agent_endpoint(
    organization_id: uuid.UUID,
    agent_id: uuid.UUID,
    session: AsyncSession = Depends(get_db_session),
) -> AgentResponse:
    """Retrieve an authoritative agent identity scoped to the organization."""
    agent = await get_agent(session, organization_id, agent_id)
    if agent is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Agent '{agent_id}' not found in organization '{organization_id}'",
        )
    return AgentResponse.model_validate(agent)


@router.patch(
    "/{agent_id}",
    response_model=AgentResponse,
    summary="Update Agent Configuration",
)
async def update_agent_endpoint(
    organization_id: uuid.UUID,
    agent_id: uuid.UUID,
    payload: AgentUpdate,
    session: AsyncSession = Depends(get_db_session),
) -> AgentResponse:
    """Update configuration attributes of an agent without altering lifecycle state."""
    try:
        agent = await update_agent(session, organization_id, agent_id, payload)
        return AgentResponse.model_validate(agent)
    except AgentNotFoundError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e),
        )
    except InvalidLifecycleTransitionError as e:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(e),
        )


@router.post(
    "/{agent_id}/suspend",
    response_model=AgentResponse,
    summary="Suspend Agent",
)
async def suspend_agent_endpoint(
    organization_id: uuid.UUID,
    agent_id: uuid.UUID,
    session: AsyncSession = Depends(get_db_session),
) -> AgentResponse:
    """Suspend an active agent to block runtime operations."""
    try:
        agent = await suspend_agent(session, organization_id, agent_id)
        return AgentResponse.model_validate(agent)
    except AgentNotFoundError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e),
        )
    except InvalidLifecycleTransitionError as e:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(e),
        )


@router.post(
    "/{agent_id}/revoke",
    response_model=AgentResponse,
    summary="Revoke Agent Identity",
)
async def revoke_agent_endpoint(
    organization_id: uuid.UUID,
    agent_id: uuid.UUID,
    session: AsyncSession = Depends(get_db_session),
) -> AgentResponse:
    """Permanently revoke an agent identity. Terminal state."""
    try:
        agent = await revoke_agent(session, organization_id, agent_id)
        return AgentResponse.model_validate(agent)
    except AgentNotFoundError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e),
        )
