"""Ingress Middleware, Security Headers, and Input Validation Tests (Milestone 22)."""

import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_ingress_request_body_size_limit_enforced(async_client: AsyncClient):
    """Verify that requests exceeding MAX_REQUEST_BODY_BYTES are rejected with 413."""
    # 15 MB content length header
    oversized_length = 15 * 1024 * 1024
    resp = await async_client.post(
        "/api/v1/auth/login",
        headers={"Content-Length": str(oversized_length)},
        content=b"x" * 100,  # small mock body but declared header exceeds limit
    )
    assert resp.status_code == 413
    assert "Payload Too Large" in resp.json()["detail"]


@pytest.mark.asyncio
async def test_ingress_security_headers_present(async_client: AsyncClient):
    """Verify that all mandatory HTTP defensive security headers are emitted."""
    resp = await async_client.get("/health")
    assert resp.status_code == 200

    headers = resp.headers
    assert headers.get("X-Content-Type-Options") == "nosniff"
    assert headers.get("X-Frame-Options") == "DENY"
    assert headers.get("Strict-Transport-Security") == "max-age=31536000; includeSubDomains"
    assert "default-src 'none'" in headers.get("Content-Security-Policy", "")


@pytest.mark.asyncio
async def test_pagination_boundary_validation(async_client: AsyncClient):
    """Verify that extreme limit parameters (>100 or <1) are rejected with 422."""
    org_resp = await async_client.post("/api/v1/organizations", json={"name": "Pagination Org"})
    org_id = org_resp.json()["id"]

    # limit > 100
    resp_large = await async_client.get(f"/api/v1/organizations/{org_id}/agents?limit=101")
    assert resp_large.status_code == 422

    # limit < 1
    resp_zero = await async_client.get(f"/api/v1/organizations/{org_id}/agents?limit=0")
    assert resp_zero.status_code == 422

    # negative offset
    resp_neg_offset = await async_client.get(f"/api/v1/organizations/{org_id}/agents?offset=-5")
    assert resp_neg_offset.status_code == 422
