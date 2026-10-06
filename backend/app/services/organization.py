"""Service functions for Organization entity."""

import uuid
from typing import Optional
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.organization import Organization, OrganizationStatus
from app.schemas.organization import OrganizationCreate, slugify


class SlugAlreadyExistsError(Exception):
    """Raised when an organization slug is already in use."""
    def __init__(self, slug: str):
        super().__init__(f"Organization with slug '{slug}' already exists")
        self.slug = slug


async def create_organization(session: AsyncSession, data: OrganizationCreate) -> Organization:
    """Create a new organization with a unique slug."""
    slug = data.slug or slugify(data.name)
    if not slug:
        slug = f"org-{uuid.uuid4().hex[:8]}"

    # Check if slug exists
    query = select(Organization).where(Organization.slug == slug)
    result = await session.execute(query)
    if result.scalar_one_or_none() is not None:
        raise SlugAlreadyExistsError(slug)

    org = Organization(
        name=data.name,
        slug=slug,
        status=OrganizationStatus.active.value,
    )
    session.add(org)
    await session.flush()
    await session.refresh(org)
    return org


async def get_organization_by_id(session: AsyncSession, organization_id: uuid.UUID) -> Optional[Organization]:
    """Retrieve an organization by its primary key ID."""
    query = select(Organization).where(Organization.id == organization_id)
    result = await session.execute(query)
    return result.scalar_one_or_none()
