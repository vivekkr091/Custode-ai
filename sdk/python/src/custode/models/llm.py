"""LLM Security Gateway models for CUSTODE SDK."""

from typing import Any, Dict, List, Literal, Optional
from pydantic import Field

from custode.models.base import CUSTODEModel


class ChatMessage(CUSTODEModel):
    """Normalized chat message."""

    role: Literal["system", "user", "assistant", "tool"] = "user"
    content: str
    name: Optional[str] = None
    tool_calls: Optional[List[Dict[str, Any]]] = None
    tool_call_id: Optional[str] = None


class LLMRequest(CUSTODEModel):
    """Inbound request to the CUSTODE LLM Security Gateway."""

    messages: List[ChatMessage]
    provider: str = "mock"
    model: str = "mock-gpt-4"
    system_prompt: Optional[str] = None
    temperature: Optional[float] = 0.7
    max_tokens: Optional[int] = 1000
    tools: Optional[List[Dict[str, Any]]] = None
    stream: bool = False
    metadata: Optional[Dict[str, Any]] = None
    environment: Optional[str] = None


class LLMResponse(CUSTODEModel):
    """Mediated, scanned LLM completion response."""

    request_id: str
    interaction_id: str
    provider: str
    model: str
    content: Optional[str] = None
    tool_calls: List[Dict[str, Any]] = Field(default_factory=list)
    usage: Dict[str, Any] = Field(default_factory=dict)
    finish_reason: Optional[str] = None
    latency_ms: float = 0.0
    security_status: str
    decision: str
    input_findings: List[Dict[str, Any]] = Field(default_factory=list)
    output_findings: List[Dict[str, Any]] = Field(default_factory=list)
    approval_id: Optional[str] = None
    created_at: Any

    @property
    def is_blocked(self) -> bool:
        """True if the prompt or completion was blocked by security policies."""
        return self.decision.lower() == "block"

    @property
    def is_allowed(self) -> bool:
        """True if execution completed cleanly without security denial."""
        return self.decision.lower() == "allow"


class LLMInteraction(CUSTODEModel):
    """Historical audit record of an LLM Gateway interaction."""

    id: str
    organization_id: str
    agent_id: str
    provider: str
    model: str
    status: str
    security_status: str
    decision: str
    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0
    latency_ms: float = 0.0
    created_at: Any


class LLMInteractionList(CUSTODEModel):
    """Paginated collection of LLM interactions."""

    items: List[LLMInteraction] = Field(default_factory=list)
    total: int = 0
