import { api } from './apiClient';
import { Decision, PaginatedResponse } from '../types';

export const decisionsApi = {
  list: (orgId: string, params?: { limit?: number; offset?: number }) =>
    api.get<PaginatedResponse<Decision>>(`/api/v1/organizations/${orgId}/decisions`, { params }),

  get: (orgId: string, decisionId: string) =>
    api.get<Decision>(`/api/v1/organizations/${orgId}/decisions/${decisionId}`),

  getForAction: (orgId: string, actionId: string) =>
    api.get<PaginatedResponse<Decision>>(`/api/v1/organizations/${orgId}/runtime-actions/${actionId}/decisions`),

  decide: (orgId: string, actionId: string) =>
    api.post<Decision>(`/api/v1/organizations/${orgId}/runtime-actions/${actionId}/decide`),
};
