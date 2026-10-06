import React, { useEffect, useState } from 'react';
import { useOrg } from '../context/OrgContext';
import { listDecisions, listRuntimeActions, assessRisk } from '../api';
import { Decision, RuntimeAction, RiskAssessment } from '../types';
import { MetricCard, SurfaceCard } from '../components/common/Card';
import { RiskBadge, EnvironmentBadge } from '../components/common/Badges';
import { Button } from '../components/common/Button';
import { Modal } from '../components/common/Modal';
import { CodeView } from '../components/common/CodeView';
import { LoadingState, EmptyState } from '../components/common/FeedbackStates';
import {
  ShieldAlertIcon,
  SearchIcon,
  PlayIcon,
  FilterIcon,
} from '../components/common/Icons';

export const RiskPage: React.FC = () => {
  const { activeOrg } = useOrg();
  const [decisions, setDecisions] = useState<Decision[]>([]);
  const [actions, setActions] = useState<RuntimeAction[]>([]);
  const [loading, setLoading] = useState(true);

  // Filter
  const [tierFilter, setTierFilter] = useState<'all' | 'low' | 'medium' | 'high' | 'critical'>('all');

  // On-demand assessment modal
  const [assessModalOpen, setAssessModalOpen] = useState(false);
  const [selectedActionId, setSelectedActionId] = useState('');
  const [evaluating, setEvaluating] = useState(false);
  const [assessmentResult, setAssessmentResult] = useState<RiskAssessment | null>(null);

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

  const handleRunAssessment = async () => {
    if (!activeOrg || !selectedActionId) return;
    try {
      setEvaluating(true);
      const res = await assessRisk(activeOrg.id, {
        runtime_action_id: selectedActionId,
      });
      setAssessmentResult(res);
    } catch (err: any) {
      alert(`Assessment failed: ${err.message}`);
    } finally {
      setEvaluating(false);
    }
  };

  const getTier = (d: Decision) => (d.risk_tier || d.risk_level || 'low').toLowerCase();

  const filteredDecisions = decisions.filter((d) => {
    if (tierFilter !== 'all' && getTier(d) !== tierFilter) return false;
    return true;
  });

  const lowCount = decisions.filter((d) => getTier(d) === 'low').length;
  const medCount = decisions.filter((d) => getTier(d) === 'medium').length;
  const highCount = decisions.filter((d) => getTier(d) === 'high').length;
  const critCount = decisions.filter((d) => getTier(d) === 'critical').length;

  return (
    <div className="space-y-6">
      {/* Top Banner */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold font-mono tracking-tight text-text-primary">
            Risk Assessment Engine
          </h1>
          <p className="text-xs text-text-secondary mt-1">
            Deterministic contextual risk scoring, sensitivity factors, and blast-radius modeling.
          </p>
        </div>
        <Button
          variant="primary"
          leftIcon={<PlayIcon className="w-4 h-4" />}
          onClick={() => {
            setAssessmentResult(null);
            setSelectedActionId(actions[0]?.id || '');
            setAssessModalOpen(true);
          }}
        >
          Evaluate Action Risk
        </Button>
      </div>

      {/* Metrics Cards */}
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
        <MetricCard
          title="Critical Risk"
          value={critCount}
          subtitle="Requires mandatory human approval"
          variant="danger"
          icon={<ShieldAlertIcon className="w-5 h-5 text-danger" />}
        />
        <MetricCard
          title="High Risk"
          value={highCount}
          subtitle="Score >= 70 or sensitive operation"
          variant="warning"
          icon={<ShieldAlertIcon className="w-5 h-5 text-warning" />}
        />
        <MetricCard
          title="Medium Risk"
          value={medCount}
          subtitle="Score 30 - 69 range"
          variant="default"
          icon={<ShieldAlertIcon className="w-5 h-5 text-accent-secondary" />}
        />
        <MetricCard
          title="Low Risk"
          value={lowCount}
          subtitle="Score < 30 standard operations"
          variant="success"
          icon={<ShieldAlertIcon className="w-5 h-5 text-success" />}
        />
      </div>

      {/* Risk Assessment Factor Legend */}
      <SurfaceCard title="Contextual Scoring Factors">
        <div className="grid grid-cols-1 md:grid-cols-4 gap-4 text-xs font-mono">
          <div className="p-3 rounded bg-bg-tertiary/40 border border-border-subtle">
            <span className="text-accent-primary font-bold block mb-1">01. Blast Radius</span>
            <span className="text-text-tertiary">
              Operation criticality: reads (low) vs write/delete/execute (high).
            </span>
          </div>
          <div className="p-3 rounded bg-bg-tertiary/40 border border-border-subtle">
            <span className="text-warning font-bold block mb-1">02. Data Sensitivity</span>
            <span className="text-text-tertiary">
              Presence of PII, financial amounts, credentials, or private schemas.
            </span>
          </div>
          <div className="p-3 rounded bg-bg-tertiary/40 border border-border-subtle">
            <span className="text-danger font-bold block mb-1">03. Target Environment</span>
            <span className="text-text-tertiary">
              Production assets carry automated score multipliers over dev/staging.
            </span>
          </div>
          <div className="p-3 rounded bg-bg-tertiary/40 border border-border-subtle">
            <span className="text-accent-secondary font-bold block mb-1">04. Agent Trust</span>
            <span className="text-text-tertiary">
              Agent autonomy level and historical permission deviations.
            </span>
          </div>
        </div>
      </SurfaceCard>

      {/* Filter Tabs */}
      <div className="flex items-center gap-2 border-b border-border-subtle pb-2">
        <span className="text-xs text-text-tertiary flex items-center gap-1 mr-2">
          <FilterIcon className="w-3.5 h-3.5" />
          Filter Tier:
        </span>
        {(['all', 'critical', 'high', 'medium', 'low'] as const).map((tier) => (
          <button
            key={tier}
            onClick={() => setTierFilter(tier)}
            className={`px-3 py-1 text-xs font-mono rounded transition-colors ${
              tierFilter === tier
                ? 'bg-accent-primary/20 text-accent-primary border border-accent-primary/40'
                : 'text-text-secondary hover:text-text-primary'
            }`}
          >
            {tier.toUpperCase()}
          </button>
        ))}
      </div>

      {/* Decisions / Risk Assessment Ledger */}
      <SurfaceCard title="Evaluated Action Risk Ledger">
        {loading ? (
          <LoadingState message="Fetching risk evaluations..." />
        ) : filteredDecisions.length === 0 ? (
          <EmptyState
            title="No Risk Evaluations Found"
            description="Run action risk assessments or trigger runtime action evaluations to populate."
          />
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-left text-xs font-mono">
              <thead>
                <tr className="border-b border-border-subtle text-text-tertiary uppercase">
                  <th className="py-2.5 px-3">Decision / Assessment ID</th>
                  <th className="py-2.5 px-3">Action ID</th>
                  <th className="py-2.5 px-3">Score & Level</th>
                  <th className="py-2.5 px-3">Primary Factor Reason</th>
                  <th className="py-2.5 px-3">Assessed At</th>
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
                      <RiskBadge score={d.risk_score} level={d.risk_tier} />
                    </td>
                    <td className="py-2.5 px-3 max-w-xs truncate text-text-tertiary">
                      {d.reason || 'Calculated via rule matrix'}
                    </td>
                    <td className="py-2.5 px-3 text-text-muted">
                      {new Date(d.evaluated_at).toLocaleString()}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </SurfaceCard>

      {/* Evaluate Risk Modal */}
      <Modal
        isOpen={assessModalOpen}
        onClose={() => setAssessModalOpen(false)}
        title="Contextual Risk Evaluation"
        size="lg"
      >
        <div className="space-y-4">
          <div>
            <label className="block text-xs font-mono uppercase text-text-tertiary mb-1">
              Select Runtime Action To Evaluate
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

          <div className="flex justify-end gap-2">
            <Button variant="ghost" onClick={() => setAssessModalOpen(false)}>
              Close
            </Button>
            <Button
              variant="primary"
              loading={evaluating}
              onClick={handleRunAssessment}
              disabled={!selectedActionId}
            >
              Compute Risk Factors
            </Button>
          </div>

          {assessmentResult && (
            <div className="mt-4 pt-4 border-t border-border-subtle space-y-3">
              <div className="flex items-center justify-between">
                <span className="text-xs font-mono text-text-secondary uppercase">
                  Assessment Result:
                </span>
                <RiskBadge
                  score={assessmentResult.overall_score}
                  level={assessmentResult.risk_tier}
                />
              </div>

              <div>
                <span className="text-[10px] font-mono uppercase text-text-tertiary block mb-1">
                  Factor Breakdown:
                </span>
                <CodeView code={assessmentResult.factors} language="json" maxHeight="200px" />
              </div>
            </div>
          )}
        </div>
      </Modal>
    </div>
  );
};
