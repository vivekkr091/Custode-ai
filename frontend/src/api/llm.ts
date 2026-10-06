import { api } from './apiClient';
import {
  LLMInteraction,
  LLMRequest,
  LLMResponse,
  LLMMetrics,
  ToolCallExecutionRequest,
  ToolCallExecutionResponse,
  PaginatedResponse,
} from '../types';

export const llmApi = {
  chat: (
    organizationId: string,
    agentId: string,
    data: LLMRequest
  ) =>
    api.post<LLMResponse>(
      `/api/v1/organizations/${organizationId}/llm/chat?agent_id=${agentId}`,
      data
    ),

  listInteractions: (
    organizationId: string,
    params?: {
      provider?: string;
      model?: string;
      status?: string;
      limit?: number;
      offset?: number;
    }
  ) =>
    api.get<PaginatedResponse<LLMInteraction>>(
      `/api/v1/organizations/${organizationId}/llm/interactions`,
      { params }
    ),

  getInteraction: (
    organizationId: string,
    interactionId: string
  ) =>
    api.get<LLMInteraction>(
      `/api/v1/organizations/${organizationId}/llm/interactions/${interactionId}`
    ),

  getMetrics: (organizationId: string) =>
    api.get<LLMMetrics>(
      `/api/v1/organizations/${organizationId}/llm/metrics`
    ),

  executeToolCall: (
    organizationId: string,
    interactionId: string,
    agentId: string,
    data: ToolCallExecutionRequest
  ) =>
    api.post<ToolCallExecutionResponse>(
      `/api/v1/organizations/${organizationId}/llm/interactions/${interactionId}/tool-call?agent_id=${agentId}`,
      data
    ),
};
