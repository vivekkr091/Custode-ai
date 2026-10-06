"""Automated tests for CUSTODE Human Approval Workflow, Reviewer Authorization, and Real-time Security Revalidation."""

from datetime import datetime, timedelta, timezone
import uuid
import pytest
from httpx import AsyncClient

from app.db.models.approval import ApprovalStatus
from app.db.models.membership import MembershipRole


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


async def provision_approval_fixture(
    async_client: AsyncClient,
    org_name: str = "Approval Org",
    op_risk_level: str = "high",   # default high -> triggers REQUIRE_APPROVAL
    permission_effect: str = "allow",
    policy_effect: str = None,
    env: str = "dev",
):
    """Provisions Org -> Admin User -> Agent -> Tool -> Operation -> Perm -> Policy -> Action -> Decision."""
    # 1. Org
    unique_org_name = f"{org_name} {uuid.uuid4().hex[:6]}"
    org_resp = await async_client.post("/api/v1/organizations", json={"name": unique_org_name})
    assert org_resp.status_code == 201, org_resp.text
    org_id = org_resp.json()["id"]

    # 2. Users with different roles
    admin_id = await create_user_and_membership(
        async_client, org_id, f"admin_{uuid.uuid4().hex[:6]}@custode.io", MembershipRole.organization_admin.value
    )
    analyst_id = await create_user_and_membership(
        async_client, org_id, f"analyst_{uuid.uuid4().hex[:6]}@custode.io", MembershipRole.security_analyst.value
    )
    dev_id = await create_user_and_membership(
        async_client, org_id, f"dev_{uuid.uuid4().hex[:6]}@custode.io", MembershipRole.developer.value
    )
    viewer_id = await create_user_and_membership(
        async_client, org_id, f"viewer_{uuid.uuid4().hex[:6]}@custode.io", MembershipRole.viewer.value
    )

    # 3. Agent
    agent_resp = await async_client.post(
        f"/api/v1/organizations/{org_id}/agents",
        json={"name": f"{org_name} Agent", "environment": "development"},
    )
    assert agent_resp.status_code == 201
    agent_id = agent_resp.json()["id"]

    # 4. Tool
    tool_resp = await async_client.post(
        f"/api/v1/organizations/{org_id}/tools",
        json={"name": f"{org_name} Tool"},
    )
    assert tool_resp.status_code == 201
    tool_id = tool_resp.json()["id"]

    # 5. Operation
    op_resp = await async_client.post(
        f"/api/v1/organizations/{org_id}/tools/{tool_id}/operations",
        json={
            "name": "Test Op",
            "operation_type": "read",
            "risk_level": op_risk_level,
        },
    )
    assert op_resp.status_code == 201
    op_id = op_resp.json()["id"]

    # 6. Permission
    if permission_effect is not None:
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
        assert perm_resp.status_code == 201
        perm_id = perm_resp.json()["id"]
    else:
        perm_id = None

    # 7. Policy
    policy_id = None
    if policy_effect is not None:
        pol_resp = await async_client.post(
            f"/api/v1/organizations/{org_id}/policies",
            json={"name": f"Policy {org_name}", "enforcement_mode": "enforce"},
        )
        assert pol_resp.status_code == 201
        policy_id = pol_resp.json()["id"]

        ver_resp = await async_client.post(
            f"/api/v1/organizations/{org_id}/policies/{policy_id}/versions",
            json={
                "rules": [
                    {
                        "name": "Approval Rule",
                        "effect": policy_effect,
                        "conditions": [{"field": "tool.id", "operator": "eq", "value": tool_id}],
                    }
                ]
            },
        )
        assert ver_resp.status_code == 201
        ver_id = ver_resp.json()["id"]
        await async_client.post(
            f"/api/v1/organizations/{org_id}/policies/{policy_id}/versions/{ver_id}/publish"
        )

    # 8. RuntimeAction
    action_resp = await async_client.post(
        f"/api/v1/organizations/{org_id}/runtime-actions",
        json={
            "tool_id": tool_id,
            "operation_id": op_id,
            "environment": env,
            "action_type": "test_action",
            "resource": "/test",
            "resource_type": "public",
        },
        headers={"X-Agent-ID": agent_id},
    )
    assert action_resp.status_code == 201
    action_id = action_resp.json()["id"]

    # 9. Initial Decision
    decision_resp = await async_client.post(
        f"/api/v1/organizations/{org_id}/runtime-actions/{action_id}/decide"
    )
    assert decision_resp.status_code == 201
    decision = decision_resp.json()

    return {
        "org_id": org_id,
        "admin_id": admin_id,
        "analyst_id": analyst_id,
        "dev_id": dev_id,
        "viewer_id": viewer_id,
        "agent_id": agent_id,
        "tool_id": tool_id,
        "op_id": op_id,
        "perm_id": perm_id,
        "policy_id": policy_id,
        "action_id": action_id,
        "decision_id": decision["id"],
        "decision": decision,
    }


@pytest.mark.asyncio
async def test_approval_creation_lifecycle_and_reuse(async_client: AsyncClient):
    """A, D, W: Approval created from REQUIRE_APPROVAL, reuses pending request, decision snapshot preserved."""
    ctx = await provision_approval_fixture(async_client, op_risk_level="high")
    org_id = ctx["org_id"]
    action_id = ctx["action_id"]
    decision_id = ctx["decision_id"]

    # A: Create Approval
    resp = await async_client.post(
        f"/api/v1/organizations/{org_id}/runtime-actions/{action_id}/approval",
        json={"decision_id": decision_id, "reason": "Requires high risk human review"},
    )
    assert resp.status_code == 201
    appr1 = resp.json()
    assert appr1["status"] == "pending"
    assert appr1["runtime_action_id"] == action_id
    assert appr1["decision_id"] == decision_id

    # W: Decision snapshot preserved
    snapshot = appr1["decision_snapshot"]
    assert snapshot["decision"] == "require_approval"
    assert snapshot["risk_level"] == "HIGH"
    assert "risk_score" in snapshot

    # D: Duplicate creation returns existing pending approval
    resp2 = await async_client.post(
        f"/api/v1/organizations/{org_id}/runtime-actions/{action_id}/approval",
        json={"decision_id": decision_id},
    )
    assert resp2.status_code == 201
    appr2 = resp2.json()
    assert appr2["id"] == appr1["id"]


@pytest.mark.asyncio
async def test_approval_creation_rejected_for_allow_or_block(async_client: AsyncClient):
    """B, C: Approval creation rejected from ALLOW or BLOCK decisions."""
    # B: From ALLOW (low risk, no policy, allowed permission)
    ctx_allow = await provision_approval_fixture(async_client, op_risk_level="low")
    assert ctx_allow["decision"]["decision"] == "allow"
    resp_b = await async_client.post(
        f"/api/v1/organizations/{ctx_allow['org_id']}/runtime-actions/{ctx_allow['action_id']}/approval",
        json={"decision_id": ctx_allow["decision_id"]},
    )
    assert resp_b.status_code == 409
    assert "require_approval" in resp_b.json()["detail"].lower()

    # C: From BLOCK (explicit deny permission)
    ctx_block = await provision_approval_fixture(async_client, permission_effect="deny")
    assert ctx_block["decision"]["decision"] == "block"
    resp_c = await async_client.post(
        f"/api/v1/organizations/{ctx_block['org_id']}/runtime-actions/{ctx_block['action_id']}/approval",
        json={"decision_id": ctx_block["decision_id"]},
    )
    assert resp_c.status_code == 409
    assert "require_approval" in resp_c.json()["detail"].lower()


@pytest.mark.asyncio
async def test_reviewer_authorization_matrix(async_client: AsyncClient):
    """E, F, G, H, I, J: Authorization roles for approve/reject."""
    ctx = await provision_approval_fixture(async_client, op_risk_level="high")
    org_id = ctx["org_id"]
    action_id = ctx["action_id"]

    # Create approval
    appr = (
        await async_client.post(
            f"/api/v1/organizations/{org_id}/runtime-actions/{action_id}/approval",
            json={"decision_id": ctx["decision_id"]},
        )
    ).json()
    appr_id = appr["id"]

    # F: Developer cannot approve -> 403
    resp_f = await async_client.post(
        f"/api/v1/organizations/{org_id}/approvals/{appr_id}/approve",
        headers={"X-User-ID": ctx["dev_id"]},
    )
    assert resp_f.status_code == 403
    assert "not authorized" in resp_f.json()["detail"].lower()

    # G: Viewer cannot approve -> 403
    resp_g = await async_client.post(
        f"/api/v1/organizations/{org_id}/approvals/{appr_id}/approve",
        headers={"X-User-ID": ctx["viewer_id"]},
    )
    assert resp_g.status_code == 403
    assert "not authorized" in resp_g.json()["detail"].lower()

    # J: Reviewer from another organization cannot approve -> 403
    ctx_other = await provision_approval_fixture(async_client, org_name="Other Org")
    resp_j = await async_client.post(
        f"/api/v1/organizations/{org_id}/approvals/{appr_id}/approve",
        headers={"X-User-ID": ctx_other["admin_id"]},
    )
    assert resp_j.status_code == 403

    # H: Security Analyst can approve -> 200
    resp_h = await async_client.post(
        f"/api/v1/organizations/{org_id}/approvals/{appr_id}/approve",
        headers={"X-User-ID": ctx["analyst_id"]},
        json={"reviewer_note": "Reviewed by security team"},
    )
    assert resp_h.status_code == 200
    assert resp_h.json()["status"] == "approved"
    assert resp_h.json()["reviewer_user_id"] == ctx["analyst_id"]

    # Action status updated to approved
    act_check = await async_client.get(f"/api/v1/organizations/{org_id}/runtime-actions/{action_id}")
    assert act_check.json()["status"] == "approved"

    # I: Organization Admin can approve another approval
    ctx2 = await provision_approval_fixture(async_client, org_name="Admin Approval Org", op_risk_level="high")
    appr2 = (
        await async_client.post(
            f"/api/v1/organizations/{ctx2['org_id']}/runtime-actions/{ctx2['action_id']}/approval",
            json={"decision_id": ctx2["decision_id"]},
        )
    ).json()
    resp_i = await async_client.post(
        f"/api/v1/organizations/{ctx2['org_id']}/approvals/{appr2['id']}/approve",
        headers={"X-User-ID": ctx2["admin_id"]},
    )
    assert resp_i.status_code == 200
    assert resp_i.json()["status"] == "approved"


@pytest.mark.asyncio
async def test_rejection_and_cancellation_workflows(async_client: AsyncClient):
    """K, L, M, N: Rejection requires reason, rejection succeeds, cancellation succeeds, invalid transition fails."""
    ctx = await provision_approval_fixture(async_client, op_risk_level="high")
    org_id = ctx["org_id"]
    action_id = ctx["action_id"]

    appr = (
        await async_client.post(
            f"/api/v1/organizations/{org_id}/runtime-actions/{action_id}/approval",
            json={"decision_id": ctx["decision_id"]},
        )
    ).json()
    appr_id = appr["id"]

    # K: Rejection requires reason -> 422 if empty
    resp_k = await async_client.post(
        f"/api/v1/organizations/{org_id}/approvals/{appr_id}/reject",
        headers={"X-User-ID": ctx["admin_id"]},
        json={"rejection_reason": ""},
    )
    assert resp_k.status_code == 422

    # L: Rejection succeeds with valid reason -> 200
    resp_l = await async_client.post(
        f"/api/v1/organizations/{org_id}/approvals/{appr_id}/reject",
        headers={"X-User-ID": ctx["admin_id"]},
        json={"rejection_reason": "High risk is unacceptable in staging environment"},
    )
    assert resp_l.status_code == 200
    assert resp_l.json()["status"] == "rejected"
    assert resp_l.json()["rejection_reason"] == "High risk is unacceptable in staging environment"

    # Action status updated to denied
    act_check = await async_client.get(f"/api/v1/organizations/{org_id}/runtime-actions/{action_id}")
    assert act_check.json()["status"] == "denied"

    # N: Invalid transition out of terminal state -> 409
    resp_n = await async_client.post(
        f"/api/v1/organizations/{org_id}/approvals/{appr_id}/approve",
        headers={"X-User-ID": ctx["admin_id"]},
    )
    assert resp_n.status_code == 409

    # M: Cancellation succeeds on a new pending approval
    ctx2 = await provision_approval_fixture(async_client, org_name="Cancel Org", op_risk_level="high")
    appr2 = (
        await async_client.post(
            f"/api/v1/organizations/{ctx2['org_id']}/runtime-actions/{ctx2['action_id']}/approval",
            json={"decision_id": ctx2["decision_id"]},
        )
    ).json()

    resp_m = await async_client.post(
        f"/api/v1/organizations/{ctx2['org_id']}/approvals/{appr2['id']}/cancel",
        json={"reason": "Action no longer required by user"},
    )
    assert resp_m.status_code == 200
    assert resp_m.json()["status"] == "cancelled"


@pytest.mark.asyncio
async def test_approval_expiration(async_client: AsyncClient):
    """O: Expired approval cannot be approved."""
    ctx = await provision_approval_fixture(async_client, op_risk_level="high")
    org_id = ctx["org_id"]
    action_id = ctx["action_id"]

    # Create approval that expired 1 hour ago
    past_time = (datetime.now(timezone.utc) - timedelta(hours=1)).isoformat()
    appr = (
        await async_client.post(
            f"/api/v1/organizations/{org_id}/runtime-actions/{action_id}/approval",
            json={"decision_id": ctx["decision_id"], "expires_at": past_time},
        )
    ).json()
    appr_id = appr["id"]

    # Attempt to approve expired request -> 409
    resp_o = await async_client.post(
        f"/api/v1/organizations/{org_id}/approvals/{appr_id}/approve",
        headers={"X-User-ID": ctx["admin_id"]},
    )
    assert resp_o.status_code == 409
    assert "expired" in resp_o.json()["detail"].lower()

    # Get approval reflects expired status
    get_check = await async_client.get(f"/api/v1/organizations/{org_id}/approvals/{appr_id}")
    assert get_check.json()["status"] == "expired"


@pytest.mark.asyncio
async def test_revalidation_security_dynamics(async_client: AsyncClient):
    """P, Q, R, S, T, U, V: Revalidation reruns engines; BLOCK prevents approval; ALLOW marks stale; REQUIRE_APPROVAL succeeds."""
    # Case T: Revalidation resulting in BLOCK prevents approval
    ctx_t = await provision_approval_fixture(async_client, org_name="Reval Block Org", op_risk_level="high")
    appr_t = (
        await async_client.post(
            f"/api/v1/organizations/{ctx_t['org_id']}/runtime-actions/{ctx_t['action_id']}/approval",
            json={"decision_id": ctx_t["decision_id"]},
        )
    ).json()
    # Revoke permission before approval to turn decision into BLOCK
    await async_client.post(
        f"/api/v1/organizations/{ctx_t['org_id']}/permissions/{ctx_t['perm_id']}/revoke"
    )
    resp_t = await async_client.post(
        f"/api/v1/organizations/{ctx_t['org_id']}/approvals/{appr_t['id']}/approve",
        headers={"X-User-ID": ctx_t["admin_id"]},
    )
    assert resp_t.status_code == 409
    assert "block" in resp_t.json()["detail"].lower()

    # Case U: Revalidation resulting in ALLOW marks approval stale
    # Create action requiring approval via Policy
    ctx_u = await provision_approval_fixture(
        async_client,
        org_name="Reval Stale Org",
        op_risk_level="low",
        policy_effect="require_approval",
    )
    appr_u = (
        await async_client.post(
            f"/api/v1/organizations/{ctx_u['org_id']}/runtime-actions/{ctx_u['action_id']}/approval",
            json={"decision_id": ctx_u["decision_id"]},
        )
    ).json()
    # Retire the policy version so policy NO LONGER requires approval -> decision becomes ALLOW
    pol_id = ctx_u["policy_id"]
    vers = (await async_client.get(f"/api/v1/organizations/{ctx_u['org_id']}/policies/{pol_id}/versions")).json()
    v_id = vers["items"][0]["id"]
    await async_client.post(f"/api/v1/organizations/{ctx_u['org_id']}/policies/{pol_id}/versions/{v_id}/retire")

    resp_u = await async_client.post(
        f"/api/v1/organizations/{ctx_u['org_id']}/approvals/{appr_u['id']}/approve",
        headers={"X-User-ID": ctx_u["admin_id"]},
    )
    assert resp_u.status_code == 409
    assert "allow" in resp_u.json()["detail"].lower()

    # Case V: Revalidation remaining REQUIRE_APPROVAL allows approval
    ctx_v = await provision_approval_fixture(async_client, org_name="Reval Ok Org", op_risk_level="high")
    appr_v = (
        await async_client.post(
            f"/api/v1/organizations/{ctx_v['org_id']}/runtime-actions/{ctx_v['action_id']}/approval",
            json={"decision_id": ctx_v["decision_id"]},
        )
    ).json()
    resp_v = await async_client.post(
        f"/api/v1/organizations/{ctx_v['org_id']}/approvals/{appr_v['id']}/approve",
        headers={"X-User-ID": ctx_v["admin_id"]},
    )
    assert resp_v.status_code == 200
    assert resp_v.json()["status"] == "approved"


@pytest.mark.asyncio
async def test_tenant_isolation_and_cross_tenant_rejections(async_client: AsyncClient):
    """Y, Z: Cross-tenant approval retrieval and mutation strictly rejected."""
    ctx_a = await provision_approval_fixture(async_client, org_name="Tenant A Org", op_risk_level="high")
    ctx_b = await provision_approval_fixture(async_client, org_name="Tenant B Org", op_risk_level="high")

    appr_a = (
        await async_client.post(
            f"/api/v1/organizations/{ctx_a['org_id']}/runtime-actions/{ctx_a['action_id']}/approval",
            json={"decision_id": ctx_a["decision_id"]},
        )
    ).json()

    # Y: Org B cannot retrieve Org A approval -> 404
    resp_y = await async_client.get(
        f"/api/v1/organizations/{ctx_b['org_id']}/approvals/{appr_a['id']}"
    )
    assert resp_y.status_code == 404

    # Z: Org B cannot approve Org A approval -> 404
    resp_z = await async_client.post(
        f"/api/v1/organizations/{ctx_b['org_id']}/approvals/{appr_a['id']}/approve",
        headers={"X-User-ID": ctx_b["admin_id"]},
    )
    assert resp_z.status_code == 404


@pytest.mark.asyncio
async def test_validation_errors_and_mismatches(async_client: AsyncClient):
    """AA, AB, AC, AD: Missing action, missing decision, mismatching decision."""
    ctx = await provision_approval_fixture(async_client, op_risk_level="high")
    org_id = ctx["org_id"]
    action_id = ctx["action_id"]

    # AA: Missing runtime action -> 404
    resp_aa = await async_client.post(
        f"/api/v1/organizations/{org_id}/runtime-actions/{uuid.uuid4()}/approval",
        json={"decision_id": ctx["decision_id"]},
    )
    assert resp_aa.status_code == 404

    # AB: Missing decision -> 404
    resp_ab = await async_client.post(
        f"/api/v1/organizations/{org_id}/runtime-actions/{action_id}/approval",
        json={"decision_id": str(uuid.uuid4())},
    )
    assert resp_ab.status_code == 404

    # AC: Decision does not belong to RuntimeAction in the same org -> 400
    action2_resp = await async_client.post(
        f"/api/v1/organizations/{org_id}/runtime-actions",
        json={
            "tool_id": ctx["tool_id"],
            "operation_id": ctx["op_id"],
            "environment": "dev",
            "action_type": "second_action",
            "resource": "/test2",
            "resource_type": "public",
        },
        headers={"X-Agent-ID": ctx["agent_id"]},
    )
    assert action2_resp.status_code == 201
    action2_id = action2_resp.json()["id"]

    dec2_resp = await async_client.post(
        f"/api/v1/organizations/{org_id}/runtime-actions/{action2_id}/decide"
    )
    assert dec2_resp.status_code == 201
    dec2_id = dec2_resp.json()["id"]

    # Try creating approval for action 1 with decision of action 2 -> 400
    resp_ac = await async_client.post(
        f"/api/v1/organizations/{org_id}/runtime-actions/{action_id}/approval",
        json={"decision_id": dec2_id},
    )
    assert resp_ac.status_code == 400
    assert "does not belong" in resp_ac.json()["detail"].lower()
