"""Controlled executor interface, execution context, and result structures."""

from abc import ABC, abstractmethod
from copy import deepcopy
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional, Set
import uuid

# Keys that often contain sensitive secrets that should be sanitized for safe logging and execution output
SENSITIVE_KEYS: Set[str] = {
    "password",
    "secret",
    "token",
    "api_key",
    "apikey",
    "access_token",
    "refresh_token",
    "private_key",
    "auth_header",
    "authorization",
    "credential",
    "credentials",
}

# Dangerous keys that should be stripped
DANGEROUS_KEYS: Set[str] = {
    "__proto__",
    "__class__",
    "__globals__",
    "constructor",
}


def sanitize_parameters(params: Dict[str, Any], depth: int = 0) -> Dict[str, Any]:
    """Sanitize parameters by stripping dangerous prototype keys and masking secrets.
    
    Operates safely and deterministically up to a maximum recursion depth.
    """
    if not isinstance(params, dict) or depth > 10:
        return {}

    cleaned: Dict[str, Any] = {}
    for k, v in params.items():
        # Prevent prototype pollution / dangerous attributes
        key_str = str(k).strip()
        if key_str in DANGEROUS_KEYS:
            continue

        # Check for sensitive key names
        if key_str.lower() in SENSITIVE_KEYS:
            cleaned[key_str] = "[REDACTED]"
            continue

        if isinstance(v, dict):
            cleaned[key_str] = sanitize_parameters(v, depth + 1)
        elif isinstance(v, list):
            cleaned[key_str] = [
                sanitize_parameters(item, depth + 1) if isinstance(item, dict) else item
                for item in v
            ]
        else:
            cleaned[key_str] = v

    return cleaned


@dataclass
class ExecutionContext:
    """Execution context containing all security governance and action parameters."""

    runtime_action_id: uuid.UUID
    organization_id: uuid.UUID
    agent_id: uuid.UUID
    tool_id: uuid.UUID
    operation_id: uuid.UUID
    action_type: str
    environment: str
    parameters: Dict[str, Any] = field(default_factory=dict)
    resource: Optional[str] = None
    resource_type: Optional[str] = None
    decision_id: Optional[uuid.UUID] = None
    approval_id: Optional[uuid.UUID] = None

    def get_sanitized_parameters(self) -> Dict[str, Any]:
        """Return a copy of parameters with sensitive data masked and dangerous keys stripped."""
        return sanitize_parameters(self.parameters)


@dataclass
class ExecutionResult:
    """Standardized deterministic execution result produced by a tool handler."""

    success: bool
    output: Optional[Dict[str, Any]] = None
    error_code: Optional[str] = None
    error_message: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None


class BaseActionExecutor(ABC):
    """Abstract interface for executing approved runtime actions."""

    @abstractmethod
    async def execute(self, context: ExecutionContext) -> ExecutionResult:
        """Dispatch action to destination tool handler after validation and approval."""
        pass
