/**
 * CUSTODE Domain Types matching backend schemas.
 */

export interface Organization {
  id: string;
  name: string;
  slug: string;
  status: 'active' | 'suspended' | 'deleted';
  created_at: string;
  updated_at: string;
}

export type UserRole = 'organization_admin' | 'security_analyst' | 'developer' | 'viewer';
export type UserStatus = 'active' | 'suspended' | 'deactivated' | 'disabled';

export interface User {
  id: string;
  email: string;
  display_name: string;
  status: UserStatus;
  last_login_at?: string | null;
  created_at: string;
  updated_at: string;
}

export interface Membership {
  id: string;
  organization_id: string;
  user_id: string;
  role: UserRole;
  status: 'active' | 'suspended';
  created_at: string;
  updated_at: string;
}

export interface AuthTokenResponse {
  access_token: string;
  token_type: string;
  expires_in: number;
  user: User;
  active_organization?: Organization | null;
  organization?: Organization | null;
  role?: UserRole | null;
  memberships?: Membership[];
  available_organizations?: {
    organization: Organization;
    role: UserRole;
  }[];
}

export interface AuthenticatedUserContext {
  id?: string;
  user_id?: string;
  email: string;
  display_name: string;
  status?: string;
  last_login_at?: string | null;
  active_organization?: Organization | null;
  organization_id?: string | null;
  active_membership?: Membership | null;
  role?: UserRole | null;
  permissions?: string[];
  memberships?: Membership[] | any[];
}

export interface AuditEvent {
  id: string;
  organization_id: string;
  actor_type?: 'USER' | 'AGENT' | 'SYSTEM' | string;
  actor_id?: string | null;
  actor_display?: string | null;
  event_type?: string;
  action: string;
  resource_type?: string;
  resource_id?: string | null;
  request_id?: string | null;
  outcome: 'success' | 'denied' | 'failure' | string;
  reason?: string | null;
  ip_address?: string | null;
  user_agent?: string | null;
  metadata?: Record<string, any>;
  created_at: string;
  // Backward compatibility aliases
  user_id?: string | null;
  agent_id?: string | null;
  target_type?: string | null;
  target_id?: string | null;
}

export interface SecurityOverviewStats {
  agents_count: number;
  tools_count: number;
  active_policies_count: number;
  runtime_actions_count: number;
  pending_approvals_count: number;
  blocked_actions_count: number;
  allowed_actions_count: number;
  high_risk_actions_count: number;
  executions_count: number;
  recent_audit_events_count: number;
}

export interface TimelineEventItem {
  stage: 'IDENTITY' | 'CONTEXT' | 'RISK' | 'DECISION' | 'GOVERNANCE' | 'EXECUTION' | 'AUDIT';
  event_name: string;
  timestamp: string;
  status: 'info' | 'success' | 'warning' | 'danger';
  summary: string;
  actor?: string | null;
  details: Record<string, any>;
}

export interface ActionForensicsResponse {
  runtime_action: RuntimeAction;
  risk_assessment?: RiskAssessment | null;
  decision?: Decision | null;
  approval_request?: ApprovalRequest | null;
  execution?: Execution | null;
  audit_events: AuditEvent[];
  timeline: TimelineEventItem[];
}

export interface SearchResultItem {
  entity_type: string;
  id: string;
  title: string;
  subtitle?: string | null;
  badge?: string | null;
  link: string;
  created_at?: string | null;
}

export interface SearchResponse {
  query: string;
  total: number;
  items: SearchResultItem[];
}

export type AgentEnvironment = 'development' | 'staging' | 'production';
export type AgentStatus = 'active' | 'suspended' | 'revoked';

export interface Agent {
  id: string;
  organization_id: string;
  name: string;
  slug: string;
  description?: string | null;
  agent_type: string;
  status: AgentStatus;
  environment: AgentEnvironment;
  created_at: string;
  updated_at: string;
}

export interface AgentCredential {
  id: string;
  agent_id: string;
  name: string;
  credential_prefix: string;
  status: 'active' | 'revoked' | 'expired';
  created_at: string;
  expires_at?: string | null;
  revoked_at?: string | null;
  last_used_at?: string | null;
}

export interface AgentCredentialCreatedResponse {
  credential: AgentCredential;
  raw_token: string;
}

export type ToolType = 'api' | 'database' | 'filesystem' | 'shell' | 'mcp' | 'cloud' | 'internal' | 'custom';
export type ToolStatus = 'active' | 'suspended' | 'revoked';

export interface Tool {
  id: string;
  organization_id: string;
  name: string;
  slug: string;
  description?: string | null;
  tool_type: ToolType;
  status: ToolStatus;
  environment: AgentEnvironment;
  endpoint?: string | null;
  created_at: string;
  updated_at: string;
}

export type OperationType = 'read' | 'write' | 'execute' | 'delete' | 'admin';
export type RiskLevel = 'low' | 'medium' | 'high' | 'critical';
export type OperationStatus = 'active' | 'suspended' | 'revoked';

export interface ToolOperation {
  id: string;
  tool_id: string;
  name: string;
  slug: string;
  description?: string | null;
  operation_type: OperationType;
  risk_level: RiskLevel;
  status: OperationStatus;
  created_at: string;
  updated_at: string;
}

export type PermissionEffect = 'allow' | 'deny';
export type PermissionStatus = 'active' | 'suspended' | 'revoked';

export interface Permission {
  id: string;
  organization_id: string;
  agent_id: string;
  tool_id: string;
  operation_id: string;
  environment: string;
  effect: PermissionEffect;
  status: PermissionStatus;
  expires_at?: string | null;
  created_at: string;
  updated_at: string;
}

export type EnforcementMode = 'enforce' | 'audit' | 'disabled';
export type PolicyStatus = 'active' | 'suspended' | 'retired';

export interface PolicyRuleCondition {
  field: string;
  operator: string;
  value: any;
}

export interface PolicyRule {
  name: string;
  conditions: PolicyRuleCondition[];
  effect: 'allow' | 'deny' | 'require_approval' | 'audit';
  priority?: number;
  description?: string | null;
}

export interface PolicyVersion {
  id: string;
  policy_id: string;
  version_number: number;
  status: 'draft' | 'published' | 'retired';
  rules: PolicyRule[];
  created_at: string;
  published_at?: string | null;
  retired_at?: string | null;
}

export interface Policy {
  id: string;
  organization_id: string;
  name: string;
  slug: string;
  description?: string | null;
  status: PolicyStatus;
  enforcement_mode: EnforcementMode;
  active_version_id?: string | null;
  created_at: string;
  updated_at: string;
}

export type ActionStatus = 'pending' | 'evaluating' | 'approved' | 'denied' | 'executed' | 'failed' | 'cancelled';

export interface RuntimeAction {
  id: string;
  organization_id: string;
  agent_id: string;
  tool_id: string;
  operation_id: string;
  request_id?: string;
  environment: string;
  resource?: string | null;
  resource_type?: string | null;
  action_type: string;
  parameters: Record<string, any>;
  amount?: number | null;
  currency?: string | null;
  ip_address?: string | null;
  user_agent?: string | null;
  status: ActionStatus;
  evaluated_at?: string | null;
  completed_at?: string | null;
  created_at: string;
  tool_name?: string;
  operation_name?: string;
  context_data?: any;
}

export interface RiskFactor {
  name: string;
  score: number;
  weight: number;
  contribution: number;
  explanation: string;
}

export interface RiskAssessment {
  id: string;
  organization_id: string;
  runtime_action_id: string;
  risk_score: number;
  risk_level: string;
  baseline_score: number;
  factors: RiskFactor[] | any;
  created_at: string;
  overall_score?: number;
  risk_tier?: string;
}

export type DecisionType = 'allow' | 'block' | 'deny' | 'require_approval';

export interface Decision {
  id: string;
  organization_id: string;
  runtime_action_id: string;
  decision: DecisionType;
  reason: string;
  risk_level: string;
  risk_score: number;
  risk_tier?: string;
  permission_effect: string;
  policy_effect?: string | null;
  policy_id?: string | null;
  policy_version_id?: string | null;
  factors: any[];
  evaluation_trace: Record<string, any>;
  engine_version?: string;
  evaluated_at: string;
  created_at?: string;
}

export type ApprovalStatus = 'pending' | 'approved' | 'rejected' | 'expired' | 'cancelled';

export interface ApprovalRequest {
  id: string;
  organization_id: string;
  runtime_action_id: string;
  decision_id: string;
  requested_by_agent_id: string;
  reviewer_user_id?: string | null;
  status: ApprovalStatus;
  reason?: string;
  rejection_reason?: string | null;
  reviewer_note?: string | null;
  expires_at?: string | null;
  decision_snapshot?: Record<string, any>;
  approval_context?: Record<string, any>;
  reviewed_at?: string | null;
  created_at: string;
}

export type ExecutionStatus = 'pending' | 'running' | 'succeeded' | 'success' | 'failed' | 'blocked' | 'skipped';

export interface Execution {
  id: string;
  organization_id: string;
  runtime_action_id: string;
  agent_id: string;
  tool_id: string;
  operation_id: string;
  decision_id?: string | null;
  approval_id?: string | null;
  status: ExecutionStatus;
  result?: Record<string, any> | null;
  error_code?: string | null;
  error_message?: string | null;
  started_at?: string;
  completed_at?: string | null;
  executed_at?: string;
  created_at: string;
}

export interface PaginatedResponse<T> {
  items: T[];
  total: number;
}

export type FindingSeverity = 'LOW' | 'MEDIUM' | 'HIGH' | 'CRITICAL';

export interface SecurityFinding {
  id: string;
  organization_id: string;
  runtime_action_id: string;
  scan_id?: string | null;
  scanner: string;
  category: string;
  severity: FindingSeverity;
  confidence: number;
  title: string;
  description: string;
  evidence?: string | null;
  remediation?: string | null;
  source: string;
  finding_metadata?: Record<string, any> | null;
  created_at: string;
}

export interface SecurityScan {
  id: string;
  organization_id: string;
  runtime_action_id: string;
  scanner_count: number;
  findings_count: number;
  critical_count: number;
  high_count: number;
  medium_count: number;
  low_count: number;
  highest_severity: string;
  status: string;
  scanners_run: string[];
  execution_time_ms: number;
  error_message?: string | null;
  scan_metadata?: Record<string, any> | null;
  created_at: string;
  findings?: SecurityFinding[];
}

export interface SecurityMetrics {
  total_scans: number;
  total_findings: number;
  critical_count: number;
  high_count: number;
  medium_count: number;
  low_count: number;
  category_distribution: Record<string, number>;
  scanner_distribution: Record<string, number>;
}

export interface ChatMessage {
  role: string;
  content: string;
  name?: string | null;
}

export interface ToolCall {
  id: string;
  type: string;
  name: string;
  arguments: Record<string, any>;
}

export interface LLMUsage {
  prompt_tokens: number;
  completion_tokens: number;
  total_tokens: number;
}

export interface LLMInteraction {
  id: string;
  organization_id: string;
  agent_id: string;
  runtime_action_id?: string | null;
  request_id?: string | null;
  provider: string;
  model: string;
  environment: string;
  status: 'evaluating' | 'completed' | 'blocked' | 'output_blocked' | 'pending_approval' | 'failed';
  input_scan_status: string;
  output_scan_status: string;
  decision?: string | null;
  risk_score?: number | null;
  risk_level?: string | null;
  latency_ms: number;
  input_tokens: number;
  output_tokens: number;
  total_tokens: number;
  input_hash: string;
  output_hash?: string | null;
  sanitized_prompt_preview?: string | null;
  sanitized_output_preview?: string | null;
  interaction_metadata?: Record<string, any> | null;
  created_at: string;
  completed_at?: string | null;
  input_findings?: SecurityFinding[];
  output_findings?: SecurityFinding[];
}

export interface LLMRequest {
  messages: ChatMessage[];
  provider?: string;
  model?: string;
  system_prompt?: string | null;
  temperature?: number;
  max_tokens?: number;
  tools?: any[];
}

export interface LLMResponse {
  request_id: string;
  interaction_id: string;
  provider: string;
  model: string;
  content?: string | null;
  tool_calls: ToolCall[];
  usage: LLMUsage;
  finish_reason: string;
  latency_ms: number;
  security_status: string;
  decision: string;
  input_findings: any[];
  output_findings: any[];
  approval_id?: string | null;
  created_at: string;
}

export interface LLMMetrics {
  total_interactions: number;
  blocked_count: number;
  approval_required_count: number;
  output_blocked_count: number;
  total_input_findings: number;
  total_output_findings: number;
  provider_distribution: Record<string, number>;
  model_distribution: Record<string, number>;
  status_distribution: Record<string, number>;
  total_tokens: number;
}

export interface ToolCallExecutionRequest {
  tool_name: string;
  operation_name: string;
  parameters: Record<string, any>;
}

export interface ToolCallExecutionResponse {
  interaction_id: string;
  runtime_action_id: string;
  decision: string;
  status: string;
  result?: Record<string, any> | null;
  error?: string | null;
}

// MCP Security Layer Types
export type MCPServerType = 'REMOTE' | 'LOCAL' | 'INTERNAL' | 'THIRD_PARTY' | 'CUSTOM';
export type MCPTransportType = 'HTTP' | 'SSE' | 'STREAMABLE_HTTP' | 'MOCK' | 'STDIO';
export type MCPServerStatus = 'ACTIVE' | 'SUSPENDED' | 'REVOKED';
export type MCPTrustLevel = 'UNTRUSTED' | 'VERIFIED' | 'TRUSTED';

export interface MCPServer {
  id: string;
  organization_id: string;
  name: string;
  slug: string;
  description?: string | null;
  server_type: MCPServerType | string;
  endpoint: string;
  transport: MCPTransportType | string;
  status: MCPServerStatus | string;
  trust_level: MCPTrustLevel | string;
  environment: string;
  metadata?: Record<string, any> | null;
  created_at: string;
  updated_at: string;
  tool_count?: number;
}

export type MCPToolStatus = 'DISCOVERED' | 'ACTIVE' | 'SUSPENDED' | 'REVOKED';
export type MCPToolRiskLevel = 'low' | 'medium' | 'high' | 'critical';

export interface MCPTool {
  id: string;
  organization_id: string;
  mcp_server_id: string;
  tool_id?: string | null;
  operation_id?: string | null;
  name: string;
  slug: string;
  description?: string | null;
  input_schema: Record<string, any>;
  output_schema?: Record<string, any> | null;
  status: MCPToolStatus | string;
  risk_level: MCPToolRiskLevel | string;
  schema_hash: string;
  previous_schema_hash?: string | null;
  schema_changed: boolean;
  discovered_at: string;
  activated_at?: string | null;
  metadata?: Record<string, any> | null;
  created_at: string;
  updated_at: string;
}

export interface MCPDiscoveryResult {
  server_id: string;
  discovered_count: number;
  new_tools_count: number;
  updated_tools_count: number;
  schema_drift_count: number;
  findings_count: number;
  tools: MCPTool[];
  findings: any[];
}

export interface MCPToolCallRequest {
  arguments: Record<string, any>;
  agent_id?: string | null;
}

export interface MCPToolCallResult {
  tool_id: string;
  runtime_action_id: string;
  decision: string;
  status: string;
  result?: any;
  approval_id?: string | null;
  latency_ms: number;
  input_findings: any[];
  output_findings: any[];
  error?: string | null;
}

export interface MCPMetrics {
  total_servers: number;
  active_servers: number;
  suspended_servers: number;
  total_tools: number;
  active_tools: number;
  discovered_tools: number;
  schema_drift_tools: number;
  total_findings: number;
  total_calls: number;
  blocked_calls: number;
}

export type BaselineState = 'COLD_START' | 'LEARNING' | 'ESTABLISHED';
export type AnomalySeverity = 'LOW' | 'MEDIUM' | 'HIGH' | 'CRITICAL';
export type AnomalyStatus = 'OPEN' | 'REVIEWED' | 'RESOLVED' | 'SUPPRESSED';

export interface BehavioralAnomaly {
  id: string;
  organization_id: string;
  agent_id: string;
  runtime_action_id?: string | null;
  anomaly_type: string;
  severity: AnomalySeverity;
  confidence: number;
  score: number;
  feature: string;
  baseline_value: Record<string, any>;
  observed_value: Record<string, any>;
  deviation: number;
  explanation: string;
  evidence: any[];
  environment: string;
  status: AnomalyStatus;
  resolved_by?: string | null;
  resolved_at?: string | null;
  resolution_note?: string | null;
  created_at: string;
  updated_at: string;
}

export interface AgentBehaviorProfile {
  agent_id: string;
  environment: string;
  state: BaselineState;
  action_count: number;
  observation_window_seconds: number;
  typical_tools: string[];
  typical_operations: string[];
  average_actions_per_hour: number;
  peak_actions_per_hour: number;
  average_risk_score: number;
  operational_hours: string;
  last_observed_at?: string | null;
  recent_anomalies_count: number;
  anomaly_counts_by_severity: Record<string, number>;
}

export interface BehaviorMetrics {
  monitored_agents: number;
  established_baselines: number;
  learning_baselines: number;
  cold_start_agents: number;
  total_anomalies: number;
  open_anomalies: number;
  critical_anomalies: number;
  high_anomalies: number;
  action_rate_spikes: number;
  failure_spikes: number;
  off_hours_events: number;
  new_tool_events: number;
  action_loops: number;
}

// ==============================================================================
// Milestone 21: Integrations & Webhooks Types
// ==============================================================================

export type IntegrationProvider = 'webhook' | 'slack';
export type IntegrationStatus = 'active' | 'suspended' | 'revoked';
export type DeliveryStatus = 'pending' | 'delivered' | 'retrying' | 'failed';
export type AttemptStatus = 'success' | 'failed' | 'retryable_failure';

export interface Integration {
  id: string;
  organization_id: string;
  name: string;
  description?: string | null;
  provider: string;
  status: IntegrationStatus;
  url: string;
  secret_prefix: string;
  subscribed_events: string[];
  headers?: Record<string, string> | null;
  last_delivery_at?: string | null;
  created_at: string;
  updated_at: string;
}

export interface IntegrationCreate {
  name: string;
  description?: string;
  provider: string;
  url: string;
  subscribed_events: string[];
  headers?: Record<string, string>;
}

export interface IntegrationCreateResponse extends Integration {
  signing_secret: string;
  warning: string;
}

export interface WebhookAttempt {
  id: string;
  delivery_id: string;
  attempt_number: number;
  status: string;
  response_status_code?: number | null;
  duration_ms?: number | null;
  sanitized_error?: string | null;
  attempted_at: string;
}

export interface WebhookDelivery {
  id: string;
  organization_id: string;
  integration_id: string;
  event_id?: string | null;
  event_type: string;
  request_id?: string | null;
  delivery_status: DeliveryStatus;
  attempt_count: number;
  max_attempts: number;
  payload: Record<string, any>;
  response_status_code?: number | null;
  sanitized_response_summary?: string | null;
  next_retry_at?: string | null;
  delivered_at?: string | null;
  created_at: string;
  attempts?: WebhookAttempt[];
}

export interface SupportedEventsResponse {
  taxonomy: Record<string, { description: string; events: string[] }>;
  all_events: string[];
}


