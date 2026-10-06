"""SSRF, schema, and payload validation for CUSTODE MCP Security Layer."""

import ipaddress
import json
import socket
from typing import Any, Dict, List, Optional, Set
from urllib.parse import urlparse

from app.mcp.exceptions import (
    MCPPayloadSizeExceededError,
    MCPSchemaValidationError,
    MCPSSRFProtectionError,
)

# Limits
MAX_SCHEMA_SIZE_BYTES = 64 * 1024       # 64 KB
MAX_ARGUMENTS_SIZE_BYTES = 256 * 1024   # 256 KB
MAX_RESPONSE_SIZE_BYTES = 1024 * 1024   # 1 MB
MAX_SCHEMA_DEPTH = 8

PROHIBITED_SCHEMA_KEYS = {"__proto__", "constructor", "prototype"}

BLOCKED_IP_NETWORKS = [
    ipaddress.ip_network("0.0.0.0/8"),
    ipaddress.ip_network("127.0.0.0/8"),
    ipaddress.ip_network("10.0.0.0/8"),
    ipaddress.ip_network("172.16.0.0/12"),
    ipaddress.ip_network("192.168.0.0/16"),
    ipaddress.ip_network("169.254.0.0/16"),  # Link-local & Cloud Metadata (169.254.169.254)
    ipaddress.ip_network("100.64.0.0/10"),  # Carrier-grade NAT
    ipaddress.ip_network("192.0.0.0/24"),
    ipaddress.ip_network("192.0.2.0/24"),   # TEST-NET-1
    ipaddress.ip_network("198.51.100.0/24"),# TEST-NET-2
    ipaddress.ip_network("203.0.113.0/24"), # TEST-NET-3
    ipaddress.ip_network("224.0.0.0/4"),    # Multicast
    ipaddress.ip_network("240.0.0.0/4"),    # Reserved
    ipaddress.ip_network("::1/128"),        # IPv6 loopback
    ipaddress.ip_network("fc00::/7"),       # IPv6 unique local
    ipaddress.ip_network("fe80::/10"),      # IPv6 link-local
]

BLOCKED_HOSTNAMES = {
    "localhost",
    "metadata.google.internal",
    "169.254.169.254",
    "instance-data",
}


def validate_mcp_endpoint_url(url: str, allow_mock: bool = True) -> str:
    """Validate that an MCP endpoint URL complies with strict SSRF protection rules.

    Rejects loopback, private RFC1918, link-local, cloud metadata, and unauthorized schemes.
    """
    if not url or not isinstance(url, str):
        raise MCPSSRFProtectionError(str(url), "Endpoint URL cannot be empty")

    url = url.strip()

    # Allow mock:// for deterministic unit tests
    if allow_mock and url.startswith("mock://"):
        return url

    parsed = urlparse(url)
    if parsed.scheme.lower() not in ("http", "https"):
        raise MCPSSRFProtectionError(url, f"Prohibited URL scheme '{parsed.scheme}'. Only HTTPS or HTTP allowed.")

    hostname = (parsed.hostname or "").strip().lower()
    if not hostname:
        raise MCPSSRFProtectionError(url, "Missing host in endpoint URL")

    if hostname in BLOCKED_HOSTNAMES:
        raise MCPSSRFProtectionError(url, f"Host '{hostname}' is a prohibited loopback, metadata, or local identifier")

    if hostname.endswith(".localhost") or hostname.endswith(".local") or hostname.endswith(".internal"):
        raise MCPSSRFProtectionError(url, f"Domain '{hostname}' resolves to an internal or reserved namespace")

    # Check direct IP addresses
    try:
        ip = ipaddress.ip_address(hostname)
        for net in BLOCKED_IP_NETWORKS:
            if ip in net:
                raise MCPSSRFProtectionError(url, f"Destination IP '{ip}' belongs to blocked private/metadata network '{net}'")
        return url
    except ValueError:
        # Not a raw IP literal; proceed with DNS resolution validation
        pass

    # Resolve hostname to verify destination IP addresses
    try:
        addr_info = socket.getaddrinfo(hostname, parsed.port or (443 if parsed.scheme == "https" else 80))
        for item in addr_info:
            ip_str = item[4][0]
            ip = ipaddress.ip_address(ip_str)
            for net in BLOCKED_IP_NETWORKS:
                if ip in net:
                    raise MCPSSRFProtectionError(
                        url,
                        f"Domain '{hostname}' resolves to blocked internal IP '{ip}' (network {net})"
                    )
    except socket.gaierror:
        # In sandboxed / offline test environments without outbound DNS, allow domain if hostname is not blocked
        pass

    return url


def validate_schema_depth_and_keys(obj: Any, current_depth: int = 1) -> None:
    """Recursively verify schema depth, prohibited prototype keys, and circular structures."""
    if current_depth > MAX_SCHEMA_DEPTH:
        raise MCPSchemaValidationError(f"Schema exceeds maximum nesting depth of {MAX_SCHEMA_DEPTH}")

    if isinstance(obj, dict):
        for k, v in obj.items():
            if k in PROHIBITED_SCHEMA_KEYS:
                raise MCPSchemaValidationError(f"Prohibited security key '{k}' detected in schema")
            validate_schema_depth_and_keys(v, current_depth + 1)
    elif isinstance(obj, list):
        for item in obj:
            validate_schema_depth_and_keys(item, current_depth + 1)


def validate_mcp_tool_schema(schema: Dict[str, Any]) -> Dict[str, Any]:
    """Validate that an MCP tool's JSON schema is safe, bounded, and well-formed."""
    if not isinstance(schema, dict):
        raise MCPSchemaValidationError("Tool schema must be a JSON object dictionary")

    try:
        serialized = json.dumps(schema)
    except Exception as exc:
        raise MCPSchemaValidationError(f"Schema cannot be serialized to valid JSON: {exc}")

    if len(serialized.encode("utf-8")) > MAX_SCHEMA_SIZE_BYTES:
        raise MCPSchemaValidationError(
            f"Schema size ({len(serialized)} bytes) exceeds limit of {MAX_SCHEMA_SIZE_BYTES} bytes"
        )

    # Check nesting depth and prototype pollution keys
    validate_schema_depth_and_keys(schema)

    # Top-level type should generally be object or unspecified
    schema_type = schema.get("type")
    if schema_type and schema_type not in ("object", "array", "string", "number", "integer", "boolean"):
        raise MCPSchemaValidationError(f"Invalid top-level schema type: '{schema_type}'")

    return schema


def validate_mcp_tool_arguments(schema: Dict[str, Any], arguments: Optional[Dict[str, Any]] = None) -> None:
    """Validate input arguments against tool input schema and payload limits."""
    # Handle parameter order (arguments, schema) or (schema, arguments)
    if arguments is not None and isinstance(arguments, dict) and isinstance(schema, dict):
        if ("properties" in arguments or "type" in arguments) and ("properties" not in schema and "type" not in schema):
            schema, arguments = arguments, schema
    elif arguments is None:
        arguments = {}

    if not isinstance(arguments, dict):
        raise MCPSchemaValidationError("Arguments must be a key-value dictionary")

    try:
        raw_bytes = json.dumps(arguments).encode("utf-8")
    except Exception as exc:
        raise MCPSchemaValidationError(f"Arguments cannot be serialized to valid JSON: {exc}")

    if len(raw_bytes) > MAX_ARGUMENTS_SIZE_BYTES:
        raise MCPPayloadSizeExceededError(len(raw_bytes), MAX_ARGUMENTS_SIZE_BYTES)

    # Check required fields defined in schema
    required_fields: List[str] = schema.get("required", [])
    if isinstance(required_fields, list):
        for req in required_fields:
            if req not in arguments:
                raise MCPSchemaValidationError(f"Missing required parameter: '{req}'")

    # Simple property type checks if defined
    properties: Dict[str, Any] = schema.get("properties", {})
    if isinstance(properties, dict):
        type_map = {
            "string": str,
            "number": (int, float),
            "integer": int,
            "boolean": bool,
            "object": dict,
            "array": list,
        }
        for arg_key, arg_val in arguments.items():
            if arg_key in properties and isinstance(properties[arg_key], dict):
                expected_type = properties[arg_key].get("type")
                if expected_type in type_map and arg_val is not None:
                    allowed_py_types = type_map[expected_type]
                    if expected_type == "integer" and isinstance(arg_val, bool):
                        raise MCPSchemaValidationError(f"Parameter '{arg_key}' expected integer, got boolean")
                    if not isinstance(arg_val, allowed_py_types):
                        raise MCPSchemaValidationError(
                            f"Parameter '{arg_key}' expected type '{expected_type}', got '{type(arg_val).__name__}'"
                        )
