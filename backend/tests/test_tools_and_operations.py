"""Automated tests for Tool Registry, Tool Operations, Lifecycle, and Tenant Isolation."""

import uuid
import pytest
from httpx import AsyncClient
from sqlalchemy import select

from app.db.models.organization import Organization, OrganizationStatus
from tests.conftest import TestingSessionLocal


@pytest.mark.asyncio
async def test_create_tool_success_and_defaults(async_client: AsyncClient) -> None:
    """Ensure a tool can be registered with generated slug, active status, and default environment."""
    org_res = await async_client.post(
        "/api/v1/organizations", json={"name": "Tools Test Org"}
    )
    org_id = org_res.json()["id"]

    # 1. Full payload
    payload = {
        "name": "GitHub Integration API",
        "description": "Internal GitHub integration",
        "tool_type": "api",
        "environment": "production",
        "endpoint": "https://api.github.com",
    }
    res = await async_client.post(
        f"/api/v1/organizations/{org_id}/tools", json=payload
    )
    assert res.status_code == 201
    data = res.json()
    assert data["name"] == "GitHub Integration API"
    assert data["slug"] == "github-integration-api"
    assert data["description"] == "Internal GitHub integration"
    assert data["tool_type"] == "api"
    assert data["status"] == "active"
    assert data["environment"] == "production"
    assert data["endpoint"] == "https://api.github.com"
    assert data["organization_id"] == org_id
    assert "id" in data
    assert "created_at" in data
    assert "updated_at" in data

    # 2. Defaults payload
    res_default = await async_client.post(
        f"/api/v1/organizations/{org_id}/tools", json={"name": "Default Shell"}
    )
    assert res_default.status_code == 201
    data_def = res_default.json()
    assert data_def["slug"] == "default-shell"
    assert data_def["status"] == "active"
    assert data_def["environment"] == "development"
    assert data_def["tool_type"] == "api"


@pytest.mark.asyncio
async def test_tool_slug_uniqueness_within_org_and_cross_org(async_client: AsyncClient) -> None:
    """Ensure tool slug is unique within an organization, but allowed across different organizations."""
    org1 = (await async_client.post("/api/v1/organizations", json={"name": "Org 1 Tools"})).json()["id"]
    org2 = (await async_client.post("/api/v1/organizations", json={"name": "Org 2 Tools"})).json()["id"]

    # First tool in Org 1
    res1 = await async_client.post(
        f"/api/v1/organizations/{org1}/tools", json={"name": "Postgres DB"}
    )
    assert res1.status_code == 201
    assert res1.json()["slug"] == "postgres-db"

    # Duplicate slug in Org 1 must be rejected with 409
    res_dup = await async_client.post(
        f"/api/v1/organizations/{org1}/tools", json={"name": "Postgres DB"}
    )
    assert res_dup.status_code == 409
    assert "already exists in organization" in res_dup.json()["detail"]

    # Same slug in Org 2 must succeed (composite uniqueness)
    res_org2 = await async_client.post(
        f"/api/v1/organizations/{org2}/tools", json={"name": "Postgres DB"}
    )
    assert res_org2.status_code == 201
    assert res_org2.json()["slug"] == "postgres-db"
    assert res1.json()["id"] != res_org2.json()["id"]


@pytest.mark.asyncio
async def test_tool_retrieval_and_listing(async_client: AsyncClient) -> None:
    """Ensure tools can be retrieved and listed scoped strictly to an organization."""
    org_id = (await async_client.post("/api/v1/organizations", json={"name": "Listing Org"})).json()["id"]

    tool1 = (
        await async_client.post(f"/api/v1/organizations/{org_id}/tools", json={"name": "Tool One"})
    ).json()
    tool2 = (
        await async_client.post(f"/api/v1/organizations/{org_id}/tools", json={"name": "Tool Two"})
    ).json()

    # Get single tool
    get_res = await async_client.get(f"/api/v1/organizations/{org_id}/tools/{tool1['id']}")
    assert get_res.status_code == 200
    assert get_res.json()["name"] == "Tool One"

    # Missing tool returns 404
    fake_id = str(uuid.uuid4())
    missing_res = await async_client.get(f"/api/v1/organizations/{org_id}/tools/{fake_id}")
    assert missing_res.status_code == 404

    # List tools
    list_res = await async_client.get(f"/api/v1/organizations/{org_id}/tools")
    assert list_res.status_code == 200
    list_data = list_res.json()
    assert list_data["total"] == 2
    names = {item["name"] for item in list_data["items"]}
    assert names == {"Tool One", "Tool Two"}


@pytest.mark.asyncio
async def test_tool_lifecycle_transitions(async_client: AsyncClient) -> None:
    """Ensure valid tool lifecycle transitions succeed and invalid transitions fail with HTTP 409."""
    org_id = (await async_client.post("/api/v1/organizations", json={"name": "Lifecycle Org"})).json()["id"]
    tool_id = (
        await async_client.post(f"/api/v1/organizations/{org_id}/tools", json={"name": "Lifecycle Tool"})
    ).json()["id"]

    # 1. active -> suspended
    res_susp = await async_client.post(f"/api/v1/organizations/{org_id}/tools/{tool_id}/suspend")
    assert res_susp.status_code == 200
    assert res_susp.json()["status"] == "suspended"

    # 2. suspended -> revoked
    res_rev = await async_client.post(f"/api/v1/organizations/{org_id}/tools/{tool_id}/revoke")
    assert res_rev.status_code == 200
    assert res_rev.json()["status"] == "revoked"

    # 3. revoked -> suspended (REJECTED)
    res_rev_susp = await async_client.post(f"/api/v1/organizations/{org_id}/tools/{tool_id}/suspend")
    assert res_rev_susp.status_code == 409
    assert "Cannot suspend a revoked tool" in res_rev_susp.json()["detail"]

    # 4. revoked cannot be updated
    res_patch = await async_client.patch(
        f"/api/v1/organizations/{org_id}/tools/{tool_id}", json={"name": "New Name"}
    )
    assert res_patch.status_code == 409
    assert "Cannot update configuration of a revoked tool" in res_patch.json()["detail"]


@pytest.mark.asyncio
async def test_operation_creation_and_defaults(async_client: AsyncClient) -> None:
    """Ensure tool operations can be created with generated slug, baseline risk, and default status."""
    org_id = (await async_client.post("/api/v1/organizations", json={"name": "Op Org"})).json()["id"]
    tool_id = (
        await async_client.post(f"/api/v1/organizations/{org_id}/tools", json={"name": "GitHub Tool"})
    ).json()["id"]

    payload = {
        "name": "Repository Delete",
        "description": "Permanently delete a repository",
        "operation_type": "delete",
        "risk_level": "critical",
    }
    res = await async_client.post(
        f"/api/v1/organizations/{org_id}/tools/{tool_id}/operations", json=payload
    )
    assert res.status_code == 201
    data = res.json()
    assert data["name"] == "Repository Delete"
    assert data["slug"] == "repository-delete"
    assert data["description"] == "Permanently delete a repository"
    assert data["operation_type"] == "delete"
    assert data["risk_level"] == "critical"
    assert data["status"] == "active"
    assert data["tool_id"] == tool_id
    assert "id" in data
    assert "created_at" in data
    assert "updated_at" in data

    # Test operation defaults
    res_def = await async_client.post(
        f"/api/v1/organizations/{org_id}/tools/{tool_id}/operations",
        json={"name": "Default Read"},
    )
    assert res_def.status_code == 201
    data_def = res_def.json()
    assert data_def["slug"] == "default-read"
    assert data_def["operation_type"] == "read"
    assert data_def["risk_level"] == "medium"
    assert data_def["status"] == "active"


@pytest.mark.asyncio
async def test_operation_slug_uniqueness_on_tool_and_across_tools(async_client: AsyncClient) -> None:
    """Ensure operation slug is unique per tool, but duplicate slugs on different tools succeed."""
    org_id = (await async_client.post("/api/v1/organizations", json={"name": "Op Slug Org"})).json()["id"]

    tool1_id = (
        await async_client.post(f"/api/v1/organizations/{org_id}/tools", json={"name": "Tool A"})
    ).json()["id"]
    tool2_id = (
        await async_client.post(f"/api/v1/organizations/{org_id}/tools", json={"name": "Tool B"})
    ).json()["id"]

    # Op 1 on Tool 1
    res1 = await async_client.post(
        f"/api/v1/organizations/{org_id}/tools/{tool1_id}/operations", json={"name": "File Read"}
    )
    assert res1.status_code == 201
    assert res1.json()["slug"] == "file-read"

    # Duplicate Op on same Tool 1 must fail with 409
    res_dup = await async_client.post(
        f"/api/v1/organizations/{org_id}/tools/{tool1_id}/operations", json={"name": "File Read"}
    )
    assert res_dup.status_code == 409
    assert "already exists under tool" in res_dup.json()["detail"]

    # Same Op slug on Tool 2 must succeed
    res_tool2 = await async_client.post(
        f"/api/v1/organizations/{org_id}/tools/{tool2_id}/operations", json={"name": "File Read"}
    )
    assert res_tool2.status_code == 201
    assert res_tool2.json()["slug"] == "file-read"
    assert res1.json()["id"] != res_tool2.json()["id"]


@pytest.mark.asyncio
async def test_operation_lifecycle_transitions(async_client: AsyncClient) -> None:
    """Ensure operation lifecycle transitions (active -> suspended -> revoked) work and revoked is terminal."""
    org_id = (await async_client.post("/api/v1/organizations", json={"name": "Op Life Org"})).json()["id"]
    tool_id = (
        await async_client.post(f"/api/v1/organizations/{org_id}/tools", json={"name": "Op Life Tool"})
    ).json()["id"]
    op_id = (
        await async_client.post(
            f"/api/v1/organizations/{org_id}/tools/{tool_id}/operations", json={"name": "Execute Script"}
        )
    ).json()["id"]

    # 1. active -> suspended
    res_susp = await async_client.post(
        f"/api/v1/organizations/{org_id}/tools/{tool_id}/operations/{op_id}/suspend"
    )
    assert res_susp.status_code == 200
    assert res_susp.json()["status"] == "suspended"

    # 2. suspended -> revoked
    res_rev = await async_client.post(
        f"/api/v1/organizations/{org_id}/tools/{tool_id}/operations/{op_id}/revoke"
    )
    assert res_rev.status_code == 200
    assert res_rev.json()["status"] == "revoked"

    # 3. revoked -> suspended (REJECTED)
    res_rev_susp = await async_client.post(
        f"/api/v1/organizations/{org_id}/tools/{tool_id}/operations/{op_id}/suspend"
    )
    assert res_rev_susp.status_code == 409
    assert "Cannot suspend a revoked operation" in res_rev_susp.json()["detail"]

    # 4. revoked cannot be updated
    res_patch = await async_client.patch(
        f"/api/v1/organizations/{org_id}/tools/{tool_id}/operations/{op_id}",
        json={"name": "Renamed Op"},
    )
    assert res_patch.status_code == 409
    assert "Cannot update configuration of a revoked operation" in res_patch.json()["detail"]


@pytest.mark.asyncio
async def test_tenant_isolation_for_tools_and_operations(async_client: AsyncClient) -> None:
    """Ensure tenant boundaries are strictly enforced across tools and tool operations."""
    # Org A
    org_a = (await async_client.post("/api/v1/organizations", json={"name": "Org A Tools"})).json()["id"]
    tool_a = (
        await async_client.post(f"/api/v1/organizations/{org_a}/tools", json={"name": "Tool A"})
    ).json()["id"]
    op_a = (
        await async_client.post(
            f"/api/v1/organizations/{org_a}/tools/{tool_a}/operations", json={"name": "Action A"}
        )
    ).json()["id"]

    # Org B
    org_b = (await async_client.post("/api/v1/organizations", json={"name": "Org B Tools"})).json()["id"]
    tool_b = (
        await async_client.post(f"/api/v1/organizations/{org_b}/tools", json={"name": "Tool B"})
    ).json()["id"]

    # 1. Org B cannot retrieve Org A's tool (returns 404)
    res_get_tool = await async_client.get(f"/api/v1/organizations/{org_b}/tools/{tool_a}")
    assert res_get_tool.status_code == 404

    # 2. Org B cannot update Org A's tool
    res_patch_tool = await async_client.patch(
        f"/api/v1/organizations/{org_b}/tools/{tool_a}", json={"name": "Hacked Tool"}
    )
    assert res_patch_tool.status_code == 404

    # 3. Org B cannot revoke Org A's tool
    res_rev_tool = await async_client.post(f"/api/v1/organizations/{org_b}/tools/{tool_a}/revoke")
    assert res_rev_tool.status_code == 404

    # 4. Org B cannot access Org A's operation
    res_get_op = await async_client.get(
        f"/api/v1/organizations/{org_b}/tools/{tool_a}/operations/{op_a}"
    )
    assert res_get_op.status_code == 404

    # 5. Org B cannot create an operation under Org A's tool
    res_create_op = await async_client.post(
        f"/api/v1/organizations/{org_b}/tools/{tool_a}/operations",
        json={"name": "Intruder Op"},
    )
    assert res_create_op.status_code == 404


@pytest.mark.asyncio
async def test_validation_errors(async_client: AsyncClient) -> None:
    """Ensure invalid types, environments, and risk levels return HTTP 422, and suspended orgs return HTTP 409."""
    org_id = (await async_client.post("/api/v1/organizations", json={"name": "Validation Org"})).json()["id"]

    # 1. Invalid tool_type -> 422
    res1 = await async_client.post(
        f"/api/v1/organizations/{org_id}/tools",
        json={"name": "Bad Tool", "tool_type": "quantum_hyperdrive"},
    )
    assert res1.status_code == 422

    # 2. Invalid environment -> 422
    res2 = await async_client.post(
        f"/api/v1/organizations/{org_id}/tools",
        json={"name": "Bad Env Tool", "environment": "metaverse"},
    )
    assert res2.status_code == 422

    # Create valid tool for operation tests
    tool_id = (
        await async_client.post(f"/api/v1/organizations/{org_id}/tools", json={"name": "Valid Tool"})
    ).json()["id"]

    # 3. Invalid operation_type -> 422
    res3 = await async_client.post(
        f"/api/v1/organizations/{org_id}/tools/{tool_id}/operations",
        json={"name": "Bad Op", "operation_type": "teleport"},
    )
    assert res3.status_code == 422

    # 4. Invalid risk_level -> 422
    res4 = await async_client.post(
        f"/api/v1/organizations/{org_id}/tools/{tool_id}/operations",
        json={"name": "Bad Risk Op", "risk_level": "apocalyptic"},
    )
    assert res4.status_code == 422

    # 5. Suspended organization cannot create tools
    async with TestingSessionLocal() as session:
        org = (
            await session.execute(
                select(Organization).where(Organization.id == uuid.UUID(org_id))
            )
        ).scalar_one()
        org.status = OrganizationStatus.suspended.value
        await session.commit()

    res5 = await async_client.post(
        f"/api/v1/organizations/{org_id}/tools", json={"name": "Blocked Tool"}
    )
    assert res5.status_code == 409
    assert "suspended organization" in res5.json()["detail"]
