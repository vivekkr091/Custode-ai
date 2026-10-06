import React, { useState, useEffect } from 'react';
import { useOrg } from '../context/OrgContext';
import { agentsApi } from '../api/agents';
import { Agent, AgentEnvironment, AgentStatus } from '../types';
import { SurfaceCard } from '../components/common/Card';
import { EnvironmentBadge, StatusBadge } from '../components/common/Badges';
import { LoadingState, ErrorState, EmptyState } from '../components/common/FeedbackStates';
import { Button } from '../components/common/Button';
import { Modal } from '../components/common/Modal';
import { Link, useNavigate } from '../router/Router';
import { BotIcon, PlusIcon, RefreshIcon, SearchIcon } from '../components/common/Icons';

export const AgentsPage: React.FC = () => {
  const { currentOrg } = useOrg();
  const navigate = useNavigate();

  const [agents, setAgents] = useState<Agent[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [searchTerm, setSearchTerm] = useState('');
  const [filterEnv, setFilterEnv] = useState<string>('');
  const [filterStatus, setFilterStatus] = useState<string>('');

  const [isCreateModalOpen, setIsCreateModalOpen] = useState(false);
  const [creating, setCreating] = useState(false);
  const [formData, setFormData] = useState({
    name: '',
    slug: '',
    description: '',
    agent_type: 'autonomous',
    environment: 'development' as AgentEnvironment,
  });

  const loadAgents = async () => {
    if (!currentOrg) return;
    setLoading(true);
    setError(null);
    try {
      const res = await agentsApi.list(currentOrg.id, {
        environment: filterEnv || undefined,
        status: filterStatus || undefined,
        limit: 100,
      });
      setAgents(res.items || []);
    } catch (err: any) {
      setError(err.message || 'Failed to load registered agents.');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadAgents();
  }, [currentOrg, filterEnv, filterStatus]);

  const handleCreate = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!currentOrg) return;
    setCreating(true);
    try {
      const newAgent = await agentsApi.create(currentOrg.id, {
        name: formData.name,
        slug: formData.slug || undefined,
        description: formData.description || undefined,
        agent_type: formData.agent_type,
        environment: formData.environment,
      });
      setIsCreateModalOpen(false);
      setFormData({ name: '', slug: '', description: '', agent_type: 'autonomous', environment: 'development' });
      navigate(`/agents/${newAgent.id}`);
    } catch (err: any) {
      alert(`Error registering agent: ${err.message}`);
    } finally {
      setCreating(false);
    }
  };

  const filteredAgents = agents.filter((a) =>
    a.name.toLowerCase().includes(searchTerm.toLowerCase()) ||
    a.slug.toLowerCase().includes(searchTerm.toLowerCase()) ||
    a.id.toLowerCase().includes(searchTerm.toLowerCase())
  );

  return (
    <div className="agents-page">
      <div className="page-header-action-row" style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '20px' }}>
        <div>
          <h2 style={{ fontSize: '20px', fontWeight: 700 }}>Agent Identity Registry</h2>
          <p className="text-muted" style={{ fontSize: '13px' }}>
            First-class cryptographic security identities for autonomous agents and LLM services.
          </p>
        </div>
        <Button
          variant="primary"
          size="md"
          icon={<PlusIcon size={16} />}
          onClick={() => setIsCreateModalOpen(true)}
        >
          Register New Agent
        </Button>
      </div>

      <SurfaceCard>
        {/* Search & Filters */}
        <div className="filter-bar" style={{ display: 'flex', gap: '12px', marginBottom: '16px', flexWrap: 'wrap' }}>
          <div style={{ position: 'relative', flex: 1, minWidth: '240px' }}>
            <input
              type="text"
              className="form-input"
              placeholder="Search by agent name, slug, or ID..."
              value={searchTerm}
              onChange={(e) => setSearchTerm(e.target.value)}
            />
          </div>
          <select
            className="form-select"
            style={{ width: '160px' }}
            value={filterEnv}
            onChange={(e) => setFilterEnv(e.target.value)}
          >
            <option value="">All Environments</option>
            <option value="development">Development</option>
            <option value="staging">Staging</option>
            <option value="production">Production</option>
          </select>
          <select
            className="form-select"
            style={{ width: '140px' }}
            value={filterStatus}
            onChange={(e) => setFilterStatus(e.target.value)}
          >
            <option value="">All Statuses</option>
            <option value="active">Active</option>
            <option value="suspended">Suspended</option>
            <option value="revoked">Revoked</option>
          </select>
          <Button variant="outline" size="md" onClick={loadAgents} icon={<RefreshIcon size={14} />}>
            Refresh
          </Button>
        </div>

        {loading ? (
          <LoadingState message="Loading agent identities..." />
        ) : error ? (
          <ErrorState message={error} onRetry={loadAgents} />
        ) : filteredAgents.length === 0 ? (
          <EmptyState
            title="No Agents Found"
            description={searchTerm ? 'No agents match your query.' : 'Register an agent identity to begin managing permissions.'}
            action={
              <Button variant="primary" size="sm" onClick={() => setIsCreateModalOpen(true)} icon={<PlusIcon size={14} />}>
                Register Agent
              </Button>
            }
          />
        ) : (
          <div className="table-responsive">
            <table className="data-table">
              <thead>
                <tr>
                  <th>Agent Name</th>
                  <th>Slug</th>
                  <th>Environment</th>
                  <th>Type</th>
                  <th>Status</th>
                  <th>Created</th>
                  <th></th>
                </tr>
              </thead>
              <tbody>
                {filteredAgents.map((agent) => (
                  <tr key={agent.id}>
                    <td>
                      <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                        <BotIcon size={16} className="text-cyan" />
                        <Link to={`/agents/${agent.id}`} style={{ fontWeight: 600, color: 'inherit', textDecoration: 'none' }}>
                          {agent.name}
                        </Link>
                      </div>
                    </td>
                    <td className="font-mono text-muted">{agent.slug}</td>
                    <td><EnvironmentBadge environment={agent.environment} /></td>
                    <td><span className="badge badge-status-neutral">{agent.agent_type}</span></td>
                    <td><StatusBadge status={agent.status} /></td>
                    <td>{new Date(agent.created_at).toLocaleDateString()}</td>
                    <td>
                      <Link to={`/agents/${agent.id}`} className="btn btn-outline btn-sm">
                        View Details
                      </Link>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </SurfaceCard>

      {/* Register Agent Modal */}
      <Modal
        isOpen={isCreateModalOpen}
        onClose={() => setIsCreateModalOpen(false)}
        title="Register New Agent Identity"
        subtitle="Provision a first-class security principal for an AI agent"
      >
        <form onSubmit={handleCreate}>
          <div className="form-group">
            <label className="form-label">Agent Name *</label>
            <input
              type="text"
              className="form-input"
              placeholder="e.g. Finance Execution Agent"
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
              placeholder="e.g. finance-exec-agent"
              value={formData.slug}
              onChange={(e) => setFormData({ ...formData, slug: e.target.value })}
            />
          </div>
          <div className="form-group">
            <label className="form-label">Agent Category / Type</label>
            <input
              type="text"
              className="form-input"
              placeholder="e.g. autonomous, assistant, pipeline"
              value={formData.agent_type}
              onChange={(e) => setFormData({ ...formData, agent_type: e.target.value })}
            />
          </div>
          <div className="form-group">
            <label className="form-label">Target Environment</label>
            <select
              className="form-select"
              value={formData.environment}
              onChange={(e) => setFormData({ ...formData, environment: e.target.value as AgentEnvironment })}
            >
              <option value="development">Development</option>
              <option value="staging">Staging</option>
              <option value="production">Production</option>
            </select>
          </div>
          <div className="form-group">
            <label className="form-label">Description</label>
            <textarea
              className="form-textarea"
              rows={3}
              placeholder="Agent role, capabilities, and expected operations"
              value={formData.description}
              onChange={(e) => setFormData({ ...formData, description: e.target.value })}
            />
          </div>
          <div className="modal-footer" style={{ margin: '-20px', marginTop: '20px' }}>
            <Button type="button" variant="outline" onClick={() => setIsCreateModalOpen(false)}>
              Cancel
            </Button>
            <Button type="submit" variant="primary" loading={creating}>
              Register Agent
            </Button>
          </div>
        </form>
      </Modal>
    </div>
  );
};
