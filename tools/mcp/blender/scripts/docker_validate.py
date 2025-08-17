#!/usr/bin/env python3
"""Validation script for Blender MCP server running in Docker."""

import asyncio
import sys
from pathlib import Path

# Add parent directories to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from tests.test_utils import TestClient  # noqa: E402


async def wait_for_job_completion(client: TestClient, job_id: str, max_wait: int = 30):
    """Wait for a job to complete using the shared test client."""
    for i in range(max_wait):
        result = await client.call_tool("get_job_status", {"job_id": job_id})

        if "error" in result:
            print(f"Error checking job status: {result['error']}")
            return None

        status = result["result"]["status"]
        print(f"Job {job_id}: {status}")

        if status == "COMPLETED":
            return result["result"]
        elif status == "FAILED":
            print(f"Job failed: {result['result'].get('message', 'Unknown error')}")
            return None

        await asyncio.sleep(1)

    print(f"Job {job_id} timed out")
    return None


async def validate_server():
    """Run validation tests against the Blender MCP server."""
    base_url = "http://localhost:8017"

    async with TestClient(base_url) as client:
        print("=" * 60)
        print("Blender MCP Server Validation")
        print("=" * 60)

        # Test 1: Create a basic scene project
        print("\n1. Creating basic scene project...")
        result = await client.call_tool(
            "create_blender_project",
            {
                "name": "test_basic_scene",
                "template": "basic_scene",
                "settings": {"resolution": [1920, 1080], "fps": 24, "engine": "CYCLES"},
            },
        )

        if "error" not in result:
            print(f"✓ Created project: {result['result']['project_path']}")
            # basic_project = result["result"]["project_path"]  # Store if needed later
            job_id = result["result"]["job_id"]

            # Wait for job to complete
            job_result = await wait_for_job_completion(client, job_id)
            if job_result:
                print("✓ Job completed successfully")
        else:
            print(f"✗ Failed to create project: {result['error']}")
            return

        # Test 2: Create a studio lighting project
        print("\n2. Creating studio lighting project...")
        result = await client.call_tool(
            "create_blender_project",
            {
                "name": "test_studio",
                "template": "studio_lighting",
                "settings": {"resolution": [2560, 1440], "fps": 30, "engine": "EEVEE"},
            },
        )

        if "error" not in result:
            print(f"✓ Created project: {result['result']['project_path']}")
            # studio_project = result["result"]["project_path"]  # Store if needed later
            job_id = result["result"]["job_id"]
            await wait_for_job_completion(client, job_id)
        else:
            print(f"✗ Failed to create project: {result['error']}")

        # Test 3: Add primitive objects
        print("\n3. Adding primitive objects to scene...")
        result = await client.call_tool(
            "add_primitive_objects",
            {
                "project": "test_basic_scene",
                "objects": [
                    {
                        "type": "cube",
                        "name": "TestCube",
                        "location": [0, 0, 1],
                        "rotation": [0, 0, 0.785],
                        "scale": [1, 1, 1],
                    },
                    {
                        "type": "sphere",
                        "name": "TestSphere",
                        "location": [3, 0, 1],
                        "scale": [0.5, 0.5, 0.5],
                    },
                    {
                        "type": "monkey",
                        "name": "Suzanne",
                        "location": [-3, 0, 1],
                        "rotation": [0, 0.785, 0],
                    },
                ],
            },
        )

        if "error" not in result:
            print(f"✓ Added {result['result']['objects_added']} objects")
            job_id = result["result"]["job_id"]
            await wait_for_job_completion(client, job_id)
        else:
            print(f"✗ Failed to add objects: {result['error']}")

        # Test 4: Apply materials
        print("\n4. Applying materials to objects...")
        materials = [
            (
                "TestCube",
                {"type": "metal", "base_color": [0.8, 0.6, 0.2, 1.0], "roughness": 0.3},
            ),
            ("TestSphere", {"type": "glass", "roughness": 0.0}),
            (
                "Suzanne",
                {
                    "type": "emission",
                    "base_color": [0.2, 0.8, 1.0, 1.0],
                    "emission_strength": 2.0,
                },
            ),
        ]

        for obj_name, material in materials:
            result = await client.call_tool(
                "apply_material",
                {
                    "project": "test_basic_scene",
                    "object_name": obj_name,
                    "material": material,
                },
            )

            if "error" not in result:
                print(f"  ✓ Applied {material['type']} material to {obj_name}")
            else:
                print(f"  ✗ Failed to apply material to {obj_name}: {result['error']}")

        # Test 5: Setup physics
        print("\n5. Setting up physics simulation...")
        result = await client.call_tool(
            "setup_physics",
            {
                "project": "test_basic_scene",
                "object_name": "TestCube",
                "physics_type": "rigid_body",
                "settings": {
                    "mass": 5.0,
                    "friction": 0.5,
                    "bounce": 0.3,
                    "collision_shape": "box",
                },
            },
        )

        if "error" not in result:
            print(f"✓ Physics applied: {result['result']['message']}")
        else:
            print(f"✗ Failed to setup physics: {result['error']}")

        # Test 6: Create animation
        print("\n6. Creating keyframe animation...")
        result = await client.call_tool(
            "create_animation",
            {
                "project": "test_basic_scene",
                "object_name": "TestSphere",
                "keyframes": [
                    {"frame": 1, "location": [3, 0, 1]},
                    {"frame": 25, "location": [3, 3, 2]},
                    {"frame": 50, "location": [-3, 3, 1]},
                    {"frame": 75, "location": [-3, -3, 2]},
                    {"frame": 100, "location": [3, -3, 1]},
                    {"frame": 125, "location": [3, 0, 1]},
                ],
                "interpolation": "BEZIER",
            },
        )

        if "error" not in result:
            print(f"✓ Animation created: {result['result']['message']}")
        else:
            print(f"✗ Failed to create animation: {result['error']}")

        # Test 7: List projects
        print("\n7. Listing available projects...")
        result = await client.call_tool("list_projects", {})

        if "error" not in result:
            projects = result["result"]["projects"]
            print(f"✓ Found {result['result']['count']} projects:")
            for project in projects:
                print(f"  - {project}")
        else:
            print(f"✗ Failed to list projects: {result['error']}")

        # Test 8: Render image
        print("\n8. Starting render job...")
        result = await client.call_tool(
            "render_image",
            {
                "project": "test_basic_scene",
                "frame": 1,
                "settings": {
                    "resolution": [1920, 1080],
                    "samples": 64,
                    "engine": "EEVEE",
                    "format": "PNG",
                },
            },
        )

        if "error" not in result:
            print(f"✓ Render job started: {result['result']['job_id']}")
            print(f"  Status endpoint: {result['result']['check_status']}")
        else:
            print(f"✗ Failed to start render: {result['error']}")

        print("\n" + "=" * 60)
        print("Validation complete!")
        print("=" * 60)


if __name__ == "__main__":
    asyncio.run(validate_server())
