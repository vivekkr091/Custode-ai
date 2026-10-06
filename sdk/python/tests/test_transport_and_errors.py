"""Unit tests for HTTP transport, correlation IDs, retries, and error mapping."""

import httpx
import pytest
from custode import CUSTODEClient
from custode.config import CUSTODEConfig
from custode.exceptions import (
    APIConnectionError,
    APITimeoutError,
    AuthenticationError,
    AuthorizationError,
    ConflictError,
    NotFoundError,
    RateLimitError,
    ServerError,
    ValidationError,
)
from custode.transport.transport import SyncTransport


def test_bearer_token_and_request_id_injected():
    """Verify Authorization Bearer header and X-Request-ID are sent."""
    captured_request = None

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal captured_request
        captured_request = request
        return httpx.Response(200, json={
            "organization_id": "00000000-0000-0000-0000-000000000001",
            "agent_id": "11111111-1111-1111-1111-111111111111",
            "credential_id": "22222222-2222-2222-2222-222222222222",
        }, headers={"X-Request-ID": request.headers["X-Request-ID"]})

    mock_http = httpx.Client(transport=httpx.MockTransport(handler), base_url="http://localhost:8000")
    client = CUSTODEClient(
        base_url="http://localhost:8000",
        api_key="cst_ag_testkey_12345",
        http_client=mock_http,
    )

    client.agents.me()
    assert captured_request is not None
    assert captured_request.headers["Authorization"] == "Bearer cst_ag_testkey_12345"
    assert "X-Request-ID" in captured_request.headers
    assert len(captured_request.headers["X-Request-ID"]) > 10
    client.close()


def test_http_401_maps_to_authentication_error():
    """Verify HTTP 401 raises AuthenticationError."""
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(401, json={"detail": "Invalid agent API key"}, headers={"X-Request-ID": "req-401"})

    mock_http = httpx.Client(transport=httpx.MockTransport(handler), base_url="http://localhost:8000")
    client = CUSTODEClient(api_key="cst_ag_bad", http_client=mock_http)

    with pytest.raises(AuthenticationError) as exc_info:
        client.agents.me()

    assert exc_info.value.status_code == 401
    assert exc_info.value.request_id == "req-401"
    assert "Invalid agent API key" in str(exc_info.value)
    client.close()


def test_http_403_maps_to_authorization_error():
    """Verify HTTP 403 raises AuthorizationError."""
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(403, json={"detail": "Agent does not belong to target organization"})

    mock_http = httpx.Client(transport=httpx.MockTransport(handler), base_url="http://localhost:8000")
    client = CUSTODEClient(api_key="cst_ag_test", organization_id="org-1", http_client=mock_http)

    with pytest.raises(AuthorizationError) as exc_info:
        client.runtime_actions.get("act-1")

    assert exc_info.value.status_code == 403
    client.close()


def test_http_404_maps_to_not_found_error():
    """Verify HTTP 404 raises NotFoundError."""
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(404, json={"detail": "Resource not found"})

    mock_http = httpx.Client(transport=httpx.MockTransport(handler), base_url="http://localhost:8000")
    client = CUSTODEClient(api_key="cst_ag_test", organization_id="org-1", http_client=mock_http)

    with pytest.raises(NotFoundError):
        client.runtime_actions.get("act-missing")
    client.close()


def test_http_409_maps_to_conflict_error():
    """Verify HTTP 409 raises ConflictError."""
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(409, json={"detail": "Resource inactive or suspended"})

    mock_http = httpx.Client(transport=httpx.MockTransport(handler), base_url="http://localhost:8000")
    client = CUSTODEClient(api_key="cst_ag_test", organization_id="org-1", http_client=mock_http)

    with pytest.raises(ConflictError):
        client.runtime_actions.get("act-conflict")
    client.close()


def test_http_422_maps_to_validation_error():
    """Verify HTTP 422 raises ValidationError."""
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(422, json={"detail": "Unprocessable payload parameters"})

    mock_http = httpx.Client(transport=httpx.MockTransport(handler), base_url="http://localhost:8000")
    client = CUSTODEClient(api_key="cst_ag_test", organization_id="org-1", http_client=mock_http)

    with pytest.raises(ValidationError):
        client.runtime_actions.create(tool_id="bad", operation_id="bad")
    client.close()


def test_http_429_maps_to_rate_limit_error():
    """Verify HTTP 429 raises RateLimitError."""
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(429, json={"detail": "Too many requests"})

    mock_http = httpx.Client(transport=httpx.MockTransport(handler), base_url="http://localhost:8000")
    client = CUSTODEClient(api_key="cst_ag_test", organization_id="org-1", http_client=mock_http)

    with pytest.raises(RateLimitError):
        client.runtime_actions.get("act-rate")
    client.close()


def test_http_500_maps_to_server_error():
    """Verify HTTP 500 raises ServerError."""
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(500, json={"detail": "Internal control plane error"})

    mock_http = httpx.Client(transport=httpx.MockTransport(handler), base_url="http://localhost:8000")
    client = CUSTODEClient(api_key="cst_ag_test", organization_id="org-1", http_client=mock_http)

    with pytest.raises(ServerError):
        client.runtime_actions.get("act-err")
    client.close()


def test_safe_retry_on_get_503():
    """Verify idempotent GET requests retry on 503 up to max_retries and succeed."""
    attempts = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal attempts
        attempts += 1
        if attempts == 1:
            return httpx.Response(503, json={"detail": "Transient gateway error"})
        return httpx.Response(200, json={"items": [], "total": 0})

    mock_http = httpx.Client(transport=httpx.MockTransport(handler), base_url="http://localhost:8000")
    client = CUSTODEClient(api_key="cst_ag_test", organization_id="org-1", max_retries=2, http_client=mock_http)

    res = client.runtime_actions.list()
    assert attempts == 2
    assert res.total == 0
    client.close()


def test_no_retry_on_post_503():
    """Verify non-idempotent POST requests are NOT retried on 503 to prevent duplicate actions."""
    attempts = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal attempts
        attempts += 1
        return httpx.Response(503, json={"detail": "Backend busy"})

    mock_http = httpx.Client(transport=httpx.MockTransport(handler), base_url="http://localhost:8000")
    client = CUSTODEClient(api_key="cst_ag_test", organization_id="org-1", max_retries=3, http_client=mock_http)

    with pytest.raises(ServerError):
        client.runtime_actions.create(tool_id="t-1", operation_id="op-1")

    assert attempts == 1  # Only tried once, no retries on POST
    client.close()


def test_no_retry_on_security_401():
    """Verify authentication failure (401) is NEVER retried as transient."""
    attempts = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal attempts
        attempts += 1
        return httpx.Response(401, json={"detail": "Unauthorized"})

    mock_http = httpx.Client(transport=httpx.MockTransport(handler), base_url="http://localhost:8000")
    client = CUSTODEClient(api_key="cst_ag_bad", max_retries=3, http_client=mock_http)

    with pytest.raises(AuthenticationError):
        client.agents.me()

    assert attempts == 1
    client.close()
