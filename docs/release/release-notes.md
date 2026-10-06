# CUSTODE Release Notes — Version 0.1.0-rc1

**Release Date:** 2026-10-01  
**Release Tag:** `v0.1.0-rc1`  
**License:** Apache 2.0  

---

## 1. Release Summary

CUSTODE `v0.1.0-rc1` represents the initial release candidate of the CUSTODE AI Agent Security & Control Plane. This release establishes a hardened, enterprise-ready control plane for managing agent identity, permissions, versioned policies, contextual risk assessment, human approvals, controlled tool execution, LLM security gatewaying, MCP boundary protection, behavioral anomaly detection, and forensic audit observability.

---

## 2. Key Capabilities & Milestones Included

- **Milestones 1–4:** Core Organization & User Identity, Tenant Isolation, RBAC (Admin, Analyst, Dev, Viewer), and Agent Registry.
- **Milestones 5–8:** Tool & Operation Catalog, Granular Permissions Engine, Declarative Versioned Policies, and RuntimeAction Normalization.
- **Milestones 9–11:** Contextual Risk Engine, Precedence Decision Engine (`DENY` > `REQUIRE_APPROVAL` > `ALLOW`), and Human Approval Workflows.
- **Milestones 12–13:** Controlled Execution Runtime with Replay Prevention, Tamper-Resistant Audit Logging with SHA-256 digests.
- **Milestones 14–17:** Security Finding & Scan System, Sentinel Integration, LLM Security Gateway (prompt/output firewalls, tool-call containment).
- **Milestones 18–19:** Model Context Protocol (MCP) Security Layer (schema fingerprinting, SSRF defenses), Statistical Behavioral Anomaly Detection Engine.
- **Milestones 20–21:** Production Python Agent Security SDK (`custode-sdk`), Enterprise Webhook Delivery with HMAC-SHA256 replay defense.
- **Milestone 22:** Defensive Security Hardening & Red Team Assessment (Pessimistic row locking, login brute force limiter, 10MB ingress body cap, security headers).
- **Milestone 23:** Production Deployment & DevOps (Multi-stage non-root Dockerfiles, `docker-compose.prod.yml`, database migration & backup scripts, health/readiness probes).
- **Milestone 24:** End-to-end QA validation, documentation consolidation, and release readiness certification.

---

## 3. Package & Component Versions

- `custode-backend`: `0.1.0`
- `custode-frontend`: `0.1.0`
- `custode-sdk`: `0.1.0`
- Database Schema Revision: `0018_add_integrations_and_webhooks`

---

## 4. Known Limitations

- In-memory rate limiting for login attempts and anomaly windows (recommend external Redis for distributed clusters).
- Local volume defaults for PostgreSQL in Docker Compose (recommend managed cloud RDS for enterprise multi-AZ HA).
