#!/usr/bin/env python3
"""Check property names in reference files directly"""

import json
import os


def check_erosion2_properties():
    """Check how Erosion2 properties are named in reference files"""

    print("=== EROSION2 PROPERTIES IN REFERENCE FILES ===\n")

    # Check Level1.terrain
    with open("reference projects/mikus files/Level1.terrain", "r") as f:
        level1 = json.load(f)

    nodes = level1["Assets"]["$values"][0]["Terrain"]["Nodes"]

    # Find Erosion2 nodes
    for node_id, node in nodes.items():
        if isinstance(node, dict) and "Erosion2" in node.get("$type", ""):
            print(f"Level1.terrain - Erosion2 node {node_id}:")
            print("Properties:")
            for key, value in node.items():
                if key not in [
                    "$id",
                    "$type",
                    "Id",
                    "Name",
                    "Position",
                    "Ports",
                    "Modifiers",
                    "SnapIns",
                    "NodeSize",
                    "IsMaskable",
                ]:
                    print(f"  - '{key}': {value}")
            print()

    # Check other reference files
    print("\n=== CHECKING ALL REFERENCE FILES ===\n")

    erosion_properties = set()
    rivers_properties = set()

    for root, dirs, files in os.walk("reference projects"):
        for file in files:
            if file.endswith(".terrain"):
                path = os.path.join(root, file)
                try:
                    with open(path, "r") as f:
                        data = json.load(f)

                    nodes = data["Assets"]["$values"][0]["Terrain"]["Nodes"]

                    for node_id, node in nodes.items():
                        if isinstance(node, dict):
                            node_type = node.get("$type", "")

                            if "Erosion2" in node_type:
                                for key in node.keys():
                                    if key not in [
                                        "$id",
                                        "$type",
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
                                        erosion_properties.add(key)

                            elif "Rivers" in node_type:
                                for key in node.keys():
                                    if key not in [
                                        "$id",
                                        "$type",
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
                                        rivers_properties.add(key)
                except:
                    pass

    print("All Erosion2 properties found:")
    for prop in sorted(erosion_properties):
        has_space = " " in prop
        print(f"  {'[SPACE]' if has_space else '[NO-SPACE]'} {prop}")

    print("\n\nAll Rivers properties found:")
    for prop in sorted(rivers_properties):
        has_space = " " in prop
        print(f"  {'[SPACE]' if has_space else '[NO-SPACE]'} {prop}")


def check_port_types():
    """Check port type formats in reference files"""

    print("\n\n=== PORT TYPE ANALYSIS ===\n")

    with open("reference projects/mikus files/Level1.terrain", "r") as f:
        level1 = json.load(f)

    nodes = level1["Assets"]["$values"][0]["Terrain"]["Nodes"]

    # Check Erosion2 Mask port specifically
    for node_id, node in nodes.items():
        if isinstance(node, dict) and "Erosion2" in node.get("$type", ""):
            print(f"Erosion2 node {node_id} ports:")
            if "Ports" in node:
                for port in node["Ports"]["$values"]:
                    if port.get("Name") == "Mask":
                        print(f"  - Mask port Type: '{port.get('Type')}'")

    # Check Export/SatMap port types
    print("\nExport/SatMap port types:")
    for node_id, node in nodes.items():
        if isinstance(node, dict):
            node_type = node.get("$type", "").split(".")[-2] if "." in node.get("$type", "") else ""
            if node_type in ["Export", "SatMap"]:
                if "Ports" in node:
                    for port in node["Ports"]["$values"]:
                        if port.get("Name") == "In":
                            print(f"  - {node_type} node {node_id}: In port Type = '{port.get('Type')}'")


def main():
    check_erosion2_properties()
    check_port_types()


if __name__ == "__main__":
    main()
