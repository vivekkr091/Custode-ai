"""Tool API endpoints for capability registry and lifecycle management."""

import uuid
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db_session
from app.schemas.tool import ToolCreate, ToolListResponse, ToolResponse, ToolUpdate
from app.services.agent import InvalidLifecycleTransitionError, OrganizationNotFoundError, OrganizationSuspendedError
from app.services.tool import (
    ToolNotFoundError,
    ToolSlugAlreadyExistsError,
    create_tool,
    get_tool,
    list_tools,
    revoke_tool,
    suspend_tool,
    update_tool,
)

router = APIRouter(
    prefix="/organizations/{organization_id}/tools",
    tags=["Tools"],
)


@router.post(
    "",
    response_model=ToolResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Register Tool Capability",
)
async def create_tool_endpoint(
    organization_id: uuid.UUID,
    payload: ToolCreate,
    session: AsyncSession = Depends(get_db_session),
) -> ToolResponse:
    """Register an external capability tool within an organization."""
    try:
        tool = await create_tool(session, organization_id, payload)
        return ToolResponse.model_validate(tool)
    except OrganizationNotFoundError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except OrganizationSuspendedError as e:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(e))
    except ToolSlugAlreadyExistsError as e:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(e))


@router.get(
    "",
    response_model=ToolListResponse,
    summary="List Tools in Organization",
)
async def list_tools_endpoint(
    organization_id: uuid.UUID,
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0),
    session: AsyncSession = Depends(get_db_session),
) -> ToolListResponse:
    """List all registered tools scoped strictly to the specified organization."""
    try:
        tools = await list_tools(session, organization_id, limit=limit, offset=offset)
        items = [ToolResponse.model_validate(t) for t in tools]
        return ToolListResponse(items=items, total=len(items))
    except OrganizationNotFoundError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))


@router.get(
    "/{tool_id}",
    response_model=ToolResponse,
    summary="Retrieve Tool Capability",
)
async def get_tool_endpoint(
    organization_id: uuid.UUID,
    tool_id: uuid.UUID,
    session: AsyncSession = Depends(get_db_session),
) -> ToolResponse:
    """Retrieve an authoritative tool identity scoped strictly to the organization."""
    tool = await get_tool(session, organization_id, tool_id)
    if tool is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Tool '{tool_id}' not found in organization '{organization_id}'",
        )
    return ToolResponse.model_validate(tool)


@router.patch(
    "/{tool_id}",
    response_model=ToolResponse,
    summary="Update Tool Configuration",
)
async def update_tool_endpoint(
    organization_id: uuid.UUID,
    tool_id: uuid.UUID,
    payload: ToolUpdate,
    session: AsyncSession = Depends(get_db_session),
) -> ToolResponse:
    """Update configuration attributes of a tool without altering its lifecycle status."""
    try:
        tool = await update_tool(session, organization_id, tool_id, payload)
        return ToolResponse.model_validate(tool)
    except ToolNotFoundError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except InvalidLifecycleTransitionError as e:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(e))


@router.post(
    "/{tool_id}/suspend",
    response_model=ToolResponse,
    summary="Suspend Tool Capability",
)
async def suspend_tool_endpoint(
    organization_id: uuid.UUID,
    tool_id: uuid.UUID,
    session: AsyncSession = Depends(get_db_session),
) -> ToolResponse:
    """Suspend an active tool capability, preventing future runtime actions."""
    try:
        tool = await suspend_tool(session, organization_id, tool_id)
        return ToolResponse.model_validate(tool)
    except ToolNotFoundError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except InvalidLifecycleTransitionError as e:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(e))


@router.post(
    "/{tool_id}/revoke",
    response_model=ToolResponse,
    summary="Revoke Tool Capability",
)
async def revoke_tool_endpoint(
    organization_id: uuid.UUID,
    tool_id: uuid.UUID,
    session: AsyncSession = Depends(get_db_session),
) -> ToolResponse:
    """Permanently revoke a tool capability. Revocation is a terminal state."""
    try:
        tool = await revoke_tool(session, organization_id, tool_id)
        return ToolResponse.model_validate(tool)
    except ToolNotFoundError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
