"""LLM Gateway and MCP Security Layer Red Team Tests (Milestone 22)."""

import uuid
import pytest
from httpx import AsyncClient

from app.db.models.membership import MembershipRole
from app.llm.registry import provider_registry


async def _setup_llm_org(async_client: AsyncClient):
    org_resp = await async_client.post("/api/v1/organizations", json={"name": f"LLM Org {uuid.uuid4().hex[:6]}"})
    org_id = org_resp.json()["id"]

    user_resp = await async_client.post(
        "/api/v1/users",
        json={"email": f"analyst_{uuid.uuid4().hex[:6]}@custode.io", "display_name": "Analyst"},
    )
    user_id = user_resp.json()["id"]
    await async_client.post(
        f"/api/v1/organizations/{org_id}/memberships",
        json={"user_id": user_id, "role": MembershipRole.security_analyst.value},
    )
    return org_id, user_id


@pytest.mark.asyncio
async def test_llm_unsupported_provider_and_model_rejected(async_client: AsyncClient):
    """Verify that unregistered LLM providers and models are rejected."""
    org_id, user_id = await _setup_llm_org(async_client)

    resp = await async_client.post(
        f"/api/v1/organizations/{org_id}/llm/chat",
        json={
            "provider": "untrusted_ai_co",
            "model": "malicious-model-v1",
            "messages": [{"role": "user", "content": "Hello"}],
        },
        headers={"X-User-ID": user_id},
    )
    assert resp.status_code in (400, 422)


@pytest.mark.asyncio
async def test_llm_oversized_messages_blocked(async_client: AsyncClient):
    """Verify that messages exceeding max prompt characters are rejected."""
    org_id, user_id = await _setup_llm_org(async_client)

    # 300,000 characters exceeds MAX_TOTAL_PROMPT_CHARS (200,000)
    huge_prompt = "A" * 250_000
    resp = await async_client.post(
        f"/api/v1/organizations/{org_id}/llm/chat",
        json={
            "provider": "openai",
            "model": "gpt-4o",
            "messages": [{"role": "user", "content": huge_prompt}],
        },
        headers={"X-User-ID": user_id},
    )
    assert resp.status_code in (400, 422, 429)


@pytest.mark.asyncio
async def test_mcp_ssrf_server_registration_blocked(async_client: AsyncClient):
    """Verify that registering an MCP server targeting loopback or private network fails with 400."""
    org_id, user_id = await _setup_llm_org(async_client)

    resp = await async_client.post(
        f"/api/v1/organizations/{org_id}/mcp/servers",
        json={
            "name": "Internal Exploiter",
            "endpoint": "http://127.0.0.1:8000/sse",
            "transport": "SSE",
        },
        headers={"X-User-ID": user_id},
    )
    assert resp.status_code == 400
    assert "ssrf" in resp.json()["detail"].lower()


@pytest.mark.asyncio
async def test_mcp_unsupported_stdio_transport_rejected(async_client: AsyncClient):
    """Verify that unvetted local STDIO transport execution is rejected."""
    org_id, user_id = await _setup_llm_org(async_client)

    resp = await async_client.post(
        f"/api/v1/organizations/{org_id}/mcp/servers",
        json={
            "name": "STDIO Exploiter",
            "endpoint": "stdio://sh",
            "transport": "STDIO",
        },
        headers={"X-User-ID": user_id},
    )
    assert resp.status_code in (400, 422)
