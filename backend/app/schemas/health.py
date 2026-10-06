"""Pydantic health check schemas."""

from typing import Dict, Optional
from pydantic import BaseModel, Field


class HealthResponse(BaseModel):
    """Health check response payload schema."""

    status: str = Field(default="ok", description="Service operational status")
    service: str = Field(default="custode-api", description="Service identifier")


class DbHealthResponse(BaseModel):
    """Database health check response payload schema."""

    status: str = Field(default="ok", description="Database connection status")
    database: str = Field(default="connected", description="Database reachability state")


class ReadinessChecks(BaseModel):
    """Component-level health check states for readiness probe."""

    database: str = Field(description="Database connectivity state")
    migrations: str = Field(description="Database schema migration state")


class ReadinessResponse(BaseModel):
    """Readiness probe response payload schema."""

    status: str = Field(default="ready", description="Overall readiness state (ready or unready)")
    service: str = Field(default="custode-api", description="Service identifier")
    checks: ReadinessChecks = Field(description="Individual dependency check results")


class OperationalMetricsResponse(BaseModel):
    """Basic non-sensitive operational metrics."""

    service: str = Field(default="custode-api", description="Service identifier")
    environment: str = Field(description="Current deployment environment")
    version: str = Field(description="Application release version")
    uptime_seconds: float = Field(description="Process uptime in seconds")
    database: str = Field(description="Database connectivity state")
