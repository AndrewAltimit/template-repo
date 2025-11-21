#!/usr/bin/env python3
"""Particle system tools for Blender."""

import json
import sys
from pathlib import Path

import bpy


def add_particle_system(args):
    """Add particle system to an object."""
    object_name = args["object_name"]
    particle_type = args.get("particle_type", "EMITTER")
    settings = args.get("settings", {})

    # Get the object
    if object_name not in bpy.data.objects:
        return {"success": False, "error": f"Object '{object_name}' not found"}

    obj = bpy.data.objects[object_name]

    # Add particle system modifier
    particle_name = f"ParticleSystem_{len(obj.particle_systems)}"
    obj.modifiers.new(particle_name, "PARTICLE_SYSTEM")

    # Get the particle system and settings
    psys = obj.particle_systems[-1]
    pset = psys.settings

    # Configure particle settings
    pset.type = particle_type
    pset.count = settings.get("count", 1000)
    pset.frame_start = settings.get("frame_start", 1)
    pset.frame_end = settings.get("frame_end", 200)
    pset.lifetime = settings.get("lifetime", 50)
    pset.emit_from = settings.get("emit_from", "FACE")

    # Physics settings
    physics_type = settings.get("physics_type", "NEWTONIAN")
    if physics_type == "NEWTONIAN":
        pset.physics_type = "NEWTON"
        pset.mass = settings.get("mass", 1.0)
        pset.normal_factor = settings.get("velocity", 2.0)
        pset.factor_random = settings.get("velocity_random", 0.5)
        pset.gravity = settings.get("gravity", 1.0)
        pset.drag_factor = settings.get("drag", 0.0)
        pset.brownian_factor = settings.get("brownian", 0.0)
    elif physics_type == "FLUID":
        pset.physics_type = "FLUID"
        pset.fluid.solver = "CLASSICAL"
        pset.fluid.stiffness = settings.get("stiffness", 1.0)
        pset.fluid.viscosity = settings.get("viscosity", 1.0)
        pset.fluid.buoyancy = settings.get("buoyancy", 0.0)
    elif physics_type == "NO":
        pset.physics_type = "NO"

    # Display settings
    pset.particle_size = settings.get("size", 0.05)
    pset.size_random = settings.get("size_random", 0.0)

    # Render settings
    pset.render_type = settings.get("render_type", "HALO")
    if pset.render_type == "OBJECT":
        render_object = settings.get("render_object")
        if render_object and render_object in bpy.data.objects:
            pset.instance_object = bpy.data.objects[render_object]

    return {"success": True, "particle_system": particle_name}


def add_hair_system(args):
    """Add hair particle system to an object."""
    object_name = args["object_name"]
    settings = args.get("settings", {})

    # Get the object
    if object_name not in bpy.data.objects:
        return {"success": False, "error": f"Object '{object_name}' not found"}

    obj = bpy.data.objects[object_name]

    # Add particle system modifier
    hair_name = f"HairSystem_{len(obj.particle_systems)}"
    obj.modifiers.new(hair_name, "PARTICLE_SYSTEM")

    # Get the particle system and settings
    psys = obj.particle_systems[-1]
    pset = psys.settings

    # Configure hair settings
    pset.type = "HAIR"
    pset.count = settings.get("count", 1000)
    pset.hair_length = settings.get("length", 0.25)
    pset.hair_step = settings.get("segments", 5)

    # Hair dynamics
    if settings.get("use_dynamics", False):
        pset.use_hair_dynamics = True
        pset.mass = settings.get("mass", 0.3)
        pset.stiffness = settings.get("stiffness", 0.5)
        pset.damping = settings.get("damping", 0.1)

    # Children
    if settings.get("use_children", True):
        pset.child_type = "INTERPOLATED"
        pset.child_nbr = settings.get("children_count", 10)
        pset.rendered_child_count = settings.get("rendered_children", 100)
        pset.child_radius = settings.get("child_radius", 0.2)

    # Hair shape
    pset.use_hair_bspline = True
    pset.render_step = 3

    return {"success": True, "hair_system": hair_name}


def add_smoke_domain(args):
    """Add smoke domain for simulation."""
    domain_name = args.get("domain_name", "SmokeDomain")
    size = args.get("size", [5, 5, 5])
    location = args.get("location", [0, 0, 2.5])
    resolution = args.get("resolution", 32)

    # Create domain cube
    bpy.ops.mesh.primitive_cube_add(size=1, location=location)
    domain = bpy.context.active_object
    domain.name = domain_name
    domain.scale = size

    # Add fluid modifier as domain
    domain.modifiers.new("Fluid", "FLUID")
    domain.modifiers["Fluid"].fluid_type = "DOMAIN"

    # Configure domain settings
    domain_settings = domain.modifiers["Fluid"].domain_settings
    domain_settings.domain_type = "GAS"
    domain_settings.resolution_max = resolution
    domain_settings.use_adaptive_domain = True

    # Cache settings
    domain_settings.cache_frame_start = 1
    domain_settings.cache_frame_end = 250

    return {"success": True, "domain": domain_name}


def add_smoke_emitter(args):
    """Add smoke emitter to an object."""
    object_name = args["object_name"]
    simulation_type = args.get("simulation_type", "SMOKE")
    settings = args.get("settings", {})

    # Get the object
    if object_name not in bpy.data.objects:
        return {"success": False, "error": f"Object '{object_name}' not found"}

    obj = bpy.data.objects[object_name]

    # Add fluid modifier as flow
    obj.modifiers.new("Fluid", "FLUID")
    obj.modifiers["Fluid"].fluid_type = "FLOW"

    # Configure flow settings
    flow_settings = obj.modifiers["Fluid"].flow_settings
    flow_settings.flow_type = "SMOKE" if simulation_type != "FIRE" else "FIRE"
    flow_settings.flow_behavior = "INFLOW"

    # Emission settings
    flow_settings.density = settings.get("density", 1.0)
    flow_settings.temperature = settings.get("temperature", 1.0)
    flow_settings.smoke_color = settings.get("color", [0.7, 0.7, 0.7])
    flow_settings.fuel_amount = settings.get("fuel", 1.0) if simulation_type == "FIRE" else 0

    # Initial velocity
    flow_settings.use_initial_velocity = settings.get("use_initial_velocity", True)
    flow_settings.velocity_factor = settings.get("velocity", 1.0)

    return {"success": True, "emitter": object_name}


def configure_particle_forces(args):
    """Add force fields for particle interaction."""
    force_type = args["force_type"]
    location = args.get("location", [0, 0, 0])
    strength = args.get("strength", 1.0)
    settings = args.get("settings", {})

    # Create empty for force field
    bpy.ops.object.empty_add(type="PLAIN_AXES", location=location)
    force_obj = bpy.context.active_object
    force_obj.name = f"Force_{force_type}"

    # Add force field
    force_obj.field.type = force_type
    force_obj.field.strength = strength

    # Configure specific force settings
    if force_type == "WIND":
        force_obj.field.flow = settings.get("flow", 1.0)
        force_obj.field.noise = settings.get("noise", 0.0)
    elif force_type == "VORTEX":
        force_obj.field.inflow = settings.get("inflow", 1.0)
    elif force_type == "TURBULENCE":
        force_obj.field.size = settings.get("size", 1.0)
        force_obj.field.flow = settings.get("flow", 1.0)
    elif force_type == "DRAG":
        force_obj.field.linear_drag = settings.get("linear", 1.0)
        force_obj.field.quadratic_drag = settings.get("quadratic", 1.0)

    # Falloff
    force_obj.field.falloff_type = settings.get("falloff_type", "SPHERE")
    force_obj.field.falloff_power = settings.get("falloff_power", 2.0)
    force_obj.field.distance_max = settings.get("distance_max", 0.0)

    return {"success": True, "force_field": force_obj.name}


def main():
    """Main entry point for particle tools."""
    # Get arguments from command line
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument("--args", type=str, required=True)
    args = parser.parse_args()

    # Parse JSON arguments
    script_args = json.loads(args.args)

    # Load the project file
    project_path = script_args["project"]
    if Path(project_path).exists():
        bpy.ops.wm.open_mainfile(filepath=project_path)
    else:
        return {"success": False, "error": f"Project file not found: {project_path}"}

    # Execute the operation
    operation = script_args["operation"]

    if operation == "add_particle_system":
        result = add_particle_system(script_args)
    elif operation == "add_hair_system":
        result = add_hair_system(script_args)
    elif operation == "add_smoke_domain":
        result = add_smoke_domain(script_args)
    elif operation == "add_smoke_emitter":
        result = add_smoke_emitter(script_args)
    elif operation == "configure_particle_forces":
        result = configure_particle_forces(script_args)
    else:
        result = {"success": False, "error": f"Unknown operation: {operation}"}

    # Save the file
    if result.get("success"):
        bpy.ops.wm.save_mainfile(filepath=project_path)

    # Output result
    print(json.dumps(result))
    sys.exit(0 if result.get("success") else 1)


if __name__ == "__main__":
    main()
