"""Centralized deterministic scoring and threshold classification for the Risk Engine."""

from app.db.models.risk_assessment import RiskLevel


# Centralized threshold boundaries
LOW_THRESHOLD = 24.0
MEDIUM_THRESHOLD = 49.0
HIGH_THRESHOLD = 74.0


def score_to_risk_level(score: float) -> str:
    """Map numeric score (0-100) to standard RiskLevel.

    Mapping:
      0–24   → LOW
      25–49  → MEDIUM
      50–74  → HIGH
      75–100 → CRITICAL
    """
    if score > HIGH_THRESHOLD:
        return RiskLevel.CRITICAL.value
    if score > MEDIUM_THRESHOLD:
        return RiskLevel.HIGH.value
    if score > LOW_THRESHOLD:
        return RiskLevel.MEDIUM.value
    return RiskLevel.LOW.value


def calculate_aggregate_score(factor_scores: list[float]) -> float:
    """Compute aggregate risk score capped deterministically at 100.0."""
    total = sum(factor_scores)
    return min(round(float(total), 2), 100.0)
