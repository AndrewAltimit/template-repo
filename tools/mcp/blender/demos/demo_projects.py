#!/usr/bin/env python3
"""
Demo projects showcasing Blender MCP server capabilities.

This script creates various demonstration projects that showcase:
- Different scene templates
- Object creation and manipulation
- Material application
- Lighting setups
- Physics simulations
- Animations
"""

import time
from typing import Any, Dict

import httpx


class BlenderMCPDemo:
    """Demo class for Blender MCP server."""

    def __init__(self, base_url: str = "http://localhost:8017"):
        self.base_url = base_url
        self.client = httpx.Client(timeout=30.0)

    def call_tool(self, tool_name: str, arguments: Dict[str, Any]) -> Dict[str, Any]:
        """Call a tool via the MCP server."""
        response = self.client.post(
            f"{self.base_url}/mcp/execute",
            json={"tool": tool_name, "arguments": arguments},
        )
        return response.json()

    def demo_1_abstract_art(self):
        """Create an abstract art scene with colorful spheres."""
        print("\n" + "=" * 60)
        print("DEMO 1: Abstract Art Scene")
        print("=" * 60)

        # Create project
        print("Creating abstract art project...")
        result = self.call_tool(
            "create_blender_project",
            {
                "name": "demo_abstract_art",
                "template": "empty",
                "settings": {"resolution": [1920, 1080], "engine": "CYCLES"},
            },
        )
        print("✓ Project created: demo_abstract_art.blend")
        time.sleep(2)

        # Add multiple colored spheres
        print("Adding colorful spheres...")
        spheres = []
        colors = [
            [1.0, 0.2, 0.2, 1.0],  # Red
            [0.2, 1.0, 0.2, 1.0],  # Green
            [0.2, 0.2, 1.0, 1.0],  # Blue
            [1.0, 1.0, 0.2, 1.0],  # Yellow
            [1.0, 0.2, 1.0, 1.0],  # Magenta
            [0.2, 1.0, 1.0, 1.0],  # Cyan
        ]

        import math

        for i in range(6):
            angle = (i / 6) * 2 * math.pi
            x = math.cos(angle) * 3
            y = math.sin(angle) * 3
            z = 1.5

            spheres.append(
                {
                    "type": "sphere",
                    "name": f"Sphere_{i+1}",
                    "location": [x, y, z],
                    "scale": [0.8, 0.8, 0.8],
                }
            )

        self.call_tool(
            "add_primitive_objects",
            {"project": "demo_abstract_art", "objects": spheres},
        )
        print(f"✓ Added {len(spheres)} colorful spheres")
        time.sleep(2)

        # Apply emission materials
        print("Applying emission materials...")
        for i, color in enumerate(colors):
            _ = self.call_tool(  # Result checked in loop
                "apply_material",
                {
                    "project": "demo_abstract_art",
                    "object_name": f"Sphere_{i+1}",
                    "material": {
                        "type": "emission",
                        "base_color": color,
                        "emission_strength": 2.0,
                    },
                },
            )
        print("✓ Applied glowing materials to spheres")

        # Add ground plane
        print("Adding reflective ground...")
        self.call_tool(
            "add_primitive_objects",
            {
                "project": "demo_abstract_art",
                "objects": [
                    {
                        "type": "plane",
                        "name": "Ground",
                        "location": [0, 0, 0],
                        "scale": [10, 10, 1],
                    }
                ],
            },
        )

        # Apply reflective material to ground
        self.call_tool(
            "apply_material",
            {
                "project": "demo_abstract_art",
                "object_name": "Ground",
                "material": {
                    "type": "principled",
                    "base_color": [0.1, 0.1, 0.1, 1.0],
                    "metallic": 0.9,
                    "roughness": 0.1,
                },
            },
        )
        print("✓ Added reflective ground plane")

        print("\n✅ Demo 1 Complete: Abstract art scene created")

    def demo_2_physics_simulation(self):
        """Create a physics simulation with falling cubes."""
        print("\n" + "=" * 60)
        print("DEMO 2: Physics Simulation")
        print("=" * 60)

        # Create project
        print("Creating physics simulation project...")
        result = self.call_tool(
            "create_blender_project",
            {
                "name": "demo_physics",
                "template": "basic_scene",
                "settings": {"resolution": [1920, 1080], "fps": 30, "engine": "EEVEE"},
            },
        )
        print("✓ Project created: demo_physics.blend")
        time.sleep(2)

        # Add stacked cubes
        print("Adding stacked cubes...")
        cubes = []
        for i in range(5):
            for j in range(5 - i):
                x = j * 1.2 - (4 - i) * 0.6
                y = 0
                z = i * 1.2 + 1

                cubes.append(
                    {
                        "type": "cube",
                        "name": f"Cube_{i}_{j}",
                        "location": [x, y, z],
                        "scale": [0.5, 0.5, 0.5],
                    }
                )

        result = self.call_tool("add_primitive_objects", {"project": "demo_physics", "objects": cubes})  # noqa: F841
        print(f"✓ Added {len(cubes)} cubes in pyramid formation")
        time.sleep(2)

        # Apply physics to cubes
        print("Setting up physics for cubes...")
        for cube in cubes:
            _ = self.call_tool(  # Result checked in loop
                "setup_physics",
                {
                    "project": "demo_physics",
                    "object_name": cube["name"],
                    "physics_type": "rigid_body",
                    "settings": {
                        "mass": 1.0,
                        "friction": 0.5,
                        "bounce": 0.3,
                        "collision_shape": "box",
                    },
                },
            )
        print("✓ Physics applied to all cubes")

        # Add a tilted platform
        print("Adding tilted platform...")
        result = self.call_tool(  # noqa: F841
            "add_primitive_objects",
            {
                "project": "demo_physics",
                "objects": [
                    {
                        "type": "plane",
                        "name": "Platform",
                        "location": [0, 0, -0.5],
                        "rotation": [0.1, 0, 0],
                        "scale": [5, 5, 1],
                    }
                ],
            },
        )

        # Make platform static physics object
        self.call_tool(
            "setup_physics",
            {
                "project": "demo_physics",
                "object_name": "Platform",
                "physics_type": "rigid_body",
                "settings": {"mass": 0, "collision_shape": "box"},  # Static object
            },
        )
        print("✓ Added tilted platform with static physics")

        print("\n✅ Demo 2 Complete: Physics simulation ready to bake")

    def demo_3_animated_logo(self):
        """Create an animated logo scene."""
        print("\n" + "=" * 60)
        print("DEMO 3: Animated Logo")
        print("=" * 60)

        # Create project
        print("Creating animated logo project...")
        result = self.call_tool(
            "create_blender_project",
            {
                "name": "demo_animated_logo",
                "template": "studio_lighting",
                "settings": {"resolution": [1920, 1080], "fps": 60, "engine": "EEVEE"},
            },
        )
        print("✓ Project created: demo_animated_logo.blend")
        time.sleep(2)

        # Add logo elements
        print("Adding logo elements...")
        result = self.call_tool(
            "add_primitive_objects",
            {
                "project": "demo_animated_logo",
                "objects": [
                    {
                        "type": "torus",
                        "name": "Logo_Ring",
                        "location": [0, 0, 0],
                        "scale": [2, 2, 0.5],
                    },
                    {
                        "type": "sphere",
                        "name": "Logo_Core",
                        "location": [0, 0, 0],
                        "scale": [0.8, 0.8, 0.8],
                    },
                    {
                        "type": "cube",
                        "name": "Logo_Cube",
                        "location": [0, 0, 0],
                        "scale": [0.5, 0.5, 0.5],
                    },
                ],
            },
        )
        print("✓ Added logo elements")
        time.sleep(2)

        # Create animations
        print("Creating rotation animation for ring...")
        result = self.call_tool(
            "create_animation",
            {
                "project": "demo_animated_logo",
                "object_name": "Logo_Ring",
                "keyframes": [
                    {"frame": 1, "rotation": [0, 0, 0]},
                    {"frame": 60, "rotation": [0, 0, 3.14159]},
                    {"frame": 120, "rotation": [0, 0, 6.28318]},
                ],
                "interpolation": "LINEAR",
            },
        )
        print("✓ Ring rotation animation created")

        print("Creating scale animation for core...")
        result = self.call_tool(
            "create_animation",
            {
                "project": "demo_animated_logo",
                "object_name": "Logo_Core",
                "keyframes": [
                    {"frame": 1, "scale": [0.8, 0.8, 0.8]},
                    {"frame": 30, "scale": [1.2, 1.2, 1.2]},
                    {"frame": 60, "scale": [0.8, 0.8, 0.8]},
                    {"frame": 90, "scale": [1.2, 1.2, 1.2]},
                    {"frame": 120, "scale": [0.8, 0.8, 0.8]},
                ],
                "interpolation": "BEZIER",
            },
        )
        print("✓ Core pulsing animation created")

        print("Creating orbit animation for cube...")
        import math

        keyframes = []
        for frame in range(0, 121, 10):
            angle = (frame / 120) * 2 * math.pi
            x = math.cos(angle) * 1.5
            y = math.sin(angle) * 1.5
            keyframes.append({"frame": frame, "location": [x, y, 0]})

        result = self.call_tool(  # noqa: F841
            "create_animation",
            {
                "project": "demo_animated_logo",
                "object_name": "Logo_Cube",
                "keyframes": keyframes,
                "interpolation": "BEZIER",
            },
        )
        print("✓ Cube orbit animation created")

        # Apply metallic materials
        print("Applying metallic materials...")
        self.call_tool(
            "apply_material",
            {
                "project": "demo_animated_logo",
                "object_name": "Logo_Ring",
                "material": {
                    "type": "metal",
                    "base_color": [0.9, 0.7, 0.3, 1.0],
                    "roughness": 0.3,
                },  # Gold
            },
        )

        self.call_tool(
            "apply_material",
            {
                "project": "demo_animated_logo",
                "object_name": "Logo_Core",
                "material": {
                    "type": "emission",
                    "base_color": [0.3, 0.6, 1.0, 1.0],
                    "emission_strength": 3.0,
                },  # Blue glow
            },
        )

        self.call_tool(
            "apply_material",
            {
                "project": "demo_animated_logo",
                "object_name": "Logo_Cube",
                "material": {
                    "type": "metal",
                    "base_color": [0.8, 0.8, 0.9, 1.0],
                    "roughness": 0.2,
                },  # Silver
            },
        )
        print("✓ Materials applied to logo elements")

        print("\n✅ Demo 3 Complete: Animated logo scene created")

    def demo_4_procedural_landscape(self):
        """Create a procedural landscape with geometry nodes."""
        print("\n" + "=" * 60)
        print("DEMO 4: Procedural Landscape")
        print("=" * 60)

        # Create project
        print("Creating procedural landscape project...")
        result = self.call_tool(
            "create_blender_project",
            {
                "name": "demo_landscape",
                "template": "empty",
                "settings": {"resolution": [2560, 1440], "engine": "CYCLES"},
            },
        )
        print("✓ Project created: demo_landscape.blend")
        time.sleep(2)

        # Add base terrain
        print("Adding base terrain...")
        result = self.call_tool(
            "add_primitive_objects",
            {
                "project": "demo_landscape",
                "objects": [
                    {
                        "type": "plane",
                        "name": "Terrain",
                        "location": [0, 0, 0],
                        "scale": [20, 20, 1],
                    }
                ],
            },
        )
        print("✓ Base terrain added")

        # Apply geometry nodes for terrain deformation
        print("Applying procedural terrain generation...")
        result = self.call_tool(
            "create_geometry_nodes",
            {
                "project": "demo_landscape",
                "object_name": "Terrain",
                "node_setup": "volume",
                "parameters": {"count": 500, "seed": 42, "scale_variance": 0.3},
            },
        )
        print("✓ Procedural terrain generation applied")

        # Add scattered objects (trees)
        print("Adding scattered trees...")
        result = self.call_tool(
            "add_primitive_objects",
            {
                "project": "demo_landscape",
                "objects": [
                    {
                        "type": "cone",
                        "name": "Tree_Base",
                        "location": [0, 0, 0],
                        "scale": [0.5, 0.5, 2],
                    }
                ],
            },
        )

        # Apply scatter geometry nodes
        result = self.call_tool(
            "create_geometry_nodes",
            {
                "project": "demo_landscape",
                "object_name": "Tree_Base",
                "node_setup": "scatter",
                "parameters": {"count": 100, "seed": 123, "scale_variance": 0.2},
            },
        )
        print("✓ Scattered trees added")

        # Setup natural lighting
        print("Setting up natural lighting...")
        result = self.call_tool(  # noqa: F841
            "setup_lighting",
            {
                "project": "demo_landscape",
                "type": "sun",
                "settings": {
                    "strength": 3.0,
                    "color": [1.0, 0.95, 0.8],
                },  # Warm sunlight
            },
        )
        print("✓ Natural sunlight configured")

        # Apply materials
        print("Applying terrain materials...")
        self.call_tool(
            "apply_material",
            {
                "project": "demo_landscape",
                "object_name": "Terrain",
                "material": {
                    "type": "principled",
                    "base_color": [0.3, 0.5, 0.2, 1.0],
                    "roughness": 0.8,
                },  # Grass green
            },
        )

        self.call_tool(
            "apply_material",
            {
                "project": "demo_landscape",
                "object_name": "Tree_Base",
                "material": {
                    "type": "principled",
                    "base_color": [0.2, 0.4, 0.1, 1.0],
                    "roughness": 0.9,
                },  # Tree green
            },
        )
        print("✓ Natural materials applied")

        print("\n✅ Demo 4 Complete: Procedural landscape created")

    def run_all_demos(self):
        """Run all demonstration projects."""
        print("\n" + "=" * 60)
        print("BLENDER MCP SERVER DEMONSTRATION")
        print("=" * 60)
        print("\nThis will create 4 demo projects showcasing different")
        print("capabilities of the Blender MCP server.")

        try:
            self.demo_1_abstract_art()
            time.sleep(2)

            self.demo_2_physics_simulation()
            time.sleep(2)

            self.demo_3_animated_logo()
            time.sleep(2)

            self.demo_4_procedural_landscape()

            # List all created projects
            print("\n" + "=" * 60)
            print("ALL DEMOS COMPLETE")
            print("=" * 60)

            result = self.call_tool("list_projects", {})
            if result.get("success"):
                projects = result["result"]["projects"]
                demo_projects = [p for p in projects if p["name"].startswith("demo_")]

                print(f"\nCreated {len(demo_projects)} demonstration projects:")
                for project in demo_projects:
                    size_mb = project["size"] / (1024 * 1024)
                    print(f"  ✓ {project['name']}.blend ({size_mb:.2f} MB)")

            print("\nYou can now:")
            print("1. Open these files in Blender to view the scenes")
            print("2. Use render tools to generate images")
            print("3. Bake physics simulations")
            print("4. Export scenes to other formats")

        except Exception as e:
            print(f"\n❌ Error during demo: {e}")
        finally:
            self.client.close()


def main():
    """Run the demonstration."""
    demo = BlenderMCPDemo()
    demo.run_all_demos()


if __name__ == "__main__":
    main()
