"""Controlled Event Registry and Standard Webhook Payload Serialization."""

from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
import uuid

from app.audit.service import AuditEventType, sanitize_metadata

WEBHOOK_SPEC_VERSION = "1.0"

SUPPORTED_EVENT_TAXONOMY: Dict[str, Dict[str, Any]] = {
    "AUTHENTICATION": {
        "description": "User authentication, credential validation, and session events",
        "events": [
            AuditEventType.AUTH_LOGIN_SUCCESS.value,
            AuditEventType.AUTH_LOGIN_FAILURE.value,
        ],
    },
    "AGENT_GOVERNANCE": {
        "description": "Agent registration, status changes, and credential issuance",
        "events": [
            AuditEventType.AGENT_CREATED.value,
            AuditEventType.AGENT_UPDATED.value,
            AuditEventType.AGENT_SUSPENDED.value,
            AuditEventType.AGENT_REVOKED.value,
            AuditEventType.AGENT_CREDENTIAL_ISSUED.value,
            AuditEventType.AGENT_CREDENTIAL_REVOKED.value,
        ],
    },
    "POLICIES_PERMISSIONS": {
        "description": "Access control policies, permissions, and enforcement updates",
        "events": [
            AuditEventType.PERMISSION_CREATED.value,
            AuditEventType.PERMISSION_UPDATED.value,
            AuditEventType.POLICY_CREATED.value,
            AuditEventType.POLICY_PUBLISHED.value,
        ],
    },
    "RUNTIME_ACTIONS": {
        "description": "Agent runtime action registration and policy evaluation",
        "events": [
            AuditEventType.RUNTIME_ACTION_CREATED.value,
            AuditEventType.RUNTIME_ACTION_EVALUATED.value,
        ],
    },
    "RISK_DECISIONS": {
        "description": "Contextual risk scoring and policy decision outcomes",
        "events": [
            AuditEventType.RISK_ASSESSMENT_CREATED.value,
            AuditEventType.DECISION_CREATED.value,
        ],
    },
    "APPROVALS": {
        "description": "Human-in-the-loop governance and approval requests",
        "events": [
            AuditEventType.APPROVAL_CREATED.value,
            AuditEventType.APPROVAL_APPROVED.value,
            AuditEventType.APPROVAL_REJECTED.value,
            AuditEventType.APPROVAL_EXPIRED.value,
        ],
    },
    "EXECUTIONS": {
        "description": "Controlled execution layer outcomes and containment",
        "events": [
            AuditEventType.EXECUTION_CREATED.value,
            AuditEventType.EXECUTION_STARTED.value,
            AuditEventType.EXECUTION_SUCCEEDED.value,
            AuditEventType.EXECUTION_FAILED.value,
            AuditEventType.EXECUTION_BLOCKED.value,
        ],
    },
    "SECURITY_FINDINGS": {
        "description": "Sentinel security scan completions and vulnerability findings",
        "events": [
            AuditEventType.SECURITY_SCAN_COMPLETED.value,
            AuditEventType.SECURITY_FINDING_CREATED.value,
        ],
    },
    "LLM_SECURITY": {
        "description": "LLM Security Gateway prompt scanning and egress security firewall events",
        "events": [
            AuditEventType.LLM_REQUEST_RECEIVED.value,
            AuditEventType.LLM_INPUT_SCANNED.value,
            AuditEventType.LLM_REQUEST_BLOCKED.value,
            AuditEventType.LLM_OUTPUT_SCANNED.value,
            AuditEventType.LLM_OUTPUT_BLOCKED.value,
            AuditEventType.LLM_PROVIDER_ERROR.value,
        ],
    },
    "MCP_SECURITY": {
        "description": "Model Context Protocol tool discovery, invocation, and runtime containment",
        "events": [
            AuditEventType.MCP_SERVER_REGISTERED.value,
            AuditEventType.MCP_TOOL_DISCOVERED.value,
            AuditEventType.MCP_TOOL_SCHEMA_CHANGED.value,
            AuditEventType.MCP_TOOL_CALL_RECEIVED.value,
            AuditEventType.MCP_TOOL_CALL_BLOCKED.value,
            AuditEventType.MCP_TOOL_CALL_EXECUTED.value,
            AuditEventType.MCP_TOOL_RESULT_SCANNED.value,
            AuditEventType.MCP_TOOL_RESULT_BLOCKED.value,
        ],
    },
    "BEHAVIORAL_ANOMALIES": {
        "description": "Baseline deviation tracking, behavioral anomalies, and resolution",
        "events": [
            AuditEventType.BEHAVIOR_ANOMALY_DETECTED.value,
            AuditEventType.BEHAVIOR_ANOMALY_REVIEWED.value,
            AuditEventType.BEHAVIOR_ANOMALY_RESOLVED.value,
        ],
    },
    "INTEGRATIONS": {
        "description": "Webhook and external integration configuration lifecycle",
        "events": [
            AuditEventType.INTEGRATION_CREATED.value,
            AuditEventType.INTEGRATION_UPDATED.value,
            AuditEventType.INTEGRATION_SUSPENDED.value,
            AuditEventType.INTEGRATION_REVOKED.value,
        ],
    },
    "SYSTEM": {
        "description": "Diagnostic and test connectivity events",
        "events": [
            AuditEventType.INTEGRATION_TEST_PING.value,
        ],
    },
}

ALL_SUPPORTED_EVENTS: List[str] = sorted(
    list(
        {
            evt
            for group in SUPPORTED_EVENT_TAXONOMY.values()
            for evt in group["events"]
        }
    )
)

# Events that MUST NEVER be dispatched via webhooks to prevent infinite recursive loops
DISALLOWED_DISPATCH_EVENTS = frozenset({
    AuditEventType.WEBHOOK_DELIVERED.value,
    AuditEventType.WEBHOOK_FAILED.value,
})


def is_event_type_supported(event_type: str) -> bool:
    """Validate whether an event type belongs to the controlled registry."""
    return event_type in ALL_SUPPORTED_EVENTS


def format_webhook_payload(
    event_id: str,
    event_type: str,
    organization_id: uuid.UUID,
    action: str,
    outcome: str,
    actor_type: str = "SYSTEM",
    actor_id: Optional[str] = None,
    actor_display: Optional[str] = None,
    resource_type: Optional[str] = None,
    resource_id: Optional[str] = None,
    data: Optional[Dict[str, Any]] = None,
    request_id: Optional[str] = None,
    timestamp: Optional[datetime] = None,
) -> Dict[str, Any]:
    """Construct an authoritative, versioned, sanitized webhook payload."""
    ts = timestamp or datetime.now(timezone.utc)
    sanitized_data = sanitize_metadata(data or {})

    return {
        "spec_version": WEBHOOK_SPEC_VERSION,
        "event_id": str(event_id),
        "event_type": event_type,
        "timestamp": ts.isoformat(),
        "organization_id": str(organization_id),
        "request_id": request_id,
        "actor": {
            "type": actor_type,
            "id": actor_id,
            "display": actor_display,
        },
        "resource": {
            "type": resource_type,
            "id": resource_id,
        },
        "action": action,
        "outcome": outcome,
        "data": sanitized_data,
    }
