"""Permission Engine: Deterministic, least-privilege authorization evaluator."""

import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Optional
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.base import utc_now
from app.db.models.agent import Agent, AgentStatus
from app.db.models.organization import Organization, OrganizationStatus
from app.db.models.permission import Permission, PermissionEffect, PermissionStatus
from app.db.models.tool import Tool, ToolStatus
from app.db.models.tool_operation import OperationStatus, ToolOperation


@dataclass(frozen=True)
class PermissionRequest:
    """Input authorization request passed to the Permission Engine."""

    organization_id: uuid.UUID
    agent_id: uuid.UUID
    tool_id: uuid.UUID
    operation_id: uuid.UUID
    environment: str


@dataclass(frozen=True)
class PermissionEvaluationResult:
    """Authoritative decision produced by the Permission Engine."""

    allowed: bool
    effect: str
    reason: str
    permission_id: Optional[uuid.UUID] = None


class PermissionEngine:
    """Core evaluation engine enforcing tenant-scoped, operation-specific least privilege."""

    @staticmethod
    async def evaluate(
        session: AsyncSession, request: PermissionRequest
    ) -> PermissionEvaluationResult:
        """Evaluate an authorization request using deterministic precedence and default deny."""
        now = utc_now()

        # STEP 1: Validate organization exists and is active
        org_res = await session.execute(
            select(Organization).where(Organization.id == request.organization_id)
        )
        org = org_res.scalar_one_or_none()
        if org is None:
            return PermissionEvaluationResult(
                allowed=False,
                effect="deny",
                reason="Organization not found",
            )
        if org.status != OrganizationStatus.active.value:
            return PermissionEvaluationResult(
                allowed=False,
                effect="deny",
                reason="Organization is not active",
            )

        # STEP 2: Validate agent belongs to organization and check status
        agent_res = await session.execute(
            select(Agent).where(
                Agent.id == request.agent_id,
                Agent.organization_id == request.organization_id,
            )
        )
        agent = agent_res.scalar_one_or_none()
        if agent is None:
            return PermissionEvaluationResult(
                allowed=False,
                effect="deny",
                reason="Agent does not belong to organization",
            )
        if agent.status == AgentStatus.suspended.value:
            return PermissionEvaluationResult(
                allowed=False,
                effect="deny",
                reason="Agent is suspended",
            )
        if agent.status == AgentStatus.revoked.value:
            return PermissionEvaluationResult(
                allowed=False,
                effect="deny",
                reason="Agent is revoked",
            )

        # STEP 3: Validate tool belongs to organization and check status
        tool_res = await session.execute(
            select(Tool).where(
                Tool.id == request.tool_id,
                Tool.organization_id == request.organization_id,
            )
        )
        tool = tool_res.scalar_one_or_none()
        if tool is None:
            return PermissionEvaluationResult(
                allowed=False,
                effect="deny",
                reason="Tool does not belong to organization",
            )
        if tool.status == ToolStatus.suspended.value:
            return PermissionEvaluationResult(
                allowed=False,
                effect="deny",
                reason="Tool is suspended",
            )
        if tool.status == ToolStatus.revoked.value:
            return PermissionEvaluationResult(
                allowed=False,
                effect="deny",
                reason="Tool is revoked",
            )

        # STEP 4: Validate operation belongs to tool and check status
        op_res = await session.execute(
            select(ToolOperation).where(
                ToolOperation.id == request.operation_id,
                ToolOperation.tool_id == request.tool_id,
            )
        )
        operation = op_res.scalar_one_or_none()
        if operation is None:
            return PermissionEvaluationResult(
                allowed=False,
                effect="deny",
                reason="Operation does not belong to tool",
            )
        if operation.status == OperationStatus.suspended.value:
            return PermissionEvaluationResult(
                allowed=False,
                effect="deny",
                reason="Operation is suspended",
            )
        if operation.status == OperationStatus.revoked.value:
            return PermissionEvaluationResult(
                allowed=False,
                effect="deny",
                reason="Operation is revoked",
            )

        # STEP 5: Load active applicable permissions matching criteria
        query = select(Permission).where(
            Permission.organization_id == request.organization_id,
            Permission.agent_id == request.agent_id,
            Permission.tool_id == request.tool_id,
            Permission.operation_id == request.operation_id,
            Permission.environment == request.environment,
            Permission.status == PermissionStatus.active.value,
        )
        perm_res = await session.execute(query)
        permissions = list(perm_res.scalars().all())

        # STEP 6: Filter out expired permissions
        active_permissions = []
        for p in permissions:
            if p.expires_at is not None:
                exp = p.expires_at
                if exp.tzinfo is None:
                    exp = exp.replace(tzinfo=timezone.utc)
                if now > exp:
                    continue  # Expired, skip
            active_permissions.append(p)

        # STEP 7: Deny precedence: If any matching DENY exists -> return DENY
        for p in active_permissions:
            if p.effect == PermissionEffect.deny.value:
                return PermissionEvaluationResult(
                    allowed=False,
                    effect="deny",
                    reason="Explicit deny permission matched",
                    permission_id=p.id,
                )

        # STEP 8: Else if matching ALLOW exists -> return ALLOW
        for p in active_permissions:
            if p.effect == PermissionEffect.allow.value:
                return PermissionEvaluationResult(
                    allowed=True,
                    effect="allow",
                    reason="Active allow permission matched",
                    permission_id=p.id,
                )

        # STEP 9: Default Deny
        return PermissionEvaluationResult(
            allowed=False,
            effect="deny",
            reason="No matching permission found",
            permission_id=None,
        )
