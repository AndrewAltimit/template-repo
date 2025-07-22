#!/usr/bin/env python3
"""Test optimized validator performance and correctness"""

# Add parent directory to path
import sys
import time
from pathlib import Path
from typing import Any, Dict

sys.path.append(str(Path(__file__).parent.parent.parent))

from tools.mcp.gaea2.schema.gaea2_schema import create_workflow_from_template, validate_gaea2_project  # noqa: E402
from tools.mcp.gaea2.validation.gaea2_optimized_validator import get_optimized_validator  # noqa: E402


def create_large_workflow(num_nodes: int) -> Dict[str, Any]:
    """Create a large workflow for performance testing"""
    nodes = []
    connections = []

    # Create a chain of nodes
    for i in range(num_nodes):
        node_type = ["Mountain", "Erosion2", "FractalTerraces", "Combine", "Shear"][i % 5]
        nodes.append(
            {
                "id": 100 + i,
                "type": node_type,
                "name": f"{node_type}_{i}",
                "properties": {
                    "Scale": 1.0 + (i % 10) * 0.1,
                    "Height": 0.5 + (i % 5) * 0.1,
                    "Seed": i,
                },
            }
        )

        # Connect to previous node
        if i > 0:
            connections.append(
                {
                    "from_node": 100 + i - 1,
                    "to_node": 100 + i,
                    "from_port": "Out",
                    "to_port": "In",
                }
            )

    # Add SatMap and Export at the end
    nodes.append(
        {
            "id": 100 + num_nodes,
            "type": "SatMap",
            "name": "FinalSatMap",
            "properties": {"Preset": "Rocky"},
        }
    )

    nodes.append(
        {
            "id": 100 + num_nodes + 1,
            "type": "Export",
            "name": "FinalExport",
            "properties": {},
        }
    )

    connections.append(
        {
            "from_node": 100 + num_nodes - 1,
            "to_node": 100 + num_nodes,
            "from_port": "Out",
            "to_port": "In",
        }
    )

    connections.append(
        {
            "from_node": 100 + num_nodes,
            "to_node": 100 + num_nodes + 1,
            "from_port": "Out",
            "to_port": "In",
        }
    )

    return {"nodes": nodes, "connections": connections}


def test_optimized_validator():
    """Test the optimized validator"""
    print("Testing Optimized Gaea2 Validator")
    print("=" * 60)

    # Test 1: Basic validation
    print("\nTest 1: Basic validation with small workflow")
    validator = get_optimized_validator()

    nodes = [
        {
            "id": 100,
            "type": "Mountain",
            "name": "Mountain1",
            "properties": {"Scale": 1.5, "Height": 0.8},
        },
        {
            "id": 101,
            "type": "Erosion2",
            "name": "Erosion1",
            "properties": {"Duration": 0.07, "Scale": 5000},
        },
    ]

    connections = [{"from_node": 100, "to_node": 101, "from_port": "Out", "to_port": "In"}]

    result = validator.validate_workflow(nodes, connections)
    print(f"Valid: {result['valid']}")
    print(f"Errors: {len(result['errors'])}")
    print(f"Warnings: {len(result['warnings'])}")

    # Test 2: Performance test with large workflow
    print("\nTest 2: Performance test with large workflow (100 nodes)")
    large_workflow = create_large_workflow(100)

    # Time regular validation
    start_time = time.time()
    for _ in range(3):
        validator.validate_workflow(large_workflow["nodes"], large_workflow["connections"])
    optimized_time = time.time() - start_time

    print(f"Optimized validation time (3 runs): {optimized_time:.3f}s")
    print(f"Average per run: {optimized_time/3:.3f}s")

    # Check cache stats
    stats = validator._get_cache_stats()
    print("\nCache statistics:")
    for key, value in stats.items():
        print(f"  {key}: {value}")

    # Test 3: Test integration with validate_gaea2_project
    print("\nTest 3: Integration with validate_gaea2_project")

    # Create a project from template
    template_nodes, template_connections = create_workflow_from_template("basic_terrain")

    # Build project structure
    project_data = {
        "$id": "test_project",
        "Assets": {"$values": [{"Terrain": {"Nodes": {}, "Name": "Test Terrain"}}]},
    }

    # Add nodes to project structure
    terrain = project_data["Assets"]["$values"][0]["Terrain"]
    for node in template_nodes:
        node_id = str(node["id"])
        terrain["Nodes"][node_id] = {
            "$type": f"QuadSpinner.Gaea.Nodes.{node['type']}, Gaea.Nodes",
            "Name": node["name"],
            **node["properties"],
        }

        # Add ports with connections
        if any(c["from_node"] == node["id"] for c in template_connections):
            terrain["Nodes"][node_id]["Ports"] = {"$values": []}
            for conn in template_connections:
                if conn["from_node"] == node["id"]:
                    terrain["Nodes"][node_id]["Ports"]["$values"].append(
                        {
                            "Record": {
                                "From": conn["from_node"],
                                "To": conn["to_node"],
                                "FromPort": conn["from_port"],
                                "ToPort": conn["to_port"],
                            }
                        }
                    )

    # Validate using the integrated function
    start_time = time.time()
    validation_result = validate_gaea2_project(project_data)
    validation_time = time.time() - start_time

    print(f"Project validation completed in {validation_time:.3f}s")
    print(f"Valid: {validation_result['valid']}")
    print(f"Node count: {validation_result['node_count']}")
    print(f"Connection count: {validation_result['connection_count']}")

    if "performance_stats" in validation_result:
        print("\nPerformance stats from integrated validation:")
        for key, value in validation_result["performance_stats"].items():
            print(f"  {key}: {value}")

    # Test 4: Cache effectiveness
    print("\nTest 4: Cache effectiveness with repeated validation")

    # Clear cache and validate again
    validator._validation_cache.clear()
    validator._property_cache_hits = 0

    # First run (cold cache)
    start_time = time.time()
    validator.validate_workflow(large_workflow["nodes"], large_workflow["connections"])
    cold_time = time.time() - start_time

    # Second run (warm cache)
    start_time = time.time()
    validator.validate_workflow(large_workflow["nodes"], large_workflow["connections"])
    warm_time = time.time() - start_time

    print(f"Cold cache validation: {cold_time:.3f}s")
    print(f"Warm cache validation: {warm_time:.3f}s")
    print(f"Speedup: {cold_time/warm_time:.1f}x")
    print(f"Cache hit rate: {validator._property_cache_hits} hits")


if __name__ == "__main__":
    test_optimized_validator()
