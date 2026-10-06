import React, { useEffect, useState } from 'react';
import { useOrg } from '../context/OrgContext';
import { checkBackendHealth } from '../api';
import { SurfaceCard } from '../components/common/Card';
import { Button } from '../components/common/Button';
import { seedSampleScenario } from '../api/seeder';
import {
  CheckCircleIcon,
  XCircleIcon,
  ServerIcon,
  ShieldCheckIcon,
  SparklesIcon,
} from '../components/common/Icons';

export const SettingsPage: React.FC = () => {
  const { activeOrg, currentUser } = useOrg();
  const [healthStatus, setHealthStatus] = useState<{ status: string; latencyMs: number } | null>(null);
  const [checking, setChecking] = useState(false);
  const [seeding, setSeeding] = useState(false);
  const [seedResult, setSeedResult] = useState<string | null>(null);

  const pingBackend = async () => {
    try {
      setChecking(true);
      const start = performance.now();
      const res = await checkBackendHealth();
      const latencyMs = Math.round(performance.now() - start);
      setHealthStatus({ status: res.status, latencyMs });
    } catch (err: any) {
      setHealthStatus({ status: 'unreachable', latencyMs: 0 });
    } finally {
      setChecking(false);
    }
  };

  useEffect(() => {
    pingBackend();
  }, []);

  const handleSeedData = async () => {
    if (!activeOrg) return;
    try {
      setSeeding(true);
      setSeedResult(null);
      const res = await seedSampleScenario(activeOrg.id);
      setSeedResult(res.message);
    } catch (err: any) {
      setSeedResult(`Seeding failed: ${err.message}`);
    } finally {
      setSeeding(false);
    }
  };

  return (
    <div className="space-y-6">
      {/* Top Banner */}
      <div>
        <h1 className="text-2xl font-bold font-mono tracking-tight text-text-primary">
          Platform Settings & Health
        </h1>
        <p className="text-xs text-text-secondary mt-1">
          Control plane configuration, backend connectivity, tenant attributes, and diagnostic tools.
        </p>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Backend Connectivity */}
        <SurfaceCard
          title="Backend API Connectivity"
          action={
            <Button
              variant="outline"
              size="sm"
              loading={checking}
              onClick={pingBackend}
            >
              Ping API
            </Button>
          }
        >
          <div className="space-y-3 font-mono text-xs">
            <div className="flex items-center justify-between p-3 rounded bg-bg-tertiary/40 border border-border-subtle">
              <span className="text-text-secondary">Health Endpoint:</span>
              <span className="text-text-primary">/health</span>
            </div>

            <div className="flex items-center justify-between p-3 rounded bg-bg-tertiary/40 border border-border-subtle">
              <span className="text-text-secondary">Connectivity Status:</span>
              <span className="flex items-center gap-1.5 font-semibold">
                {healthStatus?.status === 'ok' ? (
                  <>
                    <CheckCircleIcon className="w-4 h-4 text-success" />
                    <span className="text-success uppercase">CONNECTED (HEALTHY)</span>
                  </>
                ) : (
                  <>
                    <XCircleIcon className="w-4 h-4 text-danger" />
                    <span className="text-danger uppercase">DISCONNECTED</span>
                  </>
                )}
              </span>
            </div>

            <div className="flex items-center justify-between p-3 rounded bg-bg-tertiary/40 border border-border-subtle">
              <span className="text-text-secondary">Round-Trip Latency:</span>
              <span className="text-accent-primary font-bold">
                {healthStatus?.latencyMs || 0} ms
              </span>
            </div>

            <div className="flex items-center justify-between p-3 rounded bg-bg-tertiary/40 border border-border-subtle">
              <span className="text-text-secondary">Base URL:</span>
              <span className="text-text-muted">http://localhost:8000/api/v1</span>
            </div>
          </div>
        </SurfaceCard>

        {/* Tenant Information */}
        <SurfaceCard title="Active Tenant Context">
          <div className="space-y-3 font-mono text-xs">
            <div className="flex items-center justify-between p-3 rounded bg-bg-tertiary/40 border border-border-subtle">
              <span className="text-text-secondary">Organization Name:</span>
              <span className="text-text-primary font-semibold">{activeOrg?.name || 'Loading...'}</span>
            </div>

            <div className="flex items-center justify-between p-3 rounded bg-bg-tertiary/40 border border-border-subtle">
              <span className="text-text-secondary">Organization Slug:</span>
              <span className="text-accent-secondary">{activeOrg?.slug || 'loading'}</span>
            </div>

            <div className="flex items-center justify-between p-3 rounded bg-bg-tertiary/40 border border-border-subtle">
              <span className="text-text-secondary">Tenant ID (UUID):</span>
              <span className="text-text-muted">{activeOrg?.id || '-'}</span>
            </div>

            <div className="flex items-center justify-between p-3 rounded bg-bg-tertiary/40 border border-border-subtle">
              <span className="text-text-secondary">Governance User:</span>
              <span className="text-accent-primary font-semibold">{currentUser?.email || 'admin'}</span>
            </div>
          </div>
        </SurfaceCard>
      </div>

      {/* Security Engine Architecture & Guarantees */}
      <SurfaceCard title="Architectural Security Guarantees">
        <div className="grid grid-cols-1 md:grid-cols-3 gap-4 font-mono text-xs">
          <div className="p-3 rounded bg-bg-tertiary/40 border border-border-subtle">
            <div className="flex items-center gap-2 mb-1">
              <ShieldCheckIcon className="w-4 h-4 text-success" />
              <span className="font-semibold text-text-primary">Execution Guard</span>
            </div>
            <p className="text-text-tertiary">
              No shell execution, no arbitrary Python eval/exec, whitelist-only tool dispatch.
            </p>
          </div>

          <div className="p-3 rounded bg-bg-tertiary/40 border border-border-subtle">
            <div className="flex items-center gap-2 mb-1">
              <ShieldCheckIcon className="w-4 h-4 text-accent-primary" />
              <span className="font-semibold text-text-primary">Credential Isolation</span>
            </div>
            <p className="text-text-tertiary">
              Raw tokens are never displayed post-creation and hashed using SHA-256 before storage.
            </p>
          </div>

          <div className="p-3 rounded bg-bg-tertiary/40 border border-border-subtle">
            <div className="flex items-center gap-2 mb-1">
              <ShieldCheckIcon className="w-4 h-4 text-warning" />
              <span className="font-semibold text-text-primary">Tenant Boundary</span>
            </div>
            <p className="text-text-tertiary">
              Strict multi-tenant isolation enforced at the database and API query levels.
            </p>
          </div>
        </div>
      </SurfaceCard>

      {/* Demo Scenario Generator */}
      <SurfaceCard title="Interactive Scenario Generator">
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
          <div className="max-w-xl">
            <span className="text-xs font-semibold text-text-primary font-mono block">
              Populate Demo Security Control Plane
            </span>
            <span className="text-xs text-text-secondary mt-0.5 block">
              Creates sample enterprise agents (Billing Agent, DevOps Agent), tools (Stripe API, AWS RDS, S3),
              permissions, approval-requiring policies, actions, and executions.
            </span>
          </div>

          <Button
            variant="primary"
            loading={seeding}
            onClick={handleSeedData}
            leftIcon={<SparklesIcon className="w-4 h-4 text-accent-primary" />}
          >
            Seed Demo Scenario
          </Button>
        </div>

        {seedResult && (
          <div className="mt-4 p-3 rounded bg-bg-tertiary border border-border-default font-mono text-xs text-accent-primary">
            {seedResult}
          </div>
        )}
      </SurfaceCard>
    </div>
  );
};
