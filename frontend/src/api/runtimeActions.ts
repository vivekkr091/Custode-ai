import { api } from './apiClient';
import { PaginatedResponse, RuntimeAction } from '../types';

export const runtimeActionsApi = {
  list: (orgId: string, params?: { agent_id?: string; tool_id?: string; operation_id?: string; status?: string; environment?: string; limit?: number; offset?: number }) =>
    api.get<PaginatedResponse<RuntimeAction>>(`/api/v1/organizations/${orgId}/runtime-actions`, { params }),

  get: (orgId: string, actionId: string) =>
    api.get<RuntimeAction>(`/api/v1/organizations/${orgId}/runtime-actions/${actionId}`),

  create: (orgId: string, agentId: string, data: {
    tool_id: string;
    operation_id: string;
    environment?: string;
    action_type: string;
    parameters?: Record<string, any>;
    resource?: string;
    resource_type?: string;
    amount?: number;
    currency?: string;
    ip_address?: string;
    user_agent?: string;
  }) =>
    api.post<RuntimeAction>(
      `/api/v1/organizations/${orgId}/runtime-actions`,
      data,
      agentId ? { headers: { 'X-Agent-ID': agentId } } : undefined
    ),

  transition: (orgId: string, actionId: string, data: { status: string; reason?: string }) =>
    api.post<RuntimeAction>(`/api/v1/organizations/${orgId}/runtime-actions/${actionId}/transition`, data),
};
