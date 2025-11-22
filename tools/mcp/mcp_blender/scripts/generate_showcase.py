#!/usr/bin/env python3
"""Generate showcase scenes using Blender MCP Server."""

import asyncio
import random
from typing import Any, Dict

import httpx

BASE_URL = "http://localhost:8017"


async def call_tool(client: httpx.AsyncClient, tool_name: str, arguments: Dict[str, Any]) -> Dict[str, Any]:
    """Call a tool on the Blender MCP server."""
    payload = {"tool": tool_name, "arguments": arguments}
    response = await client.post(f"{BASE_URL}/mcp/execute", json=payload)
    result: Dict[str, Any] = response.json()
    if not result.get("success"):
        print(f"Error calling {tool_name}: {result.get('error')}")
    return result


async def create_particle_fountain(client: httpx.AsyncClient):
    """Create a fountain with particle system."""
    print("\n🎨 Creating Particle Fountain Scene...")

    # Create project
    result = await call_tool(
        client,
        "create_blender_project",
        {
            "name": "particle_fountain",
            "template": "basic_scene",
            "settings": {"resolution": [1920, 1080], "fps": 30, "engine": "BLENDER_EEVEE"},
        },
    )

    if not result.get("success"):
        return

    project = result["result"]["project_path"]

    # Create fountain base
    await call_tool(
        client,
        "add_primitive_objects",
        {
            "project": project,
            "objects": [
                {"type": "cylinder", "name": "FountainBase", "location": [0, 0, 0], "scale": [3, 3, 0.5]},
                {"type": "cylinder", "name": "FountainPillar", "location": [0, 0, 1], "scale": [0.5, 0.5, 2]},
                {"type": "sphere", "name": "WaterEmitter", "location": [0, 0, 2.5], "scale": [0.3, 0.3, 0.3]},
            ],
        },
    )

    # Apply materials
    await call_tool(
        client,
        "apply_material",
        {
            "project": project,
            "object_name": "FountainBase",
            "material": {"type": "principled", "base_color": [0.3, 0.3, 0.35, 1], "roughness": 0.7, "metallic": 0.2},
        },
    )

    await call_tool(
        client,
        "apply_material",
        {
            "project": project,
            "object_name": "FountainPillar",
            "material": {"type": "principled", "base_color": [0.3, 0.3, 0.35, 1], "roughness": 0.7, "metallic": 0.2},
        },
    )

    # Setup area lighting for dramatic effect
    await call_tool(
        client, "setup_lighting", {"project": project, "type": "area", "settings": {"strength": 3.0, "color": [0.8, 0.9, 1.0]}}
    )

    print("✅ Particle Fountain scene created!")
    return project


async def create_abstract_motion_graphics(client: httpx.AsyncClient):
    """Create an abstract motion graphics scene."""
    print("\n🎬 Creating Abstract Motion Graphics...")

    # Create project with animation template
    result = await call_tool(
        client,
        "create_blender_project",
        {
            "name": "motion_graphics",
            "template": "animation",
            "settings": {"resolution": [1920, 1080], "fps": 60, "engine": "BLENDER_EEVEE"},
        },
    )

    if not result.get("success"):
        return

    project = result["result"]["project_path"]

    # Create geometric shapes
    shapes = []
    for i in range(5):
        angle = (i / 5) * 6.28  # 2*pi
        x = 3 * (i - 2)
        shape_type = ["cube", "sphere", "torus", "cone", "cylinder"][i]
        shapes.append(
            {"type": shape_type, "name": f"Shape_{i}", "location": [x, 0, 0], "rotation": [0, 0, angle], "scale": [1, 1, 1]}
        )

    await call_tool(client, "add_primitive_objects", {"project": project, "objects": shapes})

    # Apply different materials with emission
    colors = [
        [1, 0.2, 0.2, 1],  # Red
        [0.2, 1, 0.2, 1],  # Green
        [0.2, 0.2, 1, 1],  # Blue
        [1, 1, 0.2, 1],  # Yellow
        [1, 0.2, 1, 1],  # Magenta
    ]

    for i in range(5):
        await call_tool(
            client,
            "apply_material",
            {
                "project": project,
                "object_name": f"Shape_{i}",
                "material": {"type": "emission", "base_color": colors[i], "emission_strength": 2.0},
            },
        )

        # Create complex animation
        keyframes = []
        for frame in range(0, 181, 30):  # 0 to 180 frames, every 30 frames
            t = frame / 180.0
            anim_x: float = 3 * (i - 2) + 2 * (1 if i % 2 == 0 else -1) * (t if t < 0.5 else 1 - t)
            anim_y: float = 3 * (t * 2 - 1 if t < 0.5 else 2 - t * 2)
            anim_z: float = 2 * abs((t * 4) % 2 - 1)
            rotation = frame * 0.05 * (i + 1)

            keyframes.append(
                {
                    "frame": frame + 1,
                    "location": [anim_x, anim_y, anim_z],
                    "rotation": [rotation, rotation * 0.7, rotation * 1.3],
                    "scale": [1 + 0.5 * abs((t * 8) % 2 - 1)] * 3,
                }
            )

        await call_tool(
            client,
            "create_animation",
            {"project": project, "object_name": f"Shape_{i}", "keyframes": keyframes, "interpolation": "BEZIER"},
        )

    print("✅ Motion Graphics scene created with complex animations!")
    return project


async def create_sci_fi_corridor(client: httpx.AsyncClient):
    """Create a sci-fi corridor scene."""
    print("\n🚀 Creating Sci-Fi Corridor...")

    result = await call_tool(
        client,
        "create_blender_project",
        {
            "name": "scifi_corridor",
            "template": "basic_scene",
            "settings": {"resolution": [2560, 1440], "fps": 24, "engine": "CYCLES"},
        },
    )

    if not result.get("success"):
        return

    project = result["result"]["project_path"]

    # Create corridor structure
    corridor_parts = []

    # Floor and ceiling
    for z in [0, 4]:
        corridor_parts.append(
            {"type": "cube", "name": f"{'Floor' if z == 0 else 'Ceiling'}", "location": [0, 0, z], "scale": [20, 3, 0.1]}
        )

    # Walls
    for y in [-1.5, 1.5]:
        corridor_parts.append({"type": "cube", "name": f"Wall_{y}", "location": [0, y, 2], "scale": [20, 0.1, 2]})

    # Pillars
    for x in range(-8, 9, 4):
        for y in [-1.4, 1.4]:
            corridor_parts.append({"type": "cube", "name": f"Pillar_{x}_{y}", "location": [x, y, 2], "scale": [0.3, 0.3, 2]})

    # Light panels
    for x in range(-6, 7, 3):
        corridor_parts.append({"type": "plane", "name": f"LightPanel_{x}", "location": [x, 0, 3.9], "scale": [1, 0.5, 1]})

    await call_tool(client, "add_primitive_objects", {"project": project, "objects": corridor_parts})

    # Apply materials
    # Dark metal for structure
    for name in ["Floor", "Ceiling", "Wall_-1.5", "Wall_1.5"]:
        await call_tool(
            client,
            "apply_material",
            {
                "project": project,
                "object_name": name,
                "material": {"type": "metal", "base_color": [0.1, 0.1, 0.12, 1], "roughness": 0.6, "metallic": 0.9},
            },
        )

    # Blue-ish metal for pillars
    for x in range(-8, 9, 4):
        for y in [-1.4, 1.4]:
            await call_tool(
                client,
                "apply_material",
                {
                    "project": project,
                    "object_name": f"Pillar_{x}_{y}",
                    "material": {"type": "metal", "base_color": [0.1, 0.15, 0.2, 1], "roughness": 0.4, "metallic": 0.95},
                },
            )

    # Emissive light panels
    for x in range(-6, 7, 3):
        await call_tool(
            client,
            "apply_material",
            {
                "project": project,
                "object_name": f"LightPanel_{x}",
                "material": {"type": "emission", "base_color": [0.5, 0.8, 1, 1], "emission_strength": 5.0},
            },
        )

    print("✅ Sci-Fi Corridor scene created!")
    return project


async def create_organic_growth(client: httpx.AsyncClient):
    """Create an organic growth animation using procedural generation."""
    print("\n🌿 Creating Organic Growth Scene...")

    result = await call_tool(
        client,
        "create_blender_project",
        {
            "name": "organic_growth",
            "template": "procedural",
            "settings": {"resolution": [1920, 1080], "fps": 30, "engine": "CYCLES"},
        },
    )

    if not result.get("success"):
        return

    project = result["result"]["project_path"]

    # Create base mesh for growth
    await call_tool(
        client,
        "add_primitive_objects",
        {
            "project": project,
            "objects": [{"type": "sphere", "name": "SeedPod", "location": [0, 0, 0], "scale": [0.2, 0.2, 0.2]}],
        },
    )

    # Apply procedural geometry nodes
    await call_tool(
        client,
        "create_geometry_nodes",
        {
            "project": project,
            "object_name": "SeedPod",
            "node_setup": "scatter",
            "parameters": {"count": 200, "seed": 42, "scale_variance": 0.5},
        },
    )

    # Create animated growth
    growth_keyframes = []
    for frame in range(1, 121, 10):
        scale = 0.2 + (frame / 120) * 2
        growth_keyframes.append({"frame": frame, "scale": [scale, scale, scale * 1.2]})

    await call_tool(
        client,
        "create_animation",
        {"project": project, "object_name": "SeedPod", "keyframes": growth_keyframes, "interpolation": "BEZIER"},
    )

    # Apply organic material
    await call_tool(
        client,
        "apply_material",
        {
            "project": project,
            "object_name": "SeedPod",
            "material": {"type": "principled", "base_color": [0.2, 0.6, 0.3, 1], "roughness": 0.7, "metallic": 0.0},
        },
    )

    # Setup natural lighting
    await call_tool(
        client, "setup_lighting", {"project": project, "type": "sun", "settings": {"strength": 2.0, "color": [1, 0.95, 0.8]}}
    )

    print("✅ Organic Growth scene created!")
    return project


async def create_crystal_cave(client: httpx.AsyncClient):
    """Create a crystal cave environment."""
    print("\n💎 Creating Crystal Cave...")

    result = await call_tool(
        client,
        "create_blender_project",
        {
            "name": "crystal_cave",
            "template": "basic_scene",
            "settings": {"resolution": [2560, 1440], "fps": 24, "engine": "CYCLES"},
        },
    )

    if not result.get("success"):
        return

    project = result["result"]["project_path"]

    # Create cave structure
    cave_parts = []

    # Cave floor (rough terrain)
    for x in range(-5, 6, 2):
        for y in range(-5, 6, 2):
            height = random.uniform(-0.5, 0.5)
            cave_parts.append(
                {"type": "cube", "name": f"Ground_{x}_{y}", "location": [x, y, height], "scale": [2.1, 2.1, 1 + abs(height)]}
            )

    # Crystals
    crystal_positions = [
        (0, 0, 1.5, 0.5, 0.5, 3),
        (2, -1, 1, 0.3, 0.3, 2),
        (-2, 2, 1.2, 0.4, 0.4, 2.5),
        (3, 3, 0.8, 0.3, 0.3, 1.8),
        (-3, -2, 1, 0.35, 0.35, 2.2),
        (1, 2, 0.7, 0.25, 0.25, 1.5),
        (-1, -3, 0.9, 0.3, 0.3, 1.9),
    ]

    for i, (x, y, z, sx, sy, sz) in enumerate(crystal_positions):
        # Main crystal
        cave_parts.append(
            {
                "type": "cylinder",
                "name": f"Crystal_{i}",
                "location": [x, y, z],
                "rotation": [random.uniform(-0.3, 0.3), random.uniform(-0.3, 0.3), 0],
                "scale": [sx, sy, sz],
            }
        )

        # Crystal tip
        cave_parts.append(
            {
                "type": "cone",
                "name": f"CrystalTip_{i}",
                "location": [x, y, z + sz],
                "rotation": [random.uniform(-0.3, 0.3), random.uniform(-0.3, 0.3), 0],
                "scale": [sx, sy, sz * 0.3],
            }
        )

    await call_tool(client, "add_primitive_objects", {"project": project, "objects": cave_parts})

    # Apply materials
    # Rock material for ground
    for x in range(-5, 6, 2):
        for y in range(-5, 6, 2):
            await call_tool(
                client,
                "apply_material",
                {
                    "project": project,
                    "object_name": f"Ground_{x}_{y}",
                    "material": {"type": "principled", "base_color": [0.2, 0.18, 0.15, 1], "roughness": 0.9, "metallic": 0.0},
                },
            )

    # Crystal materials with different colors
    crystal_colors = [
        [0.3, 0.7, 1, 1],  # Blue
        [0.8, 0.3, 1, 1],  # Purple
        [0.3, 1, 0.7, 1],  # Cyan
        [1, 0.5, 0.7, 1],  # Pink
        [0.5, 1, 0.5, 1],  # Green
        [1, 0.8, 0.3, 1],  # Gold
        [0.7, 0.3, 0.3, 1],  # Red
    ]

    for i in range(len(crystal_positions)):
        # Glass material for crystals
        await call_tool(
            client,
            "apply_material",
            {
                "project": project,
                "object_name": f"Crystal_{i}",
                "material": {"type": "glass", "base_color": crystal_colors[i], "roughness": 0.1},
            },
        )

        await call_tool(
            client,
            "apply_material",
            {
                "project": project,
                "object_name": f"CrystalTip_{i}",
                "material": {"type": "glass", "base_color": crystal_colors[i], "roughness": 0.05},
            },
        )

    # Add some emissive crystals for lighting
    await call_tool(
        client,
        "add_primitive_objects",
        {
            "project": project,
            "objects": [
                {"type": "sphere", "name": "GlowCrystal_1", "location": [-2, 0, 3], "scale": [0.3, 0.3, 0.3]},
                {"type": "sphere", "name": "GlowCrystal_2", "location": [2, 1, 2.5], "scale": [0.25, 0.25, 0.25]},
            ],
        },
    )

    # Apply emission material to glow crystals
    for i in [1, 2]:
        await call_tool(
            client,
            "apply_material",
            {
                "project": project,
                "object_name": f"GlowCrystal_{i}",
                "material": {"type": "emission", "base_color": [0.5, 0.8, 1, 1], "emission_strength": 10.0},
            },
        )

    print("✅ Crystal Cave scene created!")
    return project


async def main():
    """Generate all showcase scenes."""
    print("=" * 60)
    print("🎨 Blender MCP Showcase Generator")
    print("=" * 60)

    async with httpx.AsyncClient(timeout=30.0) as client:
        projects = []

        # Generate different types of scenes
        projects.append(await create_particle_fountain(client))
        projects.append(await create_abstract_motion_graphics(client))
        projects.append(await create_sci_fi_corridor(client))
        projects.append(await create_organic_growth(client))
        projects.append(await create_crystal_cave(client))

        print("\n" + "=" * 60)
        print("✨ All showcase scenes generated successfully!")
        print("=" * 60)

        print("\n📁 Created projects:")
        for project in projects:
            if project:
                print(f"  - {project}")

        # Optionally start rendering
        print("\n🎬 You can now render these projects using the render tools")
        print("   or open them in Blender for further editing.")


if __name__ == "__main__":
    asyncio.run(main())
