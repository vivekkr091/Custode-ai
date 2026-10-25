"""API endpoints for RuntimeAction lifecycle, management, and state transitions."""

from typing import Optional
import uuid
from fastapi import APIRouter, Depends, Header, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import API_KEY_PREFIX, decode_access_token
from app.db.models.membership import Membership, MembershipStatus
from app.db.models.organization import Organization, OrganizationStatus
from app.db.session import get_db_session
from app.runtime.normalizer import NormalizationError
from app.schemas.runtime_action import (
    RuntimeActionCreate,
    RuntimeActionListResponse,
    RuntimeActionResponse,
    RuntimeActionTransitionRequest,
)
from app.services.agent import OrganizationNotFoundError, OrganizationSuspendedError
from app.services.authentication import AuthenticationError, authenticate_agent_token
from app.services.runtime_action import (
    EnvironmentIncompatibilityError,
    InactiveResourceError,
    InvalidActionLifecycleTransitionError,
    ResourceHierarchyError,
    RuntimeActionNotFoundError,
    create_runtime_action,
    get_runtime_action,
    list_runtime_actions,
    transition_runtime_action_status,
)

router = APIRouter(
    prefix="/organizations/{organization_id}/runtime-actions",
    tags=["Runtime Actions"],
)


async def validate_tenant_access(
    organization_id: uuid.UUID,
    authorization: Optional[str] = Header(None, alias="Authorization"),
    x_user_id: Optional[uuid.UUID] = Header(None, alias="X-User-ID"),
    session: AsyncSession = Depends(get_db_session),
) -> Optional[Membership]:
    """Validate organization existence, active status, and human user membership if provided."""
    org_q = select(Organization).where(Organization.id == organization_id)
    org_res = await session.execute(org_q)
    org = org_res.scalar_one_or_none()
    if org is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Organization '{organization_id}' not found",
        )
    if org.status != OrganizationStatus.active.value:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Organization '{organization_id}' is suspended or inactive",
        )

    if x_user_id:
        mem_q = select(Membership).where(
            Membership.organization_id == organization_id,
            Membership.user_id == x_user_id,
            Membership.status == MembershipStatus.active.value,
        )
        mem_res = await session.execute(mem_q)
        mem = mem_res.scalar_one_or_none()
        if mem is None:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"User '{x_user_id}' does not have active membership in organization '{organization_id}'",
            )
        return mem

    if authorization:
        parts = authorization.strip().split(" ", 1)
        if len(parts) == 2 and parts[0].lower() == "bearer":
            token = parts[1].strip()
            if not token.startswith(API_KEY_PREFIX):
                try:
                    payload = decode_access_token(token)
                    sub = payload.get("sub")
                    if sub:
                        user_uuid = uuid.UUID(sub)
                        mem_q = select(Membership).where(
                            Membership.organization_id == organization_id,
                            Membership.user_id == user_uuid,
                            Membership.status == MembershipStatus.active.value,
                        )
                        mem_res = await session.execute(mem_q)
                        mem = mem_res.scalar_one_or_none()
                        if mem is None:
                            raise HTTPException(
                                status_code=status.HTTP_403_FORBIDDEN,
                                detail="Forbidden: User is not an active member of this organization",
                            )
                        return mem
                except HTTPException:
                    raise
                except Exception:
                    pass

    return None


@router.post(
    "",
    response_model=RuntimeActionResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create Runtime Action",
)
async def create_runtime_action_endpoint(
    organization_id: uuid.UUID,
    payload: RuntimeActionCreate,
    authorization: Optional[str] = Header(None, alias="Authorization"),
    x_agent_id: Optional[uuid.UUID] = Header(None, alias="X-Agent-ID"),
    session: AsyncSession = Depends(get_db_session),
) -> RuntimeActionResponse:
    """Register and canonicalize a concrete action request initiated by an agent."""
    resolved_agent_id: uuid.UUID

    if authorization:
        parts = authorization.strip().split(" ", 1)
        if len(parts) == 2 and parts[0].lower() == "bearer":
            token = parts[1].strip()
            if token.startswith(API_KEY_PREFIX):
                try:
                    auth_agent = await authenticate_agent_token(session, token)
                    if auth_agent.organization_id != organization_id:
                        raise HTTPException(
                            status_code=status.HTTP_403_FORBIDDEN,
                            detail="Authenticated agent does not belong to target organization",
                        )
                    resolved_agent_id = auth_agent.agent_id
                except AuthenticationError as e:
                    raise HTTPException(
                        status_code=status.HTTP_401_UNAUTHORIZED,
                        detail=str(e),
                        headers={"WWW-Authenticate": "Bearer"},
                    )
            elif x_agent_id:
                resolved_agent_id = x_agent_id
            else:
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Agent identity required. Provide agent token or X-Agent-ID header",
                    headers={"WWW-Authenticate": "Bearer"},
                )
        elif x_agent_id:
            resolved_agent_id = x_agent_id
        else:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Malformed Authorization header. Format: Bearer <agent-api-key>",
                headers={"WWW-Authenticate": "Bearer"},
            )
    elif x_agent_id:
        resolved_agent_id = x_agent_id
    else:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Agent identity required. Provide Authorization Bearer token or X-Agent-ID header",
            headers={"WWW-Authenticate": "Bearer"},
        )

    try:
        action = await create_runtime_action(
            session=session,
            organization_id=organization_id,
            agent_id=resolved_agent_id,
            data=payload,
        )
        return RuntimeActionResponse.model_validate(action)
    except OrganizationNotFoundError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except OrganizationSuspendedError as e:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(e))
    except ResourceHierarchyError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except InactiveResourceError as e:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(e))
    except EnvironmentIncompatibilityError as e:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(e))
    except NormalizationError as e:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(e))


@router.get(
    "",
    response_model=RuntimeActionListResponse,
    summary="List Runtime Actions",
)
async def list_runtime_actions_endpoint(
    organization_id: uuid.UUID,
    agent_id: Optional[uuid.UUID] = Query(None, description="Filter by agent UUID"),
    tool_id: Optional[uuid.UUID] = Query(None, description="Filter by tool UUID"),
    status_filter: Optional[str] = Query(None, alias="status", description="Filter by lifecycle status"),
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0),
    _tenant_check: Optional[Membership] = Depends(validate_tenant_access),
    session: AsyncSession = Depends(get_db_session),
) -> RuntimeActionListResponse:
    """List runtime actions strictly scoped to the specified organization."""
    actions = await list_runtime_actions(
        session=session,
        organization_id=organization_id,
        agent_id=agent_id,
        tool_id=tool_id,
        status=status_filter,
        limit=limit,
        offset=offset,
    )
    items = [RuntimeActionResponse.model_validate(a) for a in actions]
    return RuntimeActionListResponse(items=items, total=len(items))


@router.get(
    "/{runtime_action_id}",
    response_model=RuntimeActionResponse,
    summary="Retrieve Runtime Action",
)
async def get_runtime_action_endpoint(
    organization_id: uuid.UUID,
    runtime_action_id: uuid.UUID,
    _tenant_check: Optional[Membership] = Depends(validate_tenant_access),
    session: AsyncSession = Depends(get_db_session),
) -> RuntimeActionResponse:
    """Retrieve an authoritative RuntimeAction scoped to an organization."""
    action = await get_runtime_action(session, organization_id, runtime_action_id)
    if action is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"RuntimeAction '{runtime_action_id}' not found in organization '{organization_id}'",
        )
    return RuntimeActionResponse.model_validate(action)


@router.post(
    "/{runtime_action_id}/transition",
    response_model=RuntimeActionResponse,
    summary="Transition Runtime Action Status",
)
async def transition_runtime_action_endpoint(
    organization_id: uuid.UUID,
    runtime_action_id: uuid.UUID,
    payload: RuntimeActionTransitionRequest,
    _tenant_check: Optional[Membership] = Depends(validate_tenant_access),
    session: AsyncSession = Depends(get_db_session),
) -> RuntimeActionResponse:
    """Transition a RuntimeAction's lifecycle state under strict state-machine validation."""
    try:
        action = await transition_runtime_action_status(
            session=session,
            organization_id=organization_id,
            action_id=runtime_action_id,
            target_status=payload.target_status,
        )
        return RuntimeActionResponse.model_validate(action)
    except RuntimeActionNotFoundError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except InvalidActionLifecycleTransitionError as e:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(e))
