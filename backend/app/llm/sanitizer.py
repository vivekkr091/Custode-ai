"""Content hashing, sanitization, and secret redaction utilities for the LLM Gateway."""

import hashlib
import json
import re
from typing import Any, Dict, List, Optional, Union

from app.sentinel.findings import FindingCategory, sanitize_evidence


def compute_content_hash(data: Union[str, List[Any], Dict[str, Any]]) -> str:
    """Compute a deterministic SHA-256 cryptographic hash over text or message payloads."""
    if isinstance(data, str):
        normalized_bytes = data.strip().encode("utf-8")
    else:
        try:
            normalized_bytes = json.dumps(data, sort_keys=True, default=str).encode("utf-8")
        except Exception:
            normalized_bytes = str(data).encode("utf-8")

    return hashlib.sha256(normalized_bytes).hexdigest()


def create_sanitized_preview(text: Optional[str], max_chars: int = 250) -> Optional[str]:
    """Create a safe, truncated excerpt with all secrets, keys, and PII masked.

    Raw prompts/outputs must never be retained unredacted.
    """
    if not text:
        return None

    sanitized = text
    # AWS Keys
    sanitized = re.sub(r"AKIA[0-9A-Z]{16}", "AKIA****************", sanitized)
    # GitHub Tokens
    sanitized = re.sub(r"gh[pousr]_[0-9a-zA-Z]{36}", "gh*_************************************", sanitized)
    # Generic Bearer tokens
    sanitized = re.sub(r"(Bearer\s+)[A-Za-z0-9\-\._~\+\/]+=*", r"\1[REDACTED_TOKEN]", sanitized, flags=re.IGNORECASE)
    # Passwords in json/kv/text
    sanitized = re.sub(r'(["\']?password["\']?\s*[:=]\s*["\']?)[^"\'\s,;]+(["\']?)', r'\1[REDACTED_PASSWORD]\2', sanitized, flags=re.IGNORECASE)
    # SSNs
    sanitized = re.sub(r"\b\d{3}-\d{2}-\d{4}\b", "***-**-****", sanitized)
    # Emails
    sanitized = re.sub(r"([a-zA-Z0-9_.+-])[a-zA-Z0-9_.+-]+@([a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+)", r"\1***@\2", sanitized)

    # Truncate cleanly
    if len(sanitized) > max_chars:
        return sanitized[:max_chars].rstrip() + "... [TRUNCATED]"
    return sanitized


def sanitize_headers_for_logging(headers: Optional[Dict[str, str]]) -> Dict[str, str]:
    """Strip authentication tokens and secret headers prior to logging or recording audit traces."""
    if not headers:
        return {}

    sanitized = {}
    sensitive_keys = {"authorization", "x-api-key", "api-key", "bearer", "proxy-authorization", "cookie"}
    for k, v in headers.items():
        if k.lower() in sensitive_keys:
            sanitized[k] = "[REDACTED_SECRET]"
        else:
            sanitized[k] = v
    return sanitized
