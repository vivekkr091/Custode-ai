import React, { useEffect, useState } from 'react';
import { useOrg } from '../context/OrgContext';
import { findingsApi } from '../api/findings';
import { runtimeActionsApi } from '../api/runtimeActions';
import { SecurityFinding, RuntimeAction } from '../types';
import { Link, useParams } from '../router/Router';
import { Card } from '../components/common/Card';
import { Button } from '../components/common/Button';
import { CodeView } from '../components/common/CodeView';
import { LoadingState } from '../components/common/FeedbackStates';
import {
  AlertTriangleIcon,
  CheckCircleIcon,
  LockIcon,
  ShieldAlertIcon,
  ShieldCheckIcon,
  TerminalIcon,
} from '../components/common/Icons';

export const FindingDetailPage: React.FC = () => {
  const { currentOrg } = useOrg();
  const { id } = useParams();

  const [finding, setFinding] = useState<SecurityFinding | null>(null);
  const [action, setAction] = useState<RuntimeAction | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const loadData = async () => {
    if (!currentOrg || !id) return;
    try {
      setLoading(true);
      setError(null);

      const findingData = await findingsApi.get(currentOrg.id, id);
      setFinding(findingData);

      if (findingData.runtime_action_id) {
        try {
          const actionData = await runtimeActionsApi.get(currentOrg.id, findingData.runtime_action_id);
          setAction(actionData);
        } catch {
          // Action could be deleted or restricted
        }
      }
    } catch (err: any) {
      setError(err?.message || 'Failed to load security finding detail.');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadData();
  }, [currentOrg, id]);

  const getSeverityBadgeClass = (severity: string) => {
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

  if (loading) {
    return <LoadingState message="Loading security finding dossier..." />;
  }

  if (error || !finding) {
    return (
      <div className="page-container">
        <Card className="error-card">
          <h2>Security Finding Not Found</h2>
          <p>{error || 'The requested finding could not be located in this organization.'}</p>
          <Link to="/findings">
            <Button variant="secondary" size="sm" style={{ marginTop: '1rem' }}>
              ← Return to Findings
            </Button>
          </Link>
        </Card>
      </div>
    );
  }

  return (
    <div className="page-container">
      {/* Back Link */}
      <div style={{ marginBottom: '1rem' }}>
        <Link to="/findings" className="table-link" style={{ fontSize: '0.875rem' }}>
          ← Back to Security Findings
        </Link>
      </div>

      {/* Header Banner */}
      <div
        className="page-header"
        style={{
          borderBottom: '1px solid var(--color-border, #1e293b)',
          paddingBottom: '1.25rem',
          marginBottom: '1.5rem',
        }}
      >
        <div>
          <div style={{ display: 'flex', alignItems: 'center', gap: '0.75rem', marginBottom: '0.5rem' }}>
            <span className={`badge ${getSeverityBadgeClass(finding.severity)}`} style={{ fontSize: '0.875rem' }}>
              {finding.severity}
            </span>
            <span className="badge badge-neutral">{finding.category}</span>
            <span style={{ fontSize: '0.8125rem', color: 'var(--color-text-dim, #94a3b8)' }}>
              Source: {finding.source}
            </span>
          </div>
          <h1 className="page-title">{finding.title}</h1>
          <p className="page-subtitle" style={{ maxWidth: '800px' }}>
            {finding.description}
          </p>
        </div>
      </div>

      <div style={{ display: 'grid', gridTemplateColumns: 'minmax(0, 2fr) minmax(0, 1fr)', gap: '1.5rem' }}>
        {/* Left Column: Remediation, Evidence & Investigation Details */}
        <div style={{ display: 'flex', flexDirection: 'column', gap: '1.5rem' }}>
          {/* Remediation Guidance Box */}
          <Card
            style={{
              borderLeft:
                finding.severity === 'CRITICAL'
                  ? '4px solid var(--color-danger, #ef4444)'
                  : finding.severity === 'HIGH'
                  ? '4px solid var(--color-warning, #f59e0b)'
                  : '4px solid #38bdf8',
            }}
          >
            <div style={{ display: 'flex', alignItems: 'flex-start', gap: '0.75rem' }}>
              <ShieldCheckIcon
                size={22}
                style={{
                  color:
                    finding.severity === 'CRITICAL'
                      ? 'var(--color-danger, #ef4444)'
                      : finding.severity === 'HIGH'
                      ? 'var(--color-warning, #f59e0b)'
                      : '#38bdf8',
                  flexShrink: 0,
                  marginTop: '0.2rem',
                }}
              />
              <div>
                <h3 style={{ fontSize: '1rem', fontWeight: 600, marginBottom: '0.35rem', color: '#f8fafc' }}>
                  Recommended Remediation
                </h3>
                <p style={{ color: 'var(--color-text-main, #e2e8f0)', fontSize: '0.9rem', lineHeight: 1.5 }}>
                  {finding.remediation || 'Review action parameters and ensure compliance with security and privacy policies.'}
                </p>
              </div>
            </div>
          </Card>

          {/* Sanitized Evidence */}
          <Card title="Sanitized Detection Evidence">
            <div style={{ marginBottom: '0.5rem', fontSize: '0.8125rem', color: 'var(--color-text-dim, #94a3b8)' }}>
              Sensitive tokens, private keys, and passwords have been redacted to ensure tamper-resistant forensic logging.
            </div>
            {finding.evidence ? (
              <CodeView code={finding.evidence} language="text" />
            ) : (
              <div style={{ fontStyle: 'italic', color: 'var(--color-text-dim, #64748b)' }}>
                No raw string evidence span recorded for this finding pattern.
              </div>
            )}
          </Card>

          {/* Raw Metadata */}
          {finding.finding_metadata && Object.keys(finding.finding_metadata).length > 0 && (
            <Card title="Scanner Pattern & Trace Metadata">
              <CodeView code={JSON.stringify(finding.finding_metadata, null, 2)} language="json" />
            </Card>
          )}
        </div>

        {/* Right Column: Finding Context & Target Action */}
        <div style={{ display: 'flex', flexDirection: 'column', gap: '1.5rem' }}>
          {/* Finding Attributes */}
          <Card title="Finding Attributes">
            <dl className="property-list">
              <div>
                <dt>Finding ID</dt>
                <dd>
                  <code style={{ fontSize: '0.75rem' }}>{finding.id}</code>
                </dd>
              </div>
              <div>
                <dt>Scanner Engine</dt>
                <dd>
                  <code style={{ color: '#38bdf8' }}>{finding.scanner}</code>
                </dd>
              </div>
              <div>
                <dt>Confidence Score</dt>
                <dd>{(finding.confidence * 100).toFixed(0)}%</dd>
              </div>
              <div>
                <dt>Detected Timestamp</dt>
                <dd>{new Date(finding.created_at).toLocaleString()}</dd>
              </div>
            </dl>
          </Card>

          {/* Associated Runtime Action */}
          <Card title="Associated Runtime Action">
            {action ? (
              <div>
                <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', marginBottom: '0.75rem' }}>
                  <span className={`badge badge-${action.status}`}>{action.status}</span>
                  <span className="badge badge-neutral">{action.environment}</span>
                </div>
                <dl className="property-list">
                  <div>
                    <dt>Action Type</dt>
                    <dd>
                      <code>{action.action_type}</code>
                    </dd>
                  </div>
                  {action.resource && (
                    <div>
                      <dt>Target Resource</dt>
                      <dd>{action.resource}</dd>
                    </div>
                  )}
                  <div>
                    <dt>Initiated At</dt>
                    <dd>{new Date(action.created_at).toLocaleString()}</dd>
                  </div>
                </dl>
                <Link to={`/runtime-actions/${action.id}`}>
                  <Button variant="primary" size="sm" style={{ width: '100%', marginTop: '1rem' }}>
                    <TerminalIcon size={14} style={{ marginRight: '0.35rem' }} />
                    Inspect Runtime Action
                  </Button>
                </Link>
              </div>
            ) : (
              <div>
                <p style={{ fontSize: '0.85rem', color: 'var(--color-text-dim, #94a3b8)', marginBottom: '0.75rem' }}>
                  Action ID: <code style={{ fontSize: '0.75rem' }}>{finding.runtime_action_id}</code>
                </p>
                <Link to={`/runtime-actions/${finding.runtime_action_id}`}>
                  <Button variant="secondary" size="sm" style={{ width: '100%' }}>
                    View Action
                  </Button>
                </Link>
              </div>
            )}
          </Card>
        </div>
      </div>
    </div>
  );
};

export default FindingDetailPage;
