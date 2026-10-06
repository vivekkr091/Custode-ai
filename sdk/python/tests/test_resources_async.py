"""Unit tests for all asynchronous CUSTODE SDK resources."""

import httpx
import pytest
from custode import AsyncCUSTODEClient


def make_async_client(handler) -> AsyncCUSTODEClient:
    mock_http = httpx.AsyncClient(
        transport=httpx.MockTransport(handler),
        base_url="http://localhost:8000",
    )
    return AsyncCUSTODEClient(
        base_url="http://localhost:8000",
        api_key="cst_ag_0123456789_testkey",
        organization_id="00000000-0000-0000-0000-000000000001",
        http_client=mock_http,
    )


@pytest.mark.asyncio
async def test_async_workflow():
    """Verify end-to-end asynchronous workflow."""
    def handler(request: httpx.Request) -> httpx.Response:
        base_path = "/api/v1/organizations/00000000-0000-0000-0000-000000000001"
        if request.url.path == "/api/v1/auth/me":
            return httpx.Response(200, json={
                "organization_id": "00000000-0000-0000-0000-000000000001",
                "agent_id": "ag-async-1",
                "credential_id": "cred-async-1",
            })
        if request.method == "POST" and request.url.path == f"{base_path}/runtime-actions":
            return httpx.Response(201, json={
                "id": "act-async-100",
                "organization_id": "00000000-0000-0000-0000-000000000001",
                "agent_id": "ag-async-1",
                "tool_id": "tool-1",
                "operation_id": "op-1",
                "environment": "staging",
                "action_type": "tool_call",
                "status": "pending",
                "created_at": "2026-10-01T00:00:00Z",
                "updated_at": "2026-10-01T00:00:00Z",
            })
        if request.method == "POST" and "decide" in request.url.path:
            return httpx.Response(201, json={
                "id": "dec-async-100",
                "organization_id": "00000000-0000-0000-0000-000000000001",
                "runtime_action_id": "act-async-100",
                "decision": "allow",
                "reason": "Clean decision",
                "created_at": "2026-10-01T00:00:00Z",
            })
        if request.method == "POST" and "execute" in request.url.path:
            return httpx.Response(200, json={
                "id": "exec-async-100",
                "organization_id": "00000000-0000-0000-0000-000000000001",
                "runtime_action_id": "act-async-100",
                "agent_id": "ag-async-1",
                "tool_id": "tool-1",
                "operation_id": "op-1",
                "status": "succeeded",
                "result": {"status": "ok"},
                "started_at": "2026-10-01T00:00:00Z",
                "created_at": "2026-10-01T00:00:00Z",
            })
        if request.method == "POST" and "chat" in request.url.path:
            return httpx.Response(200, json={
                "request_id": "req-async-llm",
                "interaction_id": "inter-async-llm",
                "provider": "mock",
                "model": "mock-gpt-4",
                "content": "Async response",
                "decision": "allow",
                "security_status": "clean",
                "created_at": "2026-10-01T00:00:00Z",
            })
        return httpx.Response(200, json={"items": [], "total": 0})

    client = make_async_client(handler)

    # 1. Identity
    identity = await client.verify_identity()
    assert identity.agent_id == "ag-async-1"

    # 2. Runtime action
    action = await client.runtime_actions.create(
        tool_id="tool-1",
        operation_id="op-1",
        environment="staging",
    )
    assert action.id == "act-async-100"

    # 3. Decision
    decision = await client.runtime_actions.decide(action.id)
    assert decision.is_allowed is True

    # 4. Execution
    execution = await client.runtime_actions.execute(action.id)
    assert execution.is_succeeded is True
    assert execution.result == {"status": "ok"}

    # 5. LLM
    llm_resp = await client.llm.chat(messages=[{"role": "user", "content": "hi"}])
    assert llm_resp.is_allowed is True
    assert llm_resp.content == "Async response"

    await client.aclose()
