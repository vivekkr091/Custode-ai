"""SSRF Protection and Network Safety Boundary for Webhook Delivery."""

from collections.abc import Callable
import ipaddress
import socket
from typing import List, Optional
import urllib.parse


class SSRFProtectionError(Exception):
    """Raised when an outbound webhook URL targets an unsafe, private, or prohibited destination."""
    pass


# Prohibited CIDR blocks
BLOCKED_IPV4_NETWORKS = [
    ipaddress.ip_network("0.0.0.0/8"),          # Current network (only valid as source address)
    ipaddress.ip_network("10.0.0.0/8"),         # Private-Use (RFC 1918)
    ipaddress.ip_network("100.64.0.0/10"),      # Shared Address Space (RFC 6598)
    ipaddress.ip_network("127.0.0.0/8"),        # Loopback (RFC 1122)
    ipaddress.ip_network("169.254.0.0/16"),     # Link-Local (RFC 3927, includes cloud metadata 169.254.169.254)
    ipaddress.ip_network("172.16.0.0/12"),      # Private-Use (RFC 1918)
    ipaddress.ip_network("192.0.0.0/24"),       # IETF Protocol Assignments (RFC 6890)
    ipaddress.ip_network("192.0.2.0/24"),       # Documentation (TEST-NET-1)
    ipaddress.ip_network("192.168.0.0/16"),     # Private-Use (RFC 1918)
    ipaddress.ip_network("198.18.0.0/15"),      # Benchmarking (RFC 2544)
    ipaddress.ip_network("198.51.100.0/24"),    # Documentation (TEST-NET-2)
    ipaddress.ip_network("203.0.113.0/24"),     # Documentation (TEST-NET-3)
    ipaddress.ip_network("224.0.0.0/4"),        # Multicast (RFC 5771)
    ipaddress.ip_network("240.0.0.0/4"),        # Reserved (RFC 1112)
    ipaddress.ip_network("255.255.255.255/32"), # Limited Broadcast
]

BLOCKED_IPV6_NETWORKS = [
    ipaddress.ip_network("::1/128"),            # Loopback
    ipaddress.ip_network("::/128"),             # Unspecified
    ipaddress.ip_network("64:ff9b:1::/48"),     # Local-Use IPv4/IPv6 Translation
    ipaddress.ip_network("100::/64"),           # Discard-Only Address Block
    ipaddress.ip_network("2001:db8::/32"),      # Documentation
    ipaddress.ip_network("fc00::/7"),           # Unique-Local (ULA)
    ipaddress.ip_network("fe80::/10"),          # Link-Local Unicast
    ipaddress.ip_network("ff00::/8"),           # Multicast
]

# Prohibited hostnames
FORBIDDEN_HOSTNAMES = frozenset({
    "localhost",
    "localhost.localdomain",
    "instance-data",
    "metadata.google.internal",
    "metadata.internal",
    "169.254.169.254",
    "kubernetes.default",
    "kubernetes.default.svc",
})

_custom_dns_resolver: Optional[Callable[[str, int], List[str]]] = None


def set_custom_dns_resolver(resolver: Optional[Callable[[str, int], List[str]]]) -> None:
    """Configure a custom DNS resolver for deterministic testing in offline environments."""
    global _custom_dns_resolver
    _custom_dns_resolver = resolver


def is_ip_prohibited(ip_obj: ipaddress.IPv4Address | ipaddress.IPv6Address) -> bool:
    """Check if an IP address belongs to any restricted or private network ranges."""
    if isinstance(ip_obj, ipaddress.IPv4Address):
        return any(ip_obj in net for net in BLOCKED_IPV4_NETWORKS)
    elif isinstance(ip_obj, ipaddress.IPv6Address):
        return any(ip_obj in net for net in BLOCKED_IPV6_NETWORKS)
    return True


def validate_destination_address(
    url: str,
    allow_insecure: bool = False,
    allow_local: bool = False,
    dns_resolver: Optional[Callable[[str, int], List[str]]] = None,
) -> List[str]:
    """Validate a destination webhook URL against SSRF and private-network access.

    Performs:
    1. Scheme validation (HTTPS mandatory unless explicitly bypassed in testing)
    2. Hostname blacklisting
    3. Safe DNS pre-resolution
    4. IP address range validation against loopback, RFC 1918, Link-local, and Metadata ranges

    Returns:
        List of resolved IP addresses if valid.
    Raises:
        SSRFProtectionError if destination violates security boundaries.
    """
    if not url or not isinstance(url, str):
        raise SSRFProtectionError("Webhook URL must be a non-empty string")

    parsed = urllib.parse.urlsplit(url.strip())

    # 1. Scheme check
    if not allow_insecure and parsed.scheme.lower() != "https":
        raise SSRFProtectionError(
            f"Prohibited scheme '{parsed.scheme}'. Production webhooks require HTTPS."
        )
    if parsed.scheme.lower() not in ("http", "https"):
        raise SSRFProtectionError(f"Unsupported scheme '{parsed.scheme}'. Only HTTPS is permitted.")

    # 2. Host check
    hostname = parsed.hostname
    if not hostname:
        raise SSRFProtectionError("Webhook URL is missing a valid hostname")

    lowered_host = hostname.lower().strip(".")
    if lowered_host in FORBIDDEN_HOSTNAMES:
        if not allow_local:
            raise SSRFProtectionError(f"Prohibited webhook destination hostname: '{hostname}'")

    if lowered_host.endswith(".local") or lowered_host.endswith(".internal"):
        if not allow_local:
            raise SSRFProtectionError(f"Prohibited internal domain destination: '{hostname}'")

    # 3. Check if hostname is directly an IP literal
    is_ip_literal = False
    try:
        ip_obj = ipaddress.ip_address(lowered_host)
        is_ip_literal = True
    except ValueError:
        is_ip_literal = False

    if is_ip_literal:
        if not allow_local and is_ip_prohibited(ip_obj):
            raise SSRFProtectionError(
                f"Prohibited IP destination '{lowered_host}' falls in a restricted or private range"
            )
        return [str(ip_obj)]

    # 4. Resolve DNS and check all resolved IP addresses
    resolved_ips: List[str] = []
    port = parsed.port or (443 if parsed.scheme == "https" else 80)

    active_resolver = dns_resolver or _custom_dns_resolver

    if active_resolver is not None:
        raw_ips = active_resolver(lowered_host, port)
        for ip_str in raw_ips:
            try:
                ip_obj = ipaddress.ip_address(ip_str)
                if not allow_local and is_ip_prohibited(ip_obj):
                    raise SSRFProtectionError(
                        f"Destination hostname '{hostname}' resolves to restricted IP '{ip_str}'"
                    )
                resolved_ips.append(ip_str)
            except ValueError:
                continue
    else:
        try:
            addr_info = socket.getaddrinfo(
                lowered_host,
                port,
                proto=socket.IPPROTO_TCP,
            )
            for family, _, _, _, sockaddr in addr_info:
                ip_str = sockaddr[0]
                try:
                    ip_obj = ipaddress.ip_address(ip_str)
                    if not allow_local and is_ip_prohibited(ip_obj):
                        raise SSRFProtectionError(
                            f"Destination hostname '{hostname}' resolves to restricted IP '{ip_str}'"
                        )
                    resolved_ips.append(ip_str)
                except ValueError:
                    continue
        except socket.gaierror as e:
            if allow_local:
                return ["127.0.0.1"]
            raise SSRFProtectionError(f"Failed to resolve hostname '{hostname}': {str(e)}")

    if not resolved_ips and not allow_local:
        raise SSRFProtectionError(f"Hostname '{hostname}' could not be resolved to a valid IP address")

    return resolved_ips
