"""API endpoints for the CUSTODE Behavioral & Anomaly Detection Engine."""

from typing import Optional
import uuid
from fastapi import APIRouter, Depends, Header, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.agent import Agent
from app.db.models.membership import Membership, MembershipRole, MembershipStatus
from app.db.models.organization import Organization, OrganizationStatus
from app.db.session import get_db_session
from app.engines.behavior.models import (
    AgentBehaviorProfile,
    AnomalyResolutionRequest,
    BehaviorMetrics,
    BehavioralAnomalyListResponse,
    BehavioralAnomalyResponse,
)
from app.engines.behavior.service import (
    BehavioralAnomalyNotFoundError,
    get_agent_behavior_profile,
    get_anomaly,
    get_behavior_metrics,
    list_anomalies,
    resolve_anomaly,
    suppress_anomaly,
)

router = APIRouter(
    prefix="/organizations/{organization_id}",
    tags=["Behavioral & Anomaly Detection"],
)


async def validate_tenant_access(
    organization_id: uuid.UUID,
    x_user_id: Optional[uuid.UUID] = Header(None, alias="X-User-ID"),
    session: AsyncSession = Depends(get_db_session),
) -> Optional[Membership]:
    """Validate organization existence and optional membership RBAC context."""
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
                detail="User is not an active member of this organization",
            )
        return mem

    return None


def require_analyst_or_admin(membership: Optional[Membership]) -> None:
    """Enforce that caller has administrative or security analyst permissions."""
    if membership is None:
        return
    role = membership.role
    if role not in (MembershipRole.organization_admin.value, MembershipRole.security_analyst.value):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Operation requires organization_admin or security_analyst role",
        )


@router.get(
    "/agents/{agent_id}/behavior",
    response_model=AgentBehaviorProfile,
    summary="Get Agent Behavior Profile",
)
async def get_agent_behavior_profile_endpoint(
    organization_id: uuid.UUID,
    agent_id: uuid.UUID,
    environment: str = Query("production", description="Environment baseline to inspect"),
    session: AsyncSession = Depends(get_db_session),
    membership: Optional[Membership] = Depends(validate_tenant_access),
) -> AgentBehaviorProfile:
    """Retrieve an aggregated, explainable behavioral baseline profile for a specific agent."""
    # Ensure agent belongs to tenant
    agent_res = await session.execute(
        select(Agent).where(
            Agent.id == agent_id,
            Agent.organization_id == organization_id,
        )
    )
    if not agent_res.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Agent '{agent_id}' not found in organization '{organization_id}'",
        )

    profile = await get_agent_behavior_profile(
        session=session,
        organization_id=organization_id,
        agent_id=agent_id,
        environment=environment,
    )
    return profile


@router.get(
    "/behavior/anomalies",
    response_model=BehavioralAnomalyListResponse,
    summary="List Behavioral Anomalies",
)
async def list_behavioral_anomalies_endpoint(
    organization_id: uuid.UUID,
    agent_id: Optional[uuid.UUID] = Query(None, description="Filter by agent ID"),
    status_filter: Optional[str] = Query(None, alias="status", description="Filter by status (OPEN, REVIEWED, RESOLVED, SUPPRESSED)"),
    severity: Optional[str] = Query(None, description="Filter by severity (LOW, MEDIUM, HIGH, CRITICAL)"),
    anomaly_type: Optional[str] = Query(None, description="Filter by anomaly type"),
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0),
    session: AsyncSession = Depends(get_db_session),
    membership: Optional[Membership] = Depends(validate_tenant_access),
) -> BehavioralAnomalyListResponse:
    """List behavioral anomalies strictly scoped to organization with optional filtering."""
    items, total = await list_anomalies(
        session=session,
        organization_id=organization_id,
        agent_id=agent_id,
        status_filter=status_filter,
        severity_filter=severity,
        anomaly_type=anomaly_type,
        limit=limit,
        offset=offset,
    )
    return BehavioralAnomalyListResponse(
        items=[BehavioralAnomalyResponse.model_validate(it) for it in items],
        total=total,
    )


@router.get(
    "/behavior/anomalies/{anomaly_id}",
    response_model=BehavioralAnomalyResponse,
    summary="Get Behavioral Anomaly by ID",
)
async def get_behavioral_anomaly_endpoint(
    organization_id: uuid.UUID,
    anomaly_id: uuid.UUID,
    session: AsyncSession = Depends(get_db_session),
    membership: Optional[Membership] = Depends(validate_tenant_access),
) -> BehavioralAnomalyResponse:
    """Retrieve details and evidence for a specific behavioral anomaly finding."""
    anomaly = await get_anomaly(session, organization_id, anomaly_id)
    if not anomaly:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Behavioral anomaly '{anomaly_id}' not found in organization '{organization_id}'",
        )
    return BehavioralAnomalyResponse.model_validate(anomaly)


@router.post(
    "/behavior/anomalies/{anomaly_id}/resolve",
    response_model=BehavioralAnomalyResponse,
    summary="Resolve Behavioral Anomaly",
)
async def resolve_behavioral_anomaly_endpoint(
    organization_id: uuid.UUID,
    anomaly_id: uuid.UUID,
    payload: Optional[AnomalyResolutionRequest] = None,
    x_user_id: Optional[uuid.UUID] = Header(None, alias="X-User-ID"),
    session: AsyncSession = Depends(get_db_session),
    membership: Optional[Membership] = Depends(validate_tenant_access),
) -> BehavioralAnomalyResponse:
    """Transition an anomaly status to RESOLVED with optional reviewer justification."""
    require_analyst_or_admin(membership)
    try:
        updated = await resolve_anomaly(
            session=session,
            organization_id=organization_id,
            anomaly_id=anomaly_id,
            user_id=x_user_id,
            note=payload.note if payload else None,
        )
        return BehavioralAnomalyResponse.model_validate(updated)
    except BehavioralAnomalyNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Behavioral anomaly '{anomaly_id}' not found in organization '{organization_id}'",
        )


@router.post(
    "/behavior/anomalies/{anomaly_id}/suppress",
    response_model=BehavioralAnomalyResponse,
    summary="Suppress Behavioral Anomaly",
)
async def suppress_behavioral_anomaly_endpoint(
    organization_id: uuid.UUID,
    anomaly_id: uuid.UUID,
    payload: Optional[AnomalyResolutionRequest] = None,
    x_user_id: Optional[uuid.UUID] = Header(None, alias="X-User-ID"),
    session: AsyncSession = Depends(get_db_session),
    membership: Optional[Membership] = Depends(validate_tenant_access),
) -> BehavioralAnomalyResponse:
    """Suppress a false-positive anomaly finding."""
    require_analyst_or_admin(membership)
    try:
        updated = await suppress_anomaly(
            session=session,
            organization_id=organization_id,
            anomaly_id=anomaly_id,
            user_id=x_user_id,
            note=payload.note if payload else None,
        )
        return BehavioralAnomalyResponse.model_validate(updated)
    except BehavioralAnomalyNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Behavioral anomaly '{anomaly_id}' not found in organization '{organization_id}'",
        )


@router.get(
    "/behavior/metrics",
    response_model=BehaviorMetrics,
    summary="Get Organization Behavior Metrics",
)
async def get_behavior_metrics_endpoint(
    organization_id: uuid.UUID,
    session: AsyncSession = Depends(get_db_session),
    membership: Optional[Membership] = Depends(validate_tenant_access),
) -> BehaviorMetrics:
    """Retrieve aggregate behavioral metrics, established baseline stats, and anomaly counts."""
    metrics = await get_behavior_metrics(session, organization_id)
    return metrics
