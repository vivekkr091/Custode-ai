"""Service functions for Organization Membership entity."""

import uuid
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.membership import Membership, MembershipStatus
from app.db.models.organization import Organization
from app.db.models.user import User
from app.schemas.membership import MembershipCreate


class OrganizationNotFoundError(Exception):
    """Raised when an organization is not found."""
    def __init__(self, org_id: uuid.UUID):
        super().__init__(f"Organization '{org_id}' not found")
        self.org_id = org_id


class UserNotFoundError(Exception):
    """Raised when a user is not found."""
    def __init__(self, user_id: uuid.UUID):
        super().__init__(f"User '{user_id}' not found")
        self.user_id = user_id


class DuplicateMembershipError(Exception):
    """Raised when a user is already a member of an organization."""
    def __init__(self, org_id: uuid.UUID, user_id: uuid.UUID):
        super().__init__(f"User '{user_id}' is already a member of organization '{org_id}'")
        self.org_id = org_id
        self.user_id = user_id


async def create_membership(
    session: AsyncSession, organization_id: uuid.UUID, data: MembershipCreate
) -> Membership:
    """Create a new membership linking a User to an Organization."""
    # 1. Validate organization exists
    org_query = select(Organization).where(Organization.id == organization_id)
    org_res = await session.execute(org_query)
    if org_res.scalar_one_or_none() is None:
        raise OrganizationNotFoundError(organization_id)

    # 2. Validate user exists
    user_query = select(User).where(User.id == data.user_id)
    user_res = await session.execute(user_query)
    if user_res.scalar_one_or_none() is None:
        raise UserNotFoundError(data.user_id)

    # 3. Validate duplicate membership
    membership_query = select(Membership).where(
        Membership.organization_id == organization_id,
        Membership.user_id == data.user_id,
    )
    membership_res = await session.execute(membership_query)
    if membership_res.scalar_one_or_none() is not None:
        raise DuplicateMembershipError(organization_id, data.user_id)

    membership = Membership(
        organization_id=organization_id,
        user_id=data.user_id,
        role=data.role.value,
        status=MembershipStatus.active.value,
    )
    session.add(membership)
    await session.flush()
    await session.refresh(membership)
    return membership
