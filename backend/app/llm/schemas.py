"""Pydantic schemas for the CUSTODE LLM Security Gateway."""

from datetime import datetime
from typing import Any, Dict, List, Literal, Optional, Union
import uuid

from pydantic import BaseModel, Field, field_validator


class ChatMessage(BaseModel):
    """Normalized chat message structure."""
    role: Literal["system", "user", "assistant", "tool"] = "user"
    content: str = Field(..., max_length=100000, description="Text content of the message")
    name: Optional[str] = Field(None, max_length=100)
    tool_calls: Optional[List[Dict[str, Any]]] = None
    tool_call_id: Optional[str] = None


class ToolDefinition(BaseModel):
    """Normalized tool/function declaration available to the model."""
    name: str = Field(..., max_length=100)
    description: Optional[str] = Field(None, max_length=1000)
    parameters: Optional[Dict[str, Any]] = None


class ToolCall(BaseModel):
    """Normalized function/tool call emitted by the model."""
    id: str
    type: str = "function"
    function: Dict[str, Any]  # e.g. {"name": "query_database", "arguments": "{...}"}


class LLMRequest(BaseModel):
    """Normalized inbound request to the LLM Gateway."""
    messages: List[ChatMessage] = Field(..., min_length=1, max_length=100)
    provider: str = Field("mock", max_length=50)
    model: str = Field("mock-gpt-4", max_length=100)
    system_prompt: Optional[str] = Field(None, max_length=50000)
    temperature: Optional[float] = Field(0.7, ge=0.0, le=2.0)
    max_tokens: Optional[int] = Field(1000, ge=1, le=8192)
    tools: Optional[List[ToolDefinition]] = None
    stream: bool = False
    metadata: Optional[Dict[str, Any]] = None
    environment: Optional[str] = None

    @field_validator("messages")
    @classmethod
    def validate_messages(cls, v: List[ChatMessage]) -> List[ChatMessage]:
        if not v:
            raise ValueError("Messages list cannot be empty")
        return v


class LLMUsage(BaseModel):
    """Normalized token accounting."""
    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0


class LLMResponse(BaseModel):
    """Normalized, sanitized outbound response from the LLM Gateway."""
    request_id: uuid.UUID
    interaction_id: uuid.UUID
    provider: str
    model: str
    content: Optional[str] = None
    tool_calls: Optional[List[ToolCall]] = None
    usage: LLMUsage = Field(default_factory=LLMUsage)
    finish_reason: str = "stop"
    latency_ms: float = 0.0
    security_status: str  # allowed, blocked, output_blocked, approval_required
    decision: str  # allow, block, require_approval
    input_findings: List[Dict[str, Any]] = Field(default_factory=list)
    output_findings: List[Dict[str, Any]] = Field(default_factory=list)
    approval_id: Optional[uuid.UUID] = None
    created_at: datetime


class LLMInteractionResponse(BaseModel):
    """Audit view of an LLM Interaction."""
    id: uuid.UUID
    organization_id: uuid.UUID
    agent_id: uuid.UUID
    runtime_action_id: Optional[uuid.UUID] = None
    request_id: uuid.UUID
    provider: str
    model: str
    environment: str
    status: str
    input_scan_status: str
    output_scan_status: str
    decision: str
    risk_score: float
    risk_level: str
    latency_ms: float
    input_tokens: int
    output_tokens: int
    total_tokens: int
    input_hash: str
    output_hash: Optional[str] = None
    sanitized_prompt_preview: Optional[str] = None
    sanitized_output_preview: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None
    created_at: datetime
    completed_at: Optional[datetime] = None

    model_config = {"from_attributes": True}


class ToolCallExecutionRequest(BaseModel):
    """Request to safely execute an untrusted LLM-generated tool call."""
    tool_name: str = Field(..., max_length=100)
    operation_name: str = Field(..., max_length=100)
    parameters: Dict[str, Any] = Field(default_factory=dict)
    environment: Optional[str] = None


class ToolCallExecutionResponse(BaseModel):
    """Authoritative result of executing an LLM tool call through the CUSTODE Control Plane."""
    interaction_id: uuid.UUID
    runtime_action_id: uuid.UUID
    decision: str
    status: str
    result: Optional[Any] = None
    error: Optional[str] = None


class LLMMetricsResponse(BaseModel):
    """Aggregated LLM security metrics for an organization."""
    total_interactions: int
    blocked_count: int
    approval_required_count: int
    output_blocked_count: int
    total_input_findings: int
    total_output_findings: int
    provider_distribution: Dict[str, int]
    model_distribution: Dict[str, int]
    status_distribution: Dict[str, int]
    total_tokens: int
