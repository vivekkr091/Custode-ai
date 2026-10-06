"""ToolOperation API endpoints for granular tool action registration and controls."""

import uuid
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db_session
from app.schemas.tool_operation import (
    ToolOperationCreate,
    ToolOperationListResponse,
    ToolOperationResponse,
    ToolOperationUpdate,
)
from app.services.agent import InvalidLifecycleTransitionError
from app.services.tool import ToolNotFoundError
from app.services.tool_operation import (
    OperationNotFoundError,
    OperationSlugAlreadyExistsError,
    ToolNotActiveError,
    create_operation,
    get_operation,
    list_operations,
    revoke_operation,
    suspend_operation,
    update_operation,
)

router = APIRouter(
    prefix="/organizations/{organization_id}/tools/{tool_id}/operations",
    tags=["Tool Operations"],
)


@router.post(
    "",
    response_model=ToolOperationResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Register Tool Operation",
)
async def create_operation_endpoint(
    organization_id: uuid.UUID,
    tool_id: uuid.UUID,
    payload: ToolOperationCreate,
    session: AsyncSession = Depends(get_db_session),
) -> ToolOperationResponse:
    """Register a new callable action under a tool with baseline risk rating."""
    try:
        operation = await create_operation(session, organization_id, tool_id, payload)
        return ToolOperationResponse.model_validate(operation)
    except ToolNotFoundError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except ToolNotActiveError as e:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(e))
    except OperationSlugAlreadyExistsError as e:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(e))


@router.get(
    "",
    response_model=ToolOperationListResponse,
    summary="List Operations for Tool",
)
async def list_operations_endpoint(
    organization_id: uuid.UUID,
    tool_id: uuid.UUID,
    session: AsyncSession = Depends(get_db_session),
) -> ToolOperationListResponse:
    """List all operations configured under a specific tool."""
    try:
        operations = await list_operations(session, organization_id, tool_id)
        items = [ToolOperationResponse.model_validate(op) for op in operations]
        return ToolOperationListResponse(items=items, total=len(items))
    except ToolNotFoundError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))


@router.get(
    "/{operation_id}",
    response_model=ToolOperationResponse,
    summary="Retrieve Tool Operation",
)
async def get_operation_endpoint(
    organization_id: uuid.UUID,
    tool_id: uuid.UUID,
    operation_id: uuid.UUID,
    session: AsyncSession = Depends(get_db_session),
) -> ToolOperationResponse:
    """Retrieve operation details scoped strictly through organization and tool."""
    try:
        operation = await get_operation(session, organization_id, tool_id, operation_id)
        if operation is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Operation '{operation_id}' not found under tool '{tool_id}'",
            )
        return ToolOperationResponse.model_validate(operation)
    except ToolNotFoundError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))


@router.patch(
    "/{operation_id}",
    response_model=ToolOperationResponse,
    summary="Update Tool Operation",
)
async def update_operation_endpoint(
    organization_id: uuid.UUID,
    tool_id: uuid.UUID,
    operation_id: uuid.UUID,
    payload: ToolOperationUpdate,
    session: AsyncSession = Depends(get_db_session),
) -> ToolOperationResponse:
    """Update operation attributes without changing its lifecycle status."""
    try:
        operation = await update_operation(
            session, organization_id, tool_id, operation_id, payload
        )
        return ToolOperationResponse.model_validate(operation)
    except ToolNotFoundError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except OperationNotFoundError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except InvalidLifecycleTransitionError as e:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(e))


@router.post(
    "/{operation_id}/suspend",
    response_model=ToolOperationResponse,
    summary="Suspend Tool Operation",
)
async def suspend_operation_endpoint(
    organization_id: uuid.UUID,
    tool_id: uuid.UUID,
    operation_id: uuid.UUID,
    session: AsyncSession = Depends(get_db_session),
) -> ToolOperationResponse:
    """Suspend an active tool operation."""
    try:
        operation = await suspend_operation(session, organization_id, tool_id, operation_id)
        return ToolOperationResponse.model_validate(operation)
    except ToolNotFoundError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except OperationNotFoundError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except InvalidLifecycleTransitionError as e:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(e))


@router.post(
    "/{operation_id}/revoke",
    response_model=ToolOperationResponse,
    summary="Revoke Tool Operation",
)
async def revoke_operation_endpoint(
    organization_id: uuid.UUID,
    tool_id: uuid.UUID,
    operation_id: uuid.UUID,
    session: AsyncSession = Depends(get_db_session),
) -> ToolOperationResponse:
    """Permanently revoke an operation. Revocation is a terminal state."""
    try:
        operation = await revoke_operation(session, organization_id, tool_id, operation_id)
        return ToolOperationResponse.model_validate(operation)
    except ToolNotFoundError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except OperationNotFoundError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
