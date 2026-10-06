"""CUSTODE Behavioral & Anomaly Detection Engine.

Provides deterministic, explainable statistical and rule-based behavioral anomaly detection
for AI agent runtime actions.
"""

from app.db.models.agent_behavior_baseline import AgentBehaviorBaseline, BaselineState
from app.db.models.behavioral_anomaly import (
    AnomalySeverity,
    AnomalyStatus,
    AnomalyType,
    BehavioralAnomaly,
)
from app.engines.behavior.baseline import (
    calculate_baseline_state,
    update_baseline_statistics,
)
from app.engines.behavior.detector import BehavioralDetector
from app.engines.behavior.features import (
    ExtractedBehaviorFeatures,
    compute_action_fingerprint,
    extract_behavior_features,
    sanitize_payload_for_fingerprint,
)
from app.engines.behavior.models import (
    AgentBehaviorProfile,
    BehaviorEvaluationResult,
    BehaviorMetrics,
    BehavioralAnomalyListResponse,
    BehavioralAnomalyResponse,
    BehavioralFinding,
)
from app.engines.behavior.scoring import (
    calculate_aggregate_behavior_score,
    compute_anomaly_confidence,
    score_to_severity,
)
from app.engines.behavior.service import (
    BehavioralAnomalyNotFoundError,
    evaluate_runtime_action_behavior,
    get_agent_behavior_profile,
    get_anomaly,
    get_behavior_metrics,
    get_or_create_baseline,
    list_anomalies,
    resolve_anomaly,
    suppress_anomaly,
    update_baseline_after_action,
)

__all__ = [
    "BaselineState",
    "AnomalyType",
    "AnomalySeverity",
    "AnomalyStatus",
    "AgentBehaviorBaseline",
    "BehavioralAnomaly",
    "ExtractedBehaviorFeatures",
    "BehavioralFinding",
    "BehaviorEvaluationResult",
    "AgentBehaviorProfile",
    "BehaviorMetrics",
    "BehavioralAnomalyResponse",
    "BehavioralAnomalyListResponse",
    "BehavioralAnomalyNotFoundError",
    "calculate_baseline_state",
    "update_baseline_statistics",
    "compute_action_fingerprint",
    "sanitize_payload_for_fingerprint",
    "extract_behavior_features",
    "calculate_aggregate_behavior_score",
    "compute_anomaly_confidence",
    "score_to_severity",
    "BehavioralDetector",
    "get_or_create_baseline",
    "evaluate_runtime_action_behavior",
    "update_baseline_after_action",
    "get_agent_behavior_profile",
    "list_anomalies",
    "get_anomaly",
    "resolve_anomaly",
    "suppress_anomaly",
    "get_behavior_metrics",
]
