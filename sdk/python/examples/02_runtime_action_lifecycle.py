"""Example 2: Register and evaluate an agent RuntimeAction."""

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
            # 1. Verify identity and set organization context
            identity = client.verify_identity()
            print(f"Authenticated as Agent {identity.agent_id} in Org {identity.organization_id}")

            # 2. Register intended action
            print("\n1. Registering RuntimeAction...")
            action = client.runtime_actions.create(
                tool_id=tool_id,
                operation_id=operation_id,
                environment="development",
                action_type="tool_call",
                resource="database/customers",
                parameters={"query": "SELECT id, name FROM customers LIMIT 10"},
            )
            print(f"  Action ID:   {action.id}")
            print(f"  Status:      {action.status}")
            print(f"  Environment: {action.environment}")

            # 3. Arbitrate authorization decision
            print("\n2. Arbitrating Authorization Decision...")
            decision = client.runtime_actions.decide(action.id)
            print(f"  Decision:   {decision.decision.upper()}")
            print(f"  Reason:     {decision.reason}")
            print(f"  Risk Level: {decision.risk_level or 'N/A'}")
            print(f"  Risk Score: {decision.risk_score or 0.0}/100")

        except CUSTODEError as e:
            print(f"Operation failed: {e}")
            sys.exit(1)


if __name__ == "__main__":
    main()
