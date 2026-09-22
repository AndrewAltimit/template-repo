#!/usr/bin/env python3
"""Blender animation script."""

import os
import sys

import bpy

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from mcp_common import (  # noqa: E402  pylint: disable=wrong-import-position
    ScriptError,
    open_project,
    require_object,
    run,
    save_project,
)


def create_animation(args, _job_id):
    """Replace an object's animation with the given transform keyframes."""
    open_project(args.get("project"))
    object_name = args.get("object_name")
    keyframes = args.get("keyframes") or []
    interpolation = str(args.get("interpolation", "BEZIER")).upper()
    if interpolation not in ("LINEAR", "BEZIER", "CONSTANT"):
        raise ScriptError(f"Unknown interpolation '{interpolation}' (LINEAR, BEZIER, CONSTANT)")
    if not keyframes:
        raise ScriptError("At least one keyframe is required")

    obj = require_object(object_name)
    obj.animation_data_clear()

    keyed = 0
    frames = []
    for kf in keyframes:
        frame = kf.get("frame")
        if frame is None:
            raise ScriptError(f"Keyframe without a frame number: {kf}")
        wrote = False
        if "location" in kf:
            obj.location = kf["location"]
            obj.keyframe_insert(data_path="location", frame=frame)
            wrote = True
        if "rotation" in kf:
            obj.rotation_euler = kf["rotation"]
            obj.keyframe_insert(data_path="rotation_euler", frame=frame)
            wrote = True
        if "scale" in kf:
            obj.scale = kf["scale"]
            obj.keyframe_insert(data_path="scale", frame=frame)
            wrote = True
        if not wrote:
            raise ScriptError(f"Keyframe at frame {frame} sets none of location/rotation/scale")
        keyed += 1
        frames.append(frame)

    if obj.animation_data and obj.animation_data.action:
        for fcurve in _action_fcurves(obj.animation_data.action):
            for point in fcurve.keyframe_points:
                point.interpolation = interpolation

    scene = bpy.context.scene
    if max(frames) > scene.frame_end:
        scene.frame_end = int(max(frames))
    save_project()
    return {"success": True, "object": obj.name, "keyframes": keyed, "frame_range": [min(frames), max(frames)]}


def setup_armature(args, _job_id):
    """Setup armature for rigging."""
    try:
        # Load project
        if "project" in args:
            bpy.ops.wm.open_mainfile(filepath=args["project"])

        armature_name = args.get("name", "Armature")
        bones = args.get("bones", [])

        # Create armature
        bpy.ops.object.armature_add(location=(0, 0, 0))
        armature = bpy.context.active_object
        armature.name = armature_name

        # Enter edit mode
        bpy.ops.object.mode_set(mode="EDIT")

        # Get armature data
        arm_data = armature.data
        edit_bones = arm_data.edit_bones

        # Remove default bone
        for bone in edit_bones:
            edit_bones.remove(bone)

        # Create bones
        for bone_data in bones:
            bone_name = bone_data.get("name", "Bone")
            head = bone_data.get("head", [0, 0, 0])
            tail = bone_data.get("tail", [0, 0, 1])
            parent_name = bone_data.get("parent")

            # Create bone
            bone = edit_bones.new(bone_name)
            bone.head = head
            bone.tail = tail

            # Set parent if specified
            if parent_name:
                parent = edit_bones.get(parent_name)
                if parent:
                    bone.parent = parent
                    bone.use_connect = bone_data.get("connected", False)

        # Return to object mode
        bpy.ops.object.mode_set(mode="OBJECT")

        # Save project
        if "project" in args:
            bpy.ops.wm.save_mainfile()

        return True

    except Exception as e:
        print(f"Error setting up armature: {e}")
        return False


def _apply_copy_constraint(obj, constraint_data, constraint_type_name):
    """Apply copy location or rotation constraint."""
    constraint = obj.constraints.new(constraint_type_name)
    target_name = constraint_data.get("target")
    if target_name:
        target = bpy.data.objects.get(target_name)
        if target:
            constraint.target = target
    constraint.use_x = constraint_data.get("use_x", True)
    constraint.use_y = constraint_data.get("use_y", True)
    constraint.use_z = constraint_data.get("use_z", True)


def _apply_track_to_constraint(obj, constraint_data):
    """Apply track-to constraint."""
    constraint = obj.constraints.new("TRACK_TO")
    target_name = constraint_data.get("target")
    if target_name:
        target = bpy.data.objects.get(target_name)
        if target:
            constraint.target = target
    constraint.track_axis = constraint_data.get("track_axis", "TRACK_NEGATIVE_Z")
    constraint.up_axis = constraint_data.get("up_axis", "UP_Y")


def _apply_limit_location_constraint(obj, constraint_data):
    """Apply limit location constraint."""
    constraint = obj.constraints.new("LIMIT_LOCATION")
    for axis in ["x", "y", "z"]:
        min_key = f"min_{axis}"
        max_key = f"max_{axis}"
        if min_key in constraint_data:
            setattr(constraint, f"use_min_{axis}", True)
            setattr(constraint, f"min_{axis}", constraint_data[min_key])
        if max_key in constraint_data:
            setattr(constraint, f"use_max_{axis}", True)
            setattr(constraint, f"max_{axis}", constraint_data[max_key])


def _apply_follow_path_constraint(obj, constraint_data):
    """Apply follow path constraint."""
    constraint = obj.constraints.new("FOLLOW_PATH")
    target_name = constraint_data.get("target")
    if target_name:
        target = bpy.data.objects.get(target_name)
        if target and target.type == "CURVE":
            constraint.target = target
    constraint.use_curve_follow = constraint_data.get("follow", True)
    constraint.forward_axis = constraint_data.get("forward", "FORWARD_X")
    constraint.up_axis = constraint_data.get("up", "UP_Y")


def apply_constraints(args, _job_id):
    """Apply animation constraints to objects."""
    try:
        if "project" in args:
            bpy.ops.wm.open_mainfile(filepath=args["project"])

        object_name = args.get("object_name")
        constraints = args.get("constraints", [])

        obj = bpy.data.objects.get(object_name)
        if not obj:
            return False

        for constraint_data in constraints:
            constraint_type = constraint_data.get("type")

            if constraint_type == "copy_location":
                _apply_copy_constraint(obj, constraint_data, "COPY_LOCATION")
            elif constraint_type == "copy_rotation":
                _apply_copy_constraint(obj, constraint_data, "COPY_ROTATION")
            elif constraint_type == "track_to":
                _apply_track_to_constraint(obj, constraint_data)
            elif constraint_type == "limit_location":
                _apply_limit_location_constraint(obj, constraint_data)
            elif constraint_type == "follow_path":
                _apply_follow_path_constraint(obj, constraint_data)

        if "project" in args:
            bpy.ops.wm.save_mainfile()

        return True

    except Exception as e:
        print(f"Error applying constraints: {e}")
        return False


def create_motion_path(args, _job_id):
    """Create motion path for animation."""
    try:
        # Load project
        if "project" in args:
            bpy.ops.wm.open_mainfile(filepath=args["project"])

        path_name = args.get("name", "MotionPath")
        points = args.get("points", [])
        cyclic = args.get("cyclic", False)

        # Create curve
        curve_data = bpy.data.curves.new(name=path_name, type="CURVE")
        curve_data.dimensions = "3D"

        # Create spline
        spline = curve_data.splines.new("BEZIER")
        spline.bezier_points.add(len(points) - 1)

        # Set points
        for i, point in enumerate(points):
            bp = spline.bezier_points[i]
            bp.co = point.get("co", [0, 0, 0])
            bp.handle_left = point.get("handle_left", bp.co)
            bp.handle_right = point.get("handle_right", bp.co)
            bp.handle_left_type = point.get("handle_type", "AUTO")
            bp.handle_right_type = point.get("handle_type", "AUTO")

        # Set cyclic
        spline.use_cyclic_u = cyclic

        # Create object
        curve_obj = bpy.data.objects.new(path_name, curve_data)
        bpy.context.collection.objects.link(curve_obj)

        # Save project
        if "project" in args:
            bpy.ops.wm.save_mainfile()

        return True

    except Exception as e:
        print(f"Error creating motion path: {e}")
        return False


def create_shape_keys(args, _job_id):
    """Create shape keys for mesh deformation."""
    try:
        # Load project
        if "project" in args:
            bpy.ops.wm.open_mainfile(filepath=args["project"])

        object_name = args.get("object_name")
        shape_keys = args.get("shape_keys", [])

        # Find object
        obj = bpy.data.objects.get(object_name)
        if not obj or obj.type != "MESH":
            return False

        # Make active
        bpy.context.view_layer.objects.active = obj

        # Add basis shape key if needed
        if not obj.data.shape_keys:
            obj.shape_key_add(name="Basis")

        # Add shape keys
        for sk_data in shape_keys:
            name = sk_data.get("name", "Key")

            # Add shape key
            sk = obj.shape_key_add(name=name)

            # Set value
            if "value" in sk_data:
                sk.value = sk_data["value"]

            # Set vertex positions if provided
            if "vertices" in sk_data:
                for i, vert_pos in enumerate(sk_data["vertices"]):
                    if i < len(sk.data):
                        sk.data[i].co = vert_pos

            # Add keyframes if specified
            if "keyframes" in sk_data:
                for kf in sk_data["keyframes"]:
                    frame = kf.get("frame")
                    value = kf.get("value", 0)

                    bpy.context.scene.frame_set(frame)
                    sk.value = value
                    sk.keyframe_insert(data_path="value", frame=frame)

        # Save project
        if "project" in args:
            bpy.ops.wm.save_mainfile()

        return True

    except Exception as e:
        print(f"Error creating shape keys: {e}")
        return False


def create_nla_tracks(args, _job_id):
    """Create NLA (Non-Linear Animation) tracks."""
    try:
        # Load project
        if "project" in args:
            bpy.ops.wm.open_mainfile(filepath=args["project"])

        object_name = args.get("object_name")
        tracks = args.get("tracks", [])

        # Find object
        obj = bpy.data.objects.get(object_name)
        if not obj or not obj.animation_data:
            return False

        # Get NLA tracks
        nla_tracks = obj.animation_data.nla_tracks

        # Create tracks
        for track_data in tracks:
            track_name = track_data.get("name", "Track")

            # Create track
            track = nla_tracks.new()
            track.name = track_name

            # Add strips
            strips = track_data.get("strips", [])
            for strip_data in strips:
                action_name = strip_data.get("action")
                if not action_name:
                    continue

                # Find action
                action = bpy.data.actions.get(action_name)
                if not action:
                    continue

                # Create strip
                strip = track.strips.new(
                    name=strip_data.get("name", action_name),
                    start=strip_data.get("start", 1),
                    action=action,
                )

                # Configure strip
                strip.blend_type = strip_data.get("blend", "REPLACE")
                strip.influence = strip_data.get("influence", 1.0)
                strip.use_auto_blend = strip_data.get("auto_blend", False)

                # Set repeat if specified
                if "repeat" in strip_data:
                    strip.repeat = strip_data["repeat"]

        # Save project
        if "project" in args:
            bpy.ops.wm.save_mainfile()

        return True

    except Exception as e:
        print(f"Error creating NLA tracks: {e}")
        return False


def _action_fcurves(action):
    """All F-curves of an action, across legacy and slotted (4.4+) layouts."""
    curves = []
    layers = getattr(action, "layers", None)
    if layers:
        for layer in layers:
            for strip in layer.strips:
                for bag in getattr(strip, "channelbags", []):
                    curves.extend(bag.fcurves)
    if not curves and hasattr(action, "fcurves"):
        curves.extend(action.fcurves)
    return curves


def main():
    """Dispatch the requested operation (see mcp_common.run)."""
    run(
        {
            "create_animation": create_animation,
            "setup_armature": setup_armature,
            "apply_constraints": apply_constraints,
            "create_motion_path": create_motion_path,
            "create_shape_keys": create_shape_keys,
            "create_nla_tracks": create_nla_tracks,
        }
    )


if __name__ == "__main__":
    main()
