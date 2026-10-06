import React, { useEffect, useState } from 'react';
import { useOrg } from '../context/OrgContext';
import { listExecutions, listRuntimeActions, executeAction } from '../api';
import { Execution, RuntimeAction } from '../types';
import { MetricCard, SurfaceCard } from '../components/common/Card';
import { StatusBadge } from '../components/common/Badges';
import { Button } from '../components/common/Button';
import { Modal } from '../components/common/Modal';
import { LoadingState, EmptyState } from '../components/common/FeedbackStates';
import {
  PlayIcon,
  SearchIcon,
  FilterIcon,
  CheckCircleIcon,
  XCircleIcon,
  ShieldCheckIcon,
} from '../components/common/Icons';
import { navigate } from '../router/Router';

export const ExecutionsPage: React.FC = () => {
  const { activeOrg } = useOrg();
  const [executions, setExecutions] = useState<Execution[]>([]);
  const [actions, setActions] = useState<RuntimeAction[]>([]);
  const [loading, setLoading] = useState(true);

  // Filters
  const [statusFilter, setStatusFilter] = useState<'all' | 'success' | 'failed' | 'pending'>('all');
  const [searchQuery, setSearchQuery] = useState('');

  // Execute modal
  const [execModalOpen, setExecModalOpen] = useState(false);
  const [selectedActionId, setSelectedActionId] = useState('');
  const [executing, setExecuting] = useState(false);

  const fetchData = async () => {
    if (!activeOrg) return;
    try {
      setLoading(true);
      const [allExecutions, allActions] = await Promise.all([
        listExecutions(activeOrg.id).catch(() => []),
        listRuntimeActions(activeOrg.id).catch(() => []),
      ]);
      setExecutions(allExecutions);
      setActions(allActions);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchData();
  }, [activeOrg?.id]);

  const handleExecute = async () => {
    if (!activeOrg || !selectedActionId) return;
    try {
      setExecuting(true);
      const selectedAction = actions.find((a) => a.id === selectedActionId);
      const newExecution = await executeAction(activeOrg.id, {
        runtime_action_id: selectedActionId,
        context: selectedAction?.context_data || {},
      });
      setExecModalOpen(false);
      navigate(`/executions/${newExecution.id}`);
    } catch (err: any) {
      alert(`Execution failed: ${err.message}`);
    } finally {
      setExecuting(false);
    }
  };

  const filteredExecutions = executions.filter((e) => {
    if (statusFilter !== 'all' && e.status.toLowerCase() !== statusFilter) return false;
    if (searchQuery) {
      const q = searchQuery.toLowerCase();
      return (
        e.id.toLowerCase().includes(q) ||
        e.runtime_action_id.toLowerCase().includes(q) ||
        (e.error_message && e.error_message.toLowerCase().includes(q))
      );
    }
    return true;
  });

  const successCount = executions.filter((e) => e.status.toLowerCase() === 'success').length;
  const failedCount = executions.filter((e) => e.status.toLowerCase() === 'failed').length;

  return (
    <div className="space-y-6">
      {/* Top Banner */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold font-mono tracking-tight text-text-primary">
            Controlled Execution Engine
          </h1>
          <p className="text-xs text-text-secondary mt-1">
            Deterministic, guarded tool execution ledger. Zero shell, zero arbitrary code, strict whitelisting.
          </p>
        </div>
        <Button
          variant="primary"
          leftIcon={<PlayIcon className="w-4 h-4" />}
          onClick={() => {
            setSelectedActionId(actions[0]?.id || '');
            setExecModalOpen(true);
          }}
        >
          Execute Allowed Action
        </Button>
      </div>

      {/* Execution Guard Guarantee Callout */}
      <div className="p-3 rounded-lg bg-bg-secondary border border-border-default flex items-center justify-between">
        <div className="flex items-center gap-3">
          <div className="w-8 h-8 rounded bg-success/10 border border-success/30 flex items-center justify-center text-success shrink-0">
            <ShieldCheckIcon className="w-4 h-4" />
          </div>
          <div>
            <span className="text-xs font-semibold text-text-primary font-mono block">
              CUSTODE Execution Guard: Active
            </span>
            <span className="text-[11px] text-text-tertiary">
              Strict parameters validation, no eval(), no subprocess, only explicitly registered operations.
            </span>
          </div>
        </div>
        <span className="text-[10px] font-mono uppercase bg-accent-primary/10 text-accent-primary border border-accent-primary/20 px-2 py-0.5 rounded hidden sm:inline-block">
          Milestone 12 Enforced
        </span>
      </div>

      {/* Metrics */}
      <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
        <MetricCard
          title="Total Executions"
          value={executions.length}
          subtitle="Dispatched through execution guard"
          variant="default"
          icon={<PlayIcon className="w-5 h-5 text-accent-primary" />}
        />
        <MetricCard
          title="Successful Executions"
          value={successCount}
          subtitle="Passed guard and finished successfully"
          variant="success"
          icon={<CheckCircleIcon className="w-5 h-5 text-success" />}
        />
        <MetricCard
          title="Failed / Blocked Executions"
          value={failedCount}
          subtitle="Denied by guard or downstream failure"
          variant="danger"
          icon={<XCircleIcon className="w-5 h-5 text-danger" />}
        />
      </div>

      {/* Filter Controls */}
      <div className="flex flex-col sm:flex-row items-center justify-between gap-4">
        <div className="flex items-center gap-2 w-full sm:w-auto">
          <span className="text-xs text-text-tertiary flex items-center gap-1 mr-1">
            <FilterIcon className="w-3.5 h-3.5" />
            Status:
          </span>
          {(['all', 'success', 'failed'] as const).map((st) => (
            <button
              key={st}
              onClick={() => setStatusFilter(st)}
              className={`px-3 py-1 text-xs font-mono rounded transition-colors ${
                statusFilter === st
                  ? 'bg-accent-primary/20 text-accent-primary border border-accent-primary/40'
                  : 'text-text-secondary hover:text-text-primary'
              }`}
            >
              {st.toUpperCase()}
            </button>
          ))}
        </div>

        <div className="relative w-full sm:w-64">
          <SearchIcon className="absolute left-3 top-2.5 w-4 h-4 text-text-muted" />
          <input
            type="text"
            placeholder="Search executions..."
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            className="w-full bg-bg-secondary border border-border-default rounded pl-9 pr-3 py-1.5 text-xs text-text-primary font-mono focus:outline-none focus:border-accent-primary"
          />
        </div>
      </div>

      {/* Table */}
      <SurfaceCard title={`Execution Ledger (${filteredExecutions.length})`}>
        {loading ? (
          <LoadingState message="Fetching execution records..." />
        ) : filteredExecutions.length === 0 ? (
          <EmptyState
            title="No Executions Found"
            description="Trigger action execution once allowed or approved by governance."
          />
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-left text-xs font-mono">
              <thead>
                <tr className="border-b border-border-subtle text-text-tertiary uppercase">
                  <th className="py-2.5 px-3">Execution ID</th>
                  <th className="py-2.5 px-3">Action ID</th>
                  <th className="py-2.5 px-3">Status</th>
                  <th className="py-2.5 px-3">Execution Time</th>
                  <th className="py-2.5 px-3">Details / Result Summary</th>
                  <th className="py-2.5 px-3 text-right">Actions</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-border-subtle text-text-secondary">
                {filteredExecutions.map((e) => (
                  <tr key={e.id} className="hover:bg-bg-tertiary/50">
                    <td className="py-2.5 px-3 font-semibold text-text-primary">
                      {e.id.slice(0, 8)}...
                    </td>
                    <td className="py-2.5 px-3 text-accent-primary">
                      {e.runtime_action_id.slice(0, 8)}...
                    </td>
                    <td className="py-2.5 px-3">
                      <StatusBadge status={e.status} />
                    </td>
                    <td className="py-2.5 px-3 text-text-muted">
                      {new Date(e.executed_at || e.started_at || e.created_at).toLocaleString()}
                    </td>
                    <td className="py-2.5 px-3 max-w-xs truncate text-text-tertiary">
                      {e.error_message ? (
                        <span className="text-danger">Error: {e.error_message}</span>
                      ) : e.result ? (
                        <span className="text-success">Output payload returned</span>
                      ) : (
                        'Executed successfully'
                      )}
                    </td>
                    <td className="py-2.5 px-3 text-right">
                      <Button
                        variant="outline"
                        size="sm"
                        onClick={() => navigate(`/executions/${e.id}`)}
                      >
                        Inspect Result
                      </Button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </SurfaceCard>

      {/* Execute Action Modal */}
      <Modal
        isOpen={execModalOpen}
        onClose={() => setExecModalOpen(false)}
        title="Trigger Controlled Action Execution"
      >
        <div className="space-y-4">
          <div>
            <label className="block text-xs font-mono uppercase text-text-tertiary mb-1">
              Select Action To Execute
            </label>
            <select
              value={selectedActionId}
              onChange={(e) => setSelectedActionId(e.target.value)}
              className="w-full bg-bg-tertiary border border-border-default rounded px-3 py-2 text-xs font-mono text-text-primary focus:outline-none focus:border-accent-primary"
            >
              {actions.map((act) => (
                <option key={act.id} value={act.id}>
                  {act.tool_name}::{act.operation_name} ({act.id.slice(0, 8)}...) - {act.environment}
                </option>
              ))}
            </select>
          </div>

          <p className="text-xs text-text-secondary font-mono">
            Note: The execution engine enforces pre-flight checks: action must be in state 'allowed',
            operation must be registered, and execution parameters are validated against schema.
          </p>

          <div className="flex justify-end gap-2 pt-2">
            <Button variant="ghost" onClick={() => setExecModalOpen(false)}>
              Cancel
            </Button>
            <Button
              variant="primary"
              loading={executing}
              onClick={handleExecute}
              disabled={!selectedActionId}
            >
              Run Guarded Execution
            </Button>
          </div>
        </div>
      </Modal>
    </div>
  );
};
