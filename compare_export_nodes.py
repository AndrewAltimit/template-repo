#!/usr/bin/env python3
"""Compare Export node structure between failing file and reference files"""

import glob
import json

# Find reference files with Export nodes
reference_files = glob.glob(
    "/home/miku/Documents/repos/template-repo/gaea-references/**/*.terrain",
    recursive=True,
)

print("=== LOOKING FOR EXPORT NODES IN REFERENCE FILES ===\n")

export_examples = []

for file_path in reference_files[:20]:  # Check first 20 files
    try:
        with open(file_path, "r") as f:
            data = json.load(f)

        nodes = data["Assets"]["$values"][0]["Terrain"]["Nodes"]

        for node_id, node in nodes.items():
            if node_id != "$id" and isinstance(node, dict):
                if "Export" in node.get("$type", ""):
                    export_examples.append({"file": file_path.split("/")[-1], "node": node, "id": node_id})
                    if len(export_examples) >= 3:  # Get 3 examples
                        break

        if len(export_examples) >= 3:
            break

    except Exception as e:
        pass

if not export_examples:
    print("No Export nodes found in reference files!")
else:
    print(f"Found {len(export_examples)} Export node examples:\n")

    for i, example in enumerate(export_examples):
        print(f"Example {i+1} from {example['file']}:")
        node = example["node"]

        # Show key structure
        print(f"  Node ID: {example['id']}")
        print(f"  Type: {node.get('$type', 'unknown')}")
        print(f"  Keys: {sorted(node.keys())}")

        # Check for specific fields
        if "Format" in node:
            print(f"  Format field: {node['Format']}")
        if "SaveDefinition" in node:
            print(f"  SaveDefinition: {node['SaveDefinition']}")
        if "NodeSize" in node:
            print(f"  NodeSize: {node['NodeSize']}")

        print()

print("\n=== FAILING FILE EXPORT NODE ===")
failing_export = {
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
}

print(f"  Type: {failing_export['$type']}")
print(f"  Keys: {sorted(failing_export.keys())}")
print(f"  Format field: {failing_export.get('Format', 'missing')}")
print(f"  SaveDefinition: {failing_export.get('SaveDefinition', 'missing')}")
print(f"  NodeSize: {failing_export.get('NodeSize', 'missing')}")

print("\n=== KEY OBSERVATIONS ===")
print("1. The failing Export node has BOTH 'Format' property AND 'SaveDefinition'")
print("2. This might be redundant/conflicting")
print("3. Format='PNG' in node but Format='EXR' in SaveDefinition")
print("4. Reference files may have different structure")
