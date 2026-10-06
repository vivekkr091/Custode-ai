import React, { useState, useEffect, useRef } from 'react';
import { useLocation, navigate } from '../../router/Router';
import { useOrg } from '../../context/OrgContext';
import { EnvironmentBadge } from '../common/Badges';
import { Modal } from '../common/Modal';
import { Button } from '../common/Button';
import { CheckCircleIcon, PlusIcon, RefreshIcon, ServerIcon, SparklesIcon, SearchIcon } from '../common/Icons';
import { healthApi } from '../../api/health';
import { seedDemonstrationData } from '../../api/seeder';
import { observabilityApi } from '../../api/observability';
import { SearchResultItem } from '../../types';
import { useAuth } from '../../context/AuthContext';

export const Header: React.FC<{ onSeedComplete?: () => void }> = ({ onSeedComplete }) => {
  const { pathname } = useLocation();
  const { currentOrg, organizations, setCurrentOrg, createOrg, currentUser } = useOrg();
  const { role, logout } = useAuth();
  const [isOrgModalOpen, setIsOrgModalOpen] = useState(false);
  const [newOrgName, setNewOrgName] = useState('');
  const [isCreatingOrg, setIsCreatingOrg] = useState(false);
  const [backendStatus, setBackendStatus] = useState<'checking' | 'online' | 'offline'>('checking');
  const [seeding, setSeeding] = useState(false);
  const [seedNotice, setSeedNotice] = useState<string | null>(null);

  // Global Investigation Search
  const [searchQuery, setSearchQuery] = useState('');
  const [searchResults, setSearchResults] = useState<SearchResultItem[]>([]);
  const [isSearching, setIsSearching] = useState(false);
  const [showSearchDropdown, setShowSearchDropdown] = useState(false);
  const searchContainerRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!currentOrg || !searchQuery.trim()) {
      setSearchResults([]);
      setIsSearching(false);
      return;
    }
    setIsSearching(true);
    const timer = setTimeout(async () => {
      try {
        const res = await observabilityApi.search(currentOrg.id, searchQuery.trim(), 8);
        setSearchResults(res.items || []);
        setShowSearchDropdown(true);
      } catch {
        setSearchResults([]);
      } finally {
        setIsSearching(false);
      }
    }, 250);

    return () => clearTimeout(timer);
  }, [currentOrg, searchQuery]);

  // Click outside listener for search dropdown
  useEffect(() => {
    const handleClickOutside = (event: MouseEvent) => {
      if (searchContainerRef.current && !searchContainerRef.current.contains(event.target as Node)) {
        setShowSearchDropdown(false);
      }
    };
    document.addEventListener('mousedown', handleClickOutside);
    return () => document.removeEventListener('mousedown', handleClickOutside);
  }, []);

  useEffect(() => {
    healthApi.check()
      .then(() => setBackendStatus('online'))
      .catch(() => setBackendStatus('offline'));
  }, []);

  const getPageTitle = (path: string): string => {
    if (path === '/') return 'Security Control Overview';
    if (path.startsWith('/agents')) return 'Agent Identity Registry';
    if (path.startsWith('/tools')) return 'Callable Capabilities Registry';
    if (path.startsWith('/permissions')) return 'Agent-to-Tool Authorization';
    if (path.startsWith('/policies')) return 'Security Policy Engine';
    if (path.startsWith('/runtime-actions')) return 'Runtime Action Audit Plane';
    if (path.startsWith('/risk')) return 'Contextual Risk Assessment';
    if (path.startsWith('/decisions')) return 'Authorization Decision Records';
    if (path.startsWith('/approvals')) return 'Human Governance Approval Inbox';
    if (path.startsWith('/executions')) return 'Controlled Execution Layer';
    if (path.startsWith('/audit')) return 'Security Audit Trail';
    if (path.startsWith('/settings')) return 'Platform Settings & Environment';
    return 'Console';
  };

  const handleCreateOrg = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!newOrgName.trim()) return;
    setIsCreatingOrg(true);
    try {
      await createOrg(newOrgName.trim());
      setNewOrgName('');
      setIsOrgModalOpen(false);
    } catch (err: any) {
      alert(`Error creating organization: ${err.message}`);
    } finally {
      setIsCreatingOrg(false);
    }
  };

  const handleQuickSeed = async () => {
    if (!currentOrg) return;
    setSeeding(true);
    setSeedNotice(null);
    try {
      const res = await seedDemonstrationData(currentOrg.id, currentUser?.id);
      if (res.success) {
        setSeedNotice('Sample agents, tools, policies & actions populated!');
        if (onSeedComplete) onSeedComplete();
        setTimeout(() => setSeedNotice(null), 4000);
      } else {
        alert(res.message);
      }
    } finally {
      setSeeding(false);
    }
  };

  return (
    <header className="app-header-bar">
      <div className="header-left">
        <h1 className="header-page-title">{getPageTitle(pathname)}</h1>
        <div className="header-breadcrumbs">
          <span className="breadcrumb-root">CUSTODE</span>
          <span className="breadcrumb-separator">/</span>
          <span className="breadcrumb-current">{currentOrg?.name || 'Loading...'}</span>
        </div>
      </div>

      <div className="header-right">
        {/* Global Investigation Search */}
        <div ref={searchContainerRef} style={{ position: 'relative', width: '220px' }}>
          <div style={{ display: 'flex', alignItems: 'center', backgroundColor: 'var(--bg-tertiary, #27272a)', borderRadius: '6px', padding: '0.3rem 0.6rem', border: '1px solid var(--border-subtle, #3f3f46)' }}>
            <SearchIcon size={13} style={{ color: 'var(--text-muted, #71717a)', marginRight: '6px', flexShrink: 0 }} />
            <input
              type="text"
              placeholder="Investigate entities..."
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              onFocus={() => { if (searchResults.length > 0) setShowSearchDropdown(true); }}
              style={{ background: 'transparent', border: 'none', outline: 'none', color: 'var(--text-primary, #f4f4f5)', fontSize: '0.8rem', width: '100%' }}
            />
            {isSearching && <span style={{ fontSize: '10px', color: 'var(--text-muted, #71717a)' }}>...</span>}
          </div>

          {showSearchDropdown && searchResults.length > 0 && (
            <div style={{ position: 'absolute', top: 'calc(100% + 4px)', right: 0, width: '320px', backgroundColor: 'var(--bg-card, #18181b)', border: '1px solid var(--border-color, #3f3f46)', borderRadius: '6px', zIndex: 999, maxHeight: '340px', overflowY: 'auto', boxShadow: '0 10px 25px rgba(0,0,0,0.6)' }}>
              <div style={{ padding: '0.4rem 0.75rem', fontSize: '10px', fontWeight: 700, color: 'var(--text-muted, #71717a)', textTransform: 'uppercase', borderBottom: '1px solid var(--border-subtle, #27272a)' }}>
                Search Results ({searchResults.length})
              </div>
              {searchResults.map((item) => (
                <div
                  key={`${item.entity_type}-${item.id}`}
                  onClick={() => {
                    navigate(item.link);
                    setShowSearchDropdown(false);
                    setSearchQuery('');
                  }}
                  style={{ padding: '0.5rem 0.75rem', cursor: 'pointer', borderBottom: '1px solid var(--border-subtle, #27272a)', textAlign: 'left' }}
                  onMouseEnter={(e) => (e.currentTarget.style.backgroundColor = 'var(--bg-tertiary, #27272a)')}
                  onMouseLeave={(e) => (e.currentTarget.style.backgroundColor = 'transparent')}
                >
                  <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '2px' }}>
                    <span style={{ fontSize: '10px', textTransform: 'uppercase', fontWeight: 700, color: '#818cf8', fontFamily: 'monospace' }}>
                      {item.entity_type.replace('_', ' ')}
                    </span>
                    {item.badge && (
                      <span style={{ fontSize: '10px', padding: '1px 5px', borderRadius: '3px', backgroundColor: '#374151', color: '#9ca3af' }}>
                        {item.badge}
                      </span>
                    )}
                  </div>
                  <div style={{ fontSize: '0.8rem', fontWeight: 600, color: 'var(--text-primary, #f4f4f5)' }}>
                    {item.title}
                  </div>
                  {item.subtitle && (
                    <div style={{ fontSize: '0.72rem', color: 'var(--text-muted, #a1a1aa)', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                      {item.subtitle}
                    </div>
                  )}
                </div>
              ))}
            </div>
          )}
        </div>

        {/* Quick Seed Action for Instant Evaluation */}
        <Button
          variant="outline"
          size="sm"
          onClick={handleQuickSeed}
          loading={seeding}
          icon={<SparklesIcon size={14} />}
          title="Seed realistic agents, tools, actions & decisions"
        >
          {seeding ? 'Seeding Data...' : 'Seed Demo Data'}
        </Button>

        {seedNotice && (
          <div className="header-notice-toast">
            <CheckCircleIcon size={14} className="text-emerald" />
            <span>{seedNotice}</span>
          </div>
        )}

        {/* Backend Connectivity Status */}
        <div className={`health-indicator-pill health-${backendStatus}`} title={`Backend API: ${backendStatus}`}>
          <span className="status-ping-dot" />
          <ServerIcon size={13} />
          <span className="health-label">API {backendStatus.toUpperCase()}</span>
        </div>

        {/* Environment Badge */}
        <EnvironmentBadge environment="development" />

        {/* Organization Switcher */}
        <button
          className="org-switcher-button"
          onClick={() => setIsOrgModalOpen(true)}
          title="Switch Tenant Organization"
        >
          <span className="org-switcher-label">ORG</span>
          <span className="org-switcher-name">{currentOrg?.name || 'Select Org'}</span>
        </button>

        {/* User Identity Context & Logout */}
        <div className="user-profile-badge" title={`Role: ${role || 'Viewer'}`}>
          <div className="user-avatar-circle">
            {currentUser?.display_name ? currentUser.display_name.slice(0, 2).toUpperCase() : 'OP'}
          </div>
          <div className="user-details">
            <span className="user-name">{currentUser?.display_name || 'Operator'}</span>
            <span className="user-role">{role ? role.replace('_', ' ').toUpperCase() : 'OPERATOR'}</span>
          </div>
          <button
            className="user-logout-btn"
            onClick={() => logout()}
            title="Log out session"
          >
            Logout
          </button>
        </div>
      </div>

      {/* Switch / Create Org Modal */}
      <Modal
        isOpen={isOrgModalOpen}
        onClose={() => setIsOrgModalOpen(false)}
        title="Organization Tenant Context"
        subtitle="Manage and switch isolated multi-tenant organization boundaries"
      >
        <div className="org-modal-content">
          <div className="org-list-section">
            <h4 className="section-label">SELECT ACTIVE TENANT</h4>
            <div className="org-options-list">
              {organizations.map((org) => {
                const isSelected = org.id === currentOrg?.id;
                return (
                  <div
                    key={org.id}
                    className={`org-option-card ${isSelected ? 'org-option-selected' : ''}`}
                    onClick={() => {
                      setCurrentOrg(org);
                      setIsOrgModalOpen(false);
                    }}
                  >
                    <div>
                      <div className="org-card-title">{org.name}</div>
                      <div className="org-card-slug">{org.slug} • ID: {org.id.slice(0, 8)}...</div>
                    </div>
                    {isSelected && (
                      <span className="active-tag">ACTIVE</span>
                    )}
                  </div>
                );
              })}
            </div>
          </div>

          <div className="org-create-divider">
            <span>OR CREATE NEW TENANT</span>
          </div>

          <form onSubmit={handleCreateOrg} className="org-create-form">
            <div className="form-group">
              <label className="form-label">Organization Name</label>
              <input
                type="text"
                className="form-input"
                placeholder="e.g. Acme Cyber Systems"
                value={newOrgName}
                onChange={(e) => setNewOrgName(e.target.value)}
                required
              />
            </div>
            <Button
              type="submit"
              variant="primary"
              size="md"
              loading={isCreatingOrg}
              icon={<PlusIcon size={16} />}
            >
              Create Organization
            </Button>
          </form>
        </div>
      </Modal>
    </header>
  );
};
