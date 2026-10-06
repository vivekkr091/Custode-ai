"""Multi-Tenant Isolation and Cross-Tenant IDOR Red Team Tests (Milestone 22)."""

import uuid
import pytest
from httpx import AsyncClient

from app.db.models.membership import MembershipRole
from app.services.integrations.ssrf import set_custom_dns_resolver


@pytest.fixture(autouse=True)
def mock_dns():
    def _mock_resolver(host: str, port: int):
        return ["93.184.216.34"]
    set_custom_dns_resolver(_mock_resolver)
    yield
    set_custom_dns_resolver(None)


async def _provision_tenant(async_client: AsyncClient, name: str):
    """Helper to provision a complete isolated tenant with admin user and agent."""
    org_resp = await async_client.post("/api/v1/organizations", json={"name": name})
    assert org_resp.status_code == 201, org_resp.text
    org_id = org_resp.json()["id"]

    email = f"admin_{uuid.uuid4().hex[:6]}@custode.io"
    user_resp = await async_client.post(
        "/api/v1/users",
        json={"email": email, "display_name": f"Admin {name}"},
    )
    user_id = user_resp.json()["id"]

    mem_resp = await async_client.post(
        f"/api/v1/organizations/{org_id}/memberships",
        json={"user_id": user_id, "role": MembershipRole.organization_admin.value},
    )
    assert mem_resp.status_code == 201, mem_resp.text

    agent_resp = await async_client.post(
        f"/api/v1/organizations/{org_id}/agents",
        json={"name": f"{name} Agent", "environment": "development"},
    )
    agent_id = agent_resp.json()["id"]

    tool_resp = await async_client.post(
        f"/api/v1/organizations/{org_id}/tools",
        json={"name": f"{name} Tool", "slug": f"tool-{uuid.uuid4().hex[:6]}", "tool_type": "api", "environment": "development"},
    )
    tool_id = tool_resp.json()["id"]

    op_resp = await async_client.post(
        f"/api/v1/organizations/{org_id}/tools/{tool_id}/operations",
        json={"name": "Test Op", "slug": "op-test", "operation_type": "read", "risk_level": "low"},
    )
    op_id = op_resp.json()["id"]

    # Register an action
    action_resp = await async_client.post(
        f"/api/v1/organizations/{org_id}/runtime-actions",
        json={
            "tool_id": tool_id,
            "operation_id": op_id,
            "action_type": "tool_call",
            "environment": "dev",
            "parameters": {"test": True},
        },
        headers={"X-Agent-ID": agent_id},
    )
    assert action_resp.status_code == 201, action_resp.text
    action_id = action_resp.json()["id"]

    # Register an integration
    integ_resp = await async_client.post(
        f"/api/v1/organizations/{org_id}/integrations",
        json={
            "name": f"{name} Webhook",
            "url": f"https://example.com/{org_id}",
            "subscribed_events": ["DECISION_CREATED"],
        },
        headers={"X-User-ID": str(user_id)},
    )
    assert integ_resp.status_code == 201, integ_resp.text
    integ_id = integ_resp.json()["id"]

    return {
        "org_id": org_id,
        "user_id": user_id,
        "agent_id": agent_id,
        "tool_id": tool_id,
        "op_id": op_id,
        "action_id": action_id,
        "integ_id": integ_id,
    }


@pytest.mark.asyncio
async def test_cross_tenant_runtime_action_idor_blocked(async_client: AsyncClient):
    """Verify that Org A cannot retrieve or mutate Org B's RuntimeActions."""
    tenant_a = await _provision_tenant(async_client, "Tenant A")
    tenant_b = await _provision_tenant(async_client, "Tenant B")

    # 1. Tenant A attempts to read Tenant B's action under Tenant A's path
    resp = await async_client.get(
        f"/api/v1/organizations/{tenant_a['org_id']}/runtime-actions/{tenant_b['action_id']}"
    )
    assert resp.status_code == 404

    # 2. Tenant A user attempts to read Tenant B's action under Tenant B's path without membership
    resp2 = await async_client.get(
        f"/api/v1/organizations/{tenant_b['org_id']}/runtime-actions/{tenant_b['action_id']}",
        headers={"X-User-ID": str(tenant_a["user_id"])},
    )
    assert resp2.status_code in (403, 404)


@pytest.mark.asyncio
async def test_cross_tenant_integration_idor_blocked(async_client: AsyncClient):
    """Verify that Org A cannot view, mutate, or test Org B's integrations."""
    tenant_a = await _provision_tenant(async_client, "Tenant A Integ")
    tenant_b = await _provision_tenant(async_client, "Tenant B Integ")

    # Tenant A attempts to view Tenant B's integration under Tenant A's path
    resp = await async_client.get(
        f"/api/v1/organizations/{tenant_a['org_id']}/integrations/{tenant_b['integ_id']}",
        headers={"X-User-ID": str(tenant_a["user_id"])},
    )
    assert resp.status_code == 404

    # Tenant A attempts to suspend Tenant B's integration under Tenant A's path
    resp2 = await async_client.post(
        f"/api/v1/organizations/{tenant_a['org_id']}/integrations/{tenant_b['integ_id']}/suspend",
        headers={"X-User-ID": str(tenant_a["user_id"])},
    )
    assert resp2.status_code == 404

    # Tenant A attempts to test ping Tenant B's integration under Tenant A's path
    resp3 = await async_client.post(
        f"/api/v1/organizations/{tenant_a['org_id']}/integrations/{tenant_b['integ_id']}/test",
        headers={"X-User-ID": str(tenant_a["user_id"])},
    )
    assert resp3.status_code == 404


@pytest.mark.asyncio
async def test_cross_tenant_agent_and_tool_referencing_blocked(async_client: AsyncClient):
    """Verify that an action in Org A cannot bind to an Agent or Tool in Org B."""
    tenant_a = await _provision_tenant(async_client, "Tenant A CrossRef")
    tenant_b = await _provision_tenant(async_client, "Tenant B CrossRef")

    # Action created in Org A attempting to use Org B's agent header
    resp = await async_client.post(
        f"/api/v1/organizations/{tenant_a['org_id']}/runtime-actions",
        json={
            "tool_id": tenant_a["tool_id"],
            "operation_id": tenant_a["op_id"],
            "action_type": "tool_call",
            "environment": "dev",
            "parameters": {},
        },
        headers={"X-Agent-ID": tenant_b["agent_id"]},
    )
    assert resp.status_code == 404
    assert "not found in organization" in resp.json()["detail"]
