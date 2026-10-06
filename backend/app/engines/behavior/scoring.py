"""Deterministic scoring, severity derivation, and confidence computation for behavioral anomalies."""

from typing import List, Optional
from app.db.models.agent_behavior_baseline import BaselineState
from app.db.models.behavioral_anomaly import AnomalySeverity, AnomalyType


BASE_SEVERITY_SCORES = {
    AnomalySeverity.LOW: 15.0,
    AnomalySeverity.MEDIUM: 35.0,
    AnomalySeverity.HIGH: 60.0,
    AnomalySeverity.CRITICAL: 85.0,
}

CONFIDENCE_BY_STATE = {
    BaselineState.COLD_START: 0.35,
    BaselineState.LEARNING: 0.65,
    BaselineState.ESTABLISHED: 0.90,
}


def score_to_severity(score: float) -> AnomalySeverity:
    """Map numeric behavioral score to discrete anomaly severity."""
    if score >= 75.0:
        return AnomalySeverity.CRITICAL
    if score >= 50.0:
        return AnomalySeverity.HIGH
    if score >= 25.0:
        return AnomalySeverity.MEDIUM
    return AnomalySeverity.LOW


def compute_anomaly_confidence(
    baseline_state: BaselineState,
    observation_count: int,
    corroborating_signals: int = 1,
    deviation_magnitude: float = 1.0,
) -> float:
    """Derive deterministic confidence (0.0 to 1.0) from sample size and corroborating evidence."""
    base_conf = CONFIDENCE_BY_STATE.get(baseline_state, 0.5)

    # Observation bonus: up to +0.10 for established sample size
    obs_bonus = min(observation_count / 100.0, 0.10)

    # Corroborating signals bonus: +0.05 per extra signal
    signal_bonus = min((corroborating_signals - 1) * 0.05, 0.15) if corroborating_signals > 1 else 0.0

    # Deviation scaling: high deviation increases confidence slightly
    dev_bonus = min(max(deviation_magnitude - 1.0, 0.0) * 0.02, 0.10)

    total_conf = base_conf + obs_bonus + signal_bonus + dev_bonus
    return round(min(max(total_conf, 0.1), 1.0), 2)


def calculate_aggregate_behavior_score(anomaly_scores: List[float]) -> float:
    """Aggregate multiple anomaly scores deterministically with diminishing returns, capped at 100.0."""
    if not anomaly_scores:
        return 0.0

    sorted_scores = sorted(anomaly_scores, reverse=True)
    total = sorted_scores[0]
    weights = [0.5, 0.3, 0.2, 0.1]

    for idx, s in enumerate(sorted_scores[1:]):
        w = weights[idx] if idx < len(weights) else 0.05
        total += s * w

    return round(min(total, 100.0), 2)
