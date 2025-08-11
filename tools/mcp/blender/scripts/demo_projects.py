#!/usr/bin/env python3
"""Demo projects showcasing Blender MCP Server capabilities.

This script creates various demonstration projects that highlight
different features of the Blender MCP server.
"""

import asyncio
import sys
from pathlib import Path
from typing import Any, Dict

# Add parent directories to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))
sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent))

try:
    from tools.mcp.core.client import MCPClient
except ImportError:
    # Try alternative import for Docker environment
    sys.path.insert(0, "/app")
    from core.client import MCPClient


class BlenderDemoProjects:
    """Create demonstration projects for Blender MCP Server."""

    def __init__(self, base_url: str = "http://localhost:8017"):
        self.client = MCPClient(base_url)
        self.demos_created = []

    async def demo_1_product_visualization(self):
        """Demo 1: Product Visualization - Luxury Watch.

        Creates a high-quality product shot with studio lighting,
        reflective materials, and professional rendering settings.
        """
        print("\n🎬 Demo 1: Product Visualization - Luxury Watch")
        print("-" * 50)

        # Create project with studio lighting template
        project = await self.client.call_tool(
            "create_blender_project",
            {"name": "demo_luxury_watch", "template": "product", "settings": {"resolution": [2560, 1440], "engine": "CYCLES"}},
        )

        if not project.get("success"):
            print(f"❌ Failed to create project: {project.get('error')}")
            return

        project_path = project["project_path"]
        self.demos_created.append(("Product Visualization", project_path))
        print(f"✅ Created project: {project_path}")

        # Add watch components
        print("  Adding watch components...")
        await self.client.call_tool(
            "add_primitive_objects",
            {
                "project": project_path,
                "objects": [
                    # Watch face
                    {"type": "cylinder", "name": "WatchFace", "location": [0, 0, 0.5], "scale": [2, 2, 0.1]},
                    # Watch band
                    {"type": "torus", "name": "WatchBand", "location": [0, 0, 0.5], "scale": [2.2, 2.2, 0.3]},
                    # Crown
                    {
                        "type": "cylinder",
                        "name": "Crown",
                        "location": [2.3, 0, 0.5],
                        "scale": [0.15, 0.15, 0.3],
                        "rotation": [0, 1.57, 0],
                    },
                    # Display surface
                    {"type": "plane", "name": "Display", "location": [0, 0, 0], "scale": [8, 8, 1]},
                ],
            },
        )

        # Apply luxury materials
        print("  Applying luxury materials...")
        materials = [
            (
                "WatchFace",
                {"type": "metal", "base_color": [0.95, 0.85, 0.6, 1.0], "metallic": 1.0, "roughness": 0.1},  # Gold color
            ),
            ("WatchBand", {"type": "principled", "base_color": [0.1, 0.05, 0.02, 1.0], "roughness": 0.7}),  # Dark leather
            ("Crown", {"type": "metal", "base_color": [0.95, 0.85, 0.6, 1.0], "metallic": 1.0, "roughness": 0.15}),  # Gold
            ("Display", {"type": "principled", "base_color": [0.9, 0.9, 0.9, 1.0], "roughness": 0.3}),  # Light grey
        ]

        for obj_name, material in materials:
            await self.client.call_tool(
                "apply_material", {"project": project_path, "object_name": obj_name, "material": material}
            )

        # Setup professional studio lighting
        print("  Setting up studio lighting...")
        await self.client.call_tool(
            "setup_lighting",
            {"project": project_path, "type": "studio", "settings": {"strength": 3.0, "color": [1, 0.98, 0.95]}},
        )

        # Render high-quality image
        print("  Rendering product shot...")
        render_result = await self.client.call_tool(
            "render_image",
            {
                "project": project_path,
                "frame": 1,
                "settings": {"resolution": [2560, 1440], "samples": 256, "engine": "CYCLES", "format": "PNG"},
            },
        )

        print(f"✅ Demo 1 complete! Output: {render_result.get('output_path', 'pending')}")

    async def demo_2_physics_dominos(self):
        """Demo 2: Physics Simulation - Domino Chain Reaction.

        Creates a physics simulation with falling dominos
        demonstrating rigid body dynamics.
        """
        print("\n🎬 Demo 2: Physics Simulation - Domino Chain")
        print("-" * 50)

        # Create project
        project = await self.client.call_tool(
            "create_blender_project",
            {
                "name": "demo_domino_physics",
                "template": "physics",
                "settings": {"resolution": [1920, 1080], "fps": 30, "engine": "EEVEE"},
            },
        )

        if not project.get("success"):
            print(f"❌ Failed to create project: {project.get('error')}")
            return

        project_path = project["project_path"]
        self.demos_created.append(("Physics Dominos", project_path))
        print(f"✅ Created project: {project_path}")

        # Create ground
        print("  Creating ground...")
        await self.client.call_tool(
            "add_primitive_objects",
            {
                "project": project_path,
                "objects": [{"type": "plane", "name": "Ground", "location": [0, 0, 0], "scale": [20, 20, 1]}],
            },
        )

        # Create dominos in a curved line
        print("  Creating domino chain...")
        dominos = []
        num_dominos = 20

        for i in range(num_dominos):
            angle = i * 0.15  # Curve angle
            x = i * 0.8
            y = angle**2 * 0.5  # Parabolic curve

            dominos.append(
                {
                    "type": "cube",
                    "name": f"Domino_{i:02d}",
                    "location": [x - 8, y, 1],
                    "scale": [0.2, 0.8, 2],
                    "rotation": [0, 0, angle],
                }
            )

        # Add trigger ball
        dominos.append({"type": "sphere", "name": "TriggerBall", "location": [-9, 0, 3], "scale": [0.5, 0.5, 0.5]})

        await self.client.call_tool("add_primitive_objects", {"project": project_path, "objects": dominos})

        # Setup physics for ground (static)
        print("  Setting up physics...")
        await self.client.call_tool(
            "setup_physics",
            {
                "project": project_path,
                "object_name": "Ground",
                "physics_type": "rigid_body",
                "settings": {"mass": 0, "friction": 0.8},  # Static
            },
        )

        # Setup physics for dominos
        for i in range(num_dominos):
            await self.client.call_tool(
                "setup_physics",
                {
                    "project": project_path,
                    "object_name": f"Domino_{i:02d}",
                    "physics_type": "rigid_body",
                    "settings": {"mass": 0.5, "friction": 0.5, "bounce": 0.1, "collision_shape": "box"},
                },
            )

        # Setup physics for trigger ball
        await self.client.call_tool(
            "setup_physics",
            {
                "project": project_path,
                "object_name": "TriggerBall",
                "physics_type": "rigid_body",
                "settings": {"mass": 2.0, "friction": 0.3, "bounce": 0.3, "collision_shape": "sphere"},
            },
        )

        # Apply colorful materials
        print("  Applying materials...")
        for i in range(num_dominos):
            hue = i / num_dominos
            await self.client.call_tool(
                "apply_material",
                {
                    "project": project_path,
                    "object_name": f"Domino_{i:02d}",
                    "material": {"type": "principled", "base_color": [hue, 1.0 - hue * 0.5, 1.0 - hue, 1.0], "roughness": 0.4},
                },
            )

        # Bake simulation
        print("  Baking physics simulation...")
        await self.client.call_tool("bake_simulation", {"project": project_path, "start_frame": 1, "end_frame": 150})

        # Render animation
        print("  Rendering animation...")
        render_result = await self.client.call_tool(
            "render_animation",
            {
                "project": project_path,
                "start_frame": 1,
                "end_frame": 150,
                "settings": {"resolution": [1920, 1080], "samples": 32, "engine": "EEVEE", "format": "MP4"},
            },
        )

        print(f"✅ Demo 2 complete! Animation: {render_result.get('output_path', 'pending')}")

    async def demo_3_abstract_animation(self):
        """Demo 3: Abstract Animation - Geometric Dance.

        Creates an abstract animation with rotating and scaling
        geometric shapes, emission materials, and color transitions.
        """
        print("\n🎬 Demo 3: Abstract Animation - Geometric Dance")
        print("-" * 50)

        # Create project
        project = await self.client.call_tool(
            "create_blender_project",
            {
                "name": "demo_geometric_dance",
                "template": "animation",
                "settings": {"resolution": [1920, 1080], "fps": 60, "engine": "EEVEE"},
            },
        )

        if not project.get("success"):
            print(f"❌ Failed to create project: {project.get('error')}")
            return

        project_path = project["project_path"]
        self.demos_created.append(("Abstract Animation", project_path))
        print(f"✅ Created project: {project_path}")

        # Create geometric shapes in a circle
        print("  Creating geometric shapes...")
        shapes = []
        shape_types = ["cube", "sphere", "cylinder", "cone", "torus", "monkey"]
        radius = 4

        for i, shape_type in enumerate(shape_types):
            angle = (i / len(shape_types)) * 6.28318  # 2*pi
            x = radius * __import__("math").cos(angle)
            y = radius * __import__("math").sin(angle)

            shapes.append({"type": shape_type, "name": f"Shape_{shape_type}", "location": [x, y, 2], "scale": [1, 1, 1]})

        # Add central emissive sphere
        shapes.append({"type": "sphere", "name": "CentralCore", "location": [0, 0, 2], "scale": [1.5, 1.5, 1.5]})

        await self.client.call_tool("add_primitive_objects", {"project": project_path, "objects": shapes})

        # Apply emission materials with different colors
        print("  Applying emission materials...")
        colors = [
            [1.0, 0.2, 0.2, 1.0],  # Red
            [0.2, 1.0, 0.2, 1.0],  # Green
            [0.2, 0.2, 1.0, 1.0],  # Blue
            [1.0, 1.0, 0.2, 1.0],  # Yellow
            [1.0, 0.2, 1.0, 1.0],  # Magenta
            [0.2, 1.0, 1.0, 1.0],  # Cyan
        ]

        for i, shape_type in enumerate(shape_types):
            await self.client.call_tool(
                "apply_material",
                {
                    "project": project_path,
                    "object_name": f"Shape_{shape_type}",
                    "material": {"type": "emission", "base_color": colors[i], "emission_strength": 2.0},
                },
            )

        # Central core with pulsing white emission
        await self.client.call_tool(
            "apply_material",
            {
                "project": project_path,
                "object_name": "CentralCore",
                "material": {"type": "emission", "base_color": [1.0, 1.0, 1.0, 1.0], "emission_strength": 5.0},
            },
        )

        # Create complex animations
        print("  Creating animations...")

        # Rotating shapes around center
        for i, shape_type in enumerate(shape_types):
            keyframes = []
            for frame in range(0, 241, 60):  # 0, 60, 120, 180, 240
                angle = (i / len(shape_types) + frame / 60) * 6.28318
                x = radius * __import__("math").cos(angle)
                y = radius * __import__("math").sin(angle)
                z = 2 + __import__("math").sin(frame / 30) * 0.5

                keyframes.append({"frame": frame, "value": [x, y, z]})

            await self.client.call_tool(
                "create_animation",
                {
                    "project": project_path,
                    "object_name": f"Shape_{shape_type}",
                    "property_path": "location",
                    "keyframes": keyframes,
                },
            )

            # Rotation animation
            await self.client.call_tool(
                "create_animation",
                {
                    "project": project_path,
                    "object_name": f"Shape_{shape_type}",
                    "property_path": "rotation",
                    "keyframes": [{"frame": 1, "value": [0, 0, 0]}, {"frame": 240, "value": [6.28318, 6.28318, 6.28318]}],
                },
            )

        # Pulsing scale for central core
        await self.client.call_tool(
            "create_animation",
            {
                "project": project_path,
                "object_name": "CentralCore",
                "property_path": "scale",
                "keyframes": [
                    {"frame": 1, "value": [1.5, 1.5, 1.5]},
                    {"frame": 30, "value": [2.0, 2.0, 2.0]},
                    {"frame": 60, "value": [1.5, 1.5, 1.5]},
                    {"frame": 90, "value": [2.0, 2.0, 2.0]},
                    {"frame": 120, "value": [1.5, 1.5, 1.5]},
                    {"frame": 150, "value": [2.0, 2.0, 2.0]},
                    {"frame": 180, "value": [1.5, 1.5, 1.5]},
                    {"frame": 210, "value": [2.0, 2.0, 2.0]},
                    {"frame": 240, "value": [1.5, 1.5, 1.5]},
                ],
            },
        )

        # Render animation
        print("  Rendering animation...")
        render_result = await self.client.call_tool(
            "render_animation",
            {
                "project": project_path,
                "start_frame": 1,
                "end_frame": 240,
                "settings": {"resolution": [1920, 1080], "samples": 64, "engine": "EEVEE", "format": "MP4"},
            },
        )

        print(f"✅ Demo 3 complete! Animation: {render_result.get('output_path', 'pending')}")

    async def demo_4_architectural_viz(self):
        """Demo 4: Architectural Visualization - Modern House.

        Creates a simple modern house with realistic materials
        and outdoor lighting.
        """
        print("\n🎬 Demo 4: Architectural Visualization - Modern House")
        print("-" * 50)

        # Create project
        project = await self.client.call_tool(
            "create_blender_project",
            {
                "name": "demo_modern_house",
                "template": "architectural",
                "settings": {"resolution": [2560, 1440], "engine": "CYCLES"},
            },
        )

        if not project.get("success"):
            print(f"❌ Failed to create project: {project.get('error')}")
            return

        project_path = project["project_path"]
        self.demos_created.append(("Architectural Viz", project_path))
        print(f"✅ Created project: {project_path}")

        # Create house structure
        print("  Building house structure...")
        house_parts = [
            # Foundation/Ground
            {"type": "plane", "name": "Ground", "location": [0, 0, 0], "scale": [30, 30, 1]},
            # Main building
            {"type": "cube", "name": "MainBuilding", "location": [0, 0, 2], "scale": [5, 4, 2]},
            # Roof
            {"type": "cube", "name": "Roof", "location": [0, 0, 4.2], "scale": [5.5, 4.5, 0.2]},
            # Windows (glass panels)
            {
                "type": "plane",
                "name": "FrontWindow",
                "location": [0, -4.01, 2],
                "scale": [3, 1, 1.5],
                "rotation": [1.57, 0, 0],
            },
            {
                "type": "plane",
                "name": "SideWindow1",
                "location": [-5.01, 0, 2],
                "scale": [2, 1, 1.5],
                "rotation": [1.57, 0, 1.57],
            },
            {
                "type": "plane",
                "name": "SideWindow2",
                "location": [5.01, 0, 2],
                "scale": [2, 1, 1.5],
                "rotation": [1.57, 0, 1.57],
            },
            # Door
            {"type": "cube", "name": "Door", "location": [0, -4.01, 1], "scale": [0.8, 0.1, 1.8]},
            # Garden elements
            {"type": "cylinder", "name": "Tree1", "location": [-8, -6, 2], "scale": [0.5, 0.5, 2]},
            {"type": "sphere", "name": "TreeTop1", "location": [-8, -6, 4.5], "scale": [2, 2, 2]},
            {"type": "cylinder", "name": "Tree2", "location": [8, -6, 2], "scale": [0.5, 0.5, 2]},
            {"type": "sphere", "name": "TreeTop2", "location": [8, -6, 4.5], "scale": [2, 2, 2]},
        ]

        await self.client.call_tool("add_primitive_objects", {"project": project_path, "objects": house_parts})

        # Apply realistic materials
        print("  Applying architectural materials...")
        materials = [
            ("Ground", {"type": "principled", "base_color": [0.3, 0.5, 0.2, 1.0], "roughness": 0.9}),  # Grass green
            (
                "MainBuilding",
                {"type": "principled", "base_color": [0.9, 0.9, 0.85, 1.0], "roughness": 0.7},  # Off-white concrete
            ),
            (
                "Roof",
                {"type": "principled", "base_color": [0.2, 0.2, 0.2, 1.0], "roughness": 0.8, "metallic": 0.3},  # Dark roof
            ),
            ("FrontWindow", {"type": "glass", "base_color": [0.8, 0.9, 1.0, 0.1], "roughness": 0.0}),
            ("SideWindow1", {"type": "glass", "base_color": [0.8, 0.9, 1.0, 0.1], "roughness": 0.0}),
            ("SideWindow2", {"type": "glass", "base_color": [0.8, 0.9, 1.0, 0.1], "roughness": 0.0}),
            ("Door", {"type": "wood", "base_color": [0.4, 0.2, 0.1, 1.0], "roughness": 0.6}),
            ("Tree1", {"type": "principled", "base_color": [0.3, 0.2, 0.1, 1.0], "roughness": 0.9}),  # Tree trunk
            ("TreeTop1", {"type": "principled", "base_color": [0.2, 0.6, 0.1, 1.0], "roughness": 0.8}),  # Leaves
            ("Tree2", {"type": "principled", "base_color": [0.3, 0.2, 0.1, 1.0], "roughness": 0.9}),
            ("TreeTop2", {"type": "principled", "base_color": [0.2, 0.6, 0.1, 1.0], "roughness": 0.8}),
        ]

        for obj_name, material in materials:
            await self.client.call_tool(
                "apply_material", {"project": project_path, "object_name": obj_name, "material": material}
            )

        # Setup outdoor lighting (sun + sky)
        print("  Setting up outdoor lighting...")
        await self.client.call_tool(
            "setup_lighting",
            {"project": project_path, "type": "sun", "settings": {"strength": 5.0, "color": [1.0, 0.95, 0.8]}},
        )

        # Render architectural visualization
        print("  Rendering architectural visualization...")
        render_result = await self.client.call_tool(
            "render_image",
            {
                "project": project_path,
                "frame": 1,
                "settings": {"resolution": [2560, 1440], "samples": 256, "engine": "CYCLES", "format": "PNG"},
            },
        )

        print(f"✅ Demo 4 complete! Render: {render_result.get('output_path', 'pending')}")

    async def demo_5_procedural_scatter(self):
        """Demo 5: Procedural Generation - Forest Scatter.

        Uses geometry nodes to procedurally scatter trees
        across a landscape.
        """
        print("\n🎬 Demo 5: Procedural Generation - Forest Scatter")
        print("-" * 50)

        # Create project
        project = await self.client.call_tool(
            "create_blender_project",
            {
                "name": "demo_forest_scatter",
                "template": "procedural",
                "settings": {"resolution": [1920, 1080], "engine": "EEVEE"},
            },
        )

        if not project.get("success"):
            print(f"❌ Failed to create project: {project.get('error')}")
            return

        project_path = project["project_path"]
        self.demos_created.append(("Procedural Forest", project_path))
        print(f"✅ Created project: {project_path}")

        # Create base terrain
        print("  Creating terrain...")
        await self.client.call_tool(
            "add_primitive_objects",
            {
                "project": project_path,
                "objects": [{"type": "plane", "name": "Terrain", "location": [0, 0, 0], "scale": [20, 20, 1]}],
            },
        )

        # Create tree instances for scattering
        print("  Creating tree instances...")
        tree_instances = []
        for i in range(3):  # Create 3 tree variations
            tree_instances.extend(
                [
                    {"type": "cylinder", "name": f"TreeTrunk{i}", "location": [25 + i * 2, 0, 1], "scale": [0.2, 0.2, 1]},
                    {
                        "type": "cone",
                        "name": f"TreeLeaves{i}",
                        "location": [25 + i * 2, 0, 2.5],
                        "scale": [1.0 - i * 0.1, 1.0 - i * 0.1, 1.5 + i * 0.2],
                    },
                ]
            )

        await self.client.call_tool("add_primitive_objects", {"project": project_path, "objects": tree_instances})

        # Setup geometry nodes for scattering
        print("  Setting up procedural scattering...")
        await self.client.call_tool(
            "setup_geometry_nodes",
            {
                "project": project_path,
                "object_name": "Terrain",
                "node_type": "scatter",
                "settings": {"count": 200, "seed": 12345, "scale_min": 0.8, "scale_max": 1.2, "rotation_variance": 0.3},
            },
        )

        # Apply nature materials
        print("  Applying materials...")
        materials = [
            ("Terrain", {"type": "principled", "base_color": [0.2, 0.4, 0.1, 1.0], "roughness": 0.95})  # Forest floor
        ]

        # Tree materials
        for i in range(3):
            materials.extend(
                [
                    (f"TreeTrunk{i}", {"type": "principled", "base_color": [0.3 - i * 0.05, 0.2, 0.1, 1.0], "roughness": 0.9}),
                    (f"TreeLeaves{i}", {"type": "principled", "base_color": [0.1, 0.5 + i * 0.1, 0.1, 1.0], "roughness": 0.7}),
                ]
            )

        for obj_name, material in materials:
            await self.client.call_tool(
                "apply_material", {"project": project_path, "object_name": obj_name, "material": material}
            )

        # Add atmospheric lighting
        print("  Setting up atmospheric lighting...")
        await self.client.call_tool(
            "setup_lighting",
            {
                "project": project_path,
                "type": "sun",
                "settings": {"strength": 3.0, "color": [1.0, 0.9, 0.7]},  # Warm sunlight through trees
            },
        )

        # Render the procedural forest
        print("  Rendering procedural forest...")
        render_result = await self.client.call_tool(
            "render_image",
            {
                "project": project_path,
                "frame": 1,
                "settings": {"resolution": [1920, 1080], "samples": 64, "engine": "EEVEE", "format": "PNG"},
            },
        )

        print(f"✅ Demo 5 complete! Forest: {render_result.get('output_path', 'pending')}")

    async def run_all_demos(self):
        """Run all demonstration projects."""
        print("\n" + "=" * 60)
        print("🎬 BLENDER MCP DEMONSTRATION PROJECTS")
        print("=" * 60)

        # Check server health
        try:
            health = await self.client.call_tool("health", {})
            if health.get("status") != "healthy":
                print("❌ Server is not healthy!")
                return
        except Exception as e:
            print(f"❌ Cannot connect to server: {e}")
            print("\n📝 To start the server:")
            print("  docker-compose up -d mcp-blender")
            return

        print("Server is healthy! Starting demos...\n")

        # Run all demos
        demos = [
            self.demo_1_product_visualization,
            self.demo_2_physics_dominos,
            self.demo_3_abstract_animation,
            self.demo_4_architectural_viz,
            self.demo_5_procedural_scatter,
        ]

        for i, demo in enumerate(demos, 1):
            try:
                await demo()
            except Exception as e:
                print(f"❌ Demo {i} failed: {e}")

        # Summary
        print("\n" + "=" * 60)
        print("📊 DEMONSTRATION SUMMARY")
        print("=" * 60)
        print(f"Created {len(self.demos_created)} demonstration projects:")

        for name, path in self.demos_created:
            print(f"  ✅ {name}: {path}")

        print("\n📁 Output locations:")
        print("  - Blender files: ./blender/projects/")
        print("  - Rendered images: ./blender/outputs/")
        print("  - Animations: ./blender/outputs/")

        print("\n" + "=" * 60)
        print("All demos complete!")
        print("=" * 60)


async def main():
    """Main entry point."""
    import argparse

    parser = argparse.ArgumentParser(description="Blender MCP Demo Projects")
    parser.add_argument("--server-url", default="http://localhost:8017", help="Blender MCP server URL")
    parser.add_argument("--demo", type=int, choices=[1, 2, 3, 4, 5], help="Run specific demo (1-5)")

    args = parser.parse_args()

    demos = BlenderDemoProjects(args.server_url)

    if args.demo:
        # Run specific demo
        demo_methods = [
            demos.demo_1_product_visualization,
            demos.demo_2_physics_dominos,
            demos.demo_3_abstract_animation,
            demos.demo_4_architectural_viz,
            demos.demo_5_procedural_scatter,
        ]
        await demo_methods[args.demo - 1]()
    else:
        # Run all demos
        await demos.run_all_demos()


if __name__ == "__main__":
    asyncio.run(main())
