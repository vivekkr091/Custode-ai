import React, { useState, useEffect } from 'react';
import { useOrg } from '../context/OrgContext';
import { permissionsApi } from '../api/permissions';
import { agentsApi } from '../api/agents';
import { toolsApi } from '../api/tools';
import { Agent, Permission, Tool, ToolOperation } from '../types';
import { SurfaceCard } from '../components/common/Card';
import { EnvironmentBadge, StatusBadge } from '../components/common/Badges';
import { LoadingState, ErrorState, EmptyState } from '../components/common/FeedbackStates';
import { Button } from '../components/common/Button';
import { Modal } from '../components/common/Modal';
import { LockIcon, PlusIcon, RefreshIcon, ShieldIcon } from '../components/common/Icons';

export const PermissionsPage: React.FC = () => {
  const { currentOrg } = useOrg();

  const [permissions, setPermissions] = useState<Permission[]>([]);
  const [agents, setAgents] = useState<Agent[]>([]);
  const [tools, setTools] = useState<Tool[]>([]);
  const [operations, setOperations] = useState<ToolOperation[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  // Create Permission Modal
  const [isModalOpen, setIsModalOpen] = useState(false);
  const [creating, setCreating] = useState(false);
  const [formData, setFormData] = useState({
    agent_id: '',
    tool_id: '',
    operation_id: '',
    environment: 'development',
    effect: 'allow' as 'allow' | 'deny',
    expires_at: '',
  });

  const loadData = async () => {
    if (!currentOrg) return;
    setLoading(true);
    setError(null);
    try {
      const [permsRes, agentsRes, toolsRes] = await Promise.all([
        permissionsApi.list(currentOrg.id, { limit: 100 }),
        agentsApi.list(currentOrg.id, { limit: 100 }).catch(() => ({ items: [], total: 0 })),
        toolsApi.list(currentOrg.id, { limit: 100 }).catch(() => ({ items: [], total: 0 })),
      ]);
      setPermissions(permsRes.items || []);
      setAgents(agentsRes.items || []);
      setTools(toolsRes.items || []);
    } catch (err: any) {
      setError(err.message || 'Failed to load permissions.');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadData();
  }, [currentOrg]);

  // Load operations when tool selected in modal
  useEffect(() => {
    if (currentOrg && formData.tool_id) {
      toolsApi.listOperations(currentOrg.id, formData.tool_id)
        .then((res) => {
          setOperations(res.items || []);
          if (res.items?.length > 0) {
            setFormData((prev) => ({ ...prev, operation_id: res.items[0].id }));
          }
        })
        .catch(() => setOperations([]));
    }
  }, [currentOrg, formData.tool_id]);

  const handleCreatePermission = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!currentOrg) return;
    setCreating(true);
    try {
      await permissionsApi.create(currentOrg.id, {
        agent_id: formData.agent_id,
        tool_id: formData.tool_id,
        operation_id: formData.operation_id,
        environment: formData.environment,
        effect: formData.effect,
        expires_at: formData.expires_at || undefined,
      });
      setIsModalOpen(false);
      await loadData();
    } catch (err: any) {
      alert(`Error creating permission grant: ${err.message}`);
    } finally {
      setCreating(false);
    }
  };

  const handleRevoke = async (id: string) => {
    if (!currentOrg) return;
    if (!window.confirm('Are you sure you want to revoke this permission?')) return;
    try {
      await permissionsApi.revoke(currentOrg.id, id);
      await loadData();
    } catch (err: any) {
      alert(`Error revoking permission: ${err.message}`);
    }
  };

  return (
    <div className="permissions-page">
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '20px' }}>
        <div>
          <h2 style={{ fontSize: '20px', fontWeight: 700 }}>Agent-to-Tool Authorization</h2>
          <p className="text-muted" style={{ fontSize: '13px' }}>
            Explicit least-privilege capability assignments controlling which agents can call which tool operations.
          </p>
        </div>
        <Button
          variant="primary"
          size="md"
          icon={<PlusIcon size={16} />}
          onClick={() => {
            if (agents.length > 0 && tools.length > 0) {
              setFormData((prev) => ({
                ...prev,
                agent_id: agents[0].id,
                tool_id: tools[0].id,
              }));
            }
            setIsModalOpen(true);
          }}
        >
          Grant Permission
        </Button>
      </div>

      {/* Explanatory Policy Separation Callout */}
      <div style={{ background: 'rgba(14, 165, 233, 0.08)', border: '1px solid rgba(14, 165, 233, 0.25)', borderRadius: 'var(--radius-md)', padding: '12px 16px', marginBottom: '20px', display: 'flex', alignItems: 'center', gap: '12px' }}>
        <ShieldIcon size={20} className="text-cyan" />
        <span style={{ fontSize: '12px', color: 'var(--text-secondary)' }}>
          <strong>Architecture Principle:</strong> Permissions define whether an agent is explicitly authorized to invoke a specific tool operation. Final runtime decisions may additionally depend on organizational policy rules and contextual risk evaluation.
        </span>
      </div>

      <SurfaceCard>
        {loading ? (
          <LoadingState message="Evaluating permission bindings..." />
        ) : error ? (
          <ErrorState message={error} onRetry={loadData} />
        ) : permissions.length === 0 ? (
          <EmptyState
            title="No Permissions Defined"
            description="Grant explicit permissions to allow registered agents to invoke tool operations."
            action={
              <Button variant="primary" size="sm" onClick={() => setIsModalOpen(true)} icon={<PlusIcon size={14} />}>
                Create Permission Grant
              </Button>
            }
          />
        ) : (
          <div className="table-responsive">
            <table className="data-table">
              <thead>
                <tr>
                  <th>Agent</th>
                  <th>Tool</th>
                  <th>Operation</th>
                  <th>Environment</th>
                  <th>Effect</th>
                  <th>Status</th>
                  <th>Expires</th>
                  <th>Action</th>
                </tr>
              </thead>
              <tbody>
                {permissions.map((p) => {
                  const agentObj = agents.find((a) => a.id === p.agent_id);
                  const toolObj = tools.find((t) => t.id === p.tool_id);
                  return (
                    <tr key={p.id}>
                      <td>
                        <strong>{agentObj ? agentObj.name : `${p.agent_id.slice(0, 8)}...`}</strong>
                      </td>
                      <td className="font-mono text-muted">
                        {toolObj ? toolObj.name : `${p.tool_id.slice(0, 8)}...`}
                      </td>
                      <td className="font-mono">{p.operation_id.slice(0, 8)}...</td>
                      <td><EnvironmentBadge environment={p.environment} /></td>
                      <td>
                        <span className={`badge ${p.effect === 'allow' ? 'badge-status-success' : 'badge-status-danger'}`}>
                          {p.effect.toUpperCase()}
                        </span>
                      </td>
                      <td><StatusBadge status={p.status} /></td>
                      <td>{p.expires_at ? new Date(p.expires_at).toLocaleDateString() : 'Permanent'}</td>
                      <td>
                        {p.status === 'active' && (
                          <Button variant="ghost" size="sm" onClick={() => handleRevoke(p.id)} style={{ color: 'var(--color-rose)' }}>
                            Revoke
                          </Button>
                        )}
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        )}
      </SurfaceCard>

      {/* Grant Permission Modal */}
      <Modal
        isOpen={isModalOpen}
        onClose={() => setIsModalOpen(false)}
        title="Grant Agent Capability Permission"
        subtitle="Bind an agent identity to an authorized tool operation"
      >
        <form onSubmit={handleCreatePermission}>
          <div className="form-group">
            <label className="form-label">Target Agent *</label>
            <select
              className="form-select"
              value={formData.agent_id}
              onChange={(e) => setFormData({ ...formData, agent_id: e.target.value })}
              required
            >
              <option value="">Select Agent Identity</option>
              {agents.map((a) => (
                <option key={a.id} value={a.id}>{a.name} ({a.environment})</option>
              ))}
            </select>
          </div>

          <div className="form-group">
            <label className="form-label">Target Capability / Tool *</label>
            <select
              className="form-select"
              value={formData.tool_id}
              onChange={(e) => setFormData({ ...formData, tool_id: e.target.value })}
              required
            >
              <option value="">Select Connected Tool</option>
              {tools.map((t) => (
                <option key={t.id} value={t.id}>{t.name} ({t.tool_type})</option>
              ))}
            </select>
          </div>

          <div className="form-group">
            <label className="form-label">Tool Operation *</label>
            <select
              className="form-select"
              value={formData.operation_id}
              onChange={(e) => setFormData({ ...formData, operation_id: e.target.value })}
              required
            >
              <option value="">Select Operation</option>
              {operations.map((op) => (
                <option key={op.id} value={op.id}>{op.name} [{op.operation_type}] (Risk: {op.risk_level})</option>
              ))}
            </select>
          </div>

          <div className="form-group">
            <label className="form-label">Environment Tier</label>
            <select
              className="form-select"
              value={formData.environment}
              onChange={(e) => setFormData({ ...formData, environment: e.target.value })}
            >
              <option value="development">Development</option>
              <option value="staging">Staging</option>
              <option value="production">Production</option>
            </select>
          </div>

          <div className="form-group">
            <label className="form-label">Permission Effect</label>
            <select
              className="form-select"
              value={formData.effect}
              onChange={(e) => setFormData({ ...formData, effect: e.target.value as 'allow' | 'deny' })}
            >
              <option value="allow">ALLOW (Explicit capability authorization)</option>
              <option value="deny">DENY (Explicit prohibition)</option>
            </select>
          </div>

          <div className="modal-footer" style={{ margin: '-20px', marginTop: '20px' }}>
            <Button type="button" variant="outline" onClick={() => setIsModalOpen(false)}>
              Cancel
            </Button>
            <Button type="submit" variant="primary" loading={creating}>
              Grant Permission
            </Button>
          </div>
        </form>
      </Modal>
    </div>
  );
};
