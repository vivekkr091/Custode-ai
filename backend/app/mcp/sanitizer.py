"""Sanitization and deterministic cryptographic hashing for CUSTODE MCP Security Layer."""

import hashlib
import json
import re
from typing import Any, Dict, Optional

SENSITIVE_FIELD_NAMES = {
    "password",
    "password_hash",
    "raw_token",
    "raw_key",
    "api_key",
    "secret",
    "access_token",
    "credential_hash",
    "authorization",
    "client_secret",
}


def compute_schema_hash(schema: Optional[Dict[str, Any]]) -> str:
    """Compute deterministic SHA-256 hash of a normalized JSON schema.

    Ensures identical logical schemas yield identical hashes regardless of formatting or key order.
    """
    if not schema:
        return hashlib.sha256(b"{}").hexdigest()

    # Canonical sorted JSON representation with no whitespace
    canonical = json.dumps(schema, sort_keys=True, separators=(",", ":"), ensure_ascii=True)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def sanitize_description_text(text: Optional[str]) -> Optional[str]:
    """Sanitize description text so it is always handled as pure inert data.

    Strips script tags, event handlers, and dangerous markup patterns.
    """
    if not text:
        return None

    cleaned = str(text).replace("\x00", "").replace("\r\n", "\n").replace("\r", "\n")
    # Strip dangerous control characters (preserve newline, tab)
    cleaned = re.sub(r"[\x01-\x08\x0b\x0c\x0e-\x1f]", "", cleaned)
    # Strip <script>...</script>
    cleaned = re.sub(r"(?i)<script\b[^<]*(?:(?!<\/script>)<[^<]*)*<\/script>", "", cleaned)
    # Strip all HTML tag delimiters
    cleaned = re.sub(r"<[^>]+>", "", cleaned)
    return cleaned.strip()


def sanitize_mcp_metadata(data: Optional[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
    """Recursively redact secrets and credentials from MCP metadata dictionaries."""
    if data is None:
        return None

    sanitized: Dict[str, Any] = {}
    for k, v in data.items():
        if k.lower() in SENSITIVE_FIELD_NAMES:
            sanitized[k] = "[REDACTED_SECRET]"
        elif isinstance(v, dict):
            sanitized[k] = sanitize_mcp_metadata(v)
        elif isinstance(v, list):
            sanitized[k] = [
                sanitize_mcp_metadata(item) if isinstance(item, dict) else item
                for item in v
            ]
        else:
            sanitized[k] = v
    return sanitized
