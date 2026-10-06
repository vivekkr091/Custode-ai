# CUSTODE — AI Agent Security & Control Plane

[![Release Candidate](https://img.shields.io/badge/release-v0.1.0--rc1-blue.svg)](docs/release/release-notes.md)
[![Python Tests](https://img.shields.io/badge/backend%20tests-230%20passed-success.svg)](backend/tests/)
[![Security Tests](https://img.shields.io/badge/security%20tests-39%20passed-success.svg)](backend/tests/security/)
[![Frontend Tests](https://img.shields.io/badge/frontend%20tests-19%20passed-success.svg)](frontend/)
[![SDK Tests](https://img.shields.io/badge/sdk%20tests-39%20passed-success.svg)](sdk/python/tests/)

> **CUSTODE** (*Italian for "Guardian" / "Custodian"*) is a security-first AI Agent Security & Control Plane that sits as an intelligent control barrier between autonomous AI agents and the sensitive tools, internal APIs, databases, filesystems, and MCP servers they access.

---

## 1. What is CUSTODE?

As autonomous AI agents are granted access to databases, cloud infrastructures, financial APIs, and MCP (Model Context Protocol) capabilities, organizations face severe security and authorization challenges:
- Prompt injections hijacking agent execution paths
- Tool misuse and unauthorized API operations
- Overprivileged agent identities lacking least-privilege constraints
- High-risk operations executed without human governance
- Lack of immutable forensic logs and attribution

**CUSTODE** solves this by enforcing an authoritative security kernel between AI agents and external capabilities. Every action an agent attempts is authenticated, evaluated against least-privilege permissions, contextual policy guardrails, behavioral baselines, and inline security scanners before controlled execution.

---

## 2. Core Architectural Capabilities

1. **Agent Identity & Authentication**: First-class agent identities, environment tiers (`development`, `staging`, `production`), and cryptographic credential hashing (SHA-256 tokens).
2. **Granular Capabilities & Operations**: Strict whitelist registry for tools and discrete operations, mapped to baseline risk levels (`low`, `medium`, `high`, `critical`).
3. **Permission Engine**: Least-privilege authorization evaluating explicit `allow` and `deny` grants per agent, tool, operation, and environment.
4. **Policy Engine & Versioning**: Multi-rule contextual guardrails (e.g. monetary thresholds, temporal rules, IP restrictions) with immutable versioning and atomic publication.
5. **Contextual Risk Assessment**: Multi-factor operational risk scoring combining baseline operation risk, parameter sensitivity, behavioral anomalies, and security findings.
6. **Decision Engine & Precedence Hierarchy**: Authoritative arbitration enforcing mathematical precedence:
   $$\text{DENY} \succ \text{REQUIRE\_APPROVAL} \succ \text{ALLOW}$$
7. **Human Governance Approval Workflow**: Asynchronous approval inbox for high-risk operations with reviewer authorization, lifecycle state transitions, and real-time security revalidation before execution.
8. **Controlled Execution Layer**: Zero arbitrary shell, eval(), exec(), or unsanitized subprocesses. Deterministic handler dispatch guarded by fail-closed execution guards.
9. **Tamper-Evident Audit & Forensic Timeline**: Immutable event stream with RFC 4122 `X-Request-ID` correlation across all lifecycle stages, secret sanitization, and deep investigation search.
10. **Sentinel Scanner Integration**: Clean adapter boundary integrating inline security scanners for prompt injection, secret leakage, and malicious payloads.
11. **LLM Security Gateway**: Bidirectional input/output firewall detecting prompt injections and intercepting egress data leaks.
12. **MCP Security Proxy**: Model Context Protocol security layer enforcing canonical tool schema hash validation, drift detection, dangerous URI scheme restrictions, and SSRF prevention.
13. **Behavioral Anomaly Detection**: Agent baselining and statistical anomaly detection flagging unexpected tool usage, rapid action frequency, and off-hours execution.
14. **Integrations & Webhook Delivery**: Organization-scoped external integrations with HMAC-SHA256 signature verification, replay protection, and exponential backoff retry policies.
15. **Production Python SDK (`custode-sdk`)**: Typed Python client providing synchronous and asynchronous agent security bindings, runtime action submission, and policy evaluation interfaces.

---

## 3. Runtime Evaluation Pipeline

Every action submitted by an AI agent traverses CUSTODE's authoritative control plane:

```
                      +-----------------------------+
                      |       Autonomous Agent      |
                      +--------------+--------------+
                                     |
                                     v
                       [ 1. RuntimeAction Created ]
                                     |
                                     v
                       [ 2. Permission Engine ]
                                     |
                                     v
                       [ 3. Policy & Risk Engine ]
                                     |
                                     v
                       [ 4. Decision Arbitration ]
                                     |
             +-----------------------+-----------------------+
             |                       |                       |
       [ ALLOW ]            [ REQUIRE_APPROVAL ]          [ BLOCK ]
             |                       |                       |
     (Direct Dispatch)       (Human Approval Inbox)     (Execution Guard)
             |                       |                       |
      Auto-Executed           Admin Reviews           Blocked & Audited
      (Status: SUCCEEDED)     & Authorizes            (Status: BLOCKED)
```

---

## 4. Repository Structure

```
custode/
├── backend/                  # FastAPI backend service
│   ├── alembic/              # Alembic database migration scripts (0001-0018)
│   ├── app/
│   │   ├── api/              # API route definitions (v1 endpoints)
│   │   ├── core/             # Configuration, settings, and cryptography
│   │   ├── db/               # SQLAlchemy async models & session factory
│   │   ├── engines/          # Permission, Policy, Risk, Decision, & Behavior engines
│   │   ├── llm/              # LLM security gateway & egress sanitization
│   │   ├── mcp/              # Model Context Protocol security inspection
│   │   ├── runtime/          # Controlled execution layer & safe handlers
│   │   ├── sentinel/         # Clean adapter boundary to Sentinel scanners
│   │   ├── services/         # Core business logic & integrations
│   │   └── main.py           # Application entrypoint & middleware
│   ├── scripts/              # Migration, seed, reset, and backup utilities
│   ├── tests/                # 230 unit, integration, and security tests
│   └── requirements.txt      # Backend Python dependencies
├── frontend/                 # React 18 + TypeScript + Vite console
│   ├── src/
│   │   ├── api/              # Typed REST client modules & demo seeder
│   │   ├── components/       # UI layout, tables, modals, badges, and controls
│   │   ├── context/          # Multi-tenant Auth and Organization state
│   │   ├── pages/            # Console views for agents, tools, policies, approvals, audit
│   │   └── router/           # Client-side routing
│   └── package.json          # Frontend dependencies & scripts
├── sdk/
│   └── python/               # Production Python SDK (custode-sdk)
│       ├── src/custode/      # SDK source (client, resources, models, transport)
│       └── tests/            # 39 SDK unit and security tests
├── docker/                   # Container orchestration files
│   ├── Dockerfile.backend    # Hardened non-root Python container
│   ├── Dockerfile.frontend   # Multi-stage Nginx static build
│   └── nginx.conf            # Reverse proxy configuration
├── docs/                     # Architectural, security, deployment & release documentation
│   ├── architecture/         # System architecture & invariants
│   ├── demo/                 # Demo walkthrough, presenter script, & validation report
│   ├── deployment/           # Production deployment & operations guides
│   ├── release/              # Release notes & readiness reports
│   └── security/             # Threat model, red team reports, & hardening specs
├── scripts/                  # Root CLI wrappers for seeding and testing
├── docker-compose.yml        # Local development compose stack
├── docker-compose.prod.yml   # Production compose stack with resource constraints
├── .env.example              # Environment variables template
└── README.md                 # Primary platform documentation
```

---

## 5. Quick Start & Local Development

### Prerequisites
- Python 3.11+
- Node.js 18+
- SQLite or PostgreSQL

### 1. Backend Setup
```bash
cd backend

# Create and activate virtual environment
python3 -m venv .venv
source .venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Run database migrations
python scripts/migrate.py

# Start backend server
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```
API Documentation: [http://localhost:8000/docs](http://localhost:8000/docs)

### 2. Frontend Setup
```bash
cd frontend

# Install dependencies
npm install

# Start Vite development server
npm run dev
```
Web Console: [http://localhost:5173](http://localhost:5173)

### 3. Containerized Run (Docker Compose)
```bash
# Copy environment configuration
cp .env.example .env

# Launch multi-container stack
docker compose -f docker/docker-compose.yml up --build
```

---

## 6. Demonstration & Showcase

CUSTODE includes an idempotent synthetic scenario (**Acme Travel AI**) demonstrating the complete agent action lifecycle:

```bash
# Seed the demonstration environment
python scripts/seed_demo.py

# Reset demonstration data safely (refuses in production)
python scripts/reset_demo.py --yes
```

### Demonstration Scenarios:
1. **Scenario A (Allowed Action):** `Travel Assistant Agent` queries `search_available_rooms` $\rightarrow$ Low risk, valid permission $\rightarrow$ **ALLOW** $\rightarrow$ Status: **SUCCEEDED**.
2. **Scenario B (Blocked Action):** Agent attempts `cancel_booking` $\rightarrow$ Permission denied $\rightarrow$ **BLOCK** $\rightarrow$ Status: **BLOCKED BY GUARD** (downstream API never called).
3. **Scenario C (Human Governance):** Agent attempts $1,250 hotel reservation $\rightarrow$ High risk, triggers `High-Value Booking Guardrail` $\rightarrow$ **REQUIRE_APPROVAL** $\rightarrow$ Queued in Approval Inbox $\rightarrow$ Admin approves $\rightarrow$ Controlled execution **SUCCEEDED**.

Consult the [Demo Walkthrough](docs/demo/demo-walkthrough.md) and [Presenter Script](docs/demo/presenter-script.md) for full details.

---

## 7. Verification & Automated Test Suites

All components are covered by rigorous automated tests:

```bash
# Backend unit and integration tests (230 tests)
cd backend && .venv/bin/pytest tests/

# Security red team and defensive hardening tests (39 tests)
cd backend && .venv/bin/pytest tests/security/

# Frontend integration tests (19 tests) & production build
cd frontend && npm test && npm run build

# Python SDK test suite (39 tests)
cd sdk/python && PYTHONPATH=src pytest tests/
```

**Overall Test Results:** 327 passing automated tests, 0 failures, 100% test pass rate.

---

## 8. Release Information & Limitations

- **Current Release Candidate:** `v0.1.0-rc1`
- **Known Limitations:**
  - In-process evaluation engines are optimized for single-cluster control planes; distributed multi-region quorum consensus is scheduled for v0.2.
  - Native integrations currently provide provider-neutral webhooks and HTTP endpoints; managed cloud provider connectors (AWS EventBridge, GCP Pub/Sub) are slated for subsequent releases.
- **Reference Repository Isolation:** CUSTODE operates independently of reference projects; all scanning adapters maintain decoupled interfaces.

---

## 9. Security & Reporting

To report security vulnerabilities or consult defensive hardening specifications, refer to [docs/security/](docs/security/).

---

## 10. License

Apache 2.0. See [LICENSE](LICENSE) for details.
