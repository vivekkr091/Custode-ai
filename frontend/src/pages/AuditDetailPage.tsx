import React, { useEffect, useState } from 'react';
import { useRouteParams, navigate } from '../router/Router';
import { useOrg } from '../context/OrgContext';
import { auditApi } from '../api/audit';
import { AuditEvent } from '../types';
import { SurfaceCard } from '../components/common/Card';
import { Button } from '../components/common/Button';
import { CodeView } from '../components/common/CodeView';
import { LoadingState, ErrorState } from '../components/common/FeedbackStates';
import {
  ArrowLeftIcon,
  ShieldIcon,
  ShieldCheckIcon,
  AlertTriangleIcon,
  XCircleIcon,
  CheckCircleIcon,
  CopyIcon,
  CheckIcon,
  ClockIcon,
  UserIcon,
  BotIcon,
  TerminalIcon,
} from '../components/common/Icons';

export const AuditDetailPage: React.FC = () => {
  const params = useRouteParams();
  const eventId = params.eventId || params.id;
  const { currentOrg } = useOrg();

  const [event, setEvent] = useState<AuditEvent | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [viewMode, setViewMode] = useState<'structured' | 'raw'>('structured');
  const [copiedReqId, setCopiedReqId] = useState(false);

  const fetchEvent = async () => {
    if (!currentOrg || !eventId) return;
    try {
      setLoading(true);
      setError(null);
      const data = await auditApi.get(currentOrg.id, eventId);
      setEvent(data);
    } catch (err: any) {
      setError(err?.message || 'Failed to retrieve immutable audit record');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchEvent();
  }, [currentOrg?.id, eventId]);

  const copyRequestId = () => {
    if (event?.request_id) {
      navigator.clipboard.writeText(event.request_id);
      setCopiedReqId(true);
      setTimeout(() => setCopiedReqId(false), 2000);
    }
  };

  const getOutcomeBadge = (outcome: string) => {
    const norm = String(outcome || '').toLowerCase();
    if (norm === 'success') {
      return (
        <span className="badge-pill badge-emerald">
          <CheckCircleIcon size={12} />
          SUCCESS
        </span>
      );
    }
    if (norm === 'denied' || norm === 'blocked') {
      return (
        <span className="badge-pill badge-amber">
          <AlertTriangleIcon size={12} />
          {norm.toUpperCase()}
        </span>
      );
    }
    return (
      <span className="badge-pill badge-rose">
        <XCircleIcon size={12} />
        {norm.toUpperCase() || 'FAILURE'}
      </span>
    );
  };

  if (loading) {
    return <LoadingState message="Fetching immutable security audit record..." />;
  }

  if (error || !event) {
    return (
      <ErrorState
        title="Audit Event Not Found"
        message={error || 'Could not locate audit event in tenant ledger'}
        onRetry={fetchEvent}
      />
    );
  }

  return (
    <div className="space-y-6">
      {/* Header bar */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-3">
          <Button
            variant="ghost"
            size="sm"
            onClick={() => navigate('/audit')}
            leftIcon={<ArrowLeftIcon className="w-4 h-4" />}
          >
            Back to Audit Trail
          </Button>
          <div>
            <div className="flex items-center gap-2">
              <h1 className="text-xl font-bold font-mono tracking-tight text-text-primary">
                {event.action}
              </h1>
              {getOutcomeBadge(event.outcome)}
              <span
                style={{
                  fontSize: '0.7rem',
                  fontWeight: 700,
                  textTransform: 'uppercase',
                  padding: '0.2rem 0.5rem',
                  borderRadius: '4px',
                  backgroundColor: '#6366f122',
                  color: '#818cf8',
                  border: '1px solid #6366f144',
                }}
              >
                {event.event_type || 'SECURITY_EVENT'}
              </span>
            </div>
            <p className="text-xs text-text-tertiary font-mono mt-0.5">
              Event ID: {event.id} | Timestamp: {new Date(event.created_at).toLocaleString()}
            </p>
          </div>
        </div>

        {/* View Mode Toggle */}
        <div className="flex items-center gap-2 bg-bg-secondary p-1 rounded border border-border-default">
          <button
            type="button"
            className={`px-3 py-1 text-xs font-medium rounded ${
              viewMode === 'structured'
                ? 'bg-accent-primary text-white'
                : 'text-text-secondary hover:text-text-primary'
            }`}
            onClick={() => setViewMode('structured')}
          >
            Structured View
          </button>
          <button
            type="button"
            className={`px-3 py-1 text-xs font-medium rounded ${
              viewMode === 'raw'
                ? 'bg-accent-primary text-white'
                : 'text-text-secondary hover:text-text-primary'
            }`}
            onClick={() => setViewMode('raw')}
          >
            Advanced / Raw JSON
          </button>
        </div>
      </div>

      {/* Structured Forensic View */}
      {viewMode === 'structured' ? (
        <>
          {/* Identity & Scope Grid */}
          <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
            <div className="p-4 rounded-lg bg-bg-secondary border border-border-default">
              <span className="text-text-tertiary uppercase text-[10px] block">Actor Resolution</span>
              <div className="flex items-center gap-2 mt-1">
                {event.actor_type === 'USER' ? (
                  <UserIcon size={14} className="text-blue-400" />
                ) : event.actor_type === 'AGENT' ? (
                  <BotIcon size={14} className="text-purple-400" />
                ) : (
                  <ShieldCheckIcon size={14} className="text-zinc-400" />
                )}
                <span className="font-semibold text-text-primary text-xs">
                  {event.actor_type || (event.user_id ? 'USER' : event.agent_id ? 'AGENT' : 'SYSTEM')}
                </span>
              </div>
              <span className="text-[11px] text-text-muted mt-1 block font-mono truncate" title={event.actor_id || event.user_id || event.agent_id || ''}>
                {event.actor_display || event.actor_id || event.user_id || event.agent_id || 'Platform System'}
              </span>
            </div>

            <div className="p-4 rounded-lg bg-bg-secondary border border-border-default">
              <span className="text-text-tertiary uppercase text-[10px] block">Resource Target</span>
              <span className="font-semibold text-accent-primary text-xs mt-1 block">
                {event.resource_type || event.target_type || 'System Entity'}
              </span>
              <span className="text-[11px] text-text-muted mt-1 block font-mono truncate">
                ID: {event.resource_id || event.target_id || 'N/A'}
              </span>
            </div>

            <div className="p-4 rounded-lg bg-bg-secondary border border-border-default">
              <span className="text-text-tertiary uppercase text-[10px] block">Request Correlation ID</span>
              {event.request_id ? (
                <div className="flex items-center justify-between mt-1">
                  <span className="font-mono text-xs text-blue-400 truncate max-w-[140px]" title={event.request_id}>
                    {event.request_id}
                  </span>
                  <button
                    type="button"
                    onClick={copyRequestId}
                    className="text-text-muted hover:text-text-primary p-1"
                    title="Copy Request ID"
                  >
                    {copiedReqId ? <CheckIcon size={12} color="#10b981" /> : <CopyIcon size={12} />}
                  </button>
                </div>
              ) : (
                <span className="text-xs text-text-muted mt-1 block font-mono">None assigned</span>
              )}
              <span className="text-[10px] text-text-muted mt-1 block">End-to-end tracing token</span>
            </div>

            <div className="p-4 rounded-lg bg-bg-secondary border border-border-default">
              <span className="text-text-tertiary uppercase text-[10px] block">Network Context</span>
              <span className="font-mono text-xs text-text-secondary mt-1 block">
                IP: {event.ip_address || '127.0.0.1'}
              </span>
              <span className="text-[10px] text-text-muted mt-1 block truncate" title={event.user_agent || 'Custode Core'}>
                UA: {event.user_agent ? event.user_agent.slice(0, 30) + '...' : 'System internal'}
              </span>
            </div>
          </div>

          {/* Reason / Narrative Note */}
          {event.reason && (
            <SurfaceCard title="Security Outcome & Justification">
              <p className="text-sm text-text-primary bg-bg-tertiary/60 p-3 rounded border border-border-subtle font-mono">
                {event.reason}
              </p>
            </SurfaceCard>
          )}

          {/* Quick Investigation Links */}
          <SurfaceCard title="Correlated Security Artifacts & Actions">
            <div className="flex items-center gap-3 flex-wrap">
              {(event.resource_type === 'runtime_action' || event.metadata?.runtime_action_id) && (
                <Button
                  variant="outline"
                  size="sm"
                  onClick={() =>
                    navigate(
                      `/runtime-actions/${event.resource_id || event.metadata?.runtime_action_id}`
                    )
                  }
                >
                  Inspect Runtime Action Forensics →
                </Button>
              )}
              {(event.resource_type === 'execution' || event.metadata?.execution_id) && (
                <Button
                  variant="outline"
                  size="sm"
                  onClick={() =>
                    navigate(`/executions/${event.resource_id || event.metadata?.execution_id}`)
                  }
                >
                  Inspect Execution Log →
                </Button>
              )}
              {(event.resource_type === 'decision' || event.metadata?.decision_id) && (
                <Button
                  variant="outline"
                  size="sm"
                  onClick={() =>
                    navigate(`/decisions/${event.resource_id || event.metadata?.decision_id}`)
                  }
                >
                  Inspect Decision Trace →
                </Button>
              )}
              {event.resource_type === 'approval' && (
                <Button
                  variant="outline"
                  size="sm"
                  onClick={() => navigate('/approvals')}
                >
                  Open Governance Inbox →
                </Button>
              )}
              <Button
                variant="ghost"
                size="sm"
                onClick={() => navigate('/audit')}
              >
                View Full Audit Ledger
              </Button>
            </div>
          </SurfaceCard>

          {/* Sanitized Event Metadata */}
          <SurfaceCard title="Sanitized Event Metadata (Confidential Secrets Redacted)">
            <CodeView
              data={event.metadata || {}}
              label="TAMPER-EVIDENT RECORD PAYLOAD"
              maxHeight="360px"
            />
          </SurfaceCard>
        </>
      ) : (
        /* Raw JSON Full Event Object */
        <SurfaceCard title="Complete Authoritative Audit Event Record">
          <CodeView
            data={event}
            label="AUDIT_EVENT_DATABASE_RECORD"
            maxHeight="520px"
          />
        </SurfaceCard>
      )}
    </div>
  );
};
