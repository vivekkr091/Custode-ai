"""Structured security logging for CUSTODE audit and forensic observability."""

from datetime import datetime, timezone
import json
import logging
import re
from typing import Any, Dict, Optional
import uuid

from app.core.correlation import get_current_request_id

logger = logging.getLogger("custode.security")

SENSITIVE_FIELD_NAMES = {
    "password",
    "password_hash",
    "raw_token",
    "raw_key",
    "api_key",
    "secret",
    "secret_key",
    "auth_secret_key",
    "access_token",
    "credential_hash",
    "authorization",
    "webhook_secret",
    "signing_secret",
    "encryption_key",
    "private_key",
    "client_secret",
    "token",
    "jwt",
}

# Regex patterns to scrub accidental raw secrets in unstructured string log messages
_SECRET_PATTERNS = [
    re.compile(r"Bearer\s+([a-zA-Z0-9_\-\.]{15,})", re.IGNORECASE),
    re.compile(r"cst_[a-zA-Z0-9_\-]{20,}", re.IGNORECASE),
    re.compile(r"(password|secret|api_key|token)=([^\s&]+)", re.IGNORECASE),
]


def sanitize_log_dict(data: Optional[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
    """Recursively redact secrets and credentials from structured log data."""
    if data is None:
        return None
    sanitized: Dict[str, Any] = {}
    for k, v in data.items():
        if k.lower() in SENSITIVE_FIELD_NAMES:
            sanitized[k] = "[REDACTED]"
        elif isinstance(v, dict):
            sanitized[k] = sanitize_log_dict(v)
        elif isinstance(v, list):
            sanitized[k] = [
                sanitize_log_dict(item) if isinstance(item, dict) else item
                for item in v
            ]
        elif isinstance(v, str):
            val_clean = v
            for pattern in _SECRET_PATTERNS:
                val_clean = pattern.sub(r"[REDACTED]", val_clean)
            sanitized[k] = val_clean
        else:
            sanitized[k] = v
    return sanitized


class RedactingFilter(logging.Filter):
    """Logging filter that scrubs sensitive credentials from log record messages."""

    def filter(self, record: logging.LogRecord) -> bool:
        if isinstance(record.msg, str):
            for pattern in _SECRET_PATTERNS:
                record.msg = pattern.sub(r"[REDACTED]", record.msg)
        return True


def setup_logging(level: str = "INFO") -> None:
    """Initialize structured application logging with secret scrubbing."""
    root_logger = logging.getLogger()
    numeric_level = getattr(logging, level.upper(), logging.INFO)
    root_logger.setLevel(numeric_level)

    # Attach secret redacting filter
    redactor = RedactingFilter()
    for handler in root_logger.handlers:
        handler.addFilter(redactor)


def log_security_event(
    event: str,
    level: str = "INFO",
    organization_id: Optional[uuid.UUID] = None,
    actor_id: Optional[str] = None,
    actor_type: str = "SYSTEM",
    outcome: str = "SUCCESS",
    details: Optional[Dict[str, Any]] = None,
    request_id: Optional[str] = None,
) -> None:
    """Emit a structured JSON log entry for security and governance activities."""
    effective_req_id = request_id or get_current_request_id()
    safe_details = sanitize_log_dict(details)

    log_payload = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "level": level.upper(),
        "event": event,
        "request_id": effective_req_id,
        "organization_id": str(organization_id) if organization_id else None,
        "actor": {
            "type": actor_type,
            "id": str(actor_id) if actor_id else None,
        },
        "outcome": outcome.upper(),
        "details": safe_details or {},
    }

    log_msg = json.dumps(log_payload)
    numeric_level = getattr(logging, level.upper(), logging.INFO)
    logger.log(numeric_level, log_msg)
