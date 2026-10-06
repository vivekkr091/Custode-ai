# CUSTODE Python Agent Security SDK Guide

## 1. Overview

The `custode-sdk` package provides official Python bindings for external AI agents, autonomous frameworks (LangChain, LlamaIndex, AutoGen, CrewAI), and backend microservices to interact securely with the CUSTODE Control Plane.

**Core Principle:** The CUSTODE backend owns identity, permission evaluation, policy evaluation, risk assessment, human approvals, and execution sandboxing. The SDK provides a typed, developer-friendly interface to those controls.

---

## 2. Installation

Install via pip:

```bash
pip install custode-sdk
```

---

## 3. Asynchronous Client Usage

```python
import asyncio
from custode import AsyncCustodeClient

async def main():
    async with AsyncCustodeClient(
        base_url="http://localhost:8000",
        api_key="cst_live_agent_key_xxxxxxxx",
        organization_id="11111111-1111-1111-1111-111111111111",
    ) as client:
        # 1. Submit Runtime Action
        action = await client.actions.create(
            tool_id="22222222-2222-2222-2222-222222222222",
            operation_id="33333333-3333-3333-3333-333333333333",
            action_type="tool_call",
            environment="production",
            parameters={"query": "SELECT * FROM customers WHERE id = 1"},
        )
        print(f"Action registered: {action.id}")

        # 2. Request Authoritative Decision
        decision = await client.decisions.evaluate(action_id=action.id)
        print(f"Policy Decision: {decision.decision} (Risk: {decision.risk_level})")

        # 3. Conditional Execution Dispatch
        if decision.decision == "ALLOW":
            execution = await client.executions.execute(action_id=action.id)
            print(f"Execution succeeded: {execution.status}")
        elif decision.decision == "REQUIRE_APPROVAL":
            print("Action held for human review in CUSTODE dashboard.")
        else:
            print("Action blocked by CUSTODE security policy.")

if __name__ == "__main__":
    asyncio.run(main())
```

---

## 4. Secure Webhook Verification

Verify incoming CUSTODE webhook notifications in external automation receivers:

```python
from custode.security.webhooks import verify_webhook_signature

def handle_webhook_event(raw_payload: bytes, headers: dict, secret: str):
    is_valid = verify_webhook_signature(
        payload=raw_payload,
        signature_header=headers.get("X-Custode-Signature"),
        timestamp_header=headers.get("X-Custode-Timestamp"),
        secret=secret,
        tolerance_seconds=300,
    )
    if not is_valid:
        raise ValueError("Invalid or replayed webhook signature")

    print("Authentic webhook event verified!")
```
