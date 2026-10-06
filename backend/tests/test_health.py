"""Tests for CUSTODE health check endpoints (application and database)."""

import pytest
from httpx import AsyncClient

EXPECTED_HEALTH_PAYLOAD = {
    "status": "ok",
    "service": "custode-api",
}

EXPECTED_DB_HEALTH_PAYLOAD = {
    "status": "ok",
    "database": "connected",
}


@pytest.mark.asyncio
async def test_health_endpoint_status_code(async_client: AsyncClient) -> None:
    """Ensure GET /health returns HTTP 200 OK."""
    response = await async_client.get("/health")
    assert response.status_code == 200


@pytest.mark.asyncio
async def test_health_endpoint_payload(async_client: AsyncClient) -> None:
    """Ensure GET /health returns expected service status and name."""
    response = await async_client.get("/health")
    assert response.json() == EXPECTED_HEALTH_PAYLOAD


@pytest.mark.asyncio
async def test_api_v1_health_endpoint(async_client: AsyncClient) -> None:
    """Ensure versioned GET /api/v1/health returns HTTP 200 and expected payload."""
    response = await async_client.get("/api/v1/health")
    assert response.status_code == 200
    assert response.json() == EXPECTED_HEALTH_PAYLOAD


@pytest.mark.asyncio
async def test_db_health_endpoint_success(async_client: AsyncClient) -> None:
    """Ensure GET /health/db returns HTTP 200 and connected status."""
    response = await async_client.get("/health/db")
    assert response.status_code == 200
    assert response.json() == EXPECTED_DB_HEALTH_PAYLOAD


@pytest.mark.asyncio
async def test_api_v1_db_health_endpoint_success(async_client: AsyncClient) -> None:
    """Ensure versioned GET /api/v1/health/db returns HTTP 200 and connected status."""
    response = await async_client.get("/api/v1/health/db")
    assert response.status_code == 200
    assert response.json() == EXPECTED_DB_HEALTH_PAYLOAD
