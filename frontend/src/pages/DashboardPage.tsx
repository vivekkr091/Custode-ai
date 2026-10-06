import React, { useState, useEffect } from 'react';
import { useOrg } from '../context/OrgContext';
import { agentsApi } from '../api/agents';
import { toolsApi } from '../api/tools';
import { policiesApi } from '../api/policies';
import { approvalsApi } from '../api/approvals';
import { decisionsApi } from '../api/decisions';
import { executionsApi } from '../api/executions';
import { runtimeActionsApi } from '../api/runtimeActions';
import { observabilityApi } from '../api/observability';
import { findingsApi } from '../api/findings';
import { llmApi } from '../api/llm';
import { mcpApi } from '../api/mcp';
import { behaviorApi } from '../api/behavior';
import { MetricCard, SurfaceCard } from '../components/common/Card';
import { DecisionBadge, EnvironmentBadge, RiskBadge, StatusBadge } from '../components/common/Badges';
import { LoadingState, ErrorState, EmptyState } from '../components/common/FeedbackStates';
import { Button } from '../components/common/Button';
import { Link, useNavigate } from '../router/Router';
import {
  ActivityIcon,
  AlertTriangleIcon,
  BotIcon,
  CheckCircleIcon,
  ChevronRightIcon,
  CompassIcon,
  InboxIcon,
  KeyIcon,
  LockIcon,
  PlayIcon,
  ScaleIcon,
  ShieldAlertIcon,
  ShieldIcon,
  SparklesIcon,
  WrenchIcon,
} from '../components/common/Icons';
import { ApprovalRequest, Decision, Execution, LLMMetrics, MCPMetrics, BehaviorMetrics, RuntimeAction, SecurityFinding, SecurityMetrics, SecurityOverviewStats } from '../types';

export const DashboardPage: React.FC = () => {
  const { currentOrg } = useOrg();
  const navigate = useNavigate();

  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const [overview, setOverview] = useState<SecurityOverviewStats | null>(null);
  const [agentsCount, setAgentsCount] = useState(0);
  const [toolsCount, setToolsCount] = useState(0);
  const [policiesCount, setPoliciesCount] = useState(0);
  const [pendingApprovals, setPendingApprovals] = useState<ApprovalRequest[]>([]);
  const [recentDecisions, setRecentDecisions] = useState<Decision[]>([]);
  const [recentActions, setRecentActions] = useState<RuntimeAction[]>([]);
  const [recentExecutions, setRecentExecutions] = useState<Execution[]>([]);
  const [securityMetrics, setSecurityMetrics] = useState<SecurityMetrics | null>(null);
  const [recentFindings, setRecentFindings] = useState<SecurityFinding[]>([]);
  const [llmMetrics, setLlmMetrics] = useState<LLMMetrics | null>(null);
  const [mcpMetrics, setMcpMetrics] = useState<MCPMetrics | null>(null);
  const [behaviorMetrics, setBehaviorMetrics] = useState<BehaviorMetrics | null>(null);

  const loadDashboardData = async () => {
    if (!currentOrg) return;
    setLoading(true);
    setError(null);
    try {
      const [overviewRes, agentsRes, toolsRes, policiesRes, approvalsRes, decisionsRes, actionsRes, execsRes, secMetricsRes, findingsRes, llmMetricsRes, mcpMetricsRes, behaviorMetricsRes] =
        await Promise.all([
          observabilityApi.getSecurityOverview(currentOrg.id).catch(() => null),
          agentsApi.list(currentOrg.id, { limit: 1 }).catch(() => ({ total: 0, items: [] })),
          toolsApi.list(currentOrg.id, { limit: 1 }).catch(() => ({ total: 0, items: [] })),
          policiesApi.list(currentOrg.id, { limit: 1 }).catch(() => ({ total: 0, items: [] })),
          approvalsApi.list(currentOrg.id, { status: 'pending', limit: 10 }).catch(() => ({ total: 0, items: [] })),
          decisionsApi.list(currentOrg.id, { limit: 10 }).catch(() => ({ total: 0, items: [] })),
          runtimeActionsApi.list(currentOrg.id, { limit: 10 }).catch(() => ({ total: 0, items: [] })),
          executionsApi.list(currentOrg.id, { limit: 10 }).catch(() => ({ total: 0, items: [] })),
          findingsApi.getMetrics(currentOrg.id).catch(() => null),
          findingsApi.list(currentOrg.id, { limit: 5 }).catch(() => ({ items: [] })),
          llmApi.getMetrics(currentOrg.id).catch(() => null),
          mcpApi.getMetrics(currentOrg.id).catch(() => null),
          behaviorApi.getMetrics(currentOrg.id).catch(() => null),
        ]);

      setOverview(overviewRes);
      setAgentsCount(overviewRes?.agents_count ?? agentsRes.total ?? 0);
      setToolsCount(overviewRes?.tools_count ?? toolsRes.total ?? 0);
      setPoliciesCount(overviewRes?.active_policies_count ?? policiesRes.total ?? 0);
      setPendingApprovals(approvalsRes.items || []);
      setRecentDecisions(decisionsRes.items || []);
      setRecentActions(actionsRes.items || []);
      setRecentExecutions(execsRes.items || []);
      setSecurityMetrics(secMetricsRes);
      setRecentFindings(findingsRes.items || []);
      setLlmMetrics(llmMetricsRes);
      setMcpMetrics(mcpMetricsRes);
      setBehaviorMetrics(behaviorMetricsRes);
    } catch (err: any) {
      setError(err.message || 'Failed to load dashboard metrics.');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadDashboardData();
  }, [currentOrg]);

  if (loading) {
    return <LoadingState message="Aggregating security telemetry and policy posture..." />;
  }

  if (error) {
    return <ErrorState message={error} onRetry={loadDashboardData} />;
  }

  const allowCount = overview?.allowed_actions_count ?? recentDecisions.filter((d) => d.decision === 'allow').length;
  const blockCount = overview?.blocked_actions_count ?? recentDecisions.filter((d) => d.decision === 'block').length;
  const requireApprovalCount = overview?.pending_approvals_count ?? recentDecisions.filter((d) => d.decision === 'require_approval').length;

  return (
    <div className="dashboard-page">
      {/* Platform Banner */}
      <div className="dashboard-banner">
        <div className="banner-content">
          <div className="banner-tag">SECURE AGENT CONTROL PLANE</div>
          <h2 className="banner-heading">Active Security Posture & Enforcement</h2>
          <p className="banner-subtext">
            CUSTODE actively mediates and audits runtime AI agent operations across organizations,
            enforcing least-privilege permissions, contextual risk rules, and human governance.
          </p>
        </div>
      </div>

      {/* Security Overview Metrics */}
      <div className="grid-4" style={{ marginBottom: '24px' }}>
        <MetricCard
          title="ACTIVE AGENTS"
          value={agentsCount}
          subtext="Registered security identities"
          icon={<BotIcon size={20} />}
          onClick={() => navigate('/agents')}
        />
        <MetricCard
          title="CONNECTED TOOLS"
          value={toolsCount}
          subtext="Scoped callable capabilities"
          icon={<WrenchIcon size={20} />}
          onClick={() => navigate('/tools')}
        />
        <MetricCard
          title="ACTIVE POLICIES"
          value={policiesCount}
          subtext="Enforced rule specifications"
          icon={<ScaleIcon size={20} />}
          onClick={() => navigate('/policies')}
        />
        <MetricCard
          title="PENDING APPROVALS"
          value={pendingApprovals.length}
          subtext="Awaiting human reviewer"
          variant={pendingApprovals.length > 0 ? 'warning' : 'default'}
          icon={<InboxIcon size={20} />}
          onClick={() => navigate('/approvals')}
        />
      </div>

      {/* Sentinel Security Scanner, LLM Gateway & MCP Security Posture */}
      <div className="grid-4" style={{ marginBottom: '24px' }}>
        <MetricCard
          title="SECURITY FINDINGS"
          value={securityMetrics?.total_findings ?? recentFindings.length}
          subtext={`${(securityMetrics?.critical_count || 0) + (securityMetrics?.high_count || 0)} Critical/High detected`}
          variant={(securityMetrics?.critical_count || 0) > 0 ? 'danger' : (securityMetrics?.high_count || 0) > 0 ? 'warning' : 'default'}
          icon={<ShieldAlertIcon size={20} />}
          onClick={() => navigate('/findings')}
        />
        <MetricCard
          title="SENTINEL SCANS"
          value={securityMetrics?.total_scans ?? overview?.runtime_actions_count ?? 0}
          subtext="Prompt injection, PII & secrets scans"
          icon={<AlertTriangleIcon size={20} />}
          onClick={() => navigate('/findings')}
        />
        <MetricCard
          title="LLM GATEWAY"
          value={llmMetrics?.total_interactions ?? 0}
          subtext={`${llmMetrics?.blocked_count ?? 0} blocked, ${llmMetrics?.output_blocked_count ?? 0} leaks stopped`}
          variant={(llmMetrics?.blocked_count ?? 0) > 0 ? 'warning' : 'default'}
          icon={<SparklesIcon size={20} />}
          onClick={() => navigate('/llm-security')}
        />
        <MetricCard
          title="MCP SERVERS & TOOLS"
          value={mcpMetrics?.total_servers ?? 0}
          subtext={`${mcpMetrics?.active_tools ?? 0} active tools, ${mcpMetrics?.schema_drift_tools ?? 0} drift alerts`}
          variant={(mcpMetrics?.schema_drift_tools ?? 0) > 0 ? 'danger' : 'default'}
          icon={<CompassIcon size={20} />}
          onClick={() => navigate('/mcp-security')}
        />
      </div>

      {/* Behavioral Baseline & Anomaly Detection Telemetry */}
      <div className="grid-3" style={{ marginBottom: '24px' }}>
        <MetricCard
          title="BEHAVIORAL ANOMALIES"
          value={behaviorMetrics?.open_anomalies ?? 0}
          subtext={`${(behaviorMetrics?.critical_anomalies || 0) + (behaviorMetrics?.high_anomalies || 0)} Critical/High pending`}
          variant={(behaviorMetrics?.critical_anomalies || 0) > 0 ? 'danger' : (behaviorMetrics?.high_anomalies || 0) > 0 ? 'warning' : 'default'}
          icon={<ShieldAlertIcon size={20} />}
          onClick={() => navigate('/behavior-security')}
        />
        <MetricCard
          title="BASELINE MONITORING"
          value={behaviorMetrics?.established_baselines ?? 0}
          subtext={`${behaviorMetrics?.learning_baselines ?? 0} learning, ${behaviorMetrics?.cold_start_agents ?? 0} cold start`}
          icon={<ActivityIcon size={20} />}
          onClick={() => navigate('/behavior-security')}
        />
        <MetricCard
          title="DRIFT & SPIKE EVENTS"
          value={(behaviorMetrics?.action_rate_spikes ?? 0) + (behaviorMetrics?.failure_spikes ?? 0) + (behaviorMetrics?.off_hours_events ?? 0)}
          subtext="Rate spikes, failure clusters & off-hours"
          variant={((behaviorMetrics?.action_rate_spikes ?? 0) + (behaviorMetrics?.failure_spikes ?? 0)) > 0 ? 'warning' : 'default'}
          icon={<AlertTriangleIcon size={20} />}
          onClick={() => navigate('/behavior-security')}
        />
      </div>

      {/* Decision Distribution & Posture */}
      <div className="grid-2" style={{ marginBottom: '24px' }}>
        <SurfaceCard
          title="Recent Decision Disposition"
          subtitle="Real-time disposition distribution across recent actions"
          actions={<Link to="/decisions" className="btn btn-outline btn-sm">View All Decisions</Link>}
        >
          <div className="decision-stats-bar">
            <div className="stat-pill stat-allow">
              <span className="stat-num">{allowCount}</span>
              <span className="stat-lbl">ALLOW</span>
            </div>
            <div className="stat-pill stat-approval">
              <span className="stat-num">{requireApprovalCount}</span>
              <span className="stat-lbl">REQUIRE APPROVAL</span>
            </div>
            <div className="stat-pill stat-block">
              <span className="stat-num">{blockCount}</span>
              <span className="stat-lbl">BLOCK</span>
            </div>
          </div>
          <div className="subtle-note">
            Authoritative decision precedence strictly enforces: DENY &gt; REQUIRE_APPROVAL &gt; ALLOW.
          </div>
        </SurfaceCard>

        <SurfaceCard
          title="Controlled Executions"
          subtitle="Audit ledger of executed capabilities"
          actions={<Link to="/executions" className="btn btn-outline btn-sm">View Executions</Link>}
        >
          {recentExecutions.length === 0 ? (
            <div className="empty-inline-note">No actions have been executed yet.</div>
          ) : (
            <div className="mini-activity-list">
              {recentExecutions.slice(0, 4).map((ex) => (
                <div key={ex.id} className="mini-activity-row">
                  <StatusBadge status={ex.status} size="sm" />
                  <span className="font-mono" style={{ fontSize: '12px' }}>
                    Action: {ex.runtime_action_id.slice(0, 8)}...
                  </span>
                  <span className="text-muted" style={{ marginLeft: 'auto', fontSize: '11px' }}>
                    {new Date(ex.started_at || ex.created_at).toLocaleTimeString()}
                  </span>
                </div>
              ))}
            </div>
          )}
        </SurfaceCard>
      </div>

      {/* Pending Human Approvals Box (if any) */}
      {pendingApprovals.length > 0 && (
        <SurfaceCard
          title={`Action Required: ${pendingApprovals.length} Pending Approval${pendingApprovals.length > 1 ? 's' : ''}`}
          subtitle="High-risk or policy-mandated agent actions awaiting security lead review"
          actions={<Link to="/approvals" className="btn btn-primary btn-sm">Open Approvals Inbox</Link>}
        >
          <div className="table-responsive">
            <table className="data-table">
              <thead>
                <tr>
                  <th>Request ID</th>
                  <th>Reason</th>
                  <th>Risk Level</th>
                  <th>Created</th>
                  <th>Action</th>
                </tr>
              </thead>
              <tbody>
                {pendingApprovals.slice(0, 5).map((appr) => (
                  <tr key={appr.id}>
                    <td className="font-mono">{appr.id.slice(0, 8)}...</td>
                    <td>{appr.reason}</td>
                    <td>
                      <RiskBadge level={appr.decision_snapshot?.risk_level || 'HIGH'} />
                    </td>
                    <td>{new Date(appr.created_at).toLocaleTimeString()}</td>
                    <td>
                      <Link to="/approvals" className="btn btn-outline btn-sm">
                        Review
                      </Link>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </SurfaceCard>
      )}

      {/* Recent Sentinel Security Findings */}
      <SurfaceCard
        title={`Recent Security Findings (${recentFindings.length})`}
        subtitle="Prompt injection, sensitive credentials, and PII detected by Sentinel AI scanners"
        actions={<Link to="/findings" className="btn btn-outline btn-sm">All Findings</Link>}
      >
        {recentFindings.length === 0 ? (
          <div className="flex items-center gap-3 p-4 rounded bg-emerald-500/10 border border-emerald-500/30 text-emerald-400 text-xs">
            <CheckCircleIcon size={18} className="text-emerald-400 shrink-0" />
            <span>Zero active security vulnerabilities or sensitive data leaks detected across evaluated actions.</span>
          </div>
        ) : (
          <div className="table-responsive">
            <table className="data-table">
              <thead>
                <tr>
                  <th>Severity</th>
                  <th>Title</th>
                  <th>Category</th>
                  <th>Scanner</th>
                  <th>Action ID</th>
                  <th>Detected</th>
                  <th></th>
                </tr>
              </thead>
              <tbody>
                {recentFindings.slice(0, 5).map((finding) => (
                  <tr key={finding.id}>
                    <td>
                      <RiskBadge level={finding.severity} />
                    </td>
                    <td>
                      <span className="font-semibold text-text-primary text-xs">{finding.title}</span>
                    </td>
                    <td>
                      <span className="font-mono text-xs px-2 py-0.5 rounded bg-bg-subtle text-accent-primary">
                        {finding.category}
                      </span>
                    </td>
                    <td className="font-mono text-xs text-text-secondary">{finding.scanner}</td>
                    <td className="font-mono text-xs text-muted">
                      {finding.runtime_action_id ? `${finding.runtime_action_id.slice(0, 8)}...` : '—'}
                    </td>
                    <td className="text-xs text-muted">
                      {new Date(finding.created_at).toLocaleTimeString()}
                    </td>
                    <td>
                      <Link to={`/findings/${finding.id}`} className="btn btn-ghost btn-sm">
                        Inspect
                      </Link>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </SurfaceCard>

      {/* Recent Runtime Actions Log */}
      <SurfaceCard
        title="Recent Runtime Actions"
        subtitle="Chronological stream of authorized and audited agent requests"
        actions={<Link to="/runtime-actions" className="btn btn-outline btn-sm">Full Action Log</Link>}
      >
        {recentActions.length === 0 ? (
          <EmptyState
            title="No Runtime Actions Logged"
            description="When AI agents request tool invocations, their normalized RuntimeActions will appear here."
            action={
              <Link to="/agents" className="btn btn-primary btn-sm">
                View Registered Agents
              </Link>
            }
          />
        ) : (
          <div className="table-responsive">
            <table className="data-table">
              <thead>
                <tr>
                  <th>Action ID</th>
                  <th>Type</th>
                  <th>Environment</th>
                  <th>Resource</th>
                  <th>Status</th>
                  <th>Timestamp</th>
                  <th></th>
                </tr>
              </thead>
              <tbody>
                {recentActions.slice(0, 6).map((action) => (
                  <tr key={action.id}>
                    <td className="font-mono">{action.id.slice(0, 8)}...</td>
                    <td><strong>{action.action_type}</strong></td>
                    <td><EnvironmentBadge environment={action.environment} /></td>
                    <td className="font-mono text-muted">{action.resource || '—'}</td>
                    <td><StatusBadge status={action.status} /></td>
                    <td>{new Date(action.created_at).toLocaleString()}</td>
                    <td>
                      <Link to={`/runtime-actions/${action.id}`} className="btn btn-ghost btn-sm">
                        Inspect
                      </Link>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </SurfaceCard>
    </div>
  );
};
