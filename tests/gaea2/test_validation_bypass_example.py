#!/usr/bin/env python3
"""
Example showing how integration tests can bypass Gaea2 file validation
when testing invalid terrain generation scenarios.
"""
import asyncio
import os
import sys
import tempfile
from pathlib import Path

# Add the project root to the Python path
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

import requests


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

        # Call the MCP server to create the broken file
        response = requests.post(
            "http://localhost:8007/mcp/execute",
            json={
                "tool": "create_gaea2_project",
                "parameters": {
                    "project_name": "test_broken_for_validation",
                    "nodes": broken_workflow["nodes"],
                    "connections": broken_workflow["connections"],
                },
            },
            timeout=30,
        )

        result = response.json()

        print("Test with bypass:")
        print(f"  Success: {result.get('success')}")
        print(f"  Bypass for tests: {result.get('bypass_for_tests')}")
        print(f"  File validation performed: {result.get('file_validation_performed')}")

        if result.get("success"):
            print(f"  Created file: {result.get('project_path')}")
            print("  ✓ Successfully created broken file for testing (validation bypassed)")
        else:
            print(f"  ✗ Failed: {result.get('error')}")

    finally:
        # Clean up - remove the bypass
        os.environ.pop("GAEA2_BYPASS_FILE_VALIDATION_FOR_TESTS", None)


async def test_without_bypass():
    """Demonstrate normal behavior - validation enforced"""

    # Ensure bypass is NOT set
    os.environ.pop("GAEA2_BYPASS_FILE_VALIDATION_FOR_TESTS", None)

    # Try to create the same broken file
    broken_workflow = {
        "nodes": [
            {
                "id": "1",
                "type": "Mountain",
                "position": {"X": 0, "Y": 0},
            }
        ],
        "connections": [],
    }

    response = requests.post(
        "http://localhost:8007/mcp/execute",
        json={
            "tool": "create_gaea2_project",
            "parameters": {
                "project_name": "test_broken_should_fail",
                "nodes": broken_workflow["nodes"],
                "connections": broken_workflow["connections"],
            },
        },
        timeout=30,
    )

    result = response.json()

    print("\nTest without bypass:")
    print(f"  Success: {result.get('success')}")
    print(f"  File validation performed: {result.get('file_validation_performed')}")

    if not result.get("success"):
        print(f"  ✓ Correctly failed validation: {result.get('error')}")
        print(f"  File deleted: {result.get('file_deleted')}")
    else:
        print("  ✗ Should have failed but didn't!")


async def test_good_file():
    """Test that valid files pass validation"""

    # Use a known good template
    response = requests.post(
        "http://localhost:8007/mcp/execute",
        json={
            "tool": "create_gaea2_from_template",
            "parameters": {
                "template_name": "basic_terrain",
                "project_name": "test_good_file",
            },
        },
        timeout=60,  # Longer timeout for validation
    )

    result = response.json()

    print("\nTest with good file:")
    print(f"  Success: {result.get('success')}")
    print(f"  File validation performed: {result.get('file_validation_performed')}")
    print(f"  File validation passed: {result.get('file_validation_passed')}")

    if result.get("success"):
        print(f"  ✓ Successfully created and validated: {result.get('project_path')}")
    else:
        print(f"  ✗ Failed: {result.get('error')}")


async def main():
    """Run all test scenarios"""
    print("Gaea2 File Validation Bypass Example")
    print("=" * 50)
    print("\nThis demonstrates how integration tests can bypass")
    print("the mandatory Gaea2 file validation when needed.\n")

    # Check if server is running
    try:
        response = requests.get("http://localhost:8007/mcp/tools", timeout=5)
        if response.status_code != 200:
            print("ERROR: Gaea2 MCP server not responding correctly")
            return
    except Exception as e:
        print(f"ERROR: Cannot connect to Gaea2 MCP server at localhost:8007")
        print(f"Please start the server first: python -m tools.mcp.gaea2.server")
        return

    # Run test scenarios
    await test_with_validation_bypass()
    await test_without_bypass()
    await test_good_file()

    print("\n" + "=" * 50)
    print("Summary:")
    print("- Set GAEA2_BYPASS_FILE_VALIDATION_FOR_TESTS=1 to bypass validation")
    print("- Without bypass, invalid files are rejected and deleted")
    print("- Valid files pass validation normally")


if __name__ == "__main__":
    asyncio.run(main())
