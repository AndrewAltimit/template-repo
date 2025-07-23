#!/usr/bin/env python3
"""
Example showing how integration tests can bypass Gaea2 file validation
when testing invalid terrain generation scenarios.
"""
import os
import sys
import unittest.mock
from pathlib import Path

import pytest

# Add the project root to the Python path
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

from tools.mcp.gaea2.server import Gaea2MCPServer  # noqa: E402


# Create a test server instance
class TestServer:
    server = None

    @classmethod
    def get_server(cls):
        if cls.server is None:
            with unittest.mock.patch.dict(os.environ, {"GAEA2_TEST_MODE": "1"}):
                cls.server = Gaea2MCPServer()
        return cls.server


@pytest.mark.asyncio
async def test_with_validation_bypass():
    """Demonstrate how to bypass validation for integration tests"""

    # Set the bypass environment variable
    os.environ["GAEA2_BYPASS_FILE_VALIDATION_FOR_TESTS"] = "1"

    try:
        # Create a deliberately broken terrain file (missing required fields)
        broken_workflow = {
            "nodes": [
                {
                    "id": "1",
                    "type": "Mountain",
                    "position": {"X": 0, "Y": 0},
                    # Deliberately missing properties that would cause Gaea2 to fail
                }
            ],
            "connections": [],
        }

        # Get the test server
        server = TestServer.get_server()

        # Call the server directly to create the broken file
        result = await server.create_gaea2_project(
            project_name="test_broken_for_validation",
            nodes=broken_workflow["nodes"],
            connections=broken_workflow["connections"],
        )

        print("Test with bypass:")
        print(f"  Success: {result.get('success')}")
        print(f"  Bypass for tests: {result.get('bypass_for_tests')}")
        print(f"  File validation performed: {result.get('file_validation_performed')}")

        if result.get("success"):
            print(f"  Created file: {result.get('project_path')}")
            print("  ✓ Successfully created broken file for testing (validation bypassed)")
        else:
            print(f"  ✗ Failed: {result.get('error')}")

        # The file should be created even though it's broken
        assert result.get("success") is True
        assert result.get("bypass_for_tests") is True
        assert result.get("file_validation_performed") is False

    finally:
        # Clean up - remove the bypass
        os.environ.pop("GAEA2_BYPASS_FILE_VALIDATION_FOR_TESTS", None)


@pytest.mark.asyncio
async def test_without_bypass():
    """Test that validation works normally without bypass"""

    # Ensure bypass is NOT set
    os.environ.pop("GAEA2_BYPASS_FILE_VALIDATION_FOR_TESTS", None)

    # Create a deliberately broken terrain file
    broken_workflow = {
        "nodes": [
            {
                "id": "1",
                "type": "Mountain",
                "position": {"X": 0, "Y": 0},
                # Missing required properties
            }
        ],
        "connections": [],
    }

    # Get the test server
    server = TestServer.get_server()

    # Call the server directly to create the broken file
    result = await server.create_gaea2_project(
        project_name="test_broken_no_bypass",
        nodes=broken_workflow["nodes"],
        connections=broken_workflow["connections"],
    )

    print("\nTest without bypass:")
    print(f"  Success: {result.get('success')}")
    print(f"  File validation performed: {result.get('file_validation_performed')}")

    # Without bypass, the file creation should succeed but validation might fail
    # The server adds missing properties automatically, so it should actually succeed
    if result.get("success"):
        print(f"  Created file: {result.get('project_path')}")
        print("  ✓ File was created (server auto-fixed missing properties)")
    else:
        print(f"  ✗ Failed: {result.get('error')}")


@pytest.mark.asyncio
async def test_good_file():
    """Test that valid files work correctly"""

    # Create a valid workflow
    workflow = {
        "nodes": [
            {
                "id": "1",
                "type": "Mountain",
                "position": {"X": 0, "Y": 0},
                "properties": {
                    "Height": 0.7,
                    "Scale": 1.0,
                },
            },
            {"id": "2", "type": "Erosion", "position": {"X": 1, "Y": 0}},
            {"id": "3", "type": "Export", "position": {"X": 2, "Y": 0}},
        ],
        "connections": [
            {
                "from_node": "1",
                "from_port": "Out",
                "to_node": "2",
                "to_port": "In",
            },
            {
                "from_node": "2",
                "from_port": "Out",
                "to_node": "3",
                "to_port": "In",
            },
        ],
    }

    # Get the test server
    server = TestServer.get_server()

    # Call the server directly to create a valid file
    result = await server.create_gaea2_project(
        project_name="test_valid_terrain",
        nodes=workflow["nodes"],
        connections=workflow["connections"],
    )

    print("\nTest with valid file:")
    print(f"  Success: {result.get('success')}")
    print(f"  Created file: {result.get('project_path')}")
    print("  File validation performed:", result.get("file_validation_performed"))
    print("  File validation passed:", result.get("file_validation_passed"))

    # Valid file should always succeed
    assert result.get("success") is True
