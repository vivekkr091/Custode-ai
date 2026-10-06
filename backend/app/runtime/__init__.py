"""Runtime Action normalization, execution guard, and controlled execution package."""

from app.runtime.execution_guard import ExecutionGuard, ExecutionGuardResult
from app.runtime.execution_registry import ExecutionRegistry, execution_registry
from app.runtime.executor import (
    BaseActionExecutor,
    ExecutionContext,
    ExecutionResult,
    sanitize_parameters,
)
from app.runtime.handlers import (
    echo_handler,
    health_check_handler,
    mock_api_get_handler,
    mock_db_read_handler,
    mock_failing_handler,
)
from app.runtime.normalizer import (
    ActionNormalizer,
    NormalizationError,
    normalize_action_type,
    normalize_amount,
    normalize_currency,
    normalize_environment,
    normalize_ip_address,
    normalize_parameters,
    normalize_request_id,
    normalize_resource,
    normalize_resource_type,
    normalize_user_agent,
)

__all__ = [
    "ActionNormalizer",
    "NormalizationError",
    "normalize_environment",
    "normalize_action_type",
    "normalize_resource",
    "normalize_resource_type",
    "normalize_parameters",
    "normalize_amount",
    "normalize_currency",
    "normalize_ip_address",
    "normalize_user_agent",
    "normalize_request_id",
    "ExecutionContext",
    "ExecutionResult",
    "BaseActionExecutor",
    "sanitize_parameters",
    "ExecutionGuard",
    "ExecutionGuardResult",
    "ExecutionRegistry",
    "execution_registry",
    "health_check_handler",
    "echo_handler",
    "mock_db_read_handler",
    "mock_api_get_handler",
    "mock_failing_handler",
]
