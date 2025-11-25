#!/usr/bin/env python3
"""
Gaea2 pattern knowledge extracted from real project analysis
"""

from typing import Any, Dict, List, Optional

# Extracted from analyzing 31 real Gaea2 projects
COMMON_NODE_SEQUENCES = {
    "Mountain": ["Erosion2", "Outcrops"],
    "Erosion2": ["Rivers", "TextureBase", "ColorErosion", "Height", "Erosion2"],
    "Rivers": ["Adjust", "Height", "TextureBase", "Weathering"],
    "TextureBase": ["SatMap", "Combine"],
    "SatMap": ["Combine", "ColorErosion", "Mixer", "Weathering"],
    "Combine": ["Combine", "Shear", "Weathering", "Erosion2", "SatMap"],
    "Canyon": ["Stratify", "Sandstone", "Erosion2"],
    "Sandstone": ["Stratify", "TextureBase", "Autolevel", "SatMap", "Erosion2"],
    "Stratify": ["Stratify", "SlopeBlur", "Outcrops", "Erosion2"],
    "Crumble": ["Erosion2", "Sandstone", "Terraces"],
    "Shear": ["Crumble", "Terraces", "Stratify"],
    "Slump": ["FractalTerraces"],
    "FractalTerraces": ["Combine", "ColorErosion", "Thermal2"],
    "Island": ["Adjust", "Blur"],
    "Adjust": ["Combine", "Blur", "Tint"],
    "Height": ["Combine", "Debris", "Rivers", "Weathering"],
    "Weathering": ["Combine"],
    "ColorErosion": ["Combine", "ColorErosion", "Seamless"],
    "Ridge": ["Erosion2", "Outcrops"],
    "Volcano": ["Combine"],
    "Debris": ["Combine", "Debris", "SatMap"],
    "Blur": ["Combine"],
    "Terraces": ["Crumble", "Rivers", "Erosion2"],
}

# Workflow templates based on most common patterns
WORKFLOW_TEMPLATES = {
    "realistic_mountain": {
        "nodes": ["Mountain", "Erosion2", "Rivers", "Adjust", "TextureBase", "SatMap"],
        "description": "Standard workflow for realistic mountain terrains",
        "tags": ["mountain", "erosion", "water", "realistic"],
    },
    "terraced_landscape": {
        "nodes": [
            "Slump",
            "FractalTerraces",
            "Combine",
            "Shear",
            "Crumble",
            "Erosion2",
        ],
        "description": "Complex terraced landscapes with deformation",
        "tags": ["terraces", "geological", "complex"],
        "frequency": 9,  # Most common pattern
    },
    "desert_canyon": {
        "nodes": [
            "Canyon",
            "Sandstone",
            "Stratify",
            "Erosion2",
            "TextureBase",
            "SatMap",
        ],
        "description": "Desert canyon with rock stratification",
        "tags": ["canyon", "desert", "stratified", "sedimentary"],
    },
    "volcanic_terrain": {
        "nodes": ["Volcano", "Combine", "Thermal2", "Erosion2", "Weathering", "SatMap"],
        "description": "Volcanic landscape with thermal erosion",
        "tags": ["volcano", "thermal", "lava"],
    },
    "water_erosion": {
        "nodes": ["Mountain", "Erosion2", "Rivers", "Adjust", "Height", "Combine"],
        "description": "Water-carved terrain features",
        "tags": ["water", "erosion", "rivers", "carved"],
    },
    "alien_surface": {
        "nodes": ["CraterField", "Outcrops", "Outcrops", "SatMap"],
        "description": "Alien or lunar surface with craters",
        "tags": ["alien", "craters", "lunar", "scifi"],
    },
    "stratified_rocks": {
        "nodes": ["Sandstone", "Stratify", "Stratify", "SlopeBlur"],
        "description": "Layered rock formations",
        "tags": ["stratified", "sedimentary", "layers", "geological"],
    },
}

# Node connection probabilities based on real usage
NODE_CONNECTION_FREQUENCY = {
    "Mountain": {"Erosion2": 0.8, "Outcrops": 0.2},
    "Erosion2": {
        "Rivers": 0.26,
        "TextureBase": 0.23,
        "ColorErosion": 0.19,
        "Height": 0.13,
        "Erosion2": 0.10,
    },
    "Rivers": {"Adjust": 0.37, "Height": 0.33, "TextureBase": 0.30},
    "TextureBase": {"SatMap": 0.95, "Combine": 0.05},
    "SatMap": {
        "Combine": 0.64,
        "ColorErosion": 0.14,
        "Mixer": 0.10,
        "Weathering": 0.08,
    },
    "Combine": {
        "Combine": 0.29,
        "Shear": 0.21,
        "Weathering": 0.10,
        "Erosion2": 0.04,
        "SatMap": 0.04,
    },
    "Crumble": {"Erosion2": 0.82, "Sandstone": 0.09, "Terraces": 0.09},
    "Slump": {"FractalTerraces": 1.0},
    "Island": {"Adjust": 0.67, "Blur": 0.33},
    "Adjust": {"Combine": 0.56, "Blur": 0.33, "Tint": 0.11},
    "Height": {"Combine": 0.71, "Debris": 0.14, "Rivers": 0.07, "Weathering": 0.07},
}

# Most frequently used nodes (top 20)
NODE_USAGE_FREQUENCY = {
    "SatMap": 50,
    "Combine": 48,
    "Erosion2": 31,
    "TextureBase": 20,
    "Adjust": 18,
    "Height": 14,
    "ColorErosion": 12,
    "Crumble": 11,
    "Rivers": 10,
    "FractalTerraces": 10,
    "Shear": 10,
    "Weathering": 9,
    "Slump": 9,
    "Island": 9,
    "Blur": 9,
    "Stratify": 8,
    "Outcrops": 7,
    "Debris": 7,
    "Terraces": 7,
    "Sandstone": 6,
}

# Property recommendations based on patterns
PROPERTY_RECOMMENDATIONS = {
    "Erosion2": {
        "Duration": {
            "default": 0.07,
            "range": [0.04, 0.1],
            "note": "Lower values for better performance",
        },
        "common_patterns": {
            "subtle": {"Duration": 0.04},
            "moderate": {"Duration": 0.07},
            "heavy": {"Duration": 0.1},
        },
    },
    "Rivers": {
        "Headwaters": {
            "default": 100,
            "range": [50, 200],
            "note": "More headwaters = more detailed river networks",
        }
    },
    "Combine": {
        "Ratio": {
            "default": 0.5,
            "common_values": [0.3, 0.5, 0.7],
            "note": "0.5 for balanced blend, adjust for emphasis",
        }
    },
    "Mountain": {"Scale": {"default": 1.0, "range": [0.5, 2.0]}},
    "SatMap": {"common_presets": ["Rocky", "Desert", "Alpine", "Volcanic"]},
}


def get_next_node_suggestions(current_node: str, top_n: int = 3) -> List[Dict[str, Any]]:
    """Get suggested next nodes based on real usage patterns"""
    if current_node not in NODE_CONNECTION_FREQUENCY:
        return []

    frequencies = NODE_CONNECTION_FREQUENCY[current_node]
    sorted_nodes = sorted(frequencies.items(), key=lambda x: x[1], reverse=True)

    suggestions = []
    for node, probability in sorted_nodes[:top_n]:
        suggestions.append(
            {
                "node": node,
                "probability": probability,
                "usage_count": NODE_USAGE_FREQUENCY.get(node, 0),
            }
        )

    return suggestions


def get_workflow_for_terrain_type(terrain_type: str) -> Optional[Dict[str, Any]]:
    """Get recommended workflow for a terrain type"""
    terrain_workflows = {
        "mountain": "realistic_mountain",
        "canyon": "desert_canyon",
        "volcano": "volcanic_terrain",
        "terraced": "terraced_landscape",
        "alien": "alien_surface",
        "water": "water_erosion",
        "stratified": "stratified_rocks",
    }

    workflow_key = terrain_workflows.get(terrain_type.lower())
    if workflow_key and workflow_key in WORKFLOW_TEMPLATES:
        template = WORKFLOW_TEMPLATES[workflow_key]
        # Ensure we're returning a dict
        if isinstance(template, dict):
            return template

    return None


def suggest_properties_for_node(node_type: str, context: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """Suggest properties based on node type and context"""
    if node_type not in PROPERTY_RECOMMENDATIONS:
        return {}

    # Get recommendations and ensure it's a dict
    base_recommendations = PROPERTY_RECOMMENDATIONS.get(node_type, {})
    if not isinstance(base_recommendations, dict):
        return {}

    recommendations = base_recommendations.copy()

    # Context-aware adjustments
    if context:
        if context.get("performance_priority"):
            # Suggest lower values for performance
            if node_type == "Erosion2" and "Duration" in recommendations:
                recommendations["Duration"]["suggested"] = 0.04
            elif node_type == "Rivers" and "Headwaters" in recommendations:
                recommendations["Headwaters"]["suggested"] = 50

        if context.get("detail_priority"):
            # Suggest higher values for detail
            if node_type == "Erosion2" and "Duration" in recommendations:
                recommendations["Duration"]["suggested"] = 0.1
            elif node_type == "Rivers" and "Headwaters" in recommendations:
                recommendations["Headwaters"]["suggested"] = 200

    return recommendations
