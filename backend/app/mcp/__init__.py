"""CUSTODE MCP Security Layer.

Mediates all Model Context Protocol (MCP) server integrations:
- Untrusted MCP server boundary management & SSRF protection
- Schema fingerprinting & canonical SHA-256 drift detection
- Untrusted tool description & argument scanning with Sentinel
- CUSTODE authoritative control plane mediation (Permission, Policy, Risk, Decision)
- Controlled tool execution and output scanning
- Comprehensive forensic audit logs & telemetry
"""

from app.mcp.exceptions import (
    MCPError,
    MCPInactiveError,
    MCPNotFoundError,
    MCPSchemaDriftError,
    MCPSchemaValidationError,
    MCPServerInactiveError,
    MCPServerNotFoundError,
    MCPSSRFProtectionError,
    MCPToolInactiveError,
    MCPToolNotFoundError,
    MCPTransportError,
    MCPUnsupportedTransportError,
)
from app.mcp.gateway import MCPGateway
from app.mcp.policy import (
    MCP_INPUT_PROFILE,
    MCP_OUTPUT_PROFILE,
    MCP_TOOL_DISCOVERY_PROFILE,
    build_mcp_action_context,
    evaluate_mcp_security_policy,
)
from app.mcp.registry import MCPRegistryService
from app.mcp.sanitizer import (
    compute_schema_hash,
    sanitize_description_text,
    sanitize_mcp_metadata,
)
from app.mcp.schemas import (
    MCPDiscoveryResponse,
    MCPMetricsResponse,
    MCPServerCreate,
    MCPServerListResponse,
    MCPServerResponse,
    MCPServerUpdate,
    MCPToolCallRequest,
    MCPToolCallResponse,
    MCPToolListResponse,
    MCPToolResponse,
)
from app.mcp.transport import (
    HttpMCPTransport,
    MCPTransport,
    MockMCPTransport,
    StdioMCPTransport,
)
from app.mcp.validator import (
    validate_mcp_endpoint_url,
    validate_mcp_tool_arguments,
    validate_mcp_tool_schema,
)

__all__ = [
    "MCPError",
    "MCPNotFoundError",
    "MCPServerNotFoundError",
    "MCPToolNotFoundError",
    "MCPInactiveError",
    "MCPServerInactiveError",
    "MCPToolInactiveError",
    "MCPSchemaDriftError",
    "MCPSSRFProtectionError",
    "MCPSchemaValidationError",
    "MCPTransportError",
    "MCPUnsupportedTransportError",
    "MCPGateway",
    "MCPRegistryService",
    "MCPTransport",
    "MockMCPTransport",
    "HttpMCPTransport",
    "StdioMCPTransport",
    "validate_mcp_endpoint_url",
    "validate_mcp_tool_schema",
    "validate_mcp_tool_arguments",
    "compute_schema_hash",
    "sanitize_description_text",
    "sanitize_mcp_metadata",
    "build_mcp_action_context",
    "evaluate_mcp_security_policy",
    "MCP_TOOL_DISCOVERY_PROFILE",
    "MCP_INPUT_PROFILE",
    "MCP_OUTPUT_PROFILE",
    "MCPServerCreate",
    "MCPServerUpdate",
    "MCPServerResponse",
    "MCPServerListResponse",
    "MCPToolResponse",
    "MCPToolListResponse",
    "MCPDiscoveryResponse",
    "MCPToolCallRequest",
    "MCPToolCallResponse",
    "MCPMetricsResponse",
]
