#!/usr/bin/env python3
"""Camera manipulation tools for Blender."""

import json
import sys
from pathlib import Path

import bpy


def setup_camera(args):
    """Setup and configure camera in the scene."""
    camera_name = args.get("camera_name", "Camera")
    location = args.get("location", [7, -7, 5])
    rotation = args.get("rotation", [1.1, 0, 0.785])
    focal_length = args.get("focal_length", 50)
    dof = args.get("depth_of_field", {})

    # Check if camera exists, create if not
    if camera_name in bpy.data.objects:
        camera_obj = bpy.data.objects[camera_name]
        if camera_obj.type != "CAMERA":
            # Remove non-camera object with same name
            bpy.data.objects.remove(camera_obj, do_unlink=True)
            camera_obj = None
        else:
            camera = camera_obj.data
    else:
        camera_obj = None

    if camera_obj is None:
        # Create new camera
        camera = bpy.data.cameras.new(name=camera_name)
        camera_obj = bpy.data.objects.new(camera_name, camera)
        bpy.context.collection.objects.link(camera_obj)

    # Set camera properties
    camera_obj.location = location
    camera_obj.rotation_euler = rotation

    # Set camera lens properties
    camera.lens = focal_length
    camera.sensor_fit = "HORIZONTAL"
    camera.sensor_width = 36  # Full frame sensor

    # Setup depth of field if enabled
    if dof.get("enabled", False):
        camera.dof.use_dof = True
        camera.dof.focus_distance = dof.get("focus_distance", 10)
        camera.dof.aperture_fstop = dof.get("f_stop", 2.8)

    # Set as active camera
    bpy.context.scene.camera = camera_obj

    return {"success": True, "camera": camera_name}


def add_camera_track(args):
    """Add tracking constraint to camera."""
    camera_name = args.get("camera_name", "Camera")
    target_object = args["target_object"]
    track_type = args.get("track_type", "TRACK_TO")

    # Get camera object
    if camera_name not in bpy.data.objects:
        return {"success": False, "error": f"Camera '{camera_name}' not found"}

    camera_obj = bpy.data.objects[camera_name]

    if camera_obj.type != "CAMERA":
        return {"success": False, "error": f"'{camera_name}' is not a camera"}

    # Get target object
    if target_object not in bpy.data.objects:
        return {"success": False, "error": f"Target object '{target_object}' not found"}

    target_obj = bpy.data.objects[target_object]

    # Remove existing track constraints
    for constraint in camera_obj.constraints:
        if constraint.type in ["TRACK_TO", "DAMPED_TRACK", "LOCKED_TRACK"]:
            camera_obj.constraints.remove(constraint)

    # Add new tracking constraint
    if track_type == "TRACK_TO":
        constraint = camera_obj.constraints.new("TRACK_TO")
        constraint.target = target_obj
        constraint.track_axis = "TRACK_NEGATIVE_Z"
        constraint.up_axis = "UP_Y"
    elif track_type == "DAMPED_TRACK":
        constraint = camera_obj.constraints.new("DAMPED_TRACK")
        constraint.target = target_obj
        constraint.track_axis = "TRACK_NEGATIVE_Z"
    elif track_type == "LOCKED_TRACK":
        constraint = camera_obj.constraints.new("LOCKED_TRACK")
        constraint.target = target_obj
        constraint.track_axis = "TRACK_NEGATIVE_Z"
        constraint.lock_axis = "LOCK_Y"

    return {"success": True, "constraint": track_type}


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
    """Main entry point for camera tools."""
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

    if operation == "setup_camera":
        result = setup_camera(script_args)
    elif operation == "add_camera_track":
        result = add_camera_track(script_args)
    elif operation == "create_camera_path":
        result = create_camera_path(script_args)
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
