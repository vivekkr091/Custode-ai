import React, { useState } from 'react';
import { useAuth } from '../context/AuthContext';
import { useNavigate } from '../router/Router';
import { Button } from '../components/common/Button';
import { ShieldIcon, KeyIcon, LockIcon, AlertTriangleIcon, CheckCircleIcon } from '../components/common/Icons';

export const LoginPage: React.FC = () => {
  const { login } = useAuth();
  const navigate = useNavigate();

  const [email, setEmail] = useState('security.admin@custode.io');
  const [password, setPassword] = useState('Custode#2026Admin!');
  const [orgId, setOrgId] = useState('');
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!email.trim()) {
      setError('Please provide a valid operator email address.');
      return;
    }

    setIsLoading(true);
    setError(null);

    try {
      await login(email.trim(), password ? password : undefined, orgId.trim() ? orgId.trim() : undefined);
      navigate('/');
    } catch (err: any) {
      setError(err.message || 'Authentication failed. Please verify credentials.');
    } finally {
      setIsLoading(false);
    }
  };

  const handleDevQuickLogin = async (roleType: 'admin' | 'analyst' | 'viewer') => {
    setIsLoading(true);
    setError(null);
    let devEmail = 'security.admin@custode.io';
    let devPass = 'Custode#2026Admin!';

    if (roleType === 'analyst') {
      devEmail = 'analyst@custode.io';
      devPass = 'Analyst#2026Secure!';
    } else if (roleType === 'viewer') {
      devEmail = 'auditor@custode.io';
      devPass = 'Auditor#2026View!';
    }

    setEmail(devEmail);
    setPassword(devPass);

    try {
      await login(devEmail, devPass);
      navigate('/');
    } catch (err: any) {
      setError(err.message || 'Quick login failed. Verify user is provisioned in the backend database.');
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <div className="login-page-container">
      <div className="login-card">
        {/* Brand Header */}
        <div className="login-header">
          <div className="login-shield-wrapper">
            <ShieldIcon size={36} className="login-shield-icon" />
          </div>
          <h1 className="login-title">CUSTODE</h1>
          <p className="login-subtitle">AI AGENT SECURITY &amp; CONTROL PLANE</p>
          <div className="login-badge">AUTHORIZED OPERATOR ACCESS ONLY</div>
        </div>

        {error && (
          <div className="login-error-banner">
            <AlertTriangleIcon size={16} className="text-rose" />
            <span>{error}</span>
          </div>
        )}

        <form onSubmit={handleSubmit} className="login-form">
          <div className="form-group">
            <label className="form-label">Operator Email</label>
            <input
              type="email"
              className="form-input"
              placeholder="e.g. security.admin@custode.io"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              required
              autoFocus
            />
          </div>

          <div className="form-group">
            <label className="form-label">Password</label>
            <input
              type="password"
              className="form-input"
              placeholder="••••••••••••"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
            />
            <span className="input-hint">Default dev password: Custode#2026Admin!</span>
          </div>

          <div className="form-group">
            <label className="form-label">Organization Context (Optional)</label>
            <input
              type="text"
              className="form-input"
              placeholder="UUID or slug (Leave empty for default)"
              value={orgId}
              onChange={(e) => setOrgId(e.target.value)}
            />
          </div>

          <Button
            type="submit"
            variant="primary"
            size="lg"
            loading={isLoading}
            icon={<KeyIcon size={16} />}
            className="login-submit-button"
          >
            Authenticate &amp; Enter Platform
          </Button>
        </form>

        {/* Development Quick-Access Shortcuts */}
        <div className="dev-auth-helper">
          <div className="dev-helper-divider">
            <span>DEVELOPMENT QUICK LOGIN</span>
          </div>
          <div className="dev-roles-grid">
            <button
              type="button"
              className="dev-role-button"
              onClick={() => handleDevQuickLogin('admin')}
              disabled={isLoading}
            >
              <span className="role-chip chip-admin">Admin</span>
              <span className="role-desc">Full Security Control</span>
            </button>
            <button
              type="button"
              className="dev-role-button"
              onClick={() => handleDevQuickLogin('analyst')}
              disabled={isLoading}
            >
              <span className="role-chip chip-analyst">Analyst</span>
              <span className="role-desc">Review &amp; Approvals</span>
            </button>
            <button
              type="button"
              className="dev-role-button"
              onClick={() => handleDevQuickLogin('viewer')}
              disabled={isLoading}
            >
              <span className="role-chip chip-viewer">Viewer</span>
              <span className="role-desc">Read-Only Audit</span>
            </button>
          </div>
        </div>

        <div className="login-footer">
          <span>RFC 7519 HS256 Token Protection • Tenant Isolated</span>
        </div>
      </div>
    </div>
  );
};
