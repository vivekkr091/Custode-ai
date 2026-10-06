"""Automated tests for Organization API endpoints."""

import uuid
import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_create_organization_success(async_client: AsyncClient) -> None:
    """Ensure an organization can be created successfully."""
    payload = {"name": "Acme Security Corp"}
    response = await async_client.post("/api/v1/organizations", json=payload)
    assert response.status_code == 201
    data = response.json()
    assert data["name"] == "Acme Security Corp"
    assert data["slug"] == "acme-security-corp"
    assert data["status"] == "active"
    assert "id" in data
    assert "created_at" in data
    assert "updated_at" in data


@pytest.mark.asyncio
async def test_create_organization_custom_slug(async_client: AsyncClient) -> None:
    """Ensure an organization can be created with a custom slug."""
    payload = {"name": "Sentinel Org", "slug": "sentinel-custom"}
    response = await async_client.post("/api/v1/organizations", json=payload)
    assert response.status_code == 201
    data = response.json()
    assert data["slug"] == "sentinel-custom"


@pytest.mark.asyncio
async def test_create_organization_duplicate_slug_rejected(async_client: AsyncClient) -> None:
    """Ensure creating an organization with an existing slug returns HTTP 409 Conflict."""
    payload1 = {"name": "Acme Corp", "slug": "acme-unique"}
    res1 = await async_client.post("/api/v1/organizations", json=payload1)
    assert res1.status_code == 201

    payload2 = {"name": "Acme Duplicate", "slug": "acme-unique"}
    res2 = await async_client.post("/api/v1/organizations", json=payload2)
    assert res2.status_code == 409
    assert "already exists" in res2.json()["detail"]


@pytest.mark.asyncio
async def test_retrieve_organization_success(async_client: AsyncClient) -> None:
    """Ensure an existing organization can be retrieved by its UUID."""
    create_res = await async_client.post(
        "/api/v1/organizations", json={"name": "Cyber Defense Org"}
    )
    assert create_res.status_code == 201
    org_id = create_res.json()["id"]

    get_res = await async_client.get(f"/api/v1/organizations/{org_id}")
    assert get_res.status_code == 200
    data = get_res.json()
    assert data["id"] == org_id
    assert data["name"] == "Cyber Defense Org"
    assert data["slug"] == "cyber-defense-org"


@pytest.mark.asyncio
async def test_retrieve_organization_not_found(async_client: AsyncClient) -> None:
    """Ensure querying a non-existent organization UUID returns HTTP 404 Not Found."""
    random_id = str(uuid.uuid4())
    response = await async_client.get(f"/api/v1/organizations/{random_id}")
    assert response.status_code == 404
    assert f"Organization '{random_id}' not found" in response.json()["detail"]


@pytest.mark.asyncio
async def test_list_organizations_success(async_client: AsyncClient) -> None:
    """Ensure registered organizations can be listed."""
    create_res = await async_client.post(
        "/api/v1/organizations", json={"name": "Org For Listing"}
    )
    assert create_res.status_code == 201

    list_res = await async_client.get("/api/v1/organizations")
    assert list_res.status_code == 200
    data = list_res.json()
    assert isinstance(data, list)
    assert any(o["name"] == "Org For Listing" for o in data)
