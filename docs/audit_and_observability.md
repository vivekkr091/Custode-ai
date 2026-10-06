# CUSTODE — Milestone 15: Security Audit, Governance & Observability

## 1. Overview
Milestone 15 establishes CUSTODE as a tamper-evident, production-ready Security Governance, Audit, and Forensic Observability platform. Every administrative mutation, agent runtime action, risk evaluation, authorization decision, approval review, and controlled execution emits an immutable audit event conforming to the canonical schema:

$$\text{Actor} \longrightarrow \text{Organization} \longrightarrow \text{Action} \longrightarrow \text{Target Resource} \longrightarrow \text{Security Context} \longrightarrow \text{Outcome} \longrightarrow \text{Timestamp}$$

---

## 2. Event Taxonomy
Audit events are typed using the controlled `AuditEventType` enum:

- **Authentication (`AUTH_*`)**:
  - `AUTH_LOGIN_SUCCESS`, `AUTH_LOGIN_FAILURE`, `AUTH_LOGOUT`, `AUTH_ORGANIZATION_SWITCH`
- **Users & Memberships (`USER_*`, `MEMBERSHIP_*`)**:
  - `USER_CREATED`, `USER_UPDATED`, `USER_SUSPENDED`, `USER_DISABLED`
  - `MEMBERSHIP_CREATED`, `MEMBERSHIP_UPDATED`, `MEMBERSHIP_REVOKED`
- **Agent Identity (`AGENT_*`)**:
  - `AGENT_CREATED`, `AGENT_UPDATED`, `AGENT_SUSPENDED`, `AGENT_REVOKED`, `AGENT_CREDENTIAL_ISSUED`, `AGENT_CREDENTIAL_REVOKED`
- **Tools & Operations (`TOOL_*`, `OPERATION_*`)**:
  - `TOOL_CREATED`, `TOOL_UPDATED`, `TOOL_SUSPENDED`, `TOOL_REVOKED`
  - `OPERATION_CREATED`, `OPERATION_UPDATED`, `OPERATION_SUSPENDED`, `OPERATION_REVOKED`
- **Permissions & Policies (`PERMISSION_*`, `POLICY_*`)**:
  - `PERMISSION_CREATED`, `PERMISSION_UPDATED`, `PERMISSION_SUSPENDED`, `PERMISSION_REVOKED`
  - `POLICY_CREATED`, `POLICY_UPDATED`, `POLICY_VERSION_CREATED`, `POLICY_PUBLISHED`, `POLICY_RETIRED`
- **Runtime Actions & Risk (`RUNTIME_ACTION_*`, `RISK_ASSESSMENT_*`)**:
  - `RUNTIME_ACTION_CREATED`, `RUNTIME_ACTION_EVALUATED`
  - `RISK_ASSESSMENT_CREATED`
- **Decision Engine (`DECISION_*`)**:
  - `DECISION_CREATED`
- **Human Governance (`APPROVAL_*`)**:
  - `APPROVAL_CREATED`, `APPROVAL_APPROVED`, `APPROVAL_REJECTED`, `APPROVAL_EXPIRED`, `APPROVAL_CANCELLED`
- **Controlled Execution (`EXECUTION_*`)**:
  - `EXECUTION_CREATED`, `EXECUTION_STARTED`, `EXECUTION_SUCCEEDED`, `EXECUTION_FAILED`, `EXECUTION_BLOCKED`

---

## 3. Actor Resolution & Trust Boundary
Actor identity is strictly resolved from verified authenticated context:
- **`USER`**: Authenticated human operator via JWT Bearer session. Populates `actor_type=USER`, `actor_id=user.id`, and `actor_display=user.display_name`.
- **`AGENT`**: Authenticated AI agent identity via Bearer credential. Populates `actor_type=AGENT`, `actor_id=agent.id`, and `actor_display=agent.name`.
- **`SYSTEM`**: Platform kernel or automated background process. Populates `actor_type=SYSTEM`, `actor_id="system"`, and `actor_display="CUSTODE Core"`.

Client-provided headers (`X-User-ID`, `X-Agent-ID`) are never trusted when an authenticated session exists.

---

## 4. Security Metadata Sanitization
All metadata passed to `record_event()` is recursively sanitized via `sanitize_metadata()`. Keys matching any of the following sensitive substrings are masked with `[REDACTED_SECRET]`:
- `password`, `token`, `secret`, `api_key`, `authorization`, `credential`, `private_key`

Harmless identifiers such as `agent_id`, `tool_id`, `action_id`, `request_id`, and `decision_id` remain intact for forensic tracing.

---

## 5. End-to-End Request Correlation
The `request_correlation_middleware` extracts inbound `X-Request-ID` or generates an RFC 4122 UUID4 string. The correlation ID is:
1. Stored in Python `ContextVar` (`get_current_request_id()`).
2. Attached to `request.state.request_id`.
3. Injected into every `AuditEvent` and `RuntimeAction`.
4. Returned in HTTP response headers (`X-Request-ID`).

Investigators can query `GET /api/v1/organizations/{org_id}/audit-events?request_id={req_id}` to retrieve all correlated events across the platform.

---

## 6. Audit Immutability & Retention
- **Append-Only**: Audit records are strictly immutable. No `UPDATE` or `DELETE` endpoints exist.
- **Tenant Scoping**: All audit queries require membership within the target organization. Cross-tenant access is rejected with `403 Forbidden` or `404 Not Found`.
- **Future Retention Policy**: Retention windows (e.g. 90-day, 365-day cold archive) will be implemented via dedicated background compliance jobs in subsequent governance milestones.

---

## 7. Audit & Observability API
- `GET /api/v1/organizations/{org_id}/audit-events` (with extensive multi-field filtering & pagination)
- `GET /api/v1/organizations/{org_id}/audit-events/{event_id}` (individual event detail)
- `GET /api/v1/organizations/{org_id}/security-overview` (authoritative metrics & posture counts)
- `GET /api/v1/organizations/{org_id}/runtime-actions/{id}/forensics` (multi-stage chronological timeline)
- `GET /api/v1/organizations/{org_id}/search?q={query}` (global multi-entity search)
