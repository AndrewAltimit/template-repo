"""
Gaea2 Implementation Updates based on terrain file analysis.
This file contains property definitions and corrections discovered from analyzing real Gaea2 projects.
"""

# Additional node property definitions discovered from terrain analysis
ADDITIONAL_NODE_PROPERTIES = {
    "Sea": {
        "Level": {"type": "float", "default": 0.1, "range": [0.0, 1.0]},
        "CoastalErosion": {"type": "bool", "default": True},
        "ShoreSize": {"type": "float", "default": 0.68, "range": [0.0, 1.0]},
        "ShoreHeight": {"type": "float", "default": 0.2, "range": [0.0, 1.0]},
        "Variation": {"type": "float", "default": 0.48, "range": [0.0, 1.0]},
        "UniformVariations": {"type": "bool", "default": True},
        "ExtraCliffDetails": {"type": "bool", "default": True},
        "RenderSurface": {"type": "bool", "default": True},
    },
    "MountainSide": {
        "Detail": {"type": "float", "default": 0.25, "range": [0.0, 1.0]},
        "Style": {
            "type": "enum",
            "default": "Eroded",
            "values": ["Smooth", "Eroded", "Rocky"],
        },
        "Seed": {"type": "int", "default": 0, "range": [0, 999999]},
    },
    "Weathering": {
        "Scale": {"type": "float", "default": 0.3, "range": [0.0, 1.0]},
        "Creep": {"type": "float", "default": 0.5, "range": [0.0, 1.0]},
        "Dirt": {"type": "float", "default": 0.6, "range": [0.0, 1.0]},
    },
    "Dusting": {
        "Snowline": {"type": "float", "default": 0.5, "range": [0.0, 1.0]},
        "Falloff": {"type": "float", "default": 0.5, "range": [0.0, 1.0]},
        "Coverage": {"type": "float", "default": 0.15, "range": [0.0, 1.0]},
        "Flow": {"type": "float", "default": 0.15, "range": [0.0, 1.0]},
        "Melt": {"type": "float", "default": 0.4, "range": [0.0, 1.0]},
        "Gritty": {"type": "bool", "default": True},
        "Seed": {"type": "int", "default": 0, "range": [0, 999999]},
    },
    "Stratify": {
        "Spacing": {"type": "float", "default": 0.1, "range": [0.0, 1.0]},
        "Octaves": {"type": "int", "default": 12, "range": [1, 16]},
        "Intensity": {"type": "float", "default": 0.5, "range": [0.0, 1.0]},
        "Seed": {"type": "int", "default": 0, "range": [0, 999999]},
        "TiltAmount": {"type": "float", "default": 0.5, "range": [0.0, 1.0]},
    },
    "Perlin": {
        "Type": {
            "type": "enum",
            "default": "Ridged",
            "values": ["Default", "Ridged", "Billowy"],
        },
        "Scale": {"type": "float", "default": 0.08, "range": [0.0, 1.0]},
        "Octaves": {"type": "int", "default": 2, "range": [1, 10]},
        "Gain": {"type": "float", "default": 0.6, "range": [0.0, 1.0]},
        "Clamp": {"type": "float", "default": 1.0, "range": [0.0, 1.0]},
        "Seed": {"type": "int", "default": 0, "range": [0, 999999]},
        "WarpType": {
            "type": "enum",
            "default": "Complex",
            "values": ["None", "Simple", "Complex"],
        },
        "Frequency": {"type": "float", "default": 0.05, "range": [0.0, 1.0]},
        "Amplitude": {"type": "float", "default": 0.92, "range": [0.0, 1.0]},
        "WarpOctaves": {"type": "int", "default": 10, "range": [1, 10]},
        "ScaleX": {"type": "float", "default": 1.0, "range": [0.1, 10.0]},
        "ScaleY": {"type": "float", "default": 1.0, "range": [0.1, 10.0]},
        "X": {"type": "float", "default": 0.5, "range": [0.0, 1.0]},
        "Y": {"type": "float", "default": 0.5, "range": [0.0, 1.0]},
    },
}

# Port definitions updates - Rivers has 5 outputs, not 4
PORT_DEFINITION_UPDATES = {
    "Rivers": {
        "inputs": ["In", "Headwaters", "Mask"],
        "outputs": ["Out", "Rivers", "Depth", "Surface", "Direction"],
        # Note: All 5 outputs confirmed from terrain analysis
    },
    "Sea": {
        "inputs": ["In", "Edge", "Mask"],
        "outputs": ["Out", "Water", "Depth", "Shore", "Surface"],
    },
    "FractalTerraces": {
        "inputs": ["In", "Modulation", "Mask"],
        "outputs": ["Out", "Layers"],
    },
    "Stratify": {"inputs": ["In", "Mask"], "outputs": ["Out", "Layers"]},
    "Crumble": {"inputs": ["In", "AreaMask", "Mask"], "outputs": ["Out", "Wear"]},
    "Erosion2": {
        "inputs": ["In", "Mask"],
        "outputs": ["Out", "Flow", "Wear", "Deposits"],
    },
}

# Additional property name mappings discovered
ADDITIONAL_PROPERTY_MAPPINGS = {
    "Sea": {
        "coastalErosion": "CoastalErosion",
        "coastal_erosion": "CoastalErosion",
        "shoreSize": "ShoreSize",
        "shore_size": "ShoreSize",
        "shoreHeight": "ShoreHeight",
        "shore_height": "ShoreHeight",
        "uniformVariations": "UniformVariations",
        "uniform_variations": "UniformVariations",
        "extraCliffDetails": "ExtraCliffDetails",
        "extra_cliff_details": "ExtraCliffDetails",
        "renderSurface": "RenderSurface",
        "render_surface": "RenderSurface",
    },
    "Volcano": {
        "Surface": "Surface",  # Keep as-is, it's an enum property
    },
}

# Node-specific automatic properties to add
NODE_AUTO_PROPERTIES = {
    "Sea": {
        "NodeSize": "Standard",
        "IsMaskable": True,
    },
    "Weathering": {
        "NodeSize": "Small",
        "IsMaskable": True,
    },
    "Volcano": {
        "IsMaskable": True,
    },
    "MountainSide": {
        "IsMaskable": True,
    },
    "Stratify": {
        "IsMaskable": True,
    },
    "Perlin": {
        "IsMaskable": False,  # Perlin typically doesn't use masks
    },
    "Dusting": {
        "IsMaskable": True,
    },
}

# Common workflow patterns discovered
WORKFLOW_PATTERNS = {
    "universal_foundation": {
        "description": "The most common terrain foundation pattern (90% of projects)",
        "nodes": [
            {"type": "Slump", "properties": {"Scale": 0.15}},
            {"type": "FractalTerraces", "properties": {"Spacing": 0.1, "Octaves": 12}},
            {"type": "Combine", "properties": {"Ratio": 0.5, "Mode": "Add"}},
            {"type": "Shear", "properties": {"Strength": 0.025}},
        ],
        "connections": [
            {"from_node": 0, "to_node": 1},
            {"from_node": 1, "to_node": 2},
            {"from_node": 2, "to_node": 3},
        ],
    },
    "erosion_chain": {
        "description": "Standard erosion workflow",
        "nodes": [
            {
                "type": "Crumble",
                "properties": {"Duration": 0.5, "Strength": 0.87, "Coverage": 0.75},
            },
            {
                "type": "Erosion2",
                "properties": {
                    "Duration": 1.635,
                    "Downcutting": 0.81,
                    "ErosionScale": 15620.922,
                },
            },
            {
                "type": "Rivers",
                "properties": {"Water": 0.5, "Width": 0.8, "RiverValleyWidth": "plus2"},
            },
        ],
        "connections": [
            {"from_node": 0, "to_node": 1},
            {"from_node": 1, "to_node": 2},
        ],
    },
    "volcanic_specialty": {
        "description": "Volcanic terrain pattern",
        "nodes": [
            {
                "type": "Volcano",
                "properties": {
                    "Scale": 1.0,
                    "Height": 0.55,
                    "Mouth": 0.85,
                    "Surface": "Eroded",
                },
            },
            {"type": "MountainSide", "properties": {"Detail": 0.25, "Style": "Eroded"}},
            {"type": "Combine", "properties": {"Ratio": 0.5}},
        ],
        "connections": [
            {"from_node": 0, "to_node": 2},
            {"from_node": 1, "to_node": 2, "to_port": "Input2"},
        ],
    },
}

# SaveDefinition format for nodes that support export
SAVE_DEFINITION_FORMAT = {
    "Node": int,  # Node ID
    "Filename": str,  # Export filename
    "Format": str,  # Usually "EXR"
    "IsEnabled": bool,  # Whether export is active
}

# Common property values discovered
COMMON_PROPERTY_VALUES = {
    "Erosion2": {
        "Duration": [0.5, 1.635, 5.27, 10.33],  # Performance tiers
        "ErosionScale": 15620.922,  # Consistent across all projects
        "Shape": 0.4234392,
        "ShapeSharpness": 0.6,
        "ShapeDetailScale": 0.25,
    },
    "Rivers": {
        "RiverValleyWidth": ["zero", "plus2", "plus4"],
        "Headwaters": {
            "low": [3, 4],  # Fast performance
            "medium": [10, 100],  # Balanced
            "high": [200, 564],  # Quality
        },
    },
    "Combine": {
        "RenderIntentOverride": "Color",  # Critical for color operations
    },
    "TextureBase": {
        "Scale": 0.15,  # Consistent value
        "Slope": 0.483,
        "Soil": 0.6,
        "Patches": 0.4,
        "Chaos": 0.1,
    },
}


def update_gaea2_implementation():
    """
    Updates to apply to the Gaea2 MCP implementation based on terrain analysis.
    """
    updates = {
        "property_definitions": ADDITIONAL_NODE_PROPERTIES,
        "port_definitions": PORT_DEFINITION_UPDATES,
        "property_mappings": ADDITIONAL_PROPERTY_MAPPINGS,
        "auto_properties": NODE_AUTO_PROPERTIES,
        "workflow_patterns": WORKFLOW_PATTERNS,
        "common_values": COMMON_PROPERTY_VALUES,
    }

    return updates


# Validation rules based on discovered patterns
VALIDATION_RULES = {
    "Rivers": {
        "correlation": "Headwaters inversely correlates with Downcutting",
        "rule": lambda props: (
            (props.get("Headwaters", 10) < 10 and props.get("Downcutting", 0) > 0.7)
            or (props.get("Headwaters", 10) > 100 and props.get("Downcutting", 0) < 0.3)
            or (10 <= props.get("Headwaters", 10) <= 100)
        ),
    },
    "Combine": {
        "color_mode": "Must have RenderIntentOverride='Color' for color operations",
        "rule": lambda props, context: (
            context.get("is_color_operation") is False or props.get("RenderIntentOverride") == "Color"
        ),
    },
}
