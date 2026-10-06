import React, { useState, useEffect } from 'react';
import { useOrg } from '../context/OrgContext';
import { toolsApi } from '../api/tools';
import { Tool, ToolType, AgentEnvironment } from '../types';
import { SurfaceCard } from '../components/common/Card';
import { EnvironmentBadge, StatusBadge } from '../components/common/Badges';
import { LoadingState, ErrorState, EmptyState } from '../components/common/FeedbackStates';
import { Button } from '../components/common/Button';
import { Modal } from '../components/common/Modal';
import { Link, useNavigate } from '../router/Router';
import { PlusIcon, RefreshIcon, WrenchIcon } from '../components/common/Icons';

export const ToolsPage: React.FC = () => {
  const { currentOrg } = useOrg();
  const navigate = useNavigate();

  const [tools, setTools] = useState<Tool[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [searchTerm, setSearchTerm] = useState('');
  const [filterType, setFilterType] = useState<string>('');

  const [isCreateModalOpen, setIsCreateModalOpen] = useState(false);
  const [creating, setCreating] = useState(false);
  const [formData, setFormData] = useState({
    name: '',
    slug: '',
    description: '',
    tool_type: 'api' as ToolType,
    environment: 'development' as AgentEnvironment,
    endpoint: '',
  });

  const loadTools = async () => {
    if (!currentOrg) return;
    setLoading(true);
    setError(null);
    try {
      const res = await toolsApi.list(currentOrg.id, {
        tool_type: filterType || undefined,
        limit: 100,
      });
      setTools(res.items || []);
    } catch (err: any) {
      setError(err.message || 'Failed to load tools registry.');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadTools();
  }, [currentOrg, filterType]);

  const handleCreate = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!currentOrg) return;
    setCreating(true);
    try {
      const newTool = await toolsApi.create(currentOrg.id, {
        name: formData.name,
        slug: formData.slug || undefined,
        description: formData.description || undefined,
        tool_type: formData.tool_type,
        environment: formData.environment,
        endpoint: formData.endpoint || undefined,
      });
      setIsCreateModalOpen(false);
      setFormData({ name: '', slug: '', description: '', tool_type: 'api', environment: 'development', endpoint: '' });
      navigate(`/tools/${newTool.id}`);
    } catch (err: any) {
      alert(`Error creating tool: ${err.message}`);
    } finally {
      setCreating(false);
    }
  };

  const filtered = tools.filter((t) =>
    t.name.toLowerCase().includes(searchTerm.toLowerCase()) ||
    t.slug.toLowerCase().includes(searchTerm.toLowerCase())
  );

  return (
    <div className="tools-page">
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '20px' }}>
        <div>
          <h2 style={{ fontSize: '20px', fontWeight: 700 }}>Callable Capabilities Registry</h2>
          <p className="text-muted" style={{ fontSize: '13px' }}>
            External APIs, databases, clouds, filesystems, and tools known to the CUSTODE platform.
          </p>
        </div>
        <Button
          variant="primary"
          size="md"
          icon={<PlusIcon size={16} />}
          onClick={() => setIsCreateModalOpen(true)}
        >
          Register New Tool
        </Button>
      </div>

      <SurfaceCard>
        {/* Filters */}
        <div style={{ display: 'flex', gap: '12px', marginBottom: '16px', flexWrap: 'wrap' }}>
          <div style={{ flex: 1, minWidth: '240px' }}>
            <input
              type="text"
              className="form-input"
              placeholder="Search tools by name or slug..."
              value={searchTerm}
              onChange={(e) => setSearchTerm(e.target.value)}
            />
          </div>
          <select
            className="form-select"
            style={{ width: '160px' }}
            value={filterType}
            onChange={(e) => setFilterType(e.target.value)}
          >
            <option value="">All Categories</option>
            <option value="api">API</option>
            <option value="database">Database</option>
            <option value="cloud">Cloud Service</option>
            <option value="filesystem">Filesystem</option>
            <option value="mcp">MCP Protocol</option>
            <option value="internal">Internal Service</option>
          </select>
          <Button variant="outline" size="md" onClick={loadTools} icon={<RefreshIcon size={14} />}>
            Refresh
          </Button>
        </div>

        {loading ? (
          <LoadingState message="Loading capabilities registry..." />
        ) : error ? (
          <ErrorState message={error} onRetry={loadTools} />
        ) : filtered.length === 0 ? (
          <EmptyState
            title="No Tools Registered"
            description="Register external tools and APIs that your agents can be permitted to access."
            action={
              <Button variant="primary" size="sm" onClick={() => setIsCreateModalOpen(true)} icon={<PlusIcon size={14} />}>
                Register First Tool
              </Button>
            }
          />
        ) : (
          <div className="table-responsive">
            <table className="data-table">
              <thead>
                <tr>
                  <th>Tool Name</th>
                  <th>Slug</th>
                  <th>Category</th>
                  <th>Environment</th>
                  <th>Status</th>
                  <th>Endpoint</th>
                  <th></th>
                </tr>
              </thead>
              <tbody>
                {filtered.map((tool) => (
                  <tr key={tool.id}>
                    <td>
                      <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                        <WrenchIcon size={16} className="text-cyan" />
                        <Link to={`/tools/${tool.id}`} style={{ fontWeight: 600, color: 'inherit', textDecoration: 'none' }}>
                          {tool.name}
                        </Link>
                      </div>
                    </td>
                    <td className="font-mono text-muted">{tool.slug}</td>
                    <td>
                      <span className="badge badge-status-neutral">{tool.tool_type.toUpperCase()}</span>
                    </td>
                    <td><EnvironmentBadge environment={tool.environment} /></td>
                    <td><StatusBadge status={tool.status} /></td>
                    <td className="font-mono text-muted" style={{ maxWidth: '200px', overflow: 'hidden', textOverflow: 'ellipsis' }}>
                      {tool.endpoint || '—'}
                    </td>
                    <td>
                      <Link to={`/tools/${tool.id}`} className="btn btn-outline btn-sm">
                        View Operations
                      </Link>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </SurfaceCard>

      {/* Register Tool Modal */}
      <Modal
        isOpen={isCreateModalOpen}
        onClose={() => setIsCreateModalOpen(false)}
        title="Register External Capability / Tool"
        subtitle="Catalog an external API, database, or service for granular authorization"
      >
        <form onSubmit={handleCreate}>
          <div className="form-group">
            <label className="form-label">Tool Name *</label>
            <input
              type="text"
              className="form-input"
              placeholder="e.g. Stripe Payment API"
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
              placeholder="e.g. stripe-payments"
              value={formData.slug}
              onChange={(e) => setFormData({ ...formData, slug: e.target.value })}
            />
          </div>
          <div className="form-group">
            <label className="form-label">Tool Type</label>
            <select
              className="form-select"
              value={formData.tool_type}
              onChange={(e) => setFormData({ ...formData, tool_type: e.target.value as ToolType })}
            >
              <option value="api">HTTP API Service</option>
              <option value="database">Database</option>
              <option value="cloud">Cloud Provider</option>
              <option value="filesystem">Filesystem</option>
              <option value="mcp">Model Context Protocol (MCP)</option>
              <option value="internal">Internal Business Service</option>
            </select>
          </div>
          <div className="form-group">
            <label className="form-label">Base Endpoint URL</label>
            <input
              type="text"
              className="form-input"
              placeholder="e.g. https://api.stripe.com/v1"
              value={formData.endpoint}
              onChange={(e) => setFormData({ ...formData, endpoint: e.target.value })}
            />
          </div>
          <div className="form-group">
            <label className="form-label">Description</label>
            <textarea
              className="form-textarea"
              rows={3}
              placeholder="Tool capabilities and security scope"
              value={formData.description}
              onChange={(e) => setFormData({ ...formData, description: e.target.value })}
            />
          </div>
          <div className="modal-footer" style={{ margin: '-20px', marginTop: '20px' }}>
            <Button type="button" variant="outline" onClick={() => setIsCreateModalOpen(false)}>
              Cancel
            </Button>
            <Button type="submit" variant="primary" loading={creating}>
              Register Tool
            </Button>
          </div>
        </form>
      </Modal>
    </div>
  );
};
