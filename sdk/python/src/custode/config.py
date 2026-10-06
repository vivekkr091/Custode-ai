"""Configuration management and secure validation for CUSTODE SDK."""

from __future__ import annotations

import os
import re
from typing import Any, Dict, Optional
from urllib.parse import urlparse

from custode.exceptions import ValidationError
from custode.security.masking import mask_secret

# Localhost origins allowed over insecure HTTP for development
LOCALHOST_HOSTS = frozenset({
    "localhost",
    "127.0.0.1",
    "0.0.0.0",
    "::1",
    "testserver",
})


class CUSTODEConfig:
    """Configuration container for CUSTODEClient and AsyncCUSTODEClient.

    Loads values from constructor arguments or environment variables:
    - CUSTODE_BASE_URL: Defaults to 'http://localhost:8000'
    - CUSTODE_AGENT_API_KEY: Mandatory agent bearer token
    - CUSTODE_ORGANIZATION_ID: Tenant UUID context
    - CUSTODE_TIMEOUT: Network timeout in seconds (default 30.0)
    """

    def __init__(
        self,
        base_url: Optional[str] = None,
        api_key: Optional[str] = None,
        organization_id: Optional[str] = None,
        timeout: Optional[float] = None,
        max_retries: int = 2,
        default_headers: Optional[Dict[str, str]] = None,
    ) -> None:
        # 1. Resolve Base URL
        resolved_base_url = (
            base_url
            or os.environ.get("CUSTODE_BASE_URL")
            or "http://localhost:8000"
        ).rstrip("/")
        self.base_url = self._validate_base_url(resolved_base_url)

        # 2. Resolve Agent API Key
        resolved_api_key = api_key or os.environ.get("CUSTODE_AGENT_API_KEY")
        if not resolved_api_key or not resolved_api_key.strip():
            raise ValidationError(
                "Missing CUSTODE Agent API Key. Provide 'api_key' argument or set 'CUSTODE_AGENT_API_KEY' environment variable."
            )
        self.api_key = resolved_api_key.strip()

        # 3. Resolve Organization ID (Optional at init, resolved via auth.me if omitted)
        resolved_org_id = organization_id or os.environ.get("CUSTODE_ORGANIZATION_ID")
        self.organization_id = resolved_org_id.strip() if resolved_org_id else None

        # 4. Resolve Timeout
        if timeout is not None:
            self.timeout = float(timeout)
        elif "CUSTODE_TIMEOUT" in os.environ:
            try:
                self.timeout = float(os.environ["CUSTODE_TIMEOUT"])
            except ValueError:
                self.timeout = 30.0
        else:
            self.timeout = 30.0

        if self.timeout <= 0:
            raise ValidationError(f"Timeout must be positive, got {self.timeout}")

        # 5. Retries
        self.max_retries = max(0, int(max_retries))

        # 6. Default Headers
        self.default_headers = default_headers or {}

    @staticmethod
    def _validate_base_url(url: str) -> str:
        """Ensure base URL is well-formed and requires HTTPS for remote production hosts."""
        parsed = urlparse(url)
        if not parsed.scheme or not parsed.netloc:
            raise ValidationError(
                f"Invalid base_url '{url}'. Must include scheme and host (e.g. 'https://api.custode.io')."
            )

        scheme = parsed.scheme.lower()
        if scheme not in ("http", "https"):
            raise ValidationError(
                f"Unsupported URL scheme '{scheme}'. Only 'http' and 'https' are allowed."
            )

        hostname = (parsed.hostname or "").lower()

        # Require HTTPS for non-localhost/non-local addresses
        if scheme == "http" and hostname not in LOCALHOST_HOSTS:
            raise ValidationError(
                f"Insecure HTTP is not allowed for remote endpoint '{url}'. Production endpoints must use HTTPS."
            )

        return url

    def __repr__(self) -> str:
        return (
            f"CUSTODEConfig("
            f"base_url={self.base_url!r}, "
            f"api_key={mask_secret(self.api_key)!r}, "
            f"organization_id={self.organization_id!r}, "
            f"timeout={self.timeout}, "
            f"max_retries={self.max_retries})"
        )

    def __str__(self) -> str:
        return self.__repr__()
