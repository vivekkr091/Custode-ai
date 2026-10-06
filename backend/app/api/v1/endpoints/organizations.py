"""Organization and Organization Membership API endpoints."""

import uuid
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db_session
from app.schemas.membership import MembershipCreate, MembershipResponse
from app.schemas.organization import OrganizationCreate, OrganizationResponse
from app.services.membership import (
    DuplicateMembershipError,
    OrganizationNotFoundError,
    UserNotFoundError,
    create_membership,
)
from app.services.organization import (
    SlugAlreadyExistsError,
    create_organization,
    get_organization_by_id,
)

router = APIRouter(prefix="/organizations", tags=["Organizations"])


@router.post(
    "",
    response_model=OrganizationResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create Organization",
)
async def create_org_endpoint(
    payload: OrganizationCreate,
    session: AsyncSession = Depends(get_db_session),
) -> OrganizationResponse:
    """Create a new organization entity with a unique slug."""
    try:
        org = await create_organization(session, payload)
        return OrganizationResponse.model_validate(org)
    except SlugAlreadyExistsError as e:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(e),
        )


@router.get(
    "",
    response_model=list[OrganizationResponse],
    summary="List Organizations",
)
async def list_orgs_endpoint(
    session: AsyncSession = Depends(get_db_session),
) -> list[OrganizationResponse]:
    """Retrieve all registered organizations."""
    from sqlalchemy import select
    from app.db.models.organization import Organization

    res = await session.execute(select(Organization).order_by(Organization.created_at.desc()))
    return [OrganizationResponse.model_validate(org) for org in res.scalars().all()]


@router.get(
    "/{organization_id}",
    response_model=OrganizationResponse,
    summary="Retrieve Organization",
)
async def get_org_endpoint(
    organization_id: uuid.UUID,
    session: AsyncSession = Depends(get_db_session),
) -> OrganizationResponse:
    """Retrieve an organization by its UUID."""
    org = await get_organization_by_id(session, organization_id)
    if org is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Organization '{organization_id}' not found",
        )
    return OrganizationResponse.model_validate(org)


@router.post(
    "/{organization_id}/memberships",
    response_model=MembershipResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create Organization Membership",
)
async def create_org_membership_endpoint(
    organization_id: uuid.UUID,
    payload: MembershipCreate,
    session: AsyncSession = Depends(get_db_session),
) -> MembershipResponse:
    """Add a user to an organization with a specified role."""
    try:
        membership = await create_membership(session, organization_id, payload)
        return MembershipResponse.model_validate(membership)
    except OrganizationNotFoundError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e),
        )
    except UserNotFoundError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e),
        )
    except DuplicateMembershipError as e:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(e),
        )
