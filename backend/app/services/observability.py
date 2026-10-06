"""Service for Security Observability, Forensic Timeline Reconstruction, and Investigation Search."""

from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
import uuid

from sqlalchemy import desc, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.agent import Agent, AgentStatus
from app.db.models.approval import ApprovalRequest, ApprovalStatus
from app.db.models.audit_event import AuditEvent
from app.db.models.decision import Decision
from app.db.models.execution import Execution, ExecutionStatus
from app.db.models.llm_interaction import LLMInteraction
from app.db.models.policy import Policy, PolicyStatus
from app.db.models.risk_assessment import RiskAssessment
from app.db.models.runtime_action import ActionStatus, RuntimeAction
from app.db.models.security_finding import SecurityFinding
from app.db.models.security_scan import SecurityScan
from app.db.models.tool import Tool
from app.db.models.tool_operation import ToolOperation
from app.schemas.agent import AgentResponse
from app.schemas.approval import ApprovalResponse
from app.schemas.audit import AuditEventResponse
from app.schemas.decision import DecisionResponse
from app.schemas.execution import ExecutionResponse
from app.schemas.observability import (
    ActionForensicsResponse,
    SearchResultItem,
    SearchResponse,
    SecurityOverviewResponse,
    TimelineEventItem,
)
from app.schemas.risk import RiskAssessmentResponse
from app.schemas.runtime_action import RuntimeActionResponse
from app.schemas.security_finding import SecurityFindingResponse
from app.schemas.security_scan import SecurityScanResponse
from app.schemas.tool import ToolResponse
from app.schemas.tool_operation import ToolOperationResponse


async def get_action_forensics(
    session: AsyncSession,
    organization_id: uuid.UUID,
    action_id: uuid.UUID,
) -> Optional[ActionForensicsResponse]:
    """Compile an authoritative forensic dossier with verified timeline reconstruction."""
    # 1. Fetch Runtime Action
    action_q = select(RuntimeAction).where(
        RuntimeAction.organization_id == organization_id,
        RuntimeAction.id == action_id,
    )
    action_res = await session.execute(action_q)
    action = action_res.scalar_one_or_none()
    if action is None:
        return None

    # 2. Fetch Agent, Tool, Operation
    agent_res = await session.execute(
        select(Agent).where(Agent.id == action.agent_id, Agent.organization_id == organization_id)
    )
    agent = agent_res.scalar_one_or_none()

    tool_res = await session.execute(
        select(Tool).where(Tool.id == action.tool_id, Tool.organization_id == organization_id)
    )
    tool = tool_res.scalar_one_or_none()

    op_res = await session.execute(
        select(ToolOperation).where(ToolOperation.id == action.operation_id, ToolOperation.tool_id == action.tool_id)
    )
    operation = op_res.scalar_one_or_none()

    # 3. Fetch Risk Assessment
    risk_res = await session.execute(
        select(RiskAssessment).where(
            RiskAssessment.runtime_action_id == action_id,
            RiskAssessment.organization_id == organization_id,
        ).order_by(desc(RiskAssessment.created_at)).limit(1)
    )
    risk_assessment = risk_res.scalar_one_or_none()

    # 4. Fetch Decisions
    dec_res = await session.execute(
        select(Decision).where(
            Decision.runtime_action_id == action_id,
            Decision.organization_id == organization_id,
        ).order_by(Decision.evaluated_at.asc())
    )
    decisions = list(dec_res.scalars().all())

    # 5. Fetch Approvals
    appr_res = await session.execute(
        select(ApprovalRequest).where(
            ApprovalRequest.runtime_action_id == action_id,
            ApprovalRequest.organization_id == organization_id,
        ).order_by(ApprovalRequest.created_at.asc())
    )
    approvals = list(appr_res.scalars().all())

    # 6. Fetch Executions
    exec_res = await session.execute(
        select(Execution).where(
            Execution.runtime_action_id == action_id,
            Execution.organization_id == organization_id,
        ).order_by(Execution.created_at.asc())
    )
    executions = list(exec_res.scalars().all())

    # 7. Fetch Correlated Audit Events
    audit_q = (
        select(AuditEvent)
        .where(
            AuditEvent.organization_id == organization_id,
            or_(
                AuditEvent.resource_id == str(action_id),
                AuditEvent.target_id == str(action_id),
                AuditEvent.request_id == str(action.request_id),
            ),
        )
        .order_by(AuditEvent.created_at.asc())
    )
    audit_res = await session.execute(audit_q)
    audit_events = list(audit_res.scalars().all())

    # 8. Reconstruct Chronological Forensic Timeline
    timeline_items: List[TimelineEventItem] = []

    # Step 1: Action Registered
    timeline_items.append(
        TimelineEventItem(
            timestamp=action.created_at,
            event_type="ACTION_REGISTERED",
            stage="IDENTITY",
            title="Runtime Action Initiated",
            description=f"Agent '{agent.name if agent else action.agent_id}' initiated action '{action.action_type}' on tool '{tool.name if tool else action.tool_id}'",
            status="info",
            actor=agent.name if agent else str(action.agent_id),
            record_id=str(action.id),
            metadata={"environment": action.environment, "resource": action.resource},
        )
    )

    # Step 2: Risk Evaluation (if present)
    if risk_assessment:
        timeline_items.append(
            TimelineEventItem(
                timestamp=risk_assessment.created_at,
                event_type="RISK_EVALUATED",
                stage="RISK",
                title=f"Contextual Risk Score: {risk_assessment.risk_score} ({risk_assessment.risk_level.upper()})",
                description=f"Evaluated baseline and contextual factors yielding risk tier '{risk_assessment.risk_level}'",
                status="warning" if risk_assessment.risk_score >= 60 else "info",
                actor="risk_engine",
                record_id=str(risk_assessment.id),
                metadata={"risk_score": risk_assessment.risk_score, "factors": risk_assessment.factors},
            )
        )

    # Step 3: Decisions
    for dec in decisions:
        dec_status = "success" if dec.decision == "allow" else ("warning" if dec.decision == "require_approval" else "denied")
        timeline_items.append(
            TimelineEventItem(
                timestamp=dec.evaluated_at,
                event_type="DECISION_ARBITRATED",
                stage="DECISION",
                title=f"Arbitration Decision: {dec.decision.upper()}",
                description=dec.reason,
                status=dec_status,
                actor="decision_engine",
                record_id=str(dec.id),
                metadata={
                    "permission_effect": dec.permission_effect,
                    "policy_effect": dec.policy_effect,
                    "policy_id": str(dec.policy_id) if dec.policy_id else None,
                },
            )
        )

    # Step 4: Governance Approvals
    for appr in approvals:
        timeline_items.append(
            TimelineEventItem(
                timestamp=appr.created_at,
                event_type="APPROVAL_REQUESTED",
                stage="GOVERNANCE",
                title=f"Human Approval Requested ({appr.status.upper()})",
                description=appr.reason or "Governance review required prior to execution dispatch",
                status="warning" if appr.status == "pending" else "info",
                actor=str(appr.requested_by_agent_id),
                record_id=str(appr.id),
            )
        )
        if appr.reviewed_at:
            rev_status = "success" if appr.status == "approved" else "denied"
            timeline_items.append(
                TimelineEventItem(
                    timestamp=appr.reviewed_at,
                    event_type=f"APPROVAL_{appr.status.upper()}",
                    stage="GOVERNANCE",
                    title=f"Human Review: {appr.status.upper()}",
                    description=appr.reviewer_note or appr.rejection_reason or f"Reviewed by user '{appr.reviewer_user_id}'",
                    status=rev_status,
                    actor=str(appr.reviewer_user_id),
                    record_id=str(appr.id),
                )
            )

    # Step 5: Executions
    for exc in executions:
        timeline_items.append(
            TimelineEventItem(
                timestamp=exc.started_at,
                event_type="EXECUTION_STARTED",
                stage="EXECUTION",
                title="Controlled Execution Dispatched",
                description=f"Execution guard verified status. Dispatching operation '{operation.name if operation else exc.operation_id}'",
                status="info",
                actor="execution_dispatcher",
                record_id=str(exc.id),
            )
        )
        if exc.completed_at:
            exc_status = "success" if exc.status in ("succeeded", "success") else "denied"
            timeline_items.append(
                TimelineEventItem(
                    timestamp=exc.completed_at,
                    event_type=f"EXECUTION_{exc.status.upper()}",
                    stage="EXECUTION",
                    title=f"Execution Result: {exc.status.upper()}",
                    description=exc.error_message or "Execution completed cleanly through registered tool driver",
                    status=exc_status,
                    actor="execution_guard",
                    record_id=str(exc.id),
                    metadata={"error_code": exc.error_code},
                )
            )

    # 7.5 Fetch Security Scans and Findings
    scans_res = await session.execute(
        select(SecurityScan).where(
            SecurityScan.runtime_action_id == action_id,
            SecurityScan.organization_id == organization_id,
        ).order_by(SecurityScan.created_at.asc())
    )
    security_scans = list(scans_res.scalars().all())

    findings_res = await session.execute(
        select(SecurityFinding).where(
            SecurityFinding.runtime_action_id == action_id,
            SecurityFinding.organization_id == organization_id,
        ).order_by(SecurityFinding.created_at.asc())
    )
    security_findings = list(findings_res.scalars().all())

    for scan in security_scans:
        scan_status = "denied" if scan.critical_count > 0 else ("warning" if scan.high_count > 0 else "success")
        timeline_items.append(
            TimelineEventItem(
                timestamp=scan.created_at,
                event_type="SECURITY_SCAN_COMPLETED",
                stage="SECURITY_SCAN",
                title=f"Sentinel Scan: {scan.highest_severity} ({scan.findings_count} findings)",
                description=f"Executed {scan.scanner_count} scanners in {scan.execution_time_ms:.1f}ms. Findings: {scan.critical_count} critical, {scan.high_count} high, {scan.medium_count} med, {scan.low_count} low.",
                status=scan_status,
                actor="sentinel_adapter",
                record_id=str(scan.id),
                metadata={"scanners_run": scan.scanners_run, "highest_severity": scan.highest_severity},
            )
        )

    # Sort strictly by timestamp
    timeline_items.sort(key=lambda x: x.timestamp)

    return ActionForensicsResponse(
        action=RuntimeActionResponse.model_validate(action),
        agent=AgentResponse.model_validate(agent) if agent else None,
        tool=ToolResponse.model_validate(tool) if tool else None,
        operation=ToolOperationResponse.model_validate(operation) if operation else None,
        risk_assessment=RiskAssessmentResponse.model_validate(risk_assessment) if risk_assessment else None,
        decisions=[DecisionResponse.model_validate(d) for d in decisions],
        approvals=[ApprovalResponse.model_validate(a) for a in approvals],
        executions=[ExecutionResponse.model_validate(e) for e in executions],
        audit_events=[AuditEventResponse.model_validate(ae) for ae in audit_events],
        timeline=timeline_items,
        security_findings=[SecurityFindingResponse.model_validate(f) for f in security_findings],
        security_scans=[SecurityScanResponse.model_validate(s) for s in security_scans],
    )


async def get_security_overview(
    session: AsyncSession,
    organization_id: uuid.UUID,
) -> SecurityOverviewResponse:
    """Compute real-time aggregated security metrics strictly from persisted records."""
    # 1. Agent metrics
    active_agents = await session.scalar(
        select(func.count(Agent.id)).where(
            Agent.organization_id == organization_id,
            Agent.status == AgentStatus.active.value,
        )
    ) or 0

    suspended_agents = await session.scalar(
        select(func.count(Agent.id)).where(
            Agent.organization_id == organization_id,
            Agent.status == AgentStatus.suspended.value,
        )
    ) or 0

    # 2. Policy metrics
    active_policies = await session.scalar(
        select(func.count(Policy.id)).where(
            Policy.organization_id == organization_id,
            Policy.status == PolicyStatus.active.value,
        )
    ) or 0

    # 3. Governance metrics
    pending_approvals = await session.scalar(
        select(func.count(ApprovalRequest.id)).where(
            ApprovalRequest.organization_id == organization_id,
            ApprovalRequest.status == ApprovalStatus.pending.value,
        )
    ) or 0

    # 4. Action & Risk metrics
    high_risk_actions = await session.scalar(
        select(func.count(RiskAssessment.id)).where(
            RiskAssessment.organization_id == organization_id,
            RiskAssessment.risk_level == "high",
        )
    ) or 0

    critical_risk_actions = await session.scalar(
        select(func.count(RiskAssessment.id)).where(
            RiskAssessment.organization_id == organization_id,
            RiskAssessment.risk_level == "critical",
        )
    ) or 0

    blocked_actions = await session.scalar(
        select(func.count(Decision.id)).where(
            Decision.organization_id == organization_id,
            Decision.decision.in_(["block", "deny"]),
        )
    ) or 0

    failed_executions = await session.scalar(
        select(func.count(Execution.id)).where(
            Execution.organization_id == organization_id,
            Execution.status == ExecutionStatus.failed.value,
        )
    ) or 0

    tools_count = await session.scalar(
        select(func.count(Tool.id)).where(Tool.organization_id == organization_id)
    ) or 0

    total_executions = await session.scalar(
        select(func.count(Execution.id)).where(Execution.organization_id == organization_id)
    ) or 0

    # 5. Risk Distribution
    risk_dist_q = (
        select(RiskAssessment.risk_level, func.count(RiskAssessment.id))
        .where(RiskAssessment.organization_id == organization_id)
        .group_by(RiskAssessment.risk_level)
    )
    risk_dist_res = await session.execute(risk_dist_q)
    risk_distribution = {row[0]: row[1] for row in risk_dist_res.all()}

    # 6. Decision Distribution
    dec_dist_q = (
        select(Decision.decision, func.count(Decision.id))
        .where(Decision.organization_id == organization_id)
        .group_by(Decision.decision)
    )
    dec_dist_res = await session.execute(dec_dist_q)
    decision_distribution = {row[0]: row[1] for row in dec_dist_res.all()}

    # 7. Recent Audit Events
    recent_events_q = (
        select(AuditEvent)
        .where(AuditEvent.organization_id == organization_id)
        .order_by(desc(AuditEvent.created_at))
        .limit(10)
    )
    recent_events_res = await session.execute(recent_events_q)
    recent_events = [
        AuditEventResponse.model_validate(e)
        for e in recent_events_res.scalars().all()
    ]

    # 8. Sentinel Security Scanner metrics
    sentinel_findings_count = await session.scalar(
        select(func.count(SecurityFinding.id)).where(SecurityFinding.organization_id == organization_id)
    ) or 0

    critical_findings_count = await session.scalar(
        select(func.count(SecurityFinding.id)).where(
            SecurityFinding.organization_id == organization_id,
            SecurityFinding.severity == "CRITICAL",
        )
    ) or 0

    high_findings_count = await session.scalar(
        select(func.count(SecurityFinding.id)).where(
            SecurityFinding.organization_id == organization_id,
            SecurityFinding.severity == "HIGH",
        )
    ) or 0

    findings_cat_q = (
        select(SecurityFinding.category, func.count(SecurityFinding.id))
        .where(SecurityFinding.organization_id == organization_id)
        .group_by(SecurityFinding.category)
    )
    findings_cat_res = await session.execute(findings_cat_q)
    findings_distribution = {row[0]: row[1] for row in findings_cat_res.all()}

    return SecurityOverviewResponse(
        active_agents=active_agents,
        suspended_agents=suspended_agents,
        active_policies=active_policies,
        pending_approvals=pending_approvals,
        high_risk_actions=high_risk_actions,
        critical_risk_actions=critical_risk_actions,
        blocked_actions=blocked_actions,
        failed_executions=failed_executions,
        risk_distribution=risk_distribution,
        decision_distribution=decision_distribution,
        recent_events=recent_events,
        sentinel_findings_count=sentinel_findings_count,
        critical_findings_count=critical_findings_count,
        high_findings_count=high_findings_count,
        findings_distribution=findings_distribution,
        # Backward and frontend compatibility aliases
        agents_count=active_agents + suspended_agents,
        tools_count=tools_count,
        active_policies_count=active_policies,
        pending_approvals_count=pending_approvals,
        blocked_actions_count=blocked_actions,
        allowed_actions_count=decision_distribution.get("allow", 0),
        high_risk_actions_count=high_risk_actions + critical_risk_actions,
        executions_count=total_executions,
        recent_audit_events_count=len(recent_events),
    )


async def search_security_investigation(
    session: AsyncSession,
    organization_id: uuid.UUID,
    query_str: str,
    limit: int = 30,
) -> SearchResponse:
    """Execute global investigation search across all security entities strictly within the organization."""
    term = query_str.strip()
    if not term:
        return SearchResponse(query=query_str, results=[], total=0)

    results: List[SearchResultItem] = []

    # 1. Search Runtime Actions
    action_cond = [
        RuntimeAction.action_type.ilike(f"%{term}%"),
        RuntimeAction.resource.ilike(f"%{term}%"),
    ]
    try:
        uuid_val = uuid.UUID(term)
        action_cond.append(RuntimeAction.id == uuid_val)
        action_cond.append(RuntimeAction.request_id == uuid_val)
    except ValueError:
        pass

    action_q = (
        select(RuntimeAction)
        .where(RuntimeAction.organization_id == organization_id, or_(*action_cond))
        .order_by(desc(RuntimeAction.created_at))
        .limit(10)
    )
    actions = (await session.execute(action_q)).scalars().all()
    for a in actions:
        results.append(
            SearchResultItem(
                category="runtime_action",
                id=str(a.id),
                title=f"Action: {a.action_type}",
                subtitle=f"Resource: {a.resource or 'N/A'} • Status: {a.status}",
                created_at=a.created_at,
                status=a.status,
                metadata={"request_id": str(a.request_id)},
            )
        )

    # 2. Search Decisions
    dec_cond = [Decision.reason.ilike(f"%{term}%")]
    try:
        uuid_val = uuid.UUID(term)
        dec_cond.append(Decision.id == uuid_val)
        dec_cond.append(Decision.runtime_action_id == uuid_val)
    except ValueError:
        pass

    dec_q = (
        select(Decision)
        .where(Decision.organization_id == organization_id, or_(*dec_cond))
        .order_by(desc(Decision.evaluated_at))
        .limit(10)
    )
    decs = (await session.execute(dec_q)).scalars().all()
    for d in decs:
        results.append(
            SearchResultItem(
                category="decision",
                id=str(d.id),
                title=f"Decision: {d.decision.upper()}",
                subtitle=f"Risk: {d.risk_level.upper()} ({d.risk_score}) • {d.reason[:60]}...",
                created_at=d.evaluated_at,
                status=d.decision,
            )
        )

    # 3. Search Approvals
    appr_cond = [ApprovalRequest.reason.ilike(f"%{term}%")]
    try:
        uuid_val = uuid.UUID(term)
        appr_cond.append(ApprovalRequest.id == uuid_val)
        appr_cond.append(ApprovalRequest.runtime_action_id == uuid_val)
    except ValueError:
        pass

    appr_q = (
        select(ApprovalRequest)
        .where(ApprovalRequest.organization_id == organization_id, or_(*appr_cond))
        .order_by(desc(ApprovalRequest.created_at))
        .limit(10)
    )
    apprs = (await session.execute(appr_q)).scalars().all()
    for ap in apprs:
        results.append(
            SearchResultItem(
                category="approval",
                id=str(ap.id),
                title=f"Approval: {ap.status.upper()}",
                subtitle=ap.reason,
                created_at=ap.created_at,
                status=ap.status,
            )
        )

    # 4. Search Audit Events
    audit_cond = [
        AuditEvent.action.ilike(f"%{term}%"),
        AuditEvent.event_type.ilike(f"%{term}%"),
        AuditEvent.request_id.ilike(f"%{term}%"),
        AuditEvent.actor_id.ilike(f"%{term}%"),
    ]
    try:
        uuid_val = uuid.UUID(term)
        audit_cond.append(AuditEvent.id == uuid_val)
    except ValueError:
        pass

    audit_q = (
        select(AuditEvent)
        .where(AuditEvent.organization_id == organization_id, or_(*audit_cond))
        .order_by(desc(AuditEvent.created_at))
        .limit(10)
    )
    audit_evs = (await session.execute(audit_q)).scalars().all()
    for ae in audit_evs:
        results.append(
            SearchResultItem(
                category="audit_event",
                id=str(ae.id),
                title=f"Audit: {ae.event_type}",
                subtitle=f"Actor: {ae.actor_id or 'System'} • Outcome: {ae.outcome.upper()}",
                created_at=ae.created_at,
                status=ae.outcome,
                metadata={"request_id": ae.request_id},
            )
        )

    # 5. Search Security Findings
    finding_cond = [
        SecurityFinding.title.ilike(f"%{term}%"),
        SecurityFinding.category.ilike(f"%{term}%"),
        SecurityFinding.scanner.ilike(f"%{term}%"),
        SecurityFinding.description.ilike(f"%{term}%"),
    ]
    try:
        uuid_val = uuid.UUID(term)
        finding_cond.append(SecurityFinding.id == uuid_val)
        finding_cond.append(SecurityFinding.runtime_action_id == uuid_val)
    except ValueError:
        pass

    finding_q = (
        select(SecurityFinding)
        .where(SecurityFinding.organization_id == organization_id, or_(*finding_cond))
        .order_by(desc(SecurityFinding.created_at))
        .limit(10)
    )
    findings_list = (await session.execute(finding_q)).scalars().all()
    for f in findings_list:
        results.append(
            SearchResultItem(
                category="security_finding",
                id=str(f.id),
                title=f"Finding: {f.title}",
                subtitle=f"Severity: {f.severity} • {f.category} ({f.scanner})",
                created_at=f.created_at,
                status=f.severity,
                metadata={"action_id": str(f.runtime_action_id)},
            )
        )

    # 6. Search LLM Interactions
    llm_cond = [
        LLMInteraction.provider.ilike(f"%{term}%"),
        LLMInteraction.model.ilike(f"%{term}%"),
        LLMInteraction.status.ilike(f"%{term}%"),
    ]
    try:
        uuid_val = uuid.UUID(term)
        llm_cond.append(LLMInteraction.id == uuid_val)
        llm_cond.append(LLMInteraction.request_id == uuid_val)
    except ValueError:
        pass

    llm_q = (
        select(LLMInteraction)
        .where(LLMInteraction.organization_id == organization_id, or_(*llm_cond))
        .order_by(desc(LLMInteraction.created_at))
        .limit(10)
    )
    llm_list = (await session.execute(llm_q)).scalars().all()
    for item in llm_list:
        results.append(
            SearchResultItem(
                category="llm_interaction",
                id=str(item.id),
                title=f"LLM: {item.provider}/{item.model}",
                subtitle=f"Status: {item.status.upper()} • Decision: {item.decision.upper()} • Tokens: {item.total_tokens}",
                created_at=item.created_at,
                status=item.status,
                metadata={"request_id": str(item.request_id), "provider": item.provider, "model": item.model},
            )
        )

    trimmed = results[:limit]
    return SearchResponse(
        query=query_str,
        results=trimmed,
        items=trimmed,
        total=len(results),
    )
