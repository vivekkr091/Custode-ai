"""Example 7: Model Context Protocol (MCP) tool discovery and invocation."""

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

            # 1. Discover registered MCP servers
            servers = client.mcp.list_servers()
            print(f"Registered MCP Servers ({len(servers)}):")
            for s in servers:
                print(f"  - [{s.trust_level}] {s.name} ({s.endpoint}) - Status: {s.status}")

            # 2. List tools
            tools = client.mcp.list_tools()
            print(f"\nDiscovered MCP Tools ({len(tools)}):")
            for t in tools:
                print(f"  - {t.name} (Risk: {t.risk_level}) - Schema Drift: {t.schema_changed}")

            # 3. Call tool if any exist
            if len(tools) > 0:
                target_tool = tools[0]
                print(f"\nInvoking MCP Tool: {target_tool.name}...")
                call_res = client.mcp.call_tool(
                    tool_id=target_tool.id,
                    arguments={"query": "test"},
                )
                print(f"  Decision: {call_res.decision.upper()}")
                print(f"  Status:   {call_res.status}")
                print(f"  Result:   {call_res.result}")

        except CUSTODEError as e:
            print(f"MCP error: {e}")
            sys.exit(1)


if __name__ == "__main__":
    main()
