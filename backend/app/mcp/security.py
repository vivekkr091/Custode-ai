"""Sentinel scanner integration and security analysis for CUSTODE MCP Security Layer."""

import json
from typing import Any, Dict, List, Optional
import uuid

from app.mcp.policy import (
    MCP_INPUT_PROFILE,
    MCP_OUTPUT_PROFILE,
    MCP_TOOL_DISCOVERY_PROFILE,
)
from app.sentinel.adapter import sentinel_adapter
from app.sentinel.findings import NormalizedFinding


def scan_mcp_tool_description(
    description: Optional[str],
    tool_name: str,
    server_id: uuid.UUID,
) -> List[NormalizedFinding]:
    """Scan untrusted MCP tool description text using Sentinel discovery profile."""
    if not description or not str(description).strip():
        return []

    context = {
        "mcp_server_id": str(server_id),
        "tool_name": tool_name,
        "source": "MCP_TOOL_DESCRIPTION",
    }

    return sentinel_adapter.scan_text(
        text=str(description).strip(),
        context=context,
        scanner_names=MCP_TOOL_DISCOVERY_PROFILE,
    )


def scan_mcp_input_arguments(
    arguments: Dict[str, Any],
    tool_name: str,
    agent_id: uuid.UUID,
    server_id: uuid.UUID,
) -> List[NormalizedFinding]:
    """Extract and scan MCP tool input arguments for prompt injection, secrets, and malicious payloads."""
    if not arguments:
        return []

    context = {
        "mcp_server_id": str(server_id),
        "tool_name": tool_name,
        "agent_id": str(agent_id),
        "stage": "mcp_input",
    }

    # Extract text content from arguments
    text_chunks: List[str] = []
    def _extract_text(obj: Any):
        if isinstance(obj, str) and obj.strip():
            text_chunks.append(obj.strip())
        elif isinstance(obj, dict):
            for v in obj.values():
                _extract_text(v)
        elif isinstance(obj, (list, tuple)):
            for item in obj:
                _extract_text(item)

    _extract_text(arguments)
    if not text_chunks:
        return []

    combined_text = "\n\n".join(text_chunks)
    return sentinel_adapter.scan_text(
        text=combined_text,
        context=context,
        scanner_names=MCP_INPUT_PROFILE,
    )


def scan_mcp_output_result(
    result: Any,
    tool_name: str,
    server_id: uuid.UUID,
) -> List[NormalizedFinding]:
    """Inspect untrusted MCP server output responses before releasing to agent/caller."""
    if result is None:
        return []

    context = {
        "mcp_server_id": str(server_id),
        "tool_name": tool_name,
        "stage": "mcp_output",
    }

    if isinstance(result, str):
        output_text = result
    else:
        try:
            output_text = json.dumps(result, default=str)
        except Exception:
            output_text = str(result)

    if not output_text.strip():
        return []

    return sentinel_adapter.scan_text(
        text=output_text,
        context=context,
        scanner_names=MCP_OUTPUT_PROFILE,
    )


def detect_schema_drift(existing_hash: Optional[str], new_hash: str) -> bool:
    """Check if an MCP tool's canonical schema hash has mutated since previous approval."""
    if not existing_hash:
        return False
    return existing_hash != new_hash
