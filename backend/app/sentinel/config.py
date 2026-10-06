"""Configuration settings for Sentinel security scanners integration."""

import os
from pathlib import Path
from typing import List, Optional
from pydantic import BaseModel, Field


def _resolve_default_sentinel_path() -> Path:
    """Resolve the default filesystem path to sentinel-ai repository without hardcoding."""
    env_path = os.getenv("CUSTODE_SENTINEL_PATH")
    if env_path:
        p = Path(env_path).resolve()
        if p.exists():
            return p

    # Standard layout: <workspace_root>/sentinel-ai
    # Current file: <workspace_root>/custode/backend/app/sentinel/config.py
    candidate = Path(__file__).resolve().parents[4] / "sentinel-ai"
    if candidate.exists():
        return candidate

    # Fallback to parent check
    candidate_alt = Path(__file__).resolve().parents[3] / "sentinel-ai"
    if candidate_alt.exists():
        return candidate_alt

    return candidate


class SentinelConfig(BaseModel):
    """Runtime configuration for Sentinel scanners."""

    enabled: bool = Field(
        default_factory=lambda: os.getenv("CUSTODE_SENTINEL_ENABLED", "true").lower() in ("true", "1", "yes")
    )
    fail_mode: str = Field(
        default_factory=lambda: os.getenv("CUSTODE_SENTINEL_FAIL_MODE", "fail_open").lower()
    )  # "fail_open" or "fail_closed"
    timeout_seconds: float = Field(
        default_factory=lambda: float(os.getenv("CUSTODE_SENTINEL_TIMEOUT_SECONDS", "5.0"))
    )
    sentinel_path: Path = Field(
        default_factory=_resolve_default_sentinel_path
    )
    block_on_critical: bool = Field(
        default_factory=lambda: os.getenv("CUSTODE_SENTINEL_BLOCK_ON_CRITICAL", "true").lower() in ("true", "1", "yes")
    )
    require_approval_on_high: bool = Field(
        default_factory=lambda: os.getenv("CUSTODE_SENTINEL_REQUIRE_APPROVAL_ON_HIGH", "true").lower() in ("true", "1", "yes")
    )
    enabled_scanners: List[str] = Field(
        default_factory=lambda: [
            "prompt_injection",
            "pii",
            "secrets_scanner",
            "harmful_content",
            "toxicity",
            "obfuscation",
            "code_scanner",
            "tool_use",
            "blocked_terms",
        ]
    )


# Global singleton instance
settings = SentinelConfig()
