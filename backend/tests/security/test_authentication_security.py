"""Authentication and Session Security Red Team Tests (Milestone 22)."""

from datetime import datetime, timedelta, timezone
import json
import uuid
import pytest
from httpx import AsyncClient

from app.api.v1.endpoints.auth import reset_login_rate_limiter
from app.core.config import get_settings
from app.core.security import _base64url_encode, create_access_token, generate_agent_api_key
from app.db.models.membership import MembershipRole


@pytest.fixture(autouse=True)
def reset_rate_limit():
    """Reset the login attempt rate limiter between tests."""
    reset_login_rate_limiter()


@pytest.mark.asyncio
async def test_auth_missing_header_rejected(async_client: AsyncClient):
    """Verify that protected endpoints reject requests missing Authorization headers."""
    resp = await async_client.get("/api/v1/auth/me")
    assert resp.status_code == 401
    assert "Missing Authorization header" in resp.json()["detail"]


@pytest.mark.asyncio
async def test_auth_malformed_bearer_rejected(async_client: AsyncClient):
    """Verify rejection of malformed Authorization Bearer header formats."""
    # Only "Bearer" without token
    resp = await async_client.get(
        "/api/v1/auth/me",
        headers={"Authorization": "Bearer"},
    )
    assert resp.status_code == 401
    assert "Malformed Authorization header" in resp.json()["detail"]

    # Basic auth instead of Bearer
    resp = await async_client.get(
        "/api/v1/auth/me",
        headers={"Authorization": "Basic dXNlcjpwYXNz"},
    )
    assert resp.status_code == 401
    assert "Malformed Authorization header" in resp.json()["detail"]


@pytest.mark.asyncio
async def test_auth_expired_jwt_rejected(async_client: AsyncClient):
    """Verify that an expired JWT access token is rejected with 401."""
    expired_token, _ = create_access_token(
        subject=str(uuid.uuid4()),
        expires_delta=timedelta(seconds=-300),  # 5 minutes in the past
    )
    resp = await async_client.get(
        "/api/v1/auth/me",
        headers={"Authorization": f"Bearer {expired_token}"},
    )
    assert resp.status_code == 401
    assert "expired" in resp.json()["detail"].lower()


@pytest.mark.asyncio
async def test_auth_tampered_jwt_signature_rejected(async_client: AsyncClient):
    """Verify that a JWT with a modified payload or forged signature is rejected."""
    token, _ = create_access_token(subject=str(uuid.uuid4()))
    parts = token.split(".")
    assert len(parts) == 3

    # Tamper with signature
    tampered_sig_token = f"{parts[0]}.{parts[1]}.bad_signature_abc123"
    resp = await async_client.get(
        "/api/v1/auth/me",
        headers={"Authorization": f"Bearer {tampered_sig_token}"},
    )
    assert resp.status_code == 401
    assert "Invalid token signature" in resp.json()["detail"]

    # Tamper with payload
    tampered_payload_token = f"{parts[0]}.eyJhZG1pbiI6IHRydWV9.{parts[2]}"
    resp = await async_client.get(
        "/api/v1/auth/me",
        headers={"Authorization": f"Bearer {tampered_payload_token}"},
    )
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_auth_unsupported_algorithm_rejected(async_client: AsyncClient):
    """Verify that 'none' or mismatched algorithm headers are strictly rejected."""
    header = {"alg": "none", "typ": "JWT"}
    payload = {"sub": str(uuid.uuid4()), "exp": int(datetime.now(timezone.utc).timestamp()) + 3600}
    token = f"{_base64url_encode(json.dumps(header).encode())}.{_base64url_encode(json.dumps(payload).encode())}."

    resp = await async_client.get(
        "/api/v1/auth/me",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_auth_agent_credential_rejected_on_human_endpoints(async_client: AsyncClient):
    """Verify that agent credentials (cst_ag_...) cannot be used on human administration routes."""
    raw_key, _ = generate_agent_api_key()
    org_resp = await async_client.post("/api/v1/organizations", json={"name": "Auth Sec Org"})
    org_id = org_resp.json()["id"]

    # Attempt to list audit events (requires human user)
    resp = await async_client.get(
        f"/api/v1/organizations/{org_id}/audit-events",
        headers={"Authorization": f"Bearer {raw_key}"},
    )
    assert resp.status_code == 401
    assert "Agent credentials cannot be used for human administrative operations" in resp.json()["detail"]


@pytest.mark.asyncio
async def test_auth_login_brute_force_rate_limiting(async_client: AsyncClient):
    """Verify that repeated failed login attempts trigger 429 Too Many Requests."""
    for attempt in range(10):
        resp = await async_client.post(
            "/api/v1/auth/login",
            json={"email": "attacker@target.com", "password": f"wrong-pass-{attempt}"},
        )
        assert resp.status_code == 401

    # 11th attempt must be throttled with 429
    throttled_resp = await async_client.post(
        "/api/v1/auth/login",
        json={"email": "attacker@target.com", "password": "wrong-pass-11"},
    )
    assert throttled_resp.status_code == 429
    assert "Too many failed login attempts" in throttled_resp.json()["detail"]
