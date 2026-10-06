"""Service layer for Human Governance Approval workflows, reviewer authorization, and real-time security revalidation."""

from datetime import datetime, timezone
from typing import List, Optional, Tuple, Union
import uuid
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.base import utc_now
from app.db.models.agent import Agent, AgentStatus
from app.db.models.approval import ApprovalRequest, ApprovalStatus
from app.db.models.decision import Decision, DecisionType
from app.db.models.membership import Membership, MembershipRole, MembershipStatus
from app.db.models.organization import Organization, OrganizationStatus
from app.db.models.runtime_action import ActionStatus, RuntimeAction
from app.db.models.tool import Tool, ToolStatus
from app.db.models.tool_operation import OperationStatus, ToolOperation
from app.db.models.user import User, UserStatus
from app.engines.decision.evaluator import DecisionEngine
from app.engines.permission.evaluator import PermissionEngine, PermissionRequest
from app.engines.policy.evaluator import PolicyEngine
from app.engines.risk.evaluator import RiskEngine
from app.schemas.approval import (
    ApprovalApproveRequest,
    ApprovalCancelRequest,
    ApprovalCreate,
    ApprovalRejectRequest,
    ApprovalRevalidationResult,
)
from app.schemas.policy import ActionContext
from app.services.agent import OrganizationNotFoundError, OrganizationSuspendedError
from app.services.decision import DecisionNotFoundError
from app.services.permission import InactiveResourceError, ResourceHierarchyError
from app.services.runtime_action import RuntimeActionNotFoundError
from app.services.tool_operation import OperationNotFoundError


class ApprovalNotFoundError(Exception):
    """Raised when an approval request cannot be found within the organization context."""

    def __init__(self, org_id: uuid.UUID, approval_id: uuid.UUID):
        super().__init__(f"ApprovalRequest '{approval_id}' not found in organization '{org_id}'")
        self.org_id = org_id
        self.approval_id = approval_id


class InvalidDecisionForApprovalError(Exception):
    """Raised when attempting to create an approval request for a non-REQUIRE_APPROVAL decision."""

    def __init__(self, decision_id: uuid.UUID, decision_value: str):
        super().__init__(
            f"Cannot create approval request for decision '{decision_id}' with outcome '{decision_value}'. "
            f"Approval requests can only be initiated for decisions with status 'require_approval'."
        )
        self.decision_id = decision_id
        self.decision_value = decision_value


class DecisionMismatchError(Exception):
    """Raised when a Decision does not match the target RuntimeAction."""

    def __init__(self, message: str):
        super().__init__(message)


class InvalidApprovalLifecycleTransitionError(Exception):
    """Raised on invalid approval state transitions."""

    def __init__(self, message: str):
        super().__init__(message)


class ApprovalExpiredError(Exception):
    """Raised when attempting to approve or act upon an expired approval request."""

    def __init__(self, message: str = "Approval request has expired."):
        super().__init__(message)


class UnauthorizedReviewerError(Exception):
    """Raised when a user lacks required organizational permissions to review approval requests."""

    def __init__(self, message: str):
        super().__init__(message)


class RevalidationFailedError(Exception):
    """Raised when revalidation produces a BLOCK decision or other non-approvable security state."""

    def __init__(self, message: str, revalidation_result: Optional[ApprovalRevalidationResult] = None):
        super().__init__(message)
        self.revalidation_result = revalidation_result


class RevalidationStaleError(Exception):
    """Raised when revalidation produces an ALLOW decision, rendering approval stale."""

    def __init__(self, message: str, revalidation_result: Optional[ApprovalRevalidationResult] = None):
        super().__init__(message)
        self.revalidation_result = revalidation_result


class SelfApprovalNotAllowedError(Exception):
    """Raised when a reviewer is detected to be the same identity as the requester."""

    def __init__(self, message: str = "Self-approval is not allowed."):
        super().__init__(message)


# Authorized roles for human approval
AUTHORIZED_REVIEWER_ROLES = {
    MembershipRole.organization_admin.value,
    MembershipRole.security_analyst.value,
}


def _check_and_expire(approval: ApprovalRequest) -> bool:
    """Evaluate expiration in-memory and update status if expired."""
    if approval.status == ApprovalStatus.pending.value and approval.expires_at is not None:
        now = utc_now()
        exp = approval.expires_at
        if exp.tzinfo is None:
            exp = exp.replace(tzinfo=timezone.utc)
        if now > exp:
            approval.status = ApprovalStatus.expired.value
            return True
    return False


async def create_approval_request(
    session: AsyncSession,
    organization_id: uuid.UUID,
    runtime_action_id: uuid.UUID,
    data: ApprovalCreate,
) -> ApprovalRequest:
    """Create or reuse an authoritative human approval request.

    Preconditions:
    1. RuntimeAction exists and belongs to organization.
    2. Decision exists, belongs to same organization and RuntimeAction.
    3. Decision outcome is REQUIRE_APPROVAL.
    4. Requesting agent belongs to organization and is active.
    5. Reuses existing active pending approval for the same action if present.
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

    # 2. Validate RuntimeAction
    action_res = await session.execute(
        select(RuntimeAction).where(
            RuntimeAction.id == runtime_action_id,
            RuntimeAction.organization_id == organization_id,
        )
    )
    action = action_res.scalar_one_or_none()
    if action is None:
        raise RuntimeActionNotFoundError(organization_id, runtime_action_id)

    # 3. Validate Requesting Agent
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

    # 4. Validate Decision
    decision_res = await session.execute(
        select(Decision).where(
            Decision.id == data.decision_id,
            Decision.organization_id == organization_id,
        )
    )
    decision = decision_res.scalar_one_or_none()
    if decision is None:
        raise DecisionNotFoundError(organization_id, data.decision_id)

    if decision.runtime_action_id != action.id:
        raise DecisionMismatchError(
            f"Decision '{data.decision_id}' does not belong to RuntimeAction '{runtime_action_id}'"
        )

    # 5. Validate Decision is REQUIRE_APPROVAL
    if decision.decision.lower() != DecisionType.require_approval.value:
        raise InvalidDecisionForApprovalError(data.decision_id, decision.decision)

    # 6. Check for existing pending approval request
    existing_query = select(ApprovalRequest).where(
        ApprovalRequest.organization_id == organization_id,
        ApprovalRequest.runtime_action_id == runtime_action_id,
        ApprovalRequest.status == ApprovalStatus.pending.value,
    )
    existing_res = await session.execute(existing_query)
    existing_approval = existing_res.scalar_one_or_none()
    if existing_approval is not None:
        if not _check_and_expire(existing_approval):
            return existing_approval
        else:
            session.add(existing_approval)
            await session.flush()

    # 7. Construct Decision Snapshot
    decision_snapshot = {
        "decision": decision.decision,
        "reason": decision.reason,
        "risk_level": decision.risk_level,
        "risk_score": float(decision.risk_score) if decision.risk_score is not None else None,
        "permission_effect": decision.permission_effect,
        "policy_effect": decision.policy_effect,
        "policy_id": str(decision.policy_id) if decision.policy_id else None,
        "policy_version_id": str(decision.policy_version_id) if decision.policy_version_id else None,
        "engine_version": decision.engine_version,
    }

    # 8. Construct Safe Reviewer Approval Context (no secrets/tokens)
    approval_context = {
        "agent_id": str(action.agent_id),
        "tool_id": str(action.tool_id),
        "operation_id": str(action.operation_id),
        "environment": action.environment,
        "action_type": action.action_type,
        "resource": action.resource,
        "resource_type": action.resource_type,
        "amount": float(action.amount) if action.amount is not None else None,
        "currency": action.currency,
        "risk_level": decision.risk_level,
        "risk_score": float(decision.risk_score) if decision.risk_score is not None else None,
        "policy_id": str(decision.policy_id) if decision.policy_id else None,
        "policy_version_id": str(decision.policy_version_id) if decision.policy_version_id else None,
        "decision_reason": decision.reason,
    }

    # 9. Create ApprovalRequest
    approval = ApprovalRequest(
        organization_id=organization_id,
        runtime_action_id=runtime_action_id,
        decision_id=data.decision_id,
        requested_by_agent_id=action.agent_id,
        status=ApprovalStatus.pending.value,
        reason=data.reason or decision.reason,
        expires_at=data.expires_at,
        decision_snapshot=decision_snapshot,
        approval_context=approval_context,
    )
    session.add(approval)
    await session.flush()
    await session.refresh(approval)
    return approval


async def get_approval(
    session: AsyncSession,
    organization_id: uuid.UUID,
    approval_id: uuid.UUID,
    for_update: bool = False,
) -> Optional[ApprovalRequest]:
    """Retrieve an authoritative ApprovalRequest scoped to an organization."""
    query = select(ApprovalRequest).where(
        ApprovalRequest.organization_id == organization_id,
        ApprovalRequest.id == approval_id,
    )
    if for_update:
        query = query.with_for_update()
    res = await session.execute(query)
    approval = res.scalar_one_or_none()
    if approval is not None:
        if _check_and_expire(approval):
            session.add(approval)
            await session.flush()
            await session.refresh(approval)
    return approval


async def list_approvals(
    session: AsyncSession,
    organization_id: uuid.UUID,
    status: Optional[str] = None,
    limit: int = 50,
    offset: int = 0,
) -> Tuple[List[ApprovalRequest], int]:
    """List approval requests strictly scoped to an organization with total count."""
    count_query = select(func.count(ApprovalRequest.id)).where(
        ApprovalRequest.organization_id == organization_id
    )
    if status:
        count_query = count_query.where(ApprovalRequest.status == status)
    total_res = await session.execute(count_query)
    total = total_res.scalar() or 0

    query = select(ApprovalRequest).where(
        ApprovalRequest.organization_id == organization_id
    )
    if status:
        query = query.where(ApprovalRequest.status == status)
    query = query.order_by(ApprovalRequest.created_at.desc()).limit(limit).offset(offset)
    res = await session.execute(query)
    items = list(res.scalars().all())

    # Check expiration on retrieved items
    modified = False
    for item in items:
        if _check_and_expire(item):
            session.add(item)
            modified = True
    if modified:
        await session.flush()

    return items, total


async def authorize_reviewer(
    session: AsyncSession,
    organization_id: uuid.UUID,
    reviewer_user_id: uuid.UUID,
) -> Membership:
    """Validate reviewer identity, tenant membership, and authorized governance role."""
    # 1. Validate User
    user_res = await session.execute(
        select(User).where(User.id == reviewer_user_id)
    )
    user = user_res.scalar_one_or_none()
    if user is None:
        raise UnauthorizedReviewerError(f"User '{reviewer_user_id}' does not exist.")
    if user.status != UserStatus.active.value:
        raise UnauthorizedReviewerError(f"User '{reviewer_user_id}' is not active (state: '{user.status}').")

    # 2. Validate Membership in Organization
    mem_res = await session.execute(
        select(Membership).where(
            Membership.organization_id == organization_id,
            Membership.user_id == reviewer_user_id,
        )
    )
    membership = mem_res.scalar_one_or_none()
    if membership is None:
        raise UnauthorizedReviewerError(
            f"User '{reviewer_user_id}' is not a member of organization '{organization_id}'."
        )
    if membership.status != MembershipStatus.active.value:
        raise UnauthorizedReviewerError(
            f"User membership in organization '{organization_id}' is not active (state: '{membership.status}')."
        )

    # 3. Validate Role Authority
    if membership.role not in AUTHORIZED_REVIEWER_ROLES:
        raise UnauthorizedReviewerError(
            f"User role '{membership.role}' is not authorized to review approval requests. "
            f"Authorized roles are: {sorted(AUTHORIZED_REVIEWER_ROLES)}"
        )

    return membership


async def revalidate_security_state(
    session: AsyncSession,
    organization_id: uuid.UUID,
    approval: ApprovalRequest,
) -> ApprovalRevalidationResult:
    """Revalidate real-time security state prior to approval finalization."""
    # 1. Load current RuntimeAction
    action_res = await session.execute(
        select(RuntimeAction).where(
            RuntimeAction.id == approval.runtime_action_id,
            RuntimeAction.organization_id == organization_id,
        )
    )
    action = action_res.scalar_one_or_none()
    if action is None:
        raise RuntimeActionNotFoundError(organization_id, approval.runtime_action_id)

    # 2. Confirm action has not terminated or invalidated
    terminal_statuses = {
        ActionStatus.executed.value,
        ActionStatus.failed.value,
        ActionStatus.cancelled.value,
    }
    if action.status in terminal_statuses:
        raise RevalidationFailedError(
            f"RuntimeAction '{action.id}' has already reached a terminal lifecycle state '{action.status}'."
        )

    # 3. Load Agent, Tool, Operation
    agent_res = await session.execute(
        select(Agent).where(
            Agent.id == action.agent_id,
            Agent.organization_id == organization_id,
        )
    )
    agent = agent_res.scalar_one_or_none()
    if agent is None or agent.status != AgentStatus.active.value:
        reval = ApprovalRevalidationResult(
            valid=False,
            current_decision=DecisionType.block.value.upper(),
            reason="Agent is missing or no longer active.",
            stale=True,
            evaluation_trace={"error": "Agent inactive"},
        )
        raise RevalidationFailedError(
            "Approval cannot be completed because requesting agent is inactive.",
            revalidation_result=reval,
        )

    tool_res = await session.execute(
        select(Tool).where(
            Tool.id == action.tool_id,
            Tool.organization_id == organization_id,
        )
    )
    tool = tool_res.scalar_one_or_none()
    if tool is None or tool.status != ToolStatus.active.value:
        reval = ApprovalRevalidationResult(
            valid=False,
            current_decision=DecisionType.block.value.upper(),
            reason="Tool is missing or no longer active.",
            stale=True,
            evaluation_trace={"error": "Tool inactive"},
        )
        raise RevalidationFailedError(
            "Approval cannot be completed because target tool is inactive.",
            revalidation_result=reval,
        )

    op_res = await session.execute(
        select(ToolOperation).where(
            ToolOperation.id == action.operation_id,
            ToolOperation.tool_id == action.tool_id,
        )
    )
    operation = op_res.scalar_one_or_none()
    if operation is None or operation.status != OperationStatus.active.value:
        reval = ApprovalRevalidationResult(
            valid=False,
            current_decision=DecisionType.block.value.upper(),
            reason="Operation is missing or no longer active.",
            stale=True,
            evaluation_trace={"error": "Operation inactive"},
        )
        raise RevalidationFailedError(
            "Approval cannot be completed because target operation is inactive.",
            revalidation_result=reval,
        )

    # 4. Re-run Permission Engine
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

    # 5. Re-run Policy Engine
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
    policy_result = await PolicyEngine.evaluate(session, organization_id, action_context)

    # 6. Re-run Risk Engine
    risk_result = RiskEngine.evaluate(
        runtime_action=action,
        operation_baseline_risk_level=operation.risk_level,
        operation_type=operation.operation_type,
    )

    # 7. Re-run Decision Engine
    decision_eval = DecisionEngine.evaluate(
        permission_result=perm_result,
        policy_result=policy_result,
        risk_result=risk_result,
    )

    cur_decision_str = (
        decision_eval.decision.value if hasattr(decision_eval.decision, "value") else str(decision_eval.decision)
    ).upper()

    # 8. Compare Revalidated Decision
    if cur_decision_str == "BLOCK":
        reval = ApprovalRevalidationResult(
            valid=False,
            current_decision="BLOCK",
            current_risk_level=decision_eval.risk_level,
            current_risk_score=decision_eval.risk_score,
            reason=f"Approval cannot be completed because current authorization decision is BLOCK: {decision_eval.reason}",
            stale=True,
            evaluation_trace=decision_eval.evaluation_trace,
        )
        raise RevalidationFailedError(
            "Approval cannot be completed because the current authorization decision is BLOCK.",
            revalidation_result=reval,
        )

    if cur_decision_str == "ALLOW":
        reval = ApprovalRevalidationResult(
            valid=False,
            current_decision="ALLOW",
            current_risk_level=decision_eval.risk_level,
            current_risk_score=decision_eval.risk_score,
            reason="Current authorization decision is ALLOW; approval is no longer required.",
            stale=True,
            evaluation_trace=decision_eval.evaluation_trace,
        )
        raise RevalidationStaleError(
            "Approval cannot be completed because the current authorization decision is now ALLOW; approval is stale.",
            revalidation_result=reval,
        )

    # Remains REQUIRE_APPROVAL
    return ApprovalRevalidationResult(
        valid=True,
        current_decision="REQUIRE_APPROVAL",
        current_risk_level=decision_eval.risk_level,
        current_risk_score=decision_eval.risk_score,
        reason="Security state revalidated: action still requires approval.",
        stale=False,
        evaluation_trace=decision_eval.evaluation_trace,
    )


async def approve_request(
    session: AsyncSession,
    organization_id: uuid.UUID,
    approval_id: uuid.UUID,
    reviewer_user_id: uuid.UUID,
    data: Optional[ApprovalApproveRequest] = None,
) -> ApprovalRequest:
    """Approve a pending human governance approval request with revalidation."""
    approval = await get_approval(session, organization_id, approval_id, for_update=True)
    if approval is None:
        raise ApprovalNotFoundError(organization_id, approval_id)

    # 1. State machine check
    if approval.status != ApprovalStatus.pending.value:
        raise InvalidApprovalLifecycleTransitionError(
            f"Cannot approve request '{approval_id}' in state '{approval.status}'"
        )

    # 2. Expiration check
    if _check_and_expire(approval):
        session.add(approval)
        await session.flush()
        raise ApprovalExpiredError(f"Approval request '{approval_id}' has expired.")

    # 3. Authorize reviewer
    await authorize_reviewer(session, organization_id, reviewer_user_id)

    # 4. Self-approval prevention
    if reviewer_user_id == approval.requested_by_agent_id:
        raise SelfApprovalNotAllowedError("Requester cannot review or approve its own action.")

    # 5. Revalidate security state
    try:
        await revalidate_security_state(session, organization_id, approval)
    except RevalidationStaleError as e:
        # Mark approval as cancelled / stale
        approval.status = ApprovalStatus.cancelled.value
        session.add(approval)
        await session.flush()
        raise e

    # 6. Finalize approval
    approval.status = ApprovalStatus.approved.value
    approval.reviewer_user_id = reviewer_user_id
    approval.reviewed_at = utc_now()
    if data and data.reviewer_note:
        approval.approval_context = {
            **approval.approval_context,
            "reviewer_note": data.reviewer_note,
        }
    session.add(approval)

    # 7. Update RuntimeAction lifecycle status to approved
    action_res = await session.execute(
        select(RuntimeAction).where(RuntimeAction.id == approval.runtime_action_id)
    )
    action = action_res.scalar_one_or_none()
    if action and action.status in (ActionStatus.pending.value, ActionStatus.evaluating.value):
        action.status = ActionStatus.approved.value
        action.evaluated_at = utc_now()
        session.add(action)

    await session.flush()
    await session.refresh(approval)
    return approval


async def reject_request(
    session: AsyncSession,
    organization_id: uuid.UUID,
    approval_id: uuid.UUID,
    reviewer_user_id: uuid.UUID,
    data: ApprovalRejectRequest,
) -> ApprovalRequest:
    """Reject a pending human governance approval request with mandatory reason."""
    if not data.rejection_reason or not data.rejection_reason.strip():
        raise ValueError("Rejection reason is required")

    approval = await get_approval(session, organization_id, approval_id, for_update=True)
    if approval is None:
        raise ApprovalNotFoundError(organization_id, approval_id)

    # 1. State machine check
    if approval.status != ApprovalStatus.pending.value:
        raise InvalidApprovalLifecycleTransitionError(
            f"Cannot reject request '{approval_id}' in state '{approval.status}'"
        )

    # 2. Expiration check
    if _check_and_expire(approval):
        session.add(approval)
        await session.flush()
        raise ApprovalExpiredError(f"Approval request '{approval_id}' has expired.")

    # 3. Authorize reviewer
    await authorize_reviewer(session, organization_id, reviewer_user_id)

    # 4. Finalize rejection
    approval.status = ApprovalStatus.rejected.value
    approval.reviewer_user_id = reviewer_user_id
    approval.reviewed_at = utc_now()
    approval.rejection_reason = data.rejection_reason.strip()
    session.add(approval)

    # 5. Update RuntimeAction lifecycle status to denied
    action_res = await session.execute(
        select(RuntimeAction).where(RuntimeAction.id == approval.runtime_action_id)
    )
    action = action_res.scalar_one_or_none()
    if action and action.status in (ActionStatus.pending.value, ActionStatus.evaluating.value):
        action.status = ActionStatus.denied.value
        action.evaluated_at = utc_now()
        session.add(action)

    await session.flush()
    await session.refresh(approval)
    return approval


async def cancel_request(
    session: AsyncSession,
    organization_id: uuid.UUID,
    approval_id: uuid.UUID,
    data: Optional[ApprovalCancelRequest] = None,
) -> ApprovalRequest:
    """Cancel an active pending approval request."""
    approval = await get_approval(session, organization_id, approval_id, for_update=True)
    if approval is None:
        raise ApprovalNotFoundError(organization_id, approval_id)

    if approval.status != ApprovalStatus.pending.value:
        raise InvalidApprovalLifecycleTransitionError(
            f"Cannot cancel request '{approval_id}' in state '{approval.status}'"
        )

    approval.status = ApprovalStatus.cancelled.value
    if data and data.reason:
        approval.approval_context = {
            **approval.approval_context,
            "cancellation_reason": data.reason.strip(),
        }
    session.add(approval)

    # Update RuntimeAction lifecycle status to cancelled if pending
    action_res = await session.execute(
        select(RuntimeAction).where(RuntimeAction.id == approval.runtime_action_id)
    )
    action = action_res.scalar_one_or_none()
    if action and action.status == ActionStatus.pending.value:
        action.status = ActionStatus.cancelled.value
        session.add(action)

    await session.flush()
    await session.refresh(approval)
    return approval
