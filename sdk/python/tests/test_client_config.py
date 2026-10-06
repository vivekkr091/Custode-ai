"""Unit tests for CUSTODE SDK configuration, initialization, and security masking."""

import os
import pytest
import custode
from custode import AsyncCUSTODEClient, CUSTODEClient, CUSTODEConfig
from custode.exceptions import AuthenticationError, ValidationError
from custode.security.masking import mask_secret, sanitize_headers


def test_package_exports():
    """Verify package public API exports."""
    assert custode.__version__ == "0.1.0"
    assert hasattr(custode, "CUSTODEClient")
    assert hasattr(custode, "AsyncCUSTODEClient")
    assert hasattr(custode, "CUSTODEError")
    assert hasattr(custode, "RuntimeAction")
    assert hasattr(custode, "Decision")


def test_client_init_explicit():
    """Test client initialization with explicit parameters."""
    client = CUSTODEClient(
        base_url="http://localhost:8000",
        api_key="cst_ag_0123456789_testsecretkey12345678901234567890",
        organization_id="00000000-0000-0000-0000-000000000001",
        timeout=15.0,
    )
    assert client.config.base_url == "http://localhost:8000"
    assert client.config.api_key == "cst_ag_0123456789_testsecretkey12345678901234567890"
    assert client.config.organization_id == "00000000-0000-0000-0000-000000000001"
    assert client.config.timeout == 15.0
    client.close()


def test_async_client_init_explicit():
    """Test async client initialization with explicit parameters."""
    client = AsyncCUSTODEClient(
        base_url="http://127.0.0.1:8000",
        api_key="cst_ag_0123456789_testsecretkey12345678901234567890",
        organization_id="00000000-0000-0000-0000-000000000001",
    )
    assert client.config.base_url == "http://127.0.0.1:8000"
    assert client.config.organization_id == "00000000-0000-0000-0000-000000000001"


def test_client_init_from_env(monkeypatch):
    """Test client initialization loading from environment variables."""
    monkeypatch.setenv("CUSTODE_BASE_URL", "http://localhost:9000")
    monkeypatch.setenv("CUSTODE_AGENT_API_KEY", "cst_ag_envkey1234_abcdefg")
    monkeypatch.setenv("CUSTODE_ORGANIZATION_ID", "org-from-env-123")
    monkeypatch.setenv("CUSTODE_TIMEOUT", "45.5")

    client = CUSTODEClient()
    assert client.config.base_url == "http://localhost:9000"
    assert client.config.api_key == "cst_ag_envkey1234_abcdefg"
    assert client.config.organization_id == "org-from-env-123"
    assert client.config.timeout == 45.5
    client.close()


def test_missing_api_key_raises_validation_error(monkeypatch):
    """Ensure missing API key fails fast with ValidationError."""
    monkeypatch.delenv("CUSTODE_AGENT_API_KEY", raising=False)
    with pytest.raises(ValidationError) as exc_info:
        CUSTODEClient(api_key=None)
    assert "Missing CUSTODE Agent API Key" in str(exc_info.value)


def test_invalid_timeout_rejected():
    """Ensure non-positive timeout values are rejected."""
    with pytest.raises(ValidationError):
        CUSTODEClient(api_key="cst_ag_test", timeout=-5)


def test_production_http_url_rejected():
    """Ensure remote HTTP endpoints are rejected for security (HTTPS required)."""
    with pytest.raises(ValidationError) as exc_info:
        CUSTODEClient(
            base_url="http://api.custode.io",
            api_key="cst_ag_test",
        )
    assert "Insecure HTTP is not allowed for remote endpoint" in str(exc_info.value)


def test_production_https_url_accepted():
    """Ensure remote HTTPS endpoints are accepted."""
    client = CUSTODEClient(
        base_url="https://api.custode.io",
        api_key="cst_ag_test",
    )
    assert client.config.base_url == "https://api.custode.io"
    client.close()


def test_localhost_http_accepted():
    """Ensure localhost HTTP is permitted for local development."""
    for host in ["http://localhost:8000", "http://127.0.0.1:8000", "http://0.0.0.0:8000"]:
        client = CUSTODEClient(base_url=host, api_key="cst_ag_test")
        assert client.config.base_url == host
        client.close()


def test_secret_never_leaked_in_repr():
    """Verify raw API keys are masked in config and client __repr__."""
    raw_key = "cst_ag_0123456789_supersecretunmaskedkey"
    client = CUSTODEClient(api_key=raw_key)

    client_repr = repr(client)
    config_repr = repr(client.config)

    assert raw_key not in client_repr
    assert "supersecretunmaskedkey" not in client_repr
    assert "cst_ag_0123456789_***" in client_repr

    assert raw_key not in config_repr
    assert "cst_ag_0123456789_***" in config_repr
    client.close()


def test_secret_never_leaked_in_exception_str():
    """Verify exceptions do not expose raw secrets in str() or repr()."""
    err = AuthenticationError("Invalid credential", status_code=401, request_id="req-123")
    err_str = str(err)
    assert "Invalid credential" in err_str
    assert "401" in err_str
    assert "req-123" in err_str


def test_mask_secret_helper():
    """Verify masking logic across various secret formats."""
    assert mask_secret("cst_ag_abcdef1234_secretvalue999") == "cst_ag_abcdef1234_***"
    assert mask_secret("cst_ag_short") == "cst_ag_***"
    assert mask_secret("plainsecretpassword") == "plai...***"
    assert mask_secret("short") == "***"
    assert mask_secret("") == "[EMPTY]"
    assert mask_secret(None) == "[EMPTY]"


def test_sanitize_headers_helper():
    """Verify sensitive headers are redacted."""
    headers = {
        "Authorization": "Bearer cst_ag_secret",
        "X-Agent-API-Key": "cst_ag_secret",
        "Content-Type": "application/json",
        "X-Request-ID": "req-123",
    }
    clean = sanitize_headers(headers)
    assert clean["Authorization"] == "[REDACTED]"
    assert clean["X-Agent-API-Key"] == "[REDACTED]"
    assert clean["Content-Type"] == "application/json"
    assert clean["X-Request-ID"] == "req-123"


def test_sync_client_context_manager():
    """Test sync client context manager lifecycle."""
    with CUSTODEClient(api_key="cst_ag_test") as client:
        assert client is not None
    # Transport closed cleanly


@pytest.mark.asyncio
async def test_async_client_context_manager():
    """Test async client context manager lifecycle."""
    async with AsyncCUSTODEClient(api_key="cst_ag_test") as client:
        assert client is not None
    # Transport closed cleanly
