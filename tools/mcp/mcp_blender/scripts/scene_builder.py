#!/usr/bin/env python3
"""Blender scene building and manipulation script.

Run by the MCP server as ``blender --background --python scene_builder.py --
<args.json> <job_id>``; see ``mcp_common.py`` for the result protocol.
"""

import fnmatch
import hashlib
import math
import os
from pathlib import Path
import sys

import bpy

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from mcp_common import (  # noqa: E402  pylint: disable=wrong-import-position
    ScriptError,
    open_project,
    require_object,
    resolve_engine,
    run,
    save_project,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _add_camera(scene, location=(7, -7, 5), rotation=(1.1, 0, 0.785), lens=50.0):
    cam_data = bpy.data.cameras.new("Camera")
    cam_data.lens = lens
    camera = bpy.data.objects.new("Camera", cam_data)
    scene.collection.objects.link(camera)
    camera.location = location
    camera.rotation_euler = rotation
    scene.camera = camera
    return camera


def _add_light(scene, name, light_type, location, rotation=(0, 0, 0), energy=100.0, size=None):
    data = bpy.data.lights.new(name, light_type)
    data.energy = energy
    if size is not None and hasattr(data, "size"):
        data.size = size
    light = bpy.data.objects.new(name, data)
    scene.collection.objects.link(light)
    light.location = location
    light.rotation_euler = rotation
    return light


def _add_ground(size=20.0, name="Ground"):
    bpy.ops.mesh.primitive_plane_add(size=size, location=(0, 0, 0))
    ground = bpy.context.active_object
    ground.name = name
    return ground


def _three_point(scene, scale=1.0):
    _add_light(scene, "Key Light", "AREA", (3, -3, 3), (1.2, 0, 0.6), 500 * scale, 2.0)
    _add_light(scene, "Fill Light", "AREA", (-3, -2, 2), (1.3, 0, -0.8), 200 * scale, 3.0)
    _add_light(scene, "Rim Light", "AREA", (0, 4, 2), (-0.5, 0, 0), 300 * scale, 1.5)


def _world_color(scene, color, strength=1.0):
    world = scene.world
    if world is None:
        world = bpy.data.worlds.new("World")
        scene.world = world
    world.use_nodes = True
    bg_node = world.node_tree.nodes.get("Background")
    if bg_node is None:
        bg_node = world.node_tree.nodes.new("ShaderNodeBackground")
    bg_node.inputs["Color"].default_value = color
    bg_node.inputs["Strength"].default_value = strength
    return world


TEMPLATES = (
    "empty",
    "basic_scene",
    "studio_lighting",
    "lit_empty",
    "procedural",
    "animation",
    "physics",
    "architectural",
    "product",
    "vfx",
    "game_asset",
    "sculpting",
)


def _rgba(value, default):
    """Accept RGB or RGBA lists and return a 4-tuple."""
    if not value:
        value = default
    value = [float(c) for c in value]
    if len(value) == 3:
        value.append(1.0)
    if len(value) != 4:
        raise ScriptError(f"Colors need 3 or 4 components, got {len(value)}")
    return tuple(value)


PRIMITIVE_OPS = {
    "cube": lambda loc: bpy.ops.mesh.primitive_cube_add(location=loc),
    "sphere": lambda loc: bpy.ops.mesh.primitive_uv_sphere_add(location=loc),
    "uv_sphere": lambda loc: bpy.ops.mesh.primitive_uv_sphere_add(location=loc),
    "cylinder": lambda loc: bpy.ops.mesh.primitive_cylinder_add(location=loc),
    "cone": lambda loc: bpy.ops.mesh.primitive_cone_add(location=loc),
    "torus": lambda loc: bpy.ops.mesh.primitive_torus_add(location=loc),
    "plane": lambda loc: bpy.ops.mesh.primitive_plane_add(location=loc),
    "monkey": lambda loc: bpy.ops.mesh.primitive_monkey_add(location=loc),
}


def _world(scene):
    world = scene.world
    if world is None:
        world = bpy.data.worlds.new("World")
        scene.world = world
    world.use_nodes = True
    return world


def _texture_node(nodes, texture_type, settings):
    """Create a shader texture node; returns (node, output socket, bsdf input)."""
    scale = float(settings.get("scale", 5.0))
    if texture_type == "IMAGE":
        node = nodes.new(type="ShaderNodeTexImage")
        image_path = settings.get("image_path")
        if not image_path:
            raise ScriptError("settings.image_path is required for IMAGE textures")
        if not Path(image_path).is_file():
            raise ScriptError(f"Image file not found: {image_path}")
        node.image = bpy.data.images.load(image_path, check_existing=True)
        return node, "Color", "Base Color"
    if texture_type in ("NOISE", "MUSGRAVE"):
        # Musgrave was folded into the Noise node in Blender 4.1.
        node = nodes.new(type="ShaderNodeTexNoise")
        node.inputs["Scale"].default_value = scale
        node.inputs["Detail"].default_value = float(settings.get("detail", 2.0))
        return node, "Fac", settings.get("target", "Roughness")
    if texture_type == "VORONOI":
        node = nodes.new(type="ShaderNodeTexVoronoi")
        node.inputs["Scale"].default_value = scale
        return node, "Distance", settings.get("target", "Roughness")
    if texture_type == "WAVE":
        node = nodes.new(type="ShaderNodeTexWave")
        node.inputs["Scale"].default_value = scale
        node.inputs["Distortion"].default_value = float(settings.get("distortion", 0.0))
        return node, "Color", settings.get("target", "Base Color")
    if texture_type == "MAGIC":
        node = nodes.new(type="ShaderNodeTexMagic")
        node.inputs["Scale"].default_value = scale
        return node, "Color", settings.get("target", "Base Color")
    if texture_type == "BRICK":
        node = nodes.new(type="ShaderNodeTexBrick")
        node.inputs["Scale"].default_value = scale
        if "color1" in settings:
            node.inputs["Color1"].default_value = _rgba(settings["color1"], [0.8, 0.8, 0.8])
        if "color2" in settings:
            node.inputs["Color2"].default_value = _rgba(settings["color2"], [0.2, 0.2, 0.2])
        return node, "Color", settings.get("target", "Base Color")
    if texture_type == "CHECKER":
        node = nodes.new(type="ShaderNodeTexChecker")
        node.inputs["Scale"].default_value = scale
        return node, "Color", settings.get("target", "Base Color")
    if texture_type == "GRADIENT":
        node = nodes.new(type="ShaderNodeTexGradient")
        return node, "Color", settings.get("target", "Base Color")
    raise ScriptError(f"Unknown texture type '{texture_type}'")


def _mesh_signature(mesh):
    """Hash of a mesh's vertex positions and face topology (for instancing)."""
    digest = hashlib.sha1()
    for vert in mesh.vertices:
        digest.update(("%.5f,%.5f,%.5f;" % tuple(vert.co)).encode())
    for poly in mesh.polygons:
        digest.update((",".join(map(str, poly.vertices)) + "|").encode())
    return digest.hexdigest()


# ---------------------------------------------------------------------------
# Operations
# ---------------------------------------------------------------------------


def clear_scene():
    """Remove every object (and orphaned data) from the current scene."""
    for obj in list(bpy.data.objects):
        bpy.data.objects.remove(obj, do_unlink=True)
    for collection in (bpy.data.meshes, bpy.data.lights, bpy.data.cameras, bpy.data.materials):
        for block in list(collection):
            if block.users == 0:
                collection.remove(block)


def create_project(args, _job_id):  # noqa: C901
    """Create a new .blend project from one of the TEMPLATES."""
    template = args.get("template", "basic_scene")
    settings = args.get("settings") or {}
    project_path = args.get("project_path")
    if not project_path:
        raise ScriptError("project_path is required")
    if template not in TEMPLATES:
        raise ScriptError(f"Unknown template '{template}'. Available: {', '.join(TEMPLATES)}")

    clear_scene()
    scene = bpy.context.scene

    default_engine = {"sculpting": "BLENDER_WORKBENCH", "game_asset": "EEVEE", "animation": "EEVEE"}.get(template, "CYCLES")
    scene.render.engine = resolve_engine(settings.get("engine"), default_engine)
    resolution = settings.get("resolution") or [1920, 1080]
    scene.render.resolution_x = int(resolution[0])
    scene.render.resolution_y = int(resolution[1])
    scene.render.fps = int(settings.get("fps", 24))

    if template == "empty":
        _add_camera(scene)

    elif template == "basic_scene":
        _add_ground()
        _add_light(scene, "Sun", "SUN", (0, 0, 10), (0.785, 0, 0.785), 5.0)
        _add_camera(scene)

    elif template == "studio_lighting":
        _three_point(scene)
        _add_camera(scene, (4, -4, 2), (1.4, 0, 0.785), 85)
        _world_color(scene, (0.05, 0.05, 0.05, 1.0))

    elif template == "lit_empty":
        # Bright enough for EEVEE without a ground plane.
        _add_light(scene, "Key Light", "AREA", (3, -3, 3), (1.2, 0, 0.6), 50000, 3.0)
        _add_light(scene, "Fill Light", "AREA", (-3, -2, 2), (1.3, 0, -0.8), 20000, 4.0)
        _add_light(scene, "Back Light", "AREA", (0, 4, 2), (-0.5, 0, 0), 30000, 2.0)
        _add_light(scene, "Top Light", "AREA", (0, 0, 5), (0, 0, 0), 25000, 5.0)
        _add_camera(scene)
        _world_color(scene, (0.3, 0.3, 0.3, 1.0))

    elif template == "procedural":
        _add_ground(name="Ground")
        bpy.ops.mesh.primitive_grid_add(x_subdivisions=32, y_subdivisions=32, size=4, location=(0, 0, 0.01))
        bpy.context.active_object.name = "ProceduralBase"
        _add_light(scene, "Sun", "SUN", (0, 0, 10), (0.785, 0, 0.785), 4.0)
        _add_camera(scene)

    elif template == "animation":
        _add_ground()
        _add_light(scene, "Sun", "SUN", (0, 0, 10), (0.785, 0, 0.785), 5.0)
        _add_camera(scene)
        scene.frame_start = int(settings.get("frame_start", 1))
        scene.frame_end = int(settings.get("frame_end", 250))

    elif template == "physics":
        ground = _add_ground()
        if scene.rigidbody_world is None:
            with bpy.context.temp_override(scene=scene):
                bpy.ops.rigidbody.world_add()
        bpy.context.view_layer.objects.active = ground
        ground.select_set(True)
        bpy.ops.rigidbody.object_add()
        ground.rigid_body.type = "PASSIVE"
        ground.rigid_body.collision_shape = "BOX"
        _add_light(scene, "Sun", "SUN", (0, 0, 10), (0.785, 0, 0.785), 5.0)
        _add_camera(scene, (12, -12, 8), (1.1, 0, 0.785))
        scene.frame_end = int(settings.get("frame_end", 250))

    elif template == "architectural":
        _add_ground(size=100)
        sun = _add_light(scene, "Sun", "SUN", (0, 0, 20), (0.9, 0, 0.6), 3.0)
        sun.data.angle = 0.02
        world = _world_color(scene, (0.6, 0.75, 1.0, 1.0), 1.0)
        nodes = world.node_tree.nodes
        sky = nodes.new("ShaderNodeTexSky")
        world.node_tree.links.new(sky.outputs["Color"], nodes["Background"].inputs["Color"])
        _add_camera(scene, (15, -15, 1.7), (1.52, 0, 0.785), 24)

    elif template == "product":
        bpy.ops.mesh.primitive_plane_add(size=30, location=(0, 0, 0))
        bpy.context.active_object.name = "Backdrop Floor"
        bpy.ops.mesh.primitive_plane_add(size=30, location=(0, 10, 15), rotation=(math.pi / 2, 0, 0))
        bpy.context.active_object.name = "Backdrop Wall"
        _three_point(scene, 1.5)
        _add_camera(scene, (0, -8, 2), (1.45, 0, 0), 85)
        _world_color(scene, (1.0, 1.0, 1.0, 1.0), 0.5)

    elif template == "vfx":
        _add_ground()
        _add_light(scene, "Sun", "SUN", (0, 0, 10), (0.785, 0, 0.785), 5.0)
        _add_camera(scene)
        scene.render.film_transparent = True
        scene.use_nodes = True
        tree = scene.node_tree
        tree.nodes.clear()
        layers = tree.nodes.new("CompositorNodeRLayers")
        glare = tree.nodes.new("CompositorNodeGlare")
        composite = tree.nodes.new("CompositorNodeComposite")
        layers.location, glare.location, composite.location = (0, 0), (300, 0), (600, 0)
        tree.links.new(layers.outputs["Image"], glare.inputs["Image"])
        tree.links.new(glare.outputs["Image"], composite.inputs["Image"])

    elif template == "game_asset":
        scene.unit_settings.system = "METRIC"
        scene.unit_settings.scale_length = 1.0
        _add_light(scene, "Sun", "SUN", (0, 0, 10), (0.785, 0, 0.785), 3.0)
        _add_camera(scene, (4, -4, 3), (1.1, 0, 0.785))

    elif template == "sculpting":
        bpy.ops.mesh.primitive_uv_sphere_add(segments=64, ring_count=32, radius=1, location=(0, 0, 1))
        base = bpy.context.active_object
        base.name = "SculptBase"
        base.modifiers.new("Multires", "MULTIRES")  # subdivision levels are added while sculpting
        scene.display.shading.light = "MATCAP"
        _add_camera(scene, (0, -6, 1), (math.pi / 2, 0, 0), 85)

    save_project(project_path)
    return {
        "success": True,
        "template": template,
        "engine": scene.render.engine,
        "objects": sorted(o.name for o in bpy.data.objects),
    }


def add_primitives(args, _job_id):
    """Add primitive mesh objects; returns the names Blender actually assigned."""
    open_project(args.get("project"))
    created = []
    for obj_data in args.get("objects", []):
        obj_type = str(obj_data.get("type", "")).lower()
        op = PRIMITIVE_OPS.get(obj_type)
        if op is None:
            raise ScriptError(f"Unknown primitive type '{obj_type}'. Supported: {', '.join(sorted(PRIMITIVE_OPS))}")
        op(tuple(obj_data.get("location", [0, 0, 0])))
        obj = bpy.context.active_object
        obj.name = obj_data.get("name") or obj_type.capitalize()
        obj.rotation_euler = obj_data.get("rotation", [0, 0, 0])
        obj.scale = obj_data.get("scale", [1, 1, 1])
        created.append({"name": obj.name, "type": obj_type})
    save_project()
    return {"success": True, "objects": created}


def setup_lighting(args, _job_id):  # noqa: C901
    """Replace the scene's lights with a preset rig (existing lights are removed)."""
    open_project(args.get("project"))
    lighting_type = args.get("lighting_type")
    settings = args.get("settings") or {}
    strength = float(settings.get("strength", 1.0))
    color = _rgba(settings.get("color"), [1, 1, 1])[:3]

    removed = [obj.name for obj in bpy.data.objects if obj.type == "LIGHT"]
    for name in removed:
        bpy.data.objects.remove(bpy.data.objects[name], do_unlink=True)

    scene = bpy.context.scene
    created = []

    def light(name, kind, location, rotation, energy, size=None):
        data = bpy.data.lights.new(name, kind)
        data.energy = energy
        data.color = color
        if size is not None and hasattr(data, "size"):
            data.size = size
        obj = bpy.data.objects.new(name, data)
        scene.collection.objects.link(obj)
        obj.location = location
        obj.rotation_euler = rotation
        created.append(obj.name)

    if lighting_type == "three_point":
        light("Key Light", "AREA", (3, -3, 3), (1.2, 0, 0.6), 500 * strength, 2.0)
        light("Fill Light", "AREA", (-3, -2, 2), (1.3, 0, -0.8), 200 * strength, 3.0)
        light("Back Light", "AREA", (0, 4, 2), (-0.5, 0, 0), 300 * strength, 1.5)
    elif lighting_type == "studio":
        for i, pos in enumerate([(4, -4, 3), (-4, -4, 3), (0, 4, 3), (0, -5, 1)]):
            rotation = (
                math.atan2(math.sqrt(pos[0] ** 2 + pos[1] ** 2), pos[2]),
                0,
                math.atan2(pos[1], pos[0]) + math.pi / 2,
            )
            light(f"Studio Light {i + 1}", "AREA", pos, rotation, 300 * strength, 2.5)
    elif lighting_type == "hdri":
        hdri_path = settings.get("hdri_path")
        if not hdri_path:
            raise ScriptError("settings.hdri_path is required for hdri lighting")
        if not Path(hdri_path).is_file():
            raise ScriptError(f"HDRI file not found: {hdri_path}")
        world = _world(scene)
        nodes = world.node_tree.nodes
        links = world.node_tree.links
        nodes.clear()
        node_bg = nodes.new(type="ShaderNodeBackground")
        node_env = nodes.new(type="ShaderNodeTexEnvironment")
        node_output = nodes.new(type="ShaderNodeOutputWorld")
        node_env.image = bpy.data.images.load(hdri_path, check_existing=True)
        node_bg.inputs["Strength"].default_value = strength
        links.new(node_env.outputs["Color"], node_bg.inputs["Color"])
        links.new(node_bg.outputs["Background"], node_output.inputs["Surface"])
    elif lighting_type == "sun":
        light("Sun", "SUN", (0, 0, 10), (0.785, 0, 0.785), 5.0 * strength)
    elif lighting_type == "area":
        light("Area Light", "AREA", (0, 0, 5), (0, 0, 0), 1000 * strength, 5.0)
    else:
        raise ScriptError(f"Unknown lighting type '{lighting_type}'")

    save_project()
    return {"success": True, "lights_created": created, "lights_removed": removed}


def apply_material(args, _job_id):  # noqa: C901
    """Create a material of the requested type and assign it to slot 0."""
    open_project(args.get("project"))
    object_name = args.get("object_name")
    material_data = args.get("material") or {}
    obj = require_object(object_name)
    if not hasattr(obj.data, "materials"):
        raise ScriptError(f"Object '{object_name}' ({obj.type}) cannot hold materials")

    mat_type = material_data.get("type", "principled")
    mat = bpy.data.materials.new(name=material_data.get("name") or f"{object_name}_{mat_type}")
    mat.use_nodes = True
    nodes = mat.node_tree.nodes
    links = mat.node_tree.links
    nodes.clear()
    node_output = nodes.new(type="ShaderNodeOutputMaterial")
    node_output.location = (400, 0)

    def principled(color_default, metallic, roughness):
        bsdf = nodes.new(type="ShaderNodeBsdfPrincipled")
        bsdf.inputs["Base Color"].default_value = _rgba(material_data.get("base_color"), color_default)
        bsdf.inputs["Metallic"].default_value = metallic
        bsdf.inputs["Roughness"].default_value = float(material_data.get("roughness", roughness))
        strength = float(material_data.get("emission_strength", 0.0))
        if strength > 0:
            bsdf.inputs["Emission Color"].default_value = bsdf.inputs["Base Color"].default_value
            bsdf.inputs["Emission Strength"].default_value = strength
        links.new(bsdf.outputs["BSDF"], node_output.inputs["Surface"])
        return bsdf

    if mat_type == "principled":
        principled([0.8, 0.8, 0.8, 1.0], float(material_data.get("metallic", 0.0)), 0.5)
    elif mat_type == "emission":
        node = nodes.new(type="ShaderNodeEmission")
        node.inputs["Color"].default_value = _rgba(material_data.get("base_color"), [1, 1, 1, 1])
        strength = float(material_data.get("emission_strength", 0.0)) or 1.0
        node.inputs["Strength"].default_value = strength
        links.new(node.outputs["Emission"], node_output.inputs["Surface"])
    elif mat_type == "glass":
        node = nodes.new(type="ShaderNodeBsdfGlass")
        node.inputs["Color"].default_value = _rgba(material_data.get("base_color"), [1, 1, 1, 1])
        node.inputs["IOR"].default_value = float(material_data.get("ior", 1.45))
        node.inputs["Roughness"].default_value = float(material_data.get("roughness", 0.0))
        links.new(node.outputs["BSDF"], node_output.inputs["Surface"])
    elif mat_type == "metal":
        principled([0.7, 0.7, 0.7, 1.0], 1.0, 0.2)
    elif mat_type == "plastic":
        bsdf = principled([0.5, 0.5, 0.8, 1.0], 0.0, 0.4)
        coat = "Coat Weight" if "Coat Weight" in bsdf.inputs else "Clearcoat Weight"
        bsdf.inputs[coat].default_value = 0.5
    elif mat_type == "wood":
        bsdf = principled([0.4, 0.2, 0.1, 1.0], 0.0, 0.7)
        tex = nodes.new(type="ShaderNodeTexWave")
        tex.inputs["Scale"].default_value = 3.0
        tex.inputs["Distortion"].default_value = 6.0
        ramp = nodes.new(type="ShaderNodeValToRGB")
        ramp.color_ramp.elements[0].color = (0.2, 0.1, 0.05, 1.0)
        ramp.color_ramp.elements[1].color = (0.45, 0.25, 0.12, 1.0)
        links.new(tex.outputs["Fac"], ramp.inputs["Fac"])
        links.new(ramp.outputs["Color"], bsdf.inputs["Base Color"])
    else:
        raise ScriptError(f"Unknown material type '{mat_type}'")

    if obj.data.materials:
        obj.data.materials[0] = mat
    else:
        obj.data.materials.append(mat)
    save_project()
    return {"success": True, "material": mat.name, "object": obj.name}


IMPORTERS = {
    "FBX": lambda p: bpy.ops.import_scene.fbx(filepath=p),
    "OBJ": lambda p: bpy.ops.wm.obj_import(filepath=p),
    "GLTF": lambda p: bpy.ops.import_scene.gltf(filepath=p),
    "GLB": lambda p: bpy.ops.import_scene.gltf(filepath=p),
    "STL": lambda p: bpy.ops.wm.stl_import(filepath=p),
    "PLY": lambda p: bpy.ops.wm.ply_import(filepath=p),
    "USD": lambda p: bpy.ops.wm.usd_import(filepath=p),
}


def import_model(args, _job_id):
    """Import a model file and move the imported objects to ``location``."""
    open_project(args.get("project"))
    model_path = args.get("model_path")
    file_format = str(args.get("format", "")).upper()
    location = args.get("location", [0, 0, 0])
    if not model_path or not Path(model_path).is_file():
        raise ScriptError(f"Model file not found: {model_path}")
    importer = IMPORTERS.get(file_format)
    if importer is None:
        raise ScriptError(f"Unsupported import format '{file_format}'. Supported: {', '.join(IMPORTERS)}")

    before = set(bpy.data.objects.keys())
    importer(model_path)
    imported = [obj for obj in bpy.data.objects if obj.name not in before]
    for obj in imported:
        if obj.parent is None:
            obj.location = location
    save_project()
    return {"success": True, "imported_objects": sorted(o.name for o in imported)}


def delete_objects(args, _job_id):
    """Delete objects by exact name, object type, and/or name glob."""
    open_project(args.get("project"))
    names = list(args.get("names") or []) + list(args.get("object_names") or [])
    types = {str(t).upper() for t in (args.get("object_types") or [])}
    type_pattern = args.get("type_pattern")
    name_pattern = args.get("name_pattern") or args.get("pattern")
    if not (names or types or type_pattern or name_pattern):
        raise ScriptError("Nothing to delete: supply names, type_pattern or name_pattern")

    doomed = {}
    missing = []
    for name in names:
        obj = bpy.data.objects.get(name)
        if obj is None:
            missing.append(name)
        else:
            doomed[obj.name] = obj
    for obj in bpy.data.objects:
        if obj.type in types:
            doomed[obj.name] = obj
        if type_pattern and fnmatch.fnmatchcase(obj.type, str(type_pattern).upper()):
            doomed[obj.name] = obj
        if name_pattern and fnmatch.fnmatchcase(obj.name, name_pattern):
            doomed[obj.name] = obj

    deleted = sorted(doomed)
    for obj in doomed.values():
        bpy.data.objects.remove(obj, do_unlink=True)
    save_project()
    return {"success": True, "deleted_objects": deleted, "not_found": missing}


def create_curve(args, _job_id):
    """Create a BEZIER/NURBS/POLY curve object from control points."""
    open_project(args.get("project"))
    name = args.get("name", "Curve")
    curve_type = str(args.get("curve_type", "BEZIER")).upper()
    points = args.get("points") or [[-1.0, 0.0, 0.5], [0.0, 0.5, 0.7], [1.0, 0.0, 0.5]]
    closed = bool(args.get("cyclic", args.get("closed", False)))
    if curve_type not in ("BEZIER", "NURBS", "POLY"):
        raise ScriptError(f"Unknown curve_type '{curve_type}'. Supported: BEZIER, NURBS, POLY")
    for point in points:
        if len(point) != 3:
            raise ScriptError(f"Every curve point needs 3 coordinates, got {point}")

    curve_data = bpy.data.curves.new(name=name, type="CURVE")
    curve_data.dimensions = "3D"
    curve_data.resolution_u = int(args.get("resolution", 12))
    curve_data.bevel_depth = float(args.get("bevel_depth", 0.0))
    spline = curve_data.splines.new(curve_type)
    spline.use_cyclic_u = closed
    if curve_type == "BEZIER":
        spline.bezier_points.add(len(points) - 1)
        for bp, point in zip(spline.bezier_points, points):
            bp.co = point
            bp.handle_left_type = "AUTO"
            bp.handle_right_type = "AUTO"
    else:
        spline.points.add(len(points) - 1)
        for sp, point in zip(spline.points, points):
            sp.co = (*point, 1.0)

    curve_obj = bpy.data.objects.new(name, curve_data)
    bpy.context.scene.collection.objects.link(curve_obj)

    target_object = args.get("target_object")
    if target_object:
        target = require_object(target_object, "MESH")
        shrinkwrap = curve_obj.modifiers.new(name="ShrinkwrapCurve", type="SHRINKWRAP")
        shrinkwrap.target = target
        shrinkwrap.offset = float(args.get("surface_offset", 0.05))
        shrinkwrap.wrap_method = "NEAREST_SURFACEPOINT"

    save_project()
    return {"success": True, "curve": curve_obj.name, "points": len(points), "cyclic": closed}


def add_texture(args, _job_id):
    """Wire a procedural or image texture into the object's Principled BSDF."""
    open_project(args.get("project"))
    object_name = args.get("object_name")
    texture_type = str(args.get("texture_type", "")).upper()
    settings = args.get("settings") or {}
    obj = require_object(object_name)
    if not hasattr(obj.data, "materials"):
        raise ScriptError(f"Object '{object_name}' ({obj.type}) cannot hold materials")

    if not obj.data.materials:
        mat = bpy.data.materials.new(name=f"{object_name}_material")
        mat.use_nodes = True
        obj.data.materials.append(mat)
    mat = obj.data.materials[0]
    mat.use_nodes = True
    nodes = mat.node_tree.nodes
    links = mat.node_tree.links

    bsdf = next((n for n in nodes if n.type == "BSDF_PRINCIPLED"), None)
    if bsdf is None:
        raise ScriptError(
            f"Material '{mat.name}' has no Principled BSDF node to texture "
            "(apply a principled/metal/plastic/wood material first)"
        )

    tex_node, output, target = _texture_node(nodes, texture_type, settings)
    if target not in bsdf.inputs:
        raise ScriptError(f"Principled BSDF has no input '{target}'")
    tex_node.location = (bsdf.location.x - 350, bsdf.location.y + 250)
    links.new(tex_node.outputs[output], bsdf.inputs[target])
    save_project()
    return {"success": True, "material": mat.name, "node": tex_node.name, "connected_to": target}


def add_uv_map(args, _job_id):
    """Unwrap a mesh with the requested projection."""
    open_project(args.get("project"))
    object_name = args.get("object_name")
    projection_type = args.get("projection_type", "SMART_PROJECT")
    obj = require_object(object_name, "MESH")

    projections = {
        "SMART_PROJECT": lambda: bpy.ops.uv.smart_project(angle_limit=math.radians(66)),
        "CUBE_PROJECT": bpy.ops.uv.cube_project,
        "CYLINDER_PROJECT": bpy.ops.uv.cylinder_project,
        "SPHERE_PROJECT": bpy.ops.uv.sphere_project,
        # There is no 3D view in background mode; fall back to a planar cube projection.
        "PROJECT_FROM_VIEW": bpy.ops.uv.cube_project,
    }
    project = projections.get(projection_type)
    if project is None:
        raise ScriptError(f"Unknown projection type '{projection_type}'")

    for other in bpy.context.selected_objects:
        other.select_set(False)
    obj.select_set(True)
    bpy.context.view_layer.objects.active = obj
    bpy.ops.object.mode_set(mode="EDIT")
    try:
        bpy.ops.mesh.select_all(action="SELECT")
        project()
    finally:
        bpy.ops.object.mode_set(mode="OBJECT")
    save_project()
    return {"success": True, "uv_layers": [uv.name for uv in obj.data.uv_layers]}


def setup_compositor(args, _job_id):  # noqa: C901
    """Replace the compositor node tree with a post-processing preset."""
    open_project(args.get("project"))
    setup = args.get("setup")
    settings = args.get("settings") or {}
    if setup not in COMPOSITOR_SETUPS:
        raise ScriptError(f"Unknown compositor setup '{setup}'. Available: {', '.join(COMPOSITOR_SETUPS)}")

    scene = bpy.context.scene
    scene.use_nodes = True
    tree = scene.node_tree
    nodes = tree.nodes
    links = tree.links
    nodes.clear()

    render_layers = nodes.new(type="CompositorNodeRLayers")
    render_layers.location = (0, 300)
    composite = nodes.new(type="CompositorNodeComposite")
    composite.location = (900, 300)
    viewer = nodes.new(type="CompositorNodeViewer")
    viewer.location = (900, 0)

    def finish(node, output="Image"):
        links.new(node.outputs[output], composite.inputs["Image"])
        links.new(node.outputs[output], viewer.inputs["Image"])

    image = render_layers.outputs["Image"]
    if setup == "BASIC":
        finish(render_layers)
    elif setup == "DENOISING":
        denoise = nodes.new(type="CompositorNodeDenoise")
        denoise.location = (400, 300)
        links.new(image, denoise.inputs["Image"])
        finish(denoise)
    elif setup == "COLOR_GRADING":
        balance = nodes.new(type="CompositorNodeColorBalance")
        balance.location = (300, 300)
        curves = nodes.new(type="CompositorNodeCurveRGB")
        curves.location = (600, 300)
        links.new(image, balance.inputs["Image"])
        links.new(balance.outputs["Image"], curves.inputs["Image"])
        finish(curves)
    elif setup in ("GLARE", "FOG_GLOW"):
        glare = nodes.new(type="CompositorNodeGlare")
        glare.location = (400, 300)
        glare.glare_type = settings.get("glare_type", "FOG_GLOW" if setup == "FOG_GLOW" else "STREAKS")
        glare.quality = settings.get("quality", "HIGH")
        _set_node_value(glare, ["Threshold"], "threshold", float(settings.get("threshold", 1.0)))
        if "strength" in settings:
            _set_node_value(glare, ["Strength"], None, float(settings["strength"]))
        links.new(image, glare.inputs["Image"])
        finish(glare)
    elif setup == "LENS_DISTORTION":
        lens = nodes.new(type="CompositorNodeLensdist")
        lens.location = (400, 300)
        _set_node_value(lens, ["Distortion", "Distort"], None, float(settings.get("distort", 0.05)))
        _set_node_value(lens, ["Dispersion"], None, float(settings.get("dispersion", 0.01)))
        links.new(image, lens.inputs["Image"])
        finish(lens)
    elif setup == "VIGNETTE":
        size = float(settings.get("size", 0.8))
        ellipse = nodes.new(type="CompositorNodeEllipseMask")
        ellipse.location = (200, 0)
        ellipse.mask_width = size
        ellipse.mask_height = size
        blur = nodes.new(type="CompositorNodeBlur")
        blur.location = (400, 0)
        blur.filter_type = "FAST_GAUSS"
        blur.use_relative = True
        blur.factor_x = blur.factor_y = float(settings.get("softness", 20.0))
        mix = nodes.new(type="CompositorNodeMixRGB")
        mix.location = (650, 300)
        mix.blend_type = "MULTIPLY"
        links.new(image, mix.inputs[1])
        links.new(ellipse.outputs["Mask"], blur.inputs["Image"])
        links.new(blur.outputs["Image"], mix.inputs[2])
        finish(mix)

    save_project()
    return {"success": True, "setup": setup, "nodes": [n.name for n in nodes]}


def analyze_scene(args, _job_id):
    """Scene statistics; DETAILED/PERFORMANCE/MEMORY add progressively more."""
    open_project(args.get("project"))
    analysis_type = args.get("analysis_type", "BASIC")
    scene = bpy.context.scene

    object_counts = {}
    total_vertices = total_faces = total_tris = 0
    objects = []
    for obj in bpy.data.objects:
        object_counts[obj.type] = object_counts.get(obj.type, 0) + 1
        entry = {"name": obj.name, "type": obj.type, "location": [round(v, 4) for v in obj.location]}
        if obj.type == "MESH" and obj.data:
            mesh = obj.data
            total_vertices += len(mesh.vertices)
            total_faces += len(mesh.polygons)
            total_tris += sum(len(poly.vertices) - 2 for poly in mesh.polygons)
            entry["vertices"] = len(mesh.vertices)
        objects.append(entry)

    result = {
        "success": True,
        "object_counts": object_counts,
        "total_objects": len(bpy.data.objects),
        "total_vertices": total_vertices,
        "total_faces": total_faces,
        "total_triangles": total_tris,
        "materials": len(bpy.data.materials),
        "textures": len(bpy.data.images),
        "render_engine": scene.render.engine,
        "resolution": [scene.render.resolution_x, scene.render.resolution_y],
        "frame_range": [scene.frame_start, scene.frame_end],
        "active_camera": scene.camera.name if scene.camera else None,
        "objects": objects[:500],
        "objects_truncated": len(objects) > 500,
    }

    if analysis_type in ("DETAILED", "PERFORMANCE", "MEMORY"):
        result.update(
            {
                "meshes": len(bpy.data.meshes),
                "curves": len(bpy.data.curves),
                "lights": len(bpy.data.lights),
                "cameras": len(bpy.data.cameras),
                "collections": len(bpy.data.collections),
                "worlds": len(bpy.data.worlds),
                "scenes": len(bpy.data.scenes),
            }
        )
    if analysis_type == "PERFORMANCE":
        warnings = []
        if total_tris > 1_000_000:
            warnings.append(f"High triangle count: {total_tris}")
        if len(bpy.data.materials) > 50:
            warnings.append(f"Many materials: {len(bpy.data.materials)}")
        unused = [m.name for m in bpy.data.materials if m.users == 0]
        if unused:
            warnings.append(f"{len(unused)} unused materials (run optimize_scene MATERIAL_CLEANUP)")
        result["warnings"] = warnings
    if analysis_type == "MEMORY":
        vertex_mem = total_vertices * 12
        face_mem = total_faces * 16
        result["estimated_mesh_memory_mb"] = round((vertex_mem + face_mem) / (1024 * 1024), 2)
    return result


def optimize_scene(args, _job_id):  # noqa: C901
    """Apply one optimization pass and report what changed."""
    import bmesh  # pylint: disable=import-outside-toplevel

    open_project(args.get("project"))
    optimization_type = args.get("optimization_type")
    settings = args.get("settings") or {}
    report = {}

    if optimization_type == "MESH_CLEANUP":
        threshold = float(settings.get("merge_threshold", 0.0001))
        removed = 0
        for mesh in bpy.data.meshes:
            if mesh.users == 0:
                continue
            bm = bmesh.new()
            bm.from_mesh(mesh)
            before = len(bm.verts)
            bmesh.ops.remove_doubles(bm, verts=bm.verts, dist=threshold)
            loose = [v for v in bm.verts if not v.link_edges]
            bmesh.ops.delete(bm, geom=loose, context="VERTS")
            removed += before - len(bm.verts)
            bm.to_mesh(mesh)
            bm.free()
        report["vertices_removed"] = removed

    elif optimization_type == "TEXTURE_OPTIMIZATION":
        max_size = int(settings.get("max_size", 2048))
        resized = []
        for image in bpy.data.images:
            width, height = image.size
            if width > max_size or height > max_size:
                scale = max_size / max(width, height)
                image.scale(max(1, int(width * scale)), max(1, int(height * scale)))
                resized.append(image.name)
        report["images_resized"] = resized

    elif optimization_type == "MODIFIER_APPLY":
        applied, failed = [], []
        for obj in bpy.data.objects:
            if obj.type != "MESH":
                continue
            for modifier in list(obj.modifiers):
                try:
                    with bpy.context.temp_override(object=obj, active_object=obj):
                        bpy.ops.object.modifier_apply(modifier=modifier.name)
                    applied.append(f"{obj.name}:{modifier.name}")
                except RuntimeError as exc:
                    failed.append(f"{obj.name}:{modifier.name}: {exc}")
        report["applied"] = applied
        report["failed"] = failed

    elif optimization_type == "INSTANCE_OPTIMIZATION":
        # Objects whose meshes are geometrically identical share one mesh datablock.
        by_signature = {}
        linked = []
        for obj in bpy.data.objects:
            if obj.type != "MESH" or obj.data is None or obj.modifiers:
                continue
            key = _mesh_signature(obj.data)
            shared = by_signature.setdefault(key, obj.data)
            if shared is not obj.data:
                obj.data = shared
                linked.append(obj.name)
        for mesh in list(bpy.data.meshes):
            if mesh.users == 0:
                bpy.data.meshes.remove(mesh)
        report["objects_instanced"] = linked
        report["unique_meshes"] = len(by_signature)

    elif optimization_type == "MATERIAL_CLEANUP":
        materials = [m.name for m in bpy.data.materials if m.users == 0]
        for name in materials:
            bpy.data.materials.remove(bpy.data.materials[name])
        images = [i.name for i in bpy.data.images if i.users == 0]
        for name in images:
            bpy.data.images.remove(bpy.data.images[name])
        report["materials_removed"] = materials
        report["images_removed"] = images

    else:
        raise ScriptError(f"Unknown optimization type '{optimization_type}'")

    save_project()
    report["success"] = True
    return report


def export_scene(args, _job_id):
    """Export the scene (or the current selection) to a model file."""
    open_project(args.get("project"))
    file_format = str(args.get("format", "")).upper()
    output_path = args.get("output_path")
    selected_only = bool(args.get("selected_only", False))
    if not output_path:
        raise ScriptError("output_path is required")
    Path(output_path).parent.mkdir(parents=True, exist_ok=True)

    if file_format == "FBX":
        bpy.ops.export_scene.fbx(filepath=output_path, use_selection=selected_only)
    elif file_format == "OBJ":
        bpy.ops.wm.obj_export(filepath=output_path, export_selected_objects=selected_only)
    elif file_format in ("GLTF", "GLB"):
        bpy.ops.export_scene.gltf(
            filepath=output_path,
            use_selection=selected_only,
            export_format="GLB" if file_format == "GLB" else "GLTF_SEPARATE",
        )
    elif file_format == "STL":
        bpy.ops.wm.stl_export(filepath=output_path, export_selected_objects=selected_only)
    elif file_format == "PLY":
        bpy.ops.wm.ply_export(filepath=output_path, export_selected_objects=selected_only)
    elif file_format == "USD":
        bpy.ops.wm.usd_export(filepath=output_path, selected_objects_only=selected_only)
    else:
        raise ScriptError(f"Unsupported export format '{file_format}'")

    if not Path(output_path).is_file():
        raise ScriptError(f"Exporter reported success but {output_path} was not written")
    return {"success": True, "output_path": output_path, "bytes": Path(output_path).stat().st_size}


def _set_node_value(node, socket_names, attr, value):
    """Set a node parameter across Blender versions.

    Blender 4.4+ turned many compositor node properties into input sockets
    (e.g. Glare "Threshold", Lens Distortion "Distortion"); older releases only
    have the RNA property. Try the sockets first, then the property.
    """
    for name in socket_names:
        socket = node.inputs.get(name)
        if socket is not None and hasattr(socket, "default_value"):
            socket.default_value = value
            return
    if attr and hasattr(node, attr):
        setattr(node, attr, value)


COMPOSITOR_SETUPS = ("BASIC", "DENOISING", "COLOR_GRADING", "GLARE", "FOG_GLOW", "LENS_DISTORTION", "VIGNETTE")


def main():
    """Dispatch the requested operation (see mcp_common.run)."""
    run(
        {
            "create_project": create_project,
            "add_primitives": add_primitives,
            "setup_lighting": setup_lighting,
            "apply_material": apply_material,
            "import_model": import_model,
            "export_scene": export_scene,
            "delete_objects": delete_objects,
            "create_curve": create_curve,
            "add_texture": add_texture,
            "add_uv_map": add_uv_map,
            "setup_compositor": setup_compositor,
            "analyze_scene": analyze_scene,
            "optimize_scene": optimize_scene,
        }
    )


if __name__ == "__main__":
    main()
