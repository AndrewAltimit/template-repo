#!/usr/bin/env python3
"""Fix problematic nodes by limiting their properties"""

import json

# Based on testing, these nodes fail when they have too many properties
PROBLEMATIC_NODES = [
    "Snow",
    "Beach",
    "Coast",
    "Lakes",
    "Glacier",
    "SeaLevel",
    "LavaFlow",
    "ThermalShatter",
    "Ridge",
    "Strata",
    "Voronoi",
    "Terrace",
]

# Essential properties only for problematic nodes (max 3-4 properties)
MINIMAL_PROPERTIES = {
    "Snow": ["Duration", "SnowLine", "Melt"],  # Most important snow properties
    "Beach": ["Width", "Slope"],
    "Coast": ["Erosion", "Detail"],
    "Lakes": ["Count", "Size"],
    "Glacier": ["Scale", "Depth", "Flow"],
    "SeaLevel": ["Level", "Precision"],
    "LavaFlow": ["Temperature", "Viscosity"],
    "ThermalShatter": ["Intensity", "Scale"],
    "Ridge": ["Scale", "Complexity"],
    "Strata": ["Scale", "Layers", "Variation"],
    "Voronoi": ["Scale", "Jitter", "Style"],
    "Terrace": ["Levels", "Uniformity", "Sharp"],
}


def should_limit_properties(node_type):
    """Check if a node type should have limited properties"""
    return node_type in PROBLEMATIC_NODES


def get_minimal_properties(node_type, all_properties):
    """Get only essential properties for problematic nodes"""
    if node_type not in MINIMAL_PROPERTIES:
        return all_properties

    essential_props = MINIMAL_PROPERTIES[node_type]
    minimal = {}

    # Only include properties that are in our essential list
    for prop in essential_props:
        if prop in all_properties:
            minimal[prop] = all_properties[prop]

    return minimal


# Test with a failing template
print("Testing property limitation fix...\n")

# Read one of the failing template files
with open("regression_arctic_terrain.json", "r") as f:
    arctic_data = json.load(f)

# Count problematic nodes and their properties
terrain = arctic_data["Assets"]["$values"][0]["Terrain"]
nodes = terrain["Nodes"]

print("Original arctic_terrain template:")
for node_id, node in nodes.items():
    if node_id == "$id":
        continue

    node_type = node.get("$type", "").split(".")[-2].split(",")[0] if "$type" in node else "Unknown"
    if node_type in PROBLEMATIC_NODES:
        props = {k: v for k, v in node.items() if k not in ["$id", "$type", "Id", "Name", "Position", "Ports", "Modifiers"]}
        print(f"  {node_type}: {len(props)} properties")
        if node_type == "Snow":
            print(f"    Original properties: {list(props.keys())}")

print("\n\nFix strategy:")
print("1. Limit problematic nodes to 3-4 essential properties")
print("2. Keep normal nodes unchanged")
print("3. Update templates to use minimal properties")

# Example of how to fix in the server
print("\n\nProposed server code change in gaea2_mcp_server.py:")
print(
    """
# In create_gaea2_project method, after getting node properties:

if property_mode == 'smart':
    # Existing smart mode logic
    complex_nodes = ["Erosion2", "Rivers", "Sea", "Snow", "Thermal"]

    # NEW: Problematic nodes that need minimal properties
    problematic_nodes = ['Snow', 'Beach', 'Coast', 'Lakes', 'Glacier', 'SeaLevel',
                        'LavaFlow', 'ThermalShatter', 'Ridge', 'Strata', 'Voronoi', 'Terrace']

    if node_type in problematic_nodes:
        # Only use minimal essential properties
        essential_props = MINIMAL_PROPERTIES.get(node_type, [])
        properties = {}
        for prop in essential_props:
            if prop in raw_properties:
                properties[prop] = raw_properties[prop]
            elif prop in NODE_PROPERTY_DEFINITIONS.get(node_type, {}):
                # Add default for essential property
                prop_def = NODE_PROPERTY_DEFINITIONS[node_type][prop]
                properties[prop] = prop_def.get('default', 0.5)
    elif node_type in complex_nodes:
        # Other complex nodes still get full properties
        properties = apply_default_properties(node_type, raw_properties)
    else:
        # Simple nodes use minimal
        properties = raw_properties or {}
"""
)
