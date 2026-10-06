import { api } from './apiClient';
import { PaginatedResponse, Tool, ToolOperation } from '../types';

export const toolsApi = {
  list: (orgId: string, params?: { status?: string; environment?: string; tool_type?: string; limit?: number; offset?: number }) =>
    api.get<PaginatedResponse<Tool>>(`/api/v1/organizations/${orgId}/tools`, { params }),

  get: (orgId: string, toolId: string) =>
    api.get<Tool>(`/api/v1/organizations/${orgId}/tools/${toolId}`),

  create: (orgId: string, data: { name: string; slug?: string; description?: string; tool_type?: string; environment?: string; endpoint?: string }) =>
    api.post<Tool>(`/api/v1/organizations/${orgId}/tools`, data),

  update: (orgId: string, toolId: string, data: { name?: string; description?: string; tool_type?: string; environment?: string; endpoint?: string }) =>
    api.put<Tool>(`/api/v1/organizations/${orgId}/tools/${toolId}`, data),

  suspend: (orgId: string, toolId: string) =>
    api.post<Tool>(`/api/v1/organizations/${orgId}/tools/${toolId}/suspend`),

  revoke: (orgId: string, toolId: string) =>
    api.post<Tool>(`/api/v1/organizations/${orgId}/tools/${toolId}/revoke`),

  reactivate: (orgId: string, toolId: string) =>
    api.post<Tool>(`/api/v1/organizations/${orgId}/tools/${toolId}/reactivate`),

  // Operations
  listOperations: (orgId: string, toolId: string, params?: { status?: string; limit?: number; offset?: number }) =>
    api.get<PaginatedResponse<ToolOperation>>(`/api/v1/organizations/${orgId}/tools/${toolId}/operations`, { params }),

  getOperation: (orgId: string, toolId: string, operationId: string) =>
    api.get<ToolOperation>(`/api/v1/organizations/${orgId}/tools/${toolId}/operations/${operationId}`),

  createOperation: (orgId: string, toolId: string, data: { name: string; slug?: string; description?: string; operation_type?: string; risk_level?: string }) =>
    api.post<ToolOperation>(`/api/v1/organizations/${orgId}/tools/${toolId}/operations`, data),

  updateOperation: (orgId: string, toolId: string, operationId: string, data: { name?: string; description?: string; operation_type?: string; risk_level?: string }) =>
    api.put<ToolOperation>(`/api/v1/organizations/${orgId}/tools/${toolId}/operations/${operationId}`, data),

  suspendOperation: (orgId: string, toolId: string, operationId: string) =>
    api.post<ToolOperation>(`/api/v1/organizations/${orgId}/tools/${toolId}/operations/${operationId}/suspend`),

  revokeOperation: (orgId: string, toolId: string, operationId: string) =>
    api.post<ToolOperation>(`/api/v1/organizations/${orgId}/tools/${toolId}/operations/${operationId}/revoke`),

  reactivateOperation: (orgId: string, toolId: string, operationId: string) =>
    api.post<ToolOperation>(`/api/v1/organizations/${orgId}/tools/${toolId}/operations/${operationId}/reactivate`),
};
