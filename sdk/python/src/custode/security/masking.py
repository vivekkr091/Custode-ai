"""Security utilities for credential masking and sanitization."""

import re
from typing import Any, Dict, Mapping

# Sensitive header keys to redact
SENSITIVE_HEADERS = frozenset({
    "authorization",
    "x-agent-api-key",
    "x-api-key",
    "cookie",
    "set-cookie",
    "proxy-authorization",
})

# Sensitive parameter keys
SENSITIVE_KEYS = frozenset({
    "password",
    "token",
    "secret",
    "api_key",
    "apikey",
    "access_token",
    "refresh_token",
    "private_key",
    "client_secret",
})


def mask_secret(secret: str | None) -> str:
    """Mask a raw secret or API key for safe logging and string representations.

    Preserves public prefix format while hiding high-entropy secrets:
    - 'cst_ag_<id>_<secret>' -> 'cst_ag_<id>_***'
    - 'short' -> '***'
    """
    if not secret:
        return "[EMPTY]"
    if secret.startswith("cst_ag_"):
        parts = secret.split("_")
        if len(parts) >= 4:
            # Format: cst_ag_<prefix>_<secret>
            return f"cst_ag_{parts[2]}_***"
        return "cst_ag_***"
    if len(secret) > 8:
        return f"{secret[:4]}...***"
    return "***"


def sanitize_headers(headers: Mapping[str, str] | None) -> Dict[str, str]:
    """Return a sanitized copy of HTTP headers with sensitive tokens redacted."""
    if not headers:
        return {}
    sanitized = {}
    for key, value in headers.items():
        if key.lower() in SENSITIVE_HEADERS:
            sanitized[key] = "[REDACTED]"
        else:
            sanitized[key] = value
    return sanitized
