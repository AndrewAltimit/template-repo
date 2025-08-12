#!/usr/bin/env python3
"""Basic usage examples for Blender MCP Server."""

import asyncio
from typing import Any, Dict


async def create_simple_scene() -> Dict[str, Any]:
    """Example: Create a simple scene with basic objects.

    This example demonstrates how to:
    1. Create a new project
    2. Add primitive objects
    3. Setup lighting
    4. Apply materials
    5. Render the scene
    """
    # NOTE: This is a conceptual example showing the API flow
    # In actual usage, you would use the MCP client to call these tools

    example_flow = {
        "step1": "Create a new Blender project",
        "api_call": "create_blender_project",
        "params": {
            "name": "simple_scene",
            "template": "studio_lighting",
            "settings": {"resolution": [1920, 1080], "fps": 24, "engine": "CYCLES"},
        },
    }

    example_flow["step2"] = "Add objects to the scene"
    example_flow["objects"] = [
        {"type": "monkey", "name": "Suzanne", "location": [0, 0, 2]},
        {"type": "cube", "name": "Cube", "location": [-3, 0, 1]},
        {"type": "sphere", "name": "Sphere", "location": [3, 0, 1]},
    ]

    example_flow["step3"] = "Apply materials"
    example_flow["materials"] = {
        "Suzanne": {"type": "metal", "roughness": 0.3},
        "Cube": {"type": "glass"},
        "Sphere": {"type": "emission", "emission_strength": 2.0},
    }

    example_flow["step4"] = "Render the scene"
    example_flow["render_settings"] = {
        "samples": 128,
        "resolution": [1920, 1080],
        "format": "PNG",
    }

    return example_flow


async def physics_simulation_example() -> Dict[str, Any]:
    """Example: Create a physics simulation with falling objects.

    This example shows how to:
    1. Create objects with physics properties
    2. Setup rigid body physics
    3. Bake the simulation
    4. Render an animation
    """
    example_flow = {
        "description": "Physics simulation with falling objects",
        "steps": [
            {
                "action": "Create project",
                "tool": "create_blender_project",
                "params": {"name": "physics_demo", "template": "empty"},
            },
            {
                "action": "Add ground plane",
                "tool": "add_primitive_objects",
                "objects": [{"type": "plane", "name": "Ground", "scale": [10, 10, 1]}],
            },
            {
                "action": "Add falling objects",
                "tool": "add_primitive_objects",
                "objects": [
                    {"type": "cube", "name": "Box1", "location": [0, 0, 5]},
                    {"type": "sphere", "name": "Ball1", "location": [1, 0, 7]},
                    {"type": "cube", "name": "Box2", "location": [-1, 0, 9]},
                ],
            },
            {
                "action": "Setup physics",
                "tool": "setup_physics",
                "params": {
                    "physics_type": "rigid_body",
                    "settings": {"mass": 1.0, "friction": 0.5, "bounce": 0.3},
                },
            },
            {
                "action": "Bake simulation",
                "tool": "bake_simulation",
                "params": {"start_frame": 1, "end_frame": 120},
            },
            {
                "action": "Render animation",
                "tool": "render_animation",
                "params": {"start_frame": 1, "end_frame": 120, "format": "MP4"},
            },
        ],
    }

    return example_flow


async def procedural_generation_example() -> Dict[str, Any]:
    """Example: Use geometry nodes for procedural generation.

    This example demonstrates:
    1. Creating a base object
    2. Applying geometry nodes
    3. Configuring procedural parameters
    4. Rendering the result
    """
    example_flow = {
        "description": "Procedural scatter system using geometry nodes",
        "workflow": {
            "base_object": {
                "type": "plane",
                "name": "ScatterPlane",
                "scale": [10, 10, 1],
            },
            "geometry_nodes": {
                "node_setup": "scatter",
                "parameters": {"count": 500, "seed": 42, "scale_variance": 0.3},
            },
            "instance_object": {
                "type": "cube",
                "name": "InstanceCube",
                "scale": [0.1, 0.1, 0.1],
            },
            "render_settings": {
                "engine": "EEVEE",
                "samples": 64,
                "resolution": [1920, 1080],
            },
        },
    }

    return example_flow


def main():
    """Run examples and print the workflow."""
    import json

    # Run the async examples
    loop = asyncio.get_event_loop()

    print("=" * 60)
    print("Blender MCP Server - Usage Examples")
    print("=" * 60)

    # Example 1: Simple Scene
    print("\n1. SIMPLE SCENE EXAMPLE:")
    print("-" * 40)
    simple_scene = loop.run_until_complete(create_simple_scene())
    print(json.dumps(simple_scene, indent=2))

    # Example 2: Physics Simulation
    print("\n2. PHYSICS SIMULATION EXAMPLE:")
    print("-" * 40)
    physics_sim = loop.run_until_complete(physics_simulation_example())
    print(json.dumps(physics_sim, indent=2))

    # Example 3: Procedural Generation
    print("\n3. PROCEDURAL GENERATION EXAMPLE:")
    print("-" * 40)
    procedural = loop.run_until_complete(procedural_generation_example())
    print(json.dumps(procedural, indent=2))

    print("\n" + "=" * 60)
    print("For actual usage, use the MCP client to call these tools")
    print("See tools/mcp/blender/scripts/test_server.py for working examples")
    print("=" * 60)


if __name__ == "__main__":
    main()
