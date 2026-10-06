import React, { createContext, useContext, useState, useEffect, useCallback } from 'react';
import { Organization, User } from '../types';
import { organizationsApi } from '../api/organizations';
import { approvalsApi } from '../api/approvals';
import { useAuth } from './AuthContext';

export interface OrgContextType {
  organizations: Organization[];
  currentOrg: Organization | null;
  activeOrg: Organization | null;
  currentUser: User | null;
  loading: boolean;
  error: string | null;
  pendingApprovalsCount: number;
  setCurrentOrg: (org: Organization) => Promise<void>;
  refreshOrgs: () => Promise<void>;
  createOrg: (name: string, slug?: string) => Promise<Organization>;
  refreshPendingApprovals: () => Promise<void>;
}

const OrgContext = createContext<OrgContextType | undefined>(undefined);

const STORAGE_KEY_ORG_ID = 'custode_active_org_id';

export const OrgProvider: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  const { user, activeOrgId, switchOrganization, isAuthenticated } = useAuth();
  const [organizations, setOrganizations] = useState<Organization[]>([]);
  const [currentOrg, setCurrentOrgState] = useState<Organization | null>(null);
  const [pendingApprovalsCount, setPendingApprovalsCount] = useState<number>(0);
  const [loading, setLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);

  const refreshPendingApprovals = useCallback(async () => {
    if (!currentOrg || !isAuthenticated) return;
    try {
      const res = await approvalsApi.list(currentOrg.id, { status: 'pending' });
      setPendingApprovalsCount(res.total || res.items?.length || 0);
    } catch {
      // silent catch for background polling
    }
  }, [currentOrg, isAuthenticated]);

  const refreshOrgs = useCallback(async () => {
    if (!isAuthenticated) {
      setLoading(false);
      return;
    }

    setLoading(true);
    setError(null);
    try {
      const list = await organizationsApi.list();
      setOrganizations(list || []);

      if (list && list.length > 0) {
        // Priority 1: Auth activeOrgId
        // Priority 2: Stored localStorage org ID
        // Priority 3: First available org
        const savedOrgId = activeOrgId || localStorage.getItem(STORAGE_KEY_ORG_ID);
        const matched = list.find((o) => o.id === savedOrgId) || list[0];
        setCurrentOrgState(matched);
        localStorage.setItem(STORAGE_KEY_ORG_ID, matched.id);
      } else {
        setCurrentOrgState(null);
      }
    } catch (err: any) {
      console.warn('Failed to load organizations:', err.message);
      setError(err.message || 'Unable to connect to CUSTODE backend.');
    } finally {
      setLoading(false);
    }
  }, [isAuthenticated, activeOrgId]);

  useEffect(() => {
    refreshOrgs();
  }, [refreshOrgs]);

  useEffect(() => {
    if (currentOrg) {
      refreshPendingApprovals();
    }
  }, [currentOrg, refreshPendingApprovals]);

  const setCurrentOrg = async (org: Organization): Promise<void> => {
    setCurrentOrgState(org);
    localStorage.setItem(STORAGE_KEY_ORG_ID, org.id);
    if (activeOrgId !== org.id) {
      await switchOrganization(org.id);
    }
  };

  const createOrg = async (name: string, slug?: string): Promise<Organization> => {
    const newOrg = await organizationsApi.create({ name, slug });
    await refreshOrgs();
    await setCurrentOrg(newOrg);
    return newOrg;
  };

  return (
    <OrgContext.Provider
      value={{
        organizations,
        currentOrg,
        activeOrg: currentOrg,
        currentUser: user,
        loading,
        error,
        pendingApprovalsCount,
        setCurrentOrg,
        refreshOrgs,
        createOrg,
        refreshPendingApprovals,
      }}
    >
      {children}
    </OrgContext.Provider>
  );
};

export const useOrg = (): OrgContextType => {
  const context = useContext(OrgContext);
  if (!context) {
    throw new Error('useOrg must be used within an OrgProvider');
  }
  return context;
};
