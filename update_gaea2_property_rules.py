#!/usr/bin/env python3
"""Update Gaea2 server with property combination rules"""

# Based on our findings, here are the property rules to implement

PROPERTY_RULES = {
    # Nodes that should have LIMITED properties (max 3-4)
    "limited_property_nodes": [
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
    ],
    # Maximum properties for limited nodes
    "max_properties": 3,
    # Essential properties for each limited node
    "essential_properties": {
        "Snow": ["Duration", "SnowLine", "Melt"],  # Based on testing
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
    },
    # Valid property combinations (from reference files)
    "valid_combinations": {
        "Snow": [
            ["SettleThaw", "Melt"],  # From tut-highMountain.terrain
            ["Duration", "SnowLine"],
            ["Duration", "SnowLine", "Melt"],
        ]
    },
}

print("Property rules for Gaea2 server update:\n")

print("1. Limited property nodes (max 3 properties):")
for node in PROPERTY_RULES["limited_property_nodes"]:
    essential = PROPERTY_RULES["essential_properties"].get(node, [])
    print(f"   - {node}: {', '.join(essential)}")

print("\n2. Implementation in gaea2_mcp_server.py:")
print(
    """
# Add this after line 277 (in property_mode == "smart" block):

# NEW: Nodes that fail with too many properties
limited_property_nodes = [
    'Snow', 'Beach', 'Coast', 'Lakes', 'Glacier', 'SeaLevel',
    'LavaFlow', 'ThermalShatter', 'Ridge', 'Strata', 'Voronoi', 'Terrace'
]

if node_type in limited_property_nodes:
    # These nodes can only have limited properties (max 3)
    essential_props = {
        'Snow': ['Duration', 'SnowLine', 'Melt'],
        'Beach': ['Width', 'Slope'],
        'Coast': ['Erosion', 'Detail'],
        'Lakes': ['Count', 'Size'],
        'Glacier': ['Scale', 'Depth', 'Flow'],
        'SeaLevel': ['Level', 'Precision'],
        'LavaFlow': ['Temperature', 'Viscosity'],
        'ThermalShatter': ['Intensity', 'Scale'],
        'Ridge': ['Scale', 'Complexity'],
        'Strata': ['Scale', 'Layers', 'Variation'],
        'Voronoi': ['Scale', 'Jitter', 'Style'],
        'Terrace': ['Levels', 'Uniformity', 'Sharp']
    }

    node_essentials = essential_props.get(node_type, [])
    properties = {}

    # Only include essential properties that were provided
    for prop in node_essentials:
        if prop in raw_properties:
            properties[prop] = raw_properties[prop]
        elif prop in NODE_PROPERTY_DEFINITIONS.get(node_type, {}):
            # Add default only if not provided
            prop_def = NODE_PROPERTY_DEFINITIONS[node_type][prop]
            properties[prop] = prop_def.get('default', 0.5)

    # Ensure we don't exceed 3 properties
    if len(properties) > 3:
        # Take only the first 3 essential properties
        properties = dict(list(properties.items())[:3])

    properties = fix_property_names(properties, node_type)

elif node_type in ["Erosion2", "Rivers", "Sea", "Thermal"]:
    # These complex nodes still need full properties
    properties = apply_default_properties(node_type, raw_properties)
    properties = fix_property_names(properties, node_type)
else:
    # Simple nodes use minimal properties
    if not raw_properties:
        properties = {}
    else:
        properties = fix_property_names(raw_properties, node_type)
"""
)

print("\n3. Template updates needed:")
templates_to_fix = [
    "arctic_terrain",
    "mountain_range",
    "detailed_mountain",
    "coastal_cliffs",
    "canyon_system",
    "volcanic_island",
]

for template in templates_to_fix:
    print(f"   - {template}: Reduce Snow/Beach/Coast/etc. properties to max 3")
