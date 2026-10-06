import { api } from './apiClient';
import { PaginatedResponse, Policy, PolicyRule, PolicyVersion } from '../types';

export const policiesApi = {
  list: (orgId: string, params?: { status?: string; enforcement_mode?: string; limit?: number; offset?: number }) =>
    api.get<PaginatedResponse<Policy>>(`/api/v1/organizations/${orgId}/policies`, { params }),

  get: (orgId: string, policyId: string) =>
    api.get<Policy>(`/api/v1/organizations/${orgId}/policies/${policyId}`),

  create: (orgId: string, data: { name: string; slug?: string; description?: string; enforcement_mode?: string }) =>
    api.post<Policy>(`/api/v1/organizations/${orgId}/policies`, data),

  update: (orgId: string, policyId: string, data: { name?: string; description?: string; enforcement_mode?: string; status?: string }) =>
    api.put<Policy>(`/api/v1/organizations/${orgId}/policies/${policyId}`, data),

  // Versions
  listVersions: (orgId: string, policyId: string, params?: { status?: string; limit?: number; offset?: number }) =>
    api.get<PaginatedResponse<PolicyVersion>>(`/api/v1/organizations/${orgId}/policies/${policyId}/versions`, { params }),

  getVersion: (orgId: string, policyId: string, versionId: string) =>
    api.get<PolicyVersion>(`/api/v1/organizations/${orgId}/policies/${policyId}/versions/${versionId}`),

  createVersion: (orgId: string, policyId: string, data: { rules: PolicyRule[] }) =>
    api.post<PolicyVersion>(`/api/v1/organizations/${orgId}/policies/${policyId}/versions`, data),

  publishVersion: (orgId: string, policyId: string, versionId: string) =>
    api.post<PolicyVersion>(`/api/v1/organizations/${orgId}/policies/${policyId}/versions/${versionId}/publish`),

  retireVersion: (orgId: string, policyId: string, versionId: string) =>
    api.post<PolicyVersion>(`/api/v1/organizations/${orgId}/policies/${policyId}/versions/${versionId}/retire`),
};
