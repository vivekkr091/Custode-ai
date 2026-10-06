import React, { useState, useEffect } from 'react';
import { useOrg } from '../context/OrgContext';
import { agentsApi } from '../api/agents';
import { permissionsApi } from '../api/permissions';
import { runtimeActionsApi } from '../api/runtimeActions';
import { behaviorApi } from '../api/behavior';
import { Agent, AgentCredential, AgentBehaviorProfile, Permission, RuntimeAction } from '../types';
import { SurfaceCard } from '../components/common/Card';
import { EnvironmentBadge, StatusBadge } from '../components/common/Badges';
import { LoadingState, ErrorState, EmptyState } from '../components/common/FeedbackStates';
import { Button } from '../components/common/Button';
import { Modal } from '../components/common/Modal';
import { CodeView } from '../components/common/CodeView';
import { Link, useNavigate } from '../router/Router';
import {
  AlertTriangleIcon,
  BotIcon,
  CheckIcon,
  CopyIcon,
  KeyIcon,
  LockIcon,
  PlusIcon,
  RefreshIcon,
  TerminalIcon,
} from '../components/common/Icons';

export const AgentDetailPage: React.FC<{ agentId?: string }> = ({ agentId }) => {
  const { currentOrg } = useOrg();
  const navigate = useNavigate();

  const [agent, setAgent] = useState<Agent | null>(null);
  const [credentials, setCredentials] = useState<AgentCredential[]>([]);
  const [permissions, setPermissions] = useState<Permission[]>([]);
  const [actions, setActions] = useState<RuntimeAction[]>([]);
  const [behaviorProfile, setBehaviorProfile] = useState<AgentBehaviorProfile | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  // Modals
  const [isCredModalOpen, setIsCredModalOpen] = useState(false);
  const [credName, setCredName] = useState('');
  const [generatingCred, setGeneratingCred] = useState(false);
  const [generatedToken, setGeneratedToken] = useState<string | null>(null);
  const [copiedToken, setCopiedToken] = useState(false);

  const loadAgentDetails = async () => {
    if (!currentOrg || !agentId) return;
    setLoading(true);
    setError(null);
    try {
      const [agentData, credsData, permsData, actionsData, behaviorData] = await Promise.all([
        agentsApi.get(currentOrg.id, agentId),
        agentsApi.listCredentials(currentOrg.id, agentId).catch(() => ({ items: [], total: 0 })),
        permissionsApi.list(currentOrg.id, { agent_id: agentId }).catch(() => ({ items: [], total: 0 })),
        runtimeActionsApi.list(currentOrg.id, { agent_id: agentId, limit: 10 }).catch(() => ({ items: [], total: 0 })),
        behaviorApi.getProfile(currentOrg.id, agentId).catch(() => null),
      ]);
      setAgent(agentData);
      setCredentials(credsData.items || []);
      setPermissions(permsData.items || []);
      setActions(actionsData.items || []);
      setBehaviorProfile(behaviorData);
    } catch (err: any) {
      setError(err.message || 'Failed to load agent details.');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadAgentDetails();
  }, [currentOrg, agentId]);

  const handleStatusChange = async (action: 'suspend' | 'revoke' | 'reactivate') => {
    if (!currentOrg || !agent) return;
    const confirmMsg = `Are you sure you want to ${action} agent "${agent.name}"?`;
    if (!window.confirm(confirmMsg)) return;
    try {
      if (action === 'suspend') await agentsApi.suspend(currentOrg.id, agent.id);
      if (action === 'revoke') await agentsApi.revoke(currentOrg.id, agent.id);
      if (action === 'reactivate') await agentsApi.reactivate(currentOrg.id, agent.id);
      await loadAgentDetails();
    } catch (err: any) {
      alert(`Error updating agent status: ${err.message}`);
    }
  };

  const handleGenerateCredential = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!currentOrg || !agent) return;
    setGeneratingCred(true);
    try {
      const res = await agentsApi.createCredential(currentOrg.id, agent.id, {
        name: credName || 'Agent API Key',
      });
      setGeneratedToken(res.raw_token);
      setCredName('');
      await loadAgentDetails();
    } catch (err: any) {
      alert(`Failed to create credential: ${err.message}`);
    } finally {
      setGeneratingCred(false);
    }
  };

  const handleRevokeCredential = async (credId: string) => {
    if (!currentOrg || !agent) return;
    if (!window.confirm('Are you sure you want to revoke this agent credential? This action is immediate.')) return;
    try {
      await agentsApi.revokeCredential(currentOrg.id, agent.id, credId);
      await loadAgentDetails();
    } catch (err: any) {
      alert(`Error revoking credential: ${err.message}`);
    }
  };

  if (loading) return <LoadingState message="Loading agent identity records..." />;
  if (error || !agent) return <ErrorState message={error || 'Agent not found'} onRetry={loadAgentDetails} />;

  return (
    <div className="agent-detail-page">
      {/* Breadcrumb Navigation */}
      <div style={{ marginBottom: '16px' }}>
        <Link to="/agents" style={{ color: 'var(--text-muted)', textDecoration: 'none', fontSize: '13px' }}>
          ← Back to Agent Registry
        </Link>
      </div>

      {/* Header Profile Card */}
      <SurfaceCard>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', flexWrap: 'wrap', gap: '16px' }}>
          <div>
            <div style={{ display: 'flex', alignItems: 'center', gap: '12px', marginBottom: '8px' }}>
              <div className="brand-shield-glow">
                <BotIcon size={24} />
              </div>
              <div>
                <h2 style={{ fontSize: '20px', fontWeight: 700 }}>{agent.name}</h2>
                <div style={{ display: 'flex', alignItems: 'center', gap: '8px', marginTop: '4px' }}>
                  <span className="font-mono text-muted" style={{ fontSize: '12px' }}>{agent.slug}</span>
                  <EnvironmentBadge environment={agent.environment} />
                  <StatusBadge status={agent.status} />
                </div>
              </div>
            </div>
            <p className="text-muted" style={{ fontSize: '13px', maxWidth: '650px', marginTop: '8px' }}>
              {agent.description || 'No description provided.'}
            </p>
          </div>

          {/* Action Buttons */}
          <div style={{ display: 'flex', gap: '8px' }}>
            {agent.status === 'active' && (
              <Button variant="outline" size="sm" onClick={() => handleStatusChange('suspend')}>
                Suspend Agent
              </Button>
            )}
            {agent.status === 'suspended' && (
              <Button variant="outline" size="sm" onClick={() => handleStatusChange('reactivate')}>
                Reactivate Agent
              </Button>
            )}
            {agent.status !== 'revoked' && (
              <Button variant="danger" size="sm" onClick={() => handleStatusChange('revoke')}>
                Revoke Identity
              </Button>
            )}
          </div>
        </div>

        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(180px, 1fr))', gap: '16px', marginTop: '20px', paddingTop: '16px', borderTop: '1px solid var(--border-subtle)' }}>
          <div>
            <div className="text-muted" style={{ fontSize: '11px', fontWeight: 600 }}>AGENT UUID</div>
            <div className="font-mono" style={{ fontSize: '12px' }}>{agent.id}</div>
          </div>
          <div>
            <div className="text-muted" style={{ fontSize: '11px', fontWeight: 600 }}>CATEGORY</div>
            <div>{agent.agent_type}</div>
          </div>
          <div>
            <div className="text-muted" style={{ fontSize: '11px', fontWeight: 600 }}>REGISTERED DATE</div>
            <div>{new Date(agent.created_at).toLocaleString()}</div>
          </div>
        </div>
      </SurfaceCard>

      {/* Behavioral Baseline Profile */}
      <SurfaceCard
        title="Behavioral Baseline & Anomaly Telemetry"
        subtitle="Deterministic behavioral profiling based on historical actions, operational hours, and tool usage."
        actions={
          <Link to="/behavior-security" className="btn btn-outline btn-sm">
            View All Anomalies
          </Link>
        }
      >
        {behaviorProfile ? (
          <div>
            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(160px, 1fr))', gap: '16px', marginBottom: '16px' }}>
              <div style={{ background: 'var(--surface-hover)', padding: '12px', borderRadius: '8px' }}>
                <div className="text-muted" style={{ fontSize: '11px', fontWeight: 600 }}>BASELINE STATE</div>
                <div style={{ marginTop: '4px' }}>
                  <span
                    className={`badge ${
                      behaviorProfile.state === 'ESTABLISHED'
                        ? 'badge-success'
                        : behaviorProfile.state === 'LEARNING'
                        ? 'badge-warning'
                        : 'badge-neutral'
                    }`}
                  >
                    {behaviorProfile.state}
                  </span>
                </div>
              </div>

              <div style={{ background: 'var(--surface-hover)', padding: '12px', borderRadius: '8px' }}>
                <div className="text-muted" style={{ fontSize: '11px', fontWeight: 600 }}>ACTION VOLUME</div>
                <div style={{ fontSize: '16px', fontWeight: 700, marginTop: '4px' }}>
                  {behaviorProfile.action_count} actions
                </div>
              </div>

              <div style={{ background: 'var(--surface-hover)', padding: '12px', borderRadius: '8px' }}>
                <div className="text-muted" style={{ fontSize: '11px', fontWeight: 600 }}>RATE PROFILE</div>
                <div style={{ fontSize: '14px', fontWeight: 600, marginTop: '4px' }}>
                  {behaviorProfile.average_actions_per_hour.toFixed(1)} / hr avg
                </div>
                <div className="text-muted" style={{ fontSize: '11px' }}>
                  Peak: {behaviorProfile.peak_actions_per_hour.toFixed(1)} / hr
                </div>
              </div>

              <div style={{ background: 'var(--surface-hover)', padding: '12px', borderRadius: '8px' }}>
                <div className="text-muted" style={{ fontSize: '11px', fontWeight: 600 }}>OPERATIONAL HOURS</div>
                <div style={{ fontSize: '13px', fontWeight: 600, marginTop: '4px' }}>
                  {behaviorProfile.operational_hours}
                </div>
              </div>

              <div style={{ background: 'var(--surface-hover)', padding: '12px', borderRadius: '8px' }}>
                <div className="text-muted" style={{ fontSize: '11px', fontWeight: 600 }}>RECENT ANOMALIES</div>
                <div style={{ fontSize: '16px', fontWeight: 700, marginTop: '4px', color: behaviorProfile.recent_anomalies_count > 0 ? 'var(--color-danger, #ef4444)' : 'inherit' }}>
                  {behaviorProfile.recent_anomalies_count}
                </div>
              </div>
            </div>

            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '16px' }}>
              <div>
                <div className="text-muted" style={{ fontSize: '12px', fontWeight: 600, marginBottom: '6px' }}>
                  TYPICAL TOOLS ({behaviorProfile.typical_tools.length})
                </div>
                <div style={{ display: 'flex', flexWrap: 'wrap', gap: '6px' }}>
                  {behaviorProfile.typical_tools.length === 0 ? (
                    <span className="text-muted" style={{ fontSize: '12px' }}>No tools established yet</span>
                  ) : (
                    behaviorProfile.typical_tools.map((t) => (
                      <span key={t} className="badge badge-neutral font-mono" style={{ fontSize: '11px' }}>
                        {t}
                      </span>
                    ))
                  )}
                </div>
              </div>

              <div>
                <div className="text-muted" style={{ fontSize: '12px', fontWeight: 600, marginBottom: '6px' }}>
                  TYPICAL OPERATIONS ({behaviorProfile.typical_operations.length})
                </div>
                <div style={{ display: 'flex', flexWrap: 'wrap', gap: '6px' }}>
                  {behaviorProfile.typical_operations.length === 0 ? (
                    <span className="text-muted" style={{ fontSize: '12px' }}>No operations established yet</span>
                  ) : (
                    behaviorProfile.typical_operations.map((op) => (
                      <span key={op} className="badge badge-neutral font-mono" style={{ fontSize: '11px' }}>
                        {op}
                      </span>
                    ))
                  )}
                </div>
              </div>
            </div>
          </div>
        ) : (
          <EmptyState
            title="Baseline Profile Initializing"
            description="Agent behavioral profile is currently being aggregated from runtime telemetry."
          />
        )}
      </SurfaceCard>

      {/* Cryptographic Credentials Section */}
      <SurfaceCard
        title="Agent Credentials & Authentication"
        subtitle="HMAC-SHA256 cryptographically hashed tokens. Raw secrets are NEVER persisted."
        actions={
          agent.status === 'active' ? (
            <Button
              variant="primary"
              size="sm"
              icon={<PlusIcon size={14} />}
              onClick={() => {
                setGeneratedToken(null);
                setIsCredModalOpen(true);
              }}
            >
              Generate Credential
            </Button>
          ) : undefined
        }
      >
        {credentials.length === 0 ? (
          <EmptyState
            title="No Active Credentials"
            description="Generate an authenticated API credential token for this agent to enable RuntimeAction submissions."
          />
        ) : (
          <div className="table-responsive">
            <table className="data-table">
              <thead>
                <tr>
                  <th>Credential Name</th>
                  <th>Key Prefix</th>
                  <th>Status</th>
                  <th>Created</th>
                  <th>Last Used</th>
                  <th>Expires</th>
                  <th>Action</th>
                </tr>
              </thead>
              <tbody>
                {credentials.map((cred) => (
                  <tr key={cred.id}>
                    <td><strong>{cred.name}</strong></td>
                    <td className="font-mono text-muted">{cred.credential_prefix}...</td>
                    <td><StatusBadge status={cred.status} /></td>
                    <td>{new Date(cred.created_at).toLocaleDateString()}</td>
                    <td>{cred.last_used_at ? new Date(cred.last_used_at).toLocaleDateString() : 'Never'}</td>
                    <td>{cred.expires_at ? new Date(cred.expires_at).toLocaleDateString() : 'Never'}</td>
                    <td>
                      {cred.status === 'active' && (
                        <Button
                          variant="ghost"
                          size="sm"
                          onClick={() => handleRevokeCredential(cred.id)}
                          style={{ color: 'var(--color-rose)' }}
                        >
                          Revoke
                        </Button>
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </SurfaceCard>

      {/* Granted Permissions Section */}
      <SurfaceCard
        title="Explicit Granted Permissions"
        subtitle="Least-privilege authorization rules granted to this specific agent"
        actions={<Link to="/permissions" className="btn btn-outline btn-sm">Manage Permissions</Link>}
      >
        {permissions.length === 0 ? (
          <EmptyState
            title="No Direct Permissions"
            description="This agent has not been assigned explicit tool invocation permissions yet."
          />
        ) : (
          <div className="table-responsive">
            <table className="data-table">
              <thead>
                <tr>
                  <th>Permission ID</th>
                  <th>Tool ID</th>
                  <th>Operation ID</th>
                  <th>Environment</th>
                  <th>Effect</th>
                  <th>Status</th>
                </tr>
              </thead>
              <tbody>
                {permissions.map((p) => (
                  <tr key={p.id}>
                    <td className="font-mono">{p.id.slice(0, 8)}...</td>
                    <td className="font-mono">{p.tool_id.slice(0, 8)}...</td>
                    <td className="font-mono">{p.operation_id.slice(0, 8)}...</td>
                    <td><EnvironmentBadge environment={p.environment} /></td>
                    <td>
                      <span className={`badge ${p.effect === 'allow' ? 'badge-status-success' : 'badge-status-danger'}`}>
                        {p.effect.toUpperCase()}
                      </span>
                    </td>
                    <td><StatusBadge status={p.status} /></td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </SurfaceCard>

      {/* Generate Credential Modal */}
      <Modal
        isOpen={isCredModalOpen}
        onClose={() => setIsCredModalOpen(false)}
        title={generatedToken ? 'Credential Generated Successfully' : 'Generate Agent API Token'}
        subtitle={
          generatedToken
            ? 'CRITICAL: Copy this token immediately. It will NEVER be shown again.'
            : 'Provisions a new cryptographic bearer token scoped to this agent identity.'
        }
      >
        {generatedToken ? (
          <div>
            <div style={{ background: 'rgba(245, 158, 11, 0.12)', border: '1px solid var(--color-amber)', borderRadius: 'var(--radius-md)', padding: '12px 16px', marginBottom: '16px' }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: '8px', color: 'var(--color-amber)', fontWeight: 700, fontSize: '13px', marginBottom: '4px' }}>
                <AlertTriangleIcon size={16} />
                <span>ONE-TIME TOKEN DISCLOSURE WARNING</span>
              </div>
              <p style={{ fontSize: '12px', color: 'var(--text-secondary)' }}>
                CUSTODE stores only SHA-256 salted hashes of agent tokens. If you lose this key, you must generate a new one.
              </p>
            </div>

            <div className="code-viewer-container">
              <div className="code-viewer-header">
                <span className="code-viewer-label">RAW BEARER TOKEN</span>
                <button
                  className="code-copy-btn"
                  onClick={() => {
                    navigator.clipboard.writeText(generatedToken);
                    setCopiedToken(true);
                    setTimeout(() => setCopiedToken(false), 2000);
                  }}
                >
                  {copiedToken ? (
                    <>
                      <CheckIcon size={13} />
                      <span>Copied!</span>
                    </>
                  ) : (
                    <>
                      <CopyIcon size={13} />
                      <span>Copy Key</span>
                    </>
                  )}
                </button>
              </div>
              <div style={{ padding: '12px', fontFamily: 'var(--font-mono)', fontSize: '13px', color: '#10b981', wordBreak: 'break-all' }}>
                {generatedToken}
              </div>
            </div>

            <div style={{ marginTop: '20px', display: 'flex', justifyContent: 'flex-end' }}>
              <Button variant="primary" onClick={() => setIsCredModalOpen(false)}>
                I have securely saved this token
              </Button>
            </div>
          </div>
        ) : (
          <form onSubmit={handleGenerateCredential}>
            <div className="form-group">
              <label className="form-label">Credential Name</label>
              <input
                type="text"
                className="form-input"
                placeholder="e.g. Primary Production Token"
                value={credName}
                onChange={(e) => setCredName(e.target.value)}
                required
              />
            </div>
            <div className="modal-footer" style={{ margin: '-20px', marginTop: '20px' }}>
              <Button type="button" variant="outline" onClick={() => setIsCredModalOpen(false)}>
                Cancel
              </Button>
              <Button type="submit" variant="primary" loading={generatingCred}>
                Generate Token
              </Button>
            </div>
          </form>
        )}
      </Modal>
    </div>
  );
};
