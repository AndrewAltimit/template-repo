#!/usr/bin/env python3
"""Test script for Gaea2 MCP Server"""

import asyncio
import json  # noqa: F401
import sys
from pathlib import Path  # noqa: F401

import httpx


async def test_gaea2_server(base_url: str = "http://localhost:8007"):
    """Test Gaea2 MCP Server endpoints"""

    async with httpx.AsyncClient(timeout=30.0) as client:
        print("Testing Gaea2 MCP Server...")
        print(f"Base URL: {base_url}\n")

        # Test health endpoint
        try:
            response = await client.get(f"{base_url}/health")
            print(f"✓ Health check: {response.json()}")
        except Exception as e:
            print(f"✗ Health check failed: {e}")
            return

        # Test listing tools
        try:
            response = await client.get(f"{base_url}/mcp/tools")
            tools = response.json()
            print(f"\n✓ Available tools: {len(tools['tools'])} tools")
            for tool in tools["tools"]:
                print(f"  - {tool['name']}: {tool['description']}")
        except Exception as e:
            print(f"✗ Failed to list tools: {e}")

        # Test creating project from template
        print("\n--- Testing template creation ---")
        try:
            response = await client.post(
                f"{base_url}/mcp/execute",
                json={
                    "tool": "create_gaea2_from_template",
                    "arguments": {
                        "template_name": "basic_terrain",
                        "project_name": "test_terrain",
                    },
                },
            )
            result = response.json()
            if result["success"]:
                print("✓ Created project from template")
                print(f"  Project path: {result['result']['project_path']}")
                print(f"  Nodes: {result['result']['node_count']}")
                print(f"  Connections: {result['result']['connection_count']}")
            else:
                print(f"✗ Template creation failed: {result.get('error', result['result'].get('error'))}")
        except Exception as e:
            print(f"✗ Template creation error: {e}")

        # Test custom project creation
        print("\n--- Testing custom project creation ---")
        try:
            response = await client.post(
                f"{base_url}/mcp/execute",
                json={
                    "tool": "create_gaea2_project",
                    "arguments": {
                        "project_name": "custom_terrain",
                        "nodes": [
                            {
                                "id": "1",
                                "type": "Mountain",
                                "properties": {"Height": 0.8},
                            },
                            {
                                "id": "2",
                                "type": "Erosion2",
                                "properties": {"Duration": 15},
                            },
                            {"id": "3", "type": "Export", "properties": {}},
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
                    },
                },
            )
            result = response.json()
            if result["success"]:
                print("✓ Created custom project")
                print(f"  Validation applied: {result['result']['validation_applied']}")
            else:
                print(f"✗ Custom project failed: {result.get('error', result['result'].get('error'))}")
        except Exception as e:
            print(f"✗ Custom project error: {e}")

        # Test workflow validation
        print("\n--- Testing workflow validation ---")
        try:
            response = await client.post(
                f"{base_url}/mcp/execute",
                json={
                    "tool": "validate_and_fix_workflow",
                    "arguments": {
                        "workflow": {
                            "nodes": [
                                {"id": "1", "type": "Mountain"},
                                {"id": "2", "type": "InvalidNode"},  # Invalid node
                            ],
                            "connections": [
                                {
                                    "from_node": "1",
                                    "from_port": "Out",
                                    "to_node": "2",
                                    "to_port": "InvalidPort",  # Invalid port
                                }
                            ],
                        }
                    },
                },
            )
            result = response.json()
            if result["success"]:
                print("✓ Validation completed")
                print(f"  Valid: {result['result']['valid']}")
                print(f"  Fixed: {result['result']['fixed']}")
                if result["result"]["errors"]:
                    print(f"  Errors: {result['result']['errors'][:2]}")
            else:
                print(f"✗ Validation failed: {result['error']}")
        except Exception as e:
            print(f"✗ Validation error: {e}")

        # Test node suggestions
        print("\n--- Testing node suggestions ---")
        try:
            response = await client.post(
                f"{base_url}/mcp/execute",
                json={
                    "tool": "suggest_gaea2_nodes",
                    "arguments": {
                        "current_nodes": ["Mountain", "Erosion2"],
                        "context": "Adding color and detail",
                    },
                },
            )
            result = response.json()
            if result["success"]:
                print("✓ Got node suggestions")
                suggestions = result["result"]["suggestions"]
                for s in suggestions[:3]:
                    print(f"  - {s['node_type']}: {s['reason']}")
            else:
                print(f"✗ Suggestions failed: {result['error']}")
        except Exception as e:
            print(f"✗ Suggestions error: {e}")

        print("\n✅ Gaea2 MCP Server tests completed!")
        print("\nNote: CLI automation tests require Windows with Gaea2 installed.")


if __name__ == "__main__":
    if len(sys.argv) > 1:
        base_url = sys.argv[1]
    else:
        base_url = "http://localhost:8007"

    asyncio.run(test_gaea2_server(base_url))
