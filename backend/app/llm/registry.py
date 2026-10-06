"""Provider registry, model allowlist, and SSRF security validation for LLM Gateway."""

import ipaddress
import logging
import socket
from typing import Any, Dict, List, Optional, Set
from urllib.parse import urlparse

from app.llm.exceptions import (
    LLMModelNotAllowedError,
    LLMProviderNotFoundError,
    LLMSSRFProtectionError,
)

logger = logging.getLogger(__name__)

# Default system allowlists
DEFAULT_ALLOWED_PROVIDERS: Dict[str, Set[str]] = {
    "mock": {"mock-gpt-4", "mock-claude-3", "mock-llama-3", "mock-fast"},
    "openai": {"gpt-4o", "gpt-4o-mini", "gpt-4-turbo", "gpt-4", "gpt-3.5-turbo"},
    "anthropic": {"claude-3-5-sonnet-20241022", "claude-3-opus-20240229", "claude-3-haiku-20240307"},
    "generic_http": {"generic-model", "default", "gpt-4o", "llama-3"},
}

# Forbidden private and cloud metadata CIDR ranges (SSRF prevention)
FORBIDDEN_IP_NETWORKS = [
    ipaddress.ip_network("0.0.0.0/8"),
    ipaddress.ip_network("10.0.0.0/8"),
    ipaddress.ip_network("127.0.0.0/8"),
    ipaddress.ip_network("169.254.0.0/16"),  # Link-local & AWS/GCP/Azure instance metadata (169.254.169.254)
    ipaddress.ip_network("172.16.0.0/12"),
    ipaddress.ip_network("192.168.0.0/16"),
    ipaddress.ip_network("224.0.0.0/4"),    # Multicast
    ipaddress.ip_network("240.0.0.0/4"),    # Reserved
    ipaddress.ip_network("::1/128"),        # IPv6 loopback
    ipaddress.ip_network("fc00::/7"),       # IPv6 unique local
    ipaddress.ip_network("fe80::/10"),      # IPv6 link-local
]


def validate_server_url(url: str, allow_local_for_testing: bool = False) -> None:
    """Strictly validate an external endpoint URL to protect against Server-Side Request Forgery (SSRF).

    Reject:
    - Non-HTTP/HTTPS schemes
    - Loopback addresses (127.0.0.1, localhost)
    - Cloud metadata addresses (169.254.169.254)
    - Private RFC1918 addresses (10.0.0.0/8, 172.16.0.0/12, 192.168.0.0/16)
    - Non-resolvable or malicious hostnames
    """
    if not url:
        raise LLMSSRFProtectionError(url, "Endpoint URL cannot be empty")

    parsed = urlparse(url)
    if parsed.scheme.lower() not in ("http", "https"):
        raise LLMSSRFProtectionError(url, f"Forbidden URL scheme '{parsed.scheme}': only HTTP/HTTPS allowed")

    hostname = parsed.hostname
    if not hostname:
        raise LLMSSRFProtectionError(url, "URL has no valid hostname")

    # Reject obvious localhost / metadata aliases
    forbidden_hostnames = {"localhost", "metadata", "instance-data", "169.254.169.254"}
    if hostname.lower() in forbidden_hostnames and not allow_local_for_testing:
        raise LLMSSRFProtectionError(url, f"Host '{hostname}' is prohibited by SSRF security rules")

    if allow_local_for_testing:
        return

    # Resolve IP and verify it does not fall into any private/link-local/metadata ranges
    try:
        addr_info = socket.getaddrinfo(hostname, parsed.port or 443, proto=socket.IPPROTO_TCP)
        for entry in addr_info:
            ip_str = entry[4][0]
            ip_obj = ipaddress.ip_address(ip_str)

            for net in FORBIDDEN_IP_NETWORKS:
                if ip_obj in net:
                    raise LLMSSRFProtectionError(
                        url,
                        f"Resolved address '{ip_str}' is within prohibited private/metadata range '{net}'",
                    )
    except socket.gaierror as exc:
        raise LLMSSRFProtectionError(url, f"Failed to resolve host '{hostname}': {exc}")


class ProviderRegistry:
    """Central registry of registered LLM providers and model allowlists."""

    def __init__(self) -> None:
        self._providers: Dict[str, Any] = {}
        self._allowed_models: Dict[str, Set[str]] = {k: set(v) for k, v in DEFAULT_ALLOWED_PROVIDERS.items()}

    def register(self, provider: Any) -> None:
        """Register an active LLMProvider instance."""
        name = getattr(provider, "provider_name", str(provider)).lower()
        self._providers[name] = provider
        logger.info(f"Registered LLM provider '{name}' in CUSTODE registry")

    def get(self, name: str) -> Any:
        """Retrieve a registered provider by name."""
        norm_name = name.lower()
        if norm_name not in self._providers:
            raise LLMProviderNotFoundError(name)
        return self._providers[norm_name]

    def list_providers(self) -> List[str]:
        """List all currently registered provider names."""
        return list(self._providers.keys())

    def validate_provider_and_model(self, provider: str, model: str) -> None:
        """Ensure provider is recognized and model is in the security allowlist."""
        norm_provider = provider.lower()
        if norm_provider not in self._providers:
            raise LLMProviderNotFoundError(provider)

        allowed_for_provider = self._allowed_models.get(norm_provider, set())
        # If provider has explicit model allowlist, enforce it
        if allowed_for_provider and model not in allowed_for_provider:
            raise LLMModelNotAllowedError(provider, model)

    def add_allowed_model(self, provider: str, model: str) -> None:
        """Add an allowed model to a provider allowlist."""
        norm_p = provider.lower()
        if norm_p not in self._allowed_models:
            self._allowed_models[norm_p] = set()
        self._allowed_models[norm_p].add(model)


# Global singleton provider registry
provider_registry = ProviderRegistry()
