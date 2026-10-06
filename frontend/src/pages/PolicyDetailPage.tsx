import React, { useState, useEffect } from 'react';
import { useOrg } from '../context/OrgContext';
import { policiesApi } from '../api/policies';
import { Policy, PolicyRule, PolicyVersion } from '../types';
import { SurfaceCard } from '../components/common/Card';
import { StatusBadge } from '../components/common/Badges';
import { LoadingState, ErrorState, EmptyState } from '../components/common/FeedbackStates';
import { Button } from '../components/common/Button';
import { Modal } from '../components/common/Modal';
import { CodeView } from '../components/common/CodeView';
import { Link } from '../router/Router';
import { PlusIcon, ScaleIcon } from '../components/common/Icons';

export const PolicyDetailPage: React.FC<{ policyId?: string }> = ({ policyId }) => {
  const { currentOrg } = useOrg();

  const [policy, setPolicy] = useState<Policy | null>(null);
  const [versions, setVersions] = useState<PolicyVersion[]>([]);
  const [selectedVersion, setSelectedVersion] = useState<PolicyVersion | null>(null);
  const [activeTab, setActiveTab] = useState<'rules' | 'json'>('rules');
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  // New Version Modal
  const [isVersionModalOpen, setIsVersionModalOpen] = useState(false);
  const [creatingVersion, setCreatingVersion] = useState(false);
  const [newRule, setNewRule] = useState<PolicyRule>({
    name: 'Rule 1',
    effect: 'require_approval',
    conditions: [{ field: 'action.amount', operator: 'gt', value: 5000 }],
  });

  const loadPolicyData = async () => {
    if (!currentOrg || !policyId) return;
    setLoading(true);
    setError(null);
    try {
      const [policyData, versionsData] = await Promise.all([
        policiesApi.get(currentOrg.id, policyId),
        policiesApi.listVersions(currentOrg.id, policyId).catch(() => ({ items: [], total: 0 })),
      ]);
      setPolicy(policyData);
      setVersions(versionsData.items || []);

      // Select active published version by default, or the latest version
      if (versionsData.items?.length > 0) {
        const published = versionsData.items.find((v) => v.status === 'published');
        setSelectedVersion(published || versionsData.items[0]);
      }
    } catch (err: any) {
      setError(err.message || 'Failed to load policy versions.');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadPolicyData();
  }, [currentOrg, policyId]);

  const handlePublish = async (versionId: string) => {
    if (!currentOrg || !policy) return;
    if (!window.confirm('Publish this policy version? It will immediately take effect and retire any previous version.')) return;
    try {
      await policiesApi.publishVersion(currentOrg.id, policy.id, versionId);
      await loadPolicyData();
    } catch (err: any) {
      alert(`Error publishing version: ${err.message}`);
    }
  };

  const handleRetire = async (versionId: string) => {
    if (!currentOrg || !policy) return;
    try {
      await policiesApi.retireVersion(currentOrg.id, policy.id, versionId);
      await loadPolicyData();
    } catch (err: any) {
      alert(`Error retiring version: ${err.message}`);
    }
  };

  const handleCreateVersion = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!currentOrg || !policy) return;
    setCreatingVersion(true);
    try {
      await policiesApi.createVersion(currentOrg.id, policy.id, {
        rules: [newRule],
      });
      setIsVersionModalOpen(false);
      await loadPolicyData();
    } catch (err: any) {
      alert(`Error drafting policy version: ${err.message}`);
    } finally {
      setCreatingVersion(false);
    }
  };

  if (loading) return <LoadingState message="Loading policy specification and rule versions..." />;
  if (error || !policy) return <ErrorState message={error || 'Policy not found'} onRetry={loadPolicyData} />;

  return (
    <div className="policy-detail-page">
      <div style={{ marginBottom: '16px' }}>
        <Link to="/policies" style={{ color: 'var(--text-muted)', textDecoration: 'none', fontSize: '13px' }}>
          ← Back to Policy Registry
        </Link>
      </div>

      {/* Policy Profile */}
      <SurfaceCard>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', flexWrap: 'wrap', gap: '16px' }}>
          <div>
            <div style={{ display: 'flex', alignItems: 'center', gap: '12px', marginBottom: '8px' }}>
              <div className="brand-shield-glow">
                <ScaleIcon size={24} />
              </div>
              <div>
                <h2 style={{ fontSize: '20px', fontWeight: 700 }}>{policy.name}</h2>
                <div style={{ display: 'flex', alignItems: 'center', gap: '8px', marginTop: '4px' }}>
                  <span className="font-mono text-muted" style={{ fontSize: '12px' }}>{policy.slug}</span>
                  <span className={`badge ${policy.enforcement_mode === 'enforce' ? 'badge-status-danger' : 'badge-status-warning'}`}>
                    MODE: {policy.enforcement_mode.toUpperCase()}
                  </span>
                  <StatusBadge status={policy.status} />
                </div>
              </div>
            </div>
            <p className="text-muted" style={{ fontSize: '13px', maxWidth: '650px', marginTop: '8px' }}>
              {policy.description || 'No description provided.'}
            </p>
          </div>

          <Button
            variant="primary"
            size="sm"
            icon={<PlusIcon size={14} />}
            onClick={() => setIsVersionModalOpen(true)}
          >
            Draft New Version
          </Button>
        </div>
      </SurfaceCard>

      {/* Versions & Rules */}
      <div className="grid-2">
        {/* Version Selector Column */}
        <SurfaceCard title="Version History">
          {versions.length === 0 ? (
            <EmptyState
              title="No Versions Yet"
              description="Create a draft version with evaluation rules."
              action={
                <Button variant="primary" size="sm" onClick={() => setIsVersionModalOpen(true)}>
                  Create Version 1
                </Button>
              }
            />
          ) : (
            <div className="versions-list" style={{ display: 'flex', flexDirection: 'column', gap: '10px' }}>
              {versions.map((ver) => {
                const isSelected = selectedVersion?.id === ver.id;
                return (
                  <div
                    key={ver.id}
                    onClick={() => setSelectedVersion(ver)}
                    style={{
                      padding: '12px 16px',
                      borderRadius: 'var(--radius-md)',
                      backgroundColor: isSelected ? 'var(--bg-elevated)' : 'var(--bg-card)',
                      border: `1px solid ${isSelected ? 'var(--color-cyan)' : 'var(--border-subtle)'}`,
                      cursor: 'pointer',
                      display: 'flex',
                      alignItems: 'center',
                      justifyContent: 'space-between',
                    }}
                  >
                    <div>
                      <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                        <strong>Version {ver.version_number}</strong>
                        <StatusBadge status={ver.status} size="sm" />
                      </div>
                      <div className="text-muted" style={{ fontSize: '11px', marginTop: '4px' }}>
                        {ver.rules?.length || 0} rule(s) • Created {new Date(ver.created_at).toLocaleDateString()}
                      </div>
                    </div>

                    <div style={{ display: 'flex', gap: '6px' }}>
                      {ver.status === 'draft' && (
                        <Button
                          variant="success"
                          size="sm"
                          onClick={(e) => {
                            e.stopPropagation();
                            handlePublish(ver.id);
                          }}
                        >
                          Publish
                        </Button>
                      )}
                      {ver.status === 'published' && (
                        <Button
                          variant="ghost"
                          size="sm"
                          onClick={(e) => {
                            e.stopPropagation();
                            handleRetire(ver.id);
                          }}
                          style={{ color: 'var(--color-amber)' }}
                        >
                          Retire
                        </Button>
                      )}
                    </div>
                  </div>
                );
              })}
            </div>
          )}
        </SurfaceCard>

        {/* Selected Version Rule Viewer Column */}
        <SurfaceCard
          title={selectedVersion ? `Version ${selectedVersion.version_number} Rules` : 'Rule Specification'}
          subtitle={selectedVersion?.status === 'published' ? 'Active published enforcement rules' : 'Draft / Historical rule set'}
          actions={
            <div style={{ display: 'flex', gap: '4px' }}>
              <button
                className={`btn btn-sm ${activeTab === 'rules' ? 'btn-secondary' : 'btn-ghost'}`}
                onClick={() => setActiveTab('rules')}
              >
                Visual Rules
              </button>
              <button
                className={`btn btn-sm ${activeTab === 'json' ? 'btn-secondary' : 'btn-ghost'}`}
                onClick={() => setActiveTab('json')}
              >
                Raw JSON
              </button>
            </div>
          }
        >
          {!selectedVersion ? (
            <div className="text-muted">Select a version on the left to inspect its rules.</div>
          ) : activeTab === 'json' ? (
            <CodeView data={selectedVersion.rules} label="POLICY VERSION RULES JSON" />
          ) : selectedVersion.rules.length === 0 ? (
            <div className="text-muted">No rules in this version.</div>
          ) : (
            <div className="structured-rules-list" style={{ display: 'flex', flexDirection: 'column', gap: '16px' }}>
              {selectedVersion.rules.map((rule, idx) => (
                <div
                  key={idx}
                  style={{
                    backgroundColor: 'var(--bg-card)',
                    border: '1px solid var(--border-subtle)',
                    borderRadius: 'var(--radius-md)',
                    padding: '16px',
                  }}
                >
                  <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '12px' }}>
                    <strong style={{ fontSize: '14px' }}>{rule.name || `Rule #${idx + 1}`}</strong>
                    <span className={`badge ${rule.effect === 'deny' ? 'badge-status-danger' : rule.effect === 'require_approval' ? 'badge-status-warning' : 'badge-status-success'}`}>
                      EFFECT: {rule.effect.toUpperCase()}
                    </span>
                  </div>

                  <div style={{ fontSize: '12px', marginBottom: '6px', fontWeight: 600, color: 'var(--text-muted)' }}>
                    IF ALL CONDITIONS MATCH:
                  </div>

                  <div style={{ display: 'flex', flexDirection: 'column', gap: '6px', marginBottom: '12px' }}>
                    {rule.conditions?.map((c, cIdx) => (
                      <div
                        key={cIdx}
                        style={{
                          backgroundColor: 'var(--bg-elevated)',
                          padding: '6px 10px',
                          borderRadius: 'var(--radius-sm)',
                          fontFamily: 'var(--font-mono)',
                          fontSize: '12px',
                          display: 'flex',
                          alignItems: 'center',
                          gap: '8px',
                        }}
                      >
                        <span className="text-cyan">{c.field}</span>
                        <span className="text-muted">{c.operator}</span>
                        <span style={{ color: '#10b981' }}>{JSON.stringify(c.value)}</span>
                      </div>
                    ))}
                  </div>

                  <div style={{ fontSize: '12px', fontWeight: 600, color: 'var(--text-muted)' }}>
                    THEN RESOLVE ACTION DISPOSITION AS:
                  </div>
                  <div style={{ marginTop: '4px', fontWeight: 700, color: rule.effect === 'deny' ? 'var(--color-rose)' : 'var(--color-amber)' }}>
                    ↳ {rule.effect.toUpperCase()}
                  </div>
                </div>
              ))}
            </div>
          )}
        </SurfaceCard>
      </div>

      {/* Draft Version Modal */}
      <Modal
        isOpen={isVersionModalOpen}
        onClose={() => setIsVersionModalOpen(false)}
        title="Draft Policy Version"
        subtitle="Specify conditions and disposition effect"
      >
        <form onSubmit={handleCreateVersion}>
          <div className="form-group">
            <label className="form-label">Rule Name</label>
            <input
              type="text"
              className="form-input"
              value={newRule.name}
              onChange={(e) => setNewRule({ ...newRule, name: e.target.value })}
              required
            />
          </div>

          <div className="form-group">
            <label className="form-label">Condition Field</label>
            <select
              className="form-select"
              value={newRule.conditions[0]?.field}
              onChange={(e) =>
                setNewRule({
                  ...newRule,
                  conditions: [{ ...newRule.conditions[0], field: e.target.value }],
                })
              }
            >
              <option value="action.amount">action.amount (Transaction Value)</option>
              <option value="agent.environment">agent.environment (development / staging / production)</option>
              <option value="operation.risk_level">operation.risk_level (low / medium / high / critical)</option>
              <option value="operation.type">operation.type (read / write / execute / delete)</option>
              <option value="action.resource">action.resource (Target resource string)</option>
            </select>
          </div>

          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '12px' }}>
            <div className="form-group">
              <label className="form-label">Operator</label>
              <select
                className="form-select"
                value={newRule.conditions[0]?.operator}
                onChange={(e) =>
                  setNewRule({
                    ...newRule,
                    conditions: [{ ...newRule.conditions[0], operator: e.target.value }],
                  })
                }
              >
                <option value="gt">&gt; (Greater than)</option>
                <option value="gte">&ge; (Greater than or equal)</option>
                <option value="lt">&lt; (Less than)</option>
                <option value="eq">== (Equals)</option>
                <option value="neq">!= (Not equals)</option>
                <option value="contains">Contains substring</option>
              </select>
            </div>

            <div className="form-group">
              <label className="form-label">Condition Threshold Value</label>
              <input
                type="text"
                className="form-input"
                placeholder="e.g. 5000 or production"
                value={newRule.conditions[0]?.value}
                onChange={(e) => {
                  const val = e.target.value;
                  const num = Number(val);
                  setNewRule({
                    ...newRule,
                    conditions: [{ ...newRule.conditions[0], value: !isNaN(num) && val.trim() !== '' ? num : val }],
                  });
                }}
                required
              />
            </div>
          </div>

          <div className="form-group">
            <label className="form-label">Rule Effect</label>
            <select
              className="form-select"
              value={newRule.effect}
              onChange={(e) => setNewRule({ ...newRule, effect: e.target.value as any })}
            >
              <option value="require_approval">REQUIRE_APPROVAL (Escalate to Human Governance)</option>
              <option value="deny">DENY (Immediately block invocation)</option>
              <option value="allow">ALLOW (Explicitly permit)</option>
              <option value="audit">AUDIT (Log match without altering outcome)</option>
            </select>
          </div>

          <div className="modal-footer" style={{ margin: '-20px', marginTop: '20px' }}>
            <Button type="button" variant="outline" onClick={() => setIsVersionModalOpen(false)}>
              Cancel
            </Button>
            <Button type="submit" variant="primary" loading={creatingVersion}>
              Create Version
            </Button>
          </div>
        </form>
      </Modal>
    </div>
  );
};
