"""Tests for CUSTODE SDK Integrations, Webhook Deliveries, and Signature Verification."""

from datetime import datetime, timezone
import json
import time
import uuid

import httpx
import pytest

from custode import (
    AsyncCUSTODEClient,
    CUSTODEClient,
    Integration,
    IntegrationCreateResponse,
    IntegrationList,
    SupportedEvents,
    WebhookAttempt,
    WebhookDelivery,
    WebhookDeliveryList,
    verify_webhook_signature,
)


def test_sdk_webhook_signature_verification():
    """Test HMAC-SHA256 signature verification in custode.security."""
    secret = "cst_whsec_1234567890ab_supersecretkey12345"
    payload = {
        "spec_version": "1.0",
        "event_id": "evt-001",
        "event_type": "DECISION_CREATED",
        "action": "allow",
    }
    now = int(time.time())

    # Build signature header
    import hashlib
    import hmac

    payload_json = json.dumps(payload, separators=(",", ":"), sort_keys=True)
    canonical = f"t={now}.{payload_json}".encode("utf-8")
    sig = hmac.new(secret.encode("utf-8"), canonical, hashlib.sha256).hexdigest()
    header = f"t={now},v1={sig}"

    # Valid check
    assert verify_webhook_signature(payload, header, secret) is True
    assert verify_webhook_signature(payload_json.encode("utf-8"), header, secret) is True

    # Tampered payload
    tampered = {**payload, "action": "deny"}
    assert verify_webhook_signature(tampered, header, secret) is False

    # Tampered secret
    assert verify_webhook_signature(payload, header, "wrong_secret") is False

    # Expired timestamp (300s window)
    expired_header = f"t={now - 400},v1={sig}"
    assert verify_webhook_signature(payload, expired_header, secret, tolerance_seconds=300) is False


def test_integration_model_parsing():
    """Verify deserialization and serialization of Integration and WebhookDelivery models."""
    integ_id = uuid.uuid4()
    org_id = uuid.uuid4()
    now_iso = datetime.now(timezone.utc).isoformat()

    raw_data = {
        "id": str(integ_id),
        "organization_id": str(org_id),
        "name": "SIEM Connector",
        "description": "Splunk webhook",
        "provider": "webhook",
        "status": "active",
        "url": "https://siem.corp.internal/events",
        "secret_prefix": "cst_whsec_123",
        "subscribed_events": ["DECISION_CREATED", "APPROVAL_APPROVED"],
        "headers": {"X-Custom": "HeaderValue"},
        "last_delivery_at": now_iso,
        "created_at": now_iso,
        "updated_at": now_iso,
    }

    integration = Integration.model_validate(raw_data)
    assert integration.name == "SIEM Connector"
    assert integration.status == "active"
    assert len(integration.subscribed_events) == 2

    # IntegrationList
    list_data = {"items": [raw_data], "total": 1, "limit": 50, "offset": 0}
    integ_list = IntegrationList.model_validate(list_data)
    assert len(integ_list) == 1
    assert integ_list[0].id == integ_id

    # WebhookDelivery
    deliv_id = uuid.uuid4()
    raw_deliv = {
        "id": str(deliv_id),
        "organization_id": str(org_id),
        "integration_id": str(integ_id),
        "event_id": "evt-123",
        "event_type": "DECISION_CREATED",
        "request_id": "req-999",
        "delivery_status": "delivered",
        "attempt_count": 1,
        "max_attempts": 3,
        "payload": {"event": "data"},
        "response_status_code": 200,
        "sanitized_response_summary": "HTTP 200 Success",
        "delivered_at": now_iso,
        "created_at": now_iso,
        "attempts": [
            {
                "id": str(uuid.uuid4()),
                "delivery_id": str(deliv_id),
                "attempt_number": 1,
                "status": "success",
                "response_status_code": 200,
                "duration_ms": 45,
                "attempted_at": now_iso,
            }
        ],
    }
    delivery = WebhookDelivery.model_validate(raw_deliv)
    assert delivery.delivery_status == "delivered"
    assert delivery.attempt_count == 1
    assert len(delivery.attempts or []) == 1


def test_sync_integrations_resource():
    """Verify CUSTODEClient.integrations resource calls via mocked HTTP transport."""
    org_id = str(uuid.uuid4())
    integ_id = str(uuid.uuid4())
    now_iso = datetime.now(timezone.utc).isoformat()

    def handler(request: httpx.Request) -> httpx.Response:
        if request.method == "GET" and "/supported-events" in request.url.path:
            return httpx.Response(
                200,
                json={"taxonomy": {"AUTH": {"description": "Auth", "events": ["AUTH_LOGIN_SUCCESS"]}}, "all_events": ["AUTH_LOGIN_SUCCESS"]},
            )
        if request.method == "POST" and request.url.path.endswith("/integrations"):
            return httpx.Response(
                201,
                json={
                    "id": integ_id,
                    "organization_id": org_id,
                    "name": "Test Webhook",
                    "provider": "webhook",
                    "status": "active",
                    "url": "https://example.com/alerts",
                    "secret_prefix": "cst_whsec_abc",
                    "signing_secret": "cst_whsec_abc_rawsecret12345",
                    "warning": "Save this secret now",
                    "subscribed_events": ["DECISION_CREATED"],
                    "created_at": now_iso,
                    "updated_at": now_iso,
                },
            )
        if request.method == "GET" and request.url.path.endswith("/integrations"):
            return httpx.Response(
                200,
                json={"items": [], "total": 0, "limit": 50, "offset": 0},
            )
        return httpx.Response(404, json={"detail": "Not found"})

    client = CUSTODEClient(
        base_url="http://localhost:8000",
        api_key="cst_ag_abcdef0123_testsecretvalue1234567890",
        organization_id=org_id,
        http_client=httpx.Client(base_url="http://localhost:8000", transport=httpx.MockTransport(handler)),
    )

    # 1. Create integration
    created = client.integrations.create(
        name="Test Webhook",
        url="https://example.com/alerts",
        subscribed_events=["DECISION_CREATED"],
    )
    assert created.name == "Test Webhook"
    assert created.signing_secret == "cst_whsec_abc_rawsecret12345"

    # 2. List integrations
    integ_list = client.integrations.list()
    assert len(integ_list) == 0

    # 3. Supported events
    events = client.integrations.get_supported_events()
    assert "AUTH_LOGIN_SUCCESS" in events.all_events


@pytest.mark.asyncio
async def test_async_integrations_resource():
    """Verify AsyncCUSTODEClient.integrations resource calls via mocked async transport."""
    org_id = str(uuid.uuid4())
    integ_id = str(uuid.uuid4())
    deliv_id = str(uuid.uuid4())
    now_iso = datetime.now(timezone.utc).isoformat()

    def handler(request: httpx.Request) -> httpx.Response:
        if request.method == "POST" and request.url.path.endswith("/test"):
            return httpx.Response(
                200,
                json={
                    "id": deliv_id,
                    "organization_id": org_id,
                    "integration_id": integ_id,
                    "event_type": "INTEGRATION_TEST_PING",
                    "delivery_status": "delivered",
                    "attempt_count": 1,
                    "max_attempts": 1,
                    "payload": {"test": True},
                    "response_status_code": 200,
                    "created_at": now_iso,
                },
            )
        return httpx.Response(404, json={"detail": "Not found"})

    client = AsyncCUSTODEClient(
        base_url="http://localhost:8000",
        api_key="cst_ag_abcdef0123_testsecretvalue1234567890",
        organization_id=org_id,
        http_client=httpx.AsyncClient(base_url="http://localhost:8000", transport=httpx.MockTransport(handler)),
    )

    deliv = await client.integrations.test_ping(integ_id)
    assert deliv.delivery_status == "delivered"
    assert deliv.event_type == "INTEGRATION_TEST_PING"
    await client.aclose()
