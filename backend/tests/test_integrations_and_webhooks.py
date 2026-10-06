"""Comprehensive test suite for CUSTODE Integrations, Webhook Delivery Engine, and Signing."""

from datetime import datetime, timezone
import json
import time
from typing import Any, Dict
import uuid

import httpx
import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.audit.service import AuditEventType
from app.core.security import create_access_token
from app.db.models.integration import Integration, IntegrationProvider, IntegrationStatus
from app.db.models.membership import Membership, MembershipRole, MembershipStatus
from app.db.models.organization import Organization, OrganizationStatus
from app.db.models.user import User, UserStatus
from app.db.models.webhook_delivery import (
    AttemptStatus,
    DeliveryStatus,
    WebhookAttempt,
    WebhookDelivery,
)
from app.schemas.integration import IntegrationCreate, IntegrationUpdate
from app.services.integrations.crypto import (
    compute_webhook_signature,
    generate_webhook_signing_secret,
    get_secret_provider,
    verify_webhook_signature,
)
from app.services.integrations.delivery import (
    calculate_backoff_delay,
    dispatch_event_to_integrations,
    execute_delivery_attempt,
)
from app.services.integrations.events import (
    ALL_SUPPORTED_EVENTS,
    DISALLOWED_DISPATCH_EVENTS,
    format_webhook_payload,
    is_event_type_supported,
)
from app.services.integrations.service import (
    create_integration,
    get_delivery,
    get_integration,
    list_deliveries,
    list_integrations,
    retry_delivery,
    revoke_integration,
    suspend_integration,
    test_integration_ping as service_test_integration_ping,
    update_integration,
)
from app.services.integrations.ssrf import (
    SSRFProtectionError,
    set_custom_dns_resolver,
    validate_destination_address,
)
import pytest_asyncio


@pytest.fixture(autouse=True)
def mock_dns():
    """Ensure deterministic public DNS resolution for mocked tests."""
    def _mock_resolver(host: str, port: int):
        if host in ("example.com", "secops.example.com", "automation.example.com", "flaky.example.com", "failing.example.com"):
            return ["93.184.216.34"]  # Example.com public IPv4
        if host == "malicious-internal.attacker.com":
            return ["10.0.0.1"]  # Rebinding to internal IP
        return ["93.184.216.34"]

    set_custom_dns_resolver(_mock_resolver)
    yield
    set_custom_dns_resolver(None)


@pytest_asyncio.fixture
async def setup_org_and_users(async_session: AsyncSession):
    """Seed test organizations and users with RBAC roles."""
    org1 = Organization(
        id=uuid.uuid4(),
        name="Security SecOps Org",
        slug=f"secops-{uuid.uuid4().hex[:6]}",
        status=OrganizationStatus.active.value,
    )
    org2 = Organization(
        id=uuid.uuid4(),
        name="Tenant Isolated Org",
        slug=f"isolated-{uuid.uuid4().hex[:6]}",
        status=OrganizationStatus.active.value,
    )
    async_session.add_all([org1, org2])

    admin_user = User(
        id=uuid.uuid4(),
        email=f"admin_{uuid.uuid4().hex[:6]}@custode.ai",
        display_name="SecOps Admin",
        status=UserStatus.active.value,
    )
    viewer_user = User(
        id=uuid.uuid4(),
        email=f"viewer_{uuid.uuid4().hex[:6]}@custode.ai",
        display_name="SecOps Viewer",
        status=UserStatus.active.value,
    )
    async_session.add_all([admin_user, viewer_user])

    # Memberships
    m_admin = Membership(
        id=uuid.uuid4(),
        organization_id=org1.id,
        user_id=admin_user.id,
        role=MembershipRole.organization_admin.value,
        status=MembershipStatus.active.value,
    )
    m_viewer = Membership(
        id=uuid.uuid4(),
        organization_id=org1.id,
        user_id=viewer_user.id,
        role=MembershipRole.viewer.value,
        status=MembershipStatus.active.value,
    )
    async_session.add_all([m_admin, m_viewer])
    await async_session.commit()

    admin_token, _ = create_access_token(
        subject=str(admin_user.id),
        claims={"email": admin_user.email},
    )
    viewer_token, _ = create_access_token(
        subject=str(viewer_user.id),
        claims={"email": viewer_user.email},
    )

    return {
        "org1": org1,
        "org2": org2,
        "admin_user": admin_user,
        "viewer_user": viewer_user,
        "admin_token": admin_token,
        "viewer_token": viewer_token,
    }


# ==============================================================================
# 1. Cryptography and Signature Verification Tests
# ==============================================================================

def test_webhook_signing_and_constant_time_verification():
    """Verify HMAC-SHA256 signature generation and constant-time replay validation."""
    raw_secret, prefix, secret_hash = generate_webhook_signing_secret()
    assert raw_secret.startswith("cst_whsec_")
    assert prefix in raw_secret
    assert "$" in secret_hash

    payload = {
        "spec_version": "1.0",
        "event_id": str(uuid.uuid4()),
        "event_type": "DECISION_CREATED",
        "action": "allow",
    }
    now = int(time.time())
    header_val, sig_hex = compute_webhook_signature(payload, raw_secret, timestamp=now)

    assert f"t={now}" in header_val
    assert f"v1={sig_hex}" in header_val

    # Valid signature
    assert verify_webhook_signature(payload, header_val, raw_secret, tolerance_seconds=300) is True

    # Tampered payload fails
    tampered_payload = {**payload, "action": "deny"}
    assert verify_webhook_signature(tampered_payload, header_val, raw_secret) is False

    # Tampered secret fails
    wrong_secret = "cst_whsec_tampered_secret1234567890"
    assert verify_webhook_signature(payload, header_val, wrong_secret) is False

    # Expired timestamp (replay attack defense)
    expired_time = now - 400
    expired_header, _ = compute_webhook_signature(payload, raw_secret, timestamp=expired_time)
    assert verify_webhook_signature(payload, expired_header, raw_secret, tolerance_seconds=300) is False


def test_secret_provider_encryption_envelope():
    """Verify secret envelope encryption and decryption at rest."""
    provider = get_secret_provider()
    raw_secret, _, _ = generate_webhook_signing_secret()

    encrypted = provider.encrypt(raw_secret)
    assert encrypted.startswith("custode_enc_v1:")
    assert raw_secret not in encrypted

    decrypted = provider.decrypt(encrypted)
    assert decrypted == raw_secret


# ==============================================================================
# 2. SSRF Protection Tests
# ==============================================================================

def test_ssrf_blocks_private_and_loopback_destinations():
    """Verify SSRF boundary blocks private IPs, metadata endpoints, and non-HTTPS schemes."""
    # Loopback IP
    with pytest.raises(SSRFProtectionError, match="restricted or private range"):
        validate_destination_address("https://127.0.0.1/webhook")

    # Localhost hostname
    with pytest.raises(SSRFProtectionError, match="Prohibited webhook destination"):
        validate_destination_address("https://localhost/webhook")

    # AWS/Cloud Metadata IP
    with pytest.raises(SSRFProtectionError, match="restricted or private range|Prohibited webhook destination"):
        validate_destination_address("https://169.254.169.254/latest/meta-data")

    # Private RFC 1918 networks
    with pytest.raises(SSRFProtectionError, match="restricted or private range"):
        validate_destination_address("https://10.0.0.5/webhook")

    with pytest.raises(SSRFProtectionError, match="restricted or private range"):
        validate_destination_address("https://192.168.1.100/webhook")

    with pytest.raises(SSRFProtectionError, match="restricted or private range"):
        validate_destination_address("https://172.20.0.1/webhook")

    # DNS rebinding to internal IP
    with pytest.raises(SSRFProtectionError, match="resolves to restricted IP"):
        validate_destination_address("https://malicious-internal.attacker.com/webhook")

    # Unsafe schemes
    with pytest.raises(SSRFProtectionError, match="Production webhooks require HTTPS"):
        validate_destination_address("http://example.com/webhook", allow_insecure=False)

    with pytest.raises(SSRFProtectionError, match="Prohibited scheme|Unsupported scheme|require HTTPS"):
        validate_destination_address("ftp://example.com/webhook")

    with pytest.raises(SSRFProtectionError, match="Prohibited scheme|Unsupported scheme|require HTTPS"):
        validate_destination_address("file:///etc/passwd")


def test_ssrf_permits_public_destinations():
    """Verify valid public HTTPS destinations pass validation."""
    ips = validate_destination_address("https://example.com/webhook")
    assert len(ips) > 0
    assert ips == ["93.184.216.34"]


# ==============================================================================
# 3. Delivery Engine & Dispatch Tests
# ==============================================================================

@pytest.mark.asyncio
async def test_webhook_delivery_success_lifecycle(async_session: AsyncSession, setup_org_and_users):
    """Test 200 OK delivery records DELIVERED status and attempts."""
    org1 = setup_org_and_users["org1"]

    # Create integration
    data = IntegrationCreate(
        name="Production SecOps Webhook",
        url="https://secops.example.com/webhook",
        subscribed_events=["DECISION_CREATED", "APPROVAL_APPROVED"],
    )
    integration, raw_secret = await create_integration(
        session=async_session,
        organization_id=org1.id,
        data=data,
        allow_local=True,
    )
    await async_session.commit()

    # Mock HTTP 200 Response
    mock_transport = httpx.MockTransport(
        lambda request: httpx.Response(200, json={"status": "received", "id": "wh_123"})
    )
    mock_client = httpx.AsyncClient(transport=mock_transport)

    # Dispatch subscribed event
    deliveries = await dispatch_event_to_integrations(
        session=async_session,
        organization_id=org1.id,
        event_id=str(uuid.uuid4()),
        event_type="DECISION_CREATED",
        action="evaluate",
        outcome="success",
        data={"decision": "allow", "runtime_action_id": str(uuid.uuid4())},
        client=mock_client,
        allow_local=True,
    )
    await async_session.commit()

    assert len(deliveries) == 1
    deliv = deliveries[0]
    assert deliv.delivery_status == DeliveryStatus.DELIVERED.value
    assert deliv.attempt_count == 1
    assert deliv.response_status_code == 200
    assert deliv.delivered_at is not None
    assert deliv.next_retry_at is None

    # Check attempt record
    deliv_with_attempts = await get_delivery(async_session, org1.id, deliv.id)
    assert len(deliv_with_attempts.attempts) == 1
    attempt = deliv_with_attempts.attempts[0]
    assert attempt.status == AttemptStatus.SUCCESS.value
    assert attempt.response_status_code == 200


@pytest.mark.asyncio
async def test_webhook_delivery_terminal_4xx_failure(async_session: AsyncSession, setup_org_and_users):
    """Test 400 Client Error immediately terminates without retry."""
    org1 = setup_org_and_users["org1"]

    data = IntegrationCreate(
        name="Failing 400 Webhook",
        url="https://failing.example.com/webhook",
        subscribed_events=["DECISION_CREATED"],
    )
    integration, _ = await create_integration(
        session=async_session,
        organization_id=org1.id,
        data=data,
        allow_local=True,
    )
    await async_session.commit()

    # Mock HTTP 400 Response
    mock_transport = httpx.MockTransport(
        lambda request: httpx.Response(400, text="Bad Request: Malformed Payload")
    )
    mock_client = httpx.AsyncClient(transport=mock_transport)

    deliveries = await dispatch_event_to_integrations(
        session=async_session,
        organization_id=org1.id,
        event_id=str(uuid.uuid4()),
        event_type="DECISION_CREATED",
        action="evaluate",
        outcome="success",
        client=mock_client,
        allow_local=True,
    )
    await async_session.commit()

    assert len(deliveries) == 1
    deliv = deliveries[0]
    assert deliv.delivery_status == DeliveryStatus.FAILED.value
    assert deliv.attempt_count == 1
    assert deliv.response_status_code == 400
    assert deliv.next_retry_at is None  # Never retried


@pytest.mark.asyncio
async def test_webhook_delivery_5xx_retry_and_manual_retry(async_session: AsyncSession, setup_org_and_users):
    """Test 503 Service Unavailable triggers RETRYING with exponential backoff and manual retry."""
    org1 = setup_org_and_users["org1"]

    data = IntegrationCreate(
        name="Flaky Service Webhook",
        url="https://flaky.example.com/webhook",
        subscribed_events=["RISK_ASSESSMENT_CREATED"],
    )
    integration, _ = await create_integration(
        session=async_session,
        organization_id=org1.id,
        data=data,
        allow_local=True,
    )
    await async_session.commit()

    # 1. First attempt fails with 503
    mock_transport_503 = httpx.MockTransport(
        lambda request: httpx.Response(503, text="Service Unavailable")
    )
    client_503 = httpx.AsyncClient(transport=mock_transport_503)

    deliveries = await dispatch_event_to_integrations(
        session=async_session,
        organization_id=org1.id,
        event_id=str(uuid.uuid4()),
        event_type="RISK_ASSESSMENT_CREATED",
        action="assess",
        outcome="success",
        client=client_503,
        allow_local=True,
    )
    await async_session.commit()

    deliv = deliveries[0]
    assert deliv.delivery_status == DeliveryStatus.RETRYING.value
    assert deliv.attempt_count == 1
    assert deliv.next_retry_at is not None

    # 2. Manual retry when upstream recovers (200 OK)
    mock_transport_200 = httpx.MockTransport(
        lambda request: httpx.Response(200, json={"ok": True})
    )
    client_200 = httpx.AsyncClient(transport=mock_transport_200)

    updated_deliv = await retry_delivery(
        session=async_session,
        organization_id=org1.id,
        delivery_id=deliv.id,
        client=client_200,
        allow_local=True,
    )
    await async_session.commit()

    assert updated_deliv.delivery_status == DeliveryStatus.DELIVERED.value
    assert updated_deliv.attempt_count == 2
    assert updated_deliv.delivered_at is not None


@pytest.mark.asyncio
async def test_anti_recursion_guard(async_session: AsyncSession, setup_org_and_users):
    """Verify delivery engine explicitly prevents recursive loops for webhook events."""
    org1 = setup_org_and_users["org1"]

    deliveries = await dispatch_event_to_integrations(
        session=async_session,
        organization_id=org1.id,
        event_id=str(uuid.uuid4()),
        event_type="WEBHOOK_DELIVERED",
        action="delivered",
        outcome="success",
    )
    assert len(deliveries) == 0

    deliveries_failed = await dispatch_event_to_integrations(
        session=async_session,
        organization_id=org1.id,
        event_id=str(uuid.uuid4()),
        event_type="WEBHOOK_FAILED",
        action="failed",
        outcome="failure",
    )
    assert len(deliveries_failed) == 0


@pytest.mark.asyncio
async def test_test_integration_ping(async_session: AsyncSession, setup_org_and_users):
    """Verify diagnostic test ping event generation and execution."""
    org1 = setup_org_and_users["org1"]

    data = IntegrationCreate(
        name="Diagnostic Ping Webhook",
        url="https://secops.example.com/webhook",
        subscribed_events=["*"],
    )
    integration, _ = await create_integration(
        session=async_session,
        organization_id=org1.id,
        data=data,
        allow_local=True,
    )
    await async_session.commit()

    mock_transport = httpx.MockTransport(lambda req: httpx.Response(200, text="Ping ACK"))
    client = httpx.AsyncClient(transport=mock_transport)

    delivery = await service_test_integration_ping(
        session=async_session,
        organization_id=org1.id,
        integration_id=integration.id,
        client=client,
        allow_local=True,
    )
    await async_session.commit()

    assert delivery.event_type == AuditEventType.INTEGRATION_TEST_PING.value
    assert delivery.delivery_status == DeliveryStatus.DELIVERED.value
    assert delivery.payload["data"]["message"] == "CUSTODE Webhook verification ping"


# ==============================================================================
# 4. API Endpoints, RBAC, and Tenant Isolation Tests
# ==============================================================================

@pytest.mark.asyncio
async def test_api_integration_crud_and_secret_shown_once(async_client: httpx.AsyncClient, setup_org_and_users):
    """Test full integration lifecycle API and verify signing secret returned only once."""
    org1 = setup_org_and_users["org1"]
    admin_token = setup_org_and_users["admin_token"]
    viewer_token = setup_org_and_users["viewer_token"]

    headers_admin = {"Authorization": f"Bearer {admin_token}"}
    headers_viewer = {"Authorization": f"Bearer {viewer_token}"}

    # 1. Create integration (Admin required)
    payload = {
        "name": "SecOps Automation",
        "description": "Forward critical security events to automation router",
        "provider": "webhook",
        "url": "https://automation.example.com/alerts",
        "subscribed_events": ["DECISION_CREATED", "APPROVAL_CREATED"],
    }
    resp = await async_client.post(
        f"/api/v1/organizations/{org1.id}/integrations",
        json=payload,
        headers=headers_admin,
    )
    assert resp.status_code == 201
    created_data = resp.json()
    assert "signing_secret" in created_data
    assert created_data["signing_secret"].startswith("cst_whsec_")
    integ_id = created_data["id"]

    # 2. Viewer cannot create integrations (403 Forbidden)
    resp_viewer_create = await async_client.post(
        f"/api/v1/organizations/{org1.id}/integrations",
        json=payload,
        headers=headers_viewer,
    )
    assert resp_viewer_create.status_code == 403

    # 3. Agent API keys cannot perform human administrative operations (401 Unauthorized)
    headers_agent = {"Authorization": "Bearer cst_ag_dummykey1234567890_secretpart"}
    resp_agent_create = await async_client.post(
        f"/api/v1/organizations/{org1.id}/integrations",
        json=payload,
        headers=headers_agent,
    )
    assert resp_agent_create.status_code == 401

    # 4. GET integration details does NOT expose raw secret
    resp_get = await async_client.get(
        f"/api/v1/organizations/{org1.id}/integrations/{integ_id}",
        headers=headers_viewer,  # Viewer can view
    )
    assert resp_get.status_code == 200
    detail_data = resp_get.json()
    assert "signing_secret" not in detail_data
    assert "secret_prefix" in detail_data
    assert detail_data["secret_prefix"].startswith("cst_whsec_")

    # 5. Suspend integration
    resp_suspend = await async_client.post(
        f"/api/v1/organizations/{org1.id}/integrations/{integ_id}/suspend",
        headers=headers_admin,
    )
    assert resp_suspend.status_code == 200
    assert resp_suspend.json()["status"] == "suspended"

    # 6. Revoke integration
    resp_revoke = await async_client.post(
        f"/api/v1/organizations/{org1.id}/integrations/{integ_id}/revoke",
        headers=headers_admin,
    )
    assert resp_revoke.status_code == 200
    assert resp_revoke.json()["status"] == "revoked"

    # 7. Revoked integration cannot be suspended again (400 Bad Request)
    resp_re_suspend = await async_client.post(
        f"/api/v1/organizations/{org1.id}/integrations/{integ_id}/suspend",
        headers=headers_admin,
    )
    assert resp_re_suspend.status_code == 400


@pytest.mark.asyncio
async def test_api_tenant_isolation(async_client: httpx.AsyncClient, setup_org_and_users):
    """Test strict tenant isolation: Org B cannot access Org A's integrations or deliveries."""
    org1 = setup_org_and_users["org1"]
    org2 = setup_org_and_users["org2"]
    admin_token = setup_org_and_users["admin_token"]  # Belongs to org1

    headers = {"Authorization": f"Bearer {admin_token}"}

    # Accessing org2 with org1 credentials yields 403 Forbidden
    resp = await async_client.get(
        f"/api/v1/organizations/{org2.id}/integrations",
        headers=headers,
    )
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_api_supported_events(async_client: httpx.AsyncClient, setup_org_and_users):
    """Test retrieving controlled taxonomy of supported webhook events."""
    org1 = setup_org_and_users["org1"]
    viewer_token = setup_org_and_users["viewer_token"]
    headers = {"Authorization": f"Bearer {viewer_token}"}

    resp = await async_client.get(
        f"/api/v1/organizations/{org1.id}/integrations/supported-events",
        headers=headers,
    )
    assert resp.status_code == 200
    data = resp.json()
    assert "taxonomy" in data
    assert "all_events" in data
    assert "DECISION_CREATED" in data["all_events"]
    assert "AUTHENTICATION" in data["taxonomy"]
