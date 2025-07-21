#!/usr/bin/env python3
"""Deep analysis of working vs failing Gaea2 projects"""

import json

# The provided JSON strings
working_json = {
    "$id": "1",
    "Assets": {
        "$id": "2",
        "$values": [
            {
                "$id": "3",
                "Terrain": {
                    "$id": "4",
                    "Id": "8ddaf261-da09-4efe-984d-fc41d7eb5d44",
                    "Metadata": {
                        "$id": "5",
                        "Name": "test.project",
                        "Description": "Created by Gaea2 MCP Server",
                        "Version": "",
                        "DateCreated": "2025-07-21 16:00:31Z",
                        "DateLastBuilt": "2025-07-21 16:00:31Z",
                        "DateLastSaved": "2025-07-21 16:00:31Z",
                    },
                    "Nodes": {
                        "$id": "6",
                        "1": {
                            "$id": "7",
                            "$type": "QuadSpinner.Gaea.Nodes.Mountain, Gaea.Nodes",
                            "Id": 1,
                            "Name": "Mountain",
                            "Position": {"$id": "8", "X": 24000.0, "Y": 26000.0},
                            "Ports": {
                                "$id": "9",
                                "$values": [
                                    {
                                        "$id": "11",
                                        "Name": "In",
                                        "Type": "PrimaryIn",
                                        "IsExporting": True,
                                        "Parent": {"$ref": "7"},
                                    },
                                    {
                                        "$id": "12",
                                        "Name": "Out",
                                        "Type": "PrimaryOut",
                                        "IsExporting": True,
                                        "Parent": {"$ref": "7"},
                                    },
                                ],
                            },
                            "Modifiers": {"$id": "10", "$values": []},
                        },
                    },
                    "Groups": {"$id": "13"},
                    "Notes": {"$id": "14"},
                    "GraphTabs": {
                        "$id": "15",
                        "$values": [
                            {
                                "$id": "16",
                                "Name": "Graph 1",
                                "Color": "Brass",
                                "ZoomFactor": 0.5338687202362516,
                                "ViewportLocation": {"$id": "17", "X": 25531.445, "Y": 25791.812},
                            }
                        ],
                    },
                    "Width": 5000.0,
                    "Height": 2500.0,
                    "Ratio": 0.5,
                },
                "Automation": {
                    "$id": "18",
                    "Bindings": {"$id": "19", "$values": []},
                    "Variables": {"$id": "20"},
                    "BoundProperties": {"$id": "21", "$values": []},
                },
                "BuildDefinition": {
                    "$id": "22",
                    "Destination": "<Builds>\\[Filename]\\[+++]",
                    "Resolution": 2048,
                    "BakeResolution": 2048,
                    "TileResolution": 1024,
                    "BucketResolution": 2048,
                    "BucketCount": 1,
                    "WorldResolution": 2048,
                    "NumberOfTiles": 1,
                    "TotalTiles": 1,
                    "BucketSizeWithMargin": 3072,
                    "EdgeBlending": 0.25,
                    "EdgeSize": 512,
                    "TileZeroIndex": True,
                    "TilePattern": "_y%Y%_x%X%",
                    "OrganizeFiles": "NodeSubFolder",
                    "PostBuildScript": "",
                    "Regions": {"$id": "23", "$values": []},
                },
                "State": {
                    "$id": "24",
                    "BakeResolution": 2048,
                    "PreviewResolution": 512,
                    "SelectedNode": 1,
                    "LockedNode": None,
                    "NodeBookmarks": {"$id": "25", "$values": []},
                    "Viewport": {
                        "$id": "26",
                        "RenderMode": "Realistic",
                        "SunAltitude": 33.0,
                        "SunAzimuth": 45.0,
                        "SunIntensity": 1.0,
                        "AmbientOcclusion": True,
                        "Shadows": True,
                        "AirDensity": 1.0,
                        "AmbientIntensity": 1.0,
                        "Exposure": 1.0,
                        "FogDensity": 0.2,
                        "GroundBrightness": 0.8,
                        "Haze": 1.0,
                        "Ozone": 1.0,
                        "Camera": {"$id": "27"},
                    },
                },
            }
        ],
    },
    "Id": "8ddaf261",
    "Branch": 1,
    "Metadata": {
        "$id": "28",
        "Name": "test.project",
        "Description": "Created by Gaea2 MCP Server",
        "Version": "",
        "Owner": "",
        "DateCreated": "2025-07-21 16:00:31Z",
        "DateLastBuilt": "2025-07-21 16:00:31Z",
        "DateLastSaved": "2025-07-21 16:00:31Z",
    },
}

failing_json = {
    "$id": "1",
    "Assets": {
        "$id": "2",
        "$values": [
            {
                "$id": "3",
                "Terrain": {
                    "$id": "4",
                    "Id": "0e393e27-b485-43ab-b356-448338ef633e",
                    "Metadata": {
                        "$id": "5",
                        "Name": "regression_basic_terrain",
                        "Description": "Created by Gaea2 MCP Server",
                        "Version": "",
                        "DateCreated": "2025-07-21 16:00:33Z",
                        "DateLastBuilt": "2025-07-21 16:00:33Z",
                        "DateLastSaved": "2025-07-21 16:00:33Z",
                    },
                    "Nodes": {
                        "$id": "6",
                        "100": {
                            "$id": "7",
                            "$type": "QuadSpinner.Gaea.Nodes.Mountain, Gaea.Nodes",
                            "Scale": 1.0,
                            "Height": 0.7,
                            "Style": "Alpine",
                            "Bulk": "Medium",
                            "ReduceDetails": False,
                            "Seed": 0,
                            "X": 0.0,
                            "Y": 0.0,
                            "Id": 100,
                            "Name": "BaseTerrain",
                            "Position": {"$id": "8", "X": 25000.0, "Y": 26000.0},
                            "Ports": {
                                "$id": "9",
                                "$values": [
                                    {
                                        "$id": "11",
                                        "Name": "In",
                                        "Type": "PrimaryIn",
                                        "IsExporting": True,
                                        "Parent": {"$ref": "7"},
                                    },
                                    {
                                        "$id": "12",
                                        "Name": "Out",
                                        "Type": "PrimaryOut",
                                        "IsExporting": True,
                                        "Parent": {"$ref": "7"},
                                    },
                                ],
                            },
                            "Modifiers": {"$id": "10", "$values": []},
                        },
                        "101": {
                            "$id": "13",
                            "$type": "QuadSpinner.Gaea.Nodes.Erosion2, Gaea.Nodes",
                            "Duration": 0.04,
                            "Downcutting": 0.3,
                            "ErosionScale": 5000.0,
                            "Seed": 12345,
                            "BedLoadDischargeAmount": 0.0,
                            "BedLoadDischargeAngle": 0.0,
                            "CoarseSedimentsDischargeAmount": 0.0,
                            "CoarseSedimentsDischargeAngle": 0.0,
                            "SuspendedLoadDischargeAmount": 0.0,
                            "SuspendedLoadDischargeAngle": 0.0,
                            "Shape": 0.5,
                            "ShapeDetailScale": 0.5,
                            "ShapeSharpness": 0.5,
                            "Id": 101,
                            "Name": "NaturalErosion",
                            "Position": {"$id": "14", "X": 25500.0, "Y": 26000.0},
                            "Ports": {
                                "$id": "15",
                                "$values": [
                                    {
                                        "$id": "17",
                                        "Name": "In",
                                        "Type": "PrimaryIn",
                                        "Record": {
                                            "$id": "18",
                                            "From": 100,
                                            "To": 101,
                                            "FromPort": "Out",
                                            "ToPort": "In",
                                            "IsValid": True,
                                        },
                                        "IsExporting": True,
                                        "Parent": {"$ref": "13"},
                                    },
                                    {
                                        "$id": "19",
                                        "Name": "Out",
                                        "Type": "PrimaryOut",
                                        "IsExporting": True,
                                        "Parent": {"$ref": "13"},
                                    },
                                    {
                                        "$id": "20",
                                        "Name": "Flow",
                                        "Type": "Out",
                                        "IsExporting": True,
                                        "Parent": {"$ref": "13"},
                                    },
                                    {
                                        "$id": "21",
                                        "Name": "Wear",
                                        "Type": "Out",
                                        "IsExporting": True,
                                        "Parent": {"$ref": "13"},
                                    },
                                    {
                                        "$id": "22",
                                        "Name": "Deposits",
                                        "Type": "Out",
                                        "IsExporting": True,
                                        "Parent": {"$ref": "13"},
                                    },
                                    {"$id": "23", "Name": "Mask", "Type": "In", "IsExporting": True, "Parent": {"$ref": "13"}},
                                ],
                            },
                            "Modifiers": {"$id": "16", "$values": []},
                        },
                        "102": {
                            "$id": "24",
                            "$type": "QuadSpinner.Gaea.Nodes.TextureBase, Gaea.Nodes",
                            "Slope": 0.5,
                            "Scale": 0.5,
                            "Soil": 0.5,
                            "Patches": 0.5,
                            "Chaos": 0.5,
                            "Seed": 0,
                            "Id": 102,
                            "Name": "BaseTexture",
                            "Position": {"$id": "25", "X": 26000.0, "Y": 26000.0},
                            "Ports": {
                                "$id": "26",
                                "$values": [
                                    {
                                        "$id": "28",
                                        "Name": "In",
                                        "Type": "PrimaryIn",
                                        "Record": {
                                            "$id": "29",
                                            "From": 101,
                                            "To": 102,
                                            "FromPort": "Out",
                                            "ToPort": "In",
                                            "IsValid": True,
                                        },
                                        "IsExporting": True,
                                        "Parent": {"$ref": "24"},
                                    },
                                    {
                                        "$id": "30",
                                        "Name": "Out",
                                        "Type": "PrimaryOut",
                                        "IsExporting": True,
                                        "Parent": {"$ref": "24"},
                                    },
                                ],
                            },
                            "IsMaskable": True,
                            "Modifiers": {"$id": "27", "$values": []},
                        },
                        "103": {
                            "$id": "31",
                            "$type": "QuadSpinner.Gaea.Nodes.SatMap, Gaea.Nodes",
                            "Library": "Rock",
                            "LibraryItem": 0,
                            "Randomize": False,
                            "Range": {"$id": "32", "X": 0.5, "Y": 0.5},
                            "Bias": 0.5,
                            "Enhance": "None",
                            "Reverse": False,
                            "Rough": "None",
                            "Hue": 0.0,
                            "Saturation": 0.0,
                            "Lightness": 0.0,
                            "Id": 103,
                            "Name": "ColorMap",
                            "NodeSize": "Standard",
                            "Position": {"$id": "33", "X": 26500.0, "Y": 26000.0},
                            "Ports": {
                                "$id": "34",
                                "$values": [
                                    {
                                        "$id": "36",
                                        "Name": "In",
                                        "Type": "PrimaryIn, Required",
                                        "Record": {
                                            "$id": "37",
                                            "From": 102,
                                            "To": 103,
                                            "FromPort": "Out",
                                            "ToPort": "In",
                                            "IsValid": True,
                                        },
                                        "IsExporting": True,
                                        "Parent": {"$ref": "31"},
                                    },
                                    {
                                        "$id": "38",
                                        "Name": "Out",
                                        "Type": "PrimaryOut",
                                        "IsExporting": True,
                                        "Parent": {"$ref": "31"},
                                    },
                                ],
                            },
                            "Modifiers": {"$id": "35", "$values": []},
                        },
                        "104": {
                            "$id": "39",
                            "$type": "QuadSpinner.Gaea.Nodes.Export, Gaea.Nodes",
                            "Format": "PNG",
                            "Id": 104,
                            "Name": "TerrainExport",
                            "NodeSize": "Standard",
                            "Position": {"$id": "40", "X": 27000.0, "Y": 26000.0},
                            "SaveDefinition": {
                                "$id": "41",
                                "Node": 104,
                                "Filename": "TerrainExport",
                                "Format": "EXR",
                                "IsEnabled": True,
                            },
                            "Ports": {
                                "$id": "42",
                                "$values": [
                                    {
                                        "$id": "44",
                                        "Name": "In",
                                        "Type": "PrimaryIn, Required",
                                        "Record": {
                                            "$id": "45",
                                            "From": 103,
                                            "To": 104,
                                            "FromPort": "Out",
                                            "ToPort": "In",
                                            "IsValid": True,
                                        },
                                        "IsExporting": True,
                                        "Parent": {"$ref": "39"},
                                    },
                                    {
                                        "$id": "46",
                                        "Name": "Out",
                                        "Type": "PrimaryOut",
                                        "IsExporting": True,
                                        "Parent": {"$ref": "39"},
                                    },
                                ],
                            },
                            "Modifiers": {"$id": "43", "$values": []},
                        },
                    },
                    "Groups": {"$id": "47"},
                    "Notes": {"$id": "48"},
                    "GraphTabs": {
                        "$id": "49",
                        "$values": [
                            {
                                "$id": "50",
                                "Name": "Graph 1",
                                "Color": "Brass",
                                "ZoomFactor": 0.5338687202362516,
                                "ViewportLocation": {"$id": "51", "X": 25531.445, "Y": 25791.812},
                            }
                        ],
                    },
                    "Width": 5000.0,
                    "Height": 2500.0,
                    "Ratio": 0.5,
                },
                "Automation": {
                    "$id": "52",
                    "Bindings": {"$id": "53", "$values": []},
                    "Variables": {"$id": "54"},
                    "BoundProperties": {"$id": "55", "$values": []},
                },
                "BuildDefinition": {
                    "$id": "56",
                    "Destination": "<Builds>\\[Filename]\\[+++]",
                    "Resolution": 2048,
                    "BakeResolution": 2048,
                    "TileResolution": 1024,
                    "BucketResolution": 2048,
                    "BucketCount": 1,
                    "WorldResolution": 2048,
                    "NumberOfTiles": 1,
                    "TotalTiles": 1,
                    "BucketSizeWithMargin": 3072,
                    "EdgeBlending": 0.25,
                    "EdgeSize": 512,
                    "TileZeroIndex": True,
                    "TilePattern": "_y%Y%_x%X%",
                    "OrganizeFiles": "NodeSubFolder",
                    "PostBuildScript": "",
                    "Regions": {"$id": "57", "$values": []},
                },
                "State": {
                    "$id": "58",
                    "BakeResolution": 2048,
                    "PreviewResolution": 512,
                    "SelectedNode": 100,
                    "LockedNode": None,
                    "NodeBookmarks": {"$id": "59", "$values": []},
                    "Viewport": {
                        "$id": "60",
                        "RenderMode": "Realistic",
                        "SunAltitude": 33.0,
                        "SunAzimuth": 45.0,
                        "SunIntensity": 1.0,
                        "AmbientOcclusion": True,
                        "Shadows": True,
                        "AirDensity": 1.0,
                        "AmbientIntensity": 1.0,
                        "Exposure": 1.0,
                        "FogDensity": 0.2,
                        "GroundBrightness": 0.8,
                        "Haze": 1.0,
                        "Ozone": 1.0,
                        "Camera": {"$id": "61"},
                    },
                },
            }
        ],
    },
    "Id": "0e393e27",
    "Branch": 1,
    "Metadata": {
        "$id": "62",
        "Name": "regression_basic_terrain",
        "Description": "Created by Gaea2 MCP Server",
        "Version": "",
        "Owner": "",
        "DateCreated": "2025-07-21 16:00:33Z",
        "DateLastBuilt": "2025-07-21 16:00:33Z",
        "DateLastSaved": "2025-07-21 16:00:33Z",
    },
}

print("=== DEEP ANALYSIS: Working vs Failing Gaea2 Projects ===\n")

# Extract nodes for comparison
working_nodes = working_json["Assets"]["$values"][0]["Terrain"]["Nodes"]
failing_nodes = failing_json["Assets"]["$values"][0]["Terrain"]["Nodes"]

print("1. NODE COUNT:")
print(f"   Working: {len([k for k in working_nodes.keys() if k != '$id'])} nodes")
print(f"   Failing: {len([k for k in failing_nodes.keys() if k != '$id'])} nodes")

print("\n2. NODE IDS:")
print(f"   Working: {[k for k in working_nodes.keys() if k != '$id']}")
print(f"   Failing: {[k for k in failing_nodes.keys() if k != '$id']}")

print("\n3. MOUNTAIN NODE ANALYSIS:")
working_mountain = working_nodes["1"]
failing_mountain = failing_nodes["100"]

print("\n   Working Mountain keys:")
for key in sorted(working_mountain.keys()):
    if key not in ["$id", "$type", "Id", "Name", "Position", "Ports", "Modifiers"]:
        print(f"      {key}: {working_mountain[key]}")

print("\n   Failing Mountain keys:")
for key in sorted(failing_mountain.keys()):
    if key not in ["$id", "$type", "Id", "Name", "Position", "Ports", "Modifiers"]:
        print(f"      {key}: {failing_mountain[key]}")

print("\n4. KEY DIFFERENCES:")

# Check for properties
working_props = [
    k for k in working_mountain.keys() if k not in ["$id", "$type", "Id", "Name", "Position", "Ports", "Modifiers"]
]
failing_props = [
    k for k in failing_mountain.keys() if k not in ["$id", "$type", "Id", "Name", "Position", "Ports", "Modifiers"]
]

print(f"\n   a) Node Properties:")
print(f"      Working Mountain properties: {working_props} (count: {len(working_props)})")
print(f"      Failing Mountain properties: {failing_props} (count: {len(failing_props)})")

# Check for Export node
print(f"\n   b) Export Node:")
has_export_working = any("Export" in node.get("$type", "") for node in working_nodes.values() if isinstance(node, dict))
has_export_failing = any("Export" in node.get("$type", "") for node in failing_nodes.values() if isinstance(node, dict))
print(f"      Working has Export: {has_export_working}")
print(f"      Failing has Export: {has_export_failing}")

# Check port types
print(f"\n   c) Port Types:")
working_port_types = set()
failing_port_types = set()

for node in working_nodes.values():
    if isinstance(node, dict) and "Ports" in node:
        for port in node["Ports"].get("$values", []):
            working_port_types.add(port.get("Type"))

for node in failing_nodes.values():
    if isinstance(node, dict) and "Ports" in node:
        for port in node["Ports"].get("$values", []):
            failing_port_types.add(port.get("Type"))

print(f"      Working port types: {sorted(working_port_types)}")
print(f"      Failing port types: {sorted(failing_port_types)}")

# Check for extra node fields
print(f"\n   d) Extra Node Fields:")
for node_id, node in failing_nodes.items():
    if node_id != "$id" and isinstance(node, dict):
        extra_fields = [
            k
            for k in node.keys()
            if k not in ["$id", "$type", "Id", "Name", "Position", "Ports", "Modifiers"] and not k in failing_mountain.keys()
        ]
        if extra_fields:
            print(f"      Node {node.get('Name')}: {extra_fields}")

# Check Range objects
print(f"\n   e) Complex Properties:")
for node_id, node in failing_nodes.items():
    if node_id != "$id" and isinstance(node, dict):
        for key, value in node.items():
            if isinstance(value, dict) and "$id" in value and key != "Position":
                print(f"      Node {node.get('Name')}.{key}: has $id object")

print("\n5. HYPOTHESIS:")
print("   The failing project likely fails because:")
print("   - It has node properties (Scale, Height, Style, etc.) that Gaea2 doesn't expect")
print("   - It has an Export node which may not be needed")
print("   - It uses 'PrimaryIn, Required' port type instead of just 'PrimaryIn'")
print("   - Some nodes have NodeSize and IsMaskable properties")
print("   - The node IDs are non-sequential (100, 101, etc.) vs simple (1)")

# Save both for detailed inspection
with open("working_project_analysis.json", "w") as f:
    json.dump(working_json, f, indent=2)

with open("failing_project_analysis.json", "w") as f:
    json.dump(failing_json, f, indent=2)
