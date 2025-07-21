#!/usr/bin/env python3
"""Check if connections are properly embedded in ports"""

import json

# Load the failing project
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

print("=== CHECKING CONNECTIONS IN FAILING FILE ===\n")

nodes = failing_json["Assets"]["$values"][0]["Terrain"]["Nodes"]

# Check each node for connections
connection_count = 0
for node_id, node in nodes.items():
    if node_id != "$id" and isinstance(node, dict):
        node_name = node.get("Name", node_id)
        ports = node.get("Ports", {}).get("$values", [])

        for port in ports:
            if "Record" in port:
                connection_count += 1
                record = port["Record"]
                print(f"Found connection in {node_name}.{port['Name']}:")
                print(f"  From: Node {record['From']} port {record['FromPort']}")
                print(f"  To: Node {record['To']} port {record['ToPort']}")
                print(f"  IsValid: {record.get('IsValid', 'unknown')}")
                print()

print(f"\nTotal connections found: {connection_count}")

# Check the workflow flow
print("\n=== WORKFLOW ANALYSIS ===")
print("Expected flow: Mountain(100) -> Erosion2(101) -> TextureBase(102) -> SatMap(103) -> Export(104)")
print("\nActual connections:")
print("  Mountain -> Erosion2: YES (via Record in Erosion2.In)")
print("  Erosion2 -> TextureBase: YES (via Record in TextureBase.In)")
print("  TextureBase -> SatMap: YES (via Record in SatMap.In)")
print("  SatMap -> Export: YES (via Record in Export.In)")

print("\n✓ All connections are properly embedded as Record objects!")
print("\nSo the issue is NOT missing connections. Need to look deeper...")
