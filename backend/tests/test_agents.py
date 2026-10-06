"""Automated tests for Agent Identity, Registry, Lifecycle, and Tenant Isolation."""

import uuid
import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.agent import Agent
from app.db.models.organization import Organization, OrganizationStatus


@pytest.mark.asyncio
async def test_create_agent_success(async_client: AsyncClient) -> None:
    """Ensure an agent can be successfully registered in an organization."""
    # 1. Create Organization
    org_res = await async_client.post(
        "/api/v1/organizations", json={"name": "Cyber Defense Labs"}
    )
    assert org_res.status_code == 201
    org_id = org_res.json()["id"]

    # 2. Register Agent
    payload = {
        "name": "Research Agent",
        "description": "Internal research assistant",
        "agent_type": "assistant",
        "environment": "development",
    }
    agent_res = await async_client.post(
        f"/api/v1/organizations/{org_id}/agents", json=payload
    )
    assert agent_res.status_code == 201
    data = agent_res.json()
    assert data["name"] == "Research Agent"
    assert data["slug"] == "research-agent"
    assert data["description"] == "Internal research assistant"
    assert data["agent_type"] == "assistant"
    assert data["status"] == "active"
    assert data["environment"] == "development"
    assert data["organization_id"] == org_id
    assert data["last_seen_at"] is None
    assert "id" in data
    assert "created_at" in data
    assert "updated_at" in data


@pytest.mark.asyncio
async def test_create_agent_defaults(async_client: AsyncClient) -> None:
    """Ensure agent defaults for status, environment, and agent_type apply properly."""
    org_res = await async_client.post(
        "/api/v1/organizations", json={"name": "Alpha Corp"}
    )
    org_id = org_res.json()["id"]

    # Minimal payload
    payload = {"name": "Default Worker"}
    agent_res = await async_client.post(
        f"/api/v1/organizations/{org_id}/agents", json=payload
    )
    assert agent_res.status_code == 201
    data = agent_res.json()
    assert data["slug"] == "default-worker"
    assert data["status"] == "active"
    assert data["environment"] == "development"
    assert data["agent_type"] == "assistant"


@pytest.mark.asyncio
async def test_create_agent_invalid_agent_type(async_client: AsyncClient) -> None:
    """Ensure invalid agent_type returns HTTP 422 Unprocessable Entity."""
    org_res = await async_client.post(
        "/api/v1/organizations", json={"name": "Type Test Org"}
    )
    org_id = org_res.json()["id"]

    payload = {"name": "Bad Type Agent", "agent_type": "super_skynet"}
    agent_res = await async_client.post(
        f"/api/v1/organizations/{org_id}/agents", json=payload
    )
    assert agent_res.status_code == 422


@pytest.mark.asyncio
async def test_create_agent_invalid_environment(async_client: AsyncClient) -> None:
    """Ensure invalid environment returns HTTP 422 Unprocessable Entity."""
    org_res = await async_client.post(
        "/api/v1/organizations", json={"name": "Env Test Org"}
    )
    org_id = org_res.json()["id"]

    payload = {"name": "Bad Env Agent", "environment": "sandbox_universe"}
    agent_res = await async_client.post(
        f"/api/v1/organizations/{org_id}/agents", json=payload
    )
    assert agent_res.status_code == 422


@pytest.mark.asyncio
async def test_create_agent_missing_organization(async_client: AsyncClient) -> None:
    """Ensure attempting to register an agent under a non-existent org returns HTTP 404."""
    random_org_id = str(uuid.uuid4())
    payload = {"name": "Orphan Agent"}
    agent_res = await async_client.post(
        f"/api/v1/organizations/{random_org_id}/agents", json=payload
    )
    assert agent_res.status_code == 404
    assert f"Organization '{random_org_id}' not found" in agent_res.json()["detail"]


@pytest.mark.asyncio
async def test_create_agent_suspended_organization(
    async_client: AsyncClient,
) -> None:
    """Ensure creating an agent in a suspended organization returns HTTP 409 Conflict."""
    # Create Org
    org_res = await async_client.post(
        "/api/v1/organizations", json={"name": "Suspended Test Org"}
    )
    org_id = org_res.json()["id"]

    # Suspend organization via DB
    from tests.conftest import TestingSessionLocal
    async with TestingSessionLocal() as session:
        query = select(Organization).where(Organization.id == uuid.UUID(org_id))
        res = await session.execute(query)
        org = res.scalar_one()
        org.status = OrganizationStatus.suspended.value
        await session.commit()

    payload = {"name": "Blocked Agent"}
    agent_res = await async_client.post(
        f"/api/v1/organizations/{org_id}/agents", json=payload
    )
    assert agent_res.status_code == 409
    assert "suspended organization" in agent_res.json()["detail"]


@pytest.mark.asyncio
async def test_agent_slug_uniqueness_within_same_org(async_client: AsyncClient) -> None:
    """Ensure duplicate agent slugs within the same organization are rejected with HTTP 409."""
    org_res = await async_client.post(
        "/api/v1/organizations", json={"name": "Slug Test Org"}
    )
    org_id = org_res.json()["id"]

    # First agent
    res1 = await async_client.post(
        f"/api/v1/organizations/{org_id}/agents", json={"name": "Security Scanner"}
    )
    assert res1.status_code == 201

    # Second agent with the same name/slug in the SAME organization
    res2 = await async_client.post(
        f"/api/v1/organizations/{org_id}/agents", json={"name": "Security Scanner"}
    )
    assert res2.status_code == 409
    assert "already exists in organization" in res2.json()["detail"]


@pytest.mark.asyncio
async def test_agent_same_slug_different_orgs_allowed(async_client: AsyncClient) -> None:
    """Ensure the same slug is allowed in different organizations (composite uniqueness boundary)."""
    # Org 1
    org1_res = await async_client.post(
        "/api/v1/organizations", json={"name": "Org One"}
    )
    org1_id = org1_res.json()["id"]

    # Org 2
    org2_res = await async_client.post(
        "/api/v1/organizations", json={"name": "Org Two"}
    )
    org2_id = org2_res.json()["id"]

    # Same agent slug in Org 1
    res1 = await async_client.post(
        f"/api/v1/organizations/{org1_id}/agents", json={"name": "Compliance Bot"}
    )
    assert res1.status_code == 201
    assert res1.json()["slug"] == "compliance-bot"

    # Same agent slug in Org 2 must succeed
    res2 = await async_client.post(
        f"/api/v1/organizations/{org2_id}/agents", json={"name": "Compliance Bot"}
    )
    assert res2.status_code == 201
    assert res2.json()["slug"] == "compliance-bot"
    assert res1.json()["id"] != res2.json()["id"]


@pytest.mark.asyncio
async def test_get_agent_success_and_not_found(async_client: AsyncClient) -> None:
    """Ensure an agent can be retrieved by its ID, and returns 404 when non-existent."""
    org_res = await async_client.post(
        "/api/v1/organizations", json={"name": "Retrieve Org"}
    )
    org_id = org_res.json()["id"]

    create_res = await async_client.post(
        f"/api/v1/organizations/{org_id}/agents", json={"name": "Query Agent"}
    )
    agent_id = create_res.json()["id"]

    # Successful retrieval
    get_res = await async_client.get(
        f"/api/v1/organizations/{org_id}/agents/{agent_id}"
    )
    assert get_res.status_code == 200
    assert get_res.json()["id"] == agent_id

    # Non-existent agent ID
    random_id = str(uuid.uuid4())
    not_found_res = await async_client.get(
        f"/api/v1/organizations/{org_id}/agents/{random_id}"
    )
    assert not_found_res.status_code == 404
    assert f"Agent '{random_id}' not found" in not_found_res.json()["detail"]


@pytest.mark.asyncio
async def test_tenant_isolation_enforcement(async_client: AsyncClient) -> None:
    """Ensure tenant isolation is strictly enforced across GET, PATCH, suspend, and revoke."""
    # Org A with Agent A
    org_a = (
        await async_client.post("/api/v1/organizations", json={"name": "Org A"})
    ).json()["id"]
    agent_a = (
        await async_client.post(
            f"/api/v1/organizations/{org_a}/agents", json={"name": "Agent A"}
        )
    ).json()["id"]

    # Org B
    org_b = (
        await async_client.post("/api/v1/organizations", json={"name": "Org B"})
    ).json()["id"]

    # 1. Org B cannot retrieve Agent A (must return 404, not reveal existence)
    res_get = await async_client.get(
        f"/api/v1/organizations/{org_b}/agents/{agent_a}"
    )
    assert res_get.status_code == 404
    assert f"Agent '{agent_a}' not found in organization '{org_b}'" in res_get.json()["detail"]

    # 2. Org B cannot update Agent A
    res_patch = await async_client.patch(
        f"/api/v1/organizations/{org_b}/agents/{agent_a}",
        json={"name": "Hacked Name"},
    )
    assert res_patch.status_code == 404

    # 3. Org B cannot suspend Agent A
    res_suspend = await async_client.post(
        f"/api/v1/organizations/{org_b}/agents/{agent_a}/suspend"
    )
    assert res_suspend.status_code == 404

    # 4. Org B cannot revoke Agent A
    res_revoke = await async_client.post(
        f"/api/v1/organizations/{org_b}/agents/{agent_a}/revoke"
    )
    assert res_revoke.status_code == 404


@pytest.mark.asyncio
async def test_agent_lifecycle_transitions(async_client: AsyncClient) -> None:
    """Ensure valid lifecycle transitions work and invalid ones (revoked -> active/suspended) are rejected."""
    org_id = (
        await async_client.post("/api/v1/organizations", json={"name": "Lifecycle Org"})
    ).json()["id"]

    # Create agent (initial: active)
    agent = (
        await async_client.post(
            f"/api/v1/organizations/{org_id}/agents", json={"name": "Lifecycle Worker"}
        )
    ).json()
    agent_id = agent["id"]
    assert agent["status"] == "active"

    # Transition 1: active -> suspended
    res_susp = await async_client.post(
        f"/api/v1/organizations/{org_id}/agents/{agent_id}/suspend"
    )
    assert res_susp.status_code == 200
    assert res_susp.json()["status"] == "suspended"

    # Transition 2: suspended -> revoked
    res_rev = await async_client.post(
        f"/api/v1/organizations/{org_id}/agents/{agent_id}/revoke"
    )
    assert res_rev.status_code == 200
    assert res_rev.json()["status"] == "revoked"

    # Transition 3: revoked -> suspended REJECTED (terminal state)
    res_re_susp = await async_client.post(
        f"/api/v1/organizations/{org_id}/agents/{agent_id}/suspend"
    )
    assert res_re_susp.status_code == 409
    assert "Cannot suspend a revoked agent" in res_re_susp.json()["detail"]

    # Transition 4: revoked cannot be updated
    res_update_rev = await async_client.patch(
        f"/api/v1/organizations/{org_id}/agents/{agent_id}",
        json={"name": "Renamed Revoked"},
    )
    assert res_update_rev.status_code == 409
    assert "Cannot update configuration of a revoked agent" in res_update_rev.json()["detail"]


@pytest.mark.asyncio
async def test_list_agents_strictly_scoped_to_organization(
    async_client: AsyncClient,
) -> None:
    """Ensure listing agents returns only the agents belonging to the specified organization."""
    # Org 1 with 2 agents
    org1_id = (
        await async_client.post("/api/v1/organizations", json={"name": "Org One List"})
    ).json()["id"]
    await async_client.post(
        f"/api/v1/organizations/{org1_id}/agents", json={"name": "Agent 1A"}
    )
    await async_client.post(
        f"/api/v1/organizations/{org1_id}/agents", json={"name": "Agent 1B"}
    )

    # Org 2 with 1 agent
    org2_id = (
        await async_client.post("/api/v1/organizations", json={"name": "Org Two List"})
    ).json()["id"]
    await async_client.post(
        f"/api/v1/organizations/{org2_id}/agents", json={"name": "Agent 2A"}
    )

    # List Org 1
    list1_res = await async_client.get(f"/api/v1/organizations/{org1_id}/agents")
    assert list1_res.status_code == 200
    list1_data = list1_res.json()
    assert list1_data["total"] == 2
    assert {item["name"] for item in list1_data["items"]} == {"Agent 1A", "Agent 1B"}

    # List Org 2
    list2_res = await async_client.get(f"/api/v1/organizations/{org2_id}/agents")
    assert list2_res.status_code == 200
    list2_data = list2_res.json()
    assert list2_data["total"] == 1
    assert list2_data["items"][0]["name"] == "Agent 2A"


@pytest.mark.asyncio
async def test_update_agent_configuration(async_client: AsyncClient) -> None:
    """Ensure an active agent's configuration can be updated via PATCH."""
    org_id = (
        await async_client.post("/api/v1/organizations", json={"name": "Patch Org"})
    ).json()["id"]
    agent_id = (
        await async_client.post(
            f"/api/v1/organizations/{org_id}/agents",
            json={
                "name": "Original Name",
                "description": "Original Desc",
                "environment": "development",
            },
        )
    ).json()["id"]

    patch_payload = {
        "name": "Updated Name",
        "description": "Updated Desc",
        "environment": "staging",
        "agent_type": "workflow",
    }
    patch_res = await async_client.patch(
        f"/api/v1/organizations/{org_id}/agents/{agent_id}", json=patch_payload
    )
    assert patch_res.status_code == 200
    data = patch_res.json()
    assert data["name"] == "Updated Name"
    assert data["description"] == "Updated Desc"
    assert data["environment"] == "staging"
    assert data["agent_type"] == "workflow"
    assert data["status"] == "active"
