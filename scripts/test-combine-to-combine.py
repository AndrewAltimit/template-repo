#!/usr/bin/env python3
"""
Test specifically the connection between two Combine nodes
"""

import requests


def main():
    # Test just the failing connection: 490 -> 174
    nodes = [
        {"id": 490, "type": "Combine", "position": {"x": 27150, "y": 26008}},
        {"id": 174, "type": "Combine", "position": {"x": 27253, "y": 26008}},
    ]

    connections = [{"from_node": 490, "to_node": 174, "from_port": "Out", "to_port": "In"}]

    url = "http://192.168.0.152:8007/mcp/execute"

    payload = {
        "tool": "create_gaea2_project",
        "parameters": {
            "project_name": "test_combine_to_combine",
            "nodes": nodes,
            "connections": connections,
            "auto_validate": False,
        },
    }

    print("Testing Combine -> Combine connection...")
    print("Connection: 490 -> 174 (Out -> In)")

    try:
        response = requests.post(url, json=payload, timeout=30)
        if response.status_code == 200:
            result = response.json()

            # Check the connection
            nodes_data = (
                result.get("project_structure", {})
                .get("Assets", {})
                .get("$values", [{}])[0]
                .get("Terrain", {})
                .get("Nodes", {})
            )

            # Check node 174's In port
            if "174" in nodes_data:
                node_174 = nodes_data["174"]
                ports = node_174.get("Ports", {}).get("$values", [])
                for port in ports:
                    if port.get("Name") == "In":
                        if "Record" in port:
                            record = port["Record"]
                            print(f"\n✓ Connection found on node 174's In port: " f"{record['From']} -> {record['To']}")
                            return True
                        else:
                            print("\n✗ No connection found on node 174's In port")
                            return False

            print("\n✗ Node 174 not found in response")
            return False

        else:
            print(f"Error: {response.text}")
            return False

    except Exception as e:
        print(f"Failed: {e}")
        return False


if __name__ == "__main__":
    main()
