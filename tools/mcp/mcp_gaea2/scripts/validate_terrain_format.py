#!/usr/bin/env python3
"""Script to validate Gaea2 terrain file format"""
import json
import sys


def _check_automation(asset, issues_list):
    """Check Automation section structure."""
    if "Automation" in asset:
        automation = asset["Automation"]
        if "Variables" not in automation:
            issues_list.append("❌ Automation missing 'Variables'")
        if "BoundProperties" not in automation:
            issues_list.append("❌ Automation missing 'BoundProperties'")
    else:
        issues_list.append("❌ Missing 'Automation' section in asset")


def _check_build_definition(asset, issues_list):
    """Check BuildDefinition required fields."""
    if "BuildDefinition" not in asset:
        issues_list.append("❌ Missing 'BuildDefinition' section")
        return

    build = asset["BuildDefinition"]
    required_build = [
        "Destination",
        "Resolution",
        "BakeResolution",
        "TileResolution",
        "BucketResolution",
        "NumberOfTiles",
        "TotalTiles",
        "EdgeBlending",
        "OrganizeFiles",
        "Regions",
    ]
    for field in required_build:
        if field not in build:
            issues_list.append(f"❌ BuildDefinition missing '{field}'")

    if "Regions" in build and "$values" not in build["Regions"]:
        issues_list.append("❌ BuildDefinition.Regions missing '$values'")


def _check_state(asset, issues_list):
    """Check State structure."""
    if "State" not in asset:
        issues_list.append("❌ Missing 'State' section")
        return

    state = asset["State"]
    required_state = [
        "BakeResolution",
        "PreviewResolution",
        "SelectedNode",
        "NodeBookmarks",
        "Viewport",
    ]
    for field in required_state:
        if field not in state:
            issues_list.append(f"❌ State missing '{field}'")


def _check_terrain(asset, issues_list):
    """Check Terrain structure."""
    if "Terrain" not in asset:
        return

    terrain = asset["Terrain"]

    if "Groups" in terrain:
        if "$values" in terrain["Groups"]:
            issues_list.append("❌ Groups should NOT have '$values'")
    else:
        issues_list.append("❌ Terrain missing 'Groups'")

    if "Notes" in terrain:
        if "$values" in terrain["Notes"]:
            issues_list.append("❌ Notes should NOT have '$values'")
    else:
        issues_list.append("❌ Terrain missing 'Notes'")

    if "Regions" in terrain and "$values" not in terrain["Regions"]:
        issues_list.append("❌ Terrain.Regions missing '$values'")


def _check_metadata(data, issues_list):
    """Check top-level Metadata structure."""
    if "Metadata" not in data:
        issues_list.append("❌ Missing top-level 'Metadata'")
        return

    metadata = data["Metadata"]
    required_meta = [
        "Name",
        "Description",
        "Version",
        "Owner",
        "DateCreated",
        "DateLastBuilt",
        "DateLastSaved",
    ]
    for field in required_meta:
        if field not in metadata:
            issues_list.append(f"❌ Top-level Metadata missing '{field}'")


def check_terrain_format(terrain_file):
    """Check if terrain file matches expected Gaea2 format"""
    with open(terrain_file, "r", encoding="utf-8") as f:
        data = json.load(f)

    issues = []

    if "Assets" not in data or "$values" not in data["Assets"] or not data["Assets"]["$values"]:
        return issues

    asset = data["Assets"]["$values"][0]

    _check_automation(asset, issues)
    _check_build_definition(asset, issues)
    _check_state(asset, issues)
    _check_terrain(asset, issues)
    _check_metadata(data, issues)

    return issues


if __name__ == "__main__":
    filename = sys.argv[1] if len(sys.argv) > 1 else "final_volcano_ocean_verified.terrain"

    print(f"\nValidating {filename} against Gaea2 format requirements:")
    print("=" * 60)

    issues = check_terrain_format(filename)

    if issues:
        print("\nFormat issues found:")
        for issue in issues:
            print(f"  {issue}")
        print(f"\n❌ Total issues: {len(issues)}")
    else:
        print("\n✅ All format checks passed!")
