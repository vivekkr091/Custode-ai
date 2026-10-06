# CUSTODE System Architecture

## 1. High-Level System Architecture

CUSTODE is structured as a decoupled, multi-tiered control plane. The diagram below illustrates how an external agent interaction flows through the platform:

```text
                             AGENT / APPLICATION
                                      |
                         (REST / Python SDK / Webhook)
                                      v
+===========================================================================+
|                         CUSTODE CONTROL PLANE                             |
|                                                                           |
|   +-------------------------------------------------------------------+   |
|   |                        1. Ingress & Auth                          |   |
|   |   - TLS Termination (Reverse Proxy)                               |   |
|   |   - Rate Limiting (50 r/s) & Request Body Filter (10 MB)          |   |
|   |   - Agent Credential (`cst_...`) or User JWT Authentication       |   |
|   |   - Strict Multi-Tenant Organization Scoping                      |   |
|   +-------------------------------------------------------------------+   |
|                                     |                                     |
|                                     v                                     |
|   +-------------------------------------------------------------------+   |
|   |                   2. Canonical RuntimeAction                      |   |
|   |   - Input Parameter Normalization & Hashing                       |   |
|   |   - Target Environment & Resource Resolution                      |   |
|   +-------------------------------------------------------------------+   |
|                                     |                                     |
|           +-------------------------+-------------------------+           |
|           |                         |                         |           |
|           v                         v                         v           |
|   +---------------+         +---------------+         +---------------+   |
|   |  Permissions  |         | Policies &    |         | Sentinel Scan |   |
|   |  Evaluation   |         | Version Rules |         | Engine        |   |
|   +---------------+         +---------------+         +---------------+   |
|           |                         |                         |           |
|           +-------------------------+-------------------------+           |
|                                     |                                     |
|                                     v                                     |
|   +-------------------------------------------------------------------+   |
|   |                  3. Contextual Risk Assessment                    |   |
|   |   - Operation Base Risk + Param Scoring + Behavioral Telemetry    |   |
|   +-------------------------------------------------------------------+   |
|                                     |                                     |
|                                     v                                     |
|   +-------------------------------------------------------------------+   |
|   |                       4. Decision Engine                          |   |
|   |            Precedence: DENY > REQUIRE_APPROVAL > ALLOW            |   |
|   +-------------------------------------------------------------------+   |
|               /                      |                      \             |
|              v                       v                       v            |
|          [ ALLOW ]          [ REQUIRE_APPROVAL ]          [ DENY ]        |
|              |                       |                       |            |
|              |                       v                       |            |
|              |             +-------------------+             |            |
|              |             |  Human Reviewer   |             |            |
|              |             |  Approval Workflow|             |            |
|              |             +-------------------+             |            |
|              |                       |                       |            |
|              |                       v                       |            |
|              |             (Approved or Rejected)            |            |
|              |                       |                       |            |
|              v                       v                       v            |
|   +-------------------------------------------------------------------+   |
|   |                     5. Controlled Execution                       |   |
|   |   - Pessimistic Row Lock (`with_for_update()`)                    |   |
|   |   - Duplicate Execution & Replay Defense                          |   |
|   |   - Allowlisted Execution Handler Dispatch (No eval/exec)         |   |
|   +-------------------------------------------------------------------+   |
|                                     |                                     |
|                                     v                                     |
|   +-------------------------------------------------------------------+   |
|   |                 6. Audit & Webhook Delivery                       |   |
|   |   - Append-Only Forensic Audit Logging with SHA-256 Digest        |   |
|   |   - HMAC-SHA256 Signed Outbound Webhooks                          |   |
|   +-------------------------------------------------------------------+   |
+===========================================================================+
```

---

## 2. Component Subsystems

### Ingress & Authentication Layer
- **Reverse Proxy (Nginx):** Manages TLS termination, IP whitelisting, HTTP security headers, request body limits, and rate limiting.
- **FastAPI Core:** Provides asynchronous HTTP endpoints under `/api/v1` with typed Pydantic v2 schemas and dependency injection.
- **Identity Isolation:** Guarantees that users and agents cannot read or modify resources outside their authenticated `organization_id`.

### Policy & Evaluation Engines
- **Permission Engine:** Maps an `(agent_id, tool_id, operation_id, environment)` tuple to an authoritative grant (`ALLOW` or `DENY`).
- **Policy Engine:** Evaluates declarative, version-controlled rules against runtime action context fields (`action.amount`, `action.resource`, `context.time.hour`, `behavior.anomaly.score`).
- **Risk Engine:** Computes a composite risk score (0–100) and severity band (`LOW`, `MEDIUM`, `HIGH`, `CRITICAL`).
- **Decision Engine:** Strictly applies deterministic precedence:
  $$\text{Decision} = \text{DENY} \succ \text{REQUIRE\_APPROVAL} \succ \text{ALLOW}$$

### Human-in-the-Loop Governance
- Suspends execution when decisions mandate `REQUIRE_APPROVAL`.
- Notifies designated reviewers (`organization_admin` or `security_analyst`).
- Captures an immutable snapshot of the decision state at review time.
- Enforces atomic state transitions to prevent double-approval or approval-rejection races.

### Controlled Execution Sandbox
- Verifies that execution status is not already `succeeded` or `running`.
- Locks the `RuntimeAction` row using pessimistic database locking.
- Executes against a pre-registered handler allowlist (e.g. `internal:health_check`, `http:get`, `database:read`).
- Dynamically forbids code execution, arbitrary subprocess execution, and unsanitized command injection.
