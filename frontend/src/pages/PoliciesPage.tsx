import React, { useState, useEffect } from 'react';
import { useOrg } from '../context/OrgContext';
import { policiesApi } from '../api/policies';
import { Policy, EnforcementMode } from '../types';
import { SurfaceCard } from '../components/common/Card';
import { StatusBadge } from '../components/common/Badges';
import { LoadingState, ErrorState, EmptyState } from '../components/common/FeedbackStates';
import { Button } from '../components/common/Button';
import { Modal } from '../components/common/Modal';
import { Link, useNavigate } from '../router/Router';
import { PlusIcon, RefreshIcon, ScaleIcon } from '../components/common/Icons';

export const PoliciesPage: React.FC = () => {
  const { currentOrg } = useOrg();
  const navigate = useNavigate();

  const [policies, setPolicies] = useState<Policy[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const [isModalOpen, setIsModalOpen] = useState(false);
  const [creating, setCreating] = useState(false);
  const [formData, setFormData] = useState({
    name: '',
    slug: '',
    description: '',
    enforcement_mode: 'enforce' as EnforcementMode,
  });

  const loadPolicies = async () => {
    if (!currentOrg) return;
    setLoading(true);
    setError(null);
    try {
      const res = await policiesApi.list(currentOrg.id, { limit: 100 });
      setPolicies(res.items || []);
    } catch (err: any) {
      setError(err.message || 'Failed to load policy specifications.');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadPolicies();
  }, [currentOrg]);

  const handleCreate = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!currentOrg) return;
    setCreating(true);
    try {
      const newPolicy = await policiesApi.create(currentOrg.id, {
        name: formData.name,
        slug: formData.slug || undefined,
        description: formData.description || undefined,
        enforcement_mode: formData.enforcement_mode,
      });
      setIsModalOpen(false);
      navigate(`/policies/${newPolicy.id}`);
    } catch (err: any) {
      alert(`Error creating policy: ${err.message}`);
    } finally {
      setCreating(false);
    }
  };

  return (
    <div className="policies-page">
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '20px' }}>
        <div>
          <h2 style={{ fontSize: '20px', fontWeight: 700 }}>Security Policy Engine</h2>
          <p className="text-muted" style={{ fontSize: '13px' }}>
            Contextual rules governing action amounts, environments, resources, and time constraints.
          </p>
        </div>
        <Button
          variant="primary"
          size="md"
          icon={<PlusIcon size={16} />}
          onClick={() => setIsModalOpen(true)}
        >
          Create Policy
        </Button>
      </div>

      <SurfaceCard>
        {loading ? (
          <LoadingState message="Loading organization policy specifications..." />
        ) : error ? (
          <ErrorState message={error} onRetry={loadPolicies} />
        ) : policies.length === 0 ? (
          <EmptyState
            title="No Policies Defined"
            description="Create security guardrails to enforce transaction limits, environment boundaries, and approval requirements."
            action={
              <Button variant="primary" size="sm" onClick={() => setIsModalOpen(true)} icon={<PlusIcon size={14} />}>
                Create First Policy
              </Button>
            }
          />
        ) : (
          <div className="table-responsive">
            <table className="data-table">
              <thead>
                <tr>
                  <th>Policy Name</th>
                  <th>Slug</th>
                  <th>Enforcement Mode</th>
                  <th>Status</th>
                  <th>Active Version</th>
                  <th>Created</th>
                  <th></th>
                </tr>
              </thead>
              <tbody>
                {policies.map((p) => (
                  <tr key={p.id}>
                    <td>
                      <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                        <ScaleIcon size={16} className="text-cyan" />
                        <Link to={`/policies/${p.id}`} style={{ fontWeight: 600, color: 'inherit', textDecoration: 'none' }}>
                          {p.name}
                        </Link>
                      </div>
                    </td>
                    <td className="font-mono text-muted">{p.slug}</td>
                    <td>
                      <span className={`badge ${p.enforcement_mode === 'enforce' ? 'badge-status-danger' : 'badge-status-warning'}`}>
                        {p.enforcement_mode.toUpperCase()}
                      </span>
                    </td>
                    <td><StatusBadge status={p.status} /></td>
                    <td>
                      {p.active_version_id ? (
                        <span className="badge badge-status-success">v{p.active_version_id.slice(0, 6)} (Active)</span>
                      ) : (
                        <span className="text-muted" style={{ fontSize: '12px' }}>Draft Only</span>
                      )}
                    </td>
                    <td>{new Date(p.created_at).toLocaleDateString()}</td>
                    <td>
                      <Link to={`/policies/${p.id}`} className="btn btn-outline btn-sm">
                        View Versions & Rules
                      </Link>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </SurfaceCard>

      {/* Create Policy Modal */}
      <Modal
        isOpen={isModalOpen}
        onClose={() => setIsModalOpen(false)}
        title="Create Security Policy"
        subtitle="Initialize a versioned policy guardrail"
      >
        <form onSubmit={handleCreate}>
          <div className="form-group">
            <label className="form-label">Policy Name *</label>
            <input
              type="text"
              className="form-input"
              placeholder="e.g. Production Deletion Freeze"
              value={formData.name}
              onChange={(e) => setFormData({ ...formData, name: e.target.value })}
              required
            />
          </div>
          <div className="form-group">
            <label className="form-label">Custom Slug (Optional)</label>
            <input
              type="text"
              className="form-input"
              placeholder="e.g. prod-deletion-freeze"
              value={formData.slug}
              onChange={(e) => setFormData({ ...formData, slug: e.target.value })}
            />
          </div>
          <div className="form-group">
            <label className="form-label">Enforcement Mode</label>
            <select
              className="form-select"
              value={formData.enforcement_mode}
              onChange={(e) => setFormData({ ...formData, enforcement_mode: e.target.value as EnforcementMode })}
            >
              <option value="enforce">ENFORCE (Active blocking / approval enforcement)</option>
              <option value="audit">AUDIT (Evaluate and log matches without blocking)</option>
              <option value="disabled">DISABLED (Bypass evaluation)</option>
            </select>
          </div>
          <div className="form-group">
            <label className="form-label">Description</label>
            <textarea
              className="form-textarea"
              rows={3}
              placeholder="Rationale and operational intent of this policy"
              value={formData.description}
              onChange={(e) => setFormData({ ...formData, description: e.target.value })}
            />
          </div>
          <div className="modal-footer" style={{ margin: '-20px', marginTop: '20px' }}>
            <Button type="button" variant="outline" onClick={() => setIsModalOpen(false)}>
              Cancel
            </Button>
            <Button type="submit" variant="primary" loading={creating}>
              Create Policy
            </Button>
          </div>
        </form>
      </Modal>
    </div>
  );
};
