# CUSTODE Security Architecture & Threat Boundaries

## 1. Trust Boundaries

```text
[ Untrusted External Network ]
             |
       (Boundary 1: Ingress Boundary)
             v
+-------------------------------------------------------+
|  Edge Security (Nginx Reverse Proxy)                  |
|  - TLS 1.3 Termination                                |
|  - Rate Limiting & Ingress Body Inspection            |
+-------------------------------------------------------+
             |
       (Boundary 2: Authentication Boundary)
             v
+-------------------------------------------------------+
|  CUSTODE Application Core                             |
|  - Agent Token Auth (`cst_...`)                       |
|  - Human User JWT Auth                                |
|  - Tenant Scoping & RBAC Enforcement                  |
|                                                       |
|       (Boundary 3: Model & Integration Boundaries)     |
|       - LLM Gateway Firewall (Prompt / Output Filters)|
|       - MCP Security Boundary (Schema Drift & SSRF)   |
|       - Webhook Delivery Boundary (HMAC Signatures)   |
+-------------------------------------------------------+
             |
       (Boundary 4: Execution Boundary)
             v
+-------------------------------------------------------+
|  Controlled Execution Runtime                         |
|  - No `eval`, `exec`, or arbitrary subprocess calls   |
|  - Allowlisted handler registry                       |
|  - Row-level lock concurrency & replay defense        |
+-------------------------------------------------------+
             |
       (Boundary 5: Data Storage Boundary)
             v
+-------------------------------------------------------+
|  PostgreSQL 16 & Audit Log Store                      |
|  - Tamper-resistant append-only audit events          |
|  - SHA-256 cryptographic audit digests                |
+-------------------------------------------------------+
```

---

## 2. Core Security Invariants

The CUSTODE architecture enforces twelve inviolable security invariants:

1. **Strict Multi-Tenant Isolation:** Every database query, state transition, and API endpoint must filter on `organization_id`. Cross-tenant resource retrieval or mutation is blocked with HTTP 403 or HTTP 404.
2. **Fail-Secure Defaults:** If policy evaluation times out, an unhandled exception occurs, or permissions are absent, the decision defaults to `DENY` or `REQUIRE_APPROVAL`—never `ALLOW`.
3. **No Dynamic Execution:** Dynamic code evaluation (`eval`, `exec`, `os.system`, `subprocess.Popen`) is prohibited within the execution engine. Tools map to pre-compiled static Python handler routines.
4. **Row-Level Lock Replay Protection:** RuntimeActions and Approvals must be locked with `SELECT FOR UPDATE` before executing state transitions, preventing race conditions and replay attacks.
5. **Separation of Credentials:** Agent API keys cannot be used to authenticate human administrative endpoints, and human JWT tokens cannot authenticate agent runtime actions.
6. **No Plaintext Secret Persistence:** Agent API key secrets are hashed with SHA-256 before storage; raw tokens are displayed only once upon generation and never returned in listing APIs.
7. **SSRF Egress Defense:** Both outbound webhook deliveries and MCP server connections validate destinations against an RFC 1918 / private IP filter, blocking loopback (`127.0.0.1`), link-local (`169.254.169.254`), and private cloud metadata endpoints.
8. **Tamper-Resistant Audit Trail:** Audit log entries are strictly append-only. Each record contains an HMAC/SHA-256 digest computed across the event payload, actor, timestamp, and request ID.
9. **Prompt & Tool-Call Firewalls:** All LLM inputs are scanned for prompt injection and token overflows; LLM responses are analyzed for credential exfiltration before being returned to agents.
10. **Canonical MCP Schema Integrity:** MCP tool and resource definitions are fingerprinted with SHA-256 hashes upon registration; any drift or modification dynamically invalidates the tool.
11. **Webhook Replay Protection:** Webhook signatures are computed via HMAC-SHA256 over timestamp and body. Deliveries reject timestamps older than 300 seconds or drifting more than 60 seconds into the future.
12. **Defense-in-Depth Observability:** Operational health endpoints (`/health/live`, `/health/ready`, `/health/metrics`) and structured logs scrub all credentials and never expose stack traces or passwords.
