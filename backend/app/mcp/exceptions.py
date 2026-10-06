"""Exception hierarchy for CUSTODE MCP Security Layer."""

import uuid
from typing import Any, Optional


class MCPError(Exception):
    """Base exception for all MCP Security Layer errors."""
    def __init__(self, message: str, status_code: int = 400):
        super().__init__(message)
        self.message = message
        self.status_code = status_code


class MCPNotFoundError(MCPError):
    """Base exception for resource not found in MCP Security Layer."""
    pass


class MCPServerNotFoundError(MCPError):
    """Raised when an MCP server is not found in the organization context."""
    def __init__(self, server_id: uuid.UUID, org_id: Optional[uuid.UUID] = None):
        msg = f"MCP server '{server_id}' not found"
        if org_id:
            msg += f" in organization '{org_id}'"
        super().__init__(msg, status_code=404)
        self.server_id = server_id


class MCPServerInactiveError(MCPError):
    """Raised when attempting an operation on a suspended or revoked MCP server."""
    def __init__(self, server_id: uuid.UUID, status: str):
        super().__init__(
            f"MCP server '{server_id}' is not active (current status: '{status}')",
            status_code=403,
        )
        self.server_id = server_id
        self.server_status = status


class MCPToolNotFoundError(MCPError):
    """Raised when an MCP tool is not found."""
    def __init__(self, tool_id: uuid.UUID, org_id: Optional[uuid.UUID] = None):
        msg = f"MCP tool '{tool_id}' not found"
        if org_id:
            msg += f" in organization '{org_id}'"
        super().__init__(msg, status_code=404)
        self.tool_id = tool_id


class MCPToolInactiveError(MCPError):
    """Raised when attempting to execute an inactive, suspended, or discovered MCP tool."""
    def __init__(self, tool_id: uuid.UUID, status: str):
        super().__init__(
            f"MCP tool '{tool_id}' cannot be executed in status '{status}'. Explicit operator activation is required.",
            status_code=403,
        )
        self.tool_id = tool_id
        self.tool_status = status


class MCPSSRFProtectionError(MCPError):
    """Raised when an MCP server endpoint attempts SSRF against private, loopback, or metadata addresses."""
    def __init__(self, target_url: str, reason: str):
        super().__init__(
            f"SSRF violation: Endpoint '{target_url}' was rejected: {reason}",
            status_code=400,
        )
        self.target_url = target_url
        self.reason = reason


class MCPInactiveError(MCPError):
    """Base exception for inactive MCP resources."""
    pass


class MCPTransportError(MCPError):
    """Raised when an MCP transport encounters a network, protocol, or timeout error."""
    def __init__(self, detail_or_transport: str, detail: Optional[str] = None):
        if detail is not None:
            super().__init__(f"MCP transport error [{detail_or_transport}]: {detail}", status_code=502)
            self.transport_type = detail_or_transport
        else:
            super().__init__(f"MCP transport error: {detail_or_transport}", status_code=502)
            self.transport_type = "UNKNOWN"


class MCPUnsupportedTransportError(MCPError):
    """Raised when requesting an unsupported or unsafe transport (such as arbitrary STDIO process spawning)."""
    def __init__(self, transport_type: str):
        super().__init__(
            f"MCP transport '{transport_type}' is unsupported or prohibited for security reasons",
            status_code=400,
        )
        self.transport_type = transport_type


class MCPSchemaValidationError(MCPError):
    """Raised when an MCP tool schema is malformed, oversized, or violates recursive bomb bounds."""
    def __init__(self, detail: str):
        super().__init__(f"MCP schema validation rejected: {detail}", status_code=400)


class MCPSchemaDriftError(MCPError):
    """Raised when an MCP tool's schema changed since operator approval, requiring re-approval."""
    def __init__(self, message_or_tool_id: Any, old_hash: Optional[str] = None, new_hash: Optional[str] = None):
        if old_hash and new_hash:
            msg = f"MCP tool '{message_or_tool_id}' schema drift detected (previous: {old_hash[:12]}..., current: {new_hash[:12]}...). Revalidation required."
            super().__init__(msg, status_code=409)
            self.tool_id = message_or_tool_id
            self.old_hash = old_hash
            self.new_hash = new_hash
        else:
            super().__init__(str(message_or_tool_id), status_code=409)
            self.tool_id = None
            self.old_hash = None
            self.new_hash = None


class MCPSecurityBlockError(MCPError):
    """Raised when an MCP tool call is blocked by Sentinel, Permission, or Policy."""
    def __init__(self, reason: str, findings: Optional[list] = None):
        super().__init__(f"MCP tool call blocked by control plane: {reason}", status_code=403)
        self.reason = reason
        self.findings = findings or []


class MCPApprovalRequiredError(MCPError):
    """Raised when an MCP tool call requires human operator authorization."""
    def __init__(self, approval_id: uuid.UUID, reason: str):
        super().__init__(
            f"MCP tool call requires operator approval. Approval ID: '{approval_id}'. Reason: {reason}",
            status_code=202,
        )
        self.approval_id = approval_id
        self.reason = reason


class MCPOutputSecurityError(MCPError):
    """Raised when MCP server output leaks credentials or critical vulnerabilities."""
    def __init__(self, reason: str, findings: Optional[list] = None):
        super().__init__(f"MCP output security firewall blocked response: {reason}", status_code=403)
        self.reason = reason
        self.findings = findings or []


class MCPPayloadSizeExceededError(MCPError):
    """Raised when MCP input arguments or server responses exceed maximum allowed size."""
    def __init__(self, size_bytes: int, max_bytes: int):
        super().__init__(
            f"MCP payload size ({size_bytes} bytes) exceeds maximum limit of {max_bytes} bytes",
            status_code=413,
        )
