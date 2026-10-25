import React from 'react';
import { RouterProvider, Routes, Route, useRouter } from './router/Router';
import { AuthProvider, useAuth } from './context/AuthContext';
import { OrgProvider } from './context/OrgContext';
import { Shell } from './components/layout/Shell';

// Page components
import { LoginPage } from './pages/LoginPage';
import { DashboardPage } from './pages/DashboardPage';
import { AgentsPage } from './pages/AgentsPage';
import { AgentDetailPage } from './pages/AgentDetailPage';
import { ToolsPage } from './pages/ToolsPage';
import { ToolDetailPage } from './pages/ToolDetailPage';
import { PermissionsPage } from './pages/PermissionsPage';
import { PoliciesPage } from './pages/PoliciesPage';
import { PolicyDetailPage } from './pages/PolicyDetailPage';
import { RuntimeActionsPage } from './pages/RuntimeActionsPage';
import { RuntimeActionDetailPage } from './pages/RuntimeActionDetailPage';
import { RiskPage } from './pages/RiskPage';
import { DecisionsPage } from './pages/DecisionsPage';
import { DecisionDetailPage } from './pages/DecisionDetailPage';
import { ApprovalsPage } from './pages/ApprovalsPage';
import { ExecutionsPage } from './pages/ExecutionsPage';
import { ExecutionDetailPage } from './pages/ExecutionDetailPage';
import { AuditPage } from './pages/AuditPage';
import { AuditDetailPage } from './pages/AuditDetailPage';
import { FindingsPage } from './pages/FindingsPage';
import { FindingDetailPage } from './pages/FindingDetailPage';
import { LLMSecurityPage } from './pages/LLMSecurityPage';
import { LLMInteractionDetailPage } from './pages/LLMInteractionDetailPage';
import { MCPSecurityPage } from './pages/MCPSecurityPage';
import { BehaviorSecurityPage } from './pages/BehaviorSecurityPage';
import { IntegrationsPage } from './pages/IntegrationsPage';
import { SettingsPage } from './pages/SettingsPage';
import { CollegeBotPage } from './pages/CollegeBotPage';
import { NotFoundPage } from './pages/NotFoundPage';
import { LoadingState } from './components/common/FeedbackStates';

const AppContent: React.FC = () => {
  const { isAuthenticated, loading } = useAuth();
  const { pathname } = useRouter();

  if (loading) {
    return (
      <div style={{ display: 'flex', height: '100vh', alignItems: 'center', justifyContent: 'center', backgroundColor: '#080c14' }}>
        <LoadingState message="Verifying security credentials &amp; platform session..." />
      </div>
    );
  }

  if (!isAuthenticated || pathname === '/login') {
    return <LoginPage />;
  }

  return (
    <OrgProvider>
      <Shell>
        <Routes>
          <Route path="/" element={<DashboardPage />} />
          <Route path="/agents" element={<AgentsPage />} />
          <Route path="/agents/:id" element={<AgentDetailPage />} />
          <Route path="/tools" element={<ToolsPage />} />
          <Route path="/tools/:id" element={<ToolDetailPage />} />
          <Route path="/permissions" element={<PermissionsPage />} />
          <Route path="/policies" element={<PoliciesPage />} />
          <Route path="/policies/:id" element={<PolicyDetailPage />} />
          <Route path="/runtime-actions" element={<RuntimeActionsPage />} />
          <Route path="/runtime-actions/:id" element={<RuntimeActionDetailPage />} />
          <Route path="/risk" element={<RiskPage />} />
          <Route path="/decisions" element={<DecisionsPage />} />
          <Route path="/decisions/:id" element={<DecisionDetailPage />} />
          <Route path="/approvals" element={<ApprovalsPage />} />
          <Route path="/executions" element={<ExecutionsPage />} />
          <Route path="/executions/:id" element={<ExecutionDetailPage />} />
          <Route path="/audit" element={<AuditPage />} />
          <Route path="/audit/:id" element={<AuditDetailPage />} />
          <Route path="/findings" element={<FindingsPage />} />
          <Route path="/findings/:id" element={<FindingDetailPage />} />
          <Route path="/llm-security" element={<LLMSecurityPage />} />
          <Route path="/llm-security/:id" element={<LLMInteractionDetailPage />} />
          <Route path="/mcp-security" element={<MCPSecurityPage />} />
          <Route path="/behavior-security" element={<BehaviorSecurityPage />} />
          <Route path="/integrations" element={<IntegrationsPage />} />
          <Route path="/settings" element={<SettingsPage />} />
          <Route path="/college-bot" element={<CollegeBotPage />} />
          <Route path="*" element={<NotFoundPage />} />
        </Routes>
      </Shell>
    </OrgProvider>
  );
};

export const App: React.FC = () => {
  return (
    <RouterProvider>
      <AuthProvider>
        <AppContent />
      </AuthProvider>
    </RouterProvider>
  );
};

export default App;
