#!/usr/bin/env python3
"""Camera manipulation tools for Blender."""

import os
import sys

import bpy

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from mcp_common import (  # noqa: E402  pylint: disable=wrong-import-position
    project_operation,
    run,
)


def setup_camera(args):
    """Create or update a camera and make it the scene's active camera.

    Accepts the flat MCP parameters (``sensor_width``, ``dof_enabled``,
    ``focus_distance``, ``aperture``) as well as the legacy nested
    ``depth_of_field`` dict.
    """
    camera_name = args.get("camera_name") or "Camera"
    location = args.get("location", [7, -7, 5])
    rotation = args.get("rotation", [1.1, 0, 0.785])
    focal_length = float(args.get("focal_length", 50))
    sensor_width = float(args.get("sensor_width", 36))
    dof = dict(args.get("depth_of_field") or {})
    if "dof_enabled" in args:
        dof["enabled"] = args["dof_enabled"]
    if "focus_distance" in args:
        dof["focus_distance"] = args["focus_distance"]
    if "aperture" in args:
        dof["f_stop"] = args["aperture"]
    focus_object = args.get("focus_object")

    camera_obj = bpy.data.objects.get(camera_name)
    if camera_obj is not None and camera_obj.type != "CAMERA":
        return {"success": False, "error": f"'{camera_name}' exists but is a {camera_obj.type}, not a camera"}
    created = camera_obj is None
    if created:
        camera_data = bpy.data.cameras.new(name=camera_name)
        camera_obj = bpy.data.objects.new(camera_name, camera_data)
        bpy.context.scene.collection.objects.link(camera_obj)
    camera = camera_obj.data

    camera_obj.location = location
    camera_obj.rotation_euler = rotation
    camera.lens = focal_length
    camera.sensor_fit = "HORIZONTAL"
    camera.sensor_width = sensor_width

    camera.dof.use_dof = bool(dof.get("enabled", False))
    if camera.dof.use_dof:
        camera.dof.focus_distance = float(dof.get("focus_distance", 10))
        camera.dof.aperture_fstop = float(dof.get("f_stop", 2.8))
        if focus_object:
            target = bpy.data.objects.get(focus_object)
            if target is None:
                return {"success": False, "error": f"focus_object '{focus_object}' not found"}
            camera.dof.focus_object = target

    if args.get("set_active", True):
        bpy.context.scene.camera = camera_obj

    return {
        "success": True,
        "camera": camera_obj.name,
        "created": created,
        "active": bpy.context.scene.camera == camera_obj,
        "dof_enabled": camera.dof.use_dof,
    }


def add_camera_track(args):
    """Point a camera at a target object with a tracking constraint."""
    camera_name = args.get("camera_name") or (bpy.context.scene.camera.name if bpy.context.scene.camera else "Camera")
    target_object = args.get("target") or args.get("target_object")
    track_type = args.get("track_type", "TRACK_TO")
    if track_type not in ("TRACK_TO", "DAMPED_TRACK", "LOCKED_TRACK"):
        return {"success": False, "error": f"Unknown track_type '{track_type}'"}

    camera_obj = bpy.data.objects.get(camera_name)
    if camera_obj is None:
        return {"success": False, "error": f"Camera '{camera_name}' not found"}
    if camera_obj.type != "CAMERA":
        return {"success": False, "error": f"'{camera_name}' is not a camera"}
    target_obj = bpy.data.objects.get(target_object) if target_object else None
    if target_obj is None:
        return {"success": False, "error": f"Target object '{target_object}' not found"}

    # Replace any existing tracking constraint so repeated calls do not stack.
    for constraint in list(camera_obj.constraints):
        if constraint.type in ("TRACK_TO", "DAMPED_TRACK", "LOCKED_TRACK"):
            camera_obj.constraints.remove(constraint)

    constraint = camera_obj.constraints.new(track_type)
    constraint.target = target_obj
    constraint.track_axis = "TRACK_NEGATIVE_Z"
    if track_type == "TRACK_TO":
        constraint.up_axis = "UP_Y"
    elif track_type == "LOCKED_TRACK":
        constraint.lock_axis = "LOCK_Y"

    return {"success": True, "camera": camera_obj.name, "target": target_obj.name, "constraint": track_type}


def create_camera_path(args):
    """Create a camera path animation."""
    camera_name = args.get("camera_name", "Camera")
    path_points = args["path_points"]
    frame_duration = args.get("frame_duration", 100)
    look_at = args.get("look_at", None)

    # Get camera object
    if camera_name not in bpy.data.objects:
        return {"success": False, "error": f"Camera '{camera_name}' not found"}

    camera_obj = bpy.data.objects[camera_name]

    # Clear existing animation data
    camera_obj.animation_data_clear()

    # Create keyframes for camera path
    frames_per_point = frame_duration // len(path_points)

    for i, point in enumerate(path_points):
        frame = i * frames_per_point + 1

        # Set location
        camera_obj.location = point.get("location", camera_obj.location)
        camera_obj.keyframe_insert(data_path="location", frame=frame)

        # Set rotation if provided
        if "rotation" in point:
            camera_obj.rotation_euler = point["rotation"]
            camera_obj.keyframe_insert(data_path="rotation_euler", frame=frame)
        elif look_at:
            # Point camera at target
            if look_at in bpy.data.objects:
                target = bpy.data.objects[look_at]
                direction = target.location - camera_obj.location
                rot_quat = direction.to_track_quat("-Z", "Y")
                camera_obj.rotation_euler = rot_quat.to_euler()
                camera_obj.keyframe_insert(data_path="rotation_euler", frame=frame)

    # Set interpolation mode
    if camera_obj.animation_data and camera_obj.animation_data.action:
        for fcurve in camera_obj.animation_data.action.fcurves:
            for keyframe in fcurve.keyframe_points:
                keyframe.interpolation = "BEZIER"
                keyframe.handle_left_type = "AUTO"
                keyframe.handle_right_type = "AUTO"

    return {"success": True, "frames": len(path_points) * frames_per_point}


def main():
    """Dispatch the requested operation (see mcp_common.run)."""
    run(
        {
            "setup_camera": project_operation(setup_camera),
            "add_camera_track": project_operation(add_camera_track),
            "create_camera_path": project_operation(create_camera_path),
        }
    )


if __name__ == "__main__":
    main()
