"""Automated tests for Agent Credentials and Cryptographic Authentication."""

import uuid
from datetime import datetime, timedelta, timezone
import pytest
from httpx import AsyncClient
from sqlalchemy import select

from app.db.models.agent import Agent, AgentStatus
from app.db.models.agent_credential import AgentCredential, CredentialStatus
from app.db.models.organization import Organization, OrganizationStatus
from tests.conftest import TestingSessionLocal


@pytest.mark.asyncio
async def test_credential_creation_success(async_client: AsyncClient) -> None:
    """Ensure an agent credential can be issued with a high-entropy key returned once."""
    # 1. Create Org and Agent
    org = (
        await async_client.post("/api/v1/organizations", json={"name": "Auth Org 1"})
    ).json()
    org_id = org["id"]

    agent = (
        await async_client.post(
            f"/api/v1/organizations/{org_id}/agents", json={"name": "Security Agent"}
        )
    ).json()
    agent_id = agent["id"]

    # 2. Issue Credential
    payload = {"name": "Production Runtime Key"}
    res = await async_client.post(
        f"/api/v1/organizations/{org_id}/agents/{agent_id}/credentials",
        json=payload,
    )
    assert res.status_code == 201
    data = res.json()
    assert data["name"] == "Production Runtime Key"
    assert "api_key" in data
    assert data["api_key"].startswith("cst_ag_")
    assert data["credential_prefix"].startswith("cst_ag_")
    assert data["status"] == "active"
    assert "credential_hash" not in data
    assert "id" in data
    assert "created_at" in data

    raw_api_key = data["api_key"]
    cred_id = data["id"]

    # 3. Verify in database: hash is stored, NEVER raw key
    async with TestingSessionLocal() as session:
        db_cred = (
            await session.execute(
                select(AgentCredential).where(
                    AgentCredential.id == uuid.UUID(cred_id)
                )
            )
        ).scalar_one()
        assert db_cred.credential_hash != raw_api_key
        assert "$" in db_cred.credential_hash  # salted PBKDF2 representation
        assert raw_api_key not in db_cred.credential_hash


@pytest.mark.asyncio
async def test_credential_raw_key_never_returned_in_list_or_revoke(
    async_client: AsyncClient,
) -> None:
    """Ensure raw api_key and credential_hash are never returned in list or revoke responses."""
    org_id = (
        await async_client.post("/api/v1/organizations", json={"name": "Auth Org 2"})
    ).json()["id"]
    agent_id = (
        await async_client.post(
            f"/api/v1/organizations/{org_id}/agents", json={"name": "Audit Agent"}
        )
    ).json()["id"]

    # Issue credential
    cred = (
        await async_client.post(
            f"/api/v1/organizations/{org_id}/agents/{agent_id}/credentials",
            json={"name": "Key One"},
        )
    ).json()
    cred_id = cred["id"]

    # 1. Inspect list response
    list_res = await async_client.get(
        f"/api/v1/organizations/{org_id}/agents/{agent_id}/credentials"
    )
    assert list_res.status_code == 200
    list_data = list_res.json()
    assert list_data["total"] == 1
    item = list_data["items"][0]
    assert "api_key" not in item
    assert "credential_hash" not in item
    assert item["name"] == "Key One"

    # 2. Inspect revoke response
    revoke_res = await async_client.post(
        f"/api/v1/organizations/{org_id}/agents/{agent_id}/credentials/{cred_id}/revoke"
    )
    assert revoke_res.status_code == 200
    revoke_data = revoke_res.json()
    assert "api_key" not in revoke_data
    assert "credential_hash" not in revoke_data
    assert revoke_data["status"] == "revoked"
    assert revoke_data["revoked_at"] is not None


@pytest.mark.asyncio
async def test_authentication_with_valid_api_key(async_client: AsyncClient) -> None:
    """Ensure a valid agent API key successfully authenticates at /api/v1/auth/me."""
    org_id = (
        await async_client.post("/api/v1/organizations", json={"name": "Valid Auth Org"})
    ).json()["id"]
    agent_id = (
        await async_client.post(
            f"/api/v1/organizations/{org_id}/agents", json={"name": "Worker Bot"}
        )
    ).json()["id"]

    cred = (
        await async_client.post(
            f"/api/v1/organizations/{org_id}/agents/{agent_id}/credentials",
            json={"name": "Live Key"},
        )
    ).json()
    raw_api_key = cred["api_key"]
    cred_id = cred["id"]

    # Authenticate at /api/v1/auth/me
    headers = {"Authorization": f"Bearer {raw_api_key}"}
    me_res = await async_client.get("/api/v1/auth/me", headers=headers)
    assert me_res.status_code == 200
    auth_data = me_res.json()
    assert auth_data["organization_id"] == org_id
    assert auth_data["agent_id"] == agent_id
    assert auth_data["credential_id"] == cred_id

    # Verify last_used_at is updated
    async with TestingSessionLocal() as session:
        db_cred = (
            await session.execute(
                select(AgentCredential).where(
                    AgentCredential.id == uuid.UUID(cred_id)
                )
            )
        ).scalar_one()
        assert db_cred.last_used_at is not None


@pytest.mark.asyncio
async def test_authentication_invalid_key_fails(async_client: AsyncClient) -> None:
    """Ensure invalid token formats or wrong secrets return HTTP 401 Unauthorized."""
    # Completely fake format
    res1 = await async_client.get(
        "/api/v1/auth/me", headers={"Authorization": "Bearer not-a-valid-key"}
    )
    assert res1.status_code == 401

    # Right prefix format but non-existent or wrong secret
    res2 = await async_client.get(
        "/api/v1/auth/me", headers={"Authorization": "Bearer cst_ag_0000000000_fake_secret"}
    )
    assert res2.status_code == 401


@pytest.mark.asyncio
async def test_authentication_missing_and_malformed_header(async_client: AsyncClient) -> None:
    """Ensure missing or non-Bearer headers fail with HTTP 401."""
    # Missing header
    res_missing = await async_client.get("/api/v1/auth/me")
    assert res_missing.status_code == 401
    assert "Missing Authorization header" in res_missing.json()["detail"]

    # Basic auth instead of Bearer
    res_basic = await async_client.get(
        "/api/v1/auth/me", headers={"Authorization": "Basic user:pass"}
    )
    assert res_basic.status_code == 401
    assert "Malformed Authorization header" in res_basic.json()["detail"]


@pytest.mark.asyncio
async def test_authentication_revoked_credential_fails(async_client: AsyncClient) -> None:
    """Ensure a revoked credential immediately fails authentication."""
    org_id = (
        await async_client.post("/api/v1/organizations", json={"name": "Revoke Auth Org"})
    ).json()["id"]
    agent_id = (
        await async_client.post(
            f"/api/v1/organizations/{org_id}/agents", json={"name": "Revoke Test Agent"}
        )
    ).json()["id"]

    cred = (
        await async_client.post(
            f"/api/v1/organizations/{org_id}/agents/{agent_id}/credentials",
            json={"name": "To Be Revoked"},
        )
    ).json()
    raw_api_key = cred["api_key"]
    cred_id = cred["id"]

    # Verify key works initially
    headers = {"Authorization": f"Bearer {raw_api_key}"}
    res_before = await async_client.get("/api/v1/auth/me", headers=headers)
    assert res_before.status_code == 200

    # Revoke credential
    await async_client.post(
        f"/api/v1/organizations/{org_id}/agents/{agent_id}/credentials/{cred_id}/revoke"
    )

    # Key must now fail immediately
    res_after = await async_client.get("/api/v1/auth/me", headers=headers)
    assert res_after.status_code == 401
    assert "revoked" in res_after.json()["detail"]


@pytest.mark.asyncio
async def test_authentication_expired_credential_fails(async_client: AsyncClient) -> None:
    """Ensure an expired credential fails authentication."""
    org_id = (
        await async_client.post("/api/v1/organizations", json={"name": "Expire Org"})
    ).json()["id"]
    agent_id = (
        await async_client.post(
            f"/api/v1/organizations/{org_id}/agents", json={"name": "Expire Agent"}
        )
    ).json()["id"]

    # Issue key that was already expired 1 hour ago
    past_time = (datetime.now(timezone.utc) - timedelta(hours=1)).isoformat()
    cred = (
        await async_client.post(
            f"/api/v1/organizations/{org_id}/agents/{agent_id}/credentials",
            json={"name": "Expired Key", "expires_at": past_time},
        )
    ).json()
    raw_api_key = cred["api_key"]

    headers = {"Authorization": f"Bearer {raw_api_key}"}
    res = await async_client.get("/api/v1/auth/me", headers=headers)
    assert res.status_code == 401
    assert "expired" in res.json()["detail"]


@pytest.mark.asyncio
async def test_authentication_suspended_agent_fails(async_client: AsyncClient) -> None:
    """Ensure credentials from a suspended agent fail authentication."""
    org_id = (
        await async_client.post("/api/v1/organizations", json={"name": "Suspended Agent Org"})
    ).json()["id"]
    agent_id = (
        await async_client.post(
            f"/api/v1/organizations/{org_id}/agents", json={"name": "Suspendable Agent"}
        )
    ).json()["id"]

    cred = (
        await async_client.post(
            f"/api/v1/organizations/{org_id}/agents/{agent_id}/credentials",
            json={"name": "Suspended Key"},
        )
    ).json()
    raw_api_key = cred["api_key"]

    # Suspend agent
    await async_client.post(
        f"/api/v1/organizations/{org_id}/agents/{agent_id}/suspend"
    )

    headers = {"Authorization": f"Bearer {raw_api_key}"}
    res = await async_client.get("/api/v1/auth/me", headers=headers)
    assert res.status_code == 401
    assert "suspended" in res.json()["detail"]


@pytest.mark.asyncio
async def test_authentication_revoked_agent_fails(async_client: AsyncClient) -> None:
    """Ensure credentials from a revoked agent fail authentication."""
    org_id = (
        await async_client.post("/api/v1/organizations", json={"name": "Revoked Agent Org"})
    ).json()["id"]
    agent_id = (
        await async_client.post(
            f"/api/v1/organizations/{org_id}/agents", json={"name": "Revocable Agent"}
        )
    ).json()["id"]

    cred = (
        await async_client.post(
            f"/api/v1/organizations/{org_id}/agents/{agent_id}/credentials",
            json={"name": "Revoked Agent Key"},
        )
    ).json()
    raw_api_key = cred["api_key"]

    # Revoke agent
    await async_client.post(
        f"/api/v1/organizations/{org_id}/agents/{agent_id}/revoke"
    )

    headers = {"Authorization": f"Bearer {raw_api_key}"}
    res = await async_client.get("/api/v1/auth/me", headers=headers)
    assert res.status_code == 401
    assert "revoked" in res.json()["detail"]


@pytest.mark.asyncio
async def test_authentication_suspended_organization_fails(
    async_client: AsyncClient,
) -> None:
    """Ensure credentials belonging to a suspended organization fail authentication."""
    org_id = (
        await async_client.post("/api/v1/organizations", json={"name": "Suspended Tenant Org"})
    ).json()["id"]
    agent_id = (
        await async_client.post(
            f"/api/v1/organizations/{org_id}/agents", json={"name": "Tenant Agent"}
        )
    ).json()["id"]

    cred = (
        await async_client.post(
            f"/api/v1/organizations/{org_id}/agents/{agent_id}/credentials",
            json={"name": "Tenant Key"},
        )
    ).json()
    raw_api_key = cred["api_key"]

    # Suspend organization
    async with TestingSessionLocal() as session:
        org = (
            await session.execute(
                select(Organization).where(Organization.id == uuid.UUID(org_id))
            )
        ).scalar_one()
        org.status = OrganizationStatus.suspended.value
        await session.commit()

    headers = {"Authorization": f"Bearer {raw_api_key}"}
    res = await async_client.get("/api/v1/auth/me", headers=headers)
    assert res.status_code == 401
    assert "Organization is not active" in res.json()["detail"]


@pytest.mark.asyncio
async def test_cross_tenant_credential_isolation(async_client: AsyncClient) -> None:
    """Ensure tenant and agent boundaries cannot be crossed to view or revoke credentials."""
    # Org A + Agent A
    org_a = (
        await async_client.post("/api/v1/organizations", json={"name": "Org A Cred"})
    ).json()["id"]
    agent_a = (
        await async_client.post(
            f"/api/v1/organizations/{org_a}/agents", json={"name": "Agent A"}
        )
    ).json()["id"]
    cred_a = (
        await async_client.post(
            f"/api/v1/organizations/{org_a}/agents/{agent_a}/credentials",
            json={"name": "Cred A"},
        )
    ).json()
    cred_a_id = cred_a["id"]

    # Org B + Agent B
    org_b = (
        await async_client.post("/api/v1/organizations", json={"name": "Org B Cred"})
    ).json()["id"]
    agent_b = (
        await async_client.post(
            f"/api/v1/organizations/{org_b}/agents", json={"name": "Agent B"}
        )
    ).json()["id"]

    # Org B cannot list credentials for Agent A
    res_list = await async_client.get(
        f"/api/v1/organizations/{org_b}/agents/{agent_a}/credentials"
    )
    assert res_list.status_code == 404

    # Org B cannot revoke Credential A
    res_revoke = await async_client.post(
        f"/api/v1/organizations/{org_b}/agents/{agent_b}/credentials/{cred_a_id}/revoke"
    )
    assert res_revoke.status_code == 404
