"""Automated tests for Policy Engine, Versioning, Precedence, and Contextual Evaluation."""

import uuid
import pytest
from httpx import AsyncClient

from app.db.models.policy import EnforcementMode, PolicyStatus
from app.db.models.policy_version import PolicyVersionStatus
from app.engines.policy.conditions import evaluate_condition
from app.schemas.policy import (
    ActionContext,
    PolicyDecision,
    PolicyRule,
    PolicyRuleCondition,
    RuleEffect,
    RuleOperator,
)


async def setup_org(async_client: AsyncClient, name: str = "Policy Org") -> str:
    """Helper to provision a clean test organization."""
    org = (await async_client.post("/api/v1/organizations", json={"name": name})).json()
    return org["id"]


@pytest.mark.asyncio
async def test_policy_creation_and_retrieval(async_client: AsyncClient) -> None:
    """Ensure policies can be created, retrieved, listed, and updated."""
    org_id = await setup_org(async_client, "Policy CRUD Org")

    # 1. Create policy
    create_payload = {
        "name": "Data Access Policy",
        "description": "Protects production database queries",
        "enforcement_mode": "enforce",
    }
    res = await async_client.post(
        f"/api/v1/organizations/{org_id}/policies", json=create_payload
    )
    assert res.status_code == 201
    data = res.json()
    assert data["name"] == "Data Access Policy"
    assert data["slug"] == "data-access-policy"
    assert data["status"] == "draft"
    assert data["enforcement_mode"] == "enforce"
    assert data["active_version"] is None
    policy_id = data["id"]

    # 2. Retrieve policy
    get_res = await async_client.get(f"/api/v1/organizations/{org_id}/policies/{policy_id}")
    assert get_res.status_code == 200
    assert get_res.json()["id"] == policy_id

    # 3. Update policy
    patch_res = await async_client.patch(
        f"/api/v1/organizations/{org_id}/policies/{policy_id}",
        json={"name": "Updated Data Access Policy", "status": "active"},
    )
    assert patch_res.status_code == 200
    assert patch_res.json()["name"] == "Updated Data Access Policy"
    assert patch_res.json()["status"] == "active"

    # 4. List policies
    list_res = await async_client.get(f"/api/v1/organizations/{org_id}/policies")
    assert list_res.status_code == 200
    assert list_res.json()["total"] == 1


@pytest.mark.asyncio
async def test_reject_invalid_condition_field_and_operator(async_client: AsyncClient) -> None:
    """Ensure unknown condition fields and unsupported operators are strictly rejected."""
    org_id = await setup_org(async_client, "Validation Org")
    policy = (
        await async_client.post(
            f"/api/v1/organizations/{org_id}/policies",
            json={"name": "Strict Validation Policy"},
        )
    ).json()
    policy_id = policy["id"]

    # 1. Invalid condition field
    invalid_field_payload = {
        "rules": [
            {
                "name": "bad-field-rule",
                "conditions": [
                    {
                        "field": "unauthorized.custom.attribute",
                        "operator": "eq",
                        "value": "secret",
                    }
                ],
                "effect": "deny",
            }
        ]
    }
    res_field = await async_client.post(
        f"/api/v1/organizations/{org_id}/policies/{policy_id}/versions",
        json=invalid_field_payload,
    )
    assert res_field.status_code == 422

    # 2. Invalid operator
    invalid_op_payload = {
        "rules": [
            {
                "name": "bad-op-rule",
                "conditions": [
                    {
                        "field": "action.amount",
                        "operator": "regex_match_eval",
                        "value": 100,
                    }
                ],
                "effect": "deny",
            }
        ]
    }
    res_op = await async_client.post(
        f"/api/v1/organizations/{org_id}/policies/{policy_id}/versions",
        json=invalid_op_payload,
    )
    assert res_op.status_code == 422


@pytest.mark.asyncio
async def test_policy_versioning_and_sequential_numbering(async_client: AsyncClient) -> None:
    """Verify policy versions increment sequentially (1, 2, 3...) and maintain lifecycle states."""
    org_id = await setup_org(async_client, "Versioning Org")
    policy = (
        await async_client.post(
            f"/api/v1/organizations/{org_id}/policies",
            json={"name": "Versioning Policy"},
        )
    ).json()
    policy_id = policy["id"]

    rule_payload = {
        "rules": [
            {
                "name": "limit-amount",
                "conditions": [{"field": "action.amount", "operator": "gt", "value": 500}],
                "effect": "require_approval",
            }
        ]
    }

    # Version 1
    v1_res = await async_client.post(
        f"/api/v1/organizations/{org_id}/policies/{policy_id}/versions",
        json=rule_payload,
    )
    assert v1_res.status_code == 201
    v1 = v1_res.json()
    assert v1["version"] == 1
    assert v1["status"] == "draft"
    assert v1["published_at"] is None

    # Version 2
    v2_res = await async_client.post(
        f"/api/v1/organizations/{org_id}/policies/{policy_id}/versions",
        json=rule_payload,
    )
    assert v2_res.status_code == 201
    v2 = v2_res.json()
    assert v2["version"] == 2
    assert v2["status"] == "draft"

    # List versions
    list_res = await async_client.get(
        f"/api/v1/organizations/{org_id}/policies/{policy_id}/versions"
    )
    assert list_res.status_code == 200
    assert list_res.json()["total"] == 2
    assert list_res.json()["items"][0]["version"] == 2


@pytest.mark.asyncio
async def test_publish_retires_previous_version(async_client: AsyncClient) -> None:
    """Ensure publishing a new version retires the previously active published version."""
    org_id = await setup_org(async_client, "Retire Previous Org")
    policy = (
        await async_client.post(
            f"/api/v1/organizations/{org_id}/policies",
            json={"name": "Lifecycle Policy"},
        )
    ).json()
    policy_id = policy["id"]

    rule_payload = {
        "rules": [
            {
                "name": "rule-v1",
                "conditions": [{"field": "action.amount", "operator": "gt", "value": 100}],
                "effect": "deny",
            }
        ]
    }

    # Create v1 and publish
    v1 = (
        await async_client.post(
            f"/api/v1/organizations/{org_id}/policies/{policy_id}/versions",
            json=rule_payload,
        )
    ).json()
    v1_id = v1["id"]

    pub1 = await async_client.post(
        f"/api/v1/organizations/{org_id}/policies/{policy_id}/versions/{v1_id}/publish"
    )
    assert pub1.status_code == 200
    assert pub1.json()["status"] == "published"
    assert pub1.json()["published_at"] is not None

    # Policy status transitions to active
    pol_check = (
        await async_client.get(f"/api/v1/organizations/{org_id}/policies/{policy_id}")
    ).json()
    assert pol_check["status"] == "active"
    assert pol_check["active_version"] == 1

    # Create v2 and publish
    v2 = (
        await async_client.post(
            f"/api/v1/organizations/{org_id}/policies/{policy_id}/versions",
            json=rule_payload,
        )
    ).json()
    v2_id = v2["id"]

    pub2 = await async_client.post(
        f"/api/v1/organizations/{org_id}/policies/{policy_id}/versions/{v2_id}/publish"
    )
    assert pub2.status_code == 200
    assert pub2.json()["status"] == "published"

    # Verify v1 is now retired
    v1_check = (
        await async_client.get(
            f"/api/v1/organizations/{org_id}/policies/{policy_id}/versions/{v1_id}"
        )
    ).json()
    assert v1_check["status"] == "retired"

    # Verify policy active version is now 2
    pol_check2 = (
        await async_client.get(f"/api/v1/organizations/{org_id}/policies/{policy_id}")
    ).json()
    assert pol_check2["active_version"] == 2


@pytest.mark.asyncio
async def test_policy_evaluation_precedence_deny_over_all(async_client: AsyncClient) -> None:
    """Verify DENY precedence: DENY takes precedence over REQUIRE_APPROVAL and ALLOW."""
    org_id = await setup_org(async_client, "Precedence Org")
    policy = (
        await async_client.post(
            f"/api/v1/organizations/{org_id}/policies",
            json={"name": "Precedence Policy", "enforcement_mode": "enforce"},
        )
    ).json()
    policy_id = policy["id"]

    agent_id = str(uuid.uuid4())
    tool_id = str(uuid.uuid4())
    op_id = str(uuid.uuid4())

    rules = {
        "rules": [
            {
                "name": "allow-small-amounts",
                "conditions": [{"field": "action.amount", "operator": "lte", "value": 5000}],
                "effect": "allow",
            },
            {
                "name": "require-approval-mid-amounts",
                "conditions": [{"field": "action.amount", "operator": "gte", "value": 500}],
                "effect": "require_approval",
            },
            {
                "name": "deny-specific-agent",
                "conditions": [{"field": "agent.id", "operator": "eq", "value": agent_id}],
                "effect": "deny",
            },
        ]
    }
    v = (
        await async_client.post(
            f"/api/v1/organizations/{org_id}/policies/{policy_id}/versions", json=rules
        )
    ).json()
    await async_client.post(
        f"/api/v1/organizations/{org_id}/policies/{policy_id}/versions/{v['id']}/publish"
    )

    eval_payload = {
        "context": {
            "agent_id": agent_id,
            "tool_id": tool_id,
            "operation_id": op_id,
            "amount": 1000.0,
        }
    }
    eval_res = await async_client.post(
        f"/api/v1/organizations/{org_id}/policies/evaluate", json=eval_payload
    )
    assert eval_res.status_code == 200
    res = eval_res.json()
    # All 3 rules match, but DENY must win
    assert res["decision"] == "DENY"
    assert "deny" in res["reason"].lower()
    assert len(res["matched_rules"]) == 3
    assert len(res["enforced_rules"]) == 3


@pytest.mark.asyncio
async def test_policy_evaluation_require_approval_over_allow(async_client: AsyncClient) -> None:
    """Verify REQUIRE_APPROVAL takes precedence over ALLOW."""
    org_id = await setup_org(async_client, "Approval Precedence Org")
    policy = (
        await async_client.post(
            f"/api/v1/organizations/{org_id}/policies",
            json={"name": "Approval Policy", "enforcement_mode": "enforce"},
        )
    ).json()
    policy_id = policy["id"]

    agent_id = str(uuid.uuid4())
    tool_id = str(uuid.uuid4())
    op_id = str(uuid.uuid4())

    rules = {
        "rules": [
            {
                "name": "allow-all-safe",
                "conditions": [{"field": "tool.type", "operator": "eq", "value": "database"}],
                "effect": "allow",
            },
            {
                "name": "require-approval-production",
                "conditions": [{"field": "agent.environment", "operator": "eq", "value": "production"}],
                "effect": "require_approval",
            },
        ]
    }
    v = (
        await async_client.post(
            f"/api/v1/organizations/{org_id}/policies/{policy_id}/versions", json=rules
        )
    ).json()
    await async_client.post(
        f"/api/v1/organizations/{org_id}/policies/{policy_id}/versions/{v['id']}/publish"
    )

    eval_payload = {
        "context": {
            "agent_id": agent_id,
            "agent_environment": "production",
            "tool_id": tool_id,
            "tool_type": "database",
            "operation_id": op_id,
        }
    }
    eval_res = await async_client.post(
        f"/api/v1/organizations/{org_id}/policies/evaluate", json=eval_payload
    )
    assert eval_res.status_code == 200
    res = eval_res.json()
    assert res["decision"] == "REQUIRE_APPROVAL"
    assert len(res["matched_rules"]) == 2


@pytest.mark.asyncio
async def test_policy_evaluation_allow_and_no_match(async_client: AsyncClient) -> None:
    """Verify ALLOW when only allow matches, and NO_MATCH when no rules match."""
    org_id = await setup_org(async_client, "Allow No Match Org")
    policy = (
        await async_client.post(
            f"/api/v1/organizations/{org_id}/policies",
            json={"name": "Allow Rule Policy", "enforcement_mode": "enforce"},
        )
    ).json()
    policy_id = policy["id"]

    agent_id = str(uuid.uuid4())
    tool_id = str(uuid.uuid4())
    op_id = str(uuid.uuid4())

    rules = {
        "rules": [
            {
                "name": "allow-dev-read",
                "conditions": [
                    {"field": "agent.environment", "operator": "eq", "value": "development"},
                    {"field": "operation.type", "operator": "eq", "value": "read"},
                ],
                "effect": "allow",
            }
        ]
    }
    v = (
        await async_client.post(
            f"/api/v1/organizations/{org_id}/policies/{policy_id}/versions", json=rules
        )
    ).json()
    await async_client.post(
        f"/api/v1/organizations/{org_id}/policies/{policy_id}/versions/{v['id']}/publish"
    )

    # 1. Matching case -> ALLOW
    matching_res = await async_client.post(
        f"/api/v1/organizations/{org_id}/policies/evaluate",
        json={
            "context": {
                "agent_id": agent_id,
                "agent_environment": "development",
                "tool_id": tool_id,
                "operation_id": op_id,
                "operation_type": "read",
            }
        },
    )
    assert matching_res.status_code == 200
    assert matching_res.json()["decision"] == "ALLOW"

    # 2. Non-matching case -> NO_MATCH
    non_matching_res = await async_client.post(
        f"/api/v1/organizations/{org_id}/policies/evaluate",
        json={
            "context": {
                "agent_id": agent_id,
                "agent_environment": "production",
                "tool_id": tool_id,
                "operation_id": op_id,
                "operation_type": "write",
            }
        },
    )
    assert non_matching_res.status_code == 200
    assert non_matching_res.json()["decision"] == "NO_MATCH"
    assert len(non_matching_res.json()["matched_rules"]) == 0


@pytest.mark.asyncio
async def test_audit_mode_records_matches_without_blocking(async_client: AsyncClient) -> None:
    """Verify policies in audit mode record matched rules in audit_rules and do not produce DENY."""
    org_id = await setup_org(async_client, "Audit Mode Org")
    policy = (
        await async_client.post(
            f"/api/v1/organizations/{org_id}/policies",
            json={"name": "Audit Policy", "enforcement_mode": "audit"},
        )
    ).json()
    policy_id = policy["id"]

    agent_id = str(uuid.uuid4())
    tool_id = str(uuid.uuid4())
    op_id = str(uuid.uuid4())

    rules = {
        "rules": [
            {
                "name": "audit-heavy-transaction",
                "conditions": [{"field": "action.amount", "operator": "gt", "value": 10000}],
                "effect": "deny",  # in audit mode, even deny does NOT block
            }
        ]
    }
    v = (
        await async_client.post(
            f"/api/v1/organizations/{org_id}/policies/{policy_id}/versions", json=rules
        )
    ).json()
    await async_client.post(
        f"/api/v1/organizations/{org_id}/policies/{policy_id}/versions/{v['id']}/publish"
    )

    eval_res = await async_client.post(
        f"/api/v1/organizations/{org_id}/policies/evaluate",
        json={
            "context": {
                "agent_id": agent_id,
                "tool_id": tool_id,
                "operation_id": op_id,
                "amount": 25000.0,
            }
        },
    )
    assert eval_res.status_code == 200
    res = eval_res.json()
    # In audit mode, rule matched, but decision remains NO_MATCH
    assert res["decision"] == "NO_MATCH"
    assert len(res["audit_rules"]) == 1
    assert len(res["enforced_rules"]) == 0
    assert res["audit_rules"][0]["rule_name"] == "audit-heavy-transaction"
    assert res["audit_rules"][0]["enforcement_mode"] == "audit"


@pytest.mark.asyncio
async def test_inactive_policy_and_draft_version_not_evaluated(async_client: AsyncClient) -> None:
    """Verify that draft policy versions and suspended policies are completely excluded from evaluation."""
    org_id = await setup_org(async_client, "Exclusion Org")
    policy = (
        await async_client.post(
            f"/api/v1/organizations/{org_id}/policies",
            json={"name": "Draft Only Policy", "enforcement_mode": "enforce"},
        )
    ).json()
    policy_id = policy["id"]

    agent_id = str(uuid.uuid4())
    tool_id = str(uuid.uuid4())
    op_id = str(uuid.uuid4())

    rules = {
        "rules": [
            {
                "name": "deny-draft",
                "conditions": [{"field": "agent.id", "operator": "eq", "value": agent_id}],
                "effect": "deny",
            }
        ]
    }
    # Create draft version but DO NOT publish
    await async_client.post(
        f"/api/v1/organizations/{org_id}/policies/{policy_id}/versions", json=rules
    )

    eval_res = await async_client.post(
        f"/api/v1/organizations/{org_id}/policies/evaluate",
        json={"context": {"agent_id": agent_id, "tool_id": tool_id, "operation_id": op_id}},
    )
    assert eval_res.status_code == 200
    assert eval_res.json()["decision"] == "NO_MATCH"

    # Now publish version, but suspend policy container
    v = (await async_client.get(f"/api/v1/organizations/{org_id}/policies/{policy_id}/versions")).json()["items"][0]
    await async_client.post(f"/api/v1/organizations/{org_id}/policies/{policy_id}/versions/{v['id']}/publish")

    # Suspend policy
    await async_client.patch(
        f"/api/v1/organizations/{org_id}/policies/{policy_id}", json={"status": "suspended"}
    )

    eval_res2 = await async_client.post(
        f"/api/v1/organizations/{org_id}/policies/evaluate",
        json={"context": {"agent_id": agent_id, "tool_id": tool_id, "operation_id": op_id}},
    )
    assert eval_res2.status_code == 200
    assert eval_res2.json()["decision"] == "NO_MATCH"


@pytest.mark.asyncio
async def test_tenant_isolation_for_policies(async_client: AsyncClient) -> None:
    """Verify that policies and policy versions belonging to Org A cannot be accessed or evaluated by Org B."""
    org_a = await setup_org(async_client, "Tenant A")
    org_b = await setup_org(async_client, "Tenant B")

    policy_a = (
        await async_client.post(
            f"/api/v1/organizations/{org_a}/policies", json={"name": "Policy A"}
        )
    ).json()
    policy_a_id = policy_a["id"]

    # 1. Org B cannot retrieve Org A's policy
    res_get = await async_client.get(f"/api/v1/organizations/{org_b}/policies/{policy_a_id}")
    assert res_get.status_code == 404

    # 2. Org B cannot update Org A's policy
    res_patch = await async_client.patch(
        f"/api/v1/organizations/{org_b}/policies/{policy_a_id}", json={"name": "Hijacked Policy"}
    )
    assert res_patch.status_code == 404

    # 3. Org B cannot create versions for Org A's policy
    res_ver = await async_client.post(
        f"/api/v1/organizations/{org_b}/policies/{policy_a_id}/versions",
        json={"rules": [{"name": "r", "conditions": [{"field": "action.amount", "operator": "eq", "value": 1}], "effect": "allow"}]},
    )
    assert res_ver.status_code == 404

    # 4. Evaluation in Org B does NOT evaluate Org A's active policies
    agent_id = str(uuid.uuid4())
    v_a = (
        await async_client.post(
            f"/api/v1/organizations/{org_a}/policies/{policy_a_id}/versions",
            json={"rules": [{"name": "block-agent", "conditions": [{"field": "agent.id", "operator": "eq", "value": agent_id}], "effect": "deny"}]},
        )
    ).json()
    await async_client.post(f"/api/v1/organizations/{org_a}/policies/{policy_a_id}/versions/{v_a['id']}/publish")

    eval_org_b = await async_client.post(
        f"/api/v1/organizations/{org_b}/policies/evaluate",
        json={"context": {"agent_id": agent_id, "tool_id": str(uuid.uuid4()), "operation_id": str(uuid.uuid4())}},
    )
    assert eval_org_b.status_code == 200
    assert eval_org_b.json()["decision"] == "NO_MATCH"


def test_condition_evaluation_operators() -> None:
    """Unit test all supported operators in condition evaluation."""
    agent_id = uuid.uuid4()
    tool_id = uuid.uuid4()
    op_id = uuid.uuid4()

    ctx = ActionContext(
        agent_id=agent_id,
        agent_environment="staging",
        tool_id=tool_id,
        tool_type="filesystem",
        operation_id=op_id,
        operation_type="delete",
        operation_risk_level="high",
        amount=250.50,
        resource="/var/data/records.csv",
        ip_address="192.168.1.100",
        time_hour=14,
        request_id="req-999",
    )

    # eq & neq
    assert evaluate_condition(PolicyRuleCondition(field="agent.environment", operator="eq", value="staging"), ctx)
    assert not evaluate_condition(PolicyRuleCondition(field="agent.environment", operator="eq", value="production"), ctx)
    assert evaluate_condition(PolicyRuleCondition(field="operation.risk_level", operator="neq", value="low"), ctx)

    # gt, gte, lt, lte
    assert evaluate_condition(PolicyRuleCondition(field="action.amount", operator="gt", value=200), ctx)
    assert evaluate_condition(PolicyRuleCondition(field="action.amount", operator="gte", value=250.50), ctx)
    assert evaluate_condition(PolicyRuleCondition(field="action.amount", operator="lt", value=300), ctx)
    assert evaluate_condition(PolicyRuleCondition(field="action.amount", operator="lte", value=250.50), ctx)
    assert not evaluate_condition(PolicyRuleCondition(field="action.amount", operator="gt", value=300), ctx)

    # in & not_in
    assert evaluate_condition(PolicyRuleCondition(field="operation.type", operator="in", value=["read", "delete"]), ctx)
    assert not evaluate_condition(PolicyRuleCondition(field="operation.type", operator="in", value=["read", "write"]), ctx)
    assert evaluate_condition(PolicyRuleCondition(field="operation.type", operator="not_in", value=["read", "write"]), ctx)

    # contains, starts_with, ends_with
    assert evaluate_condition(PolicyRuleCondition(field="action.resource", operator="contains", value="data"), ctx)
    assert evaluate_condition(PolicyRuleCondition(field="action.resource", operator="starts_with", value="/var/"), ctx)
    assert evaluate_condition(PolicyRuleCondition(field="action.resource", operator="ends_with", value=".csv"), ctx)
    assert not evaluate_condition(PolicyRuleCondition(field="action.resource", operator="starts_with", value="/etc/"), ctx)

    # context time and request
    assert evaluate_condition(PolicyRuleCondition(field="context.time.hour", operator="eq", value=14), ctx)
    assert evaluate_condition(PolicyRuleCondition(field="context.request_id", operator="eq", value="req-999"), ctx)
