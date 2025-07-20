#!/usr/bin/env python3
"""
Check all Metadata fields in reference terrain files
"""

import json
from pathlib import Path

# Find all terrain files
terrain_files = list(Path("reference projects").rglob("*.terrain"))

print(f"Checking {len(terrain_files)} terrain files...\n")

# Collect all metadata fields
all_metadata_fields = set()
files_with_modified_version = []

for terrain_file in terrain_files:
    try:
        with open(terrain_file, "r") as f:
            data = json.load(f)

        # Get Terrain Metadata
        terrain_meta = data["Assets"]["$values"][0]["Terrain"]["Metadata"]
        fields = set(terrain_meta.keys())
        all_metadata_fields.update(fields)

        if "ModifiedVersion" in fields:
            files_with_modified_version.append(terrain_file)

    except Exception as e:
        print(f"Error reading {terrain_file}: {e}")

print("=== ALL METADATA FIELDS FOUND ===")
for field in sorted(all_metadata_fields):
    if field == "$id":
        continue
    print(f"  - {field}")

print("\n=== FILES WITH ModifiedVersion ===")
if files_with_modified_version:
    for f in files_with_modified_version:
        print(f"  - {f}")
else:
    print("  NONE! ModifiedVersion should NOT be in Metadata!")

# Check a few files in detail
print("\n=== SAMPLE METADATA STRUCTURES ===")
sample_files = terrain_files[:3]
for terrain_file in sample_files:
    try:
        with open(terrain_file, "r") as f:
            data = json.load(f)
        terrain_meta = data["Assets"]["$values"][0]["Terrain"]["Metadata"]
        print(f"\n{terrain_file.name}:")
        for k, v in terrain_meta.items():
            if k != "$id":
                print(f"  {k}: {repr(v)}")
    except Exception as e:
        print(f"Error: {e}")
