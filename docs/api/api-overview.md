# CUSTODE API Reference & Architecture Overview

## 1. Global Conventions

- **Base URL:** `/api/v1`
- **Request & Response Body:** JSON (`Content-Type: application/json`)
- **Correlation ID:** Every request accepts optional `X-Request-ID` and returns it on response headers.
- **Tenant Scoping:** All tenant-specific resources are prefixed with `/organizations/{organization_id}`.

---

## 2. Authentication Headers

CUSTODE enforces strict credential separation:

| Caller Type | Header Name | Header Value / Format | Allowed Operations |
|---|---|---|---|
| **Human User** | `Authorization` | `Bearer <JWT_ACCESS_TOKEN>` | Administrative operations, approvals, organization configuration. |
| **Autonomous Agent** | `Authorization` | `Bearer <cst_api_key_secret>` | Submitting runtime actions, invoking LLM gateway, MCP calls. |
| **Agent Header Fallback** | `X-Custode-Agent-Id` | `<agent_uuid>` | Identifies initiating agent context in gateway flows. |

---

## 3. Endpoints Matrix

### Authentication & Identity
- `POST /api/v1/auth/login`: Authenticate human user, returns JWT token.
- `POST /api/v1/auth/logout`: Revoke active session.
- `POST /api/v1/users`: Create user account.
- `POST /api/v1/organizations`: Create new tenant organization.
- `POST /api/v1/organizations/{org_id}/memberships`: Grant user membership role.

### Agent & Tool Registry
- `POST /api/v1/organizations/{org_id}/agents`: Register new AI agent.
- `POST /api/v1/organizations/{org_id}/agents/{agent_id}/credentials`: Generate agent API key.
- `POST /api/v1/organizations/{org_id}/tools`: Register external tool.
- `POST /api/v1/organizations/{org_id}/tools/{tool_id}/operations`: Register tool operation.

### Permissions & Policy Engine
- `POST /api/v1/organizations/{org_id}/permissions`: Grant agent permission to tool operation.
- `POST /api/v1/organizations/{org_id}/policies`: Create policy container.
- `POST /api/v1/organizations/{org_id}/policies/{policy_id}/versions`: Draft rule version.
- `POST /api/v1/organizations/{org_id}/policies/{policy_id}/versions/{version_id}/publish`: Publish policy version.

### Runtime Action, Risk, & Decisions
- `POST /api/v1/organizations/{org_id}/runtime-actions`: Canonicalize agent tool request.
- `POST /api/v1/organizations/{org_id}/runtime-actions/{action_id}/decide`: Evaluate permissions, policies, risk; produce decision (`ALLOW`, `REQUIRE_APPROVAL`, `DENY`).
- `POST /api/v1/organizations/{org_id}/runtime-actions/{action_id}/execute`: Controlled execution with replay protection.

### Human Approval Governance
- `POST /api/v1/organizations/{org_id}/runtime-actions/{action_id}/approval`: Create approval request.
- `POST /api/v1/organizations/{org_id}/approvals/{approval_id}/approve`: Reviewer approve.
- `POST /api/v1/organizations/{org_id}/approvals/{approval_id}/reject`: Reviewer reject.

### Security Gateways & Integrations
- `POST /api/v1/organizations/{org_id}/llm/chat`: Secure LLM gateway with input/output firewalling.
- `POST /api/v1/organizations/{org_id}/mcp/servers`: Register Model Context Protocol server.
- `GET /api/v1/organizations/{org_id}/findings`: List security scan findings.
- `POST /api/v1/organizations/{org_id}/integrations`: Configure outbound webhook connector.

### Health & Observability
- `GET /health/live`: Process liveness probe.
- `GET /health/ready`: Database and migration readiness probe.
- `GET /health/metrics`: Operational uptime and status metrics.
