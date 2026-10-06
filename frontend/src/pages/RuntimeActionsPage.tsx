import React, { useState, useEffect } from 'react';
import { useOrg } from '../context/OrgContext';
import { runtimeActionsApi } from '../api/runtimeActions';
import { RuntimeAction } from '../types';
import { SurfaceCard } from '../components/common/Card';
import { EnvironmentBadge, StatusBadge } from '../components/common/Badges';
import { LoadingState, ErrorState, EmptyState } from '../components/common/FeedbackStates';
import { Button } from '../components/common/Button';
import { Link, useNavigate } from '../router/Router';
import { RefreshIcon, TerminalIcon } from '../components/common/Icons';

export const RuntimeActionsPage: React.FC = () => {
  const { currentOrg } = useOrg();
  const navigate = useNavigate();

  const [actions, setActions] = useState<RuntimeAction[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [searchTerm, setSearchTerm] = useState('');
  const [filterStatus, setFilterStatus] = useState<string>('');

  const loadActions = async () => {
    if (!currentOrg) return;
    setLoading(true);
    setError(null);
    try {
      const res = await runtimeActionsApi.list(currentOrg.id, {
        status: filterStatus || undefined,
        limit: 100,
      });
      setActions(res.items || []);
    } catch (err: any) {
      setError(err.message || 'Failed to load runtime actions.');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadActions();
  }, [currentOrg, filterStatus]);

  const filtered = actions.filter((a) =>
    a.id.toLowerCase().includes(searchTerm.toLowerCase()) ||
    a.action_type.toLowerCase().includes(searchTerm.toLowerCase()) ||
    (a.resource && a.resource.toLowerCase().includes(searchTerm.toLowerCase()))
  );

  return (
    <div className="runtime-actions-page">
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '20px' }}>
        <div>
          <h2 style={{ fontSize: '20px', fontWeight: 700 }}>Runtime Action Audit Plane</h2>
          <p className="text-muted" style={{ fontSize: '13px' }}>
            Authoritative lifecycle ledger of concrete capability invocations requested by AI agents.
          </p>
        </div>
        <Button variant="outline" size="md" onClick={loadActions} icon={<RefreshIcon size={14} />}>
          Refresh Ledger
        </Button>
      </div>

      <SurfaceCard>
        {/* Search & Status Filters */}
        <div style={{ display: 'flex', gap: '12px', marginBottom: '16px', flexWrap: 'wrap' }}>
          <div style={{ flex: 1, minWidth: '240px' }}>
            <input
              type="text"
              className="form-input"
              placeholder="Search by action ID, type, or resource..."
              value={searchTerm}
              onChange={(e) => setSearchTerm(e.target.value)}
            />
          </div>
          <select
            className="form-select"
            style={{ width: '180px' }}
            value={filterStatus}
            onChange={(e) => setFilterStatus(e.target.value)}
          >
            <option value="">All Lifecycle States</option>
            <option value="pending">Pending</option>
            <option value="evaluating">Evaluating</option>
            <option value="approved">Approved</option>
            <option value="denied">Denied</option>
            <option value="executed">Executed</option>
            <option value="failed">Failed</option>
            <option value="cancelled">Cancelled</option>
          </select>
        </div>

        {loading ? (
          <LoadingState message="Streaming action audit telemetry..." />
        ) : error ? (
          <ErrorState message={error} onRetry={loadActions} />
        ) : filtered.length === 0 ? (
          <EmptyState
            title="No Runtime Actions Recorded"
            description="RuntimeActions are logged when authenticated agents invoke external tools."
          />
        ) : (
          <div className="table-responsive">
            <table className="data-table">
              <thead>
                <tr>
                  <th>Action ID</th>
                  <th>Action Type</th>
                  <th>Resource</th>
                  <th>Environment</th>
                  <th>Amount</th>
                  <th>Lifecycle Status</th>
                  <th>Created</th>
                  <th></th>
                </tr>
              </thead>
              <tbody>
                {filtered.map((action) => (
                  <tr key={action.id}>
                    <td className="font-mono">{action.id.slice(0, 8)}...</td>
                    <td>
                      <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                        <TerminalIcon size={16} className="text-cyan" />
                        <strong>{action.action_type}</strong>
                      </div>
                    </td>
                    <td className="font-mono text-muted" style={{ maxWidth: '200px', overflow: 'hidden', textOverflow: 'ellipsis' }}>
                      {action.resource || '—'}
                    </td>
                    <td><EnvironmentBadge environment={action.environment} /></td>
                    <td className="font-mono">
                      {action.amount !== null && action.amount !== undefined ? (
                        <span>${Number(action.amount).toLocaleString()} {action.currency || 'USD'}</span>
                      ) : (
                        '—'
                      )}
                    </td>
                    <td><StatusBadge status={action.status} /></td>
                    <td>{new Date(action.created_at).toLocaleString()}</td>
                    <td>
                      <Link to={`/runtime-actions/${action.id}`} className="btn btn-outline btn-sm">
                        Forensic View
                      </Link>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </SurfaceCard>
    </div>
  );
};
