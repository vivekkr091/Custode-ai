import { api } from './apiClient';
import {
  MCPServer,
  MCPTool,
  MCPDiscoveryResult,
  MCPToolCallRequest,
  MCPToolCallResult,
  MCPMetrics,
  PaginatedResponse,
} from '../types';

export const mcpApi = {
  // Servers
  listServers: (
    organizationId: string,
    params?: { status?: string; limit?: number; offset?: number }
  ) =>
    api.get<PaginatedResponse<MCPServer>>(
      `/api/v1/organizations/${organizationId}/mcp/servers`,
      { params }
    ),

  getServer: (organizationId: string, serverId: string) =>
    api.get<MCPServer>(
      `/api/v1/organizations/${organizationId}/mcp/servers/${serverId}`
    ),

  createServer: (organizationId: string, data: Partial<MCPServer>) =>
    api.post<MCPServer>(
      `/api/v1/organizations/${organizationId}/mcp/servers`,
      data
    ),

  updateServer: (
    organizationId: string,
    serverId: string,
    data: Partial<MCPServer>
  ) =>
    api.put<MCPServer>(
      `/api/v1/organizations/${organizationId}/mcp/servers/${serverId}`,
      data
    ),

  suspendServer: (organizationId: string, serverId: string) =>
    api.post<MCPServer>(
      `/api/v1/organizations/${organizationId}/mcp/servers/${serverId}/suspend`
    ),

  revokeServer: (organizationId: string, serverId: string) =>
    api.post<MCPServer>(
      `/api/v1/organizations/${organizationId}/mcp/servers/${serverId}/revoke`
    ),

  // Discovery
  discoverServerTools: (organizationId: string, serverId: string) =>
    api.post<MCPDiscoveryResult>(
      `/api/v1/organizations/${organizationId}/mcp/servers/${serverId}/discover`
    ),

  // Tools
  listTools: (
    organizationId: string,
    params?: { server_id?: string; status?: string; limit?: number; offset?: number }
  ) =>
    api.get<PaginatedResponse<MCPTool>>(
      `/api/v1/organizations/${organizationId}/mcp/tools`,
      { params }
    ),

  getTool: (organizationId: string, toolId: string) =>
    api.get<MCPTool>(
      `/api/v1/organizations/${organizationId}/mcp/tools/${toolId}`
    ),

  activateTool: (
    organizationId: string,
    toolId: string,
    data?: { risk_level?: string }
  ) =>
    api.post<MCPTool>(
      `/api/v1/organizations/${organizationId}/mcp/tools/${toolId}/activate`,
      data || {}
    ),

  suspendTool: (organizationId: string, toolId: string) =>
    api.post<MCPTool>(
      `/api/v1/organizations/${organizationId}/mcp/tools/${toolId}/suspend`
    ),

  revokeTool: (organizationId: string, toolId: string) =>
    api.post<MCPTool>(
      `/api/v1/organizations/${organizationId}/mcp/tools/${toolId}/revoke`
    ),

  callTool: (
    organizationId: string,
    toolId: string,
    data: MCPToolCallRequest,
    environment?: string
  ) =>
    api.post<MCPToolCallResult>(
      `/api/v1/organizations/${organizationId}/mcp/tools/${toolId}/call${environment ? `?environment=${environment}` : ''}`,
      data
    ),

  // Metrics
  getMetrics: (organizationId: string) =>
    api.get<MCPMetrics>(
      `/api/v1/organizations/${organizationId}/mcp/metrics`
    ),
};
