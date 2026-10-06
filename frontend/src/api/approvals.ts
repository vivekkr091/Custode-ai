import { api } from './apiClient';
import { ApprovalRequest, PaginatedResponse } from '../types';

export const approvalsApi = {
  list: (orgId: string, params?: { status?: string; limit?: number; offset?: number }) =>
    api.get<PaginatedResponse<ApprovalRequest>>(`/api/v1/organizations/${orgId}/approvals`, { params }),

  get: (orgId: string, approvalId: string) =>
    api.get<ApprovalRequest>(`/api/v1/organizations/${orgId}/approvals/${approvalId}`),

  create: (orgId: string, actionId: string, data: { decision_id: string; reason?: string; expires_at?: string }) =>
    api.post<ApprovalRequest>(`/api/v1/organizations/${orgId}/runtime-actions/${actionId}/approval`, data),

  approve: (orgId: string, approvalId: string, userId?: string, data?: { reviewer_note?: string }) =>
    api.post<ApprovalRequest>(
       `/api/v1/organizations/${orgId}/approvals/${approvalId}/approve`,
       data || {},
       userId ? { headers: { 'X-User-ID': userId } } : undefined
     ),

  reject: (orgId: string, approvalId: string, userId?: string, data?: { rejection_reason: string }) =>
    api.post<ApprovalRequest>(
       `/api/v1/organizations/${orgId}/approvals/${approvalId}/reject`,
       data || { rejection_reason: 'Rejected' },
       userId ? { headers: { 'X-User-ID': userId } } : undefined
     ),

  cancel: (orgId: string, approvalId: string, data?: { reason?: string }) =>
    api.post<ApprovalRequest>(
      `/api/v1/organizations/${orgId}/approvals/${approvalId}/cancel`,
      data || {}
    ),
};
