#!/usr/bin/env python3
"""Blender scene building and manipulation script."""

import json
import math
from pathlib import Path
import sys

import bpy


def write_result(job_id, result_data):
    """Write operation result to a file for the handler to read.

    Args:
        job_id: The job identifier
        result_data: Dictionary containing the operation result
    """
    result_dir = Path("/app/outputs/jobs")
    result_dir.mkdir(parents=True, exist_ok=True)
    result_file = result_dir / f"{job_id}.result"
    result_file.write_text(json.dumps(result_data), encoding="utf-8")


def clear_scene():
    """Clear all objects from the scene."""
    bpy.ops.object.select_all(action="SELECT")
    bpy.ops.object.delete(use_global=False)


def create_project(args, _job_id):
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
            engine = "BLENDER_EEVEE_NEXT"
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

        elif template == "lit_empty":
            # No ground plane, but with three-point lighting for good illumination
            # Key light (main light source) - very high energy for Eevee
            bpy.ops.object.light_add(type="AREA", location=(3, -3, 3))
            key = bpy.context.active_object
            key.name = "Key Light"
            key.data.energy = 50000  # Very high energy for bright Eevee render
            key.data.size = 3.0
            key.rotation_euler = (1.2, 0, 0.6)

            # Fill light (softer, fills shadows)
            bpy.ops.object.light_add(type="AREA", location=(-3, -2, 2))
            fill = bpy.context.active_object
            fill.name = "Fill Light"
            fill.data.energy = 20000
            fill.data.size = 4.0
            fill.rotation_euler = (1.3, 0, -0.8)

            # Back light (rim/separation light)
            bpy.ops.object.light_add(type="AREA", location=(0, 4, 2))
            back = bpy.context.active_object
            back.name = "Back Light"
            back.data.energy = 30000
            back.data.size = 2.0
            back.rotation_euler = (-0.5, 0, 0)

            # Top light for overall brightness
            bpy.ops.object.light_add(type="AREA", location=(0, 0, 5))
            top = bpy.context.active_object
            top.name = "Top Light"
            top.data.energy = 25000
            top.data.size = 5.0
            top.rotation_euler = (0, 0, 0)

            # Add camera
            bpy.ops.object.camera_add(location=(7, -7, 5))
            camera = bpy.context.active_object
            camera.name = "Camera"
            camera.rotation_euler = (1.1, 0, 0.785)
            scene.camera = camera

            # Set neutral gray world background
            world = scene.world
            if world is None:
                world = bpy.data.worlds.new("World")
                scene.world = world
            world.use_nodes = True
            bg_node = world.node_tree.nodes.get("Background")
            if bg_node:
                bg_node.inputs["Color"].default_value = (0.3, 0.3, 0.3, 1.0)
                bg_node.inputs["Strength"].default_value = 1.0

        # Save project
        bpy.ops.wm.save_as_mainfile(filepath=project_path)

        return True

    except Exception as e:
        print(f"Error creating project: {e}")
        return False


def add_primitives(args, _job_id):
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
            elif obj_type in ("sphere", "uv_sphere"):
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


def setup_lighting(args, _job_id):
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
                light.name = f"Studio Light {i + 1}"
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


def apply_material(args, _job_id):
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
            emission_strength = material_data.get("emission_strength", 1.0)
            node_emission.inputs["Strength"].default_value = emission_strength

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


def import_model(args, _job_id):
    """Import a 3D model into the scene."""
    try:
        # Load project
        if "project" in args:
            bpy.ops.wm.open_mainfile(filepath=args["project"])

        model_path = args.get("model_path")
        file_format = args.get("format", "").upper()
        location = args.get("location", [0, 0, 0])

        # Import based on format
        if file_format == "FBX":
            bpy.ops.import_scene.fbx(filepath=model_path)
        elif file_format == "OBJ":
            bpy.ops.import_scene.obj(filepath=model_path)
        elif file_format in ["GLTF", "GLB"]:
            bpy.ops.import_scene.gltf(filepath=model_path)
        elif file_format == "STL":
            bpy.ops.import_mesh.stl(filepath=model_path)
        elif file_format == "PLY":
            bpy.ops.import_mesh.ply(filepath=model_path)
        elif file_format == "COLLADA":
            bpy.ops.wm.collada_import(filepath=model_path)
        else:
            print(f"Unsupported format: {file_format}")
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


def delete_objects(args, job_id):
    """Delete objects from the scene by name or type."""
    try:
        # Load project
        if "project" in args:
            bpy.ops.wm.open_mainfile(filepath=args["project"])

        object_names = args.get("object_names", [])
        object_types = args.get("object_types", [])
        pattern = args.get("pattern")
        deleted = []

        # Delete by exact name
        for name in object_names:
            obj = bpy.data.objects.get(name)
            if obj:
                bpy.data.objects.remove(obj, do_unlink=True)
                deleted.append(name)

        # Delete by type (MESH, LIGHT, CAMERA, EMPTY, CURVE, etc.)
        if object_types:
            for obj in list(bpy.data.objects):
                if obj.type in object_types:
                    deleted.append(obj.name)
                    bpy.data.objects.remove(obj, do_unlink=True)

        # Delete by name pattern (simple wildcard support)
        if pattern:
            import fnmatch

            for obj in list(bpy.data.objects):
                if fnmatch.fnmatch(obj.name, pattern):
                    deleted.append(obj.name)
                    bpy.data.objects.remove(obj, do_unlink=True)

        # Save project
        if "project" in args:
            bpy.ops.wm.save_mainfile()

        # Write result to file for handler to read
        write_result(job_id, {"deleted_objects": deleted})

        # Output result for parsing (kept for backward compatibility)
        print(f"DELETED_OBJECTS:{','.join(deleted)}")
        return True

    except Exception as e:
        print(f"Error deleting objects: {e}")
        return False


def create_curve(args, _job_id):
    """Create Bézier curves for growth paths and spatial guides.

    Creates curves that can be used as targets for proximity-based effects
    or as guides for procedural growth patterns.

    Args:
        project: Blender project file path
        name: Name for the curve object (default: "GrowthPath")
        curve_type: Type of curve - BEZIER, NURBS, POLY (default: BEZIER)
        points: List of control points [[x, y, z], ...] (default: creates a simple path)
        closed: Whether to close the curve (default: False)
        resolution: Curve resolution (default: 12)
        bevel_depth: Bevel depth for 3D curve (default: 0.0)
        target_object: Optional - position curve on this object's surface
        surface_offset: Offset from surface if target_object specified (default: 0.05)
    """
    try:
        # Load project
        if "project" in args:
            bpy.ops.wm.open_mainfile(filepath=args["project"])

        name = args.get("name", "GrowthPath")
        curve_type = args.get("curve_type", "BEZIER")
        points = args.get("points")
        closed = args.get("closed", False)
        resolution = args.get("resolution", 12)
        bevel_depth = args.get("bevel_depth", 0.0)
        target_object = args.get("target_object")
        surface_offset = args.get("surface_offset", 0.05)

        # Create default points if not provided
        if not points:
            points = [
                [-1.0, 0.0, 0.5],
                [0.0, 0.5, 0.7],
                [1.0, 0.0, 0.5],
            ]

        # Create curve data
        curve_data = bpy.data.curves.new(name=name, type="CURVE")
        curve_data.dimensions = "3D"
        curve_data.resolution_u = resolution
        curve_data.bevel_depth = bevel_depth

        # Create spline
        if curve_type == "NURBS":
            spline = curve_data.splines.new("NURBS")
        elif curve_type == "POLY":
            spline = curve_data.splines.new("POLY")
        else:
            spline = curve_data.splines.new("BEZIER")

        spline.use_cyclic_u = closed

        # Add points to spline
        if curve_type == "BEZIER":
            spline.bezier_points.add(len(points) - 1)
            for i, point in enumerate(points):
                bp = spline.bezier_points[i]
                bp.co = point
                # Auto-calculate handles
                bp.handle_left_type = "AUTO"
                bp.handle_right_type = "AUTO"
        else:
            spline.points.add(len(points) - 1)
            for i, point in enumerate(points):
                # NURBS/Poly points have 4 components (x, y, z, w)
                spline.points[i].co = (*point, 1.0)

        # Create curve object
        curve_obj = bpy.data.objects.new(name, curve_data)
        bpy.context.collection.objects.link(curve_obj)

        # If target object specified, project curve onto surface
        if target_object:
            target = bpy.data.objects.get(target_object)
            if target and target.type == "MESH":
                # Use shrinkwrap modifier to project curve onto surface
                shrinkwrap = curve_obj.modifiers.new(name="ShrinkwrapCurve", type="SHRINKWRAP")
                shrinkwrap.target = target
                shrinkwrap.offset = surface_offset
                shrinkwrap.wrap_method = "NEAREST_SURFACEPOINT"

        # Save project
        if "project" in args:
            bpy.ops.wm.save_mainfile()

        print(f"Created curve: {name} with {len(points)} points")
        return True

    except Exception as e:
        print(f"Error creating curve: {e}")
        return False


def add_texture(args, _job_id):
    """Add a texture to an object."""
    try:
        # Load project
        if "project" in args:
            bpy.ops.wm.open_mainfile(filepath=args["project"])

        object_name = args.get("object_name")
        texture_type = args.get("texture_type")
        settings = args.get("settings", {})

        # Find object
        obj = bpy.data.objects.get(object_name)
        if not obj:
            print(f"Object '{object_name}' not found")
            return False

        # Ensure object has a material
        if not obj.data.materials:
            mat = bpy.data.materials.new(name=f"{object_name}_material")
            mat.use_nodes = True
            obj.data.materials.append(mat)
        mat = obj.data.materials[0]

        # Get or create node tree
        if not mat.use_nodes:
            mat.use_nodes = True
        nodes = mat.node_tree.nodes
        links = mat.node_tree.links

        # Find principled BSDF
        bsdf = None
        for node in nodes:
            if node.type == "BSDF_PRINCIPLED":
                bsdf = node
                break

        if not bsdf:
            print("No Principled BSDF found")
            return False

        # Add texture node based on type
        if texture_type == "IMAGE":
            tex_node = nodes.new(type="ShaderNodeTexImage")
            tex_node.location = (-300, 300)
            image_path = settings.get("image_path")
            if image_path and Path(image_path).exists():
                tex_node.image = bpy.data.images.load(image_path)
            links.new(tex_node.outputs["Color"], bsdf.inputs["Base Color"])

        elif texture_type == "NOISE":
            tex_node = nodes.new(type="ShaderNodeTexNoise")
            tex_node.location = (-300, 300)
            tex_node.inputs["Scale"].default_value = settings.get("scale", 5.0)
            tex_node.inputs["Detail"].default_value = settings.get("detail", 2.0)
            links.new(tex_node.outputs["Fac"], bsdf.inputs["Roughness"])

        elif texture_type == "VORONOI":
            tex_node = nodes.new(type="ShaderNodeTexVoronoi")
            tex_node.location = (-300, 300)
            tex_node.inputs["Scale"].default_value = settings.get("scale", 5.0)
            links.new(tex_node.outputs["Distance"], bsdf.inputs["Roughness"])

        elif texture_type == "MUSGRAVE":
            tex_node = nodes.new(type="ShaderNodeTexMusgrave")
            tex_node.location = (-300, 300)
            tex_node.inputs["Scale"].default_value = settings.get("scale", 5.0)
            links.new(tex_node.outputs["Fac"], bsdf.inputs["Roughness"])

        elif texture_type == "GRADIENT":
            tex_node = nodes.new(type="ShaderNodeTexGradient")
            tex_node.location = (-300, 300)
            links.new(tex_node.outputs["Color"], bsdf.inputs["Base Color"])

        elif texture_type == "CHECKER":
            tex_node = nodes.new(type="ShaderNodeTexChecker")
            tex_node.location = (-300, 300)
            tex_node.inputs["Scale"].default_value = settings.get("scale", 5.0)
            links.new(tex_node.outputs["Color"], bsdf.inputs["Base Color"])

        else:
            print(f"Unknown texture type: {texture_type}")
            return False

        # Save project
        if "project" in args:
            bpy.ops.wm.save_mainfile()

        return True

    except Exception as e:
        print(f"Error adding texture: {e}")
        return False


def add_uv_map(args, _job_id):
    """Add UV mapping to an object."""
    try:
        # Load project
        if "project" in args:
            bpy.ops.wm.open_mainfile(filepath=args["project"])

        object_name = args.get("object_name")
        projection_type = args.get("projection_type", "SMART_PROJECT")

        # Find object
        obj = bpy.data.objects.get(object_name)
        if not obj:
            print(f"Object '{object_name}' not found")
            return False

        if obj.type != "MESH":
            print(f"Object '{object_name}' is not a mesh")
            return False

        # Select and make active
        bpy.ops.object.select_all(action="DESELECT")
        obj.select_set(True)
        bpy.context.view_layer.objects.active = obj

        # Enter edit mode for UV projection
        bpy.ops.object.mode_set(mode="EDIT")
        bpy.ops.mesh.select_all(action="SELECT")

        # Apply UV projection
        if projection_type == "SMART_PROJECT":
            bpy.ops.uv.smart_project(angle_limit=math.radians(66))
        elif projection_type == "CUBE_PROJECT":
            bpy.ops.uv.cube_project()
        elif projection_type == "CYLINDER_PROJECT":
            bpy.ops.uv.cylinder_project()
        elif projection_type == "SPHERE_PROJECT":
            bpy.ops.uv.sphere_project()
        elif projection_type == "PROJECT_FROM_VIEW":
            bpy.ops.uv.project_from_view()
        else:
            print(f"Unknown projection type: {projection_type}")
            bpy.ops.object.mode_set(mode="OBJECT")
            return False

        # Return to object mode
        bpy.ops.object.mode_set(mode="OBJECT")

        # Save project
        if "project" in args:
            bpy.ops.wm.save_mainfile()

        return True

    except Exception as e:
        print(f"Error adding UV map: {e}")
        # Try to return to object mode
        try:
            bpy.ops.object.mode_set(mode="OBJECT")
        except Exception:
            pass
        return False


def setup_compositor(args, _job_id):
    """Setup compositor nodes for post-processing."""
    try:
        # Load project
        if "project" in args:
            bpy.ops.wm.open_mainfile(filepath=args["project"])

        setup = args.get("setup")
        settings = args.get("settings", {})

        scene = bpy.context.scene
        scene.use_nodes = True
        tree = scene.node_tree
        nodes = tree.nodes
        links = tree.links

        # Clear existing nodes
        nodes.clear()

        # Add render layers node
        render_layers = nodes.new(type="CompositorNodeRLayers")
        render_layers.location = (0, 300)

        # Add composite output
        composite = nodes.new(type="CompositorNodeComposite")
        composite.location = (800, 300)

        # Add viewer
        viewer = nodes.new(type="CompositorNodeViewer")
        viewer.location = (800, 0)

        if setup == "BASIC":
            # Direct connection
            links.new(render_layers.outputs["Image"], composite.inputs["Image"])
            links.new(render_layers.outputs["Image"], viewer.inputs["Image"])

        elif setup == "DENOISING":
            # Add denoise node
            denoise = nodes.new(type="CompositorNodeDenoise")
            denoise.location = (400, 300)
            links.new(render_layers.outputs["Image"], denoise.inputs["Image"])
            links.new(denoise.outputs["Image"], composite.inputs["Image"])
            links.new(denoise.outputs["Image"], viewer.inputs["Image"])

        elif setup == "COLOR_GRADING":
            # Add color balance and curves
            color_balance = nodes.new(type="CompositorNodeColorBalance")
            color_balance.location = (400, 300)
            curves = nodes.new(type="CompositorNodeCurveRGB")
            curves.location = (600, 300)
            links.new(render_layers.outputs["Image"], color_balance.inputs["Image"])
            links.new(color_balance.outputs["Image"], curves.inputs["Image"])
            links.new(curves.outputs["Image"], composite.inputs["Image"])
            links.new(curves.outputs["Image"], viewer.inputs["Image"])

        elif setup == "GLARE":
            # Add glare node
            glare = nodes.new(type="CompositorNodeGlare")
            glare.location = (400, 300)
            glare.glare_type = "FOG_GLOW"
            glare.threshold = settings.get("threshold", 1.0)
            links.new(render_layers.outputs["Image"], glare.inputs["Image"])
            links.new(glare.outputs["Image"], composite.inputs["Image"])
            links.new(glare.outputs["Image"], viewer.inputs["Image"])

        elif setup == "FOG_GLOW":
            # Add fog glow effect
            glare = nodes.new(type="CompositorNodeGlare")
            glare.location = (400, 300)
            glare.glare_type = "FOG_GLOW"
            glare.quality = "HIGH"
            links.new(render_layers.outputs["Image"], glare.inputs["Image"])
            links.new(glare.outputs["Image"], composite.inputs["Image"])
            links.new(glare.outputs["Image"], viewer.inputs["Image"])

        elif setup == "LENS_DISTORTION":
            # Add lens distortion
            lens = nodes.new(type="CompositorNodeLensdist")
            lens.location = (400, 300)
            lens.inputs["Distort"].default_value = settings.get("distort", 0.0)
            lens.inputs["Dispersion"].default_value = settings.get("dispersion", 0.0)
            links.new(render_layers.outputs["Image"], lens.inputs["Image"])
            links.new(lens.outputs["Image"], composite.inputs["Image"])
            links.new(lens.outputs["Image"], viewer.inputs["Image"])

        elif setup == "VIGNETTE":
            # Create vignette effect with ellipse mask
            ellipse = nodes.new(type="CompositorNodeEllipseMask")
            ellipse.location = (200, 0)
            ellipse.width = 0.8
            ellipse.height = 0.8
            blur = nodes.new(type="CompositorNodeBlur")
            blur.location = (400, 0)
            blur.size_x = 200
            blur.size_y = 200
            mix = nodes.new(type="CompositorNodeMixRGB")
            mix.location = (600, 300)
            mix.blend_type = "MULTIPLY"
            links.new(render_layers.outputs["Image"], mix.inputs[1])
            links.new(ellipse.outputs["Mask"], blur.inputs["Image"])
            links.new(blur.outputs["Image"], mix.inputs[2])
            links.new(mix.outputs["Image"], composite.inputs["Image"])
            links.new(mix.outputs["Image"], viewer.inputs["Image"])

        else:
            print(f"Unknown compositor setup: {setup}")
            return False

        # Save project
        if "project" in args:
            bpy.ops.wm.save_mainfile()

        return True

    except Exception as e:
        print(f"Error setting up compositor: {e}")
        return False


def analyze_scene(args, job_id):
    """Analyze scene for statistics and potential issues."""
    try:
        # Load project
        if "project" in args:
            bpy.ops.wm.open_mainfile(filepath=args["project"])

        analysis_type = args.get("analysis_type", "BASIC")
        result = {}

        # Count objects by type
        object_counts = {}
        total_vertices = 0
        total_faces = 0
        total_tris = 0

        for obj in bpy.data.objects:
            obj_type = obj.type
            object_counts[obj_type] = object_counts.get(obj_type, 0) + 1

            if obj.type == "MESH" and obj.data:
                mesh = obj.data
                total_vertices += len(mesh.vertices)
                total_faces += len(mesh.polygons)
                # Count triangles
                for poly in mesh.polygons:
                    total_tris += len(poly.vertices) - 2

        result["object_counts"] = object_counts
        result["total_objects"] = len(bpy.data.objects)
        result["total_vertices"] = total_vertices
        result["total_faces"] = total_faces
        result["total_triangles"] = total_tris
        result["materials"] = len(bpy.data.materials)
        result["textures"] = len(bpy.data.images)

        if analysis_type in ("DETAILED", "PERFORMANCE", "MEMORY"):
            # Additional detailed info
            result["meshes"] = len(bpy.data.meshes)
            result["curves"] = len(bpy.data.curves)
            result["lights"] = len(bpy.data.lights)
            result["cameras"] = len(bpy.data.cameras)
            result["collections"] = len(bpy.data.collections)
            result["worlds"] = len(bpy.data.worlds)
            result["scenes"] = len(bpy.data.scenes)

        if analysis_type == "PERFORMANCE":
            # Performance-related warnings
            warnings = []
            if total_tris > 1000000:
                warnings.append(f"High triangle count: {total_tris}")
            if len(bpy.data.materials) > 50:
                warnings.append(f"Many materials: {len(bpy.data.materials)}")
            result["warnings"] = warnings

        if analysis_type == "MEMORY":
            # Memory estimation (rough)
            vertex_mem = total_vertices * 12  # 3 floats * 4 bytes
            face_mem = total_faces * 16  # Average 4 indices * 4 bytes
            result["estimated_mesh_memory_mb"] = round((vertex_mem + face_mem) / (1024 * 1024), 2)

        # Write result to file for handler to read
        write_result(job_id, result)

        # Also print for stdout parsing
        print(json.dumps(result))
        return True

    except Exception as e:
        print(f"Error analyzing scene: {e}")
        return False


def optimize_scene(args, _job_id):
    """Optimize scene for better performance."""
    try:
        # Load project
        if "project" in args:
            bpy.ops.wm.open_mainfile(filepath=args["project"])

        optimization_type = args.get("optimization_type")
        settings = args.get("settings", {})

        if optimization_type == "MESH_CLEANUP":
            # Clean up meshes
            for obj in bpy.data.objects:
                if obj.type == "MESH":
                    bpy.ops.object.select_all(action="DESELECT")
                    obj.select_set(True)
                    bpy.context.view_layer.objects.active = obj
                    bpy.ops.object.mode_set(mode="EDIT")
                    # Remove doubles
                    bpy.ops.mesh.select_all(action="SELECT")
                    bpy.ops.mesh.remove_doubles(threshold=settings.get("merge_threshold", 0.0001))
                    # Delete loose vertices
                    bpy.ops.mesh.delete_loose()
                    bpy.ops.object.mode_set(mode="OBJECT")

        elif optimization_type == "TEXTURE_OPTIMIZATION":
            # Resize large textures
            max_size = settings.get("max_size", 2048)
            for image in bpy.data.images:
                if image.size[0] > max_size or image.size[1] > max_size:
                    scale = max_size / max(image.size)
                    new_width = int(image.size[0] * scale)
                    new_height = int(image.size[1] * scale)
                    image.scale(new_width, new_height)

        elif optimization_type == "MODIFIER_APPLY":
            # Apply modifiers
            for obj in bpy.data.objects:
                if obj.type == "MESH":
                    bpy.ops.object.select_all(action="DESELECT")
                    obj.select_set(True)
                    bpy.context.view_layer.objects.active = obj
                    for modifier in obj.modifiers[:]:
                        try:
                            bpy.ops.object.modifier_apply(modifier=modifier.name)
                        except Exception:
                            pass  # Skip modifiers that can't be applied

        elif optimization_type == "INSTANCE_OPTIMIZATION":
            # Convert duplicates to instances
            # This is a simplified version - just links duplicate mesh data
            mesh_users = {}
            for obj in bpy.data.objects:
                if obj.type == "MESH" and obj.data:
                    key = (len(obj.data.vertices), len(obj.data.polygons))
                    if key not in mesh_users:
                        mesh_users[key] = []
                    mesh_users[key].append(obj)

        elif optimization_type == "MATERIAL_CLEANUP":
            # Remove unused materials
            for mat in bpy.data.materials:
                if not mat.users:
                    bpy.data.materials.remove(mat)

            # Remove unused images
            for img in bpy.data.images:
                if not img.users:
                    bpy.data.images.remove(img)

        else:
            print(f"Unknown optimization type: {optimization_type}")
            return False

        # Save project
        if "project" in args:
            bpy.ops.wm.save_mainfile()

        return True

    except Exception as e:
        print(f"Error optimizing scene: {e}")
        # Try to return to object mode
        try:
            bpy.ops.object.mode_set(mode="OBJECT")
        except Exception:
            pass
        return False


def export_scene(args, _job_id):
    """Export scene to various formats."""
    try:
        # Load project
        if "project" in args:
            bpy.ops.wm.open_mainfile(filepath=args["project"])

        file_format = args.get("format", "").upper()
        output_path = args.get("output_path")
        selected_only = args.get("selected_only", False)

        # Select objects if needed
        if not selected_only:
            bpy.ops.object.select_all(action="SELECT")

        # Export based on format
        if file_format == "FBX":
            bpy.ops.export_scene.fbx(filepath=output_path, use_selection=selected_only)
        elif file_format == "OBJ":
            bpy.ops.export_scene.obj(filepath=output_path, use_selection=selected_only)
        elif file_format in ["GLTF", "GLB"]:
            bpy.ops.export_scene.gltf(filepath=output_path, use_selection=selected_only)
        elif file_format == "STL":
            bpy.ops.export_mesh.stl(filepath=output_path, use_selection=selected_only)
        elif file_format == "USD":
            bpy.ops.wm.usd_export(filepath=output_path, selected_objects_only=selected_only)
        else:
            print(f"Unsupported export format: {file_format}")
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

    with open(args_file, "r", encoding="utf-8") as f:
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
    elif operation == "delete_objects":
        success = delete_objects(args, job_id)
    elif operation == "create_curve":
        success = create_curve(args, job_id)
    elif operation == "add_texture":
        success = add_texture(args, job_id)
    elif operation == "add_uv_map":
        success = add_uv_map(args, job_id)
    elif operation == "setup_compositor":
        success = setup_compositor(args, job_id)
    elif operation == "analyze_scene":
        success = analyze_scene(args, job_id)
    elif operation == "optimize_scene":
        success = optimize_scene(args, job_id)
    else:
        print(f"Unknown operation: {operation}")
        sys.exit(1)

    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
