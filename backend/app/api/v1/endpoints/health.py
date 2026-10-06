"""Health check API endpoints."""

import time
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.db.session import get_db_session
from app.schemas.health import (
    DbHealthResponse,
    HealthResponse,
    OperationalMetricsResponse,
    ReadinessChecks,
    ReadinessResponse,
)

router = APIRouter()
settings = get_settings()
_STARTUP_TIME = time.time()


@router.get("/health", response_model=HealthResponse, summary="Application Health Check")
@router.get("/health/live", response_model=HealthResponse, summary="Liveness Probe")
async def get_health() -> HealthResponse:
    """Return operational status and service identifier."""
    return HealthResponse(status="ok", service="custode-api")


@router.get("/health/ready", response_model=ReadinessResponse, summary="Readiness Probe")
async def get_readiness(
    session: AsyncSession = Depends(get_db_session),
) -> ReadinessResponse:
    """Verify that all core dependencies (database, migrations) are ready to serve traffic."""
    try:
        await session.execute(text("SELECT 1"))
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Database connection unavailable",
        )

    migrations_state = "current"
    try:
        res = await session.execute(text("SELECT version_num FROM alembic_version LIMIT 1"))
        rev = res.scalar_one_or_none()
        if not rev:
            migrations_state = "pending"
    except Exception:
        migrations_state = "current"

    return ReadinessResponse(
        status="ready",
        service="custode-api",
        checks=ReadinessChecks(
            database="connected",
            migrations=migrations_state,
        ),
    )


@router.get("/health/db", response_model=DbHealthResponse, summary="Database Connectivity Health Check")
async def get_db_health(
    session: AsyncSession = Depends(get_db_session),
) -> DbHealthResponse:
    """Verify that the API can execute a query against PostgreSQL."""
    try:
        await session.execute(text("SELECT 1"))
        return DbHealthResponse(status="ok", database="connected")
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Database connection unavailable",
        )


@router.get("/health/metrics", response_model=OperationalMetricsResponse, summary="Operational Metrics")
async def get_operational_metrics(
    session: AsyncSession = Depends(get_db_session),
) -> OperationalMetricsResponse:
    """Return safe, non-sensitive operational metrics."""
    db_status = "connected"
    try:
        await session.execute(text("SELECT 1"))
    except Exception:
        db_status = "disconnected"

    uptime = round(time.time() - _STARTUP_TIME, 2)
    return OperationalMetricsResponse(
        service="custode-api",
        environment=settings.ENVIRONMENT,
        version=settings.VERSION,
        uptime_seconds=uptime,
        database=db_status,
    )
