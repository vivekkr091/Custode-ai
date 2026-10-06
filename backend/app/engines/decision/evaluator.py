from typing import Any, List, Optional
from app.engines.decision.precedence import resolve_decision_precedence
from app.engines.permission.evaluator import PermissionEvaluationResult
from app.engines.policy.evaluator import PolicyEvaluationResult
from app.engines.risk.evaluator import RiskEvaluationResult
from app.schemas.decision import DecisionEvaluationResult


class DecisionEngine:
    """Core deterministic, explainable Decision Engine."""

    ENGINE_VERSION = "1.0.0"

    @classmethod
    def evaluate(
        cls,
        permission_result: PermissionEvaluationResult,
        policy_result: PolicyEvaluationResult,
        risk_result: RiskEvaluationResult,
        security_findings: Optional[list] = None,
        behavioral_anomalies: Optional[list] = None,
    ) -> DecisionEvaluationResult:
        """Arbitrate authorization decision from Permission, Policy, Risk, and Behavioral results."""
        (
            decision,
            reason,
            enforcement_source,
            policy_id,
            policy_version_id,
            factors,
            evaluation_trace,
        ) = resolve_decision_precedence(
            permission_result=permission_result,
            policy_result=policy_result,
            risk_result=risk_result,
            security_findings=security_findings,
            behavioral_anomalies=behavioral_anomalies,
        )

        return DecisionEvaluationResult(
            decision=decision,
            reason=reason,
            risk_level=risk_result.risk_level,
            risk_score=risk_result.risk_score,
            permission_effect=permission_result.effect,
            policy_effect=policy_result.decision.lower(),
            policy_id=policy_id,
            policy_version_id=policy_version_id,
            factors=factors,
            evaluation_trace=evaluation_trace,
            engine_version=cls.ENGINE_VERSION,
        )
