#!/usr/bin/env python3
"""Analyze structural differences between working and failing Gaea2 files"""

import json
from pathlib import Path

# Load a reference working file
working_file = "gaea-references/Level1.terrain"
if Path(working_file).exists():
    with open(working_file, "r") as f:
        working = json.load(f)
else:
    print(f"Can't find {working_file}")
    exit(1)

print("=== CRITICAL STRUCTURE ANALYSIS ===\n")

# Analyze the first node in Level1.terrain
terrain = working["Assets"]["$values"][0]["Terrain"]
nodes = terrain["Nodes"]
first_node_id = next(k for k in nodes.keys() if k != "$id")
first_node = nodes[first_node_id]

print("1. WORKING NODE STRUCTURE (Level1.terrain - Volcano node):")
print(f"   Node ID: {first_node_id}")
print("\n   Properties in order:")
for i, (key, value) in enumerate(first_node.items()):
    if key in ["$id", "$type", "Id", "Name", "Position", "Ports", "Modifiers"]:
        continue
    print(f"   {i+1}. {key}: {value} (type: {type(value).__name__})")

print("\n2. KEY OBSERVATIONS:")
print("   - Node properties come BEFORE Id, Name, Position")
print("   - Properties use PascalCase with NO spaces")
print("   - X and Y properties at root level (normalized 0-1)")
print("   - Position.X/Y are different (canvas coordinates)")
print("   - Node IDs are non-sequential integers")

# Check if any nodes have ZERO properties
print("\n3. NODES WITH ZERO PROPERTIES:")
for node_id, node in nodes.items():
    if node_id == "$id":
        continue

    # Count actual properties
    props = [
        k
        for k in node.keys()
        if k
        not in [
            "$id",
            "$type",
            "Id",
            "Name",
            "Position",
            "Ports",
            "Modifiers",
            "SaveDefinition",
            "NodeSize",
            "PortCount",
            "IsMaskable",
            "IsLocked",
            "RenderIntentOverride",
        ]
    ]

    if len(props) == 0:
        print(f"   - {node.get('Name', 'Unknown')} (ID: {node.get('Id')}) - NO properties!")

# Check port structure
print("\n4. PORT STRUCTURE:")
example_port = first_node.get("Ports", {}).get("$values", [])[0] if first_node.get("Ports", {}).get("$values") else None
if example_port:
    print(f"   Port keys: {list(example_port.keys())}")
    print(f"   Port Type: {example_port.get('Type')}")

# Check Export nodes
print("\n5. EXPORT NODES:")
export_count = 0
for node_id, node in nodes.items():
    if node_id == "$id":
        continue
    if "Export" in node.get("$type", ""):
        export_count += 1
        print(f"   Found Export node: {node.get('Name')} (ID: {node.get('Id')})")

if export_count == 0:
    print("   NO Export nodes found!")

print("\n6. PROBLEMATIC PATTERNS IN OUR GENERATED FILES:")
print("   ❌ We add properties to ALL nodes (should be selective)")
print("   ❌ We use sequential IDs (100, 101, 102...)")
print("   ❌ We don't add X/Y root properties for nodes that need them")
print("   ❌ We add Export nodes (not always needed)")
print("   ❌ We use 'PrimaryIn, Required' instead of just 'PrimaryIn'")

# Check specific problem nodes
print("\n7. SNOW NODE CHECK:")
for node_id, node in nodes.items():
    if node_id == "$id":
        continue
    if "Snow" in node.get("$type", ""):
        props = [k for k in node.keys() if k not in ["$id", "$type", "Id", "Name", "Position", "Ports", "Modifiers"]]
        print(f"   Snow node has {len(props)} properties: {props}")
