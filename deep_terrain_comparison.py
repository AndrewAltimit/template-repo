#!/usr/bin/env python3
"""
Ultra-deep comparison of terrain files to find ANY differences
"""

import json

# import sys  # Not used
from pathlib import Path

# Load reference file (Level1.terrain which we know works)
reference_path = Path("reference projects/mikus files/Level1.terrain")
with open(reference_path, "r") as f:
    reference = json.load(f)

# Load our broken file
with open("test_broken_metadata_fix.json", "r") as f:
    broken = json.load(f)


def compare_keys(ref_obj, gen_obj, path=""):
    """Recursively compare all keys between objects"""
    differences = []

    # Check for missing keys in generated
    if isinstance(ref_obj, dict) and isinstance(gen_obj, dict):
        ref_keys = set(ref_obj.keys())
        gen_keys = set(gen_obj.keys())

        missing_in_gen = ref_keys - gen_keys
        extra_in_gen = gen_keys - ref_keys

        if missing_in_gen:
            differences.append(f"{path}: Missing keys in generated: {missing_in_gen}")
        if extra_in_gen:
            differences.append(f"{path}: Extra keys in generated: {extra_in_gen}")

        # Recurse into common keys
        for key in ref_keys & gen_keys:
            if isinstance(ref_obj[key], (dict, list)) and isinstance(gen_obj[key], (dict, list)):
                differences.extend(compare_keys(ref_obj[key], gen_obj[key], f"{path}.{key}"))

    return differences


print("=== DEEP STRUCTURE COMPARISON ===\n")

# First, check top-level structure
print("1. Top-level keys:")
print(f"   Reference: {sorted(reference.keys())}")
print(f"   Generated: {sorted(broken.keys())}")
print()

# Check Assets structure
print("2. Assets structure:")
ref_asset = reference["Assets"]["$values"][0]
gen_asset = broken["Assets"]["$values"][0]
print(f"   Reference asset keys: {sorted(ref_asset.keys())}")
print(f"   Generated asset keys: {sorted(gen_asset.keys())}")
print()

# Check Terrain structure in detail
print("3. Terrain structure:")
ref_terrain = ref_asset["Terrain"]
gen_terrain = gen_asset["Terrain"]
print(f"   Reference terrain keys: {sorted(ref_terrain.keys())}")
print(f"   Generated terrain keys: {sorted(gen_terrain.keys())}")
print()

# Check specific node structure
print("4. Node structure comparison:")
# Get first node from each
ref_first_node = list(ref_terrain["Nodes"].values())[1]  # Skip $id
gen_first_node = list(gen_terrain["Nodes"].values())[1]  # Skip $id

print(f"   Reference node type: {ref_first_node.get('$type', 'NO TYPE!')}")
print(f"   Generated node type: {gen_first_node.get('$type', 'NO TYPE!')}")
print(f"   Reference node keys: {sorted(ref_first_node.keys())}")
print(f"   Generated node keys: {sorted(gen_first_node.keys())}")

# Check for missing keys in nodes
ref_node_keys = set(ref_first_node.keys())
gen_node_keys = set(gen_first_node.keys())
missing_node_keys = ref_node_keys - gen_node_keys
extra_node_keys = gen_node_keys - ref_node_keys

if missing_node_keys:
    print(f"   ❌ Missing node keys: {missing_node_keys}")
if extra_node_keys:
    print(f"   ⚠️  Extra node keys: {extra_node_keys}")
print()

# Check Mountain node properties specifically
print("5. Mountain node property comparison:")
ref_mountain = None
gen_mountain = None

for node in ref_terrain["Nodes"].values():
    if isinstance(node, dict) and "Mountain" in node.get("$type", ""):
        ref_mountain = node
        break

for node in gen_terrain["Nodes"].values():
    if isinstance(node, dict) and "Mountain" in node.get("$type", ""):
        gen_mountain = node
        break

if gen_mountain:
    # Check for properties that shouldn't be at root level
    problematic_props = ["Octaves", "Complexity", "RidgeWeight", "Persistence", "Lacunarity"]
    found_at_root = [p for p in problematic_props if p in gen_mountain]
    if found_at_root:
        print(f"   ❌ Properties at root level that might need to be nested: {found_at_root}")

    # Check if Style is an issue
    if "Style" in gen_mountain:
        print(f"   Generated Mountain Style: {gen_mountain['Style']}")

print()

# Check node IDs format
print("6. Node ID format check:")
ref_node_ids = [k for k in ref_terrain["Nodes"].keys() if k != "$id"]
gen_node_ids = [k for k in gen_terrain["Nodes"].keys() if k != "$id"]
print(f"   Reference node IDs: {ref_node_ids[:3]}...")
print(f"   Generated node IDs: {gen_node_ids[:3]}...")
print()

# Check SaveDefinition locations
print("7. SaveDefinition check:")
# Check if SaveDefinitions exists at root
if "SaveDefinitions" in ref_terrain:
    print("   Reference has SaveDefinitions at Terrain root")
else:
    print("   Reference does NOT have SaveDefinitions at Terrain root")

# Check Export nodes for SaveDefinition
for node in gen_terrain["Nodes"].values():
    if isinstance(node, dict) and "Export" in node.get("$type", ""):
        if "SaveDefinition" in node:
            print("   ✅ Export node has embedded SaveDefinition")
        else:
            print("   ❌ Export node missing SaveDefinition!")

print()

# Do deep key comparison
print("8. Deep key comparison:")
differences = compare_keys(reference, broken)
if differences:
    for diff in differences[:10]:  # Show first 10
        print(f"   {diff}")
else:
    print("   No structural differences found")

print("\n=== CRITICAL FINDING ===")
print("Check Mountain node properties - some might need to be nested or removed!")
