#!/usr/bin/env python3
"""Create demo projects showcasing Blender MCP capabilities."""

import asyncio
from typing import Any, Dict

import httpx


class BlenderDemoCreator:
    """Create demo projects with the Blender MCP server."""

    def __init__(self, base_url: str = "http://localhost:8017"):
        self.base_url = base_url

    async def call_tool(self, tool: str, arguments: Dict[str, Any]) -> Dict[str, Any]:
        """Call a Blender MCP tool."""
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(f"{self.base_url}/mcp/execute", json={"tool": tool, "arguments": arguments})
            data: Dict[str, Any] = response.json()
            return data

    async def wait_for_job(self, job_id: str, max_attempts: int = 30) -> str:
        """Wait for a job to complete."""
        for _ in range(max_attempts):
            result = await self.call_tool("get_job_status", {"job_id": job_id})
            status = result["result"]["status"]
            if status in ["COMPLETED", "FAILED"]:
                return str(status)
            await asyncio.sleep(2)
        return "TIMEOUT"

    async def create_abstract_art(self):
        """Create an abstract art scene with colorful geometric shapes."""
        print("🎨 Creating Abstract Art Scene...")

        # Create project
        result = await self.call_tool(
            "create_blender_project",
            {
                "name": "abstract_art",
                "template": "empty",
                "settings": {"resolution": [2560, 1440], "fps": 30, "engine": "CYCLES"},
            },
        )
        project = result["result"]["project_path"]

        # Add geometric objects in artistic arrangement
        objects = []
        import random

        random.seed(42)

        # Create a grid of objects with variations
        for x in range(-3, 4, 2):
            for y in range(-3, 4, 2):
                obj_type = random.choice(["cube", "sphere", "cylinder", "torus", "cone"])
                z = random.uniform(0.5, 3)
                rotation = [random.uniform(0, 6.28) for _ in range(3)]
                scale_factor = random.uniform(0.5, 1.5)
                scale = [scale_factor] * 3

                objects.append(
                    {
                        "type": obj_type,
                        "name": f"{obj_type}_{x}_{y}",
                        "location": [x + random.uniform(-0.5, 0.5), y + random.uniform(-0.5, 0.5), z],
                        "rotation": rotation,
                        "scale": scale,
                    }
                )

        await self.call_tool("add_primitive_objects", {"project": project, "objects": objects})

        # Apply random materials
        materials = ["metal", "glass", "emission", "plastic"]
        for obj in objects:
            material = random.choice(materials)
            color = [random.random() for _ in range(3)] + [1.0]

            mat_settings = {
                "type": material,
                "base_color": color,
                "roughness": random.uniform(0.1, 0.9),
                "metallic": 1.0 if material == "metal" else 0.0,
            }

            if material == "emission":
                mat_settings["emission_strength"] = random.uniform(1, 5)

            await self.call_tool("apply_material", {"project": project, "object_name": obj["name"], "material": mat_settings})

        # Setup artistic lighting
        await self.call_tool("setup_lighting", {"project": project, "type": "studio", "settings": {"strength": 0.5}})

        print("✅ Abstract Art Scene created!")
        return project

    async def create_physics_simulation(self):
        """Create a physics simulation with falling dominoes."""
        print("🎱 Creating Physics Simulation...")

        # Create project
        result = await self.call_tool(
            "create_blender_project",
            {
                "name": "domino_physics",
                "template": "basic_scene",
                "settings": {"resolution": [1920, 1080], "fps": 60, "engine": "BLENDER_EEVEE"},
            },
        )
        project = result["result"]["project_path"]

        # Create dominoes in a line
        dominoes = []
        for i in range(20):
            dominoes.append({"type": "cube", "name": f"domino_{i}", "location": [i * 0.8, 0, 1], "scale": [0.2, 1, 2]})

        # Add a ball to knock them over
        dominoes.append({"type": "sphere", "name": "ball", "location": [-2, 0, 3], "scale": [0.5, 0.5, 0.5]})

        await self.call_tool("add_primitive_objects", {"project": project, "objects": dominoes})

        # Setup physics for all objects
        for domino in dominoes[:-1]:  # All dominoes
            await self.call_tool(
                "setup_physics",
                {
                    "project": project,
                    "object_name": domino["name"],
                    "physics_type": "rigid_body",
                    "settings": {"mass": 0.5, "friction": 0.8, "bounce": 0.1, "collision_shape": "box"},
                },
            )

        # Ball physics with initial velocity
        await self.call_tool(
            "setup_physics",
            {
                "project": project,
                "object_name": "ball",
                "physics_type": "rigid_body",
                "settings": {"mass": 2.0, "friction": 0.5, "bounce": 0.3, "collision_shape": "sphere"},
            },
        )

        # Create animation for the ball
        await self.call_tool(
            "create_animation",
            {
                "project": project,
                "object_name": "ball",
                "keyframes": [
                    {"frame": 1, "location": [-2, 0, 3]},
                    {"frame": 30, "location": [0, 0, 1.5]},  # Hit first domino
                ],
                "interpolation": "LINEAR",
            },
        )

        print("✅ Physics Simulation created!")
        return project

    async def create_architectural_viz(self):
        """Create a simple architectural visualization."""
        print("🏗️ Creating Architectural Visualization...")

        # Create project
        result = await self.call_tool(
            "create_blender_project",
            {"name": "arch_viz", "template": "empty", "settings": {"resolution": [3840, 2160], "fps": 24, "engine": "CYCLES"}},
        )
        project = result["result"]["project_path"]

        # Create building structure
        structure = [
            # Floor
            {"type": "cube", "name": "floor", "location": [0, 0, -0.1], "scale": [10, 10, 0.1]},
            # Walls
            {"type": "cube", "name": "wall_back", "location": [0, 5, 2.5], "scale": [10, 0.1, 2.5]},
            {"type": "cube", "name": "wall_left", "location": [-5, 0, 2.5], "scale": [0.1, 10, 2.5]},
            {"type": "cube", "name": "wall_right", "location": [5, 0, 2.5], "scale": [0.1, 10, 2.5]},
            # Ceiling with opening for skylight
            {"type": "cube", "name": "ceiling", "location": [0, 0, 5.1], "scale": [10, 10, 0.1]},
            # Furniture
            {"type": "cube", "name": "table", "location": [0, 0, 0.75], "scale": [2, 1, 0.05]},
            {"type": "cube", "name": "chair1", "location": [-1, 0, 0.5], "scale": [0.4, 0.4, 1]},
            {"type": "cube", "name": "chair2", "location": [1, 0, 0.5], "scale": [0.4, 0.4, 1]},
        ]

        await self.call_tool("add_primitive_objects", {"project": project, "objects": structure})

        # Apply materials
        await self.call_tool(
            "apply_material",
            {
                "project": project,
                "object_name": "floor",
                "material": {"type": "wood", "base_color": [0.4, 0.2, 0.1, 1.0], "roughness": 0.7},
            },
        )

        await self.call_tool(
            "apply_material",
            {
                "project": project,
                "object_name": "table",
                "material": {"type": "metal", "base_color": [0.8, 0.8, 0.8, 1.0], "metallic": 0.9, "roughness": 0.2},
            },
        )

        # Natural lighting
        await self.call_tool("setup_lighting", {"project": project, "type": "sun", "settings": {"strength": 5.0}})

        print("✅ Architectural Visualization created!")
        return project

    async def create_animated_logo(self):
        """Create an animated logo/text."""
        print("🎬 Creating Animated Logo...")

        # Create project
        result = await self.call_tool(
            "create_blender_project",
            {
                "name": "animated_logo",
                "template": "empty",
                "settings": {"resolution": [1920, 1080], "fps": 30, "engine": "BLENDER_EEVEE"},
            },
        )
        project = result["result"]["project_path"]

        # Create logo elements
        elements = []
        for i in range(3):
            elements.append(
                {"type": "torus", "name": f"ring_{i}", "location": [0, 0, 0], "scale": [1 + i * 0.3, 1 + i * 0.3, 0.2]}
            )

        # Add central sphere
        elements.append({"type": "sphere", "name": "core", "location": [0, 0, 0], "scale": [0.5, 0.5, 0.5]})

        await self.call_tool("add_primitive_objects", {"project": project, "objects": elements})

        # Apply glowing materials
        for i in range(3):
            await self.call_tool(
                "apply_material",
                {
                    "project": project,
                    "object_name": f"ring_{i}",
                    "material": {"type": "emission", "base_color": [0, 0.5 + i * 0.2, 1, 1], "emission_strength": 2 + i},
                },
            )

        await self.call_tool(
            "apply_material",
            {
                "project": project,
                "object_name": "core",
                "material": {"type": "emission", "base_color": [1, 1, 1, 1], "emission_strength": 5},
            },
        )

        # Animate the rings
        for i in range(3):
            keyframes = []
            for frame in range(0, 121, 30):
                rotation = [0, 0, frame * 0.1 * (i + 1)]
                keyframes.append({"frame": frame, "rotation": rotation})

            await self.call_tool(
                "create_animation",
                {"project": project, "object_name": f"ring_{i}", "keyframes": keyframes, "interpolation": "LINEAR"},
            )

        # Animate core pulsing
        keyframes = []
        for frame in range(0, 121, 15):
            scale = 0.5 + 0.1 * (1 if (frame // 15) % 2 == 0 else -1)
            keyframes.append({"frame": frame, "scale": [scale, scale, scale]})

        await self.call_tool(
            "create_animation", {"project": project, "object_name": "core", "keyframes": keyframes, "interpolation": "BEZIER"}
        )

        print("✅ Animated Logo created!")
        return project

    async def create_procedural_landscape(self):
        """Create a procedural landscape with geometry nodes."""
        print("🏔️ Creating Procedural Landscape...")

        # Create project
        result = await self.call_tool(
            "create_blender_project",
            {
                "name": "procedural_landscape",
                "template": "basic_scene",
                "settings": {"resolution": [2560, 1440], "fps": 24, "engine": "CYCLES"},
            },
        )
        project = result["result"]["project_path"]

        # Create base terrain
        await self.call_tool(
            "add_primitive_objects",
            {"project": project, "objects": [{"type": "plane", "name": "terrain", "scale": [20, 20, 1]}]},
        )

        # Apply procedural displacement
        await self.call_tool(
            "create_geometry_nodes",
            {
                "project": project,
                "object_name": "terrain",
                "node_setup": "scatter",
                "parameters": {"count": 500, "seed": 12345, "scale_variance": 0.5},
            },
        )

        # Add scattered rocks
        await self.call_tool(
            "add_primitive_objects",
            {
                "project": project,
                "objects": [{"type": "sphere", "name": "rock_base", "location": [0, 0, -10], "scale": [0.3, 0.3, 0.3]}],
            },
        )

        # Natural outdoor lighting
        await self.call_tool(
            "setup_lighting", {"project": project, "type": "sun", "settings": {"strength": 3.0, "color": [1, 0.95, 0.8]}}
        )

        print("✅ Procedural Landscape created!")
        return project

    async def create_all_demos(self):
        """Create all demo projects."""
        print("\n🚀 Creating All Demo Projects\n")

        demos = [
            ("Abstract Art", self.create_abstract_art),
            ("Physics Simulation", self.create_physics_simulation),
            ("Architectural Viz", self.create_architectural_viz),
            ("Animated Logo", self.create_animated_logo),
            ("Procedural Landscape", self.create_procedural_landscape),
        ]

        results = []
        for name, create_func in demos:
            try:
                project = await create_func()
                results.append((name, project, "✅ Success"))
            except Exception as e:
                results.append((name, None, f"❌ Failed: {e}"))
                print(f"Error creating {name}: {e}")

        print("\n📊 Summary:")
        for name, project, status in results:
            print(f"  {name}: {status}")
            if project:
                print(f"     Project: {project}")

        return results


async def main():
    """Main entry point."""
    creator = BlenderDemoCreator()

    # Check server health
    async with httpx.AsyncClient() as client:
        try:
            response = await client.get("http://localhost:8017/health")
            if response.status_code != 200:
                print("❌ Blender MCP server not responding")
                return
        except Exception as e:
            print(f"❌ Cannot connect to server: {e}")
            return

    # Create all demos
    await creator.create_all_demos()

    print("\n✨ All demos created! You can now render them using the render tools.")


if __name__ == "__main__":
    asyncio.run(main())
