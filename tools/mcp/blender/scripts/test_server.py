#!/usr/bin/env python3
"""Test script for Blender MCP Server."""

import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Any, Dict

# Add parent directories to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))
sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent))
sys.path.insert(0, str(Path(__file__).parent.parent))

import asyncio  # noqa: E402

from tools.mcp.blender.tests.test_utils import TestClient  # noqa: E402


class BlenderMCPClient(TestClient):
    """Specialized client for Blender MCP Server using shared test utilities."""

    def __init__(self, base_url: str = "http://localhost:8017"):
        """Initialize Blender MCP client.

        Args:
            base_url: Base URL of the Blender MCP server
        """
        super().__init__(base_url)
        self.projects: Dict[str, str] = {}
        self.jobs: Dict[str, Dict[str, Any]] = {}

    async def health_check(self) -> Dict[str, Any]:  # type: ignore[override]
        """Check server health asynchronously.

        Returns:
            Health check result
        """
        import httpx

        async with httpx.AsyncClient() as client:
            response = await client.get(f"{self.base_url}/health")
            data: Dict[str, Any] = response.json()
            return data

    async def list_tools(self) -> list:  # type: ignore[override]
        """List available tools asynchronously.

        Returns:
            List of available tools
        """
        import httpx

        async with httpx.AsyncClient() as client:
            response = await client.get(f"{self.base_url}/mcp/capabilities")
            data = response.json()
            tools = data.get("capabilities", {}).get("tools", {}).get("list", [])
            return [{"name": tool} for tool in tools]

    async def create_project(self, name: str, template: str = "basic_scene", **settings) -> Dict[str, Any]:
        """Create a new Blender project.

        Args:
            name: Project name
            template: Template to use
            **settings: Additional project settings

        Returns:
            Project creation result
        """
        result = await self.call_tool(
            "create_blender_project",
            {"name": name, "template": template, "settings": settings},
        )

        if result.get("success"):
            self.projects[name] = result["project_path"]
            if "job_id" in result:
                self.jobs[result["job_id"]] = {
                    "type": "create_project",
                    "project": name,
                    "started": datetime.now(),
                }

        return result

    async def render_image(self, project: str, frame: int = 1, wait: bool = False, **settings) -> Dict[str, Any]:
        """Render a single frame.

        Args:
            project: Project name or path
            frame: Frame number to render
            wait: Wait for completion
            **settings: Render settings

        Returns:
            Render job result
        """
        # Resolve project path
        if project in self.projects:
            project_path = self.projects[project]
        else:
            project_path = project

        result = await self.call_tool(
            "render_image",
            {"project": project_path, "frame": frame, "settings": settings},
        )

        if result.get("success") and "job_id" in result:
            self.jobs[result["job_id"]] = {
                "type": "render",
                "project": project,
                "started": datetime.now(),
            }

            if wait:
                return await self.wait_for_job(result["job_id"])

        return result

    async def wait_for_job(self, job_id: str, timeout: int = 300, poll_interval: float = 2) -> Dict[str, Any]:
        """Wait for a job to complete.

        Args:
            job_id: Job ID to wait for
            timeout: Maximum wait time in seconds
            poll_interval: Polling interval in seconds

        Returns:
            Final job result
        """
        start_time = time.time()

        while time.time() - start_time < timeout:
            status = await self.call_tool("get_job_status", {"job_id": job_id})

            if status.get("status") in ["COMPLETED", "FAILED", "CANCELLED"]:
                if status["status"] == "COMPLETED":
                    # Get the full result
                    return await self.call_tool("get_job_result", {"job_id": job_id})
                return status

            # Print progress
            progress = status.get("progress", 0)
            message = status.get("message", "")
            print(f"Job {job_id}: {status['status']} - {progress}% - {message}")

            await asyncio.sleep(poll_interval)

        return {"error": f"Job {job_id} timed out after {timeout} seconds"}

    async def quick_render_demo(self) -> Dict[str, Any]:
        """Quick demo of rendering capabilities."""
        print("\n=== Blender MCP Quick Render Demo ===\n")

        # Create project
        print("1. Creating project...")
        project = await self.create_project("demo_render", "studio_lighting", resolution=[1920, 1080], engine="EEVEE")
        print(f"   Created: {project['project_path']}")

        # Add objects
        print("\n2. Adding objects...")
        objects_result = await self.call_tool(
            "add_primitive_objects",
            {
                "project": project["project_path"],
                "objects": [
                    {
                        "type": "monkey",
                        "name": "Suzanne",
                        "location": [0, 0, 2],
                        "rotation": [0, 0.3, 0],
                    },
                    {
                        "type": "torus",
                        "name": "Torus",
                        "location": [3, 0, 1],
                        "scale": [1.5, 1.5, 1.5],
                    },
                    {
                        "type": "cube",
                        "name": "Cube",
                        "location": [-3, 0, 1],
                        "rotation": [0.5, 0.5, 0.5],
                    },
                ],
            },
        )
        print(f"   Added {objects_result.get('objects_added', 0)} objects")

        # Apply materials
        print("\n3. Applying materials...")
        for obj_name, mat_type in [
            ("Suzanne", "metal"),
            ("Torus", "glass"),
            ("Cube", "emission"),
        ]:
            await self.call_tool(
                "apply_material",
                {
                    "project": project["project_path"],
                    "object_name": obj_name,
                    "material": {
                        "type": mat_type,
                        "roughness": 0.3 if mat_type == "metal" else 0.1,
                    },
                },
            )
            print(f"   Applied {mat_type} to {obj_name}")

        # Render
        print("\n4. Starting render...")
        render_result = await self.render_image("demo_render", frame=1, wait=True, samples=32, engine="EEVEE")

        if "output_path" in render_result:
            print(f"\n✅ Render complete: {render_result['output_path']}")
        else:
            print(f"\n❌ Render failed: {render_result}")

        return render_result

    async def physics_demo(self) -> Dict[str, Any]:
        """Demo of physics simulation."""
        print("\n=== Blender MCP Physics Demo ===\n")

        # Create project
        print("1. Creating physics scene...")
        project = await self.create_project("physics_demo", "physics", resolution=[1280, 720], fps=30)

        # Add falling objects
        print("\n2. Adding objects...")
        await self.call_tool(
            "add_primitive_objects",
            {
                "project": project["project_path"],
                "objects": [
                    {"type": "cube", "name": "Box1", "location": [0, 0, 5]},
                    {"type": "sphere", "name": "Ball1", "location": [1, 0, 7]},
                    {"type": "cube", "name": "Box2", "location": [-1, 0, 9]},
                    {"type": "cylinder", "name": "Cylinder1", "location": [0, 1, 11]},
                ],
            },
        )

        # Setup physics
        print("\n3. Setting up physics...")
        for obj in ["Box1", "Ball1", "Box2", "Cylinder1"]:
            await self.call_tool(
                "setup_physics",
                {
                    "project": project["project_path"],
                    "object_name": obj,
                    "physics_type": "rigid_body",
                    "settings": {"mass": 1.0, "friction": 0.5, "bounce": 0.3},
                },
            )
            print(f"   Physics enabled for {obj}")

        # Bake simulation
        print("\n4. Baking simulation...")
        bake_result = await self.call_tool(
            "bake_simulation",
            {"project": project["project_path"], "start_frame": 1, "end_frame": 120},
        )

        if "job_id" in bake_result:
            await self.wait_for_job(bake_result["job_id"])

        print("\n✅ Physics simulation ready!")
        return bake_result

    async def animation_demo(self) -> Dict[str, Any]:
        """Demo of animation capabilities."""
        print("\n=== Blender MCP Animation Demo ===\n")

        # Create project
        print("1. Creating animation scene...")
        project = await self.create_project("animation_demo", "animation")

        # Add object to animate
        print("\n2. Adding object...")
        await self.call_tool(
            "add_primitive_objects",
            {
                "project": project["project_path"],
                "objects": [{"type": "cube", "name": "AnimCube", "location": [0, 0, 2]}],
            },
        )

        # Create animation
        print("\n3. Creating keyframe animation...")
        anim_result = await self.call_tool(
            "create_animation",
            {
                "project": project["project_path"],
                "object_name": "AnimCube",
                "keyframes": [
                    {"frame": 1, "location": [0, 0, 2], "rotation": [0, 0, 0]},
                    {"frame": 30, "location": [5, 0, 2], "rotation": [0, 1.57, 0]},
                    {"frame": 60, "location": [5, 5, 2], "rotation": [0, 3.14, 0]},
                    {"frame": 90, "location": [0, 5, 2], "rotation": [0, 4.71, 0]},
                    {"frame": 120, "location": [0, 0, 2], "rotation": [0, 6.28, 0]},
                ],
                "interpolation": "BEZIER",
            },
        )
        print(f"   Created animation with {anim_result.get('keyframes_count', 0)} keyframes")

        print("\n✅ Animation created!")
        return anim_result

    async def geometry_nodes_demo(self) -> Dict[str, Any]:
        """Demo of geometry nodes."""
        print("\n=== Blender MCP Geometry Nodes Demo ===\n")

        # Create project
        print("1. Creating procedural scene...")
        project = await self.create_project("geometry_demo", "procedural")

        # Add base object
        print("\n2. Adding base object...")
        await self.call_tool(
            "add_primitive_objects",
            {
                "project": project["project_path"],
                "objects": [{"type": "plane", "name": "ScatterPlane", "scale": [10, 10, 1]}],
            },
        )

        # Apply geometry nodes
        print("\n3. Creating procedural scatter...")
        geo_result = await self.call_tool(
            "create_geometry_nodes",
            {
                "project": project["project_path"],
                "object_name": "ScatterPlane",
                "node_setup": "scatter",
                "parameters": {"count": 200, "seed": 42, "scale_variance": 0.3},
            },
        )
        print(f"   Applied {geo_result.get('node_setup')} geometry nodes")

        print("\n✅ Procedural geometry created!")
        return geo_result


async def test_server_connection():
    """Test basic server connection."""
    print("Testing Blender MCP Server connection...")

    client = BlenderMCPClient()

    # Test health endpoint
    try:
        health = await client.health_check()
        print(f"✅ Server is healthy: {health}")
    except Exception as e:
        print(f"❌ Server connection failed: {e}")
        return False

    # Test listing tools
    try:
        tools = await client.list_tools()
        print(f"✅ Found {len(tools)} tools")

        # List some tool names
        tool_names = [tool["name"] for tool in tools[:5]]
        print(f"   Sample tools: {', '.join(tool_names)}...")
    except Exception as e:
        print(f"❌ Failed to list tools: {e}")
        return False

    return True


async def run_selected_demo(demo_type: str):
    """Run a selected demo.

    Args:
        demo_type: Type of demo to run
    """
    client = BlenderMCPClient()

    if demo_type == "render":
        await client.quick_render_demo()
    elif demo_type == "physics":
        await client.physics_demo()
    elif demo_type == "animation":
        await client.animation_demo()
    elif demo_type == "geometry":
        await client.geometry_nodes_demo()
    elif demo_type == "all":
        # Run all demos
        await client.quick_render_demo()
        await client.physics_demo()
        await client.animation_demo()
        await client.geometry_nodes_demo()
    else:
        print(f"Unknown demo type: {demo_type}")
        print("Available demos: render, physics, animation, geometry, all")


async def interactive_mode():
    """Interactive testing mode."""
    client = BlenderMCPClient()

    print("\n=== Blender MCP Interactive Mode ===")
    print("Commands:")
    print("  projects - List projects")
    print("  jobs - List jobs")
    print("  create <name> - Create project")
    print("  render <project> - Render project")
    print("  status <job_id> - Check job status")
    print("  demo <type> - Run demo (render/physics/animation/geometry)")
    print("  exit - Exit")

    while True:
        try:
            command = input("\n> ").strip().split()

            if not command:
                continue

            cmd = command[0].lower()

            if cmd == "exit":
                break

            elif cmd == "projects":
                if client.projects:
                    for name, path in client.projects.items():
                        print(f"  {name}: {path}")
                else:
                    print("No projects created yet")

            elif cmd == "jobs":
                if client.jobs:
                    for job_id, info in client.jobs.items():
                        print(f"  {job_id}: {info['type']} - {info['project']}")
                else:
                    print("No jobs running")

            elif cmd == "create" and len(command) > 1:
                name = command[1]
                template = command[2] if len(command) > 2 else "basic_scene"
                result = await client.create_project(name, template)
                print(f"Created: {result.get('project_path', 'ERROR')}")

            elif cmd == "render" and len(command) > 1:
                project = command[1]
                result = await client.render_image(project, wait=False)
                if "job_id" in result:
                    print(f"Render started: {result['job_id']}")
                else:
                    print(f"Error: {result}")

            elif cmd == "status" and len(command) > 1:
                job_id = command[1]
                status = await client.call_tool("get_job_status", {"job_id": job_id})
                print(f"Status: {status.get('status')} ({status.get('progress', 0)}%)")

            elif cmd == "demo" and len(command) > 1:
                await run_selected_demo(command[1])

            else:
                print("Unknown command or missing arguments")

        except KeyboardInterrupt:
            print("\nUse 'exit' to quit")
        except Exception as e:
            print(f"Error: {e}")

    print("\nGoodbye!")


async def main():
    """Main entry point."""
    import argparse

    parser = argparse.ArgumentParser(description="Test Blender MCP Server")
    parser.add_argument(
        "--demo",
        choices=["render", "physics", "animation", "geometry", "all"],
        help="Run a specific demo",
    )
    parser.add_argument("--interactive", action="store_true", help="Start interactive mode")
    parser.add_argument("--url", default="http://localhost:8017", help="Blender MCP server URL")

    args = parser.parse_args()

    # Test connection first
    if not await test_server_connection():
        print("\n⚠️  Server not available. Please start the server with:")
        print("  docker-compose up -d mcp-blender")
        print("  OR")
        print("  python -m tools.mcp.blender.server")
        sys.exit(1)

    print()

    if args.interactive:
        await interactive_mode()
    elif args.demo:
        await run_selected_demo(args.demo)
    else:
        # Default: run quick render demo
        client = BlenderMCPClient(args.url)
        await client.quick_render_demo()


if __name__ == "__main__":
    asyncio.run(main())
