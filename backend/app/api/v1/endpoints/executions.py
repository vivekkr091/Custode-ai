"""API endpoints for Controlled Tool Execution on RuntimeActions."""

from typing import Optional
import uuid
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db_session
from app.schemas.execution import (
    ExecutionListResponse,
    ExecutionResponse,
)
from app.services.agent import OrganizationNotFoundError, OrganizationSuspendedError
from app.services.execution import (
    DuplicateExecutionError,
    ExecutionNotFoundError,
    execute_runtime_action,
    get_execution,
    list_executions,
)
from app.services.runtime_action import RuntimeActionNotFoundError

router = APIRouter(
    prefix="/organizations/{organization_id}",
    tags=["Executions"],
)


@router.post(
    "/runtime-actions/{runtime_action_id}/execute",
    response_model=ExecutionResponse,
    status_code=status.HTTP_200_OK,
    summary="Execute Authorized RuntimeAction",
)
async def execute_runtime_action_endpoint(
    organization_id: uuid.UUID,
    runtime_action_id: uuid.UUID,
    session: AsyncSession = Depends(get_db_session),
) -> ExecutionResponse:
    """Execute a RuntimeAction under strict controlled execution guardrails.
    
    Re-runs real-time security revalidation (Permission, Policy, Risk, Decision)
    and verifies human approval before dispatching to safe registered handlers.
    """
    try:
        execution = await execute_runtime_action(
            session=session,
            organization_id=organization_id,
            runtime_action_id=runtime_action_id,
        )
        return ExecutionResponse.model_validate(execution)
    except OrganizationNotFoundError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except OrganizationSuspendedError as e:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(e))
    except RuntimeActionNotFoundError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except DuplicateExecutionError as e:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(e))


@router.get(
    "/executions/{execution_id}",
    response_model=ExecutionResponse,
    summary="Retrieve Execution Record by ID",
)
async def get_execution_endpoint(
    organization_id: uuid.UUID,
    execution_id: uuid.UUID,
    session: AsyncSession = Depends(get_db_session),
) -> ExecutionResponse:
    """Retrieve an authoritative Execution audit record scoped to an organization."""
    execution = await get_execution(session, organization_id, execution_id)
    if execution is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Execution '{execution_id}' not found in organization '{organization_id}'",
        )
    return ExecutionResponse.model_validate(execution)


@router.get(
    "/executions",
    response_model=ExecutionListResponse,
    summary="List Organization Executions",
)
async def list_organization_executions_endpoint(
    organization_id: uuid.UUID,
    runtime_action_id: Optional[uuid.UUID] = Query(None),
    agent_id: Optional[uuid.UUID] = Query(None),
    tool_id: Optional[uuid.UUID] = Query(None),
    status_filter: Optional[str] = Query(None, alias="status"),
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0),
    session: AsyncSession = Depends(get_db_session),
) -> ExecutionListResponse:
    """List execution records strictly scoped to the specified organization."""
    executions, total = await list_executions(
        session=session,
        organization_id=organization_id,
        runtime_action_id=runtime_action_id,
        agent_id=agent_id,
        tool_id=tool_id,
        status=status_filter,
        limit=limit,
        offset=offset,
    )
    items = [ExecutionResponse.model_validate(e) for e in executions]
    return ExecutionListResponse(items=items, total=total)
