# Changelog

All notable changes to the `custode-sdk` package will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.1.0] - 2026-10-01

### Added
- Milestone 20: Initial production release of `custode-sdk`.
- `CUSTODEClient` (synchronous) and `AsyncCUSTODEClient` (asynchronous) client implementations with HTTPX transport.
- Strongly-typed Pydantic domain models for AuthenticatedAgent, RuntimeAction, Decision, ApprovalRequest, Execution, LLM interaction, MCP tools/servers, SecurityFinding, and Audit records.
- Comprehensive resource interfaces:
  - `agents`: Identity validation and agent profile lookups.
  - `runtime_actions`: Create, retrieve, list, decide, and execute agent action requests.
  - `decisions`: Authorization decision arbitration, history retrieval, and status evaluation.
  - `approvals`: Human-in-the-loop governance inspection and cancellation.
  - `executions`: Controlled execution dispatching and history.
  - `llm`: Security gateway mediated chat, interaction history, and telemetry.
  - `mcp`: Model Context Protocol server/tool discovery, schema drift enforcement, and tool invocation.
  - `findings`: Sentinel vulnerability finding retrieval and threat metrics.
  - `audit`: Immutable cryptographic audit trail querying.
- RFC 4122 Request ID correlation (`X-Request-ID`) across sync and async transports.
- Strict security controls:
  - Localhost development HTTP whitelist (`http://localhost`, `http://127.0.0.1`, `http://0.0.0.0`).
  - Mandatory HTTPS for remote production hosts.
  - Automatic zero-leak secret masking for API keys in logs, representations, and exception traces.
  - Conservative retry mechanism for transient network timeouts on idempotent operations.
- Full context manager support (`with` and `async with`).
