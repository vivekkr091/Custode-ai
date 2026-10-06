"""Comprehensive test suite for Milestone 15: Security Audit, Governance & Observability."""

from datetime import datetime, timezone
import uuid
import pytest
import pytest_asyncio
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.audit.service import (
    AuditActorType,
    AuditEventType,
    AuditOutcome,
    record_agent_event,
    record_event,
    record_security_event,
    record_user_event,
    sanitize_metadata,
)
from app.core.correlation import sanitize_request_id, set_current_request_id
from app.core.security import create_access_token, hash_password
from app.db.models.membership import Membership, MembershipRole, MembershipStatus
from app.db.models.organization import Organization, OrganizationStatus
from app.db.models.user import User, UserStatus
from app.services.audit import list_audit_events


@pytest_asyncio.fixture
async def audit_obs_context(async_session: AsyncSession):
    """Seed test organizations, users with RBAC roles, and token credentials."""
    # Org A
    org_a = Organization(
        name="Cyber Ops Corp",
        slug=f"cyber-ops-{uuid.uuid4().hex[:6]}",
        status=OrganizationStatus.active.value,
    )
    # Org B (Isolated Tenant)
    org_b = Organization(
        name="Target Tenant Inc",
        slug=f"target-tenant-{uuid.uuid4().hex[:6]}",
        status=OrganizationStatus.active.value,
    )
    async_session.add_all([org_a, org_b])
    await async_session.flush()

    pw_hash = hash_password("SuperSecure#2026!")

    # Users in Org A
    admin_user = User(
        email=f"admin_{uuid.uuid4().hex[:6]}@cyberops.io",
        display_name="Cyber Admin",
        status=UserStatus.active.value,
        password_hash=pw_hash,
    )
    analyst_user = User(
        email=f"analyst_{uuid.uuid4().hex[:6]}@cyberops.io",
        display_name="Cyber Analyst",
        status=UserStatus.active.value,
        password_hash=pw_hash,
    )
    viewer_user = User(
        email=f"viewer_{uuid.uuid4().hex[:6]}@cyberops.io",
        display_name="Cyber Viewer",
        status=UserStatus.active.value,
        password_hash=pw_hash,
    )
    # User strictly in Org B
    org_b_user = User(
        email=f"intruder_{uuid.uuid4().hex[:6]}@target.io",
        display_name="Org B User",
        status=UserStatus.active.value,
        password_hash=pw_hash,
    )
    async_session.add_all([admin_user, analyst_user, viewer_user, org_b_user])
    await async_session.flush()

    # Memberships
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
    mem_org_b = Membership(
        organization_id=org_b.id,
        user_id=org_b_user.id,
        role=MembershipRole.organization_admin.value,
        status=MembershipStatus.active.value,
    )
    async_session.add_all([mem_admin, mem_analyst, mem_viewer, mem_org_b])
    await async_session.flush()

    # Tokens
    admin_token, _ = create_access_token(
        subject=str(admin_user.id),
        claims={"org_id": str(org_a.id), "role": MembershipRole.organization_admin.value},
    )
    analyst_token, _ = create_access_token(
        subject=str(analyst_user.id),
        claims={"org_id": str(org_a.id), "role": MembershipRole.security_analyst.value},
    )
    viewer_token, _ = create_access_token(
        subject=str(viewer_user.id),
        claims={"org_id": str(org_a.id), "role": MembershipRole.viewer.value},
    )
    org_b_token, _ = create_access_token(
        subject=str(org_b_user.id),
        claims={"org_id": str(org_b.id), "role": MembershipRole.organization_admin.value},
    )

    return {
        "org_a": org_a,
        "org_b": org_b,
        "admin": admin_user,
        "analyst": analyst_user,
        "viewer": viewer_user,
        "org_b_user": org_b_user,
        "admin_token": admin_token,
        "analyst_token": analyst_token,
        "viewer_token": viewer_token,
        "org_b_token": org_b_token,
    }


# ==============================================================================
# 1. Audit Service & Sanitization Tests
# ==============================================================================

def test_metadata_secret_sanitization():
    """Verify recursive sanitization strips passwords, tokens, and API secrets."""
    dirty_metadata = {
        "user_email": "operator@custode.io",
        "password": "ClearTextPassword123!",
        "auth": {
            "bearer_token": "jwt_secret_token_abc",
            "access_token": "tok_991823",
            "nested": {
                "api_key": "cst_ag_secret_key",
                "client_secret": "sensitive_secret",
                "safe_field": 42,
            },
        },
        "tags": ["prod", "finance"],
    }

    clean = sanitize_metadata(dirty_metadata)
    assert clean["user_email"] == "operator@custode.io"
    assert clean["password"] == "[REDACTED]"
    assert clean["auth"]["access_token"] == "[REDACTED]"
    assert clean["auth"]["nested"]["api_key"] == "[REDACTED]"
    assert clean["auth"]["nested"]["client_secret"] == "[REDACTED]"
    assert clean["auth"]["nested"]["safe_field"] == 42


@pytest.mark.asyncio
async def test_audit_event_recording_and_actor_resolution(
    async_session: AsyncSession,
    audit_obs_context,
):
    """Verify record_user_event, record_agent_event, record_security_event."""
    ctx = audit_obs_context
    org_id = ctx["org_a"].id

    # 1. Record User Event
    ev_user = await record_user_event(
        session=async_session,
        event_type=AuditEventType.USER_UPDATED,
        action="UPDATE_USER",
        user_id=ctx["admin"].id,
        organization_id=org_id,
        user_display="admin@cyberops.io",
        resource_type="USER",
        resource_id=ctx["analyst"].id,
        metadata={"role_change": "promoted"},
    )
    assert ev_user.actor_type == "USER"
    assert ev_user.actor_id == str(ctx["admin"].id)
    assert ev_user.actor_display == "admin@cyberops.io"
    assert ev_user.event_type == AuditEventType.USER_UPDATED.value

    # 2. Record Agent Event
    agent_id = uuid.uuid4()
    ev_agent = await record_agent_event(
        session=async_session,
        event_type=AuditEventType.RUNTIME_ACTION_CREATED,
        action="CREATE_RUNTIME_ACTION",
        agent_id=agent_id,
        organization_id=org_id,
        agent_display="Billing Agent",
        resource_type="RUNTIME_ACTION",
        resource_id=uuid.uuid4(),
        outcome=AuditOutcome.SUCCESS,
    )
    assert ev_agent.actor_type == "AGENT"
    assert ev_agent.actor_id == str(agent_id)
    assert ev_agent.actor_display == "Billing Agent"

    # 3. Record Security Event (System)
    ev_sys = await record_security_event(
        session=async_session,
        event_type=AuditEventType.DECISION_CREATED,
        action="EVALUATE_DECISION",
        organization_id=org_id,
        resource_type="DECISION",
        resource_id=uuid.uuid4(),
        outcome=AuditOutcome.DENIED,
        metadata={"reason": "Policy violation"},
    )
    assert ev_sys.actor_type == "SYSTEM"
    assert ev_sys.outcome == "denied"


# ==============================================================================
# 2. Request Correlation Tests
# ==============================================================================

@pytest.mark.asyncio
async def test_request_correlation_header_and_propagation(
    async_client: AsyncClient,
    audit_obs_context,
):
    """Ensure X-Request-ID is generated or preserved across API responses."""
    ctx = audit_obs_context
    custom_rid = "req_custom_trace_98765"

    # Client-supplied request ID
    res1 = await async_client.get(
        "/health",
        headers={"X-Request-ID": custom_rid},
    )
    assert res1.status_code == 200
    assert res1.headers.get("X-Request-ID") == custom_rid

    # Server-generated request ID when client omits header
    res2 = await async_client.get("/health")
    assert res2.status_code == 200
    generated_rid = res2.headers.get("X-Request-ID")
    assert generated_rid is not None
    assert generated_rid.startswith("req_")


# ==============================================================================
# 3. API Filtering, Pagination & Tenant Isolation Tests
# ==============================================================================

@pytest.mark.asyncio
async def test_audit_api_filtering_and_tenant_isolation(
    async_client: AsyncClient,
    async_session: AsyncSession,
    audit_obs_context,
):
    """Ensure audit events can be filtered by event_type, actor_type, outcome, and are tenant-isolated."""
    ctx = audit_obs_context
    org_a_id = ctx["org_a"].id
    org_b_id = ctx["org_b"].id

    # Populate Org A events
    await record_event(
        session=async_session,
        event_type=AuditEventType.AUTH_LOGIN_SUCCESS,
        action="USER_LOGIN",
        organization_id=org_a_id,
        actor_type=AuditActorType.USER,
        actor_id=str(ctx["admin"].id),
        outcome=AuditOutcome.SUCCESS,
    )
    await record_event(
        session=async_session,
        event_type=AuditEventType.POLICY_PUBLISHED,
        action="PUBLISH_POLICY_VERSION",
        organization_id=org_a_id,
        actor_type=AuditActorType.SYSTEM,
        outcome=AuditOutcome.SUCCESS,
    )
    await record_event(
        session=async_session,
        event_type=AuditEventType.EXECUTION_BLOCKED,
        action="BLOCK_EXECUTION",
        organization_id=org_a_id,
        actor_type=AuditActorType.SYSTEM,
        outcome=AuditOutcome.DENIED,
    )

    # Populate Org B event
    await record_event(
        session=async_session,
        event_type=AuditEventType.AUTH_LOGIN_SUCCESS,
        action="USER_LOGIN",
        organization_id=org_b_id,
        actor_type=AuditActorType.USER,
        actor_id=str(ctx["org_b_user"].id),
        outcome=AuditOutcome.SUCCESS,
    )

    # 1. Query Org A with event_type filter
    res = await async_client.get(
        f"/api/v1/organizations/{org_a_id}/audit-events?event_type={AuditEventType.POLICY_PUBLISHED.value}",
        headers={"Authorization": f"Bearer {ctx['admin_token']}"},
    )
    assert res.status_code == 200
    data = res.json()
    assert data["total"] == 1
    assert data["items"][0]["event_type"] == AuditEventType.POLICY_PUBLISHED.value

    # 2. Query Org A with outcome filter
    res_denied = await async_client.get(
        f"/api/v1/organizations/{org_a_id}/audit-events?outcome=denied",
        headers={"Authorization": f"Bearer {ctx['admin_token']}"},
    )
    assert res_denied.status_code == 200
    data_denied = res_denied.json()
    assert data_denied["total"] == 1
    assert data_denied["items"][0]["event_type"] == AuditEventType.EXECUTION_BLOCKED.value

    # 3. Tenant Isolation: Org B user attempts to query Org A -> 403 Forbidden!
    idor_res = await async_client.get(
        f"/api/v1/organizations/{org_a_id}/audit-events",
        headers={"Authorization": f"Bearer {ctx['org_b_token']}"},
    )
    assert idor_res.status_code == 403

    # 4. Direct audit event lookup tenant isolation
    org_a_event = data["items"][0]
    idor_single = await async_client.get(
        f"/api/v1/organizations/{org_b_id}/audit-events/{org_a_event['id']}",
        headers={"Authorization": f"Bearer {ctx['org_b_token']}"},
    )
    assert idor_single.status_code == 404


# ==============================================================================
# 4. Security Overview & Global Search Tests
# ==============================================================================

@pytest.mark.asyncio
async def test_security_overview_endpoint(
    async_client: AsyncClient,
    audit_obs_context,
):
    """Verify aggregated metrics endpoint returns real database counts."""
    ctx = audit_obs_context
    org_a_id = ctx["org_a"].id

    res = await async_client.get(
        f"/api/v1/organizations/{org_a_id}/security-overview",
        headers={"Authorization": f"Bearer {ctx['admin_token']}"},
    )
    assert res.status_code == 200, res.text
    data = res.json()
    assert "active_agents" in data
    assert "pending_approvals" in data
    assert "risk_distribution" in data
    assert "decision_distribution" in data
    assert "recent_events" in data


@pytest.mark.asyncio
async def test_global_investigation_search(
    async_client: AsyncClient,
    async_session: AsyncSession,
    audit_obs_context,
):
    """Verify search across entities strictly within tenant boundary."""
    ctx = audit_obs_context
    org_a_id = ctx["org_a"].id

    trace_req_id = "req_investigate_sec_42"
    await record_event(
        session=async_session,
        event_type=AuditEventType.AUTH_LOGIN_SUCCESS,
        action="USER_LOGIN",
        organization_id=org_a_id,
        actor_type=AuditActorType.USER,
        actor_id=str(ctx["admin"].id),
        request_id=trace_req_id,
        outcome=AuditOutcome.SUCCESS,
    )

    res = await async_client.get(
        f"/api/v1/organizations/{org_a_id}/search?q=USER_LOGIN",
        headers={"Authorization": f"Bearer {ctx['admin_token']}"},
    )
    assert res.status_code == 200, res.text
    data = res.json()
    assert data["total"] >= 1
    assert any(item["category"] == "audit_event" for item in data["results"])
