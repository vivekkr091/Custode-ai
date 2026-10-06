"""Explainable, rule-based behavioral anomaly detection rules."""

from typing import Any, Dict, List, Optional
from app.db.models.agent_behavior_baseline import AgentBehaviorBaseline, BaselineState
from app.db.models.behavioral_anomaly import AnomalySeverity, AnomalyType
from app.engines.behavior.features import ExtractedBehaviorFeatures
from app.engines.behavior.models import BehavioralFinding
from app.engines.behavior.scoring import compute_anomaly_confidence


def evaluate_action_rate_spike(
    features: ExtractedBehaviorFeatures,
    baseline: AgentBehaviorBaseline,
) -> Optional[BehavioralFinding]:
    """Detect abnormal spikes in action invocation frequency."""
    state = BaselineState(baseline.state)

    # In Cold Start, only flag extreme runaway spikes
    if state == BaselineState.COLD_START:
        if features.action_rate_1m >= 60.0:
            return BehavioralFinding(
                anomaly_type=AnomalyType.ACTION_RATE_SPIKE,
                severity=AnomalySeverity.HIGH,
                confidence=compute_anomaly_confidence(state, baseline.action_count, 1, 3.0),
                score=65.0,
                feature="action_rate_1m",
                baseline_value={"average_actions_per_min": 0.5, "state": state.value},
                observed_value={"actions_1m": features.action_rate_1m, "actions_5m": features.action_rate_5m * 5.0},
                deviation=round(features.action_rate_1m / 1.0, 2),
                explanation=f"Extreme runaway action burst detected: {features.action_rate_1m:.0f} actions in 1 minute during cold start.",
                evidence=[f"Observed {features.action_rate_1m:.0f} actions in the last 60 seconds"],
                signals=["RATE_BURST_COLD_START"],
            )
        return None

    # Established or Learning baseline rate comparison
    baseline_rate_per_min = max(baseline.average_actions_per_hour / 60.0, 0.2)
    ratio = features.action_rate_1m / baseline_rate_per_min if baseline_rate_per_min > 0 else 1.0

    if features.action_rate_1m >= 15.0 and ratio >= 3.0:
        if features.action_rate_1m >= 60.0 or ratio >= 10.0:
            sev = AnomalySeverity.CRITICAL
            score = 85.0
        elif features.action_rate_1m >= 30.0 or ratio >= 5.0:
            sev = AnomalySeverity.HIGH
            score = 65.0
        else:
            sev = AnomalySeverity.MEDIUM
            score = 40.0

        return BehavioralFinding(
            anomaly_type=AnomalyType.ACTION_RATE_SPIKE,
            severity=sev,
            confidence=compute_anomaly_confidence(state, baseline.action_count, 1, ratio),
            score=score,
            feature="action_rate_1m",
            baseline_value={"average_actions_per_min": round(baseline_rate_per_min, 2), "average_per_hour": baseline.average_actions_per_hour},
            observed_value={"actions_1m": features.action_rate_1m, "actions_5m": features.action_rate_5m * 5.0, "ratio": round(ratio, 2)},
            deviation=round(ratio, 2),
            explanation=f"Action invocation rate spike ({features.action_rate_1m:.0f} actions/min) exceeds typical baseline ({baseline_rate_per_min:.1f}/min) by {ratio:.1f}x.",
            evidence=[
                f"Current 1m rate: {features.action_rate_1m:.0f} actions/min",
                f"Baseline average: {baseline_rate_per_min:.2f} actions/min",
                f"Rate ratio: {ratio:.1f}x",
            ],
            signals=["ACTION_RATE_BURST"],
        )

    return None


def evaluate_new_tool_usage(
    features: ExtractedBehaviorFeatures,
    baseline: AgentBehaviorBaseline,
    tool_name: Optional[str] = None,
) -> Optional[BehavioralFinding]:
    """Detect invocation of a tool previously unseen in the agent's baseline history."""
    state = BaselineState(baseline.state)
    if state == BaselineState.COLD_START:
        return None

    if features.is_new_tool:
        t_name = tool_name or "unregistered_tool"
        is_high_risk = any(k in t_name.lower() for k in ("bash", "shell", "delete", "filesystem", "exec", "eval", "terminal"))
        sev = AnomalySeverity.HIGH if is_high_risk else AnomalySeverity.LOW
        score = 60.0 if is_high_risk else 25.0

        known_tools = list(baseline.tool_counts.keys()) if baseline.tool_counts else []
        return BehavioralFinding(
            anomaly_type=AnomalyType.NEW_TOOL_USAGE,
            severity=sev,
            confidence=compute_anomaly_confidence(state, baseline.action_count, 1, 2.0),
            score=score,
            feature="tool_usage",
            baseline_value={"known_tools": known_tools[:10], "known_tools_count": len(known_tools)},
            observed_value={"tool_name": t_name},
            deviation=1.0,
            explanation=f"Agent invoked previously unobserved tool '{t_name}'. Known tools in baseline: {len(known_tools)}.",
            evidence=[f"Tool '{t_name}' has 0 historical observations across {baseline.action_count} baseline actions"],
            signals=["NEW_TOOL"],
        )

    return None


def evaluate_new_operation_usage(
    features: ExtractedBehaviorFeatures,
    baseline: AgentBehaviorBaseline,
    operation_name: Optional[str] = None,
) -> Optional[BehavioralFinding]:
    """Detect execution of an operation type previously unseen in baseline."""
    state = BaselineState(baseline.state)
    if state == BaselineState.COLD_START:
        return None

    if features.is_new_operation:
        op_name = (operation_name or "unknown").lower()
        is_destructive = op_name in ("delete", "admin", "execute", "transfer")
        sev = AnomalySeverity.HIGH if is_destructive else AnomalySeverity.LOW
        score = 60.0 if is_destructive else 20.0

        known_ops = list(baseline.operation_counts.keys()) if baseline.operation_counts else []
        return BehavioralFinding(
            anomaly_type=AnomalyType.NEW_OPERATION_USAGE,
            severity=sev,
            confidence=compute_anomaly_confidence(state, baseline.action_count, 1, 2.0),
            score=score,
            feature="operation_usage",
            baseline_value={"known_operations": known_ops},
            observed_value={"operation_name": op_name},
            deviation=1.0,
            explanation=f"Agent invoked unobserved operation '{op_name}'. Previously established operations: {', '.join(known_ops)}.",
            evidence=[f"Operation '{op_name}' has 0 prior occurrences in agent baseline"],
            signals=["NEW_OPERATION"],
        )

    return None


def evaluate_new_sensitive_resource(
    features: ExtractedBehaviorFeatures,
    baseline: AgentBehaviorBaseline,
    resource_type: Optional[str] = None,
    resource: Optional[str] = None,
) -> Optional[BehavioralFinding]:
    """Detect access to sensitive resource types not previously accessed by this agent."""
    state = BaselineState(baseline.state)
    if state == BaselineState.COLD_START:
        return None

    if features.is_new_sensitive_resource:
        res_t = resource_type or "sensitive"
        known_res = list(baseline.resource_counts.keys()) if baseline.resource_counts else []
        return BehavioralFinding(
            anomaly_type=AnomalyType.NEW_SENSITIVE_RESOURCE,
            severity=AnomalySeverity.HIGH,
            confidence=compute_anomaly_confidence(state, baseline.action_count, 1, 2.5),
            score=65.0,
            feature="resource_type",
            baseline_value={"known_resource_types": known_res},
            observed_value={"resource_type": res_t, "resource": resource or ""},
            deviation=2.0,
            explanation=f"Agent accessed sensitive resource category '{res_t}' without prior operational history.",
            evidence=[f"Resource type '{res_t}' previously unobserved in agent history"],
            signals=["NEW_SENSITIVE_RESOURCE"],
        )

    return None


def evaluate_amount_deviation(
    features: ExtractedBehaviorFeatures,
    baseline: AgentBehaviorBaseline,
) -> Optional[BehavioralFinding]:
    """Detect financial transaction amounts significantly exceeding statistical baseline."""
    if features.current_amount is None or baseline.action_count < 5 or baseline.average_amount <= 0:
        return None

    state = BaselineState(baseline.state)
    z = features.amount_z_score
    curr_amt = features.current_amount
    avg_amt = baseline.average_amount

    if z >= 3.0 and curr_amt >= avg_amt * 2.5 and curr_amt >= 500.0:
        if z >= 5.0 or curr_amt >= avg_amt * 10.0:
            sev = AnomalySeverity.CRITICAL
            score = 80.0
        else:
            sev = AnomalySeverity.HIGH
            score = 60.0

        return BehavioralFinding(
            anomaly_type=AnomalyType.AMOUNT_DEVIATION,
            severity=sev,
            confidence=compute_anomaly_confidence(state, baseline.action_count, 1, z),
            score=score,
            feature="transaction_amount",
            baseline_value={"average_amount": round(avg_amt, 2), "max_amount": round(baseline.max_amount, 2)},
            observed_value={"amount": curr_amt, "z_score": z},
            deviation=round(z, 2),
            explanation=f"Action amount ${curr_amt:,.2f} deviates significantly from baseline average ${avg_amt:,.2f} (z-score: {z:.1f}σ).",
            evidence=[
                f"Current amount: ${curr_amt:,.2f}",
                f"Baseline average: ${avg_amt:,.2f}",
                f"Statistical deviation: {z:.1f} standard deviations",
            ],
            signals=["FINANCIAL_OUTLIER"],
        )

    return None


def evaluate_failure_spike(
    features: ExtractedBehaviorFeatures,
    baseline: AgentBehaviorBaseline,
) -> Optional[BehavioralFinding]:
    """Detect anomalous burst of failed or blocked authorization actions."""
    state = BaselineState(baseline.state)

    if features.blocked_count_5m >= 5:
        return BehavioralFinding(
            anomaly_type=AnomalyType.BLOCK_SPIKE,
            severity=AnomalySeverity.HIGH,
            confidence=compute_anomaly_confidence(state, baseline.action_count, 1, 2.0),
            score=65.0,
            feature="blocked_actions_5m",
            baseline_value={"blocked_total": baseline.blocked_action_count},
            observed_value={"blocked_last_5m": features.blocked_count_5m},
            deviation=float(features.blocked_count_5m),
            explanation=f"High frequency of blocked actions detected: {features.blocked_count_5m} actions denied in 5 minutes.",
            evidence=[f"{features.blocked_count_5m} actions were denied/blocked within the last 300 seconds"],
            signals=["BLOCK_BURST"],
        )

    if features.failure_count_5m >= 5:
        return BehavioralFinding(
            anomaly_type=AnomalyType.FAILURE_SPIKE,
            severity=AnomalySeverity.MEDIUM,
            confidence=compute_anomaly_confidence(state, baseline.action_count, 1, 1.5),
            score=45.0,
            feature="failed_actions_5m",
            baseline_value={"failed_total": baseline.failed_action_count},
            observed_value={"failed_last_5m": features.failure_count_5m},
            deviation=float(features.failure_count_5m),
            explanation=f"Unusual cluster of failed operations: {features.failure_count_5m} execution failures within 5 minutes.",
            evidence=[f"{features.failure_count_5m} actions failed within the last 300 seconds"],
            signals=["FAILURE_BURST"],
        )

    return None


def evaluate_privilege_escalation(
    features: ExtractedBehaviorFeatures,
    baseline: AgentBehaviorBaseline,
) -> Optional[BehavioralFinding]:
    """Detect sudden behavioral transition from low-privilege queries to destructive or administrative capabilities."""
    state = BaselineState(baseline.state)
    if state == BaselineState.COLD_START:
        return None

    if features.is_privilege_escalation:
        return BehavioralFinding(
            anomaly_type=AnomalyType.PRIVILEGE_ESCALATION_PATTERN,
            severity=AnomalySeverity.HIGH,
            confidence=compute_anomaly_confidence(state, baseline.action_count, 1, 2.0),
            score=70.0,
            feature="privilege_pattern",
            baseline_value={"destructive_actions_count": baseline.destructive_action_count},
            observed_value={"operation": "destructive_or_credential_access"},
            deviation=2.0,
            explanation="Behavioral privilege escalation pattern: agent with exclusively low-privilege read history attempted administrative or destructive action.",
            evidence=["Agent history contains 0 destructive actions across 10+ prior operations"],
            signals=["PRIVILEGE_ESCALATION"],
        )

    return None


def evaluate_off_hours_activity(
    features: ExtractedBehaviorFeatures,
    baseline: AgentBehaviorBaseline,
) -> Optional[BehavioralFinding]:
    """Detect actions executed outside established operational business hours."""
    state = BaselineState(baseline.state)
    if state != BaselineState.ESTABLISHED:
        return None

    if features.is_off_hours:
        return BehavioralFinding(
            anomaly_type=AnomalyType.OFF_HOURS_ACTIVITY,
            severity=AnomalySeverity.LOW,
            confidence=compute_anomaly_confidence(state, baseline.action_count, 1, 1.0),
            score=20.0,
            feature="operating_hours",
            baseline_value={"operational_hours": f"{baseline.operational_hours_start:02d}:00 - {baseline.operational_hours_end:02d}:00 UTC"},
            observed_value={"current_hour_utc": features.current_hour},
            deviation=1.0,
            explanation=f"Action executed during off-hours ({features.current_hour:02d}:00 UTC). Normal operating schedule: {baseline.operational_hours_start:02d}:00 - {baseline.operational_hours_end:02d}:00 UTC.",
            evidence=[f"Current invocation hour {features.current_hour:02d}:00 UTC is outside configured operational window"],
            signals=["OFF_HOURS"],
        )

    return None


def evaluate_action_loop(
    features: ExtractedBehaviorFeatures,
    baseline: AgentBehaviorBaseline,
) -> Optional[BehavioralFinding]:
    """Detect repetitive looping calls with identical parameters and target capabilities."""
    state = BaselineState(baseline.state)
    reps = features.fingerprint_repetition_count

    if reps >= 5:
        if reps >= 15:
            sev = AnomalySeverity.CRITICAL
            score = 80.0
        else:
            sev = AnomalySeverity.HIGH
            score = 60.0

        return BehavioralFinding(
            anomaly_type=AnomalyType.ACTION_LOOP,
            severity=sev,
            confidence=compute_anomaly_confidence(state, baseline.action_count, 1, float(reps) / 5.0),
            score=score,
            feature="action_repetition",
            baseline_value={"max_repetitive_loop": 1},
            observed_value={"repetition_count": reps, "fingerprint_prefix": features.action_fingerprint[:12]},
            deviation=float(reps),
            explanation=f"Runaway loop detected: {reps} identical consecutive action invocations within a 2-minute window.",
            evidence=[
                f"Action fingerprint {features.action_fingerprint[:12]} observed {reps} times in 120 seconds",
                "Sanitized parameter and target structure are identical across invocations",
            ],
            signals=["RUNAWAY_LOOP"],
        )

    return None


def evaluate_multi_signal_correlation(
    findings: List[BehavioralFinding],
    features: ExtractedBehaviorFeatures,
    baseline: AgentBehaviorBaseline,
) -> Optional[BehavioralFinding]:
    """Correlate multiple weak or high signals occurring simultaneously into an authoritative compound finding."""
    if len(findings) < 2:
        return None

    state = BaselineState(baseline.state)
    all_signals = []
    max_score = 0.0
    for f in findings:
        all_signals.extend(f.signals)
        if f.score > max_score:
            max_score = f.score

    # Compute compound score with elevation
    compound_score = min(max_score + (len(findings) - 1) * 15.0, 95.0)
    sev = AnomalySeverity.CRITICAL if compound_score >= 75.0 else AnomalySeverity.HIGH

    types_summary = ", ".join([f.anomaly_type.value for f in findings])
    return BehavioralFinding(
        anomaly_type=AnomalyType.MULTI_SIGNAL_ANOMALY,
        severity=sev,
        confidence=compute_anomaly_confidence(state, baseline.action_count, len(findings), 3.0),
        score=compound_score,
        feature="multi_signal_correlation",
        baseline_value={"state": state.value, "observation_count": baseline.action_count},
        observed_value={"signal_count": len(findings), "component_anomalies": [f.anomaly_type.value for f in findings]},
        deviation=float(len(findings)),
        explanation=f"Correlated multi-signal behavioral anomaly detected: {len(findings)} concurrent deviations observed ({types_summary}).",
        evidence=[f"{f.anomaly_type.value} [{f.severity.value}]: {f.explanation}" for f in findings],
        signals=list(set(all_signals)),
    )
