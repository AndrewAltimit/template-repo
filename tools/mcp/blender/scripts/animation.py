#!/usr/bin/env python3
"""Blender animation script."""

import json
import sys

import bpy


def create_animation(args, job_id):
    """Create keyframe animation for objects."""
    try:
        # Load project
        if "project" in args:
            bpy.ops.wm.open_mainfile(filepath=args["project"])

        object_name = args.get("object_name")
        keyframes = args.get("keyframes", [])
        interpolation = args.get("interpolation", "BEZIER")

        # Find object
        obj = bpy.data.objects.get(object_name)
        if not obj:
            print(f"Object '{object_name}' not found")
            return False

        # Clear existing keyframes
        obj.animation_data_clear()

        # Create keyframes
        for kf in keyframes:
            frame = kf.get("frame")
            if frame is None:
                continue

            # Set frame
            bpy.context.scene.frame_set(frame)

            # Set transform properties
            if "location" in kf:
                obj.location = kf["location"]
                obj.keyframe_insert(data_path="location", frame=frame)

            if "rotation" in kf:
                obj.rotation_euler = kf["rotation"]
                obj.keyframe_insert(data_path="rotation_euler", frame=frame)

            if "scale" in kf:
                obj.scale = kf["scale"]
                obj.keyframe_insert(data_path="scale", frame=frame)

        # Set interpolation mode
        if obj.animation_data and obj.animation_data.action:
            for fcurve in obj.animation_data.action.fcurves:
                for keyframe in fcurve.keyframe_points:
                    keyframe.interpolation = interpolation

        # Save project
        if "project" in args:
            bpy.ops.wm.save_mainfile()

        return True

    except Exception as e:
        print(f"Error creating animation: {e}")
        return False


def setup_armature(args, job_id):
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


def apply_constraints(args, job_id):
    """Apply animation constraints to objects."""
    try:
        # Load project
        if "project" in args:
            bpy.ops.wm.open_mainfile(filepath=args["project"])

        object_name = args.get("object_name")
        constraints = args.get("constraints", [])

        # Find object
        obj = bpy.data.objects.get(object_name)
        if not obj:
            return False

        # Apply constraints
        for constraint_data in constraints:
            constraint_type = constraint_data.get("type")
            target_name = constraint_data.get("target")

            # Add constraint
            if constraint_type == "copy_location":
                constraint = obj.constraints.new("COPY_LOCATION")
                if target_name:
                    target = bpy.data.objects.get(target_name)
                    if target:
                        constraint.target = target
                constraint.use_x = constraint_data.get("use_x", True)
                constraint.use_y = constraint_data.get("use_y", True)
                constraint.use_z = constraint_data.get("use_z", True)

            elif constraint_type == "copy_rotation":
                constraint = obj.constraints.new("COPY_ROTATION")
                if target_name:
                    target = bpy.data.objects.get(target_name)
                    if target:
                        constraint.target = target
                constraint.use_x = constraint_data.get("use_x", True)
                constraint.use_y = constraint_data.get("use_y", True)
                constraint.use_z = constraint_data.get("use_z", True)

            elif constraint_type == "track_to":
                constraint = obj.constraints.new("TRACK_TO")
                if target_name:
                    target = bpy.data.objects.get(target_name)
                    if target:
                        constraint.target = target
                constraint.track_axis = constraint_data.get("track_axis", "TRACK_NEGATIVE_Z")
                constraint.up_axis = constraint_data.get("up_axis", "UP_Y")

            elif constraint_type == "limit_location":
                constraint = obj.constraints.new("LIMIT_LOCATION")
                if "min_x" in constraint_data:
                    constraint.use_min_x = True
                    constraint.min_x = constraint_data["min_x"]
                if "max_x" in constraint_data:
                    constraint.use_max_x = True
                    constraint.max_x = constraint_data["max_x"]
                if "min_y" in constraint_data:
                    constraint.use_min_y = True
                    constraint.min_y = constraint_data["min_y"]
                if "max_y" in constraint_data:
                    constraint.use_max_y = True
                    constraint.max_y = constraint_data["max_y"]
                if "min_z" in constraint_data:
                    constraint.use_min_z = True
                    constraint.min_z = constraint_data["min_z"]
                if "max_z" in constraint_data:
                    constraint.use_max_z = True
                    constraint.max_z = constraint_data["max_z"]

            elif constraint_type == "follow_path":
                constraint = obj.constraints.new("FOLLOW_PATH")
                if target_name:
                    target = bpy.data.objects.get(target_name)
                    if target and target.type == "CURVE":
                        constraint.target = target
                constraint.use_curve_follow = constraint_data.get("follow", True)
                constraint.forward_axis = constraint_data.get("forward", "FORWARD_X")
                constraint.up_axis = constraint_data.get("up", "UP_Y")

        # Save project
        if "project" in args:
            bpy.ops.wm.save_mainfile()

        return True

    except Exception as e:
        print(f"Error applying constraints: {e}")
        return False


def create_motion_path(args, job_id):
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


def create_shape_keys(args, job_id):
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


def create_nla_tracks(args, job_id):
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


def main():
    """Main entry point."""
    argv = sys.argv

    if "--" in argv:
        argv = argv[argv.index("--") + 1 :]

    if len(argv) < 2:
        print("Usage: blender --python animation.py -- args.json job_id")
        sys.exit(1)

    args_file = argv[0]
    job_id = argv[1]

    with open(args_file, "r") as f:
        args = json.load(f)

    operation = args.get("operation")

    if operation == "create_animation":
        success = create_animation(args, job_id)
    elif operation == "setup_armature":
        success = setup_armature(args, job_id)
    elif operation == "apply_constraints":
        success = apply_constraints(args, job_id)
    elif operation == "create_motion_path":
        success = create_motion_path(args, job_id)
    elif operation == "create_shape_keys":
        success = create_shape_keys(args, job_id)
    elif operation == "create_nla_tracks":
        success = create_nla_tracks(args, job_id)
    else:
        print(f"Unknown operation: {operation}")
        sys.exit(1)

    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
