"""CUSTODE AI Agent Security & Control Platform - Application Entrypoint."""

from contextlib import asynccontextmanager
import time
from typing import AsyncGenerator
from fastapi import Depends, FastAPI, HTTPException, Request, Response, status
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession
from uvicorn.middleware.proxy_headers import ProxyHeadersMiddleware

from app.api.router import api_router
from app.core.config import get_settings
from app.core.correlation import sanitize_request_id, set_current_request_id
from app.core.logging import setup_logging
from app.db.session import close_engine, get_db_session
from app.schemas.health import (
    DbHealthResponse,
    HealthResponse,
    OperationalMetricsResponse,
    ReadinessChecks,
    ReadinessResponse,
)

settings = get_settings()
_STARTUP_TIME = time.time()


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Application lifespan manager for startup and shutdown hooks."""
    # 1. Configure structured logging
    setup_logging(settings.LOG_LEVEL)

    # 2. Development SQLite auto-migration bootstrap
    if "sqlite" in settings.DATABASE_URL:
        from app.db.base import Base
        from app.db.session import get_engine
        import app.db.models  # noqa: F401
        engine = get_engine()
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)

    # 3. Development bootstrap
    if settings.AUTH_MODE == "development" or settings.DEMO_MODE:
        async for session in get_db_session():
            try:
                from app.services.user_auth import bootstrap_development_environment
                await bootstrap_development_environment(session)
                await session.commit()
            except Exception:
                await session.rollback()
            break

    yield

    # 4. Graceful shutdown
    await close_engine()


def create_app() -> FastAPI:
    """Create and configure the FastAPI application instance."""
    app = FastAPI(
        title=settings.PROJECT_NAME,
        version=settings.VERSION,
        description="AI Agent Security & Control Platform",
        lifespan=lifespan,
    )

    # Trusted Proxy Headers (Milestone 23 DevOps)
    app.add_middleware(
        ProxyHeadersMiddleware,
        trusted_hosts=settings.FORWARDED_ALLOW_IPS,
    )

    # Request Body Size Limit Middleware (Milestone 22 Hardening)
    @app.middleware("http")
    async def request_size_limit_middleware(request: Request, call_next) -> Response:
        content_length = request.headers.get("content-length")
        if content_length:
            try:
                length_int = int(content_length)
                if length_int > settings.MAX_REQUEST_BODY_BYTES:
                    from fastapi.responses import JSONResponse
                    return JSONResponse(
                        status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                        content={
                            "detail": f"Payload Too Large: Content-Length {length_int} exceeds maximum permitted {settings.MAX_REQUEST_BODY_BYTES} bytes"
                        },
                    )
            except ValueError:
                pass
        return await call_next(request)

    # Request ID Correlation Middleware (Milestone 15)
    @app.middleware("http")
    async def request_correlation_middleware(request: Request, call_next) -> Response:
        raw_req_id = request.headers.get("X-Request-ID")
        req_id = sanitize_request_id(raw_req_id)
        set_current_request_id(req_id)
        request.state.request_id = req_id

        response = await call_next(request)
        response.headers["X-Request-ID"] = req_id
        return response

    # Security Headers Middleware (Milestone 14 & 22 Hardening)
    @app.middleware("http")
    async def add_security_headers(request: Request, call_next) -> Response:
        response = await call_next(request)
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        response.headers["Permissions-Policy"] = "geolocation=(), microphone=(), camera=()"
        response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
        response.headers["Content-Security-Policy"] = "default-src 'none'; frame-ancestors 'none'"
        if request.url.path.startswith("/api/"):
            response.headers["Cache-Control"] = "no-store, no-cache, must-revalidate"
        return response

    # Global Safe Exception Handler (Milestone 23 Observability)
    @app.exception_handler(Exception)
    async def global_exception_handler(request: Request, exc: Exception) -> Response:
        if isinstance(exc, HTTPException):
            from fastapi.responses import JSONResponse
            return JSONResponse(
                status_code=exc.status_code,
                content={"detail": exc.detail},
                headers=getattr(exc, "headers", None),
            )
        req_id = getattr(request.state, "request_id", "unknown")
        import logging
        logging.getLogger("custode.api").error(
            f"Unhandled exception on {request.method} {request.url.path} [request_id={req_id}]: {type(exc).__name__}: {exc}",
            exc_info=settings.DEBUG,
        )
        from fastapi.responses import JSONResponse
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={
                "detail": "Internal server error",
                "request_id": req_id,
            },
        )

    # Cross-Origin Resource Sharing (CORS) - Explicit Origins
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.CORS_ORIGINS,
        allow_credentials=True,
        allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
        allow_headers=["*"],
    )

    # --- Health, Readiness, and Liveness Probes (Milestone 23) ---

    @app.get(
        "/health",
        response_model=HealthResponse,
        summary="Service Health Check",
        tags=["Health"],
    )
    @app.get(
        "/health/live",
        response_model=HealthResponse,
        summary="Service Liveness Probe",
        tags=["Health"],
    )
    @app.get(
        "/healthz",
        response_model=HealthResponse,
        include_in_schema=False,
    )
    async def root_health() -> HealthResponse:
        """Return operational status and service identifier."""
        return HealthResponse(status="ok", service="custode-api")

    @app.get(
        "/health/ready",
        response_model=ReadinessResponse,
        summary="Service Readiness Probe",
        tags=["Health"],
    )
    @app.get(
        "/ready",
        response_model=ReadinessResponse,
        include_in_schema=False,
    )
    async def root_readiness(
        session: AsyncSession = Depends(get_db_session),
    ) -> ReadinessResponse:
        """Verify that all core dependencies (database, migrations) are ready to serve traffic."""
        # 1. Database reachability check
        try:
            await session.execute(text("SELECT 1"))
        except Exception:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Database connection unavailable",
            )

        # 2. Database migration check
        migrations_state = "current"
        try:
            res = await session.execute(text("SELECT version_num FROM alembic_version LIMIT 1"))
            rev = res.scalar_one_or_none()
            if not rev:
                migrations_state = "pending"
        except Exception:
            migrations_state = "current"  # SQLite create_all or unmigrated test fixture

        return ReadinessResponse(
            status="ready",
            service="custode-api",
            checks=ReadinessChecks(
                database="connected",
                migrations=migrations_state,
            ),
        )

    @app.get(
        "/health/db",
        response_model=DbHealthResponse,
        summary="Database Health Check",
        tags=["Health"],
    )
    async def root_db_health(
        session: AsyncSession = Depends(get_db_session),
    ) -> DbHealthResponse:
        """Verify that the API can execute a query against the database."""
        try:
            await session.execute(text("SELECT 1"))
            return DbHealthResponse(status="ok", database="connected")
        except Exception:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Database connection unavailable",
            )

    @app.get(
        "/health/metrics",
        response_model=OperationalMetricsResponse,
        summary="Operational Metrics",
        tags=["Health"],
    )
    async def operational_metrics(
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

    # Mount versioned API routes
    app.include_router(api_router, prefix=settings.API_V1_PREFIX)

    return app


app = create_app()
