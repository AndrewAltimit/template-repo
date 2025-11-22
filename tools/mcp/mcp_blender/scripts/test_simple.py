#!/usr/bin/env python3
"""Simple test for Blender MCP Server."""
import asyncio
import json

import httpx


async def test_blender_server():
    """Test Blender MCP server basic functionality."""
    base_url = "http://localhost:8017"

    async with httpx.AsyncClient() as client:
        # Test health check
        print("Testing health check...")
        health = await client.get(f"{base_url}/health")
        print(f"Health: {health.json()}")

        # Test MCP capabilities
        print("\nTesting MCP capabilities...")
        caps = await client.get(f"{base_url}/mcp/capabilities")
        print(f"Capabilities: {json.dumps(caps.json(), indent=2)[:200]}...")

        # Create a test project via MCP execute endpoint
        print("\nCreating test project...")
        create_req = {
            "tool": "create_blender_project",
            "arguments": {
                "name": "test_scene",
                "template": "basic_scene",
                "settings": {"resolution": [1920, 1080], "fps": 24, "engine": "BLENDER_EEVEE"},
            },
        }

        result = await client.post(f"{base_url}/mcp/execute", json=create_req)
        print(f"Create result: {result.json()}")

        if result.json().get("success"):
            project_path = result.json()["result"]["project_path"]

            # Add some objects
            print("\nAdding objects...")
            add_req = {
                "tool": "add_primitive_objects",
                "arguments": {
                    "project": project_path,
                    "objects": [
                        {"type": "monkey", "name": "Suzanne", "location": [0, 0, 2], "rotation": [0, 0.3, 0]},
                        {"type": "torus", "name": "Torus", "location": [3, 0, 1], "scale": [1.5, 1.5, 1.5]},
                    ],
                },
            }

            add_result = await client.post(f"{base_url}/mcp/execute", json=add_req)
            print(f"Add objects result: {add_result.json()}")

            # Apply materials
            print("\nApplying materials...")
            mat_req = {
                "tool": "apply_material",
                "arguments": {
                    "project": project_path,
                    "object_name": "Suzanne",
                    "material": {"type": "metal", "roughness": 0.3},
                },
            }

            mat_result = await client.post(f"{base_url}/mcp/execute", json=mat_req)
            print(f"Material result: {mat_result.json()}")

            # Start a render
            print("\nStarting render...")
            render_req = {
                "tool": "render_image",
                "arguments": {"project": project_path, "frame": 1, "settings": {"samples": 32, "engine": "BLENDER_EEVEE"}},
            }

            render_result = await client.post(f"{base_url}/mcp/execute", json=render_req)
            print(f"Render result: {render_result.json()}")

            # Check job status if render started
            if render_result.json().get("success") and "job_id" in render_result.json()["result"]:
                job_id = render_result.json()["result"]["job_id"]

                print(f"\nChecking job status for {job_id}...")
                for _ in range(10):
                    await asyncio.sleep(2)
                    status_req = {"tool": "get_job_status", "arguments": {"job_id": job_id}}

                    status_result = await client.post(f"{base_url}/mcp/execute", json=status_req)
                    status = status_result.json()["result"]
                    print(f"Job status: {status.get('status')} - {status.get('progress', 0)}%")

                    if status.get("status") in ["COMPLETED", "FAILED"]:
                        break

                # Get final result if completed
                if status.get("status") == "COMPLETED":
                    result_req = {"tool": "get_job_result", "arguments": {"job_id": job_id}}
                    final_result = await client.post(f"{base_url}/mcp/execute", json=result_req)
                    print(f"\nFinal result: {final_result.json()}")

        print("\n✅ Test complete!")


if __name__ == "__main__":
    asyncio.run(test_blender_server())
