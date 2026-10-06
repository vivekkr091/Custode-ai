"""Webhook Invariant, SSRF Defense, and Signature Verification Red Team Tests (Milestone 22)."""

import json
import time
import pytest
from httpx import AsyncClient

from app.services.integrations.crypto import compute_webhook_signature, verify_webhook_signature
from app.services.integrations.events import DISALLOWED_DISPATCH_EVENTS
from app.services.integrations.ssrf import (
    SSRFProtectionError,
    set_custom_dns_resolver,
    validate_destination_address,
)


@pytest.fixture(autouse=True)
def reset_dns_resolver():
    yield
    set_custom_dns_resolver(None)


def test_ssrf_defense_blocks_forbidden_destinations():
    """Verify that SSRF defense blocks loopback, private IPs, metadata IPs, and unsafe schemes."""
    dangerous_urls = [
        "http://127.0.0.1:8000/internal",
        "https://127.0.0.1:443/status",
        "http://localhost:5432",
        "http://169.254.169.254/latest/meta-data",
        "https://metadata.google.internal/computeMetadata/v1",
        "http://10.0.0.1/private",
        "http://192.168.1.1/admin",
        "http://172.16.0.1/corp",
        "ftp://example.com/file.txt",
        "gopher://127.0.0.1:6379",
        "file:///etc/passwd",
    ]

    for bad_url in dangerous_urls:
        with pytest.raises(SSRFProtectionError):
            validate_destination_address(bad_url, allow_insecure=True, allow_local=False)


def test_ssrf_defense_dns_rebinding_simulation():
    """Verify that when a domain resolves to a private IP, it is immediately blocked."""
    # Simulate DNS rebinding returning 127.0.0.1 for a public hostname
    set_custom_dns_resolver(lambda host, port: ["127.0.0.1"])

    with pytest.raises(SSRFProtectionError):
        validate_destination_address("https://rebind.attacker.com/webhook", allow_insecure=False, allow_local=False)


def test_webhook_cryptographic_signature_tampering_detection():
    """Verify constant-time HMAC signature verification detects payload or timestamp tampering."""
    secret = "cst_whsec_testprefix12_supersecretsigningkey1234567890"
    payload = {"spec_version": "1.0", "event_id": "evt-123", "event_type": "DECISION_CREATED"}
    payload_json = json.dumps(payload, separators=(",", ":"), sort_keys=True)
    now = int(time.time())

    sig_header, _ = compute_webhook_signature(payload_json, secret, timestamp=now)

    # 1. Valid payload and header succeeds
    assert verify_webhook_signature(payload, sig_header, secret) is True

    # 2. Tampered payload is detected
    tampered_payload = {**payload, "event_type": "APPROVAL_APPROVED"}
    assert verify_webhook_signature(tampered_payload, sig_header, secret) is False

    # 3. Tampered secret is detected
    assert verify_webhook_signature(payload, sig_header, "wrong_secret") is False

    # 4. Expired timestamp (>300s) is rejected
    expired_header, _ = compute_webhook_signature(payload_json, secret, timestamp=now - 400)
    assert verify_webhook_signature(payload, expired_header, secret, tolerance_seconds=300) is False

    # 5. Future timestamp (>60s) is rejected
    future_header, _ = compute_webhook_signature(payload_json, secret, timestamp=now + 120)
    assert verify_webhook_signature(payload, future_header, secret, tolerance_seconds=300) is False


def test_webhook_anti_recursion_disallowed_events():
    """Verify that delivery lifecycle events cannot be dispatched to webhooks."""
    for disallowed in DISALLOWED_DISPATCH_EVENTS:
        assert disallowed.startswith("WEBHOOK_") or disallowed.startswith("INTEGRATION_")
