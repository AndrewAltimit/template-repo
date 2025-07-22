#!/usr/bin/env python3
"""Remove only the Export node from failing project to test if that's the issue"""

import json

# The failing project
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
                                    {
                                        "$id": "23",
                                        "Name": "Mask",
                                        "Type": "In",
                                        "IsExporting": True,
                                        "Parent": {"$ref": "13"},
                                    },
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
                                "ViewportLocation": {
                                    "$id": "51",
                                    "X": 25531.445,
                                    "Y": 25791.812,
                                },
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

print("=== REMOVING EXPORT NODE FROM FAILING PROJECT ===\n")

# Remove node 104 (Export) and fix the connection from node 103
nodes = failing_json["Assets"]["$values"][0]["Terrain"]["Nodes"]

# Remove Export node
if "104" in nodes:
    del nodes["104"]
    print("✓ Removed Export node (104)")
else:
    print("✗ Export node (104) not found!")

# Remove the connection TO the Export node from SatMap
satmap = nodes.get("103")
if satmap:
    # The connection FROM SatMap TO Export was in Export's ports, not SatMap's
    # So we don't need to change SatMap
    print("✓ SatMap node unchanged (connection was in Export, not SatMap)")

# Update the node count info
print(f"\nRemaining nodes: {[k for k in nodes.keys() if k != '$id']}")

# Fix the project name
failing_json["Metadata"]["Name"] = "test_no_export_exact"
failing_json["Assets"]["$values"][0]["Terrain"]["Metadata"]["Name"] = "test_no_export_exact"

# Save the modified version
with open("test_no_export_exact.json", "w") as f:
    json.dump(failing_json, f, separators=(",", ":"))

print("\nSaved as test_no_export_exact.json")
print("\nThis file is EXACTLY like the failing file except:")
print("  - Export node removed")
print("  - Everything else unchanged (IDs 100-103, all properties, etc.)")
print("\nIf this works, then the Export node is the problem!")

# Also create a version with simple IDs
print("\n\n=== CREATING VERSION WITH SIMPLE IDS ===")

# Change IDs from 100,101,102,103 to 1,2,3,4
id_mapping = {"100": "1", "101": "2", "102": "3", "103": "4"}

# Create a new nodes dict with simple IDs
new_nodes = {"$id": nodes["$id"]}
for old_id, new_id in id_mapping.items():
    if old_id in nodes:
        node = nodes[old_id]
        # Update the Id field
        node["Id"] = int(new_id)
        # Update connection references
        for port in node.get("Ports", {}).get("$values", []):
            if "Record" in port:
                record = port["Record"]
                # Update From/To references
                if str(record.get("From")) in id_mapping:
                    record["From"] = int(id_mapping[str(record["From"])])
                if str(record.get("To")) in id_mapping:
                    record["To"] = int(id_mapping[str(record["To"])])
        new_nodes[new_id] = node

failing_json["Assets"]["$values"][0]["Terrain"]["Nodes"] = new_nodes
failing_json["Metadata"]["Name"] = "test_simple_ids"
failing_json["Assets"]["$values"][0]["Terrain"]["Metadata"]["Name"] = "test_simple_ids"

# Save the simple ID version
with open("test_simple_ids.json", "w") as f:
    json.dump(failing_json, f, separators=(",", ":"))

print("\nSaved as test_simple_ids.json")
print("This file has:")
print("  - Simple IDs (1,2,3,4 instead of 100,101,102,103)")
print("  - No Export node")
print("  - All properties intact")
