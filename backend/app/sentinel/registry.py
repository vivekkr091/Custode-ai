"""Scanner registry managing Sentinel scanner instances with isolated path resolution."""

import importlib
import logging
import sys
from typing import Any, Dict, List, Optional

from app.sentinel.config import settings
from app.sentinel.exceptions import SentinelConfigurationError

logger = logging.getLogger(__name__)


def ensure_sentinel_syspath() -> None:
    """Ensure sentinel-ai root is in sys.path without modifying the sentinel-ai repository."""
    sentinel_path = settings.sentinel_path.resolve()
    if not sentinel_path.exists():
        logger.warning(
            f"Sentinel root path '{sentinel_path}' does not exist on disk. "
            "Scanners will not load unless installed as a package."
        )
        return

    path_str = str(sentinel_path)
    if path_str not in sys.path:
        # Prepend to sys.path so sentinel modules resolve cleanly
        sys.path.insert(0, path_str)
        logger.info(f"Registered Sentinel repository in sys.path: {path_str}")


class ScannerRegistry:
    """Registry managing available Sentinel scanner instances."""

    def __init__(self) -> None:
        self._scanners: Dict[str, Any] = {}
        self._initialized = False

    def initialize(self) -> None:
        """Instantiate enabled Sentinel scanners lazily."""
        if self._initialized:
            return

        ensure_sentinel_syspath()

        # Scanner definitions: (key, module_name, class_name, init_args)
        scanner_specs = [
            ("prompt_injection", "sentinel.scanners.prompt_injection", "PromptInjectionScanner", {}),
            ("pii", "sentinel.scanners.pii", "PIIScanner", {}),
            ("secrets_scanner", "sentinel.scanners.secrets_scanner", "SecretsScanner", {}),
            ("harmful_content", "sentinel.scanners.harmful_content", "HarmfulContentScanner", {}),
            ("toxicity", "sentinel.scanners.toxicity", "ToxicityScanner", {}),
            ("obfuscation", "sentinel.scanners.obfuscation", "ObfuscationScanner", {}),
            ("code_scanner", "sentinel.scanners.code_scanner", "CodeScanner", {}),
            ("tool_use", "sentinel.scanners.tool_use", "ToolUseScanner", {}),
            ("blocked_terms", "sentinel.scanners.blocked_terms", "BlockedTermsScanner", {"terms": ["INTERNAL_CONFIDENTIAL", "RESTRICTED_KEYWORD"]}),
        ]

        for key, mod_name, cls_name, kwargs in scanner_specs:
            if key in settings.enabled_scanners:
                try:
                    mod = importlib.import_module(mod_name)
                    cls = getattr(mod, cls_name)
                    instance = cls(**kwargs)
                    self._scanners[key] = instance
                    logger.debug(f"Loaded Sentinel scanner: {key}")
                except Exception as exc:
                    logger.warning(f"Failed to load Sentinel scanner '{key}': {exc}")

        self._initialized = True

    def get_scanner(self, name: str) -> Optional[Any]:
        """Get a specific scanner by name."""
        if not self._initialized:
            self.initialize()
        return self._scanners.get(name)

    def get_all_scanners(self) -> Dict[str, Any]:
        """Return dictionary of all loaded scanners."""
        if not self._initialized:
            self.initialize()
        return dict(self._scanners)

    def get_scanner_names(self) -> List[str]:
        """Return list of active scanner names."""
        if not self._initialized:
            self.initialize()
        return list(self._scanners.keys())


# Singleton registry instance
registry = ScannerRegistry()
