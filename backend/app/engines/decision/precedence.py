"""Centralized decision precedence resolver for the CUSTODE Decision Engine.

Effective Precedence:
DENY (BLOCK) > REQUIRE_APPROVAL > ALLOW

Origin of enforcement:
- DENY: Permission Engine (highest authority) OR Policy Engine
- REQUIRE_APPROVAL: Policy Engine OR Risk Engine (CRITICAL / HIGH risk)
- ALLOW: Only when all checks pass without denial or approval requirements
"""

from typing import Any, Dict, List, Optional, Tuple
import uuid

from app.engines.permission.evaluator import PermissionEvaluationResult
from app.engines.policy.evaluator import PolicyEvaluationResult
from app.engines.risk.evaluator import RiskEvaluationResult
from app.schemas.decision import DecisionFactor, DecisionType


def resolve_decision_precedence(
    permission_result: PermissionEvaluationResult,
    policy_result: PolicyEvaluationResult,
    risk_result: RiskEvaluationResult,
    security_findings: Optional[List[Any]] = None,
    behavioral_anomalies: Optional[List[Any]] = None,
) -> Tuple[DecisionType, str, str, Optional[uuid.UUID], Optional[uuid.UUID], List[DecisionFactor], Dict[str, Any]]:
    """Resolve final authorization decision using strict, deterministic precedence.

    Returns:
        (decision, reason, enforcement_source, policy_id, policy_version_id, factors, evaluation_trace)
    """
    factors: List[DecisionFactor] = []

    # 1. Inspect Permission Result
    perm_allowed = bool(permission_result.allowed)
    perm_effect = permission_result.effect.lower()
    perm_factor = DecisionFactor(
        source="permission",
        type="agent_permission",
        value=perm_allowed,
        effect=perm_effect,
        reason=permission_result.reason,
    )
    factors.append(perm_factor)

    # 2. Inspect Policy Result
    policy_dec = policy_result.decision.upper()
    policy_id: Optional[uuid.UUID] = None
    policy_version_id: Optional[uuid.UUID] = None

    # Identify primary contributing enforced rule if any
    contributing_rule = None
    if policy_result.enforced_rules:
        # Match according to policy decision
        if policy_dec == "DENY":
            contributing_rule = next((r for r in policy_result.enforced_rules if r.effect.lower() == "deny"), None)
        elif policy_dec == "REQUIRE_APPROVAL":
            contributing_rule = next((r for r in policy_result.enforced_rules if r.effect.lower() == "require_approval"), None)
        elif policy_dec == "ALLOW":
            contributing_rule = next((r for r in policy_result.enforced_rules if r.effect.lower() == "allow"), None)
        if contributing_rule is None:
            contributing_rule = policy_result.enforced_rules[0]

    if contributing_rule:
        policy_id = contributing_rule.policy_id
        policy_version_id = getattr(contributing_rule, "policy_version_id", None)

    policy_factor = DecisionFactor(
        source="policy",
        type="policy_evaluation",
        value=policy_result.decision,
        effect=policy_result.decision.lower(),
        reason=policy_result.reason,
    )
    factors.append(policy_factor)

    # 3. Inspect Risk Result
    risk_lvl = risk_result.risk_level.upper()
    risk_requires_approval = risk_lvl in ("CRITICAL", "HIGH")
    risk_factor = DecisionFactor(
        source="risk",
        type="contextual_risk",
        value=risk_result.risk_score,
        effect="require_approval" if risk_requires_approval else "allow",
        reason=f"Risk level {risk_result.risk_level} with score {risk_result.risk_score}",
    )
    factors.append(risk_factor)

    # 4. Inspect Sentinel Security Findings
    critical_findings = []
    high_findings = []
    if security_findings:
        for f in security_findings:
            sev = getattr(f, "severity", "LOW")
            if hasattr(sev, "value"):
                sev = sev.value
            sev_str = str(sev).upper()
            if sev_str == "CRITICAL":
                critical_findings.append(f)
            elif sev_str == "HIGH":
                high_findings.append(f)

        if critical_findings:
            first_crit = critical_findings[0]
            crit_title = getattr(first_crit, "title", "Critical security finding")
            crit_cat = getattr(first_crit, "category", "SECURITY")
            factors.append(
                DecisionFactor(
                    source="sentinel",
                    type="security_finding",
                    value="CRITICAL",
                    effect="block",
                    reason=f"Sentinel critical finding: {crit_title} ({crit_cat})",
                )
            )
        elif high_findings:
            first_high = high_findings[0]
            high_title = getattr(first_high, "title", "High security finding")
            high_cat = getattr(first_high, "category", "SECURITY")
            factors.append(
                DecisionFactor(
                    source="sentinel",
                    type="security_finding",
                    value="HIGH",
                    effect="require_approval",
                    reason=f"Sentinel high finding: {high_title} ({high_cat})",
                )
            )

    # 4.5. Inspect Behavioral Anomalies
    critical_anomalies = []
    high_anomalies = []
    if behavioral_anomalies:
        for a in behavioral_anomalies:
            sev = getattr(a, "severity", "LOW")
            if hasattr(sev, "value"):
                sev = sev.value
            sev_str = str(sev).upper()
            if sev_str == "CRITICAL":
                critical_anomalies.append(a)
            elif sev_str == "HIGH":
                high_anomalies.append(a)

        if critical_anomalies:
            first_crit_anom = critical_anomalies[0]
            anom_type = getattr(first_crit_anom, "anomaly_type", "CRITICAL_ANOMALY")
            if hasattr(anom_type, "value"):
                anom_type = anom_type.value
            factors.append(
                DecisionFactor(
                    source="behavior",
                    type="behavioral_anomaly",
                    value="CRITICAL",
                    effect="require_approval",
                    reason=f"Behavioral critical anomaly: {first_crit_anom.explanation}",
                )
            )
        elif high_anomalies:
            first_high_anom = high_anomalies[0]
            anom_type = getattr(first_high_anom, "anomaly_type", "HIGH_ANOMALY")
            if hasattr(anom_type, "value"):
                anom_type = anom_type.value
            factors.append(
                DecisionFactor(
                    source="behavior",
                    type="behavioral_anomaly",
                    value="HIGH",
                    effect="risk_contribution",
                    reason=f"Behavioral high anomaly: {first_high_anom.explanation}",
                )
            )

    # 5. Resolve Precedence
    final_decision: DecisionType
    enforcement_source: str
    final_reason: str

    # RULE 1 — Permission DENY: Highest authority
    if not perm_allowed or perm_effect == "deny":
        final_decision = DecisionType.block
        enforcement_source = "permission"
        final_reason = f"Action blocked because permission check failed: {permission_result.reason}"

    # RULE 2 — Policy DENY
    elif policy_dec == "DENY":
        final_decision = DecisionType.block
        enforcement_source = "policy"
        final_reason = f"Action blocked by policy: {policy_result.reason}"

    # RULE 3 — Sentinel CRITICAL Finding -> BLOCK
    elif critical_findings:
        first_crit = critical_findings[0]
        crit_title = getattr(first_crit, "title", "Critical security finding")
        crit_cat = getattr(first_crit, "category", "SECURITY")
        final_decision = DecisionType.block
        enforcement_source = "sentinel"
        final_reason = f"Action blocked due to critical security finding: {crit_title} ({crit_cat})."

    # RULE 4 — Policy REQUIRE_APPROVAL
    elif policy_dec == "REQUIRE_APPROVAL":
        final_decision = DecisionType.require_approval
        enforcement_source = "policy"
        final_reason = f"Action requires approval by policy: {policy_result.reason}"

    # RULE 5 — Sentinel HIGH Finding -> REQUIRE_APPROVAL
    elif high_findings:
        first_high = high_findings[0]
        high_title = getattr(first_high, "title", "High security finding")
        high_cat = getattr(first_high, "category", "SECURITY")
        final_decision = DecisionType.require_approval
        enforcement_source = "sentinel"
        final_reason = f"Human approval required due to high security finding: {high_title} ({high_cat})."

    # RULE 5.5 — Critical Behavioral Anomaly -> REQUIRE_APPROVAL
    elif critical_anomalies:
        first_crit_anom = critical_anomalies[0]
        final_decision = DecisionType.require_approval
        enforcement_source = "behavior"
        final_reason = f"Human approval required due to critical behavioral anomaly: {first_crit_anom.explanation}"

    # RULE 6 — Risk CRITICAL / HIGH -> REQUIRE_APPROVAL
    elif risk_requires_approval:
        final_decision = DecisionType.require_approval
        enforcement_source = "risk"
        final_reason = (
            f"Human approval required because the action has {risk_result.risk_level.lower()} "
            f"contextual risk (risk score: {risk_result.risk_score:.2f})."
        )

    # RULE 7 — ALLOW
    else:
        final_decision = DecisionType.allow
        enforcement_source = "system"
        final_reason = (
            "Action allowed because the agent has permission, no enforcing policy denied "
            "or required approval, and contextual risk does not require approval."
        )

    # 6. Build Comprehensive Evaluation Trace
    evaluation_trace = {
        "permission": {
            "effect": perm_effect,
            "result": "passed" if perm_allowed else "denied",
            "permission_id": str(permission_result.permission_id) if permission_result.permission_id else None,
            "reason": permission_result.reason,
        },
        "policy": {
            "effect": policy_result.decision.lower(),
            "policy_id": str(policy_id) if policy_id else None,
            "policy_version_id": str(policy_version_id) if policy_version_id else None,
            "result": "matched" if (policy_result.enforced_rules or policy_result.audit_rules) else "no_match",
            "enforced_matches": len(policy_result.enforced_rules),
            "audit_matches": len(policy_result.audit_rules),
        },
        "risk": {
            "score": risk_result.risk_score,
            "level": risk_result.risk_level,
            "result": "approval_required" if risk_requires_approval else "continue",
        },
        "sentinel": {
            "findings_count": len(security_findings) if security_findings else 0,
            "critical_count": len(critical_findings),
            "high_count": len(high_findings),
        },
        "behavior": {
            "anomalies_count": len(behavioral_anomalies) if behavioral_anomalies else 0,
            "critical_count": len(critical_anomalies),
            "high_count": len(high_anomalies),
        },
        "final": {
            "decision": final_decision.value,
            "source": enforcement_source,
        },
    }

    return (
        final_decision,
        final_reason,
        enforcement_source,
        policy_id,
        policy_version_id,
        factors,
        evaluation_trace,
    )
