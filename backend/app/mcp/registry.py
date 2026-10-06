"""Database registry and lifecycle services for CUSTODE MCP Security Layer."""

import re
from typing import Any, Dict, List, Optional, Tuple
import uuid

from sqlalchemy import desc, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.audit.service import AuditActorType, AuditEventType, AuditOutcome, record_event
from app.db.base import utc_now
from app.db.models.mcp_server import (
    MCPServer,
    MCPServerStatus,
    MCPServerType,
    MCPTransportType,
    MCPTrustLevel,
)
from app.db.models.mcp_tool import (
    MCPTool,
    MCPToolRiskLevel,
    MCPToolStatus,
)
from app.db.models.organization import Organization, OrganizationStatus
from app.db.models.runtime_action import RuntimeAction
from app.db.models.security_finding import SecurityFinding
from app.db.models.tool import Tool, ToolStatus, ToolType
from app.db.models.tool_operation import OperationRiskLevel, OperationStatus, OperationType, ToolOperation
from app.mcp.exceptions import (
    MCPServerInactiveError,
    MCPServerNotFoundError,
    MCPToolInactiveError,
    MCPToolNotFoundError,
    MCPUnsupportedTransportError,
)
from app.mcp.schemas import (
    MCPMetricsResponse,
    MCPServerCreate,
    MCPServerUpdate,
)
from app.mcp.validator import validate_mcp_endpoint_url
from app.services.agent import OrganizationNotFoundError, OrganizationSuspendedError


def _slugify(text: str) -> str:
    """Normalize string to slug format."""
    slug = re.sub(r"[^\w\s-]", "", text.lower()).strip()
    slug = re.sub(r"[-\s]+", "-", slug)
    return slug[:100]


from typing import Union
Union_AuditEventType = Union[AuditEventType, str]
Union_AuditOutcome = Union[AuditOutcome, str]
Union_UUID_or_str = Union[uuid.UUID, str]


async def _audit_mcp(
    session: AsyncSession,
    event_type: Union_AuditEventType,
    action: str,
    organization_id: uuid.UUID,
    user_id: Optional[uuid.UUID] = None,
    resource_type: str = "MCP_SERVER",
    resource_id: Optional[Union_UUID_or_str] = None,
    outcome: Union_AuditOutcome = AuditOutcome.SUCCESS,
    reason: Optional[str] = None,
    metadata: Optional[Dict[str, Any]] = None,
    request_id: Optional[str] = None,
) -> Any:
    meta = dict(metadata or {})
    if reason:
        meta["reason"] = reason

    return await record_event(
        session=session,
        event_type=event_type,
        action=action,
        organization_id=organization_id,
        user_id=user_id,
        actor_type=AuditActorType.USER if user_id else AuditActorType.SYSTEM,
        actor_id=str(user_id) if user_id else "custode_mcp_control_plane",
        actor_display=f"User {user_id}" if user_id else "CUSTODE MCP Control Plane",
        resource_type=resource_type,
        resource_id=resource_id,
        outcome=outcome,
        metadata=meta,
        request_id=request_id,
    )


class MCPRegistryService:
    """Authoritative registry service managing MCP servers and discovered tools."""

    @classmethod
    async def register_server(
        cls,
        session: AsyncSession,
        organization_id: uuid.UUID,
        data: MCPServerCreate,
        user_id: Optional[uuid.UUID] = None,
    ) -> MCPServer:
        """Register a new MCP server within the tenant boundary."""
        # 1. Verify organization
        org_q = select(Organization).where(Organization.id == organization_id)
        org_res = await session.execute(org_q)
        org = org_res.scalar_one_or_none()
        if org is None:
            raise OrganizationNotFoundError(organization_id)
        if org.status != OrganizationStatus.active.value:
            raise OrganizationSuspendedError(organization_id, org.status)

        # 2. Validate endpoint against SSRF
        validated_endpoint = validate_mcp_endpoint_url(data.endpoint)

        # 3. Validate transport
        transport_upper = data.transport.upper()
        if transport_upper == "STDIO":
            raise MCPUnsupportedTransportError("STDIO")
        if transport_upper not in ("HTTP", "SSE", "STREAMABLE_HTTP", "MOCK"):
            raise MCPUnsupportedTransportError(data.transport)

        # 4. Generate unique slug
        base_slug = data.slug or _slugify(data.name)
        slug = base_slug
        count = 1
        while True:
            existing = await session.execute(
                select(MCPServer).where(
                    MCPServer.organization_id == organization_id,
                    MCPServer.slug == slug,
                )
            )
            if existing.scalar_one_or_none() is None:
                break
            slug = f"{base_slug}-{count}"
            count += 1

        server = MCPServer(
            organization_id=organization_id,
            name=data.name.strip(),
            slug=slug,
            description=data.description.strip() if data.description else None,
            server_type=data.server_type.upper(),
            endpoint=validated_endpoint,
            transport=transport_upper,
            status=MCPServerStatus.ACTIVE.value,
            trust_level=data.trust_level.upper(),
            environment=data.environment.lower(),
            server_metadata=data.metadata or {},
        )
        session.add(server)
        await session.flush()
        await session.refresh(server)

        # Emit audit event
        await _audit_mcp(
            session=session,
            event_type=AuditEventType.MCP_SERVER_REGISTERED,
            action="REGISTER_MCP_SERVER",
            organization_id=organization_id,
            user_id=user_id,
            resource_type="MCP_SERVER",
            resource_id=server.id,
            outcome=AuditOutcome.SUCCESS,
            metadata={
                "server_name": server.name,
                "server_slug": server.slug,
                "endpoint": server.endpoint,
                "transport": server.transport,
                "trust_level": server.trust_level,
            },
        )

        return server

    @classmethod
    async def get_server(
        cls,
        session: AsyncSession,
        organization_id: uuid.UUID,
        server_id: uuid.UUID,
    ) -> MCPServer:
        """Fetch a single MCP server strictly within the organization tenant context."""
        query = select(MCPServer).where(
            MCPServer.id == server_id,
            MCPServer.organization_id == organization_id,
        )
        res = await session.execute(query)
        server = res.scalar_one_or_none()
        if server is None:
            raise MCPServerNotFoundError(server_id, organization_id)
        return server

    @classmethod
    async def list_servers(
        cls,
        session: AsyncSession,
        organization_id: uuid.UUID,
        status: Optional[str] = None,
        limit: int = 50,
        offset: int = 0,
    ) -> Tuple[List[MCPServer], int]:
        """List tenant-scoped MCP servers with filtering and pagination."""
        query = select(MCPServer).where(MCPServer.organization_id == organization_id)
        count_q = select(func.count(MCPServer.id)).where(MCPServer.organization_id == organization_id)

        if status:
            query = query.where(MCPServer.status == status.upper())
            count_q = count_q.where(MCPServer.status == status.upper())

        query = query.order_by(desc(MCPServer.created_at)).offset(offset).limit(limit)

        tot_res = await session.execute(count_q)
        total = tot_res.scalar() or 0

        items_res = await session.execute(query)
        items = list(items_res.scalars().all())

        return items, total

    @classmethod
    async def update_server(
        cls,
        session: AsyncSession,
        organization_id: uuid.UUID,
        server_id: uuid.UUID,
        data: MCPServerUpdate,
        user_id: Optional[uuid.UUID] = None,
    ) -> MCPServer:
        """Update an existing MCP server registration."""
        server = await cls.get_server(session, organization_id, server_id)

        if data.name is not None:
            server.name = data.name.strip()
        if data.description is not None:
            server.description = data.description.strip()
        if data.endpoint is not None:
            server.endpoint = validate_mcp_endpoint_url(data.endpoint)
        if data.transport is not None:
            tr = data.transport.upper()
            if tr == "STDIO":
                raise MCPUnsupportedTransportError("STDIO")
            server.transport = tr
        if data.trust_level is not None:
            server.trust_level = data.trust_level.upper()
        if data.environment is not None:
            server.environment = data.environment.lower()
        if data.metadata is not None:
            server.server_metadata = data.metadata

        server.updated_at = utc_now()
        await session.flush()
        await session.refresh(server)

        await _audit_mcp(
            session=session,
            event_type=AuditEventType.MCP_SERVER_UPDATED,
            action="UPDATE_MCP_SERVER",
            organization_id=organization_id,
            user_id=user_id,
            resource_type="MCP_SERVER",
            resource_id=server.id,
            outcome=AuditOutcome.SUCCESS,
            metadata={"updated_fields": list(data.model_dump(exclude_unset=True).keys())},
        )

        return server

    @classmethod
    async def suspend_server(
        cls,
        session: AsyncSession,
        organization_id: uuid.UUID,
        server_id: uuid.UUID,
        user_id: Optional[uuid.UUID] = None,
    ) -> MCPServer:
        """Suspend an MCP server."""
        server = await cls.get_server(session, organization_id, server_id)
        server.status = MCPServerStatus.SUSPENDED.value
        server.updated_at = utc_now()
        await session.flush()

        await _audit_mcp(
            session=session,
            event_type=AuditEventType.MCP_SERVER_SUSPENDED,
            action="SUSPEND_MCP_SERVER",
            organization_id=organization_id,
            user_id=user_id,
            resource_type="MCP_SERVER",
            resource_id=server.id,
            outcome=AuditOutcome.SUCCESS,
        )

        return server

    @classmethod
    async def revoke_server(
        cls,
        session: AsyncSession,
        organization_id: uuid.UUID,
        server_id: uuid.UUID,
        user_id: Optional[uuid.UUID] = None,
    ) -> MCPServer:
        """Revoke an MCP server and all its discovered tools."""
        server = await cls.get_server(session, organization_id, server_id)
        server.status = MCPServerStatus.REVOKED.value
        server.updated_at = utc_now()

        # Revoke all tools attached to this server
        tools_q = select(MCPTool).where(MCPTool.mcp_server_id == server.id)
        tools_res = await session.execute(tools_q)
        for t in tools_res.scalars().all():
            t.status = MCPToolStatus.REVOKED.value
            t.updated_at = utc_now()

        await session.flush()

        await _audit_mcp(
            session=session,
            event_type=AuditEventType.MCP_SERVER_REVOKED,
            action="REVOKE_MCP_SERVER",
            organization_id=organization_id,
            user_id=user_id,
            resource_type="MCP_SERVER",
            resource_id=server.id,
            outcome=AuditOutcome.SUCCESS,
        )

        return server

    # -------------------------------------------------------------
    # MCP Tool Management & Mapping
    # -------------------------------------------------------------

    @classmethod
    async def get_tool(
        cls,
        session: AsyncSession,
        organization_id: uuid.UUID,
        tool_id: uuid.UUID,
    ) -> MCPTool:
        """Retrieve a specific MCP tool within the organization boundary."""
        query = select(MCPTool).where(
            MCPTool.id == tool_id,
            MCPTool.organization_id == organization_id,
        )
        res = await session.execute(query)
        tool = res.scalar_one_or_none()
        if tool is None:
            raise MCPToolNotFoundError(tool_id, organization_id)
        return tool

    @classmethod
    async def list_tools(
        cls,
        session: AsyncSession,
        organization_id: uuid.UUID,
        server_id: Optional[uuid.UUID] = None,
        status: Optional[str] = None,
        limit: int = 50,
        offset: int = 0,
    ) -> Tuple[List[MCPTool], int]:
        """List tenant-scoped MCP tools with filtering."""
        query = select(MCPTool).where(MCPTool.organization_id == organization_id)
        count_q = select(func.count(MCPTool.id)).where(MCPTool.organization_id == organization_id)

        if server_id:
            query = query.where(MCPTool.mcp_server_id == server_id)
            count_q = count_q.where(MCPTool.mcp_server_id == server_id)

        if status:
            query = query.where(MCPTool.status == status.upper())
            count_q = count_q.where(MCPTool.status == status.upper())

        query = query.order_by(desc(MCPTool.discovered_at)).offset(offset).limit(limit)

        tot_res = await session.execute(count_q)
        total = tot_res.scalar() or 0

        items_res = await session.execute(query)
        items = list(items_res.scalars().all())

        return items, total

    @classmethod
    async def activate_tool(
        cls,
        session: AsyncSession,
        organization_id: uuid.UUID,
        tool_id: uuid.UUID,
        user_id: Optional[uuid.UUID] = None,
        risk_level: Optional[str] = None,
    ) -> MCPTool:
        """Activate a discovered MCP tool and map it into CUSTODE Tool/ToolOperation."""
        mcp_tool = await cls.get_tool(session, organization_id, tool_id)
        server = await cls.get_server(session, organization_id, mcp_tool.mcp_server_id)

        if server.status != MCPServerStatus.ACTIVE.value:
            raise MCPServerInactiveError(server.id, server.status)

        # 1. Map into CUSTODE Tool abstraction
        # Each MCP Server maps to a parent Tool with tool_type='mcp'
        parent_tool_q = select(Tool).where(
            Tool.organization_id == organization_id,
            Tool.slug == f"mcp-{server.slug}",
        )
        parent_tool_res = await session.execute(parent_tool_q)
        parent_tool = parent_tool_res.scalar_one_or_none()

        if parent_tool is None:
            parent_tool = Tool(
                organization_id=organization_id,
                name=f"MCP: {server.name}",
                slug=f"mcp-{server.slug}",
                description=f"CUSTODE control plane mapping for MCP Server '{server.name}'",
                tool_type=ToolType.mcp.value,
                status=ToolStatus.active.value,
                environment=server.environment,
            )
            session.add(parent_tool)
            await session.flush()

        # 2. Map into ToolOperation abstraction
        op_slug = mcp_tool.slug
        op_q = select(ToolOperation).where(
            ToolOperation.tool_id == parent_tool.id,
            ToolOperation.slug == op_slug,
        )
        op_res = await session.execute(op_q)
        operation = op_res.scalar_one_or_none()

        effective_risk = (risk_level or mcp_tool.risk_level or "medium").lower()

        if operation is None:
            operation = ToolOperation(
                tool_id=parent_tool.id,
                name=mcp_tool.name,
                slug=op_slug,
                description=mcp_tool.description,
                operation_type=OperationType.execute.value,
                risk_level=effective_risk,
                status=OperationStatus.active.value,
            )
            session.add(operation)
            await session.flush()
        else:
            operation.status = OperationStatus.active.value
            operation.risk_level = effective_risk

        # 3. Update MCP Tool status and mapping references
        mcp_tool.tool_id = parent_tool.id
        mcp_tool.operation_id = operation.id
        mcp_tool.status = MCPToolStatus.ACTIVE.value
        mcp_tool.risk_level = effective_risk
        mcp_tool.schema_changed = False  # Operator approval clears schema drift
        mcp_tool.activated_at = utc_now()
        mcp_tool.updated_at = utc_now()

        await session.flush()
        await session.refresh(mcp_tool)

        await _audit_mcp(
            session=session,
            event_type=AuditEventType.MCP_TOOL_ACTIVATED,
            action="ACTIVATE_MCP_TOOL",
            organization_id=organization_id,
            user_id=user_id,
            resource_type="MCP_TOOL",
            resource_id=mcp_tool.id,
            outcome=AuditOutcome.SUCCESS,
            metadata={
                "tool_name": mcp_tool.name,
                "tool_slug": mcp_tool.slug,
                "mapped_tool_id": str(parent_tool.id),
                "mapped_operation_id": str(operation.id),
                "schema_hash": mcp_tool.schema_hash,
            },
        )

        return mcp_tool

    @classmethod
    async def suspend_tool(
        cls,
        session: AsyncSession,
        organization_id: uuid.UUID,
        tool_id: uuid.UUID,
        user_id: Optional[uuid.UUID] = None,
    ) -> MCPTool:
        """Suspend an MCP tool."""
        tool = await cls.get_tool(session, organization_id, tool_id)
        tool.status = MCPToolStatus.SUSPENDED.value
        tool.updated_at = utc_now()

        # Also suspend mapped operation if exists
        if tool.operation_id:
            op_q = select(ToolOperation).where(ToolOperation.id == tool.operation_id)
            op_res = await session.execute(op_q)
            op = op_res.scalar_one_or_none()
            if op:
                op.status = OperationStatus.suspended.value

        await session.flush()

        await _audit_mcp(
            session=session,
            event_type=AuditEventType.MCP_TOOL_SUSPENDED,
            action="SUSPEND_MCP_TOOL",
            organization_id=organization_id,
            user_id=user_id,
            resource_type="MCP_TOOL",
            resource_id=tool.id,
            outcome=AuditOutcome.SUCCESS,
        )

        return tool

    @classmethod
    async def revoke_tool(
        cls,
        session: AsyncSession,
        organization_id: uuid.UUID,
        tool_id: uuid.UUID,
        user_id: Optional[uuid.UUID] = None,
    ) -> MCPTool:
        """Revoke an MCP tool."""
        tool = await cls.get_tool(session, organization_id, tool_id)
        tool.status = MCPToolStatus.REVOKED.value
        tool.updated_at = utc_now()

        if tool.operation_id:
            op_q = select(ToolOperation).where(ToolOperation.id == tool.operation_id)
            op_res = await session.execute(op_q)
            op = op_res.scalar_one_or_none()
            if op:
                op.status = OperationStatus.revoked.value

        await session.flush()

        await _audit_mcp(
            session=session,
            event_type=AuditEventType.MCP_TOOL_REVOKED,
            action="REVOKE_MCP_TOOL",
            organization_id=organization_id,
            user_id=user_id,
            resource_type="MCP_TOOL",
            resource_id=tool.id,
            outcome=AuditOutcome.SUCCESS,
        )

        return tool

    @classmethod
    async def get_metrics(
        cls,
        session: AsyncSession,
        organization_id: uuid.UUID,
    ) -> MCPMetricsResponse:
        """Aggregate tenant-scoped MCP metrics."""
        # Servers
        tot_servers = (await session.execute(select(func.count(MCPServer.id)).where(MCPServer.organization_id == organization_id))).scalar() or 0
        act_servers = (await session.execute(select(func.count(MCPServer.id)).where(MCPServer.organization_id == organization_id, MCPServer.status == "ACTIVE"))).scalar() or 0
        susp_servers = (await session.execute(select(func.count(MCPServer.id)).where(MCPServer.organization_id == organization_id, MCPServer.status == "SUSPENDED"))).scalar() or 0

        # Tools
        tot_tools = (await session.execute(select(func.count(MCPTool.id)).where(MCPTool.organization_id == organization_id))).scalar() or 0
        act_tools = (await session.execute(select(func.count(MCPTool.id)).where(MCPTool.organization_id == organization_id, MCPTool.status == "ACTIVE"))).scalar() or 0
        disc_tools = (await session.execute(select(func.count(MCPTool.id)).where(MCPTool.organization_id == organization_id, MCPTool.status == "DISCOVERED"))).scalar() or 0
        drift_tools = (await session.execute(select(func.count(MCPTool.id)).where(MCPTool.organization_id == organization_id, MCPTool.schema_changed == True))).scalar() or 0

        # Findings
        tot_findings = (await session.execute(select(func.count(SecurityFinding.id)).where(SecurityFinding.organization_id == organization_id, SecurityFinding.mcp_server_id.isnot(None)))).scalar() or 0

        # Tool calls (from RuntimeAction with action_type='mcp_tool_call')
        tot_calls = (await session.execute(select(func.count(RuntimeAction.id)).where(RuntimeAction.organization_id == organization_id, RuntimeAction.action_type == "mcp_tool_call"))).scalar() or 0
        blk_calls = (await session.execute(select(func.count(RuntimeAction.id)).where(RuntimeAction.organization_id == organization_id, RuntimeAction.action_type == "mcp_tool_call", RuntimeAction.status == "denied"))).scalar() or 0

        return MCPMetricsResponse(
            total_servers=tot_servers,
            active_servers=act_servers,
            suspended_servers=susp_servers,
            total_tools=tot_tools,
            active_tools=act_tools,
            discovered_tools=disc_tools,
            schema_drift_tools=drift_tools,
            total_findings=tot_findings,
            total_calls=tot_calls,
            blocked_calls=blk_calls,
        )
