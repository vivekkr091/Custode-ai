"""Authentication, identity resolution, and session management API endpoints."""

from typing import Any, Dict, List, Optional, Union
import uuid

from fastapi import APIRouter, Depends, Header, HTTPException, Request, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.core.security import API_KEY_PREFIX
from app.db.models.organization import Organization
from app.db.models.user import User
from app.db.session import get_db_session
from app.schemas.agent_credential import AuthenticatedAgent
from app.schemas.auth import (
    AuthenticatedUserContext,
    AuthTokenResponse,
    LoginRequest,
    LogoutResponse,
    SwitchOrganizationRequest,
)
from app.schemas.membership import MembershipResponse
from app.schemas.organization import OrganizationResponse
from app.schemas.user import UserResponse
from app.services.authentication import get_authenticated_agent
from app.services.audit import log_audit_event
from app.services.user_auth import (
    authenticate_user,
    get_user_memberships,
    switch_user_organization,
    AuthenticationError,
    AuthorizationError,
)

router = APIRouter(prefix="/auth", tags=["Authentication"])


from collections import defaultdict
import time

# In-memory sliding window rate limiter for login attempts (Milestone 22 Hardening)
_login_failures: Dict[str, List[float]] = defaultdict(list)
MAX_FAILED_LOGIN_ATTEMPTS = 10
FAILED_LOGIN_WINDOW_SECONDS = 60


def reset_login_rate_limiter() -> None:
    """Helper for testing to reset the login attempt rate limiter."""
    _login_failures.clear()


def _check_rate_limit(key: str) -> bool:
    now = time.time()
    cutoff = now - FAILED_LOGIN_WINDOW_SECONDS
    _login_failures[key] = [t for t in _login_failures[key] if t > cutoff]
    return len(_login_failures[key]) >= MAX_FAILED_LOGIN_ATTEMPTS


def _record_failure(key: str) -> None:
    _login_failures[key].append(time.time())


def _reset_failures(key: str) -> None:
    _login_failures.pop(key, None)


@router.post(
    "/login",
    response_model=AuthTokenResponse,
    summary="Human User Authentication / Login",
)
async def login_endpoint(
    request: Request,
    payload: LoginRequest,
    session: AsyncSession = Depends(get_db_session),
) -> AuthTokenResponse:
    """Authenticate a human user and issue an HS256 JWT access token."""
    client_ip = request.client.host if request.client else "unknown"
    rate_key = f"{client_ip}:{payload.email.strip().lower()}"

    if _check_rate_limit(rate_key):
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Too many failed login attempts. Please try again after 60 seconds.",
        )

    user_agent = request.headers.get("user-agent")

    try:
        token, expires_in, user, active_org, memberships = await authenticate_user(
            session=session,
            email=payload.email,
            password=payload.password,
            organization_id=payload.organization_id,
            request_ip=client_ip,
            user_agent=user_agent,
        )
        _reset_failures(rate_key)
        org_resp = OrganizationResponse.model_validate(active_org) if active_org else None
        active_role = memberships[0].role if memberships else None
        return AuthTokenResponse(
            access_token=token,
            token_type="bearer",
            expires_in=expires_in,
            user=UserResponse.model_validate(user),
            active_organization=org_resp,
            organization=org_resp,
            role=active_role,
            memberships=[MembershipResponse.model_validate(m) for m in memberships],
        )
    except AuthenticationError as e:
        _record_failure(rate_key)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=str(e),
            headers={"WWW-Authenticate": "Bearer"},
        )


@router.get(
    "/me",
    summary="Resolve Authenticated Identity (Human User or AI Agent)",
    response_model=Union[AuthenticatedAgent, AuthenticatedUserContext],
)
async def get_authenticated_identity(
    authorization: Optional[str] = Header(None, alias="Authorization"),
    x_user_id: Optional[uuid.UUID] = Header(None, alias="X-User-ID"),
    session: AsyncSession = Depends(get_db_session),
) -> Any:
    """Resolve authoritative caller identity.

    - If caller presents an Agent API Key (`cst_ag_...`): returns AuthenticatedAgent (Milestone 4).
    - If caller presents a Human User JWT: returns AuthenticatedUserContext (Milestone 14).
    """
    if authorization:
        parts = authorization.strip().split(" ", 1)
        if len(parts) == 2 and parts[0].lower() == "bearer":
            raw_token = parts[1].strip()
            # 1. AI Agent Path (Milestone 4)
            if raw_token.startswith(API_KEY_PREFIX):
                return await get_authenticated_agent(authorization=authorization, session=session)

    # 2. Human User Path (Milestone 14)
    user = await get_current_user(authorization=authorization, x_user_id=x_user_id, session=session)
    memberships = await get_user_memberships(session, user.id)

    # Resolve primary active organization
    active_org: Optional[Organization] = None
    active_mem = memberships[0] if memberships else None
    if active_mem:
        org_q = select(Organization).where(Organization.id == active_mem.organization_id)
        org_res = await session.execute(org_q)
        active_org = org_res.scalar_one_or_none()

    org_resp = OrganizationResponse.model_validate(active_org) if active_org else None
    mem_resp = MembershipResponse.model_validate(active_mem) if active_mem else None

    return AuthenticatedUserContext(
        id=user.id,
        user_id=user.id,
        email=user.email,
        display_name=user.display_name,
        status=user.status,
        last_login_at=user.last_login_at,
        active_organization=org_resp,
        organization_id=active_org.id if active_org else None,
        role=active_mem.role if active_mem else None,
        active_membership=mem_resp,
        memberships=[MembershipResponse.model_validate(m) for m in memberships],
    )


@router.post(
    "/switch-organization",
    response_model=AuthTokenResponse,
    summary="Switch Active Organization Context",
)
async def switch_organization_endpoint(
    request: Request,
    payload: SwitchOrganizationRequest,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db_session),
) -> AuthTokenResponse:
    """Issue a fresh JWT token scoped to another organization where the user has active membership."""
    client_ip = request.client.host if request.client else None
    user_agent = request.headers.get("user-agent")

    try:
        token, expires_in, org, memberships = await switch_user_organization(
            session=session,
            user=user,
            target_org_id=payload.organization_id,
            request_ip=client_ip,
            user_agent=user_agent,
        )
        org_resp = OrganizationResponse.model_validate(org)
        matched_mem = next((m for m in memberships if m.organization_id == org.id), None)
        active_role = matched_mem.role if matched_mem else None

        return AuthTokenResponse(
            access_token=token,
            token_type="bearer",
            expires_in=expires_in,
            user=UserResponse.model_validate(user),
            active_organization=org_resp,
            organization=org_resp,
            role=active_role,
            memberships=[MembershipResponse.model_validate(m) for m in memberships],
        )
    except AuthorizationError as e:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=str(e),
        )


@router.post(
    "/logout",
    response_model=LogoutResponse,
    summary="Human User Logout",
)
async def logout_endpoint(
    request: Request,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db_session),
) -> LogoutResponse:
    """Safely log out user session and record audit event."""
    client_ip = request.client.host if request.client else None
    user_agent = request.headers.get("user-agent")

    await log_audit_event(
        session=session,
        action="USER_LOGOUT",
        user_id=user.id,
        outcome="success",
        metadata={"email": user.email},
        ip_address=client_ip,
        user_agent=user_agent,
    )
    return LogoutResponse(message="Logged out successfully")
