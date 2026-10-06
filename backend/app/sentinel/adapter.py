"""Sentinel Adapter providing clean, safe scanning orchestration for CUSTODE."""

import json
import logging
import time
from typing import Any, Dict, List, Optional, Set, Tuple

from app.sentinel.config import settings
from app.sentinel.exceptions import (
    SentinelAdapterError,
    SentinelScannerExecutionError,
    SentinelScannerTimeoutError,
)
from app.sentinel.findings import (
    FindingCategory,
    FindingSeverity,
    NormalizedFinding,
)
from app.sentinel.registry import registry

logger = logging.getLogger(__name__)


def extract_scan_targets(
    parameters: Optional[Dict[str, Any]] = None,
    resource: Optional[str] = None,
    action_type: Optional[str] = None,
) -> List[Tuple[str, str]]:
    """Extract individual text targets from a RuntimeAction payload for inspection.

    Returns a list of (target_label, text_content).
    """
    targets: List[Tuple[str, str]] = []

    if resource and str(resource).strip():
        targets.append(("resource", str(resource).strip()))

    if action_type and str(action_type).strip():
        targets.append(("action_type", str(action_type).strip()))

    if parameters:
        def _extract(val: Any, path: str) -> None:
            if isinstance(val, str) and val.strip():
                targets.append((path, val.strip()))
            elif isinstance(val, dict):
                for k, v in val.items():
                    _extract(v, f"{path}.{k}" if path else k)
            elif isinstance(val, (list, tuple)):
                for i, v in enumerate(val):
                    _extract(v, f"{path}[{i}]")

        _extract(parameters, "parameters")

        # Also add a canonical JSON representation of all parameters for composite scanning
        try:
            param_json = json.dumps(parameters, default=str)
            if len(param_json) > 2:
                targets.append(("composite_parameters_json", param_json))
        except Exception:
            pass

    return targets


class SentinelAdapter:
    """Authoritative adapter integrating Sentinel security scanners into CUSTODE."""

    def __init__(
        self,
        fail_mode: Optional[str] = None,
        timeout_seconds: Optional[float] = None,
    ) -> None:
        self.fail_mode = fail_mode or settings.fail_mode
        self.timeout_seconds = timeout_seconds or settings.timeout_seconds
        registry.initialize()

    def scan_text(
        self,
        text: str,
        context: Optional[Dict[str, Any]] = None,
        scanner_names: Optional[List[str]] = None,
    ) -> List[NormalizedFinding]:
        """Scan a single text string across all or selected active scanners."""
        if not text or not settings.enabled:
            return []

        active_scanners = registry.get_all_scanners()
        if scanner_names:
            active_scanners = {k: v for k, v in active_scanners.items() if k in scanner_names}

        findings: List[NormalizedFinding] = []
        for name, scanner in active_scanners.items():
            try:
                raw_findings = scanner.scan(text, context)
                for rf in raw_findings:
                    findings.append(NormalizedFinding.from_sentinel_finding(rf, full_text=text))
            except Exception as exc:
                logger.error(f"Scanner '{name}' encountered error: {exc}")
                if self.fail_mode == "fail_closed":
                    raise SentinelScannerExecutionError(name, exc) from exc

        return findings

    def scan_runtime_action_payload(
        self,
        parameters: Optional[Dict[str, Any]] = None,
        resource: Optional[str] = None,
        action_type: Optional[str] = None,
    ) -> Tuple[List[NormalizedFinding], Dict[str, Any]]:
        """Extract all payload targets from a RuntimeAction and run active Sentinel scanners.

        Returns:
            (findings, execution_metadata)
        """
        start_time = time.perf_counter()
        scanners_run = registry.get_scanner_names()

        if not settings.enabled:
            return [], {
                "scanned": False,
                "reason": "sentinel_disabled",
                "latency_ms": 0.0,
                "scanners_run": [],
            }

        targets = extract_scan_targets(parameters, resource, action_type)
        if not targets:
            elapsed = (time.perf_counter() - start_time) * 1000
            return [], {
                "scanned": True,
                "target_count": 0,
                "latency_ms": round(elapsed, 2),
                "scanners_run": scanners_run,
            }

        all_findings: List[NormalizedFinding] = []
        dedupe_keys: Set[Tuple[str, str, str]] = set()

        try:
            active_scanners = registry.get_all_scanners()
            for scanner_name, scanner in active_scanners.items():
                for label, text in targets:
                    # Avoid scanning composite json with code_scanner or long text repeatedly
                    if label == "composite_parameters_json" and scanner_name in ("code_scanner", "secrets_scanner"):
                        # Individual values are already covered
                        continue

                    try:
                        raw_findings = scanner.scan(text, context={"target": label})
                        for rf in raw_findings:
                            norm = NormalizedFinding.from_sentinel_finding(rf, full_text=text)
                            # Deduplicate identical findings across targets
                            dedupe_key = (norm.category.value, norm.title, norm.evidence or "")
                            if dedupe_key not in dedupe_keys:
                                dedupe_keys.add(dedupe_key)
                                # Tag target in metadata
                                norm.metadata["target_field"] = label
                                all_findings.append(norm)
                    except Exception as exc:
                        logger.error(f"Scanner '{scanner_name}' failed on target '{label}': {exc}")
                        if self.fail_mode == "fail_closed":
                            raise SentinelScannerExecutionError(scanner_name, exc) from exc
        except SentinelScannerExecutionError:
            raise
        except Exception as exc:
            logger.exception("Unexpected error in Sentinel scan execution")
            if self.fail_mode == "fail_closed":
                raise SentinelAdapterError(f"Sentinel scanning failed: {exc}") from exc

        elapsed = (time.perf_counter() - start_time) * 1000
        execution_metadata = {
            "scanned": True,
            "target_count": len(targets),
            "latency_ms": round(elapsed, 2),
            "scanners_run": scanners_run,
            "fail_mode": self.fail_mode,
        }

        return all_findings, execution_metadata


# Global adapter instance
sentinel_adapter = SentinelAdapter()
