import React, { useState } from 'react';
import { TimelineEventItem } from '../../types';
import { CodeView } from './CodeView';
import { ClockIcon, ShieldCheckIcon, AlertTriangleIcon, CheckIcon, XIcon, UserIcon, BotIcon } from './Icons';

interface ForensicTimelineProps {
  timeline: TimelineEventItem[];
  title?: string;
}

export const ForensicTimeline: React.FC<ForensicTimelineProps> = ({
  timeline,
  title = 'Authoritative Forensic Lifecycle Timeline',
}) => {
  const [expandedIndex, setExpandedIndex] = useState<number | null>(null);

  if (!timeline || timeline.length === 0) {
    return (
      <div style={{ padding: '2rem', textAlign: 'center', color: 'var(--text-muted)' }}>
        No forensic timeline events recorded for this runtime action.
      </div>
    );
  }

  const toggleExpand = (idx: number) => {
    setExpandedIndex(expandedIndex === idx ? null : idx);
  };

  const getStageColor = (stage: string) => {
    switch (stage) {
      case 'IDENTITY':
        return '#6366f1';
      case 'CONTEXT':
        return '#0284c7';
      case 'RISK':
        return '#f59e0b';
      case 'DECISION':
        return '#8b5cf6';
      case 'GOVERNANCE':
        return '#ec4899';
      case 'BEHAVIOR':
        return '#06b6d4';
      case 'SCAN':
        return '#f43f5e';
      case 'EXECUTION':
        return '#10b981';
      case 'AUDIT':
        return '#64748b';
      default:
        return '#3b82f6';
    }
  };

  const getStatusIcon = (status: string) => {
    switch (status) {
      case 'success':
        return <CheckIcon size={14} color="#10b981" />;
      case 'danger':
        return <XIcon size={14} color="#ef4444" />;
      case 'warning':
        return <AlertTriangleIcon size={14} color="#f59e0b" />;
      default:
        return <ShieldCheckIcon size={14} color="#3b82f6" />;
    }
  };

  return (
    <div style={{ margin: '1.5rem 0' }}>
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '1.25rem' }}>
        <h3 style={{ fontSize: '1.1rem', fontWeight: 600, color: 'var(--text-primary)', margin: 0 }}>
          {title}
        </h3>
        <span style={{ fontSize: '0.8rem', color: 'var(--text-muted)' }}>
          {timeline.length} verified milestone{timeline.length === 1 ? '' : 's'}
        </span>
      </div>

      <div style={{ position: 'relative', paddingLeft: '2rem' }}>
        {/* Continuous vertical timeline connector line */}
        <div
          style={{
            position: 'absolute',
            top: '0.75rem',
            bottom: '0.75rem',
            left: '0.875rem',
            width: '2px',
            backgroundColor: 'var(--border-color, #27272a)',
            zIndex: 1,
          }}
        />

        {timeline.map((item, idx) => {
          const isExpanded = expandedIndex === idx;
          const stageColor = getStageColor(item.stage);
          const hasDetails = item.details && Object.keys(item.details).length > 0;

          return (
            <div
              key={`${item.stage}-${idx}`}
              style={{
                position: 'relative',
                marginBottom: '1.5rem',
                zIndex: 2,
              }}
            >
              {/* Timeline Node Bullet */}
              <div
                style={{
                  position: 'absolute',
                  left: '-2rem',
                  top: '0.25rem',
                  width: '1.75rem',
                  height: '1.75rem',
                  borderRadius: '50%',
                  backgroundColor: 'var(--bg-card, #18181b)',
                  border: `2px solid ${stageColor}`,
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'center',
                  boxShadow: '0 0 10px rgba(0,0,0,0.5)',
                }}
              >
                {getStatusIcon(item.status)}
              </div>

              {/* Event Card */}
              <div
                style={{
                  backgroundColor: 'var(--bg-card, #18181b)',
                  border: '1px solid var(--border-color, #27272a)',
                  borderRadius: '8px',
                  padding: '1rem 1.25rem',
                  transition: 'border-color 0.2s ease',
                }}
              >
                <div
                  style={{
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'space-between',
                    flexWrap: 'wrap',
                    gap: '0.5rem',
                    marginBottom: '0.5rem',
                  }}
                >
                  <div style={{ display: 'flex', alignItems: 'center', gap: '0.6rem' }}>
                    <span
                      style={{
                        fontSize: '0.7rem',
                        fontWeight: 700,
                        textTransform: 'uppercase',
                        padding: '0.2rem 0.5rem',
                        borderRadius: '4px',
                        backgroundColor: `${stageColor}22`,
                        color: stageColor,
                        border: `1px solid ${stageColor}44`,
                        letterSpacing: '0.05em',
                      }}
                    >
                      {item.stage}
                    </span>
                    <strong style={{ fontSize: '0.95rem', color: 'var(--text-primary)' }}>
                      {item.event_name}
                    </strong>
                  </div>

                  <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', fontSize: '0.8rem', color: 'var(--text-muted)' }}>
                    <ClockIcon size={12} />
                    <span>{new Date(item.timestamp).toLocaleString()}</span>
                  </div>
                </div>

                <p style={{ margin: '0 0 0.6rem 0', fontSize: '0.875rem', color: 'var(--text-secondary)' }}>
                  {item.summary}
                </p>

                <div
                  style={{
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'space-between',
                    fontSize: '0.8rem',
                    color: 'var(--text-muted)',
                    paddingTop: '0.5rem',
                    borderTop: '1px solid var(--border-subtle, #27272a44)',
                  }}
                >
                  <div style={{ display: 'flex', alignItems: 'center', gap: '0.4rem' }}>
                    {item.actor ? (
                      <>
                        {item.actor.toLowerCase().includes('user') ? (
                          <UserIcon size={12} />
                        ) : item.actor.toLowerCase().includes('agent') ? (
                          <BotIcon size={12} />
                        ) : (
                          <ShieldCheckIcon size={12} />
                        )}
                        <span>Actor: {item.actor}</span>
                      </>
                    ) : (
                      <span>Engine Core</span>
                    )}
                  </div>

                  {hasDetails && (
                    <button
                      type="button"
                      onClick={() => toggleExpand(idx)}
                      style={{
                        background: 'none',
                        border: 'none',
                        color: 'var(--brand-primary, #6366f1)',
                        cursor: 'pointer',
                        fontSize: '0.8rem',
                        fontWeight: 500,
                        padding: '0.2rem 0.4rem',
                      }}
                    >
                      {isExpanded ? 'Hide Forensics ▲' : 'Inspect Forensics ▼'}
                    </button>
                  )}
                </div>

                {isExpanded && hasDetails && (
                  <div style={{ marginTop: '0.75rem' }}>
                    <CodeView data={item.details} label={`${item.stage} FORENSIC ARTIFACTS`} maxHeight="240px" />
                  </div>
                )}
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
};
