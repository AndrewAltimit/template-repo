#!/usr/bin/env python3
"""
Test Gaea2 validation against valid and invalid project files.
"""

import asyncio
import json
import os
import sys
from pathlib import Path

import pytest

# Add project root to Python path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from automation.analysis.generate_gaea2_schema import validate_gaea_project, validate_property  # noqa: E402
from tools.mcp.gaea2.server import Gaea2MCPServer  # noqa: E402


# Create a mock MCPTools class for backward compatibility
class MCPTools:
    server = None

    @classmethod
    def _get_server(cls):
        if cls.server is None:
            # Mock the environment check for testing
            import unittest.mock

            with unittest.mock.patch.dict(os.environ, {"GAEA2_TEST_MODE": "1"}):
                cls.server = Gaea2MCPServer()
        return cls.server

    @classmethod
    async def create_gaea2_project(cls, **kwargs):
        server = cls._get_server()
        # Call the method directly (not private)
        return await server.create_gaea2_project(**kwargs)


def test_valid_projects():
    """Test validation against known valid project configurations"""

    print("=== Testing Valid Projects ===")

    # Valid project from documentation example
    valid_project = {
        "nodes": [
            {
                "id": 100,
                "type": "Mountain",
                "name": "PrimaryMountain",
                "properties": {
                    "Scale": 1.8,
                    "Height": 0.85,
                    "Style": "Alpine",
                    "Bulk": "High",
                    "Seed": 42,
                },
            },
            {
                "id": 101,
                "type": "Erosion",
                "name": "NaturalErosion",
                "properties": {
                    "Duration": 0.04,
                    "Rock Softness": 0.4,
                    "Strength": 0.5,
                    "Feature Scale": 2000,
                    "Seed": 789,
                },
            },
            {
                "id": 102,
                "type": "SatMap",
                "name": "RealisticColors",
                "properties": {
                    "Library": "Rock",
                    "LibraryItem": 3,
                    "Enhance": "Autolevel",
                },
            },
        ],
        "connections": [
            {"from_node": 100, "to_node": 101, "from_port": "Out", "to_port": "In"},
            {"from_node": 101, "to_node": 102, "from_port": "Out", "to_port": "In"},
        ],
    }

    result = validate_gaea_project(valid_project["nodes"], valid_project["connections"])
    print("\nValid Mountain-Erosion-Color project:")
    print(f"  Valid: {result['valid']}")
    print(f"  Errors: {len(result['errors'])}")
    print(f"  Warnings: {len(result['warnings'])}")
    assert result["valid"], f"Expected valid project, got errors: {result['errors']}"

    # Test with real project data patterns
    real_project_pattern = {
        "nodes": [
            {
                "id": 671,
                "type": "Canyon",
                "name": "Canyon",
                "properties": {
                    "Style": "Eroded",
                    "Scale": 0.35,
                    "Slot": 0.36,
                    "Valley": 0.57795846,
                    "Surrounding": 0.6,
                    "Depth": 1.0,
                    "Seed": 37753,
                },
            },
            {
                "id": 184,
                "type": "Erosion2",
                "name": "Erosion2",
                "properties": {
                    "Duration": 10.0,  # Higher than 1.0 as seen in real projects
                    "Downcutting": 0.55541134,
                    "ErosionScale": 141.1173,
                    "Seed": 5397.0,  # Float that should be coerced to int
                    "SuspendedLoadDischargeAmount": 0.27254716,
                    "SuspendedLoadDischargeAngle": 24.0,
                    "BedLoadDischargeAmount": 0.19465701,
                    "BedLoadDischargeAngle": 15.0,
                },
            },
        ],
        "connections": [],
    }

    result = validate_gaea_project(real_project_pattern["nodes"], real_project_pattern["connections"])
    print("\nReal project pattern (Canyon + Erosion2):")
    print(f"  Valid: {result['valid']}")
    print(f"  Errors: {result['errors']}")
    print(f"  Warnings: {result['warnings']}")

    # Check that Seed was coerced to int
    erosion_node = result["corrected_nodes"][1]
    seed_value = erosion_node["properties"].get("Seed")
    assert isinstance(seed_value, int), f"Expected Seed to be int, got {type(seed_value)}"
    print(f"  ✓ Seed coerced from float to int: {seed_value}")


def test_invalid_projects():
    """Test validation against known invalid configurations"""

    print("\n=== Testing Invalid Projects ===")

    # Invalid node type
    invalid_type = {
        "nodes": [
            {
                "id": 100,
                "type": "MountainPeak",  # Doesn't exist
                "name": "BadNode",
                "properties": {},
            }
        ],
        "connections": [],
    }

    result = validate_gaea_project(invalid_type["nodes"], invalid_type["connections"])
    print("\nInvalid node type 'MountainPeak':")
    print(f"  Valid: {result['valid']}")
    print(f"  Errors: {result['errors']}")
    assert not result["valid"], "Expected validation to fail for invalid node type"

    # Invalid property values
    invalid_props = {
        "nodes": [
            {
                "id": 100,
                "type": "Mountain",
                "name": "Mountain",
                "properties": {
                    "Style": "SuperAlpine",  # Invalid enum value
                    "Height": 2.5,  # Out of range
                    "Seed": "not_a_number",  # Wrong type
                },
            }
        ],
        "connections": [],
    }

    result = validate_gaea_project(invalid_props["nodes"], invalid_props["connections"])
    print("\nInvalid property values:")
    print(f"  Valid: {result['valid']}")
    print(f"  Errors: {result['errors']}")
    assert not result["valid"], "Expected validation to fail for invalid properties"
    assert len(result["errors"]) >= 3, "Expected at least 3 errors"

    # Invalid connections
    invalid_connections = {
        "nodes": [
            {"id": 100, "type": "Mountain", "name": "Mountain", "properties": {}},
            {"id": 101, "type": "Erosion", "name": "Erosion", "properties": {}},
        ],
        "connections": [
            {"from_node": 100, "to_node": 101, "from_port": "Out", "to_port": "In"},
            {
                "from_node": 200,
                "to_node": 101,
                "from_port": "Out",
                "to_port": "In",
            },  # Non-existent node
        ],
    }

    result = validate_gaea_project(invalid_connections["nodes"], invalid_connections["connections"])
    print("\nInvalid connections (non-existent node):")
    print(f"  Valid: {result['valid']}")
    print(f"  Errors: {result['errors']}")
    assert not result["valid"], "Expected validation to fail for invalid connections"


def test_property_coercion():
    """Test property type coercion"""

    print("\n=== Testing Property Coercion ===")

    # Test integer coercion
    is_valid, error, value = validate_property("Mountain", "Seed", 12345.0)
    assert is_valid, f"Expected valid, got error: {error}"
    assert value == 12345, f"Expected 12345, got {value}"
    assert isinstance(value, int), f"Expected int, got {type(value)}"
    print(f"✓ Float 12345.0 -> int {value}")

    # Test enum validation
    is_valid, error, value = validate_property("Mountain", "Style", "Alpine")
    assert is_valid, f"Expected valid, got error: {error}"
    print("✓ Enum 'Alpine' is valid for Mountain.Style")

    is_valid, error, value = validate_property("Mountain", "Style", "InvalidStyle")
    assert not is_valid, "Expected invalid for bad enum value"
    print("✓ Enum 'InvalidStyle' correctly rejected")

    # Test range validation
    is_valid, error, value = validate_property("Mountain", "Height", 1.5)
    assert not is_valid, "Expected invalid for out-of-range value"
    print("✓ Height 1.5 correctly rejected (out of range)")

    # Test unknown property (should warn but allow)
    is_valid, error, value = validate_property("Mountain", "CustomProperty", "custom_value")
    assert is_valid, "Expected valid for unknown property"
    assert "Unknown property" in error, "Expected warning about unknown property"
    print("✓ Unknown property allowed with warning")


@pytest.mark.asyncio
async def test_mcp_integration():
    """Test integration with MCP server"""

    print("\n=== Testing MCP Integration ===")

    # This should use the new validation
    result = await MCPTools.create_gaea2_project(
        project_name="Validation Test",
        nodes=[
            {
                "id": 100,
                "type": "Mountain",
                "name": "TestMountain",
                "properties": {
                    "Scale": 1.5,
                    "Height": 0.8,
                    "Style": "Alpine",
                    "Seed": 12345.0,  # Should be coerced
                },
            }
        ],
        connections=[],
        output_path=None,  # Don't save file
    )

    print("MCP create_gaea2_project result:")
    print(f"  Success: {result.get('success')}")
    print(f"  Node count: {result.get('node_count')}")

    # Check the generated project structure
    if result.get("success") and result.get("project"):
        nodes = result["project"]["Assets"]["$values"][0]["Terrain"]["Nodes"]
        if "100" in nodes:
            seed_value = nodes["100"].get("Seed")
            print(f"  Seed value in project: {seed_value} (type: {type(seed_value).__name__})")


def main():
    """Run all validation tests"""

    print("Gaea2 Validation Test Suite")
    print("=" * 50)

    # Load schema to ensure it exists
    schema_path = Path("tools/mcp/gaea2_complete_schema.json")
    if not schema_path.exists():
        print("❌ Schema file not found. Run generate_accurate_schema.py first.")
        return

    with open(schema_path) as f:
        schema = json.load(f)
    print(f"✅ Loaded schema with {len(schema['valid_node_types'])} node types")

    # Run tests
    test_valid_projects()
    test_invalid_projects()
    test_property_coercion()

    # Run async test
    asyncio.run(test_mcp_integration())

    print("\n" + "=" * 50)
    print("✅ All validation tests passed!")


if __name__ == "__main__":
    main()
