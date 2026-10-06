"""Automated tests for CUSTODE Controlled Execution Layer and Execution Guard."""

from datetime import datetime, timedelta, timezone
from typing import Any, Dict, Optional
import uuid
import pytest
from httpx import AsyncClient

from app.db.models.approval import ApprovalStatus
from app.db.models.execution import ExecutionStatus
from app.db.models.membership import MembershipRole
from app.runtime.execution_registry import execution_registry
from app.runtime.executor import sanitize_parameters


async def create_user_and_membership(
    async_client: AsyncClient,
    org_id: str,
    email: str,
    role: str = MembershipRole.organization_admin.value,
) -> str:
    """Helper to create a user and grant them a membership in an organization."""
    user_resp = await async_client.post(
        "/api/v1/users",
        json={"email": email, "display_name": f"User {email}"},
    )
    assert user_resp.status_code == 201, user_resp.text
    user_id = user_resp.json()["id"]

    mem_resp = await async_client.post(
        f"/api/v1/organizations/{org_id}/memberships",
        json={"user_id": user_id, "role": role},
    )
    assert mem_resp.status_code == 201, mem_resp.text
    return user_id


async def provision_execution_fixture(
    async_client: AsyncClient,
    org_name: str = "Exec Org",
    tool_slug: Optional[str] = "internal",
    op_slug: Optional[str] = "health_check",
    op_risk_level: str = "low",
    permission_effect: str = "allow",
    action_params: Optional[Dict[str, Any]] = None,
):
    """Provision complete resource chain for execution tests."""
    unique_name = f"{org_name} {uuid.uuid4().hex[:6]}"
    org_resp = await async_client.post("/api/v1/organizations", json={"name": unique_name})
    assert org_resp.status_code == 201, org_resp.text
    org_id = org_resp.json()["id"]

    admin_id = await create_user_and_membership(
        async_client, org_id, f"admin_{uuid.uuid4().hex[:6]}@custode.io", MembershipRole.organization_admin.value
    )

    agent_resp = await async_client.post(
        f"/api/v1/organizations/{org_id}/agents",
        json={"name": "Worker Agent", "environment": "development"},
    )
    assert agent_resp.status_code == 201, agent_resp.text
    agent_id = agent_resp.json()["id"]

    tool_payload: Dict[str, Any] = {"name": "Internal Tool", "tool_type": "internal"}
    if tool_slug:
        tool_payload["slug"] = tool_slug
    tool_resp = await async_client.post(
        f"/api/v1/organizations/{org_id}/tools",
        json=tool_payload,
    )
    assert tool_resp.status_code == 201, tool_resp.text
    tool_id = tool_resp.json()["id"]
    tool_actual_slug = tool_resp.json()["slug"]

    op_payload: Dict[str, Any] = {
        "name": "Health Check Op",
        "operation_type": "read",
        "risk_level": op_risk_level,
    }
    if op_slug:
        op_payload["slug"] = op_slug
    op_resp = await async_client.post(
        f"/api/v1/organizations/{org_id}/tools/{tool_id}/operations",
        json=op_payload,
    )
    assert op_resp.status_code == 201, op_resp.text
    op_id = op_resp.json()["id"]
    op_actual_slug = op_resp.json()["slug"]

    if permission_effect:
        perm_resp = await async_client.post(
            f"/api/v1/organizations/{org_id}/permissions",
            json={
                "agent_id": agent_id,
                "tool_id": tool_id,
                "operation_id": op_id,
                "environment": "development",
                "effect": permission_effect,
            },
        )
        assert perm_resp.status_code == 201, perm_resp.text

    action_resp = await async_client.post(
        f"/api/v1/organizations/{org_id}/runtime-actions",
        json={
            "tool_id": tool_id,
            "operation_id": op_id,
            "environment": "dev",
            "action_type": "check",
            "parameters": action_params or {"query": "SELECT 1"},
        },
        headers={"X-Agent-ID": agent_id},
    )
    assert action_resp.status_code == 201, action_resp.text
    action_id = action_resp.json()["id"]

    return {
        "org_id": org_id,
        "admin_id": admin_id,
        "agent_id": agent_id,
        "tool_id": tool_id,
        "tool_slug": tool_actual_slug,
        "operation_id": op_id,
        "operation_slug": op_actual_slug,
        "action_id": action_id,
    }


@pytest.mark.asyncio
async def test_direct_execution_of_allowed_action_succeeds(async_client: AsyncClient):
    """A: Directly authorized action (decision=ALLOW) executes successfully."""
    # Ensure internal:health_check is available
    fix = await provision_execution_fixture(
        async_client,
        tool_slug="internal",
        op_slug="health_check",
        op_risk_level="low",
        permission_effect="allow",
    )

    # Execute runtime action
    exec_resp = await async_client.post(
        f"/api/v1/organizations/{fix['org_id']}/runtime-actions/{fix['action_id']}/execute"
    )
    assert exec_resp.status_code == 200, exec_resp.text
    data = exec_resp.json()
    assert data["status"] == "succeeded"
    assert data["result"]["status"] == "healthy"
    assert data["error_code"] is None
    assert data["started_at"] is not None
    assert data["completed_at"] is not None
    assert data["decision_id"] is not None

    # Verify RuntimeAction status updated to executed
    act_resp = await async_client.get(
        f"/api/v1/organizations/{fix['org_id']}/runtime-actions/{fix['action_id']}"
    )
    assert act_resp.status_code == 200
    assert act_resp.json()["status"] == "executed"
    assert act_resp.json()["completed_at"] is not None


@pytest.mark.asyncio
async def test_execution_blocked_when_decision_is_block(async_client: AsyncClient):
    """B: When authorization decision is BLOCK (e.g. permission deny), execution is blocked."""
    fix = await provision_execution_fixture(
        async_client,
        tool_slug="internal",
        op_slug="health_check",
        op_risk_level="low",
        permission_effect="deny",
    )

    exec_resp = await async_client.post(
        f"/api/v1/organizations/{fix['org_id']}/runtime-actions/{fix['action_id']}/execute"
    )
    assert exec_resp.status_code == 200, exec_resp.text
    data = exec_resp.json()
    assert data["status"] == "blocked"
    assert data["error_code"] == "EXECUTION_BLOCKED_BY_GUARD"
    assert data["result"] is None

    # RuntimeAction marked as denied
    act_resp = await async_client.get(
        f"/api/v1/organizations/{fix['org_id']}/runtime-actions/{fix['action_id']}"
    )
    assert act_resp.json()["status"] == "denied"


@pytest.mark.asyncio
async def test_execution_blocked_when_approval_required_but_missing(async_client: AsyncClient):
    """C: When decision requires approval but no approval exists, execution is blocked."""
    fix = await provision_execution_fixture(
        async_client,
        tool_slug="internal",
        op_slug="health_check",
        op_risk_level="critical",  # Critical risk produces REQUIRE_APPROVAL
        permission_effect="allow",
    )

    exec_resp = await async_client.post(
        f"/api/v1/organizations/{fix['org_id']}/runtime-actions/{fix['action_id']}/execute"
    )
    assert exec_resp.status_code == 200, exec_resp.text
    data = exec_resp.json()
    assert data["status"] == "blocked"
    assert data["error_code"] == "APPROVAL_REQUIRED"


@pytest.mark.asyncio
async def test_execution_succeeds_when_approved(async_client: AsyncClient):
    """D: When decision requires approval and approval is granted, execution succeeds."""
    fix = await provision_execution_fixture(
        async_client,
        tool_slug="internal",
        op_slug="health_check",
        op_risk_level="high",  # High risk produces REQUIRE_APPROVAL
        permission_effect="allow",
    )

    # 1. Decide action to generate REQUIRE_APPROVAL decision
    dec_resp = await async_client.post(
        f"/api/v1/organizations/{fix['org_id']}/runtime-actions/{fix['action_id']}/decide"
    )
    assert dec_resp.status_code == 201
    decision_id = dec_resp.json()["id"]
    assert dec_resp.json()["decision"] == "require_approval"

    # 2. Create approval request
    appr_resp = await async_client.post(
        f"/api/v1/organizations/{fix['org_id']}/runtime-actions/{fix['action_id']}/approval",
        json={"decision_id": decision_id, "reason": "Requesting production check"},
    )
    assert appr_resp.status_code == 201
    approval_id = appr_resp.json()["id"]

    # 3. Approve request with authorized reviewer
    approve_resp = await async_client.post(
        f"/api/v1/organizations/{fix['org_id']}/approvals/{approval_id}/approve",
        json={"reviewer_note": "Approved by security lead"},
        headers={"X-User-ID": fix["admin_id"]},
    )
    assert approve_resp.status_code == 200
    assert approve_resp.json()["status"] == "approved"

    # 4. Execute action
    exec_resp = await async_client.post(
        f"/api/v1/organizations/{fix['org_id']}/runtime-actions/{fix['action_id']}/execute"
    )
    assert exec_resp.status_code == 200, exec_resp.text
    data = exec_resp.json()
    assert data["status"] == "succeeded"
    assert data["approval_id"] == approval_id
    assert data["result"]["status"] == "healthy"

    # Verify RuntimeAction status updated to executed
    act_resp = await async_client.get(
        f"/api/v1/organizations/{fix['org_id']}/runtime-actions/{fix['action_id']}"
    )
    assert act_resp.json()["status"] == "executed"


@pytest.mark.asyncio
async def test_execution_blocked_when_approval_is_expired(async_client: AsyncClient):
    """E: When human approval has expired, execution is blocked."""
    fix = await provision_execution_fixture(
        async_client,
        tool_slug="internal",
        op_slug="health_check",
        op_risk_level="high",
        permission_effect="allow",
    )

    dec_resp = await async_client.post(
        f"/api/v1/organizations/{fix['org_id']}/runtime-actions/{fix['action_id']}/decide"
    )
    decision_id = dec_resp.json()["id"]

    # Create approval expiring in 1 second
    exp_time = (datetime.now(timezone.utc) + timedelta(seconds=1)).isoformat()
    appr_resp = await async_client.post(
        f"/api/v1/organizations/{fix['org_id']}/runtime-actions/{fix['action_id']}/approval",
        json={"decision_id": decision_id, "expires_at": exp_time},
    )
    approval_id = appr_resp.json()["id"]

    approve_resp = await async_client.post(
        f"/api/v1/organizations/{fix['org_id']}/approvals/{approval_id}/approve",
        headers={"X-User-ID": fix["admin_id"]},
    )
    assert approve_resp.status_code == 200

    # Wait for expiration
    import asyncio
    await asyncio.sleep(1.2)

    # Execution should now be blocked due to expired approval
    exec_resp = await async_client.post(
        f"/api/v1/organizations/{fix['org_id']}/runtime-actions/{fix['action_id']}/execute"
    )
    assert exec_resp.status_code == 200
    assert exec_resp.json()["status"] == "blocked"
    assert exec_resp.json()["error_code"] == "APPROVAL_EXPIRED"


@pytest.mark.asyncio
async def test_execution_blocked_when_approval_was_rejected(async_client: AsyncClient):
    """F: When approval request was rejected, execution is blocked."""
    fix = await provision_execution_fixture(
        async_client,
        tool_slug="internal",
        op_slug="health_check",
        op_risk_level="high",
        permission_effect="allow",
    )

    dec_resp = await async_client.post(
        f"/api/v1/organizations/{fix['org_id']}/runtime-actions/{fix['action_id']}/decide"
    )
    decision_id = dec_resp.json()["id"]

    appr_resp = await async_client.post(
        f"/api/v1/organizations/{fix['org_id']}/runtime-actions/{fix['action_id']}/approval",
        json={"decision_id": decision_id},
    )
    approval_id = appr_resp.json()["id"]

    reject_resp = await async_client.post(
        f"/api/v1/organizations/{fix['org_id']}/approvals/{approval_id}/reject",
        json={"rejection_reason": "High risk unacceptable"},
        headers={"X-User-ID": fix["admin_id"]},
    )
    assert reject_resp.status_code == 200
    assert reject_resp.json()["status"] == "rejected"

    exec_resp = await async_client.post(
        f"/api/v1/organizations/{fix['org_id']}/runtime-actions/{fix['action_id']}/execute"
    )
    assert exec_resp.status_code == 200
    assert exec_resp.json()["status"] == "blocked"
    assert exec_resp.json()["error_code"] in ("ACTION_DENIED", "APPROVAL_REQUIRED")


@pytest.mark.asyncio
async def test_duplicate_execution_idempotency_rejected(async_client: AsyncClient):
    """G: Succeeded action cannot be executed twice (idempotency enforcement)."""
    fix = await provision_execution_fixture(
        async_client,
        tool_slug="internal",
        op_slug="health_check",
        op_risk_level="low",
        permission_effect="allow",
    )

    # First execution succeeds
    first_resp = await async_client.post(
        f"/api/v1/organizations/{fix['org_id']}/runtime-actions/{fix['action_id']}/execute"
    )
    assert first_resp.status_code == 200
    assert first_resp.json()["status"] == "succeeded"

    # Second execution attempt is rejected with 409 Conflict
    dup_resp = await async_client.post(
        f"/api/v1/organizations/{fix['org_id']}/runtime-actions/{fix['action_id']}/execute"
    )
    assert dup_resp.status_code == 409
    assert "already been" in dup_resp.json()["detail"].lower()


@pytest.mark.asyncio
async def test_unregistered_handler_fails_safely(async_client: AsyncClient):
    """H: Execution with missing/unregistered tool handler fails safely without crash."""
    fix = await provision_execution_fixture(
        async_client,
        tool_slug="unregistered_tool",
        op_slug="unregistered_op",
        op_risk_level="low",
        permission_effect="allow",
    )

    exec_resp = await async_client.post(
        f"/api/v1/organizations/{fix['org_id']}/runtime-actions/{fix['action_id']}/execute"
    )
    assert exec_resp.status_code == 200, exec_resp.text
    data = exec_resp.json()
    assert data["status"] == "failed"
    assert data["error_code"] == "HANDLER_NOT_REGISTERED"

    # Action status marked as failed
    act_resp = await async_client.get(
        f"/api/v1/organizations/{fix['org_id']}/runtime-actions/{fix['action_id']}"
    )
    assert act_resp.json()["status"] == "failed"


@pytest.mark.asyncio
async def test_failing_handler_records_failure(async_client: AsyncClient):
    """I: Simulated upstream handler failure is recorded deterministically."""
    fix = await provision_execution_fixture(
        async_client,
        tool_slug="test",
        op_slug="fail",
        op_risk_level="low",
        permission_effect="allow",
    )

    exec_resp = await async_client.post(
        f"/api/v1/organizations/{fix['org_id']}/runtime-actions/{fix['action_id']}/execute"
    )
    assert exec_resp.status_code == 200, exec_resp.text
    data = exec_resp.json()
    assert data["status"] == "failed"
    assert data["error_code"] == "UPSTREAM_SERVICE_ERROR"


@pytest.mark.asyncio
async def test_parameter_sanitization_and_masking(async_client: AsyncClient):
    """J: Parameter sanitization strips dangerous attributes and redacts sensitive keys."""
    raw_params = {
        "password": "supersecretpassword",
        "api_key": "sk-1234567890",
        "nested": {"token": "jwt-token-value", "name": "normal"},
        "__proto__": {"injected": "bad"},
        "normal_key": "public_data",
    }

    # Verify unit sanitization
    sanitized = sanitize_parameters(raw_params)
    assert sanitized["password"] == "[REDACTED]"
    assert sanitized["api_key"] == "[REDACTED]"
    assert sanitized["nested"]["token"] == "[REDACTED]"
    assert sanitized["nested"]["name"] == "normal"
    assert "__proto__" not in sanitized
    assert sanitized["normal_key"] == "public_data"

    # Verify end-to-end execution echo handler
    fix = await provision_execution_fixture(
        async_client,
        tool_slug="internal",
        op_slug="echo",
        op_risk_level="low",
        permission_effect="allow",
        action_params=raw_params,
    )

    exec_resp = await async_client.post(
        f"/api/v1/organizations/{fix['org_id']}/runtime-actions/{fix['action_id']}/execute"
    )
    assert exec_resp.status_code == 200, exec_resp.text
    output = exec_resp.json()["result"]["echo"]
    assert output["password"] == "[REDACTED]"
    assert output["api_key"] == "[REDACTED]"
    assert "__proto__" not in output


@pytest.mark.asyncio
async def test_realtime_revalidation_policy_changed_to_deny(async_client: AsyncClient):
    """K: Revalidation blocks execution if policy changes to DENY after approval."""
    fix = await provision_execution_fixture(
        async_client,
        tool_slug="internal",
        op_slug="health_check",
        op_risk_level="high",
        permission_effect="allow",
    )

    # 1. Decide and approve
    dec_resp = await async_client.post(
        f"/api/v1/organizations/{fix['org_id']}/runtime-actions/{fix['action_id']}/decide"
    )
    decision_id = dec_resp.json()["id"]

    appr_resp = await async_client.post(
        f"/api/v1/organizations/{fix['org_id']}/runtime-actions/{fix['action_id']}/approval",
        json={"decision_id": decision_id},
    )
    approval_id = appr_resp.json()["id"]

    approve_resp = await async_client.post(
        f"/api/v1/organizations/{fix['org_id']}/approvals/{approval_id}/approve",
        headers={"X-User-ID": fix["admin_id"]},
    )
    assert approve_resp.status_code == 200

    # 2. Introduce a new DENY policy
    policy_resp = await async_client.post(
        f"/api/v1/organizations/{fix['org_id']}/policies",
        json={"name": "Emergency Block Policy"},
    )
    policy_id = policy_resp.json()["id"]

    ver_resp = await async_client.post(
        f"/api/v1/organizations/{fix['org_id']}/policies/{policy_id}/versions",
        json={
            "rules": [
                {
                    "name": "Block All Rule",
                    "conditions": [{"field": "agent.environment", "operator": "eq", "value": "development"}],
                    "effect": "deny",
                }
            ]
        },
    )
    assert ver_resp.status_code == 201, ver_resp.text
    version_id = ver_resp.json()["id"]
    await async_client.post(f"/api/v1/organizations/{fix['org_id']}/policies/{policy_id}/versions/{version_id}/publish")

    # 3. Execution attempt must be blocked by ExecutionGuard real-time revalidation
    exec_resp = await async_client.post(
        f"/api/v1/organizations/{fix['org_id']}/runtime-actions/{fix['action_id']}/execute"
    )
    assert exec_resp.status_code == 200
    assert exec_resp.json()["status"] == "blocked"
    assert exec_resp.json()["error_code"] == "EXECUTION_BLOCKED_BY_GUARD"


@pytest.mark.asyncio
async def test_realtime_revalidation_agent_deactivated(async_client: AsyncClient):
    """L: Revalidation blocks execution if requesting agent is suspended."""
    fix = await provision_execution_fixture(
        async_client,
        tool_slug="internal",
        op_slug="health_check",
        op_risk_level="low",
        permission_effect="allow",
    )

    # Suspend the agent
    susp_resp = await async_client.post(
        f"/api/v1/organizations/{fix['org_id']}/agents/{fix['agent_id']}/suspend"
    )
    assert susp_resp.status_code == 200

    # Execution attempt is blocked
    exec_resp = await async_client.post(
        f"/api/v1/organizations/{fix['org_id']}/runtime-actions/{fix['action_id']}/execute"
    )
    assert exec_resp.status_code == 200
    assert exec_resp.json()["status"] == "blocked"
    assert exec_resp.json()["error_code"] == "RESOURCE_INACTIVE_OR_INVALID"


@pytest.mark.asyncio
async def test_tenant_isolation_executions(async_client: AsyncClient):
    """M: Cross-tenant isolation prevents executing or reading executions across organizations."""
    fix_a = await provision_execution_fixture(async_client, org_name="Org A")
    fix_b = await provision_execution_fixture(async_client, org_name="Org B")

    # Execute in Org A
    exec_a = await async_client.post(
        f"/api/v1/organizations/{fix_a['org_id']}/runtime-actions/{fix_a['action_id']}/execute"
    )
    assert exec_a.status_code == 200
    exec_id_a = exec_a.json()["id"]

    # Org B cannot execute Org A's action
    cross_exec = await async_client.post(
        f"/api/v1/organizations/{fix_b['org_id']}/runtime-actions/{fix_a['action_id']}/execute"
    )
    assert cross_exec.status_code == 404

    # Org B cannot view Org A's execution record
    cross_get = await async_client.get(
        f"/api/v1/organizations/{fix_b['org_id']}/executions/{exec_id_a}"
    )
    assert cross_get.status_code == 404


@pytest.mark.asyncio
async def test_list_executions_with_filters_and_pagination(async_client: AsyncClient):
    """N & O: List execution records with filtering and pagination."""
    fix = await provision_execution_fixture(async_client, org_name="List Org")

    # Execute action
    exec_resp = await async_client.post(
        f"/api/v1/organizations/{fix['org_id']}/runtime-actions/{fix['action_id']}/execute"
    )
    assert exec_resp.status_code == 200
    exec_id = exec_resp.json()["id"]

    # List all executions
    list_resp = await async_client.get(
        f"/api/v1/organizations/{fix['org_id']}/executions"
    )
    assert list_resp.status_code == 200
    assert list_resp.json()["total"] >= 1
    assert any(item["id"] == exec_id for item in list_resp.json()["items"])

    # Filter by status=succeeded
    succ_resp = await async_client.get(
        f"/api/v1/organizations/{fix['org_id']}/executions?status=succeeded"
    )
    assert succ_resp.status_code == 200
    assert all(item["status"] == "succeeded" for item in succ_resp.json()["items"])

    # Filter by status=failed (should be empty for this action)
    fail_resp = await async_client.get(
        f"/api/v1/organizations/{fix['org_id']}/executions?status=failed"
    )
    assert fail_resp.status_code == 200
    assert not any(item["id"] == exec_id for item in fail_resp.json()["items"])

    # Retrieve individual execution by ID
    get_resp = await async_client.get(
        f"/api/v1/organizations/{fix['org_id']}/executions/{exec_id}"
    )
    assert get_resp.status_code == 200
    assert get_resp.json()["id"] == exec_id
    assert get_resp.json()["runtime_action_id"] == fix["action_id"]
    assert get_resp.json()["agent_id"] == fix["agent_id"]
