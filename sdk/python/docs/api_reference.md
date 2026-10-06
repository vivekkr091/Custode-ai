# CUSTODE Python SDK — API Reference

## Client Classes

### `CUSTODEClient`
Synchronous client for communicating with the CUSTODE Control Plane.

#### Parameters:
- `base_url` (*str*, optional): Base URL of CUSTODE backend. Defaults to `http://localhost:8000` or `CUSTODE_BASE_URL`. Remote hosts must use `https://`.
- `api_key` (*str*, optional): Agent API key (`cst_ag_...`). Defaults to `CUSTODE_AGENT_API_KEY`.
- `organization_id` (*str*, optional): Target organization UUID. Defaults to `CUSTODE_ORGANIZATION_ID` or resolved via `verify_identity()`.
- `timeout` (*float*, optional): Network request timeout in seconds (default: 30.0).
- `max_retries` (*int*, optional): Maximum retries on transient network errors (default: 2).
- `http_client` (*httpx.Client*, optional): Custom HTTPX client.

### `AsyncCUSTODEClient`
Asynchronous client matching the `CUSTODEClient` interface with async/await methods and `AsyncTransport`.

---

## Resources

### `client.agents` / `client.agents.me()`
- `me()`: Validates caller credentials and returns `AuthenticatedAgent`.
- `get(agent_id)`: Fetches `Agent` identity metadata.
- `list()`: Returns `PaginatedList[Agent]`.

### `client.runtime_actions`
- `create(tool_id, operation_id, ...)`: Registers intended action request.
- `get(action_id)`: Retrieves `RuntimeAction`.
- `list()`: Returns `RuntimeActionList`.
- `decide(action_id)`: Arbitrates decision via Decision Engine, returns `Decision`.
- `execute(action_id)`: Dispatches authorized action to controlled execution, returns `Execution`.

### `client.decisions`
- `get(decision_id)`: Retrieves immutable `Decision` audit record.
- `list()`: Returns `DecisionList`.
- `get_for_action(action_id)`: Returns all decisions for an action.

### `client.approvals`
- `get(approval_id)`: Retrieves `ApprovalRequest`.
- `list()`: Returns `ApprovalList`.
- `cancel(approval_id)`: Cancels pending approval.

### `client.executions`
- `get(execution_id)`: Retrieves `Execution` record.
- `list()`: Returns `ExecutionList`.

### `client.llm`
- `chat(messages, provider, model, ...)`: Mediated chat through LLM Gateway.
- `get_interaction(interaction_id)`: Retrieves `LLMInteraction`.
- `list_interactions()`: Returns `LLMInteractionList`.

### `client.mcp`
- `list_servers()`: Returns `MCPServerList`.
- `list_tools()`: Returns `MCPToolList`.
- `call_tool(tool_id, arguments)`: Dispatches governed tool invocation, returns `MCPToolCallResponse`.

### `client.findings`
- `list()`: Returns `SecurityFindingList`.
- `get(finding_id)`: Retrieves `SecurityFinding`.

### `client.audit`
- `list()`: Returns `AuditEventList`.
- `get(event_id)`: Retrieves `AuditEvent`.

---

## Exceptions

- `CUSTODEError`: Base exception for all SDK errors.
- `AuthenticationError` (HTTP 401): Invalid or missing credentials.
- `AuthorizationError` (HTTP 403): Insufficient permissions or wrong organization.
- `NotFoundError` (HTTP 404): Resource not found.
- `ConflictError` (HTTP 409): Resource suspended, inactive, or duplicate.
- `ValidationError` (HTTP 422): Invalid payload parameters or configuration.
- `RateLimitError` (HTTP 429): Rate limits exceeded.
- `APIConnectionError`: Network connection failure.
- `APITimeoutError`: Network timeout exceeded.
- `ServerError` (HTTP 5xx): Internal backend error.
- `SecurityDecisionError`: Adverse security decision.
