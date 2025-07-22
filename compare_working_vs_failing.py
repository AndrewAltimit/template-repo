#!/usr/bin/env python3
"""Compare the working template vs failing regression test"""

import json

# Load both files
with open("test_fixed_template.json", "r") as f:
    working = json.load(f)

with open("test_fixed_regression.json", "r") as f:
    failing = json.load(f)

print("=== COMPARING WORKING vs FAILING FILES ===\n")

# Extract nodes
working_nodes = working["Assets"]["$values"][0]["Terrain"]["Nodes"]
failing_nodes = failing["Assets"]["$values"][0]["Terrain"]["Nodes"]

# Compare each node type
for node_id in ["100", "101", "102", "103", "104"]:
    if node_id in working_nodes and node_id in failing_nodes:
        w_node = working_nodes[node_id]
        f_node = failing_nodes[node_id]

        print(f"\nNode {node_id} ({w_node.get('Name')}):")

        # Get all properties (excluding system fields)
        system_fields = {
            "$id",
            "$type",
            "Id",
            "Name",
            "Position",
            "Ports",
            "Modifiers",
            "NodeSize",
            "IsMaskable",
            "SaveDefinition",
        }

        w_props = {k: v for k, v in w_node.items() if k not in system_fields}
        f_props = {k: v for k, v in f_node.items() if k not in system_fields}

        # Compare properties
        all_props = set(w_props.keys()) | set(f_props.keys())

        for prop in sorted(all_props):
            w_val = w_props.get(prop, "MISSING")
            f_val = f_props.get(prop, "MISSING")

            if w_val != f_val:
                print(f"  {prop}: working={w_val}, failing={f_val}")

        # Special check for SaveDefinition
        if "SaveDefinition" in w_node or "SaveDefinition" in f_node:
            w_save = w_node.get("SaveDefinition", {})
            f_save = f_node.get("SaveDefinition", {})

            if w_save.get("Format") != f_save.get("Format"):
                print(f"  SaveDefinition.Format: working={w_save.get('Format')}, failing={f_save.get('Format')}")

# Check specific issues
print("\n=== KEY DIFFERENCES ===")

# 1. Erosion2 Duration
erosion_w = working_nodes.get("101", {})
erosion_f = failing_nodes.get("101", {})

print(f"\n1. Erosion2 Duration:")
print(f"   Working: {erosion_w.get('Duration', 'MISSING')}")
print(f"   Failing: {erosion_f.get('Duration', 'MISSING')}")

# 2. Export SaveDefinition Format
export_w = working_nodes.get("104", {})
export_f = failing_nodes.get("104", {})

print(f"\n2. Export SaveDefinition.Format:")
print(f"   Working: {export_w.get('SaveDefinition', {}).get('Format')}")
print(f"   Failing: {export_f.get('SaveDefinition', {}).get('Format')}")

# 3. Check if Export has any properties
print(f"\n3. Export node properties:")
export_props_w = {
    k: v
    for k, v in export_w.items()
    if k
    not in {
        "$id",
        "$type",
        "Id",
        "Name",
        "Position",
        "Ports",
        "Modifiers",
        "NodeSize",
        "SaveDefinition",
    }
}
export_props_f = {
    k: v
    for k, v in export_f.items()
    if k
    not in {
        "$id",
        "$type",
        "Id",
        "Name",
        "Position",
        "Ports",
        "Modifiers",
        "NodeSize",
        "SaveDefinition",
    }
}

print(f"   Working Export props: {export_props_w}")
print(f"   Failing Export props: {export_props_f}")

# 4. Check all Erosion2 properties
print(f"\n4. All Erosion2 properties:")
erosion_props_w = {
    k: v for k, v in erosion_w.items() if k not in {"$id", "$type", "Id", "Name", "Position", "Ports", "Modifiers"}
}
erosion_props_f = {
    k: v for k, v in erosion_f.items() if k not in {"$id", "$type", "Id", "Name", "Position", "Ports", "Modifiers"}
}

print("   Working Erosion2:")
for k, v in sorted(erosion_props_w.items()):
    print(f"     {k}: {v}")

print("   Failing Erosion2:")
for k, v in sorted(erosion_props_f.items()):
    print(f"     {k}: {v}")
