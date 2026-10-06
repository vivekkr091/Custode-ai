"""Request correlation and tracing context across the CUSTODE platform."""

import contextvars
import re
from typing import Optional
import uuid

# Global context variable for request correlation
_request_id_ctx: contextvars.ContextVar[Optional[str]] = contextvars.ContextVar(
    "custode_request_id",
    default=None,
)

SAFE_REQUEST_ID_REGEX = re.compile(r"^[a-zA-Z0-9_\-\.]{1,100}$")


def sanitize_request_id(raw_id: Optional[str]) -> str:
    """Validate and sanitize an incoming request correlation identifier."""
    if raw_id and isinstance(raw_id, str):
        cleaned = raw_id.strip()
        if SAFE_REQUEST_ID_REGEX.match(cleaned):
            return cleaned
    return f"req_{uuid.uuid4().hex[:12]}"


def get_current_request_id() -> str:
    """Retrieve the current request identifier from context, generating one if absent."""
    rid = _request_id_ctx.get()
    if not rid:
        rid = f"req_{uuid.uuid4().hex[:12]}"
        _request_id_ctx.set(rid)
    return rid


def set_current_request_id(request_id: str) -> None:
    """Set the current request correlation identifier into the execution context."""
    cleaned = sanitize_request_id(request_id)
    _request_id_ctx.set(cleaned)
