#!/usr/bin/env python3
"""
Test a single simple connection to isolate the issue
"""

import json

import requests


def extract_connections(response_data):
    """Extract connections from response"""
    connections = []

    if "project_structure" in response_data:
        nodes = response_data["project_structure"]["Assets"]["$values"][0]["Terrain"]["Nodes"]
    else:
        nodes = response_data.get("Nodes", {})

    for node_id, node in nodes.items():
        if isinstance(node, dict):
            ports = node.get("Ports", {}).get("$values", [])
            for port in ports:
                if "Record" in port:
                    record = port["Record"]
                    connections.append(
                        {
                            "from": record.get("From"),
                            "to": record.get("To"),
                            "from_port": record.get("FromPort"),
                            "to_port": record.get("ToPort"),
                        }
                    )
    return connections


def main():
    url = "http://192.168.0.152:8007/mcp/execute"

    # Test with just Sea -> TextureBase
    payload = {
        "tool": "create_gaea2_project",
        "parameters": {
            "project_name": "simple_test",
            "nodes": [
                {"id": 287, "type": "Sea", "position": {"x": 1000, "y": 1000}},
                {"id": 483, "type": "TextureBase", "position": {"x": 2000, "y": 1000}},
            ],
            "connections": [{"from_node": 287, "to_node": 483, "from_port": "Out", "to_port": "In"}],
            "auto_validate": False,
        },
    }

    print("Testing single connection: 287 -> 483")

    response = requests.post(url, json=payload, timeout=30)
    if response.status_code == 200:
        result = response.json()
        connections = extract_connections(result)

        print(f"\nFound {len(connections)} connections:")
        for conn in connections:
            print(f"  {conn['from']} -> {conn['to']} ({conn['from_port']} -> {conn['to_port']})")

        # Save response for inspection
        with open("/tmp/simple_test_response.json", "w") as f:
            json.dump(result, f, indent=2)
        print("\nFull response saved to /tmp/simple_test_response.json")
    else:
        print(f"Error: {response.text}")


if __name__ == "__main__":
    main()
