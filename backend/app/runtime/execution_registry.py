"""Controlled execution registry mapping registered tools/operations to safe execution handlers."""

import inspect
from typing import Any, Callable, Dict, Optional
from app.runtime.executor import ExecutionContext, ExecutionResult
from app.runtime.handlers import (
    booking_cancel_handler,
    booking_create_handler,
    booking_search_handler,
    echo_handler,
    health_check_handler,
    ipec_attendance_handler,
    ipec_fee_payment_handler,
    ipec_timetable_handler,
    mock_api_get_handler,
    mock_db_read_handler,
    mock_failing_handler,
)


class ExecutionRegistry:
    """Static registry of verified execution handlers for CUSTODE tools.
    
    Prevents arbitrary execution by maintaining an explicit allowlist of handlers.
    Strictly forbids dynamic code execution, eval, exec, and subprocess.
    """

    def __init__(self) -> None:
        self._handlers: Dict[str, Callable[[ExecutionContext], ExecutionResult]] = {}
        self._register_default_handlers()

    def _register_default_handlers(self) -> None:
        """Register safe built-in handlers."""
        self.register("internal:health_check", health_check_handler)
        self.register("internal:echo", echo_handler)
        self.register("database:read", mock_db_read_handler)
        self.register("http:get", mock_api_get_handler)
        self.register("api:get", mock_api_get_handler)
        self.register("test:fail", mock_failing_handler)
        # Acme Travel demo tool registrations
        self.register("booking_tool:search_available_rooms", booking_search_handler)
        self.register("booking_tool:create_booking", booking_create_handler)
        self.register("booking_tool:cancel_booking", booking_cancel_handler)
        self.register("booking-management-tool:search-available-rooms", booking_search_handler)
        self.register("booking-management-tool:create-booking", booking_create_handler)
        self.register("booking-management-tool:cancel-booking", booking_cancel_handler)
        # IPEC Ghaziabad Campus Bot registrations
        self.register("ipec_erp_portal:get_syllabus_and_timetable", ipec_timetable_handler)
        self.register("ipec_erp_portal:get_attendance_and_grades", ipec_attendance_handler)
        self.register("ipec_erp_portal:submit_semester_fee", ipec_fee_payment_handler)
        self.register("ipec-campus-erp-portal:get-syllabus-and-timetable", ipec_timetable_handler)
        self.register("ipec-campus-erp-portal:get-attendance-and-grades", ipec_attendance_handler)
        self.register("ipec-campus-erp-portal:submit-semester-fee", ipec_fee_payment_handler)


    def register(
        self,
        key: str,
        handler: Callable[[ExecutionContext], ExecutionResult],
    ) -> None:
        """Register a handler for a given tool/operation key."""
        self._handlers[key.lower().strip()] = handler

    def unregister(self, key: str) -> None:
        """Unregister a handler for testing purposes."""
        self._handlers.pop(key.lower().strip(), None)

    def get_handler(
        self,
        tool_slug: str,
        operation_slug: str,
        tool_type: Optional[str] = None,
        operation_type: Optional[str] = None,
    ) -> Optional[Callable[[ExecutionContext], ExecutionResult]]:
        """Look up handler by slug key first, then by type key."""
        # 1. Exact slug match: e.g. "github:read_repo" or "internal:health_check"
        slug_key = f"{tool_slug}:{operation_slug}".lower().strip()
        if slug_key in self._handlers:
            return self._handlers[slug_key]

        normalized_slug = slug_key.replace("-", "_")
        if normalized_slug in self._handlers:
            return self._handlers[normalized_slug]

        hyphen_slug = slug_key.replace("_", "-")
        if hyphen_slug in self._handlers:
            return self._handlers[hyphen_slug]

        # 2. Type fallback: e.g. "http:get" or "database:read"
        if tool_type and operation_type:
            type_key = f"{tool_type}:{operation_type}".lower().strip()
            if type_key in self._handlers:
                return self._handlers[type_key]
            if type_key.replace("-", "_") in self._handlers:
                return self._handlers[type_key.replace("-", "_")]
            if type_key.replace("_", "-") in self._handlers:
                return self._handlers[type_key.replace("_", "-")]

        return None

    async def execute(
        self,
        context: ExecutionContext,
        tool_slug: str,
        operation_slug: str,
        tool_type: Optional[str] = None,
        operation_type: Optional[str] = None,
    ) -> ExecutionResult:
        """Safely dispatch execution to registered handler."""
        handler = self.get_handler(
            tool_slug=tool_slug,
            operation_slug=operation_slug,
            tool_type=tool_type,
            operation_type=operation_type,
        )

        if not handler:
            return ExecutionResult(
                success=False,
                error_code="HANDLER_NOT_REGISTERED",
                error_message=(
                    f"No execution handler registered for tool '{tool_slug}' "
                    f"and operation '{operation_slug}'"
                ),
            )

        try:
            if inspect.iscoroutinefunction(handler):
                result = await handler(context)
            else:
                result = handler(context)
            return result
        except Exception as exc:
            return ExecutionResult(
                success=False,
                error_code="EXECUTION_HANDLER_ERROR",
                error_message=f"Handler raised exception: {str(exc)}",
            )


# Global singleton execution registry
execution_registry = ExecutionRegistry()
