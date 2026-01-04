#!/usr/bin/env python3
"""Blender geometry nodes script - Enhanced procedural generation."""

import json
from math import pi
import sys

import bpy


def create_geometry_nodes(args, _job_id):
    """Create procedural geometry with nodes."""
    try:
        # Load project
        if "project" in args:
            bpy.ops.wm.open_mainfile(filepath=args["project"])

        object_name = args.get("object_name")
        node_setup = args.get("node_setup")
        parameters = args.get("parameters", {})

        # Find or create object
        obj = bpy.data.objects.get(object_name)
        if not obj:
            # Create a default mesh object based on setup type
            if node_setup in ("scatter", "noise_displace", "wave_deform"):
                bpy.ops.mesh.primitive_plane_add(size=10, location=(0, 0, 0))
            elif node_setup in ("twist", "bend"):
                bpy.ops.mesh.primitive_cylinder_add(vertices=32, radius=1, depth=4, location=(0, 0, 0))
            elif node_setup == "extrude":
                bpy.ops.mesh.primitive_plane_add(size=2, location=(0, 0, 0))
            else:
                bpy.ops.mesh.primitive_cube_add(size=2, location=(0, 0, 0))
            obj = bpy.context.active_object
            obj.name = object_name

        # Add geometry nodes modifier
        modifier = obj.modifiers.new(name="GeometryNodes", type="NODES")

        # Create node group
        node_group = bpy.data.node_groups.new(name=f"{object_name}_geo", type="GeometryNodeTree")
        modifier.node_group = node_group

        # Get nodes and links
        nodes = node_group.nodes
        links = node_group.links

        # Clear default nodes
        nodes.clear()

        # Add input and output nodes - these are created automatically in newer Blender
        # but we need to set up the interface
        input_node = nodes.new("NodeGroupInput")
        input_node.location = (-400, 0)

        output_node = nodes.new("NodeGroupOutput")
        output_node.location = (1000, 0)

        # Setup interface sockets (Blender 4.0+ API)
        try:
            # Create geometry input/output sockets
            node_group.interface.new_socket(name="Geometry", in_out="INPUT", socket_type="NodeSocketGeometry")
            node_group.interface.new_socket(name="Geometry", in_out="OUTPUT", socket_type="NodeSocketGeometry")
        except AttributeError:
            # Fallback for older Blender versions
            pass

        # Create node setup based on type
        setup_funcs = {
            "scatter": create_scatter_setup,
            "array": create_array_setup,
            "grid": create_grid_setup,
            "curve": create_curve_setup,
            "volume": create_volume_setup,
            "custom": create_custom_setup,
            "spiral": create_spiral_setup,
            "wave_deform": create_wave_deform_setup,
            "twist": create_twist_setup,
            "noise_displace": create_noise_displace_setup,
            "extrude": create_extrude_setup,
            "voronoi_scatter": create_voronoi_scatter_setup,
            "mesh_to_points": create_mesh_to_points_setup,
            "crystal_scatter": create_crystal_scatter_setup,
            "crystal_cluster": create_crystal_cluster_setup,
        }

        setup_func = setup_funcs.get(node_setup)
        if setup_func:
            setup_func(nodes, links, input_node, output_node, parameters)
        else:
            # Default simple passthrough setup
            links.new(input_node.outputs[0], output_node.inputs[0])

        # Apply crystal material if requested (for crystal setups)
        apply_material = parameters.get("apply_crystal_material", False)
        if apply_material and node_setup in ("crystal_scatter", "crystal_cluster"):
            create_crystal_material(obj, parameters)

        # Save project
        if "project" in args:
            bpy.ops.wm.save_mainfile()

        return True

    except Exception as e:
        print(f"Error creating geometry nodes: {e}")
        import traceback

        traceback.print_exc()
        return False


def create_scatter_setup(nodes, links, input_node, output_node, parameters):
    """Create scatter/distribution node setup with enhanced options."""

    count = parameters.get("count", 100)
    seed = parameters.get("seed", 0)
    scale_variance = parameters.get("scale_variance", 0.1)
    scale_base = parameters.get("scale_base", 1.0)
    use_random_rotation = parameters.get("random_rotation", True)
    align_to_normal = parameters.get("align_to_normal", False)
    instance_object = parameters.get("instance_object", None)

    # Distribute points on faces
    distribute = nodes.new("GeometryNodeDistributePointsOnFaces")
    distribute.location = (0, 0)
    distribute.distribute_method = parameters.get("method", "RANDOM")
    distribute.inputs["Density"].default_value = count
    distribute.inputs["Seed"].default_value = seed

    # Instance on points
    instance = nodes.new("GeometryNodeInstanceOnPoints")
    instance.location = (400, 0)

    # Random scale
    random_scale = nodes.new("FunctionNodeRandomValue")
    random_scale.location = (200, -150)
    random_scale.data_type = "FLOAT_VECTOR"
    min_scale = scale_base * (1 - scale_variance)
    max_scale = scale_base * (1 + scale_variance)
    random_scale.inputs["Min"].default_value = (min_scale, min_scale, min_scale)
    random_scale.inputs["Max"].default_value = (max_scale, max_scale, max_scale)
    random_scale.inputs["Seed"].default_value = seed + 1

    # Connect geometry input to distribute
    links.new(input_node.outputs[0], distribute.inputs["Mesh"])
    links.new(distribute.outputs["Points"], instance.inputs["Points"])
    links.new(random_scale.outputs["Value"], instance.inputs["Scale"])

    if use_random_rotation:
        # Random rotation
        random_rot = nodes.new("FunctionNodeRandomValue")
        random_rot.location = (200, -300)
        random_rot.data_type = "FLOAT_VECTOR"
        random_rot.inputs["Min"].default_value = (0, 0, 0)
        random_rot.inputs["Max"].default_value = (0, 0, 2 * pi)  # Only Z rotation
        random_rot.inputs["Seed"].default_value = seed + 2
        links.new(random_rot.outputs["Value"], instance.inputs["Rotation"])

    if align_to_normal:
        # Align rotation to normal
        align = nodes.new("FunctionNodeAlignEulerToVector")
        align.location = (200, -450)
        align.axis = "Z"
        normal = nodes.new("GeometryNodeInputNormal")
        normal.location = (0, -450)
        links.new(normal.outputs["Normal"], align.inputs["Vector"])
        links.new(distribute.outputs["Normal"], align.inputs["Vector"])

    # Handle instance object
    if instance_object:
        obj_info = nodes.new("GeometryNodeObjectInfo")
        obj_info.location = (200, 200)
        obj_info.transform_space = "RELATIVE"
        # Set the object reference
        if instance_object in bpy.data.objects:
            obj_info.inputs["Object"].default_value = bpy.data.objects[instance_object]
        links.new(obj_info.outputs["Geometry"], instance.inputs["Instance"])
    else:
        # Use a simple cube as default instance
        cube = nodes.new("GeometryNodeMeshCube")
        cube.location = (200, 200)
        cube.inputs["Size"].default_value = (0.1, 0.1, 0.1)
        links.new(cube.outputs["Mesh"], instance.inputs["Instance"])

    # Realize instances for final output
    realize = nodes.new("GeometryNodeRealizeInstances")
    realize.location = (600, 0)
    links.new(instance.outputs["Instances"], realize.inputs["Geometry"])
    links.new(realize.outputs["Geometry"], output_node.inputs[0])


def create_array_setup(nodes, links, input_node, output_node, parameters):
    """Create linear array node setup."""

    count = parameters.get("count", 10)
    offset_x = parameters.get("offset_x", 2.0)
    offset_y = parameters.get("offset_y", 0.0)
    offset_z = parameters.get("offset_z", 0.0)

    # Mesh line for linear array
    mesh_line = nodes.new("GeometryNodeMeshLine")
    mesh_line.location = (0, 0)
    mesh_line.mode = "OFFSET"
    mesh_line.inputs["Count"].default_value = count
    mesh_line.inputs["Offset"].default_value = (offset_x, offset_y, offset_z)

    # Instance on points
    instance = nodes.new("GeometryNodeInstanceOnPoints")
    instance.location = (200, 0)

    # Realize instances
    realize = nodes.new("GeometryNodeRealizeInstances")
    realize.location = (400, 0)

    # Connect nodes
    links.new(mesh_line.outputs["Mesh"], instance.inputs["Points"])
    links.new(input_node.outputs[0], instance.inputs["Instance"])
    links.new(instance.outputs["Instances"], realize.inputs["Geometry"])
    links.new(realize.outputs["Geometry"], output_node.inputs[0])


def create_grid_setup(nodes, links, input_node, output_node, parameters):
    """Create 2D/3D grid array setup."""

    count_x = parameters.get("count_x", 5)
    count_y = parameters.get("count_y", 5)
    count_z = parameters.get("count_z", 1)
    spacing_x = parameters.get("spacing_x", 2.0)
    spacing_y = parameters.get("spacing_y", 2.0)
    spacing_z = parameters.get("spacing_z", 2.0)

    if count_z > 1:
        # 3D grid using mesh grid + Z instances
        grid = nodes.new("GeometryNodeMeshGrid")
        grid.location = (0, 0)
        grid.inputs["Size X"].default_value = spacing_x * (count_x - 1)
        grid.inputs["Size Y"].default_value = spacing_y * (count_y - 1)
        grid.inputs["Vertices X"].default_value = count_x
        grid.inputs["Vertices Y"].default_value = count_y

        # Z duplication using mesh line
        z_line = nodes.new("GeometryNodeMeshLine")
        z_line.location = (0, -200)
        z_line.mode = "OFFSET"
        z_line.inputs["Count"].default_value = count_z
        z_line.inputs["Offset"].default_value = (0, 0, spacing_z)

        # Instance grid on Z points
        instance_z = nodes.new("GeometryNodeInstanceOnPoints")
        instance_z.location = (200, -100)
        links.new(z_line.outputs["Mesh"], instance_z.inputs["Points"])
        links.new(grid.outputs["Mesh"], instance_z.inputs["Instance"])

        # Instance input geometry on grid
        instance = nodes.new("GeometryNodeInstanceOnPoints")
        instance.location = (400, 0)
        links.new(instance_z.outputs["Instances"], instance.inputs["Points"])
        links.new(input_node.outputs[0], instance.inputs["Instance"])
    else:
        # 2D grid
        grid = nodes.new("GeometryNodeMeshGrid")
        grid.location = (0, 0)
        grid.inputs["Size X"].default_value = spacing_x * (count_x - 1)
        grid.inputs["Size Y"].default_value = spacing_y * (count_y - 1)
        grid.inputs["Vertices X"].default_value = count_x
        grid.inputs["Vertices Y"].default_value = count_y

        # Instance on grid points
        instance = nodes.new("GeometryNodeInstanceOnPoints")
        instance.location = (200, 0)
        links.new(grid.outputs["Mesh"], instance.inputs["Points"])
        links.new(input_node.outputs[0], instance.inputs["Instance"])

    # Realize instances
    realize = nodes.new("GeometryNodeRealizeInstances")
    realize.location = (600, 0)
    links.new(instance.outputs["Instances"], realize.inputs["Geometry"])
    links.new(realize.outputs["Geometry"], output_node.inputs[0])


def create_spiral_setup(nodes, links, _input_node, output_node, parameters):
    """Create spiral pattern geometry."""

    turns = parameters.get("turns", 3)
    points = parameters.get("points", 100)
    radius_start = parameters.get("radius_start", 0.5)
    radius_end = parameters.get("radius_end", 3.0)
    height = parameters.get("height", 2.0)
    profile_radius = parameters.get("profile_radius", 0.1)

    # Create spiral curve
    spiral = nodes.new("GeometryNodeCurveSpiral")
    spiral.location = (0, 0)
    spiral.inputs["Rotations"].default_value = turns
    spiral.inputs["Resolution"].default_value = points
    spiral.inputs["Start Radius"].default_value = radius_start
    spiral.inputs["End Radius"].default_value = radius_end
    spiral.inputs["Height"].default_value = height

    # Profile curve
    profile = nodes.new("GeometryNodeCurvePrimitiveCircle")
    profile.location = (0, -200)
    profile.inputs["Radius"].default_value = profile_radius

    # Curve to mesh
    curve_to_mesh = nodes.new("GeometryNodeCurveToMesh")
    curve_to_mesh.location = (200, 0)

    # Set shade smooth
    set_smooth = nodes.new("GeometryNodeSetShadeSmooth")
    set_smooth.location = (400, 0)

    # Connect nodes
    links.new(spiral.outputs["Curve"], curve_to_mesh.inputs["Curve"])
    links.new(profile.outputs["Curve"], curve_to_mesh.inputs["Profile Curve"])
    links.new(curve_to_mesh.outputs["Mesh"], set_smooth.inputs["Geometry"])
    links.new(set_smooth.outputs["Geometry"], output_node.inputs[0])


def create_curve_setup(nodes, links, _input_node, output_node, parameters):
    """Create curve-based geometry setup."""

    radius = parameters.get("radius", 5.0)
    profile_radius = parameters.get("profile_radius", 0.1)
    resolution = parameters.get("resolution", 32)

    # Curve primitive
    curve_circle = nodes.new("GeometryNodeCurvePrimitiveCircle")
    curve_circle.location = (0, 0)
    curve_circle.inputs["Radius"].default_value = radius
    curve_circle.inputs["Resolution"].default_value = resolution

    # Curve to mesh
    curve_to_mesh = nodes.new("GeometryNodeCurveToMesh")
    curve_to_mesh.location = (200, 0)

    # Profile curve
    profile = nodes.new("GeometryNodeCurvePrimitiveCircle")
    profile.location = (0, -200)
    profile.inputs["Radius"].default_value = profile_radius

    # Set shade smooth
    set_smooth = nodes.new("GeometryNodeSetShadeSmooth")
    set_smooth.location = (400, 0)

    # Connect nodes
    links.new(curve_circle.outputs["Curve"], curve_to_mesh.inputs["Curve"])
    links.new(profile.outputs["Curve"], curve_to_mesh.inputs["Profile Curve"])
    links.new(curve_to_mesh.outputs["Mesh"], set_smooth.inputs["Geometry"])
    links.new(set_smooth.outputs["Geometry"], output_node.inputs[0])


def create_wave_deform_setup(nodes, links, input_node, output_node, parameters):
    """Create wave deformation node setup."""

    amplitude = parameters.get("amplitude", 0.5)
    frequency = parameters.get("frequency", 2.0)
    phase = parameters.get("phase", 0.0)
    axis = parameters.get("axis", "Z")  # Which axis to displace along
    wave_axis = parameters.get("wave_axis", "X")  # Which axis drives the wave

    # Subdivide for smoother deformation
    subdivide = nodes.new("GeometryNodeSubdivideMesh")
    subdivide.location = (0, 0)
    subdivide.inputs["Level"].default_value = parameters.get("subdivisions", 3)

    # Position node
    position = nodes.new("GeometryNodeInputPosition")
    position.location = (0, -200)

    # Separate XYZ to get wave driver
    separate = nodes.new("ShaderNodeSeparateXYZ")
    separate.location = (150, -200)
    links.new(position.outputs["Position"], separate.inputs["Vector"])

    # Math: multiply by frequency
    multiply_freq = nodes.new("ShaderNodeMath")
    multiply_freq.location = (300, -200)
    multiply_freq.operation = "MULTIPLY"
    multiply_freq.inputs[1].default_value = frequency

    # Wave axis selection
    wave_axis_map = {"X": 0, "Y": 1, "Z": 2}
    links.new(separate.outputs[wave_axis_map.get(wave_axis, 0)], multiply_freq.inputs[0])

    # Add phase
    add_phase = nodes.new("ShaderNodeMath")
    add_phase.location = (450, -200)
    add_phase.operation = "ADD"
    add_phase.inputs[1].default_value = phase
    links.new(multiply_freq.outputs["Value"], add_phase.inputs[0])

    # Sine wave
    sine = nodes.new("ShaderNodeMath")
    sine.location = (600, -200)
    sine.operation = "SINE"
    links.new(add_phase.outputs["Value"], sine.inputs[0])

    # Multiply by amplitude
    multiply_amp = nodes.new("ShaderNodeMath")
    multiply_amp.location = (750, -200)
    multiply_amp.operation = "MULTIPLY"
    multiply_amp.inputs[1].default_value = amplitude
    links.new(sine.outputs["Value"], multiply_amp.inputs[0])

    # Create offset vector
    combine = nodes.new("ShaderNodeCombineXYZ")
    combine.location = (900, -200)
    axis_map = {"X": 0, "Y": 1, "Z": 2}
    # Connect to the appropriate axis
    links.new(multiply_amp.outputs["Value"], combine.inputs[axis_map.get(axis, 2)])

    # Set position
    set_position = nodes.new("GeometryNodeSetPosition")
    set_position.location = (600, 0)

    # Connect nodes
    links.new(input_node.outputs[0], subdivide.inputs["Mesh"])
    links.new(subdivide.outputs["Mesh"], set_position.inputs["Geometry"])
    links.new(combine.outputs["Vector"], set_position.inputs["Offset"])
    links.new(set_position.outputs["Geometry"], output_node.inputs[0])


def create_twist_setup(nodes, links, input_node, output_node, parameters):
    """Create twist deformation node setup."""

    angle = parameters.get("angle", pi)  # Total twist angle
    axis = parameters.get("axis", "Z")  # Twist axis

    # Subdivide for smoother deformation
    subdivide = nodes.new("GeometryNodeSubdivideMesh")
    subdivide.location = (0, 0)
    subdivide.inputs["Level"].default_value = parameters.get("subdivisions", 3)

    # Position node
    position = nodes.new("GeometryNodeInputPosition")
    position.location = (0, -200)

    # Separate XYZ
    separate = nodes.new("ShaderNodeSeparateXYZ")
    separate.location = (150, -200)
    links.new(position.outputs["Position"], separate.inputs["Vector"])

    # Calculate twist amount based on Z position
    axis_map = {"X": 0, "Y": 1, "Z": 2}
    multiply = nodes.new("ShaderNodeMath")
    multiply.location = (300, -200)
    multiply.operation = "MULTIPLY"
    multiply.inputs[1].default_value = angle
    links.new(separate.outputs[axis_map.get(axis, 2)], multiply.inputs[0])

    # Create rotation axis vector
    combine_axis = nodes.new("ShaderNodeCombineXYZ")
    combine_axis.location = (300, -350)
    combine_axis.inputs[axis_map.get(axis, 2)].default_value = 1.0

    # Rotate around axis
    rotate = nodes.new("FunctionNodeRotateVector")
    rotate.location = (450, -200)
    rotate.rotation_type = "AXIS_ANGLE"
    links.new(position.outputs["Position"], rotate.inputs["Vector"])
    links.new(combine_axis.outputs["Vector"], rotate.inputs["Axis"])
    links.new(multiply.outputs["Value"], rotate.inputs["Angle"])

    # Calculate offset (new position - old position)
    vector_sub = nodes.new("ShaderNodeVectorMath")
    vector_sub.location = (600, -200)
    vector_sub.operation = "SUBTRACT"
    links.new(rotate.outputs["Vector"], vector_sub.inputs[0])
    links.new(position.outputs["Position"], vector_sub.inputs[1])

    # Set position
    set_position = nodes.new("GeometryNodeSetPosition")
    set_position.location = (450, 0)

    # Connect nodes
    links.new(input_node.outputs[0], subdivide.inputs["Mesh"])
    links.new(subdivide.outputs["Mesh"], set_position.inputs["Geometry"])
    links.new(vector_sub.outputs["Vector"], set_position.inputs["Offset"])
    links.new(set_position.outputs["Geometry"], output_node.inputs[0])


def create_noise_displace_setup(nodes, links, input_node, output_node, parameters):
    """Create noise-based displacement node setup."""

    strength = parameters.get("strength", 0.5)
    scale = parameters.get("scale", 5.0)
    detail = parameters.get("detail", 2.0)
    roughness = parameters.get("roughness", 0.5)
    use_normals = parameters.get("use_normals", True)

    # Subdivide for smoother displacement
    subdivide = nodes.new("GeometryNodeSubdivideMesh")
    subdivide.location = (0, 0)
    subdivide.inputs["Level"].default_value = parameters.get("subdivisions", 3)

    # Position node for noise input
    position = nodes.new("GeometryNodeInputPosition")
    position.location = (0, -200)

    # Noise texture
    noise = nodes.new("ShaderNodeTexNoise")
    noise.location = (150, -200)
    noise.inputs["Scale"].default_value = scale
    noise.inputs["Detail"].default_value = detail
    noise.inputs["Roughness"].default_value = roughness
    links.new(position.outputs["Position"], noise.inputs["Vector"])

    # Multiply noise by strength
    multiply = nodes.new("ShaderNodeMath")
    multiply.location = (300, -200)
    multiply.operation = "MULTIPLY"
    multiply.inputs[1].default_value = strength
    links.new(noise.outputs["Fac"], multiply.inputs[0])

    # Set position
    set_position = nodes.new("GeometryNodeSetPosition")
    set_position.location = (450, 0)

    if use_normals:
        # Normal node
        normal = nodes.new("GeometryNodeInputNormal")
        normal.location = (150, -350)

        # Multiply normal by displacement amount
        vector_multiply = nodes.new("ShaderNodeVectorMath")
        vector_multiply.location = (450, -200)
        vector_multiply.operation = "SCALE"
        links.new(normal.outputs["Normal"], vector_multiply.inputs[0])
        links.new(multiply.outputs["Value"], vector_multiply.inputs["Scale"])
        links.new(vector_multiply.outputs["Vector"], set_position.inputs["Offset"])
    else:
        # Create offset vector (just Z displacement)
        combine = nodes.new("ShaderNodeCombineXYZ")
        combine.location = (450, -200)
        links.new(multiply.outputs["Value"], combine.inputs["Z"])
        links.new(combine.outputs["Vector"], set_position.inputs["Offset"])

    # Connect nodes
    links.new(input_node.outputs[0], subdivide.inputs["Mesh"])
    links.new(subdivide.outputs["Mesh"], set_position.inputs["Geometry"])
    links.new(set_position.outputs["Geometry"], output_node.inputs[0])


def create_extrude_setup(nodes, links, input_node, output_node, parameters):
    """Create extrusion node setup."""

    offset = parameters.get("offset", 1.0)
    individual = parameters.get("individual", False)

    # Extrude mesh
    extrude = nodes.new("GeometryNodeExtrudeMesh")
    extrude.location = (200, 0)
    extrude.mode = "FACES" if not individual else "INDIVIDUAL"
    extrude.inputs["Offset Scale"].default_value = offset

    # Optionally scale the top
    top_scale = parameters.get("top_scale", 1.0)
    if top_scale != 1.0:
        scale_elements = nodes.new("GeometryNodeScaleElements")
        scale_elements.location = (400, 0)
        scale_elements.inputs["Scale"].default_value = top_scale
        links.new(input_node.outputs[0], extrude.inputs["Mesh"])
        links.new(extrude.outputs["Mesh"], scale_elements.inputs["Geometry"])
        links.new(extrude.outputs["Top"], scale_elements.inputs["Selection"])
        links.new(scale_elements.outputs["Geometry"], output_node.inputs[0])
    else:
        links.new(input_node.outputs[0], extrude.inputs["Mesh"])
        links.new(extrude.outputs["Mesh"], output_node.inputs[0])


def create_volume_setup(nodes, links, _input_node, output_node, parameters):
    """Create volume/voxel-based setup."""

    density = parameters.get("density", 1.0)
    size_x = parameters.get("size_x", 5.0)
    size_y = parameters.get("size_y", 5.0)
    size_z = parameters.get("size_z", 5.0)
    threshold = parameters.get("threshold", 0.1)

    # Volume cube
    volume_cube = nodes.new("GeometryNodeVolumeCube")
    volume_cube.location = (0, 0)
    volume_cube.inputs["Density"].default_value = density
    volume_cube.inputs["Size"].default_value = (size_x, size_y, size_z)

    # Volume to mesh
    volume_to_mesh = nodes.new("GeometryNodeVolumeToMesh")
    volume_to_mesh.location = (200, 0)
    volume_to_mesh.inputs["Threshold"].default_value = threshold

    # Smooth
    set_smooth = nodes.new("GeometryNodeSetShadeSmooth")
    set_smooth.location = (400, 0)

    # Connect nodes
    links.new(volume_cube.outputs["Volume"], volume_to_mesh.inputs["Volume"])
    links.new(volume_to_mesh.outputs["Mesh"], set_smooth.inputs["Geometry"])
    links.new(set_smooth.outputs["Geometry"], output_node.inputs[0])


def create_voronoi_scatter_setup(nodes, links, input_node, output_node, parameters):
    """Create Voronoi-based point scattering."""

    scale = parameters.get("scale", 5.0)
    randomness = parameters.get("randomness", 1.0)
    instance_scale = parameters.get("instance_scale", 0.1)

    # Position for voronoi input
    position = nodes.new("GeometryNodeInputPosition")
    position.location = (-200, -200)

    # Voronoi texture for cell centers
    voronoi = nodes.new("ShaderNodeTexVoronoi")
    voronoi.location = (0, -200)
    voronoi.feature = "SMOOTH_F1"
    voronoi.inputs["Scale"].default_value = scale
    voronoi.inputs["Randomness"].default_value = randomness
    links.new(position.outputs["Position"], voronoi.inputs["Vector"])

    # Distribute points
    distribute = nodes.new("GeometryNodeDistributePointsOnFaces")
    distribute.location = (200, 0)
    distribute.distribute_method = "POISSON"
    distribute.inputs["Distance Min"].default_value = 1.0 / scale

    # Instance cube
    cube = nodes.new("GeometryNodeMeshCube")
    cube.location = (200, 200)
    cube.inputs["Size"].default_value = (instance_scale, instance_scale, instance_scale)

    # Instance on points
    instance = nodes.new("GeometryNodeInstanceOnPoints")
    instance.location = (400, 0)

    # Use voronoi color for instance scale variation
    color_to_float = nodes.new("ShaderNodeRGBToBW")
    color_to_float.location = (200, -200)
    links.new(voronoi.outputs["Color"], color_to_float.inputs["Color"])

    # Map range for scale
    map_range = nodes.new("ShaderNodeMapRange")
    map_range.location = (350, -200)
    map_range.inputs["From Min"].default_value = 0.0
    map_range.inputs["From Max"].default_value = 1.0
    map_range.inputs["To Min"].default_value = 0.5
    map_range.inputs["To Max"].default_value = 1.5
    links.new(color_to_float.outputs["Val"], map_range.inputs["Value"])

    # Realize instances
    realize = nodes.new("GeometryNodeRealizeInstances")
    realize.location = (600, 0)

    # Connect nodes
    links.new(input_node.outputs[0], distribute.inputs["Mesh"])
    links.new(distribute.outputs["Points"], instance.inputs["Points"])
    links.new(cube.outputs["Mesh"], instance.inputs["Instance"])
    links.new(instance.outputs["Instances"], realize.inputs["Geometry"])
    links.new(realize.outputs["Geometry"], output_node.inputs[0])


def create_mesh_to_points_setup(nodes, links, input_node, output_node, parameters):
    """Convert mesh vertices to point cloud with instances."""

    point_radius = parameters.get("point_radius", 0.05)
    use_spheres = parameters.get("use_spheres", True)

    # Mesh to points
    mesh_to_points = nodes.new("GeometryNodeMeshToPoints")
    mesh_to_points.location = (200, 0)
    mesh_to_points.mode = "VERTICES"

    if use_spheres:
        # Create sphere instances
        sphere = nodes.new("GeometryNodeMeshIcoSphere")
        sphere.location = (200, 200)
        sphere.inputs["Radius"].default_value = point_radius
        sphere.inputs["Subdivisions"].default_value = 2

        # Instance on points
        instance = nodes.new("GeometryNodeInstanceOnPoints")
        instance.location = (400, 0)

        # Realize instances
        realize = nodes.new("GeometryNodeRealizeInstances")
        realize.location = (600, 0)

        links.new(input_node.outputs[0], mesh_to_points.inputs["Mesh"])
        links.new(mesh_to_points.outputs["Points"], instance.inputs["Points"])
        links.new(sphere.outputs["Mesh"], instance.inputs["Instance"])
        links.new(instance.outputs["Instances"], realize.inputs["Geometry"])
        links.new(realize.outputs["Geometry"], output_node.inputs[0])
    else:
        # Just output points with radius
        set_radius = nodes.new("GeometryNodeSetPointRadius")
        set_radius.location = (400, 0)
        set_radius.inputs["Radius"].default_value = point_radius

        links.new(input_node.outputs[0], mesh_to_points.inputs["Mesh"])
        links.new(mesh_to_points.outputs["Points"], set_radius.inputs["Points"])
        links.new(set_radius.outputs["Points"], output_node.inputs[0])


def create_crystal_material(obj, parameters):
    """Create and apply a glass/translucent crystal material to an object.

    Parameters:
        obj: The Blender object to apply the material to
        parameters: Dict with optional color settings
            - base_color: tuple (r, g, b, a) default (0.8, 0.85, 1.0, 1.0)
            - transmission: float, default 0.9
            - roughness: float, default 0.1
            - ior: float, default 1.45
    """
    # Get color parameters
    base_color = parameters.get("crystal_color", (0.8, 0.85, 1.0, 1.0))
    transmission = parameters.get("crystal_transmission", 0.9)
    roughness = parameters.get("crystal_roughness", 0.1)
    ior = parameters.get("crystal_ior", 1.45)

    # Create material
    mat_name = f"{obj.name}_CrystalMaterial"
    mat = bpy.data.materials.new(name=mat_name)
    mat.use_nodes = True

    nodes = mat.node_tree.nodes
    links = mat.node_tree.links

    # Clear default nodes
    nodes.clear()

    # Create Principled BSDF
    bsdf = nodes.new("ShaderNodeBsdfPrincipled")
    bsdf.location = (0, 0)
    bsdf.inputs["Base Color"].default_value = base_color
    bsdf.inputs["Roughness"].default_value = roughness
    bsdf.inputs["IOR"].default_value = ior

    # Set transmission (glass-like)
    # Blender 4.0+ uses "Transmission Weight", older uses "Transmission"
    try:
        bsdf.inputs["Transmission Weight"].default_value = transmission
    except KeyError:
        bsdf.inputs["Transmission"].default_value = transmission

    # Set subsurface for inner glow effect
    try:
        bsdf.inputs["Subsurface Weight"].default_value = 0.1
        bsdf.inputs["Subsurface Radius"].default_value = (0.1, 0.1, 0.1)
    except KeyError:
        # Older Blender versions
        pass

    # Create output node
    output = nodes.new("ShaderNodeOutputMaterial")
    output.location = (300, 0)

    # Connect BSDF to output
    links.new(bsdf.outputs["BSDF"], output.inputs["Surface"])

    # Assign material to object
    if obj.data.materials:
        obj.data.materials[0] = mat
    else:
        obj.data.materials.append(mat)

    return mat


def create_crystal_scatter_setup(nodes, links, input_node, output_node, parameters):
    """Create crystal scatter node setup with procedural crystal generation.

    Distributes faceted crystal shapes across a mesh surface with normal alignment,
    random height/scale variation, and optional glass material.

    Parameters:
        density (float): Crystal distribution density (default: 10.0)
        seed (int): Random seed for variation (default: 0)
        crystal_scale (float): Global scale multiplier (default: 1.0)
        crystal_height_min (float): Minimum crystal height (default: 0.1)
        crystal_height_max (float): Maximum crystal height (default: 0.5)
        crystal_radius (float): Crystal base radius (default: 0.05)
        facets (int): Number of facets, 6=hexagonal, 8=octagonal (default: 6)
        tilt_variance (float): Max tilt from normal in radians (default: 0.3)
        scale_variance (float): Scale randomization amount (default: 0.2)
        use_poisson (bool): Use Poisson disk for even spacing (default: True)
        apply_crystal_material (bool): Apply glass material (default: True)
    """
    # Extract parameters with defaults
    density = parameters.get("density", 10.0)
    seed = parameters.get("seed", 0)
    crystal_scale = parameters.get("crystal_scale", 1.0)
    height_min = parameters.get("crystal_height_min", 0.1)
    height_max = parameters.get("crystal_height_max", 0.5)
    crystal_radius = parameters.get("crystal_radius", 0.05)
    facets = parameters.get("facets", 6)
    tilt_variance = parameters.get("tilt_variance", 0.3)
    scale_variance = parameters.get("scale_variance", 0.2)
    use_poisson = parameters.get("use_poisson", True)

    # ----- Create Crystal Mesh (Cone with pointed tip) -----
    crystal_cone = nodes.new("GeometryNodeMeshCone")
    crystal_cone.location = (0, 300)
    crystal_cone.inputs["Vertices"].default_value = facets
    crystal_cone.inputs["Radius Top"].default_value = 0.0  # Pointed tip
    crystal_cone.inputs["Radius Bottom"].default_value = crystal_radius
    crystal_cone.inputs["Depth"].default_value = (height_min + height_max) / 2

    # Set shade smooth for crystal surfaces
    set_smooth = nodes.new("GeometryNodeSetShadeSmooth")
    set_smooth.location = (200, 300)
    links.new(crystal_cone.outputs["Mesh"], set_smooth.inputs["Geometry"])

    # ----- Distribute Points on Surface -----
    distribute = nodes.new("GeometryNodeDistributePointsOnFaces")
    distribute.location = (0, 0)
    distribute.distribute_method = "POISSON" if use_poisson else "RANDOM"

    # Set density based on distribution method (Blender 4.0+ API)
    if use_poisson:
        # POISSON mode uses "Distance Min", "Density Max", and "Density Factor"
        # Convert density to minimum distance (inverse relationship)
        # Higher density = smaller distance between points
        distance_min = 1.0 / max(density, 0.1) * 0.5  # Scale factor for reasonable distances
        distribute.inputs["Distance Min"].default_value = max(0.01, distance_min)
        # Density Max controls maximum points per area - must be set for POISSON to work
        distribute.inputs["Density Max"].default_value = density * 10.0
        distribute.inputs["Density Factor"].default_value = 1.0
    else:
        # RANDOM mode uses "Density"
        distribute.inputs["Density"].default_value = density

    distribute.inputs["Seed"].default_value = seed

    # Connect input geometry
    links.new(input_node.outputs[0], distribute.inputs["Mesh"])

    # ----- Random Height Variation -----
    random_height = nodes.new("FunctionNodeRandomValue")
    random_height.location = (200, -100)
    random_height.data_type = "FLOAT"
    random_height.inputs["Min"].default_value = height_min * crystal_scale
    random_height.inputs["Max"].default_value = height_max * crystal_scale
    random_height.inputs["Seed"].default_value = seed + 1

    # ----- Create Scale Vector -----
    # Scale X/Y proportionally, Z is the height
    combine_scale = nodes.new("ShaderNodeCombineXYZ")
    combine_scale.location = (400, -100)

    # Base scale with variance for X and Y
    random_xy_scale = nodes.new("FunctionNodeRandomValue")
    random_xy_scale.location = (200, -250)
    random_xy_scale.data_type = "FLOAT"
    min_xy = crystal_scale * (1 - scale_variance)
    max_xy = crystal_scale * (1 + scale_variance)
    random_xy_scale.inputs["Min"].default_value = min_xy
    random_xy_scale.inputs["Max"].default_value = max_xy
    random_xy_scale.inputs["Seed"].default_value = seed + 3

    links.new(random_xy_scale.outputs["Value"], combine_scale.inputs["X"])
    links.new(random_xy_scale.outputs["Value"], combine_scale.inputs["Y"])
    links.new(random_height.outputs["Value"], combine_scale.inputs["Z"])

    # ----- Align to Surface Normal -----
    align = nodes.new("FunctionNodeAlignEulerToVector")
    align.location = (200, -400)
    align.axis = "Z"
    links.new(distribute.outputs["Normal"], align.inputs["Vector"])

    # ----- Random Tilt Variation -----
    random_tilt = nodes.new("FunctionNodeRandomValue")
    random_tilt.location = (200, -550)
    random_tilt.data_type = "FLOAT_VECTOR"
    random_tilt.inputs["Min"].default_value = (-tilt_variance, -tilt_variance, 0)
    random_tilt.inputs["Max"].default_value = (tilt_variance, tilt_variance, 2 * pi)
    random_tilt.inputs["Seed"].default_value = seed + 2

    # Combine aligned rotation with random tilt
    rotate_euler = nodes.new("FunctionNodeRotateEuler")
    rotate_euler.location = (400, -450)
    rotate_euler.space = "LOCAL"
    links.new(align.outputs["Rotation"], rotate_euler.inputs["Rotation"])
    links.new(random_tilt.outputs["Value"], rotate_euler.inputs["Rotate By"])

    # ----- Instance Crystals on Points -----
    instance = nodes.new("GeometryNodeInstanceOnPoints")
    instance.location = (600, 0)
    links.new(distribute.outputs["Points"], instance.inputs["Points"])
    links.new(set_smooth.outputs["Geometry"], instance.inputs["Instance"])
    links.new(combine_scale.outputs["Vector"], instance.inputs["Scale"])
    links.new(rotate_euler.outputs["Rotation"], instance.inputs["Rotation"])

    # ----- Realize Instances -----
    realize = nodes.new("GeometryNodeRealizeInstances")
    realize.location = (800, 0)
    links.new(instance.outputs["Instances"], realize.inputs["Geometry"])

    # Connect to output
    links.new(realize.outputs["Geometry"], output_node.inputs[0])


def create_crystal_cluster_setup(nodes, links, input_node, output_node, parameters):
    """Create clustered crystal formation using Voronoi-based distribution.

    Creates groups of crystals at cluster centers, simulating natural crystal
    formations like geodes or mineral deposits.

    Parameters:
        cluster_scale (float): Voronoi cell size, larger = fewer clusters (default: 5.0)
        cluster_density (float): Density of cluster centers (default: 5.0)
        crystals_per_cluster_min (int): Min crystals per cluster (default: 2)
        crystals_per_cluster_max (int): Max crystals per cluster (default: 5)
        cluster_radius (float): Spread of crystals within cluster (default: 0.3)
        crystal_height_min (float): Minimum crystal height (default: 0.1)
        crystal_height_max (float): Maximum crystal height (default: 0.4)
        crystal_radius (float): Crystal base radius (default: 0.04)
        facets (int): Number of facets (default: 6)
        seed (int): Random seed (default: 0)
        tilt_variance (float): Max tilt from normal (default: 0.4)
    """
    # Extract parameters
    cluster_scale = parameters.get("cluster_scale", 5.0)
    cluster_density = parameters.get("cluster_density", 5.0)
    crystals_min = parameters.get("crystals_per_cluster_min", 2)
    crystals_max = parameters.get("crystals_per_cluster_max", 5)
    cluster_radius = parameters.get("cluster_radius", 0.3)
    height_min = parameters.get("crystal_height_min", 0.1)
    height_max = parameters.get("crystal_height_max", 0.4)
    crystal_rad = parameters.get("crystal_radius", 0.04)
    facets = parameters.get("facets", 6)
    seed = parameters.get("seed", 0)
    tilt_variance = parameters.get("tilt_variance", 0.4)

    # ----- Create Crystal Mesh -----
    crystal_cone = nodes.new("GeometryNodeMeshCone")
    crystal_cone.location = (0, 400)
    crystal_cone.inputs["Vertices"].default_value = facets
    crystal_cone.inputs["Radius Top"].default_value = 0.0
    crystal_cone.inputs["Radius Bottom"].default_value = crystal_rad
    crystal_cone.inputs["Depth"].default_value = (height_min + height_max) / 2

    set_smooth = nodes.new("GeometryNodeSetShadeSmooth")
    set_smooth.location = (200, 400)
    links.new(crystal_cone.outputs["Mesh"], set_smooth.inputs["Geometry"])

    # ----- Voronoi Texture for Cluster Detection -----
    position = nodes.new("GeometryNodeInputPosition")
    position.location = (-200, -200)

    voronoi = nodes.new("ShaderNodeTexVoronoi")
    voronoi.location = (0, -200)
    voronoi.feature = "F1"
    voronoi.inputs["Scale"].default_value = cluster_scale
    voronoi.inputs["Randomness"].default_value = 1.0
    links.new(position.outputs["Position"], voronoi.inputs["Vector"])

    # ----- Map Voronoi Distance to Density Mask -----
    # Crystals grow more densely near Voronoi cell centers
    map_range = nodes.new("ShaderNodeMapRange")
    map_range.location = (200, -200)
    map_range.inputs["From Min"].default_value = 0.0
    map_range.inputs["From Max"].default_value = 0.5
    map_range.inputs["To Min"].default_value = cluster_density * 2
    map_range.inputs["To Max"].default_value = cluster_density * 0.1
    map_range.clamp = True
    links.new(voronoi.outputs["Distance"], map_range.inputs["Value"])

    # ----- Distribute Cluster Center Points -----
    distribute = nodes.new("GeometryNodeDistributePointsOnFaces")
    distribute.location = (400, 0)
    distribute.distribute_method = "POISSON"
    distribute.inputs["Seed"].default_value = seed
    # For POISSON mode: set minimum distance, density max, and connect density factor
    # Lower distance = more points
    distribute.inputs["Distance Min"].default_value = 0.1 / max(cluster_density, 0.1)
    # Density Max must be set for POISSON to generate points
    distribute.inputs["Density Max"].default_value = cluster_density * 10.0

    links.new(input_node.outputs[0], distribute.inputs["Mesh"])
    links.new(map_range.outputs["Result"], distribute.inputs["Density Factor"])

    # ----- Random Number of Crystals per Cluster -----
    random_count = nodes.new("FunctionNodeRandomValue")
    random_count.location = (400, -150)
    random_count.data_type = "INT"
    random_count.inputs["Min"].default_value = crystals_min
    random_count.inputs["Max"].default_value = crystals_max + 1
    random_count.inputs["Seed"].default_value = seed + 10

    # ----- Create Offset Points Around Each Cluster Center -----
    # Use a small grid/circle of points around each distributed point
    mesh_circle = nodes.new("GeometryNodeCurvePrimitiveCircle")
    mesh_circle.location = (400, 200)
    mesh_circle.mode = "RADIUS"  # RADIUS mode has Radius input, POINTS mode doesn't
    mesh_circle.inputs["Resolution"].default_value = crystals_max
    mesh_circle.inputs["Radius"].default_value = cluster_radius

    # Convert circle to points
    curve_to_points = nodes.new("GeometryNodeCurveToPoints")
    curve_to_points.location = (600, 200)
    curve_to_points.mode = "COUNT"
    curve_to_points.inputs["Count"].default_value = crystals_max
    links.new(mesh_circle.outputs["Curve"], curve_to_points.inputs["Curve"])

    # ----- Instance Circle Points at Cluster Centers -----
    instance_clusters = nodes.new("GeometryNodeInstanceOnPoints")
    instance_clusters.location = (600, 0)
    links.new(distribute.outputs["Points"], instance_clusters.inputs["Points"])
    links.new(curve_to_points.outputs["Points"], instance_clusters.inputs["Instance"])

    # Random rotation for cluster orientation
    random_cluster_rot = nodes.new("FunctionNodeRandomValue")
    random_cluster_rot.location = (400, -300)
    random_cluster_rot.data_type = "FLOAT_VECTOR"
    random_cluster_rot.inputs["Min"].default_value = (0, 0, 0)
    random_cluster_rot.inputs["Max"].default_value = (0, 0, 2 * pi)
    random_cluster_rot.inputs["Seed"].default_value = seed + 5
    links.new(random_cluster_rot.outputs["Value"], instance_clusters.inputs["Rotation"])

    # Realize cluster points
    realize_clusters = nodes.new("GeometryNodeRealizeInstances")
    realize_clusters.location = (800, 0)
    links.new(instance_clusters.outputs["Instances"], realize_clusters.inputs["Geometry"])

    # ----- Random Height for Each Crystal -----
    random_height = nodes.new("FunctionNodeRandomValue")
    random_height.location = (800, -150)
    random_height.data_type = "FLOAT"
    random_height.inputs["Min"].default_value = height_min
    random_height.inputs["Max"].default_value = height_max
    random_height.inputs["Seed"].default_value = seed + 1

    # Scale vector
    combine_scale = nodes.new("ShaderNodeCombineXYZ")
    combine_scale.location = (950, -150)
    combine_scale.inputs["X"].default_value = 1.0
    combine_scale.inputs["Y"].default_value = 1.0
    links.new(random_height.outputs["Value"], combine_scale.inputs["Z"])

    # ----- Align to Original Surface Normal (approximate) -----
    # Get normal from original mesh via proximity
    geometry_proximity = nodes.new("GeometryNodeProximity")
    geometry_proximity.location = (800, -350)
    geometry_proximity.target_element = "FACES"
    links.new(input_node.outputs[0], geometry_proximity.inputs["Target"])

    # Use the original mesh normals for alignment
    align = nodes.new("FunctionNodeAlignEulerToVector")
    align.location = (950, -350)
    align.axis = "Z"

    # Get normal at closest point
    sample_normal = nodes.new("GeometryNodeInputNormal")
    sample_normal.location = (800, -500)

    # Random tilt
    random_tilt = nodes.new("FunctionNodeRandomValue")
    random_tilt.location = (800, -600)
    random_tilt.data_type = "FLOAT_VECTOR"
    random_tilt.inputs["Min"].default_value = (-tilt_variance, -tilt_variance, 0)
    random_tilt.inputs["Max"].default_value = (tilt_variance, tilt_variance, 2 * pi)
    random_tilt.inputs["Seed"].default_value = seed + 2

    rotate_euler = nodes.new("FunctionNodeRotateEuler")
    rotate_euler.location = (1100, -400)
    rotate_euler.space = "LOCAL"
    links.new(random_tilt.outputs["Value"], rotate_euler.inputs["Rotate By"])

    # ----- Instance Crystals on Cluster Points -----
    instance_crystals = nodes.new("GeometryNodeInstanceOnPoints")
    instance_crystals.location = (1000, 0)
    links.new(realize_clusters.outputs["Geometry"], instance_crystals.inputs["Points"])
    links.new(set_smooth.outputs["Geometry"], instance_crystals.inputs["Instance"])
    links.new(combine_scale.outputs["Vector"], instance_crystals.inputs["Scale"])
    links.new(rotate_euler.outputs["Rotation"], instance_crystals.inputs["Rotation"])

    # ----- Final Realize -----
    realize_final = nodes.new("GeometryNodeRealizeInstances")
    realize_final.location = (1200, 0)
    links.new(instance_crystals.outputs["Instances"], realize_final.inputs["Geometry"])

    # Connect to output
    links.new(realize_final.outputs["Geometry"], output_node.inputs[0])


def create_custom_setup(nodes, links, input_node, output_node, parameters):
    """Create custom node setup based on parameters."""

    # This is a flexible setup for advanced users
    subdivision_level = parameters.get("subdivision_level", 2)
    noise_scale = parameters.get("noise_scale", 5.0)
    noise_detail = parameters.get("noise_detail", 2.0)
    displacement_strength = parameters.get("displacement_strength", 0.3)

    # Subdivision
    subdivide = nodes.new("GeometryNodeSubdivideMesh")
    subdivide.location = (0, 0)
    subdivide.inputs["Level"].default_value = subdivision_level

    # Position for noise
    position = nodes.new("GeometryNodeInputPosition")
    position.location = (-200, -200)

    # Noise texture for displacement
    noise = nodes.new("ShaderNodeTexNoise")
    noise.location = (0, -200)
    noise.inputs["Scale"].default_value = noise_scale
    noise.inputs["Detail"].default_value = noise_detail
    links.new(position.outputs["Position"], noise.inputs["Vector"])

    # Normal node
    normal = nodes.new("GeometryNodeInputNormal")
    normal.location = (0, -350)

    # Vector math for displacement direction
    vector_multiply = nodes.new("ShaderNodeVectorMath")
    vector_multiply.location = (200, -200)
    vector_multiply.operation = "SCALE"
    links.new(normal.outputs["Normal"], vector_multiply.inputs[0])
    links.new(noise.outputs["Fac"], vector_multiply.inputs["Scale"])

    # Scale by strength
    strength_multiply = nodes.new("ShaderNodeVectorMath")
    strength_multiply.location = (350, -200)
    strength_multiply.operation = "SCALE"
    strength_multiply.inputs["Scale"].default_value = displacement_strength
    links.new(vector_multiply.outputs["Vector"], strength_multiply.inputs[0])

    # Set position for displacement
    set_position = nodes.new("GeometryNodeSetPosition")
    set_position.location = (200, 0)

    # Connect nodes
    links.new(input_node.outputs[0], subdivide.inputs["Mesh"])
    links.new(subdivide.outputs["Mesh"], set_position.inputs["Geometry"])
    links.new(strength_multiply.outputs["Vector"], set_position.inputs["Offset"])
    links.new(set_position.outputs["Geometry"], output_node.inputs[0])


def create_procedural_texture(args, _job_id):
    """Create procedural texture with nodes."""
    try:
        # Load project
        if "project" in args:
            bpy.ops.wm.open_mainfile(filepath=args["project"])

        texture_name = args.get("name", "ProceduralTexture")
        texture_type = args.get("type", "noise")
        parameters = args.get("parameters", {})

        # Create material
        mat = bpy.data.materials.new(name=texture_name)
        mat.use_nodes = True

        nodes = mat.node_tree.nodes
        links = mat.node_tree.links

        # Clear default nodes
        nodes.clear()

        # Add output node
        output = nodes.new("ShaderNodeOutputMaterial")
        output.location = (800, 0)

        # Add principled BSDF
        bsdf = nodes.new("ShaderNodeBsdfPrincipled")
        bsdf.location = (600, 0)

        # Create texture based on type
        texture_creators = {
            "noise": create_noise_texture,
            "voronoi": create_voronoi_texture,
            "wave": create_wave_texture,
            "brick": create_brick_texture,
            "gradient": create_gradient_texture,
        }

        creator = texture_creators.get(texture_type)
        if creator:
            texture = creator(nodes, parameters)
        else:
            # Default to checker
            texture = nodes.new("ShaderNodeTexChecker")
            texture.location = (0, 0)
            texture.inputs["Scale"].default_value = parameters.get("scale", 5.0)

        # Add texture coordinate
        tex_coord = nodes.new("ShaderNodeTexCoord")
        tex_coord.location = (-200, 0)

        # Connect nodes
        if "Vector" in texture.inputs:
            links.new(tex_coord.outputs["UV"], texture.inputs["Vector"])

        if "Color" in texture.outputs:
            links.new(texture.outputs["Color"], bsdf.inputs["Base Color"])
        elif "Fac" in texture.outputs:
            links.new(texture.outputs["Fac"], bsdf.inputs["Roughness"])

        links.new(bsdf.outputs["BSDF"], output.inputs["Surface"])

        # Save project
        if "project" in args:
            bpy.ops.wm.save_mainfile()

        return True

    except Exception as e:
        print(f"Error creating procedural texture: {e}")
        return False


def create_noise_texture(nodes, parameters):
    """Create noise texture node."""
    texture = nodes.new("ShaderNodeTexNoise")
    texture.location = (0, 0)
    texture.inputs["Scale"].default_value = parameters.get("scale", 5.0)
    texture.inputs["Detail"].default_value = parameters.get("detail", 2.0)
    texture.inputs["Roughness"].default_value = parameters.get("roughness", 0.5)
    return texture


def create_voronoi_texture(nodes, parameters):
    """Create voronoi texture node."""
    texture = nodes.new("ShaderNodeTexVoronoi")
    texture.location = (0, 0)
    texture.feature = parameters.get("feature", "F1")
    texture.inputs["Scale"].default_value = parameters.get("scale", 5.0)
    return texture


def create_wave_texture(nodes, parameters):
    """Create wave texture node."""
    texture = nodes.new("ShaderNodeTexWave")
    texture.location = (0, 0)
    texture.wave_type = parameters.get("wave_type", "BANDS")
    texture.inputs["Scale"].default_value = parameters.get("scale", 5.0)
    return texture


def create_brick_texture(nodes, parameters):
    """Create brick texture node."""
    texture = nodes.new("ShaderNodeTexBrick")
    texture.location = (0, 0)
    texture.inputs["Scale"].default_value = parameters.get("scale", 5.0)
    return texture


def create_gradient_texture(nodes, parameters):
    """Create gradient texture node."""
    texture = nodes.new("ShaderNodeTexGradient")
    texture.location = (0, 0)
    texture.gradient_type = parameters.get("gradient_type", "LINEAR")
    return texture


def main():
    """Main entry point."""
    argv = sys.argv

    if "--" in argv:
        argv = argv[argv.index("--") + 1 :]

    if len(argv) < 2:
        print("Usage: blender --python geometry_nodes.py -- args.json job_id")
        sys.exit(1)

    args_file = argv[0]
    job_id = argv[1]

    with open(args_file, "r", encoding="utf-8") as f:
        args = json.load(f)

    operation = args.get("operation")

    if operation == "create_geometry_nodes":
        success = create_geometry_nodes(args, job_id)
    elif operation == "create_procedural_texture":
        success = create_procedural_texture(args, job_id)
    else:
        print(f"Unknown operation: {operation}")
        sys.exit(1)

    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
