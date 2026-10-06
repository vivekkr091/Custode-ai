import React, { useState, useEffect } from 'react';
import { useOrg } from '../context/OrgContext';
import { toolsApi } from '../api/tools';
import { Tool, ToolOperation, OperationType, RiskLevel } from '../types';
import { SurfaceCard } from '../components/common/Card';
import { EnvironmentBadge, RiskBadge, StatusBadge } from '../components/common/Badges';
import { LoadingState, ErrorState, EmptyState } from '../components/common/FeedbackStates';
import { Button } from '../components/common/Button';
import { Modal } from '../components/common/Modal';
import { Link } from '../router/Router';
import { PlusIcon, WrenchIcon } from '../components/common/Icons';

export const ToolDetailPage: React.FC<{ toolId?: string }> = ({ toolId }) => {
  const { currentOrg } = useOrg();

  const [tool, setTool] = useState<Tool | null>(null);
  const [operations, setOperations] = useState<ToolOperation[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  // Add Operation Modal
  const [isOpModalOpen, setIsOpModalOpen] = useState(false);
  const [creatingOp, setCreatingOp] = useState(false);
  const [opFormData, setOpFormData] = useState({
    name: '',
    slug: '',
    description: '',
    operation_type: 'read' as OperationType,
    risk_level: 'medium' as RiskLevel,
  });

  const loadTool = async () => {
    if (!currentOrg || !toolId) return;
    setLoading(true);
    setError(null);
    try {
      const [toolData, opsData] = await Promise.all([
        toolsApi.get(currentOrg.id, toolId),
        toolsApi.listOperations(currentOrg.id, toolId).catch(() => ({ items: [], total: 0 })),
      ]);
      setTool(toolData);
      setOperations(opsData.items || []);
    } catch (err: any) {
      setError(err.message || 'Failed to load tool details.');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadTool();
  }, [currentOrg, toolId]);

  const handleToolStatus = async (action: 'suspend' | 'revoke' | 'reactivate') => {
    if (!currentOrg || !tool) return;
    if (!window.confirm(`Are you sure you want to ${action} tool "${tool.name}"?`)) return;
    try {
      if (action === 'suspend') await toolsApi.suspend(currentOrg.id, tool.id);
      if (action === 'revoke') await toolsApi.revoke(currentOrg.id, tool.id);
      if (action === 'reactivate') await toolsApi.reactivate(currentOrg.id, tool.id);
      await loadTool();
    } catch (err: any) {
      alert(`Error updating tool status: ${err.message}`);
    }
  };

  const handleCreateOperation = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!currentOrg || !tool) return;
    setCreatingOp(true);
    try {
      await toolsApi.createOperation(currentOrg.id, tool.id, {
        name: opFormData.name,
        slug: opFormData.slug || undefined,
        description: opFormData.description || undefined,
        operation_type: opFormData.operation_type,
        risk_level: opFormData.risk_level,
      });
      setIsOpModalOpen(false);
      setOpFormData({ name: '', slug: '', description: '', operation_type: 'read', risk_level: 'medium' });
      await loadTool();
    } catch (err: any) {
      alert(`Failed to add operation: ${err.message}`);
    } finally {
      setCreatingOp(false);
    }
  };

  const handleOpStatus = async (opId: string, action: 'suspend' | 'revoke' | 'reactivate') => {
    if (!currentOrg || !tool) return;
    try {
      if (action === 'suspend') await toolsApi.suspendOperation(currentOrg.id, tool.id, opId);
      if (action === 'revoke') await toolsApi.revokeOperation(currentOrg.id, tool.id, opId);
      if (action === 'reactivate') await toolsApi.reactivateOperation(currentOrg.id, tool.id, opId);
      await loadTool();
    } catch (err: any) {
      alert(`Error updating operation: ${err.message}`);
    }
  };

  if (loading) return <LoadingState message="Loading capability specification..." />;
  if (error || !tool) return <ErrorState message={error || 'Tool not found'} onRetry={loadTool} />;

  return (
    <div className="tool-detail-page">
      <div style={{ marginBottom: '16px' }}>
        <Link to="/tools" style={{ color: 'var(--text-muted)', textDecoration: 'none', fontSize: '13px' }}>
          ← Back to Capabilities Registry
        </Link>
      </div>

      {/* Header Info */}
      <SurfaceCard>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', flexWrap: 'wrap', gap: '16px' }}>
          <div>
            <div style={{ display: 'flex', alignItems: 'center', gap: '12px', marginBottom: '8px' }}>
              <div className="brand-shield-glow">
                <WrenchIcon size={24} />
              </div>
              <div>
                <h2 style={{ fontSize: '20px', fontWeight: 700 }}>{tool.name}</h2>
                <div style={{ display: 'flex', alignItems: 'center', gap: '8px', marginTop: '4px' }}>
                  <span className="font-mono text-muted" style={{ fontSize: '12px' }}>{tool.slug}</span>
                  <span className="badge badge-status-neutral">{tool.tool_type.toUpperCase()}</span>
                  <EnvironmentBadge environment={tool.environment} />
                  <StatusBadge status={tool.status} />
                </div>
              </div>
            </div>
            <p className="text-muted" style={{ fontSize: '13px', maxWidth: '650px', marginTop: '8px' }}>
              {tool.description || 'No capability description recorded.'}
            </p>
          </div>

          <div style={{ display: 'flex', gap: '8px' }}>
            {tool.status === 'active' && (
              <Button variant="outline" size="sm" onClick={() => handleToolStatus('suspend')}>
                Suspend Tool
              </Button>
            )}
            {tool.status === 'suspended' && (
              <Button variant="outline" size="sm" onClick={() => handleToolStatus('reactivate')}>
                Reactivate Tool
              </Button>
            )}
            {tool.status !== 'revoked' && (
              <Button variant="danger" size="sm" onClick={() => handleToolStatus('revoke')}>
                Revoke Capability
              </Button>
            )}
          </div>
        </div>

        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(180px, 1fr))', gap: '16px', marginTop: '20px', paddingTop: '16px', borderTop: '1px solid var(--border-subtle)' }}>
          <div>
            <div className="text-muted" style={{ fontSize: '11px', fontWeight: 600 }}>TOOL UUID</div>
            <div className="font-mono" style={{ fontSize: '12px' }}>{tool.id}</div>
          </div>
          <div>
            <div className="text-muted" style={{ fontSize: '11px', fontWeight: 600 }}>ENDPOINT</div>
            <div className="font-mono text-muted" style={{ fontSize: '12px' }}>{tool.endpoint || '—'}</div>
          </div>
          <div>
            <div className="text-muted" style={{ fontSize: '11px', fontWeight: 600 }}>REGISTERED DATE</div>
            <div>{new Date(tool.created_at).toLocaleString()}</div>
          </div>
        </div>
      </SurfaceCard>

      {/* Scoped Operations List */}
      <SurfaceCard
        title="Callable Tool Operations"
        subtitle="Individual actions exposed by this tool with baseline risk scoring"
        actions={
          tool.status === 'active' ? (
            <Button
              variant="primary"
              size="sm"
              icon={<PlusIcon size={14} />}
              onClick={() => setIsOpModalOpen(true)}
            >
              Add Operation
            </Button>
          ) : undefined
        }
      >
        {operations.length === 0 ? (
          <EmptyState
            title="No Operations Defined"
            description="Add granular callable operations (e.g. read, write, execute) to define permissions and baseline risk."
            action={
              <Button variant="primary" size="sm" onClick={() => setIsOpModalOpen(true)} icon={<PlusIcon size={14} />}>
                Add First Operation
              </Button>
            }
          />
        ) : (
          <div className="table-responsive">
            <table className="data-table">
              <thead>
                <tr>
                  <th>Operation</th>
                  <th>Slug</th>
                  <th>Action Type</th>
                  <th>Baseline Risk</th>
                  <th>Status</th>
                  <th>Action</th>
                </tr>
              </thead>
              <tbody>
                {operations.map((op) => (
                  <tr key={op.id}>
                    <td>
                      <div>
                        <strong>{op.name}</strong>
                        {op.description && <div className="text-muted" style={{ fontSize: '11px' }}>{op.description}</div>}
                      </div>
                    </td>
                    <td className="font-mono text-muted">{op.slug}</td>
                    <td>
                      <span className="badge badge-status-neutral">{op.operation_type.toUpperCase()}</span>
                    </td>
                    <td>
                      <RiskBadge level={op.risk_level} />
                    </td>
                    <td><StatusBadge status={op.status} /></td>
                    <td>
                      {op.status === 'active' ? (
                        <Button variant="ghost" size="sm" onClick={() => handleOpStatus(op.id, 'suspend')}>
                          Suspend
                        </Button>
                      ) : op.status === 'suspended' ? (
                        <Button variant="ghost" size="sm" onClick={() => handleOpStatus(op.id, 'reactivate')}>
                          Reactivate
                        </Button>
                      ) : null}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </SurfaceCard>

      {/* Add Operation Modal */}
      <Modal
        isOpen={isOpModalOpen}
        onClose={() => setIsOpModalOpen(false)}
        title="Add Callable Operation"
        subtitle={`Defines a specific callable capability under ${tool.name}`}
      >
        <form onSubmit={handleCreateOperation}>
          <div className="form-group">
            <label className="form-label">Operation Name *</label>
            <input
              type="text"
              className="form-input"
              placeholder="e.g. Charge Customer Invoice"
              value={opFormData.name}
              onChange={(e) => setOpFormData({ ...opFormData, name: e.target.value })}
              required
            />
          </div>
          <div className="form-group">
            <label className="form-label">Custom Slug (Optional)</label>
            <input
              type="text"
              className="form-input"
              placeholder="e.g. charge-customer"
              value={opFormData.slug}
              onChange={(e) => setOpFormData({ ...opFormData, slug: e.target.value })}
            />
          </div>
          <div className="form-group">
            <label className="form-label">Operation Categorization</label>
            <select
              className="form-select"
              value={opFormData.operation_type}
              onChange={(e) => setOpFormData({ ...opFormData, operation_type: e.target.value as OperationType })}
            >
              <option value="read">Read (Lookup, Query, Fetch)</option>
              <option value="write">Write (Create, Insert, Update)</option>
              <option value="execute">Execute (Process, Run, Invoke)</option>
              <option value="delete">Delete (Destroy, Terminate, Drop)</option>
              <option value="admin">Admin (Configuration, Privilege grant)</option>
            </select>
          </div>
          <div className="form-group">
            <label className="form-label">Baseline Operational Risk Rating</label>
            <select
              className="form-select"
              value={opFormData.risk_level}
              onChange={(e) => setOpFormData({ ...opFormData, risk_level: e.target.value as RiskLevel })}
            >
              <option value="low">LOW (Minor/safe operations)</option>
              <option value="medium">MEDIUM (Standard business actions)</option>
              <option value="high">HIGH (Financial, sensitive data, modification)</option>
              <option value="critical">CRITICAL (Destructive, admin, system-wide impact)</option>
            </select>
          </div>
          <div className="form-group">
            <label className="form-label">Description</label>
            <textarea
              className="form-textarea"
              rows={2}
              placeholder="What this operation does and side-effects"
              value={opFormData.description}
              onChange={(e) => setOpFormData({ ...opFormData, description: e.target.value })}
            />
          </div>
          <div className="modal-footer" style={{ margin: '-20px', marginTop: '20px' }}>
            <Button type="button" variant="outline" onClick={() => setIsOpModalOpen(false)}>
              Cancel
            </Button>
            <Button type="submit" variant="primary" loading={creatingOp}>
              Add Operation
            </Button>
          </div>
        </form>
      </Modal>
    </div>
  );
};
