#!/usr/bin/env python3
"""Deep dive analysis of failing terrain file vs reference files"""

import json
import os


def load_reference_files():
    """Load all reference terrain files for comparison"""
    references = {}
    ref_dirs = ["reference projects/mikus files", "reference projects/Official Gaea Projects"]

    for ref_dir in ref_dirs:
        if os.path.exists(ref_dir):
            for root, dirs, files in os.walk(ref_dir):
                for file in files:
                    if file.endswith(".terrain"):
                        path = os.path.join(root, file)
                        try:
                            with open(path, "r") as f:
                                references[file] = json.load(f)
                        except:
                            pass

    return references


def analyze_property_names(failing_data, references):
    """Check for property name issues"""
    print("=== PROPERTY NAME ANALYSIS ===\n")

    # Find all property names with spaces in our file
    issues = []

    nodes = failing_data["Assets"]["$values"][0]["Terrain"]["Nodes"]
    for node_id, node in nodes.items():
        if isinstance(node, dict):
            node_type = node.get("$type", "").split(".")[-2] if "." in node.get("$type", "") else "Unknown"

            for key, value in node.items():
                if " " in key and key not in ["$id", "$type", "$values"]:
                    issues.append(f"Node {node_id} ({node_type}): '{key}' has spaces")

    if issues:
        print("❌ Properties with spaces found:")
        for issue in issues:
            print(f"   - {issue}")
    else:
        print("✓ No property names with spaces")

    # Check specific problem properties
    print("\n\nChecking specific properties:")

    # Check Erosion2 node
    for node_id, node in nodes.items():
        if isinstance(node, dict) and "Erosion2" in node.get("$type", ""):
            print(f"\nErosion2 node {node_id}:")
            if "Rock Softness" in node:
                print("   ❌ Has 'Rock Softness' (with space)")
            if "RockSoftness" in node:
                print("   ✓ Has 'RockSoftness' (no space)")
            if "Base Level" in node:
                print("   ❌ Has 'Base Level' (with space)")
            if "BaseLevel" in node:
                print("   ✓ Has 'BaseLevel' (no space)")


def analyze_port_types(failing_data, references):
    """Analyze port type differences"""
    print("\n\n=== PORT TYPE ANALYSIS ===\n")

    # Check our file
    nodes = failing_data["Assets"]["$values"][0]["Terrain"]["Nodes"]

    # Look for non-standard port types
    port_types = set()
    for node_id, node in nodes.items():
        if isinstance(node, dict) and "Ports" in node:
            for port in node["Ports"]["$values"]:
                port_types.add(port.get("Type", ""))

    print("Port types in our file:")
    for pt in sorted(port_types):
        print(f"   - '{pt}'")

    # Check reference files for port types
    print("\n\nPort types in reference files:")
    ref_port_types = set()
    for filename, ref_data in references.items():
        try:
            ref_nodes = ref_data["Assets"]["$values"][0]["Terrain"]["Nodes"]
            for node_id, node in ref_nodes.items():
                if isinstance(node, dict) and "Ports" in node:
                    for port in node["Ports"]["$values"]:
                        ref_port_types.add(port.get("Type", ""))
        except:
            pass

    for pt in sorted(ref_port_types):
        print(f"   - '{pt}'")

    # Check specific problematic ports
    print("\n\nProblematic ports:")
    for node_id, node in nodes.items():
        if isinstance(node, dict) and "Ports" in node:
            node_type = node.get("$type", "").split(".")[-2] if "." in node.get("$type", "") else "Unknown"

            for port in node["Ports"]["$values"]:
                port_name = port.get("Name", "")
                port_type = port.get("Type", "")

                # Check Erosion2 Mask port
                if node_type == "Erosion2" and port_name == "Mask" and port_type == "Out":
                    print(f"   ❌ Erosion2 node {node_id}: Mask port is Type='Out' (should be 'In')")

                # Check unusual port types
                if "," in port_type:
                    print(f"   ⚠️  {node_type} node {node_id}: Port '{port_name}' has complex type: '{port_type}'")


def analyze_node_structure(failing_data, references):
    """Analyze overall node structure differences"""
    print("\n\n=== NODE STRUCTURE ANALYSIS ===\n")

    # Pick Level1.terrain as main reference
    level1 = None
    for filename, ref_data in references.items():
        if filename == "Level1.terrain":
            level1 = ref_data
            break

    if not level1:
        print("❌ Could not find Level1.terrain for comparison")
        return

    # Compare Rivers node structure
    print("Rivers node comparison:")

    # Find Rivers in our file
    our_nodes = failing_data["Assets"]["$values"][0]["Terrain"]["Nodes"]
    our_rivers = None
    for node_id, node in our_nodes.items():
        if isinstance(node, dict) and "Rivers" in node.get("$type", ""):
            our_rivers = node
            break

    # Find Rivers in reference
    ref_nodes = level1["Assets"]["$values"][0]["Terrain"]["Nodes"]
    ref_rivers = None
    for node_id, node in ref_nodes.items():
        if isinstance(node, dict) and "Rivers" in node.get("$type", ""):
            ref_rivers = node
            break

    if our_rivers and ref_rivers:
        print("\n  Property comparison:")
        our_props = set(our_rivers.keys())
        ref_props = set(ref_rivers.keys())

        missing = ref_props - our_props
        extra = our_props - ref_props

        if missing:
            print(f"  ❌ Missing properties: {missing}")
        if extra:
            print(f"  ❌ Extra properties: {extra}")

        # Check specific property values
        print("\n  Property value check:")
        for prop in ["RiverValleyWidth", "RenderSurface"]:
            if prop in our_rivers and prop in ref_rivers:
                our_val = our_rivers[prop]
                ref_val = ref_rivers[prop]
                if type(our_val) != type(ref_val):
                    print(f"  ❌ {prop}: type mismatch - ours: {type(our_val).__name__}, ref: {type(ref_val).__name__}")


def check_reference_patterns(references):
    """Look for patterns in reference files"""
    print("\n\n=== REFERENCE FILE PATTERNS ===\n")

    # Check how properties are named in references
    property_patterns = {}

    for filename, ref_data in references.items():
        try:
            nodes = ref_data["Assets"]["$values"][0]["Terrain"]["Nodes"]
            for node_id, node in nodes.items():
                if isinstance(node, dict):
                    node_type = node.get("$type", "").split(".")[-2] if "." in node.get("$type", "") else "Unknown"

                    if node_type not in property_patterns:
                        property_patterns[node_type] = set()

                    for key in node.keys():
                        if key not in [
                            "$id",
                            "$type",
                            "$values",
                            "Id",
                            "Name",
                            "Position",
                            "Ports",
                            "Modifiers",
                            "SnapIns",
                            "NodeSize",
                            "IsMaskable",
                            "SaveDefinition",
                        ]:
                            property_patterns[node_type].add(key)
        except:
            pass

    # Show properties for key node types
    for node_type in ["Erosion2", "Rivers", "Mountain"]:
        if node_type in property_patterns:
            print(f"\n{node_type} properties in references:")
            for prop in sorted(property_patterns[node_type]):
                has_space = " " in prop
                print(f"   {'❌' if has_space else '✓'} {prop}")


def main():
    # Load failing data
    failing_json = r"""{"$id":"1","Assets":{"$id":"2","$values":[{"$id":"3","Terrain":{"$id":"4","Id":"5dde2cbc-7180-4179-ac1c-a9388179a020","Metadata":{"$id":"5","Name":"rivers_fix_test","Description":"Created by Gaea2 MCP Server","Version":"2.0.6.0","DateCreated":"2025-07-20 01:30:11Z","DateLastBuilt":"2025-07-20 01:30:11Z","DateLastSaved":"2025-07-20 01:30:11Z","ModifiedVersion":"2.0.6.0"},"Nodes":{"$id":"6","183":{"$id":"7","$type":"QuadSpinner.Gaea.Nodes.Mountain, Gaea.Nodes","Seed":12345,"Scale":2.0,"Height":0.8,"Octaves":8,"Complexity":0.5,"RidgeWeight":0.5,"Persistence":0.5,"Lacunarity":2.0,"Id":183,"Name":"Base Terrain","Position":{"$id":"8","X":0.0,"Y":0.0},"Ports":{"$id":"9","$values":[{"$id":"11","Name":"In","Type":"PrimaryIn","IsExporting":true,"Parent":{"$ref":"7"}},{"$id":"12","Name":"Out","Type":"PrimaryOut","IsExporting":true,"Parent":{"$ref":"7"}}]},"Modifiers":{"$id":"10","$values":[]},"SnapIns":{"$id":"11","$values":[]}},"668":{"$id":"13","$type":"QuadSpinner.Gaea.Nodes.Erosion2, Gaea.Nodes","Duration":0.15,"Rock Softness":0.5,"Downcutting":0.3,"Base Level":0.1,"Intensity":0.5,"Id":668,"Name":"Initial Erosion","Position":{"$id":"14","X":200.0,"Y":0.0},"Ports":{"$id":"15","$values":[{"$id":"17","Name":"In","Type":"PrimaryIn","IsExporting":true,"Parent":{"$ref":"13"},"Record":{"$id":"18","From":183,"To":668,"FromPort":"Out","ToPort":"In","IsValid":true}},{"$id":"19","Name":"Out","Type":"PrimaryOut","IsExporting":true,"Parent":{"$ref":"13"}},{"$id":"20","Name":"Flow","Type":"Out","IsExporting":true,"Parent":{"$ref":"13"}},{"$id":"21","Name":"Wear","Type":"Out","IsExporting":true,"Parent":{"$ref":"13"}},{"$id":"22","Name":"Deposits","Type":"Out","IsExporting":true,"Parent":{"$ref":"13"}},{"$id":"23","Name":"Mask","Type":"Out","IsExporting":true,"Parent":{"$ref":"13"}}]},"Modifiers":{"$id":"16","$values":[]},"SnapIns":{"$id":"17","$values":[]}},"427":{"$id":"24","$type":"QuadSpinner.Gaea.Nodes.Rivers, Gaea.Nodes","Water":0.3,"Width":0.5,"Depth":0.5,"Downcutting":0.2,"RiverValleyWidth":"zero","Headwaters":100,"RenderSurface":false,"Seed":42,"Id":427,"Name":"River System","NodeSize":"Standard","Position":{"$id":"25","X":400.0,"Y":0.0},"Ports":{"$id":"26","$values":[{"$id":"28","Name":"In","Type":"PrimaryIn","IsExporting":true,"Parent":{"$ref":"24"},"Record":{"$id":"29","From":668,"To":427,"FromPort":"Out","ToPort":"In","IsValid":true}},{"$id":"30","Name":"Out","Type":"PrimaryOut","IsExporting":true,"Parent":{"$ref":"24"}},{"$id":"31","Name":"Rivers","Type":"Out","IsExporting":true,"Parent":{"$ref":"24"}},{"$id":"32","Name":"Depth","Type":"Out","IsExporting":true,"Parent":{"$ref":"24"}},{"$id":"33","Name":"Surface","Type":"Out","IsExporting":true,"Parent":{"$ref":"24"}},{"$id":"34","Name":"Direction","Type":"Out","IsExporting":true,"Parent":{"$ref":"24"}},{"$id":"35","Name":"Headwaters","Type":"In","IsExporting":true,"Parent":{"$ref":"24"}},{"$id":"36","Name":"Mask","Type":"In","IsExporting":true,"Parent":{"$ref":"24"}}]},"IsMaskable":true,"Modifiers":{"$id":"27","$values":[]},"SnapIns":{"$id":"28","$values":[]}},"281":{"$id":"37","$type":"QuadSpinner.Gaea.Nodes.SatMap, Gaea.Nodes","Id":281,"Name":"Terrain Colors","NodeSize":"Standard","Position":{"$id":"38","X":600.0,"Y":0.0},"Ports":{"$id":"39","$values":[{"$id":"41","Name":"In","Type":"PrimaryIn, Required","IsExporting":true,"Parent":{"$ref":"37"},"Record":{"$id":"42","From":427,"To":281,"FromPort":"Out","ToPort":"In","IsValid":true}},{"$id":"43","Name":"Out","Type":"PrimaryOut","IsExporting":true,"Parent":{"$ref":"37"}}]},"Modifiers":{"$id":"40","$values":[]},"SnapIns":{"$id":"41","$values":[]}},"294":{"$id":"44","$type":"QuadSpinner.Gaea.Nodes.Export, Gaea.Nodes","Id":294,"Name":"Height Export","NodeSize":"Standard","Position":{"$id":"45","X":600.0,"Y":200.0},"SaveDefinition":{"$id":"46","Node":294,"Filename":"rivers_test_height","Format":"EXR","IsEnabled":true},"Ports":{"$id":"47","$values":[{"$id":"49","Name":"In","Type":"PrimaryIn, Required","IsExporting":true,"Parent":{"$ref":"44"},"Record":{"$id":"50","From":427,"To":294,"FromPort":"Out","ToPort":"In","IsValid":true}},{"$id":"51","Name":"Out","Type":"PrimaryOut","IsExporting":true,"Parent":{"$ref":"44"}}]},"Modifiers":{"$id":"48","$values":[]},"SnapIns":{"$id":"49","$values":[]}},"949":{"$id":"52","$type":"QuadSpinner.Gaea.Nodes.Export, Gaea.Nodes","Id":949,"Name":"Rivers Export","NodeSize":"Standard","Position":{"$id":"53","X":800.0,"Y":100.0},"SaveDefinition":{"$id":"54","Node":949,"Filename":"rivers_test_rivers","Format":"PNG","IsEnabled":true},"Ports":{"$id":"55","$values":[{"$id":"57","Name":"In","Type":"PrimaryIn, Required","IsExporting":true,"Parent":{"$ref":"52"},"Record":{"$id":"58","From":427,"To":949,"FromPort":"Rivers","ToPort":"In","IsValid":true}},{"$id":"59","Name":"Out","Type":"PrimaryOut","IsExporting":true,"Parent":{"$ref":"52"}}]},"Modifiers":{"$id":"56","$values":[]},"SnapIns":{"$id":"57","$values":[]}}},"Groups":{"$id":"60"},"Notes":{"$id":"61"},"GraphTabs":{"$id":"62","$values":[{"$id":"63","Name":"Graph 1","Color":"Brass","ZoomFactor":0.5338687202362516,"ViewportLocation":{"$id":"64","X":25531.445,"Y":25791.812}}]},"Width":5000.0,"Height":2500.0,"Ratio":0.5},"Automation":{"$id":"65","Bindings":{"$id":"66","$values":[]},"Variables":{"$id":"67"},"BoundProperties":{"$id":"68","$values":[]}},"BuildDefinition":{"$id":"69","Destination":"<Builds>\\[Filename]\\[+++]","Resolution":2048,"BakeResolution":2048,"TileResolution":1024,"BucketResolution":2048,"BucketCount":1,"WorldResolution":2048,"NumberOfTiles":1,"TotalTiles":1,"BucketSizeWithMargin":3072,"EdgeBlending":0.25,"EdgeSize":512,"TileZeroIndex":true,"TilePattern":"","OrganizeFiles":"NodeSubFolder","PostBuildScript":"","Regions":{"$id":"70","$values":[]}},"State":{"$id":"71","BakeResolution":2048,"PreviewResolution":512,"SelectedNode":183,"LockedNode":null,"NodeBookmarks":{"$id":"72","$values":[]},"Viewport":{"$id":"73","RenderMode":"Realistic","SunAltitude":33.0,"SunAzimuth":45.0,"SunIntensity":1.0,"AmbientOcclusion":true,"Shadows":true,"AirDensity":1.0,"AmbientIntensity":1.0,"Exposure":1.0,"FogDensity":0.2,"GroundBrightness":0.8,"Haze":1.0,"Ozone":1.0,"Camera":{"$id":"74"}}}}]},"Id":"5dde2cbc","Branch":1,"Metadata":{"$id":"75","Name":"rivers_fix_test","Description":"Created by Gaea2 MCP Server","Version":"2.0.6.0","Owner":"","DateCreated":"2025-07-20 01:30:11Z","DateLastBuilt":"2025-07-20 01:30:11Z","DateLastSaved":"2025-07-20 01:30:11Z"}}"""

    with open("failing_terrain.json", "w") as f:
        f.write(failing_json)

    with open("failing_terrain.json", "r") as f:
        failing_data = json.load(f)

    # Load reference files
    references = load_reference_files()
    print(f"Loaded {len(references)} reference files for comparison\n")

    # Run analyses
    analyze_property_names(failing_data, references)
    analyze_port_types(failing_data, references)
    analyze_node_structure(failing_data, references)
    check_reference_patterns(references)

    print("\n" + "=" * 60)
    print("DEEP DIVE COMPLETE")


if __name__ == "__main__":
    main()
