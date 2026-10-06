"""API endpoints for Contextual Risk Assessment on RuntimeActions."""

from typing import List, Optional
import uuid
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db_session
from app.schemas.risk import (
    RiskAssessmentListResponse,
    RiskAssessmentResponse,
)
from app.services.agent import OrganizationNotFoundError, OrganizationSuspendedError
from app.services.risk_assessment import (
    RiskAssessmentNotFoundError,
    assess_runtime_action,
    get_risk_assessment,
    list_risk_assessments,
    list_risk_assessments_for_action,
)
from app.services.runtime_action import RuntimeActionNotFoundError
from app.services.tool_operation import OperationNotFoundError

router = APIRouter(
    prefix="/organizations/{organization_id}",
    tags=["Risk Assessments"],
)


@router.post(
    "/runtime-actions/{runtime_action_id}/risk-assess",
    response_model=RiskAssessmentResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Assess Contextual Risk for RuntimeAction",
)
async def assess_runtime_action_endpoint(
    organization_id: uuid.UUID,
    runtime_action_id: uuid.UUID,
    session: AsyncSession = Depends(get_db_session),
) -> RiskAssessmentResponse:
    """Evaluate deterministic contextual risk factors and persist an immutable assessment record."""
    try:
        assessment = await assess_runtime_action(
            session=session,
            organization_id=organization_id,
            runtime_action_id=runtime_action_id,
        )
        return RiskAssessmentResponse.model_validate(assessment)
    except OrganizationNotFoundError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except OrganizationSuspendedError as e:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(e))
    except RuntimeActionNotFoundError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except OperationNotFoundError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))


@router.get(
    "/runtime-actions/{runtime_action_id}/risk-assessments",
    response_model=RiskAssessmentListResponse,
    summary="List Historical Risk Assessments for Action",
)
async def list_action_risk_assessments_endpoint(
    organization_id: uuid.UUID,
    runtime_action_id: uuid.UUID,
    session: AsyncSession = Depends(get_db_session),
) -> RiskAssessmentListResponse:
    """Retrieve all historical risk assessments for a specific runtime action in descending order."""
    try:
        assessments = await list_risk_assessments_for_action(
            session=session,
            organization_id=organization_id,
            runtime_action_id=runtime_action_id,
        )
        items = [RiskAssessmentResponse.model_validate(a) for a in assessments]
        return RiskAssessmentListResponse(items=items, total=len(items))
    except RuntimeActionNotFoundError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))


@router.get(
    "/risk-assessments/{risk_assessment_id}",
    response_model=RiskAssessmentResponse,
    summary="Retrieve Risk Assessment by ID",
)
async def get_risk_assessment_endpoint(
    organization_id: uuid.UUID,
    risk_assessment_id: uuid.UUID,
    session: AsyncSession = Depends(get_db_session),
) -> RiskAssessmentResponse:
    """Retrieve an authoritative RiskAssessment scoped to an organization."""
    assessment = await get_risk_assessment(session, organization_id, risk_assessment_id)
    if assessment is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"RiskAssessment '{risk_assessment_id}' not found in organization '{organization_id}'",
        )
    return RiskAssessmentResponse.model_validate(assessment)


@router.get(
    "/risk-assessments",
    response_model=RiskAssessmentListResponse,
    summary="List Organization Risk Assessments",
)
async def list_organization_risk_assessments_endpoint(
    organization_id: uuid.UUID,
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0),
    session: AsyncSession = Depends(get_db_session),
) -> RiskAssessmentListResponse:
    """List risk assessments strictly scoped to the specified organization."""
    assessments = await list_risk_assessments(
        session=session,
        organization_id=organization_id,
        limit=limit,
        offset=offset,
    )
    items = [RiskAssessmentResponse.model_validate(a) for a in assessments]
    return RiskAssessmentListResponse(items=items, total=len(items))
