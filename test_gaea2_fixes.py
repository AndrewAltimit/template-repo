#!/usr/bin/env python3
"""Test the comprehensive Gaea2 fixes"""

import asyncio
import json
import os
import sys

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from tools.mcp.gaea2_mcp_server import Gaea2MCPServer


async def test_fixes():
    """Test the Gaea2 fixes"""
    # Initialize the server
    server = Gaea2MCPServer()

    # Test generating a volcanic terrain
    print("Testing volcanic terrain template with fixes...")
    result = await server.create_from_template(template_name="volcanic_terrain", project_name="test_volcanic_fixes")

    if result.get("success"):
        file_path = result.get("saved_path") or result.get("project_path")
        print(f"✓ Generated file: {file_path}")
        # Quick check of the generated file
        with open(file_path, "r") as f:
            data = json.load(f)
        nodes = data["Assets"]["$values"][0]["Terrain"]["Nodes"]
        print(f"✓ Generated {len(nodes)-1} nodes")

        # Check node IDs
        node_ids = []
        for node_id, node in nodes.items():
            if node_id != "$id" and isinstance(node, dict):
                node_ids.append(node.get("Id"))

        sorted_ids = sorted(node_ids)
        print(f"✓ Node IDs: {sorted_ids[:5]}...")

        # Check for Volcano X/Y
        for node in nodes.values():
            if isinstance(node, dict) and "Volcano" in node.get("$type", ""):
                if "X" in node and "Y" in node:
                    print(f"✓ Volcano has X/Y: X={node['X']}, Y={node['Y']}")
                else:
                    print("❌ Volcano missing X/Y properties")
                break
    else:
        error = result.get("error")
        print(f"❌ Failed: {error}")


# Run the async test
asyncio.run(test_fixes())
