"""Action normalization engine converting incoming requests to canonical RuntimeActionContext.

Deterministic, safe, and tamper-resistant: no eval(), exec(), or arbitrary code execution.
"""

import ipaddress
import math
from typing import Any, Dict, Optional, Union
import uuid

from app.schemas.runtime_action import RuntimeActionContext, RuntimeActionCreate


class NormalizationError(ValueError):
    """Raised when an incoming action request fails canonical normalization."""
    pass


ENV_MAPPING = {
    "dev": "dev",
    "development": "dev",
    "staging": "staging",
    "stage": "staging",
    "prod": "prod",
    "production": "prod",
}


def normalize_environment(raw_env: str) -> str:
    """Normalize environment string to canonical tier: 'dev', 'staging', or 'prod'."""
    if not raw_env or not isinstance(raw_env, str):
        raise NormalizationError("Environment must be a non-empty string")
    clean = raw_env.strip().lower()
    if clean not in ENV_MAPPING:
        raise NormalizationError(
            f"Invalid environment: '{raw_env}'. Must be one of: dev, staging, prod"
        )
    return ENV_MAPPING[clean]


def normalize_action_type(raw_type: str) -> str:
    """Normalize action type to clean lowercase identifier."""
    if not raw_type or not isinstance(raw_type, str):
        raise NormalizationError("Action type must be a non-empty string")
    clean = raw_type.strip().lower()
    if not clean:
        raise NormalizationError("Action type cannot be empty whitespace")
    return clean


def normalize_resource(raw_resource: Optional[str]) -> Optional[str]:
    """Normalize resource URI/path safely without destructive alteration."""
    if raw_resource is None:
        return None
    clean = raw_resource.strip()
    if not clean:
        return None
    # Strip redundant trailing slashes if longer than single root slash
    if len(clean) > 1 and clean.endswith("/"):
        clean = clean.rstrip("/")
    return clean


def normalize_resource_type(raw_type: Optional[str]) -> Optional[str]:
    """Normalize resource type category to clean lowercase."""
    if raw_type is None:
        return None
    clean = raw_type.strip().lower()
    return clean or None


def _validate_json_serializable(obj: Any, path: str = "parameters") -> None:
    """Recursively verify that parameter structures contain only safe JSON primitives."""
    if obj is None or isinstance(obj, (str, int, float, bool)):
        if isinstance(obj, float) and (math.isnan(obj) or math.isinf(obj)):
            raise NormalizationError(f"Parameter at '{path}' cannot contain NaN or Infinity")
        return
    if isinstance(obj, dict):
        for k, v in obj.items():
            if not isinstance(k, str):
                raise NormalizationError(f"Parameter key at '{path}' must be a string, got {type(k).__name__}")
            _validate_json_serializable(v, f"{path}.{k}")
        return
    if isinstance(obj, (list, tuple)):
        for i, item in enumerate(obj):
            _validate_json_serializable(item, f"{path}[{i}]")
        return
    raise NormalizationError(f"Parameter at '{path}' contains non-serializable type: {type(obj).__name__}")


def normalize_parameters(raw_params: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    """Normalize parameters into a deterministic, validated dictionary."""
    if raw_params is None:
        return {}
    if not isinstance(raw_params, dict):
        raise NormalizationError("Parameters must be a JSON object dictionary")
    _validate_json_serializable(raw_params)
    return dict(raw_params)


def normalize_amount(raw_amount: Optional[Any]) -> Optional[float]:
    """Normalize amount to rounded 4-decimal float, rejecting negative/invalid values."""
    if raw_amount is None:
        return None
    if isinstance(raw_amount, bool):
        raise NormalizationError("Amount cannot be a boolean value")
    try:
        val = float(raw_amount)
    except (TypeError, ValueError):
        raise NormalizationError(f"Invalid numeric amount: '{raw_amount}'")

    if math.isnan(val) or math.isinf(val):
        raise NormalizationError("Amount cannot be NaN or Infinity")
    if val < 0:
        raise NormalizationError("Amount cannot be negative")

    return round(val, 4)


def normalize_currency(raw_currency: Optional[str]) -> Optional[str]:
    """Normalize currency code to clean uppercase standard."""
    if raw_currency is None:
        return None
    clean = raw_currency.strip().upper()
    return clean or None


def normalize_ip_address(raw_ip: Optional[str]) -> Optional[str]:
    """Normalize and validate IP address string using standard library."""
    if raw_ip is None:
        return None
    clean = raw_ip.strip()
    if not clean:
        return None
    try:
        parsed = ipaddress.ip_address(clean)
        return str(parsed)
    except ValueError:
        raise NormalizationError(f"Invalid IP address format: '{raw_ip}'")


def normalize_user_agent(raw_ua: Optional[str]) -> Optional[str]:
    """Normalize user agent string with length boundary."""
    if raw_ua is None:
        return None
    clean = raw_ua.strip()
    if not clean:
        return None
    return clean[:500]


def normalize_request_id(raw_id: Optional[Union[uuid.UUID, str]]) -> uuid.UUID:
    """Normalize request correlation ID or generate a fresh UUID4."""
    if raw_id is None:
        return uuid.uuid4()
    if isinstance(raw_id, uuid.UUID):
        return raw_id
    try:
        return uuid.UUID(str(raw_id).strip())
    except ValueError:
        raise NormalizationError(f"Invalid request_id format: '{raw_id}'")


class ActionNormalizer:
    """Authoritative normalizer transforming incoming action payloads into canonical context."""

    @classmethod
    def normalize(
        cls,
        organization_id: uuid.UUID,
        agent_id: uuid.UUID,
        data: RuntimeActionCreate,
    ) -> RuntimeActionContext:
        """Produce a canonical, validated, and deterministic RuntimeActionContext."""
        if not isinstance(organization_id, uuid.UUID):
            raise NormalizationError("organization_id must be a valid UUID")
        if not isinstance(agent_id, uuid.UUID):
            raise NormalizationError("agent_id must be a valid UUID")
        if not isinstance(data.tool_id, uuid.UUID):
            raise NormalizationError("tool_id must be a valid UUID")
        if not isinstance(data.operation_id, uuid.UUID):
            raise NormalizationError("operation_id must be a valid UUID")

        env = normalize_environment(data.environment)
        action_type = normalize_action_type(data.action_type)
        resource = normalize_resource(data.resource)
        resource_type = normalize_resource_type(data.resource_type)
        parameters = normalize_parameters(data.parameters)
        amount = normalize_amount(data.amount)
        currency = normalize_currency(data.currency)
        ip_addr = normalize_ip_address(data.ip_address)
        ua = normalize_user_agent(data.user_agent)
        req_id = normalize_request_id(data.request_id)

        return RuntimeActionContext(
            organization_id=organization_id,
            agent_id=agent_id,
            tool_id=data.tool_id,
            operation_id=data.operation_id,
            request_id=req_id,
            environment=env,
            action_type=action_type,
            resource=resource,
            resource_type=resource_type,
            parameters=parameters,
            amount=amount,
            currency=currency,
            ip_address=ip_addr,
            user_agent=ua,
        )
