"""Permission API endpoints for authorization grant management and testing evaluation."""

import uuid
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db_session
from app.schemas.permission import (
    PermissionCreate,
    PermissionEvaluationRequest,
    PermissionEvaluationResponse,
    PermissionListResponse,
    PermissionResponse,
    PermissionUpdate,
)
from app.services.agent import InvalidLifecycleTransitionError, OrganizationNotFoundError, OrganizationSuspendedError
from app.services.permission import (
    DuplicatePermissionError,
    InactiveResourceError,
    PermissionNotFoundError,
    ResourceHierarchyError,
    create_permission,
    evaluate_permission,
    get_permission,
    list_permissions,
    revoke_permission,
    suspend_permission,
    update_permission,
)

router = APIRouter(
    prefix="/organizations/{organization_id}/permissions",
    tags=["Permissions"],
)


@router.post(
    "",
    response_model=PermissionResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create Permission Grant",
)
async def create_permission_endpoint(
    organization_id: uuid.UUID,
    payload: PermissionCreate,
    session: AsyncSession = Depends(get_db_session),
) -> PermissionResponse:
    """Create a new granular authorization grant under least-privilege principles."""
    try:
        perm = await create_permission(session, organization_id, payload)
        return PermissionResponse.model_validate(perm)
    except OrganizationNotFoundError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except OrganizationSuspendedError as e:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(e))
    except ResourceHierarchyError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except InactiveResourceError as e:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(e))
    except DuplicatePermissionError as e:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(e))


@router.get(
    "",
    response_model=PermissionListResponse,
    summary="List Permissions",
)
async def list_permissions_endpoint(
    organization_id: uuid.UUID,
    agent_id: Optional[uuid.UUID] = Query(None, description="Filter by agent UUID"),
    tool_id: Optional[uuid.UUID] = Query(None, description="Filter by tool UUID"),
    session: AsyncSession = Depends(get_db_session),
) -> PermissionListResponse:
    """List all permission grants scoped strictly to the organization."""
    permissions = await list_permissions(
        session, organization_id, agent_id=agent_id, tool_id=tool_id
    )
    items = [PermissionResponse.model_validate(p) for p in permissions]
    return PermissionListResponse(items=items, total=len(items))


@router.get(
    "/{permission_id}",
    response_model=PermissionResponse,
    summary="Retrieve Permission",
)
async def get_permission_endpoint(
    organization_id: uuid.UUID,
    permission_id: uuid.UUID,
    session: AsyncSession = Depends(get_db_session),
) -> PermissionResponse:
    """Retrieve an authoritative permission grant scoped to the organization."""
    perm = await get_permission(session, organization_id, permission_id)
    if perm is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Permission '{permission_id}' not found in organization '{organization_id}'",
        )
    return PermissionResponse.model_validate(perm)


@router.patch(
    "/{permission_id}",
    response_model=PermissionResponse,
    summary="Update Permission",
)
async def update_permission_endpoint(
    organization_id: uuid.UUID,
    permission_id: uuid.UUID,
    payload: PermissionUpdate,
    session: AsyncSession = Depends(get_db_session),
) -> PermissionResponse:
    """Update permission attributes (such as expiration) without altering status."""
    try:
        perm = await update_permission(session, organization_id, permission_id, payload)
        return PermissionResponse.model_validate(perm)
    except PermissionNotFoundError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except InvalidLifecycleTransitionError as e:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(e))


@router.post(
    "/{permission_id}/suspend",
    response_model=PermissionResponse,
    summary="Suspend Permission",
)
async def suspend_permission_endpoint(
    organization_id: uuid.UUID,
    permission_id: uuid.UUID,
    session: AsyncSession = Depends(get_db_session),
) -> PermissionResponse:
    """Suspend an active permission grant."""
    try:
        perm = await suspend_permission(session, organization_id, permission_id)
        return PermissionResponse.model_validate(perm)
    except PermissionNotFoundError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except InvalidLifecycleTransitionError as e:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(e))


@router.post(
    "/{permission_id}/revoke",
    response_model=PermissionResponse,
    summary="Revoke Permission",
)
async def revoke_permission_endpoint(
    organization_id: uuid.UUID,
    permission_id: uuid.UUID,
    session: AsyncSession = Depends(get_db_session),
) -> PermissionResponse:
    """Permanently revoke a permission grant. Terminal state."""
    try:
        perm = await revoke_permission(session, organization_id, permission_id)
        return PermissionResponse.model_validate(perm)
    except PermissionNotFoundError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))


@router.post(
    "/evaluate",
    response_model=PermissionEvaluationResponse,
    summary="Evaluate Permission Request",
)
async def evaluate_permission_endpoint(
    organization_id: uuid.UUID,
    payload: PermissionEvaluationRequest,
    session: AsyncSession = Depends(get_db_session),
) -> PermissionEvaluationResponse:
    """Evaluate whether an agent is authorized for an operation under least privilege."""
    result = await evaluate_permission(session, organization_id, payload)
    return PermissionEvaluationResponse(
        allowed=result.allowed,
        effect=result.effect,
        reason=result.reason,
        permission_id=result.permission_id,
    )
