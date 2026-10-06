"""Webhook Delivery Engine, Retry Management, and Network Dispatcher."""

from datetime import datetime, timedelta, timezone
import json
import logging
import random
import time
from typing import Any, Dict, List, Optional
import uuid

import httpx
from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.correlation import get_current_request_id
from app.db.models.audit_event import AuditEvent
from app.db.models.integration import Integration, IntegrationStatus
from app.db.models.webhook_delivery import (
    AttemptStatus,
    DeliveryStatus,
    WebhookAttempt,
    WebhookDelivery,
)
from app.services.integrations.crypto import (
    compute_webhook_signature,
    get_secret_provider,
)
from app.services.integrations.events import (
    DISALLOWED_DISPATCH_EVENTS,
    format_webhook_payload,
    is_event_type_supported,
)
from app.services.integrations.ssrf import (
    SSRFProtectionError,
    validate_destination_address,
)

logger = logging.getLogger("custode.webhooks.delivery")

DEFAULT_CONNECT_TIMEOUT_SEC = 5.0
DEFAULT_READ_TIMEOUT_SEC = 10.0
MAX_RESPONSE_BODY_CAPTURE_BYTES = 500


def calculate_backoff_delay(attempt_count: int, base_seconds: float = 10.0) -> float:
    """Calculate exponential backoff delay with jitter.

    Formula: min(base * (2 ** (attempt - 1)) + jitter, 3600)
    """
    exponent = max(0, attempt_count - 1)
    delay = base_seconds * (2 ** exponent)
    jitter = random.uniform(0.1, 1.5)
    return min(delay + jitter, 3600.0)


async def execute_delivery_attempt(
    session: AsyncSession,
    delivery: WebhookDelivery,
    integration: Integration,
    client: Optional[httpx.AsyncClient] = None,
    allow_local: bool = False,
    allow_insecure: bool = False,
) -> WebhookAttempt:
    """Execute an HTTP POST delivery attempt against the integration destination."""
    delivery.attempt_count += 1
    attempt_num = delivery.attempt_count
    start_time = time.monotonic()

    # 1. SSRF Pre-validation
    try:
        validate_destination_address(
            integration.url,
            allow_insecure=allow_insecure,
            allow_local=allow_local,
        )
    except SSRFProtectionError as ssrf_err:
        duration_ms = int((time.monotonic() - start_time) * 1000)
        err_msg = f"SSRF Check Blocked: {str(ssrf_err)}"
        delivery.delivery_status = DeliveryStatus.FAILED.value
        delivery.sanitized_response_summary = err_msg[:500]
        delivery.next_retry_at = None

        attempt = WebhookAttempt(
            delivery_id=delivery.id,
            attempt_number=attempt_num,
            status=AttemptStatus.FAILED.value,
            response_status_code=None,
            duration_ms=duration_ms,
            sanitized_error=err_msg[:500],
            attempted_at=datetime.now(timezone.utc),
        )
        session.add(attempt)
        await session.flush()
        return attempt

    # 2. Decrypt signing secret & compute HMAC signature
    try:
        provider = get_secret_provider()
        signing_secret = provider.decrypt(integration.encrypted_secret)
    except Exception as decrypt_err:
        duration_ms = int((time.monotonic() - start_time) * 1000)
        err_msg = f"Secret Decryption Error: {str(decrypt_err)}"
        delivery.delivery_status = DeliveryStatus.FAILED.value
        delivery.sanitized_response_summary = err_msg[:500]
        delivery.next_retry_at = None

        attempt = WebhookAttempt(
            delivery_id=delivery.id,
            attempt_number=attempt_num,
            status=AttemptStatus.FAILED.value,
            response_status_code=None,
            duration_ms=duration_ms,
            sanitized_error=err_msg[:500],
            attempted_at=datetime.now(timezone.utc),
        )
        session.add(attempt)
        await session.flush()
        return attempt

    payload_json = json.dumps(delivery.payload, separators=(",", ":"), sort_keys=True)
    ts = int(time.time())
    sig_header, _ = compute_webhook_signature(payload_json, signing_secret, timestamp=ts)

    headers = {
        "Content-Type": "application/json",
        "User-Agent": "CUSTODE-Webhook-Dispatcher/1.0",
        "X-Custode-Signature": sig_header,
        "X-Custode-Event": delivery.event_type,
        "X-Custode-Delivery": str(delivery.id),
        "X-Request-ID": delivery.request_id or "",
    }
    if integration.headers:
        # Merge custom headers without overriding security headers
        for k, v in integration.headers.items():
            if k.lower() not in (
                "x-custode-signature",
                "x-custode-event",
                "x-custode-delivery",
                "content-type",
            ):
                headers[k] = str(v)

    # 3. Perform network dispatch with bounded timeouts and follow_redirects=False
    close_client = False
    if client is None:
        client = httpx.AsyncClient(
            timeout=httpx.Timeout(
                connect=DEFAULT_CONNECT_TIMEOUT_SEC,
                read=DEFAULT_READ_TIMEOUT_SEC,
                write=DEFAULT_READ_TIMEOUT_SEC,
                pool=DEFAULT_CONNECT_TIMEOUT_SEC,
            ),
            follow_redirects=False,
        )
        close_client = True

    status_code: Optional[int] = None
    sanitized_body: Optional[str] = None
    sanitized_err: Optional[str] = None
    attempt_status = AttemptStatus.FAILED.value

    try:
        response = await client.post(
            integration.url,
            content=payload_json.encode("utf-8"),
            headers=headers,
        )
        duration_ms = int((time.monotonic() - start_time) * 1000)
        status_code = response.status_code
        delivery.response_status_code = status_code

        # Capture bounded response body
        raw_text = response.text[:MAX_RESPONSE_BODY_CAPTURE_BYTES]
        sanitized_body = "".join(ch for ch in raw_text if ch.isprintable() or ch in "\n\r\t")

        if 200 <= status_code < 300:
            # Success
            delivery.delivery_status = DeliveryStatus.DELIVERED.value
            delivery.delivered_at = datetime.now(timezone.utc)
            delivery.next_retry_at = None
            delivery.sanitized_response_summary = f"HTTP {status_code} Success: {sanitized_body[:100]}"
            integration.last_delivery_at = delivery.delivered_at
            attempt_status = AttemptStatus.SUCCESS.value
        elif status_code == 429 or status_code >= 500:
            # Retryable server error or rate limiting
            attempt_status = AttemptStatus.RETRYABLE_FAILURE.value
            if attempt_num < delivery.max_attempts:
                delivery.delivery_status = DeliveryStatus.RETRYING.value
                delay = calculate_backoff_delay(attempt_num)
                delivery.next_retry_at = datetime.now(timezone.utc) + timedelta(seconds=delay)
                delivery.sanitized_response_summary = f"HTTP {status_code} Retryable: {sanitized_body[:100]}"
            else:
                delivery.delivery_status = DeliveryStatus.FAILED.value
                delivery.next_retry_at = None
                delivery.sanitized_response_summary = f"HTTP {status_code} Max attempts exceeded: {sanitized_body[:100]}"
        else:
            # 4xx client errors (400, 401, 403, 404, etc.) are non-retryable
            delivery.delivery_status = DeliveryStatus.FAILED.value
            delivery.next_retry_at = None
            delivery.sanitized_response_summary = f"HTTP {status_code} Client Error (Non-retryable): {sanitized_body[:100]}"
            attempt_status = AttemptStatus.FAILED.value

    except (httpx.TimeoutException, httpx.NetworkError, httpx.TransportError) as net_err:
        duration_ms = int((time.monotonic() - start_time) * 1000)
        sanitized_err = f"Network Transport Error: {net_err.__class__.__name__}"
        attempt_status = AttemptStatus.RETRYABLE_FAILURE.value

        if attempt_num < delivery.max_attempts:
            delivery.delivery_status = DeliveryStatus.RETRYING.value
            delay = calculate_backoff_delay(attempt_num)
            delivery.next_retry_at = datetime.now(timezone.utc) + timedelta(seconds=delay)
            delivery.sanitized_response_summary = sanitized_err
        else:
            delivery.delivery_status = DeliveryStatus.FAILED.value
            delivery.next_retry_at = None
            delivery.sanitized_response_summary = f"{sanitized_err} (Max attempts exceeded)"

    except Exception as exc:
        duration_ms = int((time.monotonic() - start_time) * 1000)
        sanitized_err = f"Delivery Dispatch Exception: {exc.__class__.__name__}"
        delivery.delivery_status = DeliveryStatus.FAILED.value
        delivery.next_retry_at = None
        delivery.sanitized_response_summary = sanitized_err
        attempt_status = AttemptStatus.FAILED.value

    finally:
        if close_client and client:
            await client.aclose()

    attempt = WebhookAttempt(
        delivery_id=delivery.id,
        attempt_number=attempt_num,
        status=attempt_status,
        response_status_code=status_code,
        duration_ms=duration_ms,
        sanitized_error=sanitized_err,
        attempted_at=datetime.now(timezone.utc),
    )
    session.add(attempt)
    await session.flush()
    return attempt


async def dispatch_event_to_integrations(
    session: AsyncSession,
    organization_id: uuid.UUID,
    event_id: str,
    event_type: str,
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
    client: Optional[httpx.AsyncClient] = None,
    allow_local: bool = False,
    allow_insecure: bool = False,
) -> List[WebhookDelivery]:
    """Dispatch a security event to all active integrations subscribed to the event type."""
    # 1. Anti-recursion guard: Webhook delivery events must NEVER trigger deliveries!
    if event_type in DISALLOWED_DISPATCH_EVENTS:
        return []

    # 2. Query active integrations for this organization
    q = select(Integration).where(
        Integration.organization_id == organization_id,
        Integration.status == IntegrationStatus.ACTIVE.value,
    )
    res = await session.execute(q)
    integrations = list(res.scalars().all())

    matching_integrations = [
        integ for integ in integrations
        if event_type in integ.subscribed_events or "*" in integ.subscribed_events
    ]

    if not matching_integrations:
        return []

    req_id = request_id or get_current_request_id()
    payload = format_webhook_payload(
        event_id=event_id,
        event_type=event_type,
        organization_id=organization_id,
        action=action,
        outcome=outcome,
        actor_type=actor_type,
        actor_id=actor_id,
        actor_display=actor_display,
        resource_type=resource_type,
        resource_id=resource_id,
        data=data,
        request_id=req_id,
        timestamp=timestamp,
    )

    created_deliveries: List[WebhookDelivery] = []

    for integ in matching_integrations:
        delivery = WebhookDelivery(
            organization_id=organization_id,
            integration_id=integ.id,
            event_id=str(event_id),
            event_type=event_type,
            request_id=req_id,
            delivery_status=DeliveryStatus.PENDING.value,
            attempt_count=0,
            max_attempts=3,
            payload=payload,
        )
        session.add(delivery)
        await session.flush()

        # Trigger attempt immediately
        await execute_delivery_attempt(
            session=session,
            delivery=delivery,
            integration=integ,
            client=client,
            allow_local=allow_local,
            allow_insecure=allow_insecure,
        )
        created_deliveries.append(delivery)

    return created_deliveries
