"""Alembic environment configuration for CUSTODE.

Reads DATABASE_URL from alembic config, environment variables, or application settings
and wires up the async SQLAlchemy engine for online migrations.
"""

import asyncio
import os
import sys
from logging.config import fileConfig

from alembic import context
from sqlalchemy import pool
from sqlalchemy.ext.asyncio import create_async_engine

# ── make sure `app` package is importable ────────────────────────────────────
BACKEND_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if BACKEND_DIR not in sys.path:
    sys.path.insert(0, BACKEND_DIR)

# Import all models so their metadata registers with Base before autogenerate.
from app.db.base import Base  # noqa: E402
import app.db.models  # noqa: E402, F401  – side-effect: populates Base.metadata

# Alembic config object
config = context.config

# Logging setup from alembic.ini
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata


def get_database_url() -> str:
    """Return the database URL from alembic config, env, or app settings."""
    cfg_url = config.get_main_option("sqlalchemy.url")
    if cfg_url:
        if cfg_url.startswith("sqlite:///") and not cfg_url.startswith("sqlite+aiosqlite:///"):
            return cfg_url.replace("sqlite:///", "sqlite+aiosqlite:///")
        return cfg_url

    env_url = os.environ.get("DATABASE_URL")
    if env_url:
        return env_url

    from app.core.config import get_settings
    return get_settings().DATABASE_URL


def run_migrations_offline() -> None:
    """Run migrations in 'offline' mode (generate SQL without a live connection)."""
    context.configure(
        url=get_database_url(),
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        compare_type=True,
    )
    with context.begin_transaction():
        context.run_migrations()


def do_run_migrations(connection) -> None:  # type: ignore[type-arg]
    context.configure(
        connection=connection,
        target_metadata=target_metadata,
        compare_type=True,
    )
    with context.begin_transaction():
        context.run_migrations()


async def run_migrations_online() -> None:
    """Run migrations in 'online' mode using an async engine."""
    connectable = create_async_engine(
        get_database_url(),
        poolclass=pool.NullPool,
    )
    async with connectable.connect() as connection:
        await connection.run_sync(do_run_migrations)
    await connectable.dispose()


if context.is_offline_mode():
    run_migrations_offline()
else:
    asyncio.run(run_migrations_online())
