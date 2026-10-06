import { api } from './apiClient';
import { Execution, PaginatedResponse } from '../types';

export const executionsApi = {
  list: (orgId: string, params?: { runtime_action_id?: string; agent_id?: string; tool_id?: string; status?: string; limit?: number; offset?: number }) =>
    api.get<PaginatedResponse<Execution>>(`/api/v1/organizations/${orgId}/executions`, { params }),

  get: (orgId: string, executionId: string) =>
    api.get<Execution>(`/api/v1/organizations/${orgId}/executions/${executionId}`),

  execute: (orgId: string, actionId: string, data?: any) =>
    api.post<Execution>(`/api/v1/organizations/${orgId}/runtime-actions/${actionId}/execute`, data || {}),
};
