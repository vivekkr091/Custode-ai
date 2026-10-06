import React, { useEffect, useState } from 'react';
import { useRouteParams, navigate } from '../router/Router';
import { useOrg } from '../context/OrgContext';
import { getExecution, getRuntimeAction } from '../api';
import { Execution, RuntimeAction } from '../types';
import { SurfaceCard } from '../components/common/Card';
import { StatusBadge } from '../components/common/Badges';
import { Button } from '../components/common/Button';
import { CodeView } from '../components/common/CodeView';
import { LoadingState, ErrorState } from '../components/common/FeedbackStates';
import {
  ArrowLeftIcon,
  ShieldCheckIcon,
  CheckCircleIcon,
  XCircleIcon,
} from '../components/common/Icons';

export const ExecutionDetailPage: React.FC = () => {
  const { id } = useRouteParams();
  const { activeOrg } = useOrg();

  const [execution, setExecution] = useState<Execution | null>(null);
  const [action, setAction] = useState<RuntimeAction | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const fetchData = async () => {
    if (!activeOrg || !id) return;
    try {
      setLoading(true);
      setError(null);
      const exec = await getExecution(activeOrg.id, id);
      setExecution(exec);

      if (exec.runtime_action_id) {
        const act = await getRuntimeAction(activeOrg.id, exec.runtime_action_id).catch(() => null);
        setAction(act);
      }
    } catch (err: any) {
      setError(err?.message || 'Failed to fetch execution details');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchData();
  }, [activeOrg?.id, id]);

  if (loading) return <LoadingState message="Loading execution record..." />;
  if (error || !execution) {
    return (
      <ErrorState
        title="Execution Record Not Found"
        message={error || 'Could not load execution record'}
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
            onClick={() => navigate('/executions')}
            leftIcon={<ArrowLeftIcon className="w-4 h-4" />}
          >
            Back
          </Button>
          <div>
            <div className="flex items-center gap-2">
              <h1 className="text-xl font-bold font-mono tracking-tight text-text-primary">
                Execution: {execution.id}
              </h1>
              <StatusBadge status={execution.status} />
            </div>
            <p className="text-xs text-text-tertiary font-mono mt-0.5">
              Action ID: {execution.runtime_action_id} | Dispatched at:{' '}
              {new Date(execution.executed_at || execution.started_at || execution.created_at).toLocaleString()}
            </p>
          </div>
        </div>

        {action && (
          <Button
            variant="outline"
            size="sm"
            onClick={() => navigate(`/runtime-actions/${action.id}`)}
          >
            View Runtime Action
          </Button>
        )}
      </div>

      {/* Execution Summary Cards */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-4 font-mono text-xs">
        <div className="p-4 rounded-lg bg-bg-secondary border border-border-default">
          <span className="text-text-tertiary uppercase text-[10px] block">Execution Guard</span>
          <div className="flex items-center gap-2 mt-1">
            <ShieldCheckIcon className="w-4 h-4 text-success" />
            <span className="font-semibold text-text-primary">Validated Pre-Flight</span>
          </div>
          <span className="text-[11px] text-text-muted mt-1 block">
            Passed policy, permission, and parameter schema checks.
          </span>
        </div>

        <div className="p-4 rounded-lg bg-bg-secondary border border-border-default">
          <span className="text-text-tertiary uppercase text-[10px] block">Execution Outcome</span>
          <div className="flex items-center gap-2 mt-1">
            {execution.status === 'success' ? (
              <>
                <CheckCircleIcon className="w-4 h-4 text-success" />
                <span className="font-semibold text-success">SUCCESS</span>
              </>
            ) : (
              <>
                <XCircleIcon className="w-4 h-4 text-danger" />
                <span className="font-semibold text-danger">FAILED</span>
              </>
            )}
          </div>
          <span className="text-[11px] text-text-muted mt-1 block">
            {execution.error_message || 'Completed with valid output payload.'}
          </span>
        </div>

        <div className="p-4 rounded-lg bg-bg-secondary border border-border-default">
          <span className="text-text-tertiary uppercase text-[10px] block">Target Operation</span>
          <span className="font-semibold text-accent-primary mt-1 block">
            {action ? `${action.tool_name}::${action.operation_name}` : 'Registered Tool'}
          </span>
          <span className="text-[11px] text-text-muted mt-1 block">
            Environment: {action?.environment || 'Active Tenant'}
          </span>
        </div>
      </div>

      {/* Output / Results */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        <SurfaceCard title="Execution Result Payload">
          <CodeView
            code={execution.result || { message: 'No output data returned' }}
            language="json"
            maxHeight="320px"
          />
        </SurfaceCard>

        <SurfaceCard title="Full Execution Audit Metadata">
          <CodeView
            code={execution}
            language="json"
            maxHeight="320px"
          />
        </SurfaceCard>
      </div>
    </div>
  );
};
