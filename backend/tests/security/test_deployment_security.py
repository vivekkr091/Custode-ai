"""Automated Deployment Security & DevOps Validation Tests (Milestone 23)."""

import os
import sqlite3
import subprocess
import tempfile
import pytest
from httpx import AsyncClient
import pydantic

from app.core.config import Settings
from app.core.logging import RedactingFilter, sanitize_log_dict
from scripts.backup_restore import backup_sqlite, restore_sqlite


def test_production_config_rejects_insecure_default_secret_key():
    """Verify that Settings validation rejects insecure default SECRET_KEY in production."""
    with pytest.raises(pydantic.ValidationError) as exc_info:
        Settings(
            ENVIRONMENT="production",
            DEBUG=False,
            DEMO_MODE=False,
            SECRET_KEY="dev-secret-key-please-change-in-production-min-32-chars",
            AUTH_SECRET_KEY="strong_prod_auth_secret_key_32_characters_long",
            AUTH_MODE="production",
            DATABASE_URL="postgresql+asyncpg://prod_user:prod_pass@db:5432/custode_prod",
        )
    assert "Insecure default SECRET_KEY rejected in production" in str(exc_info.value)


def test_production_config_rejects_insecure_default_auth_secret():
    """Verify that Settings validation rejects insecure default AUTH_SECRET_KEY in production."""
    with pytest.raises(pydantic.ValidationError) as exc_info:
        Settings(
            ENVIRONMENT="production",
            DEBUG=False,
            DEMO_MODE=False,
            SECRET_KEY="strong_prod_secret_key_minimum_32_characters_long",
            AUTH_SECRET_KEY="dev-auth-jwt-secret-key-please-change-in-production-min-32-chars",
            AUTH_MODE="production",
            DATABASE_URL="postgresql+asyncpg://prod_user:prod_pass@db:5432/custode_prod",
        )
    assert "Insecure default AUTH_SECRET_KEY rejected in production" in str(exc_info.value)


def test_production_config_rejects_debug_mode():
    """Verify that Settings validation rejects DEBUG=True in production."""
    with pytest.raises(pydantic.ValidationError) as exc_info:
        Settings(
            ENVIRONMENT="production",
            DEBUG=True,
            DEMO_MODE=False,
            SECRET_KEY="strong_prod_secret_key_minimum_32_characters_long",
            AUTH_SECRET_KEY="strong_prod_auth_secret_key_32_characters_long",
            AUTH_MODE="production",
            DATABASE_URL="postgresql+asyncpg://prod_user:prod_pass@db:5432/custode_prod",
        )
    assert "DEBUG mode must be set to False in production" in str(exc_info.value)


def test_production_config_rejects_short_secrets():
    """Verify that Settings validation rejects keys shorter than 32 characters in production."""
    with pytest.raises(pydantic.ValidationError) as exc_info:
        Settings(
            ENVIRONMENT="production",
            DEBUG=False,
            DEMO_MODE=False,
            SECRET_KEY="too_short_secret_key",
            AUTH_SECRET_KEY="strong_prod_auth_secret_key_32_characters_long",
            AUTH_MODE="production",
            DATABASE_URL="postgresql+asyncpg://prod_user:prod_pass@db:5432/custode_prod",
        )
    assert "SECRET_KEY must be at least 32 characters" in str(exc_info.value)


def test_production_config_rejects_development_auth_mode():
    """Verify that Settings validation rejects AUTH_MODE='development' in production."""
    with pytest.raises(pydantic.ValidationError) as exc_info:
        Settings(
            ENVIRONMENT="production",
            DEBUG=False,
            DEMO_MODE=False,
            SECRET_KEY="strong_prod_secret_key_minimum_32_characters_long",
            AUTH_SECRET_KEY="strong_prod_auth_secret_key_32_characters_long",
            AUTH_MODE="development",
            DATABASE_URL="postgresql+asyncpg://prod_user:prod_pass@db:5432/custode_prod",
        )
    assert "AUTH_MODE cannot be 'development' in production" in str(exc_info.value)


def test_production_config_rejects_dev_database_password():
    """Verify that Settings validation rejects default dev database password in production."""
    with pytest.raises(pydantic.ValidationError) as exc_info:
        Settings(
            ENVIRONMENT="production",
            DEBUG=False,
            DEMO_MODE=False,
            SECRET_KEY="strong_prod_secret_key_minimum_32_characters_long",
            AUTH_SECRET_KEY="strong_prod_auth_secret_key_32_characters_long",
            AUTH_MODE="production",
            DATABASE_URL="postgresql+asyncpg://custode:custode_dev_password@db:5432/custode",
        )
    assert "Default development credentials detected in production DATABASE_URL" in str(exc_info.value)


@pytest.mark.asyncio
async def test_health_and_readiness_endpoints_behavior(async_client: AsyncClient):
    """Verify liveness (/health/live), readiness (/health/ready), and metrics (/health/metrics)."""
    # 1. Liveness probe
    live_resp = await async_client.get("/health/live")
    assert live_resp.status_code == 200
    assert live_resp.json()["status"] == "ok"
    assert live_resp.json()["service"] == "custode-api"

    # 2. Readiness probe
    ready_resp = await async_client.get("/health/ready")
    assert ready_resp.status_code == 200
    ready_data = ready_resp.json()
    assert ready_data["status"] == "ready"
    assert ready_data["checks"]["database"] == "connected"

    # 3. Operational metrics probe
    metrics_resp = await async_client.get("/health/metrics")
    assert metrics_resp.status_code == 200
    metrics_data = metrics_resp.json()
    assert metrics_data["service"] == "custode-api"
    assert "uptime_seconds" in metrics_data
    assert metrics_data["database"] == "connected"


@pytest.mark.asyncio
async def test_health_endpoints_do_not_leak_secrets(async_client: AsyncClient):
    """Verify that health endpoints never expose passwords, DATABASE_URL, or sensitive keys."""
    endpoints = ["/health", "/health/live", "/health/ready", "/health/db", "/health/metrics"]
    forbidden_substrings = [
        "custode_dev_password",
        "secret",
        "private_key",
        "postgresql+asyncpg",
        "sqlite://",
    ]

    for ep in endpoints:
        resp = await async_client.get(ep)
        body = resp.text.lower()
        for bad in forbidden_substrings:
            assert bad not in body, f"Endpoint {ep} leaked sensitive substring '{bad}'"


def test_structured_log_and_filter_redacts_credentials():
    """Verify that log redaction scrubs secrets from dicts and string log records."""
    # 1. Dictionary sanitization
    raw_payload = {
        "user_id": "usr_123",
        "password": "super_secret_password",
        "api_key": "cst_secret_agent_key_abc123",
        "webhook_secret": "whsec_confidential",
        "nested": {
            "auth_secret_key": "jwt_secret_val",
            "message": "User provided Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.token in body",
        },
    }
    cleaned = sanitize_log_dict(raw_payload)
    assert cleaned["password"] == "[REDACTED]"
    assert cleaned["api_key"] == "[REDACTED]"
    assert cleaned["webhook_secret"] == "[REDACTED]"
    assert cleaned["nested"]["auth_secret_key"] == "[REDACTED]"
    assert "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.token" not in cleaned["nested"]["message"]

    # 2. RedactingFilter on raw log record
    import logging
    record = logging.LogRecord(
        name="test",
        level=logging.INFO,
        pathname="",
        lineno=0,
        msg="Agent authenticated with cst_1234567890abcdef123456 and Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9",
        args=(),
        exc_info=None,
    )
    f = RedactingFilter()
    f.filter(record)
    assert "cst_1234567890abcdef123456" not in record.msg
    assert "[REDACTED]" in record.msg


def test_dockerfiles_enforce_non_root_execution():
    """Verify that backend and frontend Dockerfiles define non-root user execution."""
    backend_dockerfile = os.path.abspath(
        os.path.join(os.path.dirname(__file__), "..", "..", "Dockerfile")
    )
    frontend_dockerfile = os.path.abspath(
        os.path.join(os.path.dirname(__file__), "..", "..", "..", "frontend", "Dockerfile")
    )

    with open(backend_dockerfile, "r") as f:
        backend_content = f.read()
    assert "USER custode" in backend_content

    with open(frontend_dockerfile, "r") as f:
        frontend_content = f.read()
    assert "USER nginx" in frontend_content


def test_backup_and_restore_cycle_on_disposable_database():
    """Verify that backup and restore operates deterministically on a disposable database."""
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
        src_db = f.name
    with tempfile.NamedTemporaryFile(suffix=".backup", delete=False) as f:
        backup_file = f.name
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
        restored_db = f.name

    try:
        # Populate source DB
        conn = sqlite3.connect(src_db)
        conn.execute("CREATE TABLE audit_sample (id INT PRIMARY KEY, action TEXT);")
        conn.execute("INSERT INTO audit_sample VALUES (1, 'EXECUTE_TOOL');")
        conn.execute("INSERT INTO audit_sample VALUES (2, 'APPROVE_REQUEST');")
        conn.commit()
        conn.close()

        # Backup
        ok, msg, meta = backup_sqlite(src_db, backup_file)
        assert ok, f"Backup failed: {msg}"
        assert int(meta["size_bytes"]) > 0
        assert len(meta["sha256"]) == 64

        # Restore
        ok_rest, msg_rest = restore_sqlite(backup_file, restored_db)
        assert ok_rest, f"Restore failed: {msg_rest}"

        # Verify data
        r_conn = sqlite3.connect(restored_db)
        rows = r_conn.execute("SELECT id, action FROM audit_sample ORDER BY id;").fetchall()
        r_conn.close()
        assert rows == [(1, "EXECUTE_TOOL"), (2, "APPROVE_REQUEST")]
    finally:
        for path in (src_db, backup_file, restored_db):
            if os.path.exists(path):
                os.remove(path)


def test_sentinel_repository_isolation():
    """Verify that Sentinel AI reference repository remains 100% isolated and clean."""
    sentinel_path = os.path.abspath(
        os.path.join(os.path.dirname(__file__), "..", "..", "..", "..", "sentinel-ai")
    )
    assert os.path.exists(sentinel_path), f"Sentinel path {sentinel_path} does not exist"

    git_res = subprocess.run(
        ["git", "status", "--porcelain"],
        cwd=sentinel_path,
        capture_output=True,
        text=True,
    )
    assert git_res.returncode == 0
    assert git_res.stdout.strip() == "", f"Sentinel working tree is dirty: {git_res.stdout}"
