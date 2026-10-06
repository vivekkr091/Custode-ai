import { api } from './apiClient';

export interface HealthStatus {
  status: string;
  service: string;
}

export interface DbHealthStatus {
  status: string;
  database: string;
}

export const healthApi = {
  check: () => api.get<HealthStatus>('/health'),
  checkDb: () => api.get<DbHealthStatus>('/health/db'),
};
