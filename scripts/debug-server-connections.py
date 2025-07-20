#!/usr/bin/env python3
"""
Debug the server's connection handling by examining the response
"""

import requests


def main():
    # Test with just a few nodes and connections
    url = "http://192.168.0.152:8007/mcp/execute"

    # Create a simple test case with nodes that are failing
    payload = {
        "tool": "create_gaea2_project",
        "parameters": {
            "project_name": "debug_connections",
            "nodes": [
                {"id": 287, "type": "Sea", "position": {"x": 26090, "y": 25997}},
                {"id": 483, "type": "TextureBase", "position": {"x": 26398, "y": 25987}},
                {"id": 949, "type": "Rivers", "position": {"x": 25814, "y": 26000}},
                {"id": 427, "type": "Adjust", "position": {"x": 26481, "y": 26068}},
                {"id": 514, "type": "Erosion2", "position": {"x": 25584, "y": 25997}},
                {"id": 639, "type": "Stratify", "position": {"x": 25087, "y": 25988}},
                {"id": 975, "type": "Crumble", "position": {"x": 25354, "y": 25993}},
                {"id": 958, "type": "Height", "position": {"x": 26730, "y": 26374}},
            ],
            "connections": [
                {"from_node": 287, "to_node": 483, "from_port": "Out", "to_port": "In"},
                {"from_node": 949, "to_node": 427, "from_port": "Rivers", "to_port": "In"},
                {"from_node": 514, "to_node": 949, "from_port": "Out", "to_port": "In"},
                {"from_node": 639, "to_node": 975, "from_port": "Out", "to_port": "In"},
                {"from_node": 287, "to_node": 958, "from_port": "Out", "to_port": "In"},
            ],
            "auto_validate": False,
        },
    }

    print("Testing connection handling with problematic nodes...")
    print(f"Sending {len(payload['parameters']['connections'])} connections:")
    for conn in payload["parameters"]["connections"]:
        print(f"  {conn['from_node']} -> {conn['to_node']} ({conn['from_port']} -> {conn['to_port']})")

    try:
        response = requests.post(url, json=payload, timeout=30)
        if response.status_code == 200:
            result = response.json()

            # Check which nodes have connections
            nodes = (
                result.get("project_structure", {})
                .get("Assets", {})
                .get("$values", [{}])[0]
                .get("Terrain", {})
                .get("Nodes", {})
            )

            print("\nChecking node ports:")
            for node_id in ["287", "483", "949", "427", "514", "639", "975", "958"]:
                if node_id in nodes:
                    node = nodes[node_id]
                    node_type = node.get("$type", "").split(".")[-2]
                    ports = node.get("Ports", {}).get("$values", [])

                    print(f"\nNode {node_id} ({node_type}):")
                    for port in ports:
                        port_name = port.get("Name")
                        port_type = port.get("Type")
                        has_record = "Record" in port
                        print(f"  Port '{port_name}' ({port_type}): {'HAS CONNECTION' if has_record else 'no connection'}")
                        if has_record:
                            record = port["Record"]
                            print(
                                f"    From: {record.get('From')} ({record.get('FromPort')}) -> "
                                f"To: {record.get('To')} ({record.get('ToPort')})"
                            )
                else:
                    print(f"\nNode {node_id} NOT FOUND in response!")

            # Count actual connections
            connections_found = 0
            for node_id, node in nodes.items():
                if isinstance(node, dict):
                    ports = node.get("Ports", {}).get("$values", [])
                    for port in ports:
                        if "Record" in port:
                            connections_found += 1

            print(f"\nTotal connections found in response: {connections_found}")
            print(f"Expected connections: {len(payload['parameters']['connections'])}")

        else:
            print(f"Error: {response.text}")

    except Exception as e:
        print(f"Failed: {e}")


if __name__ == "__main__":
    main()
