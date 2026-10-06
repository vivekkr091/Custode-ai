# CUSTODE Python Agent Security SDK

Official production Python client library for the **CUSTODE AI Agent Security & Control Platform**.

The CUSTODE SDK enables external Python agents, multi-agent orchestrators (e.g. LangChain, LlamaIndex, Claude Agent SDK), and background services to communicate securely with the CUSTODE Control Plane.

---

## Core Principle

> **CUSTODE Backend is the authoritative source of truth.**
>
> Identity validation, permission evaluation, policy arbitration, contextual risk assessment, behavioral anomaly analysis, Sentinel security scanning, human approval governance, and controlled execution are executed on the CUSTODE backend. The SDK provides a typed, developer-friendly client layer for those capabilities without bypassing controls.

---

## Requirements

- Python 3.10+
- `httpx>=0.25.0`
- `pydantic>=2.0.0`

---

## Installation

```bash
pip install custode-sdk
```

Or for local development:

```bash
pip install -e custode/sdk/python/
```

---

## Configuration & Authentication

The SDK connects to CUSTODE using agent credentials (cryptographic API keys prefixed with `cst_ag_`).

### Environment Variables

| Variable | Description | Default |
| :--- | :--- | :--- |
| `CUSTODE_BASE_URL` | Base URL of the CUSTODE Control Plane | `http://localhost:8000` |
| `CUSTODE_AGENT_API_KEY` | Agent API credential token (`cst_ag_...`) | *Required* |
| `CUSTODE_ORGANIZATION_ID`| Target tenant UUID | Optional (auto-resolved via `verify_identity()`) |
| `CUSTODE_TIMEOUT` | Network request timeout in seconds | `30.0` |

### Security Boundaries
- **HTTPS Enforcement**: Non-localhost endpoints (e.g. `https://api.custode.io`) **must** use HTTPS. Insecure HTTP is only permitted on `localhost`, `127.0.0.1`, and `0.0.0.0` for local development.
- **Credential Masking**: API keys are masked automatically (`cst_ag_***`) in all string representations, tracebacks, and logs to prevent credential leakage.

---

## Quickstart

### Synchronous Usage

```python
import os
from custode import CUSTODEClient

with CUSTODEClient(
    base_url=os.environ.get("CUSTODE_BASE_URL", "http://localhost:8000"),
    api_key=os.environ["CUSTODE_AGENT_API_KEY"],
) as client:
    # 1. Verify agent identity
    identity = client.verify_identity()
    print(f"Connected as Agent {identity.agent_id} in Org {identity.organization_id}")

    # 2. Register intended action
    action = client.runtime_actions.create(
        tool_id="00000000-0000-0000-0000-000000000001",
        operation_id="00000000-0000-0000-0000-000000000002",
        parameters={"query": "SELECT * FROM users LIMIT 10"},
    )

    # 3. Evaluate authorization decision
    decision = client.runtime_actions.decide(action.id)

    # 4. Handle decision outcome
    if decision.is_allowed:
        execution = client.runtime_actions.execute(action.id)
        print("Execution result:", execution.result)
    elif decision.requires_approval:
        print("Action paused: Human approval required.")
    else:
        print(f"Action blocked by policy: {decision.reason}")
```

### Asynchronous Usage

```python
import asyncio
from custode import AsyncCUSTODEClient

async def main():
    async with AsyncCUSTODEClient() as client:
        identity = await client.verify_identity()
        print(f"Async agent {identity.agent_id} active.")

        # Concurrently query decisions and findings
        decisions, findings = await asyncio.gather(
            client.decisions.list(limit=10),
            client.findings.list(limit=10),
        )
        print(f"Loaded {len(decisions)} decisions and {len(findings)} findings.")

asyncio.run(main())
```

---

## Platform Modules Supported

| Resource | Description | Key Methods |
| :--- | :--- | :--- |
| `client.agents` | Identity and profile verification | `me()`, `get()`, `list()` |
| `client.runtime_actions` | Action registration and lifecycle | `create()`, `get()`, `list()`, `decide()`, `execute()` |
| `client.decisions` | Authorization arbitration records | `get()`, `list()`, `get_for_action()` |
| `client.approvals` | Human governance workflow tracking | `get()`, `list()`, `cancel()` |
| `client.executions` | Controlled execution guardrails | `get()`, `list()`, `execute()` |
| `client.llm` | LLM Gateway input/output scanning | `chat()`, `get_interaction()`, `list_interactions()` |
| `client.mcp` | MCP tool discovery & drift protection | `list_servers()`, `list_tools()`, `call_tool()` |
| `client.findings` | Sentinel vulnerability findings | `get()`, `list()` |
| `client.audit` | Cryptographic audit trail records | `get()`, `list()` |

---

## Request Correlation & Retries

- **RFC 4122 Request IDs**: Every request automatically generates or propagates an `X-Request-ID` UUID header.
- **Safe Retry Rules**:
  - Transient network connection failures and safe HTTP 5xx responses (502, 503, 504) are automatically retried up to `max_retries` **only on idempotent HTTP methods** (`GET`, `HEAD`, `OPTIONS`).
  - Security denials (401, 403, 404, 409, 422) and non-idempotent `POST` requests are **never** retried.

---

## Error Handling

All SDK exceptions inherit from `CUSTODEError`:

```python
from custode import CUSTODEClient
from custode.exceptions import (
    AuthenticationError,
    AuthorizationError,
    NotFoundError,
    RateLimitError,
    ServerError,
)

try:
    with CUSTODEClient() as client:
        client.verify_identity()
except AuthenticationError as e:
    print(f"Invalid API Key: {e} [status={e.status_code}, req_id={e.request_id}]")
except AuthorizationError as e:
    print(f"Access Denied: {e}")
except RateLimitError as e:
    print(f"Rate limited: {e}")
except ServerError as e:
    print(f"Server error: {e}")
```

---

## Development & Testing

Run the test suite using pytest:

```bash
pytest custode/sdk/python/tests/
```

Build distribution packages (wheel and source tarball):

```bash
python -m pip wheel --no-deps -w dist/ custode/sdk/python/
```

---

## License

Apache-2.0. Copyright (c) 2026 CUSTODE Security Team.
