import { api } from './apiClient';
import { PaginatedResponse, SecurityFinding, SecurityMetrics, SecurityScan } from '../types';

export const findingsApi = {
  list: (orgId: string, params?: {
    severity?: string;
    category?: string;
    scanner?: string;
    runtime_action_id?: string;
    limit?: number;
    offset?: number;
  }) =>
    api.get<PaginatedResponse<SecurityFinding>>(`/api/v1/organizations/${orgId}/findings`, { params }),

  get: (orgId: string, findingId: string) =>
    api.get<SecurityFinding>(`/api/v1/organizations/${orgId}/findings/${findingId}`),

  scanAction: (orgId: string, actionId: string) =>
    api.post<SecurityScan>(`/api/v1/organizations/${orgId}/runtime-actions/${actionId}/scan`),

  listActionScans: (orgId: string, actionId: string) =>
    api.get<PaginatedResponse<SecurityScan>>(`/api/v1/organizations/${orgId}/runtime-actions/${actionId}/scans`),

  listActionFindings: (orgId: string, actionId: string) =>
    api.get<PaginatedResponse<SecurityFinding>>(`/api/v1/organizations/${orgId}/runtime-actions/${actionId}/findings`),

  getMetrics: (orgId: string) =>
    api.get<SecurityMetrics>(`/api/v1/organizations/${orgId}/security/metrics`),
};
