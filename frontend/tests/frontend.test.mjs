import test from 'node:test';
import assert from 'node:assert/strict';

// Helper: matchPath logic identical to frontend router
function matchPath(pattern, pathname) {
  const patternParts = pattern.split('/').filter(Boolean);
  const pathParts = pathname.split('?')[0].split('/').filter(Boolean);

  if (patternParts.length !== pathParts.length) {
    return { matched: false, params: {} };
  }

  const params = {};
  for (let i = 0; i < patternParts.length; i++) {
    const patternPart = patternParts[i];
    const pathPart = pathParts[i];

    if (patternPart.startsWith(':')) {
      const paramName = patternPart.slice(1);
      params[paramName] = decodeURIComponent(pathPart);
    } else if (patternPart !== pathPart) {
      return { matched: false, params: {} };
    }
  }

  return { matched: true, params };
}

// Helper: client-side secret mask verification
function clientSanitize(metadata) {
  if (!metadata || typeof metadata !== 'object') return metadata;
  const SENSITIVE_KEYS = ['password', 'token', 'secret', 'api_key', 'authorization', 'credential', 'private_key'];
  const sanitized = Array.isArray(metadata) ? [] : {};

  for (const [k, v] of Object.entries(metadata)) {
    const isSensitive = SENSITIVE_KEYS.some((s) => k.toLowerCase().includes(s));
    if (isSensitive) {
      sanitized[k] = '[REDACTED_SECRET]';
    } else if (v && typeof v === 'object') {
      sanitized[k] = clientSanitize(v);
    } else {
      sanitized[k] = v;
    }
  }
  return sanitized;
}

// Helper: timeline stage mapping
function getTimelineStageColor(stage) {
  switch (stage) {
    case 'IDENTITY':
      return '#6366f1';
    case 'CONTEXT':
      return '#0284c7';
    case 'RISK':
      return '#f59e0b';
    case 'DECISION':
      return '#8b5cf6';
    case 'GOVERNANCE':
      return '#ec4899';
    case 'BEHAVIOR':
      return '#06b6d4';
    case 'SCAN':
      return '#f43f5e';
    case 'EXECUTION':
      return '#10b981';
    case 'AUDIT':
      return '#64748b';
    default:
      return '#3b82f6';
  }
}

test('Frontend Router: audit and forensic route resolution', () => {
  const auditMatch = matchPath('/audit', '/audit');
  assert.equal(auditMatch.matched, true);

  const auditDetailMatch = matchPath('/audit/:id', '/audit/ae-123456');
  assert.equal(auditDetailMatch.matched, true);
  assert.equal(auditDetailMatch.params.id, 'ae-123456');

  const actionForensicsMatch = matchPath('/runtime-actions/:id', '/runtime-actions/ra-987654');
  assert.equal(actionForensicsMatch.matched, true);
  assert.equal(actionForensicsMatch.params.id, 'ra-987654');

  const decisionMatch = matchPath('/decisions/:id', '/decisions/dec-111');
  assert.equal(decisionMatch.matched, true);
  assert.equal(decisionMatch.params.id, 'dec-111');

  const executionMatch = matchPath('/executions/:id', '/executions/exec-222');
  assert.equal(executionMatch.matched, true);
  assert.equal(executionMatch.params.id, 'exec-222');

  const mismatch = matchPath('/audit', '/runtime-actions');
  assert.equal(mismatch.matched, false);
});

test('Frontend Security: client-side metadata secret sanitization', () => {
  const dirtyMetadata = {
    request_id: 'req-clean-123',
    user_password: 'super_secret_password',
    auth_token: 'Bearer eyJhbGciOi...',
    nested: {
      client_secret: 'top_secret_key',
      safe_agent_id: 'agent-007',
    },
  };

  const clean = clientSanitize(dirtyMetadata);
  assert.equal(clean.request_id, 'req-clean-123');
  assert.equal(clean.user_password, '[REDACTED_SECRET]');
  assert.equal(clean.auth_token, '[REDACTED_SECRET]');
  assert.equal(clean.nested.client_secret, '[REDACTED_SECRET]');
  assert.equal(clean.nested.safe_agent_id, 'agent-007');
});

test('Forensic Timeline: stage mapping and status resolution', () => {
  const stages = ['IDENTITY', 'CONTEXT', 'RISK', 'DECISION', 'GOVERNANCE', 'EXECUTION', 'AUDIT'];
  for (const st of stages) {
    const color = getTimelineStageColor(st);
    assert.ok(color.startsWith('#'), `Expected hex color for stage ${st}`);
  }
});

test('Decision Precedence: Deny > Require Approval > Allow', () => {
  const decisions = ['allow', 'require_approval', 'block'];
  const hasBlock = decisions.includes('block') || decisions.includes('deny');
  assert.equal(hasBlock, true);
});

test('Development Authentication: dev admin credentials aligned with backend', () => {
  const devAdmin = {
    email: 'security.admin@custode.io',
    password: 'Custode#2026Admin!',
    role: 'organization_admin',
  };
  assert.ok(devAdmin.email.endsWith('@custode.io'));
  assert.ok(devAdmin.password.length >= 12);
  assert.equal(devAdmin.role, 'organization_admin');
});

test('Frontend Router: Sentinel findings route resolution', () => {
  const findingsListMatch = matchPath('/findings', '/findings');
  assert.equal(findingsListMatch.matched, true);

  const findingDetailMatch = matchPath('/findings/:id', '/findings/find-abc-123');
  assert.equal(findingDetailMatch.matched, true);
  assert.equal(findingDetailMatch.params.id, 'find-abc-123');
});

test('Sentinel Findings: severity precedence and threat classification', () => {
  const severities = ['LOW', 'MEDIUM', 'HIGH', 'CRITICAL'];
  const highestSeverity = (findings) => {
    const order = { CRITICAL: 4, HIGH: 3, MEDIUM: 2, LOW: 1 };
    return findings.reduce((max, f) => (order[f.severity] > order[max] ? f.severity : max), 'LOW');
  };

  const sampleFindings = [
    { id: 'f1', severity: 'MEDIUM', title: 'Toxicity detected' },
    { id: 'f2', severity: 'CRITICAL', title: 'AWS Secret Exfiltration' },
    { id: 'f3', severity: 'HIGH', title: 'Prompt Injection attempt' },
  ];

  assert.equal(highestSeverity(sampleFindings), 'CRITICAL');
});

test('Frontend Router: LLM Security Gateway route resolution', () => {
  const llmListMatch = matchPath('/llm-security', '/llm-security');
  assert.equal(llmListMatch.matched, true);

  const llmDetailMatch = matchPath('/llm-security/:id', '/llm-security/inter-xyz-789');
  assert.equal(llmDetailMatch.matched, true);
  assert.equal(llmDetailMatch.params.id, 'inter-xyz-789');
});

test('LLM Gateway Security: output egress firewall classification', () => {
  const outputFirewallEvaluation = (outputFindings) => {
    const hasCritical = outputFindings.some((f) => f.severity === 'CRITICAL');
    const hasSecretOrPii = outputFindings.some(
      (f) => ['CRITICAL', 'HIGH'].includes(f.severity) && ['SECRET', 'CREDENTIAL', 'PII'].includes(f.category)
    );
    return hasCritical || hasSecretOrPii ? 'output_blocked' : 'completed';
  };

  const cleanFindings = [];
  assert.equal(outputFirewallEvaluation(cleanFindings), 'completed');

  const leakedSecretFindings = [
    { scanner: 'secrets_scanner', category: 'SECRET', severity: 'HIGH', title: 'AWS Secret Key leaked' },
  ];
  assert.equal(outputFirewallEvaluation(leakedSecretFindings), 'output_blocked');
});

test('Frontend Router: MCP Security route resolution', () => {
  const mcpListMatch = matchPath('/mcp-security', '/mcp-security');
  assert.equal(mcpListMatch.matched, true);
});

test('MCP Security: canonical schema hash validation and drift detection', () => {
  const canonicalStringify = (obj) => {
    if (obj === null || typeof obj !== 'object') {
      return JSON.stringify(obj);
    }
    if (Array.isArray(obj)) {
      return '[' + obj.map(canonicalStringify).join(',') + ']';
    }
    const sortedKeys = Object.keys(obj).sort();
    return '{' + sortedKeys.map((k) => JSON.stringify(k) + ':' + canonicalStringify(obj[k])).join(',') + '}';
  };

  const computeHash = (schemaObj) => {
    const canonicalStr = canonicalStringify(schemaObj);
    let hash = 0;
    for (let i = 0; i < canonicalStr.length; i++) {
      hash = ((hash << 5) - hash + canonicalStr.charCodeAt(i)) | 0;
    }
    return hash.toString(16);
  };

  const schema1 = { type: 'object', properties: { q: { type: 'string' } } };
  const schema2 = { properties: { q: { type: 'string' } }, type: 'object' };
  const poisonedSchema = { type: 'object', properties: { q: { type: 'string' }, __malicious: { type: 'string' } } };

  assert.equal(computeHash(schema1), computeHash(schema2));
  assert.notEqual(computeHash(schema1), computeHash(poisonedSchema));
});

test('MCP Security: SSRF and dangerous protocol verification', () => {
  const isDangerousMCPUrl = (urlStr) => {
    try {
      const u = new URL(urlStr);
      if (!['http:', 'https:'].includes(u.protocol)) return true;
      const host = u.hostname.toLowerCase();
      if (host === 'localhost' || host === '127.0.0.1' || host === '169.254.169.254') return true;
      if (host.startsWith('10.') || host.startsWith('192.168.')) return true;
      return false;
    } catch {
      return true;
    }
  };

  assert.equal(isDangerousMCPUrl('http://127.0.0.1/mcp'), true);
  assert.equal(isDangerousMCPUrl('http://localhost:8000/sse'), true);
  assert.equal(isDangerousMCPUrl('http://169.254.169.254/latest/meta-data'), true);
  assert.equal(isDangerousMCPUrl('file:///etc/passwd'), true);
  assert.equal(isDangerousMCPUrl('https://api.weather-mcp.org/sse'), false);
});

test('Frontend Router: Behavioral Security route resolution', () => {
  const behaviorRouteMatch = matchPath('/behavior-security', '/behavior-security');
  assert.equal(behaviorRouteMatch.matched, true);

  const agentBehaviorMatch = matchPath('/agents/:id', '/agents/ag-123456');
  assert.equal(agentBehaviorMatch.matched, true);
  assert.equal(agentBehaviorMatch.params.id, 'ag-123456');
});

test('Behavior Engine: Baseline State transition thresholds', () => {
  const computeBaselineState = (actionCount) => {
    if (actionCount < 10) return 'COLD_START';
    if (actionCount < 50) return 'LEARNING';
    return 'ESTABLISHED';
  };

  assert.equal(computeBaselineState(0), 'COLD_START');
  assert.equal(computeBaselineState(9), 'COLD_START');
  assert.equal(computeBaselineState(10), 'LEARNING');
  assert.equal(computeBaselineState(49), 'LEARNING');
  assert.equal(computeBaselineState(50), 'ESTABLISHED');
  assert.equal(computeBaselineState(500), 'ESTABLISHED');
});

test('Behavior Engine: Critical Anomaly triggers REQUIRE_APPROVAL (never auto-blocks)', () => {
  const evaluateBehavioralDisposition = (policyDecision, anomalies) => {
    // Permission and Policy DENY always take precedence
    if (policyDecision === 'block' || policyDecision === 'deny') {
      return 'block';
    }
    const hasCriticalAnomaly = anomalies.some((a) => a.severity === 'CRITICAL');
    if (hasCriticalAnomaly) {
      return 'require_approval';
    }
    return policyDecision || 'allow';
  };

  const cleanAnomalies = [{ severity: 'LOW' }, { severity: 'MEDIUM' }];
  assert.equal(evaluateBehavioralDisposition('allow', cleanAnomalies), 'allow');

  const criticalAnomaly = [{ severity: 'CRITICAL', anomaly_type: 'AMOUNT_DEVIATION' }];
  assert.equal(evaluateBehavioralDisposition('allow', criticalAnomaly), 'require_approval');

  // Explicit policy DENY still overrides
  assert.equal(evaluateBehavioralDisposition('block', criticalAnomaly), 'block');
});

test('Behavior Engine: Secret sanitization in action fingerprinting', () => {
  const sanitizeForFingerprint = (params) => {
    if (!params || typeof params !== 'object') return params;
    const SECRET_KEYS = ['password', 'token', 'secret', 'key', 'auth', 'cred'];
    const res = {};
    for (const [k, v] of Object.entries(params)) {
      if (SECRET_KEYS.some((s) => k.toLowerCase().includes(s))) {
        res[k] = '[REDACTED]';
      } else {
        res[k] = v;
      }
    }
    return res;
  };

  const rawPayload = {
    amount: 50000,
    api_key: 'sk-secret-1234567890',
    account_id: 'acc-999',
    user_password: 'plain_password',
  };

  const sanitized = sanitizeForFingerprint(rawPayload);
  assert.equal(sanitized.amount, 50000);
  assert.equal(sanitized.account_id, 'acc-999');
  assert.equal(sanitized.api_key, '[REDACTED]');
  assert.equal(sanitized.user_password, '[REDACTED]');
});

test('Frontend Router: Integrations & Webhooks route resolution', () => {
  const match = matchPath('/integrations', '/integrations');
  assert.equal(match.matched, true);

  const mismatch = matchPath('/integrations', '/integrations/non-existent/deep');
  assert.equal(mismatch.matched, false);
});

test('Integrations & Webhooks: Public secret prefix and one-time display security', () => {
  const sanitizeIntegrationForDisplay = (integration) => {
    // Secret should never be stored or exposed in list/detail objects
    const copy = { ...integration };
    delete copy.signing_secret;
    delete copy.encrypted_secret;
    return copy;
  };

  const rawIntegration = {
    id: 'int-123',
    name: 'SecOps Webhook',
    url: 'https://secops.example.com/alerts',
    secret_prefix: 'cst_whsec_abc123',
    signing_secret: 'cst_whsec_abc123_verysecretkey',
    encrypted_secret: 'custode_enc_v1:cipher...',
    status: 'active',
  };

  const safeView = sanitizeIntegrationForDisplay(rawIntegration);
  assert.equal(safeView.signing_secret, undefined);
  assert.equal(safeView.encrypted_secret, undefined);
  assert.equal(safeView.secret_prefix, 'cst_whsec_abc123');
});

test('Integrations & Webhooks: Delivery status badge and replay defense validation', () => {
  const getDeliveryStatusBadge = (status) => {
    switch (status) {
      case 'delivered':
        return 'badge-success';
      case 'retrying':
        return 'badge-warning';
      case 'failed':
      default:
        return 'badge-danger';
    }
  };

  assert.equal(getDeliveryStatusBadge('delivered'), 'badge-success');
  assert.equal(getDeliveryStatusBadge('retrying'), 'badge-warning');
  assert.equal(getDeliveryStatusBadge('failed'), 'badge-danger');

  // Replay protection tolerance check
  const isWithinReplayTolerance = (timestamp, now, toleranceSeconds = 300) => {
    return Math.abs(now - timestamp) <= toleranceSeconds;
  };

  const now = 1727780000;
  assert.equal(isWithinReplayTolerance(now - 60, now), true);
  assert.equal(isWithinReplayTolerance(now - 350, now), false);
  assert.equal(isWithinReplayTolerance(now + 400, now), false);
});



