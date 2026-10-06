import React, { useEffect, useState } from 'react';
import { useOrg } from '../context/OrgContext';
import { llmApi } from '../api/llm';
import { LLMInteraction } from '../types';
import { Link, useParams } from '../router/Router';
import { Card } from '../components/common/Card';
import { Button } from '../components/common/Button';
import { LoadingState } from '../components/common/FeedbackStates';
import {
  ArrowLeftIcon,
  ShieldAlertIcon,
  ShieldCheckIcon,
  AlertTriangleIcon,
  TerminalIcon,
  CopyIcon,
  CheckIcon,
  ActivityIcon,
} from '../components/common/Icons';

export const LLMInteractionDetailPage: React.FC = () => {
  const { currentOrg } = useOrg();
  const { id } = useParams();
  const [interaction, setInteraction] = useState<LLMInteraction | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [copiedHash, setCopiedHash] = useState<string | null>(null);

  useEffect(() => {
    const fetchInteraction = async () => {
      if (!currentOrg || !id) return;
      try {
        setLoading(true);
        setError(null);
        const data = await llmApi.getInteraction(currentOrg.id, id);
        setInteraction(data);
      } catch (err: any) {
        setError(err?.message || 'Failed to fetch LLM interaction dossier.');
      } finally {
        setLoading(false);
      }
    };

    fetchInteraction();
  }, [currentOrg, id]);

  const copyToClipboard = (text: string, label: string) => {
    navigator.clipboard.writeText(text);
    setCopiedHash(label);
    setTimeout(() => setCopiedHash(null), 2000);
  };

  const getStatusBadge = (status: string) => {
    switch (status) {
      case 'completed':
        return <span className="badge badge-success text-sm px-3 py-1">Completed</span>;
      case 'blocked':
        return <span className="badge badge-critical text-sm px-3 py-1">Input Blocked</span>;
      case 'output_blocked':
        return <span className="badge badge-critical text-sm px-3 py-1">Output Blocked</span>;
      case 'pending_approval':
        return <span className="badge badge-warning text-sm px-3 py-1">Pending Human Approval</span>;
      case 'failed':
        return <span className="badge badge-neutral text-sm px-3 py-1">Execution Failed</span>;
      default:
        return <span className="badge badge-info text-sm px-3 py-1">{status}</span>;
    }
  };

  if (loading) {
    return <LoadingState message="Retrieving forensic interaction dossier..." />;
  }

  if (error || !interaction) {
    return (
      <div className="page-container">
        <Link to="/llm-security" className="inline-flex items-center gap-2 text-sm text-muted mb-4 hover:text-primary">
          <ArrowLeftIcon size={16} /> Back to LLM Gateway
        </Link>
        <Card className="p-8 text-center text-critical">
          <AlertTriangleIcon size={36} className="mx-auto mb-3" />
          <h2 className="text-lg font-bold mb-2">Interaction Not Found</h2>
          <p className="text-sm">{error || 'The requested LLM interaction could not be located in this organization.'}</p>
        </Card>
      </div>
    );
  }

  return (
    <div className="page-container">
      {/* Breadcrumb / Back Link */}
      <div className="mb-4">
        <Link to="/llm-security" className="inline-flex items-center gap-2 text-sm text-muted hover:text-primary">
          <ArrowLeftIcon size={16} /> Back to LLM Gateway
        </Link>
      </div>

      {/* Header Banner */}
      <div className="flex items-start justify-between mb-6 pb-4 border-b border-slate-800">
        <div>
          <div className="flex items-center gap-3 mb-2">
            <h1 className="text-2xl font-bold font-mono text-slate-100">
              Interaction {interaction.id}
            </h1>
            {getStatusBadge(interaction.status)}
          </div>
          <p className="text-sm text-muted flex items-center gap-4">
            <span>Provider: <strong className="text-slate-200">{interaction.provider}</strong></span>
            <span>•</span>
            <span>Model: <code className="text-slate-300 font-mono">{interaction.model}</code></span>
            <span>•</span>
            <span>Environment: <span className="badge badge-neutral">{interaction.environment}</span></span>
            <span>•</span>
            <span>Created: {new Date(interaction.created_at).toLocaleString()}</span>
          </p>
        </div>

        {interaction.runtime_action_id && (
          <Link to={`/actions/${interaction.runtime_action_id}`}>
            <Button variant="secondary" size="sm">
              View Associated Action
            </Button>
          </Link>
        )}
      </div>

      {/* Primary Grid */}
      <div className="grid grid-cols-3 gap-6 mb-6">
        {/* Left Column (2 spans): Cryptographic Hash & Content Previews */}
        <div className="col-span-2 space-y-6">
          {/* Cryptographic Integrity Section */}
          <Card className="p-5">
            <h2 className="text-sm font-semibold uppercase tracking-wider text-muted mb-4 flex items-center gap-2">
              <ShieldCheckIcon size={16} className="text-primary" />
              Cryptographic Integrity & SHA-256 Hashes
            </h2>
            <div className="space-y-3 font-mono text-xs">
              <div className="p-3 bg-slate-950 rounded border border-slate-800 flex items-center justify-between">
                <div>
                  <div className="text-muted text-[10px] uppercase font-bold tracking-wider mb-1">
                    Input Content SHA-256 Hash
                  </div>
                  <div className="text-cyan-400 break-all">{interaction.input_hash}</div>
                </div>
                <Button
                  variant="ghost"
                  size="sm"
                  onClick={() => copyToClipboard(interaction.input_hash, 'input_hash')}
                  icon={copiedHash === 'input_hash' ? <CheckIcon size={14} /> : <CopyIcon size={14} />}
                >
                  {copiedHash === 'input_hash' ? 'Copied' : 'Copy'}
                </Button>
              </div>

              {interaction.output_hash && (
                <div className="p-3 bg-slate-950 rounded border border-slate-800 flex items-center justify-between">
                  <div>
                    <div className="text-muted text-[10px] uppercase font-bold tracking-wider mb-1">
                      Output Content SHA-256 Hash
                    </div>
                    <div className="text-purple-400 break-all">{interaction.output_hash}</div>
                  </div>
                  <Button
                    variant="ghost"
                    size="sm"
                    onClick={() => copyToClipboard(interaction.output_hash!, 'output_hash')}
                    icon={copiedHash === 'output_hash' ? <CheckIcon size={14} /> : <CopyIcon size={14} />}
                  >
                    {copiedHash === 'output_hash' ? 'Copied' : 'Copy'}
                  </Button>
                </div>
              )}
            </div>
          </Card>

          {/* Sanitized Content Previews */}
          <Card className="p-5">
            <h2 className="text-sm font-semibold uppercase tracking-wider text-muted mb-4 flex items-center gap-2">
              <TerminalIcon size={16} className="text-info" />
              Sanitized Previews (Zero Raw Data Storage)
            </h2>

            <div className="space-y-4">
              <div>
                <div className="flex items-center justify-between mb-1">
                  <span className="text-xs font-semibold text-slate-300">Prompt / Input Preview:</span>
                  <span className={`badge ${interaction.input_scan_status === 'flagged' ? 'badge-critical' : 'badge-neutral'}`}>
                    Scan: {interaction.input_scan_status.toUpperCase()}
                  </span>
                </div>
                <div className="p-3 bg-slate-950 rounded border border-slate-800 font-mono text-xs text-slate-300 whitespace-pre-wrap">
                  {interaction.sanitized_prompt_preview || 'No prompt preview available'}
                </div>
              </div>

              <div>
                <div className="flex items-center justify-between mb-1">
                  <span className="text-xs font-semibold text-slate-300">Model Output / Response Preview:</span>
                  <span className={`badge ${interaction.output_scan_status === 'flagged' || interaction.output_scan_status === 'blocked' ? 'badge-critical' : 'badge-neutral'}`}>
                    Scan: {interaction.output_scan_status.toUpperCase()}
                  </span>
                </div>
                {interaction.status === 'output_blocked' ? (
                  <div className="p-3 bg-red-950/40 rounded border border-red-500/40 text-xs text-red-300 font-mono">
                    [GATEWAY ENFORCEMENT: Model response blocked by CUSTODE output firewall due to credential or sensitive PII detection.]
                  </div>
                ) : (
                  <div className="p-3 bg-slate-950 rounded border border-slate-800 font-mono text-xs text-slate-300 whitespace-pre-wrap">
                    {interaction.sanitized_output_preview || (interaction.status === 'blocked' ? '[Request blocked before provider invocation]' : 'No output preview')}
                  </div>
                )}
              </div>
            </div>
          </Card>

          {/* Security Findings Detail */}
          {((interaction.input_findings && interaction.input_findings.length > 0) ||
            (interaction.output_findings && interaction.output_findings.length > 0)) && (
            <Card className="p-5">
              <h2 className="text-sm font-semibold uppercase tracking-wider text-muted mb-4 flex items-center gap-2">
                <ShieldAlertIcon size={16} className="text-critical" />
                Sentinel Security Findings ({((interaction.input_findings?.length || 0) + (interaction.output_findings?.length || 0))})
              </h2>

              <div className="space-y-3">
                {interaction.input_findings?.map((f) => (
                  <div key={f.id} className="p-3 bg-red-950/30 border border-red-800/40 rounded flex items-start justify-between">
                    <div>
                      <div className="flex items-center gap-2 mb-1">
                        <span className="badge badge-critical text-[10px]">INPUT: {f.severity}</span>
                        <span className="font-semibold text-sm text-slate-200">{f.title}</span>
                      </div>
                      <p className="text-xs text-slate-300 mb-1">{f.description}</p>
                      {f.remediation && (
                        <p className="text-xs text-amber-300/80">
                          <strong>Remediation:</strong> {f.remediation}
                        </p>
                      )}
                    </div>
                    <span className="text-[10px] font-mono text-muted uppercase">{f.scanner}</span>
                  </div>
                ))}

                {interaction.output_findings?.map((f) => (
                  <div key={f.id} className="p-3 bg-amber-950/30 border border-amber-800/40 rounded flex items-start justify-between">
                    <div>
                      <div className="flex items-center gap-2 mb-1">
                        <span className="badge badge-warning text-[10px]">OUTPUT: {f.severity}</span>
                        <span className="font-semibold text-sm text-slate-200">{f.title}</span>
                      </div>
                      <p className="text-xs text-slate-300 mb-1">{f.description}</p>
                      {f.remediation && (
                        <p className="text-xs text-amber-300/80">
                          <strong>Remediation:</strong> {f.remediation}
                        </p>
                      )}
                    </div>
                    <span className="text-[10px] font-mono text-muted uppercase">{f.scanner}</span>
                  </div>
                ))}
              </div>
            </Card>
          )}
        </div>

        {/* Right Column: Telemetry & Decision Metadata */}
        <div className="space-y-6">
          <Card className="p-5">
            <h2 className="text-sm font-semibold uppercase tracking-wider text-muted mb-4 flex items-center gap-2">
              <ActivityIcon size={16} className="text-info" />
              Token & Latency Accounting
            </h2>

            <div className="space-y-3">
              <div className="flex justify-between py-2 border-b border-slate-800 text-sm">
                <span className="text-muted">Prompt Tokens</span>
                <span className="font-mono font-semibold text-slate-200">{interaction.input_tokens.toLocaleString()}</span>
              </div>
              <div className="flex justify-between py-2 border-b border-slate-800 text-sm">
                <span className="text-muted">Completion Tokens</span>
                <span className="font-mono font-semibold text-slate-200">{interaction.output_tokens.toLocaleString()}</span>
              </div>
              <div className="flex justify-between py-2 border-b border-slate-800 text-sm font-bold">
                <span className="text-slate-300">Total Tokens</span>
                <span className="font-mono text-cyan-400">{interaction.total_tokens.toLocaleString()}</span>
              </div>
              <div className="flex justify-between py-2 border-b border-slate-800 text-sm">
                <span className="text-muted">End-to-End Latency</span>
                <span className="font-mono text-slate-200">
                  {interaction.latency_ms > 0 ? `${interaction.latency_ms.toFixed(1)} ms` : '—'}
                </span>
              </div>
            </div>
          </Card>

          <Card className="p-5">
            <h2 className="text-sm font-semibold uppercase tracking-wider text-muted mb-4">
              Security Evaluation
            </h2>

            <div className="space-y-3 text-sm">
              <div className="flex justify-between py-2 border-b border-slate-800">
                <span className="text-muted">Decision Engine</span>
                <span className={`badge ${interaction.decision === 'allow' ? 'badge-success' : 'badge-critical'}`}>
                  {interaction.decision?.toUpperCase() || 'UNKNOWN'}
                </span>
              </div>
              <div className="flex justify-between py-2 border-b border-slate-800">
                <span className="text-muted">Contextual Risk</span>
                <span className="font-mono font-bold">
                  {interaction.risk_score !== null && interaction.risk_score !== undefined
                    ? `${interaction.risk_score.toFixed(1)} (${interaction.risk_level?.toUpperCase()})`
                    : '—'}
                </span>
              </div>
              <div className="flex justify-between py-2 border-b border-slate-800">
                <span className="text-muted">Agent ID</span>
                <span className="font-mono text-xs text-muted truncate max-w-[140px]">{interaction.agent_id}</span>
              </div>
              {interaction.request_id && (
                <div className="flex justify-between py-2 text-sm">
                  <span className="text-muted">Correlation ID</span>
                  <span className="font-mono text-xs text-primary truncate max-w-[140px]">{interaction.request_id}</span>
                </div>
              )}
            </div>
          </Card>
        </div>
      </div>
    </div>
  );
};
export default LLMInteractionDetailPage;
