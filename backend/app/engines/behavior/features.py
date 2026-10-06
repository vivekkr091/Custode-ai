"""Deterministic behavioral feature extraction from runtime actions and historical telemetry."""

from datetime import datetime, timezone
import hashlib
import json
import math
from typing import Any, Dict, List, Optional
import uuid

from app.db.models.agent_behavior_baseline import AgentBehaviorBaseline
from app.db.models.runtime_action import RuntimeAction
from app.engines.behavior.models import BehavioralFeature


SENSITIVE_KEYS = {
    "password", "token", "secret", "key", "api_key", "auth", "authorization",
    "private_key", "client_secret", "credential", "session_token"
}


def sanitize_payload_for_fingerprint(obj: Any) -> Any:
    """Recursively strip sensitive keys and canonicalize payload structure for behavioral fingerprinting."""
    if isinstance(obj, dict):
        clean = {}
        for k, v in sorted(obj.items()):
            k_lower = str(k).lower()
            if any(s in k_lower for s in SENSITIVE_KEYS):
                clean[k] = "[REDACTED]"
            else:
                clean[k] = sanitize_payload_for_fingerprint(v)
        return clean
    elif isinstance(obj, list):
        return [sanitize_payload_for_fingerprint(item) for item in obj]
    return obj


def compute_action_fingerprint(
    agent_id: uuid.UUID,
    tool_id: uuid.UUID,
    operation_id: uuid.UUID,
    resource: Optional[str],
    parameters: Optional[Dict[str, Any]],
) -> str:
    """Compute a deterministic, privacy-preserving SHA-256 fingerprint for action loop detection."""
    sanitized_params = sanitize_payload_for_fingerprint(parameters or {})
    raw_dict = {
        "agent_id": str(agent_id),
        "tool_id": str(tool_id),
        "operation_id": str(operation_id),
        "resource": resource or "",
        "parameters": sanitized_params,
    }
    canonical_json = json.dumps(raw_dict, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical_json.encode("utf-8")).hexdigest()


class ExtractedBehaviorFeatures:
    """Container for all deterministic features computed for an action evaluation."""

    def __init__(
        self,
        action_rate_1m: float,
        action_rate_5m: float,
        recent_actions_count_5m: int,
        tool_diversity_5m: int,
        operation_diversity_5m: int,
        failure_count_5m: int,
        blocked_count_5m: int,
        is_off_hours: bool,
        current_hour: int,
        is_new_tool: bool,
        is_new_operation: bool,
        is_new_sensitive_resource: bool,
        amount_z_score: float,
        current_amount: Optional[float],
        action_fingerprint: str,
        fingerprint_repetition_count: int,
        is_privilege_escalation: bool,
    ):
        self.action_rate_1m = action_rate_1m
        self.action_rate_5m = action_rate_5m
        self.recent_actions_count_5m = recent_actions_count_5m
        self.tool_diversity_5m = tool_diversity_5m
        self.operation_diversity_5m = operation_diversity_5m
        self.failure_count_5m = failure_count_5m
        self.blocked_count_5m = blocked_count_5m
        self.is_off_hours = is_off_hours
        self.current_hour = current_hour
        self.is_new_tool = is_new_tool
        self.is_new_operation = is_new_operation
        self.is_new_sensitive_resource = is_new_sensitive_resource
        self.amount_z_score = amount_z_score
        self.current_amount = current_amount
        self.action_fingerprint = action_fingerprint
        self.fingerprint_repetition_count = fingerprint_repetition_count
        self.is_privilege_escalation = is_privilege_escalation

    def to_dict(self) -> Dict[str, Any]:
        return {
            "action_rate_1m": self.action_rate_1m,
            "action_rate_5m": self.action_rate_5m,
            "recent_actions_count_5m": self.recent_actions_count_5m,
            "tool_diversity_5m": self.tool_diversity_5m,
            "operation_diversity_5m": self.operation_diversity_5m,
            "failure_count_5m": self.failure_count_5m,
            "blocked_count_5m": self.blocked_count_5m,
            "is_off_hours": self.is_off_hours,
            "current_hour": self.current_hour,
            "is_new_tool": self.is_new_tool,
            "is_new_operation": self.is_new_operation,
            "is_new_sensitive_resource": self.is_new_sensitive_resource,
            "amount_z_score": self.amount_z_score,
            "current_amount": self.current_amount,
            "action_fingerprint": self.action_fingerprint[:16],
            "fingerprint_repetition_count": self.fingerprint_repetition_count,
            "is_privilege_escalation": self.is_privilege_escalation,
        }


def extract_behavior_features(
    action: RuntimeAction,
    baseline: AgentBehaviorBaseline,
    recent_history: List[RuntimeAction],
    tool_name: Optional[str] = None,
    operation_name: Optional[str] = None,
) -> ExtractedBehaviorFeatures:
    """Deterministically extract behavioral features comparing current action against baseline and sliding window history."""
    now = action.created_at or datetime.now(timezone.utc)
    if now.tzinfo is None:
        now = now.replace(tzinfo=timezone.utc)

    # 1. Rate Extraction (Sliding Windows)
    actions_1m = 0
    actions_5m = 0
    recent_tools = set()
    recent_operations = set()
    recent_failures = 0
    recent_blocks = 0

    current_fingerprint = compute_action_fingerprint(
        agent_id=action.agent_id,
        tool_id=action.tool_id,
        operation_id=action.operation_id,
        resource=action.resource,
        parameters=action.parameters,
    )
    fingerprint_count = 0

    for past_action in recent_history:
        p_time = past_action.created_at or now
        if p_time.tzinfo is None:
            p_time = p_time.replace(tzinfo=timezone.utc)
        delta_sec = (now - p_time).total_seconds()
        if delta_sec < 0:
            delta_sec = 0

        # 1-minute window
        if delta_sec <= 60:
            actions_1m += 1

        # 5-minute window
        if delta_sec <= 300:
            actions_5m += 1
            recent_tools.add(str(past_action.tool_id))
            recent_operations.add(str(past_action.operation_id))
            st = past_action.status.lower() if past_action.status else ""
            if st in ("failed", "error"):
                recent_failures += 1
            elif st in ("blocked", "denied"):
                recent_blocks += 1

            # Loop detection: 2-minute window
            if delta_sec <= 120:
                past_fp = compute_action_fingerprint(
                    agent_id=past_action.agent_id,
                    tool_id=past_action.tool_id,
                    operation_id=past_action.operation_id,
                    resource=past_action.resource,
                    parameters=past_action.parameters,
                )
                if past_fp == current_fingerprint:
                    fingerprint_count += 1

    # 2. Operational Hours (Off-Hours Activity)
    current_hour = now.hour
    start_hour = baseline.operational_hours_start if baseline.operational_hours_start is not None else 8
    end_hour = baseline.operational_hours_end if baseline.operational_hours_end is not None else 20
    is_off_hours = not (start_hour <= current_hour < end_hour)

    # 3. Tool & Operation Discovery vs Baseline
    t_key = (tool_name or str(action.tool_id)).lower()
    op_key = (operation_name or str(action.operation_id)).lower()
    known_tools = set(k.lower() for k in (baseline.tool_counts or {}).keys())
    known_operations = set(k.lower() for k in (baseline.operation_counts or {}).keys())
    known_resources = set(k.lower() for k in (baseline.resource_counts or {}).keys())

    is_new_tool = t_key not in known_tools and len(known_tools) > 0
    is_new_operation = op_key not in known_operations and len(known_operations) > 0

    res_type = (action.resource_type or "").lower()
    is_sensitive_type = res_type in ("financial", "credential", "identity", "database", "sensitive")
    is_new_sensitive_resource = is_sensitive_type and (res_type not in known_resources) and len(known_resources) > 0

    # 4. Privilege Escalation Pattern:
    # History dominated by read/custom, current action is delete/admin/execute or credential
    is_destructive_or_admin = op_key in ("admin", "delete", "execute") or res_type == "credential"
    has_prior_destructive = baseline.destructive_action_count > 0 or "admin" in known_operations or "delete" in known_operations
    is_privilege_escalation = is_destructive_or_admin and not has_prior_destructive and baseline.action_count >= 10

    # 5. Amount Deviation (Z-Score)
    amount_z_score = 0.0
    current_amount = float(action.amount) if action.amount is not None else None
    if current_amount is not None and baseline.action_count > 1 and baseline.amount_variance > 0:
        std_dev = math.sqrt(baseline.amount_variance)
        if std_dev > 0.01:
            amount_z_score = (current_amount - baseline.average_amount) / std_dev

    return ExtractedBehaviorFeatures(
        action_rate_1m=float(actions_1m),
        action_rate_5m=float(actions_5m) / 5.0,
        recent_actions_count_5m=actions_5m,
        tool_diversity_5m=len(recent_tools),
        operation_diversity_5m=len(recent_operations),
        failure_count_5m=recent_failures,
        blocked_count_5m=recent_blocks,
        is_off_hours=is_off_hours,
        current_hour=current_hour,
        is_new_tool=is_new_tool,
        is_new_operation=is_new_operation,
        is_new_sensitive_resource=is_new_sensitive_resource,
        amount_z_score=round(amount_z_score, 2),
        current_amount=current_amount,
        action_fingerprint=current_fingerprint,
        fingerprint_repetition_count=fingerprint_count,
        is_privilege_escalation=is_privilege_escalation,
    )
