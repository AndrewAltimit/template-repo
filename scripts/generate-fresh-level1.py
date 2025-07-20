#!/usr/bin/env python3
"""
Generate a fresh Level1 terrain with all fixes applied
"""

import json

import requests


def main():
    # Full Level1 terrain nodes and connections
    nodes = [
        {"id": 183, "type": "Volcano", "position": {"x": 24472, "y": 25987}},
        {"id": 668, "type": "MountainSide", "position": {"x": 24472, "y": 26073}},
        {"id": 427, "type": "Adjust", "position": {"x": 26481, "y": 26068}},
        {"id": 281, "type": "Combine", "position": {"x": 24766, "y": 26003}},
        {"id": 294, "type": "Shear", "position": {"x": 24857, "y": 25988}},
        {"id": 949, "type": "Rivers", "position": {"x": 25814, "y": 26000}},
        {"id": 483, "type": "TextureBase", "position": {"x": 26398, "y": 25987}},
        {"id": 800, "type": "SatMap", "position": {"x": 26730, "y": 25991}},
        {"id": 375, "type": "SatMap", "position": {"x": 26730, "y": 26127}},
        {"id": 245, "type": "Combine", "position": {"x": 27028, "y": 26007}},
        {"id": 958, "type": "Height", "position": {"x": 26730, "y": 26374}},
        {"id": 174, "type": "Combine", "position": {"x": 27253, "y": 26008}},
        {"id": 258, "type": "SatMap", "position": {"x": 26730, "y": 26268}},
        {"id": 975, "type": "Crumble", "position": {"x": 25354, "y": 25993}},
        {"id": 639, "type": "Stratify", "position": {"x": 25087, "y": 25988}},
        {"id": 514, "type": "Erosion2", "position": {"x": 25584, "y": 25997}},
        {"id": 287, "type": "Sea", "position": {"x": 26090, "y": 25997}},
        {"id": 490, "type": "Combine", "position": {"x": 27150, "y": 26008}},
        {"id": 340, "type": "SatMap", "position": {"x": 26730, "y": 25873}},
    ]

    connections = [
        {"from_node": 183, "to_node": 281, "from_port": "Out", "to_port": "In"},
        {"from_node": 668, "to_node": 281, "from_port": "Out", "to_port": "Input2"},
        {"from_node": 281, "to_node": 294, "from_port": "Out", "to_port": "In"},
        {"from_node": 294, "to_node": 639, "from_port": "Out", "to_port": "In"},
        {"from_node": 639, "to_node": 975, "from_port": "Out", "to_port": "In"},
        {"from_node": 975, "to_node": 514, "from_port": "Out", "to_port": "In"},
        {"from_node": 514, "to_node": 949, "from_port": "Out", "to_port": "In"},
        {"from_node": 949, "to_node": 287, "from_port": "Out", "to_port": "In"},
        {"from_node": 287, "to_node": 483, "from_port": "Out", "to_port": "In"},
        {"from_node": 483, "to_node": 800, "from_port": "Out", "to_port": "In"},
        {"from_node": 483, "to_node": 375, "from_port": "Out", "to_port": "In"},
        {"from_node": 483, "to_node": 258, "from_port": "Out", "to_port": "In"},
        {"from_node": 483, "to_node": 340, "from_port": "Out", "to_port": "In"},
        {"from_node": 800, "to_node": 245, "from_port": "Out", "to_port": "In"},
        {"from_node": 375, "to_node": 245, "from_port": "Out", "to_port": "Input2"},
        {"from_node": 427, "to_node": 245, "from_port": "Out", "to_port": "Mask"},
        {"from_node": 949, "to_node": 427, "from_port": "Rivers", "to_port": "In"},
        {"from_node": 245, "to_node": 490, "from_port": "Out", "to_port": "In"},
        {"from_node": 340, "to_node": 490, "from_port": "Out", "to_port": "Input2"},
        {"from_node": 287, "to_node": 490, "from_port": "Water", "to_port": "Mask"},
        {"from_node": 490, "to_node": 174, "from_port": "Out", "to_port": "In"},
        {"from_node": 258, "to_node": 174, "from_port": "Out", "to_port": "Input2"},
        {"from_node": 958, "to_node": 174, "from_port": "Out", "to_port": "Mask"},
        {"from_node": 287, "to_node": 958, "from_port": "Out", "to_port": "In"},
    ]

    url = "http://192.168.0.152:8007/mcp/execute"

    payload = {
        "tool": "create_gaea2_project",
        "parameters": {
            "project_name": "level1_fixed",
            "nodes": nodes,
            "connections": connections,
            "auto_validate": False,
        },
    }

    print(f"Creating Level1 terrain with {len(nodes)} nodes and {len(connections)} connections...")

    try:
        response = requests.post(url, json=payload, timeout=30)
        if response.status_code == 200:
            result = response.json()
            if result.get("success"):
                print("✓ Project created successfully!")

                # Save locally
                local_path = "output/gaea2/level1_fixed.terrain"
                if "project_structure" in result:
                    with open(local_path, "w") as f:
                        json.dump(result["project_structure"], f, indent=2)
                    print(f"✓ Saved to: {local_path}")

                # Count connections
                nodes_data = (
                    result.get("project_structure", {})
                    .get("Assets", {})
                    .get("$values", [{}])[0]
                    .get("Terrain", {})
                    .get("Nodes", {})
                )

                connection_count = 0
                for node_id, node in nodes_data.items():
                    if isinstance(node, dict) and "Ports" in node:
                        for port in node.get("Ports", {}).get("$values", []):
                            if "Record" in port:
                                connection_count += 1

                print(f"\n✓ All {connection_count} connections created successfully!")
                return True
            else:
                print(f"✗ Creation failed: {result.get('error')}")
                return False
        else:
            print(f"✗ Request failed with status {response.status_code}")
            return False

    except Exception as e:
        print(f"✗ Error: {e}")
        return False


if __name__ == "__main__":
    main()
