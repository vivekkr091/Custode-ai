"""API endpoints for Authorization Decisions on RuntimeActions."""

from typing import List, Optional
import uuid
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db_session
from app.schemas.decision import (
    DecisionListResponse,
    DecisionResponse,
)
from app.services.agent import OrganizationNotFoundError, OrganizationSuspendedError
from app.services.decision import (
    DecisionNotFoundError,
    decide_runtime_action,
    get_decision,
    list_decisions,
    list_decisions_for_action,
)
from app.services.permission import InactiveResourceError, ResourceHierarchyError
from app.services.runtime_action import RuntimeActionNotFoundError
from app.services.tool_operation import OperationNotFoundError

router = APIRouter(
    prefix="/organizations/{organization_id}",
    tags=["Decisions"],
)


@router.post(
    "/runtime-actions/{runtime_action_id}/decide",
    response_model=DecisionResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Arbitrate Authorization Decision for RuntimeAction",
)
async def decide_runtime_action_endpoint(
    organization_id: uuid.UUID,
    runtime_action_id: uuid.UUID,
    session: AsyncSession = Depends(get_db_session),
) -> DecisionResponse:
    """Arbitrate deterministic authorization decision from permissions, policies, and risk, persisting an immutable decision record."""
    try:
        decision = await decide_runtime_action(
            session=session,
            organization_id=organization_id,
            runtime_action_id=runtime_action_id,
        )
        return DecisionResponse.model_validate(decision)
    except OrganizationNotFoundError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except OrganizationSuspendedError as e:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(e))
    except RuntimeActionNotFoundError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except ResourceHierarchyError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except InactiveResourceError as e:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(e))
    except OperationNotFoundError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))


@router.get(
    "/runtime-actions/{runtime_action_id}/decisions",
    response_model=DecisionListResponse,
    summary="List Historical Decisions for Action",
)
async def list_action_decisions_endpoint(
    organization_id: uuid.UUID,
    runtime_action_id: uuid.UUID,
    session: AsyncSession = Depends(get_db_session),
) -> DecisionListResponse:
    """Retrieve all historical decisions for a specific runtime action in descending order."""
    try:
        decisions = await list_decisions_for_action(
            session=session,
            organization_id=organization_id,
            runtime_action_id=runtime_action_id,
        )
        items = [DecisionResponse.model_validate(d) for d in decisions]
        return DecisionListResponse(items=items, total=len(items))
    except RuntimeActionNotFoundError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))


@router.get(
    "/decisions/{decision_id}",
    response_model=DecisionResponse,
    summary="Retrieve Decision by ID",
)
async def get_decision_endpoint(
    organization_id: uuid.UUID,
    decision_id: uuid.UUID,
    session: AsyncSession = Depends(get_db_session),
) -> DecisionResponse:
    """Retrieve an authoritative Decision scoped to an organization."""
    decision = await get_decision(session, organization_id, decision_id)
    if decision is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Decision '{decision_id}' not found in organization '{organization_id}'",
        )
    return DecisionResponse.model_validate(decision)


@router.get(
    "/decisions",
    response_model=DecisionListResponse,
    summary="List Organization Decisions",
)
async def list_organization_decisions_endpoint(
    organization_id: uuid.UUID,
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0),
    session: AsyncSession = Depends(get_db_session),
) -> DecisionListResponse:
    """List authorization decisions strictly scoped to the specified organization."""
    decisions, total = await list_decisions(
        session=session,
        organization_id=organization_id,
        limit=limit,
        offset=offset,
    )
    items = [DecisionResponse.model_validate(d) for d in decisions]
    return DecisionListResponse(items=items, total=total)
