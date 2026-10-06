"""Additional security tests for CUSTODE SDK ensuring credentials never leak in query parameters or URLs."""

import httpx
import pytest
from custode import CUSTODEClient


def test_no_credentials_in_url_or_query_params():
    """Verify that agent API keys are NEVER embedded in the request URL or query strings."""
    captured_urls = []

    def handler(request: httpx.Request) -> httpx.Response:
        captured_urls.append(str(request.url))
        if request.url.path == "/api/v1/auth/me":
            return httpx.Response(200, json={
                "organization_id": "00000000-0000-0000-0000-000000000001",
                "agent_id": "11111111-1111-1111-1111-111111111111",
                "credential_id": "22222222-2222-2222-2222-222222222222",
            })
        return httpx.Response(200, json={"items": [], "total": 0})

    raw_secret = "cst_ag_abcdef1234_myuniquesecretkey987654321"
    mock_http = httpx.Client(transport=httpx.MockTransport(handler), base_url="http://localhost:8000")
    client = CUSTODEClient(
        base_url="http://localhost:8000",
        api_key=raw_secret,
        organization_id="00000000-0000-0000-0000-000000000001",
        http_client=mock_http,
    )

    client.agents.me()
    client.runtime_actions.list()
    client.decisions.list()
    client.approvals.list()
    client.executions.list()
    client.findings.list()
    client.audit.list()

    for url in captured_urls:
        assert raw_secret not in url
        assert "cst_ag_" not in url
        assert "api_key" not in url.lower()
        assert "token" not in url.lower()

    client.close()
