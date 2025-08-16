#!/usr/bin/env python3
"""Test script to verify new tools are properly integrated."""

import asyncio
import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from blender.server import BlenderMCPServer  # noqa: E402


async def test_tool_integration():
    """Test that all new tools are available."""
    import tempfile

    with tempfile.TemporaryDirectory() as temp_dir:
        server = BlenderMCPServer(base_dir=temp_dir)

        # Get all available tools
        tools = server.get_tools()

        # List of new tools that should be available
        expected_new_tools = [
            "setup_camera",
            "add_camera_track",
            "add_modifier",
            "add_particle_system",
            "add_smoke_simulation",
            "add_texture",
            "add_uv_map",
            "setup_compositor",
            "analyze_scene",
            "optimize_scene",
            "batch_render",
            "setup_world_environment",
        ]

        print("Checking tool integration...")
        print(f"Total tools available: {len(tools)}")

        missing_tools = []
        for tool_name in expected_new_tools:
            if tool_name in tools:
                print(f"✓ {tool_name} - Found")
            else:
                print(f"✗ {tool_name} - MISSING")
                missing_tools.append(tool_name)

        if missing_tools:
            print(f"\n❌ Integration FAILED: {len(missing_tools)} tools missing")
            return False
        else:
            print(f"\n✅ Integration SUCCESS: All {len(expected_new_tools)} new tools are available")
            return True


if __name__ == "__main__":
    success = asyncio.run(test_tool_integration())
    sys.exit(0 if success else 1)
