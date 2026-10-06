"""Exceptions for Sentinel scanner integration."""


class SentinelError(Exception):
    """Base exception for all Sentinel integration errors."""
    pass


class SentinelConfigurationError(SentinelError):
    """Raised when Sentinel configuration is invalid or missing required resources."""
    pass


class SentinelAdapterError(SentinelError):
    """Raised when an error occurs during Sentinel scan orchestration."""
    pass


class SentinelScannerTimeoutError(SentinelAdapterError):
    """Raised when a Sentinel scanner exceeds the configured execution timeout."""
    def __init__(self, scanner_name: str, timeout_seconds: float):
        super().__init__(f"Sentinel scanner '{scanner_name}' timed out after {timeout_seconds}s")
        self.scanner_name = scanner_name
        self.timeout_seconds = timeout_seconds


class SentinelScannerExecutionError(SentinelAdapterError):
    """Raised when a Sentinel scanner encounters an unhandled runtime error."""
    def __init__(self, scanner_name: str, original_error: Exception):
        super().__init__(f"Sentinel scanner '{scanner_name}' failed: {original_error}")
        self.scanner_name = scanner_name
        self.original_error = original_error
