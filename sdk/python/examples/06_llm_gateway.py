"""Example 6: Mediated LLM interaction through CUSTODE Security Gateway."""

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

            print("Sending prompt through CUSTODE LLM Security Gateway...")
            response = client.llm.chat(
                messages=[
                    {"role": "system", "content": "You are a helpful customer service agent."},
                    {"role": "user", "content": "Summarize the quarterly SLA report."},
                ],
                provider="mock",
                model="mock-gpt-4",
            )

            print(f"\nInteraction ID:  {response.interaction_id}")
            print(f"Decision:        {response.decision.upper()}")
            print(f"Security Status: {response.security_status}")
            print(f"Latency:         {response.latency_ms} ms")

            if response.is_blocked:
                print("\nPrompt or output blocked by security scanning!")
                print(f"Findings: {response.input_findings or response.output_findings}")
            else:
                print(f"\nAssistant Response:\n{response.content}")

        except CUSTODEError as e:
            print(f"LLM Gateway error: {e}")
            sys.exit(1)


if __name__ == "__main__":
    main()
