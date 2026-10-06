"""Contextual risk factor definitions and evaluation logic."""

from typing import Any, List, Optional, Tuple
from app.db.models.tool_operation import OperationRiskLevel, OperationType
from app.schemas.risk import RiskFactor

# Baseline score mapping for ToolOperation.risk_level
BASELINE_RISK_SCORES = {
    OperationRiskLevel.low.value: 10.0,
    OperationRiskLevel.medium.value: 30.0,
    OperationRiskLevel.high.value: 55.0,
    OperationRiskLevel.critical.value: 80.0,
}

# Environment score contribution
ENVIRONMENT_SCORES = {
    "dev": 0.0,
    "staging": 5.0,
    "prod": 15.0,
}

# Operation type score contribution
OPERATION_TYPE_SCORES = {
    OperationType.read.value: 0.0,
    OperationType.write.value: 5.0,
    OperationType.delete.value: 15.0,
    OperationType.execute.value: 15.0,
    OperationType.transfer.value: 20.0,
    OperationType.admin.value: 25.0,
    OperationType.custom.value: 5.0,
}

# Resource type sensitivity score contribution
RESOURCE_TYPE_SCORES = {
    "public": 0.0,
    "internal": 5.0,
    "sensitive": 15.0,
    "financial": 20.0,
    "credential": 25.0,
    "identity": 15.0,
    "database": 10.0,
    "filesystem": 10.0,
    "cloud": 10.0,
    "unknown": 5.0,
}

SENSITIVE_RESOURCE_TYPES = {"financial", "credential", "identity", "sensitive"}
DESTRUCTIVE_OPERATIONS = {
    OperationType.delete.value,
    OperationType.execute.value,
    OperationType.admin.value,
}


def evaluate_factors(
    baseline_risk_level: str,
    operation_type: str,
    environment: str,
    resource_type: Optional[str] = None,
    resource: Optional[str] = None,
    amount: Optional[float] = None,
    security_findings: Optional[List[Any]] = None,
    behavioral_anomalies: Optional[List[Any]] = None,
) -> Tuple[List[RiskFactor], List[str]]:
    """Compute all contributing factors and triggered rule identifiers deterministically."""
    factors: List[RiskFactor] = []
    triggered_rules: List[str] = []

    # 1. Baseline Risk from ToolOperation
    norm_baseline = baseline_risk_level.lower() if baseline_risk_level else OperationRiskLevel.low.value
    baseline_score = BASELINE_RISK_SCORES.get(norm_baseline, 10.0)
    factors.append(
        RiskFactor(
            factor="baseline_operation_risk",
            category="operation",
            score=baseline_score,
            severity=norm_baseline,
            reason=f"Operation baseline risk level declared as '{norm_baseline}'",
            metadata={"baseline_risk_level": norm_baseline},
        )
    )
    triggered_rules.append(f"baseline:{norm_baseline}")

    # 2. Environment Context
    norm_env = environment.lower() if environment else "dev"
    env_score = ENVIRONMENT_SCORES.get(norm_env, 0.0)
    if env_score > 0.0 or norm_env == "dev":
        severity = "high" if norm_env == "prod" else ("medium" if norm_env == "staging" else "low")
        factors.append(
            RiskFactor(
                factor="environment_tier",
                category="environment",
                score=env_score,
                severity=severity,
                reason=f"Action execution targets '{norm_env}' environment tier",
                metadata={"environment": norm_env},
            )
        )
        triggered_rules.append(f"env:{norm_env}")

    # 3. Operation Type Context
    norm_op = operation_type.lower() if operation_type else OperationType.read.value
    op_score = OPERATION_TYPE_SCORES.get(norm_op, 5.0)
    if op_score > 0.0 or norm_op == OperationType.read.value:
        op_severity = (
            "critical" if norm_op == OperationType.admin.value
            else "high" if norm_op in (OperationType.transfer.value, OperationType.delete.value, OperationType.execute.value)
            else "medium" if norm_op == OperationType.write.value
            else "low"
        )
        factors.append(
            RiskFactor(
                factor="operation_type",
                category="operation",
                score=op_score,
                severity=op_severity,
                reason=f"Operation action type is '{norm_op}'",
                metadata={"operation_type": norm_op},
            )
        )
        triggered_rules.append(f"op:{norm_op}")

    # 4. Resource Sensitivity Context
    norm_res_type = resource_type.lower() if resource_type else None
    if norm_res_type:
        res_score = RESOURCE_TYPE_SCORES.get(norm_res_type, 5.0)
        res_severity = (
            "critical" if norm_res_type == "credential"
            else "high" if norm_res_type in ("financial", "sensitive", "identity")
            else "medium" if norm_res_type in ("database", "filesystem", "cloud")
            else "low"
        )
        factors.append(
            RiskFactor(
                factor="resource_sensitivity",
                category="resource",
                score=res_score,
                severity=res_severity,
                reason=f"Resource type classified as '{norm_res_type}'",
                metadata={"resource_type": norm_res_type, "resource": resource},
            )
        )
        triggered_rules.append(f"resource:{norm_res_type}")

    # 5. Monetary Amount Context
    if amount is not None and amount > 0.0:
        amt_score = 0.0
        bracket = "0-10k"
        amt_severity = "low"

        if amount > 500000.0:
            amt_score = 40.0
            bracket = ">500k"
            amt_severity = "critical"
        elif amount > 100000.0:
            amt_score = 30.0
            bracket = "100k-500k"
            amt_severity = "high"
        elif amount > 50000.0:
            amt_score = 20.0
            bracket = "50k-100k"
            amt_severity = "medium"
        elif amount > 10000.0:
            amt_score = 10.0
            bracket = "10k-50k"
            amt_severity = "medium"

        if amt_score > 0.0 or amount <= 10000.0:
            factors.append(
                RiskFactor(
                    factor="monetary_amount",
                    category="amount",
                    score=amt_score,
                    severity=amt_severity,
                    reason=f"Transaction/action amount {amount:.2f} falls in '{bracket}' tier",
                    metadata={"amount": amount, "bracket": bracket},
                )
            )
            triggered_rules.append(f"amount:{bracket}")

    # 6. Combination Rule: Production Destructive / Privileged Operations
    if norm_env == "prod" and norm_op in DESTRUCTIVE_OPERATIONS:
        factors.append(
            RiskFactor(
                factor="production_destructive_operation",
                category="combination",
                score=15.0,
                severity="critical",
                reason=f"Destructive or privileged operation '{norm_op}' executed in production environment",
                metadata={"environment": norm_env, "operation_type": norm_op},
            )
        )
        triggered_rules.append("combo:production_destructive")

    # 7. Combination Rule: Sensitive Transfer
    if norm_op == OperationType.transfer.value and norm_res_type in SENSITIVE_RESOURCE_TYPES:
        factors.append(
            RiskFactor(
                factor="sensitive_transfer",
                category="combination",
                score=15.0,
                severity="critical",
                reason=f"Transfer operation initiated on highly sensitive resource '{norm_res_type}'",
                metadata={"operation_type": norm_op, "resource_type": norm_res_type},
            )
        )
        triggered_rules.append("combo:sensitive_transfer")

    # 8. Sentinel Security Scanner Findings
    if security_findings:
        for finding in security_findings:
            sev = getattr(finding, "severity", "LOW")
            if hasattr(sev, "value"):
                sev = sev.value
            sev_str = str(sev).upper()

            cat = getattr(finding, "category", "OTHER")
            if hasattr(cat, "value"):
                cat = cat.value
            cat_str = str(cat).upper()

            title = getattr(finding, "title", "Security finding detected")
            scanner = getattr(finding, "scanner", "sentinel")

            finding_score = 5.0
            if sev_str == "CRITICAL":
                finding_score = 50.0
            elif sev_str == "HIGH":
                finding_score = 30.0
            elif sev_str == "MEDIUM":
                finding_score = 15.0
            elif sev_str == "LOW":
                finding_score = 5.0

            factors.append(
                RiskFactor(
                    factor=f"sentinel_{sev_str.lower()}_{cat_str.lower()}",
                    category="security_scanner",
                    score=finding_score,
                    severity=sev_str.lower(),
                    reason=f"Sentinel finding: {title} ({cat_str}) [{sev_str}]",
                    metadata={
                        "scanner": scanner,
                        "category": cat_str,
                        "severity": sev_str,
                        "title": title,
                    },
                )
            )
            triggered_rules.append(f"sentinel:{cat_str.lower()}:{sev_str.lower()}")

    # 9. Behavioral Anomaly Engine Findings
    if behavioral_anomalies:
        for anomaly in behavioral_anomalies:
            sev = getattr(anomaly, "severity", "LOW")
            if hasattr(sev, "value"):
                sev = sev.value
            sev_str = str(sev).upper()

            anom_type = getattr(anomaly, "anomaly_type", "ANOMALY")
            if hasattr(anom_type, "value"):
                anom_type = anom_type.value
            type_str = str(anom_type).upper()

            expl = getattr(anomaly, "explanation", "Behavioral deviation detected")
            conf = getattr(anomaly, "confidence", 1.0)
            score_attr = getattr(anomaly, "score", 0.0)

            anom_score = 5.0
            if sev_str == "CRITICAL":
                anom_score = 35.0
            elif sev_str == "HIGH":
                anom_score = 25.0
            elif sev_str == "MEDIUM":
                anom_score = 15.0
            elif sev_str == "LOW":
                anom_score = 5.0

            factors.append(
                RiskFactor(
                    factor=f"behavior_{sev_str.lower()}_{type_str.lower()}",
                    category="behavioral_anomaly",
                    score=anom_score,
                    severity=sev_str.lower(),
                    reason=f"Behavioral anomaly: {expl} [{sev_str}]",
                    metadata={
                        "anomaly_type": type_str,
                        "severity": sev_str,
                        "confidence": conf,
                        "behavioral_score": score_attr,
                    },
                )
            )
            triggered_rules.append(f"behavior:{type_str.lower()}:{sev_str.lower()}")

    return factors, triggered_rules

