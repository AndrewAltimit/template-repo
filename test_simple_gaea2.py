#!/usr/bin/env python3
"""Simple test to debug the Gaea2 MCP server"""

import json

import requests

# Test the remote Gaea2 MCP server
MCP_SERVER = "http://192.168.0.152:8007"


def test_minimal_project():
    """Test creating a minimal Gaea2 project"""

    # Create a minimal workflow
    workflow = {
        "nodes": [
            {
                "id": "mountain_1",
                "type": "Mountain",
                "name": "Mountain",
                "properties": {"Seed": 42, "Scale": 1.0, "Height": 1.0},
                "position": {"x": 0, "y": 0},
            }
        ],
        "connections": [],
    }

    print("Creating minimal project...")

    # Create the project
    response = requests.post(
        f"{MCP_SERVER}/mcp/execute",
        json={
            "tool": "create_gaea2_project",
            "parameters": {"project_name": "test_minimal", "workflow": workflow, "auto_validate": True, "save_to_disk": False},
        },
    )

    print(f"Response status: {response.status_code}")

    if response.status_code != 200:
        print(f"Error response: {response.text}")
        return None

    result = response.json()
    print(f"Success: {result.get('success')}")

    if not result.get("success"):
        print(f"Error: {result.get('error')}")
        return None

    return result


def test_with_template():
    """Test using a template"""

    print("\nTesting with template...")

    response = requests.post(
        f"{MCP_SERVER}/mcp/execute",
        json={
            "tool": "create_gaea2_from_template",
            "parameters": {"template_name": "basic_terrain", "project_name": "test_template", "output_path": None},
        },
    )

    print(f"Response status: {response.status_code}")

    if response.status_code != 200:
        print(f"Error response: {response.text}")
        return None

    result = response.json()
    print(f"Success: {result.get('success')}")

    if not result.get("success"):
        print(f"Error: {result.get('error')}")
        return None

    # Pretty print the structure
    if result.get("project_structure"):
        print("\nProject structure sample:")
        structure_str = json.dumps(result["project_structure"], indent=2)
        print(structure_str[:500] + "..." if len(structure_str) > 500 else structure_str)

    return result


def main():
    print("Testing Gaea2 MCP Server")
    print("=" * 50)

    # Test minimal project
    result1 = test_minimal_project()

    # Test with template
    result2 = test_with_template()

    if result1 and result2:
        print("\n✓ Both tests passed!")
    else:
        print("\n❌ One or more tests failed")


if __name__ == "__main__":
    main()
