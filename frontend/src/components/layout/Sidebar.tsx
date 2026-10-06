import React, { useState } from 'react';
import { Link, useLocation } from '../../router/Router';
import {
  ActivityIcon,
  AlertTriangleIcon,
  BotIcon,
  ChevronRightIcon,
  CompassIcon,
  InboxIcon,
  KeyIcon,
  LayersIcon,
  LinkIcon,
  LockIcon,
  PlayIcon,
  ScaleIcon,
  SettingsIcon,
  ShieldIcon,
  ShieldAlertIcon,
  SparklesIcon,
  TerminalIcon,
  WrenchIcon,
} from '../common/Icons';
import { useOrg } from '../../context/OrgContext';

interface NavItem {
  label: string;
  path: string;
  icon: React.ReactNode;
  badge?: string | number;
}

export const Sidebar: React.FC<{
  pendingApprovalsCount?: number;
}> = ({ pendingApprovalsCount = 0 }) => {
  const { pathname } = useLocation();
  const { currentOrg } = useOrg();
  const [collapsed, setCollapsed] = useState(false);

  const navItems: NavItem[] = [
    { label: 'Dashboard', path: '/', icon: <ActivityIcon size={18} /> },
    { label: 'Agents', path: '/agents', icon: <BotIcon size={18} /> },
    { label: 'Tools', path: '/tools', icon: <WrenchIcon size={18} /> },
    { label: 'Permissions', path: '/permissions', icon: <LockIcon size={18} /> },
    { label: 'Policies', path: '/policies', icon: <ScaleIcon size={18} /> },
    { label: 'Runtime Actions', path: '/runtime-actions', icon: <TerminalIcon size={18} /> },
    { label: 'LLM Gateway', path: '/llm-security', icon: <SparklesIcon size={18} /> },
    { label: 'MCP Security', path: '/mcp-security', icon: <CompassIcon size={18} /> },
    { label: 'Risk', path: '/risk', icon: <LayersIcon size={18} /> },
    { label: 'Decisions', path: '/decisions', icon: <KeyIcon size={18} /> },
    { label: 'Security Findings', path: '/findings', icon: <AlertTriangleIcon size={18} /> },
    { label: 'Behavioral Anomaly', path: '/behavior-security', icon: <ShieldAlertIcon size={18} /> },
    {
      label: 'Approvals',
      path: '/approvals',
      icon: <InboxIcon size={18} />,
      badge: pendingApprovalsCount > 0 ? pendingApprovalsCount : undefined,
    },
    { label: 'Executions', path: '/executions', icon: <PlayIcon size={18} /> },
    { label: 'Audit Trail', path: '/audit', icon: <ShieldIcon size={18} /> },
    { label: 'Integrations & Webhooks', path: '/integrations', icon: <LinkIcon size={18} /> },
    { label: 'Settings', path: '/settings', icon: <SettingsIcon size={18} /> },
  ];

  const isActive = (itemPath: string) => {
    if (itemPath === '/') {
      return pathname === '/';
    }
    return pathname.startsWith(itemPath);
  };

  return (
    <aside className={`app-sidebar ${collapsed ? 'sidebar-collapsed' : ''}`}>
      {/* Brand Header */}
      <div className="sidebar-brand">
        <Link to="/" className="brand-logo-link">
          <div className="brand-shield-glow">
            <ShieldIcon size={24} className="brand-shield-icon" />
          </div>
          {!collapsed && (
            <div className="brand-text-block">
              <span className="brand-name">CUSTODE</span>
              <span className="brand-tag">AGENT CONTROL PLANE</span>
            </div>
          )}
        </Link>
        <button
          className="sidebar-collapse-toggle"
          onClick={() => setCollapsed(!collapsed)}
          title={collapsed ? 'Expand sidebar' : 'Collapse sidebar'}
        >
          <ChevronRightIcon size={16} className={`toggle-arrow ${collapsed ? '' : 'rotate-180'}`} />
        </button>
      </div>

      {/* Nav Menu */}
      <nav className="sidebar-nav">
        <div className="nav-group-label">{!collapsed && 'PLATFORM MODULES'}</div>
        <ul className="nav-list">
          {navItems.map((item) => {
            const active = isActive(item.path);
            return (
              <li key={item.path} className="nav-item">
                <Link
                  to={item.path}
                  className={`nav-link ${active ? 'nav-link-active' : ''}`}
                  title={item.label}
                >
                  <span className="nav-icon">{item.icon}</span>
                  {!collapsed && <span className="nav-label">{item.label}</span>}
                  {!collapsed && item.badge !== undefined && (
                    <span className="nav-badge-pill">{item.badge}</span>
                  )}
                </Link>
              </li>
            );
          })}
        </ul>
      </nav>

      {/* Tenant Context Footer */}
      {!collapsed && (
        <div className="sidebar-footer">
          <div className="sidebar-tenant-card">
            <div className="tenant-status-dot" />
            <div className="tenant-info">
              <div className="tenant-label">ACTIVE TENANT</div>
              <div className="tenant-name" title={currentOrg?.name || 'Loading...'}>
                {currentOrg?.name || 'Default Organization'}
              </div>
            </div>
          </div>
        </div>
      )}
    </aside>
  );
};
