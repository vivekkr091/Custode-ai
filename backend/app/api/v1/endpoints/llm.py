"""API endpoints for the CUSTODE LLM Security Gateway."""

from typing import Any, Dict, List, Optional
import uuid
from fastapi import APIRouter, Depends, Header, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.db.models.agent import Agent, AgentStatus
from app.db.models.llm_interaction import LLMInteraction
from app.db.models.membership import Membership, MembershipStatus
from app.db.models.organization import Organization, OrganizationStatus
from app.db.models.security_finding import SecurityFinding
from app.db.session import get_db_session
from app.llm.exceptions import (
    LLMApprovalRequiredError,
    LLMError,
    LLMModelNotAllowedError,
    LLMOutputSecurityError,
    LLMProviderError,
    LLMProviderNotFoundError,
    LLMRateLimitError,
    LLMSecurityBlockError,
    LLMSSRFProtectionError,
    LLMToolCallSecurityError,
)
from app.llm.gateway import llm_gateway
from app.llm.schemas import (
    LLMInteractionResponse,
    LLMMetricsResponse,
    LLMRequest,
    LLMResponse,
    ToolCallExecutionRequest,
    ToolCallExecutionResponse,
)
from app.services.agent import OrganizationNotFoundError, OrganizationSuspendedError
from app.services.permission import InactiveResourceError, ResourceHierarchyError

router = APIRouter(
    prefix="/organizations/{organization_id}/llm",
    tags=["LLM Security Gateway"],
)


async def validate_tenant_access(
    organization_id: uuid.UUID,
    authorization: Optional[str] = Header(None, alias="Authorization"),
    x_user_id: Optional[uuid.UUID] = Header(None, alias="X-User-ID"),
    session: AsyncSession = Depends(get_db_session),
) -> Optional[Membership]:
    """Validate organization status and membership context."""
    org_q = select(Organization).where(Organization.id == organization_id)
    org_res = await session.execute(org_q)
    org = org_res.scalar_one_or_none()
    if org is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Organization '{organization_id}' not found",
        )
    if org.status != OrganizationStatus.active.value:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Organization '{organization_id}' is suspended or inactive",
        )

    if x_user_id:
        mem_q = select(Membership).where(
            Membership.organization_id == organization_id,
            Membership.user_id == x_user_id,
            Membership.status == MembershipStatus.active.value,
        )
        mem_res = await session.execute(mem_q)
        mem = mem_res.scalar_one_or_none()
        if mem is None:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"User '{x_user_id}' does not have active membership in organization '{organization_id}'",
            )
        return mem

    return None


@router.post(
    "/chat",
    response_model=LLMResponse,
    summary="Execute secure LLM chat completion through CUSTODE Gateway",
)
async def chat_completion(
    organization_id: uuid.UUID,
    payload: LLMRequest,
    agent_id: Optional[uuid.UUID] = Query(None),
    x_agent_id: Optional[uuid.UUID] = Header(None, alias="X-Custode-Agent-Id"),
    session: AsyncSession = Depends(get_db_session),
    membership: Optional[Membership] = Depends(validate_tenant_access),
) -> LLMResponse:
    """Execute a chat completion through the CUSTODE LLM Gateway.

    Applies the full security control plane:
    - Inbound prompt injection, secrets, PII scanning
    - Permission, Policy, and Risk assessment
    - Decision arbitration (ALLOW / BLOCK / REQUIRE_APPROVAL)
    - Outbound model output secrets and PII scanning
    - Secure content hashing and zero permanent raw prompt retention
    """
    effective_agent_id = agent_id or x_agent_id

    # If agent_id not provided, resolve or create active agent for the tenant
    if not effective_agent_id:
        agent_q = select(Agent).where(
            Agent.organization_id == organization_id,
            Agent.status == AgentStatus.active.value,
        )
        agent_res = await session.execute(agent_q)
        agent = agent_res.scalars().first()
        if agent is None:
            # Auto-provision a default gateway agent for the organization
            agent = Agent(
                organization_id=organization_id,
                name="Default LLM Assistant Agent",
                slug="default-llm-agent",
                description="Default agent identity for LLM Gateway interactions",
                agent_type="assistant",
                status=AgentStatus.active.value,
                environment="development",
            )
            session.add(agent)
            await session.flush()
        effective_agent_id = agent.id

    try:
        user_id = membership.user_id if membership else None
        response = await llm_gateway.chat(
            session=session,
            organization_id=organization_id,
            agent_id=effective_agent_id,
            request=payload,
            user_id=user_id,
        )
        await session.commit()
        return response
    except (OrganizationNotFoundError, ResourceHierarchyError, InactiveResourceError) as exc:
        await session.rollback()
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))
    except (LLMProviderNotFoundError, LLMModelNotAllowedError) as exc:
        await session.rollback()
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))
    except LLMSSRFProtectionError as exc:
        await session.rollback()
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(exc))
    except LLMRateLimitError as exc:
        await session.rollback()
        raise HTTPException(status_code=status.HTTP_429_TOO_MANY_REQUESTS, detail=str(exc))
    except LLMProviderError as exc:
        await session.commit()  # Preserve failed interaction record
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=str(exc))
    except Exception as exc:
        await session.rollback()
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"LLM Gateway error: {str(exc)}")


@router.get(
    "/interactions",
    summary="List tenant-scoped LLM interactions",
)
async def list_interactions(
    organization_id: uuid.UUID,
    provider: Optional[str] = Query(None),
    model: Optional[str] = Query(None),
    status: Optional[str] = Query(None),
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0),
    session: AsyncSession = Depends(get_db_session),
    _: Optional[Membership] = Depends(validate_tenant_access),
) -> Dict[str, Any]:
    """Retrieve historical LLM interactions for forensic auditing and governance."""
    items, total = await llm_gateway.list_interactions(
        session=session,
        organization_id=organization_id,
        provider=provider,
        model=model,
        status=status,
        limit=limit,
        offset=offset,
    )
    return {
        "items": [LLMInteractionResponse.model_validate(item) for item in items],
        "total": total,
        "limit": limit,
        "offset": offset,
    }


@router.get(
    "/interactions/{interaction_id}",
    summary="Get single LLM interaction forensic detail",
)
async def get_interaction_detail(
    organization_id: uuid.UUID,
    interaction_id: uuid.UUID,
    session: AsyncSession = Depends(get_db_session),
    _: Optional[Membership] = Depends(validate_tenant_access),
) -> Dict[str, Any]:
    """Retrieve detailed forensic trace for a specific LLM interaction, including findings."""
    interaction = await llm_gateway.get_interaction(session, organization_id, interaction_id)
    if not interaction:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"LLM interaction '{interaction_id}' not found in organization '{organization_id}'",
        )

    # Fetch associated security findings
    findings_q = select(SecurityFinding).where(
        SecurityFinding.organization_id == organization_id,
        SecurityFinding.interaction_id == interaction.id,
    )
    findings_res = await session.execute(findings_q)
    findings = list(findings_res.scalars().all())

    serialized_findings = [
        {
            "id": str(f.id),
            "scanner": f.scanner,
            "category": f.category,
            "severity": f.severity,
            "scan_direction": f.scan_direction,
            "confidence": f.confidence,
            "title": f.title,
            "description": f.description,
            "evidence": f.evidence,
            "remediation": f.remediation,
            "created_at": f.created_at,
        }
        for f in findings
    ]

    return {
        "interaction": LLMInteractionResponse.model_validate(interaction),
        "findings": serialized_findings,
    }


@router.post(
    "/interactions/{interaction_id}/tool-call",
    response_model=ToolCallExecutionResponse,
    summary="Execute validated untrusted LLM tool call",
)
async def execute_tool_call(
    organization_id: uuid.UUID,
    interaction_id: uuid.UUID,
    payload: ToolCallExecutionRequest,
    agent_id: Optional[uuid.UUID] = Query(None),
    session: AsyncSession = Depends(get_db_session),
    membership: Optional[Membership] = Depends(validate_tenant_access),
) -> ToolCallExecutionResponse:
    """Safely execute an LLM-generated tool call through the CUSTODE control plane.

    Verifies registered tool existence, operation permissions, policies, risk, and decisions.
    Never executes arbitrary commands or unregistered code.
    """
    interaction = await llm_gateway.get_interaction(session, organization_id, interaction_id)
    if not interaction:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"LLM interaction '{interaction_id}' not found in organization '{organization_id}'",
        )

    effective_agent_id = agent_id or interaction.agent_id

    try:
        result = await llm_gateway.execute_tool_call(
            session=session,
            organization_id=organization_id,
            agent_id=effective_agent_id,
            interaction_id=interaction_id,
            data=payload,
        )
        await session.commit()
        return result
    except LLMToolCallSecurityError as exc:
        await session.rollback()
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))
    except Exception as exc:
        await session.rollback()
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(exc))


@router.get(
    "/metrics",
    response_model=LLMMetricsResponse,
    summary="Get aggregated LLM security metrics",
)
async def get_llm_metrics(
    organization_id: uuid.UUID,
    session: AsyncSession = Depends(get_db_session),
    _: Optional[Membership] = Depends(validate_tenant_access),
) -> LLMMetricsResponse:
    """Retrieve real-time aggregated LLM gateway metrics for the organization."""
    return await llm_gateway.get_metrics(session, organization_id)
