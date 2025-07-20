#!/usr/bin/env python3
"""
Ultra-deep field-by-field comparison
"""

import json
from pathlib import Path

# Load files
ref_path = Path("reference projects/mikus files/Level1.terrain")
with open(ref_path, "r") as f:
    ref = json.load(f)

with open("test_still_broken.json", "r") as f:
    broken = json.load(f)


def print_node_details(node, prefix=""):
    """Print all details about a node"""
    print(f"{prefix}Node ID: {node.get('Id', 'NO ID')}")
    print(f"{prefix}Type: {node.get('$type', 'NO TYPE')}")
    print(f"{prefix}Name: {node.get('Name', 'NO NAME')}")

    # List all properties
    excluded = {"$id", "$type", "Id", "Name", "Position", "Ports", "Modifiers", "SnapIns"}
    props = {k: v for k, v in node.items() if k not in excluded}
    if props:
        print(f"{prefix}Properties: {json.dumps(props, indent=2)}")


print("=== DETAILED NODE COMPARISON ===\n")

# Get first actual node from each (skip $id)
ref_nodes = ref["Assets"]["$values"][0]["Terrain"]["Nodes"]
broken_nodes = broken["Assets"]["$values"][0]["Terrain"]["Nodes"]

ref_first_node_key = [k for k in ref_nodes.keys() if k != "$id"][0]
broken_first_node_key = [k for k in broken_nodes.keys() if k != "$id"][0]

print("1. Reference first node:")
print_node_details(ref_nodes[ref_first_node_key], "   ")

print("\n2. Our first node:")
print_node_details(broken_nodes[broken_first_node_key], "   ")

# Check node order
print("\n3. Node ordering:")
ref_node_order = [k for k in ref_nodes.keys() if k != "$id"]
broken_node_order = [k for k in broken_nodes.keys() if k != "$id"]
print(f"   Reference order: {ref_node_order}")
print(f"   Our order: {broken_node_order}")

# Check Export node details
print("\n4. Export node comparison:")
ref_export = None
broken_export = None

for node in ref_nodes.values():
    if isinstance(node, dict) and "Export" in node.get("$type", ""):
        ref_export = node
        break

for node in broken_nodes.values():
    if isinstance(node, dict) and "Export" in node.get("$type", ""):
        broken_export = node
        break

if ref_export and broken_export:
    print("   Reference Export node properties:")
    for k, v in ref_export.items():
        if k not in ["$id", "Ports", "Modifiers", "SnapIns", "Position"]:
            print(f"      {k}: {v}")

    print("\n   Our Export node properties:")
    for k, v in broken_export.items():
        if k not in ["$id", "Ports", "Modifiers", "SnapIns", "Position"]:
            print(f"      {k}: {v}")

# Check SatMap node
print("\n5. SatMap node check:")
has_satmap = any("SatMap" in str(node.get("$type", "")) for node in broken_nodes.values() if isinstance(node, dict))
print(f"   Our file has SatMap: {has_satmap}")
print("   SatMap with no connections might be an issue!")

# Check if there's a Format property in Export
if broken_export:
    if "Format" in broken_export:
        print(f"\n   ⚠️  Export node has Format property: {broken_export['Format']}")
        print("   This might need to be removed!")

# Check Camera structure
print("\n6. Camera structure:")
ref_camera = ref["Assets"]["$values"][0]["State"]["Viewport"]["Camera"]
broken_camera = broken["Assets"]["$values"][0]["State"]["Viewport"]["Camera"]
print(f"   Reference Camera: {ref_camera}")
print(f"   Our Camera: {broken_camera}")

# Check Width/Height placement
print("\n7. Width/Height/Ratio placement:")
ref_terrain = ref["Assets"]["$values"][0]["Terrain"]
broken_terrain = broken["Assets"]["$values"][0]["Terrain"]
print(f"   Reference has Width: {'Width' in ref_terrain}")
print(f"   Reference has Height: {'Height' in ref_terrain}")
print(f"   Our has Width: {'Width' in broken_terrain}")
print(f"   Our has Height: {'Height' in broken_terrain}")

print("\n=== POTENTIAL ISSUES ===")
print("1. Disconnected SatMap node (ID: 427) with no connections")
print("2. Export node might have 'Format' property that shouldn't be there")
print("3. Camera object might be missing properties")
