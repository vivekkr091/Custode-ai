"""Runtime action models and status enumerations."""

from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, Optional
from pydantic import BaseModel, Field


class ActionType(str, Enum):
    """Categorization of agent operations."""

    TOOL_CALL = "tool_call"
    API_REQUEST = "api_request"
    SHELL_EXEC = "shell_exec"
    DATABASE_QUERY = "database_query"
    FILE_OPERATION = "file_operation"
    CUSTOM = "custom"


class ActionDecision(str, Enum):
    """Disposition outcome decided by CUSTODE control plane."""

    ALLOW = "ALLOW"
    BLOCK = "BLOCK"
    REQUIRE_APPROVAL = "REQUIRE_APPROVAL"


class RuntimeAction(BaseModel):
    """Normalized representation of an operation requested by an AI agent."""

    action_id: str = Field(..., description="Unique UUID for this runtime action")
    agent_id: str = Field(..., description="Identity of the requesting agent")
    tenant_id: str = Field(default="default", description="Tenancy partition")
    action_type: ActionType = Field(default=ActionType.TOOL_CALL)
    target: str = Field(..., description="Target tool name, API endpoint, or command")
    parameters: Dict[str, Any] = Field(default_factory=dict, description="Execution parameters or arguments")
    context: Dict[str, Any] = Field(default_factory=dict, description="Environmental and conversational context")
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    model_config = {"frozen": False}
