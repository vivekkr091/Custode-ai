"""Example 3: Handling ALLOW, BLOCK, and REQUIRE_APPROVAL decision outcomes."""

import os
import sys
from custode import CUSTODEClient
from custode.exceptions import CUSTODEError


def main():
    base_url = os.environ.get("CUSTODE_BASE_URL", "http://localhost:8000")
    api_key = os.environ.get("CUSTODE_AGENT_API_KEY")

    if not api_key:
        print("ERROR: CUSTODE_AGENT_API_KEY environment variable is required.")
        sys.exit(1)

    with CUSTODEClient(base_url=base_url, api_key=api_key) as client:
        try:
            client.verify_identity()

            # Retrieve recent decisions
            decisions = client.decisions.list(limit=5)
            print(f"Inspecting {len(decisions)} recent decisions:\n")

            for dec in decisions:
                print(f"Decision ID: {dec.id} for Action: {dec.runtime_action_id}")

                if dec.is_allowed:
                    print("  --> STATUS: ALLOWED")
                    print("  --> Safe to proceed with controlled execution.")

                elif dec.is_blocked:
                    print("  --> STATUS: BLOCKED")
                    print(f"  --> Action denied: {dec.reason}")
                    print("  --> DO NOT execute. Security policy prohibits this operation.")

                elif dec.requires_approval:
                    print("  --> STATUS: REQUIRE_APPROVAL")
                    print(f"  --> Action paused: {dec.reason}")
                    print("  --> Human governance reviewer must approve before execution.")

                print("-" * 50)

        except CUSTODEError as e:
            print(f"Error querying decisions: {e}")
            sys.exit(1)


if __name__ == "__main__":
    main()
