"""Automated tests for Permission Engine, Authorization, Deny Precedence, and Tenant Boundaries."""

import uuid
from datetime import datetime, timedelta, timezone
import pytest
from httpx import AsyncClient
from sqlalchemy import select

from app.db.models.agent import Agent, AgentStatus
from app.db.models.organization import Organization, OrganizationStatus
from app.db.models.tool import Tool, ToolStatus
from app.db.models.tool_operation import OperationStatus, ToolOperation
from tests.conftest import TestingSessionLocal


async def setup_test_hierarchy(async_client: AsyncClient, name: str = "Test Org"):
    """Helper to provision a clean Org -> Agent and Org -> Tool -> Operation hierarchy."""
    org = (await async_client.post("/api/v1/organizations", json={"name": name})).json()
    org_id = org["id"]

    agent = (
        await async_client.post(
            f"/api/v1/organizations/{org_id}/agents", json={"name": f"{name} Agent"}
        )
    ).json()
    agent_id = agent["id"]

    tool = (
        await async_client.post(
            f"/api/v1/organizations/{org_id}/tools", json={"name": f"{name} Tool"}
        )
    ).json()
    tool_id = tool["id"]

    operation = (
        await async_client.post(
            f"/api/v1/organizations/{org_id}/tools/{tool_id}/operations",
            json={"name": "Read Operation", "operation_type": "read"},
        )
    ).json()
    operation_id = operation["id"]

    return org_id, agent_id, tool_id, operation_id


@pytest.mark.asyncio
async def test_create_allow_and_deny_permissions(async_client: AsyncClient) -> None:
    """Ensure both allow and explicit deny permissions can be created."""
    org_id, agent_id, tool_id, op_id = await setup_test_hierarchy(async_client, "Grants Org")

    # 1. Create ALLOW permission
    allow_payload = {
        "agent_id": agent_id,
        "tool_id": tool_id,
        "operation_id": op_id,
        "environment": "development",
        "effect": "allow",
    }
    allow_res = await async_client.post(
        f"/api/v1/organizations/{org_id}/permissions", json=allow_payload
    )
    assert allow_res.status_code == 201
    allow_data = allow_res.json()
    assert allow_data["effect"] == "allow"
    assert allow_data["status"] == "active"
    assert allow_data["environment"] == "development"

    # 2. Create DENY permission (for production)
    deny_payload = {
        "agent_id": agent_id,
        "tool_id": tool_id,
        "operation_id": op_id,
        "environment": "production",
        "effect": "deny",
    }
    deny_res = await async_client.post(
        f"/api/v1/organizations/{org_id}/permissions", json=deny_payload
    )
    assert deny_res.status_code == 201
    assert deny_res.json()["effect"] == "deny"


@pytest.mark.asyncio
async def test_create_permission_hierarchy_and_inactive_rejections(
    async_client: AsyncClient,
) -> None:
    """Ensure permission creation rejects invalid hierarchies, non-existent, and inactive resources."""
    org_id, agent_id, tool_id, op_id = await setup_test_hierarchy(async_client, "Validation Org")
    fake_id = str(uuid.uuid4())

    # Invalid Org -> 404
    res_fake_org = await async_client.post(
        f"/api/v1/organizations/{fake_id}/permissions",
        json={
            "agent_id": agent_id,
            "tool_id": tool_id,
            "operation_id": op_id,
            "environment": "development",
        },
    )
    assert res_fake_org.status_code == 404

    # Invalid Agent -> 404
    res_fake_agent = await async_client.post(
        f"/api/v1/organizations/{org_id}/permissions",
        json={
            "agent_id": fake_id,
            "tool_id": tool_id,
            "operation_id": op_id,
            "environment": "development",
        },
    )
    assert res_fake_agent.status_code == 404

    # Suspended Agent -> 409
    await async_client.post(f"/api/v1/organizations/{org_id}/agents/{agent_id}/suspend")
    res_susp_agent = await async_client.post(
        f"/api/v1/organizations/{org_id}/permissions",
        json={
            "agent_id": agent_id,
            "tool_id": tool_id,
            "operation_id": op_id,
            "environment": "development",
        },
    )
    assert res_susp_agent.status_code == 409
    assert "agent" in res_susp_agent.json()["detail"]


@pytest.mark.asyncio
async def test_duplicate_identical_permission_rejected(async_client: AsyncClient) -> None:
    """Ensure duplicate permission with identical effect is rejected with HTTP 409."""
    org_id, agent_id, tool_id, op_id = await setup_test_hierarchy(async_client, "Dup Org")

    payload = {
        "agent_id": agent_id,
        "tool_id": tool_id,
        "operation_id": op_id,
        "environment": "staging",
        "effect": "allow",
    }
    res1 = await async_client.post(f"/api/v1/organizations/{org_id}/permissions", json=payload)
    assert res1.status_code == 201

    res2 = await async_client.post(f"/api/v1/organizations/{org_id}/permissions", json=payload)
    assert res2.status_code == 409
    assert "already exists" in res2.json()["detail"]


@pytest.mark.asyncio
async def test_permission_evaluation_default_deny(async_client: AsyncClient) -> None:
    """Ensure default deny is enforced when no permission exists."""
    org_id, agent_id, tool_id, op_id = await setup_test_hierarchy(async_client, "Default Deny Org")

    eval_payload = {
        "agent_id": agent_id,
        "tool_id": tool_id,
        "operation_id": op_id,
        "environment": "development",
    }
    res = await async_client.post(
        f"/api/v1/organizations/{org_id}/permissions/evaluate", json=eval_payload
    )
    assert res.status_code == 200
    decision = res.json()
    assert decision["allowed"] is False
    assert decision["effect"] == "deny"
    assert "No matching permission found" in decision["reason"]
    assert decision["permission_id"] is None


@pytest.mark.asyncio
async def test_permission_evaluation_allow_and_deny_precedence(async_client: AsyncClient) -> None:
    """Ensure matching allow returns ALLOW, matching deny returns DENY, and allow + deny evaluates to DENY."""
    org_id, agent_id, tool_id, op_id = await setup_test_hierarchy(async_client, "Precedence Org")

    # 1. Grant ALLOW
    allow_perm = (
        await async_client.post(
            f"/api/v1/organizations/{org_id}/permissions",
            json={
                "agent_id": agent_id,
                "tool_id": tool_id,
                "operation_id": op_id,
                "environment": "development",
                "effect": "allow",
            },
        )
    ).json()

    # Evaluation with ALLOW only -> ALLOW
    res_allow = await async_client.post(
        f"/api/v1/organizations/{org_id}/permissions/evaluate",
        json={
            "agent_id": agent_id,
            "tool_id": tool_id,
            "operation_id": op_id,
            "environment": "development",
        },
    )
    assert res_allow.status_code == 200
    dec_allow = res_allow.json()
    assert dec_allow["allowed"] is True
    assert dec_allow["effect"] == "allow"
    assert dec_allow["permission_id"] == allow_perm["id"]
    assert "Active allow permission matched" in dec_allow["reason"]

    # 2. Grant explicit DENY for the exact same target
    deny_perm = (
        await async_client.post(
            f"/api/v1/organizations/{org_id}/permissions",
            json={
                "agent_id": agent_id,
                "tool_id": tool_id,
                "operation_id": op_id,
                "environment": "development",
                "effect": "deny",
            },
        )
    ).json()

    # Evaluation with BOTH ALLOW and DENY -> DENY (Deny Precedence)
    res_both = await async_client.post(
        f"/api/v1/organizations/{org_id}/permissions/evaluate",
        json={
            "agent_id": agent_id,
            "tool_id": tool_id,
            "operation_id": op_id,
            "environment": "development",
        },
    )
    assert res_both.status_code == 200
    dec_both = res_both.json()
    assert dec_both["allowed"] is False
    assert dec_both["effect"] == "deny"
    assert dec_both["permission_id"] == deny_perm["id"]
    assert "Explicit deny permission matched" in dec_both["reason"]


@pytest.mark.asyncio
async def test_permission_evaluation_dimension_mismatches(async_client: AsyncClient) -> None:
    """Ensure permission does not authorize actions when agent, tool, operation, or environment differs."""
    org_id, agent_id, tool_id, op_id = await setup_test_hierarchy(async_client, "Mismatch Org")

    # Authorize Agent in development
    await async_client.post(
        f"/api/v1/organizations/{org_id}/permissions",
        json={
            "agent_id": agent_id,
            "tool_id": tool_id,
            "operation_id": op_id,
            "environment": "development",
            "effect": "allow",
        },
    )

    # 1. Different environment (production) -> DENY
    res_env = await async_client.post(
        f"/api/v1/organizations/{org_id}/permissions/evaluate",
        json={
            "agent_id": agent_id,
            "tool_id": tool_id,
            "operation_id": op_id,
            "environment": "production",
        },
    )
    assert res_env.json()["allowed"] is False

    # 2. Different agent -> DENY
    other_agent = (
        await async_client.post(
            f"/api/v1/organizations/{org_id}/agents", json={"name": "Other Agent"}
        )
    ).json()["id"]
    res_agent = await async_client.post(
        f"/api/v1/organizations/{org_id}/permissions/evaluate",
        json={
            "agent_id": other_agent,
            "tool_id": tool_id,
            "operation_id": op_id,
            "environment": "development",
        },
    )
    assert res_agent.json()["allowed"] is False


@pytest.mark.asyncio
async def test_permission_evaluation_expiration(async_client: AsyncClient) -> None:
    """Ensure expired allow is ignored (resulting in DENY), and expired deny does not block valid allow."""
    org_id, agent_id, tool_id, op_id = await setup_test_hierarchy(async_client, "Expire Org")

    past_time = (datetime.now(timezone.utc) - timedelta(hours=1)).isoformat()

    # Expired allow permission
    await async_client.post(
        f"/api/v1/organizations/{org_id}/permissions",
        json={
            "agent_id": agent_id,
            "tool_id": tool_id,
            "operation_id": op_id,
            "environment": "development",
            "effect": "allow",
            "expires_at": past_time,
        },
    )

    # Should default deny because the only allow is expired
    res_exp = await async_client.post(
        f"/api/v1/organizations/{org_id}/permissions/evaluate",
        json={
            "agent_id": agent_id,
            "tool_id": tool_id,
            "operation_id": op_id,
            "environment": "development",
        },
    )
    assert res_exp.json()["allowed"] is False
    assert "No matching permission found" in res_exp.json()["reason"]


@pytest.mark.asyncio
async def test_permission_lifecycle(async_client: AsyncClient) -> None:
    """Ensure permission can be suspended and revoked, and suspended/revoked permissions do not authorize."""
    org_id, agent_id, tool_id, op_id = await setup_test_hierarchy(async_client, "Life Org")

    perm = (
        await async_client.post(
            f"/api/v1/organizations/{org_id}/permissions",
            json={
                "agent_id": agent_id,
                "tool_id": tool_id,
                "operation_id": op_id,
                "environment": "development",
                "effect": "allow",
            },
        )
    ).json()
    perm_id = perm["id"]

    # 1. Suspend permission
    res_susp = await async_client.post(
        f"/api/v1/organizations/{org_id}/permissions/{perm_id}/suspend"
    )
    assert res_susp.status_code == 200
    assert res_susp.json()["status"] == "suspended"

    # Evaluates to DENY when suspended
    res_eval_susp = await async_client.post(
        f"/api/v1/organizations/{org_id}/permissions/evaluate",
        json={
            "agent_id": agent_id,
            "tool_id": tool_id,
            "operation_id": op_id,
            "environment": "development",
        },
    )
    assert res_eval_susp.json()["allowed"] is False

    # 2. Revoke permission
    res_rev = await async_client.post(
        f"/api/v1/organizations/{org_id}/permissions/{perm_id}/revoke"
    )
    assert res_rev.status_code == 200
    assert res_rev.json()["status"] == "revoked"

    # Revoked cannot be suspended
    res_invalid = await async_client.post(
        f"/api/v1/organizations/{org_id}/permissions/{perm_id}/suspend"
    )
    assert res_invalid.status_code == 409


@pytest.mark.asyncio
async def test_tenant_isolation_for_permissions(async_client: AsyncClient) -> None:
    """Ensure cross-tenant permission creation, access, and evaluation are strictly blocked."""
    org_a, agent_a, tool_a, op_a = await setup_test_hierarchy(async_client, "Tenant A")
    org_b, agent_b, tool_b, op_b = await setup_test_hierarchy(async_client, "Tenant B")

    # Org A creates permission
    perm_a = (
        await async_client.post(
            f"/api/v1/organizations/{org_a}/permissions",
            json={
                "agent_id": agent_a,
                "tool_id": tool_a,
                "operation_id": op_a,
                "environment": "development",
                "effect": "allow",
            },
        )
    ).json()
    perm_a_id = perm_a["id"]

    # 1. Org B cannot retrieve Org A's permission -> 404
    res_get = await async_client.get(f"/api/v1/organizations/{org_b}/permissions/{perm_a_id}")
    assert res_get.status_code == 404

    # 2. Org A cannot create permission using Org B's agent -> 404
    res_cross_agent = await async_client.post(
        f"/api/v1/organizations/{org_a}/permissions",
        json={
            "agent_id": agent_b,
            "tool_id": tool_a,
            "operation_id": op_a,
            "environment": "development",
            "effect": "allow",
        },
    )
    assert res_cross_agent.status_code == 404

    # 3. Org A cannot create permission using Org B's tool -> 404
    res_cross_tool = await async_client.post(
        f"/api/v1/organizations/{org_a}/permissions",
        json={
            "agent_id": agent_a,
            "tool_id": tool_b,
            "operation_id": op_a,
            "environment": "development",
            "effect": "allow",
        },
    )
    assert res_cross_tool.status_code == 404

    # 4. Org B evaluating Org A's resources -> DENY (resource not in org)
    res_cross_eval = await async_client.post(
        f"/api/v1/organizations/{org_b}/permissions/evaluate",
        json={
            "agent_id": agent_a,
            "tool_id": tool_a,
            "operation_id": op_a,
            "environment": "development",
        },
    )
    assert res_cross_eval.status_code == 200
    assert res_cross_eval.json()["allowed"] is False
    assert "does not belong to organization" in res_cross_eval.json()["reason"]
