import { api } from './apiClient';
import { ActionForensicsResponse, SearchResponse, SecurityOverviewStats } from '../types';

export const observabilityApi = {
  getSecurityOverview: (orgId: string) =>
    api.get<SecurityOverviewStats>(`/api/v1/organizations/${orgId}/security-overview`),

  getActionForensics: (orgId: string, actionId: string) =>
    api.get<ActionForensicsResponse>(`/api/v1/organizations/${orgId}/runtime-actions/${actionId}/forensics`),

  search: (orgId: string, query: string, limit?: number) =>
    api.get<SearchResponse>(`/api/v1/organizations/${orgId}/search`, {
      params: { q: query, limit },
    }),
};
