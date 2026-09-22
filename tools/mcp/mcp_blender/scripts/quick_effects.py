#!/usr/bin/env python3
"""Blender quick effects script - One-click complex setups.

Based on Blender's bl_operators/object_quick_effects.py for smoke, fur, explode, liquid.
"""

import json
import os
import sys

import bpy
from mathutils import Vector

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from mcp_common import (  # noqa: E402  pylint: disable=wrong-import-position
    ScriptError,
    open_project,
    run,
    save_project,
)


def obj_bb_minmax(obj, min_co, max_co):
    """Calculate bounding box min/max for an object."""
    for i in range(0, 8):
        bb_vec = obj.matrix_world @ Vector(obj.bound_box[i])
        min_co[0] = min(bb_vec[0], min_co[0])
        min_co[1] = min(bb_vec[1], min_co[1])
        min_co[2] = min(bb_vec[2], min_co[2])
        max_co[0] = max(bb_vec[0], max_co[0])
        max_co[1] = max(bb_vec[1], max_co[1])
        max_co[2] = max(bb_vec[2], max_co[2])


def quick_smoke(args, _job_id):
    """Add smoke/fire simulation to selected objects.

    Creates a fluid domain around selected mesh objects configured as smoke emitters.

    Parameters:
        project: Blender project file path
        object_names: List of mesh object names to make smoke emitters
        style: SMOKE, FIRE, or BOTH (default: SMOKE)
        show_flows: Keep emitter objects visible during render (default: False)
        domain_resolution: Fluid resolution divisor (default: 32)
    """
    try:
        if "project" in args:
            bpy.ops.wm.open_mainfile(filepath=args["project"])

        object_names = args.get("object_names", [])
        style = args.get("style", "SMOKE")
        show_flows = args.get("show_flows", False)
        resolution = args.get("domain_resolution", 32)

        if not bpy.app.build_options.fluid:
            print("Error: Blender built without Fluid modifier support")
            return False

        # Get mesh objects
        mesh_objects = []
        for name in object_names:
            obj = bpy.data.objects.get(name)
            if obj and obj.type == "MESH":
                mesh_objects.append(obj)

        if not mesh_objects:
            print("Error: No valid mesh objects found")
            return False

        min_co = Vector((100000.0, 100000.0, 100000.0))
        max_co = -min_co

        # Make each object a smoke flow
        for obj in mesh_objects:
            bpy.context.view_layer.objects.active = obj
            bpy.ops.object.modifier_add(type="FLUID")
            obj.modifiers[-1].fluid_type = "FLOW"
            obj.modifiers[-1].flow_settings.flow_type = style
            obj.modifiers[-1].flow_settings.flow_behavior = "INFLOW"
            obj.modifiers[-1].flow_settings.surface_distance = 1.0

            if not show_flows:
                obj.display_type = "WIRE"

            obj_bb_minmax(obj, min_co, max_co)

        # Create smoke domain
        bpy.ops.mesh.primitive_cube_add()
        domain = bpy.context.active_object
        domain.name = "Smoke Domain"

        # Position and scale domain
        domain.location = 0.5 * (max_co + min_co) + Vector((0.0, 0.0, 1.0))
        domain.scale = 0.5 * (max_co - min_co) + Vector((1.0, 1.0, 2.0))

        # Setup domain
        bpy.ops.object.modifier_add(type="FLUID")
        domain.modifiers[-1].fluid_type = "DOMAIN"
        domain.modifiers[-1].domain_settings.cfl_condition = 4.0
        domain.modifiers[-1].domain_settings.resolution_max = resolution

        if style in {"FIRE", "BOTH"}:
            domain.modifiers[-1].domain_settings.use_noise = True

        if bpy.app.build_options.openvdb:
            domain.modifiers[-1].domain_settings.cache_data_format = "OPENVDB"

        # Setup volume material
        bpy.ops.object.material_slot_add()
        mat = bpy.data.materials.new("Smoke Domain Material")
        mat.use_nodes = True
        domain.material_slots[0].material = mat

        tree = mat.node_tree
        nodes = tree.nodes
        links = tree.links
        nodes.clear()

        node_out = nodes.new(type="ShaderNodeOutputMaterial")
        node_out.location = (400, 0)

        node_principled = nodes.new(type="ShaderNodeVolumePrincipled")
        node_principled.location = (0, 0)
        links.new(node_principled.outputs["Volume"], node_out.inputs["Volume"])

        node_principled.inputs["Density"].default_value = 5.0
        if style in {"FIRE", "BOTH"}:
            node_principled.inputs["Blackbody Intensity"].default_value = 1.0

        if "project" in args:
            bpy.ops.wm.save_mainfile()

        print(
            json.dumps(
                {
                    "success": True,
                    "domain": domain.name,
                    "emitters": [obj.name for obj in mesh_objects],
                    "style": style,
                }
            )
        )
        return True

    except Exception as e:
        print(f"Error in quick_smoke: {e}")
        return False


def quick_liquid(args, _job_id):
    """Add liquid simulation to selected objects.

    Creates a fluid domain with selected objects as liquid sources.

    Parameters:
        project: Blender project file path
        object_names: List of mesh object names to make liquid sources
        show_flows: Keep source objects visible during render (default: False)
        domain_resolution: Fluid resolution divisor (default: 64)
    """
    try:
        if "project" in args:
            bpy.ops.wm.open_mainfile(filepath=args["project"])

        object_names = args.get("object_names", [])
        show_flows = args.get("show_flows", False)
        resolution = args.get("domain_resolution", 64)

        if not bpy.app.build_options.fluid:
            print("Error: Blender built without Fluid modifier support")
            return False

        mesh_objects = []
        for name in object_names:
            obj = bpy.data.objects.get(name)
            if obj and obj.type == "MESH":
                mesh_objects.append(obj)

        if not mesh_objects:
            print("Error: No valid mesh objects found")
            return False

        min_co = Vector((100000.0, 100000.0, 100000.0))
        max_co = -min_co

        # Make each object a liquid flow
        for obj in mesh_objects:
            bpy.context.view_layer.objects.active = obj
            bpy.ops.object.modifier_add(type="FLUID")
            obj.modifiers[-1].fluid_type = "FLOW"
            obj.modifiers[-1].flow_settings.flow_type = "LIQUID"
            obj.modifiers[-1].flow_settings.flow_behavior = "GEOMETRY"
            obj.modifiers[-1].flow_settings.surface_distance = 0.0

            if not show_flows:
                obj.display_type = "WIRE"

            obj_bb_minmax(obj, min_co, max_co)

        # Create liquid domain
        bpy.ops.mesh.primitive_cube_add(align="WORLD")
        domain = bpy.context.active_object
        domain.name = "Liquid Domain"

        domain.location = 0.5 * (max_co + min_co) + Vector((0.0, 0.0, -1.0))
        domain.scale = 0.5 * (max_co - min_co) + Vector((1.0, 1.0, 2.0))

        # Setup liquid domain
        bpy.ops.object.modifier_add(type="FLUID")
        domain.modifiers[-1].fluid_type = "DOMAIN"
        domain.modifiers[-1].domain_settings.resolution_max = resolution

        # Set collision borders
        ds = domain.modifiers[-1].domain_settings
        ds.use_collision_border_front = True
        ds.use_collision_border_back = True
        ds.use_collision_border_right = True
        ds.use_collision_border_left = True
        ds.use_collision_border_top = True
        ds.use_collision_border_bottom = True

        if bpy.app.build_options.openvdb:
            ds.cache_data_format = "OPENVDB"
        ds.cache_mesh_format = "BOBJECT"
        ds.domain_type = "LIQUID"
        ds.color_ramp_field = "PHI"
        ds.use_slice = True
        ds.display_thickness = 0.02

        bpy.ops.object.shade_smooth()

        # Glass material for liquid
        bpy.ops.object.material_slot_add()
        mat = bpy.data.materials.new("Liquid Domain Material")
        mat.use_nodes = True
        domain.material_slots[0].material = mat

        tree = mat.node_tree
        nodes = tree.nodes
        links = tree.links
        nodes.clear()

        node_out = nodes.new(type="ShaderNodeOutputMaterial")
        node_out.location = (400, 0)

        node_glass = nodes.new(type="ShaderNodeBsdfGlass")
        node_glass.location = (0, 0)
        links.new(node_glass.outputs["BSDF"], node_out.inputs["Surface"])
        node_glass.inputs["IOR"].default_value = 1.33

        node_absorption = nodes.new(type="ShaderNodeVolumeAbsorption")
        node_absorption.location = (0, -200)
        links.new(node_absorption.outputs["Volume"], node_out.inputs["Volume"])
        node_absorption.inputs["Color"].default_value = (0.8, 0.9, 1.0, 1.0)

        if "project" in args:
            bpy.ops.wm.save_mainfile()

        print(
            json.dumps(
                {
                    "success": True,
                    "domain": domain.name,
                    "sources": [obj.name for obj in mesh_objects],
                }
            )
        )
        return True

    except Exception as e:
        print(f"Error in quick_liquid: {e}")
        return False


def quick_explode(args, _job_id):
    """Add explosion effect to selected objects.

    Creates particle system with explode modifier for destruction effects.

    Parameters:
        project: Blender project file path
        object_names: List of mesh object names to explode
        style: EXPLODE or BLEND (default: EXPLODE)
        piece_count: Number of explosion pieces (default: 100)
        frame_start: Start frame (default: 1)
        frame_duration: Explosion duration in frames (default: 50)
        velocity: Outward velocity (default: 1.0)
        fade: Fade pieces over time (default: True)
    """
    try:
        if "project" in args:
            bpy.ops.wm.open_mainfile(filepath=args["project"])

        object_names = args.get("object_names", [])
        style = args.get("style", "EXPLODE")
        piece_count = args.get("piece_count", 100)
        frame_start = args.get("frame_start", 1)
        frame_duration = args.get("frame_duration", 50)
        velocity = args.get("velocity", 1.0)
        fade = args.get("fade", True)

        mesh_objects = []
        for name in object_names:
            obj = bpy.data.objects.get(name)
            if obj and obj.type == "MESH":
                if not obj.particle_systems:
                    mesh_objects.append(obj)

        if not mesh_objects:
            print("Error: No valid mesh objects without particle systems")
            return False

        frame_end = frame_start + frame_duration

        for obj in mesh_objects:
            bpy.context.view_layer.objects.active = obj
            bpy.ops.object.particle_system_add()

            settings = obj.particle_systems[-1].settings
            settings.count = piece_count
            settings.frame_end = frame_end - frame_duration
            settings.frame_start = frame_start
            settings.lifetime = frame_duration
            settings.normal_factor = velocity
            settings.render_type = "NONE"

            explode = obj.modifiers.new(name="Explode", type="EXPLODE")
            explode.use_edge_cut = True

            if fade:
                explode.show_dead = False
                uv = obj.data.uv_layers.new(name="Explode fade")
                explode.particle_uv = uv.name

                # Create fade material
                mat = bpy.data.materials.new("Explode Fade")
                mat.use_nodes = True
                mat.surface_render_method = "DITHERED"
                nodes = mat.node_tree.nodes
                nodes.clear()

                node_out = nodes.new("ShaderNodeOutputMaterial")
                node_surface = nodes.new("ShaderNodeBsdfPrincipled")
                node_mix = nodes.new("ShaderNodeMixShader")
                node_trans = nodes.new("ShaderNodeBsdfTransparent")
                node_ramp = nodes.new("ShaderNodeValToRGB")
                node_sep = nodes.new("ShaderNodeSeparateXYZ")
                node_uv = nodes.new("ShaderNodeUVMap")
                node_uv.uv_map = uv.name

                links = mat.node_tree.links
                links.new(node_surface.outputs[0], node_mix.inputs[1])
                links.new(node_mix.outputs["Shader"], node_out.inputs["Surface"])
                links.new(node_trans.outputs["BSDF"], node_mix.inputs[2])
                links.new(node_ramp.outputs["Alpha"], node_mix.inputs["Fac"])
                links.new(node_sep.outputs["X"], node_ramp.inputs["Fac"])
                links.new(node_uv.outputs["UV"], node_sep.inputs["Vector"])

                node_ramp.color_ramp.elements[0].color[3] = 0.0
                node_ramp.color_ramp.elements[1].color[3] = 1.0

                if obj.data.materials:
                    obj.data.materials[0] = mat
                else:
                    obj.data.materials.append(mat)

            if style == "EXPLODE":
                settings.factor_random = velocity
                settings.angular_velocity_factor = velocity / 10.0

        if "project" in args:
            bpy.ops.wm.save_mainfile()

        print(
            json.dumps(
                {
                    "success": True,
                    "exploded": [obj.name for obj in mesh_objects],
                    "pieces": piece_count,
                    "duration": frame_duration,
                }
            )
        )
        return True

    except Exception as e:
        print(f"Error in quick_explode: {e}")
        return False


def quick_fur(args, _job_id):
    """Grow procedural fur (hair curves driven by geometry nodes) on meshes.

    Parameters:
        project: Blender project file path
        object_names: Mesh objects to add fur to
        density: LOW (1k), MEDIUM (10k) or HIGH (100k) strands per object
        length: Strand length in scene units (default 0.1)
        radius: Strand radius (default 0.001)
        use_noise: Clumpy noise displacement toward the tips (default True)
        use_frizz: Random per-point frizz toward the tips (default True)
    """
    open_project(args.get("project"))
    object_names = args.get("object_names") or []
    density = str(args.get("density", "MEDIUM")).upper()
    counts = {"LOW": 1000, "MEDIUM": 10000, "HIGH": 100000}
    if density not in counts:
        raise ScriptError(f"Unknown density '{density}' (LOW, MEDIUM, HIGH)")
    length = float(args.get("length", 0.1))
    radius = float(args.get("radius", 0.001))
    use_noise = bool(args.get("use_noise", True))
    use_frizz = bool(args.get("use_frizz", True))

    mesh_objects = [bpy.data.objects[n] for n in object_names if n in bpy.data.objects]
    mesh_objects = [o for o in mesh_objects if o.type == "MESH"]
    if not mesh_objects:
        raise ScriptError(f"None of {object_names} is an existing mesh object")

    fur_mat = bpy.data.materials.get("Fur Material") or bpy.data.materials.new("Fur Material")
    created = []
    for index, mesh_obj in enumerate(mesh_objects):
        area = sum(poly.area for poly in mesh_obj.data.polygons) or 1.0
        hair_density = counts[density] / area

        curves_data = bpy.data.hair_curves.new(f"{mesh_obj.name}_Fur")
        curves_obj = bpy.data.objects.new(f"{mesh_obj.name}_Fur", curves_data)
        bpy.context.scene.collection.objects.link(curves_obj)
        curves_obj.matrix_world = mesh_obj.matrix_world.copy()
        curves_obj.parent = mesh_obj
        curves_obj.matrix_parent_inverse = mesh_obj.matrix_world.inverted()
        curves_data.surface = mesh_obj
        curves_data.materials.append(fur_mat)

        group = _build_fur_group(
            f"{mesh_obj.name}_FurGen", mesh_obj, hair_density, length, radius, use_noise, use_frizz, index
        )
        modifier = curves_obj.modifiers.new(name="Generate Fur", type="NODES")
        modifier.node_group = group
        created.append(curves_obj.name)

    save_project()
    return {
        "success": True,
        "curves_created": created,
        "density": density,
        "strands_per_object": counts[density],
        "length": length,
        "radius": radius,
        "use_noise": use_noise,
        "use_frizz": use_frizz,
    }


def _build_fur_group(name, mesh_obj, hair_density, length, radius, use_noise, use_frizz, seed):
    """Geometry-node group that grows hair curves from ``mesh_obj``'s surface."""
    group = bpy.data.node_groups.new(name, "GeometryNodeTree")
    group.interface.new_socket(name="Geometry", in_out="INPUT", socket_type="NodeSocketGeometry")
    group.interface.new_socket(name="Geometry", in_out="OUTPUT", socket_type="NodeSocketGeometry")
    nodes = group.nodes
    links = group.links

    output_node = nodes.new("NodeGroupOutput")
    output_node.location = (1600, 0)
    nodes.new("NodeGroupInput").location = (-600, 0)

    obj_info = nodes.new("GeometryNodeObjectInfo")
    obj_info.location = (-400, 0)
    obj_info.transform_space = "RELATIVE"
    obj_info.inputs["Object"].default_value = mesh_obj

    distribute = nodes.new("GeometryNodeDistributePointsOnFaces")
    distribute.location = (-200, 0)
    distribute.distribute_method = "RANDOM"
    distribute.inputs["Density"].default_value = hair_density
    distribute.inputs["Seed"].default_value = seed
    links.new(obj_info.outputs["Geometry"], distribute.inputs["Mesh"])

    strand = nodes.new("GeometryNodeCurvePrimitiveLine")
    strand.location = (-200, 250)
    strand.mode = "POINTS"
    strand.inputs["Start"].default_value = (0.0, 0.0, 0.0)
    strand.inputs["End"].default_value = (0.0, 0.0, length)

    resample = nodes.new("GeometryNodeResampleCurve")
    resample.location = (0, 250)
    resample.inputs["Count"].default_value = 8
    links.new(strand.outputs["Curve"], resample.inputs["Curve"])

    # Distribute's Rotation output aligns each instance's Z axis to the surface normal.
    instance = nodes.new("GeometryNodeInstanceOnPoints")
    instance.location = (200, 0)
    links.new(distribute.outputs["Points"], instance.inputs["Points"])
    links.new(resample.outputs["Curve"], instance.inputs["Instance"])
    links.new(distribute.outputs["Rotation"], instance.inputs["Rotation"])

    realize = nodes.new("GeometryNodeRealizeInstances")
    realize.location = (400, 0)
    links.new(instance.outputs["Instances"], realize.inputs["Geometry"])
    geometry = realize.outputs["Geometry"]

    # Offsets grow from root (factor 0) to tip (factor 1) so roots stay attached.
    spline_param = nodes.new("GeometryNodeSplineParameter")
    spline_param.location = (400, -300)

    def offset_along_strand(vector_socket, amount, x):
        scale = nodes.new("ShaderNodeVectorMath")
        scale.operation = "SCALE"
        scale.location = (x, -250)
        links.new(vector_socket, scale.inputs[0])
        factor = nodes.new("ShaderNodeMath")
        factor.operation = "MULTIPLY"
        factor.location = (x - 150, -400)
        links.new(spline_param.outputs["Factor"], factor.inputs[0])
        factor.inputs[1].default_value = amount
        links.new(factor.outputs["Value"], scale.inputs["Scale"])
        set_pos = nodes.new("GeometryNodeSetPosition")
        set_pos.location = (x + 150, 0)
        links.new(scale.outputs["Vector"], set_pos.inputs["Offset"])
        return set_pos

    x = 700
    if use_noise:
        position = nodes.new("GeometryNodeInputPosition")
        position.location = (x - 400, -150)
        noise = nodes.new("ShaderNodeTexNoise")
        noise.location = (x - 250, -150)
        noise.inputs["Scale"].default_value = 8.0
        links.new(position.outputs["Position"], noise.inputs["Vector"])
        centered = nodes.new("ShaderNodeVectorMath")
        centered.operation = "SUBTRACT"
        centered.location = (x - 100, -150)
        centered.inputs[1].default_value = (0.5, 0.5, 0.5)
        links.new(noise.outputs["Color"], centered.inputs[0])
        set_pos = offset_along_strand(centered.outputs["Vector"], length * 0.6, x)
        links.new(geometry, set_pos.inputs["Geometry"])
        geometry = set_pos.outputs["Geometry"]
        x += 350
    if use_frizz:
        random = nodes.new("FunctionNodeRandomValue")
        random.data_type = "FLOAT_VECTOR"
        random.location = (x - 250, -150)
        random.inputs[0].default_value = (-1.0, -1.0, -1.0)
        random.inputs[1].default_value = (1.0, 1.0, 1.0)
        set_pos = offset_along_strand(random.outputs[0], length * 0.1, x)
        links.new(geometry, set_pos.inputs["Geometry"])
        geometry = set_pos.outputs["Geometry"]
        x += 350

    set_radius = nodes.new("GeometryNodeSetCurveRadius")
    set_radius.location = (x, 0)
    set_radius.inputs["Radius"].default_value = radius
    links.new(geometry, set_radius.inputs["Curve"])
    links.new(set_radius.outputs["Curve"], output_node.inputs[0])
    return group


def main():
    """Dispatch the requested operation (see mcp_common.run)."""
    run(
        {
            "quick_smoke": quick_smoke,
            "quick_liquid": quick_liquid,
            "quick_explode": quick_explode,
            "quick_fur": quick_fur,
        }
    )


if __name__ == "__main__":
    main()
