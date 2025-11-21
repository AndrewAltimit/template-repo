#!/usr/bin/env python3
"""Modifier tools for Blender objects."""

import json
import sys
from pathlib import Path

import bpy


def add_modifier(args):
    """Add modifier to an object."""
    object_name = args["object_name"]
    modifier_type = args["modifier_type"]
    settings = args.get("settings", {})

    # Get the object
    if object_name not in bpy.data.objects:
        return {"success": False, "error": f"Object '{object_name}' not found"}

    obj = bpy.data.objects[object_name]

    # Make sure it's a mesh object for most modifiers
    if modifier_type not in ["ARMATURE", "HOOK", "LATTICE"] and obj.type != "MESH":
        return {"success": False, "error": f"Object '{object_name}' is not a mesh"}

    # Add the modifier
    modifier_name = f"{modifier_type}_{len(obj.modifiers)}"

    if modifier_type == "SUBSURF":
        mod = obj.modifiers.new(name=modifier_name, type="SUBSURF")
        mod.levels = settings.get("levels", 2)
        mod.render_levels = settings.get("render_levels", 3)
        mod.subdivision_type = settings.get("subdivision_type", "CATMULL_CLARK")

    elif modifier_type == "ARRAY":
        mod = obj.modifiers.new(name=modifier_name, type="ARRAY")
        mod.count = settings.get("count", 3)
        relative_offset = settings.get("relative_offset", [1, 0, 0])
        mod.relative_offset_displace[0] = relative_offset[0]
        mod.relative_offset_displace[1] = relative_offset[1]
        mod.relative_offset_displace[2] = relative_offset[2]
        mod.use_relative_offset = True

    elif modifier_type == "MIRROR":
        mod = obj.modifiers.new(name=modifier_name, type="MIRROR")
        use_axis = settings.get("use_axis", [True, False, False])
        mod.use_axis[0] = use_axis[0]  # X
        mod.use_axis[1] = use_axis[1]  # Y
        mod.use_axis[2] = use_axis[2]  # Z
        mod.use_bisect_axis[0] = settings.get("use_bisect", [False, False, False])[0]
        mod.use_bisect_axis[1] = settings.get("use_bisect", [False, False, False])[1]
        mod.use_bisect_axis[2] = settings.get("use_bisect", [False, False, False])[2]

    elif modifier_type == "SOLIDIFY":
        mod = obj.modifiers.new(name=modifier_name, type="SOLIDIFY")
        mod.thickness = settings.get("thickness", 0.1)
        mod.offset = settings.get("offset", 0.0)
        mod.use_even_offset = settings.get("use_even_offset", True)

    elif modifier_type == "BEVEL":
        mod = obj.modifiers.new(name=modifier_name, type="BEVEL")
        mod.width = settings.get("width", 0.1)
        mod.segments = settings.get("segments", 2)
        mod.limit_method = settings.get("limit_method", "ANGLE")
        mod.angle_limit = settings.get("angle_limit", 0.523599)  # 30 degrees

    elif modifier_type == "DECIMATE":
        mod = obj.modifiers.new(name=modifier_name, type="DECIMATE")
        mod.decimate_type = settings.get("decimate_type", "COLLAPSE")
        mod.ratio = settings.get("ratio", 0.5)

    elif modifier_type == "REMESH":
        mod = obj.modifiers.new(name=modifier_name, type="REMESH")
        mod.mode = settings.get("mode", "VOXEL")
        mod.voxel_size = settings.get("voxel_size", 0.1)
        mod.adaptivity = settings.get("adaptivity", 0.0)

    elif modifier_type == "SMOOTH":
        mod = obj.modifiers.new(name=modifier_name, type="SMOOTH")
        mod.factor = settings.get("factor", 0.5)
        mod.iterations = settings.get("iterations", 2)

    elif modifier_type == "WAVE":
        mod = obj.modifiers.new(name=modifier_name, type="WAVE")
        mod.height = settings.get("height", 1.0)
        mod.width = settings.get("width_wave", 1.0)
        mod.speed = settings.get("speed", 1.0)
        mod.offset = settings.get("offset", 0.0)

    elif modifier_type == "DISPLACE":
        mod = obj.modifiers.new(name=modifier_name, type="DISPLACE")
        mod.strength = settings.get("strength", 1.0)
        mod.mid_level = settings.get("mid_level", 0.5)
        # Could add texture support here

    else:
        return {"success": False, "error": f"Unsupported modifier type: {modifier_type}"}

    # Update the object to apply the modifier
    obj.update_from_editmode()

    return {"success": True, "modifier": modifier_name}


def apply_modifier(args):
    """Apply a modifier permanently to an object."""
    object_name = args["object_name"]
    modifier_name = args["modifier_name"]

    # Get the object
    if object_name not in bpy.data.objects:
        return {"success": False, "error": f"Object '{object_name}' not found"}

    obj = bpy.data.objects[object_name]

    # Find the modifier
    if modifier_name not in obj.modifiers:
        return {"success": False, "error": f"Modifier '{modifier_name}' not found on object"}

    # Select and make active
    bpy.context.view_layer.objects.active = obj
    obj.select_set(True)

    # Apply the modifier
    try:
        bpy.ops.object.modifier_apply(modifier=modifier_name)
        return {"success": True, "message": f"Modifier '{modifier_name}' applied"}
    except Exception as e:
        return {"success": False, "error": str(e)}


def remove_modifier(args):
    """Remove a modifier from an object."""
    object_name = args["object_name"]
    modifier_name = args["modifier_name"]

    # Get the object
    if object_name not in bpy.data.objects:
        return {"success": False, "error": f"Object '{object_name}' not found"}

    obj = bpy.data.objects[object_name]

    # Find and remove the modifier
    if modifier_name not in obj.modifiers:
        return {"success": False, "error": f"Modifier '{modifier_name}' not found on object"}

    obj.modifiers.remove(obj.modifiers[modifier_name])

    return {"success": True, "message": f"Modifier '{modifier_name}' removed"}


def stack_modifiers(args):
    """Add multiple modifiers in a specific order."""
    object_name = args["object_name"]
    modifier_stack = args["modifier_stack"]

    # Get the object
    if object_name not in bpy.data.objects:
        return {"success": False, "error": f"Object '{object_name}' not found"}

    added_modifiers = []

    for mod_config in modifier_stack:
        mod_args = {
            "object_name": object_name,
            "modifier_type": mod_config["type"],
            "settings": mod_config.get("settings", {}),
        }
        result = add_modifier(mod_args)

        if result["success"]:
            added_modifiers.append(result["modifier"])
        else:
            return {"success": False, "error": f"Failed to add modifier: {result['error']}", "added": added_modifiers}

    return {"success": True, "modifiers": added_modifiers}


def main():
    """Main entry point for modifier tools."""
    # Get arguments from command line
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument("--args", type=str, required=True)
    args = parser.parse_args()

    # Parse JSON arguments
    script_args = json.loads(args.args)

    # Load the project file
    project_path = script_args["project"]
    if Path(project_path).exists():
        bpy.ops.wm.open_mainfile(filepath=project_path)
    else:
        return {"success": False, "error": f"Project file not found: {project_path}"}

    # Execute the operation
    operation = script_args["operation"]

    if operation == "add_modifier":
        result = add_modifier(script_args)
    elif operation == "apply_modifier":
        result = apply_modifier(script_args)
    elif operation == "remove_modifier":
        result = remove_modifier(script_args)
    elif operation == "stack_modifiers":
        result = stack_modifiers(script_args)
    else:
        result = {"success": False, "error": f"Unknown operation: {operation}"}

    # Save the file
    if result.get("success"):
        bpy.ops.wm.save_mainfile(filepath=project_path)

    # Output result
    print(json.dumps(result))
    sys.exit(0 if result.get("success") else 1)


if __name__ == "__main__":
    main()
