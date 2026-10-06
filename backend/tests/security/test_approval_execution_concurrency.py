"""Approval and Execution Concurrency & Replay Protection Tests (Milestone 22)."""

import uuid
import pytest
from httpx import AsyncClient

from app.db.models.membership import MembershipRole


async def _setup_action_fixture(async_client: AsyncClient, op_risk_level: str = "low"):
    """Set up an action authorized to execute."""
    org_resp = await async_client.post("/api/v1/organizations", json={"name": f"Exec Concurrency {uuid.uuid4().hex[:6]}"})
    org_id = org_resp.json()["id"]

    # Admin user
    user_resp = await async_client.post(
        "/api/v1/users",
        json={"email": f"admin_{uuid.uuid4().hex[:6]}@custode.io", "display_name": "Admin"},
    )
    admin_id = user_resp.json()["id"]
    await async_client.post(
        f"/api/v1/organizations/{org_id}/memberships",
        json={"user_id": admin_id, "role": MembershipRole.organization_admin.value},
    )

    agent_resp = await async_client.post(
        f"/api/v1/organizations/{org_id}/agents",
        json={"name": "Worker", "environment": "development"},
    )
    agent_id = agent_resp.json()["id"]

    tool_resp = await async_client.post(
        f"/api/v1/organizations/{org_id}/tools",
        json={"name": "Internal System", "slug": "internal", "tool_type": "internal", "environment": "development"},
    )
    tool_id = tool_resp.json()["id"]

    op_resp = await async_client.post(
        f"/api/v1/organizations/{org_id}/tools/{tool_id}/operations",
        json={"name": "Health Check", "slug": "health_check", "operation_type": "read", "risk_level": op_risk_level},
    )
    op_id = op_resp.json()["id"]

    # Explicit Allow Permission
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

    # RuntimeAction
    action_resp = await async_client.post(
        f"/api/v1/organizations/{org_id}/runtime-actions",
        json={
            "tool_id": tool_id,
            "operation_id": op_id,
            "action_type": "tool_call",
            "environment": "development",
            "parameters": {},
        },
        headers={"X-Agent-ID": agent_id},
    )
    assert action_resp.status_code == 201, action_resp.text
    action_id = action_resp.json()["id"]

    return org_id, action_id, admin_id


@pytest.mark.asyncio
async def test_execution_replay_and_duplicate_blocked(async_client: AsyncClient):
    """Verify that an executed RuntimeAction cannot be replayed or executed twice."""
    org_id, action_id, admin_id = await _setup_action_fixture(async_client, op_risk_level="low")

    # 1. First execution succeeds
    exec1_resp = await async_client.post(
        f"/api/v1/organizations/{org_id}/runtime-actions/{action_id}/execute"
    )
    assert exec1_resp.status_code == 200, exec1_resp.text
    assert exec1_resp.json()["status"] == "succeeded"

    # 2. Second execution attempt must fail with 409 Conflict (DUPLICATE_EXECUTION)
    exec2_resp = await async_client.post(
        f"/api/v1/organizations/{org_id}/runtime-actions/{action_id}/execute"
    )
    assert exec2_resp.status_code == 409
    assert "already been executed" in exec2_resp.json()["detail"].lower()


@pytest.mark.asyncio
async def test_approval_lifecycle_state_machine_prevents_double_action(async_client: AsyncClient):
    """Verify that an already approved or rejected approval request cannot be re-acted upon."""
    org_id, action_id, admin_id = await _setup_action_fixture(async_client, op_risk_level="high")

    # Decide action -> High risk generates REQUIRE_APPROVAL decision
    dec_resp = await async_client.post(
        f"/api/v1/organizations/{org_id}/runtime-actions/{action_id}/decide"
    )
    assert dec_resp.status_code == 201
    dec_id = dec_resp.json()["id"]
    assert dec_resp.json()["decision"] == "require_approval"

    # Create approval request
    appr_resp = await async_client.post(
        f"/api/v1/organizations/{org_id}/runtime-actions/{action_id}/approval",
        json={"decision_id": dec_id, "reason": "Requires governance"},
    )
    assert appr_resp.status_code == 201
    appr_id = appr_resp.json()["id"]

    # 1. First approval succeeds
    appr_action = await async_client.post(
        f"/api/v1/organizations/{org_id}/approvals/{appr_id}/approve",
        headers={"X-User-ID": admin_id},
    )
    assert appr_action.status_code == 200
    assert appr_action.json()["status"] == "approved"

    # 2. Second approval attempt on the already approved request must fail with 409 Conflict
    second_appr = await async_client.post(
        f"/api/v1/organizations/{org_id}/approvals/{appr_id}/approve",
        headers={"X-User-ID": admin_id},
    )
    assert second_appr.status_code == 409
    assert "Cannot approve" in second_appr.json()["detail"]

    # 3. Rejecting an already approved request must also fail with 409 Conflict
    reject_appr = await async_client.post(
        f"/api/v1/organizations/{org_id}/approvals/{appr_id}/reject",
        json={"rejection_reason": "Too late"},
        headers={"X-User-ID": admin_id},
    )
    assert reject_appr.status_code == 409
    assert "Cannot reject" in reject_appr.json()["detail"]
