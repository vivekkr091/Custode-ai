"""Behavioral anomaly detector coordinating feature extraction and deterministic rule evaluation."""

from typing import List, Optional
from app.db.models.agent_behavior_baseline import AgentBehaviorBaseline, BaselineState
from app.db.models.runtime_action import RuntimeAction
from app.engines.behavior.features import extract_behavior_features
from app.engines.behavior.models import BehaviorEvaluationResult, BehavioralFinding
from app.engines.behavior.rules import (
    evaluate_action_loop,
    evaluate_action_rate_spike,
    evaluate_amount_deviation,
    evaluate_failure_spike,
    evaluate_multi_signal_correlation,
    evaluate_new_operation_usage,
    evaluate_new_sensitive_resource,
    evaluate_new_tool_usage,
    evaluate_off_hours_activity,
    evaluate_privilege_escalation,
)
from app.engines.behavior.scoring import calculate_aggregate_behavior_score, score_to_severity


class BehavioralDetector:
    """Deterministic, explainable behavioral anomaly detector."""

    @classmethod
    def evaluate(
        cls,
        action: RuntimeAction,
        baseline: AgentBehaviorBaseline,
        recent_history: List[RuntimeAction],
        tool_name: Optional[str] = None,
        operation_name: Optional[str] = None,
    ) -> BehaviorEvaluationResult:
        """Evaluate a RuntimeAction against agent baseline and sliding window history."""
        # 1. Feature Extraction
        features = extract_behavior_features(
            action=action,
            baseline=baseline,
            recent_history=recent_history,
            tool_name=tool_name,
            operation_name=operation_name,
        )

        findings: List[BehavioralFinding] = []

        # 2. Rule Evaluations
        rate_finding = evaluate_action_rate_spike(features, baseline)
        if rate_finding:
            findings.append(rate_finding)

        tool_finding = evaluate_new_tool_usage(features, baseline, tool_name)
        if tool_finding:
            findings.append(tool_finding)

        op_finding = evaluate_new_operation_usage(features, baseline, operation_name)
        if op_finding:
            findings.append(op_finding)

        res_finding = evaluate_new_sensitive_resource(features, baseline, action.resource_type, action.resource)
        if res_finding:
            findings.append(res_finding)

        amt_finding = evaluate_amount_deviation(features, baseline)
        if amt_finding:
            findings.append(amt_finding)

        fail_finding = evaluate_failure_spike(features, baseline)
        if fail_finding:
            findings.append(fail_finding)

        priv_finding = evaluate_privilege_escalation(features, baseline)
        if priv_finding:
            findings.append(priv_finding)

        hours_finding = evaluate_off_hours_activity(features, baseline)
        if hours_finding:
            findings.append(hours_finding)

        loop_finding = evaluate_action_loop(features, baseline)
        if loop_finding:
            findings.append(loop_finding)

        # 3. Multi-Signal Compound Correlation
        if len(findings) >= 2:
            multi_finding = evaluate_multi_signal_correlation(findings, features, baseline)
            if multi_finding:
                findings.append(multi_finding)

        # 4. Score & Severity Aggregation
        scores = [f.score for f in findings]
        agg_score = calculate_aggregate_behavior_score(scores)
        highest_sev = score_to_severity(agg_score) if findings else None

        return BehaviorEvaluationResult(
            baseline_state=BaselineState(baseline.state),
            observation_count=baseline.action_count,
            anomalies=findings,
            behavioral_score=agg_score,
            highest_severity=highest_sev,
            features=features.to_dict(),
        )
