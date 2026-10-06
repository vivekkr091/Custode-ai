# CUSTODE Milestone 22: Security Assessment & Hardening Report

**Assessment Date:** 2026-10-01  
**Scope:** CUSTODE AI Agent Security & Control Platform (Backend, Frontend, SDK, Docker, Integrations)  
**Methodology:** STRIDE Threat Modeling, Gray-box Adversarial Red Teaming, Automated Security Regression Validation  
**Target Baseline:** Milestones 1–21 Complete  
**Reference Material:** Isolated reference repository `sentinel-ai/` (Read-only, untouched)  

---

## 1. Executive Summary

As part of **Milestone 22: Security Hardening & Red Team Validation**, a comprehensive security evaluation and defensive hardening program was conducted on the CUSTODE platform. The assessment validated the system against realistic threats facing AI agent security platforms, including:
- Tenant isolation and horizontal privilege escalation (IDOR).
- Concurrency race conditions in human approval and controlled execution lifecycles.
- Denial-of-Service (DoS) via unconstrained ingress request bodies and unbounded listing pagination.
- Authentication brute-force and credential stuffing.
- Server-Side Request Forgery (SSRF) and timestamp replay attacks via webhook delivery.
- LLM prompt injection and MCP tool-call policy evasion.
- Behavioral anomaly evasion via rate-limited or stealthy activity.

All confirmed vulnerabilities were safely reproduced with dedicated automated regression tests, systematically remediated in the codebase, and verified with zero regressions across backend, frontend, Python SDK, and deployment configurations.

---

## 2. Assessment Methodology

The assessment followed a structured defensive red team process:
1. **Threat Modeling:** Formalized trust boundaries, threat actors, assets, and threat vectors under the STRIDE methodology (`docs/security/threat-model.md`).
2. **Static Code Review & Architecture Analysis:** Inspected authentication flows, RBAC enforcement, session management, database concurrency locks, pagination bounds, and webhook signatures.
3. **Adversarial Red Team Testing:** Constructed exploit scripts and adversarial test cases simulating malicious tenants, rogue agents, concurrent approvers, and external attackers.
4. **Root Cause Analysis & Remediation:** Patched discovered weaknesses using defense-in-depth principles (row-level locking, sliding-window rate limiters, strict HTTP ingress filters, security headers).
5. **Automated Regression Test Suite:** Established `custode/backend/tests/security/` containing 27 automated security tests executing against real database sessions and API routers.
6. **Full-Platform Regression Verification:** Ran the complete suite across backend, frontend, SDK, and container definitions.

---

## 3. Vulnerability Register

### FINDING-01: Approval Lifecycle Race Condition (Double-Action)
- **Finding ID:** `FINDING-01`
- **Severity:** High (CVSS 7.4)
- **Component:** Approval Workflow (`app/services/approval.py`)
- **STRIDE Category:** Tampering / Elevation of Privilege
- **Description:** Multiple concurrent HTTP requests to approve or reject the same pending approval request could execute simultaneously before status validation was committed, leading to duplicate state transitions or conflicting reviewer records.
- **Root Cause Analysis:** `get_approval()` fetched the row without pessimistic row-level locking (`with_for_update()`), creating a time-of-check to time-of-use (TOCTOU) race window.
- **Exploitability & Impact:** An attacker or malfunctioning frontend sending rapid concurrent approvals could bypass sequential governance audit trails and duplicate approval records.
- **Remediation:** Added `with_for_update=True` support to `get_approval()` and applied row-level database locking during `approve_request()`, `reject_request()`, and `cancel_request()`. State transition validation immediately raises `409 Conflict` if the approval status is no longer `pending`.
- **Regression Test:** `tests/security/test_approval_execution_concurrency.py::test_approval_lifecycle_state_machine_prevents_double_action`

---

### FINDING-02: Double Execution / Execution Replay Vulnerability
- **Finding ID:** `FINDING-02`
- **Severity:** High (CVSS 7.8)
- **Component:** Controlled Execution (`app/runtime/execution_guard.py`)
- **STRIDE Category:** Tampering / Elevation of Privilege
- **Description:** When an authorized `RuntimeAction` is dispatched for execution, concurrent or repeated calls to `/runtime-actions/{id}/execute` could race past the execution check if executed before the first execution committed its final status.
- **Root Cause Analysis:** `ExecutionGuard.execute_action()` did not lock the `RuntimeAction` record with row-level locks before evaluating the execution status and transition state.
- **Exploitability & Impact:** Tools with side-effects (e.g. database updates, financial transactions, external API mutations) could be executed multiple times on a single authorization.
- **Remediation:** Added `with_for_update()` row-level locking on `RuntimeAction` in `ExecutionGuard.execute_action()`. Verified that both `ExecutionStatus.succeeded` and `ExecutionStatus.running` states strictly block replay with `DuplicateExecutionError` (`409 Conflict`).
- **Regression Test:** `tests/security/test_approval_execution_concurrency.py::test_execution_replay_and_duplicate_blocked`

---

### FINDING-03: Missing Ingress Request Body Size Enforcement (HTTP DoS)
- **Finding ID:** `FINDING-03`
- **Severity:** Medium (CVSS 6.5)
- **Component:** Backend Middleware (`app/main.py`)
- **STRIDE Category:** Denial of Service
- **Description:** FastAPI/Starlette lacked a global maximum request body size limit, allowing arbitrary sized payloads to be streamed into server memory, creating an unauthenticated memory exhaustion Denial-of-Service vector.
- **Root Cause Analysis:** No ingress middleware checked `Content-Length` or buffered body sizes against a defined threshold.
- **Exploitability & Impact:** Unauthenticated clients could transmit 100MB+ HTTP bodies, exhausting server RAM and degrading gateway availability.
- **Remediation:** Implemented `request_size_limit_middleware` in `app/main.py` validating `Content-Length` against `settings.MAX_REQUEST_BODY_BYTES` (default 10MB) and returning `413 Payload Too Large`.
- **Regression Test:** `tests/security/test_ingress_and_input_validation.py::test_ingress_request_body_size_limit_enforced`

---

### FINDING-04: Missing Login Brute-Force Rate Limiting
- **Finding ID:** `FINDING-04`
- **Severity:** Medium (CVSS 5.9)
- **Component:** Authentication Router (`app/api/v1/endpoints/auth.py`)
- **STRIDE Category:** Spoofing / Repudiation
- **Description:** The `/api/v1/auth/login` endpoint had no IP or account-level rate limiter on failed attempts, permitting high-frequency credential guessing.
- **Root Cause Analysis:** Absence of brute-force prevention middleware or tracking on authentication failures.
- **Exploitability & Impact:** Malicious actors could mount dictionary attacks against analyst or admin email addresses.
- **Remediation:** Implemented an in-memory sliding-window failure tracker (`_failed_login_attempts`) that tracks failed login attempts by composite key `(client_ip, email)`. If 10 failures occur within a 60-second window, subsequent requests are rejected with `429 Too Many Requests`.
- **Regression Test:** `tests/security/test_authentication_security.py::test_login_rate_limiting_brute_force_blocked`

---

### FINDING-05: Missing Defense-in-Depth Security Headers
- **Finding ID:** `FINDING-05`
- **Severity:** Low (CVSS 3.7)
- **Component:** Ingress Middleware (`app/main.py`)
- **STRIDE Category:** Information Disclosure / Tampering
- **Description:** API responses lacked standard HTTP security headers such as `Strict-Transport-Security` (HSTS) and `Content-Security-Policy` (CSP).
- **Root Cause Analysis:** Headers middleware only set basic CORS headers and request IDs.
- **Exploitability & Impact:** Increased susceptibility to clickjacking or protocol downgrade attacks when accessed in browser environments.
- **Remediation:** Added `Strict-Transport-Security: max-age=31536000; includeSubDomains` and `Content-Security-Policy: default-src 'none'; frame-ancestors 'none'` to all responses via middleware in `app/main.py`.
- **Regression Test:** `tests/security/test_ingress_and_input_validation.py::test_security_headers_present`

---

### FINDING-06: Unbounded Pagination on Registry Endpoints (Memory Exhaustion)
- **Finding ID:** `FINDING-06`
- **Severity:** Low (CVSS 3.5)
- **Component:** Agent & Tool Endpoints (`app/api/v1/endpoints/agents.py`, `tools.py`)
- **STRIDE Category:** Denial of Service
- **Description:** Listing endpoints for agents and tools accepted unconstrained queries without maximum `limit` guardrails, allowing a caller to request arbitrarily large result sets.
- **Root Cause Analysis:** `limit` parameters were unbounded or defaulted without maximum bounds checks.
- **Exploitability & Impact:** In organizations with thousands of agents or tools, single requests could generate heavy database queries and memory pressure.
- **Remediation:** Added Pydantic/FastAPI `Query(50, ge=1, le=100)` constraints to `list_agents_endpoint` and `list_tools_endpoint`.
- **Regression Test:** `tests/security/test_ingress_and_input_validation.py::test_pagination_limit_cap_enforced`

---

### FINDING-07: Webhook Signature Future Timestamp Drift
- **Finding ID:** `FINDING-07`
- **Severity:** Low (CVSS 3.1)
- **Component:** Webhook Security (`app/services/integrations/crypto.py`, SDK `custode.security.webhooks`)
- **STRIDE Category:** Tampering / Repudiation
- **Description:** Webhook signature verification verified that timestamps were not older than the tolerance window (300 seconds), but did not reject timestamps set far in the future.
- **Root Cause Analysis:** Tolerance check only checked `abs(now - ts) > tolerance` or `now - ts > tolerance`.
- **Exploitability & Impact:** Signatures crafted with future timestamps could remain valid indefinitely until the future window arrived.
- **Remediation:** Hardened signature verifier in both backend and Python SDK to explicitly reject any timestamp with future drift greater than 60 seconds (`drift > 60` returns False / raises `WebhookVerificationError`).
- **Regression Test:** `tests/security/test_webhooks_and_ssrf_redteam.py::test_webhook_future_timestamp_rejected`

---

### FINDING-08: Cross-Tenant RuntimeAction Access via Direct URL Path (IDOR)
- **Finding ID:** `FINDING-08`
- **Severity:** High (CVSS 7.5)
- **Component:** RuntimeAction Router (`app/api/v1/endpoints/runtime_actions.py`)
- **STRIDE Category:** Elevation of Privilege / Information Disclosure
- **Description:** `get_runtime_action_endpoint` and `list_runtime_actions_endpoint` did not enforce organization membership validation when user credentials (`X-User-ID` or JWT) were provided, allowing a user from Tenant A to inspect RuntimeActions in Tenant B if they knew Tenant B's organization ID.
- **Root Cause Analysis:** Missing `validate_tenant_access` dependency injection on `runtime_actions.py` endpoints.
- **Exploitability & Impact:** Cross-tenant information disclosure of agent actions, parameters, and execution telemetry.
- **Remediation:** Added `validate_tenant_access` dependency to `get_runtime_action_endpoint`, `list_runtime_actions_endpoint`, and `transition_runtime_action_endpoint`, ensuring that any caller providing user credentials must hold an active membership in the target organization (`403 Forbidden` if not).
- **Regression Test:** `tests/security/test_tenant_isolation_redteam.py::test_cross_tenant_runtime_action_idor_blocked`

---

## 4. Hardening Summary

| Area | Before Milestone 22 | After Milestone 22 Hardening |
|---|---|---|
| **Human Approval Workflow** | Unlocked read-then-write; potential double-approval race. | Row-level locking (`with_for_update()`) + atomic status transition check (`409 Conflict`). |
| **Controlled Execution** | Replay check without table lock; potential race. | Pessimistic locking on `RuntimeAction` row + dual `succeeded`/`running` guard. |
| **Ingress HTTP Bodies** | Unconstrained payload stream. | 10MB default global cap with `413 Payload Too Large`. |
| **Authentication Defense** | Unthrottled login attempts. | Sliding-window limiter (10 failures / 60s per IP+email -> `429 Too Many Requests`). |
| **Security Headers** | Basic CORS & X-Request-ID only. | Added `Strict-Transport-Security` and `Content-Security-Policy`. |
| **API Pagination** | Unbounded result query parameters. | Strict `ge=1, le=100` constraints on agent/tool listings. |
| **Webhook Delivery** | Only historical timestamp tolerance enforced. | Rejection of future drift (>60s) in both backend and SDK. |
| **RuntimeAction Multi-Tenancy** | Organization path checked against record, but caller membership unenforced on reads. | Full `validate_tenant_access` dependency enforcing active organization membership. |

---

## 5. Security Regression Test Suite

All security hardening measures are verified continuously by the dedicated test suite:
`custode/backend/tests/security/`

| Test File | Tests | Focus Area |
|---|---|---|
| `test_authentication_security.py` | 7 | JWT tampering, expired tokens, agent/user credential separation, login brute force rate limiting |
| `test_approval_execution_concurrency.py` | 2 | Execution replay prevention, double-approval state-machine enforcement |
| `test_ingress_and_input_validation.py` | 3 | Ingress body size limit (413), security response headers, pagination bounds (422) |
| `test_webhooks_and_ssrf_redteam.py` | 4 | Webhook HMAC verification, secret masking, future timestamp drift rejection, SSRF loopback blocking |
| `test_tenant_isolation_redteam.py` | 3 | Cross-tenant RuntimeAction IDOR, integration IDOR, foreign agent execution rejection |
| `test_rbac_privilege_escalation.py` | 2 | Organization role privilege escalation, suspended member rejection |
| `test_llm_and_mcp_redteam.py` | 4 | Prompt injection detection, unauthorized MCP tool-call blocking, high-risk MCP governance |
| `test_behavioral_evasion.py` | 2 | Rapid action bursts, off-hours anomaly detection |
| **Total Security Tests** | **27** | **All 27 Passed (100% Pass Rate)** |

---

## 6. Full Platform Regression Verification

| Component | Target Baseline | Milestone 22 Result | Status |
|---|---|---|---|
| **Backend Core Tests** | 191 passed | 218 passed (191 core + 27 security) | **PASS** |
| **Frontend Unit Tests** | 19 passed | 19 passed | **PASS** |
| **Frontend Production Build** | Vite Build PASS | `tsc && vite build` PASS | **PASS** |
| **Python SDK Tests** | 39 passed | 39 passed | **PASS** |
| **Docker Compose Config** | Valid syntax | `docker compose config` PASS | **PASS** |
| **Sentinel AI Isolation** | Clean working tree | 100% isolated, 0 modifications | **PASS** |

---

## 7. Residual Risks & Future Recommendations

1. **Distributed Rate Limiting (Redis-Backed):**
   - *Current State:* Login rate limiting and anomaly burst windows currently operate with in-memory state suitable for single-instance deployments.
   - *Recommendation:* When scaling out horizontally behind a load balancer, migrate the rate-limiting storage backend to Redis.
2. **mTLS for MCP Servers:**
   - *Current State:* MCP servers are communicated with via secure HTTP/SSE with bearer authentication and egress SSRF validation.
   - *Recommendation:* Introduce optional mutual TLS (mTLS) for enterprise on-premise MCP server deployments in Milestone 23/24.
3. **Database Audit Log WORM Storage:**
   - *Current State:* Audit logs are append-only with cryptographic HMAC event digests stored in PostgreSQL.
   - *Recommendation:* Stream audit records to immutable cloud object storage (e.g., AWS S3 Object Lock) for long-term forensic compliance.

---
*Report certified by CUSTODE Defensive Security Engineering.*
