#!/usr/bin/env python3
"""Particle system tools for Blender."""

import os
import sys

import bpy

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from mcp_common import (  # noqa: E402  pylint: disable=wrong-import-position
    project_operation,
    require_object,
    run,
)


def add_particle_system(args):
    """Add an emitter (or hair) particle system to an object."""
    object_name = args["object_name"]
    particle_type = str(args.get("particle_type", "EMITTER")).upper()
    settings = dict(args.get("settings") or {})
    if "count" in args and "count" not in settings:
        settings["count"] = args["count"]
    if particle_type == "HAIR":
        return add_hair_system({"object_name": object_name, "settings": settings})
    if particle_type != "EMITTER":
        return {"success": False, "error": f"Unknown particle_type '{particle_type}' (use emitter or hair)"}

    obj = require_object(object_name)
    if obj.type != "MESH":
        return {"success": False, "error": f"Particles need a mesh emitter; '{object_name}' is a {obj.type}"}

    particle_name = f"ParticleSystem_{len(obj.particle_systems)}"
    obj.modifiers.new(particle_name, "PARTICLE_SYSTEM")
    psys = obj.particle_systems[-1]
    pset = psys.settings

    pset.type = "EMITTER"
    pset.count = int(settings.get("count", 1000))
    pset.frame_start = settings.get("frame_start", 1)
    pset.frame_end = settings.get("frame_end", 200)
    pset.lifetime = settings.get("lifetime", 50)
    pset.emit_from = settings.get("emit_from", "FACE")

    physics_type = str(settings.get("physics_type", "NEWTONIAN")).upper()
    if physics_type in ("NEWTONIAN", "NEWTON"):
        pset.physics_type = "NEWTON"
        pset.mass = settings.get("mass", 1.0)
        pset.normal_factor = settings.get("velocity", 2.0)
        pset.factor_random = settings.get("velocity_random", 0.5)
        pset.effector_weights.gravity = settings.get("gravity", 1.0)
        pset.drag_factor = settings.get("drag", 0.0)
        pset.brownian_factor = settings.get("brownian", 0.0)
    elif physics_type == "FLUID":
        pset.physics_type = "FLUID"
        pset.fluid.solver = "CLASSICAL"
        pset.fluid.stiffness = settings.get("stiffness", 1.0)
        pset.fluid.linear_viscosity = settings.get("viscosity", 1.0)
        pset.fluid.buoyancy = settings.get("buoyancy", 0.0)
    elif physics_type == "NO":
        pset.physics_type = "NO"
    else:
        return {"success": False, "error": f"Unknown physics_type '{physics_type}' (NEWTONIAN, FLUID, NO)"}

    pset.particle_size = settings.get("size", 0.05)
    pset.size_random = settings.get("size_random", 0.0)
    pset.render_type = str(settings.get("render_type", "HALO")).upper()
    if pset.render_type == "OBJECT":
        render_object = settings.get("render_object")
        if not render_object or render_object not in bpy.data.objects:
            return {"success": False, "error": f"render_object '{render_object}' not found"}
        pset.instance_object = bpy.data.objects[render_object]

    return {"success": True, "particle_system": psys.name, "count": pset.count}


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
        pset.child_percent = settings.get("children_count", 10)
        pset.rendered_child_count = settings.get("rendered_children", 100)
        pset.child_radius = settings.get("child_radius", 0.2)

    # Hair shape
    pset.use_hair_bspline = True
    pset.render_step = 3

    return {"success": True, "hair_system": hair_name}


def add_smoke_domain(args):
    """Add a gas fluid domain box."""
    domain_name = args.get("domain_name", "SmokeDomain")
    size = args.get("size", [5, 5, 5])
    location = args.get("location", [0, 0, 2.5])
    resolution = int(args.get("resolution", 32))

    mesh = bpy.data.meshes.new(domain_name)
    domain = bpy.data.objects.new(domain_name, mesh)
    bpy.context.scene.collection.objects.link(domain)
    import bmesh  # pylint: disable=import-outside-toplevel

    bm = bmesh.new()
    bmesh.ops.create_cube(bm, size=1.0)
    bm.to_mesh(mesh)
    bm.free()
    domain.location = location
    domain.scale = size
    domain.display_type = "WIRE"

    modifier = domain.modifiers.new("Fluid", "FLUID")
    modifier.fluid_type = "DOMAIN"
    domain_settings = modifier.domain_settings
    domain_settings.domain_type = "GAS"
    domain_settings.resolution_max = resolution
    domain_settings.use_adaptive_domain = True
    domain_settings.cache_frame_start = 1
    domain_settings.cache_frame_end = 250

    return {"success": True, "domain": domain.name}


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


def add_smoke_simulation(args):
    """Turn an object into a smoke/fire emitter inside a new gas domain."""
    object_name = args["object_name"]
    smoke_type = str(args.get("smoke_type", "smoke")).upper()
    settings = args.get("settings") or {}
    flow_type = {"SMOKE": "SMOKE", "FIRE": "FIRE", "BOTH": "BOTH"}.get(smoke_type)
    if flow_type is None:
        return {"success": False, "error": f"Unknown smoke_type '{smoke_type}' (smoke, fire, both)"}
    if not bpy.app.build_options.fluid:
        return {"success": False, "error": "This Blender build has no fluid simulation support"}

    obj = require_object(object_name)
    if obj.type != "MESH":
        return {"success": False, "error": f"Smoke emitters must be meshes; '{object_name}' is a {obj.type}"}

    flow_mod = next((m for m in obj.modifiers if m.type == "FLUID"), None)
    if flow_mod is None:
        flow_mod = obj.modifiers.new("Fluid", "FLUID")
    elif flow_mod.fluid_type == "DOMAIN":
        return {"success": False, "error": f"'{object_name}' is already a fluid domain"}
    flow_mod.fluid_type = "FLOW"
    flow = flow_mod.flow_settings
    flow.flow_type = flow_type
    flow.flow_behavior = "INFLOW"
    flow.density = settings.get("density", 1.0)
    flow.temperature = settings.get("temperature", 1.0)
    if flow_type in ("FIRE", "BOTH"):
        flow.fuel_amount = settings.get("fuel", 1.0)
    if "color" in settings:
        flow.smoke_color = settings["color"][:3]

    # Domain: a box around the emitter, taller than wide so the plume can rise.
    size = settings.get("domain_size")
    dims = obj.dimensions
    if size is None:
        size = [max(dims.x * 3, 2.0), max(dims.y * 3, 2.0), max(dims.z * 6, 4.0)]
    center = obj.matrix_world.translation
    location = settings.get("domain_location") or [center.x, center.y, center.z + size[2] / 2 - dims.z]
    domain_args = {
        "domain_name": settings.get("domain_name", f"{obj.name}_SmokeDomain"),
        "size": size,
        "location": location,
        "resolution": settings.get("resolution", 32),
    }
    domain_result = add_smoke_domain(domain_args)
    domain = bpy.data.objects[domain_result["domain"]]
    domain_settings = domain.modifiers["Fluid"].domain_settings
    if flow_type in ("FIRE", "BOTH"):
        domain_settings.use_noise = bool(settings.get("use_noise", True))
    if bpy.app.build_options.openvdb:
        domain_settings.cache_data_format = "OPENVDB"

    return {"success": True, "emitter": obj.name, "domain": domain.name, "smoke_type": smoke_type.lower()}


def main():
    """Dispatch the requested operation (see mcp_common.run)."""
    run(
        {
            "add_particle_system": project_operation(add_particle_system),
            "add_hair_system": project_operation(add_hair_system),
            "add_smoke_simulation": project_operation(add_smoke_simulation),
            "add_smoke_domain": project_operation(add_smoke_domain),
            "add_smoke_emitter": project_operation(add_smoke_emitter),
            "configure_particle_forces": project_operation(configure_particle_forces),
        }
    )


if __name__ == "__main__":
    main()
