"""Example 1: Connect a Python agent to CUSTODE and verify caller identity."""

import os
import sys
from custode import CUSTODEClient
from custode.exceptions import AuthenticationError, CUSTODEError


def main():
    # Load configuration from environment variables
    base_url = os.environ.get("CUSTODE_BASE_URL", "http://localhost:8000")
    api_key = os.environ.get("CUSTODE_AGENT_API_KEY")

    if not api_key:
        print("ERROR: CUSTODE_AGENT_API_KEY environment variable is required.")
        print("Example: export CUSTODE_AGENT_API_KEY='cst_ag_abcdef1234_...'")
        sys.exit(1)

    print(f"Connecting to CUSTODE Control Plane at {base_url}...")

    # Initialize client
    with CUSTODEClient(base_url=base_url, api_key=api_key) as client:
        try:
            # Verify agent credentials and retrieve authoritative identity
            identity = client.verify_identity()
            print("\nSuccessfully authenticated with CUSTODE Control Plane:")
            print(f"  Organization ID: {identity.organization_id}")
            print(f"  Agent ID:        {identity.agent_id}")
            print(f"  Credential ID:   {identity.credential_id}")

            # Inspect registered agent profile
            agent = client.agents.get(identity.agent_id)
            print(f"\nAgent Profile:")
            print(f"  Name:        {agent.name}")
            print(f"  Slug:        {agent.slug}")
            print(f"  Type:        {agent.agent_type}")
            print(f"  Status:      {agent.status}")
            print(f"  Environment: {agent.environment}")

        except AuthenticationError as e:
            print(f"Authentication failed: {e}")
            sys.exit(1)
        except CUSTODEError as e:
            print(f"CUSTODE API error: {e}")
            sys.exit(1)


if __name__ == "__main__":
    main()
