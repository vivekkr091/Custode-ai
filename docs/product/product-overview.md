# CUSTODE Product Overview

## 1. Product Mission & Philosophy

**CUSTODE** is a security-first AI Agent Security & Control Plane designed to govern, inspect, monitor, and enforce authorization policies on autonomous AI agents, tool invocations, and Large Language Model (LLM) operations.

In modern enterprises, autonomous AI agents operate with high autonomy—executing SQL queries, writing code, dispatching webhooks, and accessing Model Context Protocol (MCP) servers. Without a centralized control plane, agents introduce critical risks including prompt injection, unauthorized tool execution, data exfiltration, privilege escalation, and unintended side-effects.

CUSTODE acts as an inline security boundary between agents, models, and external tools:
- **Zero Trust by Default:** No agent operation executes without explicit permission, policy evaluation, risk assessment, and decision gating.
- **Fail-Secure Architecture:** Ambiguities, errors, timeouts, or policy conflicts default to `DENY` or `REQUIRE_APPROVAL`—never silent permission grants.
- **Human-in-the-Loop Governance:** High-risk actions automatically trigger structured human review workflows with cryptographic decision snapshots.
- **Tamper-Resistant Forensic Audit:** Every action, decision, approval, scan, and anomaly is logged to append-only audit storage with SHA-256 integrity digests.

---

## 2. Core Capabilities Matrix

| Subsystem | Functionality | Key Entities |
|---|---|---|
| **Identity & Access** | Multi-tenant organization scoping, agent credential management (`cst_...` API keys), role-based access control (Admin, Security Analyst, Developer, Viewer). | `Organization`, `User`, `Membership`, `Agent`, `AgentCredential` |
| **Tool & Operation Registry** | Canonical registry of approved tools and operations categorized by risk level (`LOW`, `MEDIUM`, `HIGH`, `CRITICAL`) and environment (`development`, `staging`, `production`). | `Tool`, `ToolOperation` |
| **Permission Engine** | Deterministic agent-to-tool-operation grants with explicit `ALLOW` or `DENY` effects and environment scoping. | `Permission` |
| **Policy Engine** | Version-controlled declarative rule engine evaluating contextual action parameters (e.g., amount, IP address, time of day, anomalous score). | `Policy`, `PolicyVersion` |
| **Contextual Risk Engine** | Dynamic risk scoring combining base operation risk, parameter bounds, environment severity, and behavioral anomaly telemetry. | `RiskAssessment` |
| **Decision Engine** | Precedence-based decisioning: `DENY` > `REQUIRE_APPROVAL` > `ALLOW`. Generates authoritative execution mandates. | `Decision` |
| **Human Approval Workflow** | Multi-role reviewer workflow (Admin/Security Analyst) with state-machine governance, expiration timeouts, and re-evaluation defenses. | `ApprovalRequest` |
| **Controlled Execution** | Isolated runtime dispatcher executing approved tools with replay prevention, row-level locks, and strict handler allowlists. Dynamic code execution (`eval`/`exec`) is strictly forbidden. | `Execution` |
| **Sentinel Scanner Integration** | Deep static and dynamic security scanning analyzing prompts and tool inputs for prompt injection, secret leakage, and malicious payload patterns. | `SecurityScan`, `SecurityFinding` |
| **LLM Security Gateway** | Model-agnostic reverse-proxy firewalling prompt inputs, sanitizing output completions, and intercepting model tool calls. | `LLMInteraction` |
| **MCP Security Layer** | Untrusted integration boundary for Model Context Protocol servers; validates schemas, detects configuration drift, prevents SSRF, and audits prompt/resource access. | `MCPServer`, `MCPTool` |
| **Behavioral Anomaly Detection** | Deterministic statistical anomaly engine establishing baseline profiles (action velocity, tool transitions, off-hours activity, error rates). | `AgentBehaviorBaseline`, `BehavioralAnomaly` |
| **Integrations & Webhooks** | Outbound HMAC-SHA256 signed event webhooks delivering audit telemetry to SIEMs and alerting endpoints with replay and SSRF defenses. | `Integration`, `WebhookDelivery` |
| **Python Agent Security SDK** | Typed, production-grade Python library (`custode-sdk`) providing synchronous and asynchronous bindings for external agent frameworks. | `CustodeClient`, `AsyncCustodeClient` |
