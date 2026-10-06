import React, { useState, useEffect, useCallback } from 'react';
import { useOrg } from '../context/OrgContext';
import { useAuth } from '../context/AuthContext';
import { integrationsApi } from '../api/integrations';
import {
  Integration,
  IntegrationCreate,
  IntegrationCreateResponse,
  SupportedEventsResponse,
  WebhookDelivery,
} from '../types';
import { LoadingState, EmptyState, ErrorState } from '../components/common/FeedbackStates';
import {
  ActivityIcon,
  AlertTriangleIcon,
  CheckCircleIcon,
  CopyIcon,
  PlayIcon,
  RefreshCwIcon,
  ShieldAlertIcon,
  ShieldCheckIcon,
  XCircleIcon,
} from '../components/common/Icons';

export const IntegrationsPage: React.FC = () => {
  const { currentOrg } = useOrg();
  const { user } = useAuth();

  const [integrations, setIntegrations] = useState<Integration[]>([]);
  const [loading, setLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);

  // Creation state
  const [showCreateModal, setShowCreateModal] = useState<boolean>(false);
  const [createName, setCreateName] = useState<string>('');
  const [createDescription, setCreateDescription] = useState<string>('');
  const [createUrl, setCreateUrl] = useState<string>('');
  const [createProvider, setCreateProvider] = useState<string>('webhook');
  const [createEvents, setCreateEvents] = useState<string[]>([
    'DECISION_CREATED',
    'APPROVAL_APPROVED',
    'SECURITY_FINDING_CREATED',
  ]);
  const [submitting, setSubmitting] = useState<boolean>(false);
  const [createError, setCreateError] = useState<string | null>(null);

  // One-time secret display modal
  const [createdSecretData, setCreatedSecretData] = useState<IntegrationCreateResponse | null>(null);
  const [secretCopied, setSecretCopied] = useState<boolean>(false);

  // Delivery drawer state
  const [selectedIntegration, setSelectedIntegration] = useState<Integration | null>(null);
  const [deliveries, setDeliveries] = useState<WebhookDelivery[]>([]);
  const [loadingDeliveries, setLoadingDeliveries] = useState<boolean>(false);
  const [deliveryDetail, setDeliveryDetail] = useState<WebhookDelivery | null>(null);
  const [retryingId, setRetryingId] = useState<string | null>(null);
  const [actionMessage, setActionMessage] = useState<string | null>(null);

  // Supported events
  const [supportedEvents, setSupportedEvents] = useState<SupportedEventsResponse | null>(null);

  const fetchIntegrations = useCallback(async () => {
    if (!currentOrg) return;
    try {
      setLoading(true);
      setError(null);
      const res = await integrationsApi.list(currentOrg.id);
      setIntegrations(res.items || []);
    } catch (err: any) {
      setError(err?.response?.data?.detail || err.message || 'Failed to load integrations');
    } finally {
      setLoading(false);
    }
  }, [currentOrg]);

  const fetchSupportedEvents = useCallback(async () => {
    if (!currentOrg) return;
    try {
      const res = await integrationsApi.getSupportedEvents(currentOrg.id);
      setSupportedEvents(res);
    } catch {
      // Non-blocking
    }
  }, [currentOrg]);

  useEffect(() => {
    fetchIntegrations();
    fetchSupportedEvents();
  }, [fetchIntegrations, fetchSupportedEvents]);

  const loadDeliveries = async (integration: Integration) => {
    if (!currentOrg) return;
    setSelectedIntegration(integration);
    setLoadingDeliveries(true);
    setDeliveryDetail(null);
    try {
      const res = await integrationsApi.listDeliveries(currentOrg.id, integration.id);
      setDeliveries(res.items || []);
    } catch (err: any) {
      setActionMessage(`Error loading deliveries: ${err.message}`);
    } finally {
      setLoadingDeliveries(false);
    }
  };

  const handleCreate = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!currentOrg) return;

    if (!createUrl.startsWith('https://')) {
      setCreateError('Production webhook endpoints must use secure HTTPS.');
      return;
    }
    if (createEvents.length === 0) {
      setCreateError('Please select at least one event type to subscribe.');
      return;
    }

    try {
      setSubmitting(true);
      setCreateError(null);
      const payload: IntegrationCreate = {
        name: createName.trim(),
        description: createDescription.trim() || undefined,
        provider: createProvider,
        url: createUrl.trim(),
        subscribed_events: createEvents,
      };
      const res = await integrationsApi.create(currentOrg.id, payload);
      setCreatedSecretData(res);
      setShowCreateModal(false);
      // Reset form
      setCreateName('');
      setCreateDescription('');
      setCreateUrl('');
      fetchIntegrations();
    } catch (err: any) {
      setCreateError(err?.response?.data?.detail || err.message || 'Failed to create integration');
    } finally {
      setSubmitting(false);
    }
  };

  const handleTestPing = async (integrationId: string) => {
    if (!currentOrg) return;
    try {
      setActionMessage('Sending signed diagnostic ping...');
      const res = await integrationsApi.testPing(currentOrg.id, integrationId);
      setActionMessage(`Diagnostic ping dispatched (Status: ${res.delivery_status.toUpperCase()})`);
      fetchIntegrations();
      if (selectedIntegration?.id === integrationId) {
        loadDeliveries(selectedIntegration);
      }
    } catch (err: any) {
      setActionMessage(`Test ping failed: ${err?.response?.data?.detail || err.message}`);
    }
  };

  const handleSuspend = async (integrationId: string) => {
    if (!currentOrg) return;
    try {
      await integrationsApi.suspend(currentOrg.id, integrationId);
      setActionMessage('Integration suspended.');
      fetchIntegrations();
    } catch (err: any) {
      setActionMessage(`Failed to suspend: ${err?.response?.data?.detail || err.message}`);
    }
  };

  const handleRevoke = async (integrationId: string) => {
    if (!currentOrg) return;
    if (!window.confirm('Are you sure you want to permanently revoke this integration? This action cannot be undone.')) {
      return;
    }
    try {
      await integrationsApi.revoke(currentOrg.id, integrationId);
      setActionMessage('Integration permanently revoked.');
      fetchIntegrations();
    } catch (err: any) {
      setActionMessage(`Failed to revoke: ${err?.response?.data?.detail || err.message}`);
    }
  };

  const handleRetryDelivery = async (deliveryId: string) => {
    if (!currentOrg || !selectedIntegration) return;
    try {
      setRetryingId(deliveryId);
      await integrationsApi.retryDelivery(currentOrg.id, selectedIntegration.id, deliveryId);
      setActionMessage('Delivery retry executed.');
      loadDeliveries(selectedIntegration);
    } catch (err: any) {
      setActionMessage(`Retry failed: ${err?.response?.data?.detail || err.message}`);
    } finally {
      setRetryingId(null);
    }
  };

  const toggleEventSubscription = (eventName: string) => {
    setCreateEvents((prev) =>
      prev.includes(eventName)
        ? prev.filter((e) => e !== eventName)
        : [...prev, eventName]
    );
  };

  const copyToClipboard = (text: string) => {
    navigator.clipboard.writeText(text);
    setSecretCopied(true);
    setTimeout(() => setSecretCopied(false), 2500);
  };

  return (
    <div className="page-container">
      {/* Top Header */}
      <div className="page-header">
        <div>
          <h1 className="page-title">External Integrations &amp; Webhooks</h1>
          <p className="page-subtitle">
            Cryptographically signed security event notifications dispatched to your external SIEM, ticketing, and automation pipelines.
          </p>
        </div>
        <div style={{ display: 'flex', gap: '0.75rem', alignItems: 'center' }}>
          <button className="btn btn-secondary" onClick={fetchIntegrations} disabled={loading}>
            <RefreshCwIcon size={16} /> Refresh
          </button>
          <button className="btn btn-primary" onClick={() => setShowCreateModal(true)}>
            + New Integration
          </button>
        </div>
      </div>

      {actionMessage && (
        <div className="info-banner" style={{ marginBottom: '1.25rem' }}>
          <ActivityIcon size={18} />
          <span style={{ flex: 1 }}>{actionMessage}</span>
          <button className="btn-icon" onClick={() => setActionMessage(null)}>✕</button>
        </div>
      )}

      {loading ? (
        <LoadingState message="Loading external integrations &amp; delivery topology..." />
      ) : error ? (
        <ErrorState message={error} onRetry={fetchIntegrations} />
      ) : integrations.length === 0 ? (
        <EmptyState
          title="No Integrations Configured"
          description="Connect external security workflows by creating your first HTTPS webhook destination with cryptographic HMAC-SHA256 signing."
          action={
            <button className="btn btn-primary" onClick={() => setShowCreateModal(true)}>
              + Create Webhook
            </button>
          }
        />
      ) : (
        <div className="data-table-container">
          <table className="data-table">
            <thead>
              <tr>
                <th>Integration</th>
                <th>Provider</th>
                <th>Status</th>
                <th>Target URL</th>
                <th>Subscribed Events</th>
                <th>Last Delivery</th>
                <th style={{ textAlign: 'right' }}>Actions</th>
              </tr>
            </thead>
            <tbody>
              {integrations.map((integ) => (
                <tr key={integ.id}>
                  <td>
                    <div style={{ fontWeight: 600, color: '#f1f5f9' }}>{integ.name}</div>
                    <div style={{ fontSize: '0.75rem', color: '#64748b' }}>
                      Prefix: <code>{integ.secret_prefix}</code>
                    </div>
                  </td>
                  <td>
                    <span className="badge badge-info" style={{ textTransform: 'uppercase' }}>
                      {integ.provider}
                    </span>
                  </td>
                  <td>
                    <span
                      className={`badge ${
                        integ.status === 'active'
                          ? 'badge-success'
                          : integ.status === 'suspended'
                          ? 'badge-warning'
                          : 'badge-danger'
                      }`}
                    >
                      {integ.status.toUpperCase()}
                    </span>
                  </td>
                  <td>
                    <code style={{ fontSize: '0.8rem', color: '#94a3b8' }}>
                      {integ.url.length > 38 ? `${integ.url.slice(0, 35)}...` : integ.url}
                    </code>
                  </td>
                  <td>
                    <span className="badge badge-neutral">
                      {integ.subscribed_events.includes('*')
                        ? 'All Events (*)'
                        : `${integ.subscribed_events.length} event types`}
                    </span>
                  </td>
                  <td style={{ fontSize: '0.8rem', color: '#94a3b8' }}>
                    {integ.last_delivery_at
                      ? new Date(integ.last_delivery_at).toLocaleString()
                      : 'Never'}
                  </td>
                  <td style={{ textAlign: 'right' }}>
                    <div style={{ display: 'flex', gap: '0.5rem', justifyContent: 'flex-end' }}>
                      <button
                        className="btn btn-sm btn-secondary"
                        onClick={() => loadDeliveries(integ)}
                        title="View delivery logs"
                      >
                        Deliveries
                      </button>
                      {integ.status === 'active' && (
                        <>
                          <button
                            className="btn btn-sm btn-secondary"
                            onClick={() => handleTestPing(integ.id)}
                            title="Send diagnostic test ping"
                          >
                            <PlayIcon size={14} /> Ping
                          </button>
                          <button
                            className="btn btn-sm btn-warning"
                            onClick={() => handleSuspend(integ.id)}
                            title="Pause deliveries"
                          >
                            Suspend
                          </button>
                        </>
                      )}
                      {integ.status !== 'revoked' && (
                        <button
                          className="btn btn-sm btn-danger"
                          onClick={() => handleRevoke(integ.id)}
                          title="Permanently revoke"
                        >
                          Revoke
                        </button>
                      )}
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {/* Creation Modal */}
      {showCreateModal && (
        <div className="modal-backdrop">
          <div className="modal-card" style={{ maxWidth: '650px' }}>
            <div className="modal-header">
              <h2 className="modal-title">New Webhook Integration</h2>
              <button className="btn-icon" onClick={() => setShowCreateModal(false)}>✕</button>
            </div>
            <form onSubmit={handleCreate}>
              <div className="modal-body">
                {createError && (
                  <div className="error-banner" style={{ marginBottom: '1rem' }}>
                    <AlertTriangleIcon size={18} />
                    <span>{createError}</span>
                  </div>
                )}
                <div className="form-group">
                  <label className="form-label">Integration Name *</label>
                  <input
                    type="text"
                    className="form-input"
                    placeholder="e.g. Splunk SOAR / PagerDuty / Automation"
                    value={createName}
                    onChange={(e) => setCreateName(e.target.value)}
                    required
                  />
                </div>
                <div className="form-group">
                  <label className="form-label">Description</label>
                  <input
                    type="text"
                    className="form-input"
                    placeholder="Optional description of subscriber system"
                    value={createDescription}
                    onChange={(e) => setCreateDescription(e.target.value)}
                  />
                </div>
                <div className="form-row" style={{ display: 'grid', gridTemplateColumns: '1fr 2fr', gap: '1rem' }}>
                  <div className="form-group">
                    <label className="form-label">Provider</label>
                    <select
                      className="form-input"
                      value={createProvider}
                      onChange={(e) => setCreateProvider(e.target.value)}
                    >
                      <option value="webhook">Generic Webhook (HTTPS)</option>
                      <option value="slack">Slack Incoming Webhook</option>
                    </select>
                  </div>
                  <div className="form-group">
                    <label className="form-label">Destination URL (HTTPS Only) *</label>
                    <input
                      type="url"
                      className="form-input"
                      placeholder="https://api.yourdomain.com/webhooks/custode"
                      value={createUrl}
                      onChange={(e) => setCreateUrl(e.target.value)}
                      required
                    />
                  </div>
                </div>

                <div className="form-group">
                  <label className="form-label">Subscribed Security Event Categories</label>
                  <div
                    style={{
                      maxHeight: '180px',
                      overflowY: 'auto',
                      border: '1px solid #1e293b',
                      borderRadius: '6px',
                      padding: '0.75rem',
                      backgroundColor: '#0a0f1d',
                    }}
                  >
                    {supportedEvents ? (
                      Object.entries(supportedEvents.taxonomy).map(([catKey, catVal]) => (
                        <div key={catKey} style={{ marginBottom: '0.75rem' }}>
                          <div style={{ fontSize: '0.75rem', fontWeight: 600, color: '#38bdf8', marginBottom: '0.25rem' }}>
                            {catKey} — {catVal.description}
                          </div>
                          <div style={{ display: 'flex', flexWrap: 'wrap', gap: '0.5rem' }}>
                            {catVal.events.map((evt) => {
                              const checked = createEvents.includes(evt);
                              return (
                                <button
                                  type="button"
                                  key={evt}
                                  onClick={() => toggleEventSubscription(evt)}
                                  className={`badge ${checked ? 'badge-primary' : 'badge-neutral'}`}
                                  style={{ cursor: 'pointer', border: 'none', padding: '0.25rem 0.5rem' }}
                                >
                                  {checked ? '✓ ' : '+ '}
                                  {evt}
                                </button>
                              );
                            })}
                          </div>
                        </div>
                      ))
                    ) : (
                      <div style={{ color: '#64748b', fontSize: '0.85rem' }}>Loading event catalog...</div>
                    )}
                  </div>
                </div>
              </div>
              <div className="modal-footer">
                <button
                  type="button"
                  className="btn btn-secondary"
                  onClick={() => setShowCreateModal(false)}
                  disabled={submitting}
                >
                  Cancel
                </button>
                <button type="submit" className="btn btn-primary" disabled={submitting}>
                  {submitting ? 'Generating Secret...' : 'Create Integration'}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* Secret Shown Once Modal */}
      {createdSecretData && (
        <div className="modal-backdrop">
          <div className="modal-card" style={{ maxWidth: '600px', border: '1px solid #f59e0b' }}>
            <div className="modal-header">
              <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
                <ShieldAlertIcon size={24} />
                <h2 className="modal-title" style={{ color: '#f59e0b' }}>
                  Save Webhook Signing Secret
                </h2>
              </div>
            </div>
            <div className="modal-body">
              <div className="error-banner" style={{ backgroundColor: '#78350f22', borderColor: '#f59e0b', color: '#fbbf24', marginBottom: '1.25rem' }}>
                <AlertTriangleIcon size={20} />
                <div>
                  <strong>{createdSecretData.warning}</strong>
                  <div style={{ fontSize: '0.85rem', marginTop: '0.25rem' }}>
                    For security, CUSTODE never displays this raw secret again. Store it immediately in your receiving service's environment configuration.
                  </div>
                </div>
              </div>

              <div className="form-group">
                <label className="form-label">Signing Secret (HMAC-SHA256)</label>
                <div style={{ display: 'flex', gap: '0.5rem' }}>
                  <input
                    type="text"
                    readOnly
                    className="form-input"
                    style={{ fontFamily: 'monospace', fontWeight: 600, color: '#38bdf8' }}
                    value={createdSecretData.signing_secret}
                  />
                  <button
                    type="button"
                    className="btn btn-secondary"
                    onClick={() => copyToClipboard(createdSecretData.signing_secret)}
                  >
                    {secretCopied ? 'Copied!' : <CopyIcon size={16} />}
                  </button>
                </div>
              </div>

              <div style={{ fontSize: '0.8rem', color: '#94a3b8', lineHeight: 1.5 }}>
                <p>
                  <strong>Verification Header:</strong> <code>X-Custode-Signature: t=&lt;timestamp&gt;,v1=&lt;sig&gt;</code>
                </p>
                <p>
                  Use constant-time HMAC comparison with this secret to authenticate payloads and reject replays.
                </p>
              </div>
            </div>
            <div className="modal-footer">
              <button
                type="button"
                className="btn btn-primary"
                onClick={() => setCreatedSecretData(null)}
              >
                I Have Safely Saved This Secret
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Deliveries Drawer / Modal */}
      {selectedIntegration && (
        <div className="modal-backdrop">
          <div className="modal-card" style={{ maxWidth: '850px', maxHeight: '85vh', display: 'flex', flexDirection: 'column' }}>
            <div className="modal-header">
              <div>
                <h2 className="modal-title">Delivery Logs: {selectedIntegration.name}</h2>
                <div style={{ fontSize: '0.8rem', color: '#64748b' }}>
                  Destination: <code>{selectedIntegration.url}</code>
                </div>
              </div>
              <button className="btn-icon" onClick={() => setSelectedIntegration(null)}>✕</button>
            </div>

            <div className="modal-body" style={{ flex: 1, overflowY: 'auto' }}>
              {loadingDeliveries ? (
                <LoadingState message="Fetching recent deliveries and attempt history..." />
              ) : deliveries.length === 0 ? (
                <EmptyState
                  title="No Deliveries Yet"
                  description="No security events have been dispatched to this webhook endpoint yet. You can send a test ping to verify connectivity."
                  action={
                    <button className="btn btn-secondary" onClick={() => handleTestPing(selectedIntegration.id)}>
                      Send Test Ping
                    </button>
                  }
                />
              ) : (
                <div style={{ display: 'grid', gridTemplateColumns: deliveryDetail ? '1fr 1fr' : '1fr', gap: '1rem' }}>
                  {/* Delivery Table */}
                  <div className="data-table-container" style={{ maxHeight: '420px', overflowY: 'auto' }}>
                    <table className="data-table">
                      <thead>
                        <tr>
                          <th>Event</th>
                          <th>Status</th>
                          <th>HTTP Code</th>
                          <th>Attempts</th>
                          <th>Time</th>
                          <th>Action</th>
                        </tr>
                      </thead>
                      <tbody>
                        {deliveries.map((deliv) => (
                          <tr
                            key={deliv.id}
                            style={{
                              cursor: 'pointer',
                              backgroundColor: deliveryDetail?.id === deliv.id ? '#1e293b' : undefined,
                            }}
                            onClick={() => setDeliveryDetail(deliv)}
                          >
                            <td>
                              <span style={{ fontWeight: 600, fontSize: '0.8rem', color: '#f1f5f9' }}>
                                {deliv.event_type}
                              </span>
                            </td>
                            <td>
                              <span
                                className={`badge ${
                                  deliv.delivery_status === 'delivered'
                                    ? 'badge-success'
                                    : deliv.delivery_status === 'retrying'
                                    ? 'badge-warning'
                                    : 'badge-danger'
                                }`}
                              >
                                {deliv.delivery_status.toUpperCase()}
                              </span>
                            </td>
                            <td>
                              <code>{deliv.response_status_code || '---'}</code>
                            </td>
                            <td>
                              {deliv.attempt_count} / {deliv.max_attempts}
                            </td>
                            <td style={{ fontSize: '0.75rem', color: '#94a3b8' }}>
                              {new Date(deliv.created_at).toLocaleTimeString()}
                            </td>
                            <td>
                              {deliv.delivery_status !== 'delivered' && (
                                <button
                                  className="btn btn-sm btn-secondary"
                                  onClick={(e) => {
                                    e.stopPropagation();
                                    handleRetryDelivery(deliv.id);
                                  }}
                                  disabled={retryingId === deliv.id}
                                >
                                  {retryingId === deliv.id ? 'Retrying...' : 'Retry'}
                                </button>
                              )}
                            </td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>

                  {/* Delivery Detail Panel */}
                  {deliveryDetail && (
                    <div
                      style={{
                        backgroundColor: '#0a0f1d',
                        border: '1px solid #1e293b',
                        borderRadius: '6px',
                        padding: '1rem',
                        maxHeight: '420px',
                        overflowY: 'auto',
                      }}
                    >
                      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '0.75rem' }}>
                        <h3 style={{ margin: 0, fontSize: '0.95rem', color: '#38bdf8' }}>Delivery Detail</h3>
                        <button className="btn-icon" onClick={() => setDeliveryDetail(null)}>✕</button>
                      </div>

                      <div style={{ fontSize: '0.8rem', color: '#cbd5e1', marginBottom: '0.5rem' }}>
                        <strong>ID:</strong> <code>{deliveryDetail.id}</code>
                      </div>
                      <div style={{ fontSize: '0.8rem', color: '#cbd5e1', marginBottom: '0.5rem' }}>
                        <strong>Request Correlation:</strong> <code>{deliveryDetail.request_id || 'N/A'}</code>
                      </div>
                      <div style={{ fontSize: '0.8rem', color: '#cbd5e1', marginBottom: '0.5rem' }}>
                        <strong>Summary:</strong> {deliveryDetail.sanitized_response_summary || 'N/A'}
                      </div>

                      <div style={{ marginTop: '0.75rem' }}>
                        <strong style={{ fontSize: '0.8rem', color: '#94a3b8' }}>Payload (Sanitized):</strong>
                        <pre
                          style={{
                            backgroundColor: '#030712',
                            padding: '0.5rem',
                            borderRadius: '4px',
                            fontSize: '0.75rem',
                            color: '#a7f3d0',
                            overflowX: 'auto',
                            maxHeight: '160px',
                          }}
                        >
                          {JSON.stringify(deliveryDetail.payload, null, 2)}
                        </pre>
                      </div>

                      {deliveryDetail.delivery_status !== 'delivered' && (
                        <div style={{ marginTop: '0.75rem', display: 'flex', justifyContent: 'flex-end' }}>
                          <button
                            className="btn btn-sm btn-primary"
                            onClick={() => handleRetryDelivery(deliveryDetail.id)}
                            disabled={retryingId === deliveryDetail.id}
                          >
                            {retryingId === deliveryDetail.id ? 'Retrying...' : 'Manual Retry'}
                          </button>
                        </div>
                      )}
                    </div>
                  )}
                </div>
              )}
            </div>

            <div className="modal-footer">
              <button className="btn btn-secondary" onClick={() => setSelectedIntegration(null)}>
                Close
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};

export default IntegrationsPage;
