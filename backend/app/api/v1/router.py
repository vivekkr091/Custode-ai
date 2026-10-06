"""API v1 router registry."""

from fastapi import APIRouter
from app.api.v1.endpoints import (
    agents,
    approvals,
    audit,
    auth,
    credentials,
    decisions,
    executions,
    health,
    organizations,
    permissions,
    policies,
    risk_assessments,
    runtime_actions,
    tool_operations,
    tools,
    users,
    observability,
    findings,
    llm,
    mcp,
    behavior,
    integrations,
)

v1_router = APIRouter()
v1_router.include_router(health.router)
v1_router.include_router(organizations.router)
v1_router.include_router(users.router)
v1_router.include_router(agents.router)
v1_router.include_router(credentials.router)
v1_router.include_router(auth.router)
v1_router.include_router(tools.router)
v1_router.include_router(tool_operations.router)
v1_router.include_router(permissions.router)
v1_router.include_router(policies.router)
v1_router.include_router(runtime_actions.router)
v1_router.include_router(risk_assessments.router)
v1_router.include_router(decisions.router)
v1_router.include_router(approvals.router)
v1_router.include_router(executions.router)
v1_router.include_router(audit.router)
v1_router.include_router(observability.router)
v1_router.include_router(findings.router)
v1_router.include_router(llm.router)
v1_router.include_router(mcp.router)
v1_router.include_router(behavior.router)
v1_router.include_router(integrations.router)
