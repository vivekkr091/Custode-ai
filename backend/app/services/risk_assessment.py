"""Service layer for contextual risk assessment evaluation and historical persistence."""

from typing import List, Optional
import uuid
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.organization import Organization, OrganizationStatus
from app.db.models.risk_assessment import RiskAssessment
from app.db.models.runtime_action import RuntimeAction
from app.db.models.tool_operation import ToolOperation
from app.engines.risk.evaluator import RiskEngine
from app.services.agent import OrganizationNotFoundError, OrganizationSuspendedError
from app.services.runtime_action import RuntimeActionNotFoundError
from app.services.tool_operation import OperationNotFoundError


class RiskAssessmentNotFoundError(Exception):
    """Raised when a RiskAssessment is not found within the organization context."""
    def __init__(self, org_id: uuid.UUID, assessment_id: uuid.UUID):
        super().__init__(f"RiskAssessment '{assessment_id}' not found in organization '{org_id}'")
        self.org_id = org_id
        self.assessment_id = assessment_id


async def assess_runtime_action(
    session: AsyncSession,
    organization_id: uuid.UUID,
    runtime_action_id: uuid.UUID,
) -> RiskAssessment:
    """Evaluate and persist a deterministic contextual risk assessment for a RuntimeAction.

    Strictly preserves historical records: each evaluation creates a new immutable assessment record.
    Never mutates RuntimeAction attributes or lifecycle status.
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

    # 3. Load ToolOperation baseline risk & operation type
    op_res = await session.execute(
        select(ToolOperation).where(ToolOperation.id == action.operation_id)
    )
    operation = op_res.scalar_one_or_none()
    if operation is None:
        raise OperationNotFoundError(action.tool_id, action.operation_id)

    # 3.5 Load or execute Sentinel Security Scan
    from app.services.sentinel_scan import list_findings_for_action, scan_runtime_action
    from app.sentinel.config import settings as sentinel_settings
    existing_findings = await list_findings_for_action(session, organization_id, runtime_action_id)
    if not existing_findings and sentinel_settings.enabled:
        try:
            _, existing_findings = await scan_runtime_action(session, organization_id, runtime_action_id)
        except Exception:
            if sentinel_settings.fail_mode == "fail_closed":
                raise
            existing_findings = []

    # 4. Execute deterministic risk engine evaluation
    eval_result = RiskEngine.evaluate(
        runtime_action=action,
        operation_baseline_risk_level=operation.risk_level,
        operation_type=operation.operation_type,
        security_findings=existing_findings,
    )

    # 5. Persist RiskAssessment audit artifact
    assessment = RiskAssessment(
        organization_id=organization_id,
        runtime_action_id=runtime_action_id,
        risk_level=eval_result.risk_level,
        risk_score=eval_result.risk_score,
        factors=[f.model_dump() for f in eval_result.factors],
        triggered_rules=eval_result.triggered_rules,
        explanation=eval_result.explanation,
        engine_version=eval_result.engine_version,
    )
    session.add(assessment)
    await session.flush()
    await session.refresh(assessment)
    return assessment


async def get_risk_assessment(
    session: AsyncSession,
    organization_id: uuid.UUID,
    assessment_id: uuid.UUID,
) -> Optional[RiskAssessment]:
    """Retrieve an authoritative RiskAssessment scoped to an organization."""
    query = select(RiskAssessment).where(
        RiskAssessment.organization_id == organization_id,
        RiskAssessment.id == assessment_id,
    )
    res = await session.execute(query)
    return res.scalar_one_or_none()


async def list_risk_assessments_for_action(
    session: AsyncSession,
    organization_id: uuid.UUID,
    runtime_action_id: uuid.UUID,
) -> List[RiskAssessment]:
    """List historical risk assessments for a specific action in descending order."""
    # Verify action exists and belongs to org
    action_res = await session.execute(
        select(RuntimeAction).where(
            RuntimeAction.id == runtime_action_id,
            RuntimeAction.organization_id == organization_id,
        )
    )
    if action_res.scalar_one_or_none() is None:
        raise RuntimeActionNotFoundError(organization_id, runtime_action_id)

    query = (
        select(RiskAssessment)
        .where(
            RiskAssessment.organization_id == organization_id,
            RiskAssessment.runtime_action_id == runtime_action_id,
        )
        .order_by(RiskAssessment.created_at.desc())
    )
    res = await session.execute(query)
    return list(res.scalars().all())


async def list_risk_assessments(
    session: AsyncSession,
    organization_id: uuid.UUID,
    limit: int = 50,
    offset: int = 0,
) -> List[RiskAssessment]:
    """List risk assessments strictly scoped to the specified organization."""
    query = (
        select(RiskAssessment)
        .where(RiskAssessment.organization_id == organization_id)
        .order_by(RiskAssessment.created_at.desc())
        .limit(limit)
        .offset(offset)
    )
    res = await session.execute(query)
    return list(res.scalars().all())
