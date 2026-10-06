import { api } from './apiClient';
import {
  AgentBehaviorProfile,
  BehavioralAnomaly,
  BehaviorMetrics,
  PaginatedResponse,
} from '../types';

export const behaviorApi = {
  getProfile: (
    organizationId: string,
    agentId: string,
    environment: string = 'production'
  ) =>
    api.get<AgentBehaviorProfile>(
      `/api/v1/organizations/${organizationId}/agents/${agentId}/behavior`,
      { params: { environment } }
    ),

  listAnomalies: (
    organizationId: string,
    params?: {
      agent_id?: string;
      status?: string;
      severity?: string;
      anomaly_type?: string;
      limit?: number;
      offset?: number;
    }
  ) =>
    api.get<PaginatedResponse<BehavioralAnomaly>>(
      `/api/v1/organizations/${organizationId}/behavior/anomalies`,
      { params }
    ),

  getAnomaly: (organizationId: string, anomalyId: string) =>
    api.get<BehavioralAnomaly>(
      `/api/v1/organizations/${organizationId}/behavior/anomalies/${anomalyId}`
    ),

  resolveAnomaly: (
    organizationId: string,
    anomalyId: string,
    note?: string
  ) =>
    api.post<BehavioralAnomaly>(
      `/api/v1/organizations/${organizationId}/behavior/anomalies/${anomalyId}/resolve`,
      { note }
    ),

  suppressAnomaly: (
    organizationId: string,
    anomalyId: string,
    note?: string
  ) =>
    api.post<BehavioralAnomaly>(
      `/api/v1/organizations/${organizationId}/behavior/anomalies/${anomalyId}/suppress`,
      { note }
    ),

  getMetrics: (organizationId: string) =>
    api.get<BehaviorMetrics>(
      `/api/v1/organizations/${organizationId}/behavior/metrics`
    ),
};
