# CUSTODE Platform Threat Model

## 1. Overview & Scope

This document defines the formal threat model for the **CUSTODE AI Agent Security & Control Platform** (Milestones 1–22). It establishes trust boundaries, identifies threat actors, enumerates assets, analyzes attack surfaces using the STRIDE methodology, and details both implemented defensive controls and accepted residual risks.

The scope of this threat model includes:
- **Backend API & Middleware** (FastAPI, SQLAlchemy, asyncpg, PostgreSQL).
- **Authentication & Authorization** (HS256 JWTs, Agent API Keys `cst_ag_...`, PBKDF2 credential hashing, RBAC).
- **Multi-Tenant Scoping & Resource Hierarchy** (Organization tenant boundaries, foreign key integrity).
- **Core Security Engines** (Permission Engine, Policy Engine, Contextual Risk Engine, Decision Engine).
- **Governance & Execution Guardrails** (Human Approvals, ExecutionGuard, Controlled Execution).
- **Audit & Forensic Observability** (Append-only audit logs, cryptographic content hashing, correlation IDs).
- **Security Scanners & Sentinel Adapter** (Static/dynamic security finding ingestion, risk arbitration).
- **LLM Security Gateway** (Prompt injection scanning, secret/PII redaction, tool-call containment).
- **MCP Security Layer** (Untrusted MCP server boundaries, schema hash drift detection, SSRF protection).
- **Behavioral & Anomaly Detection Engine** (Statistical/rule-based profiling, velocity/loop detection).
- **Integrations & Webhooks** (HMAC-SHA256 signed event delivery, SSRF defenses, replay protection).
- **Python Agent SDK** (`custode-sdk`, client-side bounds, receiver verification).
- **Frontend Dashboard** (React SPA, route guards, secret masking).

---

## 2. System Architecture & Trust Boundaries

```
[ UNTRUSTED ZONE: External Internet / AI Agents / LLM Providers / Webhook Receivers ]
                                    |
                            (1) HTTPS / TLS
                                    v
+-----------------------------------------------------------------------------------+
| TRUST BOUNDARY 1: Edge & Ingress (CORS, Rate Limiting, Request Size Middleware)   |
+-----------------------------------------------------------------------------------+
                                    |
                                (2) REST API
                                    v
+-----------------------------------------------------------------------------------+
| TRUST BOUNDARY 2: Authentication & Multi-Tenant RBAC Boundary                      |
| - Agent Auth (`cst_ag_...`) | User Auth (HS256 JWT) | Tenant Context Enforcement  |
+-----------------------------------------------------------------------------------+
                                    |
                                    v
+-----------------------------------------------------------------------------------+
| TRUST BOUNDARY 3: Authoritative Security Control Plane (CUSTODE Core)             |
| - Permission Engine   - Policy Engine        - Risk Engine                        |
| - Decision Engine     - Human Approvals      - ExecutionGuard                     |
| - Behavioral Engine   - Audit Log Service    - Sentinel Scanner Adapter           |
+-----------------------------------------------------------------------------------+
         |                                                 |
         | (3) Internal Storage                            | (4) Controlled Egress
         v                                                 v
+------------------------------------+   +------------------------------------------+
| TRUST BOUNDARY 4: Data Layer       |   | TRUST BOUNDARY 5: External Connectors    |
| - PostgreSQL (Row isolation, FKs)  |   | - LLM Providers (OpenAI, Anthropic, etc.)|
| - AES-GCM Encrypted Webhook Secrets|   | - MCP Servers (HTTP/SSE JSON-RPC)        |
| - PBKDF2 Password / Key Hashes     |   | - Customer Webhook Endpoints             |
+------------------------------------+   +------------------------------------------+
```

### Trust Boundary Definitions
1. **TB-1: Network Ingress**: Untrusted network boundary where external clients, agents, and browsers submit HTTP requests. Protected by body size limits, CORS origin allowlists, and request correlation IDs.
2. **TB-2: Authentication & Tenant Boundary**: Demarcates authenticated callers from unauthenticated requests, and strictly separates Organization A from Organization B. Enforces RBAC roles and prevents IDOR.
3. **TB-3: Core Security Control Plane**: The authoritative decision-making zone. Untrusted inputs (such as agent runtime parameters or LLM outputs) cannot bypass permission, policy, risk, or human approval gates.
4. **TB-4: Data Persistence**: Encrypted/hashed sensitive credentials at rest, database constraints, row locks, and tenant cascading rules.
5. **TB-5: Outbound Network Boundary**: Untrusted external endpoints (LLM providers, MCP servers, Webhook URLs). Protected by strict SSRF CIDR blocking, non-redirect policies, and HMAC signing.

---

## 3. Assets & Sensitivity Classification

| Asset ID | Asset Name | Description | Sensitivity | Security Invariant |
| :--- | :--- | :--- | :--- | :--- |
| **A-1** | User Passwords | PBKDF2-HMAC-SHA256 hashed credentials | Critical | Never stored or logged in plaintext. |
| **A-2** | Agent API Keys | `cst_ag_...` high-entropy tokens | Critical | Revealed once on creation; stored as PBKDF2 hashes. |
| **A-3** | Webhook Signing Secrets | `cst_whsec_...` HMAC keys | High | Revealed once; encrypted via AES-GCM; verified in constant-time. |
| **A-4** | JWT Access Tokens | Signed session credentials | High | Bound to user identity, expiration (exp), audience, and issuer. |
| **A-5** | Security Policies & Permissions | Access control rules | Critical | Strict deny-overrides; tenant-scoped; published versions immutable. |
| **A-6** | Decisions & Approvals | Authorization state machine | Critical | Atomic transitions with row locks; no double-approval or bypass. |
| **A-7** | Executions | Controlled action dispatches | Critical | Exactly-once or idempotent execution; no concurrent double execution. |
| **A-8** | Audit & Forensic Logs | Security event history | High | Append-only; sanitized metadata; correlation tracking. |
| **A-9** | LLM Prompts & Outputs | Context data passed to LLMs | Confidential | Content hashed; sensitive entities redacted; zero raw persistence. |
| **A-10**| MCP Tool Schemas | Remote server capabilities | Medium | Canonical SHA-256 hash verified to block schema drift. |

---

## 4. Threat Actors & Capabilities

1. **TA-1: Unauthenticated External Attacker**:
   - Capabilities: Network scans, credential stuffing, brute force on `/auth/login`, SSRF exploitation via webhooks or MCP endpoints, DoS via memory exhaustion or large payloads.
2. **TA-2: Malicious / Rogue Authenticated User (Insider)**:
   - Capabilities: Valid credentials in Organization A. Attempts privilege escalation (viewer to admin), horizontal tenant hopping (IDOR to access Org B resources), or self-approval of unauthorized actions.
3. **TA-3: Compromised or Prompt-Injected AI Agent**:
   - Capabilities: Possesses valid Agent API key. Attempts to execute dangerous tools, exceed financial thresholds, trigger prompt injection via LLM gateway, or evade behavioral anomaly baselines.
4. **TA-4: Untrusted Third-Party Provider / Server**:
   - Capabilities: Compromised MCP server returning malicious schemas or prompt injection payloads, or malicious webhook destination attempting DNS rebinding to access cloud metadata.

---

## 5. STRIDE Threat Analysis

### S — Spoofing
- **Threat S1: User Identity Spoofing via Tampered JWT**: Attacker crafts an unsigned or modified JWT (e.g. `alg: none`).
  - *Mitigation*: `decode_access_token` verifies HS256 HMAC signature using `AUTH_SECRET_KEY` in constant time before parsing payload. Explicitly rejects `alg != "HS256"`.
- **Threat S2: Agent Impersonating Human Admin**: Agent presenting `cst_ag_...` on user administrative endpoints.
  - *Mitigation*: `get_current_user` explicitly inspects token prefix and throws `401 Unauthorized` if an agent key is supplied.
- **Threat S3: Webhook Delivery Forgery**: Fake CUSTODE events delivered to customer webhook receiver.
  - *Mitigation*: Every outbound webhook includes `X-Custode-Signature: t={ts},v1={sig}` HMAC-SHA256 signature verified by the receiver using constant-time comparison.

### T — Tampering
- **Threat T1: Policy or Permission Manipulation**: Non-admin altering active security policies.
  - *Mitigation*: RBAC dependency `require_admin` restricts policy mutation; published policy versions are immutable (`PolicyVersionImmutableError`).
- **Threat T2: Approval State Tampering via Race Condition**: Concurrent approval and rejection requests racing to corrupt approval status.
  - *Mitigation*: Database row-level locking (`with_for_update()`) serializes approval state transitions and enforces state machine integrity.
- **Threat T3: MCP Schema Drift Attack**: Malicious server updates tool parameters post-registration to include dangerous actions.
  - *Mitigation*: MCP Gateway checks runtime tool parameters against the canonical SHA-256 schema hash recorded during initial registration (`MCPSchemaDriftError`).

### R — Repudiation
- **Threat R1: Denied Execution Repudiation**: Agent or reviewer denies initiating an action or granting an approval.
  - *Mitigation*: Authoritative `Execution` and `ApprovalRequest` models record actor UUID, timestamp, reviewer notes, and IP address. Append-only audit events record every security decision.
- **Threat R2: Webhook Delivery Dispute**: Customer disputes receiving security notifications.
  - *Mitigation*: `WebhookDelivery` and `WebhookAttempt` tables persist delivery timestamps, status codes, latency, and sanitized response summaries.

### I — Information Disclosure
- **Threat I1: Cross-Tenant Data Access (IDOR)**: Attacker in Org A queries `/organizations/OrgA/runtime-actions/{org_b_action_id}`.
  - *Mitigation*: All queries explicitly filter by `organization_id == current_organization_id`. Cross-tenant resource lookups return `404 Not Found` rather than leaking existence.
- **Threat I2: Credential Hash & Secret Leakage in APIs**: APIs returning password hashes, raw API keys, or webhook signing secrets.
  - *Mitigation*: Pydantic schemas omit sensitive hash columns. API keys and webhook signing secrets are returned strictly once during initial creation (`POST`), with only public prefixes stored for display.
- **Threat I3: LLM Prompt & Secret Leakage**: Raw user prompts containing API keys or PII stored in interaction logs.
  - *Mitigation*: LLM Gateway computes SHA-256 content hashes, runs regex redaction for secrets/PII, and avoids persisting raw prompts in database tables.

### E — Denial of Service
- **Threat E1: Large Payload Memory Exhaustion**: Attacker submits gigabyte-sized JSON payloads to exhaust server RAM.
  - *Mitigation*: Ingress middleware enforces a strict 10MB maximum request body limit (`Content-Length` inspection).
- **Threat E2: Authentication Brute Force**: Attacker floods `/auth/login` with thousands of password attempts.
  - *Mitigation*: In-memory sliding-window rate limiting throttles failed login attempts per IP and target email.
- **Threat E3: Webhook Delivery Queue Starvation / Loops**: An internal event triggers a webhook that generates another event in an infinite recursion.
  - *Mitigation*: Event taxonomy defines `DISALLOWED_DISPATCH_EVENTS` to prevent recursive delivery loops. Retries use bounded exponential backoff with jitter and terminal failure on 4xx status codes.

### E — Elevation of Privilege
- **Threat E4: Horizontal & Vertical Privilege Escalation**: A `viewer` or `developer` user calling administrative endpoints.
  - *Mitigation*: Backend RBAC dependencies (`require_admin`, `require_analyst_or_admin`) validate membership role against the requested organization on every privileged route.
- **Threat E5: Double Execution / Execution Replay**: Re-executing an approved action or racing two concurrent executions.
  - *Mitigation*: `ExecutionGuard` uses row-level locking on `RuntimeAction` and verifies that no execution is already `succeeded` or `running`.

---

## 6. Security Invariants Summary

1. **Authority Invariant**: CUSTODE backend is the single source of truth for all security decisions; client SDKs and frontends are untrusted.
2. **Notification Invariant**: Webhooks are asynchronous notifications and never influence, delay, or alter security decisions.
3. **Immutability Invariant**: Published policies, decisions, and audit events cannot be modified or deleted.
4. **Tenant Isolation Invariant**: No API call can access, mutate, or observe resources outside the caller's active organization membership.
5. **SSRF Invariant**: No outbound request (webhooks, MCP, LLM) can target private IP addresses, loopback, link-local, or cloud metadata endpoints.
6. **Execution Invariant**: An authorized action can execute at most once (`exactly-once` / idempotent).

---

## 7. Residual Risks & Accepted Constraints

| Risk ID | Description | Impact | Accepted Rationale / Operational Guidance |
| :--- | :--- | :--- | :--- |
| **RR-1** | Single-node in-memory rate limiting | Low | In multi-node deployments, rate limiting state should be shared via Redis. For current containerized single-host deployments, in-memory sliding-window is appropriate. |
| **RR-2** | Local SQLite for testing | Low | Production uses PostgreSQL 16+ with ACID row-level locking (`with_for_update()`). In SQLite testing environments, table-level locking provides equivalent serializability. |
| **RR-3** | External DNS resolution in production | Medium | In production, outbound webhooks must be routed through an egress proxy or firewall with DNS pinning to guarantee immunity against DNS rebinding. |
