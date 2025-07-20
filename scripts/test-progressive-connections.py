#!/usr/bin/env python3
"""
Test connections progressively to isolate the issue
"""

import requests


def test_connections(nodes, connections, test_name):
    """Test a specific set of nodes and connections"""
    url = "http://192.168.0.152:8007/mcp/execute"

    payload = {
        "tool": "create_gaea2_project",
        "parameters": {
            "project_name": f"test_{test_name}",
            "nodes": nodes,
            "connections": connections,
            "auto_validate": False,
            "save_to_disk": False,
        },
    }

    print(f"\n=== Testing {test_name} ===")
    print(f"Nodes: {len(nodes)}, Connections: {len(connections)}")

    try:
        response = requests.post(url, json=payload, timeout=30)
        if response.status_code == 200:
            result = response.json()

            # Count actual connections
            nodes_data = (
                result.get("project_structure", {})
                .get("Assets", {})
                .get("$values", [{}])[0]
                .get("Terrain", {})
                .get("Nodes", {})
            )

            connections_found = []
            for node_id, node in nodes_data.items():
                if isinstance(node, dict) and "Ports" in node:
                    for port in node.get("Ports", {}).get("$values", []):
                        if "Record" in port:
                            record = port["Record"]
                            connections_found.append(
                                f"{record['From']} -> {record['To']} " f"({record['FromPort']} -> {record['ToPort']})"
                            )

            print(f"Connections created: {len(connections_found)}/{len(connections)}")

            # Check each expected connection
            success = True
            for conn in connections:
                from_node = conn["from_node"]
                to_node = conn["to_node"]
                from_port = conn["from_port"]
                to_port = conn["to_port"]
                conn_str = f"{from_node} -> {to_node} ({from_port} -> {to_port})"

                found = any(f"{from_node} -> {to_node} ({from_port} -> {to_port})" in c for c in connections_found)

                if found:
                    print(f"  ✓ {conn_str}")
                else:
                    print(f"  ✗ {conn_str} MISSING")
                    success = False

            return success

        else:
            print(f"Error: {response.text}")
            return False

    except Exception as e:
        print(f"Failed: {e}")
        return False


def main():
    # Base nodes
    base_nodes = [
        {"id": 258, "type": "SatMap", "position": {"x": 26730, "y": 26268}},
        {"id": 174, "type": "Combine", "position": {"x": 27253, "y": 26008}},
        {"id": 340, "type": "SatMap", "position": {"x": 26730, "y": 25873}},
        {"id": 490, "type": "Combine", "position": {"x": 27150, "y": 26008}},
    ]

    # Test 1: Just the two Combine nodes
    test_connections(
        nodes=[
            {"id": 490, "type": "Combine", "position": {"x": 27150, "y": 26008}},
            {"id": 174, "type": "Combine", "position": {"x": 27253, "y": 26008}},
        ],
        connections=[{"from_node": 490, "to_node": 174, "from_port": "Out", "to_port": "In"}],
        test_name="combine_only",
    )

    # Test 2: Add SatMaps with connections to Combine nodes
    test_connections(
        nodes=base_nodes,
        connections=[
            {"from_node": 258, "to_node": 174, "from_port": "Out", "to_port": "Input2"},
            {"from_node": 340, "to_node": 490, "from_port": "Out", "to_port": "Input2"},
            {"from_node": 490, "to_node": 174, "from_port": "Out", "to_port": "In"},
        ],
        test_name="satmaps_and_combines",
    )

    # Test 3: All problematic nodes
    all_nodes = [
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

    all_connections = [
        {"from_node": 258, "to_node": 174, "from_port": "Out", "to_port": "Input2"},
        {"from_node": 287, "to_node": 483, "from_port": "Out", "to_port": "In"},
        {"from_node": 287, "to_node": 958, "from_port": "Out", "to_port": "In"},
        {"from_node": 340, "to_node": 490, "from_port": "Out", "to_port": "Input2"},
        {"from_node": 490, "to_node": 174, "from_port": "Out", "to_port": "In"},
        {"from_node": 514, "to_node": 949, "from_port": "Out", "to_port": "In"},
        {"from_node": 639, "to_node": 975, "from_port": "Out", "to_port": "In"},
        {"from_node": 949, "to_node": 427, "from_port": "Rivers", "to_port": "In"},
    ]

    test_connections(nodes=all_nodes, connections=all_connections, test_name="all_nodes")


if __name__ == "__main__":
    main()
