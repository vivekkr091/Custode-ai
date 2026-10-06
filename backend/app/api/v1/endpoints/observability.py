"""Security Observability, Forensic Timeline, and Search API endpoints."""

from typing import Optional
import uuid

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import require_any_member
from app.db.models.membership import Membership
from app.db.session import get_db_session
from app.schemas.observability import (
    ActionForensicsResponse,
    SearchResponse,
    SecurityOverviewResponse,
)
from app.services.observability import (
    get_action_forensics,
    get_security_overview,
    search_security_investigation,
)

router = APIRouter(
    prefix="/organizations/{organization_id}",
    tags=["Observability & Forensics"],
)


@router.get(
    "/security-overview",
    response_model=SecurityOverviewResponse,
    summary="Get Organization Security Observability Overview",
)
async def get_security_overview_endpoint(
    organization_id: uuid.UUID,
    membership: Membership = Depends(require_any_member),
    session: AsyncSession = Depends(get_db_session),
) -> SecurityOverviewResponse:
    """Retrieve authoritative real-time aggregated security metrics strictly within tenant boundaries."""
    return await get_security_overview(session, organization_id)


@router.get(
    "/runtime-actions/{action_id}/forensics",
    response_model=ActionForensicsResponse,
    summary="Get Complete Forensic Timeline Dossier",
)
async def get_action_forensics_endpoint(
    organization_id: uuid.UUID,
    action_id: uuid.UUID,
    membership: Membership = Depends(require_any_member),
    session: AsyncSession = Depends(get_db_session),
) -> ActionForensicsResponse:
    """Retrieve full end-to-end forensic investigation dossier for a specific runtime action."""
    forensics = await get_action_forensics(session, organization_id, action_id)
    if forensics is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"RuntimeAction '{action_id}' not found in organization '{organization_id}'",
        )
    return forensics


@router.get(
    "/search",
    response_model=SearchResponse,
    summary="Global Security Investigation Search",
)
async def search_security_investigation_endpoint(
    organization_id: uuid.UUID,
    q: str = Query(..., min_length=1, max_length=200, description="Search query string"),
    limit: int = Query(30, ge=1, le=100),
    membership: Membership = Depends(require_any_member),
    session: AsyncSession = Depends(get_db_session),
) -> SearchResponse:
    """Search actions, decisions, approvals, executions, and audit records strictly scoped to tenant."""
    return await search_security_investigation(session, organization_id, q, limit)
