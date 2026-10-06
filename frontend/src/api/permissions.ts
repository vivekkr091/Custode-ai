import { api } from './apiClient';
import { PaginatedResponse, Permission } from '../types';

export const permissionsApi = {
  list: (orgId: string, params?: { agent_id?: string; tool_id?: string; operation_id?: string; status?: string; environment?: string; limit?: number; offset?: number }) =>
    api.get<PaginatedResponse<Permission>>(`/api/v1/organizations/${orgId}/permissions`, { params }),

  get: (orgId: string, permissionId: string) =>
    api.get<Permission>(`/api/v1/organizations/${orgId}/permissions/${permissionId}`),

  create: (orgId: string, data: { agent_id: string; tool_id: string; operation_id: string; environment: string; effect: 'allow' | 'deny'; expires_at?: string }) =>
    api.post<Permission>(`/api/v1/organizations/${orgId}/permissions`, data),

  suspend: (orgId: string, permissionId: string) =>
    api.post<Permission>(`/api/v1/organizations/${orgId}/permissions/${permissionId}/suspend`),

  revoke: (orgId: string, permissionId: string) =>
    api.post<Permission>(`/api/v1/organizations/${orgId}/permissions/${permissionId}/revoke`),

  evaluate: (orgId: string, data: { agent_id: string; tool_id: string; operation_id: string; environment: string }) =>
    api.post<{ allowed: boolean; effect: string; reason: string }>(`/api/v1/organizations/${orgId}/permissions/evaluate`, data),
};
