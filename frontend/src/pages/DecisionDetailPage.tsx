import React, { useEffect, useState } from 'react';
import { useRouteParams, navigate } from '../router/Router';
import { useOrg } from '../context/OrgContext';
import { getDecision, getRuntimeAction } from '../api';
import { Decision, RuntimeAction } from '../types';
import { SurfaceCard } from '../components/common/Card';
import { DecisionBadge, RiskBadge } from '../components/common/Badges';
import { Button } from '../components/common/Button';
import { CodeView } from '../components/common/CodeView';
import { LoadingState, ErrorState } from '../components/common/FeedbackStates';
import { ArrowLeftIcon, PlayIcon, CheckCircleIcon } from '../components/common/Icons';

export const DecisionDetailPage: React.FC = () => {
  const { id } = useRouteParams();
  const { activeOrg } = useOrg();

  const [decision, setDecision] = useState<Decision | null>(null);
  const [action, setAction] = useState<RuntimeAction | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const fetchData = async () => {
    if (!activeOrg || !id) return;
    try {
      setLoading(true);
      setError(null);
      const dec = await getDecision(activeOrg.id, id);
      setDecision(dec);

      if (dec.runtime_action_id) {
        const act = await getRuntimeAction(activeOrg.id, dec.runtime_action_id).catch(() => null);
        setAction(act);
      }
    } catch (err: any) {
      setError(err?.message || 'Failed to fetch decision details');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchData();
  }, [activeOrg?.id, id]);

  if (loading) return <LoadingState message="Loading decision evaluation trace..." />;
  if (error || !decision) {
    return (
      <ErrorState
        title="Decision Not Found"
        message={error || 'Could not load decision record'}
        onRetry={fetchData}
      />
    );
  }

  return (
    <div className="space-y-6">
      {/* Top Banner */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-3">
          <Button
            variant="ghost"
            size="sm"
            onClick={() => navigate('/decisions')}
            leftIcon={<ArrowLeftIcon className="w-4 h-4" />}
          >
            Back
          </Button>
          <div>
            <div className="flex items-center gap-2">
              <h1 className="text-xl font-bold font-mono tracking-tight text-text-primary">
                Decision: {decision.id}
              </h1>
              <DecisionBadge decision={decision.decision} />
              <RiskBadge score={decision.risk_score} level={decision.risk_tier} />
            </div>
            <p className="text-xs text-text-tertiary font-mono mt-0.5">
              Action ID: {decision.runtime_action_id} | Evaluated at:{' '}
              {new Date(decision.evaluated_at).toLocaleString()}
            </p>
          </div>
        </div>

        <div className="flex items-center gap-2">
          {action && (
            <Button
              variant="outline"
              size="sm"
              onClick={() => navigate(`/runtime-actions/${action.id}`)}
            >
              View Runtime Action
            </Button>
          )}
          {decision.decision === 'require_approval' && (
            <Button
              variant="primary"
              size="sm"
              onClick={() => navigate('/approvals')}
            >
              Open Approval Inbox
            </Button>
          )}
        </div>
      </div>

      {/* Decision Summary */}
      <SurfaceCard title="Authoritative Evaluation Outcome">
        <div className="grid grid-cols-1 md:grid-cols-3 gap-4 text-xs font-mono">
          <div className="p-3 bg-bg-tertiary/40 border border-border-subtle rounded">
            <span className="text-text-tertiary uppercase block text-[10px]">Decision Verdict</span>
            <div className="mt-1">
              <DecisionBadge decision={decision.decision} />
            </div>
            <p className="text-text-muted mt-2 text-[11px]">
              {decision.decision === 'allow'
                ? 'Execution permitted subject to environment boundaries.'
                : decision.decision === 'require_approval'
                ? 'Action paused; awaits review from designated security officer.'
                : 'Execution strictly prohibited by authorization boundary.'}
            </p>
          </div>

          <div className="p-3 bg-bg-tertiary/40 border border-border-subtle rounded">
            <span className="text-text-tertiary uppercase block text-[10px]">Assessed Risk</span>
            <div className="mt-1">
              <RiskBadge score={decision.risk_score} level={decision.risk_tier} />
            </div>
            <p className="text-text-muted mt-2 text-[11px]">
              Risk Score: <span className="font-bold text-text-primary">{decision.risk_score} / 100</span>
            </p>
          </div>

          <div className="p-3 bg-bg-tertiary/40 border border-border-subtle rounded">
            <span className="text-text-tertiary uppercase block text-[10px]">Evaluation Reason</span>
            <p className="mt-1 text-text-primary font-semibold">
              {decision.reason || 'Synthesized via permission + policy + risk matrices'}
            </p>
          </div>
        </div>
      </SurfaceCard>

      {/* Evaluation Trace / Factors */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        <SurfaceCard title="Evaluation Trace & Rules Triggered">
          <CodeView
            code={decision.evaluation_trace || { info: 'No detailed trace parameters persisted.' }}
            language="json"
            maxHeight="320px"
          />
        </SurfaceCard>

        <SurfaceCard title="Raw Decision Record">
          <CodeView
            code={decision}
            language="json"
            maxHeight="320px"
          />
        </SurfaceCard>
      </div>
    </div>
  );
};
