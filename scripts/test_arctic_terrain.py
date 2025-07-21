#!/usr/bin/env python3
"""Test the arctic terrain template to verify Combine node connections."""

import asyncio
import json

import aiohttp


async def test_arctic_terrain():
    """Create an arctic terrain project and check the connections."""
    url = "http://192.168.0.152:8007"

    print("Creating arctic terrain project...")
    async with aiohttp.ClientSession() as session:
        async with session.post(
            f"{url}/mcp/execute",
            json={
                "tool": "create_gaea2_from_template",
                "parameters": {"template_name": "arctic_terrain", "project_name": "test_arctic_fixed"},
            },
            timeout=aiohttp.ClientTimeout(total=30),
        ) as response:
            result = await response.json()

    if result.get("error"):
        print(f"ERROR: {result['error']}")
        return

    print("✓ Project created successfully!")
    print(f"  Path: {result.get('project_path')}")
    print(f"  Nodes: {result.get('node_count')}")
    print(f"  Connections: {result.get('connection_count')}")

    # Check the Combine node connections in the project structure
    if "project_structure" in result:
        nodes = result["project_structure"]["Assets"]["$values"][0]["Terrain"]["Nodes"]

        # Find the Combine node (should be node 102)
        combine_node = None
        for node_id, node_data in nodes.items():
            if isinstance(node_data, dict) and "Combine" in node_data.get("$type", ""):
                combine_node = node_data
                print(f"\n✓ Found Combine node: {node_data['Name']} (ID: {node_id})")
                break

        if combine_node and "Ports" in combine_node:
            ports = combine_node["Ports"]["$values"]

            print("  Port connections:")
            connected_ports = {}

            for port in ports:
                port_name = port["Name"]
                if "Record" in port:
                    record = port["Record"]
                    connected_ports[port_name] = record
                    from_node = record["From"]
                    to_node = record["To"]
                    from_port = record["FromPort"]
                    to_port = record["ToPort"]
                    print(f"    - {port_name}: Node {from_node} ({from_port}) → Node {to_node} ({to_port})")

            # Verify both inputs are connected
            if "In" in connected_ports and "Input2" in connected_ports:
                print("\n✅ SUCCESS: Both Combine inputs are properly connected!")
                print(f"   - Primary input (In): from node {connected_ports['In']['From']}")
                print(f"   - Secondary input (Input2): from node {connected_ports['Input2']['From']}")
            else:
                print(f"\n❌ ERROR: Missing connections. Connected ports: {list(connected_ports.keys())}")
                print("   Expected: ['In', 'Input2']")

    # Save the project structure for inspection
    with open("test_arctic_output.json", "w") as f:
        json.dump(result.get("project_structure", {}), f, indent=2)
    print("\nProject structure saved to test_arctic_output.json")


if __name__ == "__main__":
    asyncio.run(test_arctic_terrain())
