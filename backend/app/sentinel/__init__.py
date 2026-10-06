"""Sentinel integration package for CUSTODE AI Agent Security & Control Platform."""

from app.sentinel.adapter import SentinelAdapter, sentinel_adapter
from app.sentinel.config import SentinelConfig, settings
from app.sentinel.exceptions import (
    SentinelAdapterError,
    SentinelConfigurationError,
    SentinelError,
    SentinelScannerExecutionError,
    SentinelScannerTimeoutError,
)
from app.sentinel.findings import (
    FindingCategory,
    FindingSeverity,
    NormalizedFinding,
    sanitize_evidence,
)
from app.sentinel.registry import ScannerRegistry, registry

__all__ = [
    "SentinelAdapter",
    "sentinel_adapter",
    "SentinelConfig",
    "settings",
    "SentinelError",
    "SentinelConfigurationError",
    "SentinelAdapterError",
    "SentinelScannerTimeoutError",
    "SentinelScannerExecutionError",
    "FindingCategory",
    "FindingSeverity",
    "NormalizedFinding",
    "sanitize_evidence",
    "ScannerRegistry",
    "registry",
]
