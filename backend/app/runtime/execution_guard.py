"""Authoritative Execution Guard for validating runtime actions before dispatch.

Enforces:
1. Tenant scoping and resource hierarchy
2. Idempotency (prevent duplicate execution of succeeded actions)
3. Action lifecycle state validation
4. Real-time security revalidation (Permission, Policy, Risk, Decision)
5. Human approval verification for actions requiring governance
"""

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Optional
import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.base import utc_now
from app.db.models.approval import ApprovalRequest, ApprovalStatus
from app.db.models.decision import Decision, DecisionType
from app.db.models.execution import Execution, ExecutionStatus
from app.db.models.runtime_action import ActionStatus, RuntimeAction
from app.db.models.tool import Tool
from app.db.models.tool_operation import ToolOperation


@dataclass
class ExecutionGuardResult:
    """Result of an ExecutionGuard validation check."""

    allowed: bool
    error_code: Optional[str] = None
    reason: Optional[str] = None
    decision_id: Optional[uuid.UUID] = None
    approval_id: Optional[uuid.UUID] = None
    action: Optional[RuntimeAction] = None
    tool: Optional[Tool] = None
    operation: Optional[ToolOperation] = None


class ExecutionGuard:
    """Pre-execution security guard ensuring all safety prerequisites are satisfied."""

    @staticmethod
    async def validate(
        session: AsyncSession,
        organization_id: uuid.UUID,
        runtime_action_id: uuid.UUID,
    ) -> ExecutionGuardResult:
        """Validate whether a RuntimeAction is permitted to execute immediately."""
        from app.services.decision import decide_runtime_action
        from app.services.permission import InactiveResourceError, ResourceHierarchyError
        from app.services.runtime_action import RuntimeActionNotFoundError
        from app.services.tool_operation import OperationNotFoundError
        # 1. Load RuntimeAction with row-level lock
        action_res = await session.execute(
            select(RuntimeAction).where(
                RuntimeAction.id == runtime_action_id,
                RuntimeAction.organization_id == organization_id,
            ).with_for_update()
        )
        action = action_res.scalar_one_or_none()
        if action is None:
            raise RuntimeActionNotFoundError(organization_id, runtime_action_id)

        # 2. Check Idempotency: Has this action already succeeded or is it currently running?
        existing_exec_res = await session.execute(
            select(Execution).where(
                Execution.organization_id == organization_id,
                Execution.runtime_action_id == runtime_action_id,
                Execution.status.in_([ExecutionStatus.succeeded.value, ExecutionStatus.running.value]),
            )
        )
        existing_execution = existing_exec_res.scalar_one_or_none()
        if existing_execution is not None:
            reason = (
                "RuntimeAction execution is already in progress."
                if existing_execution.status == ExecutionStatus.running.value
                else "RuntimeAction has already been executed successfully."
            )
            return ExecutionGuardResult(
                allowed=False,
                error_code="DUPLICATE_EXECUTION",
                reason=reason,
                action=action,
            )

        # 3. Check Lifecycle Status
        if action.status == ActionStatus.executed.value:
            return ExecutionGuardResult(
                allowed=False,
                error_code="DUPLICATE_EXECUTION",
                reason="RuntimeAction is already marked as executed.",
                action=action,
            )
        if action.status == ActionStatus.cancelled.value:
            return ExecutionGuardResult(
                allowed=False,
                error_code="ACTION_CANCELLED",
                reason="RuntimeAction has been cancelled.",
                action=action,
            )
        if action.status == ActionStatus.denied.value:
            return ExecutionGuardResult(
                allowed=False,
                error_code="ACTION_DENIED",
                reason="RuntimeAction was previously denied.",
                action=action,
            )

        # 4. Load Tool and ToolOperation
        tool_res = await session.execute(
            select(Tool).where(
                Tool.id == action.tool_id,
                Tool.organization_id == organization_id,
            )
        )
        tool = tool_res.scalar_one_or_none()

        op_res = await session.execute(
            select(ToolOperation).where(
                ToolOperation.id == action.operation_id,
                ToolOperation.tool_id == action.tool_id,
            )
        )
        operation = op_res.scalar_one_or_none()

        # 5. Real-Time Revalidation via Decision Engine
        try:
            decision_record = await decide_runtime_action(
                session=session,
                organization_id=organization_id,
                runtime_action_id=runtime_action_id,
            )
        except (InactiveResourceError, ResourceHierarchyError, OperationNotFoundError) as exc:
            return ExecutionGuardResult(
                allowed=False,
                error_code="RESOURCE_INACTIVE_OR_INVALID",
                reason=str(exc),
                action=action,
                tool=tool,
                operation=operation,
            )

        decision_outcome = decision_record.decision.lower()

        # 6. Branch on Decision Outcome
        if decision_outcome == DecisionType.block.value:
            return ExecutionGuardResult(
                allowed=False,
                error_code="EXECUTION_BLOCKED_BY_GUARD",
                reason=f"Authorization blocked by Decision Engine: {decision_record.reason}",
                decision_id=decision_record.id,
                action=action,
                tool=tool,
                operation=operation,
            )

        if decision_outcome == DecisionType.require_approval.value:
            # Check for an approved ApprovalRequest for this action
            approval_res = await session.execute(
                select(ApprovalRequest).where(
                    ApprovalRequest.organization_id == organization_id,
                    ApprovalRequest.runtime_action_id == runtime_action_id,
                    ApprovalRequest.status == ApprovalStatus.approved.value,
                ).order_by(ApprovalRequest.created_at.desc())
            )
            approval = approval_res.scalars().first()

            if approval is None:
                return ExecutionGuardResult(
                    allowed=False,
                    error_code="APPROVAL_REQUIRED",
                    reason="Action requires human approval which has not been granted.",
                    decision_id=decision_record.id,
                    action=action,
                    tool=tool,
                    operation=operation,
                )

            # Check if approval has expired
            if approval.expires_at is not None:
                now = utc_now()
                exp = approval.expires_at
                if exp.tzinfo is None:
                    exp = exp.replace(tzinfo=timezone.utc)
                if now > exp:
                    approval.status = ApprovalStatus.expired.value
                    session.add(approval)
                    await session.flush()
                    return ExecutionGuardResult(
                        allowed=False,
                        error_code="APPROVAL_EXPIRED",
                        reason="Human approval has expired.",
                        decision_id=decision_record.id,
                        approval_id=approval.id,
                        action=action,
                        tool=tool,
                        operation=operation,
                    )

            # Approval is valid and approved
            return ExecutionGuardResult(
                allowed=True,
                decision_id=decision_record.id,
                approval_id=approval.id,
                action=action,
                tool=tool,
                operation=operation,
            )

        # Outcome is ALLOW
        return ExecutionGuardResult(
            allowed=True,
            decision_id=decision_record.id,
            action=action,
            tool=tool,
            operation=operation,
        )
