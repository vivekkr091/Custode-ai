"""Automated test suite for CUSTODE Behavioral & Anomaly Detection Engine (Milestone 19)."""

from datetime import datetime, timezone
import os
import uuid
import pytest
from httpx import AsyncClient

from app.db.models.agent_behavior_baseline import AgentBehaviorBaseline, BaselineState
from app.db.models.behavioral_anomaly import (
    AnomalySeverity,
    AnomalyStatus,
    AnomalyType,
    BehavioralAnomaly,
)
from app.db.models.runtime_action import RuntimeAction
from app.engines.behavior.baseline import (
    calculate_baseline_state,
    update_baseline_statistics,
)
from app.engines.behavior.detector import BehavioralDetector
from app.engines.behavior.features import (
    compute_action_fingerprint,
    extract_behavior_features,
    sanitize_payload_for_fingerprint,
)
from app.engines.behavior.scoring import (
    calculate_aggregate_behavior_score,
    compute_anomaly_confidence,
    score_to_severity,
)
from app.engines.decision import resolve_decision_precedence
from app.engines.permission.evaluator import PermissionEvaluationResult
from app.engines.policy.evaluator import PolicyEvaluationResult
from app.engines.risk.evaluator import RiskEngine
from app.engines.risk.factors import evaluate_factors
from tests.test_decisions import provision_test_pipeline


def test_baseline_lifecycle_and_cold_start() -> None:
    """Verify deterministic baseline state transitions and statistics updating."""
    # State thresholds
    assert calculate_baseline_state(0) == BaselineState.COLD_START
    assert calculate_baseline_state(9) == BaselineState.COLD_START
    assert calculate_baseline_state(10) == BaselineState.LEARNING
    assert calculate_baseline_state(49) == BaselineState.LEARNING
    assert calculate_baseline_state(50) == BaselineState.ESTABLISHED
    assert calculate_baseline_state(100) == BaselineState.ESTABLISHED

    org_id = uuid.uuid4()
    agent_id = uuid.uuid4()

    # Create empty baseline
    baseline = AgentBehaviorBaseline(
        organization_id=org_id,
        agent_id=agent_id,
        environment="production",
        state=BaselineState.COLD_START.value,
        observation_window_seconds=86400,
        action_count=0,
        tool_counts={},
        operation_counts={},
        resource_counts={},
    )

    action = RuntimeAction(
        organization_id=org_id,
        agent_id=agent_id,
        tool_id=uuid.uuid4(),
        operation_id=uuid.uuid4(),
        environment="production",
        resource_type="database",
        amount=100.0,
    )

    updated = update_baseline_statistics(
        baseline=baseline,
        action=action,
        is_success=True,
        risk_score=25.0,
        tool_name="sql_client",
        operation_name="read",
    )

    assert updated.action_count == 1
    assert updated.state == BaselineState.COLD_START.value
    assert updated.tool_counts["sql_client"] == 1
    assert updated.operation_counts["read"] == 1
    assert updated.resource_counts["database"] == 1
    assert updated.average_amount == 100.0
    assert updated.max_amount == 100.0
    assert updated.average_risk_score == 25.0


def test_action_fingerprint_privacy_and_secret_redaction() -> None:
    """Ensure action fingerprints strip secrets (passwords, tokens, keys) and remain deterministic."""
    agent_id = uuid.uuid4()
    tool_id = uuid.uuid4()
    op_id = uuid.uuid4()

    payload_clean = {
        "query": "SELECT * FROM users",
        "limit": 10,
    }
    payload_sensitive = {
        "query": "SELECT * FROM users",
        "limit": 10,
        "password": "super_secret_password",
        "api_key": "secret_key_12345",
        "authorization": "Bearer token_abc",
    }

    # Verify sanitizer strips secrets
    sanitized = sanitize_payload_for_fingerprint(payload_sensitive)
    assert sanitized["password"] == "[REDACTED]"
    assert sanitized["api_key"] == "[REDACTED]"
    assert sanitized["authorization"] == "[REDACTED]"
    assert sanitized["query"] == "SELECT * FROM users"

    # Fingerprints with identical non-sensitive data but different secrets must match
    fp1 = compute_action_fingerprint(
        agent_id,
        tool_id,
        op_id,
        "users_table",
        {
            "limit": 10,
            "query": "SELECT * FROM users",
            "password": "initial_secret_123",
        },
    )
    fp2 = compute_action_fingerprint(
        agent_id,
        tool_id,
        op_id,
        "users_table",
        {
            "limit": 10,
            "query": "SELECT * FROM users",
            "password": "different_secret_456",
        },
    )
    assert fp1 == fp2
    assert len(fp1) == 64  # SHA-256


def test_action_rate_and_loop_anomaly_detection() -> None:
    """Verify action rate spikes and runaway action loops produce explainable findings."""
    org_id = uuid.uuid4()
    agent_id = uuid.uuid4()
    tool_id = uuid.uuid4()
    op_id = uuid.uuid4()

    baseline = AgentBehaviorBaseline(
        organization_id=org_id,
        agent_id=agent_id,
        environment="production",
        state=BaselineState.ESTABLISHED.value,
        average_actions_per_hour=60.0,  # 1 action/min typical
        tool_counts={"db_tool": 100},
        operation_counts={"query": 100},
        resource_counts={"database": 100},
        action_count=100,
    )

    now = datetime(2026, 10, 1, 14, 0, tzinfo=timezone.utc)
    current_action = RuntimeAction(
        organization_id=org_id,
        agent_id=agent_id,
        tool_id=tool_id,
        operation_id=op_id,
        environment="production",
        resource_type="database",
        resource="users",
        parameters={"id": 1},
        created_at=now,
    )

    # 1. Normal rate -> no anomaly
    res_normal = BehavioralDetector.evaluate(
        action=current_action,
        baseline=baseline,
        recent_history=[],
        tool_name="db_tool",
        operation_name="query",
    )
    assert len(res_normal.anomalies) == 0
    assert res_normal.behavioral_score == 0.0

    # 2. Simulate 20 rapid actions in the last 60 seconds (rate spike + loop)
    burst_history = []
    for _ in range(20):
        burst_history.append(
            RuntimeAction(
                organization_id=org_id,
                agent_id=agent_id,
                tool_id=tool_id,
                operation_id=op_id,
                environment="production",
                resource_type="database",
                resource="users",
                parameters={"id": 1},
                created_at=now,
            )
        )

    res_burst = BehavioralDetector.evaluate(
        action=current_action,
        baseline=baseline,
        recent_history=burst_history,
        tool_name="db_tool",
        operation_name="query",
    )

    types = [a.anomaly_type for a in res_burst.anomalies]
    assert AnomalyType.ACTION_RATE_SPIKE in types
    assert AnomalyType.ACTION_LOOP in types
    assert AnomalyType.MULTI_SIGNAL_ANOMALY in types
    assert res_burst.behavioral_score >= 70.0
    assert res_burst.highest_severity in (AnomalySeverity.HIGH, AnomalySeverity.CRITICAL)


def test_tool_and_operation_anomaly_detection() -> None:
    """Verify previously unobserved tools and destructive operations generate behavioral signals."""
    org_id = uuid.uuid4()
    agent_id = uuid.uuid4()

    baseline = AgentBehaviorBaseline(
        organization_id=org_id,
        agent_id=agent_id,
        environment="production",
        state=BaselineState.ESTABLISHED.value,
        action_count=80,
        tool_counts={"reporting_tool": 60, "metrics_reader": 20},
        operation_counts={"read": 80},
        resource_counts={"analytics": 80},
    )

    action = RuntimeAction(
        organization_id=org_id,
        agent_id=agent_id,
        tool_id=uuid.uuid4(),
        operation_id=uuid.uuid4(),
        environment="production",
        resource_type="credential",
        resource="aws_keys",
    )

    result = BehavioralDetector.evaluate(
        action=action,
        baseline=baseline,
        recent_history=[],
        tool_name="bash_executor",
        operation_name="delete",
    )

    types = [a.anomaly_type for a in result.anomalies]
    assert AnomalyType.NEW_TOOL_USAGE in types
    assert AnomalyType.NEW_OPERATION_USAGE in types
    assert AnomalyType.NEW_SENSITIVE_RESOURCE in types
    assert AnomalyType.PRIVILEGE_ESCALATION_PATTERN in types


def test_amount_deviation_anomaly() -> None:
    """Verify extreme financial amounts trigger statistical deviation anomalies."""
    org_id = uuid.uuid4()
    agent_id = uuid.uuid4()

    # Baseline with mean $200, variance 2500 (std dev = 50)
    baseline = AgentBehaviorBaseline(
        organization_id=org_id,
        agent_id=agent_id,
        environment="production",
        state=BaselineState.ESTABLISHED.value,
        action_count=100,
        average_amount=200.0,
        max_amount=400.0,
        amount_variance=2500.0,
        tool_counts={"billing": 100},
        operation_counts={"charge": 100},
        resource_counts={"financial": 100},
    )

    # 1. Normal amount ($250, z = 1.0) -> no anomaly
    action_normal = RuntimeAction(
        organization_id=org_id,
        agent_id=agent_id,
        tool_id=uuid.uuid4(),
        operation_id=uuid.uuid4(),
        environment="production",
        amount=250.0,
    )
    res_normal = BehavioralDetector.evaluate(
        action=action_normal,
        baseline=baseline,
        recent_history=[],
        tool_name="billing",
        operation_name="charge",
    )
    assert not any(a.anomaly_type == AnomalyType.AMOUNT_DEVIATION for a in res_normal.anomalies)

    # 2. Outlier amount ($20,000, z > 300) -> CRITICAL anomaly
    action_outlier = RuntimeAction(
        organization_id=org_id,
        agent_id=agent_id,
        tool_id=uuid.uuid4(),
        operation_id=uuid.uuid4(),
        environment="production",
        amount=20000.0,
    )
    res_outlier = BehavioralDetector.evaluate(
        action=action_outlier,
        baseline=baseline,
        recent_history=[],
        tool_name="billing",
        operation_name="charge",
    )
    amt_anom = next(a for a in res_outlier.anomalies if a.anomaly_type == AnomalyType.AMOUNT_DEVIATION)
    assert amt_anom.severity == AnomalySeverity.CRITICAL
    assert amt_anom.score >= 80.0
    assert "deviates significantly" in amt_anom.explanation


def test_failure_spike_detection() -> None:
    """Verify clusters of blocked/failed operations trigger failure spike anomalies."""
    org_id = uuid.uuid4()
    agent_id = uuid.uuid4()

    baseline = AgentBehaviorBaseline(
        organization_id=org_id,
        agent_id=agent_id,
        environment="production",
        state=BaselineState.ESTABLISHED.value,
        action_count=50,
        blocked_action_count=0,
        failed_action_count=1,
    )

    now = datetime(2026, 10, 1, 14, 0, tzinfo=timezone.utc)
    current_action = RuntimeAction(
        organization_id=org_id,
        agent_id=agent_id,
        tool_id=uuid.uuid4(),
        operation_id=uuid.uuid4(),
        environment="production",
        created_at=now,
    )

    history = [
        RuntimeAction(
            organization_id=org_id,
            agent_id=agent_id,
            tool_id=uuid.uuid4(),
            operation_id=uuid.uuid4(),
            environment="production",
            status="blocked",
            created_at=now,
        )
        for _ in range(6)
    ]

    res = BehavioralDetector.evaluate(
        action=current_action,
        baseline=baseline,
        recent_history=history,
    )
    types = [a.anomaly_type for a in res.anomalies]
    assert AnomalyType.BLOCK_SPIKE in types


def test_risk_and_decision_engine_integration() -> None:
    """Verify behavioral findings contribute to Contextual Risk and Decision arbitration."""
    factors, rules = evaluate_factors(
        baseline_risk_level="low",
        operation_type="read",
        environment="dev",
        behavioral_anomalies=[
            BehavioralAnomaly(
                organization_id=uuid.uuid4(),
                agent_id=uuid.uuid4(),
                anomaly_type=AnomalyType.ACTION_RATE_SPIKE.value,
                severity=AnomalySeverity.CRITICAL.value,
                score=85.0,
                feature="action_rate_1m",
                explanation="Critical burst",
            )
        ],
    )
    behavior_factors = [f for f in factors if f.category == "behavioral_anomaly"]
    assert len(behavior_factors) == 1
    assert behavior_factors[0].score == 35.0  # Critical scaled score
    assert "behavior:action_rate_spike:critical" in rules

    # Precedence: Critical Behavioral Anomaly triggers REQUIRE_APPROVAL
    perm_res = PermissionEvaluationResult(allowed=True, effect="allow", reason="Allowed")
    policy_res = PolicyEvaluationResult(decision="ALLOW", reason="No policy rule")
    risk_res = RiskEngine.evaluate(
        runtime_action=RuntimeAction(
            organization_id=uuid.uuid4(),
            agent_id=uuid.uuid4(),
            tool_id=uuid.uuid4(),
            operation_id=uuid.uuid4(),
            environment="dev",
        ),
        operation_baseline_risk_level="low",
        operation_type="read",
        behavioral_anomalies=[
            BehavioralAnomaly(
                organization_id=uuid.uuid4(),
                agent_id=uuid.uuid4(),
                anomaly_type=AnomalyType.ACTION_RATE_SPIKE.value,
                severity=AnomalySeverity.CRITICAL.value,
                score=85.0,
                feature="action_rate_1m",
                explanation="Burst",
            )
        ],
    )

    crit_anom = [
        BehavioralAnomaly(
            organization_id=uuid.uuid4(),
            agent_id=uuid.uuid4(),
            anomaly_type=AnomalyType.ACTION_RATE_SPIKE.value,
            severity=AnomalySeverity.CRITICAL.value,
            score=85.0,
            feature="action_rate_1m",
            explanation="Burst",
        )
    ]
    dec, reason, src, _, _, factors_dec, trace = resolve_decision_precedence(
        permission_result=perm_res,
        policy_result=policy_res,
        risk_result=risk_res,
        behavioral_anomalies=crit_anom,
    )
    assert dec.value == "require_approval"
    assert src == "behavior"
    assert "critical behavioral anomaly" in reason
    assert trace["behavior"]["critical_count"] == 1


@pytest.mark.asyncio
async def test_end_to_end_behavior_pipeline_and_api(async_client: AsyncClient) -> None:
    """Verify end-to-end integration: RuntimeAction decision creates baseline, detects anomalies, and exposes APIs."""
    pipeline = await provision_test_pipeline(
        async_client=async_client,
        org_name="Behavior Engine Org",
        op_risk_level="low",
        permission_effect="allow",
        policy_effect="allow",
    )
    org_id = pipeline["org_id"]
    agent_id = pipeline["agent_id"]
    tool_id = pipeline["tool_id"]
    op_id = pipeline["operation_id"]

    # 1. Execute an action to initialize baseline
    action_resp = await async_client.post(
        f"/api/v1/organizations/{org_id}/runtime-actions",
        json={
            "action_type": "tool_call",
            "tool_id": tool_id,
            "operation_id": op_id,
            "environment": "dev",
            "resource_type": "database",
            "resource": "metrics_table",
            "parameters": {"query": "SELECT 1"},
        },
        headers={"X-Agent-ID": agent_id},
    )
    assert action_resp.status_code == 201, action_resp.text
    action_id = action_resp.json()["id"]

    # Decide on action
    decide_resp = await async_client.post(
        f"/api/v1/organizations/{org_id}/runtime-actions/{action_id}/decide"
    )
    assert decide_resp.status_code == 201, decide_resp.text

    # 2. Check Agent Behavior Profile endpoint
    profile_resp = await async_client.get(
        f"/api/v1/organizations/{org_id}/agents/{agent_id}/behavior?environment=dev"
    )
    assert profile_resp.status_code == 200, profile_resp.text
    profile = profile_resp.json()
    assert profile["agent_id"] == agent_id
    assert profile["state"] == "COLD_START"
    assert profile["action_count"] == 1

    # 3. Check Behavior Metrics endpoint
    metrics_resp = await async_client.get(
        f"/api/v1/organizations/{org_id}/behavior/metrics"
    )
    assert metrics_resp.status_code == 200, metrics_resp.text
    metrics = metrics_resp.json()
    assert metrics["monitored_agents"] >= 1
    assert metrics["cold_start_agents"] >= 1


@pytest.mark.asyncio
async def test_behavior_tenant_isolation_and_rbac(async_client: AsyncClient) -> None:
    """Verify strict tenant isolation and RBAC authorization on anomaly management."""
    # Org A
    pipe_a = await provision_test_pipeline(async_client, org_name="Tenant A Behavior Org")
    org_a = pipe_a["org_id"]
    agent_a = pipe_a["agent_id"]

    # Org B
    pipe_b = await provision_test_pipeline(async_client, org_name="Tenant B Behavior Org")
    org_b = pipe_b["org_id"]

    # Org B attempting to access Org A's agent profile must return 404
    cross_resp = await async_client.get(
        f"/api/v1/organizations/{org_b}/agents/{agent_a}/behavior"
    )
    assert cross_resp.status_code == 404


def test_security_and_no_eval() -> None:
    """Ensure no eval, exec, os.system, or subprocess calls exist in the behavioral engine."""
    behavior_dir = os.path.join(os.path.dirname(__file__), "..", "app", "engines", "behavior")
    for root, _, files in os.walk(behavior_dir):
        for f in files:
            if f.endswith(".py"):
                with open(os.path.join(root, f), "r") as py_file:
                    content = py_file.read()
                    assert "eval(" not in content, f"eval found in {f}"
                    assert "exec(" not in content, f"exec found in {f}"
                    assert "os.system(" not in content, f"os.system found in {f}"
                    assert "subprocess" not in content, f"subprocess found in {f}"
