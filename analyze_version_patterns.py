#!/usr/bin/env python3
"""
Analyze Version and ModifiedVersion patterns
"""

import json
from pathlib import Path

# Find all terrain files
terrain_files = list(Path("reference projects").rglob("*.terrain"))

print(f"Analyzing Version patterns in {len(terrain_files)} files...\n")

# Categories
empty_version_no_modified = []
empty_version_with_modified = []
has_version_no_modified = []
has_version_with_modified = []

for terrain_file in terrain_files:
    try:
        with open(terrain_file, "r") as f:
            data = json.load(f)

        terrain_meta = data["Assets"]["$values"][0]["Terrain"]["Metadata"]
        version = terrain_meta.get("Version", "")
        has_modified = "ModifiedVersion" in terrain_meta

        if version == "":
            if has_modified:
                empty_version_with_modified.append((terrain_file, terrain_meta.get("ModifiedVersion")))
            else:
                empty_version_no_modified.append(terrain_file)
        else:
            if has_modified:
                has_version_with_modified.append((terrain_file, version, terrain_meta.get("ModifiedVersion")))
            else:
                has_version_no_modified.append((terrain_file, version))

    except Exception as e:
        print(f"Error reading {terrain_file}: {e}")

print("=== PATTERN ANALYSIS ===\n")
print(f"1. Empty Version, NO ModifiedVersion: {len(empty_version_no_modified)} files")
if empty_version_no_modified:
    for f in empty_version_no_modified[:5]:
        print(f"   - {f.name}")
    if len(empty_version_no_modified) > 5:
        print(f"   ... and {len(empty_version_no_modified) - 5} more")

print(f"\n2. Empty Version, HAS ModifiedVersion: {len(empty_version_with_modified)} files")
if empty_version_with_modified:
    for f, mv in empty_version_with_modified[:5]:
        print(f"   - {f.name} (ModifiedVersion: {mv})")

print(f"\n3. Has Version, NO ModifiedVersion: {len(has_version_no_modified)} files")
if has_version_no_modified:
    for f, v in has_version_no_modified[:5]:
        print(f"   - {f.name} (Version: {v})")

print(f"\n4. Has Version, HAS ModifiedVersion: {len(has_version_with_modified)} files")
if has_version_with_modified:
    for f, v, mv in has_version_with_modified[:5]:
        print(f"   - {f.name} (Version: {v}, ModifiedVersion: {mv})")

print("\n=== KEY FINDING ===")
print("The Level1-10 files that work have:")
print("- Version: '' (empty string)")
print("- NO ModifiedVersion field")
print("\nOur generated files have:")
print("- Version: '2.0.6.0' (non-empty)")
print("- ModifiedVersion: '2.0.6.0' (should be removed)")
print("\nRECOMMENDATION: Set Version to empty string and remove ModifiedVersion!")
