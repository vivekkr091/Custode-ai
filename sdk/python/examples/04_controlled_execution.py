"""Example 4: Request controlled execution under CUSTODE guardrails."""

import os
import sys
from custode import CUSTODEClient
from custode.exceptions import CUSTODEError


def main():
    base_url = os.environ.get("CUSTODE_BASE_URL", "http://localhost:8000")
    api_key = os.environ.get("CUSTODE_AGENT_API_KEY")
    tool_id = os.environ.get("CUSTODE_TOOL_ID", "00000000-0000-0000-0000-000000000001")
    operation_id = os.environ.get("CUSTODE_OPERATION_ID", "00000000-0000-0000-0000-000000000002")

    if not api_key:
        print("ERROR: CUSTODE_AGENT_API_KEY environment variable is required.")
        sys.exit(1)

    with CUSTODEClient(base_url=base_url, api_key=api_key) as client:
        try:
            client.verify_identity()

            # 1. Register Action
            action = client.runtime_actions.create(
                tool_id=tool_id,
                operation_id=operation_id,
                parameters={"target": "read_status"},
            )
            print(f"Action registered: {action.id}")

            # 2. Evaluate Decision
            decision = client.runtime_actions.decide(action.id)
            print(f"Authorization decision: {decision.decision.upper()}")

            # 3. Controlled Execution (Only permitted if decision == ALLOW or approved)
            if decision.is_allowed:
                print("\nDispatching to CUSTODE controlled execution guardrails...")
                execution = client.runtime_actions.execute(action.id)
                print(f"Execution ID:     {execution.id}")
                print(f"Execution Status: {execution.status}")
                print(f"Result Data:      {execution.result}")
            elif decision.requires_approval:
                print("\nExecution blocked pending human review.")
                print("Visit the CUSTODE Web Console to review and approve this action.")
            else:
                print(f"\nExecution blocked by security policy: {decision.reason}")

        except CUSTODEError as e:
            print(f"Workflow error: {e}")
            sys.exit(1)


if __name__ == "__main__":
    main()
