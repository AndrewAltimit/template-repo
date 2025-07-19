#!/usr/bin/env python3
"""Analyze specific issues in our generated terrain files"""

import json


def find_mask_port_issues():
    """Find all Mask ports and check their types"""

    # Load our generated rivers output
    with open("rivers_output.json", "r") as f:
        data = json.load(f)

    print("=== MASK PORT ANALYSIS ===\n")

    nodes = data["Assets"]["$values"][0]["Terrain"]["Nodes"]

    for node_id, node in nodes.items():
        if not isinstance(node, dict):
            continue

        node_type = node.get("$type", "").split(".")[-2] if "." in node.get("$type", "") else "Unknown"

        if "Ports" in node:
            ports = node["Ports"]["$values"]
            for port in ports:
                if port.get("Name") == "Mask":
                    port_type = port.get("Type")
                    print(f"Node {node_id} ({node_type}):")
                    print(f"  - Mask port type: '{port_type}'")

                    # Check if it's correct
                    if node_type == "Rivers" and port_type != "In":
                        print(f"  ❌ WRONG! Rivers Mask should be 'In', not '{port_type}'")
                    elif node_type in ["Export", "Mountain"] and port_type == "Out":
                        print(f"  ❌ WRONG! {node_type} shouldn't have Mask as 'Out'")


def check_reference_mask_ports():
    """Check how Mask ports are defined in reference files"""

    print("\n=== REFERENCE FILE MASK PORTS ===\n")

    ref_file = "reference projects/mikus files/Level1.terrain"
    try:
        with open(ref_file, "r") as f:
            data = json.loads(f.read())

        nodes = data["Assets"]["$values"][0]["Terrain"]["Nodes"]

        # Check Rivers node specifically
        for node_id, node in nodes.items():
            if isinstance(node, dict) and "Rivers" in node.get("$type", ""):
                print(f"Rivers node {node_id}:")
                if "Ports" in node:
                    for port in node["Ports"]["$values"]:
                        if port.get("Name") == "Mask":
                            print(f"  - Mask port type: '{port.get('Type')}'")
                            print(f"  - Full port: {json.dumps(port, indent=4)}")
                        elif port.get("Name") == "Headwaters":
                            print(f"  - Headwaters port type: '{port.get('Type')}'")

    except Exception as e:
        print(f"Error reading reference: {e}")


def check_property_order():
    """Check the order of properties in nodes"""

    print("\n=== PROPERTY ORDER ANALYSIS ===\n")

    # Reference file
    with open("reference projects/mikus files/Level1.terrain", "r") as f:
        ref_data = json.loads(f.read())

    ref_nodes = ref_data["Assets"]["$values"][0]["Terrain"]["Nodes"]

    # Find first Rivers node
    for node_id, node in ref_nodes.items():
        if isinstance(node, dict) and "Rivers" in node.get("$type", ""):
            print("Reference Rivers node property order:")
            for i, key in enumerate(list(node.keys())[:20]):
                print(f"  {i+1}. {key}")
            break

    print("\nOur Rivers node property order:")
    with open("rivers_output.json", "r") as f:
        our_data = json.load(f)

    our_nodes = our_data["Assets"]["$values"][0]["Terrain"]["Nodes"]
    for node_id, node in our_nodes.items():
        if isinstance(node, dict) and "Rivers" in node.get("$type", ""):
            for i, key in enumerate(list(node.keys())[:20]):
                print(f"  {i+1}. {key}")
            break


def main():
    print("Analyzing Specific Issues in Generated Terrain Files")
    print("=" * 60)

    find_mask_port_issues()
    check_reference_mask_ports()
    check_property_order()

    print("\n" + "=" * 60)
    print("SUMMARY OF ISSUES:")
    print("1. Mask port on Rivers node has wrong type (Out instead of In)")
    print("2. Property order might matter - properties should come AFTER $id and $type")
    print("3. JSON might have syntax errors (missing closing braces)")


if __name__ == "__main__":
    main()
