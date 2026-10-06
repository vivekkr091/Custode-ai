"""API endpoints for Security Findings, Sentinel Scans, and Security Telemetry."""

from typing import List, Optional
import uuid
from fastapi import APIRouter, Depends, Header, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.db.models.membership import Membership, MembershipStatus
from app.db.models.organization import Organization, OrganizationStatus
from app.db.session import get_db_session
from app.schemas.security_finding import (
    SecurityFindingListResponse,
    SecurityFindingResponse,
)
from app.schemas.security_scan import (
    SecurityMetricsResponse,
    SecurityScanListResponse,
    SecurityScanResponse,
)
from app.services.agent import OrganizationNotFoundError, OrganizationSuspendedError
from app.services.runtime_action import RuntimeActionNotFoundError
from app.services.sentinel_scan import (
    SecurityFindingNotFoundError,
    get_security_finding,
    get_security_metrics,
    list_findings_for_action,
    list_scans_for_action,
    list_security_findings,
    scan_runtime_action,
)

router = APIRouter(
    prefix="/organizations/{organization_id}",
    tags=["Security Findings & Scans"],
)


async def validate_tenant_access(
    organization_id: uuid.UUID,
    authorization: Optional[str] = Header(None, alias="Authorization"),
    x_user_id: Optional[uuid.UUID] = Header(None, alias="X-User-ID"),
    session: AsyncSession = Depends(get_db_session),
) -> Optional[Membership]:
    """Enforce organization membership if user headers are supplied, otherwise validate organization status."""
    # 1. Validate Organization exists and is active
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

    # 2. If human user auth is present, enforce strict membership
    if authorization or x_user_id:
        user = await get_current_user(authorization=authorization, x_user_id=x_user_id, session=session)
        mem_q = select(Membership).where(
            Membership.organization_id == organization_id,
            Membership.user_id == user.id,
            Membership.status == MembershipStatus.active.value,
        )
        mem_res = await session.execute(mem_q)
        membership = mem_res.scalar_one_or_none()
        if membership is None:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Forbidden: User is not an active member of this organization",
            )
        return membership

    return None


@router.get(
    "/findings",
    response_model=SecurityFindingListResponse,
    summary="List Organization Security Findings",
)
async def list_findings_endpoint(
    organization_id: uuid.UUID,
    severity: Optional[str] = Query(None, description="Filter by severity (CRITICAL, HIGH, MEDIUM, LOW)"),
    category: Optional[str] = Query(None, description="Filter by category"),
    scanner: Optional[str] = Query(None, description="Filter by scanner name"),
    runtime_action_id: Optional[uuid.UUID] = Query(None, description="Filter by RuntimeAction ID"),
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0),
    _tenant_check: Optional[Membership] = Depends(validate_tenant_access),
    session: AsyncSession = Depends(get_db_session),
) -> SecurityFindingListResponse:
    """Retrieve security findings strictly scoped to the tenant with multi-criteria filtering."""
    findings, total = await list_security_findings(
        session=session,
        organization_id=organization_id,
        severity=severity,
        category=category,
        scanner=scanner,
        runtime_action_id=runtime_action_id,
        limit=limit,
        offset=offset,
    )
    items = [SecurityFindingResponse.model_validate(f) for f in findings]
    return SecurityFindingListResponse(items=items, total=total)


@router.get(
    "/findings/{finding_id}",
    response_model=SecurityFindingResponse,
    summary="Get Security Finding Detail",
)
async def get_finding_endpoint(
    organization_id: uuid.UUID,
    finding_id: uuid.UUID,
    _tenant_check: Optional[Membership] = Depends(validate_tenant_access),
    session: AsyncSession = Depends(get_db_session),
) -> SecurityFindingResponse:
    """Retrieve a single authoritative security finding within tenant boundary."""
    finding = await get_security_finding(session, organization_id, finding_id)
    if finding is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"SecurityFinding '{finding_id}' not found in organization '{organization_id}'",
        )
    return SecurityFindingResponse.model_validate(finding)


@router.post(
    "/runtime-actions/{runtime_action_id}/scan",
    response_model=SecurityScanResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Run Sentinel Security Scan on Runtime Action",
)
async def scan_runtime_action_endpoint(
    organization_id: uuid.UUID,
    runtime_action_id: uuid.UUID,
    _tenant_check: Optional[Membership] = Depends(validate_tenant_access),
    session: AsyncSession = Depends(get_db_session),
) -> SecurityScanResponse:
    """Execute Sentinel security scanners across payload parameters and record findings."""
    try:
        scan, findings = await scan_runtime_action(
            session=session,
            organization_id=organization_id,
            runtime_action_id=runtime_action_id,
        )
        scan_resp = SecurityScanResponse.model_validate(scan)
        scan_resp.findings = [SecurityFindingResponse.model_validate(f) for f in findings]
        return scan_resp
    except OrganizationNotFoundError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except OrganizationSuspendedError as e:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(e))
    except RuntimeActionNotFoundError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))


@router.get(
    "/runtime-actions/{runtime_action_id}/scans",
    response_model=SecurityScanListResponse,
    summary="List Security Scans for Runtime Action",
)
async def list_action_scans_endpoint(
    organization_id: uuid.UUID,
    runtime_action_id: uuid.UUID,
    _tenant_check: Optional[Membership] = Depends(validate_tenant_access),
    session: AsyncSession = Depends(get_db_session),
) -> SecurityScanListResponse:
    """List historical security scans performed on a specific action."""
    scans = await list_scans_for_action(session, organization_id, runtime_action_id)
    items = [SecurityScanResponse.model_validate(s) for s in scans]
    return SecurityScanListResponse(items=items, total=len(items))


@router.get(
    "/runtime-actions/{runtime_action_id}/findings",
    response_model=SecurityFindingListResponse,
    summary="List Security Findings for Runtime Action",
)
async def list_action_findings_endpoint(
    organization_id: uuid.UUID,
    runtime_action_id: uuid.UUID,
    _tenant_check: Optional[Membership] = Depends(validate_tenant_access),
    session: AsyncSession = Depends(get_db_session),
) -> SecurityFindingListResponse:
    """List all security findings associated with a specific action."""
    findings = await list_findings_for_action(session, organization_id, runtime_action_id)
    items = [SecurityFindingResponse.model_validate(f) for f in findings]
    return SecurityFindingListResponse(items=items, total=len(items))


@router.get(
    "/security/metrics",
    response_model=SecurityMetricsResponse,
    summary="Get Aggregated Security Findings Metrics",
)
async def get_security_metrics_endpoint(
    organization_id: uuid.UUID,
    _tenant_check: Optional[Membership] = Depends(validate_tenant_access),
    session: AsyncSession = Depends(get_db_session),
) -> SecurityMetricsResponse:
    """Retrieve organization-level security metrics, severity breakdown, and category distribution."""
    metrics = await get_security_metrics(session, organization_id)
    return SecurityMetricsResponse(**metrics)
