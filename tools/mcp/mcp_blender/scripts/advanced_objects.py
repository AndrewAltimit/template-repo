#!/usr/bin/env python3
"""Blender advanced object operations.

Covers constraints, armatures, text objects, object relations, and advanced primitives.
"""

import json
import sys

import bpy


def add_constraint(args, _job_id):
    """Add constraint to an object.

    Parameters:
        project: Blender project file path
        object_name: Object to add constraint to
        constraint_type: Type of constraint (TRACK_TO, COPY_LOCATION, COPY_ROTATION,
                        COPY_SCALE, LIMIT_LOCATION, LIMIT_ROTATION, LIMIT_SCALE,
                        FOLLOW_PATH, CLAMP_TO, CHILD_OF, FLOOR, DAMPED_TRACK)
        target_object: Target object for constraint (if applicable)
        settings: Constraint-specific settings dict
    """
    try:
        if "project" in args:
            bpy.ops.wm.open_mainfile(filepath=args["project"])

        object_name = args.get("object_name")
        constraint_type = args.get("constraint_type", "TRACK_TO")
        target_name = args.get("target_object")
        settings = args.get("settings", {})

        obj = bpy.data.objects.get(object_name)
        if not obj:
            print(f"Error: Object '{object_name}' not found")
            return False

        target = bpy.data.objects.get(target_name) if target_name else None

        # Add constraint
        constraint = obj.constraints.new(type=constraint_type)

        # Set target if applicable
        if target and hasattr(constraint, "target"):
            constraint.target = target

        # Apply common settings
        if "name" in settings:
            constraint.name = settings["name"]
        if "influence" in settings:
            constraint.influence = settings["influence"]

        # Type-specific settings
        if constraint_type == "TRACK_TO":
            constraint.track_axis = settings.get("track_axis", "TRACK_NEGATIVE_Z")
            constraint.up_axis = settings.get("up_axis", "UP_Y")

        elif constraint_type == "COPY_LOCATION":
            constraint.use_x = settings.get("use_x", True)
            constraint.use_y = settings.get("use_y", True)
            constraint.use_z = settings.get("use_z", True)
            constraint.use_offset = settings.get("use_offset", False)

        elif constraint_type == "COPY_ROTATION":
            constraint.use_x = settings.get("use_x", True)
            constraint.use_y = settings.get("use_y", True)
            constraint.use_z = settings.get("use_z", True)
            constraint.mix_mode = settings.get("mix_mode", "REPLACE")

        elif constraint_type == "COPY_SCALE":
            constraint.use_x = settings.get("use_x", True)
            constraint.use_y = settings.get("use_y", True)
            constraint.use_z = settings.get("use_z", True)

        elif constraint_type in ("LIMIT_LOCATION", "LIMIT_ROTATION", "LIMIT_SCALE"):
            for axis in ("x", "y", "z"):
                for bound in ("min", "max"):
                    key = f"{bound}_{axis}"
                    if key in settings:
                        setattr(constraint, key, settings[key])
                    use_key = f"use_{bound}_{axis}"
                    if use_key in settings:
                        setattr(constraint, use_key, settings[use_key])

        elif constraint_type == "FOLLOW_PATH":
            constraint.use_curve_follow = settings.get("use_curve_follow", True)
            constraint.forward_axis = settings.get("forward_axis", "FORWARD_Y")
            constraint.up_axis = settings.get("up_axis", "UP_Z")
            if "offset" in settings:
                constraint.offset = settings["offset"]

        elif constraint_type == "DAMPED_TRACK":
            constraint.track_axis = settings.get("track_axis", "TRACK_Y")

        elif constraint_type == "FLOOR":
            constraint.use_rotation = settings.get("use_rotation", False)
            if "offset" in settings:
                constraint.offset = settings["offset"]

        if "project" in args:
            bpy.ops.wm.save_mainfile()

        print(
            json.dumps(
                {
                    "success": True,
                    "object": object_name,
                    "constraint": constraint.name,
                    "type": constraint_type,
                }
            )
        )
        return True

    except Exception as e:
        print(f"Error adding constraint: {e}")
        return False


def create_armature(args, _job_id):
    """Create an armature with bones.

    Parameters:
        project: Blender project file path
        name: Armature name (default: Armature)
        location: World location [x, y, z]
        bones: List of bone definitions:
            - name: Bone name
            - head: Head position [x, y, z] in armature space
            - tail: Tail position [x, y, z] in armature space
            - parent: Parent bone name (optional)
            - connected: Connect to parent (default: False)
            - roll: Bone roll in radians (default: 0)
    """
    try:
        if "project" in args:
            bpy.ops.wm.open_mainfile(filepath=args["project"])

        name = args.get("name", "Armature")
        location = args.get("location", [0, 0, 0])
        bones_data = args.get("bones", [])

        # Create armature data
        armature_data = bpy.data.armatures.new(name)
        armature_obj = bpy.data.objects.new(name, armature_data)
        armature_obj.location = location

        # Link to scene
        bpy.context.collection.objects.link(armature_obj)
        bpy.context.view_layer.objects.active = armature_obj
        armature_obj.select_set(True)

        # Enter edit mode to add bones
        bpy.ops.object.mode_set(mode="EDIT")

        bone_refs = {}
        for bone_data in bones_data:
            bone_name = bone_data.get("name", "Bone")
            head = bone_data.get("head", [0, 0, 0])
            tail = bone_data.get("tail", [0, 0, 1])
            parent_name = bone_data.get("parent")
            connected = bone_data.get("connected", False)
            roll = bone_data.get("roll", 0)

            # Create bone
            bone = armature_data.edit_bones.new(bone_name)
            bone.head = head
            bone.tail = tail
            bone.roll = roll

            # Set parent
            if parent_name and parent_name in bone_refs:
                bone.parent = bone_refs[parent_name]
                bone.use_connect = connected

            bone_refs[bone_name] = bone

        # Return to object mode
        bpy.ops.object.mode_set(mode="OBJECT")

        if "project" in args:
            bpy.ops.wm.save_mainfile()

        print(
            json.dumps(
                {
                    "success": True,
                    "armature": name,
                    "bone_count": len(bones_data),
                    "bones": list(bone_refs.keys()),
                }
            )
        )
        return True

    except Exception as e:
        print(f"Error creating armature: {e}")
        import traceback

        traceback.print_exc()
        return False


def parent_objects(args, _job_id):
    """Set parent-child relationships between objects.

    Parameters:
        project: Blender project file path
        parent_name: Name of parent object
        children: List of child object names
        keep_transform: Keep world transform (default: True)
        parent_type: OBJECT, ARMATURE, BONE, VERTEX, etc. (default: OBJECT)
        bone_name: Bone name if parent_type is BONE
    """
    try:
        if "project" in args:
            bpy.ops.wm.open_mainfile(filepath=args["project"])

        parent_name = args.get("parent_name")
        children = args.get("children", [])
        keep_transform = args.get("keep_transform", True)
        parent_type = args.get("parent_type", "OBJECT")
        bone_name = args.get("bone_name")

        parent = bpy.data.objects.get(parent_name)
        if not parent:
            print(f"Error: Parent object '{parent_name}' not found")
            return False

        parented = []
        for child_name in children:
            child = bpy.data.objects.get(child_name)
            if not child:
                print(f"Warning: Child '{child_name}' not found, skipping")
                continue

            child.parent = parent
            child.parent_type = parent_type

            if parent_type == "BONE" and bone_name:
                child.parent_bone = bone_name

            if keep_transform:
                child.matrix_parent_inverse = parent.matrix_world.inverted()

            parented.append(child_name)

        if "project" in args:
            bpy.ops.wm.save_mainfile()

        print(json.dumps({"success": True, "parent": parent_name, "children_parented": parented}))
        return True

    except Exception as e:
        print(f"Error parenting objects: {e}")
        return False


def join_objects(args, _job_id):
    """Join multiple mesh objects into one.

    Parameters:
        project: Blender project file path
        object_names: List of object names to join
        target_name: Name of target object (will contain joined result)
    """
    try:
        if "project" in args:
            bpy.ops.wm.open_mainfile(filepath=args["project"])

        object_names = args.get("object_names", [])
        target_name = args.get("target_name")

        if len(object_names) < 2:
            print("Error: Need at least 2 objects to join")
            return False

        target = bpy.data.objects.get(target_name)
        if not target or target.type != "MESH":
            print(f"Error: Target '{target_name}' not found or not a mesh")
            return False

        # Deselect all
        bpy.ops.object.select_all(action="DESELECT")

        # Select objects to join
        for name in object_names:
            obj = bpy.data.objects.get(name)
            if obj and obj.type == "MESH":
                obj.select_set(True)

        # Set target as active
        bpy.context.view_layer.objects.active = target

        # Join
        bpy.ops.object.join()

        if "project" in args:
            bpy.ops.wm.save_mainfile()

        print(
            json.dumps(
                {
                    "success": True,
                    "result": target_name,
                    "objects_joined": len(object_names),
                }
            )
        )
        return True

    except Exception as e:
        print(f"Error joining objects: {e}")
        return False


def create_text_object(args, _job_id):
    """Create a 3D text object.

    Parameters:
        project: Blender project file path
        text: Text content
        name: Object name (default: Text)
        location: World location [x, y, z]
        rotation: Euler rotation [x, y, z] in radians
        size: Text size (default: 1.0)
        extrude: Extrusion depth (default: 0.0)
        bevel_depth: Bevel depth (default: 0.0)
        bevel_resolution: Bevel resolution (default: 0)
        align_x: CENTER, LEFT, RIGHT, JUSTIFY, FLUSH (default: LEFT)
        align_y: TOP, CENTER, BOTTOM (default: TOP)
        font_path: Path to font file (optional)
    """
    try:
        if "project" in args:
            bpy.ops.wm.open_mainfile(filepath=args["project"])

        text = args.get("text", "Text")
        name = args.get("name", "Text")
        location = args.get("location", [0, 0, 0])
        rotation = args.get("rotation", [0, 0, 0])
        size = args.get("size", 1.0)
        extrude = args.get("extrude", 0.0)
        bevel_depth = args.get("bevel_depth", 0.0)
        bevel_resolution = args.get("bevel_resolution", 0)
        align_x = args.get("align_x", "LEFT")
        align_y = args.get("align_y", "TOP")
        font_path = args.get("font_path")

        # Create text curve
        text_data = bpy.data.curves.new(name=name, type="FONT")
        text_data.body = text
        text_data.size = size
        text_data.extrude = extrude
        text_data.bevel_depth = bevel_depth
        text_data.bevel_resolution = bevel_resolution
        text_data.align_x = align_x
        text_data.align_y = align_y

        # Load font if specified
        if font_path:
            try:
                font = bpy.data.fonts.load(font_path)
                text_data.font = font
            except Exception as e:
                print(f"Warning: Could not load font: {e}")

        # Create object
        text_obj = bpy.data.objects.new(name, text_data)
        text_obj.location = location
        text_obj.rotation_euler = rotation

        bpy.context.collection.objects.link(text_obj)

        if "project" in args:
            bpy.ops.wm.save_mainfile()

        print(
            json.dumps(
                {
                    "success": True,
                    "object": name,
                    "text": text[:50] + "..." if len(text) > 50 else text,
                }
            )
        )
        return True

    except Exception as e:
        print(f"Error creating text object: {e}")
        return False


def add_advanced_primitives(args, _job_id):
    """Add advanced primitive objects.

    Supports additional primitives not in the basic add_primitives:
    - grid: 2D grid mesh
    - circle: Circle curve or mesh
    - ico_sphere: Icosphere
    - empty: Empty object (various types)
    - bezier_curve: Bezier curve
    - nurbs_curve: NURBS curve
    - metaball: Metaball object

    Parameters:
        project: Blender project file path
        objects: List of object definitions with:
            - type: grid, circle, ico_sphere, empty, bezier_curve, nurbs_curve, metaball
            - name: Object name
            - location: [x, y, z]
            - rotation: [x, y, z] in radians
            - scale: [x, y, z]
            - Additional type-specific parameters
    """
    try:
        if "project" in args:
            bpy.ops.wm.open_mainfile(filepath=args["project"])

        objects = args.get("objects", [])
        created = []

        for obj_data in objects:
            obj_type = obj_data.get("type")
            name = obj_data.get("name", obj_type.capitalize())
            location = obj_data.get("location", [0, 0, 0])
            rotation = obj_data.get("rotation", [0, 0, 0])
            scale = obj_data.get("scale", [1, 1, 1])

            if obj_type == "grid":
                x_subdivisions = obj_data.get("x_subdivisions", 10)
                y_subdivisions = obj_data.get("y_subdivisions", 10)
                size = obj_data.get("size", 2.0)
                bpy.ops.mesh.primitive_grid_add(
                    x_subdivisions=x_subdivisions,
                    y_subdivisions=y_subdivisions,
                    size=size,
                    location=location,
                )

            elif obj_type == "circle":
                vertices = obj_data.get("vertices", 32)
                radius = obj_data.get("radius", 1.0)
                fill_type = obj_data.get("fill_type", "NOTHING")  # NOTHING, NGON, TRIFAN
                bpy.ops.mesh.primitive_circle_add(
                    vertices=vertices,
                    radius=radius,
                    fill_type=fill_type,
                    location=location,
                )

            elif obj_type == "ico_sphere":
                subdivisions = obj_data.get("subdivisions", 2)
                radius = obj_data.get("radius", 1.0)
                bpy.ops.mesh.primitive_ico_sphere_add(subdivisions=subdivisions, radius=radius, location=location)

            elif obj_type == "empty":
                empty_type = obj_data.get(
                    "empty_type", "PLAIN_AXES"
                )  # PLAIN_AXES, ARROWS, SINGLE_ARROW, CIRCLE, CUBE, SPHERE, IMAGE
                display_size = obj_data.get("display_size", 1.0)
                bpy.ops.object.empty_add(type=empty_type, location=location)
                bpy.context.active_object.empty_display_size = display_size

            elif obj_type == "bezier_curve":
                bpy.ops.curve.primitive_bezier_curve_add(location=location)

            elif obj_type == "nurbs_curve":
                bpy.ops.curve.primitive_nurbs_curve_add(location=location)

            elif obj_type == "nurbs_circle":
                bpy.ops.curve.primitive_nurbs_circle_add(location=location)

            elif obj_type == "metaball":
                metaball_type = obj_data.get("metaball_type", "BALL")  # BALL, CAPSULE, PLANE, ELLIPSOID, CUBE
                bpy.ops.object.metaball_add(type=metaball_type, location=location)

            else:
                print(f"Unknown primitive type: {obj_type}")
                continue

            # Configure created object
            obj = bpy.context.active_object
            obj.name = name
            obj.rotation_euler = rotation
            obj.scale = scale
            created.append(name)

        if "project" in args:
            bpy.ops.wm.save_mainfile()

        print(json.dumps({"success": True, "objects_created": created}))
        return True

    except Exception as e:
        print(f"Error adding advanced primitives: {e}")
        return False


def apply_automatic_weights(args, _job_id):
    """Apply automatic weights from armature to mesh.

    Parameters:
        project: Blender project file path
        mesh_name: Name of mesh object
        armature_name: Name of armature object
    """
    try:
        if "project" in args:
            bpy.ops.wm.open_mainfile(filepath=args["project"])

        mesh_name = args.get("mesh_name")
        armature_name = args.get("armature_name")

        mesh = bpy.data.objects.get(mesh_name)
        armature = bpy.data.objects.get(armature_name)

        if not mesh or mesh.type != "MESH":
            print(f"Error: Mesh '{mesh_name}' not found")
            return False

        if not armature or armature.type != "ARMATURE":
            print(f"Error: Armature '{armature_name}' not found")
            return False

        # Deselect all, select mesh then armature (armature must be active)
        bpy.ops.object.select_all(action="DESELECT")
        mesh.select_set(True)
        armature.select_set(True)
        bpy.context.view_layer.objects.active = armature

        # Parent with automatic weights
        bpy.ops.object.parent_set(type="ARMATURE_AUTO")

        if "project" in args:
            bpy.ops.wm.save_mainfile()

        print(json.dumps({"success": True, "mesh": mesh_name, "armature": armature_name}))
        return True

    except Exception as e:
        print(f"Error applying automatic weights: {e}")
        return False


def main():
    """Main entry point."""
    argv = sys.argv

    if "--" in argv:
        argv = argv[argv.index("--") + 1 :]

    if len(argv) < 1:
        print("Usage: blender --python advanced_objects.py -- <json_args>")
        sys.exit(1)

    args = json.loads(argv[0])
    job_id = args.get("job_id", "unknown")
    operation = args.get("operation")

    operations = {
        "add_constraint": add_constraint,
        "create_armature": create_armature,
        "parent_objects": parent_objects,
        "join_objects": join_objects,
        "create_text_object": create_text_object,
        "add_advanced_primitives": add_advanced_primitives,
        "apply_automatic_weights": apply_automatic_weights,
    }

    func = operations.get(operation)
    if func:
        success = func(args, job_id)
    else:
        print(f"Unknown operation: {operation}")
        sys.exit(1)

    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
