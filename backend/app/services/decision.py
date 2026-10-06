"""Service layer for Authorization Decision arbitration, persistence, and audit retrieval."""

from datetime import datetime, timezone
from typing import List, Optional, Tuple
import uuid
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.base import utc_now
from app.db.models.agent import Agent, AgentStatus
from app.db.models.decision import Decision
from app.db.models.organization import Organization, OrganizationStatus
from app.db.models.runtime_action import RuntimeAction
from app.db.models.tool import Tool, ToolStatus
from app.db.models.tool_operation import OperationStatus, ToolOperation
from app.engines.decision.evaluator import DecisionEngine
from app.engines.permission.evaluator import PermissionEngine, PermissionRequest
from app.engines.policy.evaluator import PolicyEngine
from app.engines.risk.evaluator import RiskEngine
from app.schemas.policy import ActionContext
from app.services.agent import OrganizationNotFoundError, OrganizationSuspendedError
from app.services.permission import InactiveResourceError, ResourceHierarchyError
from app.services.runtime_action import RuntimeActionNotFoundError
from app.services.tool_operation import OperationNotFoundError


class DecisionNotFoundError(Exception):
    """Raised when a Decision is not found within the organization context."""

    def __init__(self, org_id: uuid.UUID, decision_id: uuid.UUID):
        super().__init__(f"Decision '{decision_id}' not found in organization '{org_id}'")
        self.org_id = org_id
        self.decision_id = decision_id


async def decide_runtime_action(
    session: AsyncSession,
    organization_id: uuid.UUID,
    runtime_action_id: uuid.UUID,
) -> Decision:
    """Evaluate and persist an authoritative authorization decision for a RuntimeAction.

    Pipelines:
    1. Tenant validation
    2. Agent & Tool context validation
    3. Permission Engine evaluation (least-privilege check)
    4. Policy Engine evaluation (contextual rules check)
    5. Risk Engine assessment (contextual operational risk)
    6. Decision Engine arbitration (precedence: DENY > REQUIRE_APPROVAL > ALLOW)
    7. Decision persistence (immutable audit history)

    Strictly preserves historical records: each call creates a new Decision record.
    Does NOT mutate RuntimeAction lifecycle status or parameters.
    """
    # 1. Validate Organization
    org_res = await session.execute(
        select(Organization).where(Organization.id == organization_id)
    )
    org = org_res.scalar_one_or_none()
    if org is None:
        raise OrganizationNotFoundError(organization_id)
    if org.status != OrganizationStatus.active.value:
        raise OrganizationSuspendedError(organization_id)

    # 2. Validate RuntimeAction scoped to Organization
    action_res = await session.execute(
        select(RuntimeAction).where(
            RuntimeAction.id == runtime_action_id,
            RuntimeAction.organization_id == organization_id,
        )
    )
    action = action_res.scalar_one_or_none()
    if action is None:
        raise RuntimeActionNotFoundError(organization_id, runtime_action_id)

    # 3. Validate Agent in Organization
    agent_res = await session.execute(
        select(Agent).where(
            Agent.id == action.agent_id,
            Agent.organization_id == organization_id,
        )
    )
    agent = agent_res.scalar_one_or_none()
    if agent is None:
        raise ResourceHierarchyError(f"Agent '{action.agent_id}' not found in organization '{organization_id}'")
    if agent.status != AgentStatus.active.value:
        raise InactiveResourceError("agent", action.agent_id, agent.status)

    # 4. Validate Tool in Organization
    tool_res = await session.execute(
        select(Tool).where(
            Tool.id == action.tool_id,
            Tool.organization_id == organization_id,
        )
    )
    tool = tool_res.scalar_one_or_none()
    if tool is None:
        raise ResourceHierarchyError(f"Tool '{action.tool_id}' not found in organization '{organization_id}'")
    if tool.status != ToolStatus.active.value:
        raise InactiveResourceError("tool", action.tool_id, tool.status)

    # 5. Validate ToolOperation attached to Tool
    op_res = await session.execute(
        select(ToolOperation).where(
            ToolOperation.id == action.operation_id,
            ToolOperation.tool_id == action.tool_id,
        )
    )
    operation = op_res.scalar_one_or_none()
    if operation is None:
        raise OperationNotFoundError(action.tool_id, action.operation_id)
    if operation.status != OperationStatus.active.value:
        raise InactiveResourceError("operation", action.operation_id, operation.status)

    # 6. Evaluate Permission Engine
    action_to_perm_env = {
        "dev": "development",
        "staging": "staging",
        "prod": "production",
    }
    perm_env = action_to_perm_env.get(action.environment, action.environment)

    perm_req = PermissionRequest(
        organization_id=organization_id,
        agent_id=action.agent_id,
        tool_id=action.tool_id,
        operation_id=action.operation_id,
        environment=perm_env,
    )
    perm_result = await PermissionEngine.evaluate(session, perm_req)

    # 7. Evaluate Policy Engine
    time_hour = action.created_at.hour if action.created_at else datetime.now(timezone.utc).hour
    action_context = ActionContext(
        agent_id=action.agent_id,
        agent_environment=agent.environment,
        tool_id=action.tool_id,
        tool_type=tool.tool_type,
        operation_id=action.operation_id,
        operation_type=operation.operation_type,
        operation_risk_level=operation.risk_level,
        amount=action.amount,
        resource=action.resource,
        ip_address=action.ip_address,
        time_hour=time_hour,
        request_id=str(action.request_id),
    )

    # 7.2 Evaluate Behavioral & Anomaly Detection Engine
    from app.engines.behavior.service import (
        evaluate_runtime_action_behavior,
        update_baseline_after_action,
    )
    behavior_result = await evaluate_runtime_action_behavior(
        session=session,
        organization_id=organization_id,
        action=action,
        agent=agent,
        tool=tool,
        operation=operation,
    )
    behavioral_anomalies = behavior_result.anomalies

    # Enrich ActionContext with behavior fields for Policy Engine
    if behavioral_anomalies:
        dominant_anom = behavioral_anomalies[0]
        action_context.behavior_anomaly_type = dominant_anom.anomaly_type.value if hasattr(dominant_anom.anomaly_type, "value") else str(dominant_anom.anomaly_type)
        action_context.behavior_anomaly_severity = dominant_anom.severity.value if hasattr(dominant_anom.severity, "value") else str(dominant_anom.severity)
        action_context.behavior_feature = dominant_anom.feature
    action_context.behavior_anomaly_score = behavior_result.behavioral_score
    action_context.behavior_new_tool = bool(behavior_result.features.get("is_new_tool"))
    action_context.behavior_new_operation = bool(behavior_result.features.get("is_new_operation"))
    action_context.behavior_off_hours = bool(behavior_result.features.get("is_off_hours"))
    action_context.behavior_action_rate = behavior_result.features.get("action_rate_1m")

    policy_result = await PolicyEngine.evaluate(session, organization_id, action_context)

    # 7.5 Load or execute Sentinel Security Scan
    from app.services.sentinel_scan import list_findings_for_action, scan_runtime_action
    from app.sentinel.config import settings as sentinel_settings
    security_findings = await list_findings_for_action(session, organization_id, action.id)
    if not security_findings and sentinel_settings.enabled:
        try:
            _, security_findings = await scan_runtime_action(session, organization_id, action.id)
        except Exception:
            if sentinel_settings.fail_mode == "fail_closed":
                raise
            security_findings = []

    # 8. Evaluate Risk Engine (including Sentinel & Behavioral findings)
    risk_result = RiskEngine.evaluate(
        runtime_action=action,
        operation_baseline_risk_level=operation.risk_level,
        operation_type=operation.operation_type,
        security_findings=security_findings,
        behavioral_anomalies=behavioral_anomalies,
    )

    # 9. Arbitrate Final Authorization Decision via Decision Engine
    decision_eval = DecisionEngine.evaluate(
        permission_result=perm_result,
        policy_result=policy_result,
        risk_result=risk_result,
        security_findings=security_findings,
        behavioral_anomalies=behavioral_anomalies,
    )

    # 10. Persist Immutable Decision Audit Record
    decision_record = Decision(
        organization_id=organization_id,
        runtime_action_id=action.id,
        decision=decision_eval.decision.value if hasattr(decision_eval.decision, "value") else str(decision_eval.decision),
        reason=decision_eval.reason,
        risk_level=decision_eval.risk_level,
        risk_score=decision_eval.risk_score,
        permission_effect=decision_eval.permission_effect,
        policy_effect=decision_eval.policy_effect,
        policy_id=decision_eval.policy_id,
        policy_version_id=decision_eval.policy_version_id,
        factors=[f.model_dump() if hasattr(f, "model_dump") else f for f in decision_eval.factors],
        evaluation_trace=decision_eval.evaluation_trace,
        engine_version=decision_eval.engine_version,
        evaluated_at=utc_now(),
    )
    session.add(decision_record)
    await session.flush()
    await session.refresh(decision_record)

    # 10.5 Incrementally update agent behavioral baseline
    is_blocked = (decision_record.decision == "block")
    is_appr = (decision_record.decision == "require_approval")
    is_succ = (decision_record.decision == "allow")
    await update_baseline_after_action(
        session=session,
        organization_id=organization_id,
        action=action,
        is_success=is_succ,
        is_blocked=is_blocked,
        is_approval=is_appr,
        risk_score=decision_eval.risk_score,
        tool_name=tool.slug,
        operation_name=operation.name,
    )

    from app.audit.service import record_security_event, AuditEventType, AuditOutcome
    dec_val = decision_record.decision
    audit_outcome = AuditOutcome.SUCCESS if dec_val in ("allow", "require_approval") else AuditOutcome.DENIED
    await record_security_event(
        session=session,
        event_type=AuditEventType.DECISION_CREATED,
        action="EVALUATE_DECISION",
        organization_id=organization_id,
        resource_type="DECISION",
        resource_id=decision_record.id,
        outcome=audit_outcome,
        metadata={
            "runtime_action_id": str(action.id),
            "decision": dec_val,
            "risk_score": decision_eval.risk_score,
            "risk_level": decision_eval.risk_level,
            "reason": decision_eval.reason,
            "permission_effect": decision_eval.permission_effect,
            "policy_effect": decision_eval.policy_effect,
        },
        request_id=str(action.request_id),
    )

    return decision_record


async def get_decision(
    session: AsyncSession,
    organization_id: uuid.UUID,
    decision_id: uuid.UUID,
) -> Optional[Decision]:
    """Retrieve an authoritative Decision record scoped to an organization."""
    query = select(Decision).where(
        Decision.organization_id == organization_id,
        Decision.id == decision_id,
    )
    res = await session.execute(query)
    return res.scalar_one_or_none()


async def list_decisions_for_action(
    session: AsyncSession,
    organization_id: uuid.UUID,
    runtime_action_id: uuid.UUID,
) -> List[Decision]:
    """List historical decisions for a specific action in descending order."""
    action_res = await session.execute(
        select(RuntimeAction).where(
            RuntimeAction.id == runtime_action_id,
            RuntimeAction.organization_id == organization_id,
        )
    )
    if action_res.scalar_one_or_none() is None:
        raise RuntimeActionNotFoundError(organization_id, runtime_action_id)

    query = (
        select(Decision)
        .where(
            Decision.organization_id == organization_id,
            Decision.runtime_action_id == runtime_action_id,
        )
        .order_by(Decision.created_at.desc())
    )
    res = await session.execute(query)
    return list(res.scalars().all())


async def list_decisions(
    session: AsyncSession,
    organization_id: uuid.UUID,
    limit: int = 50,
    offset: int = 0,
) -> Tuple[List[Decision], int]:
    """List authorization decisions strictly scoped to an organization with total count."""
    count_query = (
        select(func.count(Decision.id))
        .where(Decision.organization_id == organization_id)
    )
    total_res = await session.execute(count_query)
    total = total_res.scalar() or 0

    query = (
        select(Decision)
        .where(Decision.organization_id == organization_id)
        .order_by(Decision.created_at.desc())
        .limit(limit)
        .offset(offset)
    )
    res = await session.execute(query)
    return list(res.scalars().all()), total
