"""Service layer for RuntimeAction persistence, hierarchy validation, and lifecycle transitions."""

from datetime import datetime, timezone
from typing import List, Optional
import uuid
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.base import utc_now
from app.db.models.agent import Agent, AgentEnvironment, AgentStatus
from app.db.models.organization import Organization, OrganizationStatus
from app.db.models.runtime_action import ActionEnvironment, ActionStatus, RuntimeAction
from app.db.models.tool import Tool, ToolStatus
from app.db.models.tool_operation import OperationStatus, ToolOperation
from app.runtime.normalizer import ActionNormalizer, NormalizationError
from app.schemas.runtime_action import RuntimeActionCreate
from app.services.agent import OrganizationNotFoundError, OrganizationSuspendedError


class RuntimeActionNotFoundError(Exception):
    """Raised when a RuntimeAction is not found within the organization context."""
    def __init__(self, org_id: uuid.UUID, action_id: uuid.UUID):
        super().__init__(f"RuntimeAction '{action_id}' not found in organization '{org_id}'")
        self.org_id = org_id
        self.action_id = action_id


class InvalidActionLifecycleTransitionError(Exception):
    """Raised when an illegal lifecycle transition is requested for a RuntimeAction."""
    def __init__(self, current_status: str, target_status: str):
        super().__init__(f"Cannot transition RuntimeAction from '{current_status}' to '{target_status}'")
        self.current_status = current_status
        self.target_status = target_status


class EnvironmentIncompatibilityError(Exception):
    """Raised when an agent's tier is incompatible with the requested action environment."""
    def __init__(self, agent_env: str, action_env: str):
        super().__init__(f"Agent in environment '{agent_env}' cannot execute actions in '{action_env}'")
        self.agent_env = agent_env
        self.action_env = action_env


class ResourceHierarchyError(Exception):
    """Raised when a resource does not belong to the declared parent hierarchy."""
    def __init__(self, message: str):
        super().__init__(message)


class InactiveResourceError(Exception):
    """Raised when attempting action registration against an inactive/suspended resource."""
    def __init__(self, resource_type: str, resource_id: uuid.UUID, status: str):
        super().__init__(f"Cannot use {resource_type} '{resource_id}' in state '{status}'")
        self.resource_type = resource_type
        self.resource_id = resource_id
        self.status = status


# Strict deterministic lifecycle transition graph
ALLOWED_TRANSITIONS = {
    ActionStatus.pending.value: {ActionStatus.evaluating.value, ActionStatus.cancelled.value},
    ActionStatus.evaluating.value: {ActionStatus.approved.value, ActionStatus.denied.value, ActionStatus.failed.value},
    ActionStatus.approved.value: {ActionStatus.executed.value, ActionStatus.failed.value},
    ActionStatus.denied.value: set(),
    ActionStatus.executed.value: set(),
    ActionStatus.failed.value: set(),
    ActionStatus.cancelled.value: set(),
}

AGENT_ENV_TO_ACTION_ENV = {
    AgentEnvironment.development.value: ActionEnvironment.dev.value,
    AgentEnvironment.staging.value: ActionEnvironment.staging.value,
    AgentEnvironment.production.value: ActionEnvironment.prod.value,
}


async def create_runtime_action(
    session: AsyncSession,
    organization_id: uuid.UUID,
    agent_id: uuid.UUID,
    data: RuntimeActionCreate,
) -> RuntimeAction:
    """Validate hierarchy, normalize request, and persist a canonical RuntimeAction."""
    # 1. Normalize and canonicalize incoming request
    context = ActionNormalizer.normalize(
        organization_id=organization_id,
        agent_id=agent_id,
        data=data,
    )

    # 2. Validate Organization
    org_res = await session.execute(
        select(Organization).where(Organization.id == organization_id)
    )
    org = org_res.scalar_one_or_none()
    if org is None:
        raise OrganizationNotFoundError(organization_id)
    if org.status != OrganizationStatus.active.value:
        raise OrganizationSuspendedError(organization_id)

    # 3. Validate Agent in Org
    agent_res = await session.execute(
        select(Agent).where(
            Agent.id == agent_id,
            Agent.organization_id == organization_id,
        )
    )
    agent = agent_res.scalar_one_or_none()
    if agent is None:
        raise ResourceHierarchyError(f"Agent '{agent_id}' not found in organization '{organization_id}'")
    if agent.status != AgentStatus.active.value:
        raise InactiveResourceError("agent", agent_id, agent.status)

    # 4. Validate Agent Environment Compatibility
    expected_action_env = AGENT_ENV_TO_ACTION_ENV.get(agent.environment)
    if expected_action_env != context.environment:
        raise EnvironmentIncompatibilityError(agent.environment, context.environment)

    # 5. Validate Tool in Org
    tool_res = await session.execute(
        select(Tool).where(
            Tool.id == context.tool_id,
            Tool.organization_id == organization_id,
        )
    )
    tool = tool_res.scalar_one_or_none()
    if tool is None:
        raise ResourceHierarchyError(f"Tool '{context.tool_id}' not found in organization '{organization_id}'")
    if tool.status != ToolStatus.active.value:
        raise InactiveResourceError("tool", context.tool_id, tool.status)

    # 6. Validate Operation attached to Tool
    op_res = await session.execute(
        select(ToolOperation).where(
            ToolOperation.id == context.operation_id,
            ToolOperation.tool_id == context.tool_id,
        )
    )
    op = op_res.scalar_one_or_none()
    if op is None:
        raise ResourceHierarchyError(f"Operation '{context.operation_id}' not found under tool '{context.tool_id}'")
    if op.status != OperationStatus.active.value:
        raise InactiveResourceError("operation", context.operation_id, op.status)

    # 7. Persist authoritative RuntimeAction in pending state
    action = RuntimeAction(
        organization_id=organization_id,
        agent_id=agent_id,
        tool_id=context.tool_id,
        operation_id=context.operation_id,
        request_id=context.request_id,
        environment=context.environment,
        action_type=context.action_type,
        resource=context.resource,
        resource_type=context.resource_type,
        parameters=context.parameters,
        amount=context.amount,
        currency=context.currency,
        ip_address=context.ip_address,
        user_agent=context.user_agent,
        status=ActionStatus.pending.value,
        evaluated_at=None,
        completed_at=None,
    )
    session.add(action)
    await session.flush()
    await session.refresh(action)

    from app.audit.service import record_agent_event, AuditEventType, AuditOutcome
    await record_agent_event(
        session=session,
        event_type=AuditEventType.RUNTIME_ACTION_CREATED,
        action="CREATE_RUNTIME_ACTION",
        agent_id=agent_id,
        organization_id=organization_id,
        resource_type="RUNTIME_ACTION",
        resource_id=action.id,
        outcome=AuditOutcome.SUCCESS,
        metadata={
            "tool_id": str(context.tool_id),
            "operation_id": str(context.operation_id),
            "action_type": context.action_type,
            "resource": context.resource,
            "amount": context.amount,
        },
        request_id=str(context.request_id),
        ip_address=context.ip_address,
        user_agent=context.user_agent,
    )

    return action


async def get_runtime_action(
    session: AsyncSession,
    organization_id: uuid.UUID,
    action_id: uuid.UUID,
) -> Optional[RuntimeAction]:
    """Retrieve a single RuntimeAction scoped to an organization."""
    query = select(RuntimeAction).where(
        RuntimeAction.organization_id == organization_id,
        RuntimeAction.id == action_id,
    )
    res = await session.execute(query)
    return res.scalar_one_or_none()


async def list_runtime_actions(
    session: AsyncSession,
    organization_id: uuid.UUID,
    agent_id: Optional[uuid.UUID] = None,
    tool_id: Optional[uuid.UUID] = None,
    status: Optional[str] = None,
    limit: int = 50,
    offset: int = 0,
) -> List[RuntimeAction]:
    """List RuntimeActions scoped strictly to an organization with optional filters."""
    query = select(RuntimeAction).where(RuntimeAction.organization_id == organization_id)
    if agent_id:
        query = query.where(RuntimeAction.agent_id == agent_id)
    if tool_id:
        query = query.where(RuntimeAction.tool_id == tool_id)
    if status:
        query = query.where(RuntimeAction.status == status)

    query = query.order_by(RuntimeAction.created_at.desc()).limit(limit).offset(offset)
    res = await session.execute(query)
    return list(res.scalars().all())


async def transition_runtime_action_status(
    session: AsyncSession,
    organization_id: uuid.UUID,
    action_id: uuid.UUID,
    target_status: ActionStatus,
) -> RuntimeAction:
    """Transition a RuntimeAction's lifecycle state according to the state transition graph."""
    action = await get_runtime_action(session, organization_id, action_id)
    if action is None:
        raise RuntimeActionNotFoundError(organization_id, action_id)

    curr_status = action.status
    target_val = target_status.value

    # Check allowed transitions
    allowed = ALLOWED_TRANSITIONS.get(curr_status, set())
    if target_val not in allowed:
        raise InvalidActionLifecycleTransitionError(curr_status, target_val)

    now = utc_now()
    action.status = target_val

    # Update appropriate timestamps
    if target_val == ActionStatus.evaluating.value:
        action.evaluated_at = now
    elif target_val in (ActionStatus.approved.value, ActionStatus.denied.value):
        if action.evaluated_at is None:
            action.evaluated_at = now
    elif target_val in (ActionStatus.executed.value, ActionStatus.failed.value, ActionStatus.cancelled.value):
        action.completed_at = now

    session.add(action)
    await session.flush()
    await session.refresh(action)
    return action
