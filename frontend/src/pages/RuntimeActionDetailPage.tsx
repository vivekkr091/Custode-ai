import React, { useEffect, useState } from 'react';
import { useRouteParams, navigate } from '../router/Router';
import { useOrg } from '../context/OrgContext';
import {
  getRuntimeAction,
  evaluateDecision,
  executeAction,
  listDecisions,
  listApprovals,
  listExecutions,
  observabilityApi,
  findingsApi,
  behaviorApi,
} from '../api';
import {
  RuntimeAction,
  Decision,
  ApprovalRequest,
  Execution,
  ActionForensicsResponse,
  SecurityFinding,
  SecurityScan,
  BehavioralAnomaly,
} from '../types';
import { SurfaceCard } from '../components/common/Card';
import {
  StatusBadge,
  DecisionBadge,
  RiskBadge,
  EnvironmentBadge,
} from '../components/common/Badges';
import { Button } from '../components/common/Button';
import { CodeView } from '../components/common/CodeView';
import { ForensicTimeline } from '../components/common/ForensicTimeline';
import { LoadingState, ErrorState } from '../components/common/FeedbackStates';
import {
  AlertTriangleIcon,
  ArrowLeftIcon,
  ShieldAlertIcon,
  LayersIcon,
  KeyIcon,
  CheckCircleIcon,
  PlayIcon,
  ClockIcon,
} from '../components/common/Icons';

export const RuntimeActionDetailPage: React.FC = () => {
  const { id } = useRouteParams();
  const { activeOrg } = useOrg();

  const [action, setAction] = useState<RuntimeAction | null>(null);
  const [decisions, setDecisions] = useState<Decision[]>([]);
  const [approvals, setApprovals] = useState<ApprovalRequest[]>([]);
  const [executions, setExecutions] = useState<Execution[]>([]);
  const [scans, setScans] = useState<SecurityScan[]>([]);
  const [findings, setFindings] = useState<SecurityFinding[]>([]);
  const [anomalies, setAnomalies] = useState<BehavioralAnomaly[]>([]);
  const [forensics, setForensics] = useState<ActionForensicsResponse | null>(null);

  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [evaluating, setEvaluating] = useState(false);
  const [executing, setExecuting] = useState(false);
  const [scanning, setScanning] = useState(false);

  const fetchActionDetails = async () => {
    if (!activeOrg || !id) return;
    try {
      setLoading(true);
      setError(null);
      const [actionData, forensicsData, allDecisions, allApprovals, allExecutions, actionScansRes, actionFindingsRes] = await Promise.all([
        getRuntimeAction(activeOrg.id, id),
        observabilityApi.getActionForensics(activeOrg.id, id).catch(() => null),
        listDecisions(activeOrg.id, { runtime_action_id: id }).catch(() => []),
        listApprovals(activeOrg.id, { runtime_action_id: id }).catch(() => []),
        listExecutions(activeOrg.id, { runtime_action_id: id }).catch(() => []),
        findingsApi.listActionScans(activeOrg.id, id).catch(() => ({ items: [] })),
        findingsApi.listActionFindings(activeOrg.id, id).catch(() => ({ items: [] })),
      ]);

      setAction(actionData);
      setForensics(forensicsData);
      setDecisions(allDecisions);
      setApprovals(allApprovals);
      setExecutions(allExecutions);
      setScans(actionScansRes.items || []);
      setFindings(actionFindingsRes.items || []);

      if (actionData?.agent_id) {
        const anomRes = await behaviorApi.listAnomalies(activeOrg.id, { agent_id: actionData.agent_id }).catch(() => ({ items: [] }));
        setAnomalies((anomRes.items || []).filter((a: BehavioralAnomaly) => a.runtime_action_id === id));
      }
    } catch (err: any) {
      setError(err?.message || 'Failed to fetch runtime action details');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchActionDetails();
  }, [activeOrg?.id, id]);

  const handleRunScan = async () => {
    if (!activeOrg || !action) return;
    try {
      setScanning(true);
      await findingsApi.scanAction(activeOrg.id, action.id);
      await fetchActionDetails();
    } catch (err: any) {
      alert(`Security scan failed: ${err.message}`);
    } finally {
      setScanning(false);
    }
  };

  const handleEvaluateDecision = async () => {
    if (!activeOrg || !action) return;
    try {
      setEvaluating(true);
      await evaluateDecision(activeOrg.id, {
        runtime_action_id: action.id,
      });
      await fetchActionDetails();
    } catch (err: any) {
      alert(`Decision evaluation failed: ${err.message}`);
    } finally {
      setEvaluating(false);
    }
  };

  const handleExecuteAction = async () => {
    if (!activeOrg || !action) return;
    try {
      setExecuting(true);
      await executeAction(activeOrg.id, {
        runtime_action_id: action.id,
        context: action.context_data,
      });
      await fetchActionDetails();
    } catch (err: any) {
      alert(`Execution failed: ${err.message}`);
    } finally {
      setExecuting(false);
    }
  };

  if (loading) return <LoadingState message="Inspecting runtime action forensic trace..." />;
  if (error || !action) {
    return (
      <ErrorState
        title="Runtime Action Not Found"
        message={error || 'Could not load runtime action'}
        onRetry={fetchActionDetails}
      />
    );
  }

  const latestDecision = decisions[0] || null;
  const latestApproval = approvals[0] || null;
  const latestExecution = executions[0] || null;

  return (
    <div className="space-y-6">
      {/* Back button & Header */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-3">
          <Button
            variant="ghost"
            size="sm"
            onClick={() => navigate('/runtime-actions')}
            leftIcon={<ArrowLeftIcon className="w-4 h-4" />}
          >
            Back
          </Button>
          <div>
            <div className="flex items-center gap-2">
              <h1 className="text-xl font-bold font-mono tracking-tight text-text-primary">
                {action.id}
              </h1>
              <StatusBadge status={action.status} />
              <EnvironmentBadge environment={action.environment} />
              {action.request_id && (
                <span className="font-mono text-xs px-2 py-0.5 rounded bg-blue-500/10 text-blue-400 border border-blue-500/30">
                  REQ: {action.request_id}
                </span>
              )}
            </div>
            <p className="text-xs text-text-tertiary font-mono mt-0.5">
              Target: <span className="text-accent-primary">{action.tool_name}</span> ::{' '}
              <span className="text-text-primary font-semibold">{action.operation_name}</span> | Agent:{' '}
              {action.agent_id}
            </p>
          </div>
        </div>

        <div className="flex items-center gap-2">
          <Button
            variant="outline"
            size="sm"
            loading={scanning}
            onClick={handleRunScan}
            leftIcon={<ShieldAlertIcon className="w-4 h-4 text-warning" />}
          >
            Run Sentinel Scan
          </Button>

          {(!latestDecision || latestDecision.decision === 'require_approval') && (
            <Button
              variant="secondary"
              size="sm"
              loading={evaluating}
              onClick={handleEvaluateDecision}
              leftIcon={<ShieldAlertIcon className="w-4 h-4 text-warning" />}
            >
              Re-Evaluate Decision
            </Button>
          )}

          {latestDecision?.decision === 'allow' && !latestExecution && (
            <Button
              variant="primary"
              size="sm"
              loading={executing}
              onClick={handleExecuteAction}
              leftIcon={<PlayIcon className="w-4 h-4" />}
            >
              Trigger Execution
            </Button>
          )}
        </div>
      </div>

      {/* Authoritative Forensic Lifecycle Timeline */}
      <SurfaceCard title="Authoritative Forensic Trace & Timeline">
        <ForensicTimeline timeline={forensics?.timeline || []} />
      </SurfaceCard>

      {/* Sentinel Security Scans & Findings */}
      <SurfaceCard
        title={`Sentinel Security Scans & Findings (${findings.length} findings, ${scans.length} scans)`}
        action={
          <div className="flex items-center gap-2">
            <Button
              variant="outline"
              size="sm"
              loading={scanning}
              onClick={handleRunScan}
              leftIcon={<ShieldAlertIcon className="w-4 h-4 text-warning" />}
            >
              Run Security Scan
            </Button>
            {findings.length > 0 && (
              <Button
                variant="ghost"
                size="sm"
                onClick={() => navigate('/findings')}
              >
                All Findings
              </Button>
            )}
          </div>
        }
      >
        {scans.length === 0 && findings.length === 0 ? (
          <div className="text-center py-6 text-text-muted space-y-2">
            <AlertTriangleIcon className="w-8 h-8 mx-auto text-text-tertiary" />
            <p className="text-xs">No Sentinel scans have been executed for this runtime action yet.</p>
            <Button
              variant="secondary"
              size="sm"
              loading={scanning}
              onClick={handleRunScan}
            >
              Execute Sentinel Scan Now
            </Button>
          </div>
        ) : (
          <div className="space-y-4">
            {/* Scans summary badges */}
            {scans.length > 0 && (
              <div className="grid grid-cols-2 md:grid-cols-4 gap-3 p-3 rounded bg-bg-tertiary/40 border border-border-subtle">
                <div>
                  <div className="text-[11px] text-text-muted uppercase tracking-wider">Latest Status</div>
                  <div className="mt-1 flex items-center gap-1.5 font-mono text-xs font-semibold text-text-primary">
                    <StatusBadge status={scans[0].status} />
                  </div>
                </div>
                <div>
                  <div className="text-[11px] text-text-muted uppercase tracking-wider">Scanners Evaluated</div>
                  <div className="mt-1 font-mono text-xs text-text-secondary">
                    {scans[0].scanners_run?.length || 0} scanners
                  </div>
                </div>
                <div>
                  <div className="text-[11px] text-text-muted uppercase tracking-wider">Latency</div>
                  <div className="mt-1 font-mono text-xs text-text-secondary">
                    {scans[0].execution_time_ms ? `${scans[0].execution_time_ms} ms` : 'N/A'}
                  </div>
                </div>
                <div>
                  <div className="text-[11px] text-text-muted uppercase tracking-wider">Findings Detected</div>
                  <div className="mt-1 font-mono text-xs font-bold text-text-primary">
                    {findings.length} issues
                  </div>
                </div>
              </div>
            )}

            {findings.length === 0 ? (
              <div className="flex items-center gap-3 p-3 rounded bg-emerald-500/10 border border-emerald-500/30 text-emerald-400 text-xs">
                <CheckCircleIcon className="w-4 h-4 text-emerald-400 shrink-0" />
                <span>Zero security vulnerabilities detected. Prompt injection, PII, and credentials scans passed cleanly.</span>
              </div>
            ) : (
              <div className="space-y-3">
                {findings.map((f) => (
                  <div
                    key={f.id}
                    className="p-3.5 rounded border border-border-subtle bg-bg-tertiary/40 space-y-2"
                  >
                    <div className="flex items-center justify-between">
                      <div className="flex items-center gap-2">
                        <RiskBadge level={f.severity} />
                        <span className="text-xs font-semibold text-text-primary">{f.title}</span>
                        <span className="text-[11px] font-mono px-2 py-0.5 rounded bg-bg-subtle text-accent-primary">
                          {f.category}
                        </span>
                      </div>
                      <Button
                        variant="outline"
                        size="sm"
                        onClick={() => navigate(`/findings/${f.id}`)}
                      >
                        Inspect Finding
                      </Button>
                    </div>

                    <p className="text-xs text-text-secondary">{f.description}</p>

                    {f.evidence && (
                      <div className="text-[11px] font-mono bg-bg-secondary p-2 rounded border border-border-subtle text-text-tertiary truncate">
                        <span className="text-text-muted">Evidence: </span>
                        {f.evidence}
                      </div>
                    )}

                    {f.remediation && (
                      <div className="text-xs text-emerald-400/90 bg-emerald-950/20 p-2 rounded border border-emerald-500/20 flex items-start gap-1.5">
                        <span className="font-semibold shrink-0">Remediation:</span>
                        <span>{f.remediation}</span>
                      </div>
                    )}
                  </div>
                ))}
              </div>
            )}
          </div>
        )}
      </SurfaceCard>

      {/* Behavioral Anomaly & Baseline Drift */}
      <SurfaceCard
        title={`Behavioral Baseline & Anomaly Telemetry (${anomalies.length} anomalies detected)`}
        action={
          <Button
            variant="ghost"
            size="sm"
            onClick={() => navigate('/behavior-security')}
          >
            All Behavioral Anomalies
          </Button>
        }
      >
        {anomalies.length === 0 ? (
          <div className="flex items-center gap-3 p-3 rounded bg-emerald-500/10 border border-emerald-500/30 text-emerald-400 text-xs">
            <CheckCircleIcon className="w-4 h-4 text-emerald-400 shrink-0" />
            <span>Action conforms to established agent baseline. No rate, operational, or behavioral deviations detected.</span>
          </div>
        ) : (
          <div className="space-y-3">
            {anomalies.map((anom) => (
              <div
                key={anom.id}
                className="p-3.5 rounded border border-border-subtle bg-bg-tertiary/40 space-y-2"
              >
                <div className="flex items-center justify-between">
                  <div className="flex items-center gap-2">
                    <RiskBadge level={anom.severity} />
                    <span className="text-xs font-semibold text-text-primary">
                      {anom.anomaly_type.replace(/_/g, ' ')}
                    </span>
                    <span className="text-[11px] font-mono px-2 py-0.5 rounded bg-bg-subtle text-accent-primary">
                      {anom.feature}
                    </span>
                    <span className="text-[11px] font-mono text-text-tertiary">
                      Confidence: {Math.round(anom.confidence * 100)}%
                    </span>
                  </div>
                  <span className={`badge ${anom.status === 'RESOLVED' ? 'badge-success' : 'badge-warning'}`}>
                    {anom.status}
                  </span>
                </div>
                <p className="text-xs text-text-secondary">{anom.explanation}</p>
                {anom.deviation > 0 && (
                  <div className="text-[11px] font-mono text-text-tertiary">
                    Statistical Deviation: +{anom.deviation.toFixed(1)}σ from baseline
                  </div>
                )}
              </div>
            ))}
          </div>
        )}
      </SurfaceCard>

      {/* Action Data & Context */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        <SurfaceCard title="Payload Parameters (Normalized)">
          <CodeView
            code={action.parameters}
            language="json"
            maxHeight="320px"
          />
        </SurfaceCard>

        <SurfaceCard title="Execution Context & Metadata">
          <CodeView
            code={{
              action_id: action.id,
              organization_id: action.organization_id,
              agent_id: action.agent_id,
              tool_name: action.tool_name,
              operation_name: action.operation_name,
              environment: action.environment,
              status: action.status,
              created_at: action.created_at,
              context_data: action.context_data,
            }}
            language="json"
            maxHeight="320px"
          />
        </SurfaceCard>
      </div>

      {/* Related Decisions */}
      <SurfaceCard
        title={`Decisions (${decisions.length})`}
        action={
          <Button
            variant="ghost"
            size="sm"
            onClick={() => navigate('/decisions')}
          >
            View All Decisions
          </Button>
        }
      >
        {decisions.length === 0 ? (
          <p className="text-xs text-text-muted py-3">
            No decisions recorded for this action yet. Click "Re-Evaluate Decision" above to generate one.
          </p>
        ) : (
          <div className="space-y-3">
            {decisions.map((dec) => (
              <div
                key={dec.id}
                className="p-3 rounded border border-border-subtle bg-bg-tertiary/40 flex items-center justify-between"
              >
                <div className="space-y-1">
                  <div className="flex items-center gap-2">
                    <DecisionBadge decision={dec.decision} />
                    <RiskBadge score={dec.risk_score} level={dec.risk_tier} />
                    <span className="text-xs font-mono text-text-secondary">
                      {dec.id}
                    </span>
                  </div>
                  <p className="text-xs text-text-tertiary">
                    {dec.reason || 'Decision evaluated by CUSTODE policy engine.'}
                  </p>
                </div>
                <Button
                  variant="outline"
                  size="sm"
                  onClick={() => navigate(`/decisions/${dec.id}`)}
                >
                  Inspect Trace
                </Button>
              </div>
            ))}
          </div>
        )}
      </SurfaceCard>

      {/* Related Approvals */}
      {approvals.length > 0 && (
        <SurfaceCard title={`Approval Workflow (${approvals.length})`}>
          <div className="space-y-3">
            {approvals.map((app) => (
              <div
                key={app.id}
                className="p-3 rounded border border-border-subtle bg-bg-tertiary/40 flex items-center justify-between"
              >
                <div className="space-y-1">
                  <div className="flex items-center gap-2">
                    <StatusBadge status={app.status} />
                    <span className="text-xs font-mono text-text-secondary">{app.id}</span>
                    <span className="text-xs text-text-muted flex items-center gap-1">
                      <ClockIcon className="w-3 h-3" />
                      Expires: {app.expires_at ? new Date(app.expires_at).toLocaleString() : 'Never'}
                    </span>
                  </div>
                  {app.rejection_reason && (
                    <p className="text-xs text-danger">Rejection reason: {app.rejection_reason}</p>
                  )}
                  {app.reviewer_note && (
                    <p className="text-xs text-text-secondary">Reviewer note: {app.reviewer_note}</p>
                  )}
                </div>
                <Button
                  variant="outline"
                  size="sm"
                  onClick={() => navigate('/approvals')}
                >
                  Governance Inbox
                </Button>
              </div>
            ))}
          </div>
        </SurfaceCard>
      )}

      {/* Related Executions */}
      {executions.length > 0 && (
        <SurfaceCard title={`Execution Records (${executions.length})`}>
          <div className="space-y-3">
            {executions.map((exec) => (
              <div
                key={exec.id}
                className="p-3 rounded border border-border-subtle bg-bg-tertiary/40 flex items-center justify-between"
              >
                <div className="space-y-1">
                  <div className="flex items-center gap-2">
                    <StatusBadge status={exec.status} />
                    <span className="text-xs font-mono text-text-secondary">{exec.id}</span>
                    <span className="text-xs text-text-muted">
                      Executed at: {new Date(exec.executed_at || exec.started_at || exec.created_at).toLocaleString()}
                    </span>
                  </div>
                  {exec.error_message && (
                    <p className="text-xs text-danger font-mono">{exec.error_message}</p>
                  )}
                </div>
                <Button
                  variant="outline"
                  size="sm"
                  onClick={() => navigate(`/executions/${exec.id}`)}
                >
                  View Execution Log
                </Button>
              </div>
            ))}
          </div>
        </SurfaceCard>
      )}

      {/* Correlated Immutable Audit Events */}
      {forensics?.audit_events && forensics.audit_events.length > 0 && (
        <SurfaceCard title={`Correlated Audit Trail (${forensics.audit_events.length})`}>
          <div className="space-y-2">
            {forensics.audit_events.map((ev) => (
              <div
                key={ev.id}
                className="p-3 rounded border border-border-subtle bg-bg-tertiary/40 flex items-center justify-between"
              >
                <div className="space-y-1">
                  <div className="flex items-center gap-2">
                    <span className="font-mono text-xs font-semibold text-accent-primary">
                      {ev.event_type || ev.action}
                    </span>
                    <span className="text-xs px-2 py-0.5 rounded bg-bg-subtle text-text-muted font-mono">
                      {ev.actor_type || 'SYSTEM'}: {ev.actor_display || ev.actor_id || 'Core'}
                    </span>
                    <span className="text-xs text-text-muted">
                      {new Date(ev.created_at).toLocaleString()}
                    </span>
                  </div>
                  {ev.reason && (
                    <p className="text-xs text-text-secondary">{ev.reason}</p>
                  )}
                  {ev.request_id && (
                    <span className="text-[11px] font-mono text-text-muted">
                      Request-ID: {ev.request_id}
                    </span>
                  )}
                </div>
                <Button
                  variant="outline"
                  size="sm"
                  onClick={() => navigate('/audit')}
                >
                  Audit Ledger
                </Button>
              </div>
            ))}
          </div>
        </SurfaceCard>
      )}
    </div>
  );
};
