"""Automated tests for Organization Membership API endpoints."""

import uuid
import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_create_membership_success(async_client: AsyncClient) -> None:
    """Ensure a user can be successfully added to an organization."""
    # 1. Create Org
    org_res = await async_client.post(
        "/api/v1/organizations", json={"name": "Engineering Org"}
    )
    assert org_res.status_code == 201
    org_id = org_res.json()["id"]

    # 2. Create User
    user_res = await async_client.post(
        "/api/v1/users", json={"email": "eng-lead@custode.io", "display_name": "Eng Lead"}
    )
    assert user_res.status_code == 201
    user_id = user_res.json()["id"]

    # 3. Create Membership
    membership_res = await async_client.post(
        f"/api/v1/organizations/{org_id}/memberships",
        json={"user_id": user_id, "role": "organization_admin"},
    )
    assert membership_res.status_code == 201
    data = membership_res.json()
    assert data["organization_id"] == org_id
    assert data["user_id"] == user_id
    assert data["role"] == "organization_admin"
    assert data["status"] == "active"
    assert "id" in data
    assert "created_at" in data
    assert "updated_at" in data


@pytest.mark.asyncio
async def test_create_membership_invalid_organization(async_client: AsyncClient) -> None:
    """Ensure adding a member to a non-existent organization returns HTTP 404."""
    # Create User
    user_res = await async_client.post(
        "/api/v1/users", json={"email": "developer@custode.io", "display_name": "Dev User"}
    )
    assert user_res.status_code == 201
    user_id = user_res.json()["id"]

    random_org_id = str(uuid.uuid4())
    membership_res = await async_client.post(
        f"/api/v1/organizations/{random_org_id}/memberships",
        json={"user_id": user_id, "role": "developer"},
    )
    assert membership_res.status_code == 404
    assert f"Organization '{random_org_id}' not found" in membership_res.json()["detail"]


@pytest.mark.asyncio
async def test_create_membership_invalid_user(async_client: AsyncClient) -> None:
    """Ensure adding a non-existent user to an organization returns HTTP 404."""
    org_res = await async_client.post(
        "/api/v1/organizations", json={"name": "DevSecOps Org"}
    )
    assert org_res.status_code == 201
    org_id = org_res.json()["id"]

    random_user_id = str(uuid.uuid4())
    membership_res = await async_client.post(
        f"/api/v1/organizations/{org_id}/memberships",
        json={"user_id": random_user_id, "role": "security_analyst"},
    )
    assert membership_res.status_code == 404
    assert f"User '{random_user_id}' not found" in membership_res.json()["detail"]


@pytest.mark.asyncio
async def test_create_membership_invalid_role(async_client: AsyncClient) -> None:
    """Ensure adding a member with an invalid role returns HTTP 422 Unprocessable Entity."""
    org_res = await async_client.post(
        "/api/v1/organizations", json={"name": "QA Org"}
    )
    assert org_res.status_code == 201
    org_id = org_res.json()["id"]

    user_res = await async_client.post(
        "/api/v1/users", json={"email": "qa@custode.io", "display_name": "QA User"}
    )
    assert user_res.status_code == 201
    user_id = user_res.json()["id"]

    membership_res = await async_client.post(
        f"/api/v1/organizations/{org_id}/memberships",
        json={"user_id": user_id, "role": "super_root_admin"},  # invalid role
    )
    assert membership_res.status_code == 422


@pytest.mark.asyncio
async def test_create_membership_duplicate_rejected(async_client: AsyncClient) -> None:
    """Ensure assigning duplicate membership for the same org + user returns HTTP 409."""
    org_res = await async_client.post(
        "/api/v1/organizations", json={"name": "Cloud Security Org"}
    )
    org_id = org_res.json()["id"]

    user_res = await async_client.post(
        "/api/v1/users", json={"email": "analyst@custode.io", "display_name": "Analyst"}
    )
    user_id = user_res.json()["id"]

    # First membership
    m1 = await async_client.post(
        f"/api/v1/organizations/{org_id}/memberships",
        json={"user_id": user_id, "role": "viewer"},
    )
    assert m1.status_code == 201

    # Second membership for the same user and organization
    m2 = await async_client.post(
        f"/api/v1/organizations/{org_id}/memberships",
        json={"user_id": user_id, "role": "developer"},
    )
    assert m2.status_code == 409
    assert "already a member" in m2.json()["detail"]
