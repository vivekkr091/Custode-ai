"""Automated tests for User API endpoints."""

import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_create_user_success(async_client: AsyncClient) -> None:
    """Ensure a user can be created with normalized email."""
    payload = {
        "email": " Alice.Security@Example.COM ",
        "display_name": "Alice Security Analyst",
    }
    response = await async_client.post("/api/v1/users", json=payload)
    assert response.status_code == 201
    data = response.json()
    assert data["email"] == "alice.security@example.com"
    assert data["display_name"] == "Alice Security Analyst"
    assert data["status"] == "active"
    assert "id" in data
    assert "created_at" in data
    assert "updated_at" in data


@pytest.mark.asyncio
async def test_create_user_duplicate_email_rejected(async_client: AsyncClient) -> None:
    """Ensure duplicate user emails are rejected with HTTP 409 Conflict."""
    payload1 = {
        "email": "bob@custode.io",
        "display_name": "Bob Admin",
    }
    res1 = await async_client.post("/api/v1/users", json=payload1)
    assert res1.status_code == 201

    payload2 = {
        "email": "BOB@CUSTODE.IO",  # casing difference should be caught by normalization
        "display_name": "Bob Duplicate",
    }
    res2 = await async_client.post("/api/v1/users", json=payload2)
    assert res2.status_code == 409
    assert "already exists" in res2.json()["detail"]


@pytest.mark.asyncio
async def test_create_user_invalid_email_format(async_client: AsyncClient) -> None:
    """Ensure malformed email formats are rejected with HTTP 422 Unprocessable Entity."""
    payload = {
        "email": "not-an-email",
        "display_name": "Charlie Tester",
    }
    response = await async_client.post("/api/v1/users", json=payload)
    assert response.status_code == 422
