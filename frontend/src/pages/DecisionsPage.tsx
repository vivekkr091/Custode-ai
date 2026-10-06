import React, { useEffect, useState } from 'react';
import { useOrg } from '../context/OrgContext';
import { listDecisions, listRuntimeActions, evaluateDecision } from '../api';
import { Decision, RuntimeAction } from '../types';
import { MetricCard, SurfaceCard } from '../components/common/Card';
import { DecisionBadge, RiskBadge } from '../components/common/Badges';
import { Button } from '../components/common/Button';
import { Modal } from '../components/common/Modal';
import { LoadingState, EmptyState } from '../components/common/FeedbackStates';
import {
  LayersIcon,
  SearchIcon,
  PlayIcon,
  FilterIcon,
  CheckCircleIcon,
  XCircleIcon,
  ClockIcon,
} from '../components/common/Icons';
import { navigate } from '../router/Router';

export const DecisionsPage: React.FC = () => {
  const { activeOrg } = useOrg();
  const [decisions, setDecisions] = useState<Decision[]>([]);
  const [actions, setActions] = useState<RuntimeAction[]>([]);
  const [loading, setLoading] = useState(true);

  // Filters
  const [outcomeFilter, setOutcomeFilter] = useState<'all' | 'allow' | 'deny' | 'require_approval'>('all');
  const [searchQuery, setSearchQuery] = useState('');

  // Evaluate modal
  const [evalModalOpen, setEvalModalOpen] = useState(false);
  const [selectedActionId, setSelectedActionId] = useState('');
  const [evaluating, setEvaluating] = useState(false);

  const fetchData = async () => {
    if (!activeOrg) return;
    try {
      setLoading(true);
      const [allDecisions, allActions] = await Promise.all([
        listDecisions(activeOrg.id).catch(() => []),
        listRuntimeActions(activeOrg.id).catch(() => []),
      ]);
      setDecisions(allDecisions);
      setActions(allActions);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchData();
  }, [activeOrg?.id]);

  const handleEvaluate = async () => {
    if (!activeOrg || !selectedActionId) return;
    try {
      setEvaluating(true);
      const newDecision = await evaluateDecision(activeOrg.id, {
        runtime_action_id: selectedActionId,
      });
      setEvalModalOpen(false);
      navigate(`/decisions/${newDecision.id}`);
    } catch (err: any) {
      alert(`Decision evaluation failed: ${err.message}`);
    } finally {
      setEvaluating(false);
    }
  };

  const filteredDecisions = decisions.filter((d) => {
    if (outcomeFilter !== 'all' && d.decision !== outcomeFilter) return false;
    if (searchQuery) {
      const q = searchQuery.toLowerCase();
      return (
        d.id.toLowerCase().includes(q) ||
        d.runtime_action_id.toLowerCase().includes(q) ||
        (d.reason && d.reason.toLowerCase().includes(q))
      );
    }
    return true;
  });

  const allowCount = decisions.filter((d) => d.decision === 'allow').length;
  const denyCount = decisions.filter((d) => d.decision === 'deny').length;
  const approvalCount = decisions.filter((d) => d.decision === 'require_approval').length;

  return (
    <div className="space-y-6">
      {/* Top Banner */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold font-mono tracking-tight text-text-primary">
            Authorization Decision Engine
          </h1>
          <p className="text-xs text-text-secondary mt-1">
            Authoritative, deterministic policy + permission + risk synthesis ledger.
          </p>
        </div>
        <Button
          variant="primary"
          leftIcon={<PlayIcon className="w-4 h-4" />}
          onClick={() => {
            setSelectedActionId(actions[0]?.id || '');
            setEvalModalOpen(true);
          }}
        >
          Evaluate Action Decision
        </Button>
      </div>

      {/* Metrics */}
      <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
        <MetricCard
          title="Allowed Decisions"
          value={allowCount}
          subtitle="Passed permissions, policies & risk"
          variant="success"
          icon={<CheckCircleIcon className="w-5 h-5 text-success" />}
        />
        <MetricCard
          title="Human Approvals Required"
          value={approvalCount}
          subtitle="Escalated to human governance"
          variant="warning"
          icon={<ClockIcon className="w-5 h-5 text-warning" />}
        />
        <MetricCard
          title="Denied Decisions"
          value={denyCount}
          subtitle="Blocked by policy or permissions"
          variant="danger"
          icon={<XCircleIcon className="w-5 h-5 text-danger" />}
        />
      </div>

      {/* Controls Bar */}
      <div className="flex flex-col sm:flex-row items-center justify-between gap-4">
        <div className="flex items-center gap-2 w-full sm:w-auto">
          <span className="text-xs text-text-tertiary flex items-center gap-1 mr-1">
            <FilterIcon className="w-3.5 h-3.5" />
            Decision:
          </span>
          {(['all', 'allow', 'require_approval', 'deny'] as const).map((outcome) => (
            <button
              key={outcome}
              onClick={() => setOutcomeFilter(outcome)}
              className={`px-3 py-1 text-xs font-mono rounded transition-colors ${
                outcomeFilter === outcome
                  ? 'bg-accent-primary/20 text-accent-primary border border-accent-primary/40'
                  : 'text-text-secondary hover:text-text-primary'
              }`}
            >
              {outcome === 'require_approval' ? 'APPROVAL' : outcome.toUpperCase()}
            </button>
          ))}
        </div>

        <div className="relative w-full sm:w-64">
          <SearchIcon className="absolute left-3 top-2.5 w-4 h-4 text-text-muted" />
          <input
            type="text"
            placeholder="Search decisions..."
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            className="w-full bg-bg-secondary border border-border-default rounded pl-9 pr-3 py-1.5 text-xs text-text-primary font-mono focus:outline-none focus:border-accent-primary"
          />
        </div>
      </div>

      {/* Decisions Table */}
      <SurfaceCard title={`Decision Evaluation Ledger (${filteredDecisions.length})`}>
        {loading ? (
          <LoadingState message="Fetching decision records..." />
        ) : filteredDecisions.length === 0 ? (
          <EmptyState
            title="No Decisions Match Filters"
            description="No authorization decisions found matching your filter criteria."
          />
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-left text-xs font-mono">
              <thead>
                <tr className="border-b border-border-subtle text-text-tertiary uppercase">
                  <th className="py-2.5 px-3">Decision ID</th>
                  <th className="py-2.5 px-3">Action ID</th>
                  <th className="py-2.5 px-3">Outcome</th>
                  <th className="py-2.5 px-3">Risk Assessment</th>
                  <th className="py-2.5 px-3">Explanation / Reason</th>
                  <th className="py-2.5 px-3">Timestamp</th>
                  <th className="py-2.5 px-3 text-right">Actions</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-border-subtle text-text-secondary">
                {filteredDecisions.map((d) => (
                  <tr key={d.id} className="hover:bg-bg-tertiary/50">
                    <td className="py-2.5 px-3 font-semibold text-text-primary">
                      {d.id.slice(0, 8)}...
                    </td>
                    <td className="py-2.5 px-3 text-accent-primary">
                      {d.runtime_action_id.slice(0, 8)}...
                    </td>
                    <td className="py-2.5 px-3">
                      <DecisionBadge decision={d.decision} />
                    </td>
                    <td className="py-2.5 px-3">
                      <RiskBadge score={d.risk_score} level={d.risk_tier} />
                    </td>
                    <td className="py-2.5 px-3 max-w-xs truncate text-text-tertiary">
                      {d.reason || 'Authoritative engine synthesized outcome'}
                    </td>
                    <td className="py-2.5 px-3 text-text-muted">
                      {new Date(d.evaluated_at).toLocaleString()}
                    </td>
                    <td className="py-2.5 px-3 text-right">
                      <Button
                        variant="outline"
                        size="sm"
                        onClick={() => navigate(`/decisions/${d.id}`)}
                      >
                        Inspect Trace
                      </Button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </SurfaceCard>

      {/* Evaluate Decision Modal */}
      <Modal
        isOpen={evalModalOpen}
        onClose={() => setEvalModalOpen(false)}
        title="Authoritative Decision Evaluation"
      >
        <div className="space-y-4">
          <div>
            <label className="block text-xs font-mono uppercase text-text-tertiary mb-1">
              Select Action To Authorize
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

          <div className="p-3 bg-bg-tertiary/40 border border-border-subtle rounded text-xs text-text-secondary font-mono">
            Evaluating will sequentially invoke:
            <ol className="list-decimal ml-4 mt-1 space-y-0.5 text-text-tertiary">
              <li>Agent authentication & credential status</li>
              <li>Agent-to-tool permission grants</li>
              <li>Active policy rules & condition checks</li>
              <li>Contextual risk scoring & blast radius</li>
              <li>Authoritative decision persistence</li>
            </ol>
          </div>

          <div className="flex justify-end gap-2 pt-2">
            <Button variant="ghost" onClick={() => setEvalModalOpen(false)}>
              Cancel
            </Button>
            <Button
              variant="primary"
              loading={evaluating}
              onClick={handleEvaluate}
              disabled={!selectedActionId}
            >
              Run Evaluation
            </Button>
          </div>
        </div>
      </Modal>
    </div>
  );
};
