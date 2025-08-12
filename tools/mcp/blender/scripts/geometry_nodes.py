#!/usr/bin/env python3
"""Blender geometry nodes script."""

import json
import sys

import bpy


def create_geometry_nodes(args, job_id):
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
            # Create a default mesh object
            bpy.ops.mesh.primitive_plane_add(location=(0, 0, 0))
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

        # Add input and output nodes
        input_node = nodes.new("NodeGroupInput")
        input_node.location = (-200, 0)

        output_node = nodes.new("NodeGroupOutput")
        output_node.location = (800, 0)

        # Create node setup based on type
        if node_setup == "scatter":
            create_scatter_setup(nodes, links, input_node, output_node, parameters)
        elif node_setup == "array":
            create_array_setup(nodes, links, input_node, output_node, parameters)
        elif node_setup == "curve":
            create_curve_setup(nodes, links, input_node, output_node, parameters)
        elif node_setup == "volume":
            create_volume_setup(nodes, links, input_node, output_node, parameters)
        elif node_setup == "custom":
            create_custom_setup(nodes, links, input_node, output_node, parameters)
        else:
            # Default simple setup
            links.new(input_node.outputs["Geometry"], output_node.inputs["Geometry"])

        # Save project
        if "project" in args:
            bpy.ops.wm.save_mainfile()

        return True

    except Exception as e:
        print(f"Error creating geometry nodes: {e}")
        return False


def create_scatter_setup(nodes, links, input_node, output_node, parameters):
    """Create scatter/distribution node setup."""

    # Distribute points on faces
    distribute = nodes.new("GeometryNodeDistributePointsOnFaces")
    distribute.location = (0, 0)
    distribute.inputs["Density"].default_value = parameters.get("count", 100)
    distribute.inputs["Seed"].default_value = parameters.get("seed", 0)

    # Instance on points
    instance = nodes.new("GeometryNodeInstanceOnPoints")
    instance.location = (200, 0)

    # Object to instance
    obj_info = nodes.new("GeometryNodeObjectInfo")
    obj_info.location = (0, -200)

    # Random scale
    random_value = nodes.new("FunctionNodeRandomValue")
    random_value.location = (0, -100)
    random_value.data_type = "FLOAT_VECTOR"
    scale_var = parameters.get("scale_variance", 0.1)
    random_value.inputs["Min"].default_value = (
        1 - scale_var,
        1 - scale_var,
        1 - scale_var,
    )
    random_value.inputs["Max"].default_value = (
        1 + scale_var,
        1 + scale_var,
        1 + scale_var,
    )

    # Random rotation
    rotate = nodes.new("FunctionNodeRandomValue")
    rotate.location = (0, -300)
    rotate.data_type = "FLOAT_VECTOR"
    rotate.inputs["Min"].default_value = (0, 0, 0)
    rotate.inputs["Max"].default_value = (6.28, 6.28, 6.28)  # 2*pi

    # Connect nodes
    links.new(input_node.outputs["Geometry"], distribute.inputs["Mesh"])
    links.new(distribute.outputs["Points"], instance.inputs["Points"])
    links.new(obj_info.outputs["Geometry"], instance.inputs["Instance"])
    links.new(random_value.outputs["Value"], instance.inputs["Scale"])
    links.new(rotate.outputs["Value"], instance.inputs["Rotation"])
    links.new(instance.outputs["Instances"], output_node.inputs["Geometry"])


def create_array_setup(nodes, links, input_node, output_node, parameters):
    """Create array/grid node setup."""

    # Mesh line for linear array
    mesh_line = nodes.new("GeometryNodeMeshLine")
    mesh_line.location = (0, 0)
    mesh_line.inputs["Count"].default_value = parameters.get("count", 10)
    mesh_line.inputs["Offset"].default_value = (
        parameters.get("offset_x", 2),
        parameters.get("offset_y", 0),
        parameters.get("offset_z", 0),
    )

    # Instance on points
    instance = nodes.new("GeometryNodeInstanceOnPoints")
    instance.location = (200, 0)

    # Transform for each instance
    transform = nodes.new("GeometryNodeTransform")
    transform.location = (400, 0)

    # Connect nodes
    links.new(mesh_line.outputs["Mesh"], instance.inputs["Points"])
    links.new(input_node.outputs["Geometry"], instance.inputs["Instance"])
    links.new(instance.outputs["Instances"], transform.inputs["Geometry"])
    links.new(transform.outputs["Geometry"], output_node.inputs["Geometry"])


def create_curve_setup(nodes, links, input_node, output_node, parameters):
    """Create curve-based geometry setup."""

    # Curve primitive
    curve_circle = nodes.new("GeometryNodeCurvePrimitiveCircle")
    curve_circle.location = (0, 0)
    curve_circle.inputs["Radius"].default_value = parameters.get("radius", 5)

    # Curve to mesh
    curve_to_mesh = nodes.new("GeometryNodeCurveToMesh")
    curve_to_mesh.location = (200, 0)

    # Profile curve
    profile = nodes.new("GeometryNodeCurvePrimitiveCircle")
    profile.location = (0, -200)
    profile.inputs["Radius"].default_value = parameters.get("profile_radius", 0.1)

    # Set material
    set_material = nodes.new("GeometryNodeSetMaterial")
    set_material.location = (400, 0)

    # Connect nodes
    links.new(curve_circle.outputs["Curve"], curve_to_mesh.inputs["Curve"])
    links.new(profile.outputs["Curve"], curve_to_mesh.inputs["Profile Curve"])
    links.new(curve_to_mesh.outputs["Mesh"], set_material.inputs["Geometry"])
    links.new(set_material.outputs["Geometry"], output_node.inputs["Geometry"])


def create_volume_setup(nodes, links, input_node, output_node, parameters):
    """Create volume/voxel-based setup."""

    # Volume cube
    volume_cube = nodes.new("GeometryNodeVolumeCube")
    volume_cube.location = (0, 0)
    volume_cube.inputs["Density"].default_value = parameters.get("density", 1.0)
    volume_cube.inputs["Size"].default_value = (
        parameters.get("size_x", 5),
        parameters.get("size_y", 5),
        parameters.get("size_z", 5),
    )

    # Volume to mesh
    volume_to_mesh = nodes.new("GeometryNodeVolumeToMesh")
    volume_to_mesh.location = (200, 0)
    volume_to_mesh.inputs["Threshold"].default_value = parameters.get("threshold", 0.1)

    # Smooth
    set_smooth = nodes.new("GeometryNodeSetShadeSmooth")
    set_smooth.location = (400, 0)

    # Connect nodes
    links.new(volume_cube.outputs["Volume"], volume_to_mesh.inputs["Volume"])
    links.new(volume_to_mesh.outputs["Mesh"], set_smooth.inputs["Geometry"])
    links.new(set_smooth.outputs["Geometry"], output_node.inputs["Geometry"])


def create_custom_setup(nodes, links, input_node, output_node, parameters):
    """Create custom node setup based on parameters."""

    # This is a flexible setup that can be extended
    # For now, create a simple subdivided mesh with displacement

    # Subdivision
    subdivide = nodes.new("GeometryNodeSubdivideMesh")
    subdivide.location = (0, 0)
    subdivide.inputs["Level"].default_value = parameters.get("subdivision_level", 2)

    # Noise texture for displacement
    noise = nodes.new("ShaderNodeTexNoise")
    noise.location = (0, -200)
    noise.inputs["Scale"].default_value = parameters.get("noise_scale", 5.0)
    noise.inputs["Detail"].default_value = parameters.get("noise_detail", 2.0)

    # Set position for displacement
    set_position = nodes.new("GeometryNodeSetPosition")
    set_position.location = (200, 0)

    # Vector math for displacement
    vector_math = nodes.new("ShaderNodeVectorMath")
    vector_math.location = (0, -100)
    vector_math.operation = "MULTIPLY"

    # Normal node
    normal = nodes.new("GeometryNodeInputNormal")
    normal.location = (-200, -100)

    # Connect nodes
    links.new(input_node.outputs["Geometry"], subdivide.inputs["Mesh"])
    links.new(subdivide.outputs["Mesh"], set_position.inputs["Geometry"])
    links.new(noise.outputs["Fac"], vector_math.inputs[1])
    links.new(normal.outputs["Normal"], vector_math.inputs[0])
    links.new(vector_math.outputs["Vector"], set_position.inputs["Offset"])
    links.new(set_position.outputs["Geometry"], output_node.inputs["Geometry"])


def create_procedural_texture(args, job_id):
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
        if texture_type == "noise":
            texture = nodes.new("ShaderNodeTexNoise")
            texture.location = (0, 0)
            texture.inputs["Scale"].default_value = parameters.get("scale", 5.0)
            texture.inputs["Detail"].default_value = parameters.get("detail", 2.0)
            texture.inputs["Roughness"].default_value = parameters.get("roughness", 0.5)

        elif texture_type == "voronoi":
            texture = nodes.new("ShaderNodeTexVoronoi")
            texture.location = (0, 0)
            texture.feature = parameters.get("feature", "F1")
            texture.inputs["Scale"].default_value = parameters.get("scale", 5.0)

        elif texture_type == "wave":
            texture = nodes.new("ShaderNodeTexWave")
            texture.location = (0, 0)
            texture.wave_type = parameters.get("wave_type", "BANDS")
            texture.inputs["Scale"].default_value = parameters.get("scale", 5.0)

        elif texture_type == "brick":
            texture = nodes.new("ShaderNodeTexBrick")
            texture.location = (0, 0)
            texture.inputs["Scale"].default_value = parameters.get("scale", 5.0)

        elif texture_type == "gradient":
            texture = nodes.new("ShaderNodeTexGradient")
            texture.location = (0, 0)
            texture.gradient_type = parameters.get("gradient_type", "LINEAR")

        else:
            # Default to checker
            texture = nodes.new("ShaderNodeTexChecker")
            texture.location = (0, 0)
            texture.inputs["Scale"].default_value = parameters.get("scale", 5.0)

        # Add texture coordinate
        tex_coord = nodes.new("ShaderNodeTexCoord")
        tex_coord.location = (-200, 0)

        # Connect nodes
        links.new(tex_coord.outputs["UV"], texture.inputs["Vector"])

        if hasattr(texture, "outputs") and "Color" in texture.outputs:
            links.new(texture.outputs["Color"], bsdf.inputs["Base Color"])
        elif hasattr(texture, "outputs") and "Fac" in texture.outputs:
            # For single value outputs, use as roughness
            links.new(texture.outputs["Fac"], bsdf.inputs["Roughness"])

        links.new(bsdf.outputs["BSDF"], output.inputs["Surface"])

        # Save project
        if "project" in args:
            bpy.ops.wm.save_mainfile()

        return True

    except Exception as e:
        print(f"Error creating procedural texture: {e}")
        return False


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

    with open(args_file, "r") as f:
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
