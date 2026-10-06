"""Automated tests for Contextual Risk Assessment Engine, scoring, factors, and persistence."""

import uuid
import pytest
from httpx import AsyncClient

from app.db.models.risk_assessment import RiskLevel
from app.db.models.tool_operation import OperationRiskLevel, OperationType
from app.engines.risk.factors import evaluate_factors
from app.engines.risk.scorer import calculate_aggregate_score, score_to_risk_level


async def setup_test_action(
    async_client: AsyncClient,
    org_name: str = "Risk Org",
    op_risk_level: str = "low",
    op_type: str = "read",
    env: str = "dev",
    agent_env: str = "development",
    resource_type: str = "public",
    amount: float = 0.0,
):
    """Helper to provision hierarchy and create a RuntimeAction."""
    # 1. Org
    org = (await async_client.post("/api/v1/organizations", json={"name": org_name})).json()
    org_id = org["id"]

    # 2. Agent
    agent = (
        await async_client.post(
            f"/api/v1/organizations/{org_id}/agents",
            json={"name": f"{org_name} Agent", "environment": agent_env},
        )
    ).json()
    agent_id = agent["id"]

    # 3. Tool
    tool = (
        await async_client.post(
            f"/api/v1/organizations/{org_id}/tools",
            json={"name": f"{org_name} Tool"},
        )
    ).json()
    tool_id = tool["id"]

    # 4. Operation
    op = (
        await async_client.post(
            f"/api/v1/organizations/{org_id}/tools/{tool_id}/operations",
            json={
                "name": "Test Op",
                "operation_type": op_type,
                "risk_level": op_risk_level,
            },
        )
    ).json()
    op_id = op["id"]

    # 5. Action
    action = (
        await async_client.post(
            f"/api/v1/organizations/{org_id}/runtime-actions",
            json={
                "tool_id": tool_id,
                "operation_id": op_id,
                "environment": env,
                "action_type": "execute_test",
                "resource": f"/res/{resource_type}",
                "resource_type": resource_type,
                "amount": amount if amount > 0 else None,
            },
            headers={"X-Agent-ID": agent_id},
        )
    ).json()
    action_id = action["id"]

    return org_id, agent_id, tool_id, op_id, action_id


def test_baseline_risk_scores():
    """A, B, C, D: Verify baseline risk levels produce deterministic numeric scores."""
    # LOW baseline
    factors, _ = evaluate_factors(baseline_risk_level="low", operation_type="read", environment="dev")
    base_factor = next(f for f in factors if f.factor == "baseline_operation_risk")
    assert base_factor.score == 10.0
    assert score_to_risk_level(calculate_aggregate_score([f.score for f in factors])) == RiskLevel.LOW.value

    # MEDIUM baseline
    factors, _ = evaluate_factors(baseline_risk_level="medium", operation_type="read", environment="dev")
    base_factor = next(f for f in factors if f.factor == "baseline_operation_risk")
    assert base_factor.score == 30.0
    assert score_to_risk_level(calculate_aggregate_score([f.score for f in factors])) == RiskLevel.MEDIUM.value

    # HIGH baseline
    factors, _ = evaluate_factors(baseline_risk_level="high", operation_type="read", environment="dev")
    base_factor = next(f for f in factors if f.factor == "baseline_operation_risk")
    assert base_factor.score == 55.0
    assert score_to_risk_level(calculate_aggregate_score([f.score for f in factors])) == RiskLevel.HIGH.value

    # CRITICAL baseline
    factors, _ = evaluate_factors(baseline_risk_level="critical", operation_type="read", environment="dev")
    base_factor = next(f for f in factors if f.factor == "baseline_operation_risk")
    assert base_factor.score == 80.0
    assert score_to_risk_level(calculate_aggregate_score([f.score for f in factors])) == RiskLevel.CRITICAL.value


def test_contextual_factors_contributions():
    """E, F, G, H, I, J, K, L: Verify environment, operations, and resources elevate risk."""
    # E. Production increases risk (+15)
    f_dev, _ = evaluate_factors("low", "read", "dev")
    f_prod, _ = evaluate_factors("low", "read", "prod")
    score_dev = calculate_aggregate_score([f.score for f in f_dev])
    score_prod = calculate_aggregate_score([f.score for f in f_prod])
    assert score_prod == score_dev + 15.0

    # F, G, H, I: Operations (delete +15, execute +15, admin +25, transfer +20 vs read +0)
    f_del, _ = evaluate_factors("low", "delete", "dev")
    assert next(f for f in f_del if f.factor == "operation_type").score == 15.0

    f_exec, _ = evaluate_factors("low", "execute", "dev")
    assert next(f for f in f_exec if f.factor == "operation_type").score == 15.0

    f_adm, _ = evaluate_factors("low", "admin", "dev")
    assert next(f for f in f_adm if f.factor == "operation_type").score == 25.0

    f_xfer, _ = evaluate_factors("low", "transfer", "dev")
    assert next(f for f in f_xfer if f.factor == "operation_type").score == 20.0

    # J, K, L: Resources (sensitive +15, credential +25, financial +20)
    f_sens, _ = evaluate_factors("low", "read", "dev", resource_type="sensitive")
    assert next(f for f in f_sens if f.factor == "resource_sensitivity").score == 15.0

    f_cred, _ = evaluate_factors("low", "read", "dev", resource_type="credential")
    assert next(f for f in f_cred if f.factor == "resource_sensitivity").score == 25.0

    f_fin, _ = evaluate_factors("low", "read", "dev", resource_type="financial")
    assert next(f for f in f_fin if f.factor == "resource_sensitivity").score == 20.0


def test_amount_brackets():
    """M: Verify monetary amount tier contributions."""
    f0, _ = evaluate_factors("low", "read", "dev", amount=5000.0)
    assert next(f for f in f0 if f.factor == "monetary_amount").score == 0.0

    f1, _ = evaluate_factors("low", "read", "dev", amount=25000.0)
    assert next(f for f in f1 if f.factor == "monetary_amount").score == 10.0

    f2, _ = evaluate_factors("low", "read", "dev", amount=75000.0)
    assert next(f for f in f2 if f.factor == "monetary_amount").score == 20.0

    f3, _ = evaluate_factors("low", "read", "dev", amount=250000.0)
    assert next(f for f in f3 if f.factor == "monetary_amount").score == 30.0

    f4, _ = evaluate_factors("low", "read", "dev", amount=1000000.0)
    assert next(f for f in f4 if f.factor == "monetary_amount").score == 40.0


def test_combination_rules():
    """N & O: Verify production destructive operations and sensitive transfer combinations."""
    # N. Production + destructive (prod + delete -> extra +15 combo)
    f_combo_prod, rules_prod = evaluate_factors("low", "delete", "prod")
    assert "combo:production_destructive" in rules_prod
    combo_factor = next(f for f in f_combo_prod if f.factor == "production_destructive_operation")
    assert combo_factor.score == 15.0

    # Non-production does NOT trigger combo
    _, rules_dev = evaluate_factors("low", "delete", "dev")
    assert "combo:production_destructive" not in rules_dev

    # O. Transfer + sensitive resource (transfer + financial -> extra +15 combo)
    f_combo_xfer, rules_xfer = evaluate_factors("low", "transfer", "dev", resource_type="financial")
    assert "combo:sensitive_transfer" in rules_xfer
    xfer_factor = next(f for f in f_combo_xfer if f.factor == "sensitive_transfer")
    assert xfer_factor.score == 15.0


def test_score_capping_and_threshold_mapping():
    """P & Q: Score is strictly capped at 100 and maps to centralized thresholds."""
    # P: Extreme conditions (critical baseline 80 + prod 15 + admin 25 + credential 25 = 145 -> capped at 100)
    factors, _ = evaluate_factors("critical", "admin", "prod", resource_type="credential", amount=1000000.0)
    score = calculate_aggregate_score([f.score for f in factors])
    assert score == 100.0
    assert score_to_risk_level(score) == RiskLevel.CRITICAL.value

    # Q: Centralized thresholds
    assert score_to_risk_level(0.0) == RiskLevel.LOW.value
    assert score_to_risk_level(24.0) == RiskLevel.LOW.value
    assert score_to_risk_level(25.0) == RiskLevel.MEDIUM.value
    assert score_to_risk_level(49.0) == RiskLevel.MEDIUM.value
    assert score_to_risk_level(50.0) == RiskLevel.HIGH.value
    assert score_to_risk_level(74.0) == RiskLevel.HIGH.value
    assert score_to_risk_level(75.0) == RiskLevel.CRITICAL.value
    assert score_to_risk_level(100.0) == RiskLevel.CRITICAL.value


@pytest.mark.asyncio
async def test_risk_assessment_api_and_persistence(async_client: AsyncClient) -> None:
    """R, S, T, U: API assessment, explainability, deterministic evaluation, and history preservation."""
    org_id, _, _, _, action_id = await setup_test_action(
        async_client=async_client,
        org_name="Assessment Persistence Org",
        op_risk_level="high",
        op_type="transfer",
        env="dev",
        resource_type="financial",
        amount=150000.0,
    )

    # T. Post evaluation
    res = await async_client.post(
        f"/api/v1/organizations/{org_id}/runtime-actions/{action_id}/risk-assess"
    )
    assert res.status_code == 201
    data = res.json()
    assert data["organization_id"] == org_id
    assert data["runtime_action_id"] == action_id
    assert data["risk_score"] > 50.0
    assert data["risk_level"] in (RiskLevel.HIGH.value, RiskLevel.CRITICAL.value)
    assessment_1_id = data["id"]

    # R. Explanation contains actual contributing factors
    explanation = data["explanation"]
    assert "Risk score" in explanation
    assert "Operation baseline risk level" in explanation
    assert len(data["factors"]) >= 4

    # S. Deterministic repeated evaluation produces identical score
    res2 = await async_client.post(
        f"/api/v1/organizations/{org_id}/runtime-actions/{action_id}/risk-assess"
    )
    assert res2.status_code == 201
    data2 = res2.json()
    assert data2["risk_score"] == data["risk_score"]
    assert data2["risk_level"] == data["risk_level"]
    assessment_2_id = data2["id"]
    assert assessment_1_id != assessment_2_id  # Unique records

    # U. Multiple assessments preserve history
    hist_res = await async_client.get(
        f"/api/v1/organizations/{org_id}/runtime-actions/{action_id}/risk-assessments"
    )
    assert hist_res.status_code == 200
    hist = hist_res.json()
    assert hist["total"] == 2
    assert hist["items"][0]["id"] == assessment_2_id

    # Retrieve by ID
    get_res = await async_client.get(
        f"/api/v1/organizations/{org_id}/risk-assessments/{assessment_1_id}"
    )
    assert get_res.status_code == 200
    assert get_res.json()["id"] == assessment_1_id


@pytest.mark.asyncio
async def test_tenant_isolation_for_risk_assessments(async_client: AsyncClient) -> None:
    """V, W, X: Cross-tenant isolation, missing action handling, and cross-tenant rejections."""
    org_a, _, _, _, action_a = await setup_test_action(async_client, "Tenant A Org")
    org_b, _, _, _, _ = await setup_test_action(async_client, "Tenant B Org")

    # Assess action in Org A
    assess_res = await async_client.post(
        f"/api/v1/organizations/{org_a}/runtime-actions/{action_a}/risk-assess"
    )
    assert assess_res.status_code == 201
    assess_id = assess_res.json()["id"]

    # V & X: Org B cannot assess Org A's action
    res_b_assess_a = await async_client.post(
        f"/api/v1/organizations/{org_b}/runtime-actions/{action_a}/risk-assess"
    )
    assert res_b_assess_a.status_code == 404

    # Org B cannot retrieve Org A's assessment
    res_b_get_assess = await async_client.get(
        f"/api/v1/organizations/{org_b}/risk-assessments/{assess_id}"
    )
    assert res_b_get_assess.status_code == 404

    # Org B cannot list Org A's action assessments
    res_b_list_assess = await async_client.get(
        f"/api/v1/organizations/{org_b}/runtime-actions/{action_a}/risk-assessments"
    )
    assert res_b_list_assess.status_code == 404

    # W. Missing RuntimeAction rejected with 404
    fake_action_id = str(uuid.uuid4())
    res_missing = await async_client.post(
        f"/api/v1/organizations/{org_a}/runtime-actions/{fake_action_id}/risk-assess"
    )
    assert res_missing.status_code == 404
