"""Risk assessment evaluator executing deterministic contextual scoring and explanation synthesis."""

from typing import Optional
from app.db.models.runtime_action import RuntimeAction
from app.engines.risk.factors import evaluate_factors
from app.engines.risk.scorer import calculate_aggregate_score, score_to_risk_level
from app.schemas.risk import RiskEvaluationResult, RiskFactor


ENGINE_VERSION = "1.0.0"


def _generate_explanation(score: float, level: str, factors: list[RiskFactor]) -> str:
    """Synthesize explainable justification text derived directly from contributing factors."""
    elevating_factors = [f for f in factors if f.score > 0]
    if not elevating_factors:
        return f"Risk score {score:.1f} ({level}). Minimum baseline operational risk."

    factor_descriptions = []
    for f in elevating_factors:
        factor_descriptions.append(f"{f.reason} (+{f.score:.0f})")

    details = "; ".join(factor_descriptions)
    return f"Risk score {score:.1f} ({level}). Factors: {details}."


class RiskEngine:
    """Deterministic, rule-based contextual risk engine for AI agent runtime actions."""

    @classmethod
    def evaluate(
        cls,
        runtime_action: RuntimeAction,
        operation_baseline_risk_level: str,
        operation_type: str,
        security_findings: Optional[list] = None,
        behavioral_anomalies: Optional[list] = None,
    ) -> RiskEvaluationResult:
        """Evaluate an action against contextual risk rules.

        Returns a structured, explainable RiskEvaluationResult.
        """
        factors, triggered_rules = evaluate_factors(
            baseline_risk_level=operation_baseline_risk_level,
            operation_type=operation_type,
            environment=runtime_action.environment,
            resource_type=runtime_action.resource_type,
            resource=runtime_action.resource,
            amount=runtime_action.amount,
            security_findings=security_findings,
            behavioral_anomalies=behavioral_anomalies,
        )

        score = calculate_aggregate_score([f.score for f in factors])
        level = score_to_risk_level(score)
        explanation = _generate_explanation(score, level, factors)

        return RiskEvaluationResult(
            risk_score=score,
            risk_level=level,
            factors=factors,
            triggered_rules=triggered_rules,
            explanation=explanation,
            engine_version=ENGINE_VERSION,
        )
