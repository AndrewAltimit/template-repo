#!/usr/bin/env python3
"""Blender scene building and manipulation script."""

import json
import math
import sys
from pathlib import Path

import bpy


def clear_scene():
    """Clear all objects from the scene."""
    bpy.ops.object.select_all(action="SELECT")
    bpy.ops.object.delete(use_global=False)


def create_project(args, job_id):
    """Create a new Blender project from template."""
    try:
        template = args.get("template", "basic_scene")
        settings = args.get("settings", {})
        project_path = args.get("project_path")

        # Clear existing scene
        clear_scene()

        # Configure render settings
        scene = bpy.context.scene
        # Handle both old and new engine names
        engine = settings.get("engine", "CYCLES")
        if engine == "EEVEE":
            engine = "BLENDER_EEVEE"
        elif engine == "WORKBENCH":
            engine = "BLENDER_WORKBENCH"
        scene.render.engine = engine
        scene.render.resolution_x = settings.get("resolution", [1920, 1080])[0]
        scene.render.resolution_y = settings.get("resolution", [1920, 1080])[1]
        scene.render.fps = settings.get("fps", 24)

        # Set up scene based on template
        if template == "basic_scene":
            # Add ground plane
            bpy.ops.mesh.primitive_plane_add(size=20, location=(0, 0, 0))
            ground = bpy.context.active_object
            ground.name = "Ground"

            # Add sun light
            bpy.ops.object.light_add(type="SUN", location=(0, 0, 10))
            sun = bpy.context.active_object
            sun.name = "Sun"
            sun.data.energy = 5.0
            sun.rotation_euler = (0.785, 0, 0.785)

            # Add camera
            bpy.ops.object.camera_add(location=(7, -7, 5))
            camera = bpy.context.active_object
            camera.name = "Camera"
            camera.rotation_euler = (1.1, 0, 0.785)
            scene.camera = camera

        elif template == "studio_lighting":
            # Add key light
            bpy.ops.object.light_add(type="AREA", location=(3, -3, 3))
            key_light = bpy.context.active_object
            key_light.name = "Key Light"
            key_light.data.energy = 500
            key_light.data.size = 2.0
            key_light.rotation_euler = (1.2, 0, 0.6)

            # Add fill light
            bpy.ops.object.light_add(type="AREA", location=(-3, -2, 2))
            fill_light = bpy.context.active_object
            fill_light.name = "Fill Light"
            fill_light.data.energy = 200
            fill_light.data.size = 3.0
            fill_light.rotation_euler = (1.3, 0, -0.8)

            # Add rim light
            bpy.ops.object.light_add(type="AREA", location=(0, 4, 2))
            rim_light = bpy.context.active_object
            rim_light.name = "Rim Light"
            rim_light.data.energy = 300
            rim_light.data.size = 1.5
            rim_light.rotation_euler = (-0.5, 0, 0)

            # Add camera
            bpy.ops.object.camera_add(location=(4, -4, 2))
            camera = bpy.context.active_object
            camera.name = "Camera"
            camera.rotation_euler = (1.4, 0, 0.785)
            camera.data.lens = 85
            scene.camera = camera

            # Set world background
            world = scene.world
            world.use_nodes = True
            bg_node = world.node_tree.nodes["Background"]
            bg_node.inputs["Color"].default_value = (0.05, 0.05, 0.05, 1.0)

        elif template == "empty":
            # Just add a camera
            bpy.ops.object.camera_add(location=(7, -7, 5))
            camera = bpy.context.active_object
            camera.name = "Camera"
            camera.rotation_euler = (1.1, 0, 0.785)
            scene.camera = camera

        # Save project
        bpy.ops.wm.save_as_mainfile(filepath=project_path)

        return True

    except Exception as e:
        print(f"Error creating project: {e}")
        return False


def add_primitives(args, job_id):
    """Add primitive objects to the scene."""
    try:
        # Load project
        if "project" in args:
            bpy.ops.wm.open_mainfile(filepath=args["project"])

        objects = args.get("objects", [])

        for obj_data in objects:
            obj_type = obj_data.get("type")
            name = obj_data.get("name", obj_type.capitalize())
            location = obj_data.get("location", [0, 0, 0])
            rotation = obj_data.get("rotation", [0, 0, 0])
            scale = obj_data.get("scale", [1, 1, 1])

            # Create object based on type
            if obj_type == "cube":
                bpy.ops.mesh.primitive_cube_add(location=location)
            elif obj_type == "sphere":
                bpy.ops.mesh.primitive_uv_sphere_add(location=location)
            elif obj_type == "cylinder":
                bpy.ops.mesh.primitive_cylinder_add(location=location)
            elif obj_type == "cone":
                bpy.ops.mesh.primitive_cone_add(location=location)
            elif obj_type == "torus":
                bpy.ops.mesh.primitive_torus_add(location=location)
            elif obj_type == "plane":
                bpy.ops.mesh.primitive_plane_add(location=location)
            elif obj_type == "monkey":
                bpy.ops.mesh.primitive_monkey_add(location=location)
            else:
                continue

            # Configure object
            obj = bpy.context.active_object
            obj.name = name
            obj.rotation_euler = rotation
            obj.scale = scale

        # Save project
        if "project" in args:
            bpy.ops.wm.save_mainfile()

        return True

    except Exception as e:
        print(f"Error adding primitives: {e}")
        return False


def setup_lighting(args, job_id):
    """Setup scene lighting."""
    try:
        # Load project
        if "project" in args:
            bpy.ops.wm.open_mainfile(filepath=args["project"])

        lighting_type = args.get("lighting_type")
        settings = args.get("settings", {})

        # Remove existing lights (optional)
        for obj in bpy.data.objects:
            if obj.type == "LIGHT":
                bpy.data.objects.remove(obj, do_unlink=True)

        if lighting_type == "three_point":
            # Key light
            bpy.ops.object.light_add(type="AREA", location=(3, -3, 3))
            key = bpy.context.active_object
            key.name = "Key Light"
            key.data.energy = settings.get("strength", 1.0) * 500
            key.data.size = 2.0
            key.rotation_euler = (1.2, 0, 0.6)

            # Fill light
            bpy.ops.object.light_add(type="AREA", location=(-3, -2, 2))
            fill = bpy.context.active_object
            fill.name = "Fill Light"
            fill.data.energy = settings.get("strength", 1.0) * 200
            fill.data.size = 3.0
            fill.rotation_euler = (1.3, 0, -0.8)

            # Back light
            bpy.ops.object.light_add(type="AREA", location=(0, 4, 2))
            back = bpy.context.active_object
            back.name = "Back Light"
            back.data.energy = settings.get("strength", 1.0) * 300
            back.data.size = 1.5
            back.rotation_euler = (-0.5, 0, 0)

        elif lighting_type == "studio":
            # Create multiple soft box lights
            positions = [(4, -4, 3), (-4, -4, 3), (0, 4, 3), (0, -5, 1)]
            for i, pos in enumerate(positions):
                bpy.ops.object.light_add(type="AREA", location=pos)
                light = bpy.context.active_object
                light.name = f"Studio Light {i+1}"
                light.data.energy = settings.get("strength", 1.0) * 300
                light.data.size = 2.5
                # Point towards origin
                light.rotation_euler = (
                    math.atan2(pos[2], math.sqrt(pos[0] ** 2 + pos[1] ** 2)),
                    0,
                    math.atan2(pos[1], pos[0]) + math.pi / 2,
                )

        elif lighting_type == "hdri":
            # Set up HDRI lighting
            scene = bpy.context.scene
            world = scene.world
            world.use_nodes = True

            # Get node tree
            nodes = world.node_tree.nodes
            links = world.node_tree.links

            # Clear existing nodes
            nodes.clear()

            # Add nodes
            node_bg = nodes.new(type="ShaderNodeBackground")
            node_env = nodes.new(type="ShaderNodeTexEnvironment")
            node_output = nodes.new(type="ShaderNodeOutputWorld")

            # Load HDRI
            hdri_path = settings.get("hdri_path")
            if hdri_path and Path(hdri_path).exists():
                node_env.image = bpy.data.images.load(hdri_path)

            # Set strength
            node_bg.inputs["Strength"].default_value = settings.get("strength", 1.0)

            # Link nodes
            links.new(node_env.outputs["Color"], node_bg.inputs["Color"])
            links.new(node_bg.outputs["Background"], node_output.inputs["Surface"])

        elif lighting_type == "sun":
            # Add sun light
            bpy.ops.object.light_add(type="SUN", location=(0, 0, 10))
            sun = bpy.context.active_object
            sun.name = "Sun"
            sun.data.energy = settings.get("strength", 1.0) * 5.0
            sun.rotation_euler = (0.785, 0, 0.785)

            # Set color
            color = settings.get("color", [1, 1, 1])
            sun.data.color = color

        elif lighting_type == "area":
            # Add single area light
            bpy.ops.object.light_add(type="AREA", location=(0, 0, 5))
            area = bpy.context.active_object
            area.name = "Area Light"
            area.data.energy = settings.get("strength", 1.0) * 1000
            area.data.size = 5.0

        # Save project
        if "project" in args:
            bpy.ops.wm.save_mainfile()

        return True

    except Exception as e:
        print(f"Error setting up lighting: {e}")
        return False


def apply_material(args, job_id):
    """Apply material to an object."""
    try:
        # Load project
        if "project" in args:
            bpy.ops.wm.open_mainfile(filepath=args["project"])

        object_name = args.get("object_name")
        material_data = args.get("material", {})

        # Find object
        obj = bpy.data.objects.get(object_name)
        if not obj:
            print(f"Object '{object_name}' not found")
            return False

        # Create material
        mat_type = material_data.get("type", "principled")
        mat_name = f"{object_name}_{mat_type}"

        mat = bpy.data.materials.new(name=mat_name)
        mat.use_nodes = True

        # Get node tree
        nodes = mat.node_tree.nodes
        links = mat.node_tree.links

        # Clear existing nodes
        nodes.clear()

        # Add output node
        node_output = nodes.new(type="ShaderNodeOutputMaterial")
        node_output.location = (400, 0)

        if mat_type == "principled":
            # Principled BSDF (PBR)
            node_bsdf = nodes.new(type="ShaderNodeBsdfPrincipled")
            node_bsdf.location = (0, 0)

            # Set properties
            base_color = material_data.get("base_color", [0.8, 0.8, 0.8, 1.0])
            node_bsdf.inputs["Base Color"].default_value = base_color
            node_bsdf.inputs["Metallic"].default_value = material_data.get("metallic", 0.0)
            node_bsdf.inputs["Roughness"].default_value = material_data.get("roughness", 0.5)

            links.new(node_bsdf.outputs["BSDF"], node_output.inputs["Surface"])

        elif mat_type == "emission":
            # Emission shader
            node_emission = nodes.new(type="ShaderNodeEmission")
            node_emission.location = (0, 0)

            base_color = material_data.get("base_color", [1.0, 1.0, 1.0, 1.0])
            node_emission.inputs["Color"].default_value = base_color
            node_emission.inputs["Strength"].default_value = material_data.get("emission_strength", 1.0)

            links.new(node_emission.outputs["Emission"], node_output.inputs["Surface"])

        elif mat_type == "glass":
            # Glass shader
            node_glass = nodes.new(type="ShaderNodeBsdfGlass")
            node_glass.location = (0, 0)

            node_glass.inputs["IOR"].default_value = 1.45
            node_glass.inputs["Roughness"].default_value = material_data.get("roughness", 0.0)

            links.new(node_glass.outputs["BSDF"], node_output.inputs["Surface"])

        elif mat_type == "metal":
            # Metallic material
            node_bsdf = nodes.new(type="ShaderNodeBsdfPrincipled")
            node_bsdf.location = (0, 0)

            base_color = material_data.get("base_color", [0.7, 0.7, 0.7, 1.0])
            node_bsdf.inputs["Base Color"].default_value = base_color
            node_bsdf.inputs["Metallic"].default_value = 1.0
            node_bsdf.inputs["Roughness"].default_value = material_data.get("roughness", 0.2)

            links.new(node_bsdf.outputs["BSDF"], node_output.inputs["Surface"])

        elif mat_type == "plastic":
            # Plastic material
            node_bsdf = nodes.new(type="ShaderNodeBsdfPrincipled")
            node_bsdf.location = (0, 0)

            base_color = material_data.get("base_color", [0.5, 0.5, 0.8, 1.0])
            node_bsdf.inputs["Base Color"].default_value = base_color
            node_bsdf.inputs["Metallic"].default_value = 0.0
            node_bsdf.inputs["Roughness"].default_value = material_data.get("roughness", 0.4)
            node_bsdf.inputs["Clearcoat Weight"].default_value = 0.5

            links.new(node_bsdf.outputs["BSDF"], node_output.inputs["Surface"])

        elif mat_type == "wood":
            # Wood material with texture
            node_bsdf = nodes.new(type="ShaderNodeBsdfPrincipled")
            node_bsdf.location = (200, 0)

            # Add wood texture
            node_tex = nodes.new(type="ShaderNodeTexNoise")
            node_tex.location = (-200, 0)
            node_tex.inputs["Scale"].default_value = 5.0
            node_tex.inputs["Detail"].default_value = 5.0

            # Color ramp for wood pattern
            node_ramp = nodes.new(type="ShaderNodeValToRGB")
            node_ramp.location = (0, 0)
            node_ramp.color_ramp.elements[0].color = (0.2, 0.1, 0.05, 1.0)
            node_ramp.color_ramp.elements[1].color = (0.4, 0.2, 0.1, 1.0)

            links.new(node_tex.outputs["Fac"], node_ramp.inputs["Fac"])
            links.new(node_ramp.outputs["Color"], node_bsdf.inputs["Base Color"])
            node_bsdf.inputs["Roughness"].default_value = 0.7

            links.new(node_bsdf.outputs["BSDF"], node_output.inputs["Surface"])

        # Apply material to object
        if obj.data.materials:
            obj.data.materials[0] = mat
        else:
            obj.data.materials.append(mat)

        # Save project
        if "project" in args:
            bpy.ops.wm.save_mainfile()

        return True

    except Exception as e:
        print(f"Error applying material: {e}")
        return False


def import_model(args, job_id):
    """Import a 3D model into the scene."""
    try:
        # Load project
        if "project" in args:
            bpy.ops.wm.open_mainfile(filepath=args["project"])

        model_path = args.get("model_path")
        format = args.get("format", "").upper()
        location = args.get("location", [0, 0, 0])

        # Import based on format
        if format == "FBX":
            bpy.ops.import_scene.fbx(filepath=model_path)
        elif format == "OBJ":
            bpy.ops.import_scene.obj(filepath=model_path)
        elif format in ["GLTF", "GLB"]:
            bpy.ops.import_scene.gltf(filepath=model_path)
        elif format == "STL":
            bpy.ops.import_mesh.stl(filepath=model_path)
        elif format == "PLY":
            bpy.ops.import_mesh.ply(filepath=model_path)
        elif format == "COLLADA":
            bpy.ops.wm.collada_import(filepath=model_path)
        else:
            print(f"Unsupported format: {format}")
            return False

        # Move imported objects to location
        for obj in bpy.context.selected_objects:
            obj.location = location

        # Save project
        if "project" in args:
            bpy.ops.wm.save_mainfile()

        return True

    except Exception as e:
        print(f"Error importing model: {e}")
        return False


def export_scene(args, job_id):
    """Export scene to various formats."""
    try:
        # Load project
        if "project" in args:
            bpy.ops.wm.open_mainfile(filepath=args["project"])

        format = args.get("format", "").upper()
        output_path = args.get("output_path")
        selected_only = args.get("selected_only", False)

        # Select objects if needed
        if not selected_only:
            bpy.ops.object.select_all(action="SELECT")

        # Export based on format
        if format == "FBX":
            bpy.ops.export_scene.fbx(filepath=output_path, use_selection=selected_only)
        elif format == "OBJ":
            bpy.ops.export_scene.obj(filepath=output_path, use_selection=selected_only)
        elif format in ["GLTF", "GLB"]:
            bpy.ops.export_scene.gltf(filepath=output_path, use_selection=selected_only)
        elif format == "STL":
            bpy.ops.export_mesh.stl(filepath=output_path, use_selection=selected_only)
        elif format == "USD":
            bpy.ops.wm.usd_export(filepath=output_path, selected_objects_only=selected_only)
        else:
            print(f"Unsupported export format: {format}")
            return False

        return True

    except Exception as e:
        print(f"Error exporting scene: {e}")
        return False


def main():
    """Main entry point."""
    argv = sys.argv

    if "--" in argv:
        argv = argv[argv.index("--") + 1 :]

    if len(argv) < 2:
        print("Usage: blender --python scene_builder.py -- args.json job_id")
        sys.exit(1)

    args_file = argv[0]
    job_id = argv[1]

    with open(args_file, "r") as f:
        args = json.load(f)

    operation = args.get("operation")

    if operation == "create_project":
        success = create_project(args, job_id)
    elif operation == "add_primitives":
        success = add_primitives(args, job_id)
    elif operation == "setup_lighting":
        success = setup_lighting(args, job_id)
    elif operation == "apply_material":
        success = apply_material(args, job_id)
    elif operation == "import_model":
        success = import_model(args, job_id)
    elif operation == "export_scene":
        success = export_scene(args, job_id)
    else:
        print(f"Unknown operation: {operation}")
        sys.exit(1)

    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
