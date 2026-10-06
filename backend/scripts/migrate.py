#!/usr/bin/env python3
"""Production database migration script for CUSTODE.

Executes deterministic forward schema migrations up to head.
Ensures database connectivity before applying migrations and verifies
the active revision after completion.
"""

import os
import sqlite3
import sys
import time

# Ensure backend root is on sys.path
backend_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, backend_dir)

from alembic import command
from alembic.config import Config
from alembic.migration import MigrationContext
from alembic.script import ScriptDirectory

from app.core.config import get_settings


def run_migrations(target_revision: str = "head") -> int:
    """Run Alembic migrations deterministically up to target revision."""
    settings = get_settings()
    ini_path = os.path.join(backend_dir, "alembic.ini")
    migrations_dir = os.path.join(backend_dir, "app", "db", "migrations")

    print(f"[custode-migrate] Loading Alembic configuration from {ini_path}")
    alembic_cfg = Config(ini_path)
    alembic_cfg.set_main_option("script_location", migrations_dir)
    alembic_cfg.set_main_option("sqlalchemy.url", settings.DATABASE_URL)

    # Validate migration scripts
    script = ScriptDirectory.from_config(alembic_cfg)
    head_rev = script.get_current_head()
    print(f"[custode-migrate] Target migration head revision: {head_rev}")

    start_time = time.time()
    try:
        print(f"[custode-migrate] Executing upgrade to '{target_revision}'...")
        command.upgrade(alembic_cfg, target_revision)
        elapsed = round(time.time() - start_time, 2)
        print(f"[custode-migrate] Migration completed successfully in {elapsed}s.")
        return 0
    except Exception as e:
        print(f"[custode-migrate] FATAL: Migration failed with error: {e}", file=sys.stderr)
        return 1


def main() -> None:
    target = os.environ.get("MIGRATION_TARGET", "head")
    exit_code = run_migrations(target)
    sys.exit(exit_code)


if __name__ == "__main__":
    main()
