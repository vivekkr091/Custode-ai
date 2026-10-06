export * from './apiClient';
export * from './organizations';
export * from './agents';
export * from './tools';
export * from './permissions';
export * from './policies';
export * from './runtimeActions';
export * from './risk';
export * from './decisions';
export * from './approvals';
export * from './executions';
export * from './auth';
export * from './audit';
export * from './observability';
export * from './health';
export * from './seeder';
export * from './findings';
export * from './llm';
export * from './mcp';
export * from './behavior';
export * from './integrations';

// Convenient named aliases used across UI components
import { organizationsApi } from './organizations';
import { agentsApi } from './agents';
import { toolsApi } from './tools';
import { permissionsApi } from './permissions';
import { policiesApi } from './policies';
import { runtimeActionsApi } from './runtimeActions';
import { riskApi } from './risk';
import { decisionsApi } from './decisions';
import { approvalsApi } from './approvals';
import { executionsApi } from './executions';
import { observabilityApi } from './observability';
import { healthApi } from './health';
import { seedDemonstrationData } from './seeder';
import { mcpApi } from './mcp';

export const checkBackendHealth = healthApi.check;
export const seedSampleScenario = seedDemonstrationData;

// Runtime Actions helpers
export const listRuntimeActions = async (orgId: string, params?: any) => {
  const res = await runtimeActionsApi.list(orgId, params);
  return res.items || [];
};

export const getRuntimeAction = async (orgId: string, actionId: string) => {
  return runtimeActionsApi.get(orgId, actionId);
};

// Risk Engine helpers
export const assessRisk = async (orgId: string, data: { runtime_action_id: string }) => {
  return riskApi.assess(orgId, data.runtime_action_id);
};

// Decisions helpers
export const listDecisions = async (orgId: string, params?: { runtime_action_id?: string; limit?: number }) => {
  if (params?.runtime_action_id) {
    const res = await decisionsApi.getForAction(orgId, params.runtime_action_id);
    return res.items || [];
  }
  const res = await decisionsApi.list(orgId, params);
  return res.items || [];
};

export const getDecision = async (orgId: string, decisionId: string) => {
  return decisionsApi.get(orgId, decisionId);
};

export const evaluateDecision = async (orgId: string, data: { runtime_action_id: string }) => {
  return decisionsApi.decide(orgId, data.runtime_action_id);
};

// Approvals helpers
export const listApprovals = async (orgId: string, params?: any) => {
  const res = await approvalsApi.list(orgId, params);
  return res.items || [];
};

export const getApproval = async (orgId: string, approvalId: string) => {
  return approvalsApi.get(orgId, approvalId);
};

export const approveRequest = async (orgId: string, approvalId: string, data?: { reviewer_note?: string }) => {
  const savedUserId = localStorage.getItem('custode_admin_user_id') || '00000000-0000-0000-0000-000000000000';
  return approvalsApi.approve(orgId, approvalId, savedUserId, data);
};

export const rejectRequest = async (orgId: string, approvalId: string, data: { rejection_reason: string }) => {
  const savedUserId = localStorage.getItem('custode_admin_user_id') || '00000000-0000-0000-0000-000000000000';
  return approvalsApi.reject(orgId, approvalId, savedUserId, data);
};

// Execution helpers
export const listExecutions = async (orgId: string, params?: any) => {
  const res = await executionsApi.list(orgId, params);
  return res.items || [];
};

export const getExecution = async (orgId: string, executionId: string) => {
  return executionsApi.get(orgId, executionId);
};

export const executeAction = async (orgId: string, data: { runtime_action_id: string; context?: any }) => {
  return executionsApi.execute(orgId, data.runtime_action_id, { execution_parameters: data.context });
};
