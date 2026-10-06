import { api } from './apiClient';
import { PaginatedResponse, RiskAssessment } from '../types';

export const riskApi = {
  list: (orgId: string, params?: { risk_level?: string; limit?: number; offset?: number }) =>
    api.get<PaginatedResponse<RiskAssessment>>(`/api/v1/organizations/${orgId}/risk-assessments`, { params }),

  get: (orgId: string, riskId: string) =>
    api.get<RiskAssessment>(`/api/v1/organizations/${orgId}/risk-assessments/${riskId}`),

  getForAction: (orgId: string, actionId: string) =>
    api.get<PaginatedResponse<RiskAssessment>>(`/api/v1/organizations/${orgId}/runtime-actions/${actionId}/risk-assessments`),

  assess: (orgId: string, actionId: string) =>
    api.post<RiskAssessment>(`/api/v1/organizations/${orgId}/runtime-actions/${actionId}/risk-assess`),
};
