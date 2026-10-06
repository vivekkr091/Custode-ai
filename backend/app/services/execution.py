"""Service layer for controlled tool execution, execution audit persistence, and dispatch."""

from typing import List, Optional, Tuple
import uuid

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.base import utc_now
from app.db.models.execution import Execution, ExecutionStatus
from app.db.models.organization import Organization, OrganizationStatus
from app.db.models.runtime_action import ActionStatus, RuntimeAction
from app.runtime.execution_guard import ExecutionGuard
from app.runtime.execution_registry import execution_registry
from app.runtime.executor import ExecutionContext
from app.services.agent import OrganizationNotFoundError, OrganizationSuspendedError
from app.services.runtime_action import RuntimeActionNotFoundError


class DuplicateExecutionError(Exception):
    """Raised when an attempt is made to re-execute an already succeeded RuntimeAction."""

    def __init__(self, action_id: uuid.UUID, message: Optional[str] = None):
        msg = message or f"RuntimeAction '{action_id}' has already been successfully executed."
        super().__init__(msg)
        self.action_id = action_id


class ExecutionNotFoundError(Exception):
    """Raised when an Execution record is not found within the organization context."""

    def __init__(self, org_id: uuid.UUID, execution_id: uuid.UUID):
        super().__init__(f"Execution '{execution_id}' not found in organization '{org_id}'")
        self.org_id = org_id
        self.execution_id = execution_id


async def execute_runtime_action(
    session: AsyncSession,
    organization_id: uuid.UUID,
    runtime_action_id: uuid.UUID,
) -> Execution:
    """Execute a RuntimeAction under strict controlled execution guardrails.

    Workflow:
    1. Tenant validation
    2. Guard validation (Permission, Policy, Risk, Decision, Human Approval, Idempotency)
    3. If guard fails with DUPLICATE_EXECUTION: raise DuplicateExecutionError
    4. If guard fails with BLOCKED / APPROVAL_REQUIRED / RESOURCE_INACTIVE:
       Persist audit Execution record with status='blocked' and update action status if blocked.
    5. If guard allows:
       Dispatch to registered safe tool handler via ExecutionRegistry
    6. Persist execution outcome (status='succeeded' or 'failed') and update RuntimeAction lifecycle.
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

    # 2. Run Execution Guard
    guard_result = await ExecutionGuard.validate(
        session=session,
        organization_id=organization_id,
        runtime_action_id=runtime_action_id,
    )

    action = guard_result.action
    tool = guard_result.tool
    operation = guard_result.operation

    # 3. Handle Idempotency / Duplicate
    if not guard_result.allowed and guard_result.error_code == "DUPLICATE_EXECUTION":
        raise DuplicateExecutionError(runtime_action_id, guard_result.reason)

    # 4. Handle Guard Block / Failure
    if not guard_result.allowed:
        blocked_execution = Execution(
            organization_id=organization_id,
            runtime_action_id=runtime_action_id,
            agent_id=action.agent_id if action else uuid.uuid4(),
            tool_id=action.tool_id if action else uuid.uuid4(),
            operation_id=action.operation_id if action else uuid.uuid4(),
            decision_id=guard_result.decision_id,
            approval_id=guard_result.approval_id,
            status=ExecutionStatus.blocked.value,
            result=None,
            error_code=guard_result.error_code,
            error_message=guard_result.reason,
            started_at=utc_now(),
            completed_at=utc_now(),
        )

        if action and guard_result.error_code == "EXECUTION_BLOCKED_BY_GUARD":
            action.status = ActionStatus.denied.value
            action.completed_at = utc_now()
            session.add(action)

        session.add(blocked_execution)
        await session.flush()
        await session.refresh(blocked_execution)

        from app.audit.service import record_event, AuditEventType, AuditOutcome, AuditActorType
        await record_event(
            session=session,
            event_type=AuditEventType.EXECUTION_BLOCKED,
            action="BLOCK_EXECUTION",
            organization_id=organization_id,
            actor_type=AuditActorType.SYSTEM,
            actor_id="execution_guard",
            resource_type="EXECUTION",
            resource_id=blocked_execution.id,
            outcome=AuditOutcome.DENIED,
            metadata={
                "runtime_action_id": str(runtime_action_id),
                "error_code": guard_result.error_code,
                "reason": guard_result.reason,
            },
            request_id=str(action.request_id) if action else None,
        )
        return blocked_execution

    # 5. Guard Allowed: Dispatch execution
    assert action is not None
    assert tool is not None
    assert operation is not None

    start_time = utc_now()

    # Create Execution record in running state
    execution = Execution(
        organization_id=organization_id,
        runtime_action_id=runtime_action_id,
        agent_id=action.agent_id,
        tool_id=action.tool_id,
        operation_id=action.operation_id,
        decision_id=guard_result.decision_id,
        approval_id=guard_result.approval_id,
        status=ExecutionStatus.running.value,
        started_at=start_time,
    )
    session.add(execution)
    await session.flush()

    # Build ExecutionContext
    context = ExecutionContext(
        runtime_action_id=action.id,
        organization_id=organization_id,
        agent_id=action.agent_id,
        tool_id=action.tool_id,
        operation_id=action.operation_id,
        action_type=action.action_type,
        environment=action.environment,
        parameters=action.parameters or {},
        resource=action.resource,
        resource_type=action.resource_type,
        decision_id=guard_result.decision_id,
        approval_id=guard_result.approval_id,
    )

    # Dispatch to ExecutionRegistry
    exec_result = await execution_registry.execute(
        context=context,
        tool_slug=tool.slug,
        operation_slug=operation.slug,
        tool_type=tool.tool_type,
        operation_type=operation.operation_type,
    )

    end_time = utc_now()

    # 6. Record Outcome
    if exec_result.success:
        execution.status = ExecutionStatus.succeeded.value
        execution.result = exec_result.output
        execution.error_code = None
        execution.error_message = None
        execution.completed_at = end_time

        action.status = ActionStatus.executed.value
        action.completed_at = end_time
    else:
        execution.status = ExecutionStatus.failed.value
        execution.result = exec_result.output
        execution.error_code = exec_result.error_code
        execution.error_message = exec_result.error_message
        execution.completed_at = end_time

        action.status = ActionStatus.failed.value
        action.completed_at = end_time

    session.add(execution)
    session.add(action)
    await session.flush()
    await session.refresh(execution)

    from app.audit.service import record_event, AuditEventType, AuditOutcome, AuditActorType
    ev_type = AuditEventType.EXECUTION_SUCCEEDED if exec_result.success else AuditEventType.EXECUTION_FAILED
    outc = AuditOutcome.SUCCESS if exec_result.success else AuditOutcome.FAILURE
    await record_event(
        session=session,
        event_type=ev_type,
        action="EXECUTE_ACTION",
        organization_id=organization_id,
        actor_type=AuditActorType.AGENT,
        actor_id=str(action.agent_id),
        resource_type="EXECUTION",
        resource_id=execution.id,
        outcome=outc,
        metadata={
            "runtime_action_id": str(action.id),
            "tool_id": str(tool.id),
            "operation_id": str(operation.id),
            "error_code": exec_result.error_code,
            "error_message": exec_result.error_message,
        },
        request_id=str(action.request_id),
    )

    return execution


async def get_execution(
    session: AsyncSession,
    organization_id: uuid.UUID,
    execution_id: uuid.UUID,
) -> Optional[Execution]:
    """Retrieve an Execution audit record scoped to an organization."""
    query = select(Execution).where(
        Execution.organization_id == organization_id,
        Execution.id == execution_id,
    )
    res = await session.execute(query)
    return res.scalar_one_or_none()


async def list_executions(
    session: AsyncSession,
    organization_id: uuid.UUID,
    runtime_action_id: Optional[uuid.UUID] = None,
    agent_id: Optional[uuid.UUID] = None,
    tool_id: Optional[uuid.UUID] = None,
    status: Optional[str] = None,
    limit: int = 50,
    offset: int = 0,
) -> Tuple[List[Execution], int]:
    """List execution records strictly scoped to an organization with filtering and count."""
    count_query = select(func.count(Execution.id)).where(
        Execution.organization_id == organization_id
    )
    if runtime_action_id:
        count_query = count_query.where(Execution.runtime_action_id == runtime_action_id)
    if agent_id:
        count_query = count_query.where(Execution.agent_id == agent_id)
    if tool_id:
        count_query = count_query.where(Execution.tool_id == tool_id)
    if status:
        count_query = count_query.where(Execution.status == status)

    total_res = await session.execute(count_query)
    total = total_res.scalar() or 0

    query = select(Execution).where(Execution.organization_id == organization_id)
    if runtime_action_id:
        query = query.where(Execution.runtime_action_id == runtime_action_id)
    if agent_id:
        query = query.where(Execution.agent_id == agent_id)
    if tool_id:
        query = query.where(Execution.tool_id == tool_id)
    if status:
        query = query.where(Execution.status == status)

    query = query.order_by(Execution.created_at.desc()).limit(limit).offset(offset)
    res = await session.execute(query)
    return list(res.scalars().all()), total
