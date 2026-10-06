import React from 'react';

export const MetricCard: React.FC<{
  title: string;
  value: string | number;
  subtext?: string;
  subtitle?: string;
  icon?: React.ReactNode;
  badge?: React.ReactNode;
  variant?: 'default' | 'accent' | 'warning' | 'danger' | 'success';
  onClick?: () => void;
}> = ({ title, value, subtext, subtitle, icon, badge, variant = 'default', onClick }) => {
  const effectiveSub = subtext || subtitle;
  return (
    <div className={`metric-card metric-card-${variant} ${onClick ? 'metric-card-interactive' : ''}`} onClick={onClick}>
      <div className="metric-header">
        <span className="metric-title">{title}</span>
        {icon && <span className="metric-icon">{icon}</span>}
      </div>
      <div className="metric-body">
        <div className="metric-value">{value}</div>
        {badge && <div className="metric-badge">{badge}</div>}
      </div>
      {effectiveSub && <div className="metric-subtext">{effectiveSub}</div>}
    </div>
  );
};

export const SurfaceCard: React.FC<{
  title?: React.ReactNode;
  subtitle?: React.ReactNode;
  actions?: React.ReactNode;
  action?: React.ReactNode;
  children: React.ReactNode;
  className?: string;
  style?: React.CSSProperties;
}> = ({ title, subtitle, actions, action, children, className = '', style }) => {
  const effectiveActions = actions || action;
  return (
    <div className={`surface-card ${className}`} style={style}>
      {(title || effectiveActions) && (
        <div className="surface-card-header">
          <div>
            {title && <h3 className="surface-card-title">{title}</h3>}
            {subtitle && <p className="surface-card-subtitle">{subtitle}</p>}
          </div>
          {effectiveActions && <div className="surface-card-actions">{effectiveActions}</div>}
        </div>
      )}
      <div className="surface-card-content">{children}</div>
    </div>
  );
};

export const Card = SurfaceCard;

