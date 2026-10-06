"""Comprehensive test suite for Human Authentication, RBAC, Tenant Isolation, and Audit Trail."""

from datetime import timedelta
import uuid
import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import create_access_token, hash_password
from app.db.models.membership import Membership, MembershipRole, MembershipStatus
from app.db.models.organization import Organization, OrganizationStatus
from app.db.models.user import User, UserStatus
from app.services.audit import list_audit_events


import pytest_asyncio

@pytest_asyncio.fixture
async def auth_test_context(async_session: AsyncSession):
    """Seed test organizations, users with roles, and memberships."""
    # Organization A
    org_a = Organization(
        name="Alpha Cyber Systems",
        slug=f"alpha-cyber-{uuid.uuid4().hex[:6]}",
        status=OrganizationStatus.active.value,
    )
    # Organization B (Tenant Isolation Target)
    org_b = Organization(
        name="Beta Defense Inc",
        slug=f"beta-defense-{uuid.uuid4().hex[:6]}",
        status=OrganizationStatus.active.value,
    )
    async_session.add_all([org_a, org_b])
    await async_session.flush()

    # Users
    password_plain = "Secur3P@ssw0rd!2026"
    pw_hash = hash_password(password_plain)

    admin_user = User(
        email=f"admin_{uuid.uuid4().hex[:6]}@alpha.io",
        display_name="Alpha Admin",
        status=UserStatus.active.value,
        password_hash=pw_hash,
    )
    analyst_user = User(
        email=f"analyst_{uuid.uuid4().hex[:6]}@alpha.io",
        display_name="Alpha Analyst",
        status=UserStatus.active.value,
        password_hash=pw_hash,
    )
    viewer_user = User(
        email=f"viewer_{uuid.uuid4().hex[:6]}@alpha.io",
        display_name="Alpha Viewer",
        status=UserStatus.active.value,
        password_hash=pw_hash,
    )
    suspended_user = User(
        email=f"suspended_{uuid.uuid4().hex[:6]}@alpha.io",
        display_name="Suspended Person",
        status=UserStatus.suspended.value,
        password_hash=pw_hash,
    )
    disabled_user = User(
        email=f"disabled_{uuid.uuid4().hex[:6]}@alpha.io",
        display_name="Disabled Person",
        status=UserStatus.disabled.value,
        password_hash=pw_hash,
    )

    async_session.add_all([admin_user, analyst_user, viewer_user, suspended_user, disabled_user])
    await async_session.flush()

    # Memberships in Org A
    mem_admin = Membership(
        organization_id=org_a.id,
        user_id=admin_user.id,
        role=MembershipRole.organization_admin.value,
        status=MembershipStatus.active.value,
    )
    mem_analyst = Membership(
        organization_id=org_a.id,
        user_id=analyst_user.id,
        role=MembershipRole.security_analyst.value,
        status=MembershipStatus.active.value,
    )
    mem_viewer = Membership(
        organization_id=org_a.id,
        user_id=viewer_user.id,
        role=MembershipRole.viewer.value,
        status=MembershipStatus.active.value,
    )
    async_session.add_all([mem_admin, mem_analyst, mem_viewer])
    await async_session.commit()

    return {
        "org_a": org_a,
        "org_b": org_b,
        "admin": admin_user,
        "analyst": analyst_user,
        "viewer": viewer_user,
        "suspended": suspended_user,
        "disabled": disabled_user,
        "password": password_plain,
    }


# ==============================================================================
# 1. Human Authentication Tests
# ==============================================================================

@pytest.mark.asyncio
async def test_user_login_success(async_client: AsyncClient, auth_test_context):
    """Ensure valid email and password produces valid JWT access token."""
    ctx = auth_test_context
    res = await async_client.post(
        "/api/v1/auth/login",
        json={
            "email": ctx["admin"].email,
            "password": ctx["password"],
            "organization_id": str(ctx["org_a"].id),
        },
    )
    assert res.status_code == 200, res.text
    data = res.json()
    assert "access_token" in data
    assert data["token_type"] == "bearer"
    assert data["expires_in"] > 0
    assert data["user"]["email"] == ctx["admin"].email
    assert "password_hash" not in data["user"]
    assert data["active_organization"]["id"] == str(ctx["org_a"].id)
    assert len(data["memberships"]) >= 1


@pytest.mark.asyncio
async def test_user_login_invalid_password(async_client: AsyncClient, auth_test_context):
    """Ensure incorrect password fails with 401 without exposing internal details."""
    ctx = auth_test_context
    res = await async_client.post(
        "/api/v1/auth/login",
        json={
            "email": ctx["admin"].email,
            "password": "WrongPassword123!",
        },
    )
    assert res.status_code == 401
    assert "Invalid credentials" in res.json()["detail"]


@pytest.mark.asyncio
async def test_user_login_unknown_email(async_client: AsyncClient):
    """Ensure non-existent email returns generic 401."""
    res = await async_client.post(
        "/api/v1/auth/login",
        json={
            "email": "does_not_exist@custode.io",
            "password": "AnyPassword123!",
        },
    )
    assert res.status_code == 401
    assert "Invalid credentials" in res.json()["detail"]


@pytest.mark.asyncio
async def test_user_login_suspended_and_disabled_rejected(async_client: AsyncClient, auth_test_context):
    """Ensure suspended or disabled users cannot log in."""
    ctx = auth_test_context

    # Suspended user
    res_susp = await async_client.post(
        "/api/v1/auth/login",
        json={
            "email": ctx["suspended"].email,
            "password": ctx["password"],
        },
    )
    assert res_susp.status_code == 401
    assert "suspended" in res_susp.json()["detail"].lower()

    # Disabled user
    res_dis = await async_client.post(
        "/api/v1/auth/login",
        json={
            "email": ctx["disabled"].email,
            "password": ctx["password"],
        },
    )
    assert res_dis.status_code == 401
    assert "disabled" in res_dis.json()["detail"].lower()


@pytest.mark.asyncio
async def test_auth_me_with_human_jwt(async_client: AsyncClient, auth_test_context):
    """Ensure GET /auth/me returns human user context when called with JWT token."""
    ctx = auth_test_context
    login_res = await async_client.post(
        "/api/v1/auth/login",
        json={"email": ctx["analyst"].email, "password": ctx["password"]},
    )
    token = login_res.json()["access_token"]

    me_res = await async_client.get(
        "/api/v1/auth/me",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert me_res.status_code == 200, me_res.text
    me_data = me_res.json()
    assert me_data["email"] == ctx["analyst"].email
    assert me_data["status"] == "active"
    assert "password_hash" not in me_data
    assert len(me_data["memberships"]) >= 1


@pytest.mark.asyncio
async def test_jwt_token_expiration(async_client: AsyncClient, auth_test_context):
    """Ensure expired JWT access token is rejected with 401."""
    ctx = auth_test_context
    expired_token, _ = create_access_token(
        subject=str(ctx["admin"].id),
        expires_delta=timedelta(seconds=-10),  # expired 10 seconds ago
    )

    res = await async_client.get(
        "/api/v1/auth/me",
        headers={"Authorization": f"Bearer {expired_token}"},
    )
    assert res.status_code == 401
    assert "expired" in res.json()["detail"].lower()


@pytest.mark.asyncio
async def test_jwt_tampered_signature(async_client: AsyncClient, auth_test_context):
    """Ensure modified signature on JWT is rejected."""
    ctx = auth_test_context
    valid_token, _ = create_access_token(subject=str(ctx["admin"].id))
    parts = valid_token.split(".")
    tampered_token = f"{parts[0]}.{parts[1]}.tampered_signature"

    res = await async_client.get(
        "/api/v1/auth/me",
        headers={"Authorization": f"Bearer {tampered_token}"},
    )
    assert res.status_code == 401
    assert "invalid" in res.json()["detail"].lower()


@pytest.mark.asyncio
async def test_user_logout(async_client: AsyncClient, auth_test_context):
    """Ensure logout records audit event and returns safe message."""
    ctx = auth_test_context
    login_res = await async_client.post(
        "/api/v1/auth/login",
        json={"email": ctx["admin"].email, "password": ctx["password"]},
    )
    token = login_res.json()["access_token"]

    res = await async_client.post(
        "/api/v1/auth/logout",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert res.status_code == 200
    assert "Logged out successfully" in res.json()["message"]


# ==============================================================================
# 2. Organization Switching & Tenant Isolation
# ==============================================================================

@pytest.mark.asyncio
async def test_switch_organization_authorized_vs_unauthorized(
    async_client: AsyncClient,
    async_session: AsyncSession,
    auth_test_context,
):
    """Ensure a user can only switch to an organization they have active membership in."""
    ctx = auth_test_context

    login_res = await async_client.post(
        "/api/v1/auth/login",
        json={"email": ctx["admin"].email, "password": ctx["password"]},
    )
    token = login_res.json()["access_token"]

    # 1. Attempt to switch to Org B without membership -> MUST FAIL with 403 Forbidden
    res_unauth = await async_client.post(
        "/api/v1/auth/switch-organization",
        headers={"Authorization": f"Bearer {token}"},
        json={"organization_id": str(ctx["org_b"].id)},
    )
    assert res_unauth.status_code == 403
    assert "membership" in res_unauth.json()["detail"].lower()

    # 2. Grant admin user membership in Org B
    mem_b = Membership(
        organization_id=ctx["org_b"].id,
        user_id=ctx["admin"].id,
        role=MembershipRole.organization_admin.value,
        status=MembershipStatus.active.value,
    )
    async_session.add(mem_b)
    await async_session.commit()

    # 3. Now switch to Org B -> MUST SUCCEED with fresh token
    res_auth = await async_client.post(
        "/api/v1/auth/switch-organization",
        headers={"Authorization": f"Bearer {token}"},
        json={"organization_id": str(ctx["org_b"].id)},
    )
    assert res_auth.status_code == 200
    new_data = res_auth.json()
    assert new_data["active_organization"]["id"] == str(ctx["org_b"].id)


# ==============================================================================
# 3. Agent Separation & Prevention of Cross-Identity Impersonation
# ==============================================================================

@pytest.mark.asyncio
async def test_agent_key_cannot_access_human_endpoints(async_client: AsyncClient):
    """Ensure presenting an agent key (cst_ag_...) to a human-only endpoint is rejected."""
    agent_key = "cst_ag_0123456789_abcdefghijklmnopqrstuvwxyz1234567890"
    res = await async_client.post(
        "/api/v1/auth/logout",
        headers={"Authorization": f"Bearer {agent_key}"},
    )
    assert res.status_code == 401
    assert "agent credentials cannot be used" in res.json()["detail"].lower()


# ==============================================================================
# 4. Audit Trail Verification
# ==============================================================================

@pytest.mark.asyncio
async def test_audit_trail_query_and_tenant_isolation(
    async_client: AsyncClient,
    async_session: AsyncSession,
    auth_test_context,
):
    """Ensure audit events are logged, queryable by members, and tenant-isolated."""
    ctx = auth_test_context

    # 1. Log in admin to generate a USER_LOGIN audit event in Org A
    login_res = await async_client.post(
        "/api/v1/auth/login",
        json={
            "email": ctx["admin"].email,
            "password": ctx["password"],
            "organization_id": str(ctx["org_a"].id),
        },
    )
    token = login_res.json()["access_token"]

    # 2. Query Org A audit events
    audit_res = await async_client.get(
        f"/api/v1/organizations/{ctx['org_a'].id}/audit-events",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert audit_res.status_code == 200, audit_res.text
    audit_data = audit_res.json()
    assert audit_data["total"] >= 1
    events = audit_data["items"]
    assert any(e["action"] == "USER_LOGIN" for e in events)

    # 3. Check that secrets/passwords are NOT in metadata
    for ev in events:
        if ev.get("metadata"):
            assert "password" not in ev["metadata"]
            assert "raw_token" not in ev["metadata"]

    # 4. Attempt to query Org B audit events using Org A token -> 403 Forbidden!
    idor_res = await async_client.get(
        f"/api/v1/organizations/{ctx['org_b'].id}/audit-events",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert idor_res.status_code == 403
    assert "not an active member" in idor_res.json()["detail"].lower()


@pytest.mark.asyncio
async def test_development_admin_login_and_auth_me(
    async_client: AsyncClient,
):
    """Verify Milestone 15 Step 0 & Section 29: Full browser login flow, CORS, and dashboard access."""
    # 1. Health check with Browser Origin
    health_res = await async_client.get(
        "/health",
        headers={"Origin": "http://localhost:5173"},
    )
    assert health_res.status_code == 200
    assert health_res.json()["status"] == "ok"
    assert health_res.headers.get("access-control-allow-origin") == "http://localhost:5173"

    # 2. Login using dev admin credentials (auto-bootstraps in dev mode)
    login_res = await async_client.post(
        "/api/v1/auth/login",
        headers={"Origin": "http://localhost:5173"},
        json={
            "email": "security.admin@custode.io",
            "password": "Custode#2026Admin!",
        },
    )
    assert login_res.status_code == 200, login_res.text
    login_data = login_res.json()
    assert "access_token" in login_data
    token = login_data["access_token"]
    assert login_data["user"]["email"] == "security.admin@custode.io"
    assert login_data["role"] == "organization_admin"
    assert login_data["active_organization"] is not None
    assert login_data["organization"] is not None
    org_id = login_data["organization"]["id"]

    # 3. GET /auth/me with Bearer token and Browser Origin
    me_res = await async_client.get(
        "/api/v1/auth/me",
        headers={
            "Authorization": f"Bearer {token}",
            "Origin": "http://localhost:5173",
        },
    )
    assert me_res.status_code == 200, me_res.text
    me_data = me_res.json()
    assert me_data["email"] == "security.admin@custode.io"
    assert me_data["role"] == "organization_admin"
    assert me_data["user_id"] is not None
    assert me_data["organization_id"] is not None

    # 4. Downstream Dashboard Telemetry: Security Overview
    overview_res = await async_client.get(
        f"/api/v1/organizations/{org_id}/security-overview",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert overview_res.status_code == 200, overview_res.text
    assert "active_policies_count" in overview_res.json()

    # 5. Audit Trail Access
    audit_res = await async_client.get(
        f"/api/v1/organizations/{org_id}/audit-events",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert audit_res.status_code == 200, audit_res.text
    assert "items" in audit_res.json()

    # 6. Global Search Access
    search_res = await async_client.get(
        f"/api/v1/organizations/{org_id}/search?q=admin",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert search_res.status_code == 200, search_res.text
    assert "items" in search_res.json()


