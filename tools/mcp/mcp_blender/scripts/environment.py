#!/usr/bin/env python3
"""Blender world environment setup script."""

import math
import os
from pathlib import Path
import sys

import bpy

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from mcp_common import (  # noqa: E402  pylint: disable=wrong-import-position
    run,
)


def setup_world_environment(args, _job_id):
    """Setup world environment lighting and atmosphere."""
    try:
        # Load project
        if "project" in args:
            bpy.ops.wm.open_mainfile(filepath=args["project"])

        environment_type = args.get("environment_type", "SKY_TEXTURE")
        settings = args.get("settings") or {}
        if environment_type not in ("HDRI", "SKY_TEXTURE", "GRADIENT", "COLOR", "VOLUMETRIC"):
            print(f"Error: Unknown environment type '{environment_type}'")
            return False
        hdri_path = settings.get("hdri_path")
        if environment_type == "HDRI" and not (hdri_path and Path(hdri_path).is_file()):
            print(f"Error: HDRI file not found: {hdri_path} (settings.hdri_path is required)")
            return False

        scene = bpy.context.scene
        world = scene.world
        if world is None:
            world = bpy.data.worlds.new("World")
            scene.world = world

        world.use_nodes = True
        nodes = world.node_tree.nodes
        links = world.node_tree.links

        # Clear existing nodes
        nodes.clear()

        # Create output node
        node_output = nodes.new(type="ShaderNodeOutputWorld")
        node_output.location = (300, 0)

        strength = settings.get("strength", 1.0)

        if environment_type == "HDRI":
            # HDRI environment
            hdri_path = settings.get("hdri_path")

            node_bg = nodes.new(type="ShaderNodeBackground")
            node_bg.location = (0, 0)
            node_bg.inputs["Strength"].default_value = strength

            node_env = nodes.new(type="ShaderNodeTexEnvironment")
            node_env.location = (-300, 0)

            node_env.image = bpy.data.images.load(hdri_path, check_existing=True)

            # Add mapping for rotation
            rotation = settings.get("rotation", [0, 0, 0])
            if any(r != 0 for r in rotation):
                node_mapping = nodes.new(type="ShaderNodeMapping")
                node_mapping.location = (-500, 0)
                node_mapping.inputs["Rotation"].default_value = rotation

                node_coord = nodes.new(type="ShaderNodeTexCoord")
                node_coord.location = (-700, 0)

                links.new(node_coord.outputs["Generated"], node_mapping.inputs["Vector"])
                links.new(node_mapping.outputs["Vector"], node_env.inputs["Vector"])

            links.new(node_env.outputs["Color"], node_bg.inputs["Color"])
            links.new(node_bg.outputs["Background"], node_output.inputs["Surface"])

        elif environment_type == "SKY_TEXTURE":
            # Procedural sky texture
            node_bg = nodes.new(type="ShaderNodeBackground")
            node_bg.location = (0, 0)
            node_bg.inputs["Strength"].default_value = strength

            node_sky = nodes.new(type="ShaderNodeTexSky")
            node_sky.location = (-300, 0)
            node_sky.sky_type = "NISHITA"

            # Sky settings
            sun_direction = settings.get("sun_direction", [0, 0, 1])
            turbidity = settings.get("turbidity", 2.2)
            ground_albedo = settings.get("ground_albedo", 0.3)

            # Convert sun direction to elevation/rotation
            node_sky.sun_elevation = math.asin(sun_direction[2]) if abs(sun_direction[2]) <= 1 else 0
            node_sky.sun_rotation = math.atan2(sun_direction[1], sun_direction[0])
            node_sky.air_density = turbidity
            node_sky.ground_albedo = ground_albedo

            links.new(node_sky.outputs["Color"], node_bg.inputs["Color"])
            links.new(node_bg.outputs["Background"], node_output.inputs["Surface"])

        elif environment_type == "GRADIENT":
            # Gradient background
            node_bg = nodes.new(type="ShaderNodeBackground")
            node_bg.location = (0, 0)
            node_bg.inputs["Strength"].default_value = strength

            node_colorramp = nodes.new(type="ShaderNodeValToRGB")
            node_colorramp.location = (-300, 0)

            color_top = settings.get("color_top", [0.5, 0.7, 1.0, 1.0])
            color_bottom = settings.get("color_bottom", [0.2, 0.2, 0.3, 1.0])

            node_colorramp.color_ramp.elements[0].color = color_bottom
            node_colorramp.color_ramp.elements[1].color = color_top

            # Z gradient
            node_separate = nodes.new(type="ShaderNodeSeparateXYZ")
            node_separate.location = (-500, 0)

            node_coord = nodes.new(type="ShaderNodeTexCoord")
            node_coord.location = (-700, 0)

            links.new(node_coord.outputs["Generated"], node_separate.inputs["Vector"])
            links.new(node_separate.outputs["Z"], node_colorramp.inputs["Fac"])
            links.new(node_colorramp.outputs["Color"], node_bg.inputs["Color"])
            links.new(node_bg.outputs["Background"], node_output.inputs["Surface"])

        elif environment_type == "COLOR":
            # Solid color background
            node_bg = nodes.new(type="ShaderNodeBackground")
            node_bg.location = (0, 0)
            node_bg.inputs["Strength"].default_value = strength

            color = settings.get("color", [0.5, 0.5, 0.5, 1.0])
            node_bg.inputs["Color"].default_value = color

            links.new(node_bg.outputs["Background"], node_output.inputs["Surface"])

        elif environment_type == "VOLUMETRIC":
            # Volumetric fog/atmosphere
            node_bg = nodes.new(type="ShaderNodeBackground")
            node_bg.location = (0, 0)
            node_bg.inputs["Strength"].default_value = strength
            node_bg.inputs["Color"].default_value = (0.5, 0.6, 0.8, 1.0)

            # Add volume scatter
            node_volume = nodes.new(type="ShaderNodeVolumeScatter")
            node_volume.location = (0, -200)
            node_volume.inputs["Density"].default_value = settings.get("volume_density", 0.1)
            node_volume.inputs["Anisotropy"].default_value = settings.get("volume_anisotropy", 0.0)

            links.new(node_bg.outputs["Background"], node_output.inputs["Surface"])
            links.new(node_volume.outputs["Volume"], node_output.inputs["Volume"])

        # Save project
        if "project" in args:
            bpy.ops.wm.save_mainfile()

        return {"success": True, "environment_type": environment_type, "world": world.name}

    except Exception as e:
        print(f"Error setting up environment: {e}")
        return False


def main():
    """Dispatch the requested operation (see mcp_common.run)."""
    run({"setup_world_environment": setup_world_environment})


if __name__ == "__main__":
    main()
