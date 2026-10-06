"""API endpoints for the CUSTODE MCP Security Layer."""

from typing import Any, Dict, List, Optional
import uuid
from fastapi import APIRouter, Body, Depends, Header, HTTPException, Query, status
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.db.models.membership import Membership, MembershipStatus
from app.db.models.organization import Organization, OrganizationStatus
from app.db.session import get_db_session
from app.mcp.exceptions import (
    MCPError,
    MCPInactiveError,
    MCPSchemaDriftError,
    MCPSchemaValidationError,
    MCPServerInactiveError,
    MCPServerNotFoundError,
    MCPSSRFProtectionError,
    MCPToolInactiveError,
    MCPToolNotFoundError,
    MCPTransportError,
    MCPUnsupportedTransportError,
)
from app.mcp.gateway import MCPGateway
from app.mcp.registry import MCPRegistryService
from app.mcp.schemas import (
    MCPDiscoveryResponse,
    MCPMetricsResponse,
    MCPServerCreate,
    MCPServerListResponse,
    MCPServerResponse,
    MCPServerUpdate,
    MCPToolCallRequest,
    MCPToolCallResponse,
    MCPToolListResponse,
    MCPToolResponse,
)
from app.services.agent import OrganizationNotFoundError, OrganizationSuspendedError

router = APIRouter(
    prefix="/organizations/{organization_id}/mcp",
    tags=["MCP Security Layer"],
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


class MCPToolActivateRequest(BaseModel):
    risk_level: Optional[str] = Field(None, description="Optional override risk level (low, medium, high, critical)")


# -----------------------------------------------------------------------------
# MCP SERVERS
# -----------------------------------------------------------------------------

@router.post(
    "/servers",
    response_model=MCPServerResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Register a new external MCP server boundary",
)
async def register_mcp_server(
    organization_id: uuid.UUID,
    payload: MCPServerCreate,
    session: AsyncSession = Depends(get_db_session),
    membership: Optional[Membership] = Depends(validate_tenant_access),
) -> MCPServerResponse:
    """Register an untrusted MCP server destination with SSRF and transport validation."""
    try:
        user_id = membership.user_id if membership else None
        server = await MCPRegistryService.register_server(
            session=session,
            organization_id=organization_id,
            data=payload,
            user_id=user_id,
        )
        await session.commit()
        return MCPServerResponse.model_validate(server)
    except (OrganizationNotFoundError, MCPServerNotFoundError) as exc:
        await session.rollback()
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))
    except OrganizationSuspendedError as exc:
        await session.rollback()
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc))
    except (MCPSSRFProtectionError, MCPUnsupportedTransportError, MCPSchemaValidationError) as exc:
        await session.rollback()
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))
    except Exception as exc:
        await session.rollback()
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Server registration failed: {str(exc)}")


@router.get(
    "/servers",
    response_model=MCPServerListResponse,
    summary="List registered MCP servers",
)
async def list_mcp_servers(
    organization_id: uuid.UUID,
    status: Optional[str] = Query(None),
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0),
    session: AsyncSession = Depends(get_db_session),
    _: Optional[Membership] = Depends(validate_tenant_access),
) -> MCPServerListResponse:
    """List tenant-scoped MCP server boundaries."""
    items, total = await MCPRegistryService.list_servers(
        session=session,
        organization_id=organization_id,
        status=status,
        limit=limit,
        offset=offset,
    )
    return MCPServerListResponse(
        items=[MCPServerResponse.model_validate(s) for s in items],
        total=total,
    )


@router.get(
    "/servers/{server_id}",
    response_model=MCPServerResponse,
    summary="Get single MCP server registration detail",
)
async def get_mcp_server(
    organization_id: uuid.UUID,
    server_id: uuid.UUID,
    session: AsyncSession = Depends(get_db_session),
    _: Optional[Membership] = Depends(validate_tenant_access),
) -> MCPServerResponse:
    """Retrieve an MCP server definition by ID."""
    try:
        server = await MCPRegistryService.get_server(session, organization_id, server_id)
        return MCPServerResponse.model_validate(server)
    except MCPServerNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))


@router.put(
    "/servers/{server_id}",
    response_model=MCPServerResponse,
    summary="Update an existing MCP server registration",
)
async def update_mcp_server(
    organization_id: uuid.UUID,
    server_id: uuid.UUID,
    payload: MCPServerUpdate,
    session: AsyncSession = Depends(get_db_session),
    membership: Optional[Membership] = Depends(validate_tenant_access),
) -> MCPServerResponse:
    """Update MCP server configuration and metadata."""
    try:
        user_id = membership.user_id if membership else None
        server = await MCPRegistryService.update_server(
            session=session,
            organization_id=organization_id,
            server_id=server_id,
            data=payload,
            user_id=user_id,
        )
        await session.commit()
        return MCPServerResponse.model_validate(server)
    except MCPServerNotFoundError as exc:
        await session.rollback()
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))
    except (MCPSSRFProtectionError, MCPUnsupportedTransportError) as exc:
        await session.rollback()
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))
    except Exception as exc:
        await session.rollback()
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(exc))


@router.post(
    "/servers/{server_id}/suspend",
    response_model=MCPServerResponse,
    summary="Suspend an MCP server",
)
async def suspend_mcp_server(
    organization_id: uuid.UUID,
    server_id: uuid.UUID,
    session: AsyncSession = Depends(get_db_session),
    membership: Optional[Membership] = Depends(validate_tenant_access),
) -> MCPServerResponse:
    """Suspend an MCP server boundary, halting tool execution."""
    try:
        user_id = membership.user_id if membership else None
        server = await MCPRegistryService.suspend_server(session, organization_id, server_id, user_id=user_id)
        await session.commit()
        return MCPServerResponse.model_validate(server)
    except MCPServerNotFoundError as exc:
        await session.rollback()
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))


@router.post(
    "/servers/{server_id}/revoke",
    response_model=MCPServerResponse,
    summary="Revoke an MCP server and all its discovered tools",
)
async def revoke_mcp_server(
    organization_id: uuid.UUID,
    server_id: uuid.UUID,
    session: AsyncSession = Depends(get_db_session),
    membership: Optional[Membership] = Depends(validate_tenant_access),
) -> MCPServerResponse:
    """Permanently revoke an MCP server and cascade status to all child tools."""
    try:
        user_id = membership.user_id if membership else None
        server = await MCPRegistryService.revoke_server(session, organization_id, server_id, user_id=user_id)
        await session.commit()
        return MCPServerResponse.model_validate(server)
    except MCPServerNotFoundError as exc:
        await session.rollback()
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))


# -----------------------------------------------------------------------------
# DISCOVERY
# -----------------------------------------------------------------------------

@router.post(
    "/servers/{server_id}/discover",
    response_model=MCPDiscoveryResponse,
    summary="Trigger live discovery and schema fingerprinting on an MCP server",
)
async def discover_server_tools(
    organization_id: uuid.UUID,
    server_id: uuid.UUID,
    session: AsyncSession = Depends(get_db_session),
    membership: Optional[Membership] = Depends(validate_tenant_access),
) -> MCPDiscoveryResponse:
    """Connect to untrusted MCP server, fingerprint tool schemas, detect drift, and scan descriptions."""
    try:
        user_id = membership.user_id if membership else None
        result = await MCPGateway.discover_server_tools(
            session=session,
            organization_id=organization_id,
            server_id=server_id,
            user_id=user_id,
        )
        await session.commit()
        return result
    except MCPServerNotFoundError as exc:
        await session.rollback()
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))
    except MCPServerInactiveError as exc:
        await session.rollback()
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(exc))
    except (MCPTransportError, MCPUnsupportedTransportError) as exc:
        await session.commit()  # Preserve discovery failure audit trail
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=str(exc))
    except Exception as exc:
        await session.rollback()
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Discovery failed: {str(exc)}")


# -----------------------------------------------------------------------------
# MCP TOOLS
# -----------------------------------------------------------------------------

@router.get(
    "/tools",
    response_model=MCPToolListResponse,
    summary="List discovered or active MCP tools",
)
async def list_mcp_tools(
    organization_id: uuid.UUID,
    server_id: Optional[uuid.UUID] = Query(None),
    status: Optional[str] = Query(None),
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0),
    session: AsyncSession = Depends(get_db_session),
    _: Optional[Membership] = Depends(validate_tenant_access),
) -> MCPToolListResponse:
    """List tenant-scoped MCP tools with status and server filters."""
    items, total = await MCPRegistryService.list_tools(
        session=session,
        organization_id=organization_id,
        server_id=server_id,
        status=status,
        limit=limit,
        offset=offset,
    )
    return MCPToolListResponse(
        items=[MCPToolResponse.model_validate(t) for t in items],
        total=total,
    )


@router.get(
    "/tools/{tool_id}",
    response_model=MCPToolResponse,
    summary="Get single MCP tool detail",
)
async def get_mcp_tool(
    organization_id: uuid.UUID,
    tool_id: uuid.UUID,
    session: AsyncSession = Depends(get_db_session),
    _: Optional[Membership] = Depends(validate_tenant_access),
) -> MCPToolResponse:
    """Retrieve an MCP tool definition by ID."""
    try:
        tool = await MCPRegistryService.get_tool(session, organization_id, tool_id)
        return MCPToolResponse.model_validate(tool)
    except MCPToolNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))


@router.post(
    "/tools/{tool_id}/activate",
    response_model=MCPToolResponse,
    summary="Explicitly activate an MCP tool into CUSTODE control plane",
)
async def activate_mcp_tool(
    organization_id: uuid.UUID,
    tool_id: uuid.UUID,
    payload: Optional[MCPToolActivateRequest] = Body(None),
    session: AsyncSession = Depends(get_db_session),
    membership: Optional[Membership] = Depends(validate_tenant_access),
) -> MCPToolResponse:
    """Map discovered MCP tool to CUSTODE Tool & ToolOperation and mark ACTIVE."""
    try:
        user_id = membership.user_id if membership else None
        risk = payload.risk_level if payload else None
        tool = await MCPRegistryService.activate_tool(
            session=session,
            organization_id=organization_id,
            tool_id=tool_id,
            user_id=user_id,
            risk_level=risk,
        )
        await session.commit()
        return MCPToolResponse.model_validate(tool)
    except (MCPToolNotFoundError, MCPServerNotFoundError) as exc:
        await session.rollback()
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))
    except MCPServerInactiveError as exc:
        await session.rollback()
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(exc))
    except Exception as exc:
        await session.rollback()
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(exc))


@router.post(
    "/tools/{tool_id}/suspend",
    response_model=MCPToolResponse,
    summary="Suspend an MCP tool",
)
async def suspend_mcp_tool(
    organization_id: uuid.UUID,
    tool_id: uuid.UUID,
    session: AsyncSession = Depends(get_db_session),
    membership: Optional[Membership] = Depends(validate_tenant_access),
) -> MCPToolResponse:
    """Suspend an MCP tool, preventing invocation."""
    try:
        user_id = membership.user_id if membership else None
        tool = await MCPRegistryService.suspend_tool(session, organization_id, tool_id, user_id=user_id)
        await session.commit()
        return MCPToolResponse.model_validate(tool)
    except MCPToolNotFoundError as exc:
        await session.rollback()
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))


@router.post(
    "/tools/{tool_id}/revoke",
    response_model=MCPToolResponse,
    summary="Revoke an MCP tool",
)
async def revoke_mcp_tool(
    organization_id: uuid.UUID,
    tool_id: uuid.UUID,
    session: AsyncSession = Depends(get_db_session),
    membership: Optional[Membership] = Depends(validate_tenant_access),
) -> MCPToolResponse:
    """Permanently revoke an MCP tool."""
    try:
        user_id = membership.user_id if membership else None
        tool = await MCPRegistryService.revoke_tool(session, organization_id, tool_id, user_id=user_id)
        await session.commit()
        return MCPToolResponse.model_validate(tool)
    except MCPToolNotFoundError as exc:
        await session.rollback()
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))


@router.post(
    "/tools/{tool_id}/call",
    response_model=MCPToolCallResponse,
    summary="Execute controlled MCP tool call through CUSTODE Gateway",
)
async def execute_mcp_tool_call(
    organization_id: uuid.UUID,
    tool_id: uuid.UUID,
    payload: MCPToolCallRequest,
    environment: Optional[str] = Query(None),
    x_agent_id: Optional[uuid.UUID] = Header(None, alias="X-Custode-Agent-Id"),
    session: AsyncSession = Depends(get_db_session),
    membership: Optional[Membership] = Depends(validate_tenant_access),
) -> MCPToolCallResponse:
    """Execute an MCP tool call through CUSTODE's full security and execution guard pipeline."""
    try:
        user_id = membership.user_id if membership else None
        effective_agent_id = payload.agent_id or x_agent_id
        res = await MCPGateway.execute_tool_call(
            session=session,
            organization_id=organization_id,
            tool_id=tool_id,
            arguments=payload.arguments,
            agent_id=effective_agent_id,
            user_id=user_id,
            environment=environment,
        )
        await session.commit()
        return res
    except (MCPToolNotFoundError, MCPServerNotFoundError) as exc:
        await session.rollback()
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))
    except (MCPServerInactiveError, MCPToolInactiveError) as exc:
        await session.rollback()
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(exc))
    except MCPSchemaDriftError as exc:
        await session.rollback()
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc))
    except MCPSchemaValidationError as exc:
        await session.rollback()
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))
    except MCPTransportError as exc:
        await session.commit()
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=str(exc))
    except Exception as exc:
        await session.rollback()
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Execution error: {str(exc)}")


# -----------------------------------------------------------------------------
# METRICS & TELEMETRY
# -----------------------------------------------------------------------------

@router.get(
    "/metrics",
    response_model=MCPMetricsResponse,
    summary="Get aggregated MCP security metrics and telemetry",
)
async def get_mcp_metrics(
    organization_id: uuid.UUID,
    session: AsyncSession = Depends(get_db_session),
    _: Optional[Membership] = Depends(validate_tenant_access),
) -> MCPMetricsResponse:
    """Retrieve tenant-scoped MCP security and operational metrics."""
    return await MCPRegistryService.get_metrics(session, organization_id)
