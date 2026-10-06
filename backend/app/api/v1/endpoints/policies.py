"""Policy API endpoints for policy lifecycle, versioning, and contextual rule evaluation."""

import uuid
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db_session
from app.schemas.policy import (
    PolicyCreate,
    PolicyEvaluationRequest,
    PolicyEvaluationResult,
    PolicyListResponse,
    PolicyResponse,
    PolicyUpdate,
    PolicyVersionCreate,
    PolicyVersionListResponse,
    PolicyVersionResponse,
)
from app.services.agent import OrganizationNotFoundError, OrganizationSuspendedError
from app.services.policy import (
    DuplicatePolicySlugError,
    PolicyNotFoundError,
    PolicyVersionImmutableError,
    PolicyVersionNotFoundError,
    create_policy,
    create_policy_version,
    evaluate_policies,
    get_active_policy_version_number,
    get_policy,
    get_policy_version,
    list_policies,
    list_policy_versions,
    publish_policy_version,
    retire_policy_version,
    update_policy,
)

router = APIRouter(
    prefix="/organizations/{organization_id}/policies",
    tags=["Policies"],
)


async def _to_policy_response(session: AsyncSession, policy) -> PolicyResponse:
    """Helper to assemble PolicyResponse with active_version resolved."""
    active_ver = await get_active_policy_version_number(session, policy.id)
    return PolicyResponse(
        id=policy.id,
        organization_id=policy.organization_id,
        name=policy.name,
        slug=policy.slug,
        description=policy.description,
        status=policy.status,
        enforcement_mode=policy.enforcement_mode,
        active_version=active_ver,
        created_at=policy.created_at,
        updated_at=policy.updated_at,
    )


@router.post(
    "",
    response_model=PolicyResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create Policy",
)
async def create_policy_endpoint(
    organization_id: uuid.UUID,
    payload: PolicyCreate,
    session: AsyncSession = Depends(get_db_session),
) -> PolicyResponse:
    """Create a new security policy container scoped to an organization."""
    try:
        policy = await create_policy(session, organization_id, payload)
        return await _to_policy_response(session, policy)
    except OrganizationNotFoundError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except OrganizationSuspendedError as e:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(e))
    except DuplicatePolicySlugError as e:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(e))


@router.get(
    "",
    response_model=PolicyListResponse,
    summary="List Policies",
)
async def list_policies_endpoint(
    organization_id: uuid.UUID,
    status_filter: Optional[str] = Query(None, alias="status", description="Filter by status"),
    enforcement_mode: Optional[str] = Query(None, description="Filter by enforcement mode"),
    session: AsyncSession = Depends(get_db_session),
) -> PolicyListResponse:
    """List all policies scoped strictly to the organization."""
    policies = await list_policies(
        session, organization_id, status=status_filter, enforcement_mode=enforcement_mode
    )
    items = [await _to_policy_response(session, p) for p in policies]
    return PolicyListResponse(items=items, total=len(items))


@router.post(
    "/evaluate",
    response_model=PolicyEvaluationResult,
    summary="Evaluate Policies against Action Context",
)
async def evaluate_policies_endpoint(
    organization_id: uuid.UUID,
    payload: PolicyEvaluationRequest,
    session: AsyncSession = Depends(get_db_session),
) -> PolicyEvaluationResult:
    """Contextual rule evaluation against all active policies for the organization."""
    try:
        return await evaluate_policies(session, organization_id, payload.context)
    except OrganizationNotFoundError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except OrganizationSuspendedError as e:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(e))


@router.get(
    "/{policy_id}",
    response_model=PolicyResponse,
    summary="Retrieve Policy",
)
async def get_policy_endpoint(
    organization_id: uuid.UUID,
    policy_id: uuid.UUID,
    session: AsyncSession = Depends(get_db_session),
) -> PolicyResponse:
    """Retrieve an authoritative policy scoped to the organization."""
    policy = await get_policy(session, organization_id, policy_id)
    if policy is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Policy '{policy_id}' not found in organization '{organization_id}'",
        )
    return await _to_policy_response(session, policy)


@router.patch(
    "/{policy_id}",
    response_model=PolicyResponse,
    summary="Update Policy",
)
async def update_policy_endpoint(
    organization_id: uuid.UUID,
    policy_id: uuid.UUID,
    payload: PolicyUpdate,
    session: AsyncSession = Depends(get_db_session),
) -> PolicyResponse:
    """Update policy attributes (name, description, status, enforcement_mode)."""
    try:
        policy = await update_policy(session, organization_id, policy_id, payload)
        return await _to_policy_response(session, policy)
    except PolicyNotFoundError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))


# --- Policy Version Endpoints ---


@router.post(
    "/{policy_id}/versions",
    response_model=PolicyVersionResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create Policy Version",
)
async def create_policy_version_endpoint(
    organization_id: uuid.UUID,
    policy_id: uuid.UUID,
    payload: PolicyVersionCreate,
    session: AsyncSession = Depends(get_db_session),
) -> PolicyVersionResponse:
    """Draft a new policy version with sequential version numbering."""
    try:
        version = await create_policy_version(session, organization_id, policy_id, payload)
        return PolicyVersionResponse.model_validate(version)
    except PolicyNotFoundError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))


@router.get(
    "/{policy_id}/versions",
    response_model=PolicyVersionListResponse,
    summary="List Policy Versions",
)
async def list_policy_versions_endpoint(
    organization_id: uuid.UUID,
    policy_id: uuid.UUID,
    session: AsyncSession = Depends(get_db_session),
) -> PolicyVersionListResponse:
    """List all versions for a policy ordered by version descending."""
    try:
        versions = await list_policy_versions(session, organization_id, policy_id)
        items = [PolicyVersionResponse.model_validate(v) for v in versions]
        return PolicyVersionListResponse(items=items, total=len(items))
    except PolicyNotFoundError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))


@router.get(
    "/{policy_id}/versions/{version_id}",
    response_model=PolicyVersionResponse,
    summary="Retrieve Policy Version",
)
async def get_policy_version_endpoint(
    organization_id: uuid.UUID,
    policy_id: uuid.UUID,
    version_id: uuid.UUID,
    session: AsyncSession = Depends(get_db_session),
) -> PolicyVersionResponse:
    """Retrieve a specific policy version by ID."""
    version = await get_policy_version(session, organization_id, policy_id, version_id)
    if version is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Policy version '{version_id}' not found for policy '{policy_id}'",
        )
    return PolicyVersionResponse.model_validate(version)


@router.post(
    "/{policy_id}/versions/{version_id}/publish",
    response_model=PolicyVersionResponse,
    summary="Publish Policy Version",
)
async def publish_policy_version_endpoint(
    organization_id: uuid.UUID,
    policy_id: uuid.UUID,
    version_id: uuid.UUID,
    session: AsyncSession = Depends(get_db_session),
) -> PolicyVersionResponse:
    """Publish a policy version, automatically retiring any previously published version."""
    try:
        version = await publish_policy_version(session, organization_id, policy_id, version_id)
        return PolicyVersionResponse.model_validate(version)
    except PolicyNotFoundError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except PolicyVersionNotFoundError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))


@router.post(
    "/{policy_id}/versions/{version_id}/retire",
    response_model=PolicyVersionResponse,
    summary="Retire Policy Version",
)
async def retire_policy_version_endpoint(
    organization_id: uuid.UUID,
    policy_id: uuid.UUID,
    version_id: uuid.UUID,
    session: AsyncSession = Depends(get_db_session),
) -> PolicyVersionResponse:
    """Retire an active or published policy version."""
    try:
        version = await retire_policy_version(session, organization_id, policy_id, version_id)
        return PolicyVersionResponse.model_validate(version)
    except PolicyNotFoundError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except PolicyVersionNotFoundError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
