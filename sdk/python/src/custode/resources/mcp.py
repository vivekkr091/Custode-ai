"""MCP Security Layer resources for CUSTODE SDK."""

from __future__ import annotations

from typing import Any, Dict, Optional
from custode.models.mcp import (
    MCPServer,
    MCPServerList,
    MCPTool,
    MCPToolCallResponse,
    MCPToolList,
)
from custode.resources.base import AsyncBaseResource, BaseResource


class MCPResource(BaseResource):
    """Synchronous interface for MCP Security Layer operations."""

    def list_servers(
        self,
        organization_id: Optional[str] = None,
        limit: int = 50,
        offset: int = 0,
    ) -> MCPServerList:
        """List registered MCP servers."""
        org_id = self._resolve_org_id(organization_id)
        data = self._transport.request(
            "GET",
            f"/api/v1/organizations/{org_id}/mcp/servers",
            params={"limit": limit, "offset": offset},
        )
        items = [MCPServer.model_validate(it) for it in data.get("items", [])]
        return MCPServerList(items=items, total=data.get("total", len(items)))

    def get_server(
        self, server_id: str, organization_id: Optional[str] = None
    ) -> MCPServer:
        """Retrieve MCP server details by ID."""
        org_id = self._resolve_org_id(organization_id)
        data = self._transport.request(
            "GET", f"/api/v1/organizations/{org_id}/mcp/servers/{server_id}"
        )
        return MCPServer.model_validate(data)

    def list_tools(
        self,
        organization_id: Optional[str] = None,
        server_id: Optional[str] = None,
        limit: int = 50,
        offset: int = 0,
    ) -> MCPToolList:
        """List discovered or active MCP tools."""
        org_id = self._resolve_org_id(organization_id)
        params: Dict[str, Any] = {"limit": limit, "offset": offset}
        if server_id:
            params["server_id"] = server_id

        data = self._transport.request(
            "GET",
            f"/api/v1/organizations/{org_id}/mcp/tools",
            params=params,
        )
        items = [MCPTool.model_validate(it) for it in data.get("items", [])]
        return MCPToolList(items=items, total=data.get("total", len(items)))

    def get_tool(
        self, tool_id: str, organization_id: Optional[str] = None
    ) -> MCPTool:
        """Retrieve MCP tool details by ID."""
        org_id = self._resolve_org_id(organization_id)
        data = self._transport.request(
            "GET", f"/api/v1/organizations/{org_id}/mcp/tools/{tool_id}"
        )
        return MCPTool.model_validate(data)

    def call_tool(
        self,
        tool_id: str,
        arguments: Dict[str, Any],
        *,
        agent_id: Optional[str] = None,
        organization_id: Optional[str] = None,
        request_id: Optional[str] = None,
    ) -> MCPToolCallResponse:
        """Invoke an MCP tool call through CUSTODE control plane security arbitration."""
        org_id = self._resolve_org_id(organization_id)
        payload = {"arguments": arguments}
        if agent_id:
            payload["agent_id"] = agent_id

        data = self._transport.request(
            "POST",
            f"/api/v1/organizations/{org_id}/mcp/tools/{tool_id}/call",
            json=payload,
            request_id=request_id,
        )
        return MCPToolCallResponse.model_validate(data)


class AsyncMCPResource(AsyncBaseResource):
    """Asynchronous interface for MCP Security Layer operations."""

    async def list_servers(
        self,
        organization_id: Optional[str] = None,
        limit: int = 50,
        offset: int = 0,
    ) -> MCPServerList:
        """List registered MCP servers."""
        org_id = self._resolve_org_id(organization_id)
        data = await self._transport.request(
            "GET",
            f"/api/v1/organizations/{org_id}/mcp/servers",
            params={"limit": limit, "offset": offset},
        )
        items = [MCPServer.model_validate(it) for it in data.get("items", [])]
        return MCPServerList(items=items, total=data.get("total", len(items)))

    async def get_server(
        self, server_id: str, organization_id: Optional[str] = None
    ) -> MCPServer:
        """Retrieve MCP server details by ID."""
        org_id = self._resolve_org_id(organization_id)
        data = await self._transport.request(
            "GET", f"/api/v1/organizations/{org_id}/mcp/servers/{server_id}"
        )
        return MCPServer.model_validate(data)

    async def list_tools(
        self,
        organization_id: Optional[str] = None,
        server_id: Optional[str] = None,
        limit: int = 50,
        offset: int = 0,
    ) -> MCPToolList:
        """List discovered or active MCP tools."""
        org_id = self._resolve_org_id(organization_id)
        params: Dict[str, Any] = {"limit": limit, "offset": offset}
        if server_id:
            params["server_id"] = server_id

        data = await self._transport.request(
            "GET",
            f"/api/v1/organizations/{org_id}/mcp/tools",
            params=params,
        )
        items = [MCPTool.model_validate(it) for it in data.get("items", [])]
        return MCPToolList(items=items, total=data.get("total", len(items)))

    async def get_tool(
        self, tool_id: str, organization_id: Optional[str] = None
    ) -> MCPTool:
        """Retrieve MCP tool details by ID."""
        org_id = self._resolve_org_id(organization_id)
        data = await self._transport.request(
            "GET", f"/api/v1/organizations/{org_id}/mcp/tools/{tool_id}"
        )
        return MCPTool.model_validate(data)

    async def call_tool(
        self,
        tool_id: str,
        arguments: Dict[str, Any],
        *,
        agent_id: Optional[str] = None,
        organization_id: Optional[str] = None,
        request_id: Optional[str] = None,
    ) -> MCPToolCallResponse:
        """Invoke an MCP tool call through CUSTODE control plane security arbitration."""
        org_id = self._resolve_org_id(organization_id)
        payload = {"arguments": arguments}
        if agent_id:
            payload["agent_id"] = agent_id

        data = await self._transport.request(
            "POST",
            f"/api/v1/organizations/{org_id}/mcp/tools/{tool_id}/call",
            json=payload,
            request_id=request_id,
        )
        return MCPToolCallResponse.model_validate(data)
