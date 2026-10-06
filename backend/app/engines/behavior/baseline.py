"""Behavioral baseline calculation and lifecycle state management."""

from datetime import datetime, timezone
import math
from typing import Optional
from app.db.base import utc_now
from app.db.models.agent_behavior_baseline import AgentBehaviorBaseline, BaselineState
from app.db.models.runtime_action import RuntimeAction


COLD_START_THRESHOLD = 10
ESTABLISHED_THRESHOLD = 50


def calculate_baseline_state(action_count: int) -> BaselineState:
    """Determine baseline maturity state deterministically based on observation count."""
    if action_count < COLD_START_THRESHOLD:
        return BaselineState.COLD_START
    if action_count < ESTABLISHED_THRESHOLD:
        return BaselineState.LEARNING
    return BaselineState.ESTABLISHED


def update_baseline_statistics(
    baseline: AgentBehaviorBaseline,
    action: RuntimeAction,
    is_success: bool = True,
    is_blocked: bool = False,
    is_approval: bool = False,
    risk_score: float = 0.0,
    tool_name: Optional[str] = None,
    operation_name: Optional[str] = None,
) -> AgentBehaviorBaseline:
    """Incrementally update an agent's behavioral baseline statistics from a completed or evaluated action."""
    prev_count = baseline.action_count
    new_count = prev_count + 1
    baseline.action_count = new_count
    baseline.state = calculate_baseline_state(new_count).value

    # Outcome counters
    if is_blocked:
        baseline.blocked_action_count += 1
    elif is_approval:
        baseline.approval_count += 1
    elif is_success:
        baseline.successful_action_count += 1
    else:
        baseline.failed_action_count += 1

    # Tool distributions
    t_name = (tool_name or str(action.tool_id)).lower()
    tool_counts = dict(baseline.tool_counts or {})
    tool_counts[t_name] = tool_counts.get(t_name, 0) + 1
    baseline.tool_counts = tool_counts

    # Operation distributions
    op_name = (operation_name or str(action.operation_id)).lower()
    op_counts = dict(baseline.operation_counts or {})
    op_counts[op_name] = op_counts.get(op_name, 0) + 1
    baseline.operation_counts = op_counts

    # Resource distributions
    res_type = (action.resource_type or "unknown").lower()
    res_counts = dict(baseline.resource_counts or {})
    res_counts[res_type] = res_counts.get(res_type, 0) + 1
    baseline.resource_counts = res_counts

    # Sensitivity indicators
    if res_type in ("financial", "credential", "identity", "sensitive"):
        baseline.sensitive_action_count += 1

    if op_name in ("delete", "execute", "admin"):
        baseline.destructive_action_count += 1

    if op_name == "transfer":
        baseline.transfer_action_count += 1

    # Financial / Numeric amount running statistics (Welford's algorithm)
    if action.amount is not None and action.amount > 0:
        amt = float(action.amount)
        baseline.total_amount += amt
        if amt > baseline.max_amount:
            baseline.max_amount = amt

        # Update running mean and variance
        delta = amt - baseline.average_amount
        baseline.average_amount += delta / new_count
        delta2 = amt - baseline.average_amount
        # Running sample variance update
        if new_count > 1:
            baseline.amount_variance = (baseline.amount_variance * (new_count - 2) + delta * delta2) / (new_count - 1)
        else:
            baseline.amount_variance = 0.0

    # Risk score moving average
    prev_risk = baseline.average_risk_score
    baseline.average_risk_score = (prev_risk * prev_count + risk_score) / new_count
    if risk_score > baseline.max_risk_score:
        baseline.max_risk_score = risk_score

    # Actions per hour calculation
    now = utc_now()
    baseline.last_observed_at = now
    
    # Update rate statistics
    if baseline.created_at:
        b_created = baseline.created_at
        if b_created.tzinfo is None:
            b_created = b_created.replace(tzinfo=timezone.utc)
        elapsed_hours = max((now - b_created).total_seconds() / 3600.0, 1.0 / 60.0)
        baseline.average_actions_per_hour = round(new_count / elapsed_hours, 2)
        if baseline.average_actions_per_hour > baseline.peak_actions_per_hour:
            baseline.peak_actions_per_hour = baseline.average_actions_per_hour

    baseline.baseline_version += 1
    baseline.updated_at = now
    return baseline
