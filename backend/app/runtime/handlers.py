"""Controlled deterministic execution handlers for registered tools and operations.

IMPORTANT: No dynamic execution, eval(), exec(), subprocess, or shell commands.
All handlers are static, deterministic, and safe.
"""

from typing import Any, Dict
from app.runtime.executor import ExecutionContext, ExecutionResult


def health_check_handler(context: ExecutionContext) -> ExecutionResult:
    """Safe internal health check handler."""
    return ExecutionResult(
        success=True,
        output={
            "status": "healthy",
            "service": "internal",
            "environment": context.environment,
            "action_id": str(context.runtime_action_id),
        },
        metadata={"handler": "health_check_handler"},
    )


def echo_handler(context: ExecutionContext) -> ExecutionResult:
    """Safe deterministic echo handler returning sanitized parameters."""
    return ExecutionResult(
        success=True,
        output={
            "echo": context.get_sanitized_parameters(),
            "resource": context.resource,
            "environment": context.environment,
        },
        metadata={"handler": "echo_handler"},
    )


def mock_db_read_handler(context: ExecutionContext) -> ExecutionResult:
    """Safe simulated database read handler."""
    params = context.get_sanitized_parameters()
    query = params.get("query", "SELECT 1")
    return ExecutionResult(
        success=True,
        output={
            "status": "success",
            "row_count": 1,
            "data": [{"id": 101, "name": "sample_record", "query": str(query)}],
        },
        metadata={"handler": "mock_db_read_handler"},
    )


def mock_api_get_handler(context: ExecutionContext) -> ExecutionResult:
    """Safe simulated external API GET handler."""
    params = context.get_sanitized_parameters()
    endpoint = params.get("endpoint", "/api/v1/mock")
    return ExecutionResult(
        success=True,
        output={
            "status_code": 200,
            "endpoint": str(endpoint),
            "data": {"status": "ok", "message": "Simulated external API response"},
        },
        metadata={"handler": "mock_api_get_handler"},
    )


def mock_failing_handler(context: ExecutionContext) -> ExecutionResult:
    """Simulated failing handler for error handling testing."""
    return ExecutionResult(
        success=False,
        error_code="UPSTREAM_SERVICE_ERROR",
        error_message="Simulated upstream service connection failure",
        metadata={"handler": "mock_failing_handler"},
    )


def booking_search_handler(context: ExecutionContext) -> ExecutionResult:
    """Safe simulated booking room search handler for Acme Travel demo."""
    params = context.get_sanitized_parameters()
    city = params.get("city", "Paris")
    return ExecutionResult(
        success=True,
        output={
            "status": "available",
            "city": str(city),
            "rooms": [
                {
                    "room_id": "RM-PAR-101",
                    "type": "deluxe_king",
                    "nightly_rate_usd": 250,
                    "available": True,
                },
                {
                    "room_id": "RM-PAR-204",
                    "type": "executive_suite",
                    "nightly_rate_usd": 450,
                    "available": True,
                },
            ],
            "total_available": 2,
            "provider": "Acme Global Lodging Network",
        },
        metadata={"handler": "booking_search_handler", "action_id": str(context.runtime_action_id)},
    )


def booking_create_handler(context: ExecutionContext) -> ExecutionResult:
    """Safe simulated booking creation handler for Acme Travel demo."""
    params = context.get_sanitized_parameters()
    return ExecutionResult(
        success=True,
        output={
            "booking_reference": "BK-2026-ACME-90412",
            "reservation_status": "confirmed",
            "hotel_id": params.get("hotel_id", "HTL-771"),
            "room_type": params.get("room_type", "penthouse_suite"),
            "nights": params.get("nights", 3),
            "amount_billed": params.get("amount", 1250),
            "currency": params.get("currency", "USD"),
            "confirmation_code": "CONF-ACME-8841",
            "authorized_execution": True,
        },
        metadata={"handler": "booking_create_handler", "action_id": str(context.runtime_action_id)},
    )


def booking_cancel_handler(context: ExecutionContext) -> ExecutionResult:
    """Safe simulated booking cancellation handler."""
    params = context.get_sanitized_parameters()
    return ExecutionResult(
        success=True,
        output={
            "reservation_id": params.get("reservation_id", "RES-448291"),
            "cancellation_status": "cancelled",
            "refund_processed": False,
        },
        metadata={"handler": "booking_cancel_handler", "action_id": str(context.runtime_action_id)},
    )


def ipec_timetable_handler(context: ExecutionContext) -> ExecutionResult:
    """Safe deterministic handler for IPEC Ghaziabad timetable and syllabus."""
    params = context.get_sanitized_parameters()
    branch = params.get("branch", "Computer Science & Engineering")
    sem = params.get("semester", 6)
    return ExecutionResult(
        success=True,
        output={
            "institution": "Inderprastha Engineering College, Ghaziabad",
            "academic_year": "2025-2026",
            "branch": branch,
            "semester": sem,
            "schedule": [
                {"period": 1, "time": "09:00 - 10:00 AM", "subject": "Compiler Design (KCS-601)", "faculty": "Dr. A. K. Sharma", "room": "Block-B 302"},
                {"period": 2, "time": "10:00 - 11:00 AM", "subject": "Computer Networks (KCS-602)", "faculty": "Prof. Meenakshi Singh", "room": "Block-B 302"},
                {"period": 3, "time": "11:15 - 12:15 PM", "subject": "Web Technology Lab", "faculty": "Er. Rahul Verma", "room": "Lab 4, CS Dept"},
                {"period": 4, "time": "01:00 - 02:00 PM", "subject": "Data Analytics & ML", "faculty": "Dr. Vikas Kumar", "room": "Block-B 302"}
            ],
            "attendance_requirement": "75% minimum required by AKTU",
            "verified_by": "IPEC Academic Section"
        },
        metadata={"handler": "ipec_timetable_handler", "action_id": str(context.runtime_action_id)},
    )


def ipec_fee_payment_handler(context: ExecutionContext) -> ExecutionResult:
    """Safe deterministic handler for IPEC Ghaziabad semester fee payment."""
    params = context.get_sanitized_parameters()
    return ExecutionResult(
        success=True,
        output={
            "receipt_no": "IPEC-REC-2026-88914",
            "transaction_status": "PAID_AND_VERIFIED",
            "student_name": params.get("student_name", "Priya Sharma"),
            "roll_no": params.get("roll_no", "2100300100088"),
            "amount_paid_inr": params.get("amount_inr", 65000),
            "fee_head": params.get("fee_head", "6th Semester Tuition Fee"),
            "payment_gateway": "HDFC SmartHub Campus Pay",
            "approval_authorization": "Authorized by Accounts Officer",
            "timestamp": "2026-10-25T18:15:00Z"
        },
        metadata={"handler": "ipec_fee_payment_handler", "action_id": str(context.runtime_action_id)},
    )


def ipec_attendance_handler(context: ExecutionContext) -> ExecutionResult:
    """Safe deterministic handler for IPEC Ghaziabad student attendance and marks."""
    params = context.get_sanitized_parameters()
    return ExecutionResult(
        success=True,
        output={
            "student_roll_no": params.get("roll_no", "2100300100088"),
            "aggregate_attendance": "84.5%",
            "status": "ELIGIBLE_FOR_EXAMS",
            "subject_breakdown": {
                "Compiler Design": "88%",
                "Computer Networks": "82%",
                "Web Technology": "86%",
                "Data Analytics": "83%"
            },
            "sgpa_last_sem": 8.42
        },
        metadata={"handler": "ipec_attendance_handler", "action_id": str(context.runtime_action_id)},
    )

