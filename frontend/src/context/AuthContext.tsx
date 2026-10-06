import React, { createContext, useContext, useState, useEffect, useCallback } from 'react';
import { User, UserRole, AuthenticatedUserContext, AuthTokenResponse } from '../types';
import { authApi } from '../api/auth';
import { getAuthToken, setAuthToken, setOnUnauthorizedCallback } from '../api/apiClient';

export interface AuthContextType {
  token: string | null;
  user: User | null;
  userContext: AuthenticatedUserContext | null;
  activeOrgId: string | null;
  role: UserRole | null;
  isAuthenticated: boolean;
  loading: boolean;
  error: string | null;
  login: (email: string, password?: string, orgId?: string) => Promise<AuthTokenResponse>;
  logout: () => Promise<void>;
  switchOrganization: (orgId: string) => Promise<void>;
  refreshUser: () => Promise<void>;
}

const AuthContext = createContext<AuthContextType | undefined>(undefined);

export const AuthProvider: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  const [token, setTokenState] = useState<string | null>(getAuthToken());
  const [user, setUser] = useState<User | null>(null);
  const [userContext, setUserContext] = useState<AuthenticatedUserContext | null>(null);
  const [activeOrgId, setActiveOrgId] = useState<string | null>(null);
  const [role, setRole] = useState<UserRole | null>(null);
  const [loading, setLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);

  const logout = useCallback(async () => {
    try {
      if (getAuthToken()) {
        await authApi.logout();
      }
    } catch {
      // Ignore network errors on logout
    } finally {
      setAuthToken(null);
      setTokenState(null);
      setUser(null);
      setUserContext(null);
      setActiveOrgId(null);
      setRole(null);
      setError(null);
    }
  }, []);

  const refreshUser = useCallback(async () => {
    const currentToken = getAuthToken();
    if (!currentToken) {
      setLoading(false);
      return;
    }

    try {
      const me = await authApi.getMe();
      setUserContext(me);
      setUser({
        id: me.id || me.user_id || '',
        email: me.email,
        display_name: me.display_name,
        status: (me.status as any) || 'active',
        last_login_at: me.last_login_at,
        created_at: new Date().toISOString(),
        updated_at: new Date().toISOString(),
      });
      const orgId = me.active_organization?.id || me.organization_id || (me.memberships?.[0]?.organization_id) || null;
      setActiveOrgId(orgId);
      const userRole = (me.role || me.active_membership?.role || me.memberships?.[0]?.role || null) as UserRole | null;
      setRole(userRole);
    } catch (err: any) {
      console.warn('Session verification failed:', err.message);
      await logout();
    } finally {
      setLoading(false);
    }
  }, [logout]);

  useEffect(() => {
    setOnUnauthorizedCallback(() => {
      logout();
    });
    refreshUser();
  }, [logout, refreshUser]);

  const login = async (email: string, password?: string, orgId?: string): Promise<AuthTokenResponse> => {
    setLoading(true);
    setError(null);
    try {
      const res = await authApi.login({
        email,
        password,
        organization_id: orgId,
      });

      setTokenState(res.access_token);
      setUser(res.user);
      const activeOrg = res.active_organization || res.organization;
      const primaryOrgId = activeOrg?.id || (res.memberships?.[0]?.organization_id) || null;
      setActiveOrgId(primaryOrgId);
      const userRole = (res.role || res.memberships?.[0]?.role || null) as UserRole | null;
      setRole(userRole);

      // Refresh full context (permissions & memberships)
      try {
        const me = await authApi.getMe();
        setUserContext(me);
      } catch {
        // Fallback context from token response
        setUserContext({
          id: res.user.id,
          user_id: res.user.id,
          email: res.user.email,
          display_name: res.user.display_name,
          active_organization: activeOrg,
          organization_id: primaryOrgId,
          role: userRole,
          permissions: [],
          memberships: res.memberships || [],
        });
      }

      return res;
    } catch (err: any) {
      const msg = err.message || 'Login failed. Please check your credentials.';
      setError(msg);
      throw err;
    } finally {
      setLoading(false);
    }
  };

  const switchOrganization = async (orgId: string): Promise<void> => {
    setLoading(true);
    setError(null);
    try {
      const res = await authApi.switchOrganization(orgId);
      setTokenState(res.access_token);
      const activeOrg = res.active_organization || res.organization;
      const primaryOrgId = activeOrg?.id || orgId;
      setActiveOrgId(primaryOrgId);
      const userRole = (res.role || res.memberships?.[0]?.role || null) as UserRole | null;
      setRole(userRole);
      await refreshUser();
    } catch (err: any) {
      const msg = err.message || 'Failed to switch organization.';
      setError(msg);
      throw err;
    } finally {
      setLoading(false);
    }
  };

  return (
    <AuthContext.Provider
      value={{
        token,
        user,
        userContext,
        activeOrgId,
        role,
        isAuthenticated: !!token && !!user,
        loading,
        error,
        login,
        logout,
        switchOrganization,
        refreshUser,
      }}
    >
      {children}
    </AuthContext.Provider>
  );
};

export const useAuth = (): AuthContextType => {
  const context = useContext(AuthContext);
  if (!context) {
    throw new Error('useAuth must be used within an AuthProvider');
  }
  return context;
};
