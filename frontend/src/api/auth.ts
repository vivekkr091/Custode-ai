import { api, setAuthToken } from './apiClient';
import { AuthTokenResponse, AuthenticatedUserContext } from '../types';

export const authApi = {
  login: async (credentials: {
    email: string;
    password?: string;
    organization_id?: string;
  }): Promise<AuthTokenResponse> => {
    const res = await api.post<AuthTokenResponse>('/api/v1/auth/login', credentials, { skipAuth: true });
    if (res && res.access_token) {
      setAuthToken(res.access_token);
    }
    return res;
  },

  getMe: async (): Promise<AuthenticatedUserContext> => {
    return api.get<AuthenticatedUserContext>('/api/v1/auth/me');
  },

  switchOrganization: async (organizationId: string): Promise<AuthTokenResponse> => {
    const res = await api.post<AuthTokenResponse>('/api/v1/auth/switch-organization', {
      organization_id: organizationId,
    });
    if (res && res.access_token) {
      setAuthToken(res.access_token);
    }
    return res;
  },

  logout: async (): Promise<{ message: string }> => {
    try {
      const res = await api.post<{ message: string }>('/api/v1/auth/logout', {});
      return res;
    } finally {
      setAuthToken(null);
    }
  },
};
