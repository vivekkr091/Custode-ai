"""Example 08: Webhook Receiver with HMAC-SHA256 Signature Verification.

Demonstrates how an external service (e.g. FastAPI / Flask / Lambda) receives
and cryptographically authenticates incoming CUSTODE security webhooks.
"""

from datetime import datetime, timezone
import json
import time

from custode.security import verify_webhook_signature

# Secret obtained ONCE during integration creation
WEBHOOK_SECRET = "cst_whsec_7b8a9c0d1e2f_sampleSecretKeyForTestingWebhookSignatures1234"


def simulate_incoming_custode_webhook(payload_dict: dict, secret: str) -> dict:
    """Helper to simulate the CUSTODE Webhook Dispatcher sending a request."""
    import hashlib
    import hmac

    payload_json = json.dumps(payload_dict, separators=(",", ":"), sort_keys=True)
    ts = int(time.time())
    canonical = f"t={ts}.{payload_json}".encode("utf-8")
    sig = hmac.new(secret.encode("utf-8"), canonical, hashlib.sha256).hexdigest()

    headers = {
        "Content-Type": "application/json",
        "User-Agent": "CUSTODE-Webhook-Dispatcher/1.0",
        "X-Custode-Signature": f"t={ts},v1={sig}",
        "X-Custode-Event": payload_dict["event_type"],
        "X-Custode-Delivery": "deliv-12345678-abcd",
        "X-Request-ID": "req-sample-correlation-id",
    }
    return {"headers": headers, "body": payload_json.encode("utf-8")}


def handle_webhook_request(headers: dict, raw_body: bytes) -> dict:
    """Example handler for an HTTP webhook receiver."""
    sig_header = headers.get("X-Custode-Signature")
    if not sig_header:
        raise ValueError("Missing required X-Custode-Signature header")

    # 1. Cryptographically verify signature and defend against replay attacks (5-minute window)
    is_valid = verify_webhook_signature(
        payload=raw_body,
        signature_header=sig_header,
        secret=WEBHOOK_SECRET,
        tolerance_seconds=300,
    )

    if not is_valid:
        raise PermissionError("Webhook signature verification failed or timestamp expired!")

    # 2. Parse sanitized payload
    data = json.loads(raw_body.decode("utf-8"))
    event_type = data.get("event_type")
    action = data.get("action")
    outcome = data.get("outcome")

    print(f"[RECV] Verified Security Event: {event_type}")
    print(f"       Action: {action}, Outcome: {outcome}")
    print(f"       Actor: {data.get('actor')}")
    print(f"       Data: {data.get('data')}")

    return {"status": "accepted", "event_id": data.get("event_id")}


def main() -> None:
    print("--- CUSTODE Secure Webhook Receiver Example ---")

    sample_event = {
        "spec_version": "1.0",
        "event_id": "evt-777",
        "event_type": "DECISION_CREATED",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "organization_id": "org-999",
        "request_id": "req-abc-123",
        "actor": {"type": "AGENT", "id": "agent-financial-bot", "display": "FinanceBot"},
        "resource": {"type": "tool_operation", "id": "op-transfer-funds"},
        "action": "evaluate",
        "outcome": "allow",
        "data": {
            "decision": "allow",
            "risk_score": 15,
            "policy_matched": "standard-financial-limits",
        },
    }

    # Simulate dispatch
    request_data = simulate_incoming_custode_webhook(sample_event, WEBHOOK_SECRET)

    # Process incoming request
    result = handle_webhook_request(request_data["headers"], request_data["body"])
    print("[SUCCESS] Result:", result)


if __name__ == "__main__":
    main()
