import React, { useEffect, useState } from 'react';
import { useOrg } from '../context/OrgContext';
import { findingsApi } from '../api/findings';
import { SecurityFinding, SecurityMetrics } from '../types';
import { Link } from '../router/Router';
import { Card } from '../components/common/Card';
import { Button } from '../components/common/Button';
import { EmptyState, LoadingState } from '../components/common/FeedbackStates';
import { AlertTriangleIcon, CheckCircleIcon, ShieldAlertIcon, ShieldIcon, TerminalIcon } from '../components/common/Icons';

export const FindingsPage: React.FC = () => {
  const { currentOrg } = useOrg();
  const [findings, setFindings] = useState<SecurityFinding[]>([]);
  const [metrics, setMetrics] = useState<SecurityMetrics | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  // Filters
  const [severityFilter, setSeverityFilter] = useState<string>('');
  const [categoryFilter, setCategoryFilter] = useState<string>('');
  const [searchTerm, setSearchTerm] = useState<string>('');

  const loadData = async () => {
    if (!currentOrg) return;
    try {
      setLoading(true);
      setError(null);

      const [findingsRes, metricsRes] = await Promise.all([
        findingsApi.list(currentOrg.id, {
          severity: severityFilter || undefined,
          category: categoryFilter || undefined,
          limit: 100,
        }),
        findingsApi.getMetrics(currentOrg.id).catch(() => null),
      ]);

      setFindings(findingsRes.items || []);
      if (metricsRes) setMetrics(metricsRes);
    } catch (err: any) {
      setError(err?.message || 'Failed to load security findings.');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadData();
  }, [currentOrg, severityFilter, categoryFilter]);

  const filteredFindings = findings.filter((f) => {
    if (!searchTerm) return true;
    const term = searchTerm.toLowerCase();
    return (
      f.title.toLowerCase().includes(term) ||
      f.category.toLowerCase().includes(term) ||
      f.scanner.toLowerCase().includes(term) ||
      f.description.toLowerCase().includes(term)
    );
  });

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

  return (
    <div className="page-container">
      {/* Header */}
      <div className="page-header">
        <div>
          <h1 className="page-title">Sentinel Security Findings</h1>
          <p className="page-subtitle">
            Authoritative security vulnerabilities, prompt injections, credentials, and PII detected across agent actions.
          </p>
        </div>
        <Button variant="secondary" onClick={loadData} disabled={loading}>
          Refresh Findings
        </Button>
      </div>

      {/* Metrics Banner */}
      <div className="stats-grid" style={{ marginBottom: '1.5rem' }}>
        <Card className="stat-card">
          <div className="stat-label">Total Findings</div>
          <div className="stat-value">{metrics ? metrics.total_findings : findings.length}</div>
          <div className="stat-sub">Across all actions</div>
        </Card>
        <Card className="stat-card stat-critical">
          <div className="stat-label">Critical Findings</div>
          <div className="stat-value" style={{ color: 'var(--color-danger, #ef4444)' }}>
            {metrics ? metrics.critical_count : findings.filter((f) => f.severity === 'CRITICAL').length}
          </div>
          <div className="stat-sub">Immediate block triggers</div>
        </Card>
        <Card className="stat-card stat-high">
          <div className="stat-label">High Severity</div>
          <div className="stat-value" style={{ color: 'var(--color-warning, #f59e0b)' }}>
            {metrics ? metrics.high_count : findings.filter((f) => f.severity === 'HIGH').length}
          </div>
          <div className="stat-sub">Approval required</div>
        </Card>
        <Card className="stat-card">
          <div className="stat-label">Total Scans Run</div>
          <div className="stat-value">{metrics ? metrics.total_scans : 0}</div>
          <div className="stat-sub">Active Sentinel engines</div>
        </Card>
      </div>

      {/* Filters Toolbar */}
      <Card className="table-card" style={{ marginBottom: '1rem', padding: '1rem' }}>
        <div style={{ display: 'flex', gap: '1rem', flexWrap: 'wrap', alignItems: 'center' }}>
          <div style={{ flex: '1 1 250px' }}>
            <input
              type="text"
              placeholder="Search by title, scanner, or category..."
              className="input-field"
              value={searchTerm}
              onChange={(e) => setSearchTerm(e.target.value)}
              style={{ width: '100%' }}
            />
          </div>

          <div style={{ width: '160px' }}>
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

          <div style={{ width: '200px' }}>
            <select
              className="input-field"
              value={categoryFilter}
              onChange={(e) => setCategoryFilter(e.target.value)}
              style={{ width: '100%' }}
            >
              <option value="">All Categories</option>
              <option value="PROMPT_INJECTION">Prompt Injection</option>
              <option value="SECRET">Secret Exposure</option>
              <option value="PII">PII Detected</option>
              <option value="CODE_SECURITY">Code Vulnerability</option>
              <option value="HARMFUL_CONTENT">Harmful Content</option>
              <option value="TOXICITY">Toxicity</option>
              <option value="BLOCKED_TERM">Blocked Terms</option>
              <option value="OBFUSCATION">Obfuscation</option>
            </select>
          </div>

          {(severityFilter || categoryFilter || searchTerm) && (
            <Button
              variant="ghost"
              size="sm"
              onClick={() => {
                setSeverityFilter('');
                setCategoryFilter('');
                setSearchTerm('');
              }}
            >
              Clear Filters
            </Button>
          )}
        </div>
      </Card>

      {/* Findings Table */}
      {loading ? (
        <LoadingState message="Loading Sentinel security findings..." />
      ) : error ? (
        <Card className="error-card">
          <p style={{ color: 'var(--color-danger, #ef4444)' }}>{error}</p>
          <Button variant="secondary" size="sm" onClick={loadData} style={{ marginTop: '0.5rem' }}>
            Retry
          </Button>
        </Card>
      ) : filteredFindings.length === 0 ? (
        <EmptyState
          icon={<ShieldAlertIcon size={48} />}
          title="No Security Findings Found"
          description={
            severityFilter || categoryFilter || searchTerm
              ? 'No findings matched your current filter criteria.'
              : 'All evaluated agent runtime actions passed Sentinel security scans cleanly.'
          }
        />
      ) : (
        <Card className="table-card">
          <div className="table-responsive">
            <table className="data-table">
              <thead>
                <tr>
                  <th>Severity</th>
                  <th>Finding Title</th>
                  <th>Category</th>
                  <th>Scanner</th>
                  <th>Runtime Action</th>
                  <th>Detected At</th>
                  <th>Action</th>
                </tr>
              </thead>
              <tbody>
                {filteredFindings.map((finding) => (
                  <tr key={finding.id}>
                    <td>
                      <span className={`badge ${getSeverityBadgeClass(finding.severity)}`}>
                        {finding.severity}
                      </span>
                    </td>
                    <td>
                      <div style={{ fontWeight: 600, color: 'var(--color-text-main, #f1f5f9)' }}>
                        {finding.title}
                      </div>
                      <div
                        style={{
                          fontSize: '0.8125rem',
                          color: 'var(--color-text-dim, #94a3b8)',
                          maxWidth: '360px',
                          overflow: 'hidden',
                          textOverflow: 'ellipsis',
                          whiteSpace: 'nowrap',
                        }}
                      >
                        {finding.description}
                      </div>
                    </td>
                    <td>
                      <span className="badge badge-neutral">{finding.category}</span>
                    </td>
                    <td>
                      <code style={{ fontSize: '0.8125rem', color: '#38bdf8' }}>{finding.scanner}</code>
                    </td>
                    <td>
                      <Link
                        to={`/runtime-actions/${finding.runtime_action_id}`}
                        className="table-link"
                        style={{ display: 'inline-flex', alignItems: 'center', gap: '0.25rem' }}
                      >
                        <TerminalIcon size={14} />
                        {finding.runtime_action_id.slice(0, 8)}...
                      </Link>
                    </td>
                    <td style={{ fontSize: '0.8125rem', color: 'var(--color-text-dim, #94a3b8)' }}>
                      {new Date(finding.created_at).toLocaleString()}
                    </td>
                    <td>
                      <Link to={`/findings/${finding.id}`}>
                        <Button variant="secondary" size="sm">
                          Inspect
                        </Button>
                      </Link>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </Card>
      )}
    </div>
  );
};

export default FindingsPage;
