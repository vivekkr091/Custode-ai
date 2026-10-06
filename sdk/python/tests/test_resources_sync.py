"""Unit tests for all synchronous CUSTODE SDK resources."""

import httpx
import pytest
from custode import CUSTODEClient
from custode.models import (
    ApprovalRequest,
    Decision,
    Execution,
    LLMResponse,
    MCPToolCallResponse,
    RuntimeAction,
    SecurityFinding,
)


def make_client(handler) -> CUSTODEClient:
    mock_http = httpx.Client(
        transport=httpx.MockTransport(handler),
        base_url="http://localhost:8000",
    )
    return CUSTODEClient(
        base_url="http://localhost:8000",
        api_key="cst_ag_0123456789_testkey",
        organization_id="00000000-0000-0000-0000-000000000001",
        http_client=mock_http,
    )


def test_agents_resource():
    """Test agents.me(), agents.get(), and agents.list()."""
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/api/v1/auth/me":
            return httpx.Response(200, json={
                "organization_id": "00000000-0000-0000-0000-000000000001",
                "agent_id": "11111111-1111-1111-1111-111111111111",
                "credential_id": "22222222-2222-2222-2222-222222222222",
            })
        if request.url.path == "/api/v1/organizations/00000000-0000-0000-0000-000000000001/agents/11111111-1111-1111-1111-111111111111":
            return httpx.Response(200, json={
                "id": "11111111-1111-1111-1111-111111111111",
                "organization_id": "00000000-0000-0000-0000-000000000001",
                "name": "Finance Agent",
                "slug": "finance-agent",
                "description": "Processes ledger",
                "agent_type": "assistant",
                "status": "active",
                "environment": "production",
                "created_at": "2026-10-01T00:00:00Z",
            })
        if request.url.path == "/api/v1/organizations/00000000-0000-0000-0000-000000000001/agents":
            return httpx.Response(200, json={
                "items": [{
                    "id": "11111111-1111-1111-1111-111111111111",
                    "organization_id": "00000000-0000-0000-0000-000000000001",
                    "name": "Finance Agent",
                    "slug": "finance-agent",
                    "agent_type": "assistant",
                    "status": "active",
                    "environment": "production",
                    "created_at": "2026-10-01T00:00:00Z",
                }],
                "total": 1,
            })
        return httpx.Response(404)

    client = make_client(handler)

    # 1. Test verify_identity / me
    me = client.verify_identity()
    assert me.agent_id == "11111111-1111-1111-1111-111111111111"

    # 2. Test get agent
    agent = client.agents.get("11111111-1111-1111-1111-111111111111")
    assert agent.name == "Finance Agent"
    assert agent.status == "active"

    # 3. Test list agents
    agents_list = client.agents.list()
    assert len(agents_list) == 1
    assert agents_list[0].slug == "finance-agent"
    client.close()


def test_runtime_actions_resource():
    """Test runtime_actions.create(), get(), list(), decide(), execute()."""
    def handler(request: httpx.Request) -> httpx.Response:
        base_path = "/api/v1/organizations/00000000-0000-0000-0000-000000000001/runtime-actions"
        if request.method == "POST" and request.url.path == base_path:
            return httpx.Response(201, json={
                "id": "act-12345",
                "organization_id": "00000000-0000-0000-0000-000000000001",
                "agent_id": "11111111-1111-1111-1111-111111111111",
                "tool_id": "tool-sql",
                "operation_id": "op-select",
                "environment": "production",
                "action_type": "tool_call",
                "parameters": {"query": "SELECT * FROM users"},
                "status": "pending",
                "created_at": "2026-10-01T00:00:00Z",
                "updated_at": "2026-10-01T00:00:00Z",
            })
        if request.method == "GET" and request.url.path == f"{base_path}/act-12345":
            return httpx.Response(200, json={
                "id": "act-12345",
                "organization_id": "00000000-0000-0000-0000-000000000001",
                "agent_id": "11111111-1111-1111-1111-111111111111",
                "tool_id": "tool-sql",
                "operation_id": "op-select",
                "environment": "production",
                "action_type": "tool_call",
                "parameters": {"query": "SELECT * FROM users"},
                "status": "authorized",
                "created_at": "2026-10-01T00:00:00Z",
                "updated_at": "2026-10-01T00:00:00Z",
            })
        if request.method == "POST" and request.url.path == f"{base_path}/act-12345/decide":
            return httpx.Response(201, json={
                "id": "dec-999",
                "organization_id": "00000000-0000-0000-0000-000000000001",
                "runtime_action_id": "act-12345",
                "decision": "allow",
                "reason": "Policy P101 granted access cleanly",
                "risk_score": 10.0,
                "risk_level": "low",
                "created_at": "2026-10-01T00:00:00Z",
            })
        if request.method == "POST" and request.url.path == f"{base_path}/act-12345/execute":
            return httpx.Response(200, json={
                "id": "exec-777",
                "organization_id": "00000000-0000-0000-0000-000000000001",
                "runtime_action_id": "act-12345",
                "agent_id": "11111111-1111-1111-1111-111111111111",
                "tool_id": "tool-sql",
                "operation_id": "op-select",
                "status": "succeeded",
                "result": {"rows": [{"id": 1, "username": "admin"}]},
                "started_at": "2026-10-01T00:00:00Z",
                "completed_at": "2026-10-01T00:00:01Z",
                "created_at": "2026-10-01T00:00:00Z",
            })
        return httpx.Response(404)

    client = make_client(handler)

    # 1. Create action
    action = client.runtime_actions.create(
        tool_id="tool-sql",
        operation_id="op-select",
        environment="production",
        parameters={"query": "SELECT * FROM users"},
    )
    assert action.id == "act-12345"
    assert action.status == "pending"

    # 2. Get action
    fetched = client.runtime_actions.get(action.id)
    assert fetched.id == action.id

    # 3. Decide action
    decision = client.runtime_actions.decide(action.id)
    assert decision.is_allowed is True
    assert decision.is_blocked is False
    assert decision.requires_approval is False
    assert decision.decision == "allow"

    # 4. Execute action
    execution = client.runtime_actions.execute(action.id)
    assert execution.is_succeeded is True
    assert execution.result == {"rows": [{"id": 1, "username": "admin"}]}
    client.close()


def test_decisions_require_approval_and_block():
    """Verify decision helper properties for block and require_approval."""
    def handler(request: httpx.Request) -> httpx.Response:
        if "block" in request.url.path:
            return httpx.Response(200, json={
                "id": "dec-block",
                "organization_id": "00000000-0000-0000-0000-000000000001",
                "runtime_action_id": "act-block",
                "decision": "block",
                "reason": "Explicit policy DENY triggered",
                "created_at": "2026-10-01T00:00:00Z",
            })
        return httpx.Response(200, json={
            "id": "dec-approval",
            "organization_id": "00000000-0000-0000-0000-000000000001",
            "runtime_action_id": "act-appr",
            "decision": "require_approval",
            "reason": "High risk financial transaction",
            "created_at": "2026-10-01T00:00:00Z",
        })

    client = make_client(handler)

    block_dec = client.decisions.get("dec-block")
    assert block_dec.is_blocked is True
    assert block_dec.is_allowed is False
    assert block_dec.requires_approval is False

    appr_dec = client.decisions.get("dec-appr")
    assert appr_dec.requires_approval is True
    assert appr_dec.is_allowed is False
    assert appr_dec.is_blocked is False
    client.close()


def test_approvals_resource():
    """Test approvals.get(), list(), and cancel()."""
    def handler(request: httpx.Request) -> httpx.Response:
        if request.method == "POST" and "cancel" in request.url.path:
            return httpx.Response(200, json={
                "id": "appr-01",
                "organization_id": "00000000-0000-0000-0000-000000000001",
                "runtime_action_id": "act-01",
                "decision_id": "dec-01",
                "status": "cancelled",
                "reason": "Agent withdrew task",
                "created_at": "2026-10-01T00:00:00Z",
            })
        return httpx.Response(200, json={
            "id": "appr-01",
            "organization_id": "00000000-0000-0000-0000-000000000001",
            "runtime_action_id": "act-01",
            "decision_id": "dec-01",
            "status": "pending",
            "created_at": "2026-10-01T00:00:00Z",
        })

    client = make_client(handler)

    approval = client.approvals.get("appr-01")
    assert approval.is_pending is True

    cancelled = client.approvals.cancel("appr-01", reason="Agent withdrew task")
    assert cancelled.status == "cancelled"
    client.close()


def test_llm_gateway_resource():
    """Test llm.chat() and interaction inspection."""
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={
            "request_id": "req-llm-1",
            "interaction_id": "inter-llm-1",
            "provider": "mock",
            "model": "mock-gpt-4",
            "content": "Clean mediated assistant response.",
            "tool_calls": [],
            "decision": "allow",
            "security_status": "clean",
            "usage": {"total_tokens": 42},
            "created_at": "2026-10-01T00:00:00Z",
        })

    client = make_client(handler)

    response = client.llm.chat(
        messages=[{"role": "user", "content": "What is the status of the cluster?"}],
        provider="mock",
        model="mock-gpt-4",
    )
    assert response.is_allowed is True
    assert response.content == "Clean mediated assistant response."
    assert response.interaction_id == "inter-llm-1"
    client.close()


def test_mcp_security_resource():
    """Test mcp.list_servers(), list_tools(), call_tool()."""
    def handler(request: httpx.Request) -> httpx.Response:
        if "call" in request.url.path:
            return httpx.Response(200, json={
                "tool_id": "mcp-t1",
                "runtime_action_id": "act-mcp-1",
                "decision": "allow",
                "status": "succeeded",
                "result": {"temperature": 22.5},
            })
        if "tools" in request.url.path:
            return httpx.Response(200, json={
                "items": [{
                    "id": "mcp-t1",
                    "organization_id": "00000000-0000-0000-0000-000000000001",
                    "mcp_server_id": "srv-1",
                    "name": "get_weather",
                    "slug": "get-weather",
                    "input_schema": {"type": "object"},
                    "status": "active",
                    "risk_level": "low",
                    "schema_hash": "abc",
                    "discovered_at": "2026-10-01T00:00:00Z",
                    "created_at": "2026-10-01T00:00:00Z",
                    "updated_at": "2026-10-01T00:00:00Z",
                }],
                "total": 1,
            })
        return httpx.Response(200, json={"items": [], "total": 0})

    client = make_client(handler)

    tools = client.mcp.list_tools()
    assert len(tools) == 1
    assert tools[0].name == "get_weather"

    call_res = client.mcp.call_tool("mcp-t1", arguments={"location": "San Francisco"})
    assert call_res.is_allowed is True
    assert call_res.result == {"temperature": 22.5}
    client.close()


def test_findings_and_audit_resources():
    """Test findings and audit resource queries."""
    def handler(request: httpx.Request) -> httpx.Response:
        if "findings" in request.url.path:
            return httpx.Response(200, json={
                "items": [{
                    "id": "f-1",
                    "organization_id": "00000000-0000-0000-0000-000000000001",
                    "scanner": "secrets_scanner",
                    "category": "SECRET",
                    "severity": "CRITICAL",
                    "title": "AWS Key leaked",
                    "description": "Exposed key in payload",
                    "created_at": "2026-10-01T00:00:00Z",
                }],
                "total": 1,
            })
        return httpx.Response(200, json={
            "items": [{
                "id": "aud-1",
                "action": "ACTION_EVALUATED",
                "outcome": "SUCCESS",
                "created_at": "2026-10-01T00:00:00Z",
            }],
            "total": 1,
        })

    client = make_client(handler)

    findings = client.findings.list()
    assert len(findings) == 1
    assert findings[0].is_critical is True
    assert findings[0].title == "AWS Key leaked"

    audit_events = client.audit.list()
    assert len(audit_events) == 1
    assert audit_events[0].action == "ACTION_EVALUATED"
    client.close()
