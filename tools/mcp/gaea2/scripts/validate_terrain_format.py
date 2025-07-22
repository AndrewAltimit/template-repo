#!/usr/bin/env python3
import json
import sys


def check_terrain_format(filename):
    """Check if terrain file matches expected Gaea2 format"""
    with open(filename, "r") as f:
        data = json.load(f)

    issues = []

    # Check critical missing fields based on test_terrain_format.py

    # 1. Check Automation section
    if "Assets" in data and "$values" in data["Assets"] and data["Assets"]["$values"]:
        asset = data["Assets"]["$values"][0]

        # Check Automation structure
        if "Automation" in asset:
            automation = asset["Automation"]
            if "Variables" not in automation:
                issues.append("❌ Automation missing 'Variables'")
            if "BoundProperties" not in automation:
                issues.append("❌ Automation missing 'BoundProperties'")
        else:
            issues.append("❌ Missing 'Automation' section in asset")

        # Check BuildDefinition required fields
        if "BuildDefinition" in asset:
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
                    issues.append(f"❌ BuildDefinition missing '{field}'")

            # Check Regions format
            if "Regions" in build:
                if "$values" not in build["Regions"]:
                    issues.append("❌ BuildDefinition.Regions missing '$values'")
        else:
            issues.append("❌ Missing 'BuildDefinition' section")

        # Check State structure
        if "State" in asset:
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
                    issues.append(f"❌ State missing '{field}'")
        else:
            issues.append("❌ Missing 'State' section")

        # Check Terrain structure
        if "Terrain" in asset:
            terrain = asset["Terrain"]

            # Check Groups and Notes format (should NOT have $values)
            if "Groups" in terrain:
                if "$values" in terrain["Groups"]:
                    issues.append("❌ Groups should NOT have '$values'")
            else:
                issues.append("❌ Terrain missing 'Groups'")

            if "Notes" in terrain:
                if "$values" in terrain["Notes"]:
                    issues.append("❌ Notes should NOT have '$values'")
            else:
                issues.append("❌ Terrain missing 'Notes'")

            # Check Regions if exists
            if "Regions" in terrain:
                if "$values" not in terrain["Regions"]:
                    issues.append("❌ Terrain.Regions missing '$values'")

        # Check top-level Metadata structure
        if "Metadata" in data:
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
                    issues.append(f"❌ Top-level Metadata missing '{field}'")
        else:
            issues.append("❌ Missing top-level 'Metadata'")

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
