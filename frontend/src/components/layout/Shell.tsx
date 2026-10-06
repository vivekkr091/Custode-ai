import React, { useState, useEffect } from 'react';
import { Sidebar } from './Sidebar';
import { Header } from './Header';
import { useOrg } from '../../context/OrgContext';
import { approvalsApi } from '../../api/approvals';

export const Shell: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  const { currentOrg, loading, error } = useOrg();
  const [pendingApprovalsCount, setPendingApprovalsCount] = useState<number>(0);
  const [refreshTrigger, setRefreshTrigger] = useState<number>(0);

  useEffect(() => {
    if (currentOrg) {
      approvalsApi.list(currentOrg.id, { status: 'pending', limit: 100 })
        .then((res) => setPendingApprovalsCount(res.total || res.items?.length || 0))
        .catch(() => setPendingApprovalsCount(0));
    }
  }, [currentOrg, refreshTrigger]);

  const handleSeedComplete = () => {
    setRefreshTrigger((prev) => prev + 1);
  };

  return (
    <div className="app-shell">
      <Sidebar pendingApprovalsCount={pendingApprovalsCount} />
      <div className="app-main-wrapper">
        <Header onSeedComplete={handleSeedComplete} />
        <main className="app-content-area">
          {loading ? (
            <div className="shell-loading-state">
              <div className="spinner-large" />
              <p>Initializing CUSTODE Security Plane...</p>
            </div>
          ) : error ? (
            <div className="shell-error-banner">
              <div className="shell-error-title">Backend Connection Issue</div>
              <p>{error}</p>
              <p className="shell-error-sub">Ensure the FastAPI backend is running on http://localhost:8000.</p>
            </div>
          ) : (
            children
          )}
        </main>
      </div>
    </div>
  );
};
