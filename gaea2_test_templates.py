#!/usr/bin/env python3
"""
Comprehensive Gaea2 Template Maps for Testing

This file contains diverse template configurations to test:
1. Basic terrain types (mountain, desert, volcanic, etc.)
2. Complex workflows with many nodes
3. Edge cases and extreme values
4. Performance optimization scenarios
5. Validation of our Gaea2 knowledge
"""

import json
from typing import Any, Dict, List


class Gaea2TestTemplates:
    """Collection of test templates for Gaea2 MCP validation"""

    @staticmethod
    def create_basic_mountain_template() -> Dict[str, Any]:
        """Basic mountain terrain with erosion"""
        return {
            "name": "BasicMountain",
            "description": "Simple mountain with natural erosion",
            "nodes": [
                {
                    "id": "mountain1",
                    "type": "Mountain",
                    "properties": {"Height": 0.8, "Scale": 1.0, "Style": "Alpine", "Seed": 12345},
                    "position": {"x": 0, "y": 0},
                },
                {
                    "id": "erosion1",
                    "type": "Erosion2",
                    "properties": {"Strength": 0.5, "Detail": 0.6, "Iterations": 20, "Downcutting": 0.2},
                    "position": {"x": 200, "y": 0},
                },
                {
                    "id": "satmap1",
                    "type": "SatMap",
                    "properties": {"Library": "Rock", "LibraryItem": 0},
                    "position": {"x": 400, "y": 0},
                },
                {
                    "id": "export1",
                    "type": "Export",
                    "properties": {"format": "png", "filename": "basic_mountain"},
                    "position": {"x": 600, "y": 0},
                },
            ],
            "connections": [
                {"from": "mountain1", "from_port": "Out", "to": "erosion1", "to_port": "In"},
                {"from": "erosion1", "from_port": "Out", "to": "satmap1", "to_port": "In"},
                {"from": "satmap1", "from_port": "Out", "to": "export1", "to_port": "In"},
            ],
        }

    @staticmethod
    def create_desert_canyon_template() -> Dict[str, Any]:
        """Desert canyon with stratification"""
        return {
            "name": "DesertCanyon",
            "description": "Desert canyon with layered rock formations",
            "nodes": [
                {
                    "id": "ridges1",
                    "type": "Ridges",
                    "properties": {"Scale": 0.3, "Complexity": 0.7},
                    "position": {"x": 0, "y": 0},
                },
                {
                    "id": "terrace1",
                    "type": "Terrace",
                    "properties": {"Levels": 8, "Uniformity": 0.3, "SlopeBias": 0.6},
                    "position": {"x": 200, "y": 0},
                },
                {
                    "id": "erosion1",
                    "type": "Erosion",
                    "properties": {"Duration": 0.03, "Rock Softness": 0.6, "Downcutting": 0.4, "Feature Scale": 1500},
                    "position": {"x": 400, "y": 0},
                },
                {
                    "id": "stratify1",
                    "type": "Strata",
                    "properties": {"Stratification": 12, "Depth": 0.4},
                    "position": {"x": 600, "y": 0},
                },
                {"id": "colorizer1", "type": "CLUTer", "properties": {"Mode": "Altitude"}, "position": {"x": 800, "y": 0}},
                {
                    "id": "export1",
                    "type": "Export",
                    "properties": {"format": "exr", "filename": "desert_canyon"},
                    "position": {"x": 1000, "y": 0},
                },
            ],
            "connections": [
                {"from": "ridges1", "from_port": "Out", "to": "terrace1", "to_port": "In"},
                {"from": "terrace1", "from_port": "Out", "to": "erosion1", "to_port": "In"},
                {"from": "erosion1", "from_port": "Out", "to": "stratify1", "to_port": "In"},
                {"from": "stratify1", "from_port": "Out", "to": "colorizer1", "to_port": "In"},
                {"from": "colorizer1", "from_port": "Out", "to": "export1", "to_port": "In"},
            ],
        }

    @staticmethod
    def create_volcanic_terrain_template() -> Dict[str, Any]:
        """Volcanic terrain with lava flows"""
        return {
            "name": "VolcanicTerrain",
            "description": "Volcanic landscape with crater and lava flows",
            "nodes": [
                {
                    "id": "volcano1",
                    "type": "Crater",
                    "properties": {"Radius": 0.4, "Depth": 0.8, "Inner Slope": 0.7, "Outer Slope": 0.3},
                    "position": {"x": 0, "y": 0},
                },
                {
                    "id": "mountain1",
                    "type": "Mountain",
                    "properties": {"Height": 0.6, "Scale": 0.8, "Style": "Rugged"},
                    "position": {"x": 0, "y": 200},
                },
                {
                    "id": "combine1",
                    "type": "Combine",
                    "properties": {"Method": "Max", "Strength": 0.8},
                    "position": {"x": 300, "y": 100},
                },
                {
                    "id": "flow1",
                    "type": "FlowMap",
                    "properties": {"Intensity": 0.7, "Contrast": 0.5},
                    "position": {"x": 500, "y": 100},
                },
                {
                    "id": "thermal1",
                    "type": "ThermalErosion",
                    "properties": {"Strength": 0.4, "Iterations": 15},
                    "position": {"x": 700, "y": 100},
                },
                {
                    "id": "satmap1",
                    "type": "SatMap",
                    "properties": {"Library": "Volcanic", "LibraryItem": 0, "Hue": -0.1, "Saturation": 0.2},
                    "position": {"x": 900, "y": 100},
                },
                {
                    "id": "export1",
                    "type": "Export",
                    "properties": {"format": "tiff", "filename": "volcanic_terrain"},
                    "position": {"x": 1100, "y": 100},
                },
            ],
            "connections": [
                {"from": "volcano1", "from_port": "Out", "to": "combine1", "to_port": "Input"},
                {"from": "mountain1", "from_port": "Out", "to": "combine1", "to_port": "Input 2"},
                {"from": "combine1", "from_port": "Out", "to": "flow1", "to_port": "In"},
                {"from": "flow1", "from_port": "Out", "to": "thermal1", "to_port": "In"},
                {"from": "thermal1", "from_port": "Out", "to": "satmap1", "to_port": "In"},
                {"from": "satmap1", "from_port": "Out", "to": "export1", "to_port": "In"},
            ],
        }

    @staticmethod
    def create_complex_workflow_template() -> Dict[str, Any]:
        """Complex workflow with many nodes to test performance"""
        return {
            "name": "ComplexTerrain",
            "description": "Complex terrain with multiple biomes and effects",
            "nodes": [
                # Base terrain generators
                {
                    "id": "mountain1",
                    "type": "Mountain",
                    "properties": {"Height": 0.7, "Scale": 1.0},
                    "position": {"x": 0, "y": 0},
                },
                {"id": "ridges1", "type": "Ridges", "properties": {"Scale": 0.5}, "position": {"x": 0, "y": 200}},
                {
                    "id": "perlin1",
                    "type": "Perlin",
                    "properties": {"Scale": 2.0, "Octaves": 6},
                    "position": {"x": 0, "y": 400},
                },
                # Combiners
                {
                    "id": "combine1",
                    "type": "Combine",
                    "properties": {"Method": "Add", "Strength": 0.5},
                    "position": {"x": 300, "y": 100},
                },
                {
                    "id": "combine2",
                    "type": "Combine",
                    "properties": {"Method": "Multiply", "Strength": 0.7},
                    "position": {"x": 300, "y": 300},
                },
                # Erosion chain
                {
                    "id": "erosion1",
                    "type": "Erosion2",
                    "properties": {"Strength": 0.4, "Iterations": 15},
                    "position": {"x": 600, "y": 200},
                },
                {
                    "id": "thermal1",
                    "type": "ThermalErosion",
                    "properties": {"Strength": 0.3},
                    "position": {"x": 800, "y": 200},
                },
                {
                    "id": "hydraulic1",
                    "type": "HydraulicErosion",
                    "properties": {"Strength": 0.5},
                    "position": {"x": 1000, "y": 200},
                },
                # Details
                {"id": "terrace1", "type": "Terrace", "properties": {"Levels": 16}, "position": {"x": 1200, "y": 100}},
                {"id": "warp1", "type": "Warp", "properties": {"Amount": 0.2}, "position": {"x": 1200, "y": 300}},
                # Masks
                {
                    "id": "slope1",
                    "type": "SlopeSelector",
                    "properties": {"Min": 20, "Max": 60},
                    "position": {"x": 1400, "y": 0},
                },
                {
                    "id": "height1",
                    "type": "HeightSelector",
                    "properties": {"Min": 0.3, "Max": 0.8},
                    "position": {"x": 1400, "y": 200},
                },
                # Final processing
                {"id": "mixer1", "type": "Mixer", "properties": {}, "position": {"x": 1600, "y": 100}},
                {"id": "satmap1", "type": "SatMap", "properties": {"Library": "Alps"}, "position": {"x": 1800, "y": 100}},
                {
                    "id": "export1",
                    "type": "Export",
                    "properties": {"format": "raw", "filename": "complex_terrain"},
                    "position": {"x": 2000, "y": 100},
                },
            ],
            "connections": [
                # Base terrain mixing
                {"from": "mountain1", "from_port": "Out", "to": "combine1", "to_port": "Input"},
                {"from": "ridges1", "from_port": "Out", "to": "combine1", "to_port": "Input 2"},
                {"from": "combine1", "from_port": "Out", "to": "combine2", "to_port": "Input"},
                {"from": "perlin1", "from_port": "Out", "to": "combine2", "to_port": "Input 2"},
                # Erosion chain
                {"from": "combine2", "from_port": "Out", "to": "erosion1", "to_port": "In"},
                {"from": "erosion1", "from_port": "Out", "to": "thermal1", "to_port": "In"},
                {"from": "thermal1", "from_port": "Out", "to": "hydraulic1", "to_port": "In"},
                # Split for processing
                {"from": "hydraulic1", "from_port": "Out", "to": "terrace1", "to_port": "In"},
                {"from": "hydraulic1", "from_port": "Out", "to": "warp1", "to_port": "In"},
                # Masks
                {"from": "hydraulic1", "from_port": "Out", "to": "slope1", "to_port": "In"},
                {"from": "hydraulic1", "from_port": "Out", "to": "height1", "to_port": "In"},
                # Final mix
                {"from": "terrace1", "from_port": "Out", "to": "mixer1", "to_port": "Input 1"},
                {"from": "warp1", "from_port": "Out", "to": "mixer1", "to_port": "Input 2"},
                {"from": "slope1", "from_port": "Out", "to": "mixer1", "to_port": "Mask 1"},
                {"from": "height1", "from_port": "Out", "to": "mixer1", "to_port": "Mask 2"},
                # Output
                {"from": "mixer1", "from_port": "Out", "to": "satmap1", "to_port": "In"},
                {"from": "satmap1", "from_port": "Out", "to": "export1", "to_port": "In"},
            ],
        }

    @staticmethod
    def create_edge_case_template() -> Dict[str, Any]:
        """Template with edge cases and extreme values"""
        return {
            "name": "EdgeCaseTerrain",
            "description": "Tests extreme values and edge cases",
            "nodes": [
                {
                    "id": "mountain1",
                    "type": "Mountain",
                    "properties": {
                        "Height": 1.0,  # Maximum height
                        "Scale": 0.01,  # Very small scale
                        "Seed": 2147483647,  # Max int seed
                    },
                    "position": {"x": 0, "y": 0},
                },
                {
                    "id": "erosion1",
                    "type": "Erosion2",
                    "properties": {
                        "Strength": 0.0,  # No erosion
                        "Iterations": 100,  # Very high iterations
                        "Detail": 1.0,  # Maximum detail
                    },
                    "position": {"x": 200, "y": 0},
                },
                {
                    "id": "terrace1",
                    "type": "Terrace",
                    "properties": {
                        "Levels": 64,  # Very many levels
                        "Uniformity": 0.0,  # No uniformity
                        "SlopeBias": 1.0,  # Maximum bias
                    },
                    "position": {"x": 400, "y": 0},
                },
                {
                    "id": "constant1",
                    "type": "Constant",
                    "properties": {"Value": -1.0},  # Negative value
                    "position": {"x": 0, "y": 200},
                },
                {"id": "abs1", "type": "Abs", "properties": {}, "position": {"x": 200, "y": 200}},
                {"id": "clamp1", "type": "Clamp", "properties": {"Min": 0.1, "Max": 0.9}, "position": {"x": 600, "y": 100}},
                {
                    "id": "export1",
                    "type": "Export",
                    "properties": {"format": "pfm", "filename": "edge_case_terrain"},  # Less common format
                    "position": {"x": 800, "y": 100},
                },
            ],
            "connections": [
                {"from": "mountain1", "from_port": "Out", "to": "erosion1", "to_port": "In"},
                {"from": "erosion1", "from_port": "Out", "to": "terrace1", "to_port": "In"},
                {"from": "constant1", "from_port": "Out", "to": "abs1", "to_port": "In"},
                {"from": "terrace1", "from_port": "Out", "to": "clamp1", "to_port": "In"},
                {"from": "clamp1", "from_port": "Out", "to": "export1", "to_port": "In"},
            ],
        }

    @staticmethod
    def create_performance_test_template() -> Dict[str, Any]:
        """Template optimized for performance testing"""
        return {
            "name": "PerformanceTest",
            "description": "Tests performance optimization settings",
            "nodes": [
                {
                    "id": "mountain1",
                    "type": "Mountain",
                    "properties": {"Height": 0.7, "Scale": 1.0, "Style": "Alpine"},
                    "position": {"x": 0, "y": 0},
                },
                {
                    "id": "erosion1",
                    "type": "Erosion2",
                    "properties": {
                        "Strength": 0.5,
                        "Iterations": 10,  # Low for performance
                        "Detail": 0.3,  # Low for performance
                        "Downcutting": 0.2,
                    },
                    "position": {"x": 200, "y": 0},
                },
                {
                    "id": "resample1",
                    "type": "Resample",
                    "properties": {"Resolution": "512", "Method": "Bilinear"},  # Low resolution
                    "position": {"x": 400, "y": 0},
                },
                {
                    "id": "satmap1",
                    "type": "SatMap",
                    "properties": {"Quality": "Fast", "Library": "Rock"},  # Performance mode
                    "position": {"x": 600, "y": 0},
                },
                {
                    "id": "export1",
                    "type": "Export",
                    "properties": {"format": "jpg", "quality": 80, "filename": "performance_test"},  # Compressed format
                    "position": {"x": 800, "y": 0},
                },
            ],
            "connections": [
                {"from": "mountain1", "from_port": "Out", "to": "erosion1", "to_port": "In"},
                {"from": "erosion1", "from_port": "Out", "to": "resample1", "to_port": "In"},
                {"from": "resample1", "from_port": "Out", "to": "satmap1", "to_port": "In"},
                {"from": "satmap1", "from_port": "Out", "to": "export1", "to_port": "In"},
            ],
        }

    @staticmethod
    def create_data_map_template() -> Dict[str, Any]:
        """Template using data maps and advanced features"""
        return {
            "name": "DataMapTerrain",
            "description": "Tests data maps and advanced node types",
            "nodes": [
                {
                    "id": "file1",
                    "type": "File",
                    "properties": {"Filename": "heightmap.png", "Mode": "Grayscale"},
                    "position": {"x": 0, "y": 0},
                },
                {
                    "id": "datamap1",
                    "type": "DataMap",
                    "properties": {"Type": "Normal", "Strength": 1.0},
                    "position": {"x": 200, "y": 0},
                },
                {"id": "mountain1", "type": "Mountain", "properties": {"Height": 0.5}, "position": {"x": 0, "y": 200}},
                {
                    "id": "displace1",
                    "type": "Displace",
                    "properties": {"Amount": 0.3, "Direction": "Vertical"},
                    "position": {"x": 400, "y": 100},
                },
                {
                    "id": "fx1",
                    "type": "Fx",
                    "properties": {"Effect": "Sharpen", "Amount": 0.5},
                    "position": {"x": 600, "y": 100},
                },
                {
                    "id": "export1",
                    "type": "Export",
                    "properties": {"format": "r16", "filename": "datamap_terrain"},
                    "position": {"x": 800, "y": 100},
                },
                {
                    "id": "export2",
                    "type": "Export",
                    "properties": {"format": "normal", "filename": "datamap_normal"},
                    "position": {"x": 800, "y": 300},
                },
            ],
            "connections": [
                {"from": "file1", "from_port": "Out", "to": "datamap1", "to_port": "In"},
                {"from": "mountain1", "from_port": "Out", "to": "displace1", "to_port": "In"},
                {"from": "datamap1", "from_port": "Out", "to": "displace1", "to_port": "Mask"},
                {"from": "displace1", "from_port": "Out", "to": "fx1", "to_port": "In"},
                {"from": "fx1", "from_port": "Out", "to": "export1", "to_port": "In"},
                {"from": "datamap1", "from_port": "Out", "to": "export2", "to_port": "In"},
            ],
        }

    @staticmethod
    def create_island_template() -> Dict[str, Any]:
        """Island terrain with beaches and ocean"""
        return {
            "name": "IslandTerrain",
            "description": "Tropical island with beaches",
            "nodes": [
                {
                    "id": "island1",
                    "type": "Island",
                    "properties": {"Size": 0.6, "Height": 0.7, "Beaches": 0.8},
                    "position": {"x": 0, "y": 0},
                },
                {
                    "id": "mountain1",
                    "type": "Mountain",
                    "properties": {"Height": 0.4, "Scale": 0.3, "Style": "Rounded"},
                    "position": {"x": 0, "y": 200},
                },
                {
                    "id": "combine1",
                    "type": "Combine",
                    "properties": {"Method": "Add", "Strength": 0.6},
                    "position": {"x": 300, "y": 100},
                },
                {
                    "id": "beach1",
                    "type": "Beach",
                    "properties": {"Width": 0.2, "Smoothness": 0.7},
                    "position": {"x": 500, "y": 100},
                },
                {
                    "id": "erosion1",
                    "type": "CoastalErosion",
                    "properties": {"Strength": 0.4, "Iterations": 10},
                    "position": {"x": 700, "y": 100},
                },
                {
                    "id": "satmap1",
                    "type": "SatMap",
                    "properties": {"Library": "Tropical", "LibraryItem": 0},
                    "position": {"x": 900, "y": 100},
                },
                {
                    "id": "water1",
                    "type": "Water",
                    "properties": {"Level": 0.0, "Color": "#006994"},
                    "position": {"x": 1100, "y": 100},
                },
                {
                    "id": "export1",
                    "type": "Export",
                    "properties": {"format": "png", "filename": "island_terrain"},
                    "position": {"x": 1300, "y": 100},
                },
            ],
            "connections": [
                {"from": "island1", "from_port": "Out", "to": "combine1", "to_port": "Input"},
                {"from": "mountain1", "from_port": "Out", "to": "combine1", "to_port": "Input 2"},
                {"from": "combine1", "from_port": "Out", "to": "beach1", "to_port": "In"},
                {"from": "beach1", "from_port": "Out", "to": "erosion1", "to_port": "In"},
                {"from": "erosion1", "from_port": "Out", "to": "satmap1", "to_port": "In"},
                {"from": "satmap1", "from_port": "Out", "to": "water1", "to_port": "In"},
                {"from": "water1", "from_port": "Out", "to": "export1", "to_port": "In"},
            ],
        }

    @staticmethod
    def get_all_templates() -> List[Dict[str, Any]]:
        """Get all test templates"""
        return [
            Gaea2TestTemplates.create_basic_mountain_template(),
            Gaea2TestTemplates.create_desert_canyon_template(),
            Gaea2TestTemplates.create_volcanic_terrain_template(),
            Gaea2TestTemplates.create_complex_workflow_template(),
            Gaea2TestTemplates.create_edge_case_template(),
            Gaea2TestTemplates.create_performance_test_template(),
            Gaea2TestTemplates.create_data_map_template(),
            Gaea2TestTemplates.create_island_template(),
        ]

    @staticmethod
    def validate_template(template: Dict[str, Any]) -> Dict[str, Any]:
        """Validate a template structure"""
        errors = []
        warnings = []

        # Check required fields
        required_fields = ["name", "nodes", "connections"]
        for field in required_fields:
            if field not in template:
                errors.append(f"Missing required field: {field}")

        # Validate nodes
        if "nodes" in template:
            node_ids = set()
            for node in template["nodes"]:
                if "id" not in node:
                    errors.append("Node missing 'id' field")
                else:
                    if node["id"] in node_ids:
                        errors.append(f"Duplicate node id: {node['id']}")
                    node_ids.add(node["id"])

                if "type" not in node:
                    errors.append(f"Node {node.get('id', 'unknown')} missing 'type' field")

                if "position" not in node:
                    warnings.append(f"Node {node.get('id', 'unknown')} missing position")

        # Validate connections
        if "connections" in template:
            for conn in template["connections"]:
                required_conn_fields = ["from", "to"]
                for field in required_conn_fields:
                    if field not in conn:
                        errors.append(f"Connection missing '{field}' field")

                # Check if referenced nodes exist
                if "nodes" in template and "from" in conn:
                    if conn["from"] not in node_ids:
                        errors.append(f"Connection references non-existent node: {conn['from']}")
                if "nodes" in template and "to" in conn:
                    if conn["to"] not in node_ids:
                        errors.append(f"Connection references non-existent node: {conn['to']}")

        return {"valid": len(errors) == 0, "errors": errors, "warnings": warnings}


def main():
    """Test template generation and validation"""
    templates = Gaea2TestTemplates.get_all_templates()

    print(f"Generated {len(templates)} test templates:")
    print("-" * 60)

    for template in templates:
        validation = Gaea2TestTemplates.validate_template(template)
        status = "✓" if validation["valid"] else "✗"
        print(f"{status} {template['name']:20} - {template['description']}")

        if not validation["valid"]:
            for error in validation["errors"]:
                print(f"  ERROR: {error}")

        if validation["warnings"]:
            for warning in validation["warnings"]:
                print(f"  WARNING: {warning}")

        # Print statistics
        node_count = len(template.get("nodes", []))
        conn_count = len(template.get("connections", []))
        node_types = set(node.get("type") for node in template.get("nodes", []))
        print(f"  Nodes: {node_count}, Connections: {conn_count}, Types: {len(node_types)}")
        print()

    # Save templates to file for testing
    with open("gaea2_test_templates.json", "w") as f:
        json.dump(
            {
                "templates": templates,
                "metadata": {"version": "1.0", "created": "2024-01-19", "purpose": "Gaea2 MCP validation and testing"},
            },
            f,
            indent=2,
        )

    print("Templates saved to gaea2_test_templates.json")


if __name__ == "__main__":
    main()
