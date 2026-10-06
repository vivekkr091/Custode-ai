"""Example 5: High-concurrency async client workflow."""

import asyncio
import os
import sys
from custode import AsyncCUSTODEClient
from custode.exceptions import CUSTODEError


async def main():
    base_url = os.environ.get("CUSTODE_BASE_URL", "http://localhost:8000")
    api_key = os.environ.get("CUSTODE_AGENT_API_KEY")

    if not api_key:
        print("ERROR: CUSTODE_AGENT_API_KEY environment variable is required.")
        sys.exit(1)

    async with AsyncCUSTODEClient(base_url=base_url, api_key=api_key) as client:
        try:
            identity = await client.verify_identity()
            print(f"Async Agent connected: {identity.agent_id}")

            # Concurrent queries
            print("\nFetching decisions, approvals, and findings concurrently...")
            decisions_task = client.decisions.list(limit=5)
            approvals_task = client.approvals.list(limit=5)
            findings_task = client.findings.list(limit=5)

            decisions, approvals, findings = await asyncio.gather(
                decisions_task, approvals_task, findings_task
            )

            print(f"Retrieved {len(decisions)} decisions, {len(approvals)} approvals, {len(findings)} findings.")

        except CUSTODEError as e:
            print(f"Async workflow error: {e}")
            sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
