#!/usr/bin/env python3
"""Database readiness check script for CUSTODE production deployments.

Polls the configured database until it responds to queries or timeout expires.
Exits with code 0 on success, or 1 on timeout/failure.
"""

import asyncio
import os
import sys
import time

# Ensure backend root is on sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from sqlalchemy import text
from app.core.config import get_settings
from app.db.session import get_engine, close_engine


async def wait_for_db(max_retries: int = 30, retry_delay: float = 2.0) -> bool:
    """Attempt database connection with retries and exponential backoff."""
    settings = get_settings()
    # Mask credentials for logging
    db_masked = settings.DATABASE_URL
    if "@" in db_masked:
        proto, rest = db_masked.split("://", 1)
        _, host_part = rest.split("@", 1)
        db_masked = f"{proto}://[REDACTED]@{host_part}"

    print(f"[custode-db-wait] Checking database connectivity: {db_masked}")

    for attempt in range(1, max_retries + 1):
        try:
            engine = get_engine()
            async with engine.connect() as conn:
                await conn.execute(text("SELECT 1"))
            print(f"[custode-db-wait] Database ready on attempt {attempt}/{max_retries}.")
            await close_engine()
            return True
        except Exception as e:
            print(f"[custode-db-wait] Attempt {attempt}/{max_retries} failed: {type(e).__name__}. Retrying in {retry_delay}s...")
            await asyncio.sleep(retry_delay)

    print(f"[custode-db-wait] ERROR: Database connection failed after {max_retries} attempts.")
    await close_engine()
    return False


def main() -> None:
    max_retries = int(os.environ.get("DB_WAIT_MAX_RETRIES", "30"))
    retry_delay = float(os.environ.get("DB_WAIT_RETRY_DELAY", "2.0"))

    success = asyncio.run(wait_for_db(max_retries=max_retries, retry_delay=retry_delay))
    if not success:
        sys.exit(1)


if __name__ == "__main__":
    main()
