"""Automated tests for CUSTODE Authorization Decision Engine, precedence, and persistence."""

import uuid
import pytest
from httpx import AsyncClient

from app.db.models.decision import DecisionType
from app.db.models.risk_assessment import RiskLevel
from app.engines.decision import DecisionEngine, resolve_decision_precedence
from app.engines.permission.evaluator import PermissionEvaluationResult
from app.engines.policy.evaluator import PolicyEvaluationResult
from app.engines.risk.evaluator import RiskEvaluationResult
from app.schemas.policy import MatchedRuleInfo


async def provision_test_pipeline(
    async_client: AsyncClient,
    org_name: str = "Decision Org",
    op_risk_level: str = "low",
    op_type: str = "read",
    env: str = "dev",
    agent_env: str = "development",
    permission_effect: str = "allow",  # "allow", "deny", or None
    policy_effect: str = None,         # "deny", "require_approval", "allow", or None
    policy_enforcement_mode: str = "enforce",  # "enforce" or "audit"
):
    """Helper to provision complete hierarchy: Org -> Agent -> Tool -> Operation -> Perm -> Policy -> Action."""
    # 1. Org
    org_resp = await async_client.post("/api/v1/organizations", json={"name": org_name})
    assert org_resp.status_code == 201, org_resp.text
    org_id = org_resp.json()["id"]

    # 2. Agent
    agent_resp = await async_client.post(
        f"/api/v1/organizations/{org_id}/agents",
        json={"name": f"{org_name} Agent", "environment": agent_env},
    )
    assert agent_resp.status_code == 201, agent_resp.text
    agent_id = agent_resp.json()["id"]

    # 3. Tool
    tool_resp = await async_client.post(
        f"/api/v1/organizations/{org_id}/tools",
        json={"name": f"{org_name} Tool"},
    )
    assert tool_resp.status_code == 201, tool_resp.text
    tool_id = tool_resp.json()["id"]

    # 4. Operation
    op_resp = await async_client.post(
        f"/api/v1/organizations/{org_id}/tools/{tool_id}/operations",
        json={
            "name": "Test Op",
            "operation_type": op_type,
            "risk_level": op_risk_level,
        },
    )
    assert op_resp.status_code == 201, op_resp.text
    op_id = op_resp.json()["id"]

    # 5. Permission
    if permission_effect is not None:
        perm_env_map = {
            "dev": "development",
            "staging": "staging",
            "prod": "production",
        }
        perm_env = perm_env_map.get(env, env)
        perm_resp = await async_client.post(
            f"/api/v1/organizations/{org_id}/permissions",
            json={
                "agent_id": agent_id,
                "tool_id": tool_id,
                "operation_id": op_id,
                "environment": perm_env,
                "effect": permission_effect,
            },
        )
        assert perm_resp.status_code == 201, perm_resp.text

    # 6. Policy (optional)
    if policy_effect is not None:
        pol_resp = await async_client.post(
            f"/api/v1/organizations/{org_id}/policies",
            json={
                "name": f"Policy for {org_name}",
                "enforcement_mode": policy_enforcement_mode,
            },
        )
        assert pol_resp.status_code == 201, pol_resp.text
        policy_id = pol_resp.json()["id"]

        ver_resp = await async_client.post(
            f"/api/v1/organizations/{org_id}/policies/{policy_id}/versions",
            json={
                "rules": [
                    {
                        "name": f"Rule {policy_effect}",
                        "effect": policy_effect,
                        "conditions": [
                            {
                                "field": "tool.id",
                                "operator": "eq",
                                "value": tool_id,
                            }
                        ],
                    }
                ]
            },
        )
        assert ver_resp.status_code == 201, ver_resp.text
        ver_id = ver_resp.json()["id"]

        pub_resp = await async_client.post(
            f"/api/v1/organizations/{org_id}/policies/{policy_id}/versions/{ver_id}/publish"
        )
        assert pub_resp.status_code == 200, pub_resp.text

    # 7. RuntimeAction
    action_resp = await async_client.post(
        f"/api/v1/organizations/{org_id}/runtime-actions",
        json={
            "tool_id": tool_id,
            "operation_id": op_id,
            "environment": env,
            "action_type": "test_exec",
            "resource": "/data/test",
            "resource_type": "public",
        },
        headers={"X-Agent-ID": agent_id},
    )
    assert action_resp.status_code == 201, action_resp.text
    action_id = action_resp.json()["id"]

    return {
        "org_id": org_id,
        "agent_id": agent_id,
        "tool_id": tool_id,
        "operation_id": op_id,
        "action_id": action_id,
    }


@pytest.mark.asyncio
async def test_permission_deny_blocks(async_client: AsyncClient):
    """A: Permission DENY -> BLOCK (highest authority)."""
    # Case 1: Explicit DENY permission grant
    ctx1 = await provision_test_pipeline(
        async_client,
        org_name="Perm Deny Org 1",
        permission_effect="deny",
    )
    resp1 = await async_client.post(
        f"/api/v1/organizations/{ctx1['org_id']}/runtime-actions/{ctx1['action_id']}/decide"
    )
    assert resp1.status_code == 201
    data1 = resp1.json()
    assert data1["decision"] == "block"
    assert data1["permission_effect"] == "deny"
    assert data1["evaluation_trace"]["permission"]["result"] == "denied"
    assert data1["evaluation_trace"]["final"]["source"] == "permission"
    assert "permission check failed" in data1["reason"]

    # Case 2: No permission grant (default deny)
    ctx2 = await provision_test_pipeline(
        async_client,
        org_name="Perm Deny Org 2",
        permission_effect=None,
    )
    resp2 = await async_client.post(
        f"/api/v1/organizations/{ctx2['org_id']}/runtime-actions/{ctx2['action_id']}/decide"
    )
    assert resp2.status_code == 201
    data2 = resp2.json()
    assert data2["decision"] == "block"
    assert data2["permission_effect"] == "deny"
    assert data2["evaluation_trace"]["final"]["source"] == "permission"


@pytest.mark.asyncio
async def test_permission_allow_and_policy_deny_blocks(async_client: AsyncClient):
    """B: Permission ALLOW + Policy DENY -> BLOCK."""
    ctx = await provision_test_pipeline(
        async_client,
        org_name="Policy Deny Org",
        permission_effect="allow",
        policy_effect="deny",
    )
    resp = await async_client.post(
        f"/api/v1/organizations/{ctx['org_id']}/runtime-actions/{ctx['action_id']}/decide"
    )
    assert resp.status_code == 201
    data = resp.json()
    assert data["decision"] == "block"
    assert data["permission_effect"] == "allow"
    assert data["policy_effect"] == "deny"
    assert data["evaluation_trace"]["final"]["source"] == "policy"
    assert "Action blocked by policy" in data["reason"]


@pytest.mark.asyncio
async def test_permission_allow_and_policy_require_approval(async_client: AsyncClient):
    """C: Permission ALLOW + Policy REQUIRE_APPROVAL -> REQUIRE_APPROVAL."""
    ctx = await provision_test_pipeline(
        async_client,
        org_name="Policy Approval Org",
        permission_effect="allow",
        policy_effect="require_approval",
    )
    resp = await async_client.post(
        f"/api/v1/organizations/{ctx['org_id']}/runtime-actions/{ctx['action_id']}/decide"
    )
    assert resp.status_code == 201
    data = resp.json()
    assert data["decision"] == "require_approval"
    assert data["permission_effect"] == "allow"
    assert data["policy_effect"] == "require_approval"
    assert data["evaluation_trace"]["final"]["source"] == "policy"
    assert "Action requires approval by policy" in data["reason"]


@pytest.mark.asyncio
async def test_permission_allow_and_high_or_critical_risk_requires_approval(async_client: AsyncClient):
    """D, E: Permission ALLOW + no enforcing policy + HIGH / CRITICAL risk -> REQUIRE_APPROVAL."""
    # Case D: HIGH risk operation (baseline risk high -> 55 score)
    ctx_high = await provision_test_pipeline(
        async_client,
        org_name="High Risk Org",
        op_risk_level="high",
        permission_effect="allow",
        policy_effect=None,
    )
    resp_high = await async_client.post(
        f"/api/v1/organizations/{ctx_high['org_id']}/runtime-actions/{ctx_high['action_id']}/decide"
    )
    assert resp_high.status_code == 201
    data_high = resp_high.json()
    assert data_high["decision"] == "require_approval"
    assert data_high["risk_level"] == "HIGH"
    assert data_high["evaluation_trace"]["risk"]["result"] == "approval_required"
    assert data_high["evaluation_trace"]["final"]["source"] == "risk"
    assert "high contextual risk" in data_high["reason"]

    # Case E: CRITICAL risk operation (baseline risk critical -> 80 score)
    ctx_crit = await provision_test_pipeline(
        async_client,
        org_name="Critical Risk Org",
        op_risk_level="critical",
        permission_effect="allow",
        policy_effect=None,
    )
    resp_crit = await async_client.post(
        f"/api/v1/organizations/{ctx_crit['org_id']}/runtime-actions/{ctx_crit['action_id']}/decide"
    )
    assert resp_crit.status_code == 201
    data_crit = resp_crit.json()
    assert data_crit["decision"] == "require_approval"
    assert data_crit["risk_level"] == "CRITICAL"
    assert data_crit["evaluation_trace"]["risk"]["result"] == "approval_required"
    assert data_crit["evaluation_trace"]["final"]["source"] == "risk"
    assert "critical contextual risk" in data_crit["reason"]


@pytest.mark.asyncio
async def test_permission_allow_and_low_or_medium_risk_allows(async_client: AsyncClient):
    """F, G: Permission ALLOW + LOW / MEDIUM risk + no stronger rule -> ALLOW."""
    # Case G: LOW risk
    ctx_low = await provision_test_pipeline(
        async_client,
        org_name="Low Risk Allow Org",
        op_risk_level="low",
        permission_effect="allow",
        policy_effect=None,
    )
    resp_low = await async_client.post(
        f"/api/v1/organizations/{ctx_low['org_id']}/runtime-actions/{ctx_low['action_id']}/decide"
    )
    assert resp_low.status_code == 201
    data_low = resp_low.json()
    assert data_low["decision"] == "allow"
    assert data_low["risk_level"] == "LOW"
    assert data_low["evaluation_trace"]["final"]["decision"] == "allow"
    assert "Action allowed because the agent has permission" in data_low["reason"]

    # Case F: MEDIUM risk
    ctx_med = await provision_test_pipeline(
        async_client,
        org_name="Med Risk Allow Org",
        op_risk_level="medium",
        permission_effect="allow",
        policy_effect=None,
    )
    resp_med = await async_client.post(
        f"/api/v1/organizations/{ctx_med['org_id']}/runtime-actions/{ctx_med['action_id']}/decide"
    )
    assert resp_med.status_code == 201
    data_med = resp_med.json()
    assert data_med["decision"] == "allow"
    assert data_med["risk_level"] == "MEDIUM"
    assert data_med["evaluation_trace"]["final"]["decision"] == "allow"


@pytest.mark.asyncio
async def test_policy_audit_mode_does_not_block_or_require_approval(async_client: AsyncClient):
    """H, I: Policy AUDIT match does not block or require approval."""
    # Audit mode policy with deny rule
    ctx_audit_deny = await provision_test_pipeline(
        async_client,
        org_name="Audit Deny Org",
        permission_effect="allow",
        policy_effect="deny",
        policy_enforcement_mode="audit",
    )
    resp_audit_deny = await async_client.post(
        f"/api/v1/organizations/{ctx_audit_deny['org_id']}/runtime-actions/{ctx_audit_deny['action_id']}/decide"
    )
    assert resp_audit_deny.status_code == 201
    data_audit_deny = resp_audit_deny.json()
    assert data_audit_deny["decision"] == "allow"
    assert data_audit_deny["evaluation_trace"]["policy"]["audit_matches"] >= 1
    assert data_audit_deny["evaluation_trace"]["policy"]["enforced_matches"] == 0

    # Audit mode policy with require_approval rule
    ctx_audit_appr = await provision_test_pipeline(
        async_client,
        org_name="Audit Appr Org",
        permission_effect="allow",
        policy_effect="require_approval",
        policy_enforcement_mode="audit",
    )
    resp_audit_appr = await async_client.post(
        f"/api/v1/organizations/{ctx_audit_appr['org_id']}/runtime-actions/{ctx_audit_appr['action_id']}/decide"
    )
    assert resp_audit_appr.status_code == 201
    data_audit_appr = resp_audit_appr.json()
    assert data_audit_appr["decision"] == "allow"


def test_decision_precedence_combinations():
    """J, K, L: Test precedence arbitration edge cases directly against engine."""
    # J: Policy DENY overrides risk ALLOW-like condition
    perm_allow = PermissionEvaluationResult(allowed=True, effect="allow", reason="Allowed")
    pol_deny = PolicyEvaluationResult(decision="DENY", reason="Denied by policy", enforced_rules=[])
    risk_low = RiskEvaluationResult(risk_score=10.0, risk_level="LOW", factors=[], explanation="Low")
    res_j = DecisionEngine.evaluate(perm_allow, pol_deny, risk_low)
    assert res_j.decision == DecisionType.block
    assert res_j.evaluation_trace["final"]["source"] == "policy"

    # K: Policy REQUIRE_APPROVAL overrides risk LOW
    pol_appr = PolicyEvaluationResult(decision="REQUIRE_APPROVAL", reason="Approval needed", enforced_rules=[])
    res_k = DecisionEngine.evaluate(perm_allow, pol_appr, risk_low)
    assert res_k.decision == DecisionType.require_approval
    assert res_k.evaluation_trace["final"]["source"] == "policy"

    # L: DENY overrides REQUIRE_APPROVAL
    # Case L1: Permission DENY overrides Policy REQUIRE_APPROVAL and Risk HIGH
    perm_deny = PermissionEvaluationResult(allowed=False, effect="deny", reason="No permission")
    risk_high = RiskEvaluationResult(risk_score=70.0, risk_level="HIGH", factors=[], explanation="High")
    res_l1 = DecisionEngine.evaluate(perm_deny, pol_appr, risk_high)
    assert res_l1.decision == DecisionType.block
    assert res_l1.evaluation_trace["final"]["source"] == "permission"

    # Case L2: Policy DENY overrides Risk HIGH
    res_l2 = DecisionEngine.evaluate(perm_allow, pol_deny, risk_high)
    assert res_l2.decision == DecisionType.block
    assert res_l2.evaluation_trace["final"]["source"] == "policy"


@pytest.mark.asyncio
async def test_decision_persistence_and_multiple_evaluations_history(async_client: AsyncClient):
    """M, N, O, P: Trace, explainability, persistence, and historical audit preservation."""
    ctx = await provision_test_pipeline(
        async_client,
        org_name="History Org",
        permission_effect="allow",
        policy_effect="require_approval",
    )
    org_id = ctx["org_id"]
    action_id = ctx["action_id"]

    # 1. First evaluation
    resp1 = await async_client.post(
        f"/api/v1/organizations/{org_id}/runtime-actions/{action_id}/decide"
    )
    assert resp1.status_code == 201
    d1 = resp1.json()
    assert d1["id"] is not None
    assert d1["decision"] == "require_approval"
    assert "evaluation_trace" in d1
    assert "permission" in d1["evaluation_trace"]
    assert "policy" in d1["evaluation_trace"]
    assert "risk" in d1["evaluation_trace"]
    assert "final" in d1["evaluation_trace"]

    # 2. Second evaluation (preserves history, does not overwrite)
    resp2 = await async_client.post(
        f"/api/v1/organizations/{org_id}/runtime-actions/{action_id}/decide"
    )
    assert resp2.status_code == 201
    d2 = resp2.json()
    assert d2["id"] != d1["id"]  # Brand new record ID

    # 3. List decisions for action
    list_resp = await async_client.get(
        f"/api/v1/organizations/{org_id}/runtime-actions/{action_id}/decisions"
    )
    assert list_resp.status_code == 200
    action_decisions = list_resp.json()
    assert action_decisions["total"] == 2
    assert len(action_decisions["items"]) == 2

    # 4. Retrieve decision by ID
    get_resp = await async_client.get(
        f"/api/v1/organizations/{org_id}/decisions/{d1['id']}"
    )
    assert get_resp.status_code == 200
    assert get_resp.json()["id"] == d1["id"]

    # 5. List organization decisions
    org_list_resp = await async_client.get(
        f"/api/v1/organizations/{org_id}/decisions"
    )
    assert org_list_resp.status_code == 200
    assert org_list_resp.json()["total"] == 2

    # 6. Verify RuntimeAction status was NOT mutated
    action_check = await async_client.get(
        f"/api/v1/organizations/{org_id}/runtime-actions/{action_id}"
    )
    assert action_check.status_code == 200
    assert action_check.json()["status"] == "pending"


@pytest.mark.asyncio
async def test_tenant_isolation_for_decisions(async_client: AsyncClient):
    """Q, R: Cross-tenant decision operations strictly rejected."""
    # Org A
    ctx_a = await provision_test_pipeline(
        async_client,
        org_name="Tenant A Org",
        permission_effect="allow",
    )
    # Org B
    ctx_b = await provision_test_pipeline(
        async_client,
        org_name="Tenant B Org",
        permission_effect="allow",
    )

    # 1. Org B tries to decide Org A action -> 404
    decide_cross = await async_client.post(
        f"/api/v1/organizations/{ctx_b['org_id']}/runtime-actions/{ctx_a['action_id']}/decide"
    )
    assert decide_cross.status_code == 404

    # 2. Org A creates a decision
    decide_a = await async_client.post(
        f"/api/v1/organizations/{ctx_a['org_id']}/runtime-actions/{ctx_a['action_id']}/decide"
    )
    assert decide_a.status_code == 201
    decision_a_id = decide_a.json()["id"]

    # 3. Org B tries to retrieve Org A decision -> 404
    get_cross = await async_client.get(
        f"/api/v1/organizations/{ctx_b['org_id']}/decisions/{decision_a_id}"
    )
    assert get_cross.status_code == 404

    # 4. Org B lists decisions -> does not contain Org A decision
    list_b = await async_client.get(
        f"/api/v1/organizations/{ctx_b['org_id']}/decisions"
    )
    assert list_b.status_code == 200
    assert all(item["id"] != decision_a_id for item in list_b.json()["items"])


@pytest.mark.asyncio
async def test_invalid_missing_or_inactive_contexts(async_client: AsyncClient):
    """S, T: Missing action, invalid agent, or inactive resource rejected."""
    ctx = await provision_test_pipeline(
        async_client,
        org_name="Validation Error Org",
        permission_effect="allow",
    )
    org_id = ctx["org_id"]
    agent_id = ctx["agent_id"]
    action_id = ctx["action_id"]

    # S: Missing runtime action -> 404
    random_action_id = uuid.uuid4()
    missing_resp = await async_client.post(
        f"/api/v1/organizations/{org_id}/runtime-actions/{random_action_id}/decide"
    )
    assert missing_resp.status_code == 404

    # T: Inactive Agent context rejected (suspend agent -> 409)
    suspend_resp = await async_client.post(
        f"/api/v1/organizations/{org_id}/agents/{agent_id}/suspend"
    )
    assert suspend_resp.status_code == 200

    inactive_agent_resp = await async_client.post(
        f"/api/v1/organizations/{org_id}/runtime-actions/{action_id}/decide"
    )
    assert inactive_agent_resp.status_code == 409
    assert "agent" in inactive_agent_resp.json()["detail"].lower()
