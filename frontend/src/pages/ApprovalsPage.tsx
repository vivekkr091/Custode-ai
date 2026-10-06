import React, { useEffect, useState } from 'react';
import { useOrg } from '../context/OrgContext';
import { listApprovals, approveRequest, rejectRequest } from '../api';
import { ApprovalRequest } from '../types';
import { MetricCard, SurfaceCard } from '../components/common/Card';
import { StatusBadge } from '../components/common/Badges';
import { Button } from '../components/common/Button';
import { Modal } from '../components/common/Modal';
import { CodeView } from '../components/common/CodeView';
import { LoadingState, EmptyState } from '../components/common/FeedbackStates';
import {
  ClockIcon,
  CheckCircleIcon,
  XCircleIcon,
  FilterIcon,
  ShieldAlertIcon,
  ArrowRightIcon,
} from '../components/common/Icons';
import { navigate } from '../router/Router';

export const ApprovalsPage: React.FC = () => {
  const { activeOrg, pendingApprovalsCount, refreshPendingApprovals } = useOrg();
  const [approvals, setApprovals] = useState<ApprovalRequest[]>([]);
  const [loading, setLoading] = useState(true);

  // Tab filter
  const [activeTab, setActiveTab] = useState<'pending' | 'approved' | 'rejected' | 'expired'>('pending');

  // Modal states
  const [selectedApproval, setSelectedApproval] = useState<ApprovalRequest | null>(null);
  const [approveModalOpen, setApproveModalOpen] = useState(false);
  const [rejectModalOpen, setRejectModalOpen] = useState(false);
  const [detailsModalOpen, setDetailsModalOpen] = useState(false);

  const [reviewerNote, setReviewerNote] = useState('');
  const [rejectionReason, setRejectionReason] = useState('');
  const [submitting, setSubmitting] = useState(false);

  const fetchAllApprovals = async () => {
    if (!activeOrg) return;
    try {
      setLoading(true);
      const data = await listApprovals(activeOrg.id);
      setApprovals(data);
      refreshPendingApprovals();
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchAllApprovals();
  }, [activeOrg?.id]);

  const handleApprove = async () => {
    if (!activeOrg || !selectedApproval) return;
    try {
      setSubmitting(true);
      await approveRequest(activeOrg.id, selectedApproval.id, {
        reviewer_note: reviewerNote || undefined,
      });
      setApproveModalOpen(false);
      setReviewerNote('');
      setSelectedApproval(null);
      await fetchAllApprovals();
    } catch (err: any) {
      alert(`Approval failed: ${err.message}`);
    } finally {
      setSubmitting(false);
    }
  };

  const handleReject = async () => {
    if (!activeOrg || !selectedApproval) return;
    if (!rejectionReason.trim()) {
      alert('Rejection reason is required.');
      return;
    }
    try {
      setSubmitting(true);
      await rejectRequest(activeOrg.id, selectedApproval.id, {
        rejection_reason: rejectionReason,
      });
      setRejectModalOpen(false);
      setRejectionReason('');
      setSelectedApproval(null);
      await fetchAllApprovals();
    } catch (err: any) {
      alert(`Rejection failed: ${err.message}`);
    } finally {
      setSubmitting(false);
    }
  };

  const filteredApprovals = approvals.filter((a) => {
    return a.status.toLowerCase() === activeTab;
  });

  const pendingCount = approvals.filter((a) => a.status.toLowerCase() === 'pending').length;
  const approvedCount = approvals.filter((a) => a.status.toLowerCase() === 'approved').length;
  const rejectedCount = approvals.filter((a) => a.status.toLowerCase() === 'rejected').length;
  const expiredCount = approvals.filter((a) => a.status.toLowerCase() === 'expired').length;

  return (
    <div className="space-y-6">
      {/* Top Banner */}
      <div>
        <h1 className="text-2xl font-bold font-mono tracking-tight text-text-primary">
          Human Governance Inbox
        </h1>
        <p className="text-xs text-text-secondary mt-1">
          Review, approve, or reject high-risk agent operations escalated by authorization policies.
        </p>
      </div>

      {/* Metrics */}
      <div className="grid grid-cols-2 sm:grid-cols-4 gap-4">
        <MetricCard
          title="Pending Queue"
          value={pendingCount}
          subtitle="Awaiting security officer review"
          variant="warning"
          icon={<ClockIcon className="w-5 h-5 text-warning" />}
        />
        <MetricCard
          title="Approved"
          value={approvedCount}
          subtitle="Granted human authorization"
          variant="success"
          icon={<CheckCircleIcon className="w-5 h-5 text-success" />}
        />
        <MetricCard
          title="Rejected"
          value={rejectedCount}
          subtitle="Denied by reviewer"
          variant="danger"
          icon={<XCircleIcon className="w-5 h-5 text-danger" />}
        />
        <MetricCard
          title="Expired"
          value={expiredCount}
          subtitle="Timed out without review"
          variant="default"
          icon={<ShieldAlertIcon className="w-5 h-5 text-text-muted" />}
        />
      </div>

      {/* Filter Tabs */}
      <div className="flex items-center gap-2 border-b border-border-subtle pb-2">
        <span className="text-xs text-text-tertiary flex items-center gap-1 mr-2">
          <FilterIcon className="w-3.5 h-3.5" />
          Status Filter:
        </span>
        {(['pending', 'approved', 'rejected', 'expired'] as const).map((tab) => (
          <button
            key={tab}
            onClick={() => setActiveTab(tab)}
            className={`px-3 py-1 text-xs font-mono rounded transition-colors ${
              activeTab === tab
                ? 'bg-accent-primary/20 text-accent-primary border border-accent-primary/40'
                : 'text-text-secondary hover:text-text-primary'
            }`}
          >
            {tab.toUpperCase()}{' '}
            <span className="text-[10px] opacity-75">
              (
              {tab === 'pending'
                ? pendingCount
                : tab === 'approved'
                ? approvedCount
                : tab === 'rejected'
                ? rejectedCount
                : expiredCount}
              )
            </span>
          </button>
        ))}
      </div>

      {/* Table */}
      <SurfaceCard title={`Approval Requests (${filteredApprovals.length})`}>
        {loading ? (
          <LoadingState message="Fetching approval queue..." />
        ) : filteredApprovals.length === 0 ? (
          <EmptyState
            title={`No ${activeTab} Approvals`}
            description={`There are currently no approval requests with status '${activeTab}'.`}
          />
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-left text-xs font-mono">
              <thead>
                <tr className="border-b border-border-subtle text-text-tertiary uppercase">
                  <th className="py-2.5 px-3">Approval ID</th>
                  <th className="py-2.5 px-3">Action ID</th>
                  <th className="py-2.5 px-3">Status</th>
                  <th className="py-2.5 px-3">Created At</th>
                  <th className="py-2.5 px-3">Expires At</th>
                  <th className="py-2.5 px-3">Resolution Details</th>
                  <th className="py-2.5 px-3 text-right">Actions</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-border-subtle text-text-secondary">
                {filteredApprovals.map((req) => (
                  <tr key={req.id} className="hover:bg-bg-tertiary/50">
                    <td className="py-2.5 px-3 font-semibold text-text-primary">
                      {req.id.slice(0, 8)}...
                    </td>
                    <td className="py-2.5 px-3 text-accent-primary">
                      <button
                        onClick={() => navigate(`/runtime-actions/${req.runtime_action_id}`)}
                        className="hover:underline flex items-center gap-1"
                      >
                        {req.runtime_action_id.slice(0, 8)}...
                        <ArrowRightIcon className="w-3 h-3" />
                      </button>
                    </td>
                    <td className="py-2.5 px-3">
                      <StatusBadge status={req.status} />
                    </td>
                    <td className="py-2.5 px-3 text-text-muted">
                      {new Date(req.created_at).toLocaleString()}
                    </td>
                    <td className="py-2.5 px-3 text-text-muted">
                      {req.expires_at ? new Date(req.expires_at).toLocaleString() : 'Never'}
                    </td>
                    <td className="py-2.5 px-3 max-w-xs truncate text-text-tertiary">
                      {req.status === 'approved' && req.reviewer_note ? (
                        <span className="text-success">Note: {req.reviewer_note}</span>
                      ) : req.status === 'rejected' && req.rejection_reason ? (
                        <span className="text-danger">Reason: {req.rejection_reason}</span>
                      ) : (
                        '-'
                      )}
                    </td>
                    <td className="py-2.5 px-3 text-right">
                      <div className="flex items-center justify-end gap-1.5">
                        <Button
                          variant="ghost"
                          size="sm"
                          onClick={() => {
                            setSelectedApproval(req);
                            setDetailsModalOpen(true);
                          }}
                        >
                          Details
                        </Button>

                        {req.status.toLowerCase() === 'pending' && (
                          <>
                            <Button
                              variant="danger"
                              size="sm"
                              onClick={() => {
                                setSelectedApproval(req);
                                setRejectionReason('');
                                setRejectModalOpen(true);
                              }}
                            >
                              Reject
                            </Button>
                            <Button
                              variant="primary"
                              size="sm"
                              onClick={() => {
                                setSelectedApproval(req);
                                setReviewerNote('');
                                setApproveModalOpen(true);
                              }}
                            >
                              Approve
                            </Button>
                          </>
                        )}
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </SurfaceCard>

      {/* Approve Modal */}
      <Modal
        isOpen={approveModalOpen}
        onClose={() => setApproveModalOpen(false)}
        title="Approve Runtime Action"
      >
        <div className="space-y-4">
          <p className="text-xs text-text-secondary">
            You are granting authoritative human approval for action{' '}
            <span className="font-mono text-text-primary">
              {selectedApproval?.runtime_action_id}
            </span>
            . This enables the action to transition to allowed status and be executed.
          </p>

          <div>
            <label className="block text-xs font-mono uppercase text-text-tertiary mb-1">
              Reviewer Note (Optional)
            </label>
            <textarea
              value={reviewerNote}
              onChange={(e) => setReviewerNote(e.target.value)}
              placeholder="e.g. Verified transaction amount with operations team."
              rows={3}
              className="w-full bg-bg-tertiary border border-border-default rounded px-3 py-2 text-xs font-mono text-text-primary focus:outline-none focus:border-accent-primary"
            />
          </div>

          <div className="flex justify-end gap-2 pt-2">
            <Button variant="ghost" onClick={() => setApproveModalOpen(false)}>
              Cancel
            </Button>
            <Button
              variant="primary"
              loading={submitting}
              onClick={handleApprove}
            >
              Confirm Approval
            </Button>
          </div>
        </div>
      </Modal>

      {/* Reject Modal */}
      <Modal
        isOpen={rejectModalOpen}
        onClose={() => setRejectModalOpen(false)}
        title="Reject Runtime Action"
      >
        <div className="space-y-4">
          <p className="text-xs text-text-secondary">
            You are rejecting action{' '}
            <span className="font-mono text-text-primary">
              {selectedApproval?.runtime_action_id}
            </span>
            . The action will be permanently blocked from execution.
          </p>

          <div>
            <label className="block text-xs font-mono uppercase text-text-tertiary mb-1">
              Rejection Reason (Required)
            </label>
            <textarea
              value={rejectionReason}
              onChange={(e) => setRejectionReason(e.target.value)}
              placeholder="e.g. Unverified destination account detected."
              rows={3}
              required
              className="w-full bg-bg-tertiary border border-border-default rounded px-3 py-2 text-xs font-mono text-text-primary focus:outline-none focus:border-danger"
            />
          </div>

          <div className="flex justify-end gap-2 pt-2">
            <Button variant="ghost" onClick={() => setRejectModalOpen(false)}>
              Cancel
            </Button>
            <Button
              variant="danger"
              loading={submitting}
              onClick={handleReject}
              disabled={!rejectionReason.trim()}
            >
              Confirm Rejection
            </Button>
          </div>
        </div>
      </Modal>

      {/* Details Modal */}
      <Modal
        isOpen={detailsModalOpen}
        onClose={() => setDetailsModalOpen(false)}
        title="Approval Request Details"
        size="lg"
      >
        {selectedApproval && (
          <div className="space-y-4">
            <div className="flex items-center justify-between pb-2 border-b border-border-subtle">
              <span className="text-xs font-mono text-text-secondary">Request ID:</span>
              <span className="text-xs font-mono font-semibold text-text-primary">
                {selectedApproval.id}
              </span>
            </div>
            <CodeView code={selectedApproval} language="json" maxHeight="300px" />
            <div className="flex justify-end pt-2">
              <Button variant="secondary" onClick={() => setDetailsModalOpen(false)}>
                Close
              </Button>
            </div>
          </div>
        )}
      </Modal>
    </div>
  );
};
