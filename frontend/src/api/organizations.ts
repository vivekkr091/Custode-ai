import { api } from './apiClient';
import { Organization } from '../types';

export const organizationsApi = {
  list: () => api.get<Organization[]>('/api/v1/organizations'),

  get: (id: string) => api.get<Organization>(`/api/v1/organizations/${id}`),

  create: (data: { name: string; slug?: string }) =>
    api.post<Organization>('/api/v1/organizations', data),

  createMembership: (orgId: string, data: { user_id: string; role: string }) =>
    api.post(`/api/v1/organizations/${orgId}/memberships`, data),
};
