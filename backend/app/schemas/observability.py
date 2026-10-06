"""Pydantic schemas for Security Observability, Forensic Timeline, and Search."""

from datetime import datetime
from typing import Any, Dict, List, Optional
import uuid

from pydantic import BaseModel, Field

from app.schemas.agent import AgentResponse
from app.schemas.approval import ApprovalResponse
from app.schemas.audit import AuditEventResponse
from app.schemas.decision import DecisionResponse
from app.schemas.execution import ExecutionResponse
from app.schemas.risk import RiskAssessmentResponse
from app.schemas.runtime_action import RuntimeActionResponse
from app.schemas.tool import ToolResponse
from app.schemas.tool_operation import ToolOperationResponse


from app.schemas.security_finding import SecurityFindingResponse
from app.schemas.security_scan import SecurityScanResponse


class TimelineEventItem(BaseModel):
    """Single chronological step in a forensic action timeline."""
    timestamp: datetime
    event_type: str
    stage: str  # IDENTITY, PERMISSION, POLICY, RISK, DECISION, GOVERNANCE, EXECUTION, AUDIT, SECURITY_SCAN
    title: str
    description: str
    status: str  # success, denied, warning, info, failure
    actor: Optional[str] = None
    record_id: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None


class ActionForensicsResponse(BaseModel):
    """Complete forensic investigation dossier for a RuntimeAction."""
    action: RuntimeActionResponse
    agent: Optional[AgentResponse] = None
    tool: Optional[ToolResponse] = None
    operation: Optional[ToolOperationResponse] = None
    risk_assessment: Optional[RiskAssessmentResponse] = None
    decisions: List[DecisionResponse] = Field(default_factory=list)
    approvals: List[ApprovalResponse] = Field(default_factory=list)
    executions: List[ExecutionResponse] = Field(default_factory=list)
    audit_events: List[AuditEventResponse] = Field(default_factory=list)
    timeline: List[TimelineEventItem] = Field(default_factory=list)
    security_findings: List[SecurityFindingResponse] = Field(default_factory=list)
    security_scans: List[SecurityScanResponse] = Field(default_factory=list)


class SecurityOverviewResponse(BaseModel):
    """Authoritative aggregated security metrics for the organization."""
    active_agents: int = 0
    suspended_agents: int = 0
    active_policies: int = 0
    pending_approvals: int = 0
    high_risk_actions: int = 0
    critical_risk_actions: int = 0
    blocked_actions: int = 0
    failed_executions: int = 0
    risk_distribution: Dict[str, int] = Field(default_factory=dict)
    decision_distribution: Dict[str, int] = Field(default_factory=dict)
    recent_events: List[AuditEventResponse] = Field(default_factory=list)

    # Sentinel Security Scanner metrics
    sentinel_findings_count: int = 0
    critical_findings_count: int = 0
    high_findings_count: int = 0
    findings_distribution: Dict[str, int] = Field(default_factory=dict)

    # Backward and frontend compatibility aliases
    agents_count: Optional[int] = None
    tools_count: Optional[int] = None
    active_policies_count: Optional[int] = None
    pending_approvals_count: Optional[int] = None
    blocked_actions_count: Optional[int] = None
    allowed_actions_count: Optional[int] = None
    high_risk_actions_count: Optional[int] = None
    executions_count: Optional[int] = None
    recent_audit_events_count: Optional[int] = None


class SearchResultItem(BaseModel):
    """Single matching record in global security investigation search."""
    category: str  # runtime_action, decision, approval, execution, audit_event, agent, tool
    entity_type: Optional[str] = None
    id: str
    title: str
    subtitle: Optional[str] = None
    badge: Optional[str] = None
    link: Optional[str] = None
    created_at: Optional[datetime] = None
    status: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None


class SearchResponse(BaseModel):
    """Results from global security investigation search."""
    query: str
    results: List[SearchResultItem] = Field(default_factory=list)
    items: List[SearchResultItem] = Field(default_factory=list)
    total: int = 0
