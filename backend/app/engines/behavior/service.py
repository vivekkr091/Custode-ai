"""Service layer orchestrating persistent baseline lifecycle, anomaly detection, and governance."""

from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional, Tuple
import uuid

from sqlalchemy import desc, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.audit.service import AuditEventType, AuditOutcome, record_security_event
from app.db.base import utc_now
from app.db.models.agent import Agent
from app.db.models.agent_behavior_baseline import AgentBehaviorBaseline, BaselineState
from app.db.models.behavioral_anomaly import (
    AnomalySeverity,
    AnomalyStatus,
    AnomalyType,
    BehavioralAnomaly,
)
from app.db.models.runtime_action import RuntimeAction
from app.db.models.tool import Tool
from app.db.models.tool_operation import ToolOperation
from app.engines.behavior.baseline import update_baseline_statistics
from app.engines.behavior.detector import BehavioralDetector
from app.engines.behavior.models import (
    AgentBehaviorProfile,
    BehaviorEvaluationResult,
    BehaviorMetrics,
    BehavioralFinding,
)


class BehavioralAnomalyNotFoundError(Exception):
    def __init__(self, org_id: uuid.UUID, anomaly_id: uuid.UUID):
        super().__init__(f"Behavioral anomaly '{anomaly_id}' not found in organization '{org_id}'")
        self.org_id = org_id
        self.anomaly_id = anomaly_id


async def get_or_create_baseline(
    session: AsyncSession,
    organization_id: uuid.UUID,
    agent_id: uuid.UUID,
    environment: str = "production",
) -> AgentBehaviorBaseline:
    """Retrieve existing behavioral baseline or initialize a COLD_START baseline."""
    norm_env = environment.lower()
    res = await session.execute(
        select(AgentBehaviorBaseline).where(
            AgentBehaviorBaseline.organization_id == organization_id,
            AgentBehaviorBaseline.agent_id == agent_id,
            AgentBehaviorBaseline.environment == norm_env,
        )
    )
    baseline = res.scalar_one_or_none()

    if baseline is None:
        baseline = AgentBehaviorBaseline(
            organization_id=organization_id,
            agent_id=agent_id,
            environment=norm_env,
            state=BaselineState.COLD_START.value,
            observation_window_seconds=86400,
            action_count=0,
            tool_counts={},
            operation_counts={},
            resource_counts={},
        )
        session.add(baseline)
        await session.flush()
        await session.refresh(baseline)

        await record_security_event(
            session=session,
            event_type=AuditEventType.BEHAVIOR_BASELINE_CREATED,
            action="CREATE_BASELINE",
            organization_id=organization_id,
            resource_type="BEHAVIOR_BASELINE",
            resource_id=baseline.id,
            outcome=AuditOutcome.SUCCESS,
            metadata={
                "agent_id": str(agent_id),
                "environment": norm_env,
                "state": baseline.state,
            },
        )

    return baseline


async def evaluate_runtime_action_behavior(
    session: AsyncSession,
    organization_id: uuid.UUID,
    action: RuntimeAction,
    agent: Optional[Agent] = None,
    tool: Optional[Tool] = None,
    operation: Optional[ToolOperation] = None,
) -> BehaviorEvaluationResult:
    """Evaluate a RuntimeAction for behavioral anomalies, persist findings, and return explainable evaluation."""
    env = action.environment or "production"
    baseline = await get_or_create_baseline(session, organization_id, action.agent_id, env)

    # Bounded query: recent actions for this agent within the last 15 minutes
    cutoff_time = (action.created_at or utc_now()) - timedelta(minutes=15)
    history_res = await session.execute(
        select(RuntimeAction)
        .where(
            RuntimeAction.organization_id == organization_id,
            RuntimeAction.agent_id == action.agent_id,
            RuntimeAction.environment == action.environment,
            RuntimeAction.created_at >= cutoff_time,
            RuntimeAction.id != action.id,
        )
        .order_by(desc(RuntimeAction.created_at))
        .limit(100)
    )
    recent_history = list(history_res.scalars().all())

    tool_name = tool.slug if tool else None
    op_name = operation.name if operation else None

    # Detect anomalies
    result = BehavioralDetector.evaluate(
        action=action,
        baseline=baseline,
        recent_history=recent_history,
        tool_name=tool_name,
        operation_name=op_name,
    )

    # Persist findings in DB and emit audit events
    for finding in result.anomalies:
        anomaly_record = BehavioralAnomaly(
            organization_id=organization_id,
            agent_id=action.agent_id,
            runtime_action_id=action.id,
            anomaly_type=finding.anomaly_type.value,
            severity=finding.severity.value,
            confidence=finding.confidence,
            score=finding.score,
            feature=finding.feature,
            baseline_value=finding.baseline_value,
            observed_value=finding.observed_value,
            deviation=finding.deviation,
            explanation=finding.explanation,
            evidence=finding.evidence,
            environment=env,
            status=AnomalyStatus.OPEN.value,
        )
        session.add(anomaly_record)
        await session.flush()
        await session.refresh(anomaly_record)
        finding.id = anomaly_record.id

        await record_security_event(
            session=session,
            event_type=AuditEventType.BEHAVIOR_ANOMALY_DETECTED,
            action="DETECT_ANOMALY",
            organization_id=organization_id,
            resource_type="BEHAVIORAL_ANOMALY",
            resource_id=anomaly_record.id,
            outcome=AuditOutcome.SUCCESS,
            metadata={
                "agent_id": str(action.agent_id),
                "runtime_action_id": str(action.id),
                "anomaly_type": finding.anomaly_type.value,
                "severity": finding.severity.value,
                "score": finding.score,
                "feature": finding.feature,
            },
        )

    return result


async def update_baseline_after_action(
    session: AsyncSession,
    organization_id: uuid.UUID,
    action: RuntimeAction,
    is_success: bool = True,
    is_blocked: bool = False,
    is_approval: bool = False,
    risk_score: float = 0.0,
    tool_name: Optional[str] = None,
    operation_name: Optional[str] = None,
) -> AgentBehaviorBaseline:
    """Update agent baseline counters and statistical distributions after action decision or execution."""
    baseline = await get_or_create_baseline(session, organization_id, action.agent_id, action.environment)
    updated = update_baseline_statistics(
        baseline=baseline,
        action=action,
        is_success=is_success,
        is_blocked=is_blocked,
        is_approval=is_approval,
        risk_score=risk_score,
        tool_name=tool_name,
        operation_name=operation_name,
    )
    session.add(updated)
    await session.flush()
    return updated


async def get_agent_behavior_profile(
    session: AsyncSession,
    organization_id: uuid.UUID,
    agent_id: uuid.UUID,
    environment: str = "production",
) -> AgentBehaviorProfile:
    """Retrieve an aggregated, human-readable behavioral profile for an agent."""
    baseline = await get_or_create_baseline(session, organization_id, agent_id, environment)

    # Top tools & operations sorted by count
    tools_sorted = sorted(
        (baseline.tool_counts or {}).items(), key=lambda x: x[1], reverse=True
    )
    typical_tools = [k for k, _ in tools_sorted[:5]]

    ops_sorted = sorted(
        (baseline.operation_counts or {}).items(), key=lambda x: x[1], reverse=True
    )
    typical_operations = [k for k, _ in ops_sorted[:5]]

    # Count recent anomalies in last 30 days
    anomalies_res = await session.execute(
        select(BehavioralAnomaly).where(
            BehavioralAnomaly.organization_id == organization_id,
            BehavioralAnomaly.agent_id == agent_id,
            BehavioralAnomaly.environment == environment,
        )
    )
    all_anomalies = list(anomalies_res.scalars().all())
    sev_counts: Dict[str, int] = {}
    for a in all_anomalies:
        sev_counts[a.severity] = sev_counts.get(a.severity, 0) + 1

    return AgentBehaviorProfile(
        agent_id=agent_id,
        environment=environment,
        state=BaselineState(baseline.state),
        action_count=baseline.action_count,
        observation_window_seconds=baseline.observation_window_seconds,
        typical_tools=typical_tools,
        typical_operations=typical_operations,
        average_actions_per_hour=baseline.average_actions_per_hour,
        peak_actions_per_hour=baseline.peak_actions_per_hour,
        average_risk_score=baseline.average_risk_score,
        operational_hours=f"{baseline.operational_hours_start:02d}:00 - {baseline.operational_hours_end:02d}:00 UTC",
        last_observed_at=baseline.last_observed_at,
        recent_anomalies_count=len(all_anomalies),
        anomaly_counts_by_severity=sev_counts,
    )


async def list_anomalies(
    session: AsyncSession,
    organization_id: uuid.UUID,
    agent_id: Optional[uuid.UUID] = None,
    status_filter: Optional[str] = None,
    severity_filter: Optional[str] = None,
    anomaly_type: Optional[str] = None,
    limit: int = 50,
    offset: int = 0,
) -> Tuple[List[BehavioralAnomaly], int]:
    """List behavioral anomalies strictly scoped to organization with optional filtering."""
    query = select(BehavioralAnomaly).where(BehavioralAnomaly.organization_id == organization_id)
    count_query = select(func.count()).select_from(BehavioralAnomaly).where(BehavioralAnomaly.organization_id == organization_id)

    if agent_id:
        query = query.where(BehavioralAnomaly.agent_id == agent_id)
        count_query = count_query.where(BehavioralAnomaly.agent_id == agent_id)

    if status_filter:
        query = query.where(BehavioralAnomaly.status == status_filter.upper())
        count_query = count_query.where(BehavioralAnomaly.status == status_filter.upper())

    if severity_filter:
        query = query.where(BehavioralAnomaly.severity == severity_filter.upper())
        count_query = count_query.where(BehavioralAnomaly.severity == severity_filter.upper())

    if anomaly_type:
        query = query.where(BehavioralAnomaly.anomaly_type == anomaly_type.upper())
        count_query = count_query.where(BehavioralAnomaly.anomaly_type == anomaly_type.upper())

    query = query.order_by(desc(BehavioralAnomaly.created_at)).limit(limit).offset(offset)

    total_res = await session.execute(count_query)
    total = total_res.scalar() or 0

    items_res = await session.execute(query)
    items = list(items_res.scalars().all())
    return items, total


async def get_anomaly(
    session: AsyncSession,
    organization_id: uuid.UUID,
    anomaly_id: uuid.UUID,
) -> Optional[BehavioralAnomaly]:
    """Retrieve an anomaly strictly scoped to an organization."""
    res = await session.execute(
        select(BehavioralAnomaly).where(
            BehavioralAnomaly.id == anomaly_id,
            BehavioralAnomaly.organization_id == organization_id,
        )
    )
    return res.scalar_one_or_none()


async def resolve_anomaly(
    session: AsyncSession,
    organization_id: uuid.UUID,
    anomaly_id: uuid.UUID,
    user_id: Optional[uuid.UUID] = None,
    note: Optional[str] = None,
) -> BehavioralAnomaly:
    """Transition an anomaly status to RESOLVED."""
    anomaly = await get_anomaly(session, organization_id, anomaly_id)
    if not anomaly:
        raise BehavioralAnomalyNotFoundError(organization_id, anomaly_id)

    anomaly.status = AnomalyStatus.RESOLVED.value
    anomaly.resolved_by = user_id
    anomaly.resolved_at = utc_now()
    anomaly.resolution_note = note
    session.add(anomaly)
    await session.flush()

    await record_security_event(
        session=session,
        event_type=AuditEventType.BEHAVIOR_ANOMALY_RESOLVED,
        action="RESOLVE_ANOMALY",
        organization_id=organization_id,
        resource_type="BEHAVIORAL_ANOMALY",
        resource_id=anomaly.id,
        outcome=AuditOutcome.SUCCESS,
        metadata={
            "anomaly_id": str(anomaly.id),
            "agent_id": str(anomaly.agent_id),
            "anomaly_type": anomaly.anomaly_type,
            "resolved_by": str(user_id) if user_id else None,
            "note": note,
        },
    )
    return anomaly


async def suppress_anomaly(
    session: AsyncSession,
    organization_id: uuid.UUID,
    anomaly_id: uuid.UUID,
    user_id: Optional[uuid.UUID] = None,
    note: Optional[str] = None,
) -> BehavioralAnomaly:
    """Transition an anomaly status to SUPPRESSED."""
    anomaly = await get_anomaly(session, organization_id, anomaly_id)
    if not anomaly:
        raise BehavioralAnomalyNotFoundError(organization_id, anomaly_id)

    anomaly.status = AnomalyStatus.SUPPRESSED.value
    anomaly.resolved_by = user_id
    anomaly.resolved_at = utc_now()
    anomaly.resolution_note = note
    session.add(anomaly)
    await session.flush()

    await record_security_event(
        session=session,
        event_type=AuditEventType.BEHAVIOR_ANOMALY_SUPPRESSED,
        action="SUPPRESS_ANOMALY",
        organization_id=organization_id,
        resource_type="BEHAVIORAL_ANOMALY",
        resource_id=anomaly.id,
        outcome=AuditOutcome.SUCCESS,
        metadata={
            "anomaly_id": str(anomaly.id),
            "agent_id": str(anomaly.agent_id),
            "anomaly_type": anomaly.anomaly_type,
            "suppressed_by": str(user_id) if user_id else None,
            "note": note,
        },
    )
    return anomaly


async def get_behavior_metrics(
    session: AsyncSession,
    organization_id: uuid.UUID,
) -> BehaviorMetrics:
    """Calculate real-time behavioral metrics across all agents in the organization."""
    # 1. Monitored Baselines & States
    baselines_res = await session.execute(
        select(AgentBehaviorBaseline).where(
            AgentBehaviorBaseline.organization_id == organization_id
        )
    )
    baselines = list(baselines_res.scalars().all())
    monitored_agents = len(set(b.agent_id for b in baselines))
    est_baselines = sum(1 for b in baselines if b.state == BaselineState.ESTABLISHED.value)
    learn_baselines = sum(1 for b in baselines if b.state == BaselineState.LEARNING.value)
    cold_agents = sum(1 for b in baselines if b.state == BaselineState.COLD_START.value)

    # 2. Anomalies Distribution
    anomalies_res = await session.execute(
        select(BehavioralAnomaly).where(
            BehavioralAnomaly.organization_id == organization_id
        )
    )
    anomalies = list(anomalies_res.scalars().all())
    total_anom = len(anomalies)
    open_anom = sum(1 for a in anomalies if a.status == AnomalyStatus.OPEN.value)
    crit_anom = sum(1 for a in anomalies if a.severity == AnomalySeverity.CRITICAL.value)
    high_anom = sum(1 for a in anomalies if a.severity == AnomalySeverity.HIGH.value)

    rate_spikes = sum(1 for a in anomalies if a.anomaly_type == AnomalyType.ACTION_RATE_SPIKE.value)
    fail_spikes = sum(1 for a in anomalies if a.anomaly_type in (AnomalyType.FAILURE_SPIKE.value, AnomalyType.BLOCK_SPIKE.value))
    off_hours = sum(1 for a in anomalies if a.anomaly_type == AnomalyType.OFF_HOURS_ACTIVITY.value)
    new_tools = sum(1 for a in anomalies if a.anomaly_type == AnomalyType.NEW_TOOL_USAGE.value)
    loops = sum(1 for a in anomalies if a.anomaly_type == AnomalyType.ACTION_LOOP.value)

    return BehaviorMetrics(
        monitored_agents=monitored_agents,
        established_baselines=est_baselines,
        learning_baselines=learn_baselines,
        cold_start_agents=cold_agents,
        total_anomalies=total_anom,
        open_anomalies=open_anom,
        critical_anomalies=crit_anom,
        high_anomalies=high_anom,
        action_rate_spikes=rate_spikes,
        failure_spikes=fail_spikes,
        off_hours_events=off_hours,
        new_tool_events=new_tools,
        action_loops=loops,
    )
