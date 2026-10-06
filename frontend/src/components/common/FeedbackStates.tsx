import React from 'react';
import { AlertTriangleIcon, InboxIcon, RefreshIcon } from './Icons';
import { Button } from './Button';

export const LoadingState: React.FC<{ message?: string }> = ({ message = 'Loading security data...' }) => (
  <div className="state-container state-loading">
    <div className="spinner-large" />
    <p className="state-message">{message}</p>
  </div>
);

export const ErrorState: React.FC<{
  title?: string;
  message: string;
  onRetry?: () => void;
}> = ({ title = 'Failed to load data', message, onRetry }) => (
  <div className="state-container state-error">
    <div className="state-icon state-icon-danger">
      <AlertTriangleIcon size={32} />
    </div>
    <h4 className="state-title">{title}</h4>
    <p className="state-message">{message}</p>
    {onRetry && (
      <Button variant="outline" size="sm" onClick={onRetry} icon={<RefreshIcon size={14} />}>
        Retry Request
      </Button>
    )}
  </div>
);

export const EmptyState: React.FC<{
  title: string;
  description: string;
  action?: React.ReactNode;
  icon?: React.ReactNode;
}> = ({ title, description, action, icon }) => (
  <div className="state-container state-empty">
    <div className="state-icon">{icon || <InboxIcon size={36} />}</div>
    <h4 className="state-title">{title}</h4>
    <p className="state-message">{description}</p>
    {action && <div className="state-action">{action}</div>}
  </div>
);
