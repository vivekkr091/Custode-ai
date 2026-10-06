"""Automated tests for Alembic database migrations."""

import os
import sqlite3
import tempfile
from alembic import command
from alembic.config import Config


def test_alembic_migration_upgrade_and_downgrade() -> None:
    """Ensure all Alembic migrations apply cleanly and can be downgraded deterministically."""
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as tmp:
        db_path = tmp.name

    try:
        backend_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
        ini_path = os.path.join(backend_dir, "alembic.ini")
        alembic_cfg = Config(ini_path)
        alembic_cfg.set_main_option("script_location", os.path.join(backend_dir, "app", "db", "migrations"))
        alembic_cfg.set_main_option("sqlalchemy.url", f"sqlite+aiosqlite:///{db_path}")

        # 1. Apply upgrade to head
        command.upgrade(alembic_cfg, "head")

        conn = sqlite3.connect(db_path)
        tables = [
            row[0]
            for row in conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table';"
            ).fetchall()
        ]
        conn.close()
        assert "organizations" in tables
        assert "users" in tables
        assert "memberships" in tables
        assert "agents" in tables
        assert "agent_credentials" in tables
        assert "tools" in tables
        assert "tool_operations" in tables
        assert "permissions" in tables
        assert "policies" in tables
        assert "policy_versions" in tables
        assert "runtime_actions" in tables
        assert "risk_assessments" in tables
        assert "decisions" in tables
        assert "approval_requests" in tables
        assert "executions" in tables
        assert "audit_events" in tables
        assert "security_scans" in tables
        assert "security_findings" in tables
        assert "agent_behavior_baselines" in tables
        assert "behavioral_anomalies" in tables

        # 2. Revert downgrade to base
        command.downgrade(alembic_cfg, "base")

        conn = sqlite3.connect(db_path)
        tables_after_downgrade = [
            row[0]
            for row in conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table';"
            ).fetchall()
        ]
        conn.close()
        assert "behavioral_anomalies" not in tables_after_downgrade
        assert "agent_behavior_baselines" not in tables_after_downgrade
        assert "security_findings" not in tables_after_downgrade
        assert "security_scans" not in tables_after_downgrade
        assert "audit_events" not in tables_after_downgrade
        assert "executions" not in tables_after_downgrade
        assert "approval_requests" not in tables_after_downgrade
        assert "decisions" not in tables_after_downgrade
        assert "risk_assessments" not in tables_after_downgrade
        assert "runtime_actions" not in tables_after_downgrade
        assert "policy_versions" not in tables_after_downgrade
        assert "policies" not in tables_after_downgrade
        assert "permissions" not in tables_after_downgrade
        assert "tool_operations" not in tables_after_downgrade
        assert "tools" not in tables_after_downgrade
        assert "agent_credentials" not in tables_after_downgrade
        assert "agents" not in tables_after_downgrade
        assert "organizations" not in tables_after_downgrade

        # 3. Re-apply upgrade to ensure idempotency and schema reproducibility
        command.upgrade(alembic_cfg, "head")

        conn = sqlite3.connect(db_path)
        tables_reapplied = [
            row[0]
            for row in conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table';"
            ).fetchall()
        ]
        conn.close()
        assert "executions" in tables_reapplied
        assert "audit_events" in tables_reapplied
        assert "security_scans" in tables_reapplied
        assert "security_findings" in tables_reapplied
        assert "agent_behavior_baselines" in tables_reapplied
        assert "behavioral_anomalies" in tables_reapplied
        assert "approval_requests" in tables_reapplied
        assert "decisions" in tables_reapplied
        assert "risk_assessments" in tables_reapplied
        assert "runtime_actions" in tables_reapplied
        assert "policies" in tables_reapplied
        assert "policy_versions" in tables_reapplied
        assert "permissions" in tables_reapplied
        assert "tool_operations" in tables_reapplied
        assert "tools" in tables_reapplied
        assert "agent_credentials" in tables_reapplied
        assert "agents" in tables_reapplied
        assert "organizations" in tables_reapplied
    finally:
        if os.path.exists(db_path):
            os.remove(db_path)
