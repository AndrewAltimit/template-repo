#!/usr/bin/env python3
"""Showcase the Blender MCP Server capabilities."""

import asyncio
from datetime import datetime

import httpx


async def showcase_blender_mcp():
    """Demonstrate Blender MCP capabilities."""
    base_url = "http://localhost:8017"

    print("=" * 60)
    print("🎬 BLENDER MCP SERVER SHOWCASE")
    print("=" * 60)
    print()

    async with httpx.AsyncClient(timeout=30.0) as client:
        # 1. Check server health
        print("📡 Checking server status...")
        health = await client.get(f"{base_url}/health")
        print(f"   Server: {health.json()['server']} v{health.json()['version']}")
        print(f"   Status: {health.json()['status']}")
        print()

        # 2. List available tools
        print("🛠️  Available Tools:")
        caps = await client.get(f"{base_url}/mcp/capabilities")
        tools = caps.json()["capabilities"]["tools"]["list"]
        for i, tool in enumerate(tools, 1):
            print(f"   {i:2}. {tool}")
        print()

        # 3. List existing projects
        print("📁 Existing Projects:")
        list_req = {"tool": "list_projects", "arguments": {}}
        result = await client.post(f"{base_url}/mcp/execute", json=list_req)
        projects = result.json()["result"]["projects"]
        for project in projects[-5:]:  # Show last 5
            print(f"   • {project}")
        print()

        # 4. Create a showcase scene
        print("🎨 Creating Showcase Scene...")
        timestamp = datetime.now().strftime("%H%M%S")
        create_req = {
            "tool": "create_blender_project",
            "arguments": {
                "name": f"showcase_{timestamp}",
                "template": "studio_lighting",
                "settings": {"resolution": [1920, 1080], "fps": 30, "engine": "CYCLES"},
            },
        }

        result = await client.post(f"{base_url}/mcp/execute", json=create_req)
        if result.json()["success"]:
            project = result.json()["result"]["project_path"]
            print(f"   ✅ Created: {project}")

            # 5. Add showcase objects
            print("   📦 Adding objects...")
            objects_req = {
                "tool": "add_primitive_objects",
                "arguments": {
                    "project": project,
                    "objects": [
                        {"type": "monkey", "name": "Hero", "location": [0, 0, 2]},
                        {"type": "torus", "name": "Ring1", "location": [0, 0, 3.5], "scale": [2, 2, 0.3]},
                        {"type": "torus", "name": "Ring2", "location": [0, 0, 0.5], "scale": [2, 2, 0.3]},
                    ],
                },
            }
            await client.post(f"{base_url}/mcp/execute", json=objects_req)

            # 6. Apply materials
            print("   🎨 Applying materials...")
            materials = [
                ("Hero", "metal", {"roughness": 0.2, "base_color": [0.9, 0.7, 0.1, 1]}),
                ("Ring1", "emission", {"emission_strength": 3, "base_color": [0, 0.5, 1, 1]}),
                ("Ring2", "glass", {"roughness": 0.1}),
            ]

            for obj_name, mat_type, settings in materials:
                mat_req = {
                    "tool": "apply_material",
                    "arguments": {"project": project, "object_name": obj_name, "material": {"type": mat_type, **settings}},
                }
                await client.post(f"{base_url}/mcp/execute", json=mat_req)

            # 7. Create rotation animation
            print("   🎬 Creating animation...")
            for obj in ["Ring1", "Ring2"]:
                direction = 1 if obj == "Ring1" else -1
                anim_req = {
                    "tool": "create_animation",
                    "arguments": {
                        "project": project,
                        "object_name": obj,
                        "keyframes": [
                            {"frame": 1, "rotation": [0, 0, 0]},
                            {"frame": 60, "rotation": [0, direction * 3.14, 0]},
                            {"frame": 120, "rotation": [0, direction * 6.28, 0]},
                        ],
                        "interpolation": "LINEAR",
                    },
                }
                await client.post(f"{base_url}/mcp/execute", json=anim_req)

            print(f"   ✅ Showcase scene ready: {project}")
        print()

        # 6. Show statistics
        print("📊 Server Statistics:")
        print(f"   • Total projects: {len(projects)}")
        print(f"   • Available tools: {len(tools)}")
        print("   • Server uptime: Active")
        print()

        print("=" * 60)
        print("✨ Showcase complete!")
        print("   Use the render tools to generate images from any project.")
        print("=" * 60)


if __name__ == "__main__":
    asyncio.run(showcase_blender_mcp())
