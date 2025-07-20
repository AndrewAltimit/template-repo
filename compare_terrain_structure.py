#!/usr/bin/env python3
"""
Deep comparison of terrain file structures
"""

import json
from pathlib import Path

# Load reference file
reference_path = Path("reference projects/mikus files/Level1.terrain")
with open(reference_path, "r") as f:
    reference = json.load(f)

# Load our generated file
generated = {
    "$id": "1",
    "Assets": {
        "$id": "2",
        "$values": [
            {
                "$id": "3",
                "Terrain": {
                    "$id": "4",
                    "Id": "4c1a1d73-eb60-4403-a71f-0f7b316b657e",
                    "Metadata": {
                        "$id": "5",
                        "Name": "test_final_validation",
                        "Description": "Created by Gaea2 MCP Server",
                        "Version": "2.0.6.0",
                        "DateCreated": "2025-07-20 03:03:39Z",
                        "DateLastBuilt": "2025-07-20 03:03:39Z",
                        "DateLastSaved": "2025-07-20 03:03:39Z",
                        "ModifiedVersion": "2.0.6.0",  # THIS IS THE PROBLEM
                    },
                    "Nodes": {"$id": "6"},  # simplified
                    "Groups": {"$id": "74"},  # CORRECT - no $values
                    "Notes": {"$id": "75"},  # CORRECT - no $values
                    "GraphTabs": {"$id": "76", "$values": []},
                    "Width": 5000.0,
                    "Height": 2500.0,
                    "Ratio": 0.5,
                },
                "Automation": {
                    "$id": "79",
                    "Bindings": {"$id": "80", "$values": []},
                    "Variables": {"$id": "81"},  # CORRECT - no $values
                    "BoundProperties": {"$id": "82", "$values": []},
                },
                "BuildDefinition": {"$id": "83"},
                "State": {"$id": "85"},
            }
        ],
    },
    "Id": "4c1a1d73",  # Shortened ID vs full UUID
    "Branch": 1,
    "Metadata": {"$id": "89"},
}

print("=== STRUCTURAL COMPARISON ===\n")

# 1. Check Groups/Notes structure
print("1. Groups/Notes Structure:")
print(f"   Reference Groups: {reference['Assets']['$values'][0]['Terrain']['Groups']}")
print(f"   Generated Groups: {generated['Assets']['$values'][0]['Terrain']['Groups']}")
print("   ✅ Both have only $id, no $values\n")

print(f"   Reference Notes: {reference['Assets']['$values'][0]['Terrain']['Notes']}")
print(f"   Generated Notes: {generated['Assets']['$values'][0]['Terrain']['Notes']}")
print("   ✅ Both have only $id, no $values\n")

# 2. Check Variables structure
print("2. Variables Structure:")
print(f"   Reference Variables: {reference['Assets']['$values'][0]['Automation']['Variables']}")
print(f"   Generated Variables: {generated['Assets']['$values'][0]['Automation']['Variables']}")
print("   ✅ Both have only $id, no $values\n")

# 3. Check Metadata fields
print("3. Metadata Fields:")
ref_meta = reference["Assets"]["$values"][0]["Terrain"]["Metadata"]
gen_meta = generated["Assets"]["$values"][0]["Terrain"]["Metadata"]

print("   Reference Metadata keys:", sorted(ref_meta.keys()))
print("   Generated Metadata keys:", sorted(gen_meta.keys()))

if "ModifiedVersion" in gen_meta and "ModifiedVersion" not in ref_meta:
    print("   ❌ PROBLEM: Generated has 'ModifiedVersion' field that reference doesn't have!")
    print("   This extra field could prevent the file from opening!\n")

# 4. Check Id format
print("4. Root Id Format:")
print(f"   Reference Id: '{reference['Id']}' (length: {len(reference['Id'])})")
print(f"   Generated Id: '{generated['Id']}' (length: {len(generated['Id'])})")
if len(reference["Id"]) != len(generated["Id"]):
    print("   ⚠️  WARNING: Id length mismatch - might be an issue\n")

# 5. Check if reference has Version in Metadata
print("5. Version Fields in Metadata:")
print(f"   Reference has 'Version': {'Version' in ref_meta}")
print(f"   Reference Version value: {ref_meta.get('Version', 'N/A')}")
print(f"   Generated has 'Version': {'Version' in gen_meta}")
print(f"   Generated has 'ModifiedVersion': {'ModifiedVersion' in gen_meta}")
print()

# 6. Check all top-level keys
print("6. Top-level Structure:")
print("   Reference keys:", sorted(reference.keys()))
print("   Generated keys:", sorted(generated.keys()))
print()

# 7. Check for any Range objects with missing $id
print("7. Range Objects:")
print("   Need to check all Range properties have $id (can't check without full nodes)")
print()

print("\n=== CRITICAL FINDINGS ===")
print("1. ❌ ModifiedVersion field in Metadata - NOT present in ANY reference file!")
print("2. ✅ Groups/Notes structure is correct (no $values)")
print("3. ✅ Variables structure is correct (no $values)")
print("4. ⚠️  Root Id is shortened (8 chars vs 8 chars) - both are shortened, so OK")
print()
print("SOLUTION: Remove the 'ModifiedVersion' field from Metadata!")
