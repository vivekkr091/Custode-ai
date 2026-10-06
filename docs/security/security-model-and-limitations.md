# CUSTODE Security Model & Limitations

## 1. Security Architecture Summary

CUSTODE operates under a strict Zero Trust model for autonomous AI agents. The platform assumes:
- Agents are semi-trusted or untrusted runtime actors that may experience prompt injection, jailbreaking, or logic bugs.
- Model Context Protocol (MCP) servers are untrusted third-party services capable of returning adversarial schema definitions or internal SSRF targets.
- Controlled tool executions must be deterministic, non-arbitrary, idempotent, and protected by pessimistic database concurrency locks.

---

## 2. Invariants & Defensive Controls

1. **Deterministic Precedence:**
   Policy rules and decisions are strictly deterministic: `DENY` always overrides `REQUIRE_APPROVAL`, which always overrides `ALLOW`.
2. **Row-Level Lock Concurrency:**
   Approval state transitions and controlled execution triggers employ `SELECT ... FOR UPDATE` row locks, preventing race conditions or double-action execution replays.
3. **No Dynamic Execution:**
   The execution sandbox completely prohibits dynamic interpreter evaluation (`eval`, `exec`, `os.system`).
4. **Credential Hashing:**
   Agent API keys are stored as cryptographic SHA-256 digests. Raw keys are ephemeral and never returned after creation.
5. **SSRF & Private IP Filtering:**
   Outbound webhook dispatches and MCP server endpoints reject loopback, link-local, and RFC 1918 private subnets.

---

## 3. Known Limitations & Residual Risks

1. **In-Memory Rate Limiting:**
   - *Current State:* Login rate limiting and anomaly burst windows operate in single-node memory.
   - *Production Implication:* In distributed multi-replica deployments behind an external load balancer, an external Redis cache is recommended.
2. **Synchronous MCP Gateway Latency:**
   - *Current State:* Tool call scanning and schema fingerprinting occur synchronously inline with agent requests.
   - *Production Implication:* Highly loaded MCP backends may introduce latency; caching canonical tool schemas mitigates this.
3. **Local Database Volume Defaults:**
   - *Current State:* Production docker-compose defaults to a local named Docker volume for PostgreSQL.
   - *Production Implication:* Enterprise deployments should target managed database services (e.g. AWS RDS Aurora) with automated replication.
