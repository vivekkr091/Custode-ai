"""Security policy profiles and context builders for CUSTODE MCP Security Layer."""

from typing import Any, Dict, List, Optional
import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from app.engines.policy.evaluator import PolicyEngine, PolicyEvaluationResult
from app.schemas.policy import ActionContext

# Dedicated Sentinel scanning profiles for MCP stages
MCP_TOOL_DISCOVERY_PROFILE: List[str] = [
    "prompt_injection",
    "secrets_scanner",
    "pii",
    "harmful_content",
    "toxicity",
    "obfuscation",
    "blocked_terms",
]

MCP_INPUT_PROFILE: List[str] = [
    "prompt_injection",
    "secrets_scanner",
    "pii",
    "harmful_content",
    "toxicity",
    "obfuscation",
    "code_scanner",
    "blocked_terms",
]

MCP_OUTPUT_PROFILE: List[str] = [
    "secrets_scanner",
    "pii",
    "harmful_content",
    "toxicity",
    "code_scanner",
    "blocked_terms",
]


def build_mcp_action_context(
    agent_id: uuid.UUID,
    agent_environment: str,
    tool_id: uuid.UUID,
    operation_id: uuid.UUID,
    mcp_server_id: uuid.UUID,
    mcp_server_trust_level: str,
    mcp_tool_id: uuid.UUID,
    mcp_tool_slug: str,
    schema_hash: str,
    risk_level: str = "medium",
    request_id: Optional[str] = None,
) -> ActionContext:
    """Build an authoritative ActionContext enriched with MCP boundary fields."""
    return ActionContext(
        agent_id=agent_id,
        agent_environment=agent_environment,
        tool_id=tool_id,
        tool_type="mcp",
        operation_id=operation_id,
        operation_type="execute",
        operation_risk_level=risk_level,
        resource=f"mcp://{mcp_server_id}/{mcp_tool_slug}",
        request_id=request_id,
    )


async def evaluate_mcp_security_policy(
    session: AsyncSession,
    organization_id: uuid.UUID,
    context: ActionContext,
) -> PolicyEvaluationResult:
    """Evaluate tenant-scoped security policies for an MCP operation."""
    return await PolicyEngine.evaluate(session, organization_id, context)
