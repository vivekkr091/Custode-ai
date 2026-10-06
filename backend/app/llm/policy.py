"""Policy context and scanning profile definitions for the LLM Gateway."""

from typing import Any, Dict, List, Optional
import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from app.engines.policy.evaluator import PolicyEngine, PolicyEvaluationResult
from app.schemas.policy import ActionContext

# Explicit scanner profiles for LLM Gateway stages
LLM_INPUT_PROFILE: List[str] = [
    "prompt_injection",
    "secrets_scanner",
    "pii",
    "harmful_content",
    "toxicity",
    "obfuscation",
    "blocked_terms",
    "code_scanner",
]

LLM_OUTPUT_PROFILE: List[str] = [
    "secrets_scanner",
    "pii",
    "harmful_content",
    "toxicity",
    "code_scanner",
    "blocked_terms",
]


def build_llm_action_context(
    agent_id: uuid.UUID,
    agent_environment: str,
    tool_id: uuid.UUID,
    operation_id: uuid.UUID,
    provider: str,
    model: str,
    direction: str = "INPUT",
    token_usage: int = 0,
    finding_category: Optional[str] = None,
    finding_severity: Optional[str] = None,
    request_id: Optional[str] = None,
) -> ActionContext:
    """Build an authoritative ActionContext enriched with LLM security fields."""
    return ActionContext(
        agent_id=agent_id,
        agent_environment=agent_environment,
        tool_id=tool_id,
        tool_type="api",
        operation_id=operation_id,
        operation_type="execute",
        operation_risk_level="medium",
        resource=f"{provider}/{model}",
        request_id=request_id,
    )


async def evaluate_llm_security_policy(
    session: AsyncSession,
    organization_id: uuid.UUID,
    context: ActionContext,
) -> PolicyEvaluationResult:
    """Evaluate tenant security policies against the LLM action context."""
    return await PolicyEngine.evaluate(session, organization_id, context)
