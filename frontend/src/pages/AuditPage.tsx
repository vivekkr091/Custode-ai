import React, { useState, useEffect, useCallback } from 'react';
import { useOrg } from '../context/OrgContext';
import { useAuth } from '../context/AuthContext';
import { auditApi } from '../api/audit';
import { AuditEvent } from '../types';
import { SurfaceCard } from '../components/common/Card';
import { Button } from '../components/common/Button';
import { Modal } from '../components/common/Modal';
import { CodeView } from '../components/common/CodeView';
import { LoadingState, EmptyState, ErrorState } from '../components/common/FeedbackStates';
import {
  ShieldIcon,
  RefreshIcon,
  SearchIcon,
  FilterIcon,
  CheckCircleIcon,
  XCircleIcon,
  AlertTriangleIcon,
  TerminalIcon,
} from '../components/common/Icons';

export const AuditPage: React.FC = () => {
  const { currentOrg } = useOrg();
  const { role } = useAuth();

  const [events, setEvents] = useState<AuditEvent[]>([]);
  const [loading, setLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);
  const [selectedEvent, setSelectedEvent] = useState<AuditEvent | null>(null);

  // Filters
  const [actionFilter, setActionFilter] = useState<string>('');
  const [outcomeFilter, setOutcomeFilter] = useState<string>('all');
  const [actorTypeFilter, setActorTypeFilter] = useState<string>('all');
  const [searchTerm, setSearchTerm] = useState<string>('');

  const fetchAuditEvents = useCallback(async () => {
    if (!currentOrg) return;
    setLoading(true);
    setError(null);
    try {
      const params: any = { limit: 100 };
      if (actionFilter) params.action = actionFilter;
      if (outcomeFilter !== 'all') params.outcome = outcomeFilter;
      if (actorTypeFilter !== 'all') params.actor_type = actorTypeFilter;

      const res = await auditApi.list(currentOrg.id, params);
      setEvents(res.items || []);
    } catch (err: any) {
      setError(err.message || 'Failed to retrieve tenant audit trail.');
    } finally {
      setLoading(false);
    }
  }, [currentOrg, actionFilter, outcomeFilter, actorTypeFilter]);

  useEffect(() => {
    fetchAuditEvents();
  }, [fetchAuditEvents]);

  const filteredEvents = events.filter((ev) => {
    if (!searchTerm.trim()) return true;
    const term = searchTerm.toLowerCase();
    return (
      (ev.action && ev.action.toLowerCase().includes(term)) ||
      (ev.event_type && ev.event_type.toLowerCase().includes(term)) ||
      (ev.actor_type && ev.actor_type.toLowerCase().includes(term)) ||
      (ev.actor_id && ev.actor_id.toLowerCase().includes(term)) ||
      (ev.actor_display && ev.actor_display.toLowerCase().includes(term)) ||
      (ev.resource_type && ev.resource_type.toLowerCase().includes(term)) ||
      (ev.resource_id && ev.resource_id.toLowerCase().includes(term)) ||
      (ev.request_id && ev.request_id.toLowerCase().includes(term)) ||
      (ev.reason && ev.reason.toLowerCase().includes(term))
    );
  });

  const getOutcomeBadge = (outcome: string) => {
    if (outcome === 'success') {
      return (
        <span className="badge-pill badge-emerald">
          <CheckCircleIcon size={12} />
          SUCCESS
        </span>
      );
    }
    if (outcome === 'denied') {
      return (
        <span className="badge-pill badge-amber">
          <AlertTriangleIcon size={12} />
          DENIED
        </span>
      );
    }
    return (
      <span className="badge-pill badge-rose">
        <XCircleIcon size={12} />
        FAILURE
      </span>
    );
  };

  const formatTimestamp = (ts: string) => {
    try {
      const d = new Date(ts);
      return d.toLocaleString('en-US', {
        month: 'short',
        day: 'numeric',
        hour: '2-digit',
        minute: '2-digit',
        second: '2-digit',
        hour12: false,
      });
    } catch {
      return ts;
    }
  };

  return (
    <div className="page-container">
      {/* Header Bar */}
      <div className="page-header-row">
        <div>
          <h2 className="page-heading">Security Audit Trail</h2>
          <p className="page-subheading">
            Authoritative, tamper-evident log of administrative mutations, auth events &amp; governance decisions.
          </p>
        </div>
        <div className="page-actions-group">
          <Button
            variant="outline"
            size="sm"
            onClick={fetchAuditEvents}
            loading={loading}
            icon={<RefreshIcon size={14} />}
          >
            Refresh
          </Button>
        </div>
      </div>

      {/* Filter / Search Bar */}
      <SurfaceCard className="filter-card">
        <div className="audit-filters-row">
          <div className="search-input-wrapper">
            <SearchIcon size={16} className="search-icon" />
            <input
              type="text"
              placeholder="Search action, user, or target..."
              value={searchTerm}
              onChange={(e) => setSearchTerm(e.target.value)}
              className="filter-search-input"
            />
          </div>

          <div className="filter-group">
            <label className="filter-label">Outcome:</label>
            <select
              value={outcomeFilter}
              onChange={(e) => setOutcomeFilter(e.target.value)}
              className="filter-select"
            >
              <option value="all">All Outcomes</option>
              <option value="success">Success</option>
              <option value="denied">Denied</option>
              <option value="failure">Failure</option>
            </select>
          </div>

          <div className="filter-group">
            <label className="filter-label">Actor Type:</label>
            <select
              value={actorTypeFilter}
              onChange={(e) => setActorTypeFilter(e.target.value)}
              className="filter-select"
            >
              <option value="all">All Actors</option>
              <option value="USER">USER (Human)</option>
              <option value="AGENT">AGENT (AI)</option>
              <option value="SYSTEM">SYSTEM (Core)</option>
            </select>
          </div>

          <div className="filter-group">
            <label className="filter-label">Action Filter:</label>
            <select
              value={actionFilter}
              onChange={(e) => setActionFilter(e.target.value)}
              className="filter-select"
            >
              <option value="">All Actions</option>
              <option value="USER_LOGIN">USER_LOGIN</option>
              <option value="ORGANIZATION_SWITCH">ORGANIZATION_SWITCH</option>
              <option value="AGENT_CREATED">AGENT_CREATED</option>
              <option value="PERMISSION_CREATED">PERMISSION_CREATED</option>
              <option value="POLICY_PUBLISHED">POLICY_PUBLISHED</option>
              <option value="RUNTIME_ACTION_CREATED">RUNTIME_ACTION_CREATED</option>
              <option value="DECISION_CREATED">DECISION_CREATED</option>
              <option value="APPROVAL_APPROVED">APPROVAL_APPROVED</option>
              <option value="APPROVAL_REJECTED">APPROVAL_REJECTED</option>
              <option value="EXECUTION_SUCCEEDED">EXECUTION_SUCCEEDED</option>
              <option value="EXECUTION_BLOCKED">EXECUTION_BLOCKED</option>
            </select>
          </div>
        </div>
      </SurfaceCard>

      {/* Main Content Area */}
      {loading && events.length === 0 ? (
        <LoadingState message="Querying organization audit events..." />
      ) : error ? (
        <ErrorState message={error} onRetry={fetchAuditEvents} />
      ) : filteredEvents.length === 0 ? (
        <EmptyState
          title="No Audit Events Recorded"
          description="Administrative mutations, auth actions, and governance reviews in this organization will appear here."
          icon={<ShieldIcon size={36} />}
        />
      ) : (
        <SurfaceCard className="table-card">
          <div className="table-responsive">
            <table className="custode-table">
              <thead>
                <tr>
                  <th>Timestamp</th>
                  <th>Action / Event</th>
                  <th>Outcome</th>
                  <th>Actor (Type / ID)</th>
                  <th>Resource Target</th>
                  <th>Request ID</th>
                  <th style={{ textAlign: 'right' }}>Actions</th>
                </tr>
              </thead>
              <tbody>
                {filteredEvents.map((ev) => (
                  <tr key={ev.id} className="table-row-hover">
                    <td className="font-mono text-muted text-xs">
                      {formatTimestamp(ev.created_at)}
                    </td>
                    <td>
                      <div>
                        <span className="font-mono font-semibold text-cyan block">
                          {ev.action}
                        </span>
                        {ev.event_type && ev.event_type !== ev.action && (
                          <span className="text-[10px] font-mono text-dim block">
                            {ev.event_type}
                          </span>
                        )}
                      </div>
                    </td>
                    <td>{getOutcomeBadge(ev.outcome)}</td>
                    <td className="font-mono text-xs">
                      <div className="flex items-center gap-1.5">
                        <span
                          className={`px-1.5 py-0.5 rounded text-[10px] font-bold ${
                            ev.actor_type === 'USER'
                              ? 'bg-blue-500/20 text-blue-400'
                              : ev.actor_type === 'AGENT'
                              ? 'bg-purple-500/20 text-purple-400'
                              : 'bg-zinc-700/50 text-zinc-400'
                          }`}
                        >
                          {ev.actor_type || (ev.user_id ? 'USER' : ev.agent_id ? 'AGENT' : 'SYSTEM')}
                        </span>
                        <span className="text-secondary truncate max-w-[130px]" title={ev.actor_display || ev.actor_id || ev.user_id || ''}>
                          {ev.actor_display || (ev.actor_id ? `${ev.actor_id.slice(0, 8)}...` : ev.user_id ? `${ev.user_id.slice(0, 8)}...` : 'System')}
                        </span>
                      </div>
                    </td>
                    <td>
                      <span className="text-secondary">
                        {ev.resource_type || ev.target_type || 'system'}
                        {(ev.resource_id || ev.target_id) && (
                          <span className="text-dim text-xs font-mono ml-1">
                            ({(ev.resource_id || ev.target_id || '').slice(0, 8)}...)
                          </span>
                        )}
                      </span>
                    </td>
                    <td className="font-mono text-xs text-dim">
                      {ev.request_id ? (
                        <span title={ev.request_id} className="px-1.5 py-0.5 rounded bg-bg-tertiary">
                          {ev.request_id.slice(0, 10)}...
                        </span>
                      ) : (
                        '-'
                      )}
                    </td>
                    <td style={{ textAlign: 'right' }}>
                      <Button
                        variant="secondary"
                        size="sm"
                        onClick={() => setSelectedEvent(ev)}
                      >
                        Inspect
                      </Button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </SurfaceCard>
      )}

      {/* Detail Modal */}
      {selectedEvent && (
        <Modal
          isOpen={!!selectedEvent}
          onClose={() => setSelectedEvent(null)}
          title={`Audit Event: ${selectedEvent.action}`}
          subtitle={`Event ID: ${selectedEvent.id}`}
        >
          <div className="audit-detail-content">
            <div className="detail-meta-grid">
              <div className="detail-item">
                <span className="detail-label">Outcome</span>
                <div>{getOutcomeBadge(selectedEvent.outcome)}</div>
              </div>
              <div className="detail-item">
                <span className="detail-label">Timestamp</span>
                <span className="detail-value font-mono">
                  {selectedEvent.created_at}
                </span>
              </div>
              <div className="detail-item">
                <span className="detail-label">Actor Resolution</span>
                <span className="detail-value font-mono text-xs">
                  {selectedEvent.actor_type || 'SYSTEM'}: {selectedEvent.actor_display || selectedEvent.actor_id || selectedEvent.user_id || 'System'}
                </span>
              </div>
              <div className="detail-item">
                <span className="detail-label">Resource Target</span>
                <span className="detail-value">
                  {selectedEvent.resource_type || selectedEvent.target_type}: {selectedEvent.resource_id || selectedEvent.target_id || 'N/A'}
                </span>
              </div>
              {selectedEvent.request_id && (
                <div className="detail-item full-width">
                  <span className="detail-label">Request Correlation ID</span>
                  <span className="detail-value font-mono text-xs text-blue-400 bg-bg-tertiary px-2 py-1 rounded">
                    {selectedEvent.request_id}
                  </span>
                </div>
              )}
              {selectedEvent.ip_address && (
                <div className="detail-item">
                  <span className="detail-label">Client IP</span>
                  <span className="detail-value font-mono text-xs">
                    {selectedEvent.ip_address}
                  </span>
                </div>
              )}
              {selectedEvent.user_agent && (
                <div className="detail-item">
                  <span className="detail-label">User Agent</span>
                  <span className="detail-value font-mono text-xs truncate" title={selectedEvent.user_agent}>
                    {selectedEvent.user_agent}
                  </span>
                </div>
              )}
              {selectedEvent.reason && (
                <div className="detail-item full-width">
                  <span className="detail-label">Reason / Notes</span>
                  <span className="detail-value text-amber">
                    {selectedEvent.reason}
                  </span>
                </div>
              )}
            </div>

            {/* Related Investigation Shortcuts */}
            <div style={{ margin: '1rem 0', display: 'flex', gap: '0.5rem', flexWrap: 'wrap' }}>
              {(selectedEvent.resource_type === 'runtime_action' || selectedEvent.metadata?.runtime_action_id) && (
                <a
                  href={`/runtime-actions/${selectedEvent.resource_id || selectedEvent.metadata?.runtime_action_id}`}
                  className="btn btn-outline btn-sm font-mono text-xs"
                >
                  Inspect Action Forensics →
                </a>
              )}
              {(selectedEvent.resource_type === 'execution' || selectedEvent.metadata?.execution_id) && (
                <a
                  href={`/executions/${selectedEvent.resource_id || selectedEvent.metadata?.execution_id}`}
                  className="btn btn-outline btn-sm font-mono text-xs"
                >
                  Inspect Execution Log →
                </a>
              )}
              {(selectedEvent.resource_type === 'decision' || selectedEvent.metadata?.decision_id) && (
                <a
                  href={`/decisions/${selectedEvent.resource_id || selectedEvent.metadata?.decision_id}`}
                  className="btn btn-outline btn-sm font-mono text-xs"
                >
                  Inspect Decision →
                </a>
              )}
            </div>

            <div className="detail-code-section">
              <div className="section-label">SANITIZED EVENT METADATA (CONFIDENTIAL SECRETS REDACTED)</div>
              <CodeView
                code={JSON.stringify(selectedEvent.metadata || {}, null, 2)}
                language="json"
              />
            </div>
          </div>
        </Modal>
      )}
    </div>
  );
};
