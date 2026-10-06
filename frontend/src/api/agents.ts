import { api } from './apiClient';
import { Agent, AgentCredential, AgentCredentialCreatedResponse, PaginatedResponse } from '../types';

export const agentsApi = {
  list: (orgId: string, params?: { status?: string; environment?: string; limit?: number; offset?: number }) =>
    api.get<PaginatedResponse<Agent>>(`/api/v1/organizations/${orgId}/agents`, { params }),

  get: (orgId: string, agentId: string) =>
    api.get<Agent>(`/api/v1/organizations/${orgId}/agents/${agentId}`),

  create: (orgId: string, data: { name: string; slug?: string; description?: string; environment?: string; agent_type?: string }) =>
    api.post<Agent>(`/api/v1/organizations/${orgId}/agents`, data),

  update: (orgId: string, agentId: string, data: { name?: string; description?: string; environment?: string; agent_type?: string }) =>
    api.put<Agent>(`/api/v1/organizations/${orgId}/agents/${agentId}`, data),

  suspend: (orgId: string, agentId: string) =>
    api.post<Agent>(`/api/v1/organizations/${orgId}/agents/${agentId}/suspend`),

  revoke: (orgId: string, agentId: string) =>
    api.post<Agent>(`/api/v1/organizations/${orgId}/agents/${agentId}/revoke`),

  reactivate: (orgId: string, agentId: string) =>
    api.post<Agent>(`/api/v1/organizations/${orgId}/agents/${agentId}/reactivate`),

  // Credentials
  listCredentials: (orgId: string, agentId: string) =>
    api.get<PaginatedResponse<AgentCredential>>(`/api/v1/organizations/${orgId}/agents/${agentId}/credentials`),

  createCredential: (orgId: string, agentId: string, data: { name?: string; expires_at?: string }) =>
    api.post<AgentCredentialCreatedResponse>(`/api/v1/organizations/${orgId}/agents/${agentId}/credentials`, data),

  revokeCredential: (orgId: string, agentId: string, credentialId: string) =>
    api.post<AgentCredential>(`/api/v1/organizations/${orgId}/agents/${agentId}/credentials/${credentialId}/revoke`),
};
