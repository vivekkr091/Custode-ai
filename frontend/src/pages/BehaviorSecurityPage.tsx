import React, { useState, useEffect } from 'react';
import { useOrg } from '../context/OrgContext';
import { behaviorApi } from '../api/behavior';
import {
  BehavioralAnomaly,
  BehaviorMetrics,
  AnomalySeverity,
  AnomalyStatus,
} from '../types';
import { Link } from '../router/Router';
import { Card } from '../components/common/Card';
import { Button } from '../components/common/Button';
import { EmptyState, LoadingState } from '../components/common/FeedbackStates';
import {
  ActivityIcon,
  AlertTriangleIcon,
  CheckCircleIcon,
  ClockIcon,
  ShieldAlertIcon,
  TerminalIcon,
  XCircleIcon,
  XIcon,
} from '../components/common/Icons';

export const BehaviorSecurityPage: React.FC = () => {
  const { currentOrg } = useOrg();
  const orgId = currentOrg?.id;

  const [anomalies, setAnomalies] = useState<BehavioralAnomaly[]>([]);
  const [metrics, setMetrics] = useState<BehaviorMetrics | null>(null);
  const [loading, setLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);

  // Filters
  const [severityFilter, setSeverityFilter] = useState<string>('');
  const [statusFilter, setStatusFilter] = useState<string>('');
  const [typeFilter, setTypeFilter] = useState<string>('');
  const [searchTerm, setSearchTerm] = useState<string>('');

  // Selected Anomaly for Inspect/Resolve Modal
  const [selectedAnomaly, setSelectedAnomaly] = useState<BehavioralAnomaly | null>(null);
  const [reviewNote, setReviewNote] = useState<string>('');
  const [actionLoading, setActionLoading] = useState<boolean>(false);
  const [actionMessage, setActionMessage] = useState<string | null>(null);

  const loadData = async () => {
    if (!orgId) return;
    try {
      setLoading(true);
      setError(null);

      const [anomaliesRes, metricsRes] = await Promise.all([
        behaviorApi.listAnomalies(orgId, {
          severity: severityFilter || undefined,
          status: statusFilter || undefined,
          anomaly_type: typeFilter || undefined,
          limit: 100,
        }),
        behaviorApi.getMetrics(orgId).catch(() => null),
      ]);

      setAnomalies(anomaliesRes.items || []);
      if (metricsRes) setMetrics(metricsRes);
    } catch (err: any) {
      setError(err?.response?.data?.detail || err.message || 'Failed to load behavioral anomalies');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadData();
  }, [orgId, severityFilter, statusFilter, typeFilter]);

  const filteredAnomalies = anomalies.filter((a) => {
    if (!searchTerm) return true;
    const term = searchTerm.toLowerCase();
    return (
      a.anomaly_type.toLowerCase().includes(term) ||
      a.explanation.toLowerCase().includes(term) ||
      a.feature.toLowerCase().includes(term) ||
      a.agent_id.toLowerCase().includes(term)
    );
  });

  const getSeverityBadgeClass = (severity: AnomalySeverity | string) => {
    switch (severity.toUpperCase()) {
      case 'CRITICAL':
        return 'badge-critical';
      case 'HIGH':
        return 'badge-high';
      case 'MEDIUM':
        return 'badge-medium';
      case 'LOW':
        return 'badge-low';
      default:
        return 'badge-neutral';
    }
  };

  const getStatusBadgeClass = (status: AnomalyStatus | string) => {
    switch (status.toUpperCase()) {
      case 'OPEN':
        return 'badge-critical';
      case 'REVIEWED':
        return 'badge-medium';
      case 'RESOLVED':
        return 'badge-success';
      case 'SUPPRESSED':
        return 'badge-neutral';
      default:
        return 'badge-neutral';
    }
  };

  const handleResolve = async () => {
    if (!orgId || !selectedAnomaly) return;
    try {
      setActionLoading(true);
      setActionMessage(null);
      const updated = await behaviorApi.resolveAnomaly(
        orgId,
        selectedAnomaly.id,
        reviewNote || undefined
      );
      setSelectedAnomaly(updated);
      setActionMessage('Anomaly successfully resolved.');
      await loadData();
    } catch (err: any) {
      alert(err?.response?.data?.detail || 'Failed to resolve anomaly');
    } finally {
      setActionLoading(false);
    }
  };

  const handleSuppress = async () => {
    if (!orgId || !selectedAnomaly) return;
    try {
      setActionLoading(true);
      setActionMessage(null);
      const updated = await behaviorApi.suppressAnomaly(
        orgId,
        selectedAnomaly.id,
        reviewNote || undefined
      );
      setSelectedAnomaly(updated);
      setActionMessage('Anomaly successfully suppressed.');
      await loadData();
    } catch (err: any) {
      alert(err?.response?.data?.detail || 'Failed to suppress anomaly');
    } finally {
      setActionLoading(false);
    }
  };

  return (
    <div className="page-container">
      {/* Header */}
      <div className="page-header">
        <div>
          <h1 className="page-title">Behavioral &amp; Anomaly Detection</h1>
          <p className="page-subtitle">
            Deterministic baseline monitoring, explainable anomaly detection, and operational drift protection for autonomous AI agents.
          </p>
        </div>
        <Button variant="secondary" onClick={loadData} disabled={loading}>
          Refresh Anomalies
        </Button>
      </div>

      {/* Metrics Banner */}
      <div className="stats-grid" style={{ marginBottom: '1.5rem' }}>
        <Card className="stat-card">
          <div className="stat-label">Monitored Agents</div>
          <div className="stat-value">{metrics ? metrics.monitored_agents : 0}</div>
          <div className="stat-sub">
            {metrics ? `${metrics.established_baselines} Established / ${metrics.learning_baselines} Learning` : 'Active baselines'}
          </div>
        </Card>
        <Card className="stat-card stat-critical">
          <div className="stat-label">Open Anomalies</div>
          <div className="stat-value" style={{ color: 'var(--color-danger, #ef4444)' }}>
            {metrics ? metrics.open_anomalies : anomalies.filter((a) => a.status === 'OPEN').length}
          </div>
          <div className="stat-sub">Pending security review</div>
        </Card>
        <Card className="stat-card stat-high">
          <div className="stat-label">Critical / High Alerts</div>
          <div className="stat-value" style={{ color: 'var(--color-warning, #f59e0b)' }}>
            {metrics
              ? metrics.critical_anomalies + metrics.high_anomalies
              : anomalies.filter((a) => a.severity === 'CRITICAL' || a.severity === 'HIGH').length}
          </div>
          <div className="stat-sub">Approval triggers</div>
        </Card>
        <Card className="stat-card">
          <div className="stat-label">Total Anomalies Detected</div>
          <div className="stat-value">{metrics ? metrics.total_anomalies : anomalies.length}</div>
          <div className="stat-sub">
            {metrics ? `${metrics.action_rate_spikes} rate / ${metrics.failure_spikes} failures` : 'All time'}
          </div>
        </Card>
      </div>

      {/* Filters Toolbar */}
      <Card className="table-card" style={{ marginBottom: '1rem', padding: '1rem' }}>
        <div style={{ display: 'flex', gap: '1rem', flexWrap: 'wrap', alignItems: 'center' }}>
          <div style={{ flex: '1 1 250px' }}>
            <input
              type="text"
              placeholder="Search by type, explanation, feature, or agent..."
              className="input-field"
              value={searchTerm}
              onChange={(e) => setSearchTerm(e.target.value)}
              style={{ width: '100%' }}
            />
          </div>

          <div style={{ width: '150px' }}>
            <select
              className="input-field"
              value={severityFilter}
              onChange={(e) => setSeverityFilter(e.target.value)}
              style={{ width: '100%' }}
            >
              <option value="">All Severities</option>
              <option value="CRITICAL">Critical</option>
              <option value="HIGH">High</option>
              <option value="MEDIUM">Medium</option>
              <option value="LOW">Low</option>
            </select>
          </div>

          <div style={{ width: '150px' }}>
            <select
              className="input-field"
              value={statusFilter}
              onChange={(e) => setStatusFilter(e.target.value)}
              style={{ width: '100%' }}
            >
              <option value="">All Statuses</option>
              <option value="OPEN">Open</option>
              <option value="REVIEWED">Reviewed</option>
              <option value="RESOLVED">Resolved</option>
              <option value="SUPPRESSED">Suppressed</option>
            </select>
          </div>

          <div style={{ width: '220px' }}>
            <select
              className="input-field"
              value={typeFilter}
              onChange={(e) => setTypeFilter(e.target.value)}
              style={{ width: '100%' }}
            >
              <option value="">All Anomaly Types</option>
              <option value="ACTION_RATE_SPIKE">Action Rate Spike</option>
              <option value="NEW_TOOL_USAGE">New Tool Usage</option>
              <option value="NEW_OPERATION_USAGE">New Operation Usage</option>
              <option value="NEW_SENSITIVE_RESOURCE">New Sensitive Resource</option>
              <option value="AMOUNT_DEVIATION">Amount Deviation</option>
              <option value="FAILURE_SPIKE">Failure Spike</option>
              <option value="BLOCK_SPIKE">Block Spike</option>
              <option value="PRIVILEGE_ESCALATION_PATTERN">Privilege Escalation</option>
              <option value="OFF_HOURS_ACTIVITY">Off-Hours Activity</option>
              <option value="ACTION_LOOP">Action Loop</option>
              <option value="MULTI_SIGNAL_ANOMALY">Multi-Signal Anomaly</option>
            </select>
          </div>

          {(severityFilter || statusFilter || typeFilter || searchTerm) && (
            <Button
              variant="ghost"
              size="sm"
              onClick={() => {
                setSeverityFilter('');
                setStatusFilter('');
                setTypeFilter('');
                setSearchTerm('');
              }}
            >
              Clear Filters
            </Button>
          )}
        </div>
      </Card>

      {/* Anomalies Table */}
      {loading ? (
        <LoadingState message="Analyzing agent behavior and anomalous patterns..." />
      ) : error ? (
        <Card className="error-card">
          <p style={{ color: 'var(--color-danger, #ef4444)' }}>{error}</p>
          <Button variant="secondary" size="sm" onClick={loadData} style={{ marginTop: '0.5rem' }}>
            Retry
          </Button>
        </Card>
      ) : filteredAnomalies.length === 0 ? (
        <EmptyState
          icon={<ShieldAlertIcon size={48} />}
          title="No Behavioral Anomalies"
          description={
            severityFilter || statusFilter || typeFilter || searchTerm
              ? 'No anomalies match your current filter criteria.'
              : 'All agents are operating within established behavioral baselines.'
          }
        />
      ) : (
        <Card className="table-card">
          <div className="table-responsive">
            <table className="data-table">
              <thead>
                <tr>
                  <th>Severity</th>
                  <th>Anomaly Type</th>
                  <th>Agent</th>
                  <th>Explanation</th>
                  <th>Deviation</th>
                  <th>Confidence</th>
                  <th>Status</th>
                  <th>Detected At</th>
                  <th>Action</th>
                </tr>
              </thead>
              <tbody>
                {filteredAnomalies.map((anomaly) => (
                  <tr key={anomaly.id}>
                    <td>
                      <span className={`badge ${getSeverityBadgeClass(anomaly.severity)}`}>
                        {anomaly.severity}
                      </span>
                    </td>
                    <td>
                      <div style={{ fontWeight: 600, color: 'var(--color-text-main, #f1f5f9)' }}>
                        {anomaly.anomaly_type.replace(/_/g, ' ')}
                      </div>
                      <code style={{ fontSize: '0.75rem', color: '#38bdf8' }}>{anomaly.feature}</code>
                    </td>
                    <td>
                      <Link
                        to={`/agents/${anomaly.agent_id}`}
                        className="table-link"
                        style={{ fontFamily: 'monospace', fontSize: '0.8125rem' }}
                      >
                        {anomaly.agent_id.slice(0, 8)}...
                      </Link>
                    </td>
                    <td>
                      <div
                        style={{
                          fontSize: '0.8125rem',
                          color: 'var(--color-text-dim, #94a3b8)',
                          maxWidth: '320px',
                          overflow: 'hidden',
                          textOverflow: 'ellipsis',
                          whiteSpace: 'nowrap',
                        }}
                        title={anomaly.explanation}
                      >
                        {anomaly.explanation}
                      </div>
                    </td>
                    <td style={{ fontSize: '0.8125rem', fontFamily: 'monospace' }}>
                      {anomaly.deviation > 0 ? `+${anomaly.deviation.toFixed(1)}σ` : 'N/A'}
                    </td>
                    <td style={{ fontSize: '0.8125rem' }}>
                      <span style={{ fontWeight: 600 }}>{Math.round(anomaly.confidence * 100)}%</span>
                    </td>
                    <td>
                      <span className={`badge ${getStatusBadgeClass(anomaly.status)}`}>
                        {anomaly.status}
                      </span>
                    </td>
                    <td style={{ fontSize: '0.8125rem', color: 'var(--color-text-dim, #94a3b8)' }}>
                      {new Date(anomaly.created_at).toLocaleString()}
                    </td>
                    <td>
                      <Button
                        variant="secondary"
                        size="sm"
                        onClick={() => {
                          setSelectedAnomaly(anomaly);
                          setReviewNote(anomaly.resolution_note || '');
                          setActionMessage(null);
                        }}
                      >
                        Inspect
                      </Button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </Card>
      )}

      {/* Inspect & Resolution Modal */}
      {selectedAnomaly && (
        <div
          style={{
            position: 'fixed',
            inset: 0,
            backgroundColor: 'rgba(0, 0, 0, 0.75)',
            backdropFilter: 'blur(4px)',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            zIndex: 1000,
            padding: '1.5rem',
          }}
        >
          <div
            style={{
              backgroundColor: '#0f172a',
              border: '1px solid #334155',
              borderRadius: '0.75rem',
              width: '100%',
              maxWidth: '750px',
              maxHeight: '90vh',
              overflowY: 'auto',
              padding: '1.5rem',
              boxShadow: '0 25px 50px -12px rgba(0, 0, 0, 0.5)',
            }}
          >
            {/* Modal Header */}
            <div
              style={{
                display: 'flex',
                justifyContent: 'space-between',
                alignItems: 'center',
                marginBottom: '1rem',
                borderBottom: '1px solid #1e293b',
                paddingBottom: '0.75rem',
              }}
            >
              <div style={{ display: 'flex', alignItems: 'center', gap: '0.75rem' }}>
                <span className={`badge ${getSeverityBadgeClass(selectedAnomaly.severity)}`}>
                  {selectedAnomaly.severity}
                </span>
                <h3 style={{ margin: 0, fontSize: '1.25rem', color: '#f8fafc' }}>
                  {selectedAnomaly.anomaly_type.replace(/_/g, ' ')}
                </h3>
              </div>
              <button
                onClick={() => setSelectedAnomaly(null)}
                style={{
                  background: 'transparent',
                  border: 'none',
                  color: '#94a3b8',
                  cursor: 'pointer',
                }}
              >
                <XIcon size={20} />
              </button>
            </div>

            {actionMessage && (
              <div
                style={{
                  padding: '0.75rem 1rem',
                  backgroundColor: 'rgba(34, 197, 94, 0.1)',
                  border: '1px solid rgba(34, 197, 94, 0.25)',
                  borderRadius: '0.5rem',
                  color: '#4ade80',
                  fontSize: '0.875rem',
                  marginBottom: '1rem',
                }}
              >
                {actionMessage}
              </div>
            )}

            {/* Explanation Section */}
            <div style={{ marginBottom: '1.25rem' }}>
              <div style={{ fontSize: '0.8125rem', color: '#94a3b8', marginBottom: '0.25rem', textTransform: 'uppercase', letterSpacing: '0.05em' }}>
                Explainable Assessment
              </div>
              <div
                style={{
                  padding: '0.75rem 1rem',
                  backgroundColor: '#1e293b',
                  borderRadius: '0.5rem',
                  color: '#f1f5f9',
                  fontSize: '0.9375rem',
                  lineHeight: '1.5',
                }}
              >
                {selectedAnomaly.explanation}
              </div>
            </div>

            {/* Metrics & Attributes Grid */}
            <div
              style={{
                display: 'grid',
                gridTemplateColumns: 'repeat(auto-fit, minmax(160px, 1fr))',
                gap: '1rem',
                marginBottom: '1.25rem',
              }}
            >
              <div style={{ backgroundColor: '#1e293b', padding: '0.75rem', borderRadius: '0.5rem' }}>
                <div style={{ fontSize: '0.75rem', color: '#94a3b8' }}>Agent ID</div>
                <Link
                  to={`/agents/${selectedAnomaly.agent_id}`}
                  style={{ color: '#38bdf8', fontSize: '0.875rem', fontFamily: 'monospace' }}
                >
                  {selectedAnomaly.agent_id.slice(0, 12)}...
                </Link>
              </div>

              <div style={{ backgroundColor: '#1e293b', padding: '0.75rem', borderRadius: '0.5rem' }}>
                <div style={{ fontSize: '0.75rem', color: '#94a3b8' }}>Confidence / Score</div>
                <div style={{ fontSize: '0.875rem', color: '#f8fafc', fontWeight: 600 }}>
                  {Math.round(selectedAnomaly.confidence * 100)}% ({selectedAnomaly.score}/100)
                </div>
              </div>

              <div style={{ backgroundColor: '#1e293b', padding: '0.75rem', borderRadius: '0.5rem' }}>
                <div style={{ fontSize: '0.75rem', color: '#94a3b8' }}>Feature</div>
                <code style={{ fontSize: '0.8125rem', color: '#e2e8f0' }}>{selectedAnomaly.feature}</code>
              </div>

              <div style={{ backgroundColor: '#1e293b', padding: '0.75rem', borderRadius: '0.5rem' }}>
                <div style={{ fontSize: '0.75rem', color: '#94a3b8' }}>Status</div>
                <span className={`badge ${getStatusBadgeClass(selectedAnomaly.status)}`}>
                  {selectedAnomaly.status}
                </span>
              </div>
            </div>

            {/* Baseline vs Observed Values */}
            <div
              style={{
                display: 'grid',
                gridTemplateColumns: '1fr 1fr',
                gap: '1rem',
                marginBottom: '1.25rem',
              }}
            >
              <div
                style={{
                  backgroundColor: '#1e293b',
                  padding: '1rem',
                  borderRadius: '0.5rem',
                  border: '1px solid #334155',
                }}
              >
                <div style={{ fontSize: '0.8125rem', color: '#94a3b8', marginBottom: '0.5rem', fontWeight: 600 }}>
                  Baseline Value
                </div>
                <pre
                  style={{
                    backgroundColor: '#0f172a',
                    padding: '0.75rem',
                    borderRadius: '0.375rem',
                    color: '#cbd5e1',
                    fontSize: '0.8125rem',
                    overflowX: 'auto',
                    margin: 0,
                  }}
                >
                  {JSON.stringify(selectedAnomaly.baseline_value, null, 2)}
                </pre>
              </div>

              <div
                style={{
                  backgroundColor: '#1e293b',
                  padding: '1rem',
                  borderRadius: '0.5rem',
                  border: '1px solid #334155',
                }}
              >
                <div style={{ fontSize: '0.8125rem', color: '#f87171', marginBottom: '0.5rem', fontWeight: 600 }}>
                  Observed Value
                </div>
                <pre
                  style={{
                    backgroundColor: '#0f172a',
                    padding: '0.75rem',
                    borderRadius: '0.375rem',
                    color: '#fca5a5',
                    fontSize: '0.8125rem',
                    overflowX: 'auto',
                    margin: 0,
                  }}
                >
                  {JSON.stringify(selectedAnomaly.observed_value, null, 2)}
                </pre>
              </div>
            </div>

            {/* Evidence List */}
            {selectedAnomaly.evidence && selectedAnomaly.evidence.length > 0 && (
              <div style={{ marginBottom: '1.25rem' }}>
                <div style={{ fontSize: '0.8125rem', color: '#94a3b8', marginBottom: '0.5rem', fontWeight: 600 }}>
                  Deterministic Evidence Trail ({selectedAnomaly.evidence.length} items)
                </div>
                <div style={{ display: 'flex', flexDirection: 'column', gap: '0.5rem' }}>
                  {selectedAnomaly.evidence.map((item, idx) => (
                    <div
                      key={idx}
                      style={{
                        backgroundColor: '#1e293b',
                        padding: '0.75rem',
                        borderRadius: '0.375rem',
                        fontSize: '0.8125rem',
                        borderLeft: '3px solid #38bdf8',
                      }}
                    >
                      <pre style={{ margin: 0, color: '#cbd5e1', whiteSpace: 'pre-wrap', wordBreak: 'break-word' }}>
                        {typeof item === 'string' ? item : JSON.stringify(item, null, 2)}
                      </pre>
                    </div>
                  ))}
                </div>
              </div>
            )}

            {/* Runtime Action Reference */}
            {selectedAnomaly.runtime_action_id && (
              <div
                style={{
                  display: 'flex',
                  alignItems: 'center',
                  gap: '0.5rem',
                  marginBottom: '1.25rem',
                  fontSize: '0.875rem',
                }}
              >
                <TerminalIcon size={16} />
                <span style={{ color: '#94a3b8' }}>Associated Runtime Action:</span>
                <Link
                  to={`/runtime-actions/${selectedAnomaly.runtime_action_id}`}
                  style={{ color: '#38bdf8', fontFamily: 'monospace' }}
                >
                  {selectedAnomaly.runtime_action_id}
                </Link>
              </div>
            )}

            {/* Resolution Form */}
            <div
              style={{
                borderTop: '1px solid #1e293b',
                paddingTop: '1rem',
                marginTop: '1rem',
              }}
            >
              <div style={{ fontSize: '0.875rem', fontWeight: 600, color: '#f8fafc', marginBottom: '0.5rem' }}>
                Security Review &amp; Resolution
              </div>
              <textarea
                placeholder="Enter justification or reviewer note (required for compliance audit)..."
                className="input-field"
                value={reviewNote}
                onChange={(e) => setReviewNote(e.target.value)}
                style={{ width: '100%', minHeight: '80px', marginBottom: '1rem' }}
              />

              <div style={{ display: 'flex', justifyContent: 'flex-end', gap: '0.75rem' }}>
                <Button
                  variant="ghost"
                  onClick={() => setSelectedAnomaly(null)}
                  disabled={actionLoading}
                >
                  Close
                </Button>
                <Button
                  variant="secondary"
                  onClick={handleSuppress}
                  disabled={actionLoading || selectedAnomaly.status === 'SUPPRESSED'}
                >
                  Suppress (False Positive)
                </Button>
                <Button
                  variant="primary"
                  onClick={handleResolve}
                  disabled={actionLoading || selectedAnomaly.status === 'RESOLVED'}
                >
                  Resolve Anomaly
                </Button>
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};

export default BehaviorSecurityPage;
