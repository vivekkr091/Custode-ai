"""Service for human user authentication, password verification, and JWT session handling."""

from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple
import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.security import (
    create_access_token,
    decode_access_token,
    hash_password,
    verify_password,
    InvalidTokenError,
    TokenExpiredError,
)
from app.db.base import utc_now
from app.db.models.membership import Membership, MembershipRole, MembershipStatus
from app.db.models.organization import Organization, OrganizationStatus
from app.db.models.user import User, UserStatus
from app.schemas.auth import AuthTokenResponse
from app.schemas.membership import MembershipResponse
from app.schemas.organization import OrganizationResponse
from app.schemas.user import UserResponse
from app.services.audit import log_audit_event


class AuthenticationError(Exception):
    """Raised when authentication credentials or token validation fails."""
    def __init__(self, message: str = "Invalid credentials"):
        super().__init__(message)


class AuthorizationError(Exception):
    """Raised when an authenticated user lacks permissions or membership."""
    def __init__(self, message: str = "Insufficient permissions"):
        super().__init__(message)


DEV_ACCOUNTS = [
    {
        "email": "security.admin@custode.io",
        "display_name": "Security Admin",
        "password": "Custode#2026Admin!",
        "role": MembershipRole.organization_admin.value,
    },
    {
        "email": "analyst@custode.io",
        "display_name": "Security Analyst",
        "password": "Analyst#2026Secure!",
        "role": MembershipRole.security_analyst.value,
    },
    {
        "email": "auditor@custode.io",
        "display_name": "Security Auditor",
        "password": "Auditor#2026View!",
        "role": MembershipRole.viewer.value,
    },
]


async def bootstrap_development_environment(session: AsyncSession) -> None:
    """Bootstrap default organization and development users in development mode."""
    org_slug = "custode-cyber-defense"
    org_q = select(Organization).where(Organization.slug == org_slug)
    org_res = await session.execute(org_q)
    org = org_res.scalar_one_or_none()
    if org is None:
        org = Organization(
            name="CUSTODE Cyber Defense Corp",
            slug=org_slug,
            status=OrganizationStatus.active.value,
        )
        session.add(org)
        await session.flush()

    for acc in DEV_ACCOUNTS:
        user_q = select(User).where(User.email == acc["email"])
        user_res = await session.execute(user_q)
        user = user_res.scalar_one_or_none()
        if user is None:
            user = User(
                email=acc["email"],
                display_name=acc["display_name"],
                status=UserStatus.active.value,
                password_hash=hash_password(acc["password"]),
            )
            session.add(user)
            await session.flush()

        mem_q = select(Membership).where(
            Membership.user_id == user.id,
            Membership.organization_id == org.id,
        )
        mem_res = await session.execute(mem_q)
        mem = mem_res.scalar_one_or_none()
        if mem is None:
            mem = Membership(
                organization_id=org.id,
                user_id=user.id,
                role=acc["role"],
                status=MembershipStatus.active.value,
            )
            session.add(mem)
            await session.flush()


async def authenticate_user(
    session: AsyncSession,
    email: str,
    password: Optional[str] = None,
    organization_id: Optional[uuid.UUID] = None,
    request_ip: Optional[str] = None,
    user_agent: Optional[str] = None,
) -> Tuple[str, int, User, Optional[Organization], List[Membership]]:
    """Authenticate a human user with password verification or development mode bypass."""
    settings = get_settings()
    norm_email = email.strip().lower()

    # 1. Fetch user (or bootstrap dev identities if in development mode)
    user_q = select(User).where(User.email == norm_email)
    user_res = await session.execute(user_q)
    user = user_res.scalar_one_or_none()

    if user is None and (settings.AUTH_MODE == "development" or settings.DEMO_MODE):
        if norm_email in {a["email"] for a in DEV_ACCOUNTS}:
            await bootstrap_development_environment(session)
            user_res = await session.execute(user_q)
            user = user_res.scalar_one_or_none()

    if user is None:
        await log_audit_event(
            session=session,
            action="USER_LOGIN_FAILED",
            outcome="failure",
            metadata={"email": norm_email, "reason": "User not found"},
            ip_address=request_ip,
            user_agent=user_agent,
        )
        raise AuthenticationError("Invalid credentials")

    # 2. Check user status
    if user.status == UserStatus.suspended.value:
        await log_audit_event(
            session=session,
            action="USER_LOGIN_FAILED",
            user_id=user.id,
            outcome="failure",
            metadata={"reason": "User suspended"},
            ip_address=request_ip,
            user_agent=user_agent,
        )
        raise AuthenticationError("User account is suspended")

    if user.status == UserStatus.disabled.value or user.status != UserStatus.active.value:
        await log_audit_event(
            session=session,
            action="USER_LOGIN_FAILED",
            user_id=user.id,
            outcome="failure",
            metadata={"reason": "User disabled or inactive"},
            ip_address=request_ip,
            user_agent=user_agent,
        )
        raise AuthenticationError("User account is disabled")

    # 3. Verify password
    if settings.AUTH_MODE == "production":
        if not password or not user.password_hash:
            await log_audit_event(
                session=session,
                action="USER_LOGIN_FAILED",
                user_id=user.id,
                outcome="failure",
                metadata={"reason": "Missing or unconfigured password in production"},
                ip_address=request_ip,
                user_agent=user_agent,
            )
            raise AuthenticationError("Invalid credentials")
        if not verify_password(password, user.password_hash):
            await log_audit_event(
                session=session,
                action="USER_LOGIN_FAILED",
                user_id=user.id,
                outcome="failure",
                metadata={"reason": "Password mismatch"},
                ip_address=request_ip,
                user_agent=user_agent,
            )
            raise AuthenticationError("Invalid credentials")
    else:
        # Development mode: if password is provided and password_hash is set, check it; otherwise permit dev login
        if password and user.password_hash:
            if not verify_password(password, user.password_hash):
                await log_audit_event(
                    session=session,
                    action="USER_LOGIN_FAILED",
                    user_id=user.id,
                    outcome="failure",
                    metadata={"reason": "Password mismatch in dev mode"},
                    ip_address=request_ip,
                    user_agent=user_agent,
                )
                raise AuthenticationError("Invalid credentials")

    # 4. Load memberships and organizations
    mem_q = (
        select(Membership)
        .where(
            Membership.user_id == user.id,
            Membership.status == MembershipStatus.active.value,
        )
    )
    mem_res = await session.execute(mem_q)
    memberships = list(mem_res.scalars().all())

    # 5. Resolve active organization context
    active_org: Optional[Organization] = None
    active_role: Optional[str] = None

    if organization_id is not None:
        matched_mem = next((m for m in memberships if m.organization_id == organization_id), None)
        if matched_mem is None:
            raise AuthenticationError("User does not have an active membership in the requested organization")
        org_q = select(Organization).where(Organization.id == organization_id)
        org_res = await session.execute(org_q)
        active_org = org_res.scalar_one_or_none()
        active_role = matched_mem.role
    elif len(memberships) > 0:
        first_mem = memberships[0]
        org_q = select(Organization).where(Organization.id == first_mem.organization_id)
        org_res = await session.execute(org_q)
        active_org = org_res.scalar_one_or_none()
        active_role = first_mem.role

    # 6. Issue access token
    claims: Dict[str, Any] = {
        "email": user.email,
        "type": "human_user",
    }
    if active_org is not None:
        claims["org_id"] = str(active_org.id)
    if active_role is not None:
        claims["role"] = active_role

    token, expires_in = create_access_token(subject=str(user.id), claims=claims)

    # 7. Update last_login_at
    user.last_login_at = utc_now()
    session.add(user)
    await session.flush()

    # 8. Record audit log
    await log_audit_event(
        session=session,
        action="USER_LOGIN",
        organization_id=active_org.id if active_org else None,
        user_id=user.id,
        outcome="success",
        metadata={"email": user.email, "active_org": str(active_org.id) if active_org else None},
        ip_address=request_ip,
        user_agent=user_agent,
    )

    return token, expires_in, user, active_org, memberships


async def switch_user_organization(
    session: AsyncSession,
    user: User,
    target_org_id: uuid.UUID,
    request_ip: Optional[str] = None,
    user_agent: Optional[str] = None,
) -> Tuple[str, int, Organization, List[Membership]]:
    """Switch active organization context after validating membership."""
    mem_q = (
        select(Membership)
        .where(
            Membership.user_id == user.id,
            Membership.organization_id == target_org_id,
            Membership.status == MembershipStatus.active.value,
        )
    )
    mem_res = await session.execute(mem_q)
    matched_mem = mem_res.scalar_one_or_none()

    if matched_mem is None:
        raise AuthorizationError("User does not have an active membership in the target organization")

    org_q = select(Organization).where(Organization.id == target_org_id)
    org_res = await session.execute(org_q)
    org = org_res.scalar_one_or_none()
    if org is None or org.status != OrganizationStatus.active.value:
        raise AuthorizationError("Target organization is inactive or not found")

    # Issue fresh token with new org context
    claims = {
        "email": user.email,
        "type": "human_user",
        "org_id": str(org.id),
        "role": matched_mem.role,
    }
    token, expires_in = create_access_token(subject=str(user.id), claims=claims)

    # Load all user memberships
    all_mem_q = (
        select(Membership)
        .where(
            Membership.user_id == user.id,
            Membership.status == MembershipStatus.active.value,
        )
    )
    all_mem_res = await session.execute(all_mem_q)
    all_mems = list(all_mem_res.scalars().all())

    await log_audit_event(
        session=session,
        action="ORGANIZATION_SWITCHED",
        organization_id=org.id,
        user_id=user.id,
        outcome="success",
        metadata={"target_organization_id": str(target_org_id), "role": matched_mem.role},
        ip_address=request_ip,
        user_agent=user_agent,
    )

    return token, expires_in, org, all_mems


async def get_user_memberships(
    session: AsyncSession,
    user_id: uuid.UUID,
) -> List[Membership]:
    """Retrieve all active memberships for a user."""
    mem_q = (
        select(Membership)
        .where(
            Membership.user_id == user_id,
            Membership.status == MembershipStatus.active.value,
        )
    )
    mem_res = await session.execute(mem_q)
    return list(mem_res.scalars().all())
