#!/usr/bin/env python3
"""Analyze which Snow properties cause the failure"""

import json

print("Analyzing Snow node properties...\n")

# Load the working and failing Snow files
with open("test_snow_minimal.terrain", "r") as f:
    minimal_data = json.load(f)

with open("test_snow_full.terrain", "r") as f:
    full_data = json.load(f)

# Extract Snow nodes
minimal_snow = None
full_snow = None

minimal_nodes = minimal_data["Assets"]["$values"][0]["Terrain"]["Nodes"]
for node_id, node in minimal_nodes.items():
    if node_id != "$id" and "Snow" in str(node.get("$type", "")):
        minimal_snow = node
        break

full_nodes = full_data["Assets"]["$values"][0]["Terrain"]["Nodes"]
for node_id, node in full_nodes.items():
    if node_id != "$id" and "Snow" in str(node.get("$type", "")):
        full_snow = node
        break

print("MINIMAL Snow node (WORKS):")
if minimal_snow:
    props = {
        k: v for k, v in minimal_snow.items() if k not in ["$id", "$type", "Id", "Name", "Position", "Ports", "Modifiers"]
    }
    print(f"  Properties: {props}")
    print(f"  Property count: {len(props)}")

print("\nFULL Snow node (FAILS):")
if full_snow:
    props = {k: v for k, v in full_snow.items() if k not in ["$id", "$type", "Id", "Name", "Position", "Ports", "Modifiers"]}
    print(f"  Properties: {props}")
    print(f"  Property count: {len(props)}")

    print("\n  Individual properties:")
    for k, v in sorted(props.items()):
        print(f"    {k}: {v} (type: {type(v).__name__})")

# Compare with the Snow properties from failing templates
print("\n\nSnow properties from FAILING templates:")
print("\nregression_mountain_range.json:")
print("  Duration: 0.7")
print("  SnowLine: 0.7")
print("  Melt: 0.2")
print("  MeltType: Uniform")
print("  (and 6 more)")

print("\n\nPotential issues:")
print("1. MeltType might need to be a string enum value")
print("2. Boolean properties (RealScale) might have format issues")
print("3. Some properties might have invalid default values")
print("4. Property count (10 properties) might be too many")
