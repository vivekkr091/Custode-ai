"""Normalized security findings models and sanitization for Sentinel integration."""

from enum import Enum
import re
from typing import Any, Dict, Optional, Tuple
from pydantic import BaseModel, Field


class FindingSeverity(str, Enum):
    """Normalized security finding severity levels."""
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    CRITICAL = "CRITICAL"


class FindingCategory(str, Enum):
    """Canonical security finding categories."""
    PROMPT_INJECTION = "PROMPT_INJECTION"
    PII = "PII"
    SECRET = "SECRET"
    HARMFUL_CONTENT = "HARMFUL_CONTENT"
    TOXICITY = "TOXICITY"
    BLOCKED_TERM = "BLOCKED_TERM"
    OBFUSCATION = "OBFUSCATION"
    CODE_SECURITY = "CODE_SECURITY"
    TOOL_USE = "TOOL_USE"
    OTHER = "OTHER"


# Category resolution rules from Sentinel scanner names and categories
_CATEGORY_MAPPING = {
    "prompt_injection": FindingCategory.PROMPT_INJECTION,
    "pii": FindingCategory.PII,
    "secrets_scanner": FindingCategory.SECRET,
    "secrets": FindingCategory.SECRET,
    "secret": FindingCategory.SECRET,
    "aws_access_key": FindingCategory.SECRET,
    "aws_secret_key": FindingCategory.SECRET,
    "github_token": FindingCategory.SECRET,
    "openai_key": FindingCategory.SECRET,
    "private_key": FindingCategory.SECRET,
    "rsa_private_key": FindingCategory.SECRET,
    "ec_private_key": FindingCategory.SECRET,
    "harmful_content": FindingCategory.HARMFUL_CONTENT,
    "toxicity": FindingCategory.TOXICITY,
    "obfuscation": FindingCategory.OBFUSCATION,
    "code_scanner": FindingCategory.CODE_SECURITY,
    "code_security": FindingCategory.CODE_SECURITY,
    "sql_injection": FindingCategory.CODE_SECURITY,
    "command_injection": FindingCategory.CODE_SECURITY,
    "path_traversal": FindingCategory.CODE_SECURITY,
    "unsafe_deserialization": FindingCategory.CODE_SECURITY,
    "hardcoded_credential": FindingCategory.SECRET,
    "tool_use": FindingCategory.TOOL_USE,
    "blocked_terms": FindingCategory.BLOCKED_TERM,
    "blocked_term": FindingCategory.BLOCKED_TERM,
}

_REMEDIATION_GUIDELINES = {
    FindingCategory.PROMPT_INJECTION: (
        "Sanitize untrusted user input, isolate instructions using delimiters, "
        "and enforce immutable system prompts in agent workflows."
    ),
    FindingCategory.SECRET: (
        "Immediately revoke and rotate the exposed credential. Store secrets in an "
        "encrypted environment vault (e.g. AWS Secrets Manager, HashiCorp Vault) rather than payload parameters."
    ),
    FindingCategory.PII: (
        "Mask or redact sensitive personally identifiable information (PII) before transmission. "
        "Apply data minimization principles to tool invocation parameters."
    ),
    FindingCategory.CODE_SECURITY: (
        "Remediate code injection vulnerability: use parameterized queries or APIs, "
        "avoid arbitrary command or code execution (never use eval, exec, or shell=True)."
    ),
    FindingCategory.HARMFUL_CONTENT: (
        "Filter out unsafe or harmful language violating AI safety guidelines before tool execution."
    ),
    FindingCategory.TOXICITY: (
        "Enforce toxicity filtering on agent input and generated tool arguments."
    ),
    FindingCategory.OBFUSCATION: (
        "Decode and normalize obfuscated or encoded payloads before evaluation. Reject hidden execution directives."
    ),
    FindingCategory.BLOCKED_TERM: (
        "Remove restricted corporate terminology, internal codenames, or prohibited keywords from the payload."
    ),
    FindingCategory.TOOL_USE: (
        "Validate tool call arguments against strict schema definitions and enforce parameter bounds."
    ),
    FindingCategory.OTHER: (
        "Inspect the action context and ensure parameters comply with organization security policies."
    ),
}


def sanitize_evidence(raw_evidence: Optional[str], category: FindingCategory) -> Optional[str]:
    """Sanitize sensitive evidence text to prevent credential or PII leakage in audit trails."""
    if not raw_evidence:
        return None

    cleaned = raw_evidence.strip()
    if len(cleaned) > 500:
        cleaned = cleaned[:500] + "... [truncated]"

    if category == FindingCategory.SECRET:
        # Mask common secret patterns: keep first 4 and last 4 chars if long enough
        if len(cleaned) > 8:
            return cleaned[:4] + "*" * (len(cleaned) - 8) + cleaned[-4:]
        return "[REDACTED_SECRET]"

    if category == FindingCategory.PII:
        # Mask emails
        cleaned = re.sub(
            r"([a-zA-Z0-9_.+-])[a-zA-Z0-9_.+-]+@([a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+)",
            r"\1***@\2",
            cleaned,
        )
        # Mask SSNs
        cleaned = re.sub(r"\b\d{3}-\d{2}-\d{4}\b", r"XXX-XX-\g<0>", cleaned)
        # Mask credit cards
        cleaned = re.sub(r"\b(?:\d{4}[-\s]?){3}(\d{4})\b", r"XXXX-XXXX-XXXX-\1", cleaned)

    return cleaned


def normalize_category(scanner: str, raw_category: Optional[str]) -> FindingCategory:
    """Map raw Sentinel scanner and category strings to canonical FindingCategory."""
    low_cat = (raw_category or "").lower().strip()
    low_scan = (scanner or "").lower().strip()

    if low_cat in _CATEGORY_MAPPING:
        return _CATEGORY_MAPPING[low_cat]
    if low_scan in _CATEGORY_MAPPING:
        return _CATEGORY_MAPPING[low_scan]

    for key, mapped in _CATEGORY_MAPPING.items():
        if key in low_cat or key in low_scan:
            return mapped

    return FindingCategory.OTHER


def normalize_severity(raw_risk: Any) -> FindingSeverity:
    """Map Sentinel RiskLevel enum or string to canonical FindingSeverity."""
    val = str(getattr(raw_risk, "value", raw_risk)).lower()
    if "critical" in val:
        return FindingSeverity.CRITICAL
    if "high" in val:
        return FindingSeverity.HIGH
    if "medium" in val:
        return FindingSeverity.MEDIUM
    return FindingSeverity.LOW


class NormalizedFinding(BaseModel):
    """Normalized, tamper-safe security finding representation for CUSTODE."""
    scanner: str
    category: FindingCategory
    severity: FindingSeverity
    confidence: float = 1.0
    title: str
    description: str
    evidence: Optional[str] = None
    remediation: Optional[str] = None
    source: str = "sentinel"
    span: Optional[Tuple[int, int]] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)

    @classmethod
    def from_sentinel_finding(
        cls,
        raw_finding: Any,
        full_text: Optional[str] = None,
    ) -> "NormalizedFinding":
        """Convert a raw Sentinel Finding instance into a NormalizedFinding."""
        scanner_name = getattr(raw_finding, "scanner", "sentinel")
        raw_cat = getattr(raw_finding, "category", "")
        desc = getattr(raw_finding, "description", "")
        raw_risk = getattr(raw_finding, "risk", "LOW")
        span = getattr(raw_finding, "span", None)
        meta = dict(getattr(raw_finding, "metadata", {}))

        category = normalize_category(scanner_name, raw_cat)
        severity = normalize_severity(raw_risk)

        # Extract evidence from span or metadata
        evidence_snippet = None
        if "matched_text" in meta:
            evidence_snippet = str(meta["matched_text"])
        elif span and full_text and len(full_text) >= span[1]:
            evidence_snippet = full_text[span[0]:span[1]]
        elif "term" in meta:
            evidence_snippet = str(meta["term"])

        sanitized_evidence = sanitize_evidence(evidence_snippet, category)
        remediation = _REMEDIATION_GUIDELINES.get(category, _REMEDIATION_GUIDELINES[FindingCategory.OTHER])

        title = desc
        if ":" in desc and len(desc.split(":")[0]) < 40:
            title = desc.split(":")[0].strip()
        elif len(desc) > 80:
            title = f"{category.value} detected by {scanner_name}"

        return cls(
            scanner=scanner_name,
            category=category,
            severity=severity,
            confidence=float(meta.get("confidence", 1.0)),
            title=title,
            description=desc,
            evidence=sanitized_evidence,
            remediation=remediation,
            source="sentinel",
            span=span,
            metadata=meta,
        )
