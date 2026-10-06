"""Receiver-side cryptographic verification for incoming CUSTODE Webhooks."""

from datetime import datetime, timezone
import hashlib
import hmac
import json
import time
from typing import Any, Dict, Union

DEFAULT_TOLERANCE_SECONDS = 300  # 5 minutes


def verify_webhook_signature(
    payload: Union[bytes, str, Dict[str, Any]],
    signature_header: str,
    secret: str,
    tolerance_seconds: int = DEFAULT_TOLERANCE_SECONDS,
) -> bool:
    """Verify an incoming CUSTODE webhook signature with replay protection.

    Header format: `t=<timestamp>,v1=<signature>`
    Algorithm: HMAC-SHA256 over `t=<timestamp>.<serialized_payload>`

    Usage example:
    ```python
    from custode.security import verify_webhook_signature

    @app.post("/webhooks/custode")
    async def handle_custode_webhook(request: Request):
        payload_bytes = await request.body()
        sig_header = request.headers.get("X-Custode-Signature")

        if not verify_webhook_signature(payload_bytes, sig_header, WEBHOOK_SECRET):
            raise HTTPException(status_code=401, detail="Invalid signature or expired timestamp")

        event = json.loads(payload_bytes)
        print("Received verified security event:", event["event_type"])
        return {"status": "ok"}
    ```
    """
    if not signature_header or not secret:
        return False

    parts = dict(
        item.strip().split("=", 1)
        for item in signature_header.split(",")
        if "=" in item
    )
    t_str = parts.get("t")
    v1_sig = parts.get("v1")

    if not t_str or not v1_sig:
        return False

    try:
        timestamp = int(t_str)
    except ValueError:
        return False

    # 1. Replay defense (bounded past tolerance and max 60s future drift)
    now = int(time.time())
    if (now - timestamp) > tolerance_seconds or (timestamp - now) > 60:
        return False

    # 2. Serialize canonical body
    if isinstance(payload, bytes):
        payload_str = payload.decode("utf-8")
    elif isinstance(payload, dict):
        payload_str = json.dumps(payload, separators=(",", ":"), sort_keys=True)
    else:
        payload_str = str(payload)

    canonical_data = f"t={timestamp}.{payload_str}".encode("utf-8")
    expected_sig = hmac.new(
        secret.encode("utf-8"),
        canonical_data,
        hashlib.sha256,
    ).hexdigest()

    # 3. Constant-time comparison
    return hmac.compare_digest(v1_sig, expected_sig)
