#!/usr/bin/env python3
"""Verify all port connections in the complex workflow"""

import json


def analyze_ports():
    """Analyze the port connections in the generated file"""
    with open("complex_output.json", "r") as f:
        data = json.load(f)

    nodes = data["Assets"]["$values"][0]["Terrain"]["Nodes"]

    print("=== PORT ANALYSIS ===\n")

    # Track all connections
    connections = []

    for node_id, node in nodes.items():
        if isinstance(node, str):
            continue

        node_type = node.get("$type", "").split(".")[-2] if "." in node.get("$type", "") else "Unknown"
        node_name = node.get("Name", "Unknown")

        print(f"\n{node_name} (ID: {node_id}, Type: {node_type}):")

        if "Ports" in node and "$values" in node["Ports"]:
            print("  Ports:")
            for port in node["Ports"]["$values"]:
                port_name = port.get("Name")
                port_type = port.get("Type")
                print(f"    - {port_name} ({port_type})")

                # Check for connections
                if "Record" in port:
                    record = port["Record"]
                    from_node = record.get("From")
                    from_port = record.get("FromPort")
                    to_node = record.get("To")
                    to_port = record.get("ToPort")

                    connections.append(
                        {
                            "from": f"{from_node}:{from_port}",
                            "to": f"{to_node}:{to_port}",
                            "description": f"Node {from_node} port {from_port} → Node {to_node} port {to_port}",
                        }
                    )

                    print(f"      ✓ Connected from Node {from_node} port '{from_port}'")

    print("\n\n=== ALL CONNECTIONS ===")
    for i, conn in enumerate(connections, 1):
        print(f"{i}. {conn['description']}")

    # Check specific important connections
    print("\n\n=== VALIDATION ===")

    # Check Rivers export connection
    rivers_export_found = any("294:Rivers" in conn["from"] and "800:" in conn["to"] for conn in connections)
    print(f"✓ Rivers export connection: {'FOUND' if rivers_export_found else 'MISSING'}")

    # Check Erosion2 outputs
    erosion_has_outputs = any("281:" in conn["from"] for conn in connections)
    print(f"✓ Erosion2 has output connections: {'YES' if erosion_has_outputs else 'NO'}")

    # Count ports for complex nodes
    print("\n\n=== PORT COUNTS ===")
    for node_id, node in nodes.items():
        if isinstance(node, str):
            continue

        node_type = node.get("$type", "").split(".")[-2] if "." in node.get("$type", "") else "Unknown"

        if node_type in ["Rivers", "Erosion2", "Combine"]:
            port_count = len(node.get("Ports", {}).get("$values", []))
            expected = {"Rivers": 7, "Erosion2": 6, "Combine": 4}  # In + 6 outputs  # In + 5 outputs  # In, Input2, Mask, Out

            expected_count = expected.get(node_type, 0)
            status = "✓" if port_count == expected_count else "❌"
            print(f"{status} {node_type} node: {port_count} ports (expected {expected_count})")


if __name__ == "__main__":
    analyze_ports()
