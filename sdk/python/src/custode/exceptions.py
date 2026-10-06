"""Structured exception hierarchy for the CUSTODE Python SDK."""

from typing import Any, Dict, Optional
from custode.security.masking import mask_secret


class CUSTODEError(Exception):
    """Base exception for all CUSTODE SDK errors.

    Ensures that raw API keys, Authorization headers, and sensitive secrets
    are never leaked through exception representations or string formatting.
    """

    def __init__(
        self,
        message: str,
        *,
        status_code: Optional[int] = None,
        request_id: Optional[str] = None,
        response_data: Optional[Dict[str, Any]] = None,
    ) -> None:
        super().__init__(message)
        self.message = message
        self.status_code = status_code
        self.request_id = request_id
        self.response_data = response_data or {}

    def __str__(self) -> str:
        parts = [self.message]
        if self.status_code is not None:
            parts.append(f"(status: {self.status_code})")
        if self.request_id:
            parts.append(f"[request_id: {self.request_id}]")
        return " ".join(parts)

    def __repr__(self) -> str:
        return (
            f"{self.__class__.__name__}("
            f"message={self.message!r}, "
            f"status_code={self.status_code}, "
            f"request_id={self.request_id!r})"
        )


class AuthenticationError(CUSTODEError):
    """Raised when authentication fails (HTTP 401).

    Typically indicates an invalid, missing, expired, or revoked agent API key.
    """
    pass


class AuthorizationError(CUSTODEError):
    """Raised when the authenticated agent lacks permissions or tenant access (HTTP 403)."""
    pass


class NotFoundError(CUSTODEError):
    """Raised when a requested resource does not exist (HTTP 404)."""
    pass


class ConflictError(CUSTODEError):
    """Raised on state conflict or lifecycle incompatibility (HTTP 409)."""
    pass


class ValidationError(CUSTODEError):
    """Raised when request payload fails schema validation (HTTP 422)."""
    pass


class RateLimitError(CUSTODEError):
    """Raised when request rate limits are exceeded (HTTP 429)."""
    pass


class APIConnectionError(CUSTODEError):
    """Raised when a network or transport-level connection error occurs."""
    pass


class APITimeoutError(CUSTODEError):
    """Raised when an HTTP request times out."""
    pass


class ServerError(CUSTODEError):
    """Raised when the CUSTODE backend returns an HTTP 5xx error."""
    pass


class SecurityDecisionError(CUSTODEError):
    """Raised when an action is evaluated with an adverse decision (BLOCK or REQUIRE_APPROVAL).

    Attributes:
        decision: The decision string ('block', 'require_approval').
        reason: Explanation or risk justification for the decision.
        runtime_action_id: Associated action ID if available.
    """

    def __init__(
        self,
        message: str,
        *,
        decision: str,
        reason: Optional[str] = None,
        runtime_action_id: Optional[str] = None,
        request_id: Optional[str] = None,
        response_data: Optional[Dict[str, Any]] = None,
    ) -> None:
        super().__init__(
            message,
            status_code=None,
            request_id=request_id,
            response_data=response_data,
        )
        self.decision = decision
        self.reason = reason
        self.runtime_action_id = runtime_action_id

    def __str__(self) -> str:
        base = f"Security Decision [{self.decision.upper()}]: {self.message}"
        if self.reason:
            base += f" - Reason: {self.reason}"
        if self.request_id:
            base += f" [request_id: {self.request_id}]"
        return base
