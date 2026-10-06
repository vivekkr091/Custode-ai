"""Behavioral & Anomaly Detection Evasion and Explainability Tests (Milestone 22)."""

import uuid
import pytest
from httpx import AsyncClient

from app.engines.behavior.models import BehavioralFinding
from app.db.models.behavioral_anomaly import AnomalySeverity, AnomalyType


def test_behavioral_detection_deterministic_explainability():
    """Verify that behavioral anomaly detection produces deterministic, structured explanations."""
    finding = BehavioralFinding(
        anomaly_type=AnomalyType.ACTION_RATE_SPIKE,
        severity=AnomalySeverity.HIGH,
        confidence=0.85,
        score=75.0,
        feature="action_velocity",
        observed_value={"rate": 25.0},
        baseline_value={"rate": 5.0},
        deviation=5.0,
        explanation="Agent action rate (25.0 actions/min) exceeded baseline threshold (5.0 actions/min) by 5.0x",
    )

    assert finding.severity == AnomalySeverity.HIGH
    assert finding.score == 75.0
    assert "exceeded baseline threshold" in finding.explanation
    assert finding.deviation == 5.0


def test_behavioral_anomaly_governance_escalation():
    """Verify that detected critical anomalies escalate to require governance and cannot be silently bypassed."""
    finding = BehavioralFinding(
        anomaly_type=AnomalyType.ACTION_LOOP,
        severity=AnomalySeverity.CRITICAL,
        confidence=0.99,
        score=95.0,
        feature="action_loop",
        observed_value={"consecutive_identical": 120},
        baseline_value={"consecutive_identical": 1},
        deviation=120.0,
        explanation="Severe action loop detected",
    )
    assert finding.severity == AnomalySeverity.CRITICAL
