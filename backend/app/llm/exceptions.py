"""Exceptions hierarchy for CUSTODE LLM Security Gateway."""

from typing import Any, Dict, List, Optional
import uuid


class LLMError(Exception):
    """Base exception for all LLM Gateway errors."""

    def __init__(self, message: str, code: str = "LLM_GATEWAY_ERROR", details: Optional[Dict[str, Any]] = None):
        super().__init__(message)
        self.message = message
        self.code = code
        self.details = details or {}


class LLMProviderError(LLMError):
    """Raised when an external LLM provider encounters a network or service failure."""

    def __init__(self, provider: str, error_message: str):
        super().__init__(
            f"Provider '{provider}' request failed: {error_message}",
            code="PROVIDER_ERROR",
            details={"provider": provider, "error": error_message},
        )
        self.provider = provider


class LLMProviderNotFoundError(LLMError):
    """Raised when the requested provider is unknown or not registered."""

    def __init__(self, provider: str):
        super().__init__(
            f"Provider '{provider}' is not registered or supported by CUSTODE",
            code="PROVIDER_NOT_FOUND",
            details={"provider": provider},
        )
        self.provider = provider


class LLMModelNotAllowedError(LLMError):
    """Raised when a model is not permitted by system or organization allowlist."""

    def __init__(self, provider: str, model: str):
        super().__init__(
            f"Model '{model}' for provider '{provider}' is not permitted by security policy",
            code="MODEL_NOT_ALLOWED",
            details={"provider": provider, "model": model},
        )
        self.provider = provider
        self.model = model


class LLMSSRFProtectionError(LLMError):
    """Raised when a provider endpoint resolves to a forbidden destination (SSRF protection)."""

    def __init__(self, url: str, reason: str):
        super().__init__(
            f"Endpoint URL rejected by CUSTODE SSRF protection: {reason}",
            code="SSRF_PROTECTION_VIOLATION",
            details={"url": url, "reason": reason},
        )
        self.url = url
        self.reason = reason


class LLMSecurityBlockError(LLMError):
    """Raised when an LLM request or response is blocked by security findings or policy."""

    def __init__(
        self,
        reason: str,
        request_id: Optional[uuid.UUID] = None,
        interaction_id: Optional[uuid.UUID] = None,
        findings_summary: Optional[List[Dict[str, Any]]] = None,
    ):
        super().__init__(
            f"LLM request blocked by CUSTODE security policy: {reason}",
            code="SECURITY_POLICY_VIOLATION",
            details={
                "request_id": str(request_id) if request_id else None,
                "interaction_id": str(interaction_id) if interaction_id else None,
                "findings": findings_summary or [],
            },
        )
        self.request_id = request_id
        self.interaction_id = interaction_id
        self.findings_summary = findings_summary or []


class LLMApprovalRequiredError(LLMError):
    """Raised when an LLM request mandates human approval before execution."""

    def __init__(
        self,
        approval_id: uuid.UUID,
        request_id: uuid.UUID,
        interaction_id: uuid.UUID,
        reason: str,
    ):
        super().__init__(
            f"LLM request requires human approval: {reason}",
            code="APPROVAL_REQUIRED",
            details={
                "approval_id": str(approval_id),
                "request_id": str(request_id),
                "interaction_id": str(interaction_id),
                "reason": reason,
            },
        )
        self.approval_id = approval_id
        self.request_id = request_id
        self.interaction_id = interaction_id


class LLMOutputSecurityError(LLMError):
    """Raised when LLM output violates security constraints (e.g. contains leaked secrets or critical PII)."""

    def __init__(
        self,
        request_id: Optional[uuid.UUID] = None,
        interaction_id: Optional[uuid.UUID] = None,
        findings_count: int = 0,
    ):
        super().__init__(
            "Model response was blocked because sensitive or dangerous content was detected in the output.",
            code="OUTPUT_SECURITY_VIOLATION",
            details={
                "request_id": str(request_id) if request_id else None,
                "interaction_id": str(interaction_id) if interaction_id else None,
                "findings_count": findings_count,
            },
        )
        self.request_id = request_id
        self.interaction_id = interaction_id


class LLMToolCallSecurityError(LLMError):
    """Raised when an LLM-generated tool call fails validation or authorization."""

    def __init__(self, tool_name: str, operation_name: str, reason: str):
        super().__init__(
            f"Untrusted tool call '{tool_name}::{operation_name}' failed security verification: {reason}",
            code="TOOL_CALL_SECURITY_ERROR",
            details={"tool": tool_name, "operation": operation_name, "reason": reason},
        )
        self.tool_name = tool_name
        self.operation_name = operation_name


class LLMRateLimitError(LLMError):
    """Raised when request payload or token limits are exceeded."""

    def __init__(self, limit_type: str, limit_value: Any, requested_value: Any):
        super().__init__(
            f"LLM request exceeded configured resource limit '{limit_type}': maximum {limit_value}, requested {requested_value}",
            code="RESOURCE_LIMIT_EXCEEDED",
            details={"limit_type": limit_type, "limit_value": limit_value, "requested_value": requested_value},
        )
