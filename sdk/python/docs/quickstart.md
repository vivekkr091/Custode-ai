# CUSTODE Python SDK — Quickstart Guide

## Installation

```bash
pip install custode-sdk
```

## 1. Authentication & Configuration

The SDK authenticates agents using high-entropy API keys issued by the CUSTODE Control Plane.

```python
import os
from custode import CUSTODEClient

# Recommended: set CUSTODE_AGENT_API_KEY environment variable
client = CUSTODEClient(
    base_url="http://localhost:8000", # Or https://api.custode.io in production
    api_key=os.environ["CUSTODE_AGENT_API_KEY"],
)

# Verify caller identity
identity = client.verify_identity()
print(f"Connected as Agent: {identity.agent_id} in Org: {identity.organization_id}")
```

## 2. Registering and Arbitrating a RuntimeAction

```python
# 1. Register intended action
action = client.runtime_actions.create(
    tool_id="00000000-0000-0000-0000-000000000001",
    operation_id="00000000-0000-0000-0000-000000000002",
    parameters={"query": "SELECT * FROM users LIMIT 10"},
)

# 2. Evaluate security decision
decision = client.runtime_actions.decide(action.id)

if decision.is_allowed:
    # 3. Controlled execution
    execution = client.runtime_actions.execute(action.id)
    print(f"Result: {execution.result}")
elif decision.requires_approval:
    print(f"Action requires human approval: {decision.reason}")
else:
    print(f"Action blocked by policy: {decision.reason}")
```

## 3. Asynchronous Client Usage

```python
import asyncio
from custode import AsyncCUSTODEClient

async def main():
    async with AsyncCUSTODEClient() as client:
        identity = await client.verify_identity()
        print(f"Agent {identity.agent_id} verified.")

asyncio.run(main())
```
