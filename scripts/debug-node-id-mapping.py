#!/usr/bin/env python3
"""
Debug the node ID mapping issue in detail
"""

import json

import requests


def main():
    # Test with the exact nodes that are failing
    nodes = [
        {"id": 258, "type": "SatMap", "position": {"x": 26730, "y": 26268}},
        {"id": 174, "type": "Combine", "position": {"x": 27253, "y": 26008}},
        {"id": 287, "type": "Sea", "position": {"x": 26090, "y": 25997}},
        {"id": 483, "type": "TextureBase", "position": {"x": 26398, "y": 25987}},
        {"id": 958, "type": "Height", "position": {"x": 26730, "y": 26374}},
        {"id": 340, "type": "SatMap", "position": {"x": 26730, "y": 25873}},
        {"id": 490, "type": "Combine", "position": {"x": 27150, "y": 26008}},
        {"id": 514, "type": "Erosion2", "position": {"x": 25584, "y": 25997}},
        {"id": 949, "type": "Rivers", "position": {"x": 25814, "y": 26000}},
        {"id": 639, "type": "Stratify", "position": {"x": 25087, "y": 25988}},
        {"id": 975, "type": "Crumble", "position": {"x": 25354, "y": 25993}},
        {"id": 427, "type": "Adjust", "position": {"x": 26481, "y": 26068}},
    ]

    # All the missing connections
    connections = [
        {"from_node": 258, "to_node": 174, "from_port": "Out", "to_port": "Input2"},
        {"from_node": 287, "to_node": 483, "from_port": "Out", "to_port": "In"},
        {"from_node": 287, "to_node": 958, "from_port": "Out", "to_port": "In"},
        {"from_node": 340, "to_node": 490, "from_port": "Out", "to_port": "Input2"},
        {"from_node": 490, "to_node": 174, "from_port": "Out", "to_port": "In"},
        {"from_node": 514, "to_node": 949, "from_port": "Out", "to_port": "In"},
        {"from_node": 639, "to_node": 975, "from_port": "Out", "to_port": "In"},
        {"from_node": 949, "to_node": 427, "from_port": "Rivers", "to_port": "In"},
    ]

    url = "http://192.168.0.152:8007/mcp/execute"

    payload = {
        "tool": "create_gaea2_project",
        "parameters": {
            "project_name": "debug_missing_connections",
            "nodes": nodes,
            "connections": connections,
            "auto_validate": False,
        },
    }

    print("Testing with all the problematic nodes and connections...")
    print(f"Nodes: {len(nodes)}")
    print(f"Connections to create: {len(connections)}")

    try:
        response = requests.post(url, json=payload, timeout=30)
        if response.status_code == 200:
            result = response.json()

            # Extract connections from response
            connections_found = []
            nodes_data = (
                result.get("project_structure", {})
                .get("Assets", {})
                .get("$values", [{}])[0]
                .get("Terrain", {})
                .get("Nodes", {})
            )

            for node_id, node in nodes_data.items():
                if isinstance(node, dict):
                    ports = node.get("Ports", {}).get("$values", [])
                    for port in ports:
                        if "Record" in port:
                            record = port["Record"]
                            connections_found.append(
                                {
                                    "from": record.get("From"),
                                    "to": record.get("To"),
                                    "from_port": record.get("FromPort"),
                                    "to_port": record.get("ToPort"),
                                }
                            )

            print(f"\nConnections created: {len(connections_found)}")

            # Check each expected connection
            print("\nChecking each connection:")
            for conn in connections:
                from_node = conn["from_node"]
                to_node = conn["to_node"]
                from_port = conn["from_port"]
                to_port = conn["to_port"]

                found = any(
                    c["from"] == from_node and c["to"] == to_node and c["from_port"] == from_port and c["to_port"] == to_port
                    for c in connections_found
                )

                status = "✓ CREATED" if found else "✗ MISSING"
                print(f"  {from_node} -> {to_node} ({from_port} -> {to_port}): {status}")

            # Save for inspection
            with open("/tmp/debug_connections.json", "w") as f:
                json.dump(result, f, indent=2)
            print("\nFull response saved to /tmp/debug_connections.json")

        else:
            print(f"Error: {response.text}")

    except Exception as e:
        print(f"Failed: {e}")


if __name__ == "__main__":
    main()
