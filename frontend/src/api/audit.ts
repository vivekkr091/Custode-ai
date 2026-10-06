import { api } from './apiClient';
import { AuditEvent, PaginatedResponse } from '../types';

export interface AuditEventListParams {
  limit?: number;
  offset?: number;
  event_type?: string;
  action?: string;
  actor_type?: string;
  actor_id?: string;
  user_id?: string;
  resource_type?: string;
  resource_id?: string;
  outcome?: string;
  request_id?: string;
  start_time?: string;
  end_time?: string;
}

export const auditApi = {
  list: (orgId: string, params?: AuditEventListParams) =>
    api.get<PaginatedResponse<AuditEvent>>(`/api/v1/organizations/${orgId}/audit-events`, { params }),

  get: (orgId: string, eventId: string) =>
    api.get<AuditEvent>(`/api/v1/organizations/${orgId}/audit-events/${eventId}`),
};
