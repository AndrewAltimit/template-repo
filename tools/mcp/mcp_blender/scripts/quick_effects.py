#!/usr/bin/env python3
"""Blender quick effects script - One-click complex setups.

Based on Blender's bl_operators/object_quick_effects.py for smoke, fur, explode, liquid.
"""

import json
import sys

import bpy
from mathutils import Vector


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
    """Add fur/hair to selected objects using geometry nodes.

    Creates modern hair curves system with geometry node modifiers.

    Parameters:
        project: Blender project file path
        object_names: List of mesh object names to add fur
        density: LOW, MEDIUM, or HIGH (default: MEDIUM)
        length: Hair length in units (default: 0.1)
        radius: Hair strand radius (default: 0.001)
        use_noise: Add noise deformation (default: True)
        use_frizz: Add frizz variation (default: True)
    """
    try:
        if "project" in args:
            bpy.ops.wm.open_mainfile(filepath=args["project"])

        object_names = args.get("object_names", [])
        density = args.get("density", "MEDIUM")
        length = args.get("length", 0.1)
        # These would be used in a full implementation with noise/frizz modifiers
        _radius = args.get("radius", 0.001)  # noqa: F841
        _use_noise = args.get("use_noise", True)  # noqa: F841
        _use_frizz = args.get("use_frizz", True)  # noqa: F841

        mesh_objects = []
        for name in object_names:
            obj = bpy.data.objects.get(name)
            if obj and obj.type == "MESH":
                mesh_objects.append(obj)

        if not mesh_objects:
            print("Error: No valid mesh objects found")
            return False

        # Density counts
        density_map = {"LOW": 1000, "MEDIUM": 10000, "HIGH": 100000}
        count = density_map.get(density, 10000)

        # Create fur material
        fur_mat = bpy.data.materials.new("Fur Material")

        created_curves = []
        for mesh_obj in mesh_objects:
            mesh = mesh_obj.data
            if len(mesh.uv_layers) == 0:
                print(f"Warning: {mesh_obj.name} missing UV map, skipping")
                continue

            # Calculate density based on surface area
            area = sum(poly.area for poly in mesh.polygons)
            if area == 0.0:
                hair_density = 10
            else:
                hair_density = count / area

            # Create curves object
            bpy.context.view_layer.objects.active = mesh_obj
            bpy.ops.object.curves_empty_hair_add()
            curves_obj = bpy.context.active_object
            curves = curves_obj.data
            curves.materials.append(fur_mat)

            # Add generate modifier (simplified - full version would use asset library)
            gen_mod = curves_obj.modifiers.new(name="Generate", type="NODES")

            # Create simple geometry nodes setup for hair
            group = bpy.data.node_groups.new(f"{mesh_obj.name}_HairGen", "GeometryNodeTree")
            gen_mod.node_group = group

            nodes = group.nodes
            links = group.links
            nodes.clear()

            # Interface
            try:
                group.interface.new_socket(name="Geometry", in_out="INPUT", socket_type="NodeSocketGeometry")
                group.interface.new_socket(name="Geometry", in_out="OUTPUT", socket_type="NodeSocketGeometry")
            except AttributeError:
                pass

            input_node = nodes.new("NodeGroupInput")
            input_node.location = (-400, 0)
            output_node = nodes.new("NodeGroupOutput")
            output_node.location = (600, 0)

            # Distribute points on surface mesh (need to reference the mesh object)
            obj_info = nodes.new("GeometryNodeObjectInfo")
            obj_info.location = (-200, -200)
            obj_info.inputs["Object"].default_value = mesh_obj
            obj_info.transform_space = "RELATIVE"

            distribute = nodes.new("GeometryNodeDistributePointsOnFaces")
            distribute.location = (0, 0)
            distribute.distribute_method = "POISSON"
            distribute.inputs["Distance Min"].default_value = 0.01
            distribute.inputs["Density Max"].default_value = hair_density

            links.new(obj_info.outputs["Geometry"], distribute.inputs["Mesh"])

            # Create hair curve at each point
            curve_line = nodes.new("GeometryNodeCurvePrimitiveLine")
            curve_line.location = (0, 200)
            curve_line.mode = "DIRECTION"
            curve_line.inputs["Length"].default_value = length

            instance = nodes.new("GeometryNodeInstanceOnPoints")
            instance.location = (200, 0)
            links.new(distribute.outputs["Points"], instance.inputs["Points"])
            links.new(curve_line.outputs["Curve"], instance.inputs["Instance"])
            links.new(distribute.outputs["Normal"], instance.inputs["Rotation"])

            realize = nodes.new("GeometryNodeRealizeInstances")
            realize.location = (400, 0)
            links.new(instance.outputs["Instances"], realize.inputs["Geometry"])

            links.new(realize.outputs["Geometry"], output_node.inputs[0])

            created_curves.append(curves_obj.name)

        if "project" in args:
            bpy.ops.wm.save_mainfile()

        print(
            json.dumps(
                {
                    "success": True,
                    "curves_created": created_curves,
                    "density": density,
                    "length": length,
                }
            )
        )
        return True

    except Exception as e:
        print(f"Error in quick_fur: {e}")
        import traceback

        traceback.print_exc()
        return False


def main():
    """Main entry point."""
    argv = sys.argv

    if "--" in argv:
        argv = argv[argv.index("--") + 1 :]

    if len(argv) < 1:
        print("Usage: blender --python quick_effects.py -- <json_args>")
        sys.exit(1)

    args = json.loads(argv[0])
    job_id = args.get("job_id", "unknown")
    operation = args.get("operation")

    operations = {
        "quick_smoke": quick_smoke,
        "quick_liquid": quick_liquid,
        "quick_explode": quick_explode,
        "quick_fur": quick_fur,
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
