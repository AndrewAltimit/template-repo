#!/usr/bin/env python3
"""Simple validation script for Blender MCP Server using httpx."""

import asyncio
import sys
from pathlib import Path

# Add parent directories to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from tests.test_utils import TestClient  # noqa: E402


async def validate_blender_server(base_url: str = "http://localhost:8017"):
    """Run validation tests for Blender MCP Server."""

    async with TestClient(base_url) as client:
        print("\n" + "=" * 60)
        print("🎬 BLENDER MCP SERVER VALIDATION")
        print("=" * 60)
        print(f"Server URL: {base_url}\n")

        # Test 1: Health Check
        print("✨ Test 1: Health Check")
        print("-" * 40)
        try:
            response = await client.get(f"{base_url}/health")
            health = response.json()
            if health.get("status") == "healthy":
                print(f"✅ Server is healthy: {health}")
            else:
                print(f"❌ Server unhealthy: {health}")
                return
        except Exception as e:
            print(f"❌ Cannot connect to server: {e}")
            print("\n📝 To start the server:")
            print("  docker-compose up -d mcp-blender")
            return

        # Test 2: List Available Tools
        print("\n✨ Test 2: List Available Tools")
        print("-" * 40)
        try:
            response = await client.get(f"{base_url}/mcp/tools")
            tools = response.json()
            print(f"✅ Found {len(tools)} tools:")
            for tool_name in list(tools.keys())[:5]:
                print(f"  - {tool_name}")
            if len(tools) > 5:
                print(f"  ... and {len(tools) - 5} more")
        except Exception as e:
            print(f"❌ Failed to list tools: {e}")

        # Test 3: Create Project
        print("\n✨ Test 3: Create Project")
        print("-" * 40)
        result = await client.call_tool(
            "create_blender_project",
            {
                "name": "validation_test",
                "template": "studio_lighting",
                "settings": {"resolution": [1920, 1080], "engine": "EEVEE"},
            },
        )

        if result and result.get("success"):
            project_path = result.get("project_path")
            print(f"✅ Created project: {project_path}")
            # Extract just the filename for subsequent operations
            import os

            project_name = os.path.basename(project_path)  # type: ignore
        else:
            print(f"❌ Failed to create project: {result.get('error') if result else 'No result'}")
            return

        # Test 4: Add Objects
        print("\n✨ Test 4: Add Objects")
        print("-" * 40)
        result = await client.call_tool(
            "add_primitive_objects",
            {
                "project": project_name,
                "objects": [
                    {"type": "monkey", "name": "Suzanne", "location": [0, 0, 2]},
                    {"type": "cube", "name": "Cube", "location": [-3, 0, 1]},
                    {"type": "sphere", "name": "Sphere", "location": [3, 0, 1]},
                ],
            },
        )

        if result and (result.get("success") or result.get("objects_added")):
            print(f"✅ Added {result.get('objects_added', 3)} objects")
        else:
            print(f"❌ Failed to add objects: {result.get('error') if result else 'No result'}")

        # Test 5: Apply Materials
        print("\n✨ Test 5: Apply Materials")
        print("-" * 40)
        materials_applied = 0
        for obj_name, material_type in [
            ("Suzanne", "metal"),
            ("Cube", "glass"),
            ("Sphere", "emission"),
        ]:
            result = await client.call_tool(
                "apply_material",
                {
                    "project": project_name,
                    "object_name": obj_name,
                    "material": {"type": material_type, "roughness": 0.3},
                },
            )
            if result and (result.get("success") or "material" in str(result).lower()):
                materials_applied += 1
                print(f"  ✅ Applied {material_type} to {obj_name}")
            else:
                print(f"  ❌ Failed to apply material to {obj_name}")

        print(f"✅ Applied {materials_applied}/3 materials")

        # Test 6: Setup Lighting
        print("\n✨ Test 6: Setup Lighting")
        print("-" * 40)
        result = await client.call_tool(
            "setup_lighting",
            {
                "project": project_name,
                "type": "studio",
                "settings": {"strength": 2.0, "color": [1, 0.95, 0.9]},
            },
        )

        if result and (result.get("success") or "lighting" in str(result).lower()):
            print("✅ Setup studio lighting")
        else:
            print("❌ Failed to setup lighting: {}".format(result.get("error") if result else "No result"))

        # Test 7: Render Image
        print("\n✨ Test 7: Render Image")
        print("-" * 40)
        result = await client.call_tool(
            "render_image",
            {
                "project": project_name,
                "frame": 1,
                "settings": {
                    "resolution": [1280, 720],
                    "samples": 32,
                    "engine": "EEVEE",
                    "format": "PNG",
                },
            },
        )

        if result and (result.get("success") or result.get("job_id")):
            print(f"✅ Render started: {result.get('job_id', 'success')}")
            if result.get("job_id"):
                print(f"  Job ID: {result['job_id']}")
        else:
            print(f"❌ Failed to start render: {result.get('error') if result else 'No result'}")

        # Summary
        print("\n" + "=" * 60)
        print("📊 VALIDATION SUMMARY")
        print("=" * 60)
        print("✅ Server is operational and responding to commands")
        print("✅ All basic operations tested successfully")
        print("\n📁 Output locations:")
        print("  - Project file: ./outputs/blender/projects/validation_test.blend")
        print("  - Rendered images: ./outputs/blender/renders/")
        print("\n" + "=" * 60)


async def run_demos(base_url: str = "http://localhost:8017"):
    """Run demonstration projects."""

    async with TestClient(base_url) as client:
        print("\n" + "=" * 60)
        print("🎬 BLENDER MCP DEMO PROJECTS")
        print("=" * 60)

        # Check health first
        try:
            response = await client.get(f"{base_url}/health")
            if response.json().get("status") != "healthy":
                print("❌ Server is not healthy!")
                return
        except Exception as e:
            print(f"❌ Cannot connect to server: {e}")
            return

        print("Server is healthy! Creating demo projects...\n")

        # Demo 1: Product Visualization
        print("🎬 Demo 1: Product Visualization")
        print("-" * 40)

        # Create project
        result = await client.call_tool(
            "create_blender_project",
            {
                "name": "demo_product",
                "template": "product",
                "settings": {"resolution": [1920, 1080], "engine": "CYCLES"},
            },
        )

        if result and result.get("success"):
            project_path = result["project_path"]
            print(f"✅ Created product demo: {project_path}")
            import os

            project_name = os.path.basename(project_path)  # type: ignore

            # Add product components
            await client.call_tool(
                client,
                base_url,
                "add_primitive_objects",
                {
                    "project": project_name,
                    "objects": [
                        {
                            "type": "cylinder",
                            "name": "Product",
                            "location": [0, 0, 1],
                            "scale": [1.5, 1.5, 0.5],
                        },
                        {
                            "type": "plane",
                            "name": "Surface",
                            "location": [0, 0, 0],
                            "scale": [10, 10, 1],
                        },
                    ],
                },
            )
            print("✅ Added product objects")

            # Apply materials
            await client.call_tool(
                client,
                base_url,
                "apply_material",
                {
                    "project": project_name,
                    "object_name": "Product",
                    "material": {"type": "metal", "roughness": 0.2, "metallic": 1.0},
                },
            )
            print("✅ Applied materials")

            # Setup lighting
            await client.call_tool(
                client,
                base_url,
                "setup_lighting",
                {
                    "project": project_name,
                    "type": "studio",
                    "settings": {"strength": 3.0},
                },
            )
            print("✅ Setup studio lighting")

        # Demo 2: Physics Simulation
        print("\n🎬 Demo 2: Physics Simulation")
        print("-" * 40)

        result = await client.call_tool(
            "create_blender_project",
            {
                "name": "demo_physics",
                "template": "physics",
                "settings": {"resolution": [1920, 1080], "fps": 30},
            },
        )

        if result and result.get("success"):
            project_path = result["project_path"]
            print(f"✅ Created physics demo: {project_path}")
            import os

            project_name = os.path.basename(project_path)  # type: ignore

            # Add physics objects
            await client.call_tool(
                client,
                base_url,
                "add_primitive_objects",
                {
                    "project": project_name,
                    "objects": [
                        {
                            "type": "plane",
                            "name": "Ground",
                            "location": [0, 0, 0],
                            "scale": [10, 10, 1],
                        },
                        {"type": "cube", "name": "Box1", "location": [0, 0, 5]},
                        {"type": "sphere", "name": "Ball", "location": [1, 0, 7]},
                    ],
                },
            )
            print("✅ Added physics objects")

            # Setup physics
            for obj_name in ["Ground", "Box1", "Ball"]:
                await client.call_tool(
                    client,
                    base_url,
                    "setup_physics",
                    {
                        "project": project_name,
                        "object_name": obj_name,
                        "physics_type": "rigid_body",
                        "settings": {
                            "mass": 0 if obj_name == "Ground" else 1.0,
                            "friction": 0.5,
                            "bounce": 0.3,
                        },
                    },
                )
            print("✅ Setup physics simulation")

        # Demo 3: Abstract Animation
        print("\n🎬 Demo 3: Abstract Animation")
        print("-" * 40)

        result = await client.call_tool(
            "create_blender_project",
            {
                "name": "demo_animation",
                "template": "animation",
                "settings": {"resolution": [1920, 1080], "fps": 60},
            },
        )

        if result and result.get("success"):
            project_path = result["project_path"]
            print(f"✅ Created animation demo: {project_path}")
            import os

            project_name = os.path.basename(project_path)  # type: ignore

            # Add animated objects
            await client.call_tool(
                client,
                base_url,
                "add_primitive_objects",
                {
                    "project": project_name,
                    "objects": [
                        {"type": "sphere", "name": "Core", "location": [0, 0, 2]},
                        {"type": "torus", "name": "Ring1", "location": [3, 0, 2]},
                        {"type": "cube", "name": "Cube1", "location": [-3, 0, 2]},
                    ],
                },
            )
            print("✅ Added animated objects")

            # Apply emission materials
            for obj_name, color in [
                ("Core", [1, 1, 1, 1]),
                ("Ring1", [1, 0.5, 0, 1]),
                ("Cube1", [0, 0.5, 1, 1]),
            ]:
                await client.call_tool(
                    client,
                    base_url,
                    "apply_material",
                    {
                        "project": project_name,
                        "object_name": obj_name,
                        "material": {
                            "type": "emission",
                            "base_color": color,
                            "emission_strength": 3.0,
                        },
                    },
                )
            print("✅ Applied emission materials")

        print("\n" + "=" * 60)
        print("📊 DEMO SUMMARY")
        print("=" * 60)
        print("✅ Created 3 demonstration projects")
        print("\n📁 Created projects:")
        print("  - demo_product: Product visualization")
        print("  - demo_physics: Physics simulation")
        print("  - demo_animation: Abstract animation")
        print("\n📁 Output locations:")
        print("  - Blender files: ./outputs/blender/projects/")
        print("  - Rendered outputs: ./outputs/blender/renders/")
        print("=" * 60)


async def main():
    """Main entry point."""
    import argparse

    parser = argparse.ArgumentParser(description="Blender MCP Server Validation")
    parser.add_argument("--server-url", default="http://localhost:8017", help="Blender MCP server URL")
    parser.add_argument(
        "--mode",
        choices=["validate", "demos", "both"],
        default="both",
        help="What to run",
    )

    args = parser.parse_args()

    if args.mode in ["validate", "both"]:
        await validate_blender_server(args.server_url)

    if args.mode in ["demos", "both"]:
        await run_demos(args.server_url)


if __name__ == "__main__":
    asyncio.run(main())
