import React from 'react';
import { DecisionType, RiskLevel } from '../../types';

export const DecisionBadge: React.FC<{ decision: string | DecisionType; size?: 'sm' | 'md' }> = ({ decision, size = 'sm' }) => {
  const norm = String(decision || '').toUpperCase();
  let colorClass = 'badge-decision-allow';

  if (norm.includes('BLOCK') || norm.includes('DENY')) {
    colorClass = 'badge-decision-block';
  } else if (norm.includes('APPROVAL') || norm.includes('REQUIRE')) {
    colorClass = 'badge-decision-approval';
  }

  return (
    <span className={`badge ${colorClass} badge-${size}`}>
      <span className="badge-dot" />
      {norm}
    </span>
  );
};

export const RiskBadge: React.FC<{ level?: string | RiskLevel; score?: number; size?: 'sm' | 'md' }> = ({ level = 'LOW', score, size = 'sm' }) => {
  const norm = String(level || 'LOW').toUpperCase();
  let colorClass = 'badge-risk-low';

  if (norm === 'CRITICAL') {
    colorClass = 'badge-risk-critical';
  } else if (norm === 'HIGH') {
    colorClass = 'badge-risk-high';
  } else if (norm === 'MEDIUM') {
    colorClass = 'badge-risk-medium';
  }

  return (
    <span className={`badge ${colorClass} badge-${size}`}>
      {norm}
      {score !== undefined && <span className="badge-suffix">({score.toFixed(0)})</span>}
    </span>
  );
};

export const StatusBadge: React.FC<{ status: string; size?: 'sm' | 'md' }> = ({ status, size = 'sm' }) => {
  const norm = String(status || '').toLowerCase();
  let colorClass = 'badge-status-neutral';

  if (['active', 'approved', 'executed', 'succeeded', 'published', 'success'].includes(norm)) {
    colorClass = 'badge-status-success';
  } else if (['pending', 'evaluating', 'running'].includes(norm)) {
    colorClass = 'badge-status-warning';
  } else if (['suspended', 'revoked', 'failed', 'blocked', 'rejected', 'denied'].includes(norm)) {
    colorClass = 'badge-status-danger';
  } else if (['expired', 'cancelled', 'retired', 'draft'].includes(norm)) {
    colorClass = 'badge-status-muted';
  }

  return (
    <span className={`badge ${colorClass} badge-${size}`}>
      <span className="badge-dot" />
      {norm.toUpperCase()}
    </span>
  );
};

export const EnvironmentBadge: React.FC<{ environment: string }> = ({ environment }) => {
  const norm = String(environment || 'dev').toLowerCase();
  let label = 'DEV';
  let colorClass = 'badge-env-dev';

  if (norm.startsWith('prod')) {
    label = 'PROD';
    colorClass = 'badge-env-prod';
  } else if (norm.startsWith('stag')) {
    label = 'STAGE';
    colorClass = 'badge-env-stage';
  }

  return (
    <span className={`badge badge-env ${colorClass}`}>
      {label}
    </span>
  );
};
